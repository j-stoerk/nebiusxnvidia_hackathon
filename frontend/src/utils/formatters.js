export function eur(value) {
  if (value == null || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat("en-IE", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 2,
  }).format(value);
}

export function kwh(value) {
  if (value == null) return "—";
  return `${Number(value).toFixed(1)} kWh`;
}

export function kw(value) {
  if (value == null) return "—";
  return `${Number(value).toFixed(1)} kW`;
}

export function pct(value) {
  if (value == null) return "—";
  return `${Number(value).toFixed(1)}%`;
}

/** Format duration as Xh Ym Zs (or omit zero parts). */
export function formatDuration(ms) {
  if (ms == null || Number.isNaN(ms) || ms < 0) return "—";
  const totalSec = Math.round(ms / 1000);
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  const parts = [];
  if (h) parts.push(`${h}h`);
  if (m || h) parts.push(`${m}m`);
  parts.push(`${s}s`);
  return parts.join(" ");
}

/** Clock time HH:MM:SS UTC */
export function formatClock(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    timeZone: "UTC",
    hour12: false,
  });
}

/** Date + time for ops: 07 Jan · 06:45:00 UTC */
export function timeLabel(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  const date = d.toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    timeZone: "UTC",
  });
  return `${date} · ${formatClock(iso)} UTC`;
}

/** Short clock HH:MM UTC (charts) */
export function shortTime(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
    hour12: false,
  });
}

/** Slot range with duration: 06:45:00 → 07:00:00 (15m 0s) */
export function slotRange(startIso, endIso) {
  if (!startIso || !endIso) return "—";
  const ms = new Date(endIso) - new Date(startIso);
  return `${formatClock(startIso)} → ${formatClock(endIso)} (${formatDuration(ms)})`;
}
