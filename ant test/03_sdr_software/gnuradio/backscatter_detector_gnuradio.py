#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: Backscatter Tag SDR Detection Dashboard (GNU Radio)
# Author: Hesam Jafari (@hjafari890)
# Description: Coherent Lock-In Dual-Carrier SDR Detection Suite for Passive Backscatter Tags
# GNU Radio version: 3.10.12.0

import os
import signal
import sys
import time
from argparse import ArgumentParser

try:
    from PyQt5 import Qt, QtCore
    from PyQt5.QtCore import QObject, pyqtSlot
    from gnuradio import analog, blocks, filter, gr, qtgui
    from gnuradio.fft import window
    from gnuradio.filter import firdes
    from gnuradio.eng_arg import eng_float, intx
    from gnuradio import eng_notation, uhd
    import sip
    import threading
    HAS_GNURADIO = True
except ImportError as _import_err:
    HAS_GNURADIO = False
    _import_err_msg = str(_import_err)
    class _DummyTopBlock:
        pass

    class _DummyWidget:
        pass

    _BaseTopBlock = _DummyTopBlock
    _BaseWidget = _DummyWidget
else:
    _BaseTopBlock = gr.top_block
    _BaseWidget = Qt.QWidget


class backscatter_detector_gnuradio(_BaseTopBlock, _BaseWidget):

    def __init__(self):
        gr.top_block.__init__(self, "Backscatter Tag SDR Detection Dashboard (GNU Radio)", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("Backscatter Tag SDR Detection Dashboard (GNU Radio)")
        qtgui.util.check_set_qss()
        try:
            self.setWindowIcon(Qt.QIcon.fromTheme('gnuradio-grc'))
        except BaseException as exc:
            print(f"Qt GUI: Could not set Icon: {str(exc)}", file=sys.stderr)
        self.top_scroll_layout = Qt.QVBoxLayout()
        self.setLayout(self.top_scroll_layout)
        self.top_scroll = Qt.QScrollArea()
        self.top_scroll.setFrameStyle(Qt.QFrame.NoFrame)
        self.top_scroll_layout.addWidget(self.top_scroll)
        self.top_scroll.setWidgetResizable(True)
        self.top_widget = Qt.QWidget()
        self.top_scroll.setWidget(self.top_widget)
        self.top_layout = Qt.QVBoxLayout(self.top_widget)
        self.top_grid_layout = Qt.QGridLayout()
        self.top_layout.addLayout(self.top_grid_layout)

        self.settings = Qt.QSettings("gnuradio/flowgraphs", "backscatter_detector_gnuradio")

        try:
            geometry = self.settings.value("geometry")
            if geometry:
                self.restoreGeometry(geometry)
        except BaseException as exc:
            print(f"Qt GUI: Could not restore geometry: {str(exc)}", file=sys.stderr)
        self.flowgraph_started = threading.Event()

        ##################################################
        # Variables
        ##################################################
        self.samp_rate = samp_rate = 2e6
        self.tx_gain = tx_gain = 60
        self.rx_gain = rx_gain = 50
        self.lpf_taps = lpf_taps = firdes.low_pass(1.0, samp_rate, 1000, 400, window.WIN_HAMMING, 6.76)
        self.if_freq = if_freq = 100e3
        self.decim = decim = 200
        self.center_freq = center_freq = 2440e6

        ##################################################
        # Blocks
        ##################################################

        self._tx_gain_range = qtgui.Range(0, 89, 1, 60, 200)
        self._tx_gain_win = qtgui.RangeWidget(self._tx_gain_range, self.set_tx_gain, "TX Gain (dB)", "slider", float, QtCore.Qt.Horizontal)
        self.top_grid_layout.addWidget(self._tx_gain_win, 0, 2, 1, 1)
        for r in range(0, 1):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(2, 3):
            self.top_grid_layout.setColumnStretch(c, 1)
        self._rx_gain_range = qtgui.Range(0, 76, 1, 50, 200)
        self._rx_gain_win = qtgui.RangeWidget(self._rx_gain_range, self.set_rx_gain, "RX Gain (dB)", "slider", float, QtCore.Qt.Horizontal)
        self.top_grid_layout.addWidget(self._rx_gain_win, 0, 1, 1, 1)
        for r in range(0, 1):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(1, 2):
            self.top_grid_layout.setColumnStretch(c, 1)
        # Create the options list
        self._center_freq_options = [2440000000.0, 868000000.0, 2437000000.0]
        # Create the labels list
        self._center_freq_labels = ['Mode 1: 2.44 GHz IFA Tag (2440 MHz)', 'Mode 2: Sub-1GHz Meander Tag (868 MHz)', 'Mode 3: Leggiero Bowtie Tag (2437 MHz)']
        # Create the combo box
        # Create the radio buttons
        self._center_freq_group_box = Qt.QGroupBox("Operating Mode / Tag Frequency" + ": ")
        self._center_freq_box = Qt.QVBoxLayout()
        class variable_chooser_button_group(Qt.QButtonGroup):
            def __init__(self, parent=None):
                Qt.QButtonGroup.__init__(self, parent)
            @pyqtSlot(int)
            def updateButtonChecked(self, button_id):
                self.button(button_id).setChecked(True)
        self._center_freq_button_group = variable_chooser_button_group()
        self._center_freq_group_box.setLayout(self._center_freq_box)
        for i, _label in enumerate(self._center_freq_labels):
            radio_button = Qt.QRadioButton(_label)
            self._center_freq_box.addWidget(radio_button)
            self._center_freq_button_group.addButton(radio_button, i)
        self._center_freq_callback = lambda i: Qt.QMetaObject.invokeMethod(self._center_freq_button_group, "updateButtonChecked", Qt.Q_ARG("int", self._center_freq_options.index(i)))
        self._center_freq_callback(self.center_freq)
        self._center_freq_button_group.buttonClicked[int].connect(
            lambda i: self.set_center_freq(self._center_freq_options[i]))
        self.top_grid_layout.addWidget(self._center_freq_group_box, 0, 0, 1, 1)
        for r in range(0, 1):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 1):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.uhd_usrp_source_0 = uhd.usrp_source(
            ",".join(("type=b200", "")),
            uhd.stream_args(
                cpu_format="fc32",
                otw_format="sc16",
                args="",
                channels=list(range(0,1)),
            ),
        )
        self.uhd_usrp_source_0.set_samp_rate(samp_rate)
        self.uhd_usrp_source_0.set_time_unknown_pps(uhd.time_spec(0))

        self.uhd_usrp_source_0.set_center_freq(center_freq, 0)
        self.uhd_usrp_source_0.set_antenna("RX2", 0)
        self.uhd_usrp_source_0.set_rx_agc(False, 0)
        self.uhd_usrp_source_0.set_gain(rx_gain, 0)
        self.uhd_usrp_sink_0 = uhd.usrp_sink(
            ",".join(("type=b200", "")),
            uhd.stream_args(
                cpu_format="fc32",
                otw_format="sc16",
                args="",
                channels=list(range(0,1)),
            ),
            "",
        )
        self.uhd_usrp_sink_0.set_samp_rate(samp_rate)
        self.uhd_usrp_sink_0.set_time_unknown_pps(uhd.time_spec(0))

        self.uhd_usrp_sink_0.set_center_freq(center_freq, 0)
        self.uhd_usrp_sink_0.set_antenna("TX/RX", 0)
        self.uhd_usrp_sink_0.set_gain(tx_gain, 0)
        self.qtgui_time_sink_x_power = qtgui.time_sink_f(
            1000, #size
            samp_rate / decim, #samp_rate
            "Demodulated Backscatter Power Strip Chart (dBFS)", #name
            1, #number of inputs
            None # parent
        )
        self.qtgui_time_sink_x_power.set_update_time(0.05)
        self.qtgui_time_sink_x_power.set_y_axis(-90, -10)

        self.qtgui_time_sink_x_power.set_y_label('Power (dBFS)', "")

        self.qtgui_time_sink_x_power.enable_tags(False)
        self.qtgui_time_sink_x_power.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, 0, "")
        self.qtgui_time_sink_x_power.enable_autoscale(False)
        self.qtgui_time_sink_x_power.enable_grid(True)
        self.qtgui_time_sink_x_power.enable_axis_labels(True)
        self.qtgui_time_sink_x_power.enable_control_panel(False)
        self.qtgui_time_sink_x_power.enable_stem_plot(False)


        labels = ['Demodulated Power Prx(t)', 'Signal 2', 'Signal 3', 'Signal 4', 'Signal 5',
            'Signal 6', 'Signal 7', 'Signal 8', 'Signal 9', 'Signal 10']
        widths = [2, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ['cyan', 'red', 'green', 'black', 'cyan',
            'magenta', 'yellow', 'dark red', 'dark green', 'dark blue']
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]
        styles = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        markers = [-1, -1, -1, -1, -1,
            -1, -1, -1, -1, -1]


        for i in range(1):
            if len(labels[i]) == 0:
                self.qtgui_time_sink_x_power.set_line_label(i, "Data {0}".format(i))
            else:
                self.qtgui_time_sink_x_power.set_line_label(i, labels[i])
            self.qtgui_time_sink_x_power.set_line_width(i, widths[i])
            self.qtgui_time_sink_x_power.set_line_color(i, colors[i])
            self.qtgui_time_sink_x_power.set_line_style(i, styles[i])
            self.qtgui_time_sink_x_power.set_line_marker(i, markers[i])
            self.qtgui_time_sink_x_power.set_line_alpha(i, alphas[i])

        self._qtgui_time_sink_x_power_win = sip.wrapinstance(self.qtgui_time_sink_x_power.qwidget(), Qt.QWidget)
        self.top_grid_layout.addWidget(self._qtgui_time_sink_x_power_win, 1, 0, 1, 2)
        for r in range(1, 2):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 2):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.qtgui_freq_sink_x_0 = qtgui.freq_sink_c(
            1024, #size
            window.WIN_BLACKMAN_hARRIS, #wintype
            0, #fc
            samp_rate, #bw
            "Raw RF Spectrum across RX2 Channel", #name
            1,
            None # parent
        )
        self.qtgui_freq_sink_x_0.set_update_time(0.05)
        self.qtgui_freq_sink_x_0.set_y_axis((-100), (-20))
        self.qtgui_freq_sink_x_0.set_y_label('Relative Gain', 'dB')
        self.qtgui_freq_sink_x_0.set_trigger_mode(qtgui.TRIG_MODE_FREE, 0.0, 0, "")
        self.qtgui_freq_sink_x_0.enable_autoscale(False)
        self.qtgui_freq_sink_x_0.enable_grid(True)
        self.qtgui_freq_sink_x_0.set_fft_average(0.2)
        self.qtgui_freq_sink_x_0.enable_axis_labels(True)
        self.qtgui_freq_sink_x_0.enable_control_panel(False)
        self.qtgui_freq_sink_x_0.set_fft_window_normalized(False)



        labels = ['Raw RX Spectrum (Tone at +100 kHz)', '', '', '', '',
            '', '', '', '', '']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ["blue", "red", "green", "black", "cyan",
            "magenta", "yellow", "dark red", "dark green", "dark blue"]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.qtgui_freq_sink_x_0.set_line_label(i, "Data {0}".format(i))
            else:
                self.qtgui_freq_sink_x_0.set_line_label(i, labels[i])
            self.qtgui_freq_sink_x_0.set_line_width(i, widths[i])
            self.qtgui_freq_sink_x_0.set_line_color(i, colors[i])
            self.qtgui_freq_sink_x_0.set_line_alpha(i, alphas[i])

        self._qtgui_freq_sink_x_0_win = sip.wrapinstance(self.qtgui_freq_sink_x_0.qwidget(), Qt.QWidget)
        self.top_grid_layout.addWidget(self._qtgui_freq_sink_x_0_win, 2, 1, 1, 1)
        for r in range(2, 3):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(1, 2):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.qtgui_const_sink_x_0 = qtgui.const_sink_c(
            200, #size
            "Demodulated Backscatter I/Q Constellation", #name
            1, #number of inputs
            None # parent
        )
        self.qtgui_const_sink_x_0.set_update_time(0.05)
        self.qtgui_const_sink_x_0.set_y_axis((-0.1), 0.1)
        self.qtgui_const_sink_x_0.set_x_axis((-0.1), 0.1)
        self.qtgui_const_sink_x_0.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, "")
        self.qtgui_const_sink_x_0.enable_autoscale(False)
        self.qtgui_const_sink_x_0.enable_grid(True)
        self.qtgui_const_sink_x_0.enable_axis_labels(True)


        labels = ['Demodulated I/Q Vector', '', '', '', '',
            '', '', '', '', '']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ["blue", "red", "green", "black", "cyan",
            "magenta", "yellow", "dark red", "dark green", "dark blue"]
        styles = [0, 0, 0, 0, 0,
            0, 0, 0, 0, 0]
        markers = [0, 0, 0, 0, 0,
            0, 0, 0, 0, 0]
        alphas = [0.8, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.qtgui_const_sink_x_0.set_line_label(i, "Data {0}".format(i))
            else:
                self.qtgui_const_sink_x_0.set_line_label(i, labels[i])
            self.qtgui_const_sink_x_0.set_line_width(i, widths[i])
            self.qtgui_const_sink_x_0.set_line_color(i, colors[i])
            self.qtgui_const_sink_x_0.set_line_style(i, styles[i])
            self.qtgui_const_sink_x_0.set_line_marker(i, markers[i])
            self.qtgui_const_sink_x_0.set_line_alpha(i, alphas[i])

        self._qtgui_const_sink_x_0_win = sip.wrapinstance(self.qtgui_const_sink_x_0.qwidget(), Qt.QWidget)
        self.top_grid_layout.addWidget(self._qtgui_const_sink_x_0_win, 2, 0, 1, 1)
        for r in range(2, 3):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 1):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.fir_filter_xxx_0 = filter.fir_filter_ccf(decim, lpf_taps)
        self.fir_filter_xxx_0.declare_sample_delay(0)
        self.blocks_nlog10_ff_0 = blocks.nlog10_ff(10, 1, 0)
        self.blocks_multiply_xx_0 = blocks.multiply_vcc(1)
        self.blocks_complex_to_mag_squared_0 = blocks.complex_to_mag_squared(1)
        self.analog_sig_source_tx = analog.sig_source_c(samp_rate, analog.GR_COS_WAVE, if_freq, 0.707, 0, 0)
        self.analog_sig_source_ref = analog.sig_source_c(samp_rate, analog.GR_COS_WAVE, (-if_freq), 1.0, 0, 0)


        ##################################################
        # Connections
        ##################################################
        self.connect((self.analog_sig_source_ref, 0), (self.blocks_multiply_xx_0, 1))
        self.connect((self.analog_sig_source_tx, 0), (self.uhd_usrp_sink_0, 0))
        self.connect((self.blocks_complex_to_mag_squared_0, 0), (self.blocks_nlog10_ff_0, 0))
        self.connect((self.blocks_multiply_xx_0, 0), (self.fir_filter_xxx_0, 0))
        self.connect((self.blocks_nlog10_ff_0, 0), (self.qtgui_time_sink_x_power, 0))
        self.connect((self.fir_filter_xxx_0, 0), (self.blocks_complex_to_mag_squared_0, 0))
        self.connect((self.fir_filter_xxx_0, 0), (self.qtgui_const_sink_x_0, 0))
        self.connect((self.uhd_usrp_source_0, 0), (self.blocks_multiply_xx_0, 0))
        self.connect((self.uhd_usrp_source_0, 0), (self.qtgui_freq_sink_x_0, 0))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("gnuradio/flowgraphs", "backscatter_detector_gnuradio")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()

        event.accept()

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.set_lpf_taps(firdes.low_pass(1.0, self.samp_rate, 1000, 400, window.WIN_HAMMING, 6.76))
        self.analog_sig_source_tx.set_sampling_freq(self.samp_rate)
        self.uhd_usrp_sink_0.set_samp_rate(self.samp_rate)
        self.uhd_usrp_source_0.set_samp_rate(self.samp_rate)
        self.analog_sig_source_ref.set_sampling_freq(self.samp_rate)
        self.qtgui_time_sink_x_power.set_samp_rate(self.samp_rate / self.decim)
        self.qtgui_freq_sink_x_0.set_frequency_range(0, self.samp_rate)

    def get_tx_gain(self):
        return self.tx_gain

    def set_tx_gain(self, tx_gain):
        self.tx_gain = tx_gain
        self.uhd_usrp_sink_0.set_gain(self.tx_gain, 0)

    def get_rx_gain(self):
        return self.rx_gain

    def set_rx_gain(self, rx_gain):
        self.rx_gain = rx_gain
        self.uhd_usrp_source_0.set_gain(self.rx_gain, 0)

    def get_lpf_taps(self):
        return self.lpf_taps

    def set_lpf_taps(self, lpf_taps):
        self.lpf_taps = lpf_taps
        self.fir_filter_xxx_0.set_taps(self.lpf_taps)

    def get_if_freq(self):
        return self.if_freq

    def set_if_freq(self, if_freq):
        self.if_freq = if_freq
        self.analog_sig_source_tx.set_frequency(self.if_freq)
        self.analog_sig_source_ref.set_frequency((-self.if_freq))

    def get_decim(self):
        return self.decim

    def set_decim(self, decim):
        self.decim = decim
        self.qtgui_time_sink_x_power.set_samp_rate(self.samp_rate / self.decim)

    def get_center_freq(self):
        return self.center_freq

    def set_center_freq(self, center_freq):
        self.center_freq = center_freq
        self._center_freq_callback(self.center_freq)
        self.uhd_usrp_sink_0.set_center_freq(self.center_freq, 0)
        self.uhd_usrp_source_0.set_center_freq(self.center_freq, 0)




def main(top_block_cls=None, options=None):
    parser = ArgumentParser(
        description="Coherent Lock-In Dual-Carrier SDR Detection Suite for Passive Backscatter Tags (GNU Radio)"
    )
    # Parse CLI flags (handles --help and -h cleanly)
    parser.parse_args(sys.argv[1:])

    if not HAS_GNURADIO:
        print("\n" + "=" * 70, file=sys.stderr)
        print(" [ERROR] GNU Radio / PyQt5 environment not detected:", file=sys.stderr)
        print(f" {_import_err_msg}", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        print("\nPossible solutions:", file=sys.stderr)
        print("  1. Launch via Radioconda: open_gnuradio_companion.bat or launch_gnuradio_gui.bat", file=sys.stderr)
        print("  2. Activate a Python environment with gnuradio and PyQt5 installed.", file=sys.stderr)
        print("  3. For offline simulation without GNU Radio, launch the Python SDR GUI:", file=sys.stderr)
        print("     python software/backscatter_gui_app.py --mock\n", file=sys.stderr)
        return 1

    if top_block_cls is None:
        top_block_cls = backscatter_detector_gnuradio

    qapp = Qt.QApplication(sys.argv)

    try:
        tb = top_block_cls()
    except RuntimeError as exc:
        print("\n" + "=" * 70, file=sys.stderr)
        print(" [WARNING] UHD USRP Hardware Initialization Notice:", file=sys.stderr)
        print(f" {str(exc).strip()}", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        print("\nPossible solutions:", file=sys.stderr)
        print("  1. Connect an NI USRP-2900 or Ettus B200 transceiver via USB 3.0.", file=sys.stderr)
        print("  2. Verify UHD drivers with: uhd_find_devices", file=sys.stderr)
        print("  3. For offline simulation without hardware, launch the Python SDR GUI:", file=sys.stderr)
        print("     python software/backscatter_gui_app.py --mock\n", file=sys.stderr)
        return 1

    tb.start()
    tb.flowgraph_started.set()

    tb.show()

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()

        Qt.QApplication.quit()

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    timer = Qt.QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    return qapp.exec_()

if __name__ == '__main__':
    sys.exit(main() or 0)

