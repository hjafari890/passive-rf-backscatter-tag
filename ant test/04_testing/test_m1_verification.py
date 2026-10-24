"""Test and verification script for M1 Antenna Simulation and Differential RCS."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from antenna_simulation.antenna_models import (
    PlanarMeanderMonopole,
    PlanarMonopole244,
    TI_SWRA117D_IFA,
    TI_SWRA416_Helical,
    calculate_resonance,
    calculate_s11,
    calculate_zin,
)
from antenna_simulation.rcs_simulation import (
    ABSORBING_50OHM,
    REFLECTING_OPEN,
    REFLECTING_SHORT,
    analyze_all_state_pairs,
    compute_delta_gamma,
    compute_differential_rcs,
    verify_delta_gamma_contrast,
)


def run_checks():
    print("=" * 70)
    print("M1: ANTENNA MODELING & DIFFERENTIAL RCS VERIFICATION")
    print("=" * 70)

    # 1. Verify Antenna Models
    antennas = [
        PlanarMonopole244(),
        TI_SWRA117D_IFA(),
        TI_SWRA416_Helical(center_frequency=915e6),
        PlanarMeanderMonopole(center_frequency=915e6),
    ]

    for ant in antennas:
        f0 = ant.center_frequency
        zin0 = ant.input_impedance(f0)
        s11_0 = ant.return_loss_db(f0)
        vswr_0 = ant.vswr(f0)
        print(f"\n[Antenna: {ant.name}]")
        print(f"  Center Frequency: {f0 / 1e6:.1f} MHz")
        print(f"  Peak Gain:        {ant.gain_dbi:+.2f} dBi (linear: {ant.gain_linear:.3f})")
        print(f"  Zin(f0):          {zin0.real:.2f} + j{zin0.imag:.2f} Ohm")
        print(f"  Return Loss S11:  {s11_0:.2f} dB")
        print(f"  VSWR:             {vswr_0:.2f}:1")
        assert s11_0 <= -15.0, f"FAILED: S11={s11_0:.2f} dB > -15.0 dB for {ant.name}"
        assert abs(zin0.imag) <= 5.0, f"FAILED: Non-resonant reactance |Xin| > 5 Ohm"

    # 2. Verify Load Reflection States and Contrast
    print("\n" + "-" * 70)
    print("LOAD MODULATION STATES & CONTRAST VERIFICATION")
    print("-" * 70)
    g_50 = ABSORBING_50OHM.reflection_coefficient()
    g_short = REFLECTING_SHORT.reflection_coefficient()
    g_open = REFLECTING_OPEN.reflection_coefficient()

    print(f"  State 1 (50 Ohm SMD): Gamma = {g_50.real:+.4f} + j{g_50.imag:+.4f} (|Gamma| = {abs(g_50):.4f})")
    print(f"  State 2 (Short Jumper): Gamma = {g_short.real:+.4f} + j{g_short.imag:+.4f} (|Gamma| = {abs(g_short):.4f})")
    print(f"  State 3 (Open Terminals): Gamma = {g_open.real:+.4f} + j{g_open.imag:+.4f} (|Gamma| = {abs(g_open):.4f})")

    passes_short, mag_short = verify_delta_gamma_contrast(g_short, g_50, min_contrast=1.0)
    print(f"  |Delta Gamma| (Short - 50 Ohm): {mag_short:.4f} -> Passes >= 1.0: {passes_short}")
    assert passes_short, f"FAILED: |Delta Gamma| = {mag_short} < 1.0"

    passes_open, mag_open = verify_delta_gamma_contrast(g_open, g_50, min_contrast=1.0)
    print(f"  |Delta Gamma| (Open - 50 Ohm):  {mag_open:.4f} -> Passes >= 1.0: {passes_open}")
    assert passes_open, f"FAILED: |Delta Gamma| = {mag_open} < 1.0"

    delta_bpsk = compute_delta_gamma(g_open, g_short)
    mag_bpsk = abs(delta_bpsk)
    print(f"  |Delta Gamma| (Open - Short):   {mag_bpsk:.4f} -> Expected 2.0")
    assert abs(mag_bpsk - 2.0) < 0.01, f"FAILED: BPSK contrast {mag_bpsk} != 2.0"

    # 3. Verify Differential RCS Exact Values
    print("\n" + "-" * 70)
    print("DIFFERENTIAL RADAR CROSS SECTION (RCS) VERIFICATION")
    print("-" * 70)

    # Option A (2.44 GHz IFA, Gain +2.1 dBi)
    ifa = TI_SWRA117D_IFA()
    rcs_244 = compute_differential_rcs(
        np.array([2.440e9]), ifa.gain_linear, delta_gamma=(g_short - g_50)
    )
    sigma_cm2_244 = float(rcs_244["delta_sigma_cm2"][0])
    sigma_dbsm_244 = float(rcs_244["delta_sigma_dbsm"][0])
    print(f"  Option A (2.44 GHz IFA, G={ifa.gain_dbi:+.2f} dBi):")
    print(f"    Delta sigma (50 vs Short): {sigma_cm2_244:.2f} cm^2 ({sigma_dbsm_244:.2f} dBsm)")
    assert 25.0 <= sigma_cm2_244 <= 35.0, f"Unexpected Delta sigma: {sigma_cm2_244} cm^2"

    # Option B (915 MHz Helical, Gain -1.5 dBi)
    helical = TI_SWRA416_Helical(915e6)
    rcs_915 = compute_differential_rcs(
        np.array([915.0e6]), helical.gain_linear, delta_gamma=(g_short - g_50)
    )
    sigma_cm2_915 = float(rcs_915["delta_sigma_cm2"][0])
    sigma_dbsm_915 = float(rcs_915["delta_sigma_dbsm"][0])
    print(f"  Option B (915 MHz Helical, G={helical.gain_dbi:+.2f} dBi):")
    print(f"    Delta sigma (50 vs Short): {sigma_cm2_915:.2f} cm^2 ({sigma_dbsm_915:.2f} dBsm)")
    assert 38.0 <= sigma_cm2_915 <= 48.0, f"Unexpected Delta sigma: {sigma_cm2_915} cm^2"

    # Option B2 (915 MHz Meander, Gain +0.8 dBi)
    meander = PlanarMeanderMonopole(915e6)
    rcs_meander = compute_differential_rcs(
        np.array([915.0e6]), meander.gain_linear, delta_gamma=(g_short - g_50)
    )
    sigma_cm2_m = float(rcs_meander["delta_sigma_cm2"][0])
    sigma_dbsm_m = float(rcs_meander["delta_sigma_dbsm"][0])
    print(f"  Option B2 (915 MHz Meander, G={meander.gain_dbi:+.2f} dBi):")
    print(f"    Delta sigma (50 vs Short): {sigma_cm2_m:.2f} cm^2 ({sigma_dbsm_m:.2f} dBsm)")
    assert 110.0 <= sigma_cm2_m <= 135.0, f"Unexpected Delta sigma: {sigma_cm2_m} cm^2"

    print("\n" + "=" * 70)
    print("ALL M1 ELECTRODYNAMIC AND RCS CHECKS PASSED PERFECTLY!")
    print("=" * 70)


if __name__ == "__main__":
    run_checks()
