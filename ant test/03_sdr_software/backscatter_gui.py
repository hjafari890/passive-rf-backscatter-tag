"""Real-Time PyQt Backscatter Tag Acquisition & Detection Suite.

Scientific dashboard for real-time validation of passive backscatter tag antennas
using the NI USRP-2900 / B200 SDR. Features 3 dedicated detection modes for:
- Mode 1: 2.44 GHz Wi-Fi IFA Tag (TI SWRA117D)
- Mode 2: Sub-1GHz Planar Meander Tag (868 / 915 MHz)
- Mode 3: 2.44 GHz Leggiero Bowtie Tag (Cavity-Backed Aperture)

Supports live streaming, software carrier leakage cancellation, real-time
time-domain strip charts, I/Q constellation phase planes, FFT power spectra,
and instant export of measurement datasets to MATLAB (.mat), NumPy (.npz),
and publication-quality CSV/plots.
"""

from __future__ import annotations

import os
import sys

# Set high-DPI scaling via environment variable before any Qt/pyqtgraph imports
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

import time
from typing import Optional

import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QFont, QIcon
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

# Import local worker
try:
    from .sdr_worker import SDRWorker
except ImportError:
    from sdr_worker import SDRWorker

# Set pyqtgraph global styling
pg.setConfigOption("background", "#131417")
pg.setConfigOption("foreground", "#d1d5db")
pg.setConfigOption("antialias", True)


class BackscatterGUI(QMainWindow):
    """Main Application Window for Backscatter Tag Analysis & Detection."""

    def __init__(self, force_mock: bool = False) -> None:
        super().__init__()
        self.force_mock = force_mock
        self.worker: Optional[SDRWorker] = None

        # Mode definitions
        self.modes = {
            "mode1": {
                "name": "Mode 1: 2.44 GHz Wi-Fi IFA Tag",
                "tag_name": "TI SWRA117D Inverted-F",
                "center_freq": 2440.0e6,
                "sample_rate": 2.0e6,
                "rx_gain": 45.0,
                "tx_gain": 60.0,
                "carrier_mode": "cw",
                "s11_theory": "-24.4 dB",
                "rcs_theory": "-26.5 dBsm",
                "gain_theory": "+2.1 dBi",
                "description": "50Ω CPWG feed, ground counterpoise counter-clutter optimization.",
            },
            "mode2": {
                "name": "Mode 2: Sub-1GHz Planar Meander",
                "tag_name": "Single-Sided Meander Monopole",
                "center_freq": 868.0e6,
                "sample_rate": 1.0e6,
                "rx_gain": 40.0,
                "tx_gain": 55.0,
                "carrier_mode": "cw",
                "s11_theory": "-19.2 dB",
                "rcs_theory": "-21.8 dBsm",
                "gain_theory": "+0.8 dBi",
                "description": "73.5 mm planar trace replacing 19-via helical for zero-via CNC milling.",
            },
            "mode3": {
                "name": "Mode 3: 2.44 GHz Leggiero Bowtie",
                "tag_name": "Cavity-Backed Bowtie Aperture",
                "center_freq": 2437.0e6,
                "sample_rate": 5.0e6,
                "rx_gain": 55.0,
                "tx_gain": 0.0,
                "carrier_mode": "wifi",
                "s11_theory": "-18.6 dB (Wideband)",
                "rcs_theory": "-22.5 dBsm",
                "gain_theory": "+4.2 dBi",
                "description": "R=10.16mm, 80° circular sector, 36x15.5mm cavity with top ground border.",
            },
        }
        self.current_mode_key = "mode1"

        self.init_ui()
        self.apply_mode_config("mode1")

    def init_ui(self) -> None:
        """Construct the UI layout and pyqtgraph widgets."""
        self.setWindowTitle("Backscatter Tag SDR Detection & Analysis Suite — NI USRP-2900")
        self.resize(1380, 880)
        self.setMinimumSize(1024, 700)

        # Apply dark modern QSS theme
        self.setStyleSheet("""
            QMainWindow {
                background-color: #18191c;
                color: #e2e8f0;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QGroupBox {
                border: 1px solid #334155;
                border-radius: 6px;
                margin-top: 10px;
                font-weight: bold;
                font-size: 12px;
                color: #94a3b8;
                padding-top: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QLabel {
                color: #cbd5e1;
                font-size: 11px;
            }
            QPushButton {
                background-color: #334155;
                color: #f8fafc;
                border: 1px solid #475569;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: 600;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #475569;
                border-color: #64748b;
            }
            QPushButton:pressed {
                background-color: #1e293b;
            }
            QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {
                background-color: #0f172a;
                color: #f1f5f9;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
            }
            QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                border: 1px solid #00e5ff;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #1e293b;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #00e5ff;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                border: 1px solid #00e5ff;
                width: 14px;
                margin-top: -4px;
                margin-bottom: -4px;
                border-radius: 7px;
            }
            QStatusBar {
                background-color: #0f172a;
                color: #94a3b8;
                border-top: 1px solid #1e293b;
            }
        """)

        # Central layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 8, 10, 8)
        main_layout.setSpacing(8)

        # 1. Top Header Bar (Mode presets + Hardware status)
        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)

        title_label = QLabel("ANTENNA BACKSCATTER SDR ANALYZER")
        title_label.setFont(QFont("Segoe UI", 13, QFont.Bold))
        title_label.setStyleSheet("color: #00e5ff; letter-spacing: 1px;")
        header_layout.addWidget(title_label)

        header_layout.addSpacing(15)

        # Preset mode buttons
        self.btn_mode1 = QPushButton("Mode 1: 2.44GHz IFA (SWRA117D)")
        self.btn_mode2 = QPushButton("Mode 2: Sub-1GHz Meander (868/915M)")
        self.btn_mode3 = QPushButton("Mode 3: 2.44GHz Leggiero Bowtie")

        for btn in [self.btn_mode1, self.btn_mode2, self.btn_mode3]:
            btn.setCheckable(True)
            btn.setFixedHeight(30)
            header_layout.addWidget(btn)

        self.btn_mode1.clicked.connect(lambda: self.apply_mode_config("mode1"))
        self.btn_mode2.clicked.connect(lambda: self.apply_mode_config("mode2"))
        self.btn_mode3.clicked.connect(lambda: self.apply_mode_config("mode3"))

        header_layout.addStretch()

        # Hardware status indicator pill
        self.hw_status_label = QLabel("[*] Checking SDR Hardware...")
        self.hw_status_label.setStyleSheet(
            "background-color: #1e293b; color: #ffab00; border: 1px solid #d97706; "
            "border-radius: 12px; padding: 4px 12px; font-weight: bold; font-size: 11px;"
        )
        header_layout.addWidget(self.hw_status_label)

        main_layout.addLayout(header_layout)

        # 2. Splitter: Left Controls & HUD, Right Real-Time Visualizations
        body_splitter = QSplitter(Qt.Horizontal)
        body_splitter.setHandleWidth(4)

        # --- LEFT SIDEBAR (Controls & Metric HUD) ---
        sidebar_widget = QWidget()
        sidebar_layout = QVBoxLayout(sidebar_widget)
        sidebar_layout.setContentsMargins(0, 0, 4, 0)
        sidebar_layout.setSpacing(10)
        sidebar_widget.setMaximumWidth(360)
        sidebar_widget.setMinimumWidth(320)

        # Box A: Antenna Specifications
        spec_box = QGroupBox("Target Antenna Specifications")
        spec_layout = QGridLayout(spec_box)
        spec_layout.setVerticalSpacing(4)
        spec_layout.setHorizontalSpacing(8)

        spec_layout.addWidget(QLabel("Topology:"), 0, 0)
        self.lbl_spec_name = QLabel("TI SWRA117D IFA")
        self.lbl_spec_name.setStyleSheet("font-weight: bold; color: #38bdf8;")
        spec_layout.addWidget(self.lbl_spec_name, 0, 1)

        spec_layout.addWidget(QLabel("Simulated S11:"), 1, 0)
        self.lbl_spec_s11 = QLabel("-24.4 dB")
        spec_layout.addWidget(self.lbl_spec_s11, 1, 1)

        spec_layout.addWidget(QLabel("Differential RCS:"), 2, 0)
        self.lbl_spec_rcs = QLabel("-26.5 dBsm")
        spec_layout.addWidget(self.lbl_spec_rcs, 2, 1)

        spec_layout.addWidget(QLabel("Antenna Gain:"), 3, 0)
        self.lbl_spec_gain = QLabel("+2.1 dBi")
        spec_layout.addWidget(self.lbl_spec_gain, 3, 1)

        self.lbl_spec_desc = QLabel("Single-sided CPWG feed.")
        self.lbl_spec_desc.setWordWrap(True)
        self.lbl_spec_desc.setStyleSheet("color: #64748b; font-size: 10px; font-style: italic;")
        spec_layout.addWidget(self.lbl_spec_desc, 4, 0, 1, 2)

        sidebar_layout.addWidget(spec_box)

        # Box B: RF & SDR Frontend Controls
        rf_box = QGroupBox("RF Frontend Parameters")
        rf_layout = QGridLayout(rf_box)
        rf_layout.setVerticalSpacing(6)
        rf_layout.setHorizontalSpacing(8)

        rf_layout.addWidget(QLabel("Center Freq (MHz):"), 0, 0)
        self.spin_freq = QDoubleSpinBox()
        self.spin_freq.setRange(50.0, 6000.0)
        self.spin_freq.setValue(2440.0)
        self.spin_freq.setDecimals(2)
        self.spin_freq.setSingleStep(1.0)
        rf_layout.addWidget(self.spin_freq, 0, 1)

        rf_layout.addWidget(QLabel("Sample Rate:"), 1, 0)
        self.combo_rate = QComboBox()
        self.combo_rate.addItems(["1.0 MS/s", "2.0 MS/s", "5.0 MS/s", "10.0 MS/s"])
        self.combo_rate.setCurrentIndex(1)
        rf_layout.addWidget(self.combo_rate, 1, 1)

        rf_layout.addWidget(QLabel("Carrier Mode:"), 2, 0)
        self.combo_carrier = QComboBox()
        self.combo_carrier.addItems(["Active CW (TX/RX + RX2)", "Passive Ambient Wi-Fi (RX2)"])
        rf_layout.addWidget(self.combo_carrier, 2, 1)

        # RX Gain Slider
        rf_layout.addWidget(QLabel("RX Gain (0-76 dB):"), 3, 0)
        rx_gain_row = QHBoxLayout()
        self.slider_rx_gain = QSlider(Qt.Horizontal)
        self.slider_rx_gain.setRange(0, 76)
        self.slider_rx_gain.setValue(45)
        self.lbl_rx_gain_val = QLabel("45 dB")
        self.lbl_rx_gain_val.setFixedWidth(40)
        rx_gain_row.addWidget(self.slider_rx_gain)
        rx_gain_row.addWidget(self.lbl_rx_gain_val)
        rf_layout.addLayout(rx_gain_row, 3, 1)
        self.slider_rx_gain.valueChanged.connect(
            lambda v: self.lbl_rx_gain_val.setText(f"{v} dB")
        )

        # TX Gain Slider
        rf_layout.addWidget(QLabel("TX Gain (0-89 dB):"), 4, 0)
        tx_gain_row = QHBoxLayout()
        self.slider_tx_gain = QSlider(Qt.Horizontal)
        self.slider_tx_gain.setRange(0, 89)
        self.slider_tx_gain.setValue(60)
        self.lbl_tx_gain_val = QLabel("60 dB")
        self.lbl_tx_gain_val.setFixedWidth(40)
        tx_gain_row.addWidget(self.slider_tx_gain)
        tx_gain_row.addWidget(self.lbl_tx_gain_val)
        rf_layout.addLayout(tx_gain_row, 4, 1)
        self.slider_tx_gain.valueChanged.connect(
            lambda v: self.lbl_tx_gain_val.setText(f"{v} dB")
        )

        sidebar_layout.addWidget(rf_box)

        # Box C: Action Buttons
        act_box = QGroupBox("Stream & Calibration Controls")
        act_layout = QVBoxLayout(act_box)
        act_layout.setSpacing(6)

        self.btn_toggle_stream = QPushButton("▶  START ACQUISITION")
        self.btn_toggle_stream.setFixedHeight(34)
        self.btn_toggle_stream.setStyleSheet(
            "background-color: #0284c7; color: white; font-weight: bold; font-size: 12px;"
        )
        self.btn_toggle_stream.clicked.connect(self.toggle_streaming)
        act_layout.addWidget(self.btn_toggle_stream)

        self.btn_autozero = QPushButton("⌖  AUTO-ZERO BASELINE (LEAKAGE CANCELLATION)")
        self.btn_autozero.setStyleSheet(
            "background-color: #334155; color: #38bdf8; border: 1px solid #0284c7;"
        )
        self.btn_autozero.clicked.connect(self.trigger_autozero)
        act_layout.addWidget(self.btn_autozero)

        self.btn_export = QPushButton("💾  EXPORT SNAPSHOT (.MAT / .NPZ / CSV)")
        self.btn_export.setStyleSheet(
            "background-color: #0f766e; color: #5eead4; border: 1px solid #14b8a6; font-weight: bold;"
        )
        self.btn_export.clicked.connect(self.trigger_snapshot_export)
        act_layout.addWidget(self.btn_export)

        sidebar_layout.addWidget(act_box)

        # Box D: Metric HUD & Classifier
        hud_box = QGroupBox("Live Backscatter Modulation Metrics")
        hud_layout = QVBoxLayout(hud_box)
        hud_layout.setSpacing(8)

        # Big State Indicator Card
        self.card_state = QLabel("STATE 1: ABSORBING (50 Ω)")
        self.card_state.setAlignment(Qt.AlignCenter)
        self.card_state.setFixedHeight(36)
        self.card_state.setStyleSheet(
            "background-color: #0f172a; color: #38bdf8; border: 2px solid #0284c7; "
            "border-radius: 6px; font-weight: bold; font-size: 13px;"
        )
        hud_layout.addWidget(self.card_state)

        # Metric grid
        grid_hud = QGridLayout()
        grid_hud.setVerticalSpacing(4)
        grid_hud.setHorizontalSpacing(8)

        grid_hud.addWidget(QLabel("Differential Power (ΔP):"), 0, 0)
        self.lbl_metric_delta_p = QLabel("+0.00 dB")
        self.lbl_metric_delta_p.setStyleSheet("font-weight: bold; font-size: 12px; color: #4ade80;")
        grid_hud.addWidget(self.lbl_metric_delta_p, 0, 1)

        grid_hud.addWidget(QLabel("Vector Distance (Δ|V|):"), 1, 0)
        self.lbl_metric_delta_v = QLabel("0.0000")
        self.lbl_metric_delta_v.setStyleSheet("font-weight: bold; font-size: 12px; color: #a78bfa;")
        grid_hud.addWidget(self.lbl_metric_delta_v, 1, 1)

        grid_hud.addWidget(QLabel("Received Power (Prx):"), 2, 0)
        self.lbl_metric_prx = QLabel("-80.0 dBFS")
        self.lbl_metric_prx.setStyleSheet("font-weight: bold; color: #f1f5f9;")
        grid_hud.addWidget(self.lbl_metric_prx, 2, 1)

        hud_layout.addLayout(grid_hud)
        sidebar_layout.addWidget(hud_box)

        sidebar_layout.addStretch()
        body_splitter.addWidget(sidebar_widget)

        # --- RIGHT MAIN AREA: REAL-TIME PLOTS (pyqtgraph) ---
        plots_widget = QWidget()
        plots_layout = QVBoxLayout(plots_widget)
        plots_layout.setContentsMargins(4, 0, 0, 0)
        plots_layout.setSpacing(8)

        # Plot 1: Time-Domain Power Strip Chart P_rx(t)
        self.plot_strip = pg.PlotWidget(title="<b>Time-Domain Received Power Strip Chart: P_rx(t)</b>")
        self.plot_strip.setLabel("left", "Received Power", units="dBFS")
        self.plot_strip.setLabel("bottom", "Time History", units="s")
        self.plot_strip.setYRange(-90.0, -10.0)
        self.plot_strip.showGrid(x=True, y=True, alpha=0.3)
        self.curve_strip = self.plot_strip.plot(
            pen=pg.mkPen(color="#00e5ff", width=2.0),
            name="Power (dBFS)",
        )
        self.thresh_line = pg.InfiniteLine(
            pos=-50.0, angle=0, pen=pg.mkPen(color="#f59e0b", width=1.5, style=Qt.DashLine)
        )
        self.plot_strip.addItem(self.thresh_line)
        plots_layout.addWidget(self.plot_strip, stretch=4)

        # Splitter for bottom two plots
        bottom_plots_splitter = QSplitter(Qt.Horizontal)

        # Plot 2: Complex I/Q Constellation & Centroid Phase Plane
        self.plot_iq = pg.PlotWidget(title="<b>Complex I/Q Phase Plane (Centroid Separation)</b>")
        self.plot_iq.setLabel("left", "Quadrature (Q)")
        self.plot_iq.setLabel("bottom", "In-Phase (I)")
        self.plot_iq.showGrid(x=True, y=True, alpha=0.3)
        self.plot_iq.setAspectLocked(True)

        # Live sample cloud
        self.scatter_iq = pg.ScatterPlotItem(
            size=4, brush=pg.mkBrush(0, 229, 255, 120), pen=None
        )
        self.plot_iq.addItem(self.scatter_iq)

        # Centroid markers
        self.centroid_1_marker = pg.ScatterPlotItem(
            size=12, symbol="o", brush=pg.mkBrush("#0284c7"), pen=pg.mkPen("#ffffff", width=1.5)
        )
        self.centroid_2_marker = pg.ScatterPlotItem(
            size=12, symbol="s", brush=pg.mkBrush("#22c55e"), pen=pg.mkPen("#ffffff", width=1.5)
        )
        self.plot_iq.addItem(self.centroid_1_marker)
        self.plot_iq.addItem(self.centroid_2_marker)

        # Connecting vector line
        self.delta_v_line = self.plot_iq.plot(
            pen=pg.mkPen(color="#ec4899", width=2.0, style=Qt.DashLine)
        )
        bottom_plots_splitter.addWidget(self.plot_iq)

        # Plot 3: RF Spectrum (FFT / PSD)
        self.plot_fft = pg.PlotWidget(title="<b>Real-Time RF Power Spectrum (FFT / PSD)</b>")
        self.plot_fft.setLabel("left", "PSD", units="dB/Hz")
        self.plot_fft.setLabel("bottom", "Frequency Offset", units="MHz")
        self.plot_fft.showGrid(x=True, y=True, alpha=0.3)
        self.plot_fft.setYRange(-100.0, 10.0)
        self.curve_fft = self.plot_fft.plot(
            pen=pg.mkPen(color="#a855f7", width=1.5), fillLevel=-100.0, brush=pg.mkBrush(168, 85, 247, 40)
        )
        bottom_plots_splitter.addWidget(self.plot_fft)

        plots_layout.addWidget(bottom_plots_splitter, stretch=5)
        body_splitter.addWidget(plots_widget)

        main_layout.addWidget(body_splitter)

        # 3. Bottom Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready. Select an antenna mode and press START ACQUISITION.")

        # Connect control changes to active worker updates
        self.spin_freq.valueChanged.connect(self._on_freq_changed)
        self.slider_rx_gain.valueChanged.connect(self._on_rx_gain_changed)
        self.slider_tx_gain.valueChanged.connect(self._on_tx_gain_changed)
        self.combo_rate.currentIndexChanged.connect(self._on_rate_changed)
        self.combo_carrier.currentIndexChanged.connect(self._on_carrier_changed)

    def apply_mode_config(self, mode_key: str) -> None:
        """Apply preset frequencies, gains, and theoretical specs for the chosen tag."""
        self.current_mode_key = mode_key
        cfg = self.modes[mode_key]

        # Update button states
        self.btn_mode1.setChecked(mode_key == "mode1")
        self.btn_mode2.setChecked(mode_key == "mode2")
        self.btn_mode3.setChecked(mode_key == "mode3")

        # Update style highlight
        for btn, k in [(self.btn_mode1, "mode1"), (self.btn_mode2, "mode2"), (self.btn_mode3, "mode3")]:
            if k == mode_key:
                btn.setStyleSheet(
                    "background-color: #0284c7; color: #ffffff; border: 1px solid #38bdf8; font-weight: bold;"
                )
            else:
                btn.setStyleSheet("background-color: #334155; color: #94a3b8; border: 1px solid #475569;")

        # Update specs card
        self.lbl_spec_name.setText(cfg["tag_name"])
        self.lbl_spec_s11.setText(cfg["s11_theory"])
        self.lbl_spec_rcs.setText(cfg["rcs_theory"])
        self.lbl_spec_gain.setText(cfg["gain_theory"])
        self.lbl_spec_desc.setText(cfg["description"])

        # Block signals temporarily to prevent redundant worker commands
        self.spin_freq.blockSignals(True)
        self.slider_rx_gain.blockSignals(True)
        self.slider_tx_gain.blockSignals(True)
        self.combo_rate.blockSignals(True)
        self.combo_carrier.blockSignals(True)

        self.spin_freq.setValue(cfg["center_freq"] / 1e6)
        self.slider_rx_gain.setValue(int(cfg["rx_gain"]))
        self.lbl_rx_gain_val.setText(f"{int(cfg['rx_gain'])} dB")
        self.slider_tx_gain.setValue(int(cfg["tx_gain"]))
        self.lbl_tx_gain_val.setText(f"{int(cfg['tx_gain'])} dB")

        # Rate index
        rate_mhz = cfg["sample_rate"] / 1e6
        if rate_mhz == 1.0:
            self.combo_rate.setCurrentIndex(0)
        elif rate_mhz == 2.0:
            self.combo_rate.setCurrentIndex(1)
        elif rate_mhz == 5.0:
            self.combo_rate.setCurrentIndex(2)
        elif rate_mhz == 10.0:
            self.combo_rate.setCurrentIndex(3)

        self.combo_carrier.setCurrentIndex(0 if cfg["carrier_mode"] == "cw" else 1)

        self.spin_freq.blockSignals(False)
        self.slider_rx_gain.blockSignals(False)
        self.slider_tx_gain.blockSignals(False)
        self.combo_rate.blockSignals(False)
        self.combo_carrier.blockSignals(False)

        # Notify running worker
        if self.worker and self.worker.isRunning():
            self.worker.request_command("set_freq", freq=cfg["center_freq"])
            self.worker.request_command("set_rate", rate=cfg["sample_rate"])
            self.worker.request_command("set_rx_gain", gain=cfg["rx_gain"])
            self.worker.request_command("set_tx_gain", gain=cfg["tx_gain"])
            self.worker.request_command("set_mode", mode=cfg["carrier_mode"])

        self.status_bar.showMessage(f"Configured for {cfg['name']} ({cfg['center_freq']/1e6:.1f} MHz).")

    def toggle_streaming(self) -> None:
        """Start or stop the acquisition worker thread."""
        if self.worker and self.worker.isRunning():
            # Stop streaming
            self.status_bar.showMessage("Stopping acquisition...")
            self.worker.stop()
            self.worker = None
            self.btn_toggle_stream.setText("▶  START ACQUISITION")
            self.btn_toggle_stream.setStyleSheet(
                "background-color: #0284c7; color: white; font-weight: bold; font-size: 12px;"
            )
            self.status_bar.showMessage("Acquisition stopped.")
        else:
            # Start streaming
            cfg = self.modes[self.current_mode_key]
            freq_hz = self.spin_freq.value() * 1e6
            rate_map = [1.0e6, 2.0e6, 5.0e6, 10.0e6]
            rate_hz = rate_map[self.combo_rate.currentIndex()]
            rx_g = float(self.slider_rx_gain.value())
            tx_g = float(self.slider_tx_gain.value())
            carrier = "cw" if self.combo_carrier.currentIndex() == 0 else "wifi"

            self.worker = SDRWorker(
                center_freq=freq_hz,
                sample_rate=rate_hz,
                rx_gain=rx_g,
                tx_gain=tx_g,
                carrier_mode=carrier,
                force_mock=self.force_mock,
            )
            self.worker.sig_frame_ready.connect(self._on_frame_ready)
            self.worker.sig_hw_status.connect(self._on_hw_status)
            self.worker.sig_state_transition.connect(self._on_state_transition)
            self.worker.sig_snapshot_saved.connect(self._on_snapshot_saved)
            self.worker.sig_error.connect(self._on_error)

            self.worker.start()
            self.btn_toggle_stream.setText("⏹  STOP ACQUISITION")
            self.btn_toggle_stream.setStyleSheet(
                "background-color: #b91c1c; color: white; font-weight: bold; font-size: 12px;"
            )
            self.status_bar.showMessage("Acquisition active. Streaming samples...")

    def trigger_autozero(self) -> None:
        """Trigger software carrier leakage subtraction."""
        if self.worker and self.worker.isRunning():
            self.worker.calibrate_baseline()
            self.status_bar.showMessage("Auto-zero baseline calibrated! Direct carrier leakage subtracted.")
        else:
            self.status_bar.showMessage("⚠ Please start acquisition before calibrating baseline.")

    def trigger_snapshot_export(self) -> None:
        """Request high-resolution snapshot export in .mat, .npz, and CSV formats."""
        if self.worker and self.worker.isRunning():
            export_dir = os.path.join(os.path.dirname(__file__), "output", "snapshots")
            tag_slug = self.current_mode_key
            self.worker.request_snapshot(export_dir, f"backscatter_snapshot_{tag_slug}")
            self.status_bar.showMessage("Exporting measurement snapshot...")
        else:
            self.status_bar.showMessage("⚠ Please start acquisition before capturing a snapshot.")

    def _on_frame_ready(self, payload: dict) -> None:
        """Handle new frame from SDR worker and update pyqtgraph plots."""
        # 1. Update strip chart
        self.curve_strip.setData(payload["time_history"], payload["power_history"])
        self.lbl_metric_prx.setText(f"{payload['power_db']:.1f} dBFS")

        # Dynamic threshold positioning
        min_p = np.min(payload["power_history"][-60:])
        max_p = np.max(payload["power_history"][-60:])
        mid_p = (min_p + max_p) / 2.0
        self.thresh_line.setValue(mid_p)

        # 2. Update state card
        state_str = payload["current_state"]
        if "SHORT" in state_str:
            self.card_state.setText(state_str)
            self.card_state.setStyleSheet(
                "background-color: #052e16; color: #4ade80; border: 2px solid #22c55e; "
                "border-radius: 6px; font-weight: bold; font-size: 13px;"
            )
        else:
            self.card_state.setText(state_str)
            self.card_state.setStyleSheet(
                "background-color: #082f49; color: #38bdf8; border: 2px solid #0284c7; "
                "border-radius: 6px; font-weight: bold; font-size: 13px;"
            )

        # 3. Update delta metrics
        self.lbl_metric_delta_p.setText(f"+{payload['delta_p']:.2f} dB")
        self.lbl_metric_delta_v.setText(f"{payload['delta_v']:.4f}")

        # 4. Update I/Q phase plane
        iq_samples = payload["iq_samples"]
        if len(iq_samples) > 0:
            self.scatter_iq.setData(x=iq_samples.real, y=iq_samples.imag)

        c1 = payload["centroid_1"]
        c2 = payload["centroid_2"]
        self.centroid_1_marker.setData(x=[c1.real], y=[c1.imag])
        self.centroid_2_marker.setData(x=[c2.real], y=[c2.imag])
        self.delta_v_line.setData(x=[c1.real, c2.real], y=[c1.imag, c2.imag])

        # 5. Update FFT spectrum
        self.curve_fft.setData(payload["fft_freqs"], payload["fft_psd"])

    def _on_hw_status(self, msg: str, is_hardware: bool) -> None:
        """Update hardware status badge."""
        if is_hardware:
            self.hw_status_label.setText(f"[ONLINE] {msg}")
            self.hw_status_label.setStyleSheet(
                "background-color: #052e16; color: #4ade80; border: 1px solid #16a34a; "
                "border-radius: 12px; padding: 4px 12px; font-weight: bold; font-size: 11px;"
            )
        else:
            self.hw_status_label.setText(f"[SIM] {msg}")
            self.hw_status_label.setStyleSheet(
                "background-color: #1e293b; color: #ffab00; border: 1px solid #d97706; "
                "border-radius: 12px; padding: 4px 12px; font-weight: bold; font-size: 11px;"
            )
        self.status_bar.showMessage(msg)

    def _on_state_transition(self, state_name: str, delta_p: float, delta_v: float) -> None:
        """Handle detected load modulation step event."""
        self.status_bar.showMessage(
            f"⚡ Tag Transition Event: Switched to {state_name} (ΔP = +{delta_p:.2f} dB, Δ|V| = {delta_v:.4f})"
        )

    def _on_snapshot_saved(self, path: str) -> None:
        """Notify user of saved dataset for MATLAB and Python."""
        filename = os.path.basename(path)
        msg = f"[OK] Snapshot exported! MATLAB file saved: {filename}"
        self.status_bar.showMessage(msg, 10000)
        print(f"[EXPORT] {msg} -> Full Path: {path}")

    def _on_error(self, err_msg: str) -> None:
        """Log SDR error message."""
        self.status_bar.showMessage(f"⚠ SDR Error: {err_msg}")

    def _on_freq_changed(self, val: float) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.request_command("set_freq", freq=val * 1e6)

    def _on_rx_gain_changed(self, val: int) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.request_command("set_rx_gain", gain=float(val))

    def _on_tx_gain_changed(self, val: int) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.request_command("set_tx_gain", gain=float(val))

    def _on_rate_changed(self, idx: int) -> None:
        rate_map = [1.0e6, 2.0e6, 5.0e6, 10.0e6]
        if self.worker and self.worker.isRunning():
            self.worker.request_command("set_rate", rate=rate_map[idx])

    def _on_carrier_changed(self, idx: int) -> None:
        mode = "cw" if idx == 0 else "wifi"
        if self.worker and self.worker.isRunning():
            self.worker.request_command("set_mode", mode=mode)

    def closeEvent(self, event) -> None:
        """Clean shutdown of background SDR threads on close."""
        if self.worker and self.worker.isRunning():
            self.worker.stop()
        event.accept()


def main() -> None:
    """Launch the Backscatter SDR Analyzer GUI application."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = BackscatterGUI()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
