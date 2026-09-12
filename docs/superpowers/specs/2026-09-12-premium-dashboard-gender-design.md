# Premium Dashboard + Gender Metrics — Design Spec
**Date:** 2026-09-12
**Status:** Approved (Sections 1–4)

## 1. Overview
- Clarify rating distribution as "number of reviewers per band".
- Remove top-level `Overall Average` KPI; replace with `Males Assessed` / `Females Assessed`.
- Premium executive dashboard redesign (light airy base, navy/gold premium cards).
- Auto-detect staff gender from first names with admin confirmation for uncertain cases.
- Correct malformed `Isaac Adjie ( Accounts)` → `Isaac Adjei` and deduplicate.

## 2. Architecture & Components
- **DB:** `staff_names` gains `gender ENUM('male','female','unspecified') DEFAULT 'unspecified'` plus optional `gender_confidence ENUM('high','medium','low')` for flagging.
- **Module `gender_detect.py`:** `detect_gender(name) -> (gender, confidence)` — pure function, no I/O.
- **Migration:** `ensure_schema()` adds column if missing, backfills via detector, fixes the Isaac typo and deduplicates.
- **Dashboard:** KPI queries join `appraisals` → `staff_names` on `staff_id`; top row recomputed.
- **Settings:** Gender pills + inline `Confirm` selects for medium/low confidence rows.

## 3. Data Model
```sql
ALTER TABLE staff_names ADD COLUMN gender ENUM('male','female','unspecified') DEFAULT 'unspecified';
ALTER TABLE staff_names ADD COLUMN gender_confidence ENUM('high','medium','low') DEFAULT NULL;
-- backfill handled in Python (see §4)
-- Isaac fix: UPDATE staff_names SET name='Isaac Adjei' WHERE name='Isaac Adjie ( Accounts)'
-- deduplicate: if two rows now share same name (case-insensitive), reassign appraisals.staff_id to survivor and DELETE duplicate.
```
- Existing `UNIQUE(name)` remains case-insensitive via collation; gender does not affect uniqueness.

## 4. Gender Detection Heuristic
Order:
1. Extract first token: `canonical = " ".join(name.split())`, strip parens, split on space, strip initials like `N.Y.`, hyphen → first token.
2. Strong dictionaries (from roster + Ghanaian-common):
   - `FEMALE_STRONG = {Deborah, Mabel, Judith, Ruth, Winifred, Victoria, Precious, Miracle, Happy, Majesty, ...}`
   - `MALE_STRONG = {Daniel, Emmanuel, Eric, Evans, Frank, Frederick, George, Goka, Harry, Joseph, Lawrence, Marcel, Michael, Richard, Yaw, Jonas, Isaac, ...}`
   - Exact case-insensitive match → `high`.
3. Fallback: not in strong lists → `unspecified` + `low` (conservative; no ending-based guess to avoid bias).
4. Batch run: for `gender='unspecified'`, call detector, set `gender` + `gender_confidence`. High-confidence auto-applies; medium/low flagged for UI.

New staff via `POST /api/settings/staff {name, gender?}`: if `gender` omitted, auto-detect then store with its confidence; admin can still override.

## 5. Dashboard Changes
- **Top KPIs (4 cards):** `Total Appraisals` | `Staff Assessed` | `Males Assessed` | `Females Assessed`. Remove `Overall Average` from this row. Compute:
  ```sql
  SELECT COUNT(DISTINCT a.staff_id) FROM appraisals a JOIN staff_names s ON a.staff_id=s.id WHERE s.gender='male'
  -- same for female
  ```
- **Staff breakdown:** keeps mini `Overall Avg` (`stat-overall`) + category bars.
- **Rating distribution:** header → `Rating Distribution — number of reviewers per band (Excellent → Needs Improvement)`. Table cells remain `bands[Excellent]…` counts (number of people who gave that rating for that area). No data change, only label clarification.
- **Data flow:** `GET /dashboard` loads `kpis` dict with new keys; template renders them. `GET /api/staff/{id}` unchanged except now counts reflect backfilled `staff_id`.

## 6. Premium UI
- Base: keep `bg-gradient-to-br from-blue-50 to-sky-50`. Cards: `bg-white rounded-2xl shadow border border-gray-100` upgraded with `border-t-4 border-[#C9A86A]` or navy accent, `hover:-translate-y-1 shadow-xl` transition, icon + large number typography. Gender KPI cards tint `blue-50` / `pink-50` subtly.
- Header: existing navy gradient kept, add gold underline accent.
- No dark mode toggle.

## 7. Settings Confirmation UI
- Table columns: Name | Gender pill (♂ blue, ♀ pink, – gray) | Actions.
- If `gender_confidence != 'high'` and `gender != 'unspecified'`, show amber badge `Confirm` with `<select>` Male/Female. On change → `fetch POST /api/settings/staff {id, action:'update_gender', gender}` → updates row, removes badge, dashboard KPIs reflect on next load.
- Add path restores admin credentials handling (uses `Personnel Officer` hash).

## 8. Error Handling
- Invalid gender → `400`.
- Missing column → `ensure_schema` creates it; backfill wrapped in try/except and logs.
- Duplicate Isaac merge wrapped in transaction; if `INSERT` fails due to collation, `SELECT ... LOWER(name)` fallback finds survivor.

## 9. Testing
- `test_gender_detect.py`: strong names high, unknown low, parens/initials stripped.
- Existing `test_core` (29 tests) untouched.
- Integration: start server, `GET /` → `window.STAFF_NAMES` 32, `GET /dashboard` as admin → `kpis.males + kpis.females <= kpis.staff`, `GET /api/staff/<evans-id>` count 29, confirm flow updates KPI after gender change.
- Visual: Playwright screenshots 1440×900 and 390×844 for top and sticky banner.
