"""SDR Backscatter Validation Pipeline.

Provides USRP SDR control, mock hardware emulation, backscatter signal metrics,
data persistence, and publication figure generation.
"""

from .mock_usrp import (
    MockMultiUSRP,
    MockRXStreamer,
    MockTXStreamer,
    MockRXMetadata,
    MockTXMetadata,
    MockStreamArgs,
    MockStreamCMD,
    MockStreamMode,
    MockRXMetadataErrorCode,
    MockTuneRequest,
)

from .backscatter_metrics import (
    compute_moving_average_power,
    compute_differential_power,
    compute_complex_vector_distance,
    compute_scnr,
    detect_step_transition,
    save_backscatter_npz,
    load_backscatter_npz,
)

__all__ = [
    "MockMultiUSRP",
    "MockRXStreamer",
    "MockTXStreamer",
    "MockRXMetadata",
    "MockTXMetadata",
    "MockStreamArgs",
    "MockStreamCMD",
    "MockStreamMode",
    "MockRXMetadataErrorCode",
    "MockTuneRequest",
    "compute_moving_average_power",
    "compute_differential_power",
    "compute_complex_vector_distance",
    "compute_scnr",
    "detect_step_transition",
    "save_backscatter_npz",
    "load_backscatter_npz",
]
