# Premium Dashboard + Gender Metrics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace top Overall Average KPI with Males/Females Assessed, clarify rating distribution label, add heuristic gender detection with confirmation, and deliver a premium executive dashboard.

**Architecture:** Add `gender` enum to `staff_names`, pure `gender_detect.py` module, migration/backfill in `ensure_schema()`, KPI joins on `staff_id`, Settings inline confirm UI, dashboard template premium cards.

**Tech Stack:** FastAPI + Jinja2, PyMySQL (CloudClusters), Tailwind CDN, Python 3.12, Playwright for verification

**Spec:** docs/superpowers/specs/2026-09-12-premium-dashboard-gender-design.md

## Global Constraints
- Single source: `staff_names` drives dashboard selector and form `window.STAFF_NAMES`
- Strict canonical names: whitespace-collapse preserve case (no title variants)
- `UNIQUE(name)` collation case-insensitive — handle duplicates via `LOWER(name)`
- Existing 535 appraisals must retain counts after migration (backfill `staff_id`)
- `Males Assessed` = `COUNT(DISTINCT a.staff_id) JOIN staff_names WHERE gender='male'`

---

## File Structure
- `gender_detect.py` — new, pure `detect_gender(name) -> (gender, confidence)`
- `tests/test_gender_detect.py` (or `test_gender_detect.py`) — new tests
- `core.py` — no change (normalize preserved)
- `main.py` — modify `ensure_schema`, `get_all_staff`, dashboard KPIs, `/api/settings/staff`, `staff_breakdown` defense already done, add gender endpoints
- `frontend/templates/dashboard.html` — premium redesign, KPI swap, label change
- `frontend/templates/settings.html` — gender pills + Confirm select

---

### Task 1: Gender detector module

**Files:**
- Create: `gender_detect.py`
- Test: `test_gender_detect.py`

**Interfaces:**
- Consumes: nothing
- Produces: `def detect_gender(name: str) -> tuple[str, str]` where gender in `('male','female','unspecified')` and confidence in `('high','medium','low')`

- [ ] **Step 1: Write failing test**

```python
import unittest
from gender_detect import detect_gender

class TestDetect(unittest.TestCase):
    def test_strong_female(self):
        g,c = detect_gender("Deborah Otuo Twumasi")
        self.assertEqual(g, "female"); self.assertEqual(c, "high")
    def test_strong_male(self):
        g,c = detect_gender("Daniel Owusu Larbi")
        self.assertEqual(g, "male"); self.assertEqual(c, "high")
    def test_parens(self):
        g,c = detect_gender("Isaac Adjie ( Accounts)")
        self.assertEqual(g, "male")
    def test_unknown(self):
        g,c = detect_gender("Xyz Qqq")
        self.assertEqual(g, "unspecified")
```

- [ ] **Step 2: Run test to verify it fails** Run: `python -m unittest test_gender_detect -v` Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement minimal module**

```python
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
```

- [ ] **Step 4: Run test to verify it passes** Run: `python -m unittest test_gender_detect -v` Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add gender_detect.py test_gender_detect.py
git commit -m "feat: add gender detector"
```

---

### Task 2: DB migration — gender column + backfill + Isaac fix

**Files:**
- Modify: `main.py:ensure_schema`

**Interfaces:**
- Consumes: `detect_gender` from Task 1
- Produces: `staff_names.gender` populated, Isaac typo fixed, 31 vs 32 deduped

- [ ] **Step 1: Write failing check script** (no unittest, script probes DB)

```python
import pymysql, os
from dotenv import load_dotenv
load_dotenv("F:\\Web_APPs\\APPRAISAL\\.env")
conn=pymysql.connect(host=os.getenv("MYSQL_HOST"),port=int(os.getenv("MYSQL_PORT")),user=os.getenv("MYSQL_USER"),password=os.getenv("MYSQL_PASSWORD"),database=os.getenv("MYSQL_DB"),ssl={'ssl':True})
cur=conn.cursor()
cur.execute("SHOW COLUMNS FROM staff_names LIKE 'gender'")
print("has gender?", bool(cur.fetchone()))
```

Run: `python script.py` Expected: `False`

- [ ] **Step 2: Implement migration in ensure_schema** Add after admin_settings block:

```python
cursor.execute("SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='staff_names' AND COLUMN_NAME='gender'")
if not cursor.fetchone():
    cursor.execute("ALTER TABLE staff_names ADD COLUMN gender ENUM('male','female','unspecified') DEFAULT 'unspecified'")
    cursor.execute("ALTER TABLE staff_names ADD COLUMN gender_confidence ENUM('high','medium','low') DEFAULT NULL")
# Isaac fix
cursor.execute("SELECT id FROM staff_names WHERE name=%s", ("Isaac Adjie ( Accounts)",))
row=cursor.fetchone()
if row:
    dup_id=row[0]
    cursor.execute("SELECT id FROM staff_names WHERE LOWER(name)=LOWER(%s) AND id<>%s", ("Isaac Adjei", dup_id))
    dup2=cursor.fetchone()
    if dup2:
        cursor.execute("UPDATE appraisals SET staff_id=%s WHERE staff_id=%s", (dup2[0], dup_id))
        cursor.execute("DELETE FROM staff_names WHERE id=%s", (dup_id,))
    else:
        cursor.execute("UPDATE staff_names SET name=%s WHERE id=%s", ("Isaac Adjei", dup_id))
# backfill genders
from gender_detect import detect_gender
cursor.execute("SELECT id, name, gender FROM staff_names WHERE gender='unspecified' OR gender IS NULL")
for sid, name, g in cursor.fetchall():
    ng, conf = detect_gender(name)
    cursor.execute("UPDATE staff_names SET gender=%s, gender_confidence=%s WHERE id=%s", (ng, conf, sid))
```

- [ ] **Step 3: Run check script again** Expected: `True`, plus `SELECT name, gender FROM staff_names LIMIT 2` shows genders

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "feat: migrate gender column and backfill"
```

---

### Task 3: Dashboard KPIs + Settings gender API

**Files:**
- Modify: `main.py` dashboard handler + `POST /api/settings/staff`

**Interfaces:**
- Consumes: `staff_names.gender`
- Produces: `kpis` dict now `{total, staff, males, females}`

- [ ] **Step 1: Write failing check**

```python
# after startup, GET /dashboard as admin, assert kpis.males present and top Overall Average absent
```

- [ ] **Step 2: Modify dashboard**

Replace overall_avg query with:

```python
cursor.execute("SELECT COUNT(DISTINCT a.staff_id) FROM appraisals a JOIN staff_names s ON a.staff_id=s.id WHERE s.gender='male'")
kpis["males"]=cursor.fetchone()[0]
cursor.execute("SELECT COUNT(DISTINCT a.staff_id) FROM appraisals a JOIN staff_names s ON a.staff_id=s.id WHERE s.gender='female'")
kpis["females"]=cursor.fetchone()[0]
# remove overall_avg
```

And extend `POST /api/settings/staff` to handle `gender` field: if `action=="update_gender"` validate male/female/unspecified and update.

- [ ] **Step 3: Verify** Login admin, GET dashboard, assert males+females <= staff

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "feat: dashboard gender KPIs"
```

---

### Task 4: Dashboard template premium redesign

**Files:**
- Modify: `frontend/templates/dashboard.html`

**Interfaces:**
- Consumes: `kpis.males`, `kpis.females`
- Produces: premium UI

- [ ] **Step 1: Visual check before** Playwright screenshot 1440

- [ ] **Step 2: Replace KPI grid** 4 cards: Total, Staff, Males (blue tint), Females (pink tint), remove Overall Average card. Add gold top border, hover lift.

- [ ] **Step 3: Update rating distribution header** `Rating Distribution — number of reviewers per band (Excellent → Needs Improvement)` and keep band counts.

- [ ] **Step 4: Verify** Playwright screenshot premium, check no Overall Average in top row

- [ ] **Step 5: Commit**

```bash
git add frontend/templates/dashboard.html
git commit -m "feat: premium dashboard"
```

---

### Task 5: Settings gender confirmation UI

**Files:**
- Modify: `frontend/templates/settings.html`

- [ ] **Step 1: Add gender pill + Confirm select per row** JS fetches staff_list with gender, renders pill, if confidence != high show `<select>`

- [ ] **Step 2: Wire POST to update_gender**

- [ ] **Step 3: Verify** Playwright settings page shows pills

- [ ] **Step 4: Commit**

```bash
git add frontend/templates/settings.html
git commit -m "feat: settings gender confirm"
```

---

### Task 6: Verification

- [ ] Run `python -m unittest` 29+ new tests PASS
- [ ] Playwright full: form still 32, dashboard males/females sum, breakdown count 29 for Evans
- [ ] Push
