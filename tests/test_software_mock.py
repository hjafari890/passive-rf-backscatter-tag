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
