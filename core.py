import hashlib

SCORE_MIDPOINTS = {
    "90-100": 95.0,
    "80-89": 85.0,
    "70-79": 75.0,
    "60-69": 65.0,
    "below-60": 55.0,
}

CATEGORY_SOURCES = [
    ("christian_conduct", "christian_conduct"),
    ("job_performance", "job_performance"),
    ("reliability", "reliability"),
    ("teamwork", "teamwork"),
    ("communication", "communication"),
    ("initiative", "initiative"),
    ("adaptability", "adaptability"),
    ("overall_assessment", "overall"),
]

CATEGORIES = [key for _, key in CATEGORY_SOURCES]

BANDS = ("Excellent", "Very Good", "Good", "Fair", "Needs Improvement")


def score_midpoint(value):
    if value is None:
        return None
    return SCORE_MIDPOINTS.get(str(value).strip())


def rating_band(midpoint):
    if midpoint is None:
        return "Needs Improvement"
    if midpoint >= 90:
        return "Excellent"
    if midpoint >= 80:
        return "Very Good"
    if midpoint >= 70:
        return "Good"
    if midpoint >= 60:
        return "Fair"
    return "Needs Improvement"


def normalize_name(name):
    if not name:
        return ""
    collapsed = " ".join(str(name).split())
    return collapsed.title()


def _normalize_user_agent(user_agent):
    if user_agent is None:
        return ""
    return " ".join(str(user_agent).strip().lower().split())


def device_fingerprint(device_id, ip, user_agent):
    did = str(device_id or "").strip().lower()
    ip_addr = str(ip or "").strip()
    ua = _normalize_user_agent(user_agent)
    raw = f"{did}|{ip_addr}|{ua}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _empty_summary():
    return {
        "samples": 0,
        "avg": None,
        "min": None,
        "max": None,
        "bands": {band: 0 for band in BANDS},
    }


def _summarize(points):
    if not points:
        return _empty_summary()
    avg = sum(points) / len(points)
    bands = {band: 0 for band in BANDS}
    for point in points:
        bands[rating_band(point)] += 1
    return {
        "samples": len(points),
        "avg": round(avg, 2),
        "min": min(points),
        "max": max(points),
        "bands": bands,
    }


def compute_staff_stats(rows):
    points_by_category = {key: [] for _, key in CATEGORY_SOURCES}
    devices = set()
    strengths = []
    improvements = []
    first_seen = None
    last_seen = None

    for row in rows:
        for source, key in CATEGORY_SOURCES:
            mid = score_midpoint(row.get(source))
            if mid is not None:
                points_by_category[key].append(mid)

        device = row.get("device_fp") or row.get("device_id")
        if device:
            devices.add(str(device))

        strength = (row.get("strengths") or "").strip()
        if strength:
            strengths.append(strength)
        improvement = (row.get("improvements") or "").strip()
        if improvement:
            improvements.append(improvement)

        timestamp = row.get("created_at")
        if timestamp:
            if first_seen is None or timestamp < first_seen:
                first_seen = timestamp
            if last_seen is None or timestamp > last_seen:
                last_seen = timestamp

    stats = {
        "staff_name": rows[0].get("staff_name") if rows else None,
        "count": len(rows),
        "devices": len(devices),
        "first_appraisal": first_seen,
        "last_appraisal": last_seen,
        "categories": {
            key: _summarize(points_by_category[key])
            for _, key in CATEGORY_SOURCES
        },
        "strengths": strengths,
        "improvements": improvements,
    }
    return stats