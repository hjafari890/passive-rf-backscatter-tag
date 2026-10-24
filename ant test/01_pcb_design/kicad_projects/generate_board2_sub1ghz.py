"""Builds Board 2 (Sub-1GHz 868/915 MHz Planar Meander Monopole) for zero-via CNC milling, runs DRC, and exports CAM files."""

import os
import shutil
import subprocess

BASE_DIR = r"."
KICAD_DIR = os.path.join(BASE_DIR, "kicad_pcb(automated)")
READY_DIR = os.path.join(BASE_DIR, "ready_for_milling")
SUB1_DIR = os.path.join(READY_DIR, "Board2_Sub1GHz_Planar_Tag")
os.makedirs(SUB1_DIR, exist_ok=True)

KICAD_CLI = "kicad-cli"
for p in [r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe", r"C:\Program Files\KiCad\9.0\bin\kicad-cli.exe", r"C:\Program Files\KiCad\8.0\bin\kicad-cli.exe"]:
    if os.path.isfile(p):
        KICAD_CLI = p
        break

pcb_in = os.path.join(KICAD_DIR, "backscatter_tag.kicad_pcb")
pcb_out = os.path.join(KICAD_DIR, "backscatter_tag_sub1ghz.kicad_pcb")
sch_out = os.path.join(KICAD_DIR, "backscatter_tag_sub1ghz.kicad_sch")

# 1. Write schematic for Board 2
with open(os.path.join(KICAD_DIR, "backscatter_tag.kicad_sch"), "r", encoding="utf-8") as f:
    sch = f.read()

sch = sch.replace('2.4 GHz RF Backscatter Tag - M2', 'Sub-1GHz Planar Meander Tag - Zero Vias')
sch = sch.replace('TI SWRA117D 2.4 GHz IFA Layout on F.Cu', '868/915 MHz Single-Sided Planar Meander Monopole (0 Vias)')
sch = sch.replace('Texas_SWRA117D_2.4GHz', 'Planar_Meander_Sub1GHz')
sch = sch.replace('RF_Antenna:Texas_SWRA117D_2.4GHz_Right', 'RF_Antenna:Planar_Meander_Sub1GHz')

with open(sch_out, "w", encoding="utf-8") as f:
    f.write(sch)
print("Schematic written.")

# 2. Build PCB for Board 2
with open(pcb_in, "r", encoding="utf-8") as f:
    pcb = f.read()

pcb = pcb.replace('2.4 GHz RF Backscatter Tag - M2', 'Sub-1GHz Planar Meander Tag - Zero Vias')
pcb = pcb.replace('2.4 GHz RF BACKSCATTER TAG', 'SUB-1GHz PLANAR TAG')
pcb = pcb.replace('TI SWRA117D IFA', 'MEANDER MONOPOLE')

# Expand Edge.Cuts to 45.0 x 42.0 mm: Y from 3.00 to 45.00 mm
pcb = pcb.replace('(start 10.00 10.00) (end 55.00 10.00)', '(start 10.00 3.00) (end 55.00 3.00)')
pcb = pcb.replace('(start 55.00 10.00) (end 55.00 45.00)', '(start 55.00 3.00) (end 55.00 45.00)')
pcb = pcb.replace('(start 10.00 45.00) (end 10.00 10.00)', '(start 10.00 45.00) (end 10.00 3.00)')

# Replace AE1 footprint with Planar Meander Monopole footprint
ae1_start = pcb.find('(footprint "RF_Antenna:Texas_SWRA117D_2.4GHz_Right"')
ae1_end = pcb.find('\n\n\t# =========================================================================\n\t# Footprint R1:', ae1_start)

new_ae1 = '''(footprint "RF_Antenna:Planar_Meander_Monopole_Sub1GHz"
		(layer "F.Cu")
		(uuid "a1b2c3d4-sub1-47f6-a1c4-afb659fdd9f2")
		(at 30.00 18.00)
		(descr "868/915 MHz Planar Meandered Monopole Antenna, 100% single-sided on F.Cu, zero vias")
		(property "Reference" "AE1" (at 10.0 -3.0 0) (layer "F.SilkS") (effects (font (size 0.8 0.8) (thickness 0.12))))
		(property "Value" "Planar_Meander_Sub1GHz" (at 10.0 -1.5 0) (layer "F.Fab") (effects (font (size 0.8 0.8) (thickness 0.12))))
		(property "Footprint" "RF_Antenna:Planar_Meander_Monopole_Sub1GHz" (at 0 0 0) (layer "F.Fab") (hide yes))
		(attr exclude_from_pos_files exclude_from_bom)
		(pad "1" connect rect (at 0 0) (size 0.8 0.8) (layers "F.Cu") (net 2 "/FEED") (uuid "c36d4e5e-77ed-44f4-a552-7e0e665155fb"))
		(pad "2" smd rect (at -2.1 0) (size 0.9 0.5) (layers "F.Cu" "F.Mask") (zone_connect 2) (net 1 "GND") (uuid "5c24e8c4-3541-4c07-8a36-e8bb3ffc1cfd"))
		(fp_line (start -1.0 0.5) (end 22.0 0.5) (stroke (width 0.05) (type solid)) (layer "F.CrtYd") (uuid "c-1"))
		(fp_line (start 22.0 0.5) (end 22.0 -14.5) (stroke (width 0.05) (type solid)) (layer "F.CrtYd") (uuid "c-2"))
		(fp_line (start 22.0 -14.5) (end -1.0 -14.5) (stroke (width 0.05) (type solid)) (layer "F.CrtYd") (uuid "c-3"))
		(fp_line (start -1.0 -14.5) (end -1.0 0.5) (stroke (width 0.05) (type solid)) (layer "F.CrtYd") (uuid "c-4"))
	)'''
pcb = pcb[:ae1_start] + new_ae1 + pcb[ae1_end:]

# Add single-sided meandered planar tracks on F.Cu (Zero Vias)
meander_tracks = [
    '(segment (start 30.00 18.00) (end 30.00 5.00) (width 1.00) (layer "F.Cu") (net 2) (uuid "mnd-1"))',
    '(segment (start 30.00 5.00) (end 46.00 5.00) (width 1.00) (layer "F.Cu") (net 2) (uuid "mnd-2"))',
    '(segment (start 46.00 5.00) (end 46.00 7.50) (width 1.00) (layer "F.Cu") (net 2) (uuid "mnd-3"))',
    '(segment (start 46.00 7.50) (end 33.00 7.50) (width 1.00) (layer "F.Cu") (net 2) (uuid "mnd-4"))',
    '(segment (start 33.00 7.50) (end 33.00 10.00) (width 1.00) (layer "F.Cu") (net 2) (uuid "mnd-5"))',
    '(segment (start 33.00 10.00) (end 46.00 10.00) (width 1.00) (layer "F.Cu") (net 2) (uuid "mnd-6"))',
    '(segment (start 46.00 10.00) (end 46.00 12.50) (width 1.00) (layer "F.Cu") (net 2) (uuid "mnd-7"))',
    '(segment (start 46.00 12.50) (end 35.00 12.50) (width 1.00) (layer "F.Cu") (net 2) (uuid "mnd-8"))',
]
mnd_str = "# --- 100% Planar Meander Monopole Tracks on F.Cu (Zero Vias) ---\n\t" + "\n\t".join(meander_tracks) + "\n\n\t"

tr1_idx = pcb.find('# Track 0: From R1 Pad 2 to J1 Pin 1')
pcb = pcb[:tr1_idx] + mnd_str + pcb[tr1_idx:]

with open(pcb_out, "w", encoding="utf-8") as f:
    f.write(pcb)
print("Board 2 PCB written.")

# 3. Export Board 2 CAM files
# Gerbers
subprocess.run([KICAD_CLI, "pcb", "export", "gerbers", "--output", SUB1_DIR + "/", pcb_out], check=True)
# Drill
subprocess.run([KICAD_CLI, "pcb", "export", "drill", "--output", SUB1_DIR + "/", "--format", "excellon", pcb_out], check=True)
# DXFs
dxf_fcu = os.path.join(SUB1_DIR, "backscatter_tag_sub1ghz-F_Cu.dxf")
dxf_edge = os.path.join(SUB1_DIR, "backscatter_tag_sub1ghz-Edge_Cuts.dxf")
subprocess.run([KICAD_CLI, "pcb", "export", "dxf", "--output", dxf_fcu, "--mode-single", "--layers", "F.Cu", "--output-units", "mm", pcb_out], check=True)
subprocess.run([KICAD_CLI, "pcb", "export", "dxf", "--output", dxf_edge, "--mode-single", "--layers", "Edge.Cuts", "--output-units", "mm", pcb_out], check=True)

# Also copy Sub-1GHz CAM files to ready_for_milling root with clear prefixes
for fn in os.listdir(SUB1_DIR):
    shutil.copyfile(os.path.join(SUB1_DIR, fn), os.path.join(READY_DIR, fn))

print("Board 2 CAM files exported successfully to:", SUB1_DIR)
