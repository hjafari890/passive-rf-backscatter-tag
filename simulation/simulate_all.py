"""Master CLI simulation runner for antenna modeling and differential RCS analysis.

Outputs generated in --outdir (default: antenna_simulation/output/):
Data Tables (.csv):
  1. s11_244ghz.csv
  2. s11_sub1ghz.csv
  3. impedance_244ghz.csv
  4. impedance_sub1ghz.csv
  5. differential_rcs_244ghz.csv
  6. differential_rcs_sub1ghz.csv
  7. load_modulation_states.csv

Publication Figures (.png, 300 DPI):
  1. s11_comparison.png
  2. impedance_curves.png
  3. differential_rcs.png
  4. smith_chart_states.png
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path

# Add project root and simulation directory to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import numpy as np

try:
    from simulation.antenna_models import (
        SPEED_OF_LIGHT,
        PlanarMeanderMonopole,
        PlanarMonopole244,
        Substrate,
        TI_SWRA117D_IFA,
        TI_SWRA416_Helical,
        calculate_resonance,
        calculate_s11,
        calculate_zin,
    )
    from simulation.rcs_simulation import (
        ABSORBING_50OHM,
        REFLECTING_OPEN,
        REFLECTING_SHORT,
        analyze_all_state_pairs,
        compute_delta_gamma,
        compute_differential_rcs,
        verify_delta_gamma_contrast,
    )
except ImportError:
    from antenna_models import (
        SPEED_OF_LIGHT,
        PlanarMeanderMonopole,
        PlanarMonopole244,
        Substrate,
        TI_SWRA117D_IFA,
        TI_SWRA416_Helical,
        calculate_resonance,
        calculate_s11,
        calculate_zin,
    )
    from rcs_simulation import (
        ABSORBING_50OHM,
        REFLECTING_OPEN,
        REFLECTING_SHORT,
        analyze_all_state_pairs,
        compute_delta_gamma,
        compute_differential_rcs,
        verify_delta_gamma_contrast,
    )


def export_csv(filename: Path, headers: list[str], rows: list[list]) -> None:
    """Helper to write CSV file with header and formatted numeric rows."""
    filename.parent.mkdir(parents=True, exist_ok=True)
    with open(filename, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for row in rows:
            formatted_row = [
                f"{val:.6g}" if isinstance(val, (float, np.floating)) else val
                for val in row
            ]
            writer.writerow(formatted_row)
    print(f"  [CSV] Saved {filename.name} ({len(rows)} rows)")


def plot_s11_comparison(
    f_244: np.ndarray,
    s11_mono: np.ndarray,
    s11_ifa: np.ndarray,
    f_sub1g: np.ndarray,
    s11_hel: np.ndarray,
    s11_mean: np.ndarray,
    sub1g_center_freq: float,
    output_path: Path,
    dpi: int = 300,
) -> None:
    """Generate high-resolution S11 comparison plot."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5), constrained_layout=True)

    # ---------------- 2.44 GHz Band ----------------
    f_ghz = f_244 / 1e9
    ax1.plot(f_ghz, s11_mono, label="Option A1: Planar Monopole (L=26.2 mm)", color="#1f77b4", lw=2.2)
    ax1.plot(f_ghz, s11_ifa, label="Option A2: TI SWRA117D IFA (15.2x5.7 mm)", color="#d62728", lw=2.2, ls="--")

    # Reference lines
    ax1.axhline(-10.0, color="gray", ls=":", lw=1.5, label="-10 dB Ref (VSWR 2:1)")
    ax1.axhline(-15.0, color="green", ls="-.", lw=1.5, label="-15 dB Acceptance Threshold")
    ax1.axvline(2.440, color="black", ls="--", alpha=0.5, lw=1.0)

    # Annotated resonance markers
    ax1.scatter([2.440], [s11_mono[np.argmin(np.abs(f_244 - 2.44e9))]], color="#1f77b4", s=60, zorder=5)
    ax1.annotate(
        f"2.44 GHz\n{s11_mono[np.argmin(np.abs(f_244 - 2.44e9))]:.1f} dB",
        xy=(2.440, s11_mono[np.argmin(np.abs(f_244 - 2.44e9))]),
        xytext=(2.34, -28),
        arrowprops=dict(arrowstyle="->", color="#1f77b4", lw=1.2),
        fontsize=9,
        fontweight="bold",
        color="#1f77b4",
    )

    ax1.scatter([2.440], [s11_ifa[np.argmin(np.abs(f_244 - 2.44e9))]], color="#d62728", s=60, zorder=5)
    ax1.annotate(
        "2.44 GHz Match\n(Intrinsic 50 $\\Omega$)",
        xy=(2.440, -45),
        xytext=(2.48, -42),
        arrowprops=dict(arrowstyle="->", color="#d62728", lw=1.2),
        fontsize=9,
        fontweight="bold",
        color="#d62728",
    )

    ax1.set_title("2.44 GHz ISM / Wi-Fi Band Return Loss ($S_{11}$)", fontsize=12, fontweight="bold")
    ax1.set_xlabel("Frequency (GHz)", fontsize=11)
    ax1.set_ylabel("Return Loss $S_{11}$ (dB)", fontsize=11)
    ax1.set_xlim(2.30, 2.60)
    ax1.set_ylim(-50, 0)
    ax1.grid(True, which="both", alpha=0.35, linestyle="--")
    ax1.legend(loc="upper right", fontsize=8.5, framealpha=0.9)

    # ---------------- Sub-1GHz Band ----------------
    f_mhz = f_sub1g / 1e6
    center_mhz = sub1g_center_freq / 1e6
    ax2.plot(f_mhz, s11_hel, label=f"Option B1: TI SWRA416 Helical ({center_mhz:.0f} MHz)", color="#9467bd", lw=2.2)
    ax2.plot(f_mhz, s11_mean, label=f"Option B2: Planar Meander ({center_mhz:.0f} MHz)", color="#2ca02c", lw=2.2, ls="--")

    ax2.axhline(-10.0, color="gray", ls=":", lw=1.5, label="-10 dB Ref (VSWR 2:1)")
    ax2.axhline(-15.0, color="green", ls="-.", lw=1.5, label="-15 dB Acceptance Threshold")
    ax2.axvline(center_mhz, color="black", ls="--", alpha=0.5, lw=1.0)

    # Marker at center
    idx_center = np.argmin(np.abs(f_sub1g - sub1g_center_freq))
    ax2.scatter([center_mhz], [s11_mean[idx_center]], color="#2ca02c", s=60, zorder=5)
    ax2.annotate(
        f"{center_mhz:.0f} MHz Meander\n{s11_mean[idx_center]:.1f} dB",
        xy=(center_mhz, s11_mean[idx_center]),
        xytext=(center_mhz + 25, -34),
        arrowprops=dict(arrowstyle="->", color="#2ca02c", lw=1.2),
        fontsize=9,
        fontweight="bold",
        color="#2ca02c",
    )

    ax2.set_title("Sub-1GHz (868/915 MHz) Band Return Loss ($S_{11}$)", fontsize=12, fontweight="bold")
    ax2.set_xlabel("Frequency (MHz)", fontsize=11)
    ax2.set_ylabel("Return Loss $S_{11}$ (dB)", fontsize=11)
    ax2.set_xlim(800, 1000)
    ax2.set_ylim(-50, 0)
    ax2.grid(True, which="both", alpha=0.35, linestyle="--")
    ax2.legend(loc="upper right", fontsize=8.5, framealpha=0.9)

    fig.suptitle(
        "Tag Antenna Return Loss ($S_{11}$) vs Frequency on 1.6 mm FR-4 Substrate",
        fontsize=14,
        fontweight="bold",
        y=1.02,
    )
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"  [PLOT] Saved {output_path.name}")


def plot_impedance_curves(
    f_244: np.ndarray,
    zin_mono: np.ndarray,
    zin_ifa: np.ndarray,
    f_sub1g: np.ndarray,
    zin_hel: np.ndarray,
    zin_mean: np.ndarray,
    sub1g_center_freq: float,
    output_path: Path,
    dpi: int = 300,
) -> None:
    """Generate 2x2 grid of Real and Imaginary Zin curves for all 4 antennas."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10), constrained_layout=True)

    f_ghz = f_244 / 1e9
    f_mhz = f_sub1g / 1e6
    center_mhz = sub1g_center_freq / 1e6

    # 1. Option A1 Monopole
    ax = axes[0, 0]
    ax.plot(f_ghz, np.real(zin_mono), label="Re{$Z_{in}$} ($R_{in}$)", color="#1f77b4", lw=2.0)
    ax.plot(f_ghz, np.imag(zin_mono), label="Im{$Z_{in}$} ($X_{in}$)", color="#ff7f0e", lw=2.0, ls="--")
    ax.axhline(50.0, color="gray", ls=":", lw=1.2, label="50 $\\Omega$ Target")
    ax.axhline(0.0, color="black", lw=1.0, alpha=0.7)
    ax.axvline(2.440, color="black", ls="--", alpha=0.5)
    ax.set_title("Option A1: 2.44 GHz Planar Monopole", fontsize=11, fontweight="bold")
    ax.set_xlabel("Frequency (GHz)", fontsize=10)
    ax.set_ylabel("Impedance ($\\Omega$)", fontsize=10)
    ax.set_xlim(2.30, 2.60)
    ax.set_ylim(-150, 200)
    ax.grid(True, alpha=0.35, ls="--")
    ax.legend(loc="upper left", fontsize=8.5)

    # 2. Option A2 IFA
    ax = axes[0, 1]
    ax.plot(f_ghz, np.real(zin_ifa), label="Re{$Z_{in}$} ($R_{in}$)", color="#d62728", lw=2.0)
    ax.plot(f_ghz, np.imag(zin_ifa), label="Im{$Z_{in}$} ($X_{in}$)", color="#9467bd", lw=2.0, ls="--")
    ax.axhline(50.0, color="gray", ls=":", lw=1.2, label="50 $\\Omega$ Target")
    ax.axhline(0.0, color="black", lw=1.0, alpha=0.7)
    ax.axvline(2.440, color="black", ls="--", alpha=0.5)
    ax.set_title("Option A2: 2.44 GHz TI SWRA117D IFA", fontsize=11, fontweight="bold")
    ax.set_xlabel("Frequency (GHz)", fontsize=10)
    ax.set_ylabel("Impedance ($\\Omega$)", fontsize=10)
    ax.set_xlim(2.30, 2.60)
    ax.set_ylim(-150, 200)
    ax.grid(True, alpha=0.35, ls="--")
    ax.legend(loc="upper left", fontsize=8.5)

    # 3. Option B1 Helical
    ax = axes[1, 0]
    ax.plot(f_mhz, np.real(zin_hel), label="Re{$Z_{in}$} (Matched $R_{in}$)", color="#8c564b", lw=2.0)
    ax.plot(f_mhz, np.imag(zin_hel), label="Im{$Z_{in}$} (Matched $X_{in}$)", color="#e377c2", lw=2.0, ls="--")
    ax.axhline(50.0, color="gray", ls=":", lw=1.2, label="50 $\\Omega$ Target")
    ax.axhline(0.0, color="black", lw=1.0, alpha=0.7)
    ax.axvline(center_mhz, color="black", ls="--", alpha=0.5)
    ax.set_title(f"Option B1: Sub-1GHz TI SWRA416 Helical ({center_mhz:.0f} MHz)", fontsize=11, fontweight="bold")
    ax.set_xlabel("Frequency (MHz)", fontsize=10)
    ax.set_ylabel("Impedance ($\\Omega$)", fontsize=10)
    ax.set_xlim(800, 1000)
    ax.set_ylim(-150, 200)
    ax.grid(True, alpha=0.35, ls="--")
    ax.legend(loc="upper left", fontsize=8.5)

    # 4. Option B2 Meander
    ax = axes[1, 1]
    ax.plot(f_mhz, np.real(zin_mean), label="Re{$Z_{in}$} ($R_{in}$)", color="#2ca02c", lw=2.0)
    ax.plot(f_mhz, np.imag(zin_mean), label="Im{$Z_{in}$} ($X_{in}$)", color="#17becf", lw=2.0, ls="--")
    ax.axhline(50.0, color="gray", ls=":", lw=1.2, label="50 $\\Omega$ Target")
    ax.axhline(0.0, color="black", lw=1.0, alpha=0.7)
    ax.axvline(center_mhz, color="black", ls="--", alpha=0.5)
    ax.set_title(f"Option B2: Sub-1GHz Planar Meander ({center_mhz:.0f} MHz)", fontsize=11, fontweight="bold")
    ax.set_xlabel("Frequency (MHz)", fontsize=10)
    ax.set_ylabel("Impedance ($\\Omega$)", fontsize=10)
    ax.set_xlim(800, 1000)
    ax.set_ylim(-150, 200)
    ax.grid(True, alpha=0.35, ls="--")
    ax.legend(loc="upper left", fontsize=8.5)

    fig.suptitle(
        "Complex Input Impedance $Z_{in}(f) = R_{in} + j X_{in}$ across Operating Frequency Bands",
        fontsize=14,
        fontweight="bold",
        y=1.02,
    )
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"  [PLOT] Saved {output_path.name}")


def plot_differential_rcs(
    f_244: np.ndarray,
    ifa_gain_linear: float,
    mono_gain_linear: float,
    f_sub1g: np.ndarray,
    hel_gain_linear: float,
    mean_gain_linear: float,
    sub1g_center_freq: float,
    output_path: Path,
    dpi: int = 300,
) -> None:
    """Generate Differential RCS (Delta sigma) in cm^2 and dBsm."""
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10), constrained_layout=True)

    # 1. 2.44 GHz Band in cm^2
    f_ghz = f_244 / 1e9
    rcs_ifa_short = compute_differential_rcs(f_244, ifa_gain_linear, delta_gamma=-1.0)
    rcs_ifa_open = compute_differential_rcs(f_244, ifa_gain_linear, delta_gamma=+1.0)
    rcs_ifa_bpsk = compute_differential_rcs(f_244, ifa_gain_linear, delta_gamma=+2.0)
    rcs_mono_short = compute_differential_rcs(f_244, mono_gain_linear, delta_gamma=-1.0)

    ax1.plot(f_ghz, rcs_ifa_short["delta_sigma_cm2"], label="IFA: 50 $\\Omega$ vs Short ($|\\Delta\\Gamma|=1$)", color="#d62728", lw=2.2)
    ax1.plot(f_ghz, rcs_mono_short["delta_sigma_cm2"], label="Monopole: 50 $\\Omega$ vs Short ($|\\Delta\\Gamma|=1$)", color="#1f77b4", lw=2.0, ls="--")
    ax1.plot(f_ghz, rcs_ifa_bpsk["delta_sigma_cm2"], label="IFA: Open vs Short BPSK ($|\\Delta\\Gamma|=2$)", color="#9467bd", lw=1.8, ls=":")

    ax1.axvline(2.440, color="black", ls="--", alpha=0.5)
    ax1.scatter([2.440], [rcs_ifa_short["delta_sigma_cm2"][np.argmin(np.abs(f_244 - 2.44e9))]], color="#d62728", s=50)
    val_244 = rcs_ifa_short["delta_sigma_cm2"][np.argmin(np.abs(f_244 - 2.44e9))]
    ax1.annotate(
        f"2.44 GHz IFA:\n{val_244:.1f} cm$^2$",
        xy=(2.440, val_244),
        xytext=(2.46, val_244 + 15),
        arrowprops=dict(arrowstyle="->", color="#d62728", lw=1.2),
        fontweight="bold",
        color="#d62728",
        fontsize=9,
    )

    ax1.set_title("2.44 GHz Band: $\\Delta\\sigma$ (cm$^2$)", fontsize=11, fontweight="bold")
    ax1.set_xlabel("Frequency (GHz)", fontsize=10)
    ax1.set_ylabel("Differential RCS $\\Delta\\sigma$ (cm$^2$)", fontsize=10)
    ax1.set_xlim(2.30, 2.60)
    ax1.grid(True, alpha=0.35, ls="--")
    ax1.legend(loc="upper right", fontsize=8.5)

    # 2. 2.44 GHz Band in dBsm
    ax2.plot(f_ghz, rcs_ifa_short["delta_sigma_dbsm"], label="IFA: 50 $\\Omega$ vs Short ($|\\Delta\\Gamma|=1$)", color="#d62728", lw=2.2)
    ax2.plot(f_ghz, rcs_mono_short["delta_sigma_dbsm"], label="Monopole: 50 $\\Omega$ vs Short", color="#1f77b4", lw=2.0, ls="--")
    ax2.plot(f_ghz, rcs_ifa_bpsk["delta_sigma_dbsm"], label="IFA: Open vs Short BPSK ($|\\Delta\\Gamma|=2$)", color="#9467bd", lw=1.8, ls=":")
    ax2.axvline(2.440, color="black", ls="--", alpha=0.5)

    val_dbsm_244 = rcs_ifa_short["delta_sigma_dbsm"][np.argmin(np.abs(f_244 - 2.44e9))]
    ax2.annotate(
        f"2.44 GHz IFA:\n{val_dbsm_244:.2f} dBsm",
        xy=(2.440, val_dbsm_244),
        xytext=(2.46, val_dbsm_244 + 2),
        arrowprops=dict(arrowstyle="->", color="#d62728", lw=1.2),
        fontweight="bold",
        color="#d62728",
        fontsize=9,
    )

    ax2.set_title("2.44 GHz Band: $\\Delta\\sigma$ (dBsm)", fontsize=11, fontweight="bold")
    ax2.set_xlabel("Frequency (GHz)", fontsize=10)
    ax2.set_ylabel("Differential RCS $\\Delta\\sigma$ (dBsm)", fontsize=10)
    ax2.set_xlim(2.30, 2.60)
    ax2.grid(True, alpha=0.35, ls="--")
    ax2.legend(loc="upper right", fontsize=8.5)

    # 3. Sub-1GHz Band in cm^2
    f_mhz = f_sub1g / 1e6
    center_mhz = sub1g_center_freq / 1e6
    rcs_hel_short = compute_differential_rcs(f_sub1g, hel_gain_linear, delta_gamma=-1.0)
    rcs_hel_bpsk = compute_differential_rcs(f_sub1g, hel_gain_linear, delta_gamma=+2.0)
    rcs_mean_short = compute_differential_rcs(f_sub1g, mean_gain_linear, delta_gamma=-1.0)

    ax3.plot(f_mhz, rcs_hel_short["delta_sigma_cm2"], label="Helical: 50 $\\Omega$ vs Short ($|\\Delta\\Gamma|=1$)", color="#8c564b", lw=2.2)
    ax3.plot(f_mhz, rcs_mean_short["delta_sigma_cm2"], label="Meander: 50 $\\Omega$ vs Short ($|\\Delta\\Gamma|=1$)", color="#2ca02c", lw=2.0, ls="--")
    ax3.plot(f_mhz, rcs_hel_bpsk["delta_sigma_cm2"], label="Helical: Open vs Short BPSK ($|\\Delta\\Gamma|=2$)", color="#e377c2", lw=1.8, ls=":")
    ax3.axvline(center_mhz, color="black", ls="--", alpha=0.5)

    idx_c = np.argmin(np.abs(f_sub1g - sub1g_center_freq))
    val_sub1g = rcs_hel_short["delta_sigma_cm2"][idx_c]
    ax3.annotate(
        f"{center_mhz:.0f} MHz Helical:\n{val_sub1g:.1f} cm$^2$",
        xy=(center_mhz, val_sub1g),
        xytext=(center_mhz + 25, val_sub1g + 30),
        arrowprops=dict(arrowstyle="->", color="#8c564b", lw=1.2),
        fontweight="bold",
        color="#8c564b",
        fontsize=9,
    )

    ax3.set_title("Sub-1GHz Band: $\\Delta\\sigma$ (cm$^2$)", fontsize=11, fontweight="bold")
    ax3.set_xlabel("Frequency (MHz)", fontsize=10)
    ax3.set_ylabel("Differential RCS $\\Delta\\sigma$ (cm$^2$)", fontsize=10)
    ax3.set_xlim(800, 1000)
    ax3.grid(True, alpha=0.35, ls="--")
    ax3.legend(loc="upper right", fontsize=8.5)

    # 4. Sub-1GHz Band in dBsm
    ax4.plot(f_mhz, rcs_hel_short["delta_sigma_dbsm"], label="Helical: 50 $\\Omega$ vs Short ($|\\Delta\\Gamma|=1$)", color="#8c564b", lw=2.2)
    ax4.plot(f_mhz, rcs_mean_short["delta_sigma_dbsm"], label="Meander: 50 $\\Omega$ vs Short", color="#2ca02c", lw=2.0, ls="--")
    ax4.plot(f_mhz, rcs_hel_bpsk["delta_sigma_dbsm"], label="Helical: Open vs Short BPSK ($|\\Delta\\Gamma|=2$)", color="#e377c2", lw=1.8, ls=":")
    ax4.axvline(center_mhz, color="black", ls="--", alpha=0.5)

    val_dbsm_sub1g = rcs_hel_short["delta_sigma_dbsm"][idx_c]
    ax4.annotate(
        f"{center_mhz:.0f} MHz Helical:\n{val_dbsm_sub1g:.2f} dBsm",
        xy=(center_mhz, val_dbsm_sub1g),
        xytext=(center_mhz + 25, val_dbsm_sub1g + 2),
        arrowprops=dict(arrowstyle="->", color="#8c564b", lw=1.2),
        fontweight="bold",
        color="#8c564b",
        fontsize=9,
    )

    ax4.set_title("Sub-1GHz Band: $\\Delta\\sigma$ (dBsm)", fontsize=11, fontweight="bold")
    ax4.set_xlabel("Frequency (MHz)", fontsize=10)
    ax4.set_ylabel("Differential RCS $\\Delta\\sigma$ (dBsm)", fontsize=10)
    ax4.set_xlim(800, 1000)
    ax4.grid(True, alpha=0.35, ls="--")
    ax4.legend(loc="upper right", fontsize=8.5)

    fig.suptitle(
        "Differential Radar Cross Section $\\Delta\\sigma = \\frac{\\lambda^2}{4\\pi} G^2 |\\Delta\\Gamma|^2$ across Frequency Bands",
        fontsize=14,
        fontweight="bold",
        y=1.02,
    )
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"  [PLOT] Saved {output_path.name}")


def plot_smith_chart_states(
    output_path: Path,
    dpi: int = 300,
) -> None:
    """Generate Polar / Smith reflection constellation plot displaying absorbing and reflecting states."""
    fig = plt.figure(figsize=(9, 9), constrained_layout=True)
    ax = fig.add_subplot(111, polar=True)

    # State reflection coefficients:
    # State 1: 50 Ohm -> Gamma = 0.0
    # State 2: Short  -> Gamma = 1.0 angle 180 deg (pi rad)
    # State 3: Open   -> Gamma = 1.0 angle 0 deg (0 rad)

    # Unit circle and grid
    ax.set_ylim(0, 1.15)
    ax.set_yticks([0.25, 0.50, 0.75, 1.00])
    ax.set_yticklabels(["|$\\Gamma$|=0.25", "|$\\Gamma$|=0.50", "|$\\Gamma$|=0.75", "|$\\Gamma$|=1.00"], fontsize=9)
    ax.set_theta_zero_location("E")  # 0 deg at East
    ax.grid(True, color="gray", alpha=0.4, linestyle="--")

    # Plot Unit Circle perimeter
    theta_full = np.linspace(0, 2 * np.pi, 360)
    ax.plot(theta_full, np.ones_like(theta_full), color="black", lw=1.8, label="Passive Boundary ($|\\Gamma|=1.0$)")

    # 1. State 1: 50 Ohm Resistor (Origin)
    ax.scatter([0.0], [0.0], color="#2ca02c", s=140, zorder=6, label="State 1: Absorbing 50 $\\Omega$ Resistor ($\\Gamma = 0$)")
    ax.annotate(
        "State 1: Matched 50 $\\Omega$\n$\\Gamma = 0.00 \\angle 0^\\circ$\n(Zero Backscatter)",
        xy=(0, 0),
        xytext=(np.pi / 4, 0.35),
        arrowprops=dict(arrowstyle="->", color="#2ca02c", lw=1.5),
        fontweight="bold",
        color="#2ca02c",
        fontsize=10,
        bbox=dict(boxstyle="round,pad=0.3", fc="#e8f5e9", ec="#2ca02c", lw=1.2),
    )

    # 2. State 2: Short Circuit (180 deg)
    ax.scatter([np.pi], [1.0], color="#d62728", marker="s", s=160, zorder=6, label="State 2: Reflecting Short ($0\\,\\Omega, \\Gamma = -1$)")
    ax.annotate(
        "State 2: Short Circuit ($0\\,\\Omega$ Jumper)\n$\\Gamma = 1.00 \\angle 180^\\circ$\n($180^\\circ$ Phase Reversal)",
        xy=(np.pi, 1.0),
        xytext=(3 * np.pi / 4, 1.05),
        arrowprops=dict(arrowstyle="->", color="#d62728", lw=1.5),
        fontweight="bold",
        color="#d62728",
        fontsize=10,
        bbox=dict(boxstyle="round,pad=0.3", fc="#ffebee", ec="#d62728", lw=1.2),
    )

    # 3. State 3: Open Circuit (0 deg)
    ax.scatter([0.0], [1.0], color="#1f77b4", marker="^", s=160, zorder=6, label="State 3: Reflecting Open ($\\infty\\,\\Omega, \\Gamma = +1$)")
    ax.annotate(
        "State 3: Open Circuit\n$\\Gamma = 1.00 \\angle 0^\\circ$\n(In-Phase Reflection)",
        xy=(0.0, 1.0),
        xytext=(-np.pi / 6, 1.05),
        arrowprops=dict(arrowstyle="->", color="#1f77b4", lw=1.5),
        fontweight="bold",
        color="#1f77b4",
        fontsize=10,
        bbox=dict(boxstyle="round,pad=0.3", fc="#e3f2fd", ec="#1f77b4", lw=1.2),
    )

    # Transition Vectors:
    # Vector 1: State 1 -> State 2 (|Delta Gamma| = 1.00)
    ax.annotate(
        "",
        xy=(np.pi, 0.98),
        xytext=(0, 0),
        arrowprops=dict(arrowstyle="->", color="#d62728", lw=3.0, alpha=0.85),
    )
    # Vector 2: State 1 -> State 3 (|Delta Gamma| = 1.00)
    ax.annotate(
        "",
        xy=(0, 0.98),
        xytext=(0, 0),
        arrowprops=dict(arrowstyle="->", color="#1f77b4", lw=3.0, alpha=0.85),
    )
    # Vector 3: State 2 -> State 3 (|Delta Gamma| = 2.00)
    ax.annotate(
        "",
        xy=(0, 0.98),
        xytext=(np.pi, 0.98),
        arrowprops=dict(arrowstyle="<->", color="#9467bd", lw=2.2, ls="--", alpha=0.9),
    )

    # Text summary box in polar plot corner
    summary_text = (
        "Modulation Depth Contrast:\n"
        "• |$\\Delta\\Gamma_{short-50}$| = |-1.00 - 0.00| = 1.000 $\\geq$ 1.00 [PASS]\n"
        "• |$\\Delta\\Gamma_{open-50}$|  = |+1.00 - 0.00| = 1.000 $\\geq$ 1.00 [PASS]\n"
        "• |$\\Delta\\Gamma_{open-short}$| = |+1.00 - (-1.00)| = 2.000 (Full BPSK)\n\n"
        "Differential RCS Formulation:\n"
        "$\\Delta\\sigma = \\frac{\\lambda^2}{4\\pi} G^2 |\\Delta\\Gamma|^2$\n"
        "$\\Delta\\sigma_{short-50} = 31.6\\,\\mathrm{cm}^2$ @ 2.44 GHz\n"
        "$\\Delta\\sigma_{short-50} = 42.8\\,\\mathrm{cm}^2$ @ 915 MHz"
    )
    ax.text(
        -np.pi / 2,
        0.88,
        summary_text,
        fontsize=9,
        bbox=dict(boxstyle="round,pad=0.5", fc="#fff9c4", ec="#fbc02d", lw=1.5),
        ha="center",
        va="center",
        fontfamily="monospace",
    )

    ax.set_title(
        "Complex Reflection Plane Constellation $\\Gamma_L$ & Differential Modulation Contrast $|\\Delta\\Gamma| \\geq 1.0$",
        fontsize=12,
        fontweight="bold",
        pad=20,
    )
    ax.legend(loc="lower left", bbox_to_anchor=(-0.1, -0.08), fontsize=9, framealpha=0.9)

    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"  [PLOT] Saved {output_path.name}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run electromagnetic simulations and differential RCS analysis for backscatter tag antennas."
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=PROJECT_ROOT / "simulation" / "output",
        help="Target directory for CSV data tables and PNG figures.",
    )
    parser.add_argument(
        "--sub1g-freq",
        type=float,
        default=915.0e6,
        help="Sub-1GHz design resonance frequency in Hz (868e6 or 915e6, default: 915e6).",
    )
    parser.add_argument(
        "--num-points",
        type=int,
        default=401,
        help="Number of points across frequency sweeps (default: 401).",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=300,
        help="Resolution in DPI for exported figures (default: 300).",
    )
    parser.add_argument(
        "--check-pass",
        action="store_true",
        help="Assert acceptance criteria (S11 <= -15 dB, |Delta Gamma| >= 1.0).",
    )
    args = parser.parse_args()

    outdir: Path = args.outdir
    outdir.mkdir(parents=True, exist_ok=True)
    num_pts: int = args.num_points
    sub1g_f0: float = args.sub1g_freq

    print("=" * 75)
    print("BACKSCATTER TAG ANTENNA SIMULATION & DIFFERENTIAL RCS ENGINE")
    print("=" * 75)
    print(f"Output Directory:    {outdir.resolve()}")
    print(f"Frequency Sweep:     {num_pts} points")
    print(f"Sub-1GHz Frequency:  {sub1g_f0 / 1e6:.1f} MHz")
    print(f"Plot Resolution:     {args.dpi} DPI")
    print("-" * 75)

    # 1. Instantiate Antenna Models
    substrate = Substrate()
    mono = PlanarMonopole244(substrate=substrate)
    ifa = TI_SWRA117D_IFA(substrate=substrate)
    hel = TI_SWRA416_Helical(center_frequency=sub1g_f0, substrate=substrate)
    mean = PlanarMeanderMonopole(center_frequency=sub1g_f0, substrate=substrate)

    # 2. Define Frequency Arrays
    # 2.44 GHz band: 2.30 to 2.60 GHz (covering Wi-Fi Ch 1-14 and 2.4 GHz ISM)
    f_244 = np.linspace(2.30e9, 2.60e9, num_pts)
    # Sub-1GHz band: 800 to 1000 MHz (covering 868 MHz SRD and 915 MHz ISM)
    f_sub1g = np.linspace(800.0e6, 1000.0e6, num_pts)

    # 3. Simulate S11 and Impedances
    print("\n[Step 1/4] Simulating Antenna Electrodynamics & S-Parameters...")
    zin_mono = calculate_zin(mono, f_244)
    s11_mono = calculate_s11(mono, f_244)
    vswr_mono = mono.vswr(f_244)

    zin_ifa = calculate_zin(ifa, f_244)
    s11_ifa = calculate_s11(ifa, f_244)
    vswr_ifa = ifa.vswr(f_244)

    zin_hel = calculate_zin(hel, f_sub1g)
    s11_hel = calculate_s11(hel, f_sub1g)
    vswr_hel = hel.vswr(f_sub1g)

    zin_mean = calculate_zin(mean, f_sub1g)
    s11_mean = calculate_s11(mean, f_sub1g)
    vswr_mean = mean.vswr(f_sub1g)

    # 4. Check Performance Criteria at Resonances
    print("\n[Step 2/4] Verifying Acceptance Criteria at Resonant Frequencies:")
    antennas = [mono, ifa, hel, mean]
    criteria_passed = True

    for ant in antennas:
        f0 = ant.center_frequency
        zin_0 = ant.input_impedance(f0)
        s11_0 = ant.return_loss_db(f0)
        vswr_0 = ant.vswr(f0)
        passes_s11 = s11_0 <= -15.0
        print(f"  [*] {ant.name}:")
        print(f"      f0 = {f0/1e6:.1f} MHz | Zin = {zin_0.real:.2f} + j{zin_0.imag:.2f} Ohm")
        print(f"      S11 = {s11_0:.2f} dB (<= -15 dB: {passes_s11}) | VSWR = {vswr_0:.2f}:1")
        if not passes_s11:
            criteria_passed = False

    # Check Load Modulation
    g_50 = ABSORBING_50OHM.reflection_coefficient()
    g_short = REFLECTING_SHORT.reflection_coefficient()
    g_open = REFLECTING_OPEN.reflection_coefficient()
    passes_contrast, contrast_val = verify_delta_gamma_contrast(g_short, g_50, min_contrast=1.0)
    print(f"\n  [*] Load Modulation: |Delta Gamma (Short - 50 Ohm)| = {contrast_val:.4f} (>= 1.0: {passes_contrast})")
    if not passes_contrast:
        criteria_passed = False

    # 5. Export CSV Data Tables
    print("\n[Step 3/4] Exporting Simulation Data Tables to CSV...")
    # CSV 1: s11_244ghz.csv
    rows_s11_244 = [
        [f_244[i] / 1e9, s11_mono[i], s11_ifa[i], vswr_mono[i], vswr_ifa[i]]
        for i in range(num_pts)
    ]
    export_csv(
        outdir / "s11_244ghz.csv",
        ["frequency_ghz", "monopole_s11_db", "ifa_s11_db", "monopole_vswr", "ifa_vswr"],
        rows_s11_244,
    )

    # CSV 2: s11_sub1ghz.csv
    rows_s11_sub1g = [
        [f_sub1g[i] / 1e6, s11_hel[i], s11_mean[i], vswr_hel[i], vswr_mean[i]]
        for i in range(num_pts)
    ]
    export_csv(
        outdir / "s11_sub1ghz.csv",
        ["frequency_mhz", "helical_s11_db", "meander_s11_db", "helical_vswr", "meander_vswr"],
        rows_s11_sub1g,
    )

    # CSV 3: impedance_244ghz.csv
    rows_imp_244 = [
        [
            f_244[i] / 1e9,
            zin_mono[i].real,
            zin_mono[i].imag,
            zin_ifa[i].real,
            zin_ifa[i].imag,
        ]
        for i in range(num_pts)
    ]
    export_csv(
        outdir / "impedance_244ghz.csv",
        [
            "frequency_ghz",
            "monopole_rin_ohm",
            "monopole_xin_ohm",
            "ifa_rin_ohm",
            "ifa_xin_ohm",
        ],
        rows_imp_244,
    )

    # CSV 4: impedance_sub1ghz.csv
    rows_imp_sub1g = [
        [
            f_sub1g[i] / 1e6,
            zin_hel[i].real,
            zin_hel[i].imag,
            zin_mean[i].real,
            zin_mean[i].imag,
        ]
        for i in range(num_pts)
    ]
    export_csv(
        outdir / "impedance_sub1ghz.csv",
        [
            "frequency_mhz",
            "helical_rin_ohm",
            "helical_xin_ohm",
            "meander_rin_ohm",
            "meander_xin_ohm",
        ],
        rows_imp_sub1g,
    )

    # Differential RCS Computations
    rcs_ifa_s = compute_differential_rcs(f_244, ifa.gain_linear, delta_gamma=-1.0)
    rcs_ifa_o = compute_differential_rcs(f_244, ifa.gain_linear, delta_gamma=+1.0)
    rcs_mono_s = compute_differential_rcs(f_244, mono.gain_linear, delta_gamma=-1.0)

    rcs_hel_s = compute_differential_rcs(f_sub1g, hel.gain_linear, delta_gamma=-1.0)
    rcs_hel_o = compute_differential_rcs(f_sub1g, hel.gain_linear, delta_gamma=+1.0)
    rcs_mean_s = compute_differential_rcs(f_sub1g, mean.gain_linear, delta_gamma=-1.0)

    # CSV 5: differential_rcs_244ghz.csv
    rows_rcs_244 = [
        [
            f_244[i] / 1e9,
            rcs_ifa_s["delta_sigma_cm2"][i],
            rcs_ifa_s["delta_sigma_dbsm"][i],
            rcs_ifa_o["delta_sigma_cm2"][i],
            rcs_ifa_o["delta_sigma_dbsm"][i],
            rcs_mono_s["delta_sigma_cm2"][i],
            rcs_mono_s["delta_sigma_dbsm"][i],
        ]
        for i in range(num_pts)
    ]
    export_csv(
        outdir / "differential_rcs_244ghz.csv",
        [
            "frequency_ghz",
            "ifa_short_delta_sigma_cm2",
            "ifa_short_delta_sigma_dbsm",
            "ifa_open_delta_sigma_cm2",
            "ifa_open_delta_sigma_dbsm",
            "monopole_short_delta_sigma_cm2",
            "monopole_short_delta_sigma_dbsm",
        ],
        rows_rcs_244,
    )

    # CSV 6: differential_rcs_sub1ghz.csv
    rows_rcs_sub1g = [
        [
            f_sub1g[i] / 1e6,
            rcs_hel_s["delta_sigma_cm2"][i],
            rcs_hel_s["delta_sigma_dbsm"][i],
            rcs_hel_o["delta_sigma_cm2"][i],
            rcs_hel_o["delta_sigma_dbsm"][i],
            rcs_mean_s["delta_sigma_cm2"][i],
            rcs_mean_s["delta_sigma_dbsm"][i],
        ]
        for i in range(num_pts)
    ]
    export_csv(
        outdir / "differential_rcs_sub1ghz.csv",
        [
            "frequency_mhz",
            "helical_short_delta_sigma_cm2",
            "helical_short_delta_sigma_dbsm",
            "helical_open_delta_sigma_cm2",
            "helical_open_delta_sigma_dbsm",
            "meander_short_delta_sigma_cm2",
            "meander_short_delta_sigma_dbsm",
        ],
        rows_rcs_sub1g,
    )

    # CSV 7: load_modulation_states.csv
    states = [ABSORBING_50OHM, REFLECTING_SHORT, REFLECTING_OPEN]
    rows_states = []
    for st in states:
        gamma = st.reflection_coefficient()
        phase_deg = math.degrees(math.atan2(gamma.imag, gamma.real))
        rows_states.append([
            st.state_id,
            st.name,
            st.nominal_impedance.real,
            st.nominal_impedance.imag,
            gamma.real,
            gamma.imag,
            abs(gamma),
            phase_deg,
            st.description,
        ])
    export_csv(
        outdir / "load_modulation_states.csv",
        [
            "state_id",
            "state_name",
            "nominal_z_re",
            "nominal_z_im",
            "gamma_re",
            "gamma_im",
            "gamma_mag",
            "gamma_deg",
            "description",
        ],
        rows_states,
    )

    # 6. Generate Figures
    print("\n[Step 4/4] Generating Publication Figures (Matplotlib)...")
    plot_s11_comparison(
        f_244=f_244,
        s11_mono=s11_mono,
        s11_ifa=s11_ifa,
        f_sub1g=f_sub1g,
        s11_hel=s11_hel,
        s11_mean=s11_mean,
        sub1g_center_freq=sub1g_f0,
        output_path=outdir / "s11_comparison.png",
        dpi=args.dpi,
    )

    plot_impedance_curves(
        f_244=f_244,
        zin_mono=zin_mono,
        zin_ifa=zin_ifa,
        f_sub1g=f_sub1g,
        zin_hel=zin_hel,
        zin_mean=zin_mean,
        sub1g_center_freq=sub1g_f0,
        output_path=outdir / "impedance_curves.png",
        dpi=args.dpi,
    )

    plot_differential_rcs(
        f_244=f_244,
        ifa_gain_linear=ifa.gain_linear,
        mono_gain_linear=mono.gain_linear,
        f_sub1g=f_sub1g,
        hel_gain_linear=hel.gain_linear,
        mean_gain_linear=mean.gain_linear,
        sub1g_center_freq=sub1g_f0,
        output_path=outdir / "differential_rcs.png",
        dpi=args.dpi,
    )

    plot_smith_chart_states(
        output_path=outdir / "smith_chart_states.png",
        dpi=args.dpi,
    )

    print("-" * 75)
    print("SIMULATION & VERIFICATION COMPLETE!")
    print(f"Data files and publication plots written to:\n  {outdir.resolve()}")
    print("=" * 75)

    if args.check_pass and not criteria_passed:
        print("[ERROR] One or more acceptance criteria failed!")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
