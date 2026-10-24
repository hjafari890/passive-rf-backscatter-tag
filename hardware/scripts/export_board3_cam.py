"""Exports clean CAM files for Board 3 (Leggiero Bowtie Tag)."""

import os
import shutil
import subprocess

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BOARD3_DIR = os.path.join(BASE_DIR, "board3_cavity_bowtie_2.4ghz")
GERBERS_DIR = os.path.join(BOARD3_DIR, "gerbers")
DXF_DIR = os.path.join(BOARD3_DIR, "dxf")
PCB_PATH = os.path.join(BOARD3_DIR, "backscatter_tag_leggiero.kicad_pcb")

KICAD_CLI = "kicad-cli"
for p in [r"C:\Program Files\KiCad\9.0\bin\kicad-cli.exe", r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe", r"C:\Program Files\KiCad\8.0\bin\kicad-cli.exe"]:
    if os.path.isfile(p):
        KICAD_CLI = p
        break

os.makedirs(GERBERS_DIR, exist_ok=True)
os.makedirs(DXF_DIR, exist_ok=True)

# 1. Gerbers
subprocess.run([KICAD_CLI, "pcb", "export", "gerbers", "--output", GERBERS_DIR + os.sep, PCB_PATH], check=True)

# 2. Drill (only 3 holes for J1, 0 vias!)
subprocess.run([KICAD_CLI, "pcb", "export", "drill", "--output", GERBERS_DIR + os.sep, "--format", "excellon", PCB_PATH], check=True)

# 3. DXFs (1:1 mm metric scale)
dxf_fcu = os.path.join(DXF_DIR, "backscatter_tag_leggiero-F_Cu.dxf")
dxf_edge = os.path.join(DXF_DIR, "backscatter_tag_leggiero-Edge_Cuts.dxf")
subprocess.run([KICAD_CLI, "pcb", "export", "dxf", "--output", dxf_fcu, "--mode-single", "--layers", "F.Cu", "--output-units", "mm", PCB_PATH], check=True)
subprocess.run([KICAD_CLI, "pcb", "export", "dxf", "--output", dxf_edge, "--mode-single", "--layers", "Edge.Cuts", "--output-units", "mm", PCB_PATH], check=True)

print("Exported Board 3 CAM files successfully to:", BOARD3_DIR)
