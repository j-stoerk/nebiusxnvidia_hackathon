import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Field, SelectField } from "@/components/fields";
import ListPager, { usePage } from "@/components/ListPager";

function NumberField({ id, label, value, onChange, busy, min = 0, max, step = "any" }) {
  return <div className="grid gap-2"><Label htmlFor={id}>{label}</Label>
    <Input id={id} type="number" required min={min} max={max} step={step} value={value} disabled={busy} onChange={e => onChange(e.target.value === "" ? "" : Number(e.target.value))} /></div>;
}

export default function StationSettings({ station: form, onChange: setForm, busy }) {
  const inventory = usePage(form?.chargers || []);
  if (!form) return null;
  const set = (key, value) => setForm({ ...form, [key]: value });
  const tariff = (key, value) => set("demand_tariff", { ...form.demand_tariff, [key]: value });
  function count(value) {
    if (!Number.isSafeInteger(value) || value < 1) { set("charger_count", value); return; }
    const chargers = form.chargers.slice(0, value);
    const used = new Set(form.chargers.map(c => c.charger_id));
    while (chargers.length < value) {
      let n = chargers.length + 1;
      while (used.has(`CH-${String(n).padStart(2, "0")}`)) n++;
      const charger_id = `CH-${String(n).padStart(2, "0")}`;
      used.add(charger_id);
      chargers.push({ charger_id, max_power_kw: form.charger_max_power_kw, connector_type: "Type2", available: true, simulated: true });
    }
    setForm({ ...form, chargers, charger_count: value });
  }
  function port(index, key, value) {
    setForm({ ...form, chargers: form.chargers.map((c, i) => i === index ? { ...c, [key]: value } : c) },
      key === "charger_id" ? { from: form.chargers[index].charger_id, to: value } : null);
  }
  return <div className="grid gap-4 sm:grid-cols-2">
    <Field label="Station ID" value={form.station_id} required onChange={v => set("station_id", v)} />
    <NumberField id="new-port-power" label="Default power for new chargers (kW)" value={form.charger_max_power_kw} min={.1} max={1000} step="any" busy={busy} onChange={v => set("charger_max_power_kw", v)} />
    <NumberField id="site-power" label="Available EV charging power (kW)" value={form.station_power_limit_kw} min={.1} busy={busy} onChange={v => set("station_power_limit_kw", v)} />
    <NumberField id="charger-count" label="Number of chargers" value={form.charger_count} min={1} step={1} busy={busy} onChange={count} />
    <NumberField id="efficiency" label="Charging efficiency (0–1)" value={form.charging_efficiency} min={.000001} max={1} busy={busy} onChange={v => set("charging_efficiency", v)} />
    <NumberField id="demand-rate" label="Demand tariff (EUR/kW per billing period)" value={form.demand_tariff.eur_per_kw} busy={busy} onChange={v => tariff("eur_per_kw", v)} />
    <NumberField id="prior-peak" label="Prior billing peak (kW)" value={form.demand_tariff.prior_peak_kw} busy={busy} onChange={v => tariff("prior_peak_kw", v)} />
    <SelectField label="Demand billing period" value={form.demand_tariff.period} onChange={v => set("demand_tariff", { ...form.demand_tariff, period: v, prior_peaks_kw: {} })}><option value="month">Month</option><option value="year">Year</option></SelectField>
    <SelectField label="Billing timezone" value={form.demand_tariff.timezone} onChange={v => tariff("timezone", v)}><option>Europe/Berlin</option><option>UTC</option></SelectField>
    <div className="grid gap-2"><Label htmlFor="objective">Planning goal</Label><select id="objective" className="h-10 rounded-md border border-border bg-card px-3 text-sm" value={form.optimization_goal || "cost"} disabled={busy} onChange={e => set("optimization_goal", e.target.value)}>
      <option value="cost">Lowest energy + demand cost</option><option value="peak">Lowest peak, then cost</option>
    </select><p className="text-xs text-muted-foreground">Meeting energy targets takes priority in both modes.</p></div>
    <details open className="rounded-md border border-border p-3 sm:col-span-2"><summary className="cursor-pointer text-sm font-medium">Charger inventory</summary>
      <div className="my-3 flex flex-wrap gap-3"><Button type="button" variant="outline" onClick={() => { count(form.chargers.length + 1); inventory.setPage(Math.floor(form.chargers.length / 10)); }}>Add charger</Button>
        <Button type="button" variant="ghost" onClick={() => set("chargers", form.chargers.map(c => ({ ...c, max_power_kw: form.charger_max_power_kw })))}>Apply default kW to all chargers</Button></div>
      <ListPager list={inventory} name="chargers" />
      <div className="mt-3 grid gap-4">{inventory.rows.map((c, offset) => { const i = inventory.offset + offset; return <div key={i} className="grid items-end gap-3 border-b border-border pb-3 sm:grid-cols-2 lg:grid-cols-4">
        <Field label={`Charger ${i + 1} ID`} value={c.charger_id} required onChange={v => port(i, "charger_id", v)} />
        <NumberField id={`port-${i}`} label={`${c.charger_id} power (kW)`} value={c.max_power_kw} min={.1} busy={busy} onChange={v => port(i, "max_power_kw", v)} />
        <Field label={`${c.charger_id} connector`} value={c.connector_type} required maxLength={40} onChange={v => port(i, "connector_type", v)} />
        <Label className="flex min-h-10 items-center gap-2"><input type="checkbox" checked={c.available} disabled={busy} onChange={e => port(i, "available", e.target.checked)} />Available for charging</Label>
        <Button type="button" variant="ghost" disabled={form.chargers.length === 1} onClick={() => { const chargers = form.chargers.filter((_, index) => index !== i); setForm({ ...form, chargers, charger_count: chargers.length }); }}>Remove charger {c.charger_id}</Button>
      </div>; })}</div>
      <ListPager list={inventory} name="chargers" />
    </details>
    <div className="flex items-center gap-3"><Switch id="fixed-plugs" checked={form.fixed_connections} disabled={busy} onCheckedChange={v => set("fixed_connections", v)} /><Label htmlFor="fixed-plugs">Keep vehicles on their plugs until departure</Label></div>
    <details className="rounded-md border border-border p-3 sm:col-span-2"><summary className="text-sm font-medium">Prior peaks by billing period</summary>
      <p className="my-2 text-xs text-muted-foreground">Overrides the fallback above. Enter YYYY-MM for monthly billing, YYYY for annual. Changing billing period clears overrides.</p>
      {Object.entries(form.demand_tariff.prior_peaks_kw).map(([period, value], index) => <div key={index} className="my-2 grid grid-cols-[1fr_1fr_auto] items-end gap-2">
        <Field label="Billing period" value={period} required onChange={v => { const entries = Object.entries(form.demand_tariff.prior_peaks_kw); entries[index] = [v, value]; tariff("prior_peaks_kw", Object.fromEntries(entries)); }} />
        <Field label="Prior peak (kW)" type="number" min={0} max={100000} value={value} required onChange={v => tariff("prior_peaks_kw", { ...form.demand_tariff.prior_peaks_kw, [period]: v })} />
        <Button type="button" variant="ghost" onClick={() => tariff("prior_peaks_kw", Object.fromEntries(Object.entries(form.demand_tariff.prior_peaks_kw).filter(([k]) => k !== period)))}>Remove</Button>
      </div>)}
      <Button type="button" variant="outline" size="sm" disabled={Object.keys(form.demand_tariff.prior_peaks_kw).length >= 24} onClick={() => { let n = 2026; while ((form.demand_tariff.period === "month" ? `${n}-01` : String(n)) in form.demand_tariff.prior_peaks_kw) n++; tariff("prior_peaks_kw", { ...form.demand_tariff.prior_peaks_kw, [form.demand_tariff.period === "month" ? `${n}-01` : String(n)]: 0 }); }}>Add billing period</Button>
    </details>
    <p className="text-xs text-muted-foreground sm:col-span-2">Scenario times are UTC; meter averages use fixed 15-minute windows. Removing a charger releases its vehicle bindings.</p>
  </div>;
}
