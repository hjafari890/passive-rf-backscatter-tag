pcb = r".\kicad_pcb(automated)\backscatter_tag.kicad_pcb"
with open(pcb, "r", encoding="utf-8") as f:
    text = f.read()
text = text.replace("zone_connect 22 (", "zone_connect 2) (")
with open(pcb, "w", encoding="utf-8") as f:
    f.write(text)
print("Fixed zone_connect successfully")
