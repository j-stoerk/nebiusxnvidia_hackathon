import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { shortTime } from "@/utils/formatters";

export default function EnergyChart({ series = [], baselineSeries = [], powerLimit }) {
  const baseline = Object.fromEntries(baselineSeries.map(p => [p.timestamp, p.power_kw]));
  const data = series.map((p) => ({
    time: shortTime(p.timestamp),
    power_kw: Number(p.power_kw?.toFixed?.(2) ?? p.power_kw),
    price: p.price_eur_per_kwh,
    limit: powerLimit,
    baseline_kw: baseline[p.timestamp],
  }));

  if (!data.length) {
    return <p className="text-sm text-muted-foreground">Run the optimizer to see station power usage over time.</p>;
  }

  return (
    <div className="h-[300px] w-full text-muted-foreground">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="currentColor" className="text-border" />
          <XAxis dataKey="time" minTickGap={28} tick={{ fontSize: 11, fill: "var(--color-muted-foreground)" }} />
          <YAxis tick={{ fontSize: 11, fill: "var(--color-muted-foreground)" }} unit=" kW" width={56} />
          <Tooltip
            contentStyle={{
              borderRadius: 6,
              border: "1px solid var(--color-border)",
              background: "var(--color-card)",
            }}
          />
          <Legend />
          <Area
            type="stepAfter" dataKey="baseline_kw" name="FCFS" stroke="#94a3b8" fill="transparent" strokeWidth={1.5} strokeDasharray="5 4"
          />
          <Area
            type="stepAfter"
            dataKey="power_kw"
            name="Station power"
            stroke="var(--color-primary)"
            fill="var(--color-primary)"
            fillOpacity={0.08}
            strokeWidth={2}
          />
          <Area
            type="stepAfter"
            dataKey="limit"
            name="Power limit"
            stroke="var(--color-warning)"
            fill="transparent"
            strokeDasharray="4 4"
            strokeWidth={1.5}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
