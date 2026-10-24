# Master Architectural Guide & Handoff Document
## Passive RF Backscatter Tag System — SDR Acquisition & Detection Software

**Target Audience:** New Agent / Engineering Team Member / Supervisor  
**Workspace Root:** `.`  
**Consolidated Engineering Directory:** `.`  
**System Date:** October 2026  

---

## 1. Executive Summary & Physical Hardware State

The physical hardware and antenna engineering milestones are **100% complete**:
- **3 Physical Tag Boards Milled & On Hand:**
  1. **Board 1 (2.44 GHz ISM IFA):** Based on TI SWRA117D, adapted for zero-via single-sided CNC milling on 1.6 mm FR-4. Feedline is a 50 $\Omega$ Grounded Coplanar Waveguide (CPWG, $W=1.85\,\text{mm}, G=0.50\,\text{mm}$).
  2. **Board 2 (868/915 MHz Sub-1GHz Planar Meander):** Single-sided $L_{\text{eff}} = 73.5\,\text{mm}$ meander line replacing the legacy 19-via helical benchmark.
  3. **Board 3 (2.44 GHz Leggiero Bowtie Aperture):** Replicated and reverse-engineered from the published Leggiero paper and Altium design ($R=10.16\,\text{mm}, 80^\circ$ sector, $36 \times 15.5\,\text{mm}$ ground cavity, unified top ground counterpoise loop, 0 vias).
  - All CAM packages (1:1 isolation DXF, RS-274X Gerbers, Excellon drills) reside in [`ant test/01_pcb_design/ready_for_milling/`](01_pcb_design/ready_for_milling/).
  - Each board features dual pads: an 0805 footprint for a $50\,\Omega$ termination resistor and parallel pin header pads for a shorting jumper (0 $\Omega$ state).
- **Physical Test Bench Hardware:**
  - **SDR:** National Instruments NI USRP-2900 (Ettus B200 clone, USB 3.0, Serial: `30BF6B0`). Verified streaming at $\sim 2.0\,\text{MS/s}$.
  - **Host Environment:** Windows 10/11, Python environment via Radioconda (`%USERPROFILE%\radioconda\python.exe`, includes UHD 4.8.0), and **MATLAB R2025a** (`C:\Program Files\MATLAB\R2025a\bin\matlab.exe`).

---

## 2. Core Physics & Detection Objective

The fundamental RF physics task is measuring the **differential radar cross section ($\Delta \sigma$)** between two antenna load states:
$$\Delta \sigma = \frac{\lambda^2 G^2}{4\pi} |\Gamma_{\text{reflect}} - \Gamma_{\text{absorb}}|^2$$

Where:
- **State 1 (Absorbing / Quiescent):** Load resistor $Z_L = 50\,\Omega \implies \Gamma \approx 0$. Minimal RF reflection.
- **State 2 (Reflecting / Modulated):** Jumper shorted $Z_L = 0\,\Omega \implies \Gamma \approx -1$. Strong RF reflection.
- **Contrast Goal:** Contrast delta $\Delta P_{\text{rx}} = 10 \log_{10}(P_{\text{reflect}} / P_{\text{absorb}}) \ge 3\text{ to }12\,\text{dB}$, and complex vector distance $\Delta |V_{\text{rx}}| = |\bar{V}_{\text{reflect}} - \bar{V}_{\text{absorb}}| > 0$.

### Two Operating Modes:
1. **Mode 1 (Bistatic Continuous Wave - CW):**
   - USRP `TX/RX` port transmits a clean CW unmodulated tone (e.g., $+10\,\text{dBm}$ at 2.44 GHz or 868 MHz).
   - USRP `RX2` port receives the reflected step response. When the user shorts the jumper, a step transition occurs in $P_{\text{rx}}(t)$ and the complex constellation moves between two distinct centroids.
2. **Mode 2 (Ambient Wi-Fi Carrier):**
   - USRP transmits nothing (passive receiver).
   - `RX2` tunes to Wi-Fi Channel 6 ($2.437\,\text{GHz}$) or Channel 1 ($2.412\,\text{GHz}$) and measures beacon packet RSSI step delta or energy variance between open/short.

---

## 3. Root Cause Analysis: Why the Previous Python Desktop GUI Failed

1. **Environment Conflicts in Radioconda:**
   - Radioconda ships with mixed Qt5 and Qt6 C++ runtime libraries and an empty 0-byte `Qt5Core.dll`, causing Windows to raise fatal `0xC0000409` aborts whenever PyQt5/PyQt6 initializes `qwindows.dll`.
2. **Threading & Windows Message Queue Deadlocks:**
   - High-throughput SDR streaming ($2\,\text{MS/s} = 16\,\text{MB/s}$ over USB 3.0) requires real-time buffer consumption.
   - Coupling UHD buffer consumption, decimation, FFT calculation, and Matplotlib canvas redraws within a Python GUI event loop leads to thread starvation, buffer overflows (`UUUUU` under-runs), and sluggish/frozen windows.
3. **Impedance Mismatch with Lab Workflow:**
   - A single monolithic desktop GUI tries to do too many things simultaneously (driver management, hardware probing, live graphing, export, DSP thresholding). When one part fails, the entire tool crashes.

---

## 4. Alternative Architectural Paths (Ranked by Robustness)

### Option A: Native GNU Radio Companion (GRC) Flowgraph (⭐ Recommended for Live RF Exploration)
- **Why it excels:** Radioconda already includes GNU Radio 3.10 and UHD. GNU Radio runs its signal processing pipeline entirely in compiled C++ threads. It includes pre-built, hardware-accelerated GUI sinks (`QT GUI Time Sink`, `QT GUI Frequency Sink`, `QT GUI Constellation Sink`) that run at 60 FPS without buffer drops.
- **Implementation:** A single `.grc` flowgraph with:
  - `UHD: USRP Sink` (CW Tone generator at $f_c$)
  - `UHD: USRP Source` (RX2 capture at $f_c$)
  - `Complex to Mag^2` $\to$ `Moving Average` $\to$ `QT GUI Time Sink` (shows live step response when jumper is shorted).
  - `QT GUI Constellation Sink` (shows I/Q phase trajectory).
- **Effort:** 15 minutes to assemble and test. Zero Python GUI coding.

### Option B: Pure MATLAB App Designer / Live Script (⭐ Recommended for Academic Publication)
- **Why it excels:** MATLAB R2025a is already installed and verified on this machine. MATLAB has native USRP hardware support (`comm.SDRuReceiver`, `comm.SDRuTransmitter`), rock-solid graphics, built-in Welch PSD, and produces publication-ready vector figures directly for your supervisor.
- **Implementation:** A clean MATLAB Live Script (`backscatter_test_suite.mlx`) or App Designer GUI that connects to the USRP, streams 5 seconds of data while you toggle the jumper, detects the step edge, and exports figures to PDF/EPS.

### Option C: Decoupled Web-Based Dashboard (Streamlit / Dash / FastAPI + Plotly)
- **Why it excels:** Completely bypasses Windows desktop GUI DLL issues. The Python backend streams USRP samples and serves metrics over a local WebSocket to a browser window (`http://localhost:8501`).
- **Implementation:** Streamlit or Dash interface with a "Record 5s Capture" button and interactive Plotly strip charts.

### Option D: Fast Headless Python Streamer + Auto-Triggered MATLAB Plot
- **Why it excels:** The simplest, most failure-proof software design.
- **Workflow:**
  1. A small Python CLI script (`python record_backscatter.py --mode ifa --duration 10`) streams from the USRP over USB 3.0, prints live console status:
     ```text
     [STATE] Absorbing (50 Ohm) -> Prx = -42.1 dBFS
     [TRIGGER] Detected Short!   -> Prx = -31.4 dBFS (Delta P = +10.7 dB)
     ```
  2. Automatically saves `capture_latest.mat`.
  3. Launches MATLAB to render and save the final figures.

---

## 5. Directory Map of Current Clean Files

```text
.\
├── 01_pcb_design/
│   ├── ready_for_milling/
│   │   ├── Board1_2.4GHz_IFA_Tag/            # Milling DXF, Gerbers, NC drill for Board 1
│   │   ├── Board2_Sub1GHz_Planar_Tag/        # Milling DXF, Gerbers, NC drill for Board 2
│   │   ├── Board3_2.4GHz_Leggiero_Bowtie_Tag/# Milling DXF, Gerbers, NC drill for Board 3
│   │   └── Archive_END_Platform_SWRA416_Helical/
│   └── kicad_projects/                       # Editable KiCad 9 schematics & PCB files
├── 02_simulation/
│   ├── antenna_models.py                     # Antenna input impedance & S11 models
│   ├── calc_feedline_impedance.py            # CPWG 50-Ohm solver
│   ├── rcs_simulation.py                     # Harrington differential RCS solver
│   └── output/                               # Simulated S11 & RCS PNG figures
├── 03_sdr_software/
│   ├── backscatter_gui_app.py                # Standalone Tkinter GUI
│   ├── sdr_worker.py                         # Multithreaded USRP streaming worker
│   ├── mock_usrp.py                          # Hardware fallback simulator
│   ├── backscatter_metrics.py                # Delta P & Delta V DSP math
│   └── output/snapshots/                     # Saved .mat, .npz, and .csv files
├── 04_testing/
│   ├── test_usrp_hardware_streaming.py       # VERIFIED: Live USRP-2900 USB 3.0 streaming probe
│   ├── test_gui_native_app.py                # Headless GUI lifecycle test
│   └── test_kicad_hardware.py                # KiCad hardware verification
└── 05_reports/
    ├── backscatter_design_and_simulation_report.md # Complete supervisor report
    ├── Backscatter_Tag_Simulation_Report.pdf # Formal PDF report
    └── figures/                              # 14 high-resolution 300 DPI figures
```

---

## 6. Turnkey Copy-Paste Prompt for the Next Chat

*Copy and paste the exact block below into a new chat session to continue this project seamlessly without re-explaining anything:*

```markdown
You are an expert RF and Software-Defined Radio (SDR) engineer assisting with a passive RF backscatter tag experimental validation project.

### Project Context & Status
1. **Hardware State (Completed):**
   We have designed, simulated, and CNC-milled 3 physical single-sided 1.6 mm FR-4 backscatter tag prototypes (zero vias):
   - **Board 1:** 2.44 GHz IFA (TI SWRA117D CPWG adaptation, 50 Ohm match).
   - **Board 2:** 868/915 MHz Sub-1GHz Planar Meander (73.5 mm trace, single-sided).
   - **Board 3:** 2.44 GHz Leggiero Bowtie Aperture with ground cavity loop (reverse-engineered from the Leggiero paper).
   Each board has dual SMD pads: a 50 Ohm resistor (absorbing state, Gamma ≈ 0) and a parallel 2-pin header for a shorting jumper (reflecting state, Gamma ≈ -1). The boards are physically soldered and in hand.

2. **Test Equipment & Environment:**
   - **SDR:** NI USRP-2900 (Ettus B200 clone, USB 3.0, Serial: 30BF6B0). Verified working with UHD 4.8.0.
   - **Host Software:** Windows 10/11, Radioconda Python 3.11 (`%USERPROFILE%\radioconda\python.exe`), and MATLAB R2025a (`C:\Program Files\MATLAB\R2025a\bin\matlab.exe`).
   - **Working Directory:** `.`
     - CAM & Milling files: `01_pcb_design/ready_for_milling/`
     - Simulations: `02_simulation/`
     - SDR Code: `03_sdr_software/`
     - Hardware & Unit Tests: `04_testing/`
     - Academic Reports: `05_reports/`

3. **Current Problem & What We Need:**
   We tried building a standalone Python desktop GUI (PyQt/Tkinter), but desktop Python GUIs have been prone to environment DLL conflicts and threading friction with high-rate SDR USB streaming.
   We want to abandon fragile desktop GUI frameworks in favor of a clean, robust, and dependable architecture to detect and measure backscatter switching contrast (Delta P_rx and Delta |V_rx|).

4. **Your Task:**
   Help me implement the best alternative approach:
   - **Option A (GNU Radio Companion):** Provide a ready-to-run `.grc` flowgraph for Radioconda's GNU Radio 3.10 that transmits a CW tone on TX/RX and plots live reflected power and I/Q constellation on RX2.
   - **Option B (Pure MATLAB):** Provide a clean MATLAB script/app utilizing MATLAB R2025a to stream USRP-2900 samples, perform step detection when the jumper is toggled, and plot publication figures.
   - **Option C (Simple Headless Python CLI Streamer):** A lightweight Python streaming script that streams USRP samples, prints state transitions to console in real time, and auto-saves `.mat` captures for MATLAB.

Please review the existing workspace in `.` and recommend the cleanest, most immediate way to get live backscatter measurements on my hardware today.
```
