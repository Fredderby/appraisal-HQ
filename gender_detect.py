FEMALE_STRONG = {"deborah","mabel","judith","ruth","winifred","victoria","precious","miracle","happy","majesty","marcel"}
MALE_STRONG = {"daniel","emmanuel","eric","evans","frank","frederick","george","goka","harry","joseph","lawrence","marcel","michael","richard","yaw","jonas","isaac","harry"}
def detect_gender(name: str):
    import re
    if not name: return ("unspecified","low")
    base = " ".join(str(name).split())
    # strip parens content
    base = re.sub(r"\s*\(.*?\)\s*", " ", base).strip()
    first = base.split()[0].strip(". ").lower()
    # strip initials like N.Y.
    if "." in first: first = first.replace(".","")
    if first in FEMALE_STRONG: return ("female","high")
    if first in MALE_STRONG: return ("male","high")
    return ("unspecified","low")
