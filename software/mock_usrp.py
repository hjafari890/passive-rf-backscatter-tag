"""Mock NI USRP-2900 / Ettus USRP B200 Hardware Emulator.

Provides a drop-in software emulation harness for UHD MultiUSRP, RXStreamer,
TXStreamer, and RXMetadata when physical USRP hardware is disconnected.
Enforces the UHD 2D buffer contract (shape (1, N) complex64) and implements
physics-based synthetic sample generation for both Mode 1 (CW Carrier) and
Mode 2 (Ambient Wi-Fi Channel).
"""

from __future__ import annotations

import enum
import math
from typing import Any, List, Optional, Tuple, Union

import numpy as np

# Try importing real uhd types for maximum interoperability; provide mocks if unavailable
try:
    import uhd
    HAS_UHD = True
except ImportError:
    uhd = None  # type: ignore
    HAS_UHD = False


class MockRXMetadataErrorCode(enum.IntEnum):
    """Mock error codes for RXMetadata matching uhd.types.RXMetadataErrorCode."""
    none = 0
    overflow = 1
    timeout = 2
    late = 3
    broken_chain = 4
    alignment = 5


class MockStreamMode(enum.IntEnum):
    """Mock stream modes matching uhd.types.StreamMode."""
    start_cont = 1
    stop_cont = 2
    num_done = 3


class MockRXMetadata:
    """Mock structure for uhd.types.RXMetadata."""

    def __init__(self) -> None:
        self.error_code = (
            uhd.types.RXMetadataErrorCode.none if HAS_UHD else MockRXMetadataErrorCode.none
        )
        self.has_time_spec: bool = False
        self.time_spec: float = 0.0
        self.more_fragments: bool = False
        self.fragment_offset: int = 0
        self.out_of_sequence: bool = False

    def strerror(self) -> str:
        """Return human-readable error description."""
        if hasattr(self.error_code, "name"):
            return str(self.error_code.name)
        return "none" if self.error_code == 0 else f"error_{self.error_code}"


class MockTXMetadata:
    """Mock structure for uhd.types.TXMetadata."""

    def __init__(self) -> None:
        self.has_time_spec: bool = False
        self.time_spec: float = 0.0
        self.start_of_burst: bool = True
        self.end_of_burst: bool = False


class MockStreamCMD:
    """Mock structure for uhd.types.StreamCMD."""

    def __init__(self, stream_mode: Any) -> None:
        self.stream_mode = stream_mode
        self.stream_now: bool = True
        self.num_samps: int = 0
        self.time_spec: float = 0.0


class MockStreamArgs:
    """Mock structure for uhd.usrp.StreamArgs."""

    def __init__(self, cpu_format: str = "fc32", otw_format: str = "sc16") -> None:
        self.cpu_format = cpu_format
        self.otw_format = otw_format
        self.channels: List[int] = [0]


class MockTuneRequest:
    """Mock structure for uhd.types.TuneRequest."""

    def __init__(self, target_freq: float, rf_offset: float = 0.0) -> None:
        self.target_freq = float(target_freq)
        self.rf_offset = float(rf_offset)


class MockRXStreamer:
    """Drop-in emulator for uhd.usrp.RXStreamer.
    
    Enforces the 2D NumPy buffer contract and streams synthetic samples generated
    by the parent MockMultiUSRP physics engine.
    """

    def __init__(self, usrp: MockMultiUSRP) -> None:
        self.usrp = usrp
        self.stream_active: bool = False
        self.sample_index: int = 0

    def issue_stream_cmd(self, stream_cmd: Any) -> None:
        """Handle stream start/stop commands."""
        mode_val = getattr(stream_cmd, "stream_mode", stream_cmd)
        
        # Check against both real UHD and mock modes
        is_start = False
        is_stop = False
        if HAS_UHD and hasattr(uhd.types, "StreamMode"):
            if mode_val == uhd.types.StreamMode.start_cont:
                is_start = True
            elif mode_val == uhd.types.StreamMode.stop_cont:
                is_stop = True
        if mode_val in (MockStreamMode.start_cont, 1, "start_cont"):
            is_start = True
        elif mode_val in (MockStreamMode.stop_cont, 2, "stop_cont"):
            is_stop = True

        if is_start:
            self.stream_active = True
        elif is_stop:
            self.stream_active = False

    def recv(
        self,
        buffer: np.ndarray,
        metadata: Any,
        timeout: float = 1.0,
    ) -> int:
        """Receive a chunk of samples into the provided 2D buffer.
        
        Args:
            buffer: Must be a 2D numpy array of shape (num_channels, chunk_size)
                    with dtype np.complex64.
            metadata: RXMetadata object updated with reception status.
            timeout: Maximum wait time in seconds.

        Returns:
            Number of samples received into buffer[0, :].

        Raises:
            ValueError: If buffer is not 2D or has invalid channel count.
            TypeError: If buffer dtype is not np.complex64.
        """
        # Strict UHD 2D buffer contract enforcement
        if not isinstance(buffer, np.ndarray):
            raise TypeError("Buffer must be a numpy.ndarray")
        if buffer.ndim != 2:
            raise ValueError(
                f"Expected 2D array of shape (num_channels, chunk_size), got ndim={buffer.ndim}"
            )
        if buffer.shape[0] < 1:
            raise ValueError(
                f"Expected at least 1 channel row in buffer, got shape={buffer.shape}"
            )
        if buffer.dtype != np.complex64:
            raise TypeError(
                f"Expected buffer dtype numpy.complex64, got {buffer.dtype}"
            )

        chunk_size = buffer.shape[1]
        if not self.stream_active:
            if metadata is not None:
                err_code = (
                    uhd.types.RXMetadataErrorCode.none
                    if HAS_UHD
                    else MockRXMetadataErrorCode.none
                )
                metadata.error_code = err_code
            return 0

        # Generate chunk from physics generator
        chunk_samples = self.usrp.generate_samples(self.sample_index, chunk_size)
        buffer[0, :chunk_size] = chunk_samples
        self.sample_index += chunk_size

        if metadata is not None:
            err_code = (
                uhd.types.RXMetadataErrorCode.none
                if HAS_UHD
                else MockRXMetadataErrorCode.none
            )
            metadata.error_code = err_code
            metadata.has_time_spec = True
            metadata.time_spec = self.sample_index / self.usrp.rx_rate

        return chunk_size


class MockTXStreamer:
    """Drop-in emulator for uhd.usrp.TXStreamer."""

    def __init__(self, usrp: MockMultiUSRP) -> None:
        self.usrp = usrp
        self.samples_transmitted: int = 0

    def send(
        self,
        buffer: np.ndarray,
        metadata: Any,
        timeout: float = 1.0,
    ) -> int:
        """Transmit samples from buffer.
        
        Args:
            buffer: Must be a 2D numpy array of shape (num_channels, chunk_size)
                    with dtype np.complex64.
            metadata: TXMetadata instance.
            timeout: Maximum wait time in seconds.

        Returns:
            Number of samples transmitted.
        """
        if not isinstance(buffer, np.ndarray):
            raise TypeError("Buffer must be a numpy.ndarray")
        if buffer.ndim != 2:
            raise ValueError(
                f"Expected 2D array of shape (num_channels, chunk_size), got ndim={buffer.ndim}"
            )
        if buffer.shape[0] < 1:
            raise ValueError(
                f"Expected at least 1 channel row in buffer, got shape={buffer.shape}"
            )
        if buffer.dtype != np.complex64:
            raise TypeError(
                f"Expected buffer dtype numpy.complex64, got {buffer.dtype}"
            )

        chunk_size = buffer.shape[1]
        self.samples_transmitted += chunk_size
        return chunk_size


class MockMultiUSRP:
    """Complete drop-in emulator for uhd.usrp.MultiUSRP.
    
    Implements full transceiver configuration API and realistic physics-based
    synthetic sample generation for:
      - Mode 1: CW Carrier tone with direct carrier leakage, tag step response,
                and thermal noise.
      - Mode 2: Ambient Wi-Fi channel with periodic 802.11 beacon frames (102.4 ms),
                OFDM data packet bursts, and tag backscatter modulation.
    """

    def __init__(
        self,
        device_args: str = "",
        mode: str = "cw",
        switch_time: float = 1.0,
        random_seed: Optional[int] = 42,
        sample_rate: Optional[float] = None,
    ) -> None:
        self.device_args = device_args
        self.mode = mode.lower()
        self.switch_time = switch_time
        
        # RF Transceiver configuration
        rate = float(sample_rate) if sample_rate is not None else 2.0e6
        self.rx_rate: float = rate
        self.tx_rate: float = rate
        self.rx_freq: float = 2.44e9 if self.mode == "cw" else 2.437e9
        self.tx_freq: float = 2.44e9
        self.rx_gain: float = 30.0
        self.tx_gain: float = 50.0
        self.rx_antenna: str = "RX2"
        self.tx_antenna: str = "TX/RX"
        self.rx_agc: bool = False

        
        # Internal PRNG for reproducible and authentic noise generation
        self.rng = np.random.default_rng(random_seed)

        # Wi-Fi packet schedule precomputation for Mode 2
        self._init_wifi_schedule()

    def set_rx_rate(self, rate: float, chan: int = 0) -> None:
        self.rx_rate = float(rate)

    def get_rx_rate(self, chan: int = 0) -> float:
        return self.rx_rate

    def set_tx_rate(self, rate: float, chan: int = 0) -> None:
        self.tx_rate = float(rate)

    def get_tx_rate(self, chan: int = 0) -> float:
        return self.tx_rate

    def set_rx_freq(self, tune_req: Any, chan: int = 0) -> None:
        freq = getattr(tune_req, "target_freq", tune_req)
        self.rx_freq = float(freq)

    def get_rx_freq(self, chan: int = 0) -> float:
        return self.rx_freq

    def set_tx_freq(self, tune_req: Any, chan: int = 0) -> None:
        freq = getattr(tune_req, "target_freq", tune_req)
        self.tx_freq = float(freq)

    def get_tx_freq(self, chan: int = 0) -> float:
        return self.tx_freq

    def set_rx_gain(self, gain: float, chan: int = 0) -> None:
        self.rx_gain = float(gain)

    def get_rx_gain(self, chan: int = 0) -> float:
        return self.rx_gain

    def set_tx_gain(self, gain: float, chan: int = 0) -> None:
        self.tx_gain = float(gain)

    def get_tx_gain(self, chan: int = 0) -> float:
        return self.tx_gain

    def set_rx_antenna(self, ant: str, chan: int = 0) -> None:
        self.rx_antenna = str(ant)

    def get_rx_antenna(self, chan: int = 0) -> str:
        return self.rx_antenna

    def set_tx_antenna(self, ant: str, chan: int = 0) -> None:
        self.tx_antenna = str(ant)

    def get_tx_antenna(self, chan: int = 0) -> str:
        return self.tx_antenna

    def set_rx_agc(self, enable: bool, chan: int = 0) -> None:
        self.rx_agc = bool(enable)

    def get_rx_agc(self, chan: int = 0) -> bool:
        return self.rx_agc

    def get_rx_stream(self, stream_args: Any) -> MockRXStreamer:
        return MockRXStreamer(self)

    def get_tx_stream(self, stream_args: Any) -> MockTXStreamer:
        return MockTXStreamer(self)

    def _init_wifi_schedule(self) -> None:
        """Precompute ambient Wi-Fi packet intervals for Mode 2."""
        # Beacons every 102.4 ms (approx 9.76 Hz)
        self.beacon_interval_s = 0.1024
        self.beacon_duration_s = 0.000300  # 300 us beacon frame
        
        # Periodic and random data bursts
        self.data_burst_starts: List[Tuple[float, float, float]] = []
        # Generate 10 seconds of random ambient traffic bursts (start_time, duration, amplitude)
        cur_t = 0.015
        while cur_t < 15.0:
            burst_dur = float(self.rng.uniform(0.000150, 0.000600))
            burst_amp = float(self.rng.uniform(0.12, 0.28))
            self.data_burst_starts.append((cur_t, burst_dur, burst_amp))
            cur_t += float(self.rng.exponential(0.025)) + burst_dur

    def generate_samples(self, start_idx: int, count: int) -> np.ndarray:
        """Generate physics-grounded synthetic complex baseband samples.
        
        Args:
            start_idx: Global sample index offset.
            count: Number of samples to generate.

        Returns:
            1D numpy array of shape (count,) with dtype complex64.
        """
        fs = self.rx_rate
        t = (np.arange(start_idx, start_idx + count, dtype=np.float64)) / fs

        if self.mode == "cw":
            return self._generate_cw_samples(t)
        elif self.mode == "wifi":
            return self._generate_wifi_samples(t)
        else:
            raise ValueError(f"Unknown operating mode: {self.mode}")

    def _generate_cw_samples(self, t: np.ndarray) -> np.ndarray:
        """Mode 1: CW Carrier tone with carrier leakage, step response, and AWGN."""
        # Gain scaling factor relative to 50 dB TX and 30 dB RX nominal
        tx_scale = 10.0 ** ((self.tx_gain - 50.0) / 40.0)
        rx_scale = 10.0 ** ((self.rx_gain - 30.0) / 40.0)
        total_scale = tx_scale * rx_scale

        # 1. Direct antenna-to-antenna / port-to-port carrier leakage (~ -30 dBm baseband equivalent)
        # Constant vector V_leak = 0.35 + 0.15j (magnitude ~ 0.38)
        v_leak = complex(0.35, 0.15) * total_scale

        # 2. Tag backscatter reflection V_tag(t) across 3 jumper states:
        # State 1 (50 Ohm absorbing, Gamma ~ 0): Jumper Pins 1-2
        # State 2 (Short reflecting, Gamma = -1.0, 180 deg phase): Jumper Pins 2-3
        # State 3 (Open reflecting, Gamma = +1.0, 0 deg phase): Jumper Removed
        v_tag_state1 = complex(0.005, 0.002) * total_scale    # 50-Ohm matched load residual
        v_tag_state2 = complex(-0.090, -0.045) * total_scale  # Short-circuit reflection (Gamma = -1)
        v_tag_state3 = complex(+0.088, +0.044) * total_scale  # Open-circuit reflection (Gamma = +1, opposite phase)

        # 3-State cycle period: 12 seconds (4s per state)
        cycle_period = 12.0
        t_mod = np.mod(t, cycle_period)
        bounce_dur = 0.002  # 2 ms mechanical bounce

        v_tag = np.zeros(len(t), dtype=np.complex64)

        # State 1: 0.0 <= t_mod < 4.0
        m1 = (t_mod < 4.0 - bounce_dur)
        v_tag[m1] = v_tag_state1

        # State 2: 4.0 <= t_mod < 8.0
        m2 = (t_mod >= 4.0) & (t_mod < 8.0 - bounce_dur)
        v_tag[m2] = v_tag_state2

        # State 3: 8.0 <= t_mod < 12.0
        m3 = (t_mod >= 8.0) & (t_mod < 12.0 - bounce_dur)
        v_tag[m3] = v_tag_state3

        # Transitions with chatter
        b12 = (t_mod >= 4.0 - bounce_dur) & (t_mod < 4.0)
        if np.any(b12):
            v_tag[b12] = v_tag_state2
        b23 = (t_mod >= 8.0 - bounce_dur) & (t_mod < 8.0)
        if np.any(b23):
            v_tag[b23] = v_tag_state3
        b31 = (t_mod >= 12.0 - bounce_dur)
        if np.any(b31):
            v_tag[b31] = v_tag_state1

        # 3. Additive White Gaussian Noise (AWGN)
        sigma = 0.006 * rx_scale
        noise_i = self.rng.normal(0.0, sigma, size=len(t)).astype(np.float32)
        noise_q = self.rng.normal(0.0, sigma, size=len(t)).astype(np.float32)
        noise = noise_i + 1j * noise_q

        # Total signal: x(t) = V_leak + V_tag(t) + w(t)
        samples = (v_leak + v_tag + noise).astype(np.complex64)
        return samples

    def _generate_wifi_samples(self, t: np.ndarray) -> np.ndarray:
        """Mode 2: Ambient Wi-Fi channel with beacon bursts, OFDM traffic, and tag reflection."""
        if len(t) == 0:
            return np.array([], dtype=np.complex64)

        rx_scale = 10.0 ** ((self.rx_gain - 30.0) / 40.0)
        n_samples = len(t)
        samples = np.zeros(n_samples, dtype=np.complex64)

        # Tag state: State 1 (Absorbing, Gamma ~ 0) vs State 2 (Reflecting, Gamma = -1.0)
        t_switch = self.switch_time
        # Tag reflection factor for ambient Wi-Fi backscatter:
        # In State 1: reflection is negligible (alpha ~ 0.01)
        # In State 2: backscatter creates constructive/differential packet energy (alpha ~ 0.28)
        tag_gain = np.where(t >= t_switch, 1.28, 1.00).astype(np.float32)
        tag_phase_shift = np.where(t >= t_switch, np.exp(1j * 0.45), 1.0 + 0j).astype(np.complex64)

        # 1. Synthesize periodic beacon frames (every 102.4 ms)
        t_start = t[0]
        t_end = t[-1]
        k_min = int(math.floor(t_start / self.beacon_interval_s))
        k_max = int(math.ceil(t_end / self.beacon_interval_s))

        for k in range(k_min, k_max + 1):
            b_start = k * self.beacon_interval_s
            b_end = b_start + self.beacon_duration_s
            mask_b = (t >= b_start) & (t < b_end)
            if np.any(mask_b):
                tb = t[mask_b] - b_start
                # Synthesize 802.11 OFDM preamble & subcarrier superposition
                # Short training preamble (10 periodic bursts at 1.25 MHz) + OFDM subcarriers
                preamble_freq = 1.25e6
                subcarrier_1 = np.exp(1j * 2.0 * np.pi * 312500.0 * tb)
                subcarrier_2 = np.exp(1j * 2.0 * np.pi * -625000.0 * tb)
                subcarrier_3 = np.exp(1j * 2.0 * np.pi * 937500.0 * tb)
                ofdm_sum = (subcarrier_1 + 0.8 * subcarrier_2 + 0.6 * subcarrier_3) / 2.4
                preamble = 0.30 * np.sin(2.0 * np.pi * preamble_freq * tb)
                # Coherent baseband preamble + OFDM subcarriers
                beacon_wave = (0.15 + 0.20 * ofdm_sum + 0.15 * preamble).astype(np.complex64)
                # Apply tag reflection modulation
                samples[mask_b] += (beacon_wave * tag_gain[mask_b] * tag_phase_shift[mask_b]).astype(np.complex64)

        # 2. Synthesize ambient data packet bursts
        for burst_start, burst_dur, burst_amp in self.data_burst_starts:
            burst_end = burst_start + burst_dur
            if burst_end < t_start or burst_start > t_end:
                continue
            mask_d = (t >= burst_start) & (t < burst_end)
            if np.any(mask_d):
                td = t[mask_d] - burst_start
                # OFDM multi-subcarrier envelope with coherent baseband pilot
                ofdm_carrier = np.exp(1j * 2.0 * np.pi * 625000.0 * td)
                data_wave = (burst_amp * (0.25 + 0.85 * ofdm_carrier)).astype(np.complex64)
                samples[mask_d] += (data_wave * tag_gain[mask_d] * tag_phase_shift[mask_d]).astype(np.complex64)

        # 3. Add background thermal AWGN floor
        sigma_noise = 0.003 * rx_scale
        noise_i = self.rng.normal(0.0, sigma_noise, size=n_samples).astype(np.float32)
        noise_q = self.rng.normal(0.0, sigma_noise, size=n_samples).astype(np.float32)
        samples += (noise_i + 1j * noise_q)

        return (samples * rx_scale).astype(np.complex64)
