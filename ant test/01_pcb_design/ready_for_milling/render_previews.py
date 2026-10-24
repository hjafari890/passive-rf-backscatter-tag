"""Generates clean PNG preview renders of Board 1 (2.4 GHz IFA) and Board 2 (Sub-1GHz Planar Meander)."""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

def render_board1():
    fig, ax = plt.subplots(figsize=(8, 7), dpi=150)
    ax.set_facecolor('#1e2227')
    fig.patch.set_facecolor('#141619')
    
    # Board outline (45 x 35 mm, X in [10, 55], Y in [10, 45])
    board = patches.Rectangle((10, 10), 45, 35, linewidth=2, edgecolor='#e5c07b', facecolor='#282c34', zorder=1)
    ax.add_patch(board)
    
    # Antenna Keepout outline (X in [10, 55], Y in [10, 18])
    keepout = patches.Rectangle((10, 10), 45, 8, linewidth=1, linestyle='--', edgecolor='#e06c75', facecolor='#2c313a', alpha=0.5, zorder=2)
    ax.add_patch(keepout)
    ax.text(32.5, 11.2, "ANTENNA KEEPOUT (BARE FR-4, NO GND)", color='#e06c75', fontsize=8, ha='center', fontweight='bold', zorder=5)
    
    # Ground Planes on F.Cu
    # Left Ground
    left_gnd = patches.Polygon([[10.5, 18], [28.5, 18], [28.5, 19.2], [26, 19.2], [26, 24.5], [28.5, 24.5], [28.5, 44.5], [10.5, 44.5]], 
                               closed=True, facecolor='#b58900', edgecolor='#d19a66', alpha=0.85, zorder=3)
    ax.add_patch(left_gnd)
    
    # Right Ground
    right_gnd = patches.Polygon([[31.5, 18], [54.5, 18], [54.5, 44.5], [31.5, 44.5]], 
                                closed=True, facecolor='#b58900', edgecolor='#d19a66', alpha=0.85, zorder=3)
    ax.add_patch(right_gnd)
    
    # 50 Ohm Feedline (X=30, W=1.85 mm, Y from 18 to 43.4)
    feedline = patches.Rectangle((30 - 1.85/2, 18), 1.85, 25.4, facecolor='#d19a66', edgecolor='#e5c07b', linewidth=1, zorder=4)
    ax.add_patch(feedline)
    
    # IFA Radiator (SWRA117D on F.Cu)
    # Radiator arm at top
    arm = patches.Rectangle((27.45, 12.85), 14.4, 1.0, facecolor='#d19a66', edgecolor='#e5c07b', zorder=4)
    ax.add_patch(arm)
    # Shorting stub to ground at X=27.9
    stub = patches.Rectangle((27.45, 12.85), 0.9, 5.15, facecolor='#d19a66', edgecolor='#e5c07b', zorder=4)
    ax.add_patch(stub)
    
    # 3-pin Header J1 at (30, 23)
    for i, x in enumerate([27.46, 30.00, 32.54]):
        pin = patches.Circle((x, 23), 0.85, facecolor='#61afef', edgecolor='#ffffff', linewidth=1, zorder=6)
        ax.add_patch(pin)
        hole = patches.Circle((x, 23), 0.5, facecolor='#1e2227', zorder=7)
        ax.add_patch(hole)
    ax.text(27.46, 24.5, "Pin 1 (50R)", color='#61afef', fontsize=7, ha='center', zorder=8)
    ax.text(30.00, 24.5, "Pin 2 (Feed)", color='#ffffff', fontsize=7, ha='center', zorder=8)
    ax.text(32.54, 24.5, "Pin 3 (GND)", color='#e5c07b', fontsize=7, ha='center', zorder=8)
    
    # Resistor R1 (49.9 Ohm 0805)
    r1 = patches.Rectangle((27.46 - 0.7, 19.5 - 1.0), 1.4, 2.0, facecolor='#98c379', edgecolor='#ffffff', linewidth=1, zorder=6)
    ax.add_patch(r1)
    ax.text(25.0, 19.5, "R1 (49.9Ω)", color='#98c379', fontsize=8, ha='right', va='center', fontweight='bold', zorder=8)
    
    # Cal Link R2 (0805)
    r2 = patches.Rectangle((30.0 - 0.7, 32.0 - 1.0), 1.4, 2.0, facecolor='#c678dd', edgecolor='#ffffff', linewidth=1, zorder=6)
    ax.add_patch(r2)
    ax.text(32.5, 32.0, "R2 (0Ω Cal Link)", color='#c678dd', fontsize=8, ha='left', va='center', fontweight='bold', zorder=8)
    
    # SMA Connector J2 at (30, 43.4)
    sma = patches.Rectangle((30 - 3.5, 42.3), 7.0, 2.2, facecolor='#5c6370', edgecolor='#e5c07b', linewidth=1.5, zorder=6)
    ax.add_patch(sma)
    ax.text(30, 44.2, "SMA EDGE-LAUNCH (CAL PORT)", color='#e5c07b', fontsize=7, ha='center', fontweight='bold', zorder=8)
    
    ax.set_xlim(8, 57)
    ax.set_ylim(47, 8) # Inverted Y for PCB top view
    ax.set_title("Board 1: 2.44 GHz Wi-Fi / ISM Tag (TI SWRA117D IFA, Zero Vias)", color='#ffffff', fontsize=12, fontweight='bold', pad=12)
    ax.set_xlabel("Width X (mm) - Board Width: 45.0 mm", color='#abb2bf')
    ax.set_ylabel("Length Y (mm) - Board Length: 35.0 mm", color='#abb2bf')
    ax.tick_params(colors='#abb2bf')
    ax.grid(True, linestyle=':', alpha=0.3, color='#5c6370')
    
    # Annotations
    ax.text(19, 35, "SOLID F.Cu GND\n(26.5 x 18 mm)", color='#e5c07b', fontsize=9, ha='center', fontweight='bold', zorder=8)
    ax.text(43, 35, "SOLID F.Cu GND\n(26.5 x 23 mm)", color='#e5c07b', fontsize=9, ha='center', fontweight='bold', zorder=8)
    ax.text(30, 27.5, "W=1.85mm, g=0.575mm\nCPWG Z0 = 49.0 Ω", color='#d19a66', fontsize=8, ha='center', fontweight='bold', zorder=8)
    
    out_path = r".\ready_for_milling\board1_preview.png"
    plt.tight_layout()
    plt.savefig(out_path, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close()
    print("Generated:", out_path)

def render_board2():
    fig, ax = plt.subplots(figsize=(8, 7), dpi=150)
    ax.set_facecolor('#1e2227')
    fig.patch.set_facecolor('#141619')
    
    # Board outline (45 x 42 mm, X in [10, 55], Y in [3, 45])
    board = patches.Rectangle((10, 3), 45, 42, linewidth=2, edgecolor='#e5c07b', facecolor='#282c34', zorder=1)
    ax.add_patch(board)
    
    # Antenna Keepout outline (X in [10, 55], Y in [3, 18])
    keepout = patches.Rectangle((10, 3), 45, 15, linewidth=1, linestyle='--', edgecolor='#e06c75', facecolor='#2c313a', alpha=0.5, zorder=2)
    ax.add_patch(keepout)
    ax.text(32.5, 4.2, "ANTENNA KEEPOUT (BARE FR-4, ZERO VIAS)", color='#e06c75', fontsize=8, ha='center', fontweight='bold', zorder=5)
    
    # Ground Planes on F.Cu
    left_gnd = patches.Polygon([[10.5, 18], [28.5, 18], [28.5, 19.2], [26, 19.2], [26, 24.5], [28.5, 24.5], [28.5, 44.5], [10.5, 44.5]], 
                               closed=True, facecolor='#b58900', edgecolor='#d19a66', alpha=0.85, zorder=3)
    ax.add_patch(left_gnd)
    
    right_gnd = patches.Polygon([[31.5, 18], [54.5, 18], [54.5, 44.5], [31.5, 44.5]], 
                                closed=True, facecolor='#b58900', edgecolor='#d19a66', alpha=0.85, zorder=3)
    ax.add_patch(right_gnd)
    
    # 50 Ohm Feedline
    feedline = patches.Rectangle((30 - 1.85/2, 18), 1.85, 25.4, facecolor='#d19a66', edgecolor='#e5c07b', linewidth=1, zorder=4)
    ax.add_patch(feedline)
    
    # Planar Meander Tracks (100% on F.Cu, W=1.0 mm)
    meander_pts = [
        [30, 18], [30, 5], [46, 5], [46, 7.5], [33, 7.5], [33, 10], [46, 10], [46, 12.5], [35, 12.5]
    ]
    xs, ys = zip(*meander_pts)
    ax.plot(xs, ys, color='#e5c07b', linewidth=4.0, solid_capstyle='round', zorder=5)
    ax.text(47, 8.75, "Planar Meander Monopole\n(L=73.5 mm, W=1.0 mm)", color='#e5c07b', fontsize=8, ha='left', va='center', fontweight='bold', zorder=8)
    
    # 3-pin Header J1 at (30, 23)
    for i, x in enumerate([27.46, 30.00, 32.54]):
        pin = patches.Circle((x, 23), 0.85, facecolor='#61afef', edgecolor='#ffffff', linewidth=1, zorder=6)
        ax.add_patch(pin)
        hole = patches.Circle((x, 23), 0.5, facecolor='#1e2227', zorder=7)
        ax.add_patch(hole)
    ax.text(27.46, 24.5, "Pin 1 (50R)", color='#61afef', fontsize=7, ha='center', zorder=8)
    ax.text(30.00, 24.5, "Pin 2 (Feed)", color='#ffffff', fontsize=7, ha='center', zorder=8)
    ax.text(32.54, 24.5, "Pin 3 (GND)", color='#e5c07b', fontsize=7, ha='center', zorder=8)
    
    # Resistor R1
    r1 = patches.Rectangle((27.46 - 0.7, 19.5 - 1.0), 1.4, 2.0, facecolor='#98c379', edgecolor='#ffffff', linewidth=1, zorder=6)
    ax.add_patch(r1)
    ax.text(25.0, 19.5, "R1 (49.9Ω)", color='#98c379', fontsize=8, ha='right', va='center', fontweight='bold', zorder=8)
    
    # Cal Link R2
    r2 = patches.Rectangle((30.0 - 0.7, 32.0 - 1.0), 1.4, 2.0, facecolor='#c678dd', edgecolor='#ffffff', linewidth=1, zorder=6)
    ax.add_patch(r2)
    ax.text(32.5, 32.0, "R2 (0Ω Cal Link)", color='#c678dd', fontsize=8, ha='left', va='center', fontweight='bold', zorder=8)
    
    # SMA Connector J2
    sma = patches.Rectangle((30 - 3.5, 42.3), 7.0, 2.2, facecolor='#5c6370', edgecolor='#e5c07b', linewidth=1.5, zorder=6)
    ax.add_patch(sma)
    ax.text(30, 44.2, "SMA EDGE-LAUNCH (CAL PORT)", color='#e5c07b', fontsize=7, ha='center', fontweight='bold', zorder=8)
    
    ax.set_xlim(8, 57)
    ax.set_ylim(47, 1)
    ax.set_title("Board 2: Sub-1GHz (868/915 MHz) Planar Meander Tag (Zero Vias)", color='#ffffff', fontsize=12, fontweight='bold', pad=12)
    ax.set_xlabel("Width X (mm) - Board Width: 45.0 mm", color='#abb2bf')
    ax.set_ylabel("Length Y (mm) - Board Length: 42.0 mm", color='#abb2bf')
    ax.tick_params(colors='#abb2bf')
    ax.grid(True, linestyle=':', alpha=0.3, color='#5c6370')
    
    out_path = r".\ready_for_milling\board2_preview.png"
    plt.tight_layout()
    plt.savefig(out_path, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close()
    print("Generated:", out_path)

if __name__ == '__main__':
    render_board1()
    render_board2()
