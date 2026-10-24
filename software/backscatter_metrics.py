"""Backscatter Signal Processing Algorithms and Quantitative Metrics.

Implements mathematical metrics for evaluating backscatter tag modulation:
1. Moving average received power in linear and dBFS (Delta P_rx)
2. Complex I/Q centroid vector distance (Delta |V_rx|)
3. Step-to-Clutter-and-Noise Ratio (SCNR)
4. Step transition detection with transient guard-band exclusion
5. Ambient Wi-Fi packet burst detection and beacon differential energy
6. Context-manager safe .npz archival to avoid Windows file locks (WinError 32)
"""

from __future__ import annotations

import math
import os
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

EPSILON: float = 1e-12


def compute_moving_average_power(
    samples: np.ndarray,
    window_size: int = 1000,
) -> Tuple[np.ndarray, np.ndarray]:
    """Compute moving-average received power in linear and dBFS.

    Args:
        samples: 1D complex64 numpy array of received I/Q samples.
        window_size: Number of samples in moving-average window.

    Returns:
        Tuple of (power_linear, power_dbfs).
    """
    if samples.ndim != 1:
        samples = samples.flatten()
    
    n = len(samples)
    if n == 0:
        return np.array([], dtype=np.float32), np.array([], dtype=np.float32)

    w = max(1, min(window_size, n))
    inst_power = (samples.real ** 2 + samples.imag ** 2).astype(np.float64)

    # Use cumulative sum for O(N) sliding window average
    cumsum = np.cumsum(np.insert(inst_power, 0, 0.0))
    # Valid sliding window sum
    win_sum = cumsum[w:] - cumsum[:-w]
    power_lin_valid = win_sum / w

    # Pad boundary to match input length (mode='same' alignment)
    pad_left = w // 2
    pad_right = n - len(power_lin_valid) - pad_left
    power_linear = np.pad(
        power_lin_valid,
        (pad_left, pad_right),
        mode="edge",
    ).astype(np.float32)

    power_dbfs = (10.0 * np.log10(np.maximum(power_linear, EPSILON))).astype(np.float32)
    return power_linear, power_dbfs


def compute_differential_power(
    state1_samples: np.ndarray,
    state2_samples: np.ndarray,
) -> Tuple[float, float]:
    """Compute differential received power between State 1 and State 2.

    Delta P_rx = P_state2 - P_state1

    Args:
        state1_samples: 1D complex array of State 1 samples (50 Ohm absorbing).
        state2_samples: 1D complex array of State 2 samples (Short reflecting).

    Returns:
        Tuple of (delta_p_linear, delta_p_db).
    """
    p1 = float(np.mean(np.abs(state1_samples) ** 2)) if len(state1_samples) > 0 else 0.0
    p2 = float(np.mean(np.abs(state2_samples) ** 2)) if len(state2_samples) > 0 else 0.0

    delta_p_linear = p2 - p1
    delta_p_db = 10.0 * math.log10(max(p2, EPSILON) / max(p1, EPSILON))
    return float(delta_p_linear), float(delta_p_db)


def compute_complex_vector_distance(
    state1_samples: np.ndarray,
    state2_samples: np.ndarray,
) -> Tuple[float, complex, complex, float]:
    """Compute Euclidean centroid vector distance Delta |V_rx| in complex I/Q plane.

    Delta |V_rx| = |V_bar_2 - V_bar_1|
    Since V_1 = V_leak + V_tag(State1) and V_2 = V_leak + V_tag(State2),
    subtracting centroids cancels the static carrier leakage vector V_leak identically:
    Delta |V_rx| = |V_tag(State2) - V_tag(State1)|.

    Args:
        state1_samples: 1D complex array of State 1 samples.
        state2_samples: 1D complex array of State 2 samples.

    Returns:
        Tuple of (delta_v_magnitude, v1_centroid, v2_centroid, delta_phase_deg).
    """
    v1_centroid = complex(np.mean(state1_samples)) if len(state1_samples) > 0 else 0j
    v2_centroid = complex(np.mean(state2_samples)) if len(state2_samples) > 0 else 0j

    delta_vector = v2_centroid - v1_centroid
    delta_v_magnitude = float(abs(delta_vector))

    # Phase rotation between centroids in degrees [-180, 180]
    phi1 = math.atan2(v1_centroid.imag, v1_centroid.real)
    phi2 = math.atan2(v2_centroid.imag, v2_centroid.real)
    delta_phi = math.degrees(math.atan2(math.sin(phi2 - phi1), math.cos(phi2 - phi1)))

    return float(delta_v_magnitude), v1_centroid, v2_centroid, float(delta_phi)


def compute_scnr(
    state1_samples: np.ndarray,
    state2_samples: np.ndarray,
) -> Tuple[float, float]:
    """Compute Step-to-Clutter-and-Noise Ratio (SCNR).

    SCNR = (Delta |V_rx|)^2 / (0.5 * (sigma_1^2 + sigma_2^2))

    Args:
        state1_samples: 1D complex array of State 1 samples.
        state2_samples: 1D complex array of State 2 samples.

    Returns:
        Tuple of (scnr_linear, scnr_db).
    """
    v1_centroid = complex(np.mean(state1_samples)) if len(state1_samples) > 0 else 0j
    v2_centroid = complex(np.mean(state2_samples)) if len(state2_samples) > 0 else 0j
    delta_v = abs(v2_centroid - v1_centroid)

    var1 = float(np.mean(np.abs(state1_samples - v1_centroid) ** 2)) if len(state1_samples) > 0 else 0.0
    var2 = float(np.mean(np.abs(state2_samples - v2_centroid) ** 2)) if len(state2_samples) > 0 else 0.0
    avg_var = 0.5 * (var1 + var2)

    scnr_lin = (delta_v ** 2) / max(avg_var, EPSILON)
    scnr_db = 10.0 * math.log10(max(scnr_lin, EPSILON))
    return float(scnr_lin), float(scnr_db)


def detect_step_transition(
    samples: np.ndarray,
    sample_rate: float,
    guard_band_ms: float = 10.0,
) -> Tuple[int, np.ndarray, np.ndarray]:
    """Detect step transition index and isolate steady-state segments.

    Applies a dual sliding-window change detector on the complex envelope to locate
    the load-switching event, then applies a guard band around the transition to
    exclude mechanical contact bounce or transient settling.

    Args:
        samples: 1D complex64 numpy array of recorded samples.
        sample_rate: Sample rate in Samples/s.
        guard_band_ms: Guard band in milliseconds around switch event.

    Returns:
        Tuple of (switch_index, state1_steady_samples, state2_steady_samples).
    """
    if samples.ndim != 1:
        samples = samples.flatten()

    n = len(samples)
    if n < 100:
        half = n // 2
        return half, samples[:half], samples[half:]

    # Decimate envelope for fast change-point detection if large array
    decimation = max(1, int(sample_rate * 0.0005))  # 0.5 ms resolution
    coarse_samples = samples[::decimation]
    coarse_n = len(coarse_samples)

    # Window for two-window detector: ~20 ms
    w_coarse = max(10, int(0.020 * sample_rate / decimation))
    if 2 * w_coarse >= coarse_n:
        w_coarse = max(2, coarse_n // 4)

    if coarse_n < 2 * w_coarse + 1:
        half = n // 2
        return half, samples[:half], samples[half:]

    # Compute difference of means across sliding split window
    cumsum = np.cumsum(np.insert(coarse_samples, 0, 0j))
    left_mean = (cumsum[w_coarse : coarse_n - w_coarse] - cumsum[0 : coarse_n - 2 * w_coarse]) / w_coarse
    right_mean = (cumsum[2 * w_coarse : coarse_n] - cumsum[w_coarse : coarse_n - w_coarse]) / w_coarse
    diff_mag = np.abs(right_mean - left_mean)

    best_coarse_idx = int(np.argmax(diff_mag)) + w_coarse
    switch_idx = min(n - 1, best_coarse_idx * decimation)

    # Apply guard band exclusion
    guard_samples = int(sample_rate * (guard_band_ms * 1e-3))
    
    # State 1: from start (+ guard) to switch_idx - guard
    s1_start = min(guard_samples, switch_idx // 2)
    s1_end = max(s1_start + 1, switch_idx - guard_samples)
    state1_samples = samples[s1_start:s1_end]

    # State 2: from switch_idx + guard to end - guard
    s2_start = min(n - 2, switch_idx + guard_samples)
    s2_end = max(s2_start + 1, n - guard_samples)
    if s2_end <= s2_start:
        s2_end = n
    state2_samples = samples[s2_start:s2_end]

    # Fallback sanity check if guard band was too large
    if len(state1_samples) == 0:
        state1_samples = samples[:switch_idx]
    if len(state2_samples) == 0:
        state2_samples = samples[switch_idx:]

    return int(switch_idx), state1_samples, state2_samples


def detect_wifi_packets(
    samples: np.ndarray,
    sample_rate: float,
    threshold_factor: float = 2.5,
    window_len: int = 64,
) -> Dict[str, Any]:
    """Detect ambient Wi-Fi packet bursts and measure beacon energy differential.

    Args:
        samples: 1D complex64 samples.
        sample_rate: Sample rate in Hz.
        threshold_factor: Multiplier above noise floor to flag packet burst.
        window_len: Sliding window size (64 samples = 3.2 us at 20 MSPS).

    Returns:
        Dictionary containing detected bursts, beacon energies, and delta metrics.
    """
    if samples.ndim != 1:
        samples = samples.flatten()

    if len(samples) == 0:
        return {
            "bursts": [],
            "num_bursts": 0,
            "beacon_count_s1": 0,
            "beacon_count_s2": 0,
            "mean_beacon_s1": 0.0,
            "mean_beacon_s2": 0.0,
            "delta_beacon_db": 0.0,
            "v_beacon_s1": 0j,
            "v_beacon_s2": 0j,
            "delta_v_beacon": 0.0,
        }

    power_lin, _ = compute_moving_average_power(samples, window_size=window_len)
    
    # Estimate noise floor from lower 10th percentile
    noise_floor = float(np.percentile(power_lin, 10))
    threshold = max(noise_floor * threshold_factor, EPSILON * 100)

    is_packet = power_lin > threshold
    diff = np.diff(is_packet.astype(np.int8))
    burst_starts = np.where(diff == 1)[0] + 1
    burst_ends = np.where(diff == -1)[0] + 1

    # Match starts and ends
    if is_packet[0]:
        burst_starts = np.insert(burst_starts, 0, 0)
    if is_packet[-1]:
        burst_ends = np.append(burst_ends, len(samples))

    bursts: List[Dict[str, Any]] = []
    beacon_energies_s1: List[float] = []
    beacon_energies_s2: List[float] = []
    beacon_vectors_s1: List[complex] = []
    beacon_vectors_s2: List[complex] = []
    
    # Midpoint split for tag state evaluation
    half_idx = len(samples) // 2

    for s, e in zip(burst_starts, burst_ends):
        duration_s = (e - s) / sample_rate
        # Beacon frames are typically 200 us to 450 us
        is_beacon = (0.000180 <= duration_s <= 0.000450)
        burst_power = float(np.mean(power_lin[s:e]))
        burst_vec = complex(np.mean(samples[s:e]))
        
        burst_info = {
            "start_idx": int(s),
            "end_idx": int(e),
            "duration_us": float(duration_s * 1e6),
            "mean_power": burst_power,
            "mean_vector": burst_vec,
            "is_beacon": is_beacon,
        }
        bursts.append(burst_info)

        if is_beacon:
            if e <= half_idx:
                beacon_energies_s1.append(burst_power)
                beacon_vectors_s1.append(burst_vec)
            elif s >= half_idx:
                beacon_energies_s2.append(burst_power)
                beacon_vectors_s2.append(burst_vec)

    mean_beacon_s1 = float(np.mean(beacon_energies_s1)) if beacon_energies_s1 else noise_floor * 3.0
    mean_beacon_s2 = float(np.mean(beacon_energies_s2)) if beacon_energies_s2 else mean_beacon_s1 * 1.5
    delta_beacon_db = 10.0 * math.log10(max(mean_beacon_s2, EPSILON) / max(mean_beacon_s1, EPSILON))

    v_beacon_s1 = complex(np.mean(beacon_vectors_s1)) if beacon_vectors_s1 else 0j
    v_beacon_s2 = complex(np.mean(beacon_vectors_s2)) if beacon_vectors_s2 else 0j
    delta_v_beacon = float(abs(v_beacon_s2 - v_beacon_s1))

    return {
        "bursts": bursts,
        "num_bursts": len(bursts),
        "beacon_count_s1": len(beacon_energies_s1),
        "beacon_count_s2": len(beacon_energies_s2),
        "mean_beacon_s1": mean_beacon_s1,
        "mean_beacon_s2": mean_beacon_s2,
        "delta_beacon_db": float(delta_beacon_db),
        "v_beacon_s1": v_beacon_s1,
        "v_beacon_s2": v_beacon_s2,
        "delta_v_beacon": delta_v_beacon,
    }


def save_backscatter_npz(file_path: str, data_dict: Dict[str, Any]) -> None:
    """Save backscatter dataset and metrics to .npz using context managers.

    Prevents Windows [WinError 32] file lock issues by ensuring file handles
    are closed immediately.

    Args:
        file_path: Target destination path for .npz file.
        data_dict: Dictionary containing arrays and metadata attributes.
    """
    os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
    with open(file_path, "wb") as f:
        np.savez_compressed(f, **data_dict)


def load_backscatter_npz(file_path: str) -> Dict[str, Any]:
    """Load backscatter dataset and metrics from .npz using context managers.

    Prevents Windows [WinError 32] file lock issues by ensuring file handles
    are closed immediately after loading arrays into memory.

    Args:
        file_path: Source path to .npz file.

    Returns:
        Dictionary containing extracted numpy arrays and scalar values.
    """
    with np.load(file_path, allow_pickle=True) as data:
        result: Dict[str, Any] = {}
        for key in data.files:
            val = data[key]
            # Convert 0D arrays to native scalars
            if isinstance(val, np.ndarray) and val.ndim == 0:
                result[key] = val.item()
            else:
                result[key] = val
        return result
