import re

# Reasons in FI Additional Information that should be excluded from AOI analysis
NON_AOI_REASONS = ["Missing Coating"]


def parse_fi_rejections(info: str, ignore_phrases: list[str]) -> int:
    """Parse FI Additional Information and sum counts not in ignore list."""
    if not info:
        return 0
    total = 0
    entries = [e.strip() for e in info.split(",") if e.strip()]
    pattern = re.compile(r"\((\d+)\)")
    ignore = [p.lower() for p in ignore_phrases]
    for entry in entries:
        entry_lower = entry.lower()
        if any(phrase in entry_lower for phrase in ignore):
            continue
        match = pattern.search(entry)
        if match:
            total += int(match.group(1))
    return total
