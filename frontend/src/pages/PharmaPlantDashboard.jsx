import { useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from "recharts";

// ─── DESIGN TOKENS ────────────────────────────────────────────────────────────
const T = {
  bg: "#f0f2f7",
  surface: "#ffffff",
  border: "#e8eaf0",
  borderAlert: "#fcd9b6",
  text: { primary: "#0f1117", secondary: "#5a6072", muted: "#9da3b4" },
  green: { solid: "#16a34a", light: "#dcfce7", text: "#15803d" },
  blue: { solid: "#2563eb", light: "#dbeafe", text: "#1d4ed8" },
  purple: { solid: "#7c3aed", light: "#ede9fe", text: "#6d28d9" },
  amber: { solid: "#d97706", light: "#fef3c7", text: "#b45309" },
  red: { solid: "#dc2626", light: "#fee2e2", text: "#b91c1c" },
  orange: { solid: "#ea580c", light: "#ffedd5", text: "#c2410c" },
  pink: { solid: "#db2777", light: "#fce7f3", text: "#be185d" },
};

// ─── DATA ─────────────────────────────────────────────────────────────────────
const KPI_CARDS = [
  { id: "production", label: "Today's Production", value: "1.25M", unit: "Units", delta: "+8.4% vs target",    deltaPositive: true,  sparkData: [8,12,9,15,11,14,18,16,20],   iconType: "factory",  iconBg: "#ede9fe", iconColor: "#6366f1", gradientA: "#6366f1", gradientB: "#818cf8" },
  { id: "capacity",   label: "Capacity Utilization",value: "68%",   unit: null,   delta: "+5.6% vs yesterday", deltaPositive: true,  sparkData: [55,60,58,62,59,65,63,67,68], iconType: "box",      iconBg: "#e0f2fe", iconColor: "#0ea5e9", gradientA: "#0ea5e9", gradientB: "#38bdf8" },
  { id: "quality",    label: "Quality Pass Rate",   value: "98.6%", unit: null,   delta: "+1.3% vs yesterday", deltaPositive: true,  sparkData: [96,97,96,98,97,99,98,98,99], iconType: "shield",   iconBg: "#d1fae5", iconColor: "#10b981", gradientA: "#10b981", gradientB: "#34d399" },
  { id: "batch",      label: "Batch Success Rate",  value: "96.2%", unit: null,   delta: "+2.1% vs yesterday", deltaPositive: true,  sparkData: [92,94,91,95,93,96,95,97,96], iconType: "check",    iconBg: "#ede9fe", iconColor: "#8b5cf6", gradientA: "#8b5cf6", gradientB: "#a78bfa" },
  { id: "delivery",   label: "On Time Delivery",    value: "92%",   unit: null,   delta: "+3.4% vs yesterday", deltaPositive: true,  sparkData: [85,88,87,90,89,91,90,92,92], iconType: "truck",    iconBg: "#fef3c7", iconColor: "#f59e0b", gradientA: "#f59e0b", gradientB: "#fbbf24" },
  { id: "issues",     label: "Open Issues",         value: "4",     unit: null,   delta: "Requires Attention", deltaPositive: false, sparkData: [2,3,2,4,3,5,4,3,4],          iconType: "alertTri", iconBg: "#fee2e2", iconColor: "#ef4444", gradientA: "#ef4444", gradientB: "#f87171", isAlert: true },
];

const PRODUCTION_BY_AREA = [
  { name: "Granulation", value: 32, color: "#2563eb" },
  { name: "Compression", value: 28, color: "#16a34a" },
  { name: "Coating",     value: 20, color: "#7c3aed" },
  { name: "Packaging",   value: 15, color: "#d97706" },
  { name: "Others",      value: 5,  color: "#cbd5e1" },
];

const BATCH_STATUS = [
  { name: "Completed",   value: 12, pct: "50%", color: "#16a34a" },
  { name: "In Progress", value: 8,  pct: "33%", color: "#2563eb" },
  { name: "Pending",     value: 3,  pct: "12%", color: "#d97706" },
  { name: "Hold",        value: 1,  pct: "5%",  color: "#dc2626" },
];

const QUALITY_BY_TEST = [
  { test: "Assay",        pass: 185, fail: 15 },
  { test: "Dissolution",  pass: 160, fail: 20 },
  { test: "DP Uniformity",pass: 175, fail: 10 },
  { test: "Moisture",     pass: 165, fail: 12 },
  { test: "Microbial",    pass: 120, fail: 8  },
];

const INVENTORY = [
  { label: "Raw Materials",       value: 128, unit: "Lots", iconType: "droplet", iconBg: T.blue.light,   iconColor: T.blue.solid,   bar: 0.80 },
  { label: "WIP",                 value: 45,  unit: "Lots", iconType: "gear",    iconBg: T.amber.light,  iconColor: T.amber.solid,  bar: 0.45 },
  { label: "Finished Goods",      value: 78,  unit: "Lots", iconType: "box2",    iconBg: T.green.light,  iconColor: T.green.solid,  bar: 0.65 },
  { label: "Packaging Materials", value: 62,  unit: "Lots", iconType: "package", iconBg: T.pink.light,   iconColor: T.pink.solid,   bar: 0.52 },
];

const CRITICAL_PARAMS = [
  { label: "Granulator Speed",    value: "450", unit: "RPM", status: "Normal", iconType: "gear",      iconBg: "#ede9fe", iconColor: "#7c3aed", gaugePct: 0.75 },
  { label: "Coater Inlet Temp.", value: "58",  unit: "°C",  status: "Normal", iconType: "snowflake", iconBg: "#d1fae5", iconColor: "#10b981", gaugePct: 0.58 },
  { label: "Compression Force",  value: "18",  unit: "kN",  status: "Normal", iconType: "compress",  iconBg: "#dbeafe", iconColor: "#2563eb", gaugePct: 0.60 },
  { label: "Humidity",            value: "45",  unit: "% RH",status: "Normal", iconType: "droplet",   iconBg: "#e0f2fe", iconColor: "#0ea5e9", gaugePct: 0.45 },
  { label: "Differential Press.",value: "12",  unit: "Pa",  status: "Normal", iconType: "gauge",     iconBg: "#fef3c7", iconColor: "#d97706", gaugePct: 0.40 },
  { label: "Water System TOC",   value: "120", unit: "ppb", status: "Normal", iconType: "flask",     iconBg: "#fce7f3", iconColor: "#db2777", gaugePct: 0.80 },
];

const UPCOMING_ACTIVITIES = [
  { label: "Equipment Calibration",  note: "3 Due Today",      iconBg: T.blue.light,   iconColor: T.blue.solid,   iconType: "cal",      urgency: "high" },
  { label: "Preventive Maintenance", note: "5 Due This Week",  iconBg: T.green.light,  iconColor: T.green.solid,  iconType: "wrench",   urgency: "med"  },
  { label: "Changeover",             note: "4 Scheduled",      iconBg: T.amber.light,  iconColor: T.amber.solid,  iconType: "swap",     urgency: "low"  },
  { label: "QC Review Meeting",      note: "Today 03:00 PM",   iconBg: T.purple.light, iconColor: T.purple.solid, iconType: "calcheck", urgency: "low"  },
];

// ─── ICON SYSTEM ──────────────────────────────────────────────────────────────
function Icon({ type, size = 16, color = "currentColor" }) {
  const s = size;
  const props = { width: s, height: s, viewBox: "0 0 24 24", fill: "none", stroke: color, strokeWidth: "2", strokeLinecap: "round", strokeLinejoin: "round" };
  switch (type) {
    case "factory":    return <svg {...props}><path d="M2 20V8l5-3v4l5-3v4l5-3v16H2z"/><rect x="5" y="14" width="3" height="6"/><rect x="10" y="14" width="3" height="6"/></svg>;
    case "box":        return <svg {...props}><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/></svg>;
    case "shield":     return <svg {...props}><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/></svg>;
    case "check":      return <svg {...props}><path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z"/><polyline points="9 12 11 14 15 10"/></svg>;
    case "truck":      return <svg {...props}><rect x="1" y="3" width="15" height="13"/><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/></svg>;
    case "alertTri":   return <svg width={s} height={s} viewBox="0 0 24 24" fill={color}><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13" stroke="white" strokeWidth="2" strokeLinecap="round"/><circle cx="12" cy="17" r="1" fill="white"/></svg>;
    case "droplet":    return <svg {...props}><path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z"/></svg>;
    case "gear":       return <svg {...props}><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>;
    case "box2":       return <svg {...props}><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/></svg>;
    case "package":    return <svg {...props}><line x1="16.5" y1="9.4" x2="7.5" y2="4.21"/><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>;
    case "snowflake":  return <svg {...props}><line x1="12" y1="2" x2="12" y2="22"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>;
    case "compress":   return <svg {...props}><polyline points="4 14 10 14 10 20"/><polyline points="20 10 14 10 14 4"/><line x1="10" y1="14" x2="3" y2="21"/><line x1="21" y1="3" x2="14" y2="10"/></svg>;
    case "gauge":      return <svg {...props}><path d="M12 2a10 10 0 1 0 10 10"/><path d="M12 12l3-4"/><circle cx="12" cy="12" r="1" fill={color}/></svg>;
    case "flask":      return <svg {...props}><path d="M9 3h6"/><path d="M10 3v5L6.5 14A4 4 0 0 0 10 20h4a4 4 0 0 0 3.5-6L14 8V3"/></svg>;
    case "cal":        return <svg {...props}><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>;
    case "wrench":     return <svg {...props}><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>;
    case "swap":       return <svg {...props}><polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></svg>;
    case "calcheck":   return <svg {...props}><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/><polyline points="9 16 11 18 15 14"/></svg>;
    default:           return null;
  }
}

// ─── SPARKLINE ────────────────────────────────────────────────────────────────
function Sparkline({ data, color, filled }) {
  const w = 80, h = 34;
  const min = Math.min(...data), max = Math.max(...data);
  const range = max - min || 1;
  const pts = data.map((p, i) => ({
    x: (i / (data.length - 1)) * w,
    y: h - 4 - ((p - min) / range) * (h - 8),
  }));
  const polyPts = pts.map(p => `${p.x},${p.y}`).join(" ");
  const areaPath = `M${pts[0].x},${h} ` + pts.map(p => `L${p.x},${p.y}`).join(" ") + ` L${pts[pts.length-1].x},${h} Z`;
  return (
    <svg width={w} height={h} style={{ flexShrink: 0, overflow: "visible" }}>
      {filled && <path d={areaPath} fill={color} opacity="0.12" />}
      <polyline points={polyPts} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={pts[pts.length-1].x} cy={pts[pts.length-1].y} r="3" fill={color} />
    </svg>
  );
}

// ─── DONUT (interactive: hover segments to highlight + update center) ──────────
function Donut({ data, total, centerText, centerSub, size = 150, thickness = 18 }) {
  const [hovered, setHovered] = useState(null);
  const r = (size / 2) - thickness;
  const cx = size / 2, cy = size / 2;
  const circ = 2 * Math.PI * r;
  let cum = 0;
  const slices = data.map(d => {
    const pct = d.value / total;
    const s = { ...d, pct, offset: cum };
    cum += pct;
    return s;
  });

  const displayText = hovered !== null ? (data[hovered].pct ?? `${data[hovered].value}`) : centerText;
  const displaySub  = hovered !== null ? data[hovered].name : centerSub;

  return (
    <svg width={size} height={size} style={{ cursor: "pointer" }}>
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="#eef0f5" strokeWidth={thickness} />
      {slices.map((s, i) => {
        const isHov = hovered === i;
        const thick = isHov ? thickness + 4 : thickness;
        const dim   = hovered !== null && !isHov;
        return (
          <circle
            key={i} cx={cx} cy={cy} r={r} fill="none"
            stroke={s.color}
            strokeWidth={thick}
            strokeDasharray={`${s.pct * circ} ${circ}`}
            strokeDashoffset={-s.offset * circ}
            transform={`rotate(-90 ${cx} ${cy})`}
            strokeLinecap="butt"
            opacity={dim ? 0.3 : 1}
            style={{ transition: "all 0.18s ease", cursor: "pointer" }}
            onMouseEnter={() => setHovered(i)}
            onMouseLeave={() => setHovered(null)}
          />
        );
      })}
      <text x={cx} y={cy - 7} textAnchor="middle" fontSize="15" fontWeight="700" fill={T.text.primary} fontFamily="Inter, system-ui, sans-serif"
        style={{ transition: "all 0.15s" }}>
        {displayText}
      </text>
      <text x={cx} y={cy + 10} textAnchor="middle" fontSize="10" fill={hovered !== null ? slices[hovered]?.color : T.text.muted}
        fontFamily="Inter, system-ui, sans-serif" style={{ transition: "all 0.15s" }}>
        {displaySub}
      </text>
    </svg>
  );
}

// ─── RESPONSIVE CSS ───────────────────────────────────────────────────────────
const DASHBOARD_CSS = `
  .pd-content { padding: 12px 14px; display: flex; flex-direction: column; gap: 12px; }
  @media (min-width: 768px) { .pd-content { padding: 16px 24px; gap: 14px; } }

  /* KPI row */
  .pd-grid-kpi { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
  @media (min-width: 480px)  { .pd-grid-kpi { grid-template-columns: repeat(3, 1fr); } }
  @media (min-width: 1024px) { .pd-grid-kpi { grid-template-columns: repeat(6, 1fr); gap: 10px; } }

  /* Charts row */
  .pd-grid-charts { display: grid; grid-template-columns: 1fr; gap: 10px; }
  @media (min-width: 640px)  { .pd-grid-charts { grid-template-columns: repeat(2, 1fr); } }
  @media (min-width: 1280px) { .pd-grid-charts { grid-template-columns: 1fr 1fr 2fr 1fr 1fr; } }

  /* Quality card spans full row on tablet, auto on desktop */
  @media (min-width: 640px) and (max-width: 1279px) { .pd-quality-card { grid-column: span 2; } }

  /* Bottom row */
  .pd-grid-bottom { display: grid; grid-template-columns: 1fr; gap: 10px; }
  @media (min-width: 1024px) { .pd-grid-bottom { grid-template-columns: 3fr 1fr; } }

  /* Critical params inner grid */
  .pd-grid-params { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
  @media (min-width: 480px)  { .pd-grid-params { grid-template-columns: repeat(3, 1fr); } }
  @media (min-width: 1280px) { .pd-grid-params { grid-template-columns: repeat(6, 1fr); gap: 10px; } }

  /* KPI card value — shrink on very small screens */
  .pd-kpi-value { font-size: 22px; }
  @media (min-width: 480px) { .pd-kpi-value { font-size: 26px; } }

  /* Sparkline: hide on smallest screens */
  .pd-sparkline-wrap { display: none; }
  @media (min-width: 360px) { .pd-sparkline-wrap { display: flex; } }

  /* Live badge: icon+text on wider, dot only on mobile */
  .pd-live-text { display: none; }
  @media (min-width: 480px) { .pd-live-text { display: inline; } }

  /* Pharma header title truncation */
  .pd-header-title { font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 180px; }
  @media (min-width: 480px) { .pd-header-title { font-size: 15px; max-width: none; } }
`;

// ─── CARD SHELL (hover lift) ───────────────────────────────────────────────────
function Card({ children, style = {}, alert, className = "" }) {
  const [hov, setHov] = useState(false);
  return (
    <div
      className={className}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        background: T.surface,
        border: `1px solid ${alert ? T.borderAlert : hov ? "#c8ccd8" : T.border}`,
        borderRadius: 12,
        boxShadow: hov
          ? "0 8px 28px rgba(0,0,0,0.10), 0 2px 6px rgba(0,0,0,0.06)"
          : "0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.03)",
        transform: hov ? "translateY(-2px)" : "translateY(0)",
        transition: "all 0.2s ease",
        ...style,
      }}
    >
      {children}
    </div>
  );
}

// ─── SECTION TITLE ────────────────────────────────────────────────────────────
function SectionTitle({ children, action }) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
      <span style={{ fontSize: 13, fontWeight: 700, color: T.text.primary, letterSpacing: "0.01em" }}>{children}</span>
      {action && <span style={{ fontSize: 11, color: T.blue.text, fontWeight: 600, cursor: "pointer" }}>{action}</span>}
    </div>
  );
}

// ─── RECHARTS TOOLTIP ─────────────────────────────────────────────────────────
function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: "#fff", border: `1px solid ${T.border}`, borderRadius: 8, padding: "8px 12px", fontSize: 12, boxShadow: "0 4px 16px rgba(0,0,0,0.12)" }}>
      <div style={{ fontWeight: 700, color: T.text.primary, marginBottom: 5 }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ display: "flex", alignItems: "center", gap: 6, color: T.text.secondary, marginBottom: 2 }}>
          <span style={{ width: 8, height: 8, borderRadius: 2, background: p.fill, display: "inline-block" }} />
          {p.name}: <b style={{ color: T.text.primary, marginLeft: 2 }}>{p.value}</b>
        </div>
      ))}
    </div>
  );
}

// ─── QUALITY BAR CHART (Recharts — fully interactive) ────────────────────────
function QualityBarChart({ data }) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} barCategoryGap="22%" barGap={3} margin={{ top: 4, right: 8, left: -12, bottom: 40 }}>
        <XAxis
          dataKey="test"
          interval={0}
          tick={{ fontSize: 10, fill: T.text.muted, fontFamily: "Inter, system-ui, sans-serif", angle: -30, textAnchor: "end", dy: 6 }}
          axisLine={false}
          tickLine={false}
          height={55}
        />
        <YAxis
          domain={[0, 200]}
          ticks={[0, 50, 100, 150, 200]}
          tick={{ fontSize: 10, fill: T.text.muted, fontFamily: "Inter, system-ui, sans-serif" }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(0,0,0,0.04)", radius: [4, 4, 0, 0] }} />
        <Legend
          iconType="square"
          iconSize={9}
          wrapperStyle={{ fontSize: 11, fontFamily: "Inter, system-ui, sans-serif", paddingTop: 4 }}
        />
        <Bar dataKey="pass" name="Pass" fill="#16a34a" radius={[4, 4, 0, 0]} />
        <Bar dataKey="fail" name="Fail" fill="#dc2626" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

// ─── PARAM GAUGE ARC ─────────────────────────────────────────────────────────
function ParamGauge({ pct, color }) {
  const r = 22, cx = 32, cy = 30, stroke = 5;
  const startAngle = -200, sweepDeg = 220;
  const toRad = (d) => (d * Math.PI) / 180;
  const arc = (angle) => {
    const rad = toRad(angle);
    return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
  };
  const s = arc(startAngle);
  const eAll = arc(startAngle + sweepDeg);
  const eFill = arc(startAngle + sweepDeg * pct);
  const lg = sweepDeg > 180 ? 1 : 0;
  const lgFill = sweepDeg * pct > 180 ? 1 : 0;
  return (
    <svg width={64} height={38} style={{ marginBottom: 4, overflow: "visible" }}>
      <path d={`M ${s.x} ${s.y} A ${r} ${r} 0 ${lg} 1 ${eAll.x} ${eAll.y}`}
        fill="none" stroke="#eef0f5" strokeWidth={stroke} strokeLinecap="round" />
      {pct > 0 && (
        <path d={`M ${s.x} ${s.y} A ${r} ${r} 0 ${lgFill} 1 ${eFill.x} ${eFill.y}`}
          fill="none" stroke={color} strokeWidth={stroke} strokeLinecap="round" opacity="0.85" />
      )}
      <circle cx={eFill.x} cy={eFill.y} r="3" fill={color} />
    </svg>
  );
}

// ─── MAIN ─────────────────────────────────────────────────────────────────────
export default function PharmaPlantDashboard() {
  const batchTotal = BATCH_STATUS.reduce((s, d) => s + d.value, 0);

  return (
    <div style={{ fontFamily: "Inter, system-ui, -apple-system, sans-serif", background: T.bg, minHeight: "100%" }}>
      <style>{DASHBOARD_CSS}</style>

      {/* ── STICKY HEADER ──────────────────────────────────────────────────── */}
      <div style={{
        position: "sticky", top: 0, zIndex: 20,
        background: "#fff", borderBottom: `1px solid ${T.border}`,
        padding: "0 16px", display: "flex", alignItems: "center",
        justifyContent: "space-between", height: 52, flexShrink: 0,
        boxShadow: "0 2px 8px rgba(0,0,0,0.06)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
          <div style={{ width: 32, height: 32, flexShrink: 0, borderRadius: 8, background: "linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%)", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke={T.blue.solid} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="m10.5 20.5 10-10a4.95 4.95 0 1 0-7-7l-10 10a4.95 4.95 0 1 0 7 7Z"/>
              <path d="M8.5 8.5 16 16"/>
            </svg>
          </div>
          <div style={{ minWidth: 0 }}>
            <div className="pd-header-title" style={{ fontWeight: 800, color: T.text.primary, letterSpacing: "-0.01em" }}>Pharma Manufacturing Plant</div>
            <div style={{ fontSize: 10.5, color: T.text.muted, marginTop: 1 }}>Operations Overview</div>
          </div>
        </div>
        <div style={{ flexShrink: 0, marginLeft: 8 }}>
          <div style={{ fontSize: 10.5, color: T.green.text, background: T.green.light, padding: "4px 10px", borderRadius: 20, border: `1px solid ${T.green.solid}30`, fontWeight: 600, whiteSpace: "nowrap" }}>
            ●<span className="pd-live-text"> Live · Updated just now</span>
          </div>
        </div>
      </div>

      <div className="pd-content">

        {/* ── ROW 1: KPI CARDS ───────────────────────────────────────────────── */}
        <div className="pd-grid-kpi">
          {KPI_CARDS.map((k) => (
            <Card key={k.id} alert={k.isAlert} style={{ padding: "14px 16px 13px", display: "flex", flexDirection: "column", gap: 0, position: "relative", overflow: "hidden", cursor: "pointer" }}>
              <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 3, borderRadius: "12px 12px 0 0", background: k.gradientA }} />
              <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginTop: 4, marginBottom: 10 }}>
                <span style={{ fontSize: 11, color: T.text.secondary, fontWeight: 500, lineHeight: 1.4, maxWidth: "52%" }}>{k.label}</span>
                <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
                  <div style={{ width: 26, height: 26, borderRadius: 7, background: k.iconBg, display: "flex", alignItems: "center", justifyContent: "center" }}>
                    <Icon type={k.iconType} size={13} color={k.iconColor} />
                  </div>
                  <div className="pd-sparkline-wrap"><Sparkline data={k.sparkData} color={k.gradientA} filled /></div>
                </div>
              </div>
              <div style={{ marginBottom: 9 }}>
                <span className="pd-kpi-value" style={{ fontWeight: 800, color: T.text.primary, letterSpacing: "-0.03em" }}>{k.value}</span>
                {k.unit && <span style={{ fontSize: 11, color: T.text.muted, marginLeft: 4, fontWeight: 500 }}>{k.unit}</span>}
              </div>
              <div style={{ height: 1, background: T.border, marginBottom: 9 }} />
              <div style={{ fontSize: 11, color: k.deltaPositive ? T.green.text : T.orange.text, fontWeight: 600, display: "flex", alignItems: "center", gap: 3 }}>
                <span style={{ fontSize: 13 }}>{k.deltaPositive ? "↑" : "⚠"}</span>
                <span>{k.delta}</span>
              </div>
            </Card>
          ))}
        </div>

        {/* ── ROW 2: CHARTS ──────────────────────────────────────────────────── */}
        <div className="pd-grid-charts">

          {/* Production by Area */}
          <Card style={{ padding: "16px 18px" }}>
            <SectionTitle>Production by Area</SectionTitle>
            <div style={{ display: "flex", justifyContent: "center", marginBottom: 12 }}>
              <Donut data={PRODUCTION_BY_AREA} total={100} centerText="1.25M" centerSub="Units" size={148} thickness={19} />
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
              {PRODUCTION_BY_AREA.map((d) => (
                <DonutLegendRow key={d.name} d={d} />
              ))}
            </div>
          </Card>

          {/* Batch Status */}
          <Card style={{ padding: "16px 18px" }}>
            <SectionTitle>Batch Status</SectionTitle>
            <div style={{ display: "flex", justifyContent: "center", marginBottom: 12 }}>
              <Donut data={BATCH_STATUS} total={batchTotal} centerText={batchTotal} centerSub="Total Batches" size={148} thickness={19} />
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {BATCH_STATUS.map((d) => (
                <BatchLegendRow key={d.name} d={d} />
              ))}
            </div>
          </Card>

          {/* Quality by Test Type — Recharts */}
          <Card className="pd-quality-card" style={{ padding: "16px 18px" }}>
            <SectionTitle>Quality by Test Type</SectionTitle>
            <QualityBarChart data={QUALITY_BY_TEST} />
          </Card>

          {/* Inventory Summary */}
          <Card style={{ padding: "16px 18px" }}>
            <SectionTitle>Inventory Summary</SectionTitle>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {INVENTORY.map((inv) => (
                <InventoryRow key={inv.label} inv={inv} />
              ))}
            </div>
          </Card>

          {/* Upcoming Activities */}
          <Card style={{ padding: "16px 18px" }}>
            <SectionTitle action="View All →">Upcoming Activities</SectionTitle>
            <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
              {UPCOMING_ACTIVITIES.map((a, i) => (
                <ActivityRow key={a.label} a={a} last={i === UPCOMING_ACTIVITIES.length - 1} />
              ))}
            </div>
          </Card>
        </div>

        {/* ── ROW 3: CRITICAL PARAMS + ALERTS ────────────────────────────────── */}
        <div className="pd-grid-bottom">

          {/* Critical Parameters */}
          <Card style={{ padding: "16px 20px" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ fontSize: 13, fontWeight: 700, color: T.text.primary }}>Critical Parameters</span>
                <span style={{ fontSize: 10, fontWeight: 600, color: T.green.text, background: T.green.light, padding: "2px 8px", borderRadius: 10 }}>● Live</span>
              </div>
            </div>
            <div className="pd-grid-params">
              {CRITICAL_PARAMS.map((p) => (
                <ParamCard key={p.label} p={p} />
              ))}
            </div>
          </Card>

          {/* Alerts Summary */}
          <Card style={{ padding: "16px 18px" }}>
            <SectionTitle action="View All →">Alerts Summary</SectionTitle>
            <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 16 }}>
              {[
                { label: "High",   count: 1, color: T.red.text,   bg: T.red.light,   fill: "#dc2626" },
                { label: "Medium", count: 2, color: T.amber.text, bg: T.amber.light, fill: "#d97706" },
                { label: "Low",    count: 3, color: T.blue.text,  bg: T.blue.light,  fill: "#2563eb" },
              ].map(a => (
                <AlertRow key={a.label} a={a} />
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

// ─── SUB-ROW COMPONENTS (each has its own hover state) ───────────────────────

function DonutLegendRow({ d }) {
  const [hov, setHov] = useState(false);
  return (
    <div
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "3px 6px", borderRadius: 6, cursor: "default",
        background: hov ? `${d.color}12` : "transparent",
        transition: "background 0.15s",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
        <span style={{ width: 8, height: 8, borderRadius: "50%", background: d.color, display: "inline-block", flexShrink: 0 }} />
        <span style={{ fontSize: 11, color: T.text.secondary }}>{d.name}</span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <div style={{ width: 36, height: 4, borderRadius: 4, background: "#eef0f5", overflow: "hidden" }}>
          <div style={{ width: `${d.value * 3}%`, height: "100%", background: d.color, borderRadius: 4, transition: "width 0.3s" }} />
        </div>
        <span style={{ fontSize: 11, fontWeight: 700, color: T.text.primary, minWidth: 26, textAlign: "right" }}>{d.value}%</span>
      </div>
    </div>
  );
}

function BatchLegendRow({ d }) {
  const [hov, setHov] = useState(false);
  return (
    <div
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "3px 6px", borderRadius: 6, cursor: "default",
        background: hov ? `${d.color}12` : "transparent",
        transition: "background 0.15s",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
        <span style={{ width: 8, height: 8, borderRadius: "50%", background: d.color, display: "inline-block", flexShrink: 0 }} />
        <span style={{ fontSize: 11, color: T.text.secondary }}>{d.name}</span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <span style={{ fontSize: 11, fontWeight: 700, color: T.text.primary }}>{d.value}</span>
        <span style={{ fontSize: 10, color: T.text.muted, background: hov ? `${d.color}20` : "#f4f5f8", padding: "1px 5px", borderRadius: 4, transition: "background 0.15s" }}>{d.pct}</span>
      </div>
    </div>
  );
}

function InventoryRow({ inv }) {
  const [hov, setHov] = useState(false);
  return (
    <div
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        padding: "6px 8px", borderRadius: 8, cursor: "default",
        background: hov ? `${inv.iconColor}0a` : "transparent",
        border: `1px solid ${hov ? `${inv.iconColor}25` : "transparent"}`,
        transition: "all 0.15s",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 5 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{ width: 28, height: 28, borderRadius: 7, background: inv.iconBg, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, transform: hov ? "scale(1.1)" : "scale(1)", transition: "transform 0.15s" }}>
            <Icon type={inv.iconType} size={13} color={inv.iconColor} />
          </div>
          <span style={{ fontSize: 11.5, color: T.text.secondary }}>{inv.label}</span>
        </div>
        <div>
          <span style={{ fontSize: 15, fontWeight: 700, color: T.text.primary }}>{inv.value}</span>
          <span style={{ fontSize: 10, color: T.text.muted, marginLeft: 3 }}>{inv.unit}</span>
        </div>
      </div>
      <div style={{ height: 4, borderRadius: 4, background: "#eef0f5", overflow: "hidden" }}>
        <div style={{ width: `${inv.bar * 100}%`, height: "100%", background: inv.iconColor, borderRadius: 4, opacity: hov ? 1 : 0.7, transition: "all 0.3s" }} />
      </div>
    </div>
  );
}

function ActivityRow({ a, last }) {
  const [hov, setHov] = useState(false);
  return (
    <div
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        display: "flex", alignItems: "center", gap: 10,
        padding: "9px 6px",
        borderBottom: last ? "none" : `1px solid ${T.border}`,
        borderRadius: 8,
        background: hov ? `${a.iconColor}08` : "transparent",
        cursor: "pointer",
        transition: "background 0.15s",
      }}
    >
      <div style={{ width: 30, height: 30, borderRadius: 8, background: a.iconBg, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, transform: hov ? "scale(1.08)" : "scale(1)", transition: "transform 0.15s" }}>
        <Icon type={a.iconType} size={14} color={a.iconColor} />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 11.5, fontWeight: 600, color: hov ? T.text.primary : T.text.primary, marginBottom: 2, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{a.label}</div>
        <div style={{ fontSize: 10.5, color: a.iconColor, fontWeight: 600 }}>{a.note}</div>
      </div>
      {hov && <span style={{ fontSize: 10, color: a.iconColor, fontWeight: 700, flexShrink: 0 }}>→</span>}
    </div>
  );
}

function ParamCard({ p }) {
  const [hov, setHov] = useState(false);
  return (
    <div
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        background: hov
          ? `linear-gradient(160deg, ${p.iconBg}99 0%, #f8f9ff 60%)`
          : `linear-gradient(160deg, ${p.iconBg}55 0%, #ffffff 60%)`,
        border: `1px solid ${hov ? `${p.iconColor}50` : `${p.iconColor}30`}`,
        borderRadius: 12,
        padding: "14px 12px 12px",
        display: "flex", flexDirection: "column", alignItems: "center", gap: 0,
        position: "relative", overflow: "hidden",
        transform: hov ? "translateY(-2px)" : "translateY(0)",
        boxShadow: hov ? `0 6px 20px ${p.iconColor}25` : "none",
        transition: "all 0.2s ease",
        cursor: "default",
      }}
    >
      <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 3, borderRadius: "12px 0 0 12px", background: p.iconColor }} />
      <ParamGauge color={p.iconColor} pct={p.gaugePct} />
      <div style={{ display: "flex", alignItems: "center", gap: 5, marginBottom: 6, width: "100%" }}>
        <div style={{ width: 22, height: 22, borderRadius: 5, background: p.iconBg, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
          <Icon type={p.iconType} size={11} color={p.iconColor} />
        </div>
        <span style={{ fontSize: 9.5, color: T.text.muted, lineHeight: 1.3, fontWeight: 500 }}>{p.label}</span>
      </div>
      <div style={{ width: "100%", marginBottom: 8 }}>
        <span style={{ fontSize: 22, fontWeight: 800, color: T.text.primary, letterSpacing: "-0.02em" }}>{p.value}</span>
        <span style={{ fontSize: 10, color: T.text.muted, marginLeft: 2 }}>{p.unit}</span>
      </div>
      <div style={{ width: "100%", display: "flex", alignItems: "center", gap: 4, background: p.iconBg, borderRadius: 6, padding: "3px 7px" }}>
        <span style={{ width: 5, height: 5, borderRadius: "50%", background: p.iconColor, display: "inline-block", flexShrink: 0 }} />
        <span style={{ fontSize: 10, color: p.iconColor, fontWeight: 700 }}>{p.status}</span>
      </div>
    </div>
  );
}

function AlertRow({ a }) {
  const [hov, setHov] = useState(false);
  return (
    <div
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        background: hov ? `${a.fill}22` : a.bg,
        borderRadius: 8, padding: "9px 12px",
        border: `1px solid ${hov ? `${a.fill}40` : "transparent"}`,
        cursor: "pointer",
        transform: hov ? "translateX(2px)" : "translateX(0)",
        transition: "all 0.15s ease",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill={a.fill}><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13" stroke="white" strokeWidth="2" strokeLinecap="round"/><circle cx="12" cy="17" r="1" fill="white"/></svg>
        <span style={{ fontSize: 12, fontWeight: 600, color: a.color }}>{a.label}</span>
      </div>
      <span style={{ fontSize: 18, fontWeight: 800, color: a.fill }}>{a.count}</span>
    </div>
  );
}
