"""Background SDR Streaming Worker Thread for Real-Time Backscatter Acquisition.

Manages USRP streaming via UHD or physics-accurate MockMultiUSRP, continuously
computing real-time power, complex I/Q constellation centroids, FFT power spectra,
and tag state classification without blocking the PyQt GUI event loop.
"""

from __future__ import annotations

import os
import queue
import time
from typing import Any, Dict, Optional, Tuple

import numpy as np
import scipy.io
import scipy.signal

from PyQt5.QtCore import QThread, pyqtSignal

# Import local backscatter utilities
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
        compute_moving_average_power,
        compute_scnr,
    )
except ImportError:
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
        compute_moving_average_power,
        compute_scnr,
    )

if HAS_UHD:
    import uhd


class SDRWorker(QThread):
    """Asynchronous SDR worker thread for high-FPS acquisition and DSP analysis."""

    # Qt Signals for GUI updates
    sig_frame_ready = pyqtSignal(dict)
    sig_hw_status = pyqtSignal(str, bool)  # (status_message, is_hardware)
    sig_state_transition = pyqtSignal(str, float, float)  # (state_name, delta_p, delta_v)
    sig_snapshot_saved = pyqtSignal(str)
    sig_error = pyqtSignal(str)

    def __init__(
        self,
        center_freq: float = 2.44e9,
        sample_rate: float = 2.0e6,
        rx_gain: float = 45.0,
        tx_gain: float = 60.0,
        carrier_mode: str = "cw",  # "cw" or "wifi"
        force_mock: bool = False,
        parent: Optional[Any] = None,
    ) -> None:
        super().__init__(parent)
        self.center_freq = center_freq
        self.sample_rate = sample_rate
        self.rx_gain = rx_gain
        self.tx_gain = tx_gain
        self.carrier_mode = carrier_mode
        self.force_mock = force_mock

        self._running = False
        self._command_queue: queue.Queue = queue.Queue()

        # Calibration state
        self.baseline_offset: complex = 0.0 + 0.0j
        self.calibrated_p1_db: Optional[float] = None
        self.calibrated_p2_db: Optional[float] = None

        # State tracking
        self.current_state: str = "STATE 1: ABSORBING (50 Ω)"
        self.last_transition_time: float = time.time()

        # Ring buffer for strip chart (keeps up to 10 seconds of power history)
        self.history_len = 300
        self.power_history = np.full(self.history_len, -80.0, dtype=np.float32)
        self.time_history = np.linspace(-10.0, 0.0, self.history_len, dtype=np.float32)

        # Snapshot capture buffer
        self._pending_snapshot: Optional[Dict[str, Any]] = None

        # Hardware connection handles
        self.usrp: Any = None
        self.is_hardware: bool = False

    def request_command(self, cmd_type: str, **kwargs) -> None:
        """Enqueue a thread-safe control command for the SDR worker."""
        self._command_queue.put({"type": cmd_type, **kwargs})

    def request_snapshot(self, export_dir: str, base_filename: str) -> None:
        """Request an instantaneous high-fidelity measurement export."""
        self._command_queue.put({
            "type": "snapshot",
            "export_dir": export_dir,
            "base_filename": base_filename,
        })

    def calibrate_baseline(self) -> None:
        """Request software carrier leakage cancellation / baseline zeroing."""
        self._command_queue.put({"type": "calibrate"})

    def stop(self) -> None:
        """Signal the worker thread to terminate cleanly."""
        self._running = False
        self.wait(2000)

    def _init_transceiver(self) -> None:
        """Initialize USRP hardware or physics-grounded mock fallback."""
        if not self.force_mock and HAS_UHD:
            try:
                self.sig_hw_status.emit("Probing for NI USRP-2900 (B200)...", False)
                # Specifically request B200 / NI USRP-2900
                self.usrp = uhd.usrp.MultiUSRP("type=b200")
                self.is_hardware = True
                serial = self.usrp.get_usrp_rx_info(0).get("mboard_serial", "Unknown")
                self.sig_hw_status.emit(f"NI USRP-2900 Connected [Serial: {serial}]", True)
                return
            except Exception as e:
                self.sig_hw_status.emit(f"Hardware probe note: {e}. Using Mock Engine.", False)

        # Fallback to software emulator
        self.usrp = MockMultiUSRP(mode=self.carrier_mode)
        self.is_hardware = False
        self.sig_hw_status.emit("Simulation Engine Active (Physics Mock)", False)

    def _apply_rf_config(self) -> None:
        """Configure frequencies, gains, sample rates, and antennas."""
        if self.usrp is None:
            return

        try:
            # 1. Sample rate
            self.usrp.set_rx_rate(self.sample_rate, 0)
            self.usrp.set_tx_rate(self.sample_rate, 0)

            # 2. Carrier frequency
            tune_req = (
                MockTuneRequest(self.center_freq)
                if not self.is_hardware
                else uhd.types.TuneRequest(self.center_freq)
            )
            self.usrp.set_rx_freq(tune_req, 0)
            self.usrp.set_tx_freq(tune_req, 0)

            # 3. Antennas (Bistatic: TX on TX/RX, RX on RX2)
            self.usrp.set_rx_antenna("RX2", 0)
            self.usrp.set_tx_antenna("TX/RX", 0)

            # 4. Gains
            self.usrp.set_rx_gain(self.rx_gain, 0)
            tx_gain_val = self.tx_gain if self.carrier_mode == "cw" else 0.0
            self.usrp.set_tx_gain(tx_gain_val, 0)

            # 5. Disable AGC to preserve linear reflection step response
            self.usrp.set_rx_agc(False, 0)
        except Exception as exc:
            self.sig_error.emit(f"RF Config Error: {exc}")

    def run(self) -> None:
        """Main streaming and DSP computation loop."""
        self._running = True
        self._init_transceiver()
        self._apply_rf_config()

        chunk_size = 4096
        stream_args = (
            MockStreamArgs("fc32", "sc16")
            if not self.is_hardware
            else uhd.usrp.StreamArgs("fc32", "sc16")
        )
        stream_args.channels = [0]

        try:
            rx_streamer = self.usrp.get_rx_stream(stream_args)
            tx_streamer = (
                self.usrp.get_tx_stream(stream_args)
                if (self.carrier_mode == "cw" and self.usrp)
                else None
            )
        except Exception as exc:
            self.sig_error.emit(f"Stream creation failed: {exc}")
            return

        recv_buffer = np.zeros((1, chunk_size), dtype=np.complex64)
        rx_md = MockRXMetadata() if not self.is_hardware else uhd.types.RXMetadata()
        tx_md = MockTXMetadata() if not self.is_hardware else uhd.types.TXMetadata()

        if tx_md is not None:
            tx_md.start_of_burst = True
            tx_md.end_of_burst = False

        # Issue continuous RX start command
        stream_cmd_type = MockStreamCMD if not self.is_hardware else uhd.types.StreamCMD
        stream_mode_start = (
            MockStreamMode.start_cont if not self.is_hardware else uhd.types.StreamMode.start_cont
        )
        cmd = stream_cmd_type(stream_mode_start)
        cmd.stream_now = True
        rx_streamer.issue_stream_cmd(cmd)

        cw_chunk = np.ones((1, chunk_size), dtype=np.complex64) * 0.707

        # Prefill TX buffer in CW mode to prevent initial underflows
        if self.carrier_mode == "cw" and tx_streamer is not None:
            for _ in range(3):
                try:
                    tx_streamer.send(cw_chunk, tx_md)
                    tx_md.start_of_burst = False
                except Exception:
                    pass

        last_render_time = time.time()
        render_interval = 1.0 / 30.0  # 30 FPS GUI refresh rate

        # Circular buffer for snapshot persistence
        recent_samples = np.zeros(int(self.sample_rate * 1.5), dtype=np.complex64)
        recent_pos = 0

        # Absorbing state cluster tracking
        c1_samples = []
        c2_samples = []

        try:
            while self._running:
                # Process pending commands
                while not self._command_queue.empty():
                    msg = self._command_queue.get_nowait()
                    cmd_type = msg.get("type")
                    if cmd_type == "set_freq":
                        self.center_freq = msg["freq"]
                        self._apply_rf_config()
                    elif cmd_type == "set_rx_gain":
                        self.rx_gain = msg["gain"]
                        self._apply_rf_config()
                    elif cmd_type == "set_tx_gain":
                        self.tx_gain = msg["gain"]
                        self._apply_rf_config()
                    elif cmd_type == "set_rate":
                        self.sample_rate = msg["rate"]
                        self._apply_rf_config()
                    elif cmd_type == "set_mode":
                        self.carrier_mode = msg["mode"]
                        self._apply_rf_config()
                    elif cmd_type == "calibrate":
                        # Compute mean carrier leakage vector
                        if len(recent_samples) > 0:
                            self.baseline_offset = np.mean(recent_samples[-16384:])
                    elif cmd_type == "snapshot":
                        self._execute_snapshot_export(
                            msg["export_dir"], msg["base_filename"], recent_samples
                        )

                # CW TX transmission
                if self.carrier_mode == "cw" and tx_streamer is not None:
                    try:
                        tx_streamer.send(cw_chunk, tx_md)
                        tx_md.start_of_burst = False
                    except Exception:
                        pass

                # Receive RX chunk
                num_rx = rx_streamer.recv(recv_buffer, rx_md, timeout=0.1)
                if num_rx <= 0:
                    continue

                # In software emulation mode, pace chunks to match physical ADC sample rate
                if not self.is_hardware:
                    time.sleep(num_rx / self.sample_rate)

                raw_chunk = recv_buffer[0, :num_rx]

                # Apply carrier leakage cancellation if calibrated
                clean_chunk = raw_chunk - self.baseline_offset

                # Update recent samples ring buffer
                n_put = len(clean_chunk)
                if recent_pos + n_put <= len(recent_samples):
                    recent_samples[recent_pos : recent_pos + n_put] = clean_chunk
                    recent_pos += n_put
                else:
                    first_part = len(recent_samples) - recent_pos
                    recent_samples[recent_pos:] = clean_chunk[:first_part]
                    second_part = n_put - first_part
                    recent_samples[:second_part] = clean_chunk[first_part:]
                    recent_pos = second_part

                # Throttled GUI metric computation at 30 FPS
                now = time.time()
                if now - last_render_time >= render_interval:
                    last_render_time = now

                    # 1. Moving average power
                    inst_power = float(np.mean(np.abs(clean_chunk) ** 2))
                    inst_power_db = float(10.0 * np.log10(max(inst_power, 1e-12)))

                    # Update strip chart rolling history
                    self.power_history[:-1] = self.power_history[1:]
                    self.power_history[-1] = inst_power_db

                    # 2. State classification
                    # Evaluate dynamic step threshold
                    min_p = np.min(self.power_history[-60:])
                    max_p = np.max(self.power_history[-60:])
                    step_threshold = (min_p + max_p) / 2.0
                    step_contrast = max_p - min_p

                    prev_state = self.current_state
                    if step_contrast >= 1.2:
                        if inst_power_db >= step_threshold:
                            self.current_state = "STATE 2: REFLECTING (SHORT)"
                            c2_samples.append(np.mean(clean_chunk))
                        else:
                            self.current_state = "STATE 1: ABSORBING (50 Ω)"
                            c1_samples.append(np.mean(clean_chunk))
                    else:
                        # Baseline un-modulated
                        if self.current_state.startswith("STATE 2"):
                            c2_samples.append(np.mean(clean_chunk))
                        else:
                            c1_samples.append(np.mean(clean_chunk))

                    # Keep cluster samples bounded
                    if len(c1_samples) > 200:
                        c1_samples = c1_samples[-200:]
                    if len(c2_samples) > 200:
                        c2_samples = c2_samples[-200:]

                    # Signal transition event if state flipped
                    if prev_state != self.current_state:
                        delta_p = step_contrast
                        delta_v = (
                            float(np.abs(np.mean(c2_samples) - np.mean(c1_samples)))
                            if (c1_samples and c2_samples)
                            else 0.0
                        )
                        self.sig_state_transition.emit(self.current_state, delta_p, delta_v)

                    # 3. FFT computation
                    n_fft = 1024
                    fft_chunk = clean_chunk[:n_fft]
                    if len(fft_chunk) < n_fft:
                        fft_chunk = np.pad(fft_chunk, (0, n_fft - len(fft_chunk)))
                    window = np.hanning(n_fft)
                    psd = np.abs(np.fft.fftshift(np.fft.fft(fft_chunk * window))) ** 2
                    psd_db = 10.0 * np.log10(np.maximum(psd, 1e-12))
                    freqs = np.fft.fftshift(np.fft.fftfreq(n_fft, d=1.0 / self.sample_rate)) / 1e6

                    # 4. Decimated constellation samples for fast rendering
                    step = max(1, len(clean_chunk) // 250)
                    iq_sub = clean_chunk[::step]

                    # 5. Delta metrics
                    centroid_1 = (
                        complex(np.mean(c1_samples)) if c1_samples else 0.0 + 0.0j
                    )
                    centroid_2 = (
                        complex(np.mean(c2_samples)) if c2_samples else 0.0 + 0.0j
                    )
                    delta_v_mag = float(np.abs(centroid_2 - centroid_1))

                    payload = {
                        "power_db": inst_power_db,
                        "power_history": self.power_history.copy(),
                        "time_history": self.time_history,
                        "iq_samples": iq_sub,
                        "centroid_1": centroid_1,
                        "centroid_2": centroid_2,
                        "delta_v": delta_v_mag,
                        "delta_p": step_contrast if step_contrast >= 1.0 else 0.0,
                        "current_state": self.current_state,
                        "fft_freqs": freqs,
                        "fft_psd": psd_db,
                        "carrier_freq_mhz": self.center_freq / 1e6,
                    }
                    self.sig_frame_ready.emit(payload)

        finally:
            # Stop stream commands cleanly
            try:
                stream_mode_stop = (
                    MockStreamMode.stop_cont
                    if not self.is_hardware
                    else uhd.types.StreamMode.stop_cont
                )
                stop_cmd = stream_cmd_type(stream_mode_stop)
                stop_cmd.stream_now = True
                rx_streamer.issue_stream_cmd(stop_cmd)
            except Exception:
                pass

    def _execute_snapshot_export(
        self, export_dir: str, base_filename: str, samples: np.ndarray
    ) -> None:
        """Export measurement data in .npz, MATLAB .mat, CSV, and summary formats."""
        try:
            os.makedirs(export_dir, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            prefix = f"{base_filename}_{timestamp}"

            # Capture up to the most recent 1 second of samples for fast I/O
            max_snap = int(self.sample_rate * 1.0)
            snap_samples = samples[-max_snap:] if len(samples) > max_snap else samples

            # 1. Save uncompressed NumPy .npz (fast write)
            npz_path = os.path.join(export_dir, f"{prefix}.npz")
            np.savez(
                npz_path,
                samples=snap_samples,
                sample_rate=self.sample_rate,
                center_freq=self.center_freq,
                rx_gain=self.rx_gain,
                tx_gain=self.tx_gain,
                carrier_mode=self.carrier_mode,
                current_state=self.current_state,
                timestamp=timestamp,
            )

            # 2. Save MATLAB .mat workspace file for direct load in MATLAB
            mat_path = os.path.join(export_dir, f"{prefix}.mat")
            mat_dict = {
                "iq_samples": snap_samples,
                "sample_rate": float(self.sample_rate),
                "carrier_freq_hz": float(self.center_freq),
                "rx_gain_db": float(self.rx_gain),
                "tx_gain_db": float(self.tx_gain),
                "carrier_mode": str(self.carrier_mode),
                "state_label": str(self.current_state),
                "timestamp": str(timestamp),
            }
            scipy.io.savemat(mat_path, mat_dict)

            # 3. Save CSV Metrics Table
            csv_path = os.path.join(export_dir, f"{prefix}_metrics.csv")
            with open(csv_path, "w", encoding="utf-8") as f:
                f.write("Parameter,Value,Unit\n")
                f.write(f"Timestamp,{timestamp},-\n")
                f.write(f"Center Frequency,{self.center_freq / 1e6:.3f},MHz\n")
                f.write(f"Sample Rate,{self.sample_rate / 1e6:.2f},MS/s\n")
                f.write(f"RX Gain,{self.rx_gain:.1f},dB\n")
                f.write(f"TX Gain,{self.tx_gain:.1f},dB\n")
                f.write(f"Carrier Mode,{self.carrier_mode},-\n")
                f.write(f"Active State,{self.current_state},-\n")
                f.write(f"Sample Count,{len(snap_samples)},samples\n")

            self.sig_snapshot_saved.emit(mat_path)
        except Exception as exc:
            self.sig_error.emit(f"Snapshot export failed: {exc}")
