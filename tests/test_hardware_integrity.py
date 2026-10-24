"""Automated verification test suite for Hardware KiCad projects, Gerbers, and CNC Milling packages."""

from __future__ import annotations

import os
import re
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
HW_DIR = os.path.join(REPO_ROOT, "hardware")

BOARD1_DIR = os.path.join(HW_DIR, "board1_ifa_2.4ghz")
BOARD2_DIR = os.path.join(HW_DIR, "board2_meander_sub1ghz")
BOARD3_DIR = os.path.join(HW_DIR, "board3_cavity_bowtie_2.4ghz")


class TestHardwareIntegrity:
    """Validates that all 3 boards exist, have compliant KiCad 9 files and valid Gerbers."""

    @pytest.mark.parametrize("board_dir,base_name", [
        (BOARD1_DIR, "backscatter_tag"),
        (BOARD2_DIR, "backscatter_tag_sub1ghz"),
        (BOARD3_DIR, "backscatter_tag_leggiero"),
    ])
    def test_kicad_project_files_exist_and_valid(self, board_dir: str, base_name: str) -> None:
        """Verify KiCad .kicad_pro, .kicad_sch, and .kicad_pcb exist and have valid headers."""
        pro_path = os.path.join(board_dir, f"{base_name}.kicad_pro")
        sch_path = os.path.join(board_dir, f"{base_name}.kicad_sch")
        pcb_path = os.path.join(board_dir, f"{base_name}.kicad_pcb")

        assert os.path.isfile(pro_path), f"Missing project file: {pro_path}"
        assert os.path.isfile(sch_path), f"Missing schematic file: {sch_path}"
        assert os.path.isfile(pcb_path), f"Missing PCB file: {pcb_path}"

        # Check schematic format header
        with open(sch_path, "r", encoding="utf-8", errors="ignore") as f:
            sch_content = f.read(500)
            assert "(kicad_sch" in sch_content, f"Invalid KiCad schematic header in {sch_path}"

        # Check PCB layout format header
        with open(pcb_path, "r", encoding="utf-8", errors="ignore") as f:
            pcb_content = f.read(500)
            assert "(kicad_pcb" in pcb_content, f"Invalid KiCad PCB header in {pcb_path}"

    @pytest.mark.parametrize("board_dir,base_name", [
        (BOARD1_DIR, "backscatter_tag"),
        (BOARD2_DIR, "backscatter_tag_sub1ghz"),
        (BOARD3_DIR, "backscatter_tag_leggiero"),
    ])
    def test_gerber_files_exist_and_standard_headers(self, board_dir: str, base_name: str) -> None:
        """Verify that RS-274X Gerber milling files and Excellon drills exist with correct headers."""
        gerbers_dir = os.path.join(board_dir, "gerbers")
        assert os.path.isdir(gerbers_dir), f"Missing gerbers directory: {gerbers_dir}"

        # Check Top Copper Gerber
        f_cu_candidates = [
            os.path.join(gerbers_dir, f"{base_name}-F_Cu.gtl"),
            os.path.join(gerbers_dir, f"{base_name}-F_Cu.gbr"),
        ]
        f_cu_path = next((p for p in f_cu_candidates if os.path.isfile(p)), None)
        assert f_cu_path is not None, f"Missing Top Copper Gerber in {gerbers_dir}"

        with open(f_cu_path, "r", encoding="utf-8", errors="ignore") as f:
            gbr_content = f.read(1000)
            assert "%FSLAX" in gbr_content or "%MO" in gbr_content, f"Missing standard RS-274X header in {f_cu_path}"

        # Check Drill file
        drl_path = os.path.join(gerbers_dir, f"{base_name}.drl")
        assert os.path.isfile(drl_path), f"Missing Excellon drill file: {drl_path}"
        with open(drl_path, "r", encoding="utf-8", errors="ignore") as f:
            drl_content = f.read(500)
            assert "M48" in drl_content, f"Missing M48 header in Excellon drill file {drl_path}"

    @pytest.mark.parametrize("board_dir,base_name", [
        (BOARD1_DIR, "backscatter_tag"),
        (BOARD2_DIR, "backscatter_tag_sub1ghz"),
        (BOARD3_DIR, "backscatter_tag_leggiero"),
    ])
    def test_single_sided_zero_vias_constraint(self, board_dir: str, base_name: str) -> None:
        """Verify the single-sided zero-via rule: no via constructs in the PCB layout."""
        pcb_path = os.path.join(board_dir, f"{base_name}.kicad_pcb")
        with open(pcb_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        # Check for via definitions
        vias = re.findall(r"\(via\s+", content)
        assert len(vias) == 0, f"Found {len(vias)} forbidden vias in single-sided layout {pcb_path}"

    @pytest.mark.parametrize("board_dir,base_name", [
        (BOARD1_DIR, "backscatter_tag"),
        (BOARD2_DIR, "backscatter_tag_sub1ghz"),
        (BOARD3_DIR, "backscatter_tag_leggiero"),
    ])
    def test_kicad_cli_load_and_drc(self, board_dir: str, base_name: str, tmp_path) -> None:
        """Verify that KiCad CLI loads each board cleanly without load errors and generates a DRC report."""
        import subprocess

        kicad_cli = None
        for p in [
            r"C:\Program Files\KiCad\9.0\bin\kicad-cli.exe",
            r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe",
            r"C:\Program Files\KiCad\8.0\bin\kicad-cli.exe",
        ]:
            if os.path.isfile(p):
                kicad_cli = p
                break

        if not kicad_cli:
            pytest.skip("KiCad CLI not installed on host")

        pcb_path = os.path.join(board_dir, f"{base_name}.kicad_pcb")
        rpt_path = str(tmp_path / f"{base_name}_drc.rpt")

        res = subprocess.run(
            [kicad_cli, "pcb", "drc", "--output", rpt_path, pcb_path],
            capture_output=True,
            text=True,
        )
        assert "Failed to load board" not in res.stderr, f"KiCad CLI failed to load {pcb_path}: {res.stderr}"
        assert res.returncode == 0, f"KiCad DRC failed with code {res.returncode}: {res.stderr}"
        assert os.path.isfile(rpt_path), f"DRC report was not created: {rpt_path}"
