"""Radar Cross Section (RCS) and Load Modulation Reflection Simulation Engine.

Theoretical Foundation:
According to Harrington's theory of loaded scatterers and antenna aperture reciprocity,
the total electromagnetic backscattering from a tag antenna consists of two components:
    E_scat = E_structural + Gamma_L * E_antenna

When switching between two load states (e.g. State 1: 50 Ohm absorbing, State 2: 0 Ohm reflecting short),
the invariant structural scattering E_structural cancels out completely under coherent subtraction.
The resulting differential backscattered field is:
    Delta E_scat = (Gamma_State2 - Gamma_State1) * E_antenna = Delta_Gamma * E_antenna

The Differential Radar Cross Section (Delta sigma) is given by:
    Delta sigma = (lambda^2 / (4 * pi)) * G^2 * |Delta Gamma|^2

where:
    - lambda = c / f is the carrier wavelength in meters
    - G is the antenna power gain in linear scale: G = 10^(G_dBi / 10)
    - Delta Gamma = Gamma_State2 - Gamma_State1 is the complex reflection difference vector
    - |Delta Gamma| is the modulation depth in the complex I/Q reflection plane
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Tuple, Union

import numpy as np

# Physical constant
SPEED_OF_LIGHT: float = 299792458.0  # m/s


@dataclass(frozen=True)
class LoadState:
    """RF Load Termination State definition."""

    name: str
    nominal_impedance: complex
    state_id: int
    description: str

    def reflection_coefficient(
        self, z0: float = 50.0, f: float | np.ndarray | None = None
    ) -> complex | np.ndarray:
        """Compute reflection coefficient Gamma_L = (ZL - Z0) / (ZL + Z0)."""
        if f is None or np.isscalar(f):
            zl = self.nominal_impedance
            if abs(zl) > 1e8:  # Open circuit approximation
                return complex(1.0, 0.0)
            return (zl - z0) / (zl + z0)
        else:
            # Array of frequencies
            f_arr = np.asarray(f, dtype=float)
            zl = self.nominal_impedance
            if abs(zl) > 1e8:
                return np.ones_like(f_arr, dtype=complex)
            return np.full_like(f_arr, (zl - z0) / (zl + z0), dtype=complex)


# Predefined canonical backscatter load states
ABSORBING_50OHM = LoadState(
    name="Absorbing (50 Ohm SMD Resistor)",
    nominal_impedance=complex(50.0, 0.0),
    state_id=1,
    description="Matched 50.0 Ohm SMD resistor dissipates incident carrier power (Gamma ~ 0).",
)

REFLECTING_SHORT = LoadState(
    name="Reflecting (0 Ohm Short / Jumper ON)",
    nominal_impedance=complex(0.0, 0.0),
    state_id=2,
    description="2-pin jumper installed creating an RF short-circuit (Gamma = -1.0, 180 deg phase).",
)

REFLECTING_OPEN = LoadState(
    name="Reflecting (Open Circuit / Jumper OFF without Resistor)",
    nominal_impedance=complex(1e9, 0.0),  # > 1 GOhm open circuit
    state_id=3,
    description="Open terminals causing total in-phase reflection (Gamma = +1.0, 0 deg phase).",
)


def compute_gamma_l(
    z_load: Union[complex, float], z_0: float = 50.0
) -> complex:
    """Compute load reflection coefficient Gamma_L = (Z_L - Z_0) / (Z_L + Z_0).

    Args:
        z_load: Load impedance in Ohms (can be complex or infinite float).
        z_0: System characteristic impedance in Ohms (default: 50.0).

    Returns:
        Complex reflection coefficient Gamma_L.
    """
    if math.isinf(abs(z_load)) or abs(z_load) > 1e8:
        return complex(1.0, 0.0)
    zl = complex(z_load)
    return (zl - z_0) / (zl + z_0)


def compute_delta_gamma(
    gamma_state2: Union[complex, float],
    gamma_state1: Union[complex, float],
) -> complex:
    """Compute the differential reflection vector Delta Gamma = Gamma2 - Gamma1.

    Args:
        gamma_state2: Reflection coefficient of state 2 (e.g. Short or Open).
        gamma_state1: Reflection coefficient of state 1 (e.g. 50 Ohm absorbing).

    Returns:
        Complex difference vector Delta Gamma.
    """
    return complex(gamma_state2) - complex(gamma_state1)


def verify_delta_gamma_contrast(
    gamma_reflecting: Union[complex, float] = -1.0,
    gamma_absorbing: Union[complex, float] = 0.0,
    min_contrast: float = 1.0,
    allow_tolerance: bool = False,
) -> Tuple[bool, float]:
    """Verify that |Delta Gamma| = |Gamma_reflecting - Gamma_absorbing| >= min_contrast.

    Theoretical Foundation:
    - Ideal short (0.0 Ohm, Gamma = -1.0) vs ideal matched load (50.0 Ohm, Gamma = 0.0)
      yields ideal theoretical contrast |Delta Gamma| = 1.0000 >= 1.0.
    - Under realistic component parasitics and manufacturing tolerances (e.g. 47 - 49.9 Ohm
      SMD resistors, jumper contact resistances 0.01 - 0.1 Ohm, and package ESL/pin inductances),
      the operational modulation depth |Delta Gamma| ranges between 0.88 and 0.999.
      When allow_tolerance=True, the operational acceptance threshold min_contrast = 0.85
      is applied (-1.1 dB loss relative to ideal, fully within the dynamic range of USRP SDRs).

    Args:
        gamma_reflecting: Reflection coefficient of reflecting state (default: -1.0 for short).
        gamma_absorbing: Reflection coefficient of absorbing state (default: 0.0 for 50 Ohm).
        min_contrast: Minimum acceptable modulation depth (default: 1.0).
        allow_tolerance: If True, uses operational threshold (0.85) unless min_contrast is explicitly specified lower.

    Returns:
        Tuple of (passes_threshold: bool, magnitude: float).
    """
    delta_g = compute_delta_gamma(gamma_reflecting, gamma_absorbing)
    mag = abs(delta_g)
    threshold = min_contrast
    if allow_tolerance and threshold > 0.85:
        threshold = 0.85
    # Using 1e-4 tolerance for floating point precision
    passes = bool(mag >= (threshold - 1e-4))
    return passes, float(mag)


def evaluate_realistic_parasitics(
    f: float = 2.440e9,
    r_smd: float = 49.9,
    l_esl: float = 0.5e-9,
    r_contact: float = 0.05,
    l_jumper: float = 0.5e-9,
    z0: float = 50.0,
) -> Dict[str, Union[complex, float, bool]]:
    """Evaluate realistic RF parasitic component behavior and modulation contrast.

    Commercial surface-mount resistors have non-zero manufacturing tolerances (e.g. 47 - 53 Ohm)
    and package parasitic equivalent series inductance (ESL ~ 0.5 - 1.0 nH).
    Jumper pin shorts exhibit non-zero contact resistance (0.01 - 0.1 Ohm) and pin inductance (0.5 - 1.5 nH).

    This function rigorously models the physical impedances:
        Z_smd(f) = R_smd + j * 2 * pi * f * L_esl
        Z_jumper(f) = R_contact + j * 2 * pi * f * L_jumper
    and evaluates the resulting complex reflection coefficients and operational contrast.

    Args:
        f: Operating carrier frequency in Hz (default: 2.440 GHz).
        r_smd: Nominal resistance of SMD load resistor in Ohms (default: 49.9 Ohm).
        l_esl: Equivalent series inductance (ESL) of SMD resistor in Henries (default: 0.5 nH).
        r_contact: Jumper contact and trace resistance in Ohms (default: 0.05 Ohm).
        l_jumper: Jumper pin and via series inductance in Henries (default: 0.5 nH).
        z0: System reference characteristic impedance in Ohms (default: 50.0 Ohm).

    Returns:
        Dictionary containing:
            - 'frequency_hz': Operating frequency in Hz.
            - 'z_smd': Complex impedance of the SMD resistor load.
            - 'z_jumper': Complex impedance of the reflecting short.
            - 'gamma_smd': Complex reflection coefficient of absorbing load.
            - 'gamma_jumper': Complex reflection coefficient of reflecting short.
            - 'delta_gamma': Complex difference reflection vector.
            - 'delta_gamma_mag': Magnitude |Delta Gamma|.
            - 'contrast_loss_db': Modulation depth degradation in dB (20*log10(|Delta Gamma|)).
            - 'operational_contrast_pass': True if |Delta Gamma| >= 0.85.
    """
    omega = 2.0 * math.pi * float(f)
    z_smd = complex(r_smd, omega * l_esl)
    z_jumper = complex(r_contact, omega * l_jumper)

    gamma_smd = compute_gamma_l(z_smd, z0)
    gamma_jumper = compute_gamma_l(z_jumper, z0)

    delta_gamma = compute_delta_gamma(gamma_jumper, gamma_smd)
    delta_gamma_mag = abs(delta_gamma)
    contrast_loss_db = 20.0 * math.log10(max(delta_gamma_mag, 1e-12))
    operational_contrast_pass = bool(delta_gamma_mag >= (0.85 - 1e-4))

    return {
        "frequency_hz": float(f),
        "z_smd": z_smd,
        "z_jumper": z_jumper,
        "gamma_smd": gamma_smd,
        "gamma_jumper": gamma_jumper,
        "delta_gamma": delta_gamma,
        "delta_gamma_mag": float(delta_gamma_mag),
        "contrast_loss_db": float(contrast_loss_db),
        "operational_contrast_pass": operational_contrast_pass,
    }


def compute_differential_rcs(
    frequencies: np.ndarray,
    gain_linear: Union[float, np.ndarray],
    delta_gamma: Union[complex, float] = 1.0,
) -> Dict[str, np.ndarray]:
    """Compute differential radar cross section (Delta sigma) across frequency.

    Formula:
        Delta sigma = (lambda^2 / (4 * pi)) * G^2 * |Delta Gamma|^2

    Args:
        frequencies: Array of frequencies in Hz.
        gain_linear: Linear antenna power gain G (can be scalar or frequency-dependent array).
        delta_gamma: Complex reflection vector difference Delta Gamma.

    Returns:
        Dictionary containing:
            - 'frequencies_hz': Frequencies in Hz.
            - 'wavelength_m': Free-space wavelength lambda in meters.
            - 'isotropic_aperture_m2': A0 = lambda^2 / (4 * pi) in m^2.
            - 'delta_gamma_mag': |Delta Gamma|.
            - 'delta_sigma_m2': Delta sigma in m^2.
            - 'delta_sigma_cm2': Delta sigma in cm^2 (m^2 * 1e4).
            - 'delta_sigma_dbsm': Delta sigma in dBsm (10 * log10(Delta sigma in m^2)).
    """
    f_arr = np.asarray(frequencies, dtype=float)
    g_arr = np.asarray(gain_linear, dtype=float)
    mag_delta_g = abs(complex(delta_gamma))

    # Free-space wavelength lambda = c / f (safely handling f=0 without unhandled warnings)
    with np.errstate(divide="ignore"):
        wavelengths = np.where(f_arr == 0.0, np.inf, SPEED_OF_LIGHT / f_arr)
        # Isotropic effective aperture A0 = lambda^2 / (4 * pi)
        a0 = (wavelengths**2) / (4.0 * np.pi)

    # Delta sigma = A0 * G^2 * |Delta Gamma|^2
    delta_sigma_m2 = a0 * (g_arr**2) * (mag_delta_g**2)
    delta_sigma_cm2 = delta_sigma_m2 * 1e4  # Convert m^2 to cm^2

    # Protect log10 from zero
    safe_sigma = np.maximum(delta_sigma_m2, 1e-18)
    delta_sigma_dbsm = 10.0 * np.log10(safe_sigma)

    return {
        "frequencies_hz": f_arr,
        "wavelength_m": wavelengths,
        "isotropic_aperture_m2": a0,
        "delta_gamma_mag": np.full_like(f_arr, mag_delta_g),
        "delta_sigma_m2": delta_sigma_m2,
        "delta_sigma_cm2": delta_sigma_cm2,
        "delta_sigma_dbsm": delta_sigma_dbsm,
    }


def analyze_all_state_pairs(
    frequencies: np.ndarray,
    gain_linear: float,
    z0: float = 50.0,
) -> Dict[str, Dict[str, Union[complex, float, np.ndarray]]]:
    """Perform differential RCS analysis across all canonical load state pairs.

    Pairs evaluated:
        1. Short vs 50 Ohm (Canonical Backscatter: Delta Gamma = -1.0, |Delta Gamma| = 1.0)
        2. Open vs 50 Ohm (Alternative Backscatter: Delta Gamma = +1.0, |Delta Gamma| = 1.0)
        3. Open vs Short (Full BPSK 180-deg Phase Backscatter: Delta Gamma = +2.0, |Delta Gamma| = 2.0)
    """
    g_50 = ABSORBING_50OHM.reflection_coefficient(z0=z0)
    g_short = REFLECTING_SHORT.reflection_coefficient(z0=z0)
    g_open = REFLECTING_OPEN.reflection_coefficient(z0=z0)

    pairs = {
        "short_vs_50ohm": {
            "name": "Short (0 Ohm) vs 50 Ohm Resistor",
            "state_a": REFLECTING_SHORT,
            "state_b": ABSORBING_50OHM,
            "gamma_a": g_short,
            "gamma_b": g_50,
        },
        "open_vs_50ohm": {
            "name": "Open (Inf Ohm) vs 50 Ohm Resistor",
            "state_a": REFLECTING_OPEN,
            "state_b": ABSORBING_50OHM,
            "gamma_a": g_open,
            "gamma_b": g_50,
        },
        "open_vs_short": {
            "name": "Open (Inf Ohm) vs Short (0 Ohm)",
            "state_a": REFLECTING_OPEN,
            "state_b": REFLECTING_SHORT,
            "gamma_a": g_open,
            "gamma_b": g_short,
        },
    }

    results: Dict[str, Dict[str, Union[complex, float, np.ndarray]]] = {}
    for key, p in pairs.items():
        ga = complex(p["gamma_a"])
        gb = complex(p["gamma_b"])
        dg = compute_delta_gamma(ga, gb)
        rcs_data = compute_differential_rcs(frequencies, gain_linear, delta_gamma=dg)
        results[key] = {
            "name": p["name"],
            "gamma_a": ga,
            "gamma_b": gb,
            "delta_gamma": dg,
            "delta_gamma_mag": abs(dg),
            "rcs_data": rcs_data,
        }

    return results
