"""Update Board 3 AE1 footprint with net_tie_pad_groups and re-run DRC."""

import subprocess
import os

KICAD_CLI = r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"
PCB_PATH = r".\kicad_pcb(automated)\backscatter_tag_leggiero.kicad_pcb"

with open(PCB_PATH, "r", encoding="utf-8") as f:
    text = f.read()

# Add net_tie_pad_groups "1,2" right after attr line
text = text.replace('(attr exclude_from_pos_files exclude_from_bom)', '(attr exclude_from_pos_files exclude_from_bom)\n\t\t(net_tie_pad_groups "1,2")')

with open(PCB_PATH, "w", encoding="utf-8") as f:
    f.write(text)

drc_rpt = r".\ready_for_milling\Board3_2.4GHz_Leggiero_Bowtie_Tag\drc_report.txt"
subprocess.run([KICAD_CLI, "pcb", "drc", "--output", drc_rpt, "--severity-all", PCB_PATH], check=True)

with open(drc_rpt, "r", encoding="utf-8") as f:
    print(f.read())
