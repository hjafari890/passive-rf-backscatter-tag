"""Calculate precise resonance dimensions for single-sided planar meander monopole at 915 MHz / 868 MHz."""

import numpy as np

c = 299792458.0
eps_r = 4.4
h = 1.6e-3
w = 1.0e-3 # 1.0 mm trace width

# Effective dielectric constant for microstrip/coplanar trace on FR-4
u = w / h
eps_eff = (eps_r + 1.0)/2.0 + ((eps_r - 1.0)/2.0) * (1.0 + 12.0/u)**(-0.5)

# Free space wavelength
lambda_915 = c / 915e6
lambda_868 = c / 868e6

# Guided quarter wavelength
l_quarter_915 = lambda_915 / (4.0 * np.sqrt(eps_eff))
l_quarter_868 = lambda_868 / (4.0 * np.sqrt(eps_eff))

# Due to meander inter-trace capacitive coupling (meander factor ~ 1.15 - 1.25):
meander_slow_wave_factor = 1.18
l_physical_915 = l_quarter_915 / meander_slow_wave_factor
l_physical_868 = l_quarter_868 / meander_slow_wave_factor

print(f"915 MHz: lambda_0 = {lambda_915*1e3:.1f} mm, lambda_g/4 = {l_quarter_915*1e3:.1f} mm, physical target = {l_physical_915*1e3:.1f} mm")
print(f"868 MHz: lambda_0 = {lambda_868*1e3:.1f} mm, lambda_g/4 = {l_quarter_868*1e3:.1f} mm, physical target = {l_physical_868*1e3:.1f} mm")
