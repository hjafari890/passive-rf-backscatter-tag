"""Generates high-resolution PNG render of Board 3 (2.4 GHz Leggiero Bowtie Tag)."""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

def render_board3():
    fig, ax = plt.subplots(figsize=(8.5, 7.5), dpi=150)
    ax.set_facecolor('#1e2227')
    fig.patch.set_facecolor('#141619')

    # Board outline (50.0 x 45.0 mm, X in [5, 55], Y in [5, 50])
    board = patches.Rectangle((5, 5), 50, 45, linewidth=2, edgecolor='#e5c07b', facecolor='#282c34', zorder=1)
    ax.add_patch(board)

    # Leggiero Ground Cavity Keepout (Bare FR-4 empty space around bowtie)
    # X in [12, 48], Y in [7.5, 23.0] -> 36.0 mm x 15.5 mm
    cavity = patches.Rectangle((12, 7.5), 36, 15.5, linewidth=1.5, linestyle='--', edgecolor='#e06c75', facecolor='#21252b', alpha=0.9, zorder=2)
    ax.add_patch(cavity)
    ax.text(30.0, 6.2, "LEGGIERO APERTURE CAVITY (EMPTY SPACE / BARE FR-4)", color='#e06c75', fontsize=7.5, ha='center', fontweight='bold', zorder=5)

    # Unified Ground Plane on F.Cu
    # Surrounds top, left, right, and bottom flanks
    zone_pts = [
        [5.5, 5.5], [54.5, 5.5], [54.5, 49.5], [31.5, 49.5],
        [31.5, 23.0], [48.0, 23.0], [48.0, 7.5], [12.0, 7.5],
        [12.0, 23.0], [28.5, 23.0], [28.5, 24.2], [26.0, 24.2],
        [26.0, 29.5], [28.5, 29.5], [28.5, 49.5], [5.5, 49.5]
    ]
    zone_poly = patches.Polygon(zone_pts, closed=True, facecolor='#b58900', edgecolor='#d19a66', alpha=0.85, zorder=3)
    ax.add_patch(zone_poly)

    # 50 Ohm Feedline (X=30.0, W=1.85 mm, Y from 16 to 48.4)
    feedline = patches.Rectangle((30 - 1.85/2, 16), 1.85, 32.4, facecolor='#d19a66', edgecolor='#e5c07b', linewidth=1, zorder=4)
    ax.add_patch(feedline)

    # Bowtie Antenna (Apex at 30, 16, R = 10.16 mm, 80 deg sector)
    # Right Wing
    r_angles = np.linspace(-40, 40, 30) * np.pi / 180.0
    r_pts = [[30.0, 16.0]]
    for th in r_angles:
        r_pts.append([30.0 + 10.16 * np.cos(th), 16.0 + 10.16 * np.sin(th)])
    r_pts.append([30.0, 16.0])
    right_wing = patches.Polygon(r_pts, closed=True, facecolor='#f5a623', edgecolor='#ffffff', linewidth=1.5, zorder=5)
    ax.add_patch(right_wing)

    # Left Wing
    l_angles = np.linspace(140, 220, 30) * np.pi / 180.0
    l_pts = [[30.0, 16.0]]
    for th in l_angles:
        l_pts.append([30.0 + 10.16 * np.cos(th), 16.0 + 10.16 * np.sin(th)])
    l_pts.append([30.0, 16.0])
    left_wing = patches.Polygon(l_pts, closed=True, facecolor='#f5a623', edgecolor='#ffffff', linewidth=1.5, zorder=5)
    ax.add_patch(left_wing)

    ax.text(30.0, 16.0, "Apex Feed", color='#1e2227', fontsize=7, ha='center', va='center', fontweight='bold', zorder=6)
    ax.text(41.5, 16.0, "Right Wing\n(R=10.2mm)", color='#f5a623', fontsize=7.5, ha='left', va='center', fontweight='bold', zorder=6)
    ax.text(18.5, 16.0, "Left Wing\n(R=10.2mm)", color='#f5a623', fontsize=7.5, ha='right', va='center', fontweight='bold', zorder=6)

    # 3-pin Header J1 at (30, 28)
    for i, x in enumerate([27.46, 30.00, 32.54]):
        pin = patches.Circle((x, 28), 0.85, facecolor='#61afef', edgecolor='#ffffff', linewidth=1, zorder=7)
        ax.add_patch(pin)
        hole = patches.Circle((x, 28), 0.5, facecolor='#1e2227', zorder=8)
        ax.add_patch(hole)
    ax.text(27.46, 29.5, "Pin 1 (50R)", color='#61afef', fontsize=7, ha='center', zorder=9)
    ax.text(30.00, 29.5, "Pin 2 (Feed)", color='#ffffff', fontsize=7, ha='center', zorder=9)
    ax.text(32.54, 29.5, "Pin 3 (GND)", color='#e5c07b', fontsize=7, ha='center', zorder=9)

    # Resistor R1 (49.9 Ohm 0805) at (27.46, 24.50)
    r1 = patches.Rectangle((27.46 - 0.7, 24.50 - 1.0), 1.4, 2.0, facecolor='#98c379', edgecolor='#ffffff', linewidth=1, zorder=7)
    ax.add_patch(r1)
    ax.text(25.0, 24.5, "R1 (49.9Ω)", color='#98c379', fontsize=8, ha='right', va='center', fontweight='bold', zorder=9)

    # Cal Link R2 (0805) at (30.00, 37.00)
    r2 = patches.Rectangle((30.0 - 0.7, 37.0 - 1.0), 1.4, 2.0, facecolor='#c678dd', edgecolor='#ffffff', linewidth=1, zorder=7)
    ax.add_patch(r2)
    ax.text(32.5, 37.0, "R2 (0Ω Cal Link)", color='#c678dd', fontsize=8, ha='left', va='center', fontweight='bold', zorder=9)

    # SMA Connector J2 at (30, 48.4)
    sma = patches.Rectangle((30 - 3.5, 47.3), 7.0, 2.2, facecolor='#5c6370', edgecolor='#e5c07b', linewidth=1.5, zorder=7)
    ax.add_patch(sma)
    ax.text(30, 49.2, "SMA EDGE-LAUNCH (CAL PORT)", color='#e5c07b', fontsize=7, ha='center', fontweight='bold', zorder=9)

    ax.set_xlim(3, 57)
    ax.set_ylim(52, 3) # Inverted Y for PCB view
    ax.set_title("Board 3: 2.4 GHz Leggiero Bowtie Aperture Tag (Zero Vias)", color='#ffffff', fontsize=12, fontweight='bold', pad=12)
    ax.set_xlabel("Width X (mm) - Board Width: 50.0 mm", color='#abb2bf')
    ax.set_ylabel("Length Y (mm) - Board Length: 45.0 mm", color='#abb2bf')
    ax.tick_params(colors='#abb2bf')
    ax.grid(True, linestyle=':', alpha=0.3, color='#5c6370')

    # Annotations
    ax.text(8.5, 38, "SOLID F.Cu GND\n(Side Reflector)", color='#e5c07b', fontsize=8, ha='center', fontweight='bold', zorder=9)
    ax.text(48.5, 38, "SOLID F.Cu GND\n(Side Reflector)", color='#e5c07b', fontsize=8, ha='center', fontweight='bold', zorder=9)
    ax.text(30, 33.5, "CPWG 50-OHM FEED\n(W=1.85mm, g=0.575mm)", color='#d19a66', fontsize=7.5, ha='center', fontweight='bold', zorder=9)

    out_path = r".\ready_for_milling\board3_preview.png"
    plt.tight_layout()
    plt.savefig(out_path, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close()
    print("Generated Board 3 render:", out_path)

if __name__ == '__main__':
    render_board3()
