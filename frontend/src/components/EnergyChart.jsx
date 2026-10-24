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

export default function EnergyChart({ series = [], powerLimit }) {
  const data = series.map((p) => ({
    time: shortTime(p.timestamp),
    power_kw: Number(p.power_kw?.toFixed?.(2) ?? p.power_kw),
    price: p.price_eur_per_kwh,
    limit: powerLimit,
  }));

  if (!data.length) {
    return <p className="text-sm text-muted-foreground">Run the optimizer to see station power usage over time.</p>;
  }

  return (
    <div className="h-[300px] w-full animate-fade">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data}>
          <defs>
            <linearGradient id="powerFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#6366f1" stopOpacity={0.45} />
              <stop offset="100%" stopColor="#6366f1" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="currentColor" className="text-border" />
          <XAxis dataKey="time" minTickGap={28} tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} unit=" kW" width={56} />
          <Tooltip
            contentStyle={{
              borderRadius: 12,
              border: "1px solid var(--color-border)",
              background: "var(--color-card)",
            }}
          />
          <Legend />
          <Area
            type="stepAfter"
            dataKey="power_kw"
            name="Station power"
            stroke="#6366f1"
            fill="url(#powerFill)"
            strokeWidth={2}
          />
          <Area
            type="stepAfter"
            dataKey="limit"
            name="Power limit"
            stroke="#7c3aed"
            fill="transparent"
            strokeDasharray="4 4"
            strokeWidth={1.5}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
