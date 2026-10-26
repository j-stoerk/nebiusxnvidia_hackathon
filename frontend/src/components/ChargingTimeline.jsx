import { useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import ListPager, { usePage } from "@/components/ListPager";
import { formatClock, formatDuration, kw, slotRange, timeLabel } from "@/utils/formatters";

const COLORS = [
  "bg-blue-600 dark:bg-blue-400",
  "bg-teal-700 dark:bg-teal-400",
  "bg-slate-600 dark:bg-slate-400",
  "bg-amber-700 dark:bg-amber-400",
  "bg-cyan-700 dark:bg-cyan-400",
];

function SlotPopover({ tip, x, y }) {
  if (!tip) return null;
  const left = Math.min(Math.max(12, x + 14), (typeof window !== "undefined" ? window.innerWidth : 400) - 280);
  const top = Math.max(12, y - 8);
  return (
    <div
      className="pointer-events-none fixed z-[100] w-[260px] -translate-y-full rounded-md border border-border bg-card p-3 text-xs shadow-md"
      style={{ left, top }}
      role="tooltip"
    >
      <p className="mb-2 text-sm font-semibold text-foreground">{tip.title}</p>
      <dl className="space-y-1.5 text-muted-foreground">
        {tip.rows.map(([label, value]) => (
          <div key={label} className="flex justify-between gap-3">
            <dt>{label}</dt>
            <dd className="text-right font-medium tabular-nums text-foreground">{value}</dd>
          </div>
        ))}
      </dl>
      {tip.note ? <p className="mt-2 border-t border-border pt-2 text-[11px] leading-snug">{tip.note}</p> : null}
    </div>
  );
}

function mergeAdjacent(allocations) {
  const sorted = [...allocations].sort((a, b) => {
    if (a.vehicle_id !== b.vehicle_id) return a.vehicle_id.localeCompare(b.vehicle_id);
    if (a.charger_id !== b.charger_id) return a.charger_id.localeCompare(b.charger_id);
    return new Date(a.start_time) - new Date(b.start_time);
  });
  const merged = [];
  for (const a of sorted) {
    const last = merged[merged.length - 1];
    const contiguous =
      last &&
      last.vehicle_id === a.vehicle_id &&
      last.charger_id === a.charger_id &&
      new Date(last.end_time).getTime() === new Date(a.start_time).getTime() &&
      Math.abs(last.power_kw - a.power_kw) < 0.05;
    if (contiguous) {
      const d1 = new Date(last.end_time) - new Date(last.start_time);
      const d2 = new Date(a.end_time) - new Date(a.start_time);
      last.power_kw = (last.power_kw * d1 + a.power_kw * d2) / (d1 + d2);
      last.end_time = a.end_time;
    } else {
      merged.push({ ...a });
    }
  }
  return merged;
}

export default function ChargingTimeline({ allocations = [], sessions = [] }) {
  const [filter, setFilter] = useState("");
  const [popover, setPopover] = useState({ tip: null, x: 0, y: 0 });

  function showTip(tip, event) {
    setPopover({ tip, x: event.clientX, y: event.clientY });
  }

  function moveTip(event) {
    setPopover((prev) => (prev.tip ? { ...prev, x: event.clientX, y: event.clientY } : prev));
  }

  function hideTip() {
    setPopover({ tip: null, x: 0, y: 0 });
  }

  const { byVehicle, horizonStart, horizonEnd, spanMs, displayAllocations } = useMemo(() => {
    if (!allocations.length) {
      return { byVehicle: {}, horizonStart: 0, horizonEnd: 1, spanMs: 1, displayAllocations: [] };
    }
    const displayAllocations = mergeAdjacent(allocations);
    const map = {};
    let min = Infinity;
    let max = -Infinity;
    for (const a of displayAllocations) {
      (map[a.vehicle_id] ||= []).push(a);
      min = Math.min(min, new Date(a.start_time).getTime());
      max = Math.max(max, new Date(a.end_time).getTime());
    }
    for (const s of sessions) {
      map[s.vehicle_id] ||= [];
      min = Math.min(min, new Date(s.arrival_time).getTime());
      max = Math.max(max, new Date(s.departure_time).getTime());
    }
    if (!Number.isFinite(min) || !Number.isFinite(max) || max <= min) {
      min = 0;
      max = 1;
    }
    return { byVehicle: map, horizonStart: min, horizonEnd: max, spanMs: max - min, displayAllocations };
  }, [allocations, sessions]);

  const vehicles = Object.keys(byVehicle)
    .sort()
    .filter((id) => !filter || id.toLowerCase().includes(filter.toLowerCase()));
  const vehiclePage = usePage(vehicles, 30);
  const allocationPage = usePage(displayAllocations, 80);

  const ticks = useMemo(() => {
    const count = 6;
    return Array.from({ length: count }, (_, i) => {
      const t = horizonStart + (spanMs * i) / (count - 1);
      return { left: `${(i / (count - 1)) * 100}%`, label: formatClock(new Date(t).toISOString()) };
    });
  }, [horizonStart, spanMs]);

  if (!allocations.length) {
    return (
      <p className="text-sm text-muted-foreground">
        No charging intervals yet. Run the optimizer to build the vehicle schedule.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <Badge variant="secondary">UTC timeline</Badge>
          <Badge variant="outline">Merged continuous slots</Badge>
          <span>
            {formatClock(new Date(horizonStart).toISOString())} →{" "}
            {formatClock(new Date(horizonEnd).toISOString())} ({formatDuration(spanMs)})
          </span>
        </div>
        <Input
          className="max-w-xs"
          placeholder="Filter vehicle ID…"
          value={filter}
          onChange={(e) => { setFilter(e.target.value); vehiclePage.setPage(0); }}
        />
      </div>

      <div className="overflow-x-auto rounded-md border border-border bg-muted/30">
        <div className="min-w-[720px] p-3">
          <div className="mb-2 ml-[100px] relative h-6 border-b border-border">
            {ticks.map((tick) => (
              <span
                key={tick.label + tick.left}
                className="absolute -translate-x-1/2 text-[10px] font-medium text-muted-foreground"
                style={{ left: tick.left }}
              >
                {tick.label}
              </span>
            ))}
          </div>

          <div className="space-y-2">
            {vehiclePage.rows.map((id, idx) => {
              const slots = byVehicle[id];
              const color = COLORS[idx % COLORS.length];
              const session = sessions.find((s) => s.vehicle_id === id);
              const availLeft = session
                ? ((new Date(session.arrival_time) - horizonStart) / spanMs) * 100
                : 0;
              const availWidth = session
                ? ((new Date(session.departure_time) - new Date(session.arrival_time)) / spanMs) * 100
                : 100;

              return (
                <div key={id} className="grid grid-cols-[100px_1fr] items-center gap-2">
                  <div className="truncate pr-1">
                    <p className="text-xs font-semibold">{id}</p>
                    {session ? (
                      <p className="text-[10px] text-muted-foreground">
                        dwell {formatDuration(new Date(session.departure_time) - new Date(session.arrival_time))}
                      </p>
                    ) : null}
                  </div>
                  <div className="relative h-9 rounded-lg bg-card/80 ring-1 ring-border">
                    {session ? (
                      <div
                        className="absolute inset-y-1 rounded-sm bg-primary/10 cursor-help"
                        style={{
                          left: `${Math.max(0, availLeft)}%`,
                          width: `${Math.min(100, Math.max(0, availWidth))}%`,
                        }}
                        onMouseEnter={(e) =>
                          showTip(
                            {
                              title: `${id} · availability window`,
                              rows: [
                                ["Status", "Parked / can charge"],
                                ["Arrival", timeLabel(session.arrival_time)],
                                ["Departure", timeLabel(session.departure_time)],
                                [
                                  "Dwell",
                                  formatDuration(
                                    new Date(session.departure_time) - new Date(session.arrival_time)
                                  ),
                                ],
                                ["Range", slotRange(session.arrival_time, session.departure_time)],
                              ],
                              note: "Light bar = vehicle is at the depot. Solid segments show charging.",
                            },
                            e
                          )
                        }
                        onMouseMove={moveTip}
                        onMouseLeave={hideTip}
                      />
                    ) : null}
                    {slots.map((a, i) => {
                      const left = ((new Date(a.start_time) - horizonStart) / spanMs) * 100;
                      const width = ((new Date(a.end_time) - new Date(a.start_time)) / spanMs) * 100;
                      const durationMs = new Date(a.end_time) - new Date(a.start_time);
                      return (
                        <div
                          key={`${id}-${i}`}
                          className={`slot-bar absolute top-1.5 bottom-1.5 z-10 rounded-sm ${color} cursor-pointer`}
                          style={{
                            left: `${Math.max(0, left)}%`,
                            width: `${Math.max(0.4, width)}%`,
                          }}
                          onMouseEnter={(e) =>
                            showTip(
                              {
                                title: `${a.vehicle_id} · charging now`,
                                rows: [
                                  ["Status", "Actively charging"],
                                  ["Charger", a.charger_id],
                                  ["Power", kw(a.power_kw)],
                                  ["Start", timeLabel(a.start_time)],
                                  ["End", timeLabel(a.end_time)],
                                  ["Duration", formatDuration(durationMs)],
                                  ["Slot", slotRange(a.start_time, a.end_time)],
                                ],
                                note: "Solid segment = this vehicle is drawing power in this UTC window.",
                              },
                              e
                            )
                          }
                          onMouseMove={moveTip}
                          onMouseLeave={hideTip}
                        />
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <SlotPopover tip={popover.tip} x={popover.x} y={popover.y} />

      <ListPager list={vehiclePage} name="vehicles" />

      <div className="max-h-48 overflow-auto rounded-md border border-border">
        <table className="w-full text-left text-xs">
          <thead className="sticky top-0 bg-muted">
            <tr className="text-muted-foreground">
              <th className="px-3 py-2 font-medium">Vehicle</th>
              <th className="px-3 py-2 font-medium">Charger</th>
              <th className="px-3 py-2 font-medium">Start (UTC)</th>
              <th className="px-3 py-2 font-medium">End (UTC)</th>
              <th className="px-3 py-2 font-medium">Duration</th>
              <th className="px-3 py-2 font-medium">Power</th>
            </tr>
          </thead>
          <tbody>
            {allocationPage.rows.map((a, i) => (
              <tr key={i} className="border-t border-border/70 hover:bg-muted/40 transition-colors">
                <td className="px-3 py-2 font-medium">{a.vehicle_id}</td>
                <td className="px-3 py-2">{a.charger_id}</td>
                <td className="px-3 py-2 tabular-nums">{formatClock(a.start_time)}</td>
                <td className="px-3 py-2 tabular-nums">{formatClock(a.end_time)}</td>
                <td className="px-3 py-2 tabular-nums">
                  {formatDuration(new Date(a.end_time) - new Date(a.start_time))}
                </td>
                <td className="px-3 py-2">{kw(a.power_kw)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ListPager list={allocationPage} name="allocations" />
    </div>
  );
}
