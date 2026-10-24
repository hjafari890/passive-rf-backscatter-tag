"""Exports clean CAM files for Board 3 (Leggiero Bowtie Tag)."""

import os
import shutil
import subprocess

BASE_DIR = r"."
KICAD_DIR = os.path.join(BASE_DIR, "kicad_pcb(automated)")
READY_DIR = os.path.join(BASE_DIR, "ready_for_milling")
BOARD3_DIR = os.path.join(READY_DIR, "Board3_2.4GHz_Leggiero_Bowtie_Tag")
PCB_PATH = os.path.join(KICAD_DIR, "backscatter_tag_leggiero.kicad_pcb")

KICAD_CLI = r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"

os.makedirs(BOARD3_DIR, exist_ok=True)

# 1. Gerbers
subprocess.run([KICAD_CLI, "pcb", "export", "gerbers", "--output", BOARD3_DIR + "/", PCB_PATH], check=True)

# 2. Drill (only 3 holes for J1, 0 vias!)
subprocess.run([KICAD_CLI, "pcb", "export", "drill", "--output", BOARD3_DIR + "/", "--format", "excellon", PCB_PATH], check=True)

# 3. DXFs (1:1 mm metric scale)
dxf_fcu = os.path.join(BOARD3_DIR, "backscatter_tag_leggiero-F_Cu.dxf")
dxf_edge = os.path.join(BOARD3_DIR, "backscatter_tag_leggiero-Edge_Cuts.dxf")
subprocess.run([KICAD_CLI, "pcb", "export", "dxf", "--output", dxf_fcu, "--mode-single", "--layers", "F.Cu", "--output-units", "mm", PCB_PATH], check=True)
subprocess.run([KICAD_CLI, "pcb", "export", "dxf", "--output", dxf_edge, "--mode-single", "--layers", "Edge.Cuts", "--output-units", "mm", PCB_PATH], check=True)

# Copy main CAM files to ready_for_milling root with clear prefixes
for fn in os.listdir(BOARD3_DIR):
    shutil.copyfile(os.path.join(BOARD3_DIR, fn), os.path.join(READY_DIR, fn))

print("Exported Board 3 CAM files successfully to:", BOARD3_DIR)
