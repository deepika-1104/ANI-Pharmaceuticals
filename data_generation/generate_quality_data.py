import csv
import os
import random
from datetime import date, timedelta
from collections import Counter, defaultdict
from pathlib import Path
import statistics as stats

random.seed(99)

PRODUCTS = list({
    "Amoxicillin 500mg":    (96.5, 2.0),
    "Ibuprofen 400mg":      (95.8, 2.5),
    "Paracetamol 650mg":    (97.2, 1.8),
    "Metformin 1g":         (96.0, 2.2),
    "Cetirizine 10mg":      (97.5, 1.5),
    "Atorvastatin 20mg":    (94.5, 3.0),
    "Omeprazole 20mg":      (95.0, 2.8),
    "Amlodipine 5mg":       (96.8, 1.8),
    "Ciprofloxacin 500mg":  (93.5, 3.5),
    "Azithromycin 250mg":   (94.0, 3.2),
}.keys())

PRODUCT_PROFILES = {
    "Amoxicillin 500mg":    (96.5, 2.0),
    "Ibuprofen 400mg":      (95.8, 2.5),
    "Paracetamol 650mg":    (97.2, 1.8),
    "Metformin 1g":         (96.0, 2.2),
    "Cetirizine 10mg":      (97.5, 1.5),
    "Atorvastatin 20mg":    (94.5, 3.0),
    "Omeprazole 20mg":      (95.0, 2.8),
    "Amlodipine 5mg":       (96.8, 1.8),
    "Ciprofloxacin 500mg":  (93.5, 3.5),
    "Azithromycin 250mg":   (94.0, 3.2),
}

INSPECTION_STAGES = (
    ["In-Process"] * 4 + ["Final Release"] * 2 + ["Stability", "Incoming"]
)

# Full audit pool with priorities and typical recurrence (days between occurrences)
AUDIT_POOL = [
    ("Internal GMP Audit",        "Manufacturing",    35, "High",   30),
    ("Supplier Qualification",    "Procurement",      20, "Medium", 45),
    ("Annual Regulatory Audit",   "QA Department",    10, "High",   90),
    ("Process Validation Audit",  "Production",       15, "Medium", 60),
    ("Environmental Monitoring",  "Quality Control",  12, "Low",    21),
    ("Equipment Qualification",   "Engineering",       8, "Medium", 45),
]
AUDIT_NAMES      = [a[0] for a in AUDIT_POOL]
AUDIT_DEPTS      = [a[1] for a in AUDIT_POOL]
AUDIT_WEIGHTS    = [a[2] for a in AUDIT_POOL]
AUDIT_PRIORITIES = [a[3] for a in AUDIT_POOL]
AUDIT_RECURRENCE = [a[4] for a in AUDIT_POOL]

SEASONAL_MODIFIER = {
    1:  (-1.5, 1.2),  2: (-1.0, 1.0),  3: (-0.5, 0.8),
    4:  ( 0.0, 0.7),  5: ( 0.3, 0.6),  6: ( 0.5, 0.6),
    7:  ( 0.0, 0.8),  8: (-0.3, 0.9),  9: ( 0.2, 0.7),
    10: ( 0.5, 0.6), 11: (-0.2, 0.8), 12: (-1.2, 1.1),
}

def clamp(val, lo, hi):
    return max(lo, min(hi, val))

# ── Pre-generate a rolling audit schedule for the full year ───────────────────
# Each audit type fires on a schedule; on any given day we pick the 3 soonest
def build_audit_schedule(start: date, end: date) -> dict:
    """Returns dict: date_str -> list of (name, dept, audit_date, priority)"""
    # Generate next occurrence for each audit type across the year
    all_events = []
    for idx, (name, dept, _, priority, recur) in enumerate(AUDIT_POOL):
        # Stagger start dates so they don't all fire on Jan 1
        offset = random.randint(3, recur)
        current = start + timedelta(days=offset)
        while current <= end + timedelta(days=60):  # extend so Dec has future audits
            # Add some jitter to the recurrence
            jitter = random.randint(-5, 5)
            all_events.append((current, name, dept, priority))
            current += timedelta(days=recur + jitter)

    # For each date in range, find next 3 upcoming audits
    schedule = {}
    all_dates = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    for d in all_dates:
        upcoming = sorted(
            [(ev_date, nm, dp, pr) for (ev_date, nm, dp, pr) in all_events if ev_date > d],
            key=lambda x: x[0]
        )[:3]
        # Pad to 3 if not enough
        while len(upcoming) < 3:
            upcoming.append((d + timedelta(days=30), "Internal GMP Audit", "Manufacturing", "High"))
        schedule[d.strftime("%Y-%m-%d")] = upcoming
    return schedule

# ── Pre-generate audit scores with memory (for "vs last audit" delta) ─────────
def build_audit_score_history(start: date, end: date) -> dict:
    """Returns dict: date_str -> (today_score, previous_score)"""
    history = {}
    prev_score = round(clamp(random.gauss(94.0, 2.0), 82, 100), 1)
    all_dates = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    for d in all_dates:
        # Score changes slowly — autocorrelated walk
        change = random.gauss(0, 0.8)
        today_score = round(clamp(prev_score + change, 82, 100), 1)
        history[d.strftime("%Y-%m-%d")] = (today_score, prev_score)
        prev_score = today_score
    return history

_day_cache = {}

def get_day_context(d: date, audit_schedule: dict, audit_history: dict) -> dict:
    if d in _day_cache:
        return _day_cache[d]

    mod_mean, mod_std = SEASONAL_MODIFIER[d.month]

    event = random.choices(
        ["normal", "quality_issue", "maintenance", "audit_day"],
        weights=[82, 11, 4, 3]
    )[0]

    score_drag = {
        "normal":        0,
        "quality_issue": random.uniform(3.0, 7.0),
        "maintenance":   random.uniform(1.0, 3.0),
        "audit_day":     random.uniform(0.5, 1.5),
    }[event]

    day_modifier = clamp(random.gauss(mod_mean, mod_std) - score_drag, -10, 3)

    if event == "quality_issue":
        dev_critical = random.choices([0,1,2,3], weights=[25,40,25,10])[0]
        dev_major    = random.choices([1,2,3,4,5], weights=[15,30,30,18,7])[0]
        dev_minor    = random.randint(8, 18)
    elif event == "maintenance":
        dev_critical = random.choices([0,1], weights=[55,45])[0]
        dev_major    = random.choices([1,2,3], weights=[40,38,22])[0]
        dev_minor    = random.randint(4, 12)
    elif event == "audit_day":
        dev_critical = random.choices([0,1], weights=[65,35])[0]
        dev_major    = random.choices([0,1,2], weights=[45,38,17])[0]
        dev_minor    = random.randint(3, 10)
    else:
        dev_critical = random.choices([0,1], weights=[90,10])[0]
        dev_major    = random.choices([0,1,2], weights=[55,35,10])[0]
        dev_minor    = random.randint(0, 7)

    open_ncrs = clamp(
        int(random.gauss(4, 2.0) + dev_critical * 2.0 + dev_major * 0.6), 0, 20
    )

    capa_critical = dev_critical
    capa_major    = max(0, dev_major - random.randint(0, 1))
    capa_min      = capa_critical + capa_major
    capa_extra    = random.randint(0, 2)
    capa_pending  = max(capa_min, clamp(capa_min + capa_extra, 0, max(open_ncrs, capa_min)))

    # Audit score: use autocorrelated history + event drag
    audit_drag = {
        "normal": 0, "quality_issue": random.uniform(1, 3),
        "maintenance": random.uniform(0.5, 1.5), "audit_day": random.uniform(0.5, 1.0)
    }[event]
    base_audit, prev_audit = audit_history[d.strftime("%Y-%m-%d")]
    audit_score     = round(clamp(base_audit - audit_drag, 82, 100), 1)
    prev_audit_score = round(prev_audit, 1)

    base_batches = random.choices([3,4,5,6,7,8], weights=[4,14,28,30,16,8])[0]
    if d.weekday() >= 5:
        base_batches = max(2, base_batches - 2)
    if event == "maintenance":
        base_batches = max(2, base_batches - 1)

    # 3 upcoming audits from schedule
    upcoming = audit_schedule[d.strftime("%Y-%m-%d")]

    ctx = {
        "event":             event,
        "day_modifier":      day_modifier,
        "dev_critical":      dev_critical,
        "dev_major":         dev_major,
        "dev_minor":         dev_minor,
        "open_ncrs":         open_ncrs,
        "capa_pending":      capa_pending,
        "capa_critical":     capa_critical,
        "capa_major":        capa_major,
        "audit_score":       audit_score,
        "prev_audit_score":  prev_audit_score,
        "n_batches":         base_batches,
        "allow_fail":        (dev_critical > 0 or dev_major > 0),
        # 3 upcoming audits
        "audit1_name":       upcoming[0][1],
        "audit1_department": upcoming[0][2],
        "audit1_date":       upcoming[0][0].strftime("%Y-%m-%d"),
        "audit1_priority":   upcoming[0][3],
        "audit2_name":       upcoming[1][1],
        "audit2_department": upcoming[1][2],
        "audit2_date":       upcoming[1][0].strftime("%Y-%m-%d"),
        "audit2_priority":   upcoming[1][3],
        "audit3_name":       upcoming[2][1],
        "audit3_department": upcoming[2][2],
        "audit3_date":       upcoming[2][0].strftime("%Y-%m-%d"),
        "audit3_priority":   upcoming[2][3],
    }
    _day_cache[d] = ctx
    return ctx


def score_to_result(score: int, allow_fail: bool) -> str:
    if score >= 93:
        return "Pass"
    elif score >= 88:
        return random.choices(["Pass", "Cond.Pass"], weights=[60, 40])[0]
    elif score >= 78:
        return random.choices(["Cond.Pass", "Fail"], weights=[75, 25])[0] if allow_fail else "Cond.Pass"
    else:
        return "Fail" if allow_fail else "Cond.Pass"


def result_to_severity(result: str) -> str:
    if result == "Fail":
        return random.choices(["Critical", "Major"], weights=[35, 65])[0]
    elif result == "Cond.Pass":
        return random.choices(["Major", "Minor"], weights=[55, 45])[0]
    else:
        return random.choices(["Minor", "None"], weights=[30, 70])[0]


def generate_rows(d: date, audit_schedule: dict, audit_history: dict) -> list:
    ctx   = get_day_context(d, audit_schedule, audit_history)
    rows  = []
    prods = random.sample(PRODUCTS, min(ctx["n_batches"], len(PRODUCTS)))
    force_bad = ctx["dev_critical"] > 0 or ctx["dev_major"] >= 2

    for i, product in enumerate(prods):
        batch_id = f"BTC-{d.strftime('%Y%m%d')}-{i+1:03d}"
        stage    = random.choice(INSPECTION_STAGES)

        prod_mean, prod_std = PRODUCT_PROFILES[product]
        score = clamp(random.gauss(prod_mean + ctx["day_modifier"], prod_std), 62, 100)

        if force_bad and i == 0:
            score = clamp(random.gauss(84, 3), 62, 87)

        score        = int(round(score))
        result       = score_to_result(score, allow_fail=ctx["allow_fail"])
        dev_severity = result_to_severity(result)

        rows.append({
            "record_date":              d.strftime("%Y-%m-%d"),
            "batch_id":                 batch_id,
            "product_name":             product,
            "inspection_stage":         stage,
            "inspection_score":         score,
            "inspection_result":        result,
            "deviation_severity":       dev_severity,
            "open_ncrs_count":          ctx["open_ncrs"],
            "capa_pending_count":       ctx["capa_pending"],
            "capa_critical_count":      ctx["capa_critical"],
            "capa_major_count":         ctx["capa_major"],
            "audit_score_pct":          ctx["audit_score"],
            "previous_audit_score_pct": ctx["prev_audit_score"],   # GAP 1 FIX
            "deviation_critical_count": ctx["dev_critical"],
            "deviation_major_count":    ctx["dev_major"],
            "deviation_minor_count":    ctx["dev_minor"],
            "audit1_name":              ctx["audit1_name"],         # GAP 2 FIX
            "audit1_department":        ctx["audit1_department"],
            "audit1_date":              ctx["audit1_date"],
            "audit1_priority":          ctx["audit1_priority"],
            "audit2_name":              ctx["audit2_name"],
            "audit2_department":        ctx["audit2_department"],
            "audit2_date":              ctx["audit2_date"],
            "audit2_priority":          ctx["audit2_priority"],
            "audit3_name":              ctx["audit3_name"],
            "audit3_department":        ctx["audit3_department"],
            "audit3_date":              ctx["audit3_date"],
            "audit3_priority":          ctx["audit3_priority"],
        })

    return rows


def load_env(env_path: Path) -> None:
    """Parse a .env file and set variables into os.environ (no third-party deps)."""
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def main():
    # ── Load .env ──────────────────────────────────────────────────────────────
    # Walk up from the script's directory to find backend/.env
    env_file = None
    search_dir = Path(__file__).resolve().parent
    for _ in range(5):  # search up to 5 levels
        candidate = search_dir / "backend" / ".env"
        if candidate.exists():
            env_file = candidate
            break
        search_dir = search_dir.parent

    if env_file:
        load_env(env_file)
    else:
        print("Warning: backend/.env not found — falling back to environment variables")

    mongo_uri = os.environ.get("MONGO_URI", "")
    db_name   = os.environ.get("MONGO_DB_NAME", "voxa")

    if not mongo_uri:
        raise RuntimeError("MONGO_URI is not set. Add it to backend/.env")

    start    = date(2026, 1, 1)
    end      = date(2026, 12, 31)

    print("Building audit schedule...")
    audit_schedule = build_audit_schedule(start, end)

    print("Building audit score history...")
    audit_history = build_audit_score_history(start, end)

    all_rows = []
    current  = start
    while current <= end:
        all_rows.extend(generate_rows(current, audit_schedule, audit_history))
        current += timedelta(days=1)

    # ── Write CSV locally ─────────────────────────────────────────────────────
    output_file = "quality_dashboard.csv"
    fieldnames  = list(all_rows[0].keys())
    with open(output_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\nCSV written  : {output_file}  ({len(all_rows)} rows)")

    # ── Insert into MongoDB ───────────────────────────────────────────────────
    try:
        from pymongo import MongoClient
    except ImportError:
        raise RuntimeError("pymongo is not installed. Run: pip install pymongo")

    client     = MongoClient(mongo_uri)
    db         = client[db_name]
    collection = db["quality_dashboard"]

    # Drop existing data so re-runs are idempotent
    collection.drop()
    result = collection.insert_many(all_rows)

    print(f"MongoDB      : {len(result.inserted_ids)} documents inserted")
    print(f"  database   : {db_name}")
    print(f"  collection : quality_dashboard")
    print(f"  date range : {start} to {end}")

    client.close()

    # ── Validation ────────────────────────────────────────────────────────────
    scores  = [int(r["inspection_score"]) for r in all_rows]
    results = Counter(r["inspection_result"] for r in all_rows)
    total   = len(all_rows)

    capa_issues = sum(
        1 for r in all_rows
        if int(r["capa_pending_count"]) < int(r["capa_critical_count"]) + int(r["capa_major_count"])
    )
    daily = defaultdict(list)
    for r in all_rows: daily[r["record_date"]].append(r)
    mismatched = sum(
        1 for d, drows in daily.items()
        if int(drows[0]["deviation_critical_count"]) == 0
        and int(drows[0]["deviation_major_count"]) == 0
        and any(r["inspection_result"] == "Fail" for r in drows)
    )

    # Verify 3 distinct audits per day
    sample_day = "2026-01-15"
    sd = daily[sample_day][0]
    print(f"\nSample day {sample_day}:")
    print(f"  audit_score={sd['audit_score_pct']}  prev_audit_score={sd['previous_audit_score_pct']}")
    print(f"  Audit 1: {sd['audit1_name']} | {sd['audit1_department']} | {sd['audit1_date']} | {sd['audit1_priority']}")
    print(f"  Audit 2: {sd['audit2_name']} | {sd['audit2_department']} | {sd['audit2_date']} | {sd['audit2_priority']}")
    print(f"  Audit 3: {sd['audit3_name']} | {sd['audit3_department']} | {sd['audit3_date']} | {sd['audit3_priority']}")

    print(f"\nGenerated  : {total} rows | Columns: {len(fieldnames)}")
    print(f"Result dist: {dict(results)}")
    print(f"Score      : min={min(scores)}  max={max(scores)}  mean={stats.mean(scores):.1f}")
    print(f"\n── Logic checks (all must be 0) ──")
    print(f"  capa_pending < crit+major   : {capa_issues}")
    print(f"  No-deviation days with Fail : {mismatched}")

    print(f"\n── Dashboard coverage ──")
    print(f"  ✓ Inspection Pass Rate + vs yesterday  (derived from inspection_result)")
    print(f"  ✓ Open NCRs + vs last week             (open_ncrs_count)")
    print(f"  ✓ CAPA Pending + critical/major label  (capa_pending/critical/major_count)")
    print(f"  ✓ Audit Score + vs last audit          (audit_score_pct, previous_audit_score_pct)")
    print(f"  ✓ Deviation by Severity                (deviation_critical/major/minor_count)")
    print(f"  ✓ Inspection Score Trend 7-day         (record_date + inspection_score)")
    print(f"  ✓ Upcoming Audits (3 entries)          (audit1/2/3 columns)")
    print(f"  ✓ Recent Inspections table             (batch-level rows)")


if __name__ == "__main__":
    main()
