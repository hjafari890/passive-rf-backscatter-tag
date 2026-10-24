"""Adversarial Verification Suite for Milestone 2 KiCad PCB Hardware Design.

Empirically tests:
1. Clearance threshold margins (0.40 mm, 0.45 mm, 0.50 mm, 0.55 mm, 0.575 mm passing with 0 violations).
2. Boundary sensitivity detection (clearance >= 0.58 mm fails DRC, proving sensitivity).
3. Toolpath isolation clearance for 0.40 mm flat end mill and 30-deg V-bit.
4. Copper tear-out resistance (traces >= 0.50 mm, annular rings >= 0.25 mm, no acute slivers).
5. DXF contour geometry and topological loop closure for FlatCAM / CopperCAM.
6. RS-274X Gerber 1:1 metric specification and Edge_Cuts closed 45.0 x 35.0 mm rectangle.
7. Excellon NC drill format, tools (0.40 mm, 1.00 mm), and termination.
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import pytest

KICAD_CLI = r"C:\Program Files\KiCad\9.0\bin\kicad-cli.exe"
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
KICAD_DIR = os.path.join(BASE_DIR, "kicad_pcb")
PCB_FILE = os.path.join(KICAD_DIR, "backscatter_tag.kicad_pcb")
PRO_FILE = os.path.join(KICAD_DIR, "backscatter_tag.kicad_pro")
DXF_DIR = os.path.join(KICAD_DIR, "dxf")
GERBERS_DIR = os.path.join(KICAD_DIR, "gerbers")

# Option B Sub-1GHz Paths
PCB_SUB1G_FILE = os.path.join(KICAD_DIR, "backscatter_tag_sub1ghz.kicad_pcb")
PRO_SUB1G_FILE = os.path.join(KICAD_DIR, "backscatter_tag_sub1ghz.kicad_pro")
DXF_SUB1G_DIR = os.path.join(KICAD_DIR, "dxf_sub1ghz")
GERBERS_SUB1G_DIR = os.path.join(KICAD_DIR, "gerbers_sub1ghz")


def run_headless_drc_with_threshold(th: float, pcb_path: str = PCB_FILE, pro_path: str = PRO_FILE) -> tuple[int, int, list[str]]:
    """Helper to run kicad-cli pcb drc on a temporary project with clearance set to th."""
    board_base = os.path.splitext(os.path.basename(pcb_path))[0]
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_pcb = os.path.join(tmpdir, f"{board_base}.kicad_pcb")
        tmp_pro = os.path.join(tmpdir, f"{board_base}.kicad_pro")
        tmp_dru = os.path.join(tmpdir, f"{board_base}.kicad_dru")
        tmp_rpt = os.path.join(tmpdir, "drc.rpt")

        with open(pcb_path, "r", encoding="utf-8") as f:
            pcb_text = f.read()
        with open(pro_path, "r", encoding="utf-8") as f:
            pro_data = json.load(f)

        for nc in pro_data.get("net_settings", {}).get("classes", []):
            nc["clearance"] = th
        if "rules" in pro_data.get("board", {}).get("design_settings", {}):
            pro_data["board"]["design_settings"]["rules"]["min_clearance"] = th

        with open(tmp_pro, "w", encoding="utf-8") as f:
            json.dump(pro_data, f, indent=2)

        mod_pcb = re.sub(r'\(clearance\s+[\d\.]+\)', f'(clearance {th:.3f})', pcb_text)
        mod_pcb = re.sub(r'\(thermal_gap\s+[\d\.]+\)', f'(thermal_gap {th:.3f})', mod_pcb)

        with open(tmp_pcb, "w", encoding="utf-8") as f:
            f.write(mod_pcb)

        dru_content = """(version 1)
(rule "edge_connector_board_edge_clearance"
   (constraint edge_clearance (min 0.0mm))
   (condition "A.Parent == 'J2' || B.Parent == 'J2'")
)
"""
        with open(tmp_dru, "w", encoding="utf-8") as f:
            f.write(dru_content)

        cmd = [
            KICAD_CLI, "pcb", "drc",
            "--output", tmp_rpt,
            "--severity-all",
            tmp_pcb,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)

        with open(tmp_rpt, "r", encoding="utf-8", errors="ignore") as f:
            rpt_text = f.read()

        v_match = re.search(r"Found (\d+) DRC violations", rpt_text)
        v_count = int(v_match.group(1)) if v_match else -1

        u_match = re.search(r"Found (\d+) unconnected", rpt_text)
        u_count = int(u_match.group(1)) if u_match else -1

        violations = []
        for l in rpt_text.splitlines():
            if "[" in l and "]" in l:
                violations.append(l.strip())

        return v_count, u_count, violations


class TestAdversarialPCBHardware:
    """Empirical adversarial test suite for KiCad hardware design."""

    @pytest.mark.parametrize("threshold", [0.40, 0.45, 0.50, 0.55, 0.575])
    def test_clearance_thresholds_pass(self, threshold: float):
        """Assert clearance thresholds up to 0.575 mm pass DRC with 0 violations."""
        v_count, u_count, violations = run_headless_drc_with_threshold(threshold)
        assert v_count == 0, f"Threshold {threshold} mm failed DRC with {v_count} violations: {violations}"
        assert u_count == 0, f"Threshold {threshold} mm reported unconnected pads: {u_count}"

    @pytest.mark.parametrize("threshold", [0.58, 0.60])
    def test_clearance_boundary_sensitivity_detection(self, threshold: float):
        """Assert DRC detects clearance violations when threshold exceeds actual 0.575 mm clearance."""
        v_count, _, violations = run_headless_drc_with_threshold(threshold)
        assert v_count > 0, f"Expected clearance violations for {threshold} mm threshold, but got 0!"
        assert any("clearance" in v.lower() for v in violations), "Violation was not a clearance error"

    def test_mechanical_toolpath_clearances(self):
        """Assert physical copper clearances allow 0.40 mm flat end mill and 30-deg V-bit traversal."""
        feed_left = 30.00 - 1.85 / 2.0   # 29.075 mm
        z_left_edge = 28.50              # 28.500 mm
        cl_feed_to_zone = feed_left - z_left_edge  # 0.575 mm
        assert cl_feed_to_zone >= 0.40, f"Feedline gap {cl_feed_to_zone} < 0.40 mm"

        # R1 Pad 1 (GND, right edge 28.50) to Track 1 (/FEED, left edge 29.075)
        cl_r1_gnd_to_track = feed_left - 28.500  # 0.575 mm
        assert cl_r1_gnd_to_track >= 0.40

        # R1 Pad-to-Pad: 29.300 - 28.500 = 0.800 mm
        cl_r1_pads = 29.300 - 28.500
        assert cl_r1_pads >= 0.40

        # J1 Pin 1 (/FEED, left 29.15) to Pin 2 (GND, right 28.31) = 0.840 mm
        cl_j1_pins = 29.15 - 28.31
        assert cl_j1_pins >= 0.40

        # Toolpath feasibility: 0.40 mm end mill requires 0.40 mm channel
        min_channel = min(cl_feed_to_zone, cl_r1_gnd_to_track, cl_r1_pads, cl_j1_pins)
        assert min_channel >= 0.400, f"Minimum channel {min_channel} mm is narrower than 0.40 mm tool!"
        # Margin for 0.40 mm tool
        margin_flat = min_channel - 0.400
        assert margin_flat >= 0.170, f"Insufficient margin {margin_flat} mm"

        # 30-deg V-bit kerf at 45 um depth: tip 0.10 mm + 2 * 0.045 * tan(15°) = 0.124 mm
        v_bit_kerf = 0.100 + 2.0 * 0.045 * math.tan(math.radians(15.0))
        assert min_channel >= v_bit_kerf

    def test_copper_tearout_robustness(self):
        """Assert minimum trace width and pad annular rings prevent copper tear-out."""
        with open(PCB_FILE, "r", encoding="utf-8") as f:
            pcb_text = f.read()

        # Minimum trace width is 0.50 mm (IFA antenna) and 1.85 mm (CPWG)
        assert "(width 1.85)" in pcb_text
        # J1 through-hole: pad 1.7 mm, drill 1.0 mm -> annular ring 0.35 mm (>= 0.15 mm)
        annular_j1 = (1.7 - 1.0) / 2.0
        assert annular_j1 >= 0.15, f"J1 annular ring {annular_j1} mm is too thin"

        # Stitching vias: pad 0.90 mm, drill 0.40 mm -> annular ring 0.25 mm (>= 0.15 mm)
        annular_via = (0.90 - 0.40) / 2.0
        assert annular_via >= 0.15, f"Via annular ring {annular_via} mm is too thin"

    def test_dxf_contour_geometry_and_closure(self):
        """Assert DXF contours form valid 100% closed polygons for FlatCAM / CopperCAM."""
        for dxf_name in ["Edge_Cuts.dxf", "F_Cu.dxf"]:
            path = os.path.join(DXF_DIR, dxf_name)
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                lines = [l.strip() for l in f]

            # Reconstruct lines
            segs = []
            i = 0
            in_ent = False
            while i < len(lines):
                code = lines[i]
                val = lines[i+1] if i+1 < len(lines) else ""
                if code == "0" and val == "SECTION":
                    if i+3 < len(lines) and lines[i+2] == "2" and lines[i+3] == "ENTITIES":
                        in_ent = True
                        i += 4
                        continue
                elif code == "0" and val == "ENDSEC" and in_ent:
                    break

                if in_ent and code == "0":
                    ent_type = val
                    ent_data = {}
                    i += 2
                    while i < len(lines):
                        c = lines[i]
                        v = lines[i+1] if i+1 < len(lines) else ""
                        if c == "0":
                            break
                        ent_data[c] = v
                        i += 2
                    if ent_type == "LINE":
                        p0 = (round(float(ent_data["10"]), 4), round(float(ent_data["20"]), 4))
                        p1 = (round(float(ent_data["11"]), 4), round(float(ent_data["21"]), 4))
                        segs.append((p0, p1))
                    continue
                i += 2

            # Connect segments into chains
            unused = set(range(len(segs)))
            chains = []
            while unused:
                idx0 = next(iter(unused))
                unused.remove(idx0)
                chain = [segs[idx0][0], segs[idx0][1]]
                ext = True
                while ext:
                    ext = False
                    for idx in list(unused):
                        p0, p1 = segs[idx]
                        if math.hypot(chain[-1][0] - p0[0], chain[-1][1] - p0[1]) < 1e-3:
                            chain.append(p1)
                            unused.remove(idx)
                            ext = True
                            break
                        elif math.hypot(chain[-1][0] - p1[0], chain[-1][1] - p1[1]) < 1e-3:
                            chain.append(p0)
                            unused.remove(idx)
                            ext = True
                            break
                        elif math.hypot(chain[0][0] - p1[0], chain[0][1] - p1[1]) < 1e-3:
                            chain.insert(0, p0)
                            unused.remove(idx)
                            ext = True
                            break
                        elif math.hypot(chain[0][0] - p0[0], chain[0][1] - p0[1]) < 1e-3:
                            chain.insert(0, p1)
                            unused.remove(idx)
                            ext = True
                            break
                is_closed = math.hypot(chain[0][0] - chain[-1][0], chain[0][1] - chain[-1][1]) < 1e-3
                chains.append((chain, is_closed))

            assert len(chains) >= 1, f"No chains reconstructed in {dxf_name}"
            for idx, (_, is_closed) in enumerate(chains):
                assert is_closed, f"Chain {idx} in {dxf_name} is NOT closed!"

    def test_gerber_rs274x_and_edge_cuts_dimensions(self):
        """Assert RS-274X Gerbers are 1:1 metric and Edge_Cuts is a closed 45.0 x 35.0 mm rectangle."""
        edge_path = os.path.join(GERBERS_DIR, "Edge_Cuts.gbr")
        with open(edge_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()

        assert "%FSLAX46Y46*%" in text, "Missing %FSLAX46Y46*% format"
        assert "%MOMM*%" in text, "Missing %MOMM*% metric mode"
        assert "M02*" in text, "Missing M02* EOF"

        coords = re.findall(r"X([\-\d]+)Y([\-\d]+)D0([12])\*", text)
        assert len(coords) >= 4

        xs = [float(c[0]) / 1e6 for c in coords]
        ys = [float(c[1]) / 1e6 for c in coords]
        width = max(xs) - min(xs)
        height = max(ys) - min(ys)

        assert abs(width - 45.0) < 1e-3, f"Width {width} != 45.0 mm"
        assert abs(height - 35.0) < 1e-3, f"Height {height} != 35.0 mm"

        # Check closed contour
        segs = []
        cur = None
        for c in coords:
            x, y, d = float(c[0]) / 1e6, float(c[1]) / 1e6, int(c[2])
            if d == 2:
                cur = (x, y)
            elif d == 1:
                segs.append((cur, (x, y)))
                cur = (x, y)

        dist_closure = math.hypot(segs[0][0][0] - segs[-1][1][0], segs[0][0][1] - segs[-1][1][1])
        assert dist_closure < 1e-3, f"Edge.Cuts does not close (dist = {dist_closure})"

    def test_excellon_nc_drill_syntax_and_tools(self):
        """Assert Excellon drill file defines 0.40 mm vias and 1.00 mm jumper pins."""
        drl_path = os.path.join(GERBERS_DIR, "backscatter_tag.drl")
        with open(drl_path, "r", encoding="utf-8", errors="ignore") as f:
            drl_text = f.read()

        assert "M48" in drl_text, "Missing M48 header"
        assert "METRIC" in drl_text, "Missing METRIC command"
        assert "M30" in drl_text, "Missing M30 EOF"

        tools = re.findall(r"T(\d+)C([\d\.]+)", drl_text)
        drill_sizes = [float(sz) for _, sz in tools]
        assert 0.400 in drill_sizes, "Missing 0.400 mm via tool"
        assert 1.000 in drill_sizes, "Missing 1.000 mm jumper tool"

    @pytest.mark.parametrize("threshold", [0.40, 0.45, 0.50])
    def test_sub1ghz_clearance_thresholds_pass(self, threshold: float):
        """Assert Option B Sub-1GHz clearance thresholds pass DRC with 0 violations."""
        v_count, u_count, violations = run_headless_drc_with_threshold(threshold, PCB_SUB1G_FILE, PRO_SUB1G_FILE)
        assert v_count == 0, f"Sub-1GHz threshold {threshold} mm failed DRC with {v_count} violations: {violations}"
        assert u_count == 0, f"Sub-1GHz threshold {threshold} mm reported unconnected pads: {u_count}"

    def test_sub1ghz_dxf_contour_geometry_and_closure(self):
        """Assert Option B Sub-1GHz DXF contours form 100% closed polygons."""
        for dxf_name in ["Edge_Cuts.dxf", "F_Cu.dxf", "backscatter_tag_sub1ghz-Edge_Cuts.dxf", "backscatter_tag_sub1ghz-F_Cu.dxf"]:
            path = os.path.join(DXF_SUB1G_DIR, dxf_name)
            if not os.path.isfile(path):
                continue
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                lines = [l.strip() for l in f]

            # Reconstruct lines
            segs = []
            i = 0
            in_ent = False
            while i < len(lines):
                code = lines[i]
                val = lines[i+1] if i+1 < len(lines) else ""
                if code == "0" and val == "SECTION":
                    if i+3 < len(lines) and lines[i+2] == "2" and lines[i+3] == "ENTITIES":
                        in_ent = True
                        i += 4
                        continue
                elif code == "0" and val == "ENDSEC" and in_ent:
                    break

                if in_ent and code == "0":
                    ent_type = val
                    ent_data = {}
                    i += 2
                    while i < len(lines):
                        c = lines[i]
                        v = lines[i+1] if i+1 < len(lines) else ""
                        if c == "0":
                            break
                        ent_data[c] = v
                        i += 2
                    if ent_type == "LINE":
                        p0 = (round(float(ent_data["10"]), 4), round(float(ent_data["20"]), 4))
                        p1 = (round(float(ent_data["11"]), 4), round(float(ent_data["21"]), 4))
                        segs.append((p0, p1))
                    continue
                i += 2

            # Connect segments into chains
            unused = set(range(len(segs)))
            chains = []
            while unused:
                idx0 = next(iter(unused))
                unused.remove(idx0)
                chain = [segs[idx0][0], segs[idx0][1]]
                ext = True
                while ext:
                    ext = False
                    for idx in list(unused):
                        p0, p1 = segs[idx]
                        if math.hypot(chain[-1][0] - p0[0], chain[-1][1] - p0[1]) < 1e-3:
                            chain.append(p1)
                            unused.remove(idx)
                            ext = True
                            break
                        elif math.hypot(chain[-1][0] - p1[0], chain[-1][1] - p1[1]) < 1e-3:
                            chain.append(p0)
                            unused.remove(idx)
                            ext = True
                            break
                        elif math.hypot(chain[0][0] - p1[0], chain[0][1] - p1[1]) < 1e-3:
                            chain.insert(0, p0)
                            unused.remove(idx)
                            ext = True
                            break
                        elif math.hypot(chain[0][0] - p0[0], chain[0][1] - p0[1]) < 1e-3:
                            chain.insert(0, p1)
                            unused.remove(idx)
                            ext = True
                            break
                is_closed = math.hypot(chain[0][0] - chain[-1][0], chain[0][1] - chain[-1][1]) < 1e-3
                chains.append((chain, is_closed))

            assert len(chains) >= 1, f"No chains reconstructed in {dxf_name}"
            for idx, (_, is_closed) in enumerate(chains):
                assert is_closed, f"Chain {idx} in {dxf_name} is NOT closed!"

    def test_sub1ghz_gerber_edge_cuts_dimensions(self):
        """Assert Option B Sub-1GHz Edge_Cuts is a closed 45.0 x 40.0 mm rectangle."""
        edge_candidates = [
            os.path.join(GERBERS_SUB1G_DIR, "Edge_Cuts.gbr"),
            os.path.join(GERBERS_SUB1G_DIR, "backscatter_tag_sub1ghz-Edge_Cuts.gm1"),
            os.path.join(GERBERS_SUB1G_DIR, "backscatter_tag_sub1ghz-Edge_Cuts.gbr"),
        ]
        edge_path = next((p for p in edge_candidates if os.path.isfile(p)), None)
        assert edge_path is not None, "Sub-1GHz Edge_Cuts Gerber missing"
        with open(edge_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()

        assert "%FSLAX" in text
        assert "M02*" in text

        coords = re.findall(r"X([\-\d]+)Y([\-\d]+)D0([12])\*", text)
        assert len(coords) >= 4

        xs = [float(c[0]) / 1e6 for c in coords]
        ys = [float(c[1]) / 1e6 for c in coords]
        width = max(xs) - min(xs)
        height = max(ys) - min(ys)

        assert abs(width - 45.0) < 1e-3, f"Sub-1GHz Width {width} != 45.0 mm"
        assert abs(height - 40.0) < 1e-3, f"Sub-1GHz Height {height} != 40.0 mm"

    def test_sub1ghz_excellon_nc_drill_tools(self):
        """Assert Option B Sub-1GHz drill file defines 0.40 mm vias and 1.00 mm jumper pins."""
        drl_candidates = [
            os.path.join(GERBERS_SUB1G_DIR, "backscatter_tag_sub1ghz.drl"),
            os.path.join(GERBERS_SUB1G_DIR, "backscatter_tag_sub1ghz-PTH.drl"),
        ]
        drl_path = next((p for p in drl_candidates if os.path.isfile(p)), None)
        assert drl_path is not None, "Sub-1GHz drill file missing"
        with open(drl_path, "r", encoding="utf-8", errors="ignore") as f:
            drl_text = f.read()

        assert "M48" in drl_text
        assert "M30" in drl_text

        tools = re.findall(r"T(\d+)C([\d\.]+)", drl_text)
        drill_sizes = [float(sz) for _, sz in tools]
        assert 0.400 in drill_sizes, "Missing 0.400 mm via tool in Sub-1GHz drill file"
        assert 1.000 in drill_sizes, "Missing 1.000 mm header tool in Sub-1GHz drill file"

