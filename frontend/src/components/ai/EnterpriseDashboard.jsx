import React, { useState } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  LineChart, Line, Legend,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
} from 'recharts';
import { useProductionData } from '../../hooks/useProductionData';
import { useQualityData } from '../../hooks/useQualityData';

// ─── DESIGN TOKENS ───────────────────────────────────────────────────────────
const T = {
  bg: '#f0f2f7', surface: '#ffffff', border: '#e8eaf0', borderAlert: '#fcd9b6',
  text: { primary: '#0f1117', secondary: '#5a6072', muted: '#9da3b4' },
  green:  { solid: '#16a34a', light: '#dcfce7', text: '#15803d' },
  red:    { solid: '#dc2626', light: '#fee2e2', text: '#b91c1c' },
  amber:  { solid: '#d97706', light: '#fef3c7', text: '#b45309' },
  blue:   { solid: '#2563eb', light: '#dbeafe', text: '#1d4ed8' },
  prod:   { solid: '#6366f1', light: '#ede9fe', text: '#4f46e5', gradA: '#6366f1', gradB: '#818cf8' },
  pkg:    { solid: '#0ea5e9', light: '#e0f2fe', text: '#0369a1', gradA: '#0ea5e9', gradB: '#38bdf8' },
  qlt:    { solid: '#10b981', light: '#d1fae5', text: '#059669', gradA: '#10b981', gradB: '#34d399' },
  log:    { solid: '#f59e0b', light: '#fef3c7', text: '#b45309', gradA: '#f59e0b', gradB: '#fbbf24' },
};

// ─── HELPERS ─────────────────────────────────────────────────────────────────
function fmtUnits(n) {
  if (!n || n === 0) return '0';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000)     return `${(n / 1_000).toFixed(1)}K`;
  return String(Math.round(n));
}

function safeSpark(arr, key, fallback) {
  const vals = arr.map(d => d?.[key] ?? 0);
  return vals.filter(v => v > 0).length >= 2 ? vals : fallback;
}

// ─── DATA BUILDERS ────────────────────────────────────────────────────────────

function buildKpiCards(p, pY, q, qY, pLast9, qLast9) {
  const totalProduced = p.totalProduced ?? 0;
  const totalTarget   = p.totalTarget   ?? 1;
  const outputDelta   = totalTarget > 0 ? ((totalProduced / totalTarget - 1) * 100) : 0;

  const capPct   = p.capacityPct ?? 0;
  const capDelta = capPct - (pY.capacityPct ?? capPct);

  const qpr      = q.qualityPassRate ?? 0;
  const qprDelta = qpr - (qY.qualityPassRate ?? qpr);

  const ncr      = q.openNcrs ?? 0;
  const ncrDelta = ncr - (qY.openNcrs ?? ncr);

  return [
    {
      id: 'prod-out', domain: 'Production', label: "Today's Output",
      value: fmtUnits(totalProduced), unit: 'units',
      delta: `${outputDelta >= 0 ? '+' : ''}${outputDelta.toFixed(1)}% vs target`,
      pos: outputDelta >= 0,
      spark: safeSpark(pLast9, 'totalProduced', [8,12,9,15,11,14,18,16,20]),
      ...T.prod, iconBg: T.prod.light, iconColor: T.prod.solid, iconType: 'factory',
    },
    {
      id: 'prod-cap', domain: 'Production', label: 'Capacity Utilization',
      value: `${capPct.toFixed(1)}%`, unit: null,
      delta: `${capDelta >= 0 ? '+' : ''}${capDelta.toFixed(1)}% vs yesterday`,
      pos: capDelta >= 0,
      spark: safeSpark(pLast9, 'capacityPct', [55,60,58,62,59,65,63,67,68]),
      ...T.prod, iconBg: T.prod.light, iconColor: T.prod.solid, iconType: 'gauge',
    },
    {
      id: 'pkg-eff', domain: 'Packaging', label: 'Line Efficiency',
      value: '94.2%', unit: null, delta: '+2.1% vs yesterday', pos: true,
      spark: [88,90,89,92,91,93,92,94,94],
      ...T.pkg, iconBg: T.pkg.light, iconColor: T.pkg.solid, iconType: 'box',
    },
    {
      id: 'pkg-pkg', domain: 'Packaging', label: 'Packages Today',
      value: '45.2K', unit: null, delta: '+6.8% vs target', pos: true,
      spark: [38,40,39,42,41,43,44,45,45],
      ...T.pkg, iconBg: T.pkg.light, iconColor: T.pkg.solid, iconType: 'package',
    },
    {
      id: 'qlt-pas', domain: 'Quality', label: 'Quality Pass Rate',
      value: `${qpr.toFixed(1)}%`, unit: null,
      delta: `${qprDelta >= 0 ? '+' : ''}${qprDelta.toFixed(1)}% vs yesterday`,
      pos: qprDelta >= 0,
      spark: safeSpark(qLast9, 'qualityPassRate', [96,97,96,98,97,99,98,98,99]),
      ...T.qlt, iconBg: T.qlt.light, iconColor: T.qlt.solid, iconType: 'shield',
    },
    {
      id: 'qlt-ncr', domain: 'Quality', label: 'Open NCRs',
      value: String(ncr), unit: null,
      delta: ncrDelta === 0
        ? 'No change vs yesterday'
        : `${ncrDelta > 0 ? '+' : ''}${ncrDelta} vs yesterday`,
      pos: ncrDelta <= 0,
      spark: safeSpark(qLast9, 'openNcrs', [12,10,9,8,9,7,8,7,7]),
      ...T.qlt, iconBg: T.qlt.light, iconColor: T.qlt.solid, iconType: 'alertTri', isAlert: ncr > 5,
    },
    {
      id: 'log-otd', domain: 'Logistics', label: 'On-Time Delivery',
      value: '92%', unit: null, delta: '+3.4% vs last month', pos: true,
      spark: [85,87,88,89,90,91,90,92,92],
      ...T.log, iconBg: T.log.light, iconColor: T.log.solid, iconType: 'truck',
    },
    {
      id: 'log-int', domain: 'Logistics', label: 'In Transit',
      value: '15', unit: null, delta: '2 delayed', pos: false,
      spark: [10,12,11,13,14,13,15,15,15],
      ...T.log, iconBg: T.log.light, iconColor: T.log.solid, iconType: 'truck', isAlert: true,
    },
  ];
}

const DAY_LABELS   = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const PKG_WEEKLY_D = [91, 92, 90, 93, 94, 92, 94];
const LOG_WEEKLY_D = [89, 91, 88, 90, 92, 90, 88];

function buildWeeklyTrend(pLast9, qLast9) {
  const pSlice = pLast9.slice(-7);
  const qSlice = qLast9.slice(-7);
  return Array.from({ length: 7 }, (_, i) => ({
    day:        DAY_LABELS[i],
    Production: Math.round(pSlice[i]?.capacityPct      ?? (82 + i)),
    Packaging:  PKG_WEEKLY_D[i],
    Quality:    Math.round(qSlice[i]?.qualityPassRate  ?? (96 + (i % 3))),
    Logistics:  LOG_WEEKLY_D[i],
  }));
}

function buildPerfVsTarget(p, q) {
  return [
    { domain: 'Production', actual: Math.round(p.capacityPct     ?? 92), target: 85 },
    { domain: 'Packaging',  actual: 94,                                   target: 90 },
    { domain: 'Quality',    actual: Math.round(q.qualityPassRate  ?? 99), target: 95 },
    { domain: 'Logistics',  actual: 88,                                   target: 90 },
  ];
}

function buildDomainStatus(p, q) {
  const inProgress  = p.batches?.in_progress ?? 0;
  const totalB      = (p.batches?.in_progress ?? 0) + (p.batches?.completed ?? 0)
                    + (p.batches?.pending ?? 0)      + (p.batches?.on_hold ?? 0);
  const prodHigh    = p.alerts?.high ?? 0;
  const prodHealth  = prodHigh === 0 ? 'On Track' : prodHigh <= 2 ? 'Attention' : 'Critical';
  const prodHc      = prodHealth === 'On Track' ? T.green.solid : prodHealth === 'Attention' ? T.amber.solid : T.red.solid;
  const prodHb      = prodHealth === 'On Track' ? T.green.light : prodHealth === 'Attention' ? T.amber.light : T.red.light;

  const capaCrit    = q.capaCritical       ?? 0;
  const devCrit     = q.deviationCritical  ?? 0;
  const openNcrs    = q.openNcrs           ?? 0;
  const qualHealth  = (capaCrit > 0 || devCrit > 0) ? 'Attention' : 'On Track';
  const qualHc      = qualHealth === 'On Track' ? T.green.solid : T.amber.solid;
  const qualHb      = qualHealth === 'On Track' ? T.green.light : T.amber.light;

  return [
    {
      icon: '🏭', label: 'Production', color: T.prod.solid, light: T.prod.light,
      health: prodHealth, hc: prodHc, hb: prodHb,
      detail: `${inProgress} active batch${inProgress !== 1 ? 'es' : ''} · ${totalB > 0 ? '3/3' : '0/3'} shifts running`,
    },
    {
      icon: '📦', label: 'Packaging', color: T.pkg.solid, light: T.pkg.light,
      health: 'On Track', hc: T.green.solid, hb: T.green.light,
      detail: '2/4 lines running · Line C under maintenance',
    },
    {
      icon: '📋', label: 'Quality', color: T.qlt.solid, light: T.qlt.light,
      health: qualHealth, hc: qualHc, hb: qualHb,
      detail: `${capaCrit > 0 ? `${capaCrit} critical CAPA pending` : 'No critical CAPAs'} · ${openNcrs} open NCR${openNcrs !== 1 ? 's' : ''}`,
    },
    {
      icon: '🚛', label: 'Logistics', color: T.log.solid, light: T.log.light,
      health: 'Attention', hc: T.amber.solid, hb: T.amber.light,
      detail: '2 shipments delayed · 23 pending dispatch',
    },
  ];
}

function buildAlerts(p, q) {
  const alerts       = [];
  const openIssues   = p.openIssues    ?? 0;
  const capaCrit     = q.capaCritical  ?? 0;
  const upcomingAuds = q.upcomingAudits ?? [];

  if (openIssues > 0) {
    alerts.push({
      icon: '🏭', domain: 'Production',
      msg: `${openIssues} open production issue${openIssues !== 1 ? 's' : ''} require attention`,
      priority: 'High', pc: T.red.solid, pb: T.red.light,
    });
  }
  if (capaCrit > 0) {
    alerts.push({
      icon: '📋', domain: 'Quality',
      msg: `${capaCrit} critical CAPA ${capaCrit === 1 ? 'is' : 'are'} overdue for review`,
      priority: 'High', pc: T.red.solid, pb: T.red.light,
    });
  }

  // Show the most urgent upcoming quality audit from real data
  const urgentAudit = upcomingAuds.find(a => a.priority === 'High')
                   ?? upcomingAuds.find(a => a.priority === 'Medium')
                   ?? upcomingAuds[0];
  if (urgentAudit) {
    const auditColors = urgentAudit.priority === 'High'   ? { pc: T.red.solid,   pb: T.red.light   }
                      : urgentAudit.priority === 'Medium' ? { pc: T.amber.solid, pb: T.amber.light }
                      :                                     { pc: T.blue.solid,  pb: T.blue.light  };
    alerts.push({
      icon: '📋', domain: 'Quality',
      msg: `${urgentAudit.name} scheduled ${urgentAudit.date}`,
      priority: urgentAudit.priority ?? 'Low',
      ...auditColors,
    });
  }

  alerts.push(
    { icon: '🚛', domain: 'Logistics', msg: 'SHP-004 & SHP-005 delayed — Bangalore & Chennai', priority: 'Medium', pc: T.amber.solid, pb: T.amber.light },
    { icon: '📦', domain: 'Packaging', msg: 'Line C maintenance expected complete by 4 PM',    priority: 'Low',    pc: T.blue.solid,  pb: T.blue.light  },
  );
  return alerts;
}

function buildUpcoming(p, q) {
  const calibDue     = p.activities?.equipment_calibration_due    ?? 0;
  const maintDue     = p.activities?.preventive_maintenance_due   ?? 0;
  const upcomingAuds = q.upcomingAudits ?? [];
  const items        = [];

  if (calibDue > 0) {
    items.push({
      label: 'Equipment Calibration', note: `${calibDue} due today`,
      iconBg: T.blue.light, iconColor: T.blue.solid, urgency: 'high', domain: 'Production',
    });
  }
  if (maintDue > 0) {
    items.push({
      label: 'Preventive Maintenance', note: `${maintDue} due this week`,
      iconBg: T.green.light, iconColor: T.green.solid, urgency: 'med', domain: 'Production',
    });
  }

  const nextAudit = upcomingAuds[0];
  items.push({
    label: nextAudit?.name ?? 'CAPA Review Meeting',
    note:  nextAudit?.date ?? 'Today 3:00 PM',
    iconBg: T.red.light, iconColor: T.red.solid, urgency: 'high', domain: 'Quality',
  });

  items.push({
    label: 'Carrier Performance Review', note: 'Jun 25',
    iconBg: T.log.light, iconColor: T.log.solid, urgency: 'low', domain: 'Logistics',
  });

  return items.slice(0, 4);
}

function buildScorecard(p, q) {
  const capPct   = Math.round(p.capacityPct      ?? 92);
  const bsr      = Math.round(p.batchSuccessRate ?? 96);
  const onTime   = Math.round(p.onTimePct        ?? 88);
  const prodQPR  = Math.round(p.qualityPassRate  ?? 97);

  const qpr           = Math.round(q.qualityPassRate ?? 99);
  const auditScore    = Math.round(q.auditScore      ?? 92);
  const inspCoverage  = (q.totalInspected ?? 0) > 0
    ? Math.round((q.passCount / q.totalInspected) * 100)
    : 95;

  return [
    { metric: 'Efficiency',  Production: capPct,  Packaging: 94, Quality: qpr,          Logistics: 88 },
    { metric: 'Quality',     Production: prodQPR, Packaging: 91, Quality: qpr,          Logistics: 85 },
    { metric: 'Delivery',    Production: onTime,  Packaging: 90, Quality: auditScore,   Logistics: 92 },
    { metric: 'Capacity',    Production: capPct,  Packaging: 75, Quality: inspCoverage, Logistics: 78 },
    { metric: 'Compliance',  Production: bsr,     Packaging: 93, Quality: auditScore,   Logistics: 90 },
    { metric: 'Cost Index',  Production: 85,      Packaging: 88, Quality: 91,           Logistics: 82 },
  ];
}

function buildScorecardTiles(_p, _q, scorecard) {
  const avg = (domain) => {
    const vals = scorecard.map(r => r[domain]);
    return (vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(1);
  };
  const best = (domain) => {
    let maxVal = -Infinity, maxMetric = '';
    for (const row of scorecard) {
      if (row[domain] > maxVal) { maxVal = row[domain]; maxMetric = row.metric; }
    }
    return `${maxMetric} ${maxVal}%`;
  };
  return [
    { label: 'Production', color: T.prod.solid, light: T.prod.light, avg: avg('Production'), top: best('Production') },
    { label: 'Packaging',  color: T.pkg.solid,  light: T.pkg.light,  avg: '88.5',            top: 'Efficiency 94%'  },
    { label: 'Quality',    color: T.qlt.solid,  light: T.qlt.light,  avg: avg('Quality'),    top: best('Quality')   },
    { label: 'Logistics',  color: T.log.solid,  light: T.log.light,  avg: '85.8',            top: 'Delivery 92%'    },
  ];
}

// ─── PRODUCTION LINE BUILDER (existing) ──────────────────────────────────────
const PROD_LINE_BASE = [
  { key: 'granulation', label: 'Granulation', color: T.prod.solid, light: T.prod.light },
  { key: 'compression', label: 'Compression', color: T.pkg.solid,  light: T.pkg.light  },
  { key: 'coating',     label: 'Coating',     color: T.qlt.solid,  light: T.qlt.light  },
  { key: 'packaging',   label: 'Packaging',   color: T.log.solid,  light: T.log.light  },
];

function buildProdLines(prodData) {
  const areas    = prodData?.today?.areas    ?? {};
  const total    = prodData?.today?.totalProduced ?? 1;
  const maintDue = prodData?.today?.activities?.preventive_maintenance_due ?? 0;
  const onHold   = prodData?.today?.batches?.on_hold ?? 0;

  return PROD_LINE_BASE.map((l, i) => {
    const units = areas[l.key] ?? 0;
    const pct   = total > 0 ? ((units / total) * 100).toFixed(1) : '0.0';

    let status, statusColor, statusBg, dotColor;
    if (i === 2 && maintDue > 3) {
      status = 'Maintenance'; statusColor = T.amber.text; statusBg = T.amber.light; dotColor = T.amber.solid;
    } else if (i === 3 && onHold > 2) {
      status = 'On Hold'; statusColor = T.amber.text; statusBg = T.amber.light; dotColor = T.amber.solid;
    } else if (units > 0) {
      status = 'Running'; statusColor = T.green.text; statusBg = T.green.light; dotColor = T.green.solid;
    } else {
      status = 'Idle'; statusColor = T.text.secondary; statusBg = T.border; dotColor = T.text.muted;
    }

    return {
      ...l, status, statusColor, statusBg, dotColor,
      sub: `${pct}% of total output`,
      unitsFormatted: `${(units / 1000).toFixed(1)}K`,
    };
  });
}

// ─── DOMAIN LEGEND ────────────────────────────────────────────────────────────
const DOMAIN_LEGEND = [
  { label: 'Production', color: T.prod.solid },
  { label: 'Packaging',  color: T.pkg.solid  },
  { label: 'Quality',    color: T.qlt.solid  },
  { label: 'Logistics',  color: T.log.solid  },
];

const PERF_COLORS = [T.prod.solid, T.pkg.solid, T.qlt.solid, T.log.solid];

// ─── ICON SYSTEM ─────────────────────────────────────────────────────────────
function Icon({ type, size = 14, color = 'currentColor' }) {
  const p = { width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: color, strokeWidth: '2', strokeLinecap: 'round', strokeLinejoin: 'round' };
  switch (type) {
    case 'factory':  return <svg {...p}><path d="M2 20V8l5-3v4l5-3v4l5-3v16H2z"/><rect x="5" y="14" width="3" height="6"/><rect x="10" y="14" width="3" height="6"/></svg>;
    case 'box':      return <svg {...p}><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/></svg>;
    case 'shield':   return <svg {...p}><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/></svg>;
    case 'truck':    return <svg {...p}><rect x="1" y="3" width="15" height="13"/><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/></svg>;
    case 'package':  return <svg {...p}><line x1="16.5" y1="9.4" x2="7.5" y2="4.21"/><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>;
    case 'gauge':    return <svg {...p}><path d="M12 2a10 10 0 1 0 10 10"/><path d="M12 12l3-4"/><circle cx="12" cy="12" r="1" fill={color}/></svg>;
    case 'alertTri': return <svg width={size} height={size} viewBox="0 0 24 24" fill={color}><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13" stroke="white" strokeWidth="2" strokeLinecap="round"/><circle cx="12" cy="17" r="1" fill="white"/></svg>;
    default:         return null;
  }
}

// ─── SPARKLINE ────────────────────────────────────────────────────────────────
function Sparkline({ data, color }) {
  const w = 72, h = 30;
  const min = Math.min(...data), max = Math.max(...data), range = max - min || 1;
  const pts = data.map((p, i) => ({ x: (i / (data.length - 1)) * w, y: h - 4 - ((p - min) / range) * (h - 8) }));
  const area = `M${pts[0].x},${h} ` + pts.map(p => `L${p.x},${p.y}`).join(' ') + ` L${pts[pts.length-1].x},${h} Z`;
  return (
    <svg width={w} height={h} style={{ overflow: 'visible', flexShrink: 0 }}>
      <path d={area} fill={color} opacity="0.12" />
      <polyline points={pts.map(p => `${p.x},${p.y}`).join(' ')} fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={pts[pts.length-1].x} cy={pts[pts.length-1].y} r="3" fill={color} />
    </svg>
  );
}

// ─── CARD ────────────────────────────────────────────────────────────────────
function Card({ children, style = {}, alert }) {
  const [hov, setHov] = useState(false);
  return (
    <div
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        background: T.surface, borderRadius: 12,
        border: `1px solid ${alert ? T.borderAlert : hov ? '#c8ccd8' : T.border}`,
        boxShadow: hov ? '0 8px 28px rgba(0,0,0,0.10),0 2px 6px rgba(0,0,0,0.06)' : '0 1px 3px rgba(0,0,0,0.04)',
        transform: hov ? 'translateY(-2px)' : 'none',
        transition: 'all 0.2s ease',
        ...style,
      }}
    >
      {children}
    </div>
  );
}

function SectionTitle({ children, action }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
      <span style={{ fontSize: 13, fontWeight: 700, color: T.text.primary, letterSpacing: '0.01em' }}>{children}</span>
      {action && <span style={{ fontSize: 11, color: T.blue.text, fontWeight: 600, cursor: 'pointer' }}>{action}</span>}
    </div>
  );
}

function ChartTip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: '#fff', border: `1px solid ${T.border}`, borderRadius: 8, padding: '8px 12px', fontSize: 12, boxShadow: '0 4px 16px rgba(0,0,0,0.12)' }}>
      <div style={{ fontWeight: 700, color: T.text.primary, marginBottom: 5 }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, color: T.text.secondary, marginBottom: 2 }}>
          <span style={{ width: 8, height: 8, borderRadius: 2, background: p.color || p.fill, display: 'inline-block' }} />
          {p.name}: <b style={{ color: T.text.primary, marginLeft: 2 }}>{p.value}%</b>
        </div>
      ))}
    </div>
  );
}

// ─── CSS ─────────────────────────────────────────────────────────────────────
const CSS = `
  .ent-content { padding: 14px 16px; display: flex; flex-direction: column; gap: 14px; }
  @media (min-width: 768px) { .ent-content { padding: 16px 24px; gap: 16px; } }

  .ent-kpi { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
  @media (min-width: 640px)  { .ent-kpi { grid-template-columns: repeat(4, 1fr); } }
  @media (min-width: 1200px) { .ent-kpi { grid-template-columns: repeat(8, 1fr); gap: 10px; } }

  .ent-mid { display: grid; grid-template-columns: 1fr; gap: 12px; }
  @media (min-width: 900px)  { .ent-mid { grid-template-columns: 1.2fr 1fr; } }
  @media (min-width: 1280px) { .ent-mid { grid-template-columns: 1.2fr 1fr 1fr; } }

  .ent-bot { display: grid; grid-template-columns: 1fr; gap: 12px; }
  @media (min-width: 900px)  { .ent-bot { grid-template-columns: 1fr 1fr; } }
  @media (min-width: 1280px) { .ent-bot { grid-template-columns: 1fr 1fr 1fr; } }

  .ent-kpi-val { font-size: 20px; }
  @media (min-width: 480px) { .ent-kpi-val { font-size: 24px; } }

  .ent-spark { display: none; }
  @media (min-width: 360px) { .ent-spark { display: flex; } }
`;

// ─── MAIN ────────────────────────────────────────────────────────────────────
export default function EnterpriseDashboard() {
  const { data: prodData } = useProductionData();
  const { data: qualData } = useQualityData();

  const p      = prodData?.today     ?? {};
  const pY     = prodData?.yesterday ?? {};
  const q      = qualData?.today     ?? {};
  const qY     = qualData?.yesterday ?? {};
  const pLast9 = prodData?.last9     ?? [];
  const qLast9 = qualData?.last9     ?? [];

  const kpiCards      = buildKpiCards(p, pY, q, qY, pLast9, qLast9);
  const weeklyTrend   = buildWeeklyTrend(pLast9, qLast9);
  const perfVsTarget  = buildPerfVsTarget(p, q);
  const domainStatus  = buildDomainStatus(p, q);
  const alerts        = buildAlerts(p, q);
  const scorecard     = buildScorecard(p, q);
  const scorecardTiles = buildScorecardTiles(p, q, scorecard);
  const upcoming      = buildUpcoming(p, q);
  const prodLines     = buildProdLines(prodData);

  // Dynamic Y-axis floors so real data (e.g. 68% capacity) stays visible
  const trendMin  = weeklyTrend.length
    ? Math.max(55, Math.floor(Math.min(...weeklyTrend.flatMap(d => [d.Production, d.Packaging, d.Quality, d.Logistics])) / 5) * 5 - 3)
    : 82;
  const perfMin   = perfVsTarget.length
    ? Math.max(55, Math.floor(Math.min(...perfVsTarget.flatMap(d => [d.actual, d.target])) / 5) * 5 - 5)
    : 78;

  return (
    <div style={{ fontFamily: 'Inter, system-ui, -apple-system, sans-serif', background: T.bg, minHeight: '100%' }}>
      <style>{CSS}</style>

      {/* ── Sticky Header ── */}
      <div style={{
        position: 'sticky', top: 0, zIndex: 20,
        background: '#fff', borderBottom: `1px solid ${T.border}`,
        padding: '0 20px', height: 52,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 32, height: 32, borderRadius: 8, flexShrink: 0,
            background: 'linear-gradient(135deg, #ede9fe 0%, #ddd6fe 100%)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={T.prod.solid} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>
            </svg>
          </div>
          <div>
            <div style={{ fontSize: 14, fontWeight: 800, color: T.text.primary, letterSpacing: '-0.01em' }}>Enterprise Overview</div>
            <div style={{ fontSize: 10.5, color: T.text.muted, marginTop: 1 }}>Consolidated view across all operations</div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {DOMAIN_LEGEND.map(d => (
              <span key={d.label} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 10.5, color: d.color, fontWeight: 600 }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: d.color, display: 'inline-block' }} />
                {d.label}
              </span>
            ))}
          </div>
          <div style={{ fontSize: 10.5, color: T.green.text, background: T.green.light, padding: '4px 10px', borderRadius: 20, border: `1px solid ${T.green.solid}30`, fontWeight: 600, whiteSpace: 'nowrap', flexShrink: 0 }}>
            ● Live
          </div>
        </div>
      </div>

      <div className="ent-content">

        {/* ── Row 1: 8 KPI Cards ── */}
        <div className="ent-kpi">
          {kpiCards.map((k) => (
            <Card key={k.id} alert={k.isAlert} style={{ padding: '13px 14px 12px', display: 'flex', flexDirection: 'column', gap: 0, position: 'relative', overflow: 'hidden', cursor: 'pointer' }}>
              <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 3, borderRadius: '12px 12px 0 0', background: `linear-gradient(90deg, ${k.gradA}, ${k.gradB})` }} />
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginTop: 5, marginBottom: 8 }}>
                <span style={{ fontSize: 10.5, color: T.text.secondary, fontWeight: 500, lineHeight: 1.3, maxWidth: '55%' }}>{k.label}</span>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}>
                  <div style={{ width: 24, height: 24, borderRadius: 6, background: k.iconBg, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <Icon type={k.iconType} size={12} color={k.iconColor} />
                  </div>
                  <div className="ent-spark">
                    <Sparkline data={k.spark} color={k.gradA} />
                  </div>
                </div>
              </div>
              <div style={{ marginBottom: 8 }}>
                <span className="ent-kpi-val" style={{ fontWeight: 800, color: T.text.primary, letterSpacing: '-0.03em' }}>{k.value}</span>
                {k.unit && <span style={{ fontSize: 10.5, color: T.text.muted, marginLeft: 3, fontWeight: 500 }}>{k.unit}</span>}
              </div>
              <div style={{ height: 1, background: T.border, marginBottom: 8 }} />
              <div style={{ fontSize: 10.5, color: k.pos ? T.green.text : T.red.text, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 3 }}>
                <span style={{ fontSize: 12 }}>{k.pos ? '↑' : '↓'}</span>
                <span>{k.delta}</span>
              </div>
            </Card>
          ))}
        </div>

        {/* ── Row 2: Weekly Trend + Production Line Status + Active Alerts ── */}
        <div className="ent-mid">

          {/* Weekly Performance Trend */}
          <Card style={{ padding: '16px 20px' }}>
            <SectionTitle>Weekly Performance Trend (%)</SectionTitle>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={weeklyTrend} margin={{ top: 4, right: 8, left: -18, bottom: 0 }}>
                <XAxis dataKey="day" tick={{ fontSize: 11, fill: T.text.muted }} axisLine={false} tickLine={false} />
                <YAxis domain={[trendMin, 100]} tick={{ fontSize: 11, fill: T.text.muted }} axisLine={false} tickLine={false} />
                <Tooltip content={<ChartTip />} />
                <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11, fontFamily: 'Inter, system-ui' }} />
                <Line type="monotone" dataKey="Production" stroke={T.prod.solid} strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="Packaging"  stroke={T.pkg.solid}  strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="Quality"    stroke={T.qlt.solid}  strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="Logistics"  stroke={T.log.solid}  strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </Card>

          {/* Production Line Status */}
          <Card style={{ padding: '16px 18px' }}>
            <SectionTitle>Production Line Status</SectionTitle>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {prodLines.map((line) => (
                <div key={line.key} style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '10px 12px', borderRadius: 10,
                  border: `1px solid ${T.border}`,
                  background: `${line.light}55`,
                }}>
                  <span style={{ width: 9, height: 9, borderRadius: '50%', background: line.dotColor, flexShrink: 0 }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: T.text.primary }}>{line.label}</div>
                    <div style={{ fontSize: 10.5, color: T.text.muted, marginTop: 1 }}>{line.sub}</div>
                  </div>
                  <div style={{
                    flexShrink: 0, fontSize: 10, fontWeight: 700,
                    padding: '3px 9px', borderRadius: 999,
                    background: line.statusBg, color: line.statusColor,
                    border: `1px solid ${line.statusColor}30`,
                  }}>
                    {line.status}
                  </div>
                  <div style={{ fontSize: 11, fontWeight: 700, color: T.text.secondary, minWidth: 44, textAlign: 'right', flexShrink: 0 }}>
                    {line.unitsFormatted}
                  </div>
                </div>
              ))}
            </div>

            {prodData?.today && (
              <>
                <div style={{ height: 1, background: T.border, margin: '12px 0 10px' }} />
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  {[
                    { label: 'In Progress', value: prodData.today.batches.in_progress ?? 0, color: T.prod.solid },
                    { label: 'Completed',   value: prodData.today.batches.completed   ?? 0, color: T.green.solid },
                    { label: 'On Hold',     value: prodData.today.batches.on_hold     ?? 0, color: T.amber.solid },
                    { label: 'Pending',     value: prodData.today.batches.pending     ?? 0, color: T.text.muted  },
                  ].map((s, i) => (
                    <div key={i} style={{ textAlign: 'center', flex: 1 }}>
                      <div style={{ fontSize: 18, fontWeight: 800, color: s.color, letterSpacing: '-0.03em' }}>{s.value}</div>
                      <div style={{ fontSize: 9.5, color: T.text.muted, marginTop: 2, fontWeight: 500 }}>{s.label}</div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </Card>

          {/* Active Alerts */}
          <Card style={{ padding: '16px 18px' }}>
            <SectionTitle action="View All →">Active Alerts</SectionTitle>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
              {alerts.map((a, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'flex-start', gap: 9,
                  padding: '8px 11px', borderRadius: 8,
                  background: a.pb, border: `1px solid ${a.pc}20`,
                }}>
                  <span style={{ fontSize: 14, flexShrink: 0, marginTop: 1 }}>{a.icon}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 9.5, fontWeight: 700, color: a.pc, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 1 }}>
                      {a.domain} · {a.priority}
                    </div>
                    <div style={{ fontSize: 11.5, color: T.text.secondary, lineHeight: 1.4 }}>{a.msg}</div>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>

        {/* ── Row 3: Performance vs Target + Scorecard + Domain Health + Upcoming ── */}
        <div className="ent-bot" style={{ alignItems: 'stretch' }}>

          {/* Performance vs Target */}
          <Card style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column' }}>
            <SectionTitle>Performance vs Target (%)</SectionTitle>
            <ResponsiveContainer width="100%" height={190}>
              <BarChart data={perfVsTarget} margin={{ top: 4, right: 8, left: -18, bottom: 0 }} barCategoryGap="32%" barGap={3}>
                <XAxis dataKey="domain" tick={{ fontSize: 11, fill: T.text.muted }} axisLine={false} tickLine={false} />
                <YAxis domain={[perfMin, 100]} ticks={[perfMin, Math.round((perfMin + 100) / 2), 100]} tick={{ fontSize: 11, fill: T.text.muted }} axisLine={false} tickLine={false} />
                <Tooltip content={<ChartTip />} cursor={{ fill: 'rgba(0,0,0,0.04)', radius: [4, 4, 0, 0] }} />
                <Legend iconType="square" iconSize={9} wrapperStyle={{ fontSize: 11, fontFamily: 'Inter, system-ui' }} />
                <Bar dataKey="actual" name="Actual" radius={[4, 4, 0, 0]}>
                  {perfVsTarget.map((_, i) => <Cell key={i} fill={PERF_COLORS[i]} />)}
                </Bar>
                <Bar dataKey="target" name="Target" fill="#dde1ea" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>

            <div style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 10, flex: 1 }}>
              <div style={{ height: 1, background: T.border, marginBottom: 2 }} />
              {perfVsTarget.map((d, i) => (
                <div key={i}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span style={{ width: 8, height: 8, borderRadius: '50%', background: PERF_COLORS[i], display: 'inline-block', flexShrink: 0 }} />
                      <span style={{ fontSize: 11.5, color: T.text.secondary, fontWeight: 500 }}>{d.domain}</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontSize: 11, color: T.text.muted }}>Target: {d.target}%</span>
                      <span style={{
                        fontSize: 11, fontWeight: 700, color: d.actual >= d.target ? T.green.text : T.red.text,
                        background: d.actual >= d.target ? T.green.light : T.red.light,
                        padding: '1px 6px', borderRadius: 999,
                      }}>
                        {d.actual >= d.target ? '▲' : '▼'} {d.actual}%
                      </span>
                    </div>
                  </div>
                  <div style={{ height: 7, background: T.border, borderRadius: 999, position: 'relative', overflow: 'hidden' }}>
                    <div style={{ height: '100%', borderRadius: 999, background: PERF_COLORS[i], width: `${((d.actual - perfMin) / (100 - perfMin)) * 100}%`, transition: 'width 0.4s ease' }} />
                    <div style={{ position: 'absolute', top: 0, bottom: 0, left: `${((d.target - perfMin) / (100 - perfMin)) * 100}%`, width: 2, background: '#64748b', opacity: 0.5 }} />
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {/* Domain Scorecard — Radar */}
          <Card style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column' }}>
            <SectionTitle>Domain Scorecard</SectionTitle>
            <ResponsiveContainer width="100%" height={210}>
              <RadarChart data={scorecard} cx="50%" cy="52%" outerRadius="62%" margin={{ top: 28, right: 36, left: 36, bottom: 16 }}>
                <PolarGrid stroke={T.border} />
                <PolarAngleAxis dataKey="metric" tick={{ fontSize: 10.5, fill: T.text.secondary, fontFamily: 'Inter, system-ui', fontWeight: 500 }} />
                <PolarRadiusAxis domain={[60, 100]} tick={false} axisLine={false} />
                <Tooltip content={<ChartTip />} />
                <Radar name="Production" dataKey="Production" stroke={T.prod.solid} fill={T.prod.solid} fillOpacity={0.13} strokeWidth={2} />
                <Radar name="Packaging"  dataKey="Packaging"  stroke={T.pkg.solid}  fill={T.pkg.solid}  fillOpacity={0.13} strokeWidth={2} />
                <Radar name="Quality"    dataKey="Quality"    stroke={T.qlt.solid}  fill={T.qlt.solid}  fillOpacity={0.13} strokeWidth={2} />
                <Radar name="Logistics"  dataKey="Logistics"  stroke={T.log.solid}  fill={T.log.solid}  fillOpacity={0.13} strokeWidth={2} />
                <Legend iconType="circle" iconSize={8} verticalAlign="top" align="center" wrapperStyle={{ fontSize: 11, fontFamily: 'Inter, system-ui', paddingBottom: 4 }} />
              </RadarChart>
            </ResponsiveContainer>

            <div style={{ marginTop: 14, flex: 1 }}>
              <div style={{ height: 1, background: T.border, marginBottom: 12 }} />
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
                {scorecardTiles.map((d, i) => (
                  <div key={i} style={{ background: `${d.light}80`, borderRadius: 10, padding: '10px 12px', border: `1px solid ${d.color}22` }}>
                    <div style={{ fontSize: 10.5, color: T.text.secondary, fontWeight: 500, marginBottom: 4 }}>{d.label}</div>
                    <div style={{ fontSize: 20, fontWeight: 800, color: d.color, letterSpacing: '-0.03em', lineHeight: 1 }}>{d.avg}<span style={{ fontSize: 11, fontWeight: 500, marginLeft: 1 }}>%</span></div>
                    <div style={{ fontSize: 10, color: T.text.muted, marginTop: 4 }}>avg · best: {d.top}</div>
                  </div>
                ))}
              </div>
            </div>
          </Card>

          {/* Domain Health Status + Upcoming Activities */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>

            <Card style={{ padding: '16px 18px', flex: 1 }}>
              <SectionTitle>Domain Health Status</SectionTitle>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
                {domainStatus.map((d, i) => (
                  <div key={i} style={{
                    display: 'flex', alignItems: 'center', gap: 10,
                    padding: '10px 12px', borderRadius: 10,
                    border: `1px solid ${T.border}`,
                    background: `${d.light}60`,
                  }}>
                    <span style={{ fontSize: 18, flexShrink: 0 }}>{d.icon}</span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 12, fontWeight: 700, color: T.text.primary }}>{d.label}</div>
                      <div style={{ fontSize: 10.5, color: T.text.muted, marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{d.detail}</div>
                    </div>
                    <div style={{
                      flexShrink: 0, fontSize: 10, fontWeight: 700,
                      padding: '3px 9px', borderRadius: 999,
                      background: d.hb, color: d.hc,
                      border: `1px solid ${d.hc}30`,
                    }}>
                      {d.health}
                    </div>
                  </div>
                ))}
              </div>
            </Card>

            <Card style={{ padding: '16px 18px' }}>
              <SectionTitle action="View All →">Upcoming Activities</SectionTitle>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                {upcoming.map((a, i) => (
                  <div key={i} style={{
                    display: 'flex', alignItems: 'center', gap: 10,
                    padding: '9px 0',
                    borderBottom: i < upcoming.length - 1 ? `1px solid ${T.border}` : 'none',
                  }}>
                    <div style={{ width: 28, height: 28, borderRadius: 7, background: a.iconBg, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke={a.iconColor} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>
                      </svg>
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 12, fontWeight: 600, color: T.text.primary }}>{a.label}</div>
                      <div style={{ fontSize: 10.5, color: T.text.muted, marginTop: 1 }}>{a.domain} · {a.note}</div>
                    </div>
                    <div style={{
                      fontSize: 9.5, fontWeight: 700, padding: '2px 7px', borderRadius: 999,
                      background: a.urgency === 'high' ? T.red.light  : a.urgency === 'med' ? T.amber.light : T.blue.light,
                      color:      a.urgency === 'high' ? T.red.text   : a.urgency === 'med' ? T.amber.text  : T.blue.text,
                      textTransform: 'uppercase', flexShrink: 0,
                    }}>
                      {a.urgency === 'high' ? 'Urgent' : a.urgency === 'med' ? 'Soon' : 'Planned'}
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        </div>

      </div>
    </div>
  );
}
