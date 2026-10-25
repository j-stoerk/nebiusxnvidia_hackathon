import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { eur, kwh, kw, pct } from "@/utils/formatters";

export default function CapacityPanel({ study, busy, onRun }) {
  const rec = study?.recommendation;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground max-w-xl">
          Find how much charging capacity this roster needs. Every feasible candidate has an independently checked schedule.
        </p>
        <Button type="button" disabled={busy} onClick={onRun}>
          Run capacity study
        </Button>
      </div>

      {!study ? (
        <p className="text-sm text-muted-foreground">No capacity study yet. Optimize first, then run the study.</p>
      ) : (
        <>
          {rec ? (
            <div className="rounded-md border border-emerald-500/30 bg-emerald-500/5 p-4">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <h3 className="font-semibold">{study.minimum_proven ? "Smallest checked configuration" : "Best feasible candidate tested"}</h3>
                <Badge variant="success">{study.minimum_proven ? "Minimum proven" : "Verified feasible"}</Badge>
              </div>
              <p className="text-lg font-semibold">
                {rec.charger_count} chargers · {kw(rec.station_power_limit_kw)} site limit
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                Peak {kw(rec.peak_power_kw)} · cost {eur(rec.cost_eur)} · targets{" "}
                {pct(rec.target_success_percent)} · unserved {kwh(rec.unserved_kwh)}
              </p>
            </div>
          ) : (
            <div className="rounded-md border border-amber-500/30 bg-amber-500/5 p-4 text-sm">
              {study.candidates.some(c => c.outcome === "unresolved") ? "Capacity check incomplete. Try a smaller roster; no minimum is certified." : "No tested configuration meets every target. Review the shortfalls and plug bindings."}
            </div>
          )}

          <div className="max-h-56 overflow-auto rounded-md border border-border">
            <table className="w-full text-left text-xs">
              <thead className="sticky top-0 bg-muted/90">
                <tr className="text-muted-foreground">
                  <th className="px-3 py-2">Chargers</th>
                  <th className="px-3 py-2">Power cap</th>
                  <th className="px-3 py-2">Peak</th>
                  <th className="px-3 py-2">Unserved</th>
                  <th className="px-3 py-2">Cost</th>
                  <th className="px-3 py-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {(study.candidates || []).map((c, i) => (
                  <tr key={i} className="border-t border-border/70">
                    <td className="px-3 py-2">{c.charger_count}</td>
                    <td className="px-3 py-2">{kw(c.station_power_limit_kw)}</td>
                    <td className="px-3 py-2">{c.peak_power_kw != null ? kw(c.peak_power_kw) : "—"}</td>
                    <td className="px-3 py-2">{c.unserved_kwh != null ? kwh(c.unserved_kwh) : "—"}</td>
                    <td className="px-3 py-2">{c.cost_eur != null ? eur(c.cost_eur) : "—"}</td>
                    <td className="px-3 py-2">
                      {c.feasible ? "Verified feasible" : c.outcome === "unresolved" ? "Search incomplete" : "Proven shortfall / binding limit"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {study.proof ? (
            <details className="text-xs text-muted-foreground"><summary className="cursor-pointer font-medium">Show capacity proof</summary><p className="mt-2">{study.proof.note}</p><p className="mt-2">Installed: {study.proof.installed_chargers} ports · {kw(study.proof.installed_power_limit_kw)} connection. Fixed plugs: {study.proof.fixed_connections ? "yes" : "no"}.</p></details>
          ) : null}
        </>
      )}
    </div>
  );
}
