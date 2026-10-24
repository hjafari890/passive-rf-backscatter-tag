"""Unit tests for Antenna Models, Reflection Coefficients, and Differential RCS."""

import math
import sys
from pathlib import Path

import numpy as np
import unittest

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from antenna_simulation.antenna_models import (
    SPEED_OF_LIGHT,
    PlanarMeanderMonopole,
    PlanarMonopole244,
    Substrate,
    TI_SWRA117D_IFA,
    TI_SWRA416_Helical,
    calculate_resonance,
    calculate_s11,
    calculate_zin,
    get_antenna,
)
from antenna_simulation.rcs_simulation import (
    ABSORBING_50OHM,
    REFLECTING_OPEN,
    REFLECTING_SHORT,
    analyze_all_state_pairs,
    compute_delta_gamma,
    compute_differential_rcs,
    compute_gamma_l,
    verify_delta_gamma_contrast,
)


class TestAntennaModels(unittest.TestCase):
    """Tests covering Features F01, F02, and F03."""

    def test_substrate_properties(self):
        sub = Substrate()
        assert sub.thickness_m == 0.0016
        assert sub.eps_r == 4.40
        assert sub.tan_d == 0.020
        assert sub.copper_thickness_m == 35e-6
        assert sub.copper_conductivity == 5.8e7

    def test_f01_planar_monopole_244(self):
        ant = PlanarMonopole244()
        assert ant.center_frequency == 2.440e9
        assert ant.gain_dbi == 2.05
        assert ant.band == "2.44GHz"
        assert math.isclose(ant.gain_linear, 10.0 ** (2.05 / 10.0), rel_tol=1e-5)

        # Check Zin at resonance
        zin0 = ant.input_impedance(ant.center_frequency)
        assert abs(zin0.imag) < 1.0, f"Reactance {zin0.imag} not near 0 at resonance"
        assert 40.0 <= zin0.real <= 50.0, f"Real impedance {zin0.real} out of expected range"

        # Check S11 <= -15 dB
        s11 = ant.return_loss_db(ant.center_frequency)
        assert s11 <= -15.0, f"S11 {s11} dB > -15 dB"

        # Check VSWR < 1.5
        vswr = ant.vswr(ant.center_frequency)
        assert 1.0 <= vswr < 1.5

        # Check vector evaluation
        f_arr = np.linspace(2.3e9, 2.6e9, 50)
        zin_arr = ant.input_impedance(f_arr)
        assert len(zin_arr) == 50
        assert isinstance(zin_arr, np.ndarray)

    def test_f02_ti_swra117d_ifa(self):
        ant = TI_SWRA117D_IFA()
        assert ant.center_frequency == 2.440e9
        assert ant.gain_dbi == 2.10
        assert ant.band == "2.44GHz"

        # Check dimensions
        assert ant.dimensions_mm["envelope_x_mm"] == 15.2
        assert ant.dimensions_mm["envelope_y_mm"] == 5.7
        assert ant.dimensions_mm["shorting_stub_width_mm"] == 0.90
        assert ant.dimensions_mm["feed_pitch_mm"] == 2.10

        # Check 50 Ohm match at resonance
        zin0 = ant.input_impedance(ant.center_frequency)
        assert math.isclose(zin0.real, 50.0, rel_tol=1e-2), f"Re(Zin) = {zin0.real} != 50 Ohm"
        assert abs(zin0.imag) < 1.0, f"Im(Zin) = {zin0.imag} != 0 Ohm"

        # S11 <= -20 dB
        s11 = ant.return_loss_db(ant.center_frequency)
        assert s11 <= -20.0, f"S11 = {s11} dB > -20 dB"
        assert ant.vswr(ant.center_frequency) < 1.25

    def test_f03_ti_swra416_helical(self):
        # 915 MHz US ISM
        ant_915 = TI_SWRA416_Helical(center_frequency=915.0e6)
        assert ant_915.center_frequency == 915.0e6
        assert ant_915.gain_dbi == -1.50
        assert ant_915.dimensions_mm["via_count"] == 19
        assert ant_915.dimensions_mm["via_drill_mm"] == 0.40

        # Check raw untuned impedance
        z_raw = ant_915.raw_antenna_impedance(915e6)
        assert 10.0 <= z_raw.real <= 15.0
        assert 100.0 <= z_raw.imag <= 125.0

        # Check matched input impedance
        zin_matched = ant_915.input_impedance(915e6)
        assert math.isclose(zin_matched.real, 50.0, rel_tol=1e-2)
        assert abs(zin_matched.imag) < 1.0
        assert ant_915.return_loss_db(915e6) <= -20.0

        # 868 MHz EU SRD
        ant_868 = TI_SWRA416_Helical(center_frequency=868.0e6)
        assert ant_868.center_frequency == 868.0e6
        zin_868 = ant_868.input_impedance(868e6)
        assert math.isclose(zin_868.real, 50.0, rel_tol=1e-2)
        assert ant_868.return_loss_db(868e6) <= -20.0

    def test_f03_planar_meander_monopole(self):
        ant = PlanarMeanderMonopole(center_frequency=915.0e6)
        assert ant.center_frequency == 915.0e6
        assert ant.gain_dbi == 0.80
        assert ant.dimensions_mm["developed_length_mm"] == 74.5
        assert ant.dimensions_mm["gap_spacing_mm"] == 1.00

        zin0 = ant.input_impedance(915e6)
        assert 45.0 <= zin0.real <= 52.0
        assert abs(zin0.imag) < 1.0
        assert ant.return_loss_db(915e6) <= -20.0

    def test_factory_and_resonance_finder(self):
        a1 = get_antenna("option_a1")
        assert isinstance(a1, PlanarMonopole244)

        a2 = get_antenna("option_a2")
        assert isinstance(a2, TI_SWRA117D_IFA)

        b1 = get_antenna("option_b1")
        assert isinstance(b1, TI_SWRA416_Helical)

        b2 = get_antenna("option_b2")
        assert isinstance(b2, PlanarMeanderMonopole)

        with self.assertRaises(ValueError):
            get_antenna("unknown_antenna")

        # Test calculate_resonance
        f_res = calculate_resonance(a1, (2.3e9, 2.6e9))
        assert math.isclose(f_res, 2.440e9, rel_tol=1e-3)


class TestRcsSimulation(unittest.TestCase):
    """Tests covering Features F04 and F05."""

    def test_f04_load_reflection_coefficients(self):
        g_50 = compute_gamma_l(50.0, z_0=50.0)
        assert abs(g_50) == 0.0

        g_short = compute_gamma_l(0.0, z_0=50.0)
        assert abs(g_short + 1.0) < 1e-6  # Gamma = -1.0

        g_open = compute_gamma_l(float("inf"), z_0=50.0)
        assert abs(g_open - 1.0) < 1e-6  # Gamma = +1.0

        # State objects
        assert abs(ABSORBING_50OHM.reflection_coefficient()) < 1e-3
        assert abs(REFLECTING_SHORT.reflection_coefficient() + 1.0) < 1e-3
        assert abs(REFLECTING_OPEN.reflection_coefficient() - 1.0) < 1e-3

    def test_f04_delta_gamma_contrast_requirement(self):
        """Prove that |Delta Gamma| = |Gamma_short - Gamma_50ohm| >= 1.0."""
        g_50 = ABSORBING_50OHM.reflection_coefficient()
        g_short = REFLECTING_SHORT.reflection_coefficient()
        g_open = REFLECTING_OPEN.reflection_coefficient()

        passes, mag = verify_delta_gamma_contrast(g_short, g_50, min_contrast=1.0)
        assert passes is True
        assert mag >= 1.0

        # Verify Open vs 50 Ohm
        passes_open, mag_open = verify_delta_gamma_contrast(g_open, g_50, min_contrast=1.0)
        assert passes_open is True
        assert mag_open >= 1.0

        # Verify BPSK Short vs Open contrast
        dg_bpsk = compute_delta_gamma(g_open, g_short)
        assert abs(abs(dg_bpsk) - 2.0) < 0.01

    def test_f05_differential_rcs_values(self):
        """Verify exact numerical values of Delta sigma across frequencies."""
        # 2.44 GHz IFA: Gain = +2.1 dBi (linear 1.6218), lambda = 0.122866 m
        ifa = TI_SWRA117D_IFA()
        f_arr = np.array([2.440e9])
        rcs_244 = compute_differential_rcs(f_arr, ifa.gain_linear, delta_gamma=-1.0)

        lambda_calc = SPEED_OF_LIGHT / 2.440e9
        a0_expected = (lambda_calc**2) / (4.0 * math.pi)
        sigma_expected_m2 = a0_expected * (ifa.gain_linear**2) * (1.0**2)
        sigma_expected_cm2 = sigma_expected_m2 * 1e4

        assert math.isclose(rcs_244["delta_sigma_cm2"][0], sigma_expected_cm2, rel_tol=1e-4)
        assert 30.0 <= rcs_244["delta_sigma_cm2"][0] <= 33.0
        assert -25.5 <= rcs_244["delta_sigma_dbsm"][0] <= -24.5

        # 915 MHz Helical: Gain = -1.5 dBi (linear 0.7079), lambda = 0.32764 m
        hel = TI_SWRA416_Helical(915e6)
        rcs_915 = compute_differential_rcs(np.array([915.0e6]), hel.gain_linear, delta_gamma=-1.0)
        assert 40.0 <= rcs_915["delta_sigma_cm2"][0] <= 45.0
        assert -24.0 <= rcs_915["delta_sigma_dbsm"][0] <= -23.0

        # Compare with Open vs Short (BPSK, |Delta Gamma| = 2.0)
        # Delta sigma should be exactly 4x higher (+6.02 dB)
        rcs_bpsk = compute_differential_rcs(np.array([915.0e6]), hel.gain_linear, delta_gamma=2.0)
        assert math.isclose(rcs_bpsk["delta_sigma_cm2"][0], 4.0 * rcs_915["delta_sigma_cm2"][0], rel_tol=1e-4)
        assert math.isclose(rcs_bpsk["delta_sigma_dbsm"][0], rcs_915["delta_sigma_dbsm"][0] + 10 * math.log10(4), rel_tol=1e-3)

    def test_state_pair_analysis(self):
        ifa = TI_SWRA117D_IFA()
        freqs = np.array([2.40e9, 2.44e9, 2.48e9])
        results = analyze_all_state_pairs(freqs, ifa.gain_linear)

        assert "short_vs_50ohm" in results
        assert "open_vs_50ohm" in results
        assert "open_vs_short" in results
        assert results["short_vs_50ohm"]["delta_gamma_mag"] >= 0.999
        assert results["open_vs_short"]["delta_gamma_mag"] >= 1.999


if __name__ == "__main__":
    unittest.main()
