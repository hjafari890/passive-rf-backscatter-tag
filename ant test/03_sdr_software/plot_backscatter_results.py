"""Publication-Quality Plotting Module for Backscatter SDR Validation.

Generates 300 DPI publication figures:
1. cw_step_response.png: Two-panel strip chart showing P(t) (dBFS) and I(t), Q(t) traces
2. cw_iq_trajectory.png: Complex plane constellation scatter with centroids and Delta V arrow
3. wifi_ambient_backscatter.png: Ambient Wi-Fi packet envelope with periodic beacons & delta P
4. wifi_iq_constellation.png: Wi-Fi complex baseband constellation comparing load states
"""

from __future__ import annotations

import os
from typing import Optional, Tuple

import matplotlib
matplotlib.use("Agg")  # Non-interactive headless backend
import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np

try:
    from .backscatter_metrics import (
        compute_complex_vector_distance,
        compute_differential_power,
        compute_moving_average_power,
        compute_scnr,
        detect_step_transition,
        detect_wifi_packets,
    )
except ImportError:
    import sys
    from pathlib import Path
    _script_dir = Path(__file__).resolve().parent
    if str(_script_dir) not in sys.path:
        sys.path.insert(0, str(_script_dir))
    from backscatter_metrics import (
        compute_complex_vector_distance,
        compute_differential_power,
        compute_moving_average_power,
        compute_scnr,
        detect_step_transition,
        detect_wifi_packets,
    )


def _draw_confidence_ellipse(
    ax: matplotlib.axes.Axes,
    samples: np.ndarray,
    centroid: complex,
    n_std: float = 2.0,
    edgecolor: str = "blue",
    facecolor: str = "none",
    linestyle: str = "--",
    alpha: float = 0.8,
) -> None:
    """Draw a 2-sigma covariance confidence ellipse around cluster centroid."""
    if len(samples) < 5:
        return

    pts = np.column_stack((samples.real, samples.imag))
    cov = np.cov(pts, rowvar=False)
    if cov.shape != (2, 2) or np.isnan(cov).any():
        return

    vals, vecs = np.linalg.eigh(cov)
    vals = np.maximum(vals, 1e-12)
    order = vals.argsort()[::-1]
    vals, vecs = vals[order], vecs[:, order]

    theta = np.degrees(np.arctan2(*vecs[:, 0][::-1]))
    width, height = 2.0 * n_std * np.sqrt(vals)

    ellipse = patches.Ellipse(
        xy=(centroid.real, centroid.imag),
        width=width,
        height=height,
        angle=theta,
        edgecolor=edgecolor,
        facecolor=facecolor,
        linestyle=linestyle,
        linewidth=1.5,
        alpha=alpha,
    )
    ax.add_patch(ellipse)


def plot_cw_step_response(
    samples: np.ndarray,
    sample_rate: float,
    output_path: str,
    switch_idx: Optional[int] = None,
    guard_band_ms: float = 10.0,
) -> None:
    """Generate two-panel time-domain strip chart for Mode 1 CW backscatter.

    Args:
        samples: 1D complex64 array of received CW samples.
        sample_rate: Sample rate in Samples/s.
        output_path: Destination path for PNG file.
        switch_idx: Optional pre-detected switch index.
        guard_band_ms: Guard band in ms around switch event.
    """
    n_samples = len(samples)
    t = np.arange(n_samples) / sample_rate

    if switch_idx is None:
        switch_idx, s1, s2 = detect_step_transition(samples, sample_rate, guard_band_ms)
    else:
        guard_n = int(sample_rate * (guard_band_ms * 1e-3))
        s1 = samples[: max(1, switch_idx - guard_n)]
        s2 = samples[min(n_samples - 1, switch_idx + guard_n) :]

    t_switch = switch_idx / sample_rate

    # Compute moving average power
    w_size = max(50, int(sample_rate * 0.001))  # 1 ms window
    p_lin, p_db = compute_moving_average_power(samples, window_size=w_size)
    delta_p_lin, delta_p_db = compute_differential_power(s1, s2)
    p1_mean_db = 10.0 * np.log10(max(np.mean(np.abs(s1) ** 2), 1e-12))
    p2_mean_db = 10.0 * np.log10(max(np.mean(np.abs(s2) ** 2), 1e-12))

    # Decimate for plotting if large
    max_plot_pts = 40000
    stride = max(1, n_samples // max_plot_pts)
    t_plot = t[::stride] * 1e3  # in milliseconds
    p_db_plot = p_db[::stride]
    i_plot = samples.real[::stride]
    q_plot = samples.imag[::stride]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True, dpi=300)
    fig.patch.set_facecolor("white")

    # Panel 1: Received Power Envelope P(t)
    ax1.plot(t_plot, p_db_plot, color="#1f77b4", linewidth=1.2, label=r"Moving Average $P_{\mathrm{rx}}(t)$ (1 ms window)")
    ax1.axvline(t_switch * 1e3, color="#d62728", linestyle="--", linewidth=1.5, label=f"Tag Switch ($t = {t_switch*1e3:.1f}$ ms)")
    
    # Shading for states
    ax1.axvspan(0, t_switch * 1e3, color="#2ca02c", alpha=0.12, label=r"State 1: $50\,\Omega$ Absorbing ($\Gamma \approx 0$)")
    ax1.axvspan(t_switch * 1e3, t[-1] * 1e3, color="#ff7f0e", alpha=0.12, label=r"State 2: Short Reflecting ($|\Gamma| = 1.0$)")

    # Annotate metrics box
    metric_text = (
        f"State 1 Mean: {p1_mean_db:.2f} dBFS\n"
        f"State 2 Mean: {p2_mean_db:.2f} dBFS\n"
        f"$\\Delta P_{{\\mathrm{{rx}}}}$: {delta_p_db:+.2f} dB"
    )
    ax1.text(
        0.02,
        0.15,
        metric_text,
        transform=ax1.transAxes,
        fontsize=9,
        verticalalignment="bottom",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="white", edgecolor="#666666", alpha=0.9),
    )

    ax1.set_ylabel("Power (dBFS)", fontsize=11, fontweight="bold")
    ax1.set_title("Mode 1: CW Carrier Backscatter Step Response", fontsize=12, fontweight="bold")
    ax1.grid(True, linestyle=":", alpha=0.6)
    ax1.legend(loc="upper right", fontsize=8.5, framealpha=0.9)

    # Panel 2: In-Phase and Quadrature envelopes
    ax2.plot(t_plot, i_plot, color="#0055ff", linewidth=0.8, alpha=0.85, label=r"In-Phase $I(t)$")
    ax2.plot(t_plot, q_plot, color="#ff5500", linewidth=0.8, alpha=0.85, label=r"Quadrature $Q(t)$")
    ax2.axvline(t_switch * 1e3, color="#d62728", linestyle="--", linewidth=1.5)
    ax2.axvspan(0, t_switch * 1e3, color="#2ca02c", alpha=0.12)
    ax2.axvspan(t_switch * 1e3, t[-1] * 1e3, color="#ff7f0e", alpha=0.12)

    ax2.set_xlabel("Time (ms)", fontsize=11, fontweight="bold")
    ax2.set_ylabel("Amplitude", fontsize=11, fontweight="bold")
    ax2.grid(True, linestyle=":", alpha=0.6)
    ax2.legend(loc="upper right", fontsize=8.5, framealpha=0.9)

    plt.tight_layout()
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    plt.savefig(output_path, dpi=300, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)


def plot_cw_iq_trajectory(
    samples: np.ndarray,
    sample_rate: float,
    output_path: str,
    switch_idx: Optional[int] = None,
    guard_band_ms: float = 10.0,
) -> None:
    """Generate complex I/Q constellation and trajectory plot for Mode 1 CW.

    Args:
        samples: 1D complex64 samples.
        sample_rate: Sample rate in Samples/s.
        output_path: Destination path for PNG figure.
        switch_idx: Optional pre-detected switch index.
        guard_band_ms: Guard band in ms around switch.
    """
    if switch_idx is None:
        switch_idx, s1, s2 = detect_step_transition(samples, sample_rate, guard_band_ms)
    else:
        n_samples = len(samples)
        guard_n = int(sample_rate * (guard_band_ms * 1e-3))
        s1 = samples[: max(1, switch_idx - guard_n)]
        s2 = samples[min(n_samples - 1, switch_idx + guard_n) :]

    delta_v, v1_cen, v2_cen, delta_phi = compute_complex_vector_distance(s1, s2)
    _, delta_p_db = compute_differential_power(s1, s2)
    _, scnr_db = compute_scnr(s1, s2)

    # Subsample points for scatter plot to avoid sluggish rendering
    max_pts = 6000
    s1_pts = s1[:: max(1, len(s1) // max_pts)]
    s2_pts = s2[:: max(1, len(s2) // max_pts)]

    fig, ax = plt.subplots(figsize=(8, 8), dpi=300)
    fig.patch.set_facecolor("white")

    # Scatter points for both states
    ax.scatter(s1_pts.real, s1_pts.imag, c="#1f77b4", s=6, alpha=0.25, label=r"State 1 ($50\,\Omega$ Absorbing)")
    ax.scatter(s2_pts.real, s2_pts.imag, c="#d62728", s=6, alpha=0.25, label=r"State 2 (Short Reflecting)")

    # Draw 2-sigma confidence ellipses
    _draw_confidence_ellipse(ax, s1, v1_cen, n_std=2.0, edgecolor="#0b407a", linestyle="--")
    _draw_confidence_ellipse(ax, s2, v2_cen, n_std=2.0, edgecolor="#8b0000", linestyle="--")

    # Plot large centroids
    ax.plot(
        v1_cen.real,
        v1_cen.imag,
        "o",
        markersize=11,
        color="#0b407a",
        markeredgecolor="white",
        markeredgewidth=2,
        label=r"Centroid $\bar{V}_1$",
        zorder=5,
    )
    ax.plot(
        v2_cen.real,
        v2_cen.imag,
        "o",
        markersize=11,
        color="#8b0000",
        markeredgecolor="white",
        markeredgewidth=2,
        label=r"Centroid $\bar{V}_2$",
        zorder=5,
    )

    # Plot differential vector arrow
    ax.annotate(
        "",
        xy=(v2_cen.real, v2_cen.imag),
        xytext=(v1_cen.real, v1_cen.imag),
        arrowprops=dict(arrowstyle="-|>", color="#00aa55", lw=2.5, mutation_scale=20),
        zorder=6,
    )

    # Annotate mid-arrow label
    mid_x = 0.5 * (v1_cen.real + v2_cen.real)
    mid_y = 0.5 * (v1_cen.imag + v2_cen.imag)
    ax.text(
        mid_x,
        mid_y + 0.015,
        r"$\Delta \vec{V}_{\mathrm{rx}}$",
        color="#007733",
        fontsize=12,
        fontweight="bold",
        ha="center",
        zorder=7,
    )

    # Inset metrics card
    card_text = (
        f"$\\Delta |V_{{\\mathrm{{rx}}}}| = {delta_v:.4f}$\n"
        f"$\\Delta \\theta = {delta_phi:+.1f}^\\circ$\n"
        f"$\\Delta P_{{\\mathrm{{rx}}}} = {delta_p_db:+.2f}$ dB\n"
        f"$\\mathrm{{SCNR}}_{{\\mathrm{{dB}}}} = {scnr_db:.1f}$ dB"
    )
    ax.text(
        0.03,
        0.97,
        card_text,
        transform=ax.transAxes,
        fontsize=10,
        verticalalignment="top",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="#f8f9fa", edgecolor="#333333", alpha=0.92),
        zorder=8,
    )

    ax.axhline(0, color="gray", linestyle=":", alpha=0.5)
    ax.axvline(0, color="gray", linestyle=":", alpha=0.5)
    ax.set_aspect("equal", adjustable="datalim")
    ax.set_xlabel("In-Phase (I)", fontsize=11, fontweight="bold")
    ax.set_ylabel("Quadrature (Q)", fontsize=11, fontweight="bold")
    ax.set_title("Mode 1: Complex Plane I/Q Constellation & Differential Vector", fontsize=12, fontweight="bold")
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="lower right", fontsize=9, framealpha=0.9)

    plt.tight_layout()
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    plt.savefig(output_path, dpi=300, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)


def plot_wifi_ambient_backscatter(
    samples: np.ndarray,
    sample_rate: float,
    output_path: str,
    switch_idx: Optional[int] = None,
) -> None:
    """Generate ambient Wi-Fi packet energy envelope figure for Mode 2.

    Args:
        samples: 1D complex64 samples.
        sample_rate: Sample rate in Samples/s.
        output_path: Destination path for PNG figure.
        switch_idx: Optional switch index separating State 1 and State 2.
    """
    n_samples = len(samples)
    t = np.arange(n_samples) / sample_rate
    if switch_idx is None:
        switch_idx = n_samples // 2
    t_switch = switch_idx / sample_rate

    # Packet detection metrics
    wifi_metrics = detect_wifi_packets(samples, sample_rate)

    # Moving average power with short window matching OFDM symbol
    w_size = max(16, int(sample_rate * 0.00005))  # 50 us window
    p_lin, p_db = compute_moving_average_power(samples, window_size=w_size)

    # Decimate for plotting
    max_pts = 40000
    stride = max(1, n_samples // max_pts)
    t_plot = t[::stride] * 1e3
    p_plot = p_lin[::stride]

    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=300)
    fig.patch.set_facecolor("white")

    ax.plot(t_plot, p_plot, color="#004488", linewidth=1.0, label="Ambient Wi-Fi Instantaneous Power")
    ax.axvline(t_switch * 1e3, color="#d62728", linestyle="--", linewidth=1.5, label=f"Tag Switch ({t_switch*1e3:.1f} ms)")

    # Shading for states
    ax.axvspan(0, t_switch * 1e3, color="#2ca02c", alpha=0.10, label=r"State 1: $50\,\Omega$ Absorbing ($\Gamma \approx 0$)")
    ax.axvspan(t_switch * 1e3, t[-1] * 1e3, color="#ff7f0e", alpha=0.10, label=r"State 2: Short Reflecting ($|\Gamma| = 1.0$)")

    # Annotate metrics box
    card_text = (
        f"Wi-Fi Carrier: 2.437 GHz (Ch 6)\n"
        f"Detected Bursts: {wifi_metrics['num_bursts']}\n"
        f"Beacon Mean State 1: {wifi_metrics['mean_beacon_s1']:.5f}\n"
        f"Beacon Mean State 2: {wifi_metrics['mean_beacon_s2']:.5f}\n"
        f"$\\Delta P_{{\\mathrm{{beacon}}}}$: {wifi_metrics['delta_beacon_db']:+.2f} dB"
    )
    ax.text(
        0.02,
        0.95,
        card_text,
        transform=ax.transAxes,
        fontsize=9,
        verticalalignment="top",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="#f8f9fa", edgecolor="#444444", alpha=0.92),
    )

    ax.set_xlabel("Time (ms)", fontsize=11, fontweight="bold")
    ax.set_ylabel("Normalized Baseband Power", fontsize=11, fontweight="bold")
    ax.set_title("Mode 2: Ambient Wi-Fi Channel Energy & Beacon Backscatter Modulation", fontsize=12, fontweight="bold")
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="upper right", fontsize=8.5, framealpha=0.9)

    plt.tight_layout()
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    plt.savefig(output_path, dpi=300, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)


def plot_wifi_iq_constellation(
    samples: np.ndarray,
    sample_rate: float,
    output_path: str,
    switch_idx: Optional[int] = None,
) -> None:
    """Generate ambient Wi-Fi baseband constellation comparison figure.

    Args:
        samples: 1D complex64 samples.
        sample_rate: Sample rate in Samples/s.
        output_path: Destination path for PNG figure.
        switch_idx: Optional switch index separating State 1 and State 2.
    """
    n_samples = len(samples)
    if switch_idx is None:
        switch_idx = n_samples // 2

    s1 = samples[:switch_idx]
    s2 = samples[switch_idx:]

    v1_cen = complex(np.mean(s1))
    v2_cen = complex(np.mean(s2))
    delta_v = abs(v2_cen - v1_cen)

    # Subsample points for constellation display
    max_pts = 6000
    s1_pts = s1[:: max(1, len(s1) // max_pts)]
    s2_pts = s2[:: max(1, len(s2) // max_pts)]

    fig, ax = plt.subplots(figsize=(8, 8), dpi=300)
    fig.patch.set_facecolor("white")

    ax.scatter(s1_pts.real, s1_pts.imag, c="#1f77b4", s=6, alpha=0.25, label=r"State 1 ($50\,\Omega$ Absorbing)")
    ax.scatter(s2_pts.real, s2_pts.imag, c="#ff7f0e", s=6, alpha=0.25, label=r"State 2 (Short Reflecting)")

    # Plot centroids
    ax.plot(
        v1_cen.real,
        v1_cen.imag,
        "o",
        markersize=10,
        color="#0b407a",
        markeredgecolor="white",
        markeredgewidth=2,
        label=r"State 1 Centroid $\bar{V}_1$",
        zorder=5,
    )
    ax.plot(
        v2_cen.real,
        v2_cen.imag,
        "o",
        markersize=10,
        color="#c05000",
        markeredgecolor="white",
        markeredgewidth=2,
        label=r"State 2 Centroid $\bar{V}_2$",
        zorder=5,
    )

    # Vector arrow
    ax.annotate(
        "",
        xy=(v2_cen.real, v2_cen.imag),
        xytext=(v1_cen.real, v1_cen.imag),
        arrowprops=dict(arrowstyle="-|>", color="#00aa55", lw=2.2, mutation_scale=18),
        zorder=6,
    )

    card_text = (
        f"Ambient Channel: 2.437 GHz\n"
        f"$\\Delta |V_{{\\mathrm{{rx}}}}| = {delta_v:.5f}$\n"
        f"$|\\bar{{V}}_1| = {abs(v1_cen):.5f}$\n"
        f"$|\\bar{{V}}_2| = {abs(v2_cen):.5f}$"
    )
    ax.text(
        0.03,
        0.97,
        card_text,
        transform=ax.transAxes,
        fontsize=10,
        verticalalignment="top",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="#f8f9fa", edgecolor="#333333", alpha=0.92),
        zorder=7,
    )

    ax.axhline(0, color="gray", linestyle=":", alpha=0.5)
    ax.axvline(0, color="gray", linestyle=":", alpha=0.5)
    ax.set_aspect("equal", adjustable="datalim")
    ax.set_xlabel("In-Phase (I)", fontsize=11, fontweight="bold")
    ax.set_ylabel("Quadrature (Q)", fontsize=11, fontweight="bold")
    ax.set_title("Mode 2: Ambient Wi-Fi Baseband Constellation Comparison", fontsize=12, fontweight="bold")
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="lower right", fontsize=9, framealpha=0.9)

    plt.tight_layout()
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    plt.savefig(output_path, dpi=300, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
