"""Builds Board 3: 2.4 GHz Leggiero Bowtie Aperture Antenna Backscatter Tag for zero-via CNC milling, verifies DRC, and exports CAM files."""

import json
import os
import shutil
import subprocess

BASE_DIR = r"."
KICAD_DIR = os.path.join(BASE_DIR, "kicad_pcb(automated)")
READY_DIR = os.path.join(BASE_DIR, "ready_for_milling")
BOARD3_DIR = os.path.join(READY_DIR, "Board3_2.4GHz_Leggiero_Bowtie_Tag")
os.makedirs(BOARD3_DIR, exist_ok=True)

KICAD_CLI = r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"

PRO_PATH = os.path.join(KICAD_DIR, "backscatter_tag_leggiero.kicad_pro")
SCH_PATH = os.path.join(KICAD_DIR, "backscatter_tag_leggiero.kicad_sch")
PCB_PATH = os.path.join(KICAD_DIR, "backscatter_tag_leggiero.kicad_pcb")

def build_board3():
    print("=================================================================")
    print("Building Board 3: Leggiero 2.4 GHz Bowtie Backscatter Tag")
    print("=================================================================")

    # 1. Project file
    shutil.copyfile(os.path.join(KICAD_DIR, "backscatter_tag.kicad_pro"), PRO_PATH)

    # 2. Schematic
    with open(os.path.join(KICAD_DIR, "backscatter_tag.kicad_sch"), "r", encoding="utf-8") as f:
        sch = f.read()
    
    sch = sch.replace('2.4 GHz RF Backscatter Tag - M2', '2.4 GHz Leggiero Bowtie Backscatter Tag - Board 3')
    sch = sch.replace('TI SWRA117D 2.4 GHz IFA Layout on F.Cu', 'Leggiero Bowtie Aperture Antenna with Empty-Space Cavity')
    sch = sch.replace('Texas_SWRA117D_2.4GHz', 'Leggiero_Bowtie_2.4GHz')
    sch = sch.replace('RF_Antenna:Texas_SWRA117D_2.4GHz_Right', 'RF_Antenna:Leggiero_Bowtie_2.4GHz')
    
    with open(SCH_PATH, "w", encoding="utf-8") as f:
        f.write(sch)
    print("Board 3 Schematic created.")

    # 3. PCB Layout
    # Dimensions: 50.0 mm x 45.0 mm (X in [5.00, 55.00], Y in [5.00, 50.00])
    # Antenna apex at (30.00, 16.00)
    # Bowtie wings: R = 10.16 mm, 80 deg sector
    # Cavity keepout: X in [12.00, 48.00], Y in [5.00, 26.00] (bare FR-4)
    # Ground plane: surrounds cavity and flanks feedline below Y=26.00 mm
    
    # Footprint AE1: Leggiero Bowtie Antenna
    ae1_fp = '''(footprint "RF_Antenna:Leggiero_Bowtie_2.4GHz"
		(layer "F.Cu")
		(uuid "ae1-leggiero-bowtie-24ghz")
		(at 30.00 16.00)
		(descr "2.4 GHz Bowtie Aperture Antenna from Leggiero (R=10.16 mm, 80 deg sector wings on F.Cu)")
		(property "Reference" "AE1" (at 0 -10.0 0) (layer "F.SilkS") (effects (font (size 0.8 0.8) (thickness 0.12))))
		(property "Value" "Leggiero_Bowtie_2.4GHz" (at 0 -8.5 0) (layer "F.Fab") (effects (font (size 0.8 0.8) (thickness 0.12))))
		(property "Footprint" "RF_Antenna:Leggiero_Bowtie_2.4GHz" (at 0 0 0) (layer "F.Fab") (hide yes))
		(attr exclude_from_pos_files exclude_from_bom)
		# Pad 1: Feed point at center apex
		(pad "1" connect rect (at 0 0) (size 1.0 1.0) (layers "F.Cu") (net 2 "/FEED") (uuid "ae1-pad-feed"))
		# Pad 2: GND reference pad solidly tied to surrounding ground
		(pad "2" smd rect (at -17.0 0) (size 1.5 1.0) (layers "F.Cu" "F.Mask") (zone_connect 2) (net 1 "GND") (uuid "ae1-pad-gnd"))
		# Right Bowtie Wing (fp_poly)
		(fp_poly
			(pts
				(xy 0 0)
				(xy 7.783 -6.531)
				(xy 9.00 -5.0)
				(xy 9.80 -3.0)
				(xy 10.16 0)
				(xy 9.80 3.0)
				(xy 9.00 5.0)
				(xy 7.783 6.531)
				(xy 0 0)
			)
			(stroke (width 0) (type solid))
			(fill yes)
			(layer "F.Cu")
			(uuid "fp-poly-bowtie-right")
		)
		# Left Bowtie Wing (fp_poly)
		(fp_poly
			(pts
				(xy 0 0)
				(xy -7.783 -6.531)
				(xy -9.00 -5.0)
				(xy -9.80 -3.0)
				(-10.16 0)
				(xy -9.80 3.0)
				(xy -9.00 5.0)
				(xy -7.783 6.531)
				(xy 0 0)
			)
			(stroke (width 0) (type solid))
			(fill yes)
			(layer "F.Cu")
			(uuid "fp-poly-bowtie-left")
		)
		# Cavity keepout courtyard (36.0 x 22.0 mm)
		(fp_line (start -18.0 -11.0) (end 18.0 -11.0) (stroke (width 0.05) (type solid)) (layer "F.CrtYd") (uuid "c-1"))
		(fp_line (start 18.0 -11.0) (end 18.0 11.0) (stroke (width 0.05) (type solid)) (layer "F.CrtYd") (uuid "c-2"))
		(fp_line (start 18.0 11.0) (end -18.0 11.0) (stroke (width 0.05) (type solid)) (layer "F.CrtYd") (uuid "c-3"))
		(fp_line (start -18.0 11.0) (end -18.0 -11.0) (stroke (width 0.05) (type solid)) (layer "F.CrtYd") (uuid "c-4"))
	)'''

    # Fix typo in left wing points (-10.16 -> (xy -10.16 0))
    ae1_fp = ae1_fp.replace('(-10.16 0)', '(xy -10.16 0)')

    # Load Board 1 PCB as base
    with open(os.path.join(KICAD_DIR, "backscatter_tag.kicad_pcb"), "r", encoding="utf-8") as f:
        pcb = f.read()

    pcb = pcb.replace('2.4 GHz RF Backscatter Tag - M2', '2.4 GHz Leggiero Bowtie Tag - Board 3')
    pcb = pcb.replace('2.4 GHz RF BACKSCATTER TAG', 'LEGGIERO BOWTIE 2.4GHz')
    pcb = pcb.replace('TI SWRA117D IFA', 'BOWTIE APERTURE')

    # Update Edge.Cuts to 50.0 mm x 45.0 mm (X in [5.00, 55.00], Y in [5.00, 50.00])
    pcb = pcb.replace('(start 10.00 10.00) (end 55.00 10.00)', '(start 5.00 5.00) (end 55.00 5.00)')
    pcb = pcb.replace('(start 55.00 10.00) (end 55.00 45.00)', '(start 55.00 5.00) (end 55.00 50.00)')
    pcb = pcb.replace('(start 55.00 45.00) (end 10.00 45.00)', '(start 55.00 50.00) (end 5.00 50.00)')
    pcb = pcb.replace('(start 10.00 45.00) (end 10.00 10.00)', '(start 5.00 50.00) (end 5.00 5.00)')

    # Replace AE1 footprint
    ae1_start = pcb.find('(footprint "RF_Antenna:Texas_SWRA117D_2.4GHz_Right"')
    ae1_end = pcb.find('\n\n\t# =========================================================================\n\t# Footprint R1:', ae1_start)
    pcb = pcb[:ae1_start] + ae1_fp + pcb[ae1_end:]

    # Components positions:
    # J1 at (30.00, 28.00)
    # R1 at (27.46, 24.50)
    # R2 at (30.00, 37.00)
    # SMA J2 at (30.00, 48.40)
    pcb = pcb.replace('(at 30.00 23.00)', '(at 30.00 28.00)')
    pcb = pcb.replace('(at 27.46 19.50)', '(at 27.46 24.50)')
    pcb = pcb.replace('(at 30.00 32.00)', '(at 30.00 37.00)')
    pcb = pcb.replace('(at 30.00 43.40)', '(at 30.00 48.40)')

    # Tracks:
    # Track 0: From R1 Pad 2 (27.46, 25.4125) to J1 Pin 1 (27.46, 28.00)
    pcb = pcb.replace('(start 27.46 20.4125) (end 27.46 23.00)', '(start 27.46 25.4125) (end 27.46 28.00)')
    # Track 1: From Bowtie Apex (30, 16) to J1 Pin 2 (30, 28)
    pcb = pcb.replace('(start 30.00 18.00) (end 30.00 23.00)', '(start 30.00 16.00) (end 30.00 28.00)')
    # Track 2: From J1 Pin 2 (30, 28) to R2 Pad 1 (30, 35.50)
    pcb = pcb.replace('(start 30.00 23.00) (end 30.00 30.50)', '(start 30.00 28.00) (end 30.00 35.50)')
    # Track 3: From R2 Pad 2 (30, 38.50) to SMA Pad 1 (30, 48.40)
    pcb = pcb.replace('(start 30.00 33.50) (end 30.00 43.40)', '(start 30.00 38.50) (end 30.00 48.40)')

    # Update Ground Zones to surround the Leggiero cavity:
    # Left Ground on F.Cu:
    # Encloses from X=5.50 to X=28.50, Y=5.50 to 49.50, but keeps out X in [12.0, 28.5] for Y in [5.5, 27.0]!
    # That creates the exact Leggiero empty cavity!
    zone_left = '''(zone
		(net 1)
		(net_name "GND")
		(layer "F.Cu")
		(uuid "zone-left-leggiero")
		(hatch edge 0.5)
		(connect_pads (clearance 0.50))
		(min_thickness 0.25)
		(filled_areas_thickness no)
		(fill yes (thermal_gap 0.50) (thermal_bridge_width 0.50))
		(polygon
			(pts
				(xy 5.50 5.50) (xy 12.00 5.50) (xy 12.00 27.00)
				(xy 26.00 27.00) (xy 26.00 29.50) (xy 28.50 29.50)
				(xy 28.50 49.50) (xy 5.50 49.50)
			)
		)
		(filled_polygon
			(pts
				(xy 5.50 5.50) (xy 12.00 5.50) (xy 12.00 27.00)
				(xy 26.00 27.00) (xy 26.00 29.50) (xy 28.50 29.50)
				(xy 28.50 49.50) (xy 5.50 49.50)
			)
		)
	)'''

    # Right Ground on F.Cu:
    # Encloses from X=31.50 to 54.50, Y=5.50 to 49.50, keeping out X in [31.5, 48.0] for Y in [5.5, 27.0]!
    zone_right = '''(zone
		(net 1)
		(net_name "GND")
		(layer "F.Cu")
		(uuid "zone-right-leggiero")
		(hatch edge 0.5)
		(connect_pads (clearance 0.50))
		(min_thickness 0.25)
		(filled_areas_thickness no)
		(fill yes (thermal_gap 0.50) (thermal_bridge_width 0.50))
		(polygon
			(pts
				(xy 48.00 5.50) (xy 54.50 5.50) (xy 54.50 49.50)
				(xy 31.50 49.50) (xy 31.50 27.00) (xy 48.00 27.00)
			)
		)
		(filled_polygon
			(pts
				(xy 48.00 5.50) (xy 54.50 5.50) (xy 54.50 49.50)
				(xy 31.50 49.50) (xy 31.50 27.00) (xy 48.00 27.00)
			)
		)
	)'''

    # Replace existing zones with new Leggiero cavity zones
    z1_start = pcb.find('# Zone 1: Left Top Ground on F.Cu')
    z_end = pcb.rfind('\n)') # before last paren
    pcb = pcb[:z1_start] + "# Leggiero Ground Zones (Empty Space Cavity Around Bowtie Antenna)\n\t" + zone_left + "\n\n\t" + zone_right + "\n)"

    with open(PCB_PATH, "w", encoding="utf-8") as f:
        f.write(pcb)
    print("Board 3 PCB layout generated.")

    # 4. Run DRC on Board 3
    drc_rpt = os.path.join(BOARD3_DIR, "drc_report.txt")
    res_drc = subprocess.run([KICAD_CLI, "pcb", "drc", "--output", drc_rpt, "--severity-all", PCB_PATH], capture_output=True, text=True)
    print(f"DRC run result: {res_drc.returncode}")
    with open(drc_rpt, "r", encoding="utf-8") as f:
        print(f.read()[:500])

    # 5. Export CAM files for Board 3
    # Gerbers
    subprocess.run([KICAD_CLI, "pcb", "export", "gerbers", "--output", BOARD3_DIR + "/", PCB_PATH], check=True)
    # Drill
    subprocess.run([KICAD_CLI, "pcb", "export", "drill", "--output", BOARD3_DIR + "/", "--format", "excellon", PCB_PATH], check=True)
    # DXFs (1:1 mm metric scale)
    dxf_fcu = os.path.join(BOARD3_DIR, "backscatter_tag_leggiero-F_Cu.dxf")
    dxf_edge = os.path.join(BOARD3_DIR, "backscatter_tag_leggiero-Edge_Cuts.dxf")
    subprocess.run([KICAD_CLI, "pcb", "export", "dxf", "--output", dxf_fcu, "--mode-single", "--layers", "F.Cu", "--output-units", "mm", PCB_PATH], check=True)
    subprocess.run([KICAD_CLI, "pcb", "export", "dxf", "--output", dxf_edge, "--mode-single", "--layers", "Edge.Cuts", "--output-units", "mm", PCB_PATH], check=True)

    # Also copy main files to ready_for_milling root
    for fn in ["backscatter_tag_leggiero-F_Cu.gtl", "backscatter_tag_leggiero-Edge_Cuts.gm1", "backscatter_tag_leggiero.drl", "backscatter_tag_leggiero-F_Cu.dxf", "backscatter_tag_leggiero-Edge_Cuts.dxf"]:
        src = os.path.join(BOARD3_DIR, fn)
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(READY_DIR, fn))

    print("Board 3 exported successfully to:", BOARD3_DIR)

if __name__ == '__main__':
    build_board3()
