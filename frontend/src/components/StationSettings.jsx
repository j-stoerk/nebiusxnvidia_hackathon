import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

function NumberField({ id, label, value, onChange, busy, min = 0, max, step = .1 }) {
  return <div className="grid gap-2"><Label htmlFor={id}>{label}</Label>
    <Input id={id} type="number" required min={min} max={max} step={step} value={value} disabled={busy} onChange={e => onChange(Number(e.target.value))} /></div>;
}

export default function StationSettings({ station, onSave, busy }) {
  const [form, setForm] = useState(null);
  useEffect(() => { if (station) setForm(structuredClone(station)); }, [station]);
  if (!form) return null;
  const set = (key, value) => setForm(previous => ({ ...previous, [key]: value }));
  const tariff = (key, value) => set("demand_tariff", { ...form.demand_tariff, [key]: value });
  function count(value) {
    const chargers = Array.from({ length: value }, (_, i) => form.chargers[i] || {
      charger_id: `CH-${String(i + 1).padStart(2, "0")}`, max_power_kw: form.charger_max_power_kw,
      connector_type: "Type2", available: true, simulated: true,
    });
    setForm({ ...form, chargers, charger_count: value });
  }
  function port(index, key, value) {
    set("chargers", form.chargers.map((c, i) => i === index ? { ...c, [key]: value } : c));
  }
  return <form className="grid gap-4" onSubmit={e => { e.preventDefault(); onSave(form); }}>
    <NumberField id="site-power" label="Available EV charging power (kW)" value={form.station_power_limit_kw} min={.1} busy={busy} onChange={v => set("station_power_limit_kw", v)} />
    <NumberField id="charger-count" label="Number of chargers" value={form.chargers.length} min={1} max={50} step={1} busy={busy} onChange={v => count(Math.max(1, Math.min(50, Math.floor(v))))} />
    <NumberField id="efficiency" label="Charging efficiency (0–1)" value={form.charging_efficiency} min={.01} max={1} step={.01} busy={busy} onChange={v => set("charging_efficiency", v)} />
    <NumberField id="demand-rate" label="Demand tariff (EUR/kW per billing period)" value={form.demand_tariff.eur_per_kw} busy={busy} onChange={v => tariff("eur_per_kw", v)} />
    <NumberField id="prior-peak" label="Prior billing peak (kW)" value={form.demand_tariff.prior_peak_kw} busy={busy} onChange={v => tariff("prior_peak_kw", v)} />
    <div className="grid gap-2"><Label htmlFor="objective">Planning goal</Label><select id="objective" className="h-10 rounded-xl border border-border bg-card px-3 text-sm" value={form.optimization_goal || "cost"} disabled={busy} onChange={e => set("optimization_goal", e.target.value)}>
      <option value="cost">Lowest energy + demand cost</option><option value="peak">Lowest peak, then cost</option>
    </select><p className="text-xs text-muted-foreground">Meeting energy targets takes priority in both modes.</p></div>
    <details className="rounded-xl border border-border p-3"><summary className="cursor-pointer text-sm font-medium">Charger inventory</summary>
      <div className="mt-3 grid gap-4">{form.chargers.map((c, i) => <div key={c.charger_id} className="grid gap-2 border-b border-border pb-3">
        <NumberField id={`port-${i}`} label={`${c.charger_id} power (kW)`} value={c.max_power_kw} min={.1} busy={busy} onChange={v => port(i, "max_power_kw", v)} />
        <Label htmlFor={`connector-${i}`}>Connector</Label><Input id={`connector-${i}`} value={c.connector_type} disabled={busy} onChange={e => port(i, "connector_type", e.target.value)} />
        <Label className="flex items-center gap-2"><input type="checkbox" checked={c.available} disabled={busy} onChange={e => port(i, "available", e.target.checked)} />{c.charger_id} administratively available</Label>
      </div>)}</div>
    </details>
    <div className="flex items-center gap-3"><Switch id="fixed-plugs" checked={form.fixed_connections} disabled={busy} onCheckedChange={v => set("fixed_connections", v)} /><Label htmlFor="fixed-plugs">Keep vehicles on their plugs until departure</Label></div>
    <Button type="submit" variant="secondary" disabled={busy}>Save station settings</Button>
    <p className="text-xs text-muted-foreground">Simulated planning · 15-minute meter averages · incremental demand charges above the declared prior peak.</p>
  </form>;
}
