/** Keep the decision readable; retain solver evidence behind an explicit disclosure. */
import { useState } from "react";
import type { Controller } from "../useWorkspace";
import type { Schedule } from "../types";
import { api } from "../api";
import { money, number } from "../format";
import { PanelTitle } from "./Dashboard";

type CapacityRow = {
  chargers: number;
  connection_kw: number | null;
  unserved_kwh: number | null;
  meets_all_departures: boolean;
  minimum_proven: boolean;
  infeasibility_proven: boolean;
  solver_status: string;
  validated: boolean;
};

function DataTable({
  label,
  headings,
  rows,
}: {
  label: string;
  headings: string[];
  rows: string[][];
}) {
  return (
    <div className="table-scroll">
      <table aria-label={label}>
        <thead>
          <tr>
            {headings.map((h) => (
              <th key={h}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((cells, i) => (
            <tr key={i}>
              {cells.map((cell, j) => (
                <td key={j}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CapacityProof({ rows }: { rows: CapacityRow[] }) {
  return (
    <details className="capacity-proof">
      <summary>Show capacity proof</summary>
      <p className="comparison-note">
        Each option uses installed charger ratings, connector compatibility, fixed plug occupancy,
        vehicle power limits and supplied battery taper. The connection ceiling is the current site
        limit.
      </p>
      <DataTable
        label="Capacity proof"
        headings={["Chargers", "Power", "Unserved", "Independent check", "Solver result"]}
        rows={rows.map((r) => [
          String(r.chargers),
          r.connection_kw == null ? "—" : `${number(r.connection_kw, 2)} kW`,
          r.unserved_kwh == null ? "—" : `${number(r.unserved_kwh, 2)} kWh`,
          r.validated ? "Passed" : "No checked schedule",
          r.minimum_proven
            ? "Meets every departure · minimum power proven"
            : r.meets_all_departures
              ? "Meets departures · power minimum unproven"
              : r.infeasibility_proven
                ? "Cannot meet every departure · proven"
                : "Time limit · no conclusion",
        ])}
      />
      <p className="comparison-note">
        Proof applies to this roster and the model's limits (1e-5 kWh tolerance). It does not
        establish future reliability or a quoted capex saving.
      </p>
    </details>
  );
}

export function PlanningPanel({ ui }: { ui: Controller }) {
  const data = ui.data!;
  const [rows, setRows] = useState<CapacityRow[]>([]);
  const [error, setError] = useState("");
  const schedules = [
    data.baseline,
    data.references.EDF,
    data.references.LLF,
    data.optimized,
  ].filter((s): s is Schedule => s != null && s.state_version === data.state_version);
  const count = Math.min(10, data.station.chargers.length);
  const best = rows.find((r) => r.meets_all_departures);
  const smallest =
    best && rows.filter((r) => r.chargers < best.chargers).every((r) => r.infeasibility_proven);
  const noneFit = rows.length > 0 && rows.every((r) => r.infeasibility_proven);

  async function study() {
    ui.set({ busy: "Checking the depot against its physical limits" });
    setError("");
    try {
      const report = await api<{ candidates: CapacityRow[] }>(
        `/workspaces/${data.workspace_id}/capacity`,
        {
          expected_version: data.state_version,
          counts: Array.from({ length: count }, (_, i) => i + 1),
        },
      );
      setRows(report.candidates);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Capacity check failed");
    } finally {
      ui.set({ busy: null });
    }
  }

  return (
    <section className="panel comparison-panel">
      <PanelTitle eyebrow="COMPARISON" title="Same depot. Four charging strategies." />
      <p className="comparison-note">
        {data.station.fixed_connections
          ? "One vehicle per plug until departure. Charger ratings, vehicle limits, outages and shared site power apply to every strategy."
          : "Legacy simulation: vehicles may be moved between plugs. Operator uploads use fixed connections."}
      </p>
      <DataTable
        label="Charging policy comparison"
        headings={["Strategy", "Ready", "Unserved", "Peak", "Energy", "Demand", "Total"]}
        rows={schedules.map((s) => [
          s.kind === "optimized" ? "OR-Tools" : s.solver_status,
          `${number(s.metrics.target_success_percent)}%`,
          `${number(s.metrics.unserved_kwh, 2)} kWh`,
          `${number(s.metrics.peak_power_kw)} kW`,
          money(s.metrics.energy_cost_eur),
          money(s.metrics.demand_cost_eur),
          money(s.metrics.cost_eur),
        ])}
      />
      <p className="comparison-note">
        Full-information demo. Demand cost is the increase over prior billing peaks (
        {data.station.demand_tariff.timezone}). Compare readiness before cost.
      </p>
      <div className="capacity-heading">
        <div>
          <h2>Check the connection and charger count</h2>
          <p>
            Use this roster and the installed hardware to find a smaller configuration that still
            meets every departure.
          </p>
        </div>
        <button
          className="button secondary"
          disabled={!!ui.busy || data.history_records > 0}
          onClick={study}
        >
          Check capacity
        </button>
      </div>
      {data.history_records > 0 && (
        <p className="comparison-note">Restart the scenario to check the whole day's capacity.</p>
      )}
      {error && (
        <p className="comparison-note warn-text" role="alert">
          {error}
        </p>
      )}
      {best && (
        <p className="capacity-result">
          <strong>
            {best.chargers} chargers · {number(best.connection_kw || 0, 2)} kW
          </strong>
          Meet every departure in this roster.{" "}
          {smallest
            ? "This is the smallest checked charger count."
            : "Smaller options still need checking."}
        </p>
      )}
      {noneFit && (
        <p className="comparison-note">
          The tested charger counts cannot meet every departure with fixed plugs. More plugs or a
          changed roster are needed.
        </p>
      )}
      {!best && rows.length > 0 && !noneFit && (
        <p className="comparison-note">
          The calculation did not finish for every option. See the proof for the checked results.
        </p>
      )}
      {rows.length > 0 && <CapacityProof rows={rows} />}
    </section>
  );
}
