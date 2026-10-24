pcb = r".\kicad_pcb(automated)\backscatter_tag.kicad_pcb"
with open(pcb, "r", encoding="utf-8") as f:
    text = f.read()

# Remove Zone 3 (B.Cu)
bcu_zone_idx = text.find('(layer "B.Cu")')
if bcu_zone_idx != -1:
    # find enclosing zone
    zone_start = text.rfind('(zone', 0, bcu_zone_idx)
    # find closing paren of this zone
    # Count parens
    p_count = 0
    zone_end = -1
    for i in range(zone_start, len(text)):
        if text[i] == '(':
            p_count += 1
        elif text[i] == ')':
            p_count -= 1
            if p_count == 0:
                zone_end = i + 1
                break
    if zone_end != -1:
        text = text[:zone_start] + text[zone_end:]
        print("Removed B.Cu zone")

with open(pcb, "w", encoding="utf-8") as f:
    f.write(text)
