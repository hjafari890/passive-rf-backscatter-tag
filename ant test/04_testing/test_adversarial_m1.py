"""Adversarial Test Harness for Milestone 1: Antenna Modeling and Differential RCS.

This suite stress-tests:
1. Boundary conditions and extreme frequencies (DC, negative f, mmWave 100 GHz, empty arrays).
2. Electrodynamic scaling laws (lambda^2, G^2, |Delta Gamma|^2).
3. Realistic component parasitics and tolerance space (47-53 Ohm, ESL, contact resistance).
4. Physical fidelity and dielectric parameter sensitivity.
5. Numerical singularities (division by zero, negative resistance, invalid inputs).
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

# Ensure project root is in path
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
    evaluate_realistic_parasitics,
    verify_delta_gamma_contrast,
)


class TestResult:
    def __init__(self, name: str, passed: bool, details: str, severity: str = "INFO"):
        self.name = name
        self.passed = passed
        self.details = details
        self.severity = severity  # INFO, MINOR, MAJOR, CRITICAL

    def __repr__(self) -> str:
        status = "PASS" if self.passed else f"FAIL [{self.severity}]"
        return f"{status} - {self.name}: {self.details}"


def test_realistic_parasitics_and_tolerances() -> List[TestResult]:
    """Test Challenge 1: Operational |Delta Gamma| >= 0.85 across realistic RF components."""
    results: List[TestResult] = []

    # Nominal baseline: Ideal Short vs 50 Ohm must strictly achieve |Delta Gamma| = 1.0000 >= 1.0
    g_short_ideal = compute_gamma_l(0.0, 50.0)
    g_50_ideal = compute_gamma_l(50.0, 50.0)
    dg_ideal = abs(compute_delta_gamma(g_short_ideal, g_50_ideal))
    passes_ideal, _ = verify_delta_gamma_contrast(g_short_ideal, g_50_ideal, min_contrast=1.0)
    results.append(
        TestResult(
            "Ideal Baseline |Delta Gamma|",
            passes_ideal and math.isclose(dg_ideal, 1.0, abs_tol=1e-6),
            f"|Delta Gamma| = {dg_ideal:.6f}",
        )
    )

    # 1. Resistor Tolerance alone (pure resistance, 47 to 53 Ohm)
    res_tolerances = [47.0, 48.0, 49.0, 49.5, 49.9, 50.0, 50.1, 50.5, 51.0, 52.0, 53.0]
    sub_1_count = 0
    sub_1_details = []
    for r in res_tolerances:
        g_r = compute_gamma_l(r, 50.0)
        dg = abs(compute_delta_gamma(g_short_ideal, g_r))
        passes, _ = verify_delta_gamma_contrast(g_short_ideal, g_r, allow_tolerance=True)
        if not passes:
            sub_1_count += 1
            sub_1_details.append(f"R={r} Ohm -> |Delta Gamma|={dg:.5f}")

    results.append(
        TestResult(
            "Resistor Tolerance Sweep (47-53 Ohm) vs Ideal Short",
            sub_1_count == 0,
            f"{sub_1_count}/{len(res_tolerances)} failed operational contrast (>= 0.85): {sub_1_details}",
            severity="HIGH" if sub_1_count > 0 else "INFO",
        )
    )

    # 2. Jumper contact resistance alone (0.01 to 0.5 Ohm)
    contact_resistances = [0.01, 0.05, 0.1, 0.2, 0.5]
    jumper_fail_count = 0
    jumper_details = []
    for r_c in contact_resistances:
        g_j = compute_gamma_l(r_c, 50.0)
        dg = abs(compute_delta_gamma(g_j, g_50_ideal))
        passes, _ = verify_delta_gamma_contrast(g_j, g_50_ideal, allow_tolerance=True)
        if not passes:
            jumper_fail_count += 1
            jumper_details.append(f"Rc={r_c} Ohm -> |Delta Gamma|={dg:.5f}")

    results.append(
        TestResult(
            "Jumper Contact Resistance (0.01-0.5 Ohm) vs Ideal 50 Ohm",
            jumper_fail_count == 0,
            f"{jumper_fail_count}/{len(contact_resistances)} failed operational contrast (>= 0.85): {jumper_details}",
            severity="HIGH" if jumper_fail_count > 0 else "INFO",
        )
    )

    # 3. Comprehensive RF Parasitic Grid at 2.44 GHz
    # R_smd in [47, 50, 53] Ohm, L_esl in [0.0, 0.5, 1.0] nH
    # R_jumper in [0.01, 0.1] Ohm, L_jumper in [0.0, 0.5, 1.5] nH
    f = 2.440e9
    omega = 2.0 * math.pi * f
    grid_total = 0
    grid_fails = 0
    min_dg = 999.0
    max_dg = 0.0
    worst_case = ""

    for r_smd in [47.0, 49.9, 50.0, 53.0]:
        for l_esl in [0.0e-9, 0.5e-9, 1.0e-9]:
            z_smd = complex(r_smd, omega * l_esl)
            g_smd = compute_gamma_l(z_smd, 50.0)

            for r_j in [0.0, 0.05, 0.1]:
                for l_j in [0.0e-9, 0.5e-9, 1.5e-9]:
                    z_j = complex(r_j, omega * l_j)
                    g_j = compute_gamma_l(z_j, 50.0)

                    dg = abs(compute_delta_gamma(g_j, g_smd))
                    passes, _ = verify_delta_gamma_contrast(g_j, g_smd, allow_tolerance=True)
                    grid_total += 1
                    if dg < min_dg:
                        min_dg = dg
                        worst_case = f"R_smd={r_smd}, L_esl={l_esl*1e9:.1f}nH, R_j={r_j}, L_j={l_j*1e9:.1f}nH"
                    if dg > max_dg:
                        max_dg = dg
                    if not passes:
                        grid_fails += 1

    results.append(
        TestResult(
            "Full RF Parasitics Grid at 2.44 GHz",
            grid_fails == 0,
            f"Grid fails: {grid_fails}/{grid_total}. Min |Delta Gamma| = {min_dg:.4f} ({worst_case}), Max = {max_dg:.4f}",
            severity="HIGH" if grid_fails > 0 else "INFO",
        )
    )

    # 4. Check if modulation contrast is practically viable (>= 0.85) and verify evaluate_realistic_parasitics
    eval_worst = evaluate_realistic_parasitics(f, 47.0, 1.0e-9, 0.1, 1.5e-9)
    practical_pass = (min_dg >= 0.85) and (eval_worst["operational_contrast_pass"] is True)
    results.append(
        TestResult(
            "Practical Modulation Contrast Robustness (|Delta Gamma| >= 0.85)",
            practical_pass,
            f"Worst-case |Delta Gamma| = {min_dg:.4f} >= 0.85 (SDR can reliably detect step response, loss = {eval_worst['contrast_loss_db']:.2f} dB)",
            severity="INFO" if practical_pass else "CRITICAL",
        )
    )

    return results


def test_electrodynamic_scaling_laws() -> List[TestResult]:
    """Test Challenge 2: Verification of physics equations and scaling laws."""
    results: List[TestResult] = []

    # 1. Frequency / Wavelength Scaling: Delta sigma proportional to lambda^2 (1 / f^2)
    # If f doubles, Delta sigma must decrease by exactly a factor of 4 (-6.0206 dB)
    f1 = np.array([1.0e9])
    f2 = np.array([2.0e9])
    f4 = np.array([4.0e9])
    gain_const = 1.622  # linear gain

    rcs1 = compute_differential_rcs(f1, gain_const, delta_gamma=1.0)["delta_sigma_m2"][0]
    rcs2 = compute_differential_rcs(f2, gain_const, delta_gamma=1.0)["delta_sigma_m2"][0]
    rcs4 = compute_differential_rcs(f4, gain_const, delta_gamma=1.0)["delta_sigma_m2"][0]

    ratio_2_1 = rcs1 / rcs2
    ratio_4_2 = rcs2 / rcs4
    f_scaling_pass = math.isclose(ratio_2_1, 4.0, rel_tol=1e-12) and math.isclose(ratio_4_2, 4.0, rel_tol=1e-12)
    results.append(
        TestResult(
            "Wavelength Squared Scaling Law (lambda^2 proportional to 1/f^2)",
            f_scaling_pass,
            f"Ratio f1/f2 = {ratio_2_1:.10f} (expected 4.0), Ratio f2/f4 = {ratio_4_2:.10f} (expected 4.0)",
            severity="CRITICAL" if not f_scaling_pass else "INFO",
        )
    )

    # 2. Gain Squared Scaling: Delta sigma proportional to G^2
    # If G doubles, Delta sigma must increase by exactly 4x
    g1 = 1.0
    g2 = 2.0
    g4 = 4.0
    rcs_g1 = compute_differential_rcs(f1, g1, delta_gamma=1.0)["delta_sigma_m2"][0]
    rcs_g2 = compute_differential_rcs(f1, g2, delta_gamma=1.0)["delta_sigma_m2"][0]
    rcs_g4 = compute_differential_rcs(f1, g4, delta_gamma=1.0)["delta_sigma_m2"][0]

    g_ratio_2_1 = rcs_g2 / rcs_g1
    g_ratio_4_2 = rcs_g4 / rcs_g2
    g_scaling_pass = math.isclose(g_ratio_2_1, 4.0, rel_tol=1e-12) and math.isclose(g_ratio_4_2, 4.0, rel_tol=1e-12)
    results.append(
        TestResult(
            "Gain Squared Scaling Law (Delta sigma proportional to G^2)",
            g_scaling_pass,
            f"Ratio G2/G1 = {g_ratio_2_1:.10f} (expected 4.0), Ratio G4/G2 = {g_ratio_4_2:.10f} (expected 4.0)",
            severity="CRITICAL" if not g_scaling_pass else "INFO",
        )
    )

    # 3. Delta Gamma Squared Scaling: Delta sigma proportional to |Delta Gamma|^2
    # Short vs 50 Ohm (|Delta Gamma| = 1.0) vs Open vs Short (|Delta Gamma| = 2.0) -> Exactly 4x
    rcs_dg1 = compute_differential_rcs(f1, gain_const, delta_gamma=1.0)["delta_sigma_m2"][0]
    rcs_dg2 = compute_differential_rcs(f1, gain_const, delta_gamma=2.0)["delta_sigma_m2"][0]
    dg_ratio = rcs_dg2 / rcs_dg1
    dg_scaling_pass = math.isclose(dg_ratio, 4.0, rel_tol=1e-12)
    results.append(
        TestResult(
            "Modulation Depth Squared Scaling Law (|Delta Gamma|^2)",
            dg_scaling_pass,
            f"Ratio DG=2.0 / DG=1.0 = {dg_ratio:.10f} (expected 4.0)",
            severity="CRITICAL" if not dg_scaling_pass else "INFO",
        )
    )

    # 4. Strict Non-Negativity: Delta sigma >= 0 across random and edge cases
    test_freqs = np.linspace(100e6, 10e9, 200)
    test_gains = np.linspace(0.01, 10.0, 200)
    rcs_grid = compute_differential_rcs(test_freqs, test_gains, delta_gamma=complex(0.5, -0.8))
    min_sigma = np.min(rcs_grid["delta_sigma_m2"])
    results.append(
        TestResult(
            "Differential RCS Non-Negativity (Delta sigma >= 0)",
            min_sigma >= 0.0,
            f"Minimum Delta sigma observed = {min_sigma:.6e} m^2",
            severity="CRITICAL" if min_sigma < 0.0 else "INFO",
        )
    )

    # 5. Delta sigma dBsm Floor Protection at Zero Reflection
    rcs_zero = compute_differential_rcs(f1, gain_const, delta_gamma=0.0)
    dbsm_zero = rcs_zero["delta_sigma_dbsm"][0]
    results.append(
        TestResult(
            "Zero Delta Gamma Logarithm Protection (No -inf dBsm crash)",
            math.isfinite(dbsm_zero) and dbsm_zero <= -170.0,
            f"dBsm at Delta Gamma = 0: {dbsm_zero:.2f} dBsm (clamped safely)",
            severity="MAJOR" if not math.isfinite(dbsm_zero) else "INFO",
        )
    )

    return results


def test_boundary_and_singularity_conditions() -> List[TestResult]:
    """Test Challenge 3: Extreme boundary conditions, numerical singularities, and invalid inputs."""
    results: List[TestResult] = []

    # 1. Zero Frequency (DC) in compute_differential_rcs
    try:
        rcs_dc = compute_differential_rcs(np.array([0.0]), 1.0, delta_gamma=1.0)
        # If it doesn't raise, check if it produced inf or nan
        val = rcs_dc["delta_sigma_m2"][0]
        is_inf = math.isinf(val) or math.isnan(val)
        results.append(
            TestResult(
                "RCS at f = 0 Hz (DC singularity)",
                is_inf,  # Expected behavior without crash is inf or handled
                f"Value at DC = {val} (wavelength is infinite)",
                severity="MINOR" if is_inf else "INFO",
            )
        )
    except ZeroDivisionError as e:
        results.append(
            TestResult(
                "RCS at f = 0 Hz (DC singularity)",
                False,
                f"Raised unhandled ZeroDivisionError: {e}",
                severity="MINOR",
            )
        )

    # 2. Antenna models at DC (f = 0.0)
    antennas = [
        PlanarMonopole244(),
        TI_SWRA117D_IFA(),
        TI_SWRA416_Helical(915e6),
        PlanarMeanderMonopole(915e6),
    ]

    for ant in antennas:
        try:
            zin = ant.input_impedance(0.0)
            results.append(
                TestResult(
                    f"{ant.name} Input Impedance at DC (f=0)",
                    True,
                    f"Returned Zin = {zin}",
                )
            )
        except Exception as e:
            results.append(
                TestResult(
                    f"{ant.name} Input Impedance at DC (f=0)",
                    False,
                    f"Crash on f=0: {type(e).__name__}: {e}",
                    severity="MAJOR",
                )
            )

    # 3. Antenna models at negative frequencies
    for ant in antennas:
        try:
            import warnings
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                zin = ant.input_impedance(-ant.center_frequency)
                has_nan = np.isnan(complex(zin).real) or np.isnan(complex(zin).imag)
                warn_msg = f" (Warnings: {[str(item.message) for item in w]})" if w else ""
                results.append(
                    TestResult(
                        f"{ant.name} Input Impedance at negative frequency",
                        not has_nan,
                        f"Zin = {zin}{warn_msg}",
                        severity="MINOR" if has_nan else "INFO",
                    )
                )
        except Exception as e:
            results.append(
                TestResult(
                    f"{ant.name} Input Impedance at negative frequency",
                    False,
                    f"Crashed with {type(e).__name__}: {e}",
                    severity="MINOR",
                )
            )

    # 4. Out-of-band mmWave frequencies (100 GHz)
    for ant in antennas:
        try:
            zin = ant.input_impedance(100.0e9)
            s11 = ant.return_loss_db(100.0e9)
            results.append(
                TestResult(
                    f"{ant.name} Behavior at 100 GHz (mmWave out-of-band)",
                    math.isfinite(s11),
                    f"Zin = {zin:.2f}, S11 = {s11:.2f} dB",
                )
            )
        except Exception as e:
            results.append(
                TestResult(
                    f"{ant.name} Behavior at 100 GHz",
                    False,
                    f"Crashed: {e}",
                    severity="MINOR",
                )
            )

    # 5. Empty numpy array input handling
    try:
        empty_f = np.array([])
        rcs_empty = compute_differential_rcs(empty_f, 1.0)
        passed = len(rcs_empty["delta_sigma_m2"]) == 0
        results.append(
            TestResult(
                "Differential RCS with empty frequency array",
                passed,
                f"Returned dictionary with {len(rcs_empty['delta_sigma_m2'])} elements",
            )
        )
    except Exception as e:
        results.append(
            TestResult(
                "Differential RCS with empty frequency array",
                False,
                f"Crashed: {e}",
                severity="MINOR",
            )
        )

    # 6. Singular load impedance: Z_L = -Z_0 (-50 Ohm, zero denominator)
    try:
        g_sing = compute_gamma_l(-50.0, 50.0)
        results.append(
            TestResult(
                "compute_gamma_l with Z_L = -Z_0 (Zero Denominator)",
                False,
                f"Did not raise, returned {g_sing}",
                severity="MINOR",
            )
        )
    except ZeroDivisionError as e:
        results.append(
            TestResult(
                "compute_gamma_l with Z_L = -Z_0 (Zero Denominator)",
                True,
                f"Correctly raised ZeroDivisionError: {e}",
                severity="INFO",
            )
        )

    # 7. Characteristic Impedance Z0 = 0
    try:
        g_z0_zero = compute_gamma_l(50.0, 0.0)
        results.append(
            TestResult(
                "compute_gamma_l with Z_0 = 0.0 Ohm",
                True,
                f"Returned {g_z0_zero} (ZL/ZL = 1.0)",
            )
        )
    except Exception as e:
        results.append(
            TestResult(
                "compute_gamma_l with Z_0 = 0.0 Ohm",
                False,
                f"Crashed with {e}",
                severity="MINOR",
            )
        )

    # 8. Scalar frequency argument to compute_differential_rcs
    try:
        rcs_scalar = compute_differential_rcs(2.44e9, 1.622, delta_gamma=1.0)
        val = rcs_scalar["delta_sigma_cm2"]
        results.append(
            TestResult(
                "compute_differential_rcs with scalar frequency (float)",
                True,
                f"Returned scalar array result: {val}",
            )
        )
    except Exception as e:
        results.append(
            TestResult(
                "compute_differential_rcs with scalar frequency (float)",
                False,
                f"Crashed with {type(e).__name__}: {e}",
                severity="MINOR",
            )
        )

    return results


def test_dielectric_and_physical_fidelity() -> List[TestResult]:
    """Test Challenge 4: Dielectric parameter sensitivity and physical model fidelity."""
    results: List[TestResult] = []

    # 1. Monopole dielectric sensitivity: if eps_r varies from 4.1 to 4.6, does resonance shift?
    mono_41 = PlanarMonopole244(substrate=Substrate(eps_r=4.1))
    mono_46 = PlanarMonopole244(substrate=Substrate(eps_r=4.6))
    mono_10 = PlanarMonopole244(substrate=Substrate(eps_r=10.0))

    f0_41 = mono_41.find_resonance((2.0e9, 3.0e9))
    f0_46 = mono_46.find_resonance((2.0e9, 3.0e9))
    f0_10 = mono_10.find_resonance((1.0e9, 3.0e9))

    # In a physical antenna, higher eps_r lowers resonance frequency (f0 proportional to 1/sqrt(eps_eff))
    eps_sensitive = not math.isclose(f0_41, f0_46, rel_tol=1e-4)
    eps_10_sensitive = not math.isclose(f0_41, f0_10, rel_tol=1e-4)

    results.append(
        TestResult(
            "Planar Monopole Dielectric Sensitivity (eps_r 4.1 vs 4.6 vs 10.0)",
            eps_sensitive or eps_10_sensitive,
            f"f0(eps=4.1)={f0_41/1e6:.2f} MHz, f0(eps=4.6)={f0_46/1e6:.2f} MHz, f0(eps=10.0)={f0_10/1e6:.2f} MHz",
            severity="MEDIUM" if not (eps_sensitive or eps_10_sensitive) else "INFO",
        )
    )

    # 2. Check if theta clamping creates artificial flatness far out of band
    mono = PlanarMonopole244()
    zin_10g = mono.input_impedance(10.0e9)
    zin_20g = mono.input_impedance(20.0e9)
    # If theta is clamped to 0.95*pi, reactance remains frozen!
    clamped_reactance = math.isclose(complex(zin_10g).imag, complex(zin_20g).imag, rel_tol=1e-4)
    results.append(
        TestResult(
            "Out-of-band Reactance Clamping Artifact Check",
            not clamped_reactance,
            f"Im(Zin) at 10 GHz = {complex(zin_10g).imag:.2f} Ohm vs 20 GHz = {complex(zin_20g).imag:.2f} Ohm "
            f"(Clamped to 0.95*pi constant: {clamped_reactance})",
            severity="LOW" if clamped_reactance else "INFO",
        )
    )

    return results


def run_all_adversarial_tests() -> Dict[str, Any]:
    print("=" * 80)
    print("EMPIRICAL CHALLENGER: ADVERSARIAL STRESS TEST SUITE (MILESTONE 1)")
    print("=" * 80)

    all_results: Dict[str, List[TestResult]] = {}

    print("\n--- 1. Testing Realistic Component Parasitics & Tolerances (|Delta Gamma| >= 1.0) ---")
    all_results["parasitics"] = test_realistic_parasitics_and_tolerances()
    for res in all_results["parasitics"]:
        print(f"  {res}")

    print("\n--- 2. Testing Electrodynamic Scaling Laws & Aperture Physics ---")
    all_results["scaling_laws"] = test_electrodynamic_scaling_laws()
    for res in all_results["scaling_laws"]:
        print(f"  {res}")

    print("\n--- 3. Testing Boundary Conditions, Singularities & Extreme Inputs ---")
    all_results["boundaries"] = test_boundary_and_singularity_conditions()
    for res in all_results["boundaries"]:
        print(f"  {res}")

    print("\n--- 4. Testing Dielectric Sensitivity & Physical Model Fidelity ---")
    all_results["fidelity"] = test_dielectric_and_physical_fidelity()
    for res in all_results["fidelity"]:
        print(f"  {res}")

    # Summary
    total_tests = sum(len(r) for r in all_results.values())
    total_passed = sum(sum(1 for t in r if t.passed) for r in all_results.values())
    total_failed = total_tests - total_passed

    print("\n" + "=" * 80)
    print(f"TEST SUMMARY: Total: {total_tests} | Passed: {total_passed} | Failed: {total_failed}")
    print("=" * 80)

    return {
        "total": total_tests,
        "passed": total_passed,
        "failed": total_failed,
        "results": all_results,
    }


if __name__ == "__main__":
    run_all_adversarial_tests()
