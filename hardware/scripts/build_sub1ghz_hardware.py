"""Build and CAM Export Automation for Option B Sub-1GHz Backscatter Tag Hardware.

Generates:
1. kicad_pcb/backscatter_tag_sub1ghz.kicad_pro
2. kicad_pcb/backscatter_tag_sub1ghz.kicad_dru
3. kicad_pcb/backscatter_tag_sub1ghz.kicad_sch
4. kicad_pcb/backscatter_tag_sub1ghz.kicad_pcb
5. kicad_pcb/erc_report_sub1ghz.txt
6. kicad_pcb/drc_report_sub1ghz.txt
7. kicad_pcb/gerbers_sub1ghz/
8. kicad_pcb/dxf_sub1ghz/
9. kicad_pcb/pcb_render_sub1ghz.png
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BOARD1_DIR = os.path.join(BASE_DIR, "board1_ifa_2.4ghz")
BOARD2_DIR = os.path.join(BASE_DIR, "board2_meander_sub1ghz")

KICAD_CLI = "kicad-cli"
for p in [r"C:\Program Files\KiCad\9.0\bin\kicad-cli.exe", r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe", r"C:\Program Files\KiCad\8.0\bin\kicad-cli.exe"]:
    if os.path.isfile(p):
        KICAD_CLI = p
        break

PRO_PATH = os.path.join(BOARD2_DIR, "backscatter_tag_sub1ghz.kicad_pro")
DRU_PATH = os.path.join(BOARD2_DIR, "backscatter_tag_sub1ghz.kicad_dru")
SCH_PATH = os.path.join(BOARD2_DIR, "backscatter_tag_sub1ghz.kicad_sch")
PCB_PATH = os.path.join(BOARD2_DIR, "backscatter_tag_sub1ghz.kicad_pcb")

ERC_RPT = os.path.join(BOARD2_DIR, "erc_report_sub1ghz.txt")
DRC_RPT = os.path.join(BOARD2_DIR, "drc_report_sub1ghz.txt")
GERBERS_DIR = os.path.join(BOARD2_DIR, "gerbers")
DXF_DIR = os.path.join(BOARD2_DIR, "dxf")
RENDER_PNG = os.path.join(BOARD2_DIR, "preview.png")


def create_project_file() -> None:
    """Generate backscatter_tag_sub1ghz.kicad_pro."""
    with open(os.path.join(BOARD1_DIR, "backscatter_tag.kicad_pro"), "r", encoding="utf-8") as f:
        pro_data = json.load(f)

    with open(PRO_PATH, "w", encoding="utf-8") as f:
        json.dump(pro_data, f, indent=2)
    print(f"Generated: {PRO_PATH}")


def create_dru_file() -> None:
    """Generate backscatter_tag_sub1ghz.kicad_dru."""
    dru_content = """(version 1)
# CNC PCB Isolation Milling Custom Design Rules for Sub-1GHz Tag
# Enforces strict >= 0.40 mm (0.50 mm configured) clearance across all copper items
# Enforces minimum trace width >= 0.50 mm

(rule "cnc_milling_isolation_clearance"
   (constraint clearance (min 0.50mm))
   (condition "true")
)

(rule "cnc_milling_trace_width"
   (constraint track_width (min 0.50mm))
   (condition "true")
)

(rule "edge_connector_board_edge_clearance"
   (constraint edge_clearance (min 0.0mm))
   (condition "A.Parent == 'J2' || B.Parent == 'J2'")
)
"""
    with open(DRU_PATH, "w", encoding="utf-8") as f:
        f.write(dru_content)
    print(f"Generated: {DRU_PATH}")


def create_schematic_file() -> None:
    """Generate backscatter_tag_sub1ghz.kicad_sch."""
    with open(os.path.join(KICAD_DIR, "backscatter_tag.kicad_sch"), "r", encoding="utf-8") as f:
        sch_text = f.read()

    # Update title and comments
    sch_mod = sch_text.replace(
        '(title "2.4 GHz RF Backscatter Tag - M2")',
        '(title "Sub-1GHz (868/915 MHz) RF Backscatter Tag - M2 Option B")'
    )
    sch_mod = sch_mod.replace(
        '(comment 1 "TI SWRA117D 2.4 GHz IFA Layout on F.Cu")',
        '(comment 1 "TI SWRA416 Sub-1GHz 868/915 MHz Miniature Helical Antenna")'
    )
    sch_mod = sch_mod.replace(
        '(property "Value" "Texas_SWRA117D_2.4GHz"',
        '(property "Value" "Texas_SWRA416_868MHz_915MHz"'
    )
    sch_mod = sch_mod.replace(
        '(property "Footprint" "RF_Antenna:Texas_SWRA117D_2.4GHz_Right"',
        '(property "Footprint" "RF_Antenna:Texas_SWRA416_868MHz_915MHz"'
    )
    sch_mod = sch_mod.replace(
        '(property "Datasheet" "http://www.ti.com/lit/an/swra117d/swra117d.pdf"',
        '(property "Datasheet" "http://www.ti.com/lit/an/swra416/swra416.pdf"'
    )
    sch_mod = sch_mod.replace(
        '(property "Description" "2.44 GHz Inverted-F PCB Antenna with 50 Ohm Feed and Ground Shunt"',
        '(property "Description" "TI SWRA416 Sub-1GHz 868/915 MHz Miniature Helical PCB Antenna with 50 Ohm Feed and Ground Return"'
    )
    sch_mod = sch_mod.replace(
        '(symbol "Device:Antenna_Shield"',
        '(symbol "Device:Antenna_Shield"'
    )

    with open(SCH_PATH, "w", encoding="utf-8") as f:
        f.write(sch_mod)
    print(f"Generated: {SCH_PATH}")


def create_pcb_file() -> None:
    """Generate backscatter_tag_sub1ghz.kicad_pcb."""
    # Build antenna segments and vias
    # TI SWRA416 Helical Antenna: 19 vias, 1.0 mm trace width, 2.0 mm pitch, 9.5 turns
    # Envelope: 18.0 mm (X: 30.00 to 48.00) x 11.0 mm (Y: 6.30 to 17.30)
    # Feed Pad at (30.00, 18.00) mm
    segments = []
    vias = []

    # Turn 0 on F.Cu: From feed pad (30.00, 18.00) to top via at (30.00, 6.30)
    segments.append('(segment (start 30.00 18.00) (end 30.00 6.30) (width 1.00) (layer "F.Cu") (net 2) (uuid "ant-fcu-0"))')
    vias.append('(via (at 30.00 6.30) (size 1.00) (drill 0.40) (layers "F.Cu" "B.Cu") (net 2) (uuid "ant-via-0"))')

    # 9 full helical turns (turns 1 to 9)
    for i in range(9):
        x = 30.00 + i * 2.00
        x_mid = x + 1.00
        x_next = x + 2.00

        # Diagonal return on B.Cu: (x, 6.30) -> (x_mid, 7.30) -> (x_mid, 10.30) -> (x_next, 11.30)
        segments.append(f'(segment (start {x:.2f} 6.30) (end {x_mid:.2f} 7.30) (width 1.00) (layer "B.Cu") (net 2) (uuid "ant-bcu1-{i}"))')
        segments.append(f'(segment (start {x_mid:.2f} 7.30) (end {x_mid:.2f} 10.30) (width 1.00) (layer "B.Cu") (net 2) (uuid "ant-bcu2-{i}"))')
        segments.append(f'(segment (start {x_mid:.2f} 10.30) (end {x_next:.2f} 11.30) (width 1.00) (layer "B.Cu") (net 2) (uuid "ant-bcu3-{i}"))')

        # Bottom via at (x_next, 11.30)
        vias.append(f'(via (at {x_next:.2f} 11.30) (size 1.00) (drill 0.40) (layers "F.Cu" "B.Cu") (net 2) (uuid "ant-via-bot-{i}"))')

        # Top vertical turn on F.Cu: (x_next, 11.30) to (x_next, 6.30)
        segments.append(f'(segment (start {x_next:.2f} 11.30) (end {x_next:.2f} 6.30) (width 1.00) (layer "F.Cu") (net 2) (uuid "ant-fcu-{i+1}"))')

        # Top via at (x_next, 6.30)
        vias.append(f'(via (at {x_next:.2f} 6.30) (size 1.00) (drill 0.40) (layers "F.Cu" "B.Cu") (net 2) (uuid "ant-via-top-{i+1}"))')

    seg_text = "\n\t".join(segments)
    via_text = "\n\t".join(vias)

    with open(os.path.join(KICAD_DIR, "backscatter_tag.kicad_pcb"), "r", encoding="utf-8") as f:
        pcb_orig = f.read()

    # Update Title
    pcb_mod = pcb_orig.replace("2.4 GHz RF Backscatter Tag - M2", "Sub-1GHz (868/915 MHz) RF Backscatter Tag - M2 Option B")
    pcb_mod = pcb_mod.replace("TI SWRA117D 2.4 GHz IFA Layout on F.Cu", "TI SWRA416 Sub-1GHz 868/915 MHz Helical Antenna Layout")

    # Update Edge.Cuts to 45.0 x 40.0 mm (Y: 5.00 to 45.00)
    pcb_mod = pcb_mod.replace("(start 10.00 10.00) (end 55.00 10.00)", "(start 10.00 5.00) (end 55.00 5.00)")
    pcb_mod = pcb_mod.replace("(start 55.00 10.00) (end 55.00 45.00)", "(start 55.00 5.00) (end 55.00 45.00)")
    pcb_mod = pcb_mod.replace("(start 10.00 45.00) (end 10.00 10.00)", "(start 10.00 45.00) (end 10.00 5.00)")

    # Update Silkscreen
    pcb_mod = pcb_mod.replace("2.4 GHz RF BACKSCATTER TAG", "SUB-1GHz RF BACKSCATTER TAG")
    pcb_mod = pcb_mod.replace("TI SWRA117D IFA", "TI SWRA416 HELICAL")

    # Replace AE1 footprint
    ae1_start = pcb_mod.find('(footprint "RF_Antenna:Texas_SWRA117D_2.4GHz_Right"')
    ae1_end = pcb_mod.find('\n\t)\n\n\t# =========================================================================\n\t# Footprint R1:', ae1_start)
    assert ae1_start != -1 and ae1_end != -1, "AE1 footprint bounds not found"

    new_ae1 = '''(footprint "RF_Antenna:Texas_SWRA416_868MHz_915MHz"
		(layer "F.Cu")
		(uuid "4c852491-438f-47f6-a1c4-afb659fdd9f2")
		(at 30.00 18.00)
		(descr "TI SWRA416 Sub-1GHz 868/915 MHz Miniature Helical Antenna on 1.6 mm FR-4")
		(tags "PCB antenna helical sub-1ghz 868MHz 915MHz")
		(property "Reference" "AE1" (at 9.0 -13.0 0) (layer "F.SilkS") (effects (font (size 0.8 0.8) (thickness 0.12))))
		(property "Value" "Texas_SWRA416_868MHz_915MHz" (at 9.0 -14.5 0) (layer "F.Fab") (effects (font (size 0.8 0.8) (thickness 0.12))))
		(property "Footprint" "RF_Antenna:Texas_SWRA416_868MHz_915MHz" (at 0 0 0) (layer "F.Fab") (hide yes))
		(attr exclude_from_pos_files exclude_from_bom)
		# Pad 1: 50 Ohm Feed
		(pad "1" connect rect (at 0 0) (size 0.5 0.5) (layers "F.Cu") (net 2 "/FEED") (uuid "c36d4e5e-77ed-44f4-a552-7e0e665155fb"))
		# Pad 2: Ground Reference Pad solidly connected to GND plane
		(pad "2" smd rect (at -2.1 0) (size 0.9 0.5) (layers "F.Cu" "F.Mask") (zone_connect 1) (net 1 "GND") (uuid "5c24e8c4-3541-4c07-8a36-e8bb3ffc1cfd"))
		# Antenna Courtyard and Keepout outline (18.0 x 11.0 mm)
		(fp_line (start -0.5 0.5) (end 18.5 0.5) (stroke (width 0.05) (type solid)) (layer "F.CrtYd") (uuid "c-1"))
		(fp_line (start 18.5 0.5) (end 18.5 -12.5) (stroke (width 0.05) (type solid)) (layer "F.CrtYd") (uuid "c-2"))
		(fp_line (start 18.5 -12.5) (end -0.5 -12.5) (stroke (width 0.05) (type solid)) (layer "F.CrtYd") (uuid "c-3"))
		(fp_line (start -0.5 -12.5) (end -0.5 0.5) (stroke (width 0.05) (type solid)) (layer "F.CrtYd") (uuid "c-4"))
	)'''

    pcb_mid = pcb_mod[:ae1_start] + new_ae1 + pcb_mod[ae1_end:]

    # Insert antenna helical segments and vias
    tr1_idx = pcb_mid.find('# Track 1: From Antenna Feed')
    assert tr1_idx != -1, "Track 1 comment not found"

    antenna_block = f'''# --- TI SWRA416 868/915 MHz Helical Antenna Segments & Vias ---
	{seg_text}
	{via_text}

	'''

    pcb_final = pcb_mid[:tr1_idx] + antenna_block + pcb_mid[tr1_idx:]

    with open(PCB_PATH, "w", encoding="utf-8") as f:
        f.write(pcb_final)
    print(f"Generated: {PCB_PATH}")


def run_checks_and_exports() -> None:
    """Run ERC, DRC, Gerber, Drill, DXF, and 3D Render exports."""
    # 1. ERC
    cmd_erc = [KICAD_CLI, "sch", "erc", "--output", ERC_RPT, "--severity-all", SCH_PATH]
    print(f"Running ERC: {' '.join(cmd_erc)}")
    res = subprocess.run(cmd_erc, capture_output=True, text=True)
    print(res.stdout)
    assert res.returncode == 0, f"ERC failed with code {res.returncode}"

    # 2. DRC
    cmd_drc = [KICAD_CLI, "pcb", "drc", "--output", DRC_RPT, "--severity-all", PCB_PATH]
    print(f"Running DRC: {' '.join(cmd_drc)}")
    res = subprocess.run(cmd_drc, capture_output=True, text=True)
    print(res.stdout)
    assert res.returncode == 0, f"DRC failed with code {res.returncode}"

    with open(DRC_RPT, "r", encoding="utf-8") as f:
        drc_text = f.read()
    assert "Found 0 DRC violations" in drc_text or "violations **\n0" in drc_text or "Found 0 violations" in drc_text, f"DRC violations found:\n{drc_text}"
    assert "Found 0 unconnected" in drc_text or "unconnected items **\n0" in drc_text, f"DRC unconnected found:\n{drc_text}"

    # 3. Gerbers Export
    os.makedirs(GERBERS_DIR, exist_ok=True)
    cmd_gerber = [KICAD_CLI, "pcb", "export", "gerbers", "--output", GERBERS_DIR + "/", PCB_PATH]
    print(f"Exporting Gerbers: {' '.join(cmd_gerber)}")
    res = subprocess.run(cmd_gerber, capture_output=True, text=True)
    assert res.returncode == 0, f"Gerber export failed: {res.stderr}"

    cmd_drill = [KICAD_CLI, "pcb", "export", "drill", "--output", GERBERS_DIR + "/", PCB_PATH]
    print(f"Exporting Drill: {' '.join(cmd_drill)}")
    res = subprocess.run(cmd_drill, capture_output=True, text=True)
    assert res.returncode == 0, f"Drill export failed: {res.stderr}"

    # 4. DXF Export
    os.makedirs(DXF_DIR, exist_ok=True)
    cmd_dxf = [
        KICAD_CLI, "pcb", "export", "dxf",
        "--output", DXF_DIR + "/",
        "--layers", "F.Cu,Edge.Cuts",
        "--output-units", "mm",
        PCB_PATH
    ]
    print(f"Exporting DXF: {' '.join(cmd_dxf)}")
    res = subprocess.run(cmd_dxf, capture_output=True, text=True)
    assert res.returncode == 0, f"DXF export failed: {res.stderr}"

    # 5. 3D Render
    cmd_render = [
        KICAD_CLI, "pcb", "render",
        "--output", RENDER_PNG,
        "--width", "1600",
        "--height", "1200",
        PCB_PATH
    ]
    print(f"Exporting 3D Render: {' '.join(cmd_render)}")
    res = subprocess.run(cmd_render, capture_output=True, text=True)
    assert res.returncode == 0, f"3D Render export failed: {res.stderr}"
    print(f"Successfully generated: {RENDER_PNG}")


def main() -> None:
    print("=== Building Option B Sub-1GHz KiCad Hardware ===")
    create_project_file()
    create_dru_file()
    create_schematic_file()
    create_pcb_file()
    run_checks_and_exports()
    print("=== Option B Sub-1GHz Build & Verification Complete ===")


if __name__ == "__main__":
    main()
