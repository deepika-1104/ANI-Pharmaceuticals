import { useState, useEffect } from "react";

const NON_PARAM_PREFIXES = ["area_", "batches_", "alert_", "activity_"];
const NON_PARAM_KEYS = new Set([
  "record_date", "shift", "total_units_produced", "units_target",
  "capacity_utilization_pct", "on_time_delivery_pct", "open_issues_count",
  "batch_id", "batch_status", "total_batches",
]);

const UNIT_SUFFIXES = [
  { suffix: "pct_rh", unit: "% RH" },
  { suffix: "celsius", unit: "°C" },
  { suffix: "rpm", unit: "RPM" },
  { suffix: "ppb", unit: "ppb" },
  { suffix: "pa", unit: "Pa" },
  { suffix: "kn", unit: "kN" },
  { suffix: "pct", unit: "%" },
];

function parseCSV(text) {
  const lines = text.trim().split("\n");
  const headers = lines[0].split(",").map((h) => h.trim());
  const rows = lines.slice(1).map((line) => {
    const vals = line.split(",");
    const row = {};
    headers.forEach((h, i) => {
      const v = vals[i]?.trim();
      row[h] = isNaN(v) || v === "" ? v : Number(v);
    });
    return row;
  });
  return { headers, rows };
}

function detectColumns(headers) {
  return {
    areaColumns: headers.filter((h) => h.startsWith("area_") && h.endsWith("_units")),
    batchColumns: headers.filter((h) => h.startsWith("batches_")),
    alertColumns: headers.filter((h) => h.startsWith("alert_") && h.endsWith("_count")),
    activityColumns: headers.filter((h) => h.startsWith("activity_")),
    paramColumns: headers.filter(
      (h) => !NON_PARAM_KEYS.has(h) && !NON_PARAM_PREFIXES.some((p) => h.startsWith(p))
    ),
  };
}

export function extractParamMeta(colName) {
  for (const { suffix, unit } of UNIT_SUFFIXES) {
    if (colName.endsWith("_" + suffix)) {
      const label = colName
        .slice(0, -(suffix.length + 1))
        .replace(/_/g, " ")
        .replace(/\b\w/g, (c) => c.toUpperCase());
      return { unit, label };
    }
  }
  return {
    unit: "",
    label: colName.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
  };
}

function avg(arr) {
  return arr.length ? arr.reduce((s, v) => s + v, 0) / arr.length : 0;
}

function sum(arr) {
  return arr.reduce((s, v) => s + v, 0);
}

function aggregateDay(rows, colGroups) {
  if (!rows.length) return null;
  const { areaColumns, batchColumns, alertColumns, activityColumns, paramColumns } = colGroups;

  const totalProduced = sum(rows.map((r) => r.total_units_produced));
  const totalTarget = sum(rows.map((r) => r.units_target));
  const totalBatches = sum(rows.map((r) => r.total_batches));

  const batches = { total: totalBatches };
  batchColumns.forEach((col) => {
    batches[col.replace(/^batches_/, "")] = sum(rows.map((r) => r[col]));
  });

  const completed = batches.completed ?? 0;
  const in_progress = batches.in_progress ?? 0;

  const areas = {};
  areaColumns.forEach((col) => {
    areas[col.replace(/^area_/, "").replace(/_units$/, "")] = sum(rows.map((r) => r[col]));
  });

  const params = {};
  paramColumns.forEach((col) => {
    params[col] = avg(rows.map((r) => r[col]));
  });

  const alerts = {};
  alertColumns.forEach((col) => {
    alerts[col.replace(/^alert_/, "").replace(/_count$/, "")] = sum(rows.map((r) => r[col]));
  });

  const activities = {};
  activityColumns.forEach((col) => {
    const key = col.replace(/^activity_/, "");
    const vals = rows.map((r) => r[col]);
    activities[key] = typeof vals[0] === "number" ? sum(vals) : vals[vals.length - 1];
  });

  return {
    totalProduced,
    totalTarget,
    capacityPct: avg(rows.map((r) => r.capacity_utilization_pct)),
    onTimePct: avg(rows.map((r) => r.on_time_delivery_pct)),
    openIssues: sum(rows.map((r) => r.open_issues_count)),
    batchSuccessRate: totalBatches > 0 ? (completed / totalBatches) * 100 : 0,
    qualityPassRate: totalBatches > 0 ? ((completed + in_progress) / totalBatches) * 100 : 0,
    batches,
    areas,
    params,
    alerts,
    activities,
  };
}

export function useProductionData() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch("/production_dashboard.csv")
      .then((r) => r.text())
      .then((text) => {
        const { headers, rows } = parseCSV(text);
        const colGroups = detectColumns(headers);

        const paramRanges = {};
        colGroups.paramColumns.forEach((col) => {
          const values = rows.filter((r) => typeof r[col] === "number").map((r) => r[col]);
          paramRanges[col] = {
            ...extractParamMeta(col),
            min: Math.min(...values),
            max: Math.max(...values),
          };
        });

        const byDate = {};
        rows.forEach((r) => {
          if (!byDate[r.record_date]) byDate[r.record_date] = [];
          byDate[r.record_date].push(r);
        });

        const dates = Object.keys(byDate).sort();
        const todayDate = new Date().toISOString().slice(0, 10);
        const todayKey = byDate[todayDate] ? todayDate : dates[dates.length - 1];
        const yesterdayKey = dates[dates.indexOf(todayKey) - 1];

        const today = aggregateDay(byDate[todayKey] || [], colGroups);
        const yesterday = yesterdayKey ? aggregateDay(byDate[yesterdayKey], colGroups) : null;
        const last9 = dates.slice(-9).map((d) => aggregateDay(byDate[d], colGroups));

        const shiftData = (byDate[todayKey] || []).map((r) => ({
          shift: r.shift,
          produced: Math.round(r.total_units_produced / 1000),
          target: Math.round(r.units_target / 1000),
        }));

        setData({ today, yesterday, last9, latestDate: todayKey, shiftData, paramRanges });
        setLoading(false);
      })
      .catch((e) => {
        setError(e.message);
        setLoading(false);
      });
  }, []);

  return { data, loading, error };
}
