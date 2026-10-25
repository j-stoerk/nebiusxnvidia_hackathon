import { Badge } from "@/components/ui/badge";
import { eur, kwh, kw, pct } from "@/utils/formatters";

function Col({ title, rows, badge }) {
  return (
    <div className="rounded-xl border border-border bg-muted/40 p-4 transition-colors hover:bg-muted/70">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">{title}</h3>
        {badge}
      </div>
      <ul className="space-y-2 text-sm text-muted-foreground">
        {rows.map(([k, v]) => (
          <li key={k} className="flex justify-between gap-3">
            <span>{k}</span>
            <span className="font-medium text-foreground">{v}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function CostComparison({ comparison, optimized, baseline, references = {} }) {
  if (!comparison) {
    return (
      <p className="text-sm text-muted-foreground">
        Cost and peak comparisons appear only after both FCFS baseline and OR-Tools schedules are calculated.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-3">
        <Col
          title="Baseline (FCFS)"
          badge={<Badge variant="outline">Greedy</Badge>}
          rows={[
            ["Total cost", eur(comparison.baseline_cost_eur)],
            ["Energy cost", eur(comparison.baseline_energy_cost_eur)],
            ["Demand cost", eur(comparison.baseline_demand_cost_eur)],
            ["Unserved", kwh(comparison.baseline_unserved_kwh)],
            ["Peak", kw(comparison.baseline_peak_kw)],
            ["Targets met", pct(baseline?.metrics?.target_success_percent)],
          ]}
        />
        <Col
          title="Optimized (OR-Tools)"
          badge={<Badge>{optimized?.validated ? "Independently checked" : "Unchecked"}</Badge>}
          rows={[
            ["Total cost", eur(comparison.optimized_cost_eur)],
            ["Energy cost", eur(comparison.optimized_energy_cost_eur)],
            ["Demand cost", eur(comparison.optimized_demand_cost_eur)],
            ["Unserved", kwh(comparison.optimized_unserved_kwh)],
            ["Peak", kw(comparison.optimized_peak_kw)],
            ["Targets met", pct(optimized?.metrics?.target_success_percent)],
          ]}
        />
        <div className="rounded-xl border border-primary/30 bg-gradient-to-br from-indigo-500/10 to-violet-500/10 p-4">
          <h3 className="text-sm font-semibold">Simulated comparison</h3>
          <p className="mt-3 text-2xl font-semibold text-primary">{eur(comparison.cost_savings_eur)}</p>
          <p className="mt-1 text-xs text-muted-foreground">{comparison.equal_energy_comparison ? "Cost difference at equal delivered energy" : "Different delivered energy: compare shortfalls first"}</p>
          <ul className="mt-3 space-y-1.5 text-sm text-muted-foreground">
            <li className="flex justify-between gap-2">
              <span>Energy €</span>
              <span className="font-medium text-foreground">{eur(comparison.energy_cost_savings_eur)}</span>
            </li>
            <li className="flex justify-between gap-2">
              <span>Demand €</span>
              <span className="font-medium text-foreground">{eur(comparison.demand_cost_savings_eur)}</span>
            </li>
            <li className="flex justify-between gap-2">
              <span>Peak reduction</span>
              <span className="font-medium text-foreground">{kw(comparison.peak_reduction_kw)}</span>
            </li>
          </ul>
          <p className="mt-3 text-[11px] leading-relaxed text-muted-foreground">
            Demand uses tariff {eur(comparison.demand_tariff_eur_per_kw)}/kW above prior peak{" "}
            {kw(comparison.prior_peak_kw)}. Efficiency {pct((comparison.charging_efficiency || 1) * 100)}.
            {comparison.fixed_connections ? " Fixed plugs enabled." : ""}
          </p>
        </div>
      </div>
      <div className="overflow-auto rounded-xl border border-border">
        <table className="w-full text-left text-xs">
          <thead className="bg-muted"><tr>{["Policy", "Unserved kWh", "Peak kW", "Energy €", "Demand €", "Total €", "Checks"].map(h => <th key={h} className="px-3 py-2">{h}</th>)}</tr></thead>
          <tbody>{[["FCFS", baseline], ["EDF", references.EDF], ["LLF", references.LLF], ["OR-Tools", optimized]].filter(([, p]) => p).map(([name, plan]) => (
            <tr key={name} className="border-t border-border"><td className="px-3 py-2 font-medium">{name}</td>
              {[plan.metrics.unserved_kwh.toFixed(3), plan.metrics.peak_power_kw.toFixed(2), eur(plan.metrics.energy_cost_eur), eur(plan.metrics.demand_cost_eur), eur(plan.metrics.cost_eur), plan.validated ? "Passed" : "Unchecked"].map((v, i) => <td key={i} className="px-3 py-2 tabular-nums">{v}</td>)}
            </tr>))}</tbody>
        </table>
      </div>
    </div>
  );
}
