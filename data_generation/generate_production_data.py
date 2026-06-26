import csv
import random
import math
import os
from datetime import date, timedelta
from collections import defaultdict
from pathlib import Path

random.seed(42)

SHIFTS = ["Morning", "Afternoon", "Night"]

SHIFT_EFFICIENCY = {
    "Morning":   1.00,
    "Afternoon": 0.95,
    "Night":     0.88,
}

# Each month: (mean, std) — day-level base drawn once per date
SEASONAL_BAND = {
    1:  (0.92, 0.03),
    2:  (0.93, 0.025),
    3:  (0.97, 0.02),
    4:  (0.98, 0.02),
    5:  (1.00, 0.015),
    6:  (1.01, 0.015),
    7:  (0.97, 0.025),
    8:  (0.96, 0.025),
    9:  (1.02, 0.02),
    10: (1.03, 0.015),
    11: (0.99, 0.02),
    12: (0.97, 0.03),
}

def clamp(value, lo, hi):
    return max(lo, min(hi, value))

# ── Day-level cache: one draw per date shared across all 3 shifts ──────────────
# This makes "bad days" consistently bad and "good days" consistently good
_day_cache = {}

def get_day_context(d: date) -> dict:
    if d in _day_cache:
        return _day_cache[d]

    mean, std = SEASONAL_BAND[d.month]
    weekend_dip = random.uniform(0.03, 0.06) if d.weekday() >= 5 else 0.0
    seasonal   = clamp(random.gauss(mean, std) - weekend_dip, 0.80, 1.10)

    # Day-level "event" — rare equipment issue or maintenance day
    event = random.choices(["normal", "minor_issue", "maintenance"], weights=[80, 15, 5])[0]

    # Day-level open issues drift — tends to cluster
    base_open_issues = random.choices([0,1,2,3,4,5,6], weights=[8,18,25,22,15,8,4])[0]

    # Day-level on-time delivery baseline (shared, then shift adds noise)
    otd_base = clamp(random.gauss(91, 4) * seasonal, 70, 99)

    # Capacity baseline for the day
    cap_base = clamp(random.gauss(68, 6) * seasonal, 50, 95)

    # Alert tendency for the day — some days are just alert-heavy
    alert_tendency = random.choices(["quiet", "normal", "busy"], weights=[25, 55, 20])[0]

    # Parameter drift — equipment wanders over the day
    param_drift = {
        "granulator_speed": random.gauss(0, 8),
        "coater_temp":      random.gauss(0, 1.5),
        "compression":      random.gauss(0, 0.8),
        "humidity":         random.gauss(0, 3),
        "diff_pressure":    random.gauss(0, 1),
        "toc":              random.gauss(0, 10),
    }

    ctx = {
        "seasonal":          seasonal,
        "event":             event,
        "base_open_issues":  base_open_issues,
        "otd_base":          otd_base,
        "cap_base":          cap_base,
        "alert_tendency":    alert_tendency,
        "param_drift":       param_drift,
    }
    _day_cache[d] = ctx
    return ctx


def generate_row(d: date, shift: str) -> dict:
    ctx  = get_day_context(d)
    eff  = SHIFT_EFFICIENCY[shift] * ctx["seasonal"]
    event = ctx["event"]

    # Event impact
    event_factor = {"normal": 1.0, "minor_issue": random.uniform(0.88, 0.96), "maintenance": random.uniform(0.70, 0.85)}[event]

    # ── KPI: Units Produced ──────────────────────────────────────────────────
    units_target         = int(420000 * eff)
    # Shift-level noise on top of day + event
    shift_noise          = random.gauss(1.0, 0.04)
    total_units_produced = int(clamp(units_target * shift_noise * event_factor, 200000, 520000))

    # ── KPI: Capacity Utilization ────────────────────────────────────────────
    # Derived from units but with its own shift-level jitter
    cap_shift_jitter         = random.gauss(0, 2)
    capacity_utilization_pct = round(clamp(ctx["cap_base"] * event_factor + cap_shift_jitter, 45, 95), 1)

    # ── KPI: On Time Delivery ────────────────────────────────────────────────
    # Night shift tends to have slightly lower OTD
    shift_otd_penalty        = {"Morning": 0, "Afternoon": random.uniform(-1, 0), "Night": random.uniform(-3, 0)}[shift]
    on_time_delivery_pct     = round(clamp(ctx["otd_base"] + shift_otd_penalty + random.gauss(0, 1.5), 65, 99), 1)

    # ── KPI: Open Issues ────────────────────────────────────────────────────
    # Shift adds small variation around the day's base
    shift_issue_delta = random.choices([-1, 0, 1], weights=[20, 60, 20])[0]
    open_issues_count = max(0, ctx["base_open_issues"] + shift_issue_delta)

    # ── Production by Area ────────────────────────────────────────────────────
    # Each area has its own random share that sums to 100%
    raw = [
        clamp(random.gauss(0.32, 0.015), 0.27, 0.37),  # granulation
        clamp(random.gauss(0.28, 0.015), 0.23, 0.33),  # compression
        clamp(random.gauss(0.20, 0.012), 0.16, 0.25),  # coating
        clamp(random.gauss(0.15, 0.012), 0.11, 0.19),  # packaging
    ]
    total_pct = sum(raw)
    gran_pct, comp_pct, coat_pct, pack_pct = [r / total_pct for r in raw]
    other_pct = 1 - gran_pct - comp_pct - coat_pct - pack_pct

    area_granulation_units = int(total_units_produced * gran_pct)
    area_compression_units = int(total_units_produced * comp_pct)
    area_coating_units     = int(total_units_produced * coat_pct)
    area_packaging_units   = int(total_units_produced * pack_pct)
    area_others_units      = total_units_produced - (
        area_granulation_units + area_compression_units +
        area_coating_units + area_packaging_units
    )

    # ── Batch Status ──────────────────────────────────────────────────────────
    # Total batches varies by shift and event
    base_batches     = {"Morning": 26, "Afternoon": 24, "Night": 21}[shift]
    total_batches    = clamp(int(random.gauss(base_batches, 2) * event_factor), 15, 35)

    # Completed ratio higher on morning, lower on night
    comp_ratio       = clamp(random.gauss({"Morning": 0.50, "Afternoon": 0.47, "Night": 0.42}[shift], 0.05), 0.30, 0.65)
    prog_ratio       = clamp(random.gauss(0.32, 0.04), 0.20, 0.45)
    pend_ratio       = clamp(random.gauss(0.12, 0.03), 0.05, 0.22)

    batches_completed   = int(total_batches * comp_ratio)
    batches_in_progress = int(total_batches * prog_ratio)
    batches_pending     = int(total_batches * pend_ratio)
    batches_on_hold     = max(0, total_batches - batches_completed - batches_in_progress - batches_pending)

    batch_id     = f"BT{d.strftime('%Y%m%d')}{SHIFTS.index(shift)+1}"
    status_pool  = (
        ["Completed"]   * batches_completed +
        ["In Progress"] * batches_in_progress +
        ["Pending"]     * batches_pending +
        ["On Hold"]     * batches_on_hold
    )
    batch_status = random.choice(status_pool) if status_pool else "Completed"

    # ── Critical Parameters ───────────────────────────────────────────────────
    # Base + day-level drift + shift-level noise
    drift = ctx["param_drift"]

    granulator_speed_rpm      = int(clamp(random.gauss(450 + drift["granulator_speed"], 6), 400, 520))
    coater_inlet_temp_celsius = round(clamp(random.gauss(58 + drift["coater_temp"], 1.0), 52, 66), 1)
    compression_force_kn      = round(clamp(random.gauss(18 + drift["compression"], 0.6), 14, 23), 1)
    humidity_pct_rh           = round(clamp(random.gauss(45 + drift["humidity"], 2.0), 33, 62), 1)
    differential_pressure_pa  = round(clamp(random.gauss(12 + drift["diff_pressure"], 0.8), 7, 19), 1)
    water_system_toc_ppb      = round(clamp(random.gauss(120 + drift["toc"], 8.0), 75, 165), 1)

    # ── Alerts ────────────────────────────────────────────────────────────────
    # Alert counts are influenced by day tendency + event
    alert_weights = {
        "quiet":  {"high": [80,16,4],   "medium": [50,30,15,5],   "low": [35,35,20,8,2]},
        "normal": {"high": [60,30,10],  "medium": [30,35,25,10],  "low": [20,30,25,15,10]},
        "busy":   {"high": [35,40,25],  "medium": [15,25,35,25],  "low": [10,20,30,25,15]},
    }[ctx["alert_tendency"]]

    if event == "maintenance":
        alert_high_count   = random.choices([0,1,2,3], weights=[20,35,30,15])[0]
    else:
        alert_high_count   = random.choices([0,1,2], weights=alert_weights["high"])[0]

    alert_medium_count = random.choices([0,1,2,3],   weights=alert_weights["medium"])[0]
    alert_low_count    = random.choices([0,1,2,3,4], weights=alert_weights["low"])[0]

    # ── Upcoming Activities ───────────────────────────────────────────────────
    # Calibration tends to cluster near month-start and mid-month
    day_of_month = d.day
    cal_boost    = 2 if day_of_month in range(1, 5) or day_of_month in range(14, 18) else 0
    activity_equipment_calibration_due  = clamp(random.choices([0,1,2,3,4,5], weights=[20,25,22,18,10,5])[0] + cal_boost, 0, 7)

    # Preventive maintenance spikes mid-week
    pm_boost     = 2 if d.weekday() in [1, 2] else 0
    activity_preventive_maintenance_due = clamp(random.choices([0,1,2,3,4,5,6,7], weights=[15,20,20,18,12,8,5,2])[0] + pm_boost, 0, 10)

    activity_changeover_scheduled       = random.choices([0,1,2,3,4,5,6], weights=[15,20,22,20,13,7,3])[0]

    qc_hours   = random.choices([9,10,11,14,15,16], weights=[10,20,15,25,20,10])[0]
    qc_minutes = random.choices([0, 15, 30, 45],    weights=[40, 25, 25, 10])[0]
    activity_qc_review_time = f"{qc_hours:02d}:{qc_minutes:02d}"

    return {
        "record_date":                          d.strftime("%Y-%m-%d"),
        "shift":                                shift,
        "total_units_produced":                 total_units_produced,
        "units_target":                         units_target,
        "capacity_utilization_pct":             capacity_utilization_pct,
        "on_time_delivery_pct":                 on_time_delivery_pct,
        "open_issues_count":                    open_issues_count,
        "area_granulation_units":               area_granulation_units,
        "area_compression_units":               area_compression_units,
        "area_coating_units":                   area_coating_units,
        "area_packaging_units":                 area_packaging_units,
        "area_others_units":                    area_others_units,
        "batch_id":                             batch_id,
        "batch_status":                         batch_status,
        "total_batches":                        total_batches,
        "batches_completed":                    batches_completed,
        "batches_in_progress":                  batches_in_progress,
        "batches_pending":                      batches_pending,
        "batches_on_hold":                      batches_on_hold,
        "granulator_speed_rpm":                 granulator_speed_rpm,
        "coater_inlet_temp_celsius":            coater_inlet_temp_celsius,
        "compression_force_kn":                 compression_force_kn,
        "humidity_pct_rh":                      humidity_pct_rh,
        "differential_pressure_pa":             differential_pressure_pa,
        "water_system_toc_ppb":                 water_system_toc_ppb,
        "alert_high_count":                     alert_high_count,
        "alert_medium_count":                   alert_medium_count,
        "alert_low_count":                      alert_low_count,
        "activity_equipment_calibration_due":   activity_equipment_calibration_due,
        "activity_preventive_maintenance_due":  activity_preventive_maintenance_due,
        "activity_changeover_scheduled":        activity_changeover_scheduled,
        "activity_qc_review_time":              activity_qc_review_time,
    }


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
    env_file = Path(__file__).parent / "backend" / ".env"
    if env_file.exists():
        load_env(env_file)
    else:
        print(f"Warning: {env_file} not found — falling back to environment variables")

    mongo_uri = os.environ.get("MONGO_URI", "")
    db_name   = os.environ.get("MONGO_DB_NAME", "voxa")

    if not mongo_uri:
        raise RuntimeError("MONGO_URI is not set. Add it to backend/.env")

    # ── Generate rows ──────────────────────────────────────────────────────────
    start = date(2026, 1, 1)
    end   = date(2026, 12, 31)
    rows  = []

    current = start
    while current <= end:
        for shift in SHIFTS:
            rows.append(generate_row(current, shift))
        current += timedelta(days=1)

    # ── Write CSV ──────────────────────────────────────────────────────────────
    output_file = "production_dashboard.csv"
    fieldnames  = list(rows[0].keys())

    with open(output_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"CSV written  : {output_file}  ({len(rows)} rows)")

    # ── Insert into MongoDB ────────────────────────────────────────────────────
    try:
        from pymongo import MongoClient
    except ImportError:
        raise RuntimeError("pymongo is not installed. Run: pip install pymongo")

    client     = MongoClient(mongo_uri)
    db         = client[db_name]
    collection = db["production_dashboard"]

    # Drop existing data so re-runs are idempotent
    collection.drop()
    result = collection.insert_many(rows)

    print(f"MongoDB      : {len(result.inserted_ids)} documents inserted")
    print(f"  database   : {db_name}")
    print(f"  collection : production_dashboard")
    print(f"  date range : {start} to {end}, 3 shifts/day")

    client.close()


if __name__ == "__main__":
    main()
