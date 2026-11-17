import re


def read_uid(rows, width, height):
    """Accept explicit game identity labels observed in supported CN clients."""
    candidates = set()
    for text,score,(x,y) in rows:
        if score < .94 or x < width*.65 or y < height*.85:
            continue
        match = re.fullmatch(r'(?:UID|特征码)\s*[:：]?\s*(\d{8,12})',text.strip(),re.I)
        if match:
            candidates.add(match[1])
    return next(iter(candidates)) if len(candidates) == 1 else None
