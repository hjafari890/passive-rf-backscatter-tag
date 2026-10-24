"""Master Build & Verification Automation for 2.4 GHz (Board 1) and Sub-1GHz (Board 2) KiCad PCB Hardware.

Architecture:
1. Board 1: 2.4 GHz ISM / Wi-Fi (2.44 GHz)
   - Antenna: TI SWRA117D Inverted-F Antenna (IFA)
   - 3-Pin Header (PinHeader_1x03_P2.54mm_Vertical):
     * Pin 1 (Left, X=27.46, Y=23.00): Connected to 50 Ohm 0805 SMD resistor R1 (/TERM_50R)
     * Pin 2 (Center, X=30.00, Y=23.00): Connected to Antenna Feedpoint (/FEED)
     * Pin 3 (Right, X=32.54, Y=23.00): Connected to Ground (GND, 0 Ohm short)
   - Series link R2 (0R 0805)
   - Edge-Launch SMA Connector J2 (Samtec SMA-J-P-H-ST-EM1)
   - Board Outline: 45.0 x 35.0 mm (X in [10.00, 55.00], Y in [10.00, 45.00])
   - Custom DRC milling rules: clearance >= 0.50 mm (>= 0.40 mm), track width >= 0.50 mm

2. Board 2: Sub-1GHz (868/915 MHz)
   - Antenna: TI SWRA416 Miniature Helical Antenna (18.0 x 11.0 mm, 19 vias, 1.0 mm width, 2.0 mm pitch, 9.5 turns)
   - 3-Pin Header (PinHeader_1x03_P2.54mm_Vertical):
     * Pin 1 (Left, X=27.46, Y=23.00): Connected to 50 Ohm 0805 SMD resistor R1 (/TERM_50R)
     * Pin 2 (Center, X=30.00, Y=23.00): Connected to Antenna Feedpoint (/FEED)
     * Pin 3 (Right, X=32.54, Y=23.00): Connected to Ground (GND, 0 Ohm short)
   - Series link R2 (0R 0805)
   - Edge-Launch SMA Connector J2 (Samtec SMA-J-P-H-ST-EM1)
   - Board Outline: 45.0 x 40.0 mm (X in [10.00, 55.00], Y in [5.00, 45.00])
   - Custom DRC milling rules: clearance >= 0.50 mm (>= 0.40 mm), track width >= 0.50 mm

Outputs:
- kicad_pcb/backscatter_tag.kicad_pro, .kicad_sch, .kicad_pcb, .kicad_dru
- kicad_pcb/backscatter_tag_sub1ghz.kicad_pro, .kicad_sch, .kicad_pcb, .kicad_dru
- kicad_pcb/erc_report.txt, kicad_pcb/drc_report.txt
- kicad_pcb/erc_report_sub1ghz.txt, kicad_pcb/drc_report_sub1ghz.txt
- kicad_pcb/gerbers/ & kicad_pcb/dxf/
- kicad_pcb/gerbers_sub1ghz/ & kicad_pcb/dxf_sub1ghz/
- kicad_pcb/pcb_render.png & kicad_pcb/pcb_render_sub1ghz.png
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
KICAD_DIR = os.path.join(BASE_DIR, "kicad_pcb")
KICAD_CLI = r"C:\Program Files\KiCad\9.0\bin\kicad-cli.exe"


def build_board1_24ghz():
    print("--- Building Board 1: 2.4 GHz Tag ---")
    sch_path = os.path.join(KICAD_DIR, "backscatter_tag.kicad_sch")
    pcb_path = os.path.join(KICAD_DIR, "backscatter_tag.kicad_pcb")
    pro_path = os.path.join(KICAD_DIR, "backscatter_tag.kicad_pro")
    dru_path = os.path.join(KICAD_DIR, "backscatter_tag.kicad_dru")

    # 1. Ensure project file has both netclasses
    with open(pro_path, "r", encoding="utf-8") as f:
        pro_data = json.load(f)
    classes = pro_data.setdefault("net_settings", {}).setdefault("classes", [])
    # Update RF_50OHM to include /TERM_50R if needed, or Default
    class_names = [c.get("name") for c in classes]
    if "RF_50OHM" in class_names:
        rf_c = next(c for c in classes if c.get("name") == "RF_50OHM")
        nets = rf_c.setdefault("nets", [])
        for n in ["/FEED", "/SMA_FEED", "/TERM_50R"]:
            if n not in nets:
                nets.append(n)
    with open(pro_path, "w", encoding="utf-8") as f:
        json.dump(pro_data, f, indent=2)

    # 2. Build schematic for Board 1
    # Full, clean schematic string with Conn_01x03 and exact wire coordinates
    sch_content = """(kicad_sch
	(version 20250114)
	(generator "eeschema")
	(generator_version "9.0")
	(uuid "02c01990-2ff0-482c-b26a-93108500257b")
	(paper "A4")
	(title_block
		(title "2.4 GHz RF Backscatter Tag - M2")
		(date "2026-10-20")
		(rev "2.0")
		(company "Backscattering SDR Research")
		(comment 1 "TI SWRA117D 2.4 GHz IFA Layout on F.Cu")
		(comment 2 "3-State Termination: Pos A (1-2) 50R, Pos B (open) +1, Pos C (2-3) 0R Short")
		(comment 3 "Edge-Launch SMA Connector with Calibration Bridge")
		(comment 4 "CNC PCB Isolation Milling Clearance >= 0.40 mm (0.50 mm configured)")
	)
	(lib_symbols
		(symbol "Device:Antenna_Shield"
			(pin_names (offset 1.016) (hide yes))
			(exclude_from_sim no) (in_bom yes) (on_board yes)
			(property "Reference" "AE" (at -1.905 4.445 0) (effects (font (size 1.27 1.27)) (justify right)))
			(property "Value" "Antenna_Shield" (at -1.905 2.54 0) (effects (font (size 1.27 1.27)) (justify right)))
			(property "Footprint" "RF_Antenna:Texas_SWRA117D_2.4GHz_Right" (at 0 2.54 0) (effects (font (size 1.27 1.27)) (hide yes)))
			(property "Datasheet" "http://www.ti.com/lit/an/swra117d/swra117d.pdf" (at 0 2.54 0) (effects (font (size 1.27 1.27)) (hide yes)))
			(property "Description" "TI SWRA117D 2.4 GHz IFA Antenna with Ground Shunt" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
			(symbol "Antenna_Shield_0_1"
				(polyline (pts (xy 0 2.54) (xy 0 -3.81)) (stroke (width 0.254) (type default)) (fill (type none)))
				(polyline (pts (xy 1.27 2.54) (xy 0 -2.54) (xy -1.27 2.54)) (stroke (width 0.254) (type default)) (fill (type none)))
				(polyline (pts (xy 2.54 -2.54) (xy 2.54 -3.81)) (stroke (width 0.254) (type default)) (fill (type none)))
			)
			(symbol "Antenna_Shield_1_1"
				(pin input line (at 0 5.08 270) (length 1.27) (name "Feed" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
				(pin passive line (at 2.54 5.08 270) (length 1.27) (name "GND" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27)))))
			)
		)
		(symbol "Device:R"
			(pin_numbers (hide yes)) (pin_names (offset 0)) (exclude_from_sim no) (in_bom yes) (on_board yes)
			(property "Reference" "R" (at 2.032 0 90) (effects (font (size 1.27 1.27))))
			(property "Value" "R" (at 0 0 90) (effects (font (size 1.27 1.27))))
			(property "Footprint" "" (at -1.778 0 90) (effects (font (size 1.27 1.27)) (hide yes)))
			(property "Datasheet" "~" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
			(property "Description" "Resistor" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
			(symbol "R_0_1"
				(rectangle (start -1.016 -2.54) (end 1.016 2.54) (stroke (width 0.254) (type default)) (fill (type none)))
			)
			(symbol "R_1_1"
				(pin passive line (at 0 3.81 270) (length 1.27) (name "~" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
				(pin passive line (at 0 -3.81 90) (length 1.27) (name "~" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27)))))
			)
		)
		(symbol "Connector_Generic:Conn_01x03"
			(pin_names (offset 1.016) (hide yes)) (exclude_from_sim no) (in_bom yes) (on_board yes)
			(property "Reference" "J" (at 0 2.54 0) (effects (font (size 1.27 1.27))))
			(property "Value" "Conn_01x03" (at 0 -7.62 0) (effects (font (size 1.27 1.27))))
			(property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
			(property "Datasheet" "~" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
			(property "Description" "Generic connector, single row, 01x03" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
			(symbol "Conn_01x03_1_1"
				(rectangle (start -1.27 1.27) (end 1.27 -6.35) (stroke (width 0.254) (type default)) (fill (type background)))
				(pin passive line (at -5.08 0 0) (length 3.81) (name "Pin_1" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
				(pin passive line (at -5.08 -2.54 0) (length 3.81) (name "Pin_2" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27)))))
				(pin passive line (at -5.08 -5.08 0) (length 3.81) (name "Pin_3" (effects (font (size 1.27 1.27)))) (number "3" (effects (font (size 1.27 1.27)))))
			)
		)
		(symbol "Connector:Conn_Coaxial"
			(pin_names (offset 1.016) (hide yes)) (exclude_from_sim no) (in_bom yes) (on_board yes)
			(property "Reference" "J" (at 0 2.54 0) (effects (font (size 1.27 1.27))))
			(property "Value" "Conn_Coaxial" (at 0 -5.08 0) (effects (font (size 1.27 1.27))))
			(property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
			(property "Datasheet" "~" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
			(property "Description" "Coaxial connector (BNC, SMA, SMB, SMC, Cinch/RCA, ...)" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
			(symbol "Conn_Coaxial_1_1"
				(circle (center 0 0) (radius 1.27) (stroke (width 0.254) (type default)) (fill (type none)))
				(circle (center 0 0) (radius 0.254) (stroke (width 0.254) (type default)) (fill (type outline)))
				(pin passive line (at -5.08 0 0) (length 3.81) (name "In" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
				(pin passive line (at 0 -3.81 90) (length 2.54) (name "Ext" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27)))))
			)
		)
		(symbol "power:GND"
			(power) (pin_numbers (hide yes)) (pin_names (offset 0) (hide yes)) (exclude_from_sim no) (in_bom yes) (on_board yes)
			(property "Reference" "#PWR" (at 0 -6.35 0) (effects (font (size 1.27 1.27)) (hide yes)))
			(property "Value" "GND" (at 0 -3.81 0) (effects (font (size 1.27 1.27))))
			(property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
			(property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
			(property "Description" "Power symbol creates a global label with name GND" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
			(symbol "GND_0_1"
				(polyline (pts (xy 0 0) (xy 0 -1.27) (xy 1.27 -1.27) (xy 0 -2.54) (xy -1.27 -1.27) (xy 0 -1.27)) (stroke (width 0) (type default)) (fill (type none)))
			)
			(symbol "GND_1_1"
				(pin power_in line (at 0 0 270) (length 0) (name "~" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
			)
		)
		(symbol "power:PWR_FLAG"
			(power) (pin_numbers (hide yes)) (pin_names (offset 0) (hide yes)) (exclude_from_sim no) (in_bom yes) (on_board yes)
			(property "Reference" "#FLG" (at 0 1.905 0) (effects (font (size 1.27 1.27)) (hide yes)))
			(property "Value" "PWR_FLAG" (at 0 3.81 0) (effects (font (size 1.27 1.27))))
			(property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
			(property "Datasheet" "~" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
			(property "Description" "Special symbol for telling ERC where power comes from" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
			(symbol "PWR_FLAG_0_1"
				(polyline (pts (xy 0 0) (xy 0 1.27) (xy -1.27 1.905) (xy 0 2.54) (xy 1.27 1.905) (xy 0 1.27)) (stroke (width 0) (type default)) (fill (type none)))
			)
			(symbol "PWR_FLAG_1_1"
				(pin power_out line (at 0 0 90) (length 0) (name "~" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
			)
		)
	)

	# --- Primary Antenna Radiator: TI SWRA117D IFA ---
	(symbol (lib_id "Device:Antenna_Shield") (at 60.96 50.80 0) (unit 1)
		(exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)
		(uuid "de7fdbc2-1048-4bcf-a6f7-b3df78099977")
		(property "Reference" "AE1" (at 63.5 45.72 0) (effects (font (size 1.27 1.27))))
		(property "Value" "Texas_SWRA117D_2.4GHz" (at 63.5 48.26 0) (effects (font (size 1.27 1.27))))
		(property "Footprint" "RF_Antenna:Texas_SWRA117D_2.4GHz_Right" (at 60.96 50.80 0) (effects (font (size 1.27 1.27)) (hide yes)))
		(property "Datasheet" "http://www.ti.com/lit/an/swra117d/swra117d.pdf" (at 60.96 50.80 0) (effects (font (size 1.27 1.27)) (hide yes)))
		(property "Description" "2.44 GHz Inverted-F PCB Antenna with 50 Ohm Feed and Ground Shunt" (at 60.96 50.80 0) (effects (font (size 1.27 1.27)) (hide yes)))
		(pin "1" (uuid "cac0e7a7-a9f5-4a7a-926d-512f6d525404"))
		(pin "2" (uuid "8f50ecc6-5bc4-4e91-8519-7f9d9013d06d"))
	)

	# --- Dual Termination Resistor: R1 (49.9 Ohm 1% 0805) ---
	(symbol (lib_id "Device:R") (at 88.9 66.04 0) (unit 1)
		(exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)
		(uuid "9e50b86f-6f3b-4ecb-ac4c-85c90bc6b6eb")
		(property "Reference" "R1" (at 91.44 63.5 0) (effects (font (size 1.27 1.27))))
		(property "Value" "49.9R 1%" (at 91.44 66.04 0) (effects (font (size 1.27 1.27))))
		(property "Footprint" "Resistor_SMD:R_0805_2012Metric" (at 88.9 66.04 0) (effects (font (size 1.27 1.27)) (hide yes)))
		(property "Datasheet" "~" (at 88.9 66.04 0) (effects (font (size 1.27 1.27)) (hide yes)))
		(property "Description" "50 Ohm nominal absorbing termination resistor" (at 88.9 66.04 0) (effects (font (size 1.27 1.27)) (hide yes)))
		(pin "1" (uuid "977ea15b-6e72-496f-a01e-abfb7b10806e"))
		(pin "2" (uuid "9a689557-63a7-45b3-8cf2-9b0bbcc91b6c"))
	)

	# --- 3-State Termination Jumper Switch: J1 (3-pin 2.54mm Header) ---
	(symbol (lib_id "Connector_Generic:Conn_01x03") (at 114.3 58.42 0) (unit 1)
		(exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)
		(uuid "2171f803-fad9-41b9-acbf-e2db1b86ea0f")
		(property "Reference" "J1" (at 116.84 55.88 0) (effects (font (size 1.27 1.27))))
		(property "Value" "PinHeader_1x03_P2.54mm" (at 116.84 58.42 0) (effects (font (size 1.27 1.27))))
		(property "Footprint" "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical" (at 114.3 58.42 0) (effects (font (size 1.27 1.27)) (hide yes)))
		(property "Datasheet" "~" (at 114.3 58.42 0) (effects (font (size 1.27 1.27)) (hide yes)))
		(property "Description" "3-pin jumper header: Pos A (1-2) 50R absorb, Pos B (open) reflect +1, Pos C (2-3) 0R short -1" (at 114.3 58.42 0) (effects (font (size 1.27 1.27)) (hide yes)))
		(pin "1" (uuid "9f20ea6a-3118-4f5c-830a-9f83eebe4b4c"))
		(pin "2" (uuid "4c1aa17f-a592-48b6-8197-0a0c3878d46f"))
		(pin "3" (uuid "f7a8b9c0-1d2e-4f3a-b4c5-d6e7f8a9b0c1"))
	)

	# --- Optional Calibration Disconnect Link: R2 (0 Ohm 0805) ---
	(symbol (lib_id "Device:R") (at 142.24 55.88 90) (unit 1)
		(exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)
		(uuid "0fafdc9d-fc14-4b1e-8996-73ad4ea8a4b9")
		(property "Reference" "R2" (at 142.24 50.8 0) (effects (font (size 1.27 1.27))))
		(property "Value" "0R (Link)" (at 142.24 53.34 0) (effects (font (size 1.27 1.27))))
		(property "Footprint" "Resistor_SMD:R_0805_2012Metric" (at 142.24 55.88 90) (effects (font (size 1.27 1.27)) (hide yes)))
		(property "Datasheet" "~" (at 142.24 55.88 90) (effects (font (size 1.27 1.27)) (hide yes)))
		(property "Description" "0 Ohm Jumper Link to isolate SMA connector during over-the-air tests" (at 142.24 55.88 90) (effects (font (size 1.27 1.27)) (hide yes)))
		(pin "1" (uuid "2e2601c7-c598-4c91-9e79-5ad0fc6ff8fa"))
		(pin "2" (uuid "034e3b12-9214-4e4c-9fef-489025ce1778"))
	)

	# --- Edge-Launch SMA Connector: J2 (Samtec EdgeMount) ---
	(symbol (lib_id "Connector:Conn_Coaxial") (at 167.64 55.88 0) (unit 1)
		(exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)
		(uuid "d98d2b63-5422-4bb7-8eb2-ddedc2c0dde2")
		(property "Reference" "J2" (at 170.18 50.8 0) (effects (font (size 1.27 1.27))))
		(property "Value" "SMA_EdgeMount" (at 170.18 53.34 0) (effects (font (size 1.27 1.27))))
		(property "Footprint" "Connector_Coaxial:SMA_Samtec_SMA-J-P-H-ST-EM1_EdgeMount" (at 167.64 55.88 0) (effects (font (size 1.27 1.27)) (hide yes)))
		(property "Datasheet" "http://suddendocs.samtec.com/prints/sma-j-p-x-st-em1-mkt.pdf" (at 167.64 55.88 0) (effects (font (size 1.27 1.27)) (hide yes)))
		(property "Description" "1.6mm PCB Edge-Launch 50 Ohm SMA Jack for VNA/SDR Calibration" (at 167.64 55.88 0) (effects (font (size 1.27 1.27)) (hide yes)))
		(pin "1" (uuid "a915aa42-897a-4e0a-91b6-bd310c8ac0c5"))
		(pin "2" (uuid "3af5b476-778d-453e-a003-8f531741e6de"))
	)

	# --- Power GND Symbols ---
	(symbol (lib_id "power:GND") (at 63.5 58.42 0) (unit 1)
		(exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)
		(uuid "fb95774c-b203-4e38-bbda-94b32a69df1d")
		(property "Reference" "#PWR01" (at 63.5 64.77 0) (effects (font (size 1.27 1.27)) (hide yes)))
		(property "Value" "GND" (at 63.5 62.23 0) (effects (font (size 1.27 1.27))))
		(pin "1" (uuid "88d8a66f-fb64-47ce-b168-93af65338861"))
	)
	(symbol (lib_id "power:PWR_FLAG") (at 63.5 64.77 0) (unit 1)
		(exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)
		(uuid "d8b64957-71f6-4508-b3dc-442fde6d6440")
		(property "Reference" "#FLG01" (at 63.5 67.31 0) (effects (font (size 1.27 1.27)) (hide yes)))
		(property "Value" "PWR_FLAG" (at 63.5 64.77 0) (effects (font (size 1.27 1.27))))
		(pin "1" (uuid "12dfca23-3f79-4753-96f3-a52053a859eb"))
	)
	(wire (pts (xy 63.5 58.42) (xy 63.5 64.77)) (stroke (width 0) (type default)) (uuid "6d385148-341c-4dc6-a3a9-033d73c9b064"))

	(symbol (lib_id "power:GND") (at 88.9 76.2 0) (unit 1)
		(exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)
		(uuid "fa03f9df-827f-4fe5-9498-0debf465d086")
		(property "Reference" "#PWR02" (at 88.9 82.55 0) (effects (font (size 1.27 1.27)) (hide yes)))
		(property "Value" "GND" (at 88.9 80.01 0) (effects (font (size 1.27 1.27))))
		(pin "1" (uuid "35e02e78-b5bd-4a46-9beb-a5f447173ac6"))
	)
	(symbol (lib_id "power:GND") (at 109.22 68.58 0) (unit 1)
		(exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)
		(uuid "97831b26-14b7-456a-a9cd-ece5b3eed916")
		(property "Reference" "#PWR03" (at 109.22 74.93 0) (effects (font (size 1.27 1.27)) (hide yes)))
		(property "Value" "GND" (at 109.22 72.39 0) (effects (font (size 1.27 1.27))))
		(pin "1" (uuid "4ddf05d8-b0b8-4de0-ad74-2cf105f79793"))
	)
	(symbol (lib_id "power:GND") (at 167.64 64.77 0) (unit 1)
		(exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)
		(uuid "3f7c9574-f145-4142-9314-64bb8b41ea68")
		(property "Reference" "#PWR04" (at 167.64 71.12 0) (effects (font (size 1.27 1.27)) (hide yes)))
		(property "Value" "GND" (at 167.64 68.58 0) (effects (font (size 1.27 1.27))))
		(pin "1" (uuid "bf7bd4c3-9051-463e-aca6-416efbceb020"))
	)

	# --- Interconnecting Wires & Net Labels ---
	(wire (pts (xy 60.96 45.72) (xy 60.96 55.88)) (stroke (width 0) (type default)) (uuid "c1a2b3d4-e5f6-4789-abcd-ef0123456789"))
	(wire (pts (xy 60.96 55.88) (xy 109.22 55.88)) (stroke (width 0) (type default)) (uuid "0dfb5076-0bc6-423d-92a4-e41094190ae9"))
	(junction (at 109.22 55.88) (diameter 0) (color 0 0 0 0) (uuid "bc23a69a-548a-46b9-a709-49c863bd1fe4"))
	(wire (pts (xy 109.22 55.88) (xy 109.22 60.96)) (stroke (width 0) (type default)) (uuid "86e7bc3f-3698-4406-af4d-a1caaa681349"))
	(wire (pts (xy 109.22 55.88) (xy 138.43 55.88)) (stroke (width 0) (type default)) (uuid "dd00a8e9-8a43-465c-85da-bd8dc10bf903"))

	# J1 Pin 1 (/TERM_50R) connects to R1 Pin 1
	(wire (pts (xy 88.9 62.23) (xy 88.9 58.42)) (stroke (width 0) (type default)) (uuid "5c837bd0-fbee-4307-885a-9e960997aa26"))
	(wire (pts (xy 88.9 58.42) (xy 109.22 58.42)) (stroke (width 0) (type default)) (uuid "w-term-50r"))

	# J1 Pin 3 connects to GND #PWR03
	(wire (pts (xy 109.22 63.50) (xy 109.22 68.58)) (stroke (width 0) (type default)) (uuid "f1401e1d-57ed-421f-bb22-81f5ca8abddc"))

	(wire (pts (xy 63.5 45.72) (xy 63.5 58.42)) (stroke (width 0) (type default)) (uuid "bb7b0280-a523-4308-85b3-58924c61ecd2"))
	(wire (pts (xy 88.9 69.85) (xy 88.9 76.2)) (stroke (width 0) (type default)) (uuid "8b385a0b-4c58-480e-b0be-7c4287a6f671"))
	(wire (pts (xy 146.05 55.88) (xy 162.56 55.88)) (stroke (width 0) (type default)) (uuid "a2b39ea7-19c6-4317-92f7-553367e31882"))
	(wire (pts (xy 167.64 59.69) (xy 167.64 64.77)) (stroke (width 0) (type default)) (uuid "db169c8e-65c1-47a9-be78-343ccf4fae19"))

	(label "TERM_50R" (at 99.06 58.42 0) (fields_autoplaced yes) (effects (font (size 1.27 1.27))) (uuid "a1b2c3d4-e5f6-7890-abcd-ef0123456789"))
	(label "FEED" (at 74.93 55.88 0) (fields_autoplaced yes) (effects (font (size 1.27 1.27))) (uuid "dccd03fa-0f7c-46f7-a2a8-8ffb3fd03f7d"))
	(label "SMA_FEED" (at 152.4 55.88 0) (fields_autoplaced yes) (effects (font (size 1.27 1.27))) (uuid "6290f773-67bc-4113-a2b5-5905a8c3e9a0"))

	(sheet_instances
		(path "/" (page "1"))
	)
)
"""
    with open(sch_path, "w", encoding="utf-8") as f:
        f.write(sch_content)
    print(f"Generated Board 1 Schematic: {sch_path}")

    # 3. Build PCB for Board 1
    # Update backscatter_tag.kicad_pcb with 3-pin J1 and R1 at (27.46, 19.50)
    with open(pcb_path, "r", encoding="utf-8") as f:
        pcb = f.read()

    # Net definitions
    if '(net 4 "/TERM_50R")' not in pcb:
        pcb = pcb.replace('\t(net 3 "/SMA_FEED")\n', '\t(net 3 "/SMA_FEED")\n\t(net 4 "/TERM_50R")\n', 1)

    # R1 footprint
    r1_start = pcb.find('(footprint "Resistor_SMD:R_0805_2012Metric"')
    r1_end = pcb.find('\n\n\t# =========================================================================\n\t# Footprint J1:', r1_start)
    r1_new = '''(footprint "Resistor_SMD:R_0805_2012Metric"
		(layer "F.Cu")
		(uuid "b28c20b5-e53d-4017-8fb4-f1b5c0a78dbf")
		(at 27.46 19.50)
		(descr "Resistor SMD 0805 (2012 Metric), 49.9 Ohm 1% absorbing load")
		(property "Reference" "R1" (at -2.5 0 0) (layer "F.SilkS") (effects (font (size 0.8 0.8) (thickness 0.12))))
		(property "Value" "49.9R" (at 2.5 0 0) (layer "F.Fab") (effects (font (size 0.8 0.8) (thickness 0.12))))
		(property "Footprint" "Resistor_SMD:R_0805_2012Metric" (at 0 0 0) (layer "F.Fab") (hide yes))
		(attr smd)
		# Pad 1: GND (top) solidly connected to ground copper
		(pad "1" smd roundrect (at 0 -0.9125) (size 1.4 1.025) (layers "F.Cu" "F.Mask") (roundrect_rratio 0.25) (zone_connect 1) (net 1 "GND") (uuid "7ebc9125-47d0-44dd-b87d-9e2ce67a3100"))
		# Pad 2: TERM_50R (bottom) connected to J1 Pin 1
		(pad "2" smd roundrect (at 0 0.9125) (size 1.4 1.025) (layers "F.Cu" "F.Mask") (roundrect_rratio 0.25) (net 4 "/TERM_50R") (uuid "334d994b-4f1f-4738-87ee-658eca4ab3fd"))
	)'''
    pcb = pcb[:r1_start] + r1_new + pcb[r1_end:]

    # J1 footprint: 3-pin
    j1_start = pcb.find('(footprint "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical"')
    if j1_start == -1:
        j1_start = pcb.find('(footprint "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical"')
    j1_end = pcb.find('\n\n\t# =========================================================================\n\t# Footprint R2:', j1_start)
    j1_new = '''(footprint "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical"
		(layer "F.Cu")
		(uuid "5111a279-3a43-4fe1-8479-3a859cbff0c0")
		(at 30.00 23.00)
		(descr "Through-hole pin header 1x03, 2.54mm pitch (3-State Termination Switching Jumper)")
		(property "Reference" "J1" (at 0 -2.5 0) (layer "F.SilkS") (effects (font (size 0.8 0.8) (thickness 0.12))))
		(property "Value" "PinHeader_1x03_P2.54mm" (at 0 2.5 0) (layer "F.Fab") (effects (font (size 0.8 0.8) (thickness 0.12))))
		(property "Footprint" "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical" (at 0 0 0) (layer "F.Fab") (hide yes))
		(attr through_hole)
		# Pin 1: TERM_50R (at X=-2.54, Y=0 relative -> X=27.46, Y=23.00)
		(pad "1" thru_hole rect (at -2.54 0) (size 1.7 1.7) (drill 1.0) (layers "*.Cu" "*.Mask") (remove_unused_layers no) (net 4 "/TERM_50R") (uuid "bf2b4e4d-bf71-4bfe-8df5-94651205935a"))
		# Pin 2: FEED Center Common (at X=0, Y=0 relative -> X=30.00, Y=23.00)
		(pad "2" thru_hole circle (at 0 0) (size 1.7 1.7) (drill 1.0) (layers "*.Cu" "*.Mask") (remove_unused_layers no) (net 2 "/FEED") (uuid "70ba1674-3b38-495c-b816-9877837472ac"))
		# Pin 3: GND Short (at X=2.54, Y=0 relative -> X=32.54, Y=23.00) solidly connected to GND plane
		(pad "3" thru_hole circle (at 2.54 0) (size 1.7 1.7) (drill 1.0) (layers "*.Cu" "*.Mask") (remove_unused_layers no) (zone_connect 1) (net 1 "GND") (uuid "c8a4b3d2-e1f0-4987-a2b1-5e8c9d0f1a2b"))
	)'''
    pcb = pcb[:j1_start] + j1_new + pcb[j1_end:]

    # Connecting segment from R1 Pad 2 to J1 Pin 1
    if '(net 4) (uuid "term-50r-track-1")' not in pcb:
        term_track = '(segment (start 27.46 20.4125) (end 27.46 23.00) (width 0.50) (layer "F.Cu") (net 4) (uuid "term-50r-track-1"))'
        tr1_idx = pcb.find('# Track 1: From Antenna Feed')
        pcb = pcb[:tr1_idx] + '# Track 0: From R1 Pad 2 to J1 Pin 1 (/TERM_50R)\n\t' + term_track + '\n\n\t' + pcb[tr1_idx:]

    # Left Ground Zone notch on F.Cu
    zone1_old_pts = '''(polygon
			(pts
				(xy 10.50 18.00) (xy 28.50 18.00) (xy 28.50 44.50) (xy 10.50 44.50)
			)
		)
		(filled_polygon
			(pts
				(xy 10.50 18.00) (xy 28.50 18.00) (xy 28.50 44.50) (xy 10.50 44.50)
			)
		)'''
    zone1_new_pts = '''(polygon
			(pts
				(xy 10.50 18.00) (xy 28.50 18.00) (xy 28.50 19.20)
				(xy 26.00 19.20) (xy 26.00 24.50) (xy 28.50 24.50)
				(xy 28.50 44.50) (xy 10.50 44.50)
			)
		)
		(filled_polygon
			(pts
				(xy 10.50 18.00) (xy 28.50 18.00) (xy 28.50 19.20)
				(xy 26.00 19.20) (xy 26.00 24.50) (xy 28.50 24.50)
				(xy 28.50 44.50) (xy 10.50 44.50)
			)
		)'''
    pcb = pcb.replace(zone1_old_pts, zone1_new_pts)

    # Bottom Ground Zone notch on B.Cu
    zone3_old_pts = '''(polygon
			(pts
				(xy 10.50 18.00) (xy 28.50 18.00) (xy 28.50 25.00)
				(xy 31.50 25.00) (xy 31.50 18.00) (xy 54.50 18.00)
				(xy 54.50 44.50) (xy 10.50 44.50)
			)
		)
		(filled_polygon
			(pts
				(xy 10.50 18.00) (xy 28.50 18.00) (xy 28.50 25.00)
				(xy 31.50 25.00) (xy 31.50 18.00) (xy 54.50 18.00)
				(xy 54.50 44.50) (xy 10.50 44.50)
			)
		)'''
    zone3_new_pts = '''(polygon
			(pts
				(xy 10.50 18.00) (xy 26.00 18.00) (xy 26.00 24.50)
				(xy 31.50 24.50) (xy 31.50 18.00) (xy 54.50 18.00)
				(xy 54.50 44.50) (xy 10.50 44.50)
			)
		)
		(filled_polygon
			(pts
				(xy 10.50 18.00) (xy 26.00 18.00) (xy 26.00 24.50)
				(xy 31.50 24.50) (xy 31.50 18.00) (xy 54.50 18.00)
				(xy 54.50 44.50) (xy 10.50 44.50)
			)
		)'''
    pcb = pcb.replace(zone3_old_pts, zone3_new_pts)

    # Silkscreen text
    pcb = pcb.replace("JMP OFF: 50R ABSORB", "JMP 1-2: 50R ABSORB")
    pcb = pcb.replace("JMP ON : 0R REFLECT", "JMP 2-3: 0R REFLECT")

    with open(pcb_path, "w", encoding="utf-8") as f:
        f.write(pcb)
    print(f"Generated Board 1 PCB: {pcb_path}")


def build_board2_sub1ghz():
    print("--- Building Board 2: Sub-1GHz Tag (868/915 MHz SWRA416) ---")
    sch_path = os.path.join(KICAD_DIR, "backscatter_tag_sub1ghz.kicad_sch")
    pcb_path = os.path.join(KICAD_DIR, "backscatter_tag_sub1ghz.kicad_pcb")
    pro_path = os.path.join(KICAD_DIR, "backscatter_tag_sub1ghz.kicad_pro")
    dru_path = os.path.join(KICAD_DIR, "backscatter_tag_sub1ghz.kicad_dru")

    # 1. Project file
    shutil.copyfile(os.path.join(KICAD_DIR, "backscatter_tag.kicad_pro"), pro_path)
    shutil.copyfile(os.path.join(KICAD_DIR, "backscatter_tag.kicad_dru"), dru_path)

    # 2. Schematic for Board 2
    with open(os.path.join(KICAD_DIR, "backscatter_tag.kicad_sch"), "r", encoding="utf-8") as f:
        sch = f.read()

    sch = sch.replace('(title "2.4 GHz RF Backscatter Tag - M2")', '(title "Sub-1GHz (868/915 MHz) RF Backscatter Tag - M2 Option B")')
    sch = sch.replace('(comment 1 "TI SWRA117D 2.4 GHz IFA Layout on F.Cu")', '(comment 1 "TI SWRA416 Sub-1GHz 868/915 MHz Miniature Helical Antenna Layout")')
    sch = sch.replace('(property "Value" "Texas_SWRA117D_2.4GHz"', '(property "Value" "Texas_SWRA416_868MHz_915MHz"')
    sch = sch.replace('(property "Footprint" "RF_Antenna:Texas_SWRA117D_2.4GHz_Right"', '(property "Footprint" "RF_Antenna:Texas_SWRA416_868MHz_915MHz"')
    sch = sch.replace('(property "Datasheet" "http://www.ti.com/lit/an/swra117d/swra117d.pdf"', '(property "Datasheet" "http://www.ti.com/lit/an/swra416/swra416.pdf"')
    sch = sch.replace('(property "Description" "2.44 GHz Inverted-F PCB Antenna with 50 Ohm Feed and Ground Shunt"', '(property "Description" "TI SWRA416 Sub-1GHz 868/915 MHz Miniature Helical PCB Antenna with 50 Ohm Feed and Ground Return"')

    with open(sch_path, "w", encoding="utf-8") as f:
        f.write(sch)
    print(f"Generated Board 2 Schematic: {sch_path}")

    # 3. PCB for Board 2
    with open(os.path.join(KICAD_DIR, "backscatter_tag.kicad_pcb"), "r", encoding="utf-8") as f:
        pcb = f.read()

    # Title & Comments
    pcb = pcb.replace('(title "2.4 GHz RF Backscatter Tag - M2")', '(title "Sub-1GHz (868/915 MHz) RF Backscatter Tag - M2 Option B")')
    pcb = pcb.replace('(comment 1 "TI SWRA117D 2.4 GHz IFA Layout on F.Cu")', '(comment 1 "TI SWRA416 Sub-1GHz 868/915 MHz Helical Antenna Layout")')

    # Edge.Cuts to 45.0 x 40.0 mm (Y: 5.00 to 45.00)
    pcb = pcb.replace('(start 10.00 10.00) (end 55.00 10.00)', '(start 10.00 5.00) (end 55.00 5.00)')
    pcb = pcb.replace('(start 55.00 10.00) (end 55.00 45.00)', '(start 55.00 5.00) (end 55.00 45.00)')
    pcb = pcb.replace('(start 10.00 45.00) (end 10.00 10.00)', '(start 10.00 45.00) (end 10.00 5.00)')

    # Silkscreen text
    pcb = pcb.replace("2.4 GHz RF BACKSCATTER TAG", "SUB-1GHz RF BACKSCATTER TAG")
    pcb = pcb.replace("TI SWRA117D IFA", "TI SWRA416 HELICAL")

    # Replace AE1 footprint with TI SWRA416
    ae1_start = pcb.find('(footprint "RF_Antenna:Texas_SWRA117D_2.4GHz_Right"')
    ae1_end = pcb.find('\n\n\t# =========================================================================\n\t# Footprint R1:', ae1_start)

    new_ae1 = '''(footprint "RF_Antenna:Texas_SWRA416_868MHz_915MHz"
		(layer "F.Cu")
		(uuid "4c852491-438f-47f6-a1c4-afb659fdd9f2")
		(at 30.00 18.00)
		(descr "TI SWRA416 Sub-1GHz 868/915 MHz Miniature Helical Antenna on 1.6 mm FR-4")
		(tags "PCB antenna helical sub-1ghz 868MHz 915MHz")
		(property "Reference" "AE1" (at 9.0 -4.0 0) (layer "F.SilkS") (effects (font (size 0.8 0.8) (thickness 0.12))))
		(property "Value" "Texas_SWRA416_868MHz_915MHz" (at 9.0 -2.5 0) (layer "F.Fab") (effects (font (size 0.8 0.8) (thickness 0.12))))
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
    pcb = pcb[:ae1_start] + new_ae1 + pcb[ae1_end:]

    # Adjust Silkscreen title position & size to prevent Edge.Cuts clipping
    pcb = pcb.replace(
        '(gr_text "SUB-1GHz RF BACKSCATTER TAG" (at 21.00 13.00 0) (layer "F.SilkS")\n\t\t(effects (font (size 0.9 0.9) (thickness 0.14)))',
        '(gr_text "SUB-1GHz RF BACKSCATTER TAG" (at 24.00 13.00 0) (layer "F.SilkS")\n\t\t(effects (font (size 0.8 0.8) (thickness 0.12)))'
    )

    # Add SWRA416 genuine helical copper segments and vias (19 vias, 1.0 mm width, 9.5 turns)
    segments = []
    vias = []
    segments.append('(segment (start 30.00 18.00) (end 30.00 6.30) (width 1.00) (layer "F.Cu") (net 2) (uuid "ant-fcu-0"))')
    vias.append('(via (at 30.00 6.30) (size 1.00) (drill 0.40) (layers "F.Cu" "B.Cu") (net 2) (uuid "ant-via-0"))')

    for i in range(9):
        x = 30.00 + i * 2.00
        x_mid = x + 1.00
        x_next = x + 2.00
        segments.append(f'(segment (start {x:.2f} 6.30) (end {x_mid:.2f} 7.30) (width 1.00) (layer "B.Cu") (net 2) (uuid "ant-bcu1-{i}"))')
        segments.append(f'(segment (start {x_mid:.2f} 7.30) (end {x_mid:.2f} 10.30) (width 1.00) (layer "B.Cu") (net 2) (uuid "ant-bcu2-{i}"))')
        segments.append(f'(segment (start {x_mid:.2f} 10.30) (end {x_next:.2f} 11.30) (width 1.00) (layer "B.Cu") (net 2) (uuid "ant-bcu3-{i}"))')
        vias.append(f'(via (at {x_next:.2f} 11.30) (size 1.00) (drill 0.40) (layers "F.Cu" "B.Cu") (net 2) (uuid "ant-via-bot-{i}"))')
        segments.append(f'(segment (start {x_next:.2f} 11.30) (end {x_next:.2f} 6.30) (width 1.00) (layer "F.Cu") (net 2) (uuid "ant-fcu-{i+1}"))')
        vias.append(f'(via (at {x_next:.2f} 6.30) (size 1.00) (drill 0.40) (layers "F.Cu" "B.Cu") (net 2) (uuid "ant-via-top-{i+1}"))')

    # Connect the 19th via on B.Cu with a short termination stub so it connects on both layers
    segments.append('(segment (start 48.00 6.30) (end 48.00 6.80) (width 1.00) (layer "B.Cu") (net 2) (uuid "ant-bcu-term"))')

    seg_via_block = "# --- TI SWRA416 Helical Antenna Segments & Vias ---\n\t" + "\n\t".join(segments) + "\n\t" + "\n\t".join(vias) + "\n\n\t"

    tr1_idx = pcb.find('# Track 0: From R1 Pad 2 to J1 Pin 1')
    if tr1_idx == -1:
        tr1_idx = pcb.find('# Track 1: From Antenna Feed')
    pcb = pcb[:tr1_idx] + seg_via_block + pcb[tr1_idx:]

    with open(pcb_path, "w", encoding="utf-8") as f:
        f.write(pcb)
    print(f"Generated Board 2 PCB: {pcb_path}")


def run_checks_and_exports_for_board(board_name: str, sch_file: str, pcb_file: str, erc_rpt: str, drc_rpt: str, gerber_dir: str, dxf_dir: str, render_png: str):
    print(f"\n=== Verifying & Exporting {board_name} ===")

    # 1. ERC
    cmd_erc = [KICAD_CLI, "sch", "erc", "--output", erc_rpt, "--severity-all", sch_file]
    print(f"Running ERC: {' '.join(cmd_erc)}")
    res = subprocess.run(cmd_erc, capture_output=True, text=True)
    print(res.stdout)
    assert res.returncode == 0, f"ERC failed on {sch_file}: {res.stderr}"

    with open(erc_rpt, "r", encoding="utf-8") as f:
        erc_text = f.read()
    assert "Errors 0" in erc_text or "0 violations" in erc_text, f"ERC errors in {erc_rpt}:\n{erc_text}"

    # 2. DRC
    cmd_drc = [KICAD_CLI, "pcb", "drc", "--output", drc_rpt, "--severity-all", pcb_file]
    print(f"Running DRC: {' '.join(cmd_drc)}")
    res = subprocess.run(cmd_drc, capture_output=True, text=True)
    print(res.stdout)
    assert res.returncode == 0, f"DRC failed on {pcb_file}: {res.stderr}"

    with open(drc_rpt, "r", encoding="utf-8") as f:
        drc_text = f.read()
    assert ("Found 0 DRC violations" in drc_text) or ("violations **\n0" in drc_text) or ("Found 0 violations" in drc_text), f"DRC violations in {drc_rpt}:\n{drc_text}"
    assert ("Found 0 unconnected" in drc_text) or ("unconnected items **\n0" in drc_text), f"DRC unconnected in {drc_rpt}:\n{drc_text}"

    # 3. Gerbers & Drill
    os.makedirs(gerber_dir, exist_ok=True)
    cmd_gerber = [KICAD_CLI, "pcb", "export", "gerbers", "--output", gerber_dir + "/", pcb_file]
    print(f"Exporting Gerbers to {gerber_dir}/")
    res = subprocess.run(cmd_gerber, capture_output=True, text=True)
    assert res.returncode == 0, f"Gerber export failed: {res.stderr}"

    cmd_drill = [KICAD_CLI, "pcb", "export", "drill", "--output", gerber_dir + "/", pcb_file]
    print(f"Exporting Drill to {gerber_dir}/")
    res = subprocess.run(cmd_drill, capture_output=True, text=True)
    assert res.returncode == 0, f"Drill export failed: {res.stderr}"

    # 4. DXF
    os.makedirs(dxf_dir, exist_ok=True)
    cmd_dxf = [
        KICAD_CLI, "pcb", "export", "dxf",
        "--output", dxf_dir + "/",
        "--layers", "F.Cu,Edge.Cuts",
        "--output-units", "mm",
        pcb_file
    ]
    print(f"Exporting DXF to {dxf_dir}/")
    res = subprocess.run(cmd_dxf, capture_output=True, text=True)
    assert res.returncode == 0, f"DXF export failed: {res.stderr}"

    # 5. 3D Render
    cmd_render = [
        KICAD_CLI, "pcb", "render",
        "--output", render_png,
        "--width", "1600",
        "--height", "1200",
        pcb_file
    ]
    print(f"Exporting 3D Render to {render_png}")
    res = subprocess.run(cmd_render, capture_output=True, text=True)
    assert res.returncode == 0, f"Render failed: {res.stderr}"
    print(f"Render generated: {render_png} ({os.path.getsize(render_png)} bytes)")


def main():
    print("=================================================================")
    print("Executing Full Build for Option A (2.4 GHz) and Option B (Sub-1GHz)")
    print("=================================================================")
    build_board1_24ghz()
    build_board2_sub1ghz()

    # Verify Board 1
    run_checks_and_exports_for_board(
        board_name="Board 1 (2.4 GHz)",
        sch_file=os.path.join(KICAD_DIR, "backscatter_tag.kicad_sch"),
        pcb_file=os.path.join(KICAD_DIR, "backscatter_tag.kicad_pcb"),
        erc_rpt=os.path.join(KICAD_DIR, "erc_report.txt"),
        drc_rpt=os.path.join(KICAD_DIR, "drc_report.txt"),
        gerber_dir=os.path.join(KICAD_DIR, "gerbers"),
        dxf_dir=os.path.join(KICAD_DIR, "dxf"),
        render_png=os.path.join(KICAD_DIR, "pcb_render.png"),
    )

    # Verify Board 2
    run_checks_and_exports_for_board(
        board_name="Board 2 (Sub-1GHz)",
        sch_file=os.path.join(KICAD_DIR, "backscatter_tag_sub1ghz.kicad_sch"),
        pcb_file=os.path.join(KICAD_DIR, "backscatter_tag_sub1ghz.kicad_pcb"),
        erc_rpt=os.path.join(KICAD_DIR, "erc_report_sub1ghz.txt"),
        drc_rpt=os.path.join(KICAD_DIR, "drc_report_sub1ghz.txt"),
        gerber_dir=os.path.join(KICAD_DIR, "gerbers_sub1ghz"),
        dxf_dir=os.path.join(KICAD_DIR, "dxf_sub1ghz"),
        render_png=os.path.join(KICAD_DIR, "pcb_render_sub1ghz.png"),
    )

    print("\n=================================================================")
    print("SUCCESS: Both boards passed 100% of ERC and DRC checks with 0 errors!")
    print("CAM files exported to gerbers/, dxf/, gerbers_sub1ghz/, dxf_sub1ghz/")
    print("=================================================================")


if __name__ == "__main__":
    main()
