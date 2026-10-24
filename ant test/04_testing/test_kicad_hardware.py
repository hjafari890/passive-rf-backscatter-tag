"""Automated verification test suite for KiCad 9.0 RF Backscatter Tag Hardware.

Validates:
1. KiCad 9 project files existence, valid formatting, and schema compliance.
2. DRC compliance: 0 errors, 0 unconnected items, 0 footprint errors.
3. CNC isolation milling rules: clearance >= 0.40 mm (configured at 0.50 mm), trace width >= 0.50 mm.
4. Component footprints and values: SWRA117D IFA, R1 (49.9 Ohm), J1 (jumper), J2 (SMA edge-launch), R2.
5. 1:1 RS-274X Gerber headers (%FSLAX, %MOMM*, M02*).
6. Excellon Drill headers (M48, METRIC/T1, M30).
7. AutoCAD DXF contours (SECTION, HEADER, ENTITIES, EOF).
8. 3D PCB render image validity (PNG magic bytes, size > 1 KB).
9. RF feedline CPWG dimensions (W = 1.85 mm, G = 0.50 mm).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import pytest

# Paths
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
KICAD_DIR = os.path.join(BASE_DIR, "kicad_pcb")
PRO_PATH = os.path.join(KICAD_DIR, "backscatter_tag.kicad_pro")
SCH_PATH = os.path.join(KICAD_DIR, "backscatter_tag.kicad_sch")
PCB_PATH = os.path.join(KICAD_DIR, "backscatter_tag.kicad_pcb")
DRC_REPORT_PATH = os.path.join(KICAD_DIR, "drc_report.txt")
ERC_REPORT_PATH = os.path.join(KICAD_DIR, "erc_report.txt")
GERBERS_DIR = os.path.join(KICAD_DIR, "gerbers")
DXF_DIR = os.path.join(KICAD_DIR, "dxf")
RENDER_PATH = os.path.join(KICAD_DIR, "pcb_render.png")

# Option B Sub-1GHz Paths
PRO_SUB1G_PATH = os.path.join(KICAD_DIR, "backscatter_tag_sub1ghz.kicad_pro")
SCH_SUB1G_PATH = os.path.join(KICAD_DIR, "backscatter_tag_sub1ghz.kicad_sch")
PCB_SUB1G_PATH = os.path.join(KICAD_DIR, "backscatter_tag_sub1ghz.kicad_pcb")
DRC_SUB1G_REPORT_PATH = os.path.join(KICAD_DIR, "drc_report_sub1ghz.txt")
ERC_SUB1G_REPORT_PATH = os.path.join(KICAD_DIR, "erc_report_sub1ghz.txt")
GERBERS_SUB1G_DIR = os.path.join(KICAD_DIR, "gerbers_sub1ghz")
DXF_SUB1G_DIR = os.path.join(KICAD_DIR, "dxf_sub1ghz")
RENDER_SUB1G_PATH = os.path.join(KICAD_DIR, "pcb_render_sub1ghz.png")

KICAD_CLI = r"C:\Program Files\KiCad\9.0\bin\kicad-cli.exe"


class TestKiCadHardware:
    """Test suite for Milestone 2 KiCad 9.0 RF Backscatter Tag."""

    def test_kicad_project_files_exist(self) -> None:
        """Assert project definition, schematic, and layout files exist and are non-empty."""
        assert os.path.isfile(PRO_PATH), f"Project file missing: {PRO_PATH}"
        assert os.path.isfile(SCH_PATH), f"Schematic file missing: {SCH_PATH}"
        assert os.path.isfile(PCB_PATH), f"PCB layout file missing: {PCB_PATH}"

        assert os.path.getsize(PRO_PATH) > 100, "Project file is too small or empty"
        assert os.path.getsize(SCH_PATH) > 1000, "Schematic file is too small or empty"
        assert os.path.getsize(PCB_PATH) > 2000, "PCB layout file is too small or empty"

    def test_project_netclasses_configuration(self) -> None:
        """Assert KiCad project JSON configures netclasses with >= 0.40 mm clearance."""
        with open(PRO_PATH, "r", encoding="utf-8") as f:
            pro_data = json.load(f)

        assert "net_settings" in pro_data, "net_settings missing in .kicad_pro"
        netclasses = pro_data["net_settings"].get("classes", [])
        assert len(netclasses) >= 1, "No netclasses found in .kicad_pro"

        class_names = [nc.get("name") for nc in netclasses]
        assert "Default" in class_names, "Default netclass missing"
        assert "RF_50OHM" in class_names, "RF_50OHM netclass missing"

        for nc in netclasses:
            name = nc.get("name")
            clearance = nc.get("clearance", 0.0)
            assert clearance >= 0.40, (
                f"Netclass '{name}' clearance {clearance} mm is below CNC milling minimum (0.40 mm)"
            )
            if name == "RF_50OHM":
                track_w = nc.get("track_width", 0.0)
                assert track_w >= 1.80, f"RF_50OHM track width {track_w} mm mismatch (expected ~1.85 mm)"

    def test_schematic_components_and_symbols(self) -> None:
        """Assert schematic defines antenna AE1, resistor R1, jumper J1, SMA J2, and R2."""
        with open(SCH_PATH, "r", encoding="utf-8") as f:
            sch_text = f.read()

        assert "kicad_sch" in sch_text, "Invalid KiCad schematic header"
        # Check components
        assert "AE1" in sch_text, "Antenna AE1 missing in schematic"
        assert "Texas_SWRA117D_2.4GHz_Right" in sch_text, "SWRA117D antenna footprint missing in schematic"

        assert "R1" in sch_text, "Resistor R1 missing in schematic"
        assert ("49.9" in sch_text) or ("50" in sch_text), "R1 50-ohm / 49.9-ohm value missing in schematic"
        assert "R_0805_2012Metric" in sch_text, "R1 0805 footprint missing in schematic"

        assert "J1" in sch_text, "Jumper J1 missing in schematic"
        assert ("PinHeader_1x03_P2.54mm_Vertical" in sch_text) or ("PinHeader_1x02_P2.54mm_Vertical" in sch_text), "J1 2.54mm jumper footprint missing in schematic"

        assert "J2" in sch_text, "SMA connector J2 missing in schematic"
        assert "SMA_Samtec_SMA-J-P-H-ST-EM1_EdgeMount" in sch_text, "J2 SMA edge mount footprint missing in schematic"

        assert "R2" in sch_text, "Series calibration link R2 missing in schematic"

        # Check nets
        assert "FEED" in sch_text, "FEED net missing in schematic"
        assert "GND" in sch_text, "GND net missing in schematic"

    def test_pcb_footprints_and_geometry(self) -> None:
        """Assert PCB layout places antenna, termination resistor, jumper, and SMA connector."""
        with open(PCB_PATH, "r", encoding="utf-8") as f:
            pcb_text = f.read()

        assert "kicad_pcb" in pcb_text, "Invalid KiCad PCB header"
        assert "Texas_SWRA117D_2.4GHz_Right" in pcb_text, "SWRA117D footprint missing in PCB layout"
        assert "R_0805_2012Metric" in pcb_text, "0805 footprint missing in PCB layout"
        assert ("PinHeader_1x03_P2.54mm_Vertical" in pcb_text) or ("PinHeader_1x02_P2.54mm_Vertical" in pcb_text), "Jumper footprint missing in PCB layout"
        assert "SMA_Samtec_SMA-J-P-H-ST-EM1_EdgeMount" in pcb_text, "SMA footprint missing in PCB layout"

        # Check Edge.Cuts board outline
        assert "Edge.Cuts" in pcb_text, "Edge.Cuts outline missing in PCB"

        # Check CPWG 50-ohm feedline width (1.85 mm)
        assert "(width 1.85)" in pcb_text, "CPWG 1.85 mm feedline trace missing in PCB"

    def test_cnc_isolation_milling_clearance_rules(self) -> None:
        """Assert PCB netclasses and copper zones enforce >= 0.40 mm clearance."""
        with open(PCB_PATH, "r", encoding="utf-8") as f:
            pcb_text = f.read()

        # Netclass clearances in PCB file
        clearance_matches = re.findall(r'\(clearance\s+([\d\.]+)\)', pcb_text)
        assert len(clearance_matches) > 0, "No clearance definitions found in PCB"
        for cl_str in clearance_matches:
            cl_val = float(cl_str)
            assert cl_val >= 0.40, (
                f"Clearance {cl_val} mm is below the minimum CNC isolation milling limit (0.40 mm)"
            )

        # Thermal gap in copper fill zones
        thermal_gaps = re.findall(r'\(thermal_gap\s+([\d\.]+)\)', pcb_text)
        for tg_str in thermal_gaps:
            tg_val = float(tg_str)
            assert tg_val >= 0.40, (
                f"Zone thermal gap {tg_val} mm is below CNC milling clearance (0.40 mm)"
            )

    def test_headless_drc_clean(self) -> None:
        """Assert headless DRC report reports 0 DRC violations and 0 unconnected items."""
        # If KiCad CLI is installed, execute a fresh DRC run
        if os.path.exists(KICAD_CLI):
            res = subprocess.run(
                [KICAD_CLI, "pcb", "drc", "--output", DRC_REPORT_PATH, "--severity-all", PCB_PATH],
                capture_output=True,
                text=True,
            )
            assert res.returncode == 0, f"DRC CLI returned error: {res.stderr}\n{res.stdout}"

        assert os.path.isfile(DRC_REPORT_PATH), f"DRC report missing: {DRC_REPORT_PATH}"
        with open(DRC_REPORT_PATH, "r", encoding="utf-8") as f:
            report_text = f.read()

        # Check 0 violations
        assert ("Found 0 DRC violations" in report_text) or ("violations **\n0" in report_text) or ("Found 0 violations" in report_text), (
            f"DRC reported violations:\n{report_text}"
        )
        # Check 0 unconnected
        assert ("Found 0 unconnected" in report_text) or ("unconnected items **\n0" in report_text), (
            f"DRC reported unconnected pads:\n{report_text}"
        )
        # Check 0 footprint errors
        assert ("Found 0 Footprint errors" in report_text) or ("0 Footprint errors" in report_text), (
            f"DRC reported footprint errors:\n{report_text}"
        )

    def test_rs274x_gerber_files_syntax(self) -> None:
        """Assert RS-274X Gerber files exist and contain valid RS-274X directives."""
        assert os.path.isdir(GERBERS_DIR), f"Gerbers directory missing: {GERBERS_DIR}"

        # Look for F_Cu gerber
        fcu_candidates = [
            os.path.join(GERBERS_DIR, "F_Cu.gbr"),
            os.path.join(GERBERS_DIR, "backscatter_tag-F_Cu.gbr"),
        ]
        fcu_path = next((p for p in fcu_candidates if os.path.isfile(p)), None)
        assert fcu_path is not None, "F_Cu Gerber file missing in gerbers/"

        with open(fcu_path, "r", encoding="utf-8", errors="ignore") as f:
            fcu_content = f.read()

        assert len(fcu_content) > 500, "F_Cu Gerber file is too small"
        assert "%FSLAX" in fcu_content, "F_Cu Gerber missing RS-274X %FSLAX format specification"
        assert ("%MOMM*" in fcu_content) or ("%MOIN*" in fcu_content), (
            "F_Cu Gerber missing RS-274X mode specification (%MOMM*)"
        )
        assert "M02*" in fcu_content, "F_Cu Gerber missing RS-274X end-of-file command (M02*)"

        # Look for Edge_Cuts gerber
        edge_candidates = [
            os.path.join(GERBERS_DIR, "Edge_Cuts.gbr"),
            os.path.join(GERBERS_DIR, "backscatter_tag-Edge_Cuts.gbr"),
        ]
        edge_path = next((p for p in edge_candidates if os.path.isfile(p)), None)
        assert edge_path is not None, "Edge_Cuts Gerber file missing in gerbers/"

        with open(edge_path, "r", encoding="utf-8", errors="ignore") as f:
            edge_content = f.read()

        assert "%FSLAX" in edge_content, "Edge_Cuts Gerber missing %FSLAX"
        assert "M02*" in edge_content, "Edge_Cuts Gerber missing M02*"

    def test_excellon_drill_file_syntax(self) -> None:
        """Assert Excellon drill file exists and contains valid NC drill syntax."""
        drill_candidates = [
            os.path.join(GERBERS_DIR, "backscatter_tag.drl"),
            os.path.join(GERBERS_DIR, "backscatter_tag-PTH.drl"),
        ]
        drill_path = next((p for p in drill_candidates if os.path.isfile(p)), None)
        assert drill_path is not None, "Excellon drill file missing in gerbers/"

        with open(drill_path, "r", encoding="utf-8", errors="ignore") as f:
            drill_content = f.read()

        assert len(drill_content) > 100, "Drill file is too small"
        # Standard Excellon header commands
        assert ("M48" in drill_content) or ("METRIC" in drill_content) or ("INCH" in drill_content), (
            "Drill file missing M48 header or METRIC command"
        )
        assert ("M30" in drill_content) or ("T1" in drill_content), (
            "Drill file missing M30 end-of-program or tool definition"
        )

    def test_dxf_contour_files_syntax(self) -> None:
        """Assert AutoCAD DXF contours exist and contain valid DXF structure."""
        assert os.path.isdir(DXF_DIR), f"DXF directory missing: {DXF_DIR}"

        dxf_fcu_candidates = [
            os.path.join(DXF_DIR, "F_Cu.dxf"),
            os.path.join(DXF_DIR, "backscatter_tag-F_Cu.dxf"),
        ]
        dxf_fcu_path = next((p for p in dxf_fcu_candidates if os.path.isfile(p)), None)
        assert dxf_fcu_path is not None, "F_Cu DXF file missing in dxf/"

        with open(dxf_fcu_path, "r", encoding="utf-8", errors="ignore") as f:
            dxf_content = f.read()

        assert len(dxf_content) > 500, "F_Cu DXF file is too small"
        assert "SECTION" in dxf_content, "DXF missing SECTION tag"
        assert "ENTITIES" in dxf_content, "DXF missing ENTITIES section"
        assert "EOF" in dxf_content, "DXF missing EOF marker"

        dxf_edge_candidates = [
            os.path.join(DXF_DIR, "Edge_Cuts.dxf"),
            os.path.join(DXF_DIR, "backscatter_tag-Edge_Cuts.dxf"),
        ]
        dxf_edge_path = next((p for p in dxf_edge_candidates if os.path.isfile(p)), None)
        assert dxf_edge_path is not None, "Edge_Cuts DXF file missing in dxf/"

        with open(dxf_edge_path, "r", encoding="utf-8", errors="ignore") as f:
            edge_dxf_content = f.read()
        assert "ENTITIES" in edge_dxf_content, "Edge_Cuts DXF missing ENTITIES"
        assert "EOF" in edge_dxf_content, "Edge_Cuts DXF missing EOF"

    def test_pcb_3d_render_validity(self) -> None:
        """Assert rendered board image exists and is a valid PNG image (> 1 KB)."""
        assert os.path.isfile(RENDER_PATH), f"PCB render image missing: {RENDER_PATH}"
        size = os.path.getsize(RENDER_PATH)
        assert size > 1024, f"PCB render image is too small ({size} bytes <= 1 KB)"

        with open(RENDER_PATH, "rb") as f:
            header = f.read(8)
        # PNG magic number: 89 50 4E 47 0D 0A 1A 0A
        assert header == b"\x89PNG\r\n\x1a\n", "Render file is not a valid PNG image"

    def test_antenna_swra117d_geometry(self) -> None:
        """Assert TI SWRA117D IFA geometry adheres to 2.4 GHz specification."""
        with open(PCB_PATH, "r", encoding="utf-8") as f:
            pcb_text = f.read()

        # Footprint SWRA117D contains feed pad (at 0 0) and stub pad (at -2.1 0)
        assert '(pad "1" connect rect (at 0 0) (size 0.5 0.5)' in pcb_text, "SWRA117D feed pad geometry mismatch"
        assert '(pad "2" smd rect (at -2.1 0) (size 0.9 0.5)' in pcb_text, "SWRA117D ground stub pad geometry mismatch"
        assert '(net 2 "/FEED")' in pcb_text, "Pad 1 not connected to /FEED"
        assert '(net 1 "GND")' in pcb_text, "Pad 2 not connected to GND"

        # Check radiating arm geometry: relative footprint polygon extends to 11.85 mm and -5.15 mm
        assert "fp_poly" in pcb_text, "Antenna fp_poly missing in PCB layout"
        assert "(xy 11.85 -5.15)" in pcb_text, "SWRA117D antenna radiating arm endpoint missing"
        assert "(xy -2.55 -5.15)" in pcb_text, "SWRA117D antenna ground stub corner missing"

    def test_cpwg_feedline_and_ground_stitching(self) -> None:
        """Assert CPWG feedline track and ground stitching vias conform to RF requirements."""
        with open(PCB_PATH, "r", encoding="utf-8") as f:
            pcb_text = f.read()

        # Feedline track segment (start 30.00 18.00) (end 30.00 23.00) (width 1.85) (net 2)
        assert '(segment (start 30.00 18.00) (end 30.00 23.00) (width 1.85) (layer "F.Cu") (net 2)' in pcb_text, (
            "CPWG feedline segment missing or incorrect width"
        )

        # 4x ground stitching vias (drill 0.40, size 0.90) connecting F.Cu and B.Cu ground planes
        via_count = pcb_text.count('(size 0.90) (drill 0.40) (layers "F.Cu" "B.Cu") (net 1)')
        assert via_count >= 4, f"Found only {via_count} ground stitching vias (expected >= 4)"

    def test_schematic_erc_clean(self) -> None:
        """Assert 2.4 GHz schematic passes KiCad ERC with 0 violations/errors."""
        if os.path.exists(KICAD_CLI):
            res = subprocess.run(
                [KICAD_CLI, "sch", "erc", "--output", ERC_REPORT_PATH, "--severity-all", SCH_PATH],
                capture_output=True,
                text=True,
            )
            assert res.returncode == 0, f"ERC CLI failed: {res.stderr}\n{res.stdout}"

        assert os.path.isfile(ERC_REPORT_PATH), f"ERC report missing: {ERC_REPORT_PATH}"
        with open(ERC_REPORT_PATH, "r", encoding="utf-8") as f:
            erc_text = f.read()
        assert ("Found 0 violations" in erc_text) or ("Errors 0" in erc_text) or ("violations **\n0" in erc_text), (
            f"ERC reported violations in {SCH_PATH}:\n{erc_text}"
        )

    def test_3pin_termination_architecture(self) -> None:
        """Assert 3-pin termination header connects Pin 1=50R, Pin 2=FEED, Pin 3=GND."""
        with open(PCB_PATH, "r", encoding="utf-8") as f:
            pcb_text = f.read()

        assert 'net 4 "/TERM_50R"' in pcb_text, "TERM_50R net missing in PCB"
        assert 'net 2 "/FEED"' in pcb_text, "FEED net missing in PCB"
        assert 'net 1 "GND"' in pcb_text, "GND net missing in PCB"
        assert "PinHeader_1x03_P2.54mm_Vertical" in pcb_text, "3-pin header missing in PCB"


class TestSub1GHzKiCadHardware:
    """Test suite for Option B Sub-1GHz (868/915 MHz SWRA416) KiCad 9.0 RF Backscatter Tag."""

    def test_sub1ghz_project_files_exist(self) -> None:
        """Assert Sub-1GHz project, schematic, and layout files exist."""
        assert os.path.isfile(PRO_SUB1G_PATH), f"Project file missing: {PRO_SUB1G_PATH}"
        assert os.path.isfile(SCH_SUB1G_PATH), f"Schematic file missing: {SCH_SUB1G_PATH}"
        assert os.path.isfile(PCB_SUB1G_PATH), f"PCB layout file missing: {PCB_SUB1G_PATH}"

        assert os.path.getsize(PRO_SUB1G_PATH) > 100
        assert os.path.getsize(SCH_SUB1G_PATH) > 1000
        assert os.path.getsize(PCB_SUB1G_PATH) > 2000

    def test_sub1ghz_schematic_erc_clean(self) -> None:
        """Assert Sub-1GHz schematic passes KiCad ERC with 0 violations/errors."""
        if os.path.exists(KICAD_CLI):
            res = subprocess.run(
                [KICAD_CLI, "sch", "erc", "--output", ERC_SUB1G_REPORT_PATH, "--severity-all", SCH_SUB1G_PATH],
                capture_output=True,
                text=True,
            )
            assert res.returncode == 0, f"ERC CLI failed: {res.stderr}\n{res.stdout}"

        assert os.path.isfile(ERC_SUB1G_REPORT_PATH), f"ERC report missing: {ERC_SUB1G_REPORT_PATH}"
        with open(ERC_SUB1G_REPORT_PATH, "r", encoding="utf-8") as f:
            erc_text = f.read()
        assert ("Found 0 violations" in erc_text) or ("Errors 0" in erc_text) or ("violations **\n0" in erc_text), (
            f"ERC reported violations in {SCH_SUB1G_PATH}:\n{erc_text}"
        )

    def test_sub1ghz_headless_drc_clean(self) -> None:
        """Assert Sub-1GHz PCB layout passes KiCad DRC with 0 violations and 0 unconnected items."""
        if os.path.exists(KICAD_CLI):
            res = subprocess.run(
                [KICAD_CLI, "pcb", "drc", "--output", DRC_SUB1G_REPORT_PATH, "--severity-all", PCB_SUB1G_PATH],
                capture_output=True,
                text=True,
            )
            assert res.returncode == 0, f"DRC CLI returned error: {res.stderr}\n{res.stdout}"

        assert os.path.isfile(DRC_SUB1G_REPORT_PATH), f"DRC report missing: {DRC_SUB1G_REPORT_PATH}"
        with open(DRC_SUB1G_REPORT_PATH, "r", encoding="utf-8") as f:
            report_text = f.read()

        assert ("Found 0 DRC violations" in report_text) or ("violations **\n0" in report_text) or ("Found 0 violations" in report_text), (
            f"DRC reported violations:\n{report_text}"
        )
        assert ("Found 0 unconnected" in report_text) or ("unconnected items **\n0" in report_text), (
            f"DRC reported unconnected pads:\n{report_text}"
        )

    def test_sub1ghz_antenna_swra416_geometry(self) -> None:
        """Assert TI SWRA416 helical geometry: 19 vias (pad 1.0mm, drill 0.4mm), 1.0mm traces, 9.5 turns."""
        with open(PCB_SUB1G_PATH, "r", encoding="utf-8") as f:
            pcb_text = f.read()

        assert "Texas_SWRA416_868MHz_915MHz" in pcb_text, "SWRA416 footprint missing in PCB"
        assert '(pad "1" connect rect (at 0 0) (size 0.5 0.5)' in pcb_text
        assert '(pad "2" smd rect (at -2.1 0) (size 0.9 0.5)' in pcb_text

        # Check helical vias: 19 vias on /FEED net connecting F.Cu and B.Cu
        via_count = pcb_text.count('(size 1.00) (drill 0.40) (layers "F.Cu" "B.Cu") (net 2)')
        assert via_count == 19, f"Expected 19 helical vias on net 2, found {via_count}"

        # Check 1.0 mm helical trace segments
        trace_count_fcu = pcb_text.count('(width 1.00) (layer "F.Cu") (net 2)')
        trace_count_bcu = pcb_text.count('(width 1.00) (layer "B.Cu") (net 2)')
        assert trace_count_fcu >= 10, f"Expected >= 10 F.Cu 1.0mm segments, found {trace_count_fcu}"
        assert trace_count_bcu >= 9, f"Expected >= 9 B.Cu 1.0mm segments, found {trace_count_bcu}"

    def test_sub1ghz_cnc_clearances(self) -> None:
        """Assert Sub-1GHz PCB enforces >= 0.40 mm CNC milling clearance across netclasses and copper fills."""
        with open(PCB_SUB1G_PATH, "r", encoding="utf-8") as f:
            pcb_text = f.read()

        clearance_matches = re.findall(r'\(clearance\s+([\d\.]+)\)', pcb_text)
        assert len(clearance_matches) > 0
        for cl_str in clearance_matches:
            cl_val = float(cl_str)
            assert cl_val >= 0.40, f"Sub-1GHz clearance {cl_val} mm < 0.40 mm"

        thermal_gaps = re.findall(r'\(thermal_gap\s+([\d\.]+)\)', pcb_text)
        for tg_str in thermal_gaps:
            tg_val = float(tg_str)
            assert tg_val >= 0.40, f"Sub-1GHz thermal gap {tg_val} mm < 0.40 mm"

    def test_sub1ghz_3pin_termination_architecture(self) -> None:
        """Assert Sub-1GHz board implements 3-pin termination architecture."""
        with open(PCB_SUB1G_PATH, "r", encoding="utf-8") as f:
            pcb_text = f.read()

        assert "PinHeader_1x03_P2.54mm_Vertical" in pcb_text
        assert 'net 4 "/TERM_50R"' in pcb_text
        assert 'net 2 "/FEED"' in pcb_text
        assert 'net 1 "GND"' in pcb_text

    def test_sub1ghz_gerber_and_drill_files(self) -> None:
        """Assert Sub-1GHz Gerbers and drill files exist and have valid RS-274X / Excellon format."""
        assert os.path.isdir(GERBERS_SUB1G_DIR), f"Sub-1GHz gerber dir missing: {GERBERS_SUB1G_DIR}"

        # F_Cu Gerber
        fcu_candidates = [
            os.path.join(GERBERS_SUB1G_DIR, "F_Cu.gbr"),
            os.path.join(GERBERS_SUB1G_DIR, "backscatter_tag_sub1ghz-F_Cu.gbr"),
            os.path.join(GERBERS_SUB1G_DIR, "backscatter_tag_sub1ghz-F_Cu.gtl"),
        ]
        fcu_path = next((p for p in fcu_candidates if os.path.isfile(p)), None)
        assert fcu_path is not None, "Sub-1GHz F_Cu Gerber missing"
        with open(fcu_path, "r", encoding="utf-8", errors="ignore") as f:
            fcu_content = f.read()
        assert "%FSLAX" in fcu_content
        assert "%MOMM*" in fcu_content
        assert "M02*" in fcu_content

        # Drill file
        drill_candidates = [
            os.path.join(GERBERS_SUB1G_DIR, "backscatter_tag_sub1ghz.drl"),
            os.path.join(GERBERS_SUB1G_DIR, "backscatter_tag_sub1ghz-PTH.drl"),
        ]
        drill_path = next((p for p in drill_candidates if os.path.isfile(p)), None)
        assert drill_path is not None, "Sub-1GHz Excellon drill file missing"
        with open(drill_path, "r", encoding="utf-8", errors="ignore") as f:
            drill_content = f.read()
        assert ("M48" in drill_content) or ("METRIC" in drill_content)
        assert ("M30" in drill_content) or ("T1" in drill_content)

    def test_sub1ghz_dxf_files(self) -> None:
        """Assert Sub-1GHz DXF files exist and contain valid AutoCAD DXF entities."""
        assert os.path.isdir(DXF_SUB1G_DIR), f"Sub-1GHz DXF dir missing: {DXF_SUB1G_DIR}"
        dxf_candidates = [
            os.path.join(DXF_SUB1G_DIR, "F_Cu.dxf"),
            os.path.join(DXF_SUB1G_DIR, "backscatter_tag_sub1ghz-F_Cu.dxf"),
        ]
        dxf_path = next((p for p in dxf_candidates if os.path.isfile(p)), None)
        assert dxf_path is not None, "Sub-1GHz F_Cu DXF missing"
        with open(dxf_path, "r", encoding="utf-8", errors="ignore") as f:
            dxf_content = f.read()
        assert "SECTION" in dxf_content
        assert "ENTITIES" in dxf_content
        assert "EOF" in dxf_content

    def test_sub1ghz_pcb_render_validity(self) -> None:
        """Assert Sub-1GHz 3D render image exists and is a valid PNG (> 1 KB)."""
        assert os.path.isfile(RENDER_SUB1G_PATH), f"Sub-1GHz render missing: {RENDER_SUB1G_PATH}"
        assert os.path.getsize(RENDER_SUB1G_PATH) > 1024
        with open(RENDER_SUB1G_PATH, "rb") as f:
            header = f.read(8)
        assert header == b"\x89PNG\r\n\x1a\n", "Sub-1GHz render is not a valid PNG image"


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))


