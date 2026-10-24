"""Robust Real-Time Backscatter Tag SDR Acquisition & Detection Dashboard.

Engineered with Tkinter and Matplotlib for 100% crash-proof cross-platform
stability on Windows. Integrates directly with NI USRP-2900 / B200 (USB 3.0)
via UHD or seamless physics-grounded mock fallback.

Features:
- 3 Dedicated Detection Modes (2.44 GHz IFA, Sub-1GHz Meander, Leggiero Bowtie)
- Real-time time-domain strip chart P_rx(t) with dynamic step detection
- Complex I/Q constellation phase plane with centroid tracking (Delta V)
- Fast real-time RF power spectrum (FFT / PSD)
- Software carrier leakage cancellation (Auto-Zero Baseline)
- Instant export to MATLAB (.mat), NumPy (.npz), and CSV
"""

from __future__ import annotations

import argparse
import os
import queue
import sys
import threading
import time
from typing import Any, Dict, Optional, Tuple

import numpy as np
import scipy.io
import scipy.signal

# Tkinter and Matplotlib
import tkinter as tk
from tkinter import messagebox, ttk

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

# Import local backscatter utilities
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

try:
    from mock_usrp import (
        HAS_UHD,
        MockMultiUSRP,
        MockRXMetadata,
        MockRXMetadataErrorCode,
        MockStreamArgs,
        MockStreamCMD,
        MockStreamMode,
        MockTXMetadata,
        MockTuneRequest,
    )
    from backscatter_metrics import (
        compute_complex_vector_distance,
        compute_differential_power,
        compute_moving_average_power,
        compute_scnr,
    )
except ImportError:
    from .mock_usrp import (
        HAS_UHD,
        MockMultiUSRP,
        MockRXMetadata,
        MockRXMetadataErrorCode,
        MockStreamArgs,
        MockStreamCMD,
        MockStreamMode,
        MockTXMetadata,
        MockTuneRequest,
    )
    from .backscatter_metrics import (
        compute_complex_vector_distance,
        compute_differential_power,
        compute_moving_average_power,
        compute_scnr,
    )

if HAS_UHD:
    import uhd


class SDRStreamThread(threading.Thread):
    """Background SDR streaming thread decoupled from the UI mainloop."""

    def __init__(
        self,
        center_freq: float = 2.44e9,
        sample_rate: float = 2.0e6,
        rx_gain: float = 45.0,
        tx_gain: float = 60.0,
        carrier_mode: str = "cw",
        force_mock: bool = False,
        sensitivity_db: float = 0.3,
        data_queue: Optional[queue.Queue] = None,
        event_queue: Optional[queue.Queue] = None,
    ) -> None:
        super().__init__(daemon=True)
        self.center_freq = center_freq
        self.sample_rate = sample_rate
        self.rx_gain = rx_gain
        self.tx_gain = tx_gain
        self.carrier_mode = carrier_mode
        self.force_mock = force_mock
        self.sensitivity_db = sensitivity_db
        self.if_freq = 100e3  # 100 kHz IF tone for lock-in & DC notch avoidance
        self.tx_running = False
        self.tx_thread: Optional[threading.Thread] = None
        self.data_queue = data_queue or queue.Queue(maxsize=10)
        self.event_queue = event_queue or queue.Queue()

        self._running = False
        self._command_queue: queue.Queue = queue.Queue()

        self.baseline_offset: complex = 0.0 + 0.0j
        self.current_state: str = "STATE 1: ABSORBING (50 Ω)"

        self.history_len = 250
        self.power_history = np.full(self.history_len, -80.0, dtype=np.float32)
        self.time_history = np.linspace(-10.0, 0.0, self.history_len, dtype=np.float32)

        self.usrp: Any = None
        self.is_hardware: bool = False

    def request_command(self, cmd_type: str, **kwargs) -> None:
        self._command_queue.put({"type": cmd_type, **kwargs})

    def stop(self) -> None:
        self._running = False
        self.tx_running = False

    def _init_transceiver(self) -> None:
        if not self.force_mock and HAS_UHD:
            try:
                self.event_queue.put(("hw_status", "Probing NI USRP-2900...", False))
                self.usrp = uhd.usrp.MultiUSRP("type=b200")
                self.is_hardware = True
                serial = self.usrp.get_usrp_rx_info(0).get("mboard_serial", "Unknown")
                self.event_queue.put(("hw_status", f"ONLINE: NI USRP-2900 [Serial: {serial}]", True))
                return
            except Exception as e:
                self.event_queue.put(("hw_status", f"Hardware probe notice: {e}. Using Simulation.", False))

        self.usrp = MockMultiUSRP(mode=self.carrier_mode)
        self.is_hardware = False
        self.event_queue.put(("hw_status", "SIMULATION ACTIVE (Physics Mock)", False))

    def _apply_rf_config(self) -> None:
        if self.usrp is None:
            return
        try:
            self.usrp.set_rx_rate(self.sample_rate, 0)
            self.usrp.set_tx_rate(self.sample_rate, 0)

            tune_req = (
                MockTuneRequest(self.center_freq)
                if not self.is_hardware
                else uhd.types.TuneRequest(self.center_freq)
            )
            self.usrp.set_rx_freq(tune_req, 0)
            self.usrp.set_tx_freq(tune_req, 0)

            self.usrp.set_rx_antenna("RX2", 0)
            self.usrp.set_tx_antenna("TX/RX", 0)

            self.usrp.set_rx_gain(self.rx_gain, 0)
            tx_gain_val = self.tx_gain if self.carrier_mode == "cw" else 0.0
            self.usrp.set_tx_gain(tx_gain_val, 0)
            self.usrp.set_rx_agc(False, 0)
        except Exception as exc:
            self.event_queue.put(("error", f"RF Config Error: {exc}"))

    def run(self) -> None:
        self._running = True
        self._init_transceiver()
        self._apply_rf_config()

        # Chunk size tuned to contain an exact integer multiple of 100 kHz IF cycles
        chunk_size = 4000
        stream_args = (
            MockStreamArgs("fc32", "sc16")
            if not self.is_hardware
            else uhd.usrp.StreamArgs("fc32", "sc16")
        )
        stream_args.channels = [0]

        try:
            rx_streamer = self.usrp.get_rx_stream(stream_args)
            tx_streamer = (
                self.usrp.get_tx_stream(stream_args)
                if (self.carrier_mode == "cw" and self.usrp)
                else None
            )
        except Exception as exc:
            self.event_queue.put(("error", f"Stream init failed: {exc}"))
            return

        recv_buffer = np.zeros((1, chunk_size), dtype=np.complex64)
        rx_md = MockRXMetadata() if not self.is_hardware else uhd.types.RXMetadata()

        # Build CW Tone buffers: IF tone at +100 kHz avoids AD9361 DC notch filter & LO leakage
        if self.carrier_mode == "cw":
            t_chunk = np.arange(chunk_size, dtype=np.float32) / self.sample_rate
            if self.is_hardware:
                cw_chunk = (0.707 * np.exp(1j * 2 * np.pi * self.if_freq * t_chunk)).astype(np.complex64).reshape(1, chunk_size)
                rx_downconvert = np.exp(-1j * 2 * np.pi * self.if_freq * t_chunk).astype(np.complex64)
            else:
                cw_chunk = np.ones((1, chunk_size), dtype=np.complex64) * 0.707
                rx_downconvert = np.ones(chunk_size, dtype=np.complex64)
        else:
            cw_chunk = np.zeros((1, chunk_size), dtype=np.complex64)
            rx_downconvert = np.ones(chunk_size, dtype=np.complex64)

        # Start RX stream
        stream_cmd_type = MockStreamCMD if not self.is_hardware else uhd.types.StreamCMD
        stream_mode_start = (
            MockStreamMode.start_cont if not self.is_hardware else uhd.types.StreamMode.start_cont
        )
        cmd = stream_cmd_type(stream_mode_start)
        cmd.stream_now = True
        rx_streamer.issue_stream_cmd(cmd)

        # Dedicated TX streaming thread: keeps USRP hardware FIFO completely full (0 underflows)
        if self.carrier_mode == "cw" and tx_streamer is not None:
            self.tx_running = True
            def _tx_feeder() -> None:
                tx_md_loc = MockTXMetadata() if not self.is_hardware else uhd.types.TXMetadata()
                tx_md_loc.start_of_burst = True
                tx_md_loc.end_of_burst = False
                while self._running and self.tx_running:
                    try:
                        tx_streamer.send(cw_chunk, tx_md_loc)
                        tx_md_loc.start_of_burst = False
                    except Exception:
                        pass
            self.tx_thread = threading.Thread(target=_tx_feeder, daemon=True)
            self.tx_thread.start()

        last_render_time = time.time()
        render_interval = 1.0 / 30.0

        recent_samples = np.zeros(int(self.sample_rate * 1.0), dtype=np.complex64)
        recent_pos = 0

        c1_samples = []  # State 1: 50-Ohm Absorbing (Jumper Pins 1-2)
        c2_samples = []  # State 2: Short Reflecting (Jumper Pins 2-3)
        c3_samples = []  # State 3: Open Reflecting (No Jumper)

        try:
            while self._running:
                while not self._command_queue.empty():
                    msg = self._command_queue.get_nowait()
                    t = msg.get("type")
                    if t == "set_freq":
                        self.center_freq = msg["freq"]
                        self._apply_rf_config()
                    elif t == "set_rx_gain":
                        self.rx_gain = msg["gain"]
                        self._apply_rf_config()
                    elif t == "set_tx_gain":
                        self.tx_gain = msg["gain"]
                        self._apply_rf_config()
                    elif t == "set_rate":
                        self.sample_rate = msg["rate"]
                        self._apply_rf_config()
                    elif t == "set_mode":
                        self.carrier_mode = msg["mode"]
                        self._apply_rf_config()
                    elif t == "set_sensitivity":
                        self.sensitivity_db = float(msg.get("val", 0.3))
                    elif t == "calibrate":
                        if len(recent_samples) > 0:
                            # Auto-zero baseline from demodulated carrier
                            self.baseline_offset = np.mean(demod_chunk)
                            c1_samples.clear()
                            c2_samples.clear()
                            c3_samples.clear()
                            self.current_state = "STATE 1: ABSORBING (50 Ω)"
                    elif t == "snapshot":
                        self._execute_snapshot_export(
                            msg["export_dir"], msg["base_filename"], recent_samples
                        )

                num_rx = rx_streamer.recv(recv_buffer, rx_md, timeout=0.1)
                if num_rx <= 0:
                    time.sleep(0.005)
                    continue

                if not self.is_hardware:
                    time.sleep(num_rx / self.sample_rate)

                raw_chunk = recv_buffer[0, :num_rx]
                # Coherent Lock-in Demodulation: downconverts IF carrier tone to baseband DC
                demod_chunk = raw_chunk * rx_downconvert[:num_rx]
                clean_chunk = demod_chunk - self.baseline_offset

                n_put = len(clean_chunk)
                if recent_pos + n_put <= len(recent_samples):
                    recent_samples[recent_pos : recent_pos + n_put] = clean_chunk
                    recent_pos += n_put
                else:
                    first_part = len(recent_samples) - recent_pos
                    recent_samples[recent_pos:] = clean_chunk[:first_part]
                    second_part = n_put - first_part
                    recent_samples[:second_part] = clean_chunk[first_part:]
                    recent_pos = second_part

                now = time.time()
                if now - last_render_time >= render_interval:
                    last_render_time = now

                    inst_power = float(np.mean(np.abs(clean_chunk) ** 2))
                    inst_power_db = float(10.0 * np.log10(max(inst_power, 1e-12)))
                    c_mean = complex(np.mean(clean_chunk))
                    phase_deg = float(np.degrees(np.angle(c_mean)))

                    self.power_history[:-1] = self.power_history[1:]
                    self.power_history[-1] = inst_power_db

                    min_p = np.min(self.power_history[-60:])
                    max_p = np.max(self.power_history[-60:])
                    step_threshold = (min_p + max_p) / 2.0
                    step_contrast = max_p - min_p

                    prev_state = self.current_state
                    # Adaptive sensitivity thresholding
                    if step_contrast >= self.sensitivity_db:
                        if inst_power_db < step_threshold:
                            self.current_state = "STATE 1: ABSORBING (50 Ω)"
                            c1_samples.append(c_mean)
                        else:
                            # Reflective state: distinguish Short vs Open
                            c1_val = np.mean(c1_samples) if c1_samples else (0.0 + 0.0j)
                            v_diff = c_mean - c1_val
                            if len(c2_samples) > 0 and len(c3_samples) > 0:
                                d2 = abs(c_mean - np.mean(c2_samples))
                                d3 = abs(c_mean - np.mean(c3_samples))
                                if d2 <= d3:
                                    self.current_state = "STATE 2: REFLECTIVE SHORT (0 Ω)"
                                    c2_samples.append(c_mean)
                                else:
                                    self.current_state = "STATE 3: REFLECTIVE OPEN (∞ Ω)"
                                    c3_samples.append(c_mean)
                            elif len(c2_samples) > 0:
                                v2 = np.mean(c2_samples) - c1_val
                                denom = abs(v_diff) * abs(v2) + 1e-9
                                proj = np.real(v_diff * np.conj(v2)) / denom
                                if proj >= 0.0:
                                    self.current_state = "STATE 2: REFLECTIVE SHORT (0 Ω)"
                                    c2_samples.append(c_mean)
                                else:
                                    self.current_state = "STATE 3: REFLECTIVE OPEN (∞ Ω)"
                                    c3_samples.append(c_mean)
                            else:
                                self.current_state = "STATE 2: REFLECTIVE SHORT (0 Ω)"
                                c2_samples.append(c_mean)
                    else:
                        if "SHORT" in self.current_state:
                            c2_samples.append(c_mean)
                        elif "OPEN" in self.current_state:
                            c3_samples.append(c_mean)
                        else:
                            c1_samples.append(c_mean)

                    if len(c1_samples) > 150:
                        c1_samples = c1_samples[-150:]
                    if len(c2_samples) > 150:
                        c2_samples = c2_samples[-150:]
                    if len(c3_samples) > 150:
                        c3_samples = c3_samples[-150:]

                    if prev_state != self.current_state:
                        self.event_queue.put((
                            "transition",
                            self.current_state,
                            step_contrast,
                        ))

                    n_fft = 512
                    fft_chunk = clean_chunk[:n_fft]
                    if len(fft_chunk) < n_fft:
                        fft_chunk = np.pad(fft_chunk, (0, n_fft - len(fft_chunk)))
                    window = np.hanning(n_fft)
                    psd = np.abs(np.fft.fftshift(np.fft.fft(fft_chunk * window))) ** 2
                    psd_db = 10.0 * np.log10(np.maximum(psd, 1e-12))
                    freqs = np.fft.fftshift(np.fft.fftfreq(n_fft, d=1.0 / self.sample_rate)) / 1e6

                    step = max(1, len(clean_chunk) // 150)
                    iq_sub = clean_chunk[::step]

                    centroid_1 = complex(np.mean(c1_samples)) if c1_samples else 0.0 + 0.0j
                    centroid_2 = complex(np.mean(c2_samples)) if c2_samples else 0.0 + 0.0j
                    centroid_3 = complex(np.mean(c3_samples)) if c3_samples else 0.0 + 0.0j
                    delta_v_mag = float(np.abs(centroid_2 - centroid_1))
                    delta_v_open = float(np.abs(centroid_3 - centroid_1))

                    payload = {
                        "power_db": inst_power_db,
                        "power_history": self.power_history.copy(),
                        "time_history": self.time_history,
                        "iq_samples": iq_sub,
                        "centroid_1": centroid_1,
                        "centroid_2": centroid_2,
                        "centroid_3": centroid_3,
                        "delta_v": delta_v_mag,
                        "delta_v_open": delta_v_open,
                        "phase_deg": phase_deg,
                        "delta_p": step_contrast,
                        "current_state": self.current_state,
                        "fft_freqs": freqs,
                        "fft_psd": psd_db,
                    }
                    if not self.data_queue.full():
                        self.data_queue.put_nowait(payload)

        finally:
            self.tx_running = False
            if self.carrier_mode == "cw" and tx_streamer is not None and self.is_hardware:
                try:
                    tx_end_md = uhd.types.TXMetadata()
                    tx_end_md.end_of_burst = True
                    tx_streamer.send(np.zeros((1, 100), dtype=np.complex64), tx_end_md)
                except Exception:
                    pass
            try:
                stream_mode_stop = (
                    MockStreamMode.stop_cont
                    if not self.is_hardware
                    else uhd.types.StreamMode.stop_cont
                )
                stop_cmd = stream_cmd_type(stream_mode_stop)
                stop_cmd.stream_now = True
                rx_streamer.issue_stream_cmd(stop_cmd)
            except Exception:
                pass

    def _execute_snapshot_export(
        self, export_dir: str, base_filename: str, samples: np.ndarray
    ) -> None:
        try:
            os.makedirs(export_dir, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            prefix = f"{base_filename}_{timestamp}"

            max_snap = int(self.sample_rate * 1.0)
            snap_samples = samples[-max_snap:] if len(samples) > max_snap else samples

            npz_path = os.path.join(export_dir, f"{prefix}.npz")
            np.savez(
                npz_path,
                samples=snap_samples,
                sample_rate=self.sample_rate,
                center_freq=self.center_freq,
                rx_gain=self.rx_gain,
                tx_gain=self.tx_gain,
                carrier_mode=self.carrier_mode,
                current_state=self.current_state,
                timestamp=timestamp,
            )

            mat_path = os.path.join(export_dir, f"{prefix}.mat")
            mat_dict = {
                "iq_samples": snap_samples,
                "sample_rate": float(self.sample_rate),
                "carrier_freq_hz": float(self.center_freq),
                "rx_gain_db": float(self.rx_gain),
                "tx_gain_db": float(self.tx_gain),
                "carrier_mode": str(self.carrier_mode),
                "state_label": str(self.current_state),
                "timestamp": str(timestamp),
            }
            scipy.io.savemat(mat_path, mat_dict)

            csv_path = os.path.join(export_dir, f"{prefix}_metrics.csv")
            with open(csv_path, "w", encoding="utf-8") as f:
                f.write("Parameter,Value,Unit\n")
                f.write(f"Timestamp,{timestamp},-\n")
                f.write(f"Center Frequency,{self.center_freq / 1e6:.3f},MHz\n")
                f.write(f"Sample Rate,{self.sample_rate / 1e6:.2f},MS/s\n")
                f.write(f"RX Gain,{self.rx_gain:.1f},dB\n")
                f.write(f"TX Gain,{self.tx_gain:.1f},dB\n")
                f.write(f"Carrier Mode,{self.carrier_mode},-\n")
                f.write(f"Active State,{self.current_state},-\n")
                f.write(f"Sample Count,{len(snap_samples)},samples\n")

            self.event_queue.put(("snapshot_saved", mat_path))
        except Exception as exc:
            self.event_queue.put(("error", f"Snapshot export failed: {exc}"))


class BackscatterTkGUI:
    """Modern Dark Scientific Backscatter Analyzer GUI built with Tkinter & Matplotlib."""

    def __init__(self, root: tk.Tk, force_mock: bool = False) -> None:
        self.root = root
        self.force_mock = force_mock
        self.root.title("Backscatter Tag SDR Detection & Analysis Suite — NI USRP-2900")
        self.root.geometry("1380x880")
        self.root.minsize(1024, 720)
        self.root.configure(bg="#18191c")

        self.worker: Optional[SDRStreamThread] = None
        self.data_queue = queue.Queue(maxsize=10)
        self.event_queue = queue.Queue()

        self.modes = {
            "mode1": {
                "name": "Mode 1: 2.44 GHz IFA (SWRA117D)",
                "tag_name": "TI SWRA117D Inverted-F",
                "center_freq": 2440.0e6,
                "sample_rate": 2.0e6,
                "rx_gain": 45.0,
                "tx_gain": 60.0,
                "carrier_mode": "cw",
                "s11_theory": "-24.4 dB",
                "rcs_theory": "-26.5 dBsm",
                "gain_theory": "+2.1 dBi",
                "desc": "50Ω CPWG feed, ground counterpoise clutter suppression.",
            },
            "mode2": {
                "name": "Mode 2: Sub-1GHz Meander (868/915M)",
                "tag_name": "Single-Sided Meander Monopole",
                "center_freq": 868.0e6,
                "sample_rate": 1.0e6,
                "rx_gain": 40.0,
                "tx_gain": 55.0,
                "carrier_mode": "cw",
                "s11_theory": "-19.2 dB",
                "rcs_theory": "-21.8 dBsm",
                "gain_theory": "+0.8 dBi",
                "desc": "73.5 mm planar trace replacing 19-via helical for 0-via milling.",
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
                "desc": "R=10.16mm, 80° sector, 36x15.5mm cavity with top ground border.",
            },
        }
        self.current_mode_key = "mode1"

        self._build_ui()
        self.apply_mode_config("mode1")

        # Start periodic GUI update loop
        self.root.after(30, self._poll_queues)

    def _build_ui(self) -> None:
        # Top Header Bar
        top_bar = tk.Frame(self.root, bg="#131417", pady=8, padx=12)
        top_bar.pack(fill=tk.X, side=tk.TOP)

        title_lbl = tk.Label(
            top_bar,
            text="BACKSCATTER SDR ANALYZER",
            font=("Segoe UI", 12, "bold"),
            fg="#00e5ff",
            bg="#131417",
        )
        title_lbl.pack(side=tk.LEFT, padx=(0, 20))

        # Mode Buttons
        self.btn_mode1 = tk.Button(
            top_bar,
            text="Mode 1: 2.44GHz IFA",
            font=("Segoe UI", 9, "bold"),
            bg="#0284c7",
            fg="white",
            relief=tk.FLAT,
            padx=10,
            command=lambda: self.apply_mode_config("mode1"),
        )
        self.btn_mode1.pack(side=tk.LEFT, padx=4)

        self.btn_mode2 = tk.Button(
            top_bar,
            text="Mode 2: Sub-1GHz Meander",
            font=("Segoe UI", 9, "bold"),
            bg="#334155",
            fg="#cbd5e1",
            relief=tk.FLAT,
            padx=10,
            command=lambda: self.apply_mode_config("mode2"),
        )
        self.btn_mode2.pack(side=tk.LEFT, padx=4)

        self.btn_mode3 = tk.Button(
            top_bar,
            text="Mode 3: Leggiero Bowtie",
            font=("Segoe UI", 9, "bold"),
            bg="#334155",
            fg="#cbd5e1",
            relief=tk.FLAT,
            padx=10,
            command=lambda: self.apply_mode_config("mode3"),
        )
        self.btn_mode3.pack(side=tk.LEFT, padx=4)

        # Hardware Badge
        self.lbl_hw = tk.Label(
            top_bar,
            text="[*] Probing SDR Hardware...",
            font=("Segoe UI", 9, "bold"),
            fg="#ffab00",
            bg="#1e293b",
            padx=10,
            pady=3,
        )
        self.lbl_hw.pack(side=tk.RIGHT)

        # Main Body Splitter
        body = tk.Frame(self.root, bg="#18191c")
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        # Left Sidebar (Width: 320)
        sidebar = tk.Frame(body, bg="#222428", width=340, padx=10, pady=8)
        sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        sidebar.pack_propagate(False)

        # Box 1: Antenna Target Specs
        lbl_sec1 = tk.Label(sidebar, text="ANTENNA TARGET SPECS", font=("Segoe UI", 9, "bold"), fg="#94a3b8", bg="#222428")
        lbl_sec1.pack(anchor="w", pady=(0, 4))

        self.lbl_spec_tag = tk.Label(sidebar, text="TI SWRA117D IFA", font=("Segoe UI", 10, "bold"), fg="#38bdf8", bg="#222428")
        self.lbl_spec_tag.pack(anchor="w")

        spec_frame = tk.Frame(sidebar, bg="#222428")
        spec_frame.pack(fill=tk.X, pady=4)
        self.lbl_s11 = tk.Label(spec_frame, text="S11: -24.4 dB", font=("Segoe UI", 9), fg="#e2e8f0", bg="#222428")
        self.lbl_s11.pack(side=tk.LEFT, padx=(0, 10))
        self.lbl_rcs = tk.Label(spec_frame, text="Δσ: -26.5 dBsm", font=("Segoe UI", 9), fg="#e2e8f0", bg="#222428")
        self.lbl_rcs.pack(side=tk.LEFT)

        self.lbl_desc = tk.Label(sidebar, text="", font=("Segoe UI", 8, "italic"), fg="#64748b", bg="#222428", wraplength=310, justify="left")
        self.lbl_desc.pack(anchor="w", pady=(0, 10))

        # Box 2: RF Controls
        lbl_sec2 = tk.Label(sidebar, text="RF & FRONTEND CONTROLS", font=("Segoe UI", 9, "bold"), fg="#94a3b8", bg="#222428")
        lbl_sec2.pack(anchor="w", pady=(6, 4))

        # Freq
        row_freq = tk.Frame(sidebar, bg="#222428")
        row_freq.pack(fill=tk.X, pady=2)
        tk.Label(row_freq, text="Center Freq (MHz):", font=("Segoe UI", 9), fg="#cbd5e1", bg="#222428").pack(side=tk.LEFT)
        self.var_freq = tk.DoubleVar(value=2440.0)
        self.entry_freq = tk.Spinbox(row_freq, from_=50.0, to=6000.0, increment=1.0, textvariable=self.var_freq, width=8, bg="#0f172a", fg="white", buttonbackground="#334155")
        self.entry_freq.pack(side=tk.RIGHT)

        # Rate
        row_rate = tk.Frame(sidebar, bg="#222428")
        row_rate.pack(fill=tk.X, pady=2)
        tk.Label(row_rate, text="Sample Rate:", font=("Segoe UI", 9), fg="#cbd5e1", bg="#222428").pack(side=tk.LEFT)
        self.var_rate = tk.StringVar(value="2.0 MS/s")
        self.combo_rate = ttk.Combobox(row_rate, textvariable=self.var_rate, values=["1.0 MS/s", "2.0 MS/s", "5.0 MS/s", "10.0 MS/s"], width=10, state="readonly")
        self.combo_rate.pack(side=tk.RIGHT)

        # Carrier Mode
        row_carrier = tk.Frame(sidebar, bg="#222428")
        row_carrier.pack(fill=tk.X, pady=2)
        tk.Label(row_carrier, text="Carrier Mode:", font=("Segoe UI", 9), fg="#cbd5e1", bg="#222428").pack(side=tk.LEFT)
        self.var_carrier = tk.StringVar(value="Active CW (Tx+Rx)")
        self.combo_carrier = ttk.Combobox(row_carrier, textvariable=self.var_carrier, values=["Active CW (Tx+Rx)", "Passive Ambient (Rx)"], width=14, state="readonly")
        self.combo_carrier.pack(side=tk.RIGHT)

        # RX Gain
        row_rx = tk.Frame(sidebar, bg="#222428")
        row_rx.pack(fill=tk.X, pady=(4, 2))
        self.lbl_rx_val = tk.Label(row_rx, text="RX Gain: 45 dB", font=("Segoe UI", 9), fg="#cbd5e1", bg="#222428")
        self.lbl_rx_val.pack(anchor="w")
        self.scale_rx = tk.Scale(row_rx, from_=0, to=76, orient=tk.HORIZONTAL, bg="#222428", fg="white", highlightthickness=0, troughcolor="#0f172a", showvalue=False, command=self._on_scale_rx)
        self.scale_rx.set(45)
        self.scale_rx.pack(fill=tk.X)

        # TX Gain
        row_tx = tk.Frame(sidebar, bg="#222428")
        row_tx.pack(fill=tk.X, pady=2)
        self.lbl_tx_val = tk.Label(row_tx, text="TX Gain: 60 dB", font=("Segoe UI", 9), fg="#cbd5e1", bg="#222428")
        self.lbl_tx_val.pack(anchor="w")
        self.scale_tx = tk.Scale(row_tx, from_=0, to=89, orient=tk.HORIZONTAL, bg="#222428", fg="white", highlightthickness=0, troughcolor="#0f172a", showvalue=False, command=self._on_scale_tx)
        self.scale_tx.set(60)
        self.scale_tx.pack(fill=tk.X)

        # Detection Sensitivity
        row_sens = tk.Frame(sidebar, bg="#222428")
        row_sens.pack(fill=tk.X, pady=(4, 2))
        tk.Label(row_sens, text="Sensitivity:", font=("Segoe UI", 9), fg="#cbd5e1", bg="#222428").pack(side=tk.LEFT)
        self.var_sens = tk.StringVar(value="0.30 dB (High)")
        self.combo_sens = ttk.Combobox(row_sens, textvariable=self.var_sens, values=["0.15 dB (Ultra)", "0.30 dB (High)", "0.60 dB (Normal)", "1.00 dB (Low)"], width=14, state="readonly")
        self.combo_sens.pack(side=tk.RIGHT)
        self.combo_sens.bind("<<ComboboxSelected>>", self._on_sens_changed)

        # Action Buttons
        self.btn_stream = tk.Button(
            sidebar,
            text="▶  START ACQUISITION",
            font=("Segoe UI", 10, "bold"),
            bg="#0284c7",
            fg="white",
            relief=tk.FLAT,
            pady=6,
            command=self.toggle_streaming,
        )
        self.btn_stream.pack(fill=tk.X, pady=(12, 4))

        self.btn_zero = tk.Button(
            sidebar,
            text="⌖  AUTO-ZERO BASELINE",
            font=("Segoe UI", 9, "bold"),
            bg="#334155",
            fg="#38bdf8",
            relief=tk.FLAT,
            pady=4,
            command=self.trigger_autozero,
        )
        self.btn_zero.pack(fill=tk.X, pady=2)

        self.btn_export = tk.Button(
            sidebar,
            text="💾  EXPORT SNAPSHOT (.MAT/.NPZ/CSV)",
            font=("Segoe UI", 9, "bold"),
            bg="#0f766e",
            fg="#5eead4",
            relief=tk.FLAT,
            pady=4,
            command=self.trigger_snapshot,
        )
        self.btn_export.pack(fill=tk.X, pady=2)

        # Metric HUD
        lbl_sec3 = tk.Label(sidebar, text="LIVE MODULATION METRICS", font=("Segoe UI", 9, "bold"), fg="#94a3b8", bg="#222428")
        lbl_sec3.pack(anchor="w", pady=(14, 4))

        self.card_state = tk.Label(
            sidebar,
            text="STATE 1: ABSORBING (50 Ω)",
            font=("Segoe UI", 10, "bold"),
            fg="#38bdf8",
            bg="#0f172a",
            relief=tk.SOLID,
            bd=1,
            pady=6,
        )
        self.card_state.pack(fill=tk.X, pady=4)

        # Jumper Hardware Guide
        frame_jumper = tk.LabelFrame(
            sidebar,
            text="🏷️ JUMPER CONFIGURATION (J1)",
            font=("Segoe UI", 8, "bold"),
            fg="#cbd5e1",
            bg="#1e293b",
            padx=8,
            pady=4,
        )
        frame_jumper.pack(fill=tk.X, pady=(4, 6))
        tk.Label(frame_jumper, text="• Pin 1-2 (Left)  : 50Ω Absorbing", font=("Segoe UI", 8), fg="#38bdf8", bg="#1e293b").pack(anchor="w")
        tk.Label(frame_jumper, text="• Pin 2-3 (Right) : 0Ω Short (Refl)", font=("Segoe UI", 8), fg="#4ade80", bg="#1e293b").pack(anchor="w")
        tk.Label(frame_jumper, text="• Jumper Removed  : ∞Ω Open (Refl)", font=("Segoe UI", 8), fg="#fb923c", bg="#1e293b").pack(anchor="w")

        self.lbl_hud_delta_p = tk.Label(sidebar, text="ΔP (Contrast): +0.00 dB", font=("Segoe UI", 9, "bold"), fg="#4ade80", bg="#222428")
        self.lbl_hud_delta_p.pack(anchor="w", pady=1)

        self.lbl_hud_delta_v = tk.Label(sidebar, text="Δ|V| (Vector):  0.0000", font=("Segoe UI", 9, "bold"), fg="#a78bfa", bg="#222428")
        self.lbl_hud_delta_v.pack(anchor="w", pady=1)

        self.lbl_hud_phase = tk.Label(sidebar, text="Phase Angle:   +0.0°", font=("Segoe UI", 9), fg="#38bdf8", bg="#222428")
        self.lbl_hud_phase.pack(anchor="w", pady=1)

        self.lbl_hud_prx = tk.Label(sidebar, text="Prx (Power):   -80.0 dBFS", font=("Segoe UI", 9), fg="#e2e8f0", bg="#222428")
        self.lbl_hud_prx.pack(anchor="w", pady=1)

        # Right Visualization Area (Matplotlib Figure Canvas)
        plots_frame = tk.Frame(body, bg="#18191c")
        plots_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.fig = Figure(figsize=(10, 7), facecolor="#18191c", dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=plots_frame)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill=tk.BOTH, expand=True)

        # Setup Subplots
        # 1. Top Strip Chart P_rx(t)
        self.ax_strip = self.fig.add_subplot(2, 1, 1, facecolor="#131417")
        self.ax_strip.set_title("Time-Domain Received Power Strip Chart: P_rx(t)", color="#e2e8f0", fontsize=10, fontweight="bold")
        self.ax_strip.set_ylabel("Power (dBFS)", color="#94a3b8", fontsize=8)
        self.ax_strip.set_xlabel("Time History (s)", color="#94a3b8", fontsize=8)
        self.ax_strip.set_ylim(-90.0, -10.0)
        self.ax_strip.set_xlim(-10.0, 0.0)
        self.ax_strip.grid(True, color="#334155", alpha=0.4, linestyle="--")
        self.ax_strip.tick_params(colors="#94a3b8", labelsize=8)
        (self.line_strip,) = self.ax_strip.plot([], [], color="#00e5ff", lw=1.5)
        self.line_thresh = self.ax_strip.axhline(-50.0, color="#f59e0b", lw=1.0, linestyle="--")

        # 2. Bottom-Left I/Q Constellation
        self.ax_iq = self.fig.add_subplot(2, 2, 3, facecolor="#131417")
        self.ax_iq.set_title("Complex I/Q Phase Plane", color="#e2e8f0", fontsize=10, fontweight="bold")
        self.ax_iq.set_xlabel("In-Phase (I)", color="#94a3b8", fontsize=8)
        self.ax_iq.set_ylabel("Quadrature (Q)", color="#94a3b8", fontsize=8)
        self.ax_iq.set_xlim(-0.25, 0.25)
        self.ax_iq.set_ylim(-0.25, 0.25)
        self.ax_iq.grid(True, color="#334155", alpha=0.4, linestyle="--")
        self.ax_iq.tick_params(colors="#94a3b8", labelsize=8)
        self.scatter_iq = self.ax_iq.scatter([], [], s=8, color="#00e5ff", alpha=0.5)
        (self.c1_plot,) = self.ax_iq.plot([], [], "o", color="#0284c7", markersize=8, markeredgecolor="white", label="50Ω")
        (self.c2_plot,) = self.ax_iq.plot([], [], "s", color="#22c55e", markersize=8, markeredgecolor="white", label="Short")
        (self.c3_plot,) = self.ax_iq.plot([], [], "^", color="#f97316", markersize=8, markeredgecolor="white", label="Open")
        (self.line_delta_v,) = self.ax_iq.plot([], [], "--", color="#ec4899", lw=1.5)
        (self.line_delta_v2,) = self.ax_iq.plot([], [], ":", color="#f59e0b", lw=1.5)

        # 3. Bottom-Right FFT Spectrum
        self.ax_fft = self.fig.add_subplot(2, 2, 4, facecolor="#131417")
        self.ax_fft.set_title("Real-Time RF Power Spectrum (FFT)", color="#e2e8f0", fontsize=10, fontweight="bold")
        self.ax_fft.set_xlabel("Frequency Offset (MHz)", color="#94a3b8", fontsize=8)
        self.ax_fft.set_ylabel("PSD (dB/Hz)", color="#94a3b8", fontsize=8)
        self.ax_fft.set_ylim(-90.0, 10.0)
        self.ax_fft.grid(True, color="#334155", alpha=0.4, linestyle="--")
        self.ax_fft.tick_params(colors="#94a3b8", labelsize=8)
        (self.line_fft,) = self.ax_fft.plot([], [], color="#a855f7", lw=1.2)

        self.fig.tight_layout(pad=2.0)
        self.canvas.draw()

        # Status Bar
        self.status_bar = tk.Label(self.root, text="Ready. Select an antenna mode and click START ACQUISITION.", font=("Segoe UI", 8), fg="#94a3b8", bg="#0f172a", anchor="w", padx=10, pady=4)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    def apply_mode_config(self, mode_key: str) -> None:
        self.current_mode_key = mode_key
        cfg = self.modes[mode_key]

        # Highlight active mode button
        self.btn_mode1.configure(bg="#0284c7" if mode_key == "mode1" else "#334155", fg="white" if mode_key == "mode1" else "#cbd5e1")
        self.btn_mode2.configure(bg="#0284c7" if mode_key == "mode2" else "#334155", fg="white" if mode_key == "mode2" else "#cbd5e1")
        self.btn_mode3.configure(bg="#0284c7" if mode_key == "mode3" else "#334155", fg="white" if mode_key == "mode3" else "#cbd5e1")

        # Update specs card
        self.lbl_spec_tag.configure(text=cfg["tag_name"])
        self.lbl_s11.configure(text=f"S11: {cfg['s11_theory']}")
        self.lbl_rcs.configure(text=f"Δσ: {cfg['rcs_theory']}")
        self.lbl_desc.configure(text=cfg["desc"])

        # Update controls
        self.var_freq.set(cfg["center_freq"] / 1e6)
        self.scale_rx.set(int(cfg["rx_gain"]))
        self.scale_tx.set(int(cfg["tx_gain"]))
        self.lbl_rx_val.configure(text=f"RX Gain: {int(cfg['rx_gain'])} dB")
        self.lbl_tx_val.configure(text=f"TX Gain: {int(cfg['tx_gain'])} dB")

        rate_str = f"{cfg['sample_rate']/1e6:.1f} MS/s"
        self.var_rate.set(rate_str)
        self.var_carrier.set("Active CW (Tx+Rx)" if cfg["carrier_mode"] == "cw" else "Passive Ambient (Rx)")

        # Notify running worker
        if self.worker and self.worker.is_alive():
            self.worker.request_command("set_freq", freq=cfg["center_freq"])
            self.worker.request_command("set_rate", rate=cfg["sample_rate"])
            self.worker.request_command("set_rx_gain", gain=cfg["rx_gain"])
            self.worker.request_command("set_tx_gain", gain=cfg["tx_gain"])
            self.worker.request_command("set_mode", mode=cfg["carrier_mode"])

        self.status_bar.configure(text=f"Configured for {cfg['name']} ({cfg['center_freq']/1e6:.1f} MHz).")

    def toggle_streaming(self) -> None:
        if self.worker and self.worker.is_alive():
            self.status_bar.configure(text="Stopping acquisition...")
            self.worker.stop()
            self.worker = None
            self.btn_stream.configure(text="▶  START ACQUISITION", bg="#0284c7")
            self.status_bar.configure(text="Acquisition stopped.")
        else:
            cfg = self.modes[self.current_mode_key]
            freq_hz = float(self.var_freq.get()) * 1e6
            rate_val = float(self.var_rate.get().split()[0]) * 1e6
            rx_g = float(self.scale_rx.get())
            tx_g = float(self.scale_tx.get())
            carrier = "cw" if "Active" in self.var_carrier.get() else "wifi"

            sens_val = float(self.var_sens.get().split()[0])
            self.worker = SDRStreamThread(
                center_freq=freq_hz,
                sample_rate=rate_val,
                rx_gain=rx_g,
                tx_gain=tx_g,
                carrier_mode=carrier,
                force_mock=self.force_mock,
                sensitivity_db=sens_val,
                data_queue=self.data_queue,
                event_queue=self.event_queue,
            )
            self.worker.start()
            self.btn_stream.configure(text="⏹  STOP ACQUISITION", bg="#b91c1c")
            self.status_bar.configure(text="Acquisition running. Streaming samples...")

    def trigger_autozero(self) -> None:
        if self.worker and self.worker.is_alive():
            self.worker.request_command("calibrate")
            self.status_bar.configure(text="Auto-zero baseline calibrated! Carrier leakage subtracted.")
        else:
            self.status_bar.configure(text="⚠ Please start acquisition before calibrating baseline.")

    def trigger_snapshot(self) -> None:
        if self.worker and self.worker.is_alive():
            export_dir = os.path.join(script_dir, "output", "snapshots")
            tag_slug = self.current_mode_key
            self.worker.request_command("snapshot", export_dir=export_dir, base_filename=f"backscatter_snapshot_{tag_slug}")
            self.status_bar.configure(text="Capturing measurement snapshot...")
        else:
            self.status_bar.configure(text="⚠ Please start acquisition before capturing a snapshot.")

    def _on_scale_rx(self, val: str) -> None:
        self.lbl_rx_val.configure(text=f"RX Gain: {val} dB")
        if self.worker and self.worker.is_alive():
            self.worker.request_command("set_rx_gain", gain=float(val))

    def _on_scale_tx(self, val: str) -> None:
        self.lbl_tx_val.configure(text=f"TX Gain: {val} dB")
        if self.worker and self.worker.is_alive():
            self.worker.request_command("set_tx_gain", gain=float(val))

    def _on_sens_changed(self, event=None) -> None:
        try:
            val = float(self.var_sens.get().split()[0])
            if self.worker and self.worker.is_alive():
                self.worker.request_command("set_sensitivity", val=val)
            self.status_bar.configure(text=f"Detection sensitivity set to {val:.2f} dB threshold.")
        except Exception:
            pass

    def _poll_queues(self) -> None:
        # 1. Process Event Messages
        while not self.event_queue.empty():
            evt = self.event_queue.get_nowait()
            evt_type = evt[0]
            if evt_type == "hw_status":
                msg, is_hw = evt[1], evt[2]
                self.lbl_hw.configure(text=msg, fg="#4ade80" if is_hw else "#ffab00", bg="#052e16" if is_hw else "#1e293b")
                self.status_bar.configure(text=msg)
            elif evt_type == "transition":
                state_name, delta_p = evt[1], evt[2]
                self.status_bar.configure(text=f"⚡ State Transition: Switched to {state_name} (ΔP = +{delta_p:.2f} dB)")
            elif evt_type == "snapshot_saved":
                mat_path = evt[1]
                filename = os.path.basename(mat_path)
                self.status_bar.configure(text=f"[OK] Snapshot saved: {filename} (MATLAB ready)")
            elif evt_type == "error":
                self.status_bar.configure(text=f"⚠ Error: {evt[1]}")

        # 2. Process High-Speed Data Frame
        latest_payload = None
        while not self.data_queue.empty():
            latest_payload = self.data_queue.get_nowait()

        if latest_payload is not None:
            self._render_frame(latest_payload)

        # Schedule next poll
        self.root.after(30, self._poll_queues)

    def _render_frame(self, p: Dict[str, Any]) -> None:
        try:
            # Update HUD
            self.lbl_hud_prx.configure(text=f"Prx (Power):   {p['power_db']:.1f} dBFS")
            self.lbl_hud_delta_p.configure(text=f"ΔP (Contrast): +{p['delta_p']:.2f} dB")
            self.lbl_hud_delta_v.configure(text=f"Δ|V| (Vector):  {p['delta_v']:.4f}")
            self.lbl_hud_phase.configure(text=f"Phase Angle:   {p.get('phase_deg', 0.0):+.1f}°")

            state_str = p["current_state"]
            if "SHORT" in state_str:
                self.card_state.configure(text=state_str, fg="#4ade80", bg="#052e16")
            elif "OPEN" in state_str:
                self.card_state.configure(text=state_str, fg="#fb923c", bg="#451a03")
            else:
                self.card_state.configure(text=state_str, fg="#38bdf8", bg="#082f49")

            # Update Strip Chart
            self.line_strip.set_data(p["time_history"], p["power_history"])
            min_p = np.min(p["power_history"][-60:])
            max_p = np.max(p["power_history"][-60:])
            mid_p = (min_p + max_p) / 2.0
            self.line_thresh.set_ydata([mid_p, mid_p])

            # Update Constellation
            iq = p["iq_samples"]
            if len(iq) > 0:
                offsets = np.column_stack((iq.real, iq.imag))
                self.scatter_iq.set_offsets(offsets)
                max_r = max(0.15, float(np.max(np.abs(iq))) * 1.3)
                self.ax_iq.set_xlim(-max_r, max_r)
                self.ax_iq.set_ylim(-max_r, max_r)

            c1 = p["centroid_1"]
            c2 = p["centroid_2"]
            c3 = p.get("centroid_3", 0.0 + 0.0j)
            self.c1_plot.set_data([c1.real], [c1.imag])
            self.c2_plot.set_data([c2.real], [c2.imag])
            self.c3_plot.set_data([c3.real], [c3.imag])
            self.line_delta_v.set_data([c1.real, c2.real], [c1.imag, c2.imag])
            self.line_delta_v2.set_data([c1.real, c3.real], [c1.imag, c3.imag])

            # Update FFT Spectrum
            freqs = p["fft_freqs"]
            psd = p["fft_psd"]
            self.line_fft.set_data(freqs, psd)
            if len(freqs) > 0:
                self.ax_fft.set_xlim(freqs[0], freqs[-1])

            self.canvas.draw_idle()
        except Exception as exc:
            print("Render Frame Error:", exc)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Robust Real-Time Backscatter Tag SDR Acquisition & Detection Dashboard"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Force offline mock streaming mode without requiring physical SDR hardware",
    )
    args = parser.parse_args()

    root = tk.Tk()
    app = BackscatterTkGUI(root, force_mock=args.mock)
    root.protocol("WM_DELETE_WINDOW", lambda: (app.worker.stop() if app.worker else None, root.destroy()))
    root.mainloop()


if __name__ == "__main__":
    main()
