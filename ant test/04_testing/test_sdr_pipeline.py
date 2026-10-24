"""Comprehensive Automated Test Suite for USRP-2900 Backscatter Validation Pipeline.

Verifies:
1. Mock MultiUSRP API compliance & 2D buffer contract enforcement
2. Mode 1 CW backscatter step response & differential metrics (Delta P_rx, Delta |V_rx|, SCNR)
3. Mode 2 Ambient Wi-Fi packet detection & beacon modulation
4. Context-manager safe .npz persistence and Windows file lock immunity
5. Publication-quality 300 DPI plot generation and binary integrity
6. End-to-end CLI execution
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Dict, Any

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


class TestMockMultiUSRPAPI:
    """Tests for MockMultiUSRP compliance with UHD API and 2D buffer contract."""

    def test_mock_usrp_initialization_defaults(self):
        usrp = MockMultiUSRP(mode="cw")
        assert usrp.get_rx_rate() == 2.0e6
        assert usrp.get_tx_rate() == 2.0e6
        assert usrp.get_rx_freq() == 2.44e9
        assert usrp.get_tx_freq() == 2.44e9
        assert usrp.get_rx_gain() == 30.0
        assert usrp.get_tx_gain() == 50.0
        assert usrp.get_rx_antenna() == "RX2"
        assert usrp.get_tx_antenna() == "TX/RX"
        assert usrp.get_rx_agc() is False

    def test_transceiver_parameter_tuning(self):
        usrp = MockMultiUSRP()
        
        # Test rate setting
        usrp.set_rx_rate(5.0e6)
        assert usrp.get_rx_rate() == 5.0e6
        usrp.set_tx_rate(5.0e6)
        assert usrp.get_tx_rate() == 5.0e6

        # Test frequency tuning with float and TuneRequest
        usrp.set_rx_freq(915.0e6)
        assert usrp.get_rx_freq() == 915.0e6
        tune_req = MockTuneRequest(2.437e9)
        usrp.set_rx_freq(tune_req)
        assert usrp.get_rx_freq() == 2.437e9

        # Test gain setting
        usrp.set_rx_gain(42.0)
        assert usrp.get_rx_gain() == 42.0
        usrp.set_tx_gain(65.0)
        assert usrp.get_tx_gain() == 65.0

        # Test antenna selection
        usrp.set_rx_antenna("RX2")
        assert usrp.get_rx_antenna() == "RX2"
        usrp.set_tx_antenna("TX/RX")
        assert usrp.get_tx_antenna() == "TX/RX"

        # Test AGC disable
        usrp.set_rx_agc(False)
        assert usrp.get_rx_agc() is False

    def test_streamers_creation(self):
        usrp = MockMultiUSRP()
        st_args = MockStreamArgs("fc32", "sc16")
        rx_stream = usrp.get_rx_stream(st_args)
        tx_stream = usrp.get_tx_stream(st_args)
        assert isinstance(rx_stream, MockRXStreamer)
        assert isinstance(tx_stream, MockTXStreamer)

    def test_2d_buffer_contract_enforcement(self):
        usrp = MockMultiUSRP()
        st_args = MockStreamArgs("fc32", "sc16")
        rx_stream = usrp.get_rx_stream(st_args)
        tx_stream = usrp.get_tx_stream(st_args)
        rx_md = MockRXMetadata()
        tx_md = MockTXMetadata()

        rx_stream.issue_stream_cmd(MockStreamCMD(MockStreamMode.start_cont))

        # 1. Reject 1D buffer
        buf_1d = np.zeros(2048, dtype=np.complex64)
        with pytest.raises(ValueError, match="Expected 2D array"):
            rx_stream.recv(buf_1d, rx_md)
        with pytest.raises(ValueError, match="Expected 2D array"):
            tx_stream.send(buf_1d, tx_md)

        # 2. Reject non-complex64 dtype
        buf_float = np.zeros((1, 2048), dtype=np.float32)
        with pytest.raises(TypeError, match="Expected buffer dtype numpy.complex64"):
            rx_stream.recv(buf_float, rx_md)
        with pytest.raises(TypeError, match="Expected buffer dtype numpy.complex64"):
            tx_stream.send(buf_float, tx_md)

        # 3. Accept valid 2D complex64 buffer of shape (1, N)
        buf_valid = np.zeros((1, 2048), dtype=np.complex64)
        n_rx = rx_stream.recv(buf_valid, rx_md)
        assert n_rx == 2048
        assert rx_md.error_code == MockRXMetadataErrorCode.none

        n_tx = tx_stream.send(buf_valid, tx_md)
        assert n_tx == 2048

    def test_stream_start_stop_command(self):
        usrp = MockMultiUSRP()
        st_args = MockStreamArgs("fc32", "sc16")
        rx_stream = usrp.get_rx_stream(st_args)
        rx_md = MockRXMetadata()
        buf = np.zeros((1, 1024), dtype=np.complex64)

        # Before start_cont, recv returns 0
        assert rx_stream.recv(buf, rx_md) == 0

        # Start stream
        rx_stream.issue_stream_cmd(MockStreamCMD(MockStreamMode.start_cont))
        assert rx_stream.recv(buf, rx_md) == 1024

        # Stop stream
        rx_stream.issue_stream_cmd(MockStreamCMD(MockStreamMode.stop_cont))
        assert rx_stream.recv(buf, rx_md) == 0


class TestMode1CWAcquisitionAndMetrics:
    """Tests for Mode 1 CW backscatter step response and differential metrics."""

    def test_cw_synthetic_sample_generation(self):
        usrp = MockMultiUSRP(mode="cw", switch_time=0.5, random_seed=123)
        usrp.set_rx_rate(2.0e6)
        samples = usrp.generate_samples(0, 2000000)  # 1.0 second capture
        assert len(samples) == 2000000
        assert samples.dtype == np.complex64

        # State 1 (first 400 ms) and State 2 (last 400 ms)
        s1 = samples[:800000]
        s2 = samples[1200000:]

        # Mean centroids
        v1 = complex(np.mean(s1))
        v2 = complex(np.mean(s2))

        # Check that centroids correspond to physics models:
        # V1 ~ 0.355 + 0.152j (|V1| ~ 0.38)
        # V2 ~ 0.260 + 0.105j (|V2| ~ 0.28)
        assert abs(v1.real - 0.355) < 0.02
        assert abs(v1.imag - 0.152) < 0.02
        assert abs(v2.real - 0.260) < 0.02
        assert abs(v2.imag - 0.105) < 0.02

    def test_detect_step_transition(self):
        sample_rate = 2.0e6
        usrp = MockMultiUSRP(mode="cw", switch_time=1.0, random_seed=42)
        samples = usrp.generate_samples(0, int(sample_rate * 2.0))  # 2.0 s capture

        switch_idx, s1, s2 = detect_step_transition(samples, sample_rate, guard_band_ms=10.0)
        detected_time_s = switch_idx / sample_rate

        # Detected switch time must be within 15 ms of nominal 1.00 s
        assert abs(detected_time_s - 1.00) < 0.015
        assert len(s1) > 0
        assert len(s2) > 0

    def test_differential_power_and_vector_metrics(self):
        sample_rate = 2.0e6
        usrp = MockMultiUSRP(mode="cw", switch_time=1.0, random_seed=42)
        samples = usrp.generate_samples(0, int(sample_rate * 2.0))

        switch_idx, s1, s2 = detect_step_transition(samples, sample_rate)
        delta_p_lin, delta_p_db = compute_differential_power(s1, s2)
        delta_v, v1_cen, v2_cen, delta_theta = compute_complex_vector_distance(s1, s2)
        scnr_lin, scnr_db = compute_scnr(s1, s2)

        # Differential vector Delta |V_rx| must be genuine and significant (> 0.08)
        assert delta_v > 0.08
        # SCNR must exceed 15 dB threshold
        assert scnr_db >= 15.0
        # Delta P_rx must be non-zero
        assert abs(delta_p_db) > 0.5

    def test_orthogonality_resilience_edge_case(self):
        """Verify that complex vector distance isolates backscatter when power delta vanishes."""
        # Consider carrier leakage V_leak = 1.0 + 0j
        # Tag State 1: delta_V1 = 0
        # Tag State 2: delta_V2 = 0 + 0.15j (orthogonal to V_leak!)
        np.random.seed(99)
        n = 10000
        noise = 0.005 * (np.random.randn(n) + 1j * np.random.randn(n))
        s1 = 1.0 + 0.0j + noise
        s2 = 1.0 + 0.15j + noise

        delta_p_lin, delta_p_db = compute_differential_power(s1, s2)
        delta_v, v1, v2, _ = compute_complex_vector_distance(s1, s2)

        # Scalar power change is negligible because |1.0 + 0.15j|^2 = 1.0225 (~0.09 dB)
        assert abs(delta_p_db) < 0.15
        # Vector distance detects the full tag reflection magnitude (|0.15j| = 0.15)
        assert abs(delta_v - 0.15) < 0.01

    def test_compute_moving_average_power(self):
        samples = np.ones(500, dtype=np.complex64) * (0.6 + 0.8j)  # |x|^2 = 1.0
        p_lin, p_db = compute_moving_average_power(samples, window_size=50)
        assert len(p_lin) == 500
        assert len(p_db) == 500
        assert np.allclose(p_lin, 1.0, atol=1e-3)
        assert np.allclose(p_db, 0.0, atol=1e-2)


class TestMode2AmbientWiFi:
    """Tests for Mode 2 Ambient Wi-Fi packet detection and backscatter modulation."""

    def test_wifi_synthetic_generation_and_packet_bursts(self):
        sample_rate = 2.0e6
        usrp = MockMultiUSRP(mode="wifi", switch_time=1.0, random_seed=42)
        samples = usrp.generate_samples(0, int(sample_rate * 2.0))
        assert len(samples) == int(sample_rate * 2.0)

        wifi_res = detect_wifi_packets(samples, sample_rate)
        assert wifi_res["num_bursts"] > 10
        assert wifi_res["beacon_count_s1"] >= 5
        assert wifi_res["beacon_count_s2"] >= 5

        # Beacon energy delta must be positive due to State 2 backscatter gain
        assert wifi_res["delta_beacon_db"] > 0.5
        # Beacon vector shift must be measurable
        assert wifi_res["delta_v_beacon"] > 0.01


class TestDataPersistence:
    """Tests for context-manager safe .npz persistence and Windows file lock immunity."""

    def test_npz_safe_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            npz_path = os.path.join(tmpdir, "test_backscatter.npz")
            test_iq = (np.random.randn(1000) + 1j * np.random.randn(1000)).astype(np.complex64)
            test_dict = {
                "iq": test_iq,
                "sample_rate": 2.0e6,
                "center_freq": 2.44e9,
                "mode": "cw",
                "delta_p_rx_db": 2.5,
                "delta_v_rx": 0.105,
                "scnr_db": 22.0,
            }

            # 1. Save
            save_backscatter_npz(npz_path, test_dict)
            assert os.path.exists(npz_path)

            # 2. Load
            loaded = load_backscatter_npz(npz_path)
            assert np.allclose(loaded["iq"], test_iq)
            assert loaded["sample_rate"] == 2.0e6
            assert loaded["mode"] == "cw"
            assert abs(loaded["delta_p_rx_db"] - 2.5) < 1e-4

            # 3. Test overwrite without PermissionError (WinError 32 prevention)
            save_backscatter_npz(npz_path, test_dict)
            # 4. Test immediate removal without file locking
            os.remove(npz_path)
            assert not os.path.exists(npz_path)


class TestPlotGeneration:
    """Tests for publication-quality 300 DPI plot generation and PNG integrity."""

    def test_plot_generation_binary_integrity(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sample_rate = 2.0e6
            usrp_cw = MockMultiUSRP(mode="cw", switch_time=0.5, random_seed=42)
            cw_samples = usrp_cw.generate_samples(0, int(sample_rate * 1.0))

            usrp_wifi = MockMultiUSRP(mode="wifi", switch_time=0.5, random_seed=42)
            wifi_samples = usrp_wifi.generate_samples(0, int(sample_rate * 1.0))

            fig_cw_step = os.path.join(tmpdir, "cw_step_response.png")
            fig_cw_iq = os.path.join(tmpdir, "cw_iq_trajectory.png")
            fig_wifi_ambient = os.path.join(tmpdir, "wifi_ambient_backscatter.png")
            fig_wifi_constellation = os.path.join(tmpdir, "wifi_iq_constellation.png")

            # Generate all 4 publication figures
            plot_cw_step_response(cw_samples, sample_rate, fig_cw_step)
            plot_cw_iq_trajectory(cw_samples, sample_rate, fig_cw_iq)
            plot_wifi_ambient_backscatter(wifi_samples, sample_rate, fig_wifi_ambient)
            plot_wifi_iq_constellation(wifi_samples, sample_rate, fig_wifi_constellation)

            for fig_path in [fig_cw_step, fig_cw_iq, fig_wifi_ambient, fig_wifi_constellation]:
                assert os.path.exists(fig_path), f"Figure missing: {fig_path}"
                assert os.path.getsize(fig_path) > 15000, f"Figure too small: {fig_path}"
                with open(fig_path, "rb") as f:
                    header = f.read(8)
                assert header == b"\x89PNG\r\n\x1a\n", f"Invalid PNG header: {fig_path}"


class TestCLIExecution:
    """End-to-end test of master CLI in both modes."""

    def test_cli_mode_cw_execution(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            args = parse_arguments([
                "--mode", "cw",
                "--freq", "2.44e9",
                "--rate", "2.0e6",
                "--duration", "1.0",
                "--mock",
                "--output-dir", tmpdir,
            ])
            results = run_backscatter(args)
            assert results["mode"] == "cw"
            assert results["delta_v_rx"] > 0.08
            assert results["scnr_db"] >= 15.0
            assert os.path.exists(results["fig_step_response"])
            assert os.path.exists(results["fig_iq_trajectory"])
            assert os.path.exists(results["npz_path"])

    def test_cli_mode_wifi_execution(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            args = parse_arguments([
                "--mode", "wifi",
                "--freq", "2.437e9",
                "--rate", "2.0e6",
                "--duration", "1.0",
                "--mock",
                "--output-dir", tmpdir,
            ])
            results = run_backscatter(args)
            assert results["mode"] == "wifi"
            assert results["wifi_num_bursts"] > 0
            assert results["delta_beacon_db"] > 0.0
            assert os.path.exists(results["fig_ambient_backscatter"])
            assert os.path.exists(results["fig_iq_constellation"])
            assert os.path.exists(results["npz_path"])
