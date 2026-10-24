"""Verification tests for SDR software, mock USRP generator, and GUI lifecycle."""

from __future__ import annotations

import os
import sys
import time
import tkinter as tk
import numpy as np
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
if os.path.join(REPO_ROOT, "software") not in sys.path:
    sys.path.insert(0, os.path.join(REPO_ROOT, "software"))

from software.mock_usrp import MockMultiUSRP
from software.backscatter_metrics import (
    compute_complex_vector_distance,
    compute_differential_power,
    compute_moving_average_power,
)
from software.backscatter_gui_app import BackscatterTkGUI


class TestSoftwareMock:
    """Tests the software suite in mock / headless mode."""

    def test_mock_usrp_streaming(self) -> None:
        """Verify MockMultiUSRP generates non-zero complex samples."""
        mock = MockMultiUSRP(mode="cw")
        samples = mock.generate_samples(start_idx=0, count=1024)
        assert len(samples) == 1024
        assert np.iscomplexobj(samples)
        assert np.mean(np.abs(samples)) > 0.0, "Mock USRP returned all-zero samples"

    def test_backscatter_metrics(self) -> None:
        """Verify differential power and vector distance calculations."""
        # 2 states with 180 deg phase inversion
        iq1 = np.ones(500, dtype=np.complex64) * (1.0 + 0.0j)
        iq2 = np.ones(500, dtype=np.complex64) * (-1.0 + 0.0j)

        delta_v_mag, v1, v2, delta_phi = compute_complex_vector_distance(iq1, iq2)
        assert abs(delta_v_mag - 2.0) < 1e-4, f"Vector distance expected 2.0, got {delta_v_mag}"
        assert abs(abs(delta_phi) - 180.0) < 1e-2, f"Expected 180 deg phase flip, got {delta_phi}"

    def test_tkinter_gui_mock_lifecycle(self) -> None:
        """Verify Tkinter GUI initializes in mock mode, transitions states, and exits cleanly."""
        root = tk.Tk()
        app = BackscatterTkGUI(root, force_mock=True)

        assert app.current_mode_key == "mode1"
        app.apply_mode_config("mode2")
        assert app.current_mode_key == "mode2"

        # Toggle streaming on
        app.toggle_streaming()
        assert app.worker is not None and app.worker.is_alive()

        # Pump Tkinter loop for 0.5s
        app.root.after(500, app.root.quit)
        app.root.mainloop()

        # Stop streaming and destroy
        app.toggle_streaming()
        assert app.worker is None
        app.root.destroy()

    def test_gui_cli_help(self) -> None:
        """Verify that backscatter_gui_app.py --help executes cleanly with code 0."""
        import subprocess

        cmd = [
            sys.executable,
            os.path.join(REPO_ROOT, "software", "backscatter_gui_app.py"),
            "--help",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        assert res.returncode == 0, f"GUI --help failed: {res.stderr}"
        assert "--mock" in res.stdout, "Expected --mock flag documented in help output"

    def test_plot_backscatter_results(self, tmp_path) -> None:
        """Verify publication plotting functions in software/plot_backscatter_results.py."""
        from software.plot_backscatter_results import (
            plot_cw_step_response,
            plot_cw_iq_trajectory,
        )

        n_samples = 1000
        iq_cw = np.random.normal(0, 0.01, n_samples) + 1j * np.random.normal(0, 0.01, n_samples)
        # Add step in second half
        iq_cw[500:] += 0.05 + 0.05j

        out_step = str(tmp_path / "test_step.png")
        out_traj = str(tmp_path / "test_traj.png")

        plot_cw_step_response(iq_cw, sample_rate=2e6, output_path=out_step)
        plot_cw_iq_trajectory(iq_cw, sample_rate=2e6, output_path=out_traj)

        assert os.path.isfile(out_step) and os.path.getsize(out_step) > 1000
        assert os.path.isfile(out_traj) and os.path.getsize(out_traj) > 1000

    def test_plot_backscatter_results_cli(self, tmp_path) -> None:
        """Verify that software/plot_backscatter_results.py CLI generates all 4 publication plots."""
        import subprocess

        cmd = [
            sys.executable,
            os.path.join(REPO_ROOT, "software", "plot_backscatter_results.py"),
            "--outdir",
            str(tmp_path),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        assert res.returncode == 0, f"plot_backscatter_results.py CLI failed: {res.stderr}"

        expected_plots = [
            "cw_step_response.png",
            "cw_iq_trajectory.png",
            "wifi_ambient_backscatter.png",
            "wifi_iq_constellation.png",
        ]
        for plot_name in expected_plots:
            p = tmp_path / plot_name
            assert p.is_file(), f"Missing plot: {plot_name}"
            assert p.stat().st_size > 1000, f"Plot {plot_name} is too small"

    def test_gnuradio_script_cli_help(self) -> None:
        """Verify that backscatter_detector_gnuradio.py --help executes cleanly with code 0."""
        import subprocess

        script_path = os.path.join(REPO_ROOT, "software", "gnuradio", "backscatter_detector_gnuradio.py")

        # Test with current Python environment (standard Python)
        res = subprocess.run([sys.executable, script_path, "--help"], capture_output=True, text=True, timeout=10)
        assert res.returncode == 0, f"GNU Radio script --help failed with standard Python: {res.stderr}"
        assert "--help" in res.stdout or "-h" in res.stdout

        # Also test with Radioconda Python if available
        for p in [os.path.expanduser(r"~\radioconda\python.exe"), r"C:\radioconda\python.exe"]:
            if os.path.isfile(p):
                res_rc = subprocess.run([p, script_path, "--help"], capture_output=True, text=True, timeout=10)
                assert res_rc.returncode == 0, f"GNU Radio script --help failed with Radioconda: {res_rc.stderr}"
                assert "--help" in res_rc.stdout or "-h" in res_rc.stdout
                break

