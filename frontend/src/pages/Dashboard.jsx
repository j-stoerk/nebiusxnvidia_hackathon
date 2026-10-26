import { LoaderCircle, PlugZap, RefreshCw } from "lucide-react";
import { useState } from "react";
import AgentChat from "@/components/AgentChat";
import CapacityPanel from "@/components/CapacityPanel";
import ChargingTimeline from "@/components/ChargingTimeline";
import CostComparison from "@/components/CostComparison";
import EnergyChart from "@/components/EnergyChart";
import EventSimulator from "@/components/EventSimulator";
import FileUpload from "@/components/FileUpload";
import MetricCard from "@/components/MetricCard";
import RiskList from "@/components/RiskList";
import ScenarioEditor from "@/components/ScenarioEditor";
import OptimizationProgress from "@/components/OptimizationProgress";
import ThemeToggle from "@/components/ThemeToggle";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/api/client";
import brand from "@/assets/brand.svg";
import { eur, formatDuration, kwh, kw, pct, timeLabel } from "@/utils/formatters";

export default function Dashboard({ state, theme }) {
  const { data, busy, error, notice, setNotice, setError, run, setData, setBusy, calculate, simulate, progress } = state;
  const analytics = data?.analytics;
  const optimized = data?.optimized;
  const baseline = data?.baseline;
  const series = optimized?.metrics?.power_series || baseline?.metrics?.power_series || [];
  const allocations = optimized?.allocations || baseline?.allocations || [];
  const sessions = data?.sessions || [];
  const [tab, setTab] = useState("overview");
  const [demoStep, setDemoStep] = useState(0);
  const [editorKey, setEditorKey] = useState(0);
  async function loadSample() {
    const result = await run(() => api.reset(), "Demo sample reloaded");
    if (result) { setDemoStep(0); setEditorKey(value => value + 1); }
  }
  async function importInputs(sessionsFile, prices) {
    const result = await run(() => api.upload(sessionsFile, prices), "CSV validated and loaded");
    if (result) setEditorKey(value => value + 1);
  }
  async function demoNext() {
    const start = new Date(Math.min(...sessions.map(s => new Date(s.arrival_time).getTime())));
    const at = hours => new Date(start.getTime() + hours * 3600000).toISOString();
    const priceEvent = { event_id: "guided-price", type: "PRICE_CHANGED", start_time: at(9), end_time: at(12), add_eur_per_kwh: .2 };
    let result;
    if (demoStep === 0) {
      if (!await run(() => api.reset())) return;
      setEditorKey(value => value + 1);
      result = await run(calculate, "All four policies calculated and independently checked.");
      setTab("overview");
    } else if (demoStep === 1) {
      result = await run(() => simulate({ event_id: "guided-outage", type: "CHARGER_FAILED", charger_id: "CH-01", start_time: at(2), end_time: at(6) }), "Replanned around the outage; inspect the new peak and departure targets.");
      setTab("schedule");
    } else {
      result = await run(() => simulate(priceEvent), demoStep === 2 ? "Price change applied; compare energy and demand cost separately." : "Same event replayed: no duplicate change to the plan.");
      setTab(demoStep === 2 ? "overview" : "operations");
    }
    if (result) setDemoStep(previous => previous + 1);
  }
  const horizon =
    analytics?.earliest_arrival && analytics?.latest_departure
      ? formatDuration(new Date(analytics.latest_departure) - new Date(analytics.earliest_arrival))
      : null;

  return (
    <>
      <div className="border-b border-border bg-card">
        <div className="mx-auto flex min-h-16 max-w-7xl items-center justify-between gap-3 px-4 sm:px-6 lg:px-8">
          <a href="/" className="flex items-center gap-2.5 rounded-sm focus-visible:outline-2 focus-visible:outline-primary" aria-label="ChargeWise home">
            <span className="rounded-sm bg-white p-1"><img src={brand} alt="" width="30" height="30" /></span>
            <span className="text-lg font-semibold tracking-tight">ChargeWise</span>
            <span className="ml-3 hidden border-l border-border pl-4 text-sm text-muted-foreground sm:block">Depot planning</span>
          </a>
          <div className="flex items-center gap-4">
            <span className="hidden text-xs text-muted-foreground sm:block">Simulation workspace</span>
            <ThemeToggle theme={theme.theme} onToggle={theme.toggle} />
          </div>
        </div>
      </div>
    <main className="mx-auto max-w-7xl px-4 py-7 sm:px-6 lg:px-8">
      <header className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span>Fleet operations</span><span aria-hidden="true">/</span><span>Charging planner</span>
            {data?.stale && <Badge variant="warning">Previous plan is stale · recalculate</Badge>}
            {busy ? (
              <Badge variant="secondary" className="gap-1">
                <LoaderCircle className="h-3 w-3 animate-spin" /> Working
              </Badge>
            ) : null}
          </div>
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
            Fleet charging planner
          </h1>
          <p className="mt-2 max-w-xl text-sm text-muted-foreground leading-relaxed">
            Get every van ready within your site’s power limit.
          </p>
          {analytics?.earliest_arrival ? (
            <p className="mt-2 text-xs text-muted-foreground">
              {timeLabel(analytics.earliest_arrival)} → {timeLabel(analytics.latest_departure)}
              {horizon ? ` · span ${horizon}` : ""}
            </p>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" disabled={busy} onClick={() => setTab("inputs")}>Edit inputs</Button>
          <Button
            variant="outline"
            disabled={busy}
            onClick={loadSample}
          >
            <RefreshCw className="h-4 w-4" />
            Load sample
          </Button>
          <Button disabled={busy} onClick={() => run(calculate, "Optimized schedule ready")}>
            Run optimizer
          </Button>
        </div>
      </header>

      {(error || notice) && (
        <div
          role={error ? "alert" : "status"}
          className={`mb-4 flex items-center justify-between gap-3 rounded-md border px-4 py-3 text-sm ${
            error
              ? "border-destructive/30 bg-red-500/10 text-destructive"
              : "border-emerald-500/30 bg-emerald-500/10 text-success"
          }`}
        >
          <span className="min-w-0 break-words">{error || notice}</span>
          <Button
            size="sm"
            variant="ghost"
            className="shrink-0"
            onClick={() => {
              setError(null);
              setNotice(null);
            }}
          >
            Dismiss
          </Button>
        </div>
      )}

      <OptimizationProgress progress={progress} />

      <section className="metrics-strip mb-5" aria-label="Plan summary">
        {[
          { label: "Vehicles", value: analytics?.vehicle_count ?? "—" },
          { label: "Energy required", value: kwh(analytics?.total_energy_required_kwh) },
          {
            label: "Optimized cost",
            value: eur(optimized?.metrics?.cost_eur),
            hint: data?.comparison ? `Savings ${eur(data.comparison.cost_savings_eur)}` : "Run optimize",
          },
          {
            label: "Targets met",
            value: pct(optimized?.metrics?.target_success_percent),
            hint: optimized ? `Unserved ${kwh(optimized.metrics.unserved_kwh)}` : "Shows shortfalls if infeasible",
          },
          {
            label: "Peak power",
            value: kw(optimized?.metrics?.peak_power_kw),
            hint: `${kw(analytics?.station_power_limit_kw)} site limit`,
          },
          {
            label: "Chargers",
            value: `${analytics?.available_chargers ?? "—"} / ${analytics?.total_chargers ?? "—"}`,
            hint: "Simulated availability",
          },
        ].map(m => (
          <MetricCard key={m.label} {...m} />
        ))}
      </section>

      <section className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-card px-5 py-3" aria-label="Guided demo">
        <div><p className="text-sm font-medium">Sample walkthrough <span className="ml-2 text-xs font-normal text-muted-foreground">{Math.min(demoStep + 1, 4)} of 4</span></p><p className="mt-1 text-xs text-muted-foreground">{[
          "Start with equal energy targets and an illustrative demand tariff.",
          "Compare cost and peak, then make CH-01 unavailable from 08:00 to 12:00 UTC.",
          "The plan preserves departures. Next, increase the afternoon electricity price.",
          "Inspect the new costs, then replay the same event to verify idempotency.",
          "Walkthrough complete. Check capacity or ask for a local computed summary.",
        ][demoStep]}</p></div>
        <Button variant="outline" size="sm" disabled={busy || demoStep === 4} onClick={demoNext}>{["Start guided demo", "Simulate outage", "Apply price change", "Replay event", "Complete"][demoStep]}</Button>
      </section>
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList aria-label="Planner sections" className="flex h-auto w-full justify-start gap-x-2 overflow-x-auto">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="inputs">Inputs</TabsTrigger>
          <TabsTrigger value="schedule">Schedule</TabsTrigger>
          <TabsTrigger value="capacity">Capacity</TabsTrigger>
          <TabsTrigger value="operations">Operations</TabsTrigger>
          <TabsTrigger value="agent">Plan assistant</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="grid gap-4 lg:grid-cols-2">
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle>Cost & peak: baseline vs optimized</CardTitle>
              <CardDescription>
                Equal physical limits and targets · {data?.station?.optimization_goal === "peak" ? "peak first, then cost" : "energy + incremental demand cost"}. Efficiency{" "}
                {analytics?.charging_efficiency ?? "—"} · prior peak {kw(analytics?.prior_peak_kw)}.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <CostComparison comparison={data?.comparison} optimized={optimized} baseline={baseline} references={data?.references} />
            </CardContent>
          </Card>

          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle>Station power usage</CardTitle>
              <CardDescription>15-minute meter intervals vs site power limit.</CardDescription>
            </CardHeader>
            <CardContent>
              <EnergyChart series={series} baselineSeries={baseline?.metrics?.power_series} powerLimit={data?.station?.station_power_limit_kw} />
            </CardContent>
          </Card>
          <div className="rounded-lg border border-border bg-card p-5 lg:col-span-2"><Button variant="outline" onClick={() => setTab("inputs")}>Edit scenario inputs</Button><p className="mt-2 text-xs text-muted-foreground">Change vehicles, prices, hardware or tariffs, then recalculate.</p></div>
        </TabsContent>

        <TabsContent forceMount value="inputs" className="space-y-4 data-[state=inactive]:hidden">
          <Card><CardContent className="p-5"><ScenarioEditor key={editorKey} data={data} busy={busy} onSave={async draft => {
            const result = await run(async () => { await api.updateScenario(draft); return calculate(); }, "Your scenario has been calculated and independently checked.");
            if (result) { setDemoStep(0); setTab("overview"); }
            return result;
          }} /></CardContent></Card>
          <Card><CardHeader><CardTitle>Import from CSV instead</CardTitle><CardDescription>Replace vehicle sessions and optional matching prices.</CardDescription></CardHeader><CardContent><FileUpload busy={busy} onUpload={importInputs} /></CardContent></Card>
        </TabsContent>

        <TabsContent value="schedule" className="grid gap-4">
          <Card>
            <CardHeader>
              <div className="flex flex-wrap items-center gap-2">
                <CardTitle>Charging schedule timeline</CardTitle>
                <Badge variant="outline">
                  <PlugZap className="mr-1 h-3 w-3" />
                  {allocations.length} slots
                </Badge>
              </div>
              <CardDescription>
                Vehicle availability windows and assigned charge intervals with HH:MM:SS UTC timing.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ChargingTimeline allocations={allocations} sessions={sessions} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Vehicles at risk</CardTitle>
              <CardDescription>Energy targets not fully served before departure.</CardDescription>
            </CardHeader>
            <CardContent>
              <RiskList atRisk={data?.at_risk || []} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Vehicle energy & SoC</CardTitle>
              <CardDescription>
                Battery capacity, initial/requested SoC, delivered energy, bound charger (fixed plug).
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="max-h-64 overflow-auto rounded-md border border-border">
                <table className="w-full text-left text-xs">
                  <thead className="sticky top-0 bg-muted/90">
                    <tr className="text-muted-foreground">
                      <th className="px-3 py-2">Vehicle</th>
                      <th className="px-3 py-2">Charger</th>
                      <th className="px-3 py-2">Capacity</th>
                      <th className="px-3 py-2">Init SoC</th>
                      <th className="px-3 py-2">Req SoC</th>
                      <th className="px-3 py-2">Final SoC</th>
                      <th className="px-3 py-2">Delivered</th>
                      <th className="px-3 py-2">Target</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(optimized?.metrics?.vehicles || baseline?.metrics?.vehicles || [])
                      .slice(0, 40)
                      .map((v) => (
                        <tr key={v.vehicle_id} className="border-t border-border/70">
                          <td className="px-3 py-2 font-medium">{v.vehicle_id}</td>
                          <td className="px-3 py-2">{v.charger_id || "—"}</td>
                          <td className="px-3 py-2">
                            {v.battery_capacity_kwh != null ? kwh(v.battery_capacity_kwh) : "—"}
                          </td>
                          <td className="px-3 py-2">
                            {v.initial_soc != null ? pct(v.initial_soc * 100) : "—"}
                          </td>
                          <td className="px-3 py-2">
                            {v.requested_soc != null ? pct(v.requested_soc * 100) : "—"}
                          </td>
                          <td className="px-3 py-2">
                            {v.final_soc != null ? pct(v.final_soc * 100) : "—"}
                          </td>
                          <td className="px-3 py-2">{kwh(v.delivered_kwh)}</td>
                          <td className="px-3 py-2">{v.target_met ? "Met" : "Short"}</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="capacity" className="grid gap-4">
          <Card>
            <CardHeader>
              <CardTitle>Capacity planning & proof</CardTitle>
              <CardDescription>
                Smallest charger count and site power that still meet all energy targets.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <CapacityPanel
                study={data?.capacity_study}
                busy={busy}
                onRun={() => run(() => api.capacity(), "Capacity study complete")}
              />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="operations" className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Simulate an event</CardTitle>
              <CardDescription>Charger outage or price spike, then re-optimize.</CardDescription>
            </CardHeader>
            <CardContent>
              <EventSimulator
                station={data?.station}
                sessions={sessions}
                now={data?.now}
                busy={busy}
                onSubmit={(event) =>
                  run(() => simulate(event), "Simulated event applied and re-optimized")
                }
              />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Active plan status</CardTitle>
              <CardDescription>Solver labels and simulated event ledger.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className="flex justify-between gap-3">
                <span className="text-muted-foreground">Optimized solver</span>
                <span className="font-medium">{optimized?.solver_status || "—"}</span>
              </div>
              <div className="flex justify-between gap-3">
                <span className="text-muted-foreground">Baseline</span>
                <span className="font-medium">{baseline?.solver_status || "—"}</span>
              </div>
              <div className="flex justify-between gap-3">
                <span className="text-muted-foreground">Runtime</span>
                <span className="font-medium">
                  {optimized ? `${Number(optimized.runtime_seconds).toFixed(2)}s` : "—"}
                </span>
              </div>
              <Separator />
              <p className="text-xs text-muted-foreground">
                {(data?.events || []).length
                  ? `${data.events.length} simulated event(s) recorded`
                  : "No simulated events yet"}
              </p>
              <ul className="max-h-40 space-y-2 overflow-auto text-xs">
                {(data?.events || []).slice(-8).map((ev) => (
                  <li key={ev.event_id} className="rounded-lg border border-border px-3 py-2">
                    <span className="font-medium">{ev.type}</span>
                    <span className="text-muted-foreground"> · {ev.event_id}</span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="agent">
          <Card>
            <CardHeader>
              <CardTitle>Plan assistant</CardTitle>
              <CardDescription>
                Readiness, costs and constraints from checked results. Local summaries work offline;
                optional NVIDIA Nemotron explains the plan when a model is connected.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <AgentChat busy={busy} setBusy={setBusy} onWorkspace={(workspace) => setData(workspace)} />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
      <footer className="mt-8 flex flex-wrap justify-between gap-2 border-t border-border pt-4 text-xs text-muted-foreground">
        <span>ChargeWise · Fleet charging decisions</span><span>Planning simulation · All times UTC</span>
      </footer>
    </main>
    </>
  );
}
