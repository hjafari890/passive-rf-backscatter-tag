"""USRP-2900 Dual-Mode Backscatter Validation Pipeline CLI.

Supports:
- Mode 1: Continuous Wave (CW) Tone validation
- Mode 2: Ambient Wi-Fi Channel (2.437 GHz / Ch 6) validation
- Seamless fallback to physics-grounded mock USRP if hardware is offline
- Step metrics: Delta P_rx, Delta |V_rx|, SCNR
- Context-manager safe .npz persistence to avoid Windows file locks
- Publication figure generation (300 DPI)
"""

from __future__ import annotations

import argparse
import datetime
import os
import sys
import time
from typing import Any, Dict, Optional

import numpy as np

try:
    from .mock_usrp import (
        HAS_UHD,
        MockMultiUSRP,
        MockRXMetadata,
        MockRXMetadataErrorCode,
        MockStreamArgs,
        MockStreamCMD,
        MockStreamMode,
        MockTXMetadata,
        MockTuneRequest,
    )
    from .backscatter_metrics import (
        compute_complex_vector_distance,
        compute_differential_power,
        compute_scnr,
        detect_step_transition,
        detect_wifi_packets,
        load_backscatter_npz,
        save_backscatter_npz,
    )
    from .plot_backscatter_results import (
        plot_cw_iq_trajectory,
        plot_cw_step_response,
        plot_wifi_ambient_backscatter,
        plot_wifi_iq_constellation,
    )
except ImportError:
    import sys
    from pathlib import Path
    _script_dir = Path(__file__).resolve().parent
    _proj_root = _script_dir.parent
    if str(_proj_root) not in sys.path:
        sys.path.insert(0, str(_proj_root))
    if str(_script_dir) not in sys.path:
        sys.path.insert(0, str(_script_dir))
    from mock_usrp import (
        HAS_UHD,
        MockMultiUSRP,
        MockRXMetadata,
        MockRXMetadataErrorCode,
        MockStreamArgs,
        MockStreamCMD,
        MockStreamMode,
        MockTXMetadata,
        MockTuneRequest,
    )
    from backscatter_metrics import (
        compute_complex_vector_distance,
        compute_differential_power,
        compute_scnr,
        detect_step_transition,
        detect_wifi_packets,
        load_backscatter_npz,
        save_backscatter_npz,
    )
    from plot_backscatter_results import (
        plot_cw_iq_trajectory,
        plot_cw_step_response,
        plot_wifi_ambient_backscatter,
        plot_wifi_iq_constellation,
    )

if HAS_UHD:
    import uhd


def parse_arguments(args: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="USRP-2900 Dual-Mode Backscatter Validation Pipeline",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--mode",
        choices=["cw", "wifi"],
        default="cw",
        help="Validation mode: 'cw' (Mode 1: CW carrier) or 'wifi' (Mode 2: ambient Wi-Fi)",
    )
    parser.add_argument(
        "--freq",
        type=float,
        default=None,
        help="RF carrier frequency in Hz (defaults: 2.44 GHz for CW, 2.437 GHz for Wi-Fi)",
    )
    parser.add_argument(
        "--rate",
        type=float,
        default=2.0e6,
        help="Sample rate in Samples/s (default: 2.0 MSps)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=3.0,
        help="Acquisition duration in seconds (default: 3.0 s)",
    )
    parser.add_argument(
        "--tx-gain",
        type=float,
        default=50.0,
        help="TX gain in dB (0.0 to 89.8 dB; inactive in wifi mode)",
    )
    parser.add_argument(
        "--rx-gain",
        type=float,
        default=30.0,
        help="RX gain in dB (0.0 to 76.0 dB, AGC is disabled)",
    )
    parser.add_argument(
        "--switch-time",
        type=float,
        default=None,
        help="Tag load switch timestamp in seconds (default: duration / 2)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="sdr_pipeline/output/",
        help="Output directory for captures and figures",
    )
    parser.add_argument(
        "--save-raw",
        action="store_true",
        default=True,
        help="Save raw I/Q samples, metadata, and computed metrics to .npz",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Force software emulation mock harness even if physical USRP is connected",
    )
    parser.add_argument(
        "--hardware",
        action="store_true",
        help="Force physical USRP hardware; exit with error if hardware is offline",
    )

    parsed = parser.parse_args(args)
    
    # Apply mode-dependent default frequencies
    if parsed.freq is None:
        parsed.freq = 2.44e9 if parsed.mode == "cw" else 2.437e9

    # Default switch time: duration / 2 or 1.0 s
    if parsed.switch_time is None:
        parsed.switch_time = min(1.0, parsed.duration / 2.0)

    return parsed


def initialize_transceiver(args: argparse.Namespace) -> tuple[Any, bool]:
    """Connect to physical USRP or fall back to mock emulator."""
    using_mock = False

    if args.mock:
        print("[INFO] --mock flag requested. Initializing MockMultiUSRP software emulator.")
        usrp = MockMultiUSRP(mode=args.mode, switch_time=args.switch_time)
        using_mock = True
        return usrp, using_mock

    # Attempt physical hardware initialization if UHD is present
    if HAS_UHD and not args.mock:
        try:
            print("[INFO] Probing for physical USRP device (type=b200)...")
            usrp = uhd.usrp.MultiUSRP("type=b200")
            print("[SUCCESS] Connected to physical USRP hardware.")
            return usrp, False
        except Exception as exc:
            if args.hardware:
                print(f"[ERROR] Physical USRP required by --hardware, but connection failed: {exc}", file=sys.stderr)
                sys.exit(1)
            print(f"[INFO] Physical USRP not detected ({exc}). Falling back to MockMultiUSRP software emulator.")
            usrp = MockMultiUSRP(mode=args.mode, switch_time=args.switch_time)
            using_mock = True
            return usrp, using_mock
    else:
        if args.hardware:
            print("[ERROR] --hardware specified but UHD Python binding is not installed.", file=sys.stderr)
            sys.exit(1)
        print("[INFO] UHD not available. Falling back to MockMultiUSRP software emulator.")
        usrp = MockMultiUSRP(mode=args.mode, switch_time=args.switch_time)
        using_mock = True
        return usrp, using_mock


def configure_usrp(usrp: Any, args: argparse.Namespace, using_mock: bool) -> None:
    """Configure RF front-end frequencies, sample rates, gains, antennas, and AGC."""
    # 1. Sample rate
    usrp.set_rx_rate(args.rate, 0)
    usrp.set_tx_rate(args.rate, 0)

    # 2. Carrier frequency
    tune_req = (
        MockTuneRequest(args.freq)
        if using_mock
        else uhd.types.TuneRequest(args.freq)
    )
    usrp.set_rx_freq(tune_req, 0)
    usrp.set_tx_freq(tune_req, 0)

    # 3. Antennas (Bistatic configuration: TX on TX/RX, RX on RX2)
    usrp.set_rx_antenna("RX2", 0)
    usrp.set_tx_antenna("TX/RX", 0)

    # 4. Gains
    usrp.set_rx_gain(args.rx_gain, 0)
    tx_gain_val = args.tx_gain if args.mode == "cw" else 0.0
    usrp.set_tx_gain(tx_gain_val, 0)

    # 5. Strictly disable RX AGC to prevent distorting tag step response
    usrp.set_rx_agc(False, 0)


def acquire_samples(
    usrp: Any,
    args: argparse.Namespace,
    using_mock: bool,
) -> np.ndarray:
    """Execute streaming acquisition for Mode 1 (CW) or Mode 2 (Ambient Wi-Fi)."""
    stream_args = (
        MockStreamArgs("fc32", "sc16")
        if using_mock
        else uhd.usrp.StreamArgs("fc32", "sc16")
    )
    stream_args.channels = [0]

    rx_streamer = usrp.get_rx_stream(stream_args)
    tx_streamer = usrp.get_tx_stream(stream_args) if args.mode == "cw" else None

    num_samples_to_rx = int(args.rate * args.duration)
    chunk_size = 4096
    recv_buffer = np.zeros((1, chunk_size), dtype=np.complex64)
    rx_buffer = np.zeros(num_samples_to_rx, dtype=np.complex64)

    # Prepare metadata structs
    rx_md = MockRXMetadata() if using_mock else uhd.types.RXMetadata()
    tx_md = MockTXMetadata() if using_mock else uhd.types.TXMetadata()
    if tx_md is not None:
        tx_md.start_of_burst = True
        tx_md.end_of_burst = False

    # Issue RX Start Command
    stream_cmd_type = MockStreamCMD if using_mock else uhd.types.StreamCMD
    stream_mode_start = (
        MockStreamMode.start_cont if using_mock else uhd.types.StreamMode.start_cont
    )
    cmd = stream_cmd_type(stream_mode_start)
    cmd.stream_now = True
    rx_streamer.issue_stream_cmd(cmd)

    # CW baseband normalized amplitude (0.707 = -3 dBFS to prevent DAC saturation)
    cw_chunk = np.ones((1, chunk_size), dtype=np.complex64) * 0.707

    samples_collected = 0
    try:
        while samples_collected < num_samples_to_rx:
            # Transmit CW chunk if in CW mode
            if args.mode == "cw" and tx_streamer is not None:
                tx_streamer.send(cw_chunk, tx_md)
                tx_md.start_of_burst = False

            # Receive backscatter chunk
            num_rx = rx_streamer.recv(recv_buffer, rx_md, timeout=1.0)
            
            # Check for error codes
            err_code = getattr(rx_md, "error_code", 0)
            err_none = (
                MockRXMetadataErrorCode.none
                if using_mock
                else uhd.types.RXMetadataErrorCode.none
            )
            if err_code != err_none:
                # Log overflow warning without crashing
                continue

            if num_rx > 0:
                end_idx = min(samples_collected + num_rx, num_samples_to_rx)
                rx_buffer[samples_collected:end_idx] = recv_buffer[0, : end_idx - samples_collected]
                samples_collected = end_idx

    finally:
        # Stop streams cleanly
        if args.mode == "cw" and tx_streamer is not None:
            tx_md.end_of_burst = True
            try:
                tx_streamer.send(np.zeros((1, 100), dtype=np.complex64), tx_md)
            except Exception:
                pass

        stream_mode_stop = (
            MockStreamMode.stop_cont if using_mock else uhd.types.StreamMode.stop_cont
        )
        stop_cmd = stream_cmd_type(stream_mode_stop)
        rx_streamer.issue_stream_cmd(stop_cmd)

    return rx_buffer


def run_backscatter(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
    """Execute complete SDR backscatter acquisition, signal processing, and reporting."""
    if args is None:
        args = parse_arguments()

    print("=" * 72)
    print(" USRP-2900 Dual-Mode Backscatter Validation Pipeline")
    print("=" * 72)
    print(f" Mode              : {args.mode.upper()} {'(CW Carrier Test)' if args.mode == 'cw' else '(Ambient Wi-Fi Test)'}")
    print(f" Carrier Frequency : {args.freq / 1e6:.3f} MHz")
    print(f" Sample Rate       : {args.rate / 1e6:.3f} MSps")
    print(f" Capture Duration  : {args.duration:.2f} s ({int(args.rate * args.duration):,} samples)")
    print(f" TX Gain (TX/RX)   : {args.tx_gain:.1f} dB" if args.mode == "cw" else " TX Port (TX/RX)   : DISABLED (Passive Ambient)")
    print(f" RX Gain (RX2)     : {args.rx_gain:.1f} dB (AGC: DISABLED)")
    print(f" Output Directory  : {args.output_dir}")
    print("=" * 72)

    os.makedirs(args.output_dir, exist_ok=True)

    # 1. Initialize transceiver
    usrp, using_mock = initialize_transceiver(args)

    # 2. Configure RF parameters
    configure_usrp(usrp, args, using_mock)
    if not using_mock:
        time.sleep(0.5)  # Allow physical PLL lock

    # 3. Stream & acquire samples
    print("[1/4] Acquiring baseband I/Q samples...")
    t0 = time.time()
    samples = acquire_samples(usrp, args, using_mock)
    elapsed = time.time() - t0
    print(f"[2/4] Acquired {len(samples):,} samples in {elapsed:.2f} s.")

    # 4. Signal Processing & Metrics Calculation
    print("[3/4] Computing differential backscatter metrics...")
    results: Dict[str, Any] = {
        "mode": args.mode,
        "sample_rate": args.rate,
        "center_freq": args.freq,
        "duration": args.duration,
        "tx_gain": args.tx_gain,
        "rx_gain": args.rx_gain,
        "using_mock": using_mock,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    if args.mode == "cw":
        switch_idx, s1, s2 = detect_step_transition(samples, args.rate, guard_band_ms=10.0)
        delta_p_lin, delta_p_db = compute_differential_power(s1, s2)
        delta_v, v1_cen, v2_cen, delta_theta = compute_complex_vector_distance(s1, s2)
        scnr_lin, scnr_db = compute_scnr(s1, s2)

        results.update({
            "switch_sample": switch_idx,
            "switch_time_s": switch_idx / args.rate,
            "delta_p_rx_linear": delta_p_lin,
            "delta_p_rx_db": delta_p_db,
            "delta_v_rx": delta_v,
            "v1_centroid": v1_cen,
            "v2_centroid": v2_cen,
            "delta_theta_deg": delta_theta,
            "scnr_linear": scnr_lin,
            "scnr_db": scnr_db,
        })

        print("-" * 72)
        print(f" Tag Step Switch Instant      : {results['switch_time_s']*1e3:.2f} ms (sample #{switch_idx:,})")
        print(f" State 1 Centroid (50 Ohm)    : {v1_cen.real:+.4f} + {v1_cen.imag:+.4f}j  (|V1| = {abs(v1_cen):.4f})")
        print(f" State 2 Centroid (Short)     : {v2_cen.real:+.4f} + {v2_cen.imag:+.4f}j  (|V2| = {abs(v2_cen):.4f})")
        print(f" Differential Power Delta     : {delta_p_db:+.2f} dB (Linear: {delta_p_lin:+.4e})")
        print(f" Centroid Vector Distance     : Delta |V_rx| = {delta_v:.4f} (Phase Shift: {delta_theta:+.1f} deg)")
        print(f" Step-to-Clutter-and-Noise    : SCNR = {scnr_db:.1f} dB (Linear: {scnr_lin:.1f})")
        print("-" * 72)

        # Plot CW figures
        fig1_path = os.path.join(args.output_dir, "cw_step_response.png")
        fig2_path = os.path.join(args.output_dir, "cw_iq_trajectory.png")
        plot_cw_step_response(samples, args.rate, fig1_path, switch_idx=switch_idx)
        plot_cw_iq_trajectory(samples, args.rate, fig2_path, switch_idx=switch_idx)
        results["fig_step_response"] = fig1_path
        results["fig_iq_trajectory"] = fig2_path

    else:  # wifi mode
        switch_idx = len(samples) // 2
        wifi_metrics = detect_wifi_packets(samples, args.rate)
        s1 = samples[:switch_idx]
        s2 = samples[switch_idx:]
        delta_p_lin, delta_p_db = compute_differential_power(s1, s2)
        delta_v, v1_cen, v2_cen, delta_theta = compute_complex_vector_distance(s1, s2)
        delta_v_beacon = wifi_metrics.get("delta_v_beacon", delta_v)
        v1_cen_beacon = wifi_metrics.get("v_beacon_s1", v1_cen)
        v2_cen_beacon = wifi_metrics.get("v_beacon_s2", v2_cen)

        results.update({
            "switch_sample": switch_idx,
            "switch_time_s": switch_idx / args.rate,
            "wifi_num_bursts": wifi_metrics["num_bursts"],
            "delta_beacon_db": wifi_metrics["delta_beacon_db"],
            "mean_beacon_s1": wifi_metrics["mean_beacon_s1"],
            "mean_beacon_s2": wifi_metrics["mean_beacon_s2"],
            "delta_p_rx_db": delta_p_db,
            "delta_v_rx": delta_v_beacon,
            "v1_centroid": v1_cen_beacon,
            "v2_centroid": v2_cen_beacon,
        })

        print("-" * 72)
        print(f" Detected Wi-Fi Bursts        : {wifi_metrics['num_bursts']} total packets")
        print(f" Beacon Energy State 1        : {wifi_metrics['mean_beacon_s1']:.5e}")
        print(f" Beacon Energy State 2        : {wifi_metrics['mean_beacon_s2']:.5e}")
        print(f" Beacon Energy Delta          : Delta P_beacon = {wifi_metrics['delta_beacon_db']:+.2f} dB")
        print(f" Beacon Vector Shift          : Delta |V_rx| = {delta_v_beacon:.5f}")
        print("-" * 72)

        # Plot Wi-Fi figures
        fig1_path = os.path.join(args.output_dir, "wifi_ambient_backscatter.png")
        fig2_path = os.path.join(args.output_dir, "wifi_iq_constellation.png")
        plot_wifi_ambient_backscatter(samples, args.rate, fig1_path, switch_idx=switch_idx)
        plot_wifi_iq_constellation(samples, args.rate, fig2_path, switch_idx=switch_idx)
        results["fig_ambient_backscatter"] = fig1_path
        results["fig_iq_constellation"] = fig2_path

    # 5. Data Persistence
    if args.save_raw:
        print("[4/4] Archiving raw baseband data and metrics...")
        npz_filename = f"backscatter_{args.mode}_valid.npz"
        npy_filename = f"backscatter_{args.mode}_raw.npy"
        npz_path = os.path.join(args.output_dir, npz_filename)
        npy_path = os.path.join(args.output_dir, npy_filename)

        archive_dict = {
            "iq": samples,
            "sample_rate": args.rate,
            "center_freq": args.freq,
            "mode": args.mode,
            "tx_gain": args.tx_gain,
            "rx_gain": args.rx_gain,
            "duration": args.duration,
            "switch_sample": switch_idx,
            "delta_p_rx_db": results.get("delta_p_rx_db", 0.0),
            "delta_v_rx": results.get("delta_v_rx", 0.0),
            "timestamp": results["timestamp"],
        }
        if "scnr_db" in results:
            archive_dict["scnr_db"] = results["scnr_db"]

        # Save using context-manager safe functions
        save_backscatter_npz(npz_path, archive_dict)
        with open(npy_path, "wb") as f:
            np.save(f, samples)

        results["npz_path"] = npz_path
        results["npy_path"] = npy_path
        print(f" Saved compressed dataset : {npz_path}")
        print(f" Saved raw I/Q samples    : {npy_path}")

    print("=" * 72)
    print(" Validation acquisition completed successfully.")
    print("=" * 72)

    return results


def main() -> None:
    """CLI entrypoint."""
    args = parse_arguments()
    run_backscatter(args)


if __name__ == "__main__":
    main()
