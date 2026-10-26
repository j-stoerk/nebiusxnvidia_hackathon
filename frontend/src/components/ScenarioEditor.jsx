import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Field, SelectField, utcInput, utcTime } from "@/components/fields";
import StationSettings from "@/components/StationSettings";

const copy = data => structuredClone({ sessions: data.sessions, prices: data.prices, station: data.station });

function VehicleFields({ session: s, index, chargers, onChange, onRemove }) {
  function set(key, value) {
    const next = { ...s, [key]: value };
    if (key === "requested_soc" && typeof value === "number" && next.battery_capacity_kwh && next.initial_soc != null)
      next.energy_required_kwh = Number((next.battery_capacity_kwh * (value - next.initial_soc)).toFixed(6));
    else if (["energy_required_kwh", "battery_capacity_kwh", "initial_soc"].includes(key) && next.battery_capacity_kwh && typeof next.initial_soc === "number")
      next.requested_soc = next.initial_soc + next.energy_required_kwh / next.battery_capacity_kwh;
    onChange(next);
  }
  const number = (key, label, min, max) => <Field label={label} type="number" min={min} max={max} required value={s[key] ?? ""} onChange={v => set(key, v)} />;
  return <article className="space-y-4 rounded-md border border-border p-4">
    <div className="flex items-center justify-between"><h3 className="text-sm font-semibold">Vehicle {index + 1}</h3><Button type="button" variant="ghost" size="sm" onClick={onRemove}>Remove vehicle</Button></div>
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <Field label="Vehicle ID" value={s.vehicle_id} maxLength={80} required onChange={v => set("vehicle_id", v)} />
      <Field label="Arrival (UTC)" type="datetime-local" step={1} value={utcInput(s.arrival_time)} required onChange={v => set("arrival_time", utcTime(v))} />
      <Field label="Departure (UTC)" type="datetime-local" step={1} value={utcInput(s.departure_time)} required onChange={v => set("departure_time", utcTime(v))} />
      {number("energy_required_kwh", "Battery energy required (kWh)", 0, 1000)}
      {number("max_charging_power_kw", "Vehicle charging limit (kW)", .01, 1000)}
      <SelectField label="Bound charger" value={s.charger_id || ""} onChange={v => set("charger_id", v || null)}><option value="">Automatic assignment</option>{chargers.map((c, i) => <option key={i} value={c.charger_id}>{c.charger_id}</option>)}</SelectField>
    </div>
    <details><summary className="text-xs font-medium text-muted-foreground">Battery, taper and connector</summary>
      <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Field label="Vehicle connector" value={s.connector_type} maxLength={40} required onChange={v => set("connector_type", v)} />
        {number("transition_soc", "Taper transition SoC (0–1)", .001, .999)}
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={s.battery_capacity_kwh != null} onChange={e => onChange({ ...s, battery_capacity_kwh: e.target.checked ? "" : null, initial_soc: e.target.checked ? "" : null, requested_soc: null })} />Model battery SoC and taper</label>
        {s.battery_capacity_kwh != null && <>
          {number("battery_capacity_kwh", "Battery capacity (kWh)", .01, 2000)}
          {number("initial_soc", "Initial SoC (0–1)", 0, 1)}
          <Field label="Target SoC (0–1)" type="number" min={0} max={1} value={s.requested_soc ?? ""} onChange={v => set("requested_soc", v === "" ? null : v)} />
        </>}
      </div><p className="mt-2 text-xs text-muted-foreground">Energy and target SoC stay linked when battery details are supplied. Leave battery modelling off if telemetry is unknown.</p>
    </details>
  </article>;
}

function PriceFields({ prices, sessions, onChange }) {
  const [page, setPage] = useState(0), [flat, setFlat] = useState(.2);
  const pageCount = Math.max(1, Math.ceil(prices.length / 48));
  const current = Math.min(page, pageCount - 1);
  function fill() {
    const start = Math.floor(Math.min(...sessions.map(s => Date.parse(s.arrival_time))) / 900000) * 900000;
    const end = Math.max(...sessions.map(s => Date.parse(s.departure_time)));
    if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start || end - start > 72 * 3600000) return;
    const rows = [];
    for (let t = start; t < end; t += 900000) rows.push({ timestamp: new Date(t).toISOString(), price_eur_per_kwh: Number(flat) });
    onChange(rows); setPage(0);
  }
  return <div className="space-y-4">
    <p className="text-sm text-muted-foreground">Edit every interval, including negative prices. Changing the roster’s dates needs a matching quarter-hour grid.</p>
    <div className="flex flex-wrap items-end gap-3"><Field label="Flat price (EUR/kWh)" type="number" min={-10} max={100} value={flat} onChange={setFlat} /><Button type="button" variant="outline" onClick={fill} disabled={flat === ""}>Replace grid with flat price</Button></div>
    <div className="space-y-2">{prices.slice(current * 48, (current + 1) * 48).map((p, offset) => <div key={current * 48 + offset} className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] items-end gap-3">
      <Field label="Interval start (UTC)" type="datetime-local" step={900} value={utcInput(p.timestamp)} required onChange={v => onChange(prices.map((row, i) => i === current * 48 + offset ? { ...row, timestamp: utcTime(v) } : row))} />
      <Field label="Price (EUR/kWh)" type="number" min={-10} max={100} value={p.price_eur_per_kwh} required onChange={v => onChange(prices.map((row, i) => i === current * 48 + offset ? { ...row, price_eur_per_kwh: v } : row))} />
      <Button type="button" variant="ghost" onClick={() => onChange(prices.filter((_, i) => i !== current * 48 + offset))}>Remove</Button>
    </div>)}</div>
    <div className="flex flex-wrap items-center gap-3"><Button type="button" variant="outline" disabled={prices.length >= 2000} onClick={() => onChange([...prices, { timestamp: new Date(Date.parse(prices.at(-1)?.timestamp || sessions[0].arrival_time) + 900000).toISOString(), price_eur_per_kwh: Number(flat) }])}>Add interval</Button>
      <Button type="button" variant="ghost" disabled={!current} onClick={() => setPage(current - 1)}>Previous</Button><span className="text-xs text-muted-foreground">Page {current + 1} of {pageCount} · {prices.length} intervals</span><Button type="button" variant="ghost" disabled={current + 1 >= pageCount} onClick={() => setPage(current + 1)}>Next</Button>
    </div>
  </div>;
}

export default function ScenarioEditor({ data, busy, onSave }) {
  const [draft, setDraft] = useState(null), [dirty, setDirty] = useState(false), [section, setSection] = useState("Vehicles");
  useEffect(() => { if (data && !dirty) setDraft(copy(data)); }, [data, dirty]);
  if (!draft) return null;
  const set = (key, value) => { setDraft(previous => ({ ...previous, [key]: value })); setDirty(true); };
  function invalid(e) {
    const part = e.target.closest("[data-section]");
    if (part) setSection(part.dataset.section);
    e.target.closest("details")?.setAttribute("open", "");
  }
  return <form noValidate onInvalidCapture={invalid} onSubmit={async e => {
    e.preventDefault();
    const bad = [...e.currentTarget.querySelectorAll("input,select")].find(input => !input.checkValidity());
    if (bad) { requestAnimationFrame(() => { bad.focus(); bad.reportValidity(); }); return; }
    if (await onSave(draft)) setDirty(false);
  }} className="space-y-5">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div><h2 className="text-base font-semibold">Edit scenario inputs</h2><p className="mt-1 text-xs text-muted-foreground">Applying a draft starts a new simulation and clears events and delivery history.</p></div>
      <div className="flex gap-2"><Button type="button" variant="outline" disabled={busy || !dirty} onClick={() => { setDirty(false); setDraft(copy(data)); }}>Discard changes</Button><Button type="submit" disabled={busy}>Apply & recalculate{dirty ? " *" : ""}</Button></div>
    </div>
    <fieldset disabled={busy} className="min-w-0 space-y-4">
      <div className="flex flex-wrap gap-2">{["Vehicles", "Prices", "Station"].map(name => <Button key={name} type="button" variant={section === name ? "secondary" : "ghost"} aria-pressed={section === name} onClick={() => setSection(name)}>{name}</Button>)}</div>
      <div data-section="Vehicles" hidden={section !== "Vehicles"} className="space-y-4">{draft.sessions.map((s, index) => <VehicleFields key={index} session={s} index={index} chargers={draft.station.chargers} onChange={value => set("sessions", draft.sessions.map((row, i) => i === index ? value : row))} onRemove={() => { if (draft.sessions.length > 1) set("sessions", draft.sessions.filter((_, i) => i !== index)); }} />)}
        <Button type="button" variant="outline" disabled={draft.sessions.length >= 100} onClick={() => { const template = draft.sessions.at(-1); let n = draft.sessions.length + 1; while (draft.sessions.some(s => s.vehicle_id === `VAN-${n}`)) n++; set("sessions", [...draft.sessions, { vehicle_id: `VAN-${n}`, arrival_time: template.arrival_time, departure_time: template.departure_time, energy_required_kwh: 10, max_charging_power_kw: 11, charger_id: null, connector_type: "Type2", transition_soc: .8, battery_capacity_kwh: null, initial_soc: null, requested_soc: null }]); }}>Add vehicle</Button>
      </div>
      <div data-section="Prices" hidden={section !== "Prices"}><PriceFields prices={draft.prices} sessions={draft.sessions} onChange={v => set("prices", v)} /></div>
      <div data-section="Station" hidden={section !== "Station"}><StationSettings station={draft.station} busy={busy} onChange={v => set("station", v)} /></div>
    </fieldset>
  </form>;
}
