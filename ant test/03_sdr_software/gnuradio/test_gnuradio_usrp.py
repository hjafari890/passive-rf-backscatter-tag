"""Headless test: GNU Radio full-duplex TX+RX on NI USRP-2900 with lock-in demod."""

from gnuradio import gr, uhd, analog, blocks, filter as grfilter, fft
from gnuradio.filter import firdes
import numpy as np
import sys
import time


class BackscatterHeadlessTest(gr.top_block):
    def __init__(self):
        gr.top_block.__init__(self, "Backscatter Headless Test", catch_exceptions=True)

        samp_rate = 2e6
        center_freq = 2.44e9
        if_freq = 100e3
        capture_seconds = 2.0
        decim = 200  # output rate = 10 kS/s

        # ── TX Chain ──
        self.tx_sink = uhd.usrp_sink(
            ",".join(("type=b200", "")),
            uhd.stream_args(cpu_format="fc32", otw_format="sc16", channels=[0]),
            "",
        )
        self.tx_sink.set_samp_rate(samp_rate)
        self.tx_sink.set_center_freq(center_freq, 0)
        self.tx_sink.set_gain(60, 0)
        self.tx_sink.set_antenna("TX/RX", 0)

        self.tx_tone = analog.sig_source_c(
            samp_rate, analog.GR_COS_WAVE, if_freq, 0.707, 0
        )

        # ── RX Chain ──
        self.rx_source = uhd.usrp_source(
            ",".join(("type=b200", "")),
            uhd.stream_args(cpu_format="fc32", otw_format="sc16", channels=[0]),
        )
        self.rx_source.set_samp_rate(samp_rate)
        self.rx_source.set_center_freq(center_freq, 0)
        self.rx_source.set_gain(50, 0)
        self.rx_source.set_antenna("RX2", 0)

        # Lock-in reference tone: exp(-j * 2*pi * 100kHz * t)
        self.rx_ref = analog.sig_source_c(
            samp_rate, analog.GR_COS_WAVE, -if_freq, 1.0, 0
        )

        # Mixer (lock-in multiplication)
        self.mixer = blocks.multiply_cc()

        # Lock-in Low Pass Filter with decimation
        lpf_taps = firdes.low_pass(
            1.0, samp_rate, 500, 200, fft.window.WIN_HAMMING
        )
        self.lpf = grfilter.fir_filter_ccf(decim, lpf_taps)

        # Limit capture duration
        output_samples = int((samp_rate / decim) * capture_seconds)
        self.head = blocks.head(gr.sizeof_gr_complex, output_samples)

        # Data sink
        self.data_sink = blocks.vector_sink_c()

        # ── Connections ──
        self.connect(self.tx_tone, self.tx_sink)

        self.connect(self.rx_source, (self.mixer, 0))
        self.connect(self.rx_ref, (self.mixer, 1))
        self.connect(self.mixer, self.lpf, self.head, self.data_sink)


def main():
    print("[GR-TEST] Building GNU Radio flowgraph...", flush=True)
    tb = BackscatterHeadlessTest()

    print("[GR-TEST] Starting full-duplex TX+RX streaming...", flush=True)
    t0 = time.time()
    tb.start()
    tb.wait()
    elapsed = time.time() - t0

    data = np.array(tb.data_sink.data())
    print(f"[GR-TEST] Captured {len(data)} demodulated samples in {elapsed:.2f}s", flush=True)

    if len(data) < 100:
        print("[GR-TEST] [FAIL] Too few samples captured!", flush=True)
        return False

    # Analyse the last 1 second of stable data
    half = len(data) // 2
    stable = data[half:]

    mag = np.abs(stable)
    mean_mag = np.mean(mag)
    std_mag = np.std(mag)
    mean_power_db = 20.0 * np.log10(max(mean_mag, 1e-12))
    phase_deg = np.degrees(np.mean(np.angle(stable)))

    print(f"[GR-TEST] Lock-in carrier magnitude : {mean_mag:.6f}", flush=True)
    print(f"[GR-TEST] Lock-in carrier power     : {mean_power_db:.2f} dBFS", flush=True)
    print(f"[GR-TEST] Lock-in carrier phase     : {phase_deg:.1f} deg", flush=True)
    print(f"[GR-TEST] Magnitude stability (std) : {std_mag:.6f}", flush=True)
    print(f"[GR-TEST] Jitter (std/mean)         : {std_mag/max(mean_mag,1e-12)*100:.3f} %", flush=True)

    if mean_power_db > -80.0:
        print("[GR-TEST] [SUCCESS] Coherent carrier detected through lock-in!", flush=True)
        return True
    else:
        print("[GR-TEST] [WARNING] Carrier very weak. Check antenna connections.", flush=True)
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
