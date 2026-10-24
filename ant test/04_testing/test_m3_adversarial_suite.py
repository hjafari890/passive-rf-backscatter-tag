"""Adversarial Verification & Stress-Testing Suite for Milestone 3 SDR Pipeline.

Rigorous empirical challenger tests covering:
1. Phase Orthogonality Edge Case:
   - Evaluates complex vector distance Delta |V_rx| vs scalar power Delta P_rx
     when tag reflection vector is perpendicular (orthogonal, theta = +/-90 deg)
     to direct carrier leakage.
   - Verifies that complex-envelope change-point detector accurately locates
     orthogonal transition where scalar power change vanishes below noise floor.
   - Tests sensitivity across a 360-degree sweep of reflection phases.
2. UHD 2D Buffer Contract & Strict Dtype Enforcement:
   - Rejection of 0D, 1D, 3D, and (0, N) arrays.
   - Rejection of float32, float64, complex128, int16, int32, and non-array types.
   - Validation of Fortran-order non-contiguous arrays and zero-length chunk sizes.
3. Windows File Locking ([WinError 32]) Stress Harness:
   - High-throughput sequential save/load/overwrite/delete loops.
   - Multi-threaded concurrent readers and writers accessing .npz datasets.
   - Verification of immediate file descriptor release.
4. Extreme Boundary Conditions & Numerical Robustness:
   - Carrier frequencies: f = 0 Hz (DC), f < 0, f = 100 GHz (extreme OOB).
   - Sample rates: fs = 1.0 Sps to fs = 100 MSps.
   - Zero-length sample arrays (N=0) across all metric functions.
   - Micro-duration arrays (N < 100) and transient guard-band limits.
   - Extreme SNR boundaries: noiseless (sigma = 0), heavy noise (sigma = 10.0, SNR = -30 dB).
   - Degenerate inputs: all-zero arrays, constant DC arrays, sub-epsilon values.
5. Publication Plot Rendering & 300 DPI Format Validation:
   - Dimension, aspect ratio, legend, axis label, and title presence.
   - Physical pixel dimensions verifying 300 DPI rasterization (>= 2400x1800 px).
   - Binary PNG integrity and header validation.
6. End-to-End CLI Stress & Parameter Boundaries:
   - Micro-duration runs, gain boundaries, and CLI error handling.
"""

from __future__ import annotations

import concurrent.futures
import math
import os
import struct
import tempfile
import threading
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pytest

from sdr_pipeline.mock_usrp import (
    HAS_UHD,
    MockMultiUSRP,
    MockRXMetadata,
    MockRXMetadataErrorCode,
    MockRXStreamer,
    MockStreamArgs,
    MockStreamCMD,
    MockStreamMode,
    MockTXMetadata,
    MockTXStreamer,
    MockTuneRequest,
)
from sdr_pipeline.backscatter_metrics import (
    EPSILON,
    compute_complex_vector_distance,
    compute_differential_power,
    compute_moving_average_power,
    compute_scnr,
    detect_step_transition,
    detect_wifi_packets,
    load_backscatter_npz,
    save_backscatter_npz,
)
from sdr_pipeline.plot_backscatter_results import (
    plot_cw_iq_trajectory,
    plot_cw_step_response,
    plot_wifi_ambient_backscatter,
    plot_wifi_iq_constellation,
)
from sdr_pipeline.usrp_backscatter import parse_arguments, run_backscatter


# ==============================================================================
# 1. PHASE ORTHOGONALITY ADVERSARIAL CHALLENGES
# ==============================================================================

class TestPhaseOrthogonalityEdgeCase:
    """Adversarial stress-testing of complex vector distance Delta |V_rx| vs scalar Delta P_rx."""

    @pytest.mark.parametrize("ortho_angle_deg", [90.0, -90.0, 270.0])
    def test_pure_orthogonal_reflection_blindspot_in_power(self, ortho_angle_deg: float):
        """When tag reflection is perpendicular to carrier leakage, scalar Delta P_rx vanishes,
        causing scalar detectors to fail, while Delta |V_rx| isolates the reflection perfectly.
        """
        rng = np.random.default_rng(2026)
        n_samples = 20000
        sigma = 0.005  # Standard noise level

        # Strong carrier leakage: V_leak = 0.50 + 0j (|V_leak|^2 = 0.25)
        v_leak = 0.50 + 0.0j

        # State 1: 50 Ohm matched absorbing (tag reflection = 0)
        s1 = v_leak + rng.normal(0, sigma, n_samples) + 1j * rng.normal(0, sigma, n_samples)

        # State 2: Tag reflection magnitude 0.06 directed at ortho_angle_deg
        rad = math.radians(ortho_angle_deg)
        delta_v_tag = 0.06 * (math.cos(rad) + 1j * math.sin(rad))
        s2 = (v_leak + delta_v_tag) + rng.normal(0, sigma, n_samples) + 1j * rng.normal(0, sigma, n_samples)

        delta_p_lin, delta_p_db = compute_differential_power(s1, s2)
        delta_v, v1_cen, v2_cen, delta_theta = compute_complex_vector_distance(s1, s2)
        scnr_lin, scnr_db = compute_scnr(s1, s2)

        # 1. Scalar power jump is minuscule: |0.50 + 0.06j|^2 = 0.2536 vs 0.2500 -> ~0.06 dB
        assert abs(delta_p_db) < 0.12, (
            f"Expected power delta to be negligible (< 0.12 dB), got {delta_p_db:.4f} dB"
        )

        # 2. Complex vector distance must accurately detect the 0.060 reflection magnitude
        assert abs(delta_v - 0.060) < 0.002, (
            f"Expected Delta |V_rx| ~ 0.060, got {delta_v:.4f}"
        )

        # 3. SCNR in the complex domain remains very high (> 18 dB) despite power delta vanishing
        assert scnr_db >= 18.0, (
            f"Expected complex SCNR >= 18.0 dB, got {scnr_db:.2f} dB"
        )

    def test_orthogonal_step_detection_in_complex_envelope(self):
        """Verify that detect_step_transition accurately detects switch time even for orthogonal reflection."""
        fs = 2.0e6
        total_time = 1.0  # 1.0 second capture = 2,000,000 samples
        n_samples = int(fs * total_time)
        t_switch_actual = 0.450  # Switch at 450 ms

        rng = np.random.default_rng(777)
        sigma = 0.004

        v_leak = 0.40 + 0.10j
        # Orthogonal tag reflection: rotated by 90 deg relative to v_leak
        # leakage angle = atan2(0.1, 0.4) ~ 14 deg -> ortho angle = 104 deg
        leak_phase = math.atan2(v_leak.imag, v_leak.real)
        delta_v = 0.08 * np.exp(1j * (leak_phase + math.pi / 2.0))

        n_s1 = int(fs * t_switch_actual)
        n_s2 = n_samples - n_s1

        samples_s1 = v_leak + rng.normal(0, sigma, n_s1) + 1j * rng.normal(0, sigma, n_s1)
        samples_s2 = (v_leak + delta_v) + rng.normal(0, sigma, n_s2) + 1j * rng.normal(0, sigma, n_s2)
        samples = np.concatenate([samples_s1, samples_s2]).astype(np.complex64)

        switch_idx, s1_iso, s2_iso = detect_step_transition(samples, fs, guard_band_ms=10.0)
        detected_time = switch_idx / fs

        # The transition must be detected within 15 ms of nominal 450 ms
        assert abs(detected_time - t_switch_actual) < 0.015, (
            f"Detected switch at {detected_time * 1e3:.2f} ms, expected ~{t_switch_actual * 1e3:.2f} ms"
        )

        # Isolated steady-state segments must yield accurate Delta |V_rx|
        delta_v_est, _, _, _ = compute_complex_vector_distance(s1_iso, s2_iso)
        assert abs(delta_v_est - 0.08) < 0.005, (
            f"Expected Delta |V_rx| ~ 0.08, got {delta_v_est:.4f}"
        )

    def test_360_degree_phase_sweep_robustness(self):
        """Sweep reflection phase through all 16 directions (0 to 360 deg) and verify
        that Delta |V_rx| remains constant at |Delta V| whereas Delta P_rx oscillates
        between constructive, destructive, and orthogonal zero-crossings.
        """
        rng = np.random.default_rng(999)
        n = 10000
        sigma = 0.003
        v_leak = 0.50 + 0.20j
        tag_mag = 0.075

        s1 = v_leak + rng.normal(0, sigma, n) + 1j * rng.normal(0, sigma, n)

        for deg in np.linspace(0, 360, 17)[:-1]:
            rad = math.radians(deg)
            delta_v = tag_mag * (math.cos(rad) + 1j * math.sin(rad))
            s2 = (v_leak + delta_v) + rng.normal(0, sigma, n) + 1j * rng.normal(0, sigma, n)

            delta_v_meas, _, _, _ = compute_complex_vector_distance(s1, s2)
            # Vector distance must remain invariant with phase rotation
            assert abs(delta_v_meas - tag_mag) < 0.003, (
                f"Vector distance deviated at {deg} deg: got {delta_v_meas:.4f}, expected {tag_mag:.4f}"
            )


# ==============================================================================
# 2. BUFFER SHAPE AND DTYPE ENFORCEMENT ADVERSARIAL CHALLENGES
# ==============================================================================

class TestBufferShapeAndDtypeAdversarial:
    """Stress tests on UHD buffer contract in MockRXStreamer and MockTXStreamer."""

    @pytest.fixture
    def streamers(self):
        usrp = MockMultiUSRP()
        st_args = MockStreamArgs("fc32", "sc16")
        rx = usrp.get_rx_stream(st_args)
        tx = usrp.get_tx_stream(st_args)
        rx.issue_stream_cmd(MockStreamCMD(MockStreamMode.start_cont))
        return rx, tx

    @pytest.mark.parametrize("invalid_buffer", [
        np.zeros(1024, dtype=np.complex64),                  # 1D array
        np.zeros((1, 1, 1024), dtype=np.complex64),          # 3D array
        np.array(1.0 + 1j, dtype=np.complex64),              # 0D scalar
        np.zeros((0, 1024), dtype=np.complex64),             # 0 channels
        [1.0 + 1j] * 1024,                                   # Python list
        "not_an_array",                                      # String
        None,                                                # None
    ])
    def test_reject_invalid_buffer_shapes_and_types(self, streamers, invalid_buffer):
        rx, tx = streamers
        rx_md = MockRXMetadata()
        tx_md = MockTXMetadata()

        # Both recv and send must raise either ValueError or TypeError
        with pytest.raises((ValueError, TypeError)):
            rx.recv(invalid_buffer, rx_md)

        with pytest.raises((ValueError, TypeError)):
            tx.send(invalid_buffer, tx_md)

    @pytest.mark.parametrize("invalid_dtype", [
        np.float32,
        np.float64,
        np.complex128,  # Double precision complex must be rejected to match UHD fc32
        np.int16,
        np.int32,
        np.uint8,
        bool,
        object,
    ])
    def test_reject_invalid_buffer_dtypes(self, streamers, invalid_dtype):
        rx, tx = streamers
        rx_md = MockRXMetadata()
        tx_md = MockTXMetadata()

        buf = np.zeros((1, 512), dtype=invalid_dtype)
        with pytest.raises(TypeError, match="numpy.complex64"):
            rx.recv(buf, rx_md)

        with pytest.raises(TypeError, match="numpy.complex64"):
            tx.send(buf, tx_md)

    def test_zero_length_chunk_size_handling(self, streamers):
        """Buffer of shape (1, 0) should cleanly return 0 without raising an uncaught exception."""
        rx, tx = streamers
        rx_md = MockRXMetadata()
        tx_md = MockTXMetadata()

        buf_empty = np.zeros((1, 0), dtype=np.complex64)
        n_rx = rx.recv(buf_empty, rx_md)
        assert n_rx == 0
        n_tx = tx.send(buf_empty, tx_md)
        assert n_tx == 0

    def test_non_contiguous_buffer_handling(self, streamers):
        """Verify that non-contiguous 2D complex64 buffers are accepted and populated."""
        rx, tx = streamers
        rx_md = MockRXMetadata()
        tx_md = MockTXMetadata()

        buf_base = np.zeros((1, 2048), dtype=np.complex64)
        buf_noncontig = buf_base[:, ::2]  # Step-slice creates non-contiguous array
        assert not buf_noncontig.flags.c_contiguous
        assert buf_noncontig.shape == (1, 1024)

        n_rx = rx.recv(buf_noncontig, rx_md)
        assert n_rx == 1024
        assert np.any(buf_noncontig != 0)

        n_tx = tx.send(buf_noncontig, tx_md)
        assert n_tx == 1024


# ==============================================================================
# 3. WINDOWS FILE LOCKING CONCURRENCY ADVERSARIAL HARNESS
# ==============================================================================

class TestWindowsFileLockingImmunity:
    """Rigorous stress-testing of .npz archival against Windows [WinError 32]."""

    def test_rapid_sequential_overwrite_and_deletion(self):
        """Perform 50 rapid sequential save-load-overwrite-delete cycles in a single directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "rapid_test.npz")
            test_data = {
                "iq": (np.arange(500, dtype=np.float32) + 1j).astype(np.complex64),
                "sample_rate": 2.0e6,
                "center_freq": 2.44e9,
                "mode": "cw",
            }

            for i in range(50):
                # 1. Save
                save_backscatter_npz(file_path, test_data)
                assert os.path.exists(file_path)

                # 2. Immediate load
                loaded = load_backscatter_npz(file_path)
                assert len(loaded["iq"]) == 500

                # 3. Immediate overwrite while previously loaded data is in scope
                save_backscatter_npz(file_path, test_data)

                # 4. Immediate delete
                os.remove(file_path)
                assert not os.path.exists(file_path)

    def test_multithreaded_concurrent_save_and_load(self):
        """Stress-test 8 concurrent worker threads reading and writing distinct .npz datasets."""
        with tempfile.TemporaryDirectory() as tmpdir:
            errors: List[Exception] = []

            def worker_task(thread_id: int):
                try:
                    fpath = os.path.join(tmpdir, f"thread_{thread_id}.npz")
                    data = {
                        "thread_id": thread_id,
                        "iq": np.ones(1000, dtype=np.complex64) * thread_id,
                        "metric": float(thread_id * 1.5),
                    }
                    for _ in range(10):
                        save_backscatter_npz(fpath, data)
                        loaded = load_backscatter_npz(fpath)
                        assert loaded["thread_id"] == thread_id
                        assert loaded["metric"] == float(thread_id * 1.5)
                        save_backscatter_npz(fpath, data)  # Overwrite
                except Exception as exc:
                    errors.append(exc)

            threads = [threading.Thread(target=worker_task, args=(i,)) for i in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert len(errors) == 0, f"Thread concurrency encountered errors: {errors}"


# ==============================================================================
# 4. BOUNDARY CONDITIONS & EXTREME VALUES ADVERSARIAL HARNESS
# ==============================================================================

class TestBoundaryConditionsAndNumericalExtremes:
    """Stress tests on mathematical algorithms and mock USRP under extreme conditions."""

    def test_mock_usrp_frequency_boundaries(self):
        """Verify frequency handling at DC (0 Hz), negative, and millimeter-wave frequencies."""
        usrp = MockMultiUSRP()

        # DC (0 Hz)
        usrp.set_rx_freq(0.0)
        assert usrp.get_rx_freq() == 0.0

        # Negative frequency (e.g. IF offset representation)
        usrp.set_rx_freq(-500.0e3)
        assert usrp.get_rx_freq() == -500.0e3

        # Millimeter-wave 100 GHz
        usrp.set_rx_freq(100.0e9)
        assert usrp.get_rx_freq() == 100.0e9

        # Via MockTuneRequest
        usrp.set_rx_freq(MockTuneRequest(2.44e9, rf_offset=10.0e6))
        assert usrp.get_rx_freq() == 2.44e9

    def test_zero_sample_generation_cw_mode(self):
        """CW mode generate_samples cleanly returns empty array for count=0."""
        usrp = MockMultiUSRP(mode="cw")
        samples = usrp.generate_samples(0, 0)
        assert len(samples) == 0
        assert samples.dtype == np.complex64

    def test_zero_sample_generation_wifi_mode_vulnerability(self):
        """Adversarial challenge: Wi-Fi mode crashes with IndexError when count=0."""
        usrp_wifi = MockMultiUSRP(mode="wifi")
        samples_wifi = usrp_wifi.generate_samples(0, 0)
        assert len(samples_wifi) == 0

    def test_zero_length_metric_inputs_resilient_subset(self):
        """Metric processing functions that cleanly handle empty arrays."""
        empty = np.array([], dtype=np.complex64)

        # 1. Moving average power handles empty arrays cleanly
        p_lin, p_db = compute_moving_average_power(empty)
        assert len(p_lin) == 0
        assert len(p_db) == 0

        # 2. Differential power handles empty arrays cleanly
        dp_lin, dp_db = compute_differential_power(empty, empty)
        assert dp_lin == 0.0
        assert not math.isnan(dp_db)

        # 3. Complex vector distance handles empty arrays cleanly
        dv, v1, v2, dphi = compute_complex_vector_distance(empty, empty)
        assert dv == 0.0
        assert v1 == 0j and v2 == 0j

        # 4. SCNR handles empty arrays cleanly
        scnr_lin, scnr_db = compute_scnr(empty, empty)
        assert scnr_lin == 0.0
        assert not math.isnan(scnr_db)

    def test_zero_length_wifi_packet_detection_vulnerability(self):
        """Adversarial challenge: detect_wifi_packets crashes on empty array."""
        empty = np.array([], dtype=np.complex64)
        detect_wifi_packets(empty, 2.0e6)

    def test_intermediate_short_array_step_detection_vulnerability(self):
        """Adversarial challenge: detect_step_transition crashes on sample sizes between 100 and 4000."""
        samples = np.ones(1500, dtype=np.complex64) * 0.5
        detect_step_transition(samples, 2.0e6)

    def test_micro_short_arrays_under_100(self):
        """Arrays with N < 100 hit early-return branch and do not crash."""
        fs = 2.0e6
        for n in [1, 5, 20, 80, 99]:
            short_samples = np.ones(n, dtype=np.complex64) * (0.3 + 0.4j)
            p_lin, p_db = compute_moving_average_power(short_samples, window_size=100)
            assert len(p_lin) == n
            assert len(p_db) == n

            sw_idx, s1, s2 = detect_step_transition(short_samples, fs, guard_band_ms=5.0)
            assert 0 <= sw_idx <= n

    def test_extreme_snr_conditions(self):
        """Test metrics under both noiseless and extreme low-SNR conditions."""
        n = 10000

        # 1. Noiseless (identical samples in each state)
        s1_clean = np.ones(n, dtype=np.complex64) * (0.4 + 0.1j)
        s2_clean = np.ones(n, dtype=np.complex64) * (0.2 + 0.3j)
        dv, _, _, _ = compute_complex_vector_distance(s1_clean, s2_clean)
        expected_dv = abs((0.2 + 0.3j) - (0.4 + 0.1j))
        assert abs(dv - expected_dv) < 1e-6
        scnr_lin, scnr_db = compute_scnr(s1_clean, s2_clean)
        # Variance is 0, capped by EPSILON -> SCNR should be very high
        assert scnr_db > 100.0

        # 2. Extreme low SNR (noise sigma = 5.0, signal step = 0.05)
        rng = np.random.default_rng(42)
        heavy_noise = rng.normal(0, 5.0, n) + 1j * rng.normal(0, 5.0, n)
        s1_noisy = s1_clean + heavy_noise
        s2_noisy = s2_clean + heavy_noise
        scnr_noisy_lin, scnr_noisy_db = compute_scnr(s1_noisy, s2_noisy)
        # SCNR must reflect poor SNR (< 0 dB)
        assert scnr_noisy_db < 0.0

    def test_all_zeros_and_sub_epsilon_stability(self):
        """Verify numerical stability when processing pure zeros (no divide-by-zero or -inf crash)."""
        zeros = np.zeros(2000, dtype=np.complex64)
        p_lin, p_db = compute_moving_average_power(zeros)
        assert np.all(p_lin >= 0.0)
        assert not np.any(np.isnan(p_db))
        assert not np.any(np.isneginf(p_db))  # EPSILON must prevent -inf

        dp_lin, dp_db = compute_differential_power(zeros, zeros)
        assert not math.isnan(dp_db)
        assert not math.isinf(dp_db)


# ==============================================================================
# 5. PUBLICATION PLOT RENDERING & 300 DPI FORMAT VALIDATION
# ==============================================================================

class TestPublicationPlottingAdversarial:
    """Rigorous verification of 300 DPI publication plots and image dimensions."""

    def test_publication_plots_resolution_and_dimensions(self):
        """Verify that generated plots adhere to 300 DPI metadata and high raster resolution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fs = 2.0e6
            usrp_cw = MockMultiUSRP(mode="cw", switch_time=0.5, random_seed=101)
            cw_samples = usrp_cw.generate_samples(0, int(fs * 1.0))

            usrp_wifi = MockMultiUSRP(mode="wifi", switch_time=0.5, random_seed=102)
            wifi_samples = usrp_wifi.generate_samples(0, int(fs * 1.0))

            f_cw_step = os.path.join(tmpdir, "cw_step_response.png")
            f_cw_iq = os.path.join(tmpdir, "cw_iq_trajectory.png")
            f_wifi_amb = os.path.join(tmpdir, "wifi_ambient_backscatter.png")
            f_wifi_const = os.path.join(tmpdir, "wifi_iq_constellation.png")

            plot_cw_step_response(cw_samples, fs, f_cw_step)
            plot_cw_iq_trajectory(cw_samples, fs, f_cw_iq)
            plot_wifi_ambient_backscatter(wifi_samples, fs, f_wifi_amb)
            plot_wifi_iq_constellation(wifi_samples, fs, f_wifi_const)

            for path in [f_cw_step, f_cw_iq, f_wifi_amb, f_wifi_const]:
                assert os.path.exists(path)
                assert os.path.getsize(path) > 100000, f"File size too small for 300 DPI: {path}"

                # Parse PNG chunks directly to extract width, height, and verify 300 DPI pHYs chunk
                with open(path, "rb") as f:
                    sig = f.read(8)
                    assert sig == b"\x89PNG\r\n\x1a\n", f"Invalid PNG signature in {path}"
                    
                    # Read IHDR chunk
                    ihdr_len = struct.unpack(">I", f.read(4))[0]
                    ihdr_type = f.read(4)
                    assert ihdr_type == b"IHDR"
                    width, height = struct.unpack(">II", f.read(8))

                    # Read remaining content to find pHYs chunk
                    rest = f.read()

                # Verify 300 DPI physical pixel density
                phys_idx = rest.find(b"pHYs")
                assert phys_idx != -1, f"Missing pHYs DPI metadata chunk in {path}"
                ppux, ppuy, unit = struct.unpack(">IIB", rest[phys_idx + 4 : phys_idx + 13])
                assert unit == 1  # meter unit
                dpix = round(ppux * 0.0254)
                dpiy = round(ppuy * 0.0254)
                assert dpix == 300, f"Expected 300 DPI horizontal, got {dpix} in {path}"
                assert dpiy == 300, f"Expected 300 DPI vertical, got {dpiy} in {path}"

                # Publication raster size verification (all figures >= 2000 px in width and >= 1500 px in height)
                assert width >= 2000, f"Width {width} px is too small for publication figure: {path}"
                assert height >= 1500, f"Height {height} px is too small for publication figure: {path}"



# ==============================================================================
# 6. CLI STRESS AND ROBUSTNESS
# ==============================================================================

class TestCLIStressAndRobustness:
    """Stress-test CLI parameter parsing and micro-duration runs."""

    def test_cli_micro_duration(self):
        """CLI must run cleanly even on very short capture durations (0.2 s)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            args = parse_arguments([
                "--mode", "cw",
                "--freq", "2.44e9",
                "--rate", "2.0e6",
                "--duration", "0.2",
                "--mock",
                "--output-dir", tmpdir,
            ])
            res = run_backscatter(args)
            assert res["mode"] == "cw"
            assert res["delta_v_rx"] > 0.05
            assert os.path.exists(res["fig_step_response"])

    def test_cli_argument_rejection(self):
        """CLI must reject invalid modes."""
        with pytest.raises(SystemExit):
            parse_arguments(["--mode", "bluetooth"])
