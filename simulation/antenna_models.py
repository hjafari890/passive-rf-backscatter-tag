"""Antenna Electrodynamic and Transmission-Line Impedance Models.

Models:
- Option A1: 2.44 GHz Planar Quarter-Wave Monopole (L=26.2 mm, W=2.5 mm, GP 35x35 mm, Gain +2.05 dBi)
- Option A2: 2.44 GHz TI SWRA117D Inverted-F Antenna (IFA) (15.2x5.7 mm envelope, 0.50 mm trace,
             0.90 mm shorting stub at X=-2.1 mm, feed at X=0, Gain +2.1 dBi)
- Option B1: 868/915 MHz TI SWRA416 Miniature Helical Antenna (18.0x11.0 mm, 19 vias, 1.0 mm trace, Gain -1.5 dBi)
- Option B2: 868/915 MHz Single-Sided Planar Meander Monopole (34.0x16.0 mm, 1.0 mm trace/gap, Gain +0.8 dBi)

All antennas are dimensioned for standard 1.6 mm FR-4 substrate:
- Substrate thickness h = 1.60 mm
- Relative permittivity eps_r = 4.40
- Dielectric loss tangent tan_d = 0.020
- Copper thickness t = 35 um (1 oz/sq.ft)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Tuple, Union

import numpy as np

# Physical constants (SI units)
SPEED_OF_LIGHT: float = 299792458.0  # m/s
MU_0: float = 4.0 * math.pi * 1e-7  # H/m
EPSILON_0: float = 1.0 / (MU_0 * SPEED_OF_LIGHT**2)  # F/m
ETA_0: float = math.sqrt(MU_0 / EPSILON_0)  # Free space wave impedance (~376.73 Ohm)


@dataclass(frozen=True)
class Substrate:
    """Dielectric substrate specifications for FR-4."""

    thickness_m: float = 0.0016  # 1.6 mm
    eps_r: float = 4.40  # Relative dielectric permittivity
    tan_d: float = 0.020  # Dielectric loss tangent at GHz frequencies
    copper_thickness_m: float = 35e-6  # 35 um (1 oz copper)
    copper_conductivity: float = 5.8e7  # S/m (annealed copper)


@dataclass
class AntennaModel:
    """Base electrodynamic antenna model interface."""

    name: str
    band: str
    center_frequency: float  # Hz
    gain_dbi: float  # dBi
    substrate: Substrate = field(default_factory=Substrate)
    description: str = ""
    dimensions_mm: Dict[str, float] = field(default_factory=dict)

    @property
    def gain_linear(self) -> float:
        """Linear power gain G = 10^(G_dBi / 10)."""
        return 10.0 ** (self.gain_dbi / 10.0)

    @property
    def wavelength_0(self) -> float:
        """Free-space wavelength at center frequency in meters."""
        return SPEED_OF_LIGHT / self.center_frequency

    def input_impedance(
        self, f: Union[float, np.ndarray]
    ) -> Union[complex, np.ndarray]:
        """Compute complex input impedance Zin(f) = Rin(f) + j*Xin(f) in Ohms."""
        raise NotImplementedError("Subclasses must implement input_impedance")

    def reflection_coefficient(
        self, f: Union[float, np.ndarray], z0: float = 50.0
    ) -> Union[complex, np.ndarray]:
        """Compute input reflection coefficient Gamma_in(f) = (Zin - Z0) / (Zin + Z0)."""
        zin = self.input_impedance(f)
        return (zin - z0) / (zin + z0)

    def return_loss_db(
        self, f: Union[float, np.ndarray], z0: float = 50.0
    ) -> Union[float, np.ndarray]:
        """Compute return loss S11(f) in dB = 20 * log10(|Gamma_in(f)|)."""
        gamma = self.reflection_coefficient(f, z0=z0)
        mag_gamma = np.abs(gamma)
        # Avoid log of zero by setting lower numerical floor at 1e-12 (-240 dB)
        mag_gamma = np.maximum(mag_gamma, 1e-12)
        return 20.0 * np.log10(mag_gamma)

    def vswr(
        self, f: Union[float, np.ndarray], z0: float = 50.0
    ) -> Union[float, np.ndarray]:
        """Compute Voltage Standing Wave Ratio VSWR = (1 + |Gamma|) / (1 - |Gamma|)."""
        gamma = np.abs(self.reflection_coefficient(f, z0=z0))
        gamma = np.minimum(gamma, 0.999999)
        return (1.0 + gamma) / (1.0 - gamma)

    def find_resonance(
        self, f_range: Tuple[float, float], num_points: int = 2000
    ) -> float:
        """Find resonance frequency f0 in range where reactance Xin(f0) == 0."""
        f_arr = np.linspace(f_range[0], f_range[1], num_points)
        zin = self.input_impedance(f_arr)
        xin = np.imag(zin)
        # Find zero crossing of reactance Xin
        sign_change = np.where(np.diff(np.signbit(xin)))[0]
        if len(sign_change) > 0:
            idx = sign_change[0]
            # Linear interpolation for sub-point precision
            denom = xin[idx + 1] - xin[idx]
            if abs(denom) > 1e-12:
                f0 = f_arr[idx] - xin[idx] * (f_arr[idx + 1] - f_arr[idx]) / denom
                return float(f0)
            return float(f_arr[idx])
        # Fallback to minimum return loss if no zero-crossing detected
        s11 = self.return_loss_db(f_arr)
        min_idx = int(np.argmin(s11))
        return float(f_arr[min_idx])


# -------------------------------------------------------------------------
# Option A1: 2.44 GHz Planar Quarter-Wave Monopole
# -------------------------------------------------------------------------
class PlanarMonopole244(AntennaModel):
    """Option A.1: 2.44 GHz Planar Quarter-Wave Monopole on 1.6 mm FR-4.

    Dimensions:
    - Length L = 26.2 mm
    - Width W = 2.5 mm
    - Ground plane GP = 35.0 x 35.0 mm
    - Peak Gain = +2.05 dBi
    """

    def __init__(self, substrate: Substrate | None = None) -> None:
        sub = substrate or Substrate()
        super().__init__(
            name="Planar Monopole 2.44 GHz (Option A1)",
            band="2.44GHz",
            center_frequency=2.440e9,
            gain_dbi=2.05,
            substrate=sub,
            description="Planar quarter-wave printed blade monopole over 35x35 mm ground on 1.6 mm FR-4.",
            dimensions_mm={
                "length_mm": 26.2,
                "width_mm": 2.5,
                "ground_length_mm": 35.0,
                "ground_width_mm": 35.0,
                "feed_gap_mm": 0.5,
            },
        )
        self.L = self.dimensions_mm["length_mm"] * 1e-3
        self.W = self.dimensions_mm["width_mm"] * 1e-3
        # Estimate fringing end extension delta_L
        eps_approx = 0.5 * (self.substrate.eps_r + 1.0)
        self.delta_l = 0.412 * self.substrate.thickness_m * (
            (eps_approx + 0.3) / (eps_approx - 0.258)
        ) * ((self.W / self.substrate.thickness_m + 0.264) / (self.W / self.substrate.thickness_m + 0.8))
        self.L_eff = self.L + self.delta_l
        # Derive dielectric filling factor q so that at nominal eps_r=4.40, resonance is exactly 2.440 GHz
        eps_eff_nom = (SPEED_OF_LIGHT / (4.0 * self.center_frequency * self.L_eff)) ** 2
        self.q = (eps_eff_nom - 1.0) / (4.40 - 1.0)
        self.eps_eff = 1.0 + self.q * (self.substrate.eps_r - 1.0)
        # Equivalent cylindrical wire radius for a planar flat strip of width W
        self.a_eq = 0.25 * self.W
        # Characteristic radiation impedance of the monopole element
        self.z_ant = 60.0 * (math.log(2.0 * self.L / self.a_eq) - 1.0)
        # Radiation resistance at resonance on finite ground
        self.R0 = 42.5  # Ohms (monopole finite ground plane adjustment)

    def input_impedance(
        self, f: Union[float, np.ndarray]
    ) -> Union[complex, np.ndarray]:
        f_arr = np.asarray(f, dtype=float)
        f_arr_abs = np.abs(f_arr)
        # Scaling frequency relative to design resonance f0
        f_ratio = f_arr_abs / self.center_frequency

        # Radiation resistance scales quadratically near quarter-wave resonance
        r_rad = self.R0 * (f_ratio**2)

        # Ohmic and dielectric loss resistances
        delta_skin = np.sqrt(1.0 / (np.pi * np.maximum(f_arr_abs, 1e6) * MU_0 * self.substrate.copper_conductivity))
        r_ohmic = (1.0 / (self.substrate.copper_conductivity * delta_skin)) * (self.L / (2.0 * self.W))
        # Dielectric loss
        r_diel = 0.5 * self.substrate.tan_d * self.z_ant * (self.substrate.eps_r / self.eps_eff)
        r_in = r_rad + r_ohmic + r_diel

        # Electrical phase delay using effective substrate parameters
        beta = 2.0 * np.pi * f_arr * np.sqrt(self.eps_eff) / SPEED_OF_LIGHT
        theta = beta * self.L_eff

        # Transmission-line stub reactance: X = -Z_ant * cot(theta)
        sin_theta = np.sin(theta)
        sin_safe = np.where(np.abs(sin_theta) < 1e-4, np.sign(sin_theta + 1e-12) * 1e-4, sin_theta)
        cot_theta = np.cos(theta) / sin_safe
        x_in = -self.z_ant * cot_theta

        z_out = r_in + 1j * x_in
        if np.isscalar(f):
            return complex(z_out.item() if hasattr(z_out, "item") else z_out)
        return z_out


# -------------------------------------------------------------------------
# Option A2: 2.44 GHz TI SWRA117D Inverted-F Antenna (IFA)
# -------------------------------------------------------------------------
class TI_SWRA117D_IFA(AntennaModel):
    """Option A.2: Texas Instruments SWRA117D Inverted-F Antenna (IFA).

    Dimensions:
    - Bounding area: 15.2 mm x 5.7 mm
    - Trace width: 0.50 mm
    - Shorting stub: 0.90 mm width, centered at X = -2.10 mm to Ground
    - Feed pin: 0.50 mm width, centered at X = 0.00 mm (pitch = 2.10 mm)
    - Meandered radiating arm length: ~25.5 mm developed length
    - Peak Gain: +2.10 dBi
    - Intrinsic 50 Ohm match
    """

    def __init__(self, substrate: Substrate | None = None) -> None:
        sub = substrate or Substrate()
        super().__init__(
            name="TI SWRA117D IFA 2.44 GHz (Option A2)",
            band="2.44GHz",
            center_frequency=2.440e9,
            gain_dbi=2.10,
            substrate=sub,
            description="TI SWRA117D compact meandered Inverted-F Antenna with integrated 50 Ohm shunt match.",
            dimensions_mm={
                "envelope_x_mm": 15.2,
                "envelope_y_mm": 5.7,
                "trace_width_mm": 0.50,
                "shorting_stub_width_mm": 0.90,
                "feed_pitch_mm": 2.10,
                "meander_length_mm": 25.5,
            },
        )
        self.w_stub = self.dimensions_mm["shorting_stub_width_mm"] * 1e-3
        self.w_trace = self.dimensions_mm["trace_width_mm"] * 1e-3
        self.d_feed = self.dimensions_mm["feed_pitch_mm"] * 1e-3
        self.L_arm = self.dimensions_mm["meander_length_mm"] * 1e-3

        # Electrodynamic equivalent circuit parameters for IFA
        omega0 = 2.0 * math.pi * self.center_frequency
        self.L_s = 2.25e-9  # Shorting stub self-inductance
        self.r_s = 0.35  # Shorting stub ohmic resistance
        y_s0 = 1.0 / (self.r_s + 1j * omega0 * self.L_s)
        target_b = -y_s0.imag

        self.r_a0 = 5.2  # Radiating arm resistance at resonance
        # Solve for arm reactance x_a0 that cancels stub susceptance at f0
        roots = np.roots([target_b, 1.0, target_b * (self.r_a0**2)])
        self.x_a0 = float(roots[-1])  # Negative (capacitive) root
        y_a0 = 1.0 / (self.r_a0 + 1j * self.x_a0)
        y_sum0 = y_s0 + y_a0
        # Tap factor transforms input resistance to precisely 50.0 Ohm
        self.tap = float(1.0 / (50.0 * y_sum0.real))
        self.z0_arm = 110.0
        # Electrical angle of arm at f0
        self.theta0 = float(np.arctan2(self.z0_arm, -self.x_a0))

    def input_impedance(
        self, f: Union[float, np.ndarray]
    ) -> Union[complex, np.ndarray]:
        f_arr = np.asarray(f, dtype=float)
        omega = 2.0 * np.pi * f_arr
        f_ratio = f_arr / self.center_frequency
        f_ratio_abs = np.abs(f_ratio)

        # Shorting stub admittance (guard DC f=0 and negative f)
        r_stub = self.r_s * np.maximum(np.sqrt(f_ratio_abs), 0.05)
        x_stub = omega * self.L_s
        y_stub = 1.0 / (r_stub + 1j * x_stub)

        # Open meandered arm admittance
        r_arm = self.r_a0 * (f_ratio_abs**2)
        theta = self.theta0 * f_ratio
        theta_sign = np.where(f_ratio >= 0, 1.0, -1.0)
        theta_clamped = np.clip(np.abs(theta), 0.05 * np.pi, 0.95 * np.pi) * theta_sign
        x_arm = -self.z0_arm / np.tan(theta_clamped)
        y_arm = 1.0 / (r_arm + 1j * x_arm)

        # Parallel combination scaled by tap ratio
        y_in = (y_stub + y_arm) * self.tap
        z_in = 1.0 / y_in

        if np.isscalar(f):
            return complex(z_in.item() if hasattr(z_in, "item") else z_in)
        return z_in


# -------------------------------------------------------------------------
# Option B1: 868/915 MHz TI SWRA416 Miniature Helical Antenna
# -------------------------------------------------------------------------
class TI_SWRA416_Helical(AntennaModel):
    """Option B.1: Texas Instruments SWRA416 Miniature Helical PCB Antenna.

    Dimensions:
    - Envelope: 18.0 mm x 11.0 mm
    - 19 through-hole vias (0.40 mm finished drill, 1.0 mm pads)
    - 9.5 helical turns, 1.0 mm trace width, 2.0 mm pitch
    - Peak Gain: -1.50 dBi
    - Untuned impedance: ~ 12 + j110 Ohm
    - Matched feed impedance: 50 Ohm at target band (default 915 MHz, selectable 868 MHz)
    """

    def __init__(
        self,
        center_frequency: float = 915.0e6,
        substrate: Substrate | None = None,
    ) -> None:
        sub = substrate or Substrate()
        freq = float(center_frequency)
        band_name = "915MHz" if abs(freq - 915e6) < abs(freq - 868e6) else "868MHz"
        super().__init__(
            name=f"TI SWRA416 Helical {band_name} (Option B1)",
            band="Sub-1GHz",
            center_frequency=freq,
            gain_dbi=-1.50,
            substrate=sub,
            description="TI SWRA416 compact 2-layer rectangular helical antenna with 19 vias and 50 Ohm matching.",
            dimensions_mm={
                "envelope_x_mm": 18.0,
                "envelope_y_mm": 11.0,
                "trace_width_mm": 1.0,
                "via_count": 19,
                "via_drill_mm": 0.40,
                "turn_pitch_mm": 2.0,
                "turns": 9.5,
            },
        )
        self.L_helix = 19.5e-9
        self.R_rad_0 = 9.8  # Ohms radiation resistance
        self.R_loss = 2.4  # Ohms conductor loss through vias and copper

        # TI SWRA416 Matching network parameters (L-section matching to 50 Ohm)
        omega0 = 2.0 * math.pi * self.center_frequency
        r_ant_0 = self.R_rad_0 + self.R_loss  # ~12.2 Ohm
        x_ant_0 = omega0 * self.L_helix
        # Series tuning capacitor to cancel antenna self-inductance
        self.C_series = 1.0 / (omega0 * x_ant_0)
        # L-section matching network: transforms R_ant_0 to 50 Ohm
        q_factor = math.sqrt(50.0 / r_ant_0 - 1.0)
        x_l_match = r_ant_0 * q_factor
        self.L_match = x_l_match / omega0
        b_c_match = q_factor / 50.0
        self.C_match = b_c_match / omega0

    def raw_antenna_impedance(
        self, f: Union[float, np.ndarray]
    ) -> Union[complex, np.ndarray]:
        """Impedance of the bare helical radiator without matching components."""
        f_arr = np.asarray(f, dtype=float)
        omega = 2.0 * np.pi * f_arr
        f_ratio = np.abs(f_arr) / self.center_frequency

        r_ant = self.R_rad_0 * (f_ratio**2) + self.R_loss * np.maximum(np.sqrt(f_ratio), 0.05)
        x_ant = omega * self.L_helix
        z_raw = r_ant + 1j * x_ant
        if np.isscalar(f):
            return complex(z_raw.item() if hasattr(z_raw, "item") else z_raw)
        return z_raw

    def input_impedance(
        self, f: Union[float, np.ndarray]
    ) -> Union[complex, np.ndarray]:
        """Matched input impedance Zin(f) presented at the 50 Ohm feed terminals."""
        f_arr = np.asarray(f, dtype=float)
        # Guard against DC (f=0) causing ZeroDivisionError while preserving sign for negative frequencies
        f_sign = np.where(f_arr >= 0.0, 1.0, -1.0)
        f_safe = np.maximum(np.abs(f_arr), 1e3) * f_sign
        omega = 2.0 * np.pi * f_safe
        z_ant = self.raw_antenna_impedance(f_safe)

        # Series tuning capacitor
        z_mid = z_ant - 1j / (omega * self.C_series)
        # Series L of matching network
        z2 = z_mid + 1j * omega * self.L_match
        # Shunt C of matching network
        y2 = (1.0 / z2) + 1j * omega * self.C_match
        z_in = 1.0 / y2

        if np.isscalar(f):
            return complex(z_in.item() if hasattr(z_in, "item") else z_in)
        return z_in


# -------------------------------------------------------------------------
# Option B2: 868/915 MHz Single-Sided Planar Meander Monopole
# -------------------------------------------------------------------------
class PlanarMeanderMonopole(AntennaModel):
    """Option B.2: 868/915 MHz Single-Sided Planar Meander Monopole.

    Dimensions:
    - Envelope: 34.0 mm x 16.0 mm
    - Trace width: 1.00 mm
    - Inter-trace gap: 1.00 mm (passes >= 0.4 mm CNC isolation milling)
    - Total developed length: 74.5 mm
    - Single-sided milling optimized on 1.6 mm FR-4
    - Peak Gain: +0.80 dBi
    - Resonates at 915 MHz (or selectable 868 MHz)
    """

    def __init__(
        self,
        center_frequency: float = 915.0e6,
        substrate: Substrate | None = None,
    ) -> None:
        sub = substrate or Substrate()
        freq = float(center_frequency)
        band_name = "915MHz" if abs(freq - 915e6) < abs(freq - 868e6) else "868MHz"
        super().__init__(
            name=f"Planar Meander Monopole {band_name} (Option B2)",
            band="Sub-1GHz",
            center_frequency=freq,
            gain_dbi=0.80,
            substrate=sub,
            description="Single-sided planar meandered monopole for CNC isolation milling with 1.0 mm gap.",
            dimensions_mm={
                "envelope_x_mm": 34.0,
                "envelope_y_mm": 16.0,
                "trace_width_mm": 1.00,
                "gap_spacing_mm": 1.00,
                "developed_length_mm": 74.5,
                "folds": 4,
            },
        )
        self.L_total = self.dimensions_mm["developed_length_mm"] * 1e-3
        self.W_trace = self.dimensions_mm["trace_width_mm"] * 1e-3
        self.z0_meander = 128.0  # Characteristic impedance of meander strip
        self.R0 = 48.5  # Radiation resistance tuned close to 50 Ohm

    def input_impedance(
        self, f: Union[float, np.ndarray]
    ) -> Union[complex, np.ndarray]:
        f_arr = np.asarray(f, dtype=float)
        f_ratio = f_arr / self.center_frequency
        f_ratio_abs = np.abs(f_ratio)

        # Radiation resistance and losses (guard negative f against NaN)
        r_rad = 44.5 * (f_ratio_abs**2)
        r_loss = 4.0 * np.sqrt(f_ratio_abs)
        r_in = r_rad + r_loss

        # Reactance of open-circuited meandered quarter-wave radiator
        theta = 0.5 * np.pi * f_ratio
        theta_sign = np.where(f_ratio >= 0, 1.0, -1.0)
        theta_clamped = np.clip(np.abs(theta), 0.05 * np.pi, 0.95 * np.pi) * theta_sign
        x_in = -self.z0_meander * (1.0 / np.tan(theta_clamped))

        z_out = r_in + 1j * x_in
        if np.isscalar(f):
            return complex(z_out.item() if hasattr(z_out, "item") else z_out)
        return z_out


# -------------------------------------------------------------------------
# Factory and Analysis Functions
# -------------------------------------------------------------------------
def get_antenna(name: str, **kwargs) -> AntennaModel:
    """Retrieve an antenna model by key or option name."""
    normalized = name.strip().lower()
    if normalized in ["option_a1", "monopole", "planar_monopole", "2.44ghz_monopole"]:
        return PlanarMonopole244(**kwargs)
    elif normalized in ["option_a2", "ifa", "swra117d", "ti_swra117d", "2.44ghz_ifa"]:
        return TI_SWRA117D_IFA(**kwargs)
    elif normalized in ["option_b1", "swra416", "ti_swra416", "helical", "sub1g_helical"]:
        return TI_SWRA416_Helical(**kwargs)
    elif normalized in ["option_b2", "meander", "planar_meander", "sub1g_meander"]:
        return PlanarMeanderMonopole(**kwargs)
    else:
        raise ValueError(
            f"Unknown antenna model '{name}'. "
            f"Available: 'option_a1', 'option_a2', 'option_b1', 'option_b2'."
        )


def calculate_zin(
    antenna: AntennaModel, frequencies: np.ndarray
) -> np.ndarray:
    """Compute complex input impedance array Zin(f) across frequency array."""
    return np.asarray(antenna.input_impedance(frequencies), dtype=complex)


def calculate_s11(
    antenna: AntennaModel, frequencies: np.ndarray, z0: float = 50.0
) -> np.ndarray:
    """Compute return loss S11(f) in dB across frequency array."""
    return np.asarray(antenna.return_loss_db(frequencies, z0=z0), dtype=float)


def calculate_resonance(
    antenna: AntennaModel, f_range: Tuple[float, float]
) -> float:
    """Find the precise zero-reactance resonance frequency f0 in Hz."""
    return antenna.find_resonance(f_range)
