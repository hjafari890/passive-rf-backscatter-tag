"""Verification tests for electrodynamic antenna models and Harrington RCS simulation."""

from __future__ import annotations

import os
import sys
import numpy as np
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from simulation.antenna_models import (
    get_antenna,
    calculate_s11,
    calculate_resonance,
)
from simulation.rcs_simulation import (
    compute_gamma_l,
    compute_delta_gamma,
    compute_differential_rcs,
)


class TestSimulationModels:
    """Verifies that the electrodynamic solvers compute accurate physical responses."""

    def test_board1_ifa_resonance(self) -> None:
        """Board 1 IFA must exhibit a clean resonant dip near 2.44 GHz with S11 < -15 dB."""
        ifa = get_antenna("ifa")
        freqs = np.linspace(2.0e9, 3.0e9, 201)
        s11_db = calculate_s11(ifa, freqs, z0=50.0)

        min_idx = np.argmin(s11_db)
        f_res = freqs[min_idx]
        s11_min = s11_db[min_idx]

        assert abs(f_res - 2.44e9) < 0.1e9, f"IFA resonance offset too large: {f_res/1e9:.3f} GHz"
        assert s11_min < -15.0, f"IFA return loss at resonance insufficient: {s11_min:.1f} dB"

    def test_board2_meander_resonance(self) -> None:
        """Board 2 Meander must resonate in the Sub-1GHz ISM band (868-915 MHz)."""
        meander = get_antenna("meander")
        freqs = np.linspace(700.0e6, 1100.0e6, 201)
        s11_db = calculate_s11(meander, freqs, z0=50.0)

        min_idx = np.argmin(s11_db)
        f_res = freqs[min_idx]
        s11_min = s11_db[min_idx]

        assert 800.0e6 <= f_res <= 960.0e6, f"Meander resonance outside Sub-1GHz: {f_res/1e6:.1f} MHz"
        assert s11_min < -12.0, f"Meander return loss insufficient: {s11_min:.1f} dB"

    def test_harrington_delta_gamma(self) -> None:
        """Verify Harrington reflection coefficients: State 1 (50 Ohm) vs State 2 (0 Ohm)."""
        z_ant = 50.0 + 0j
        gamma_50 = compute_gamma_l(50.0 + 0j, z_ant)
        gamma_short = compute_gamma_l(0.0 + 0j, z_ant)
        gamma_open = compute_gamma_l(1e9 + 0j, z_ant)

        # State 1 (matched) should have reflection near 0
        assert abs(gamma_50) < 1e-6
        # State 2 (short) should have reflection near -1
        assert abs(gamma_short - (-1.0)) < 1e-6
        # State 3 (open) should have reflection near +1
        assert abs(gamma_open - 1.0) < 1e-4

        # Contrast between absorb and reflect
        delta = compute_delta_gamma(gamma_50, gamma_short)
        assert abs(delta - 1.0) < 1e-4

        # Contrast between open and short
        delta_phase = compute_delta_gamma(gamma_open, gamma_short)
        assert abs(delta_phase - 2.0) < 1e-4
