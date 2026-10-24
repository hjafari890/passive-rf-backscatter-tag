"""Antenna simulation and differential RCS analysis package for backscatter tags."""

from .antenna_models import (
    Substrate,
    AntennaModel,
    PlanarMonopole244,
    TI_SWRA117D_IFA,
    TI_SWRA416_Helical,
    PlanarMeanderMonopole,
    get_antenna,
    calculate_zin,
    calculate_s11,
    calculate_resonance,
)

from .rcs_simulation import (
    LoadState,
    compute_gamma_l,
    compute_delta_gamma,
    verify_delta_gamma_contrast,
    compute_differential_rcs,
    ABSORBING_50OHM,
    REFLECTING_SHORT,
    REFLECTING_OPEN,
)

__all__ = [
    "Substrate",
    "AntennaModel",
    "PlanarMonopole244",
    "TI_SWRA117D_IFA",
    "TI_SWRA416_Helical",
    "PlanarMeanderMonopole",
    "get_antenna",
    "calculate_zin",
    "calculate_s11",
    "calculate_resonance",
    "LoadState",
    "compute_gamma_l",
    "compute_delta_gamma",
    "verify_delta_gamma_contrast",
    "compute_differential_rcs",
    "ABSORBING_50OHM",
    "REFLECTING_SHORT",
    "REFLECTING_OPEN",
]
