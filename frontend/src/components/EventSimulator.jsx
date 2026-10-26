import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { utcInput, utcTime } from "@/components/fields";

export default function EventSimulator({ station, sessions, now, onSubmit, busy }) {
  const [type, setType] = useState("CHARGER_FAILED");
  const [chargerId, setChargerId] = useState(station?.chargers?.[0]?.charger_id || "CH-01");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [addPrice, setAddPrice] = useState(0.1);
  const chargers = station?.chargers || [];
  useEffect(() => {
    if (!chargers.some(c => c.charger_id === chargerId)) setChargerId(chargers[0]?.charger_id || "");
  }, [station, chargerId]);
  useEffect(() => {
    if (!sessions?.length) return;
    const a = Date.parse(now || sessions[0].arrival_time), b = Math.max(...sessions.map(s => Date.parse(s.departure_time)));
    setStart(new Date(Math.min(a + 3600000, b - 900000)).toISOString());
    setEnd(new Date(Math.min(a + 7200000, b)).toISOString());
  }, [now, sessions]);

  return (
    <form
      className="grid gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        const event_id = `sim-${Date.now()}`;
        if (type === "PRICE_CHANGED") {
          onSubmit({
            event_id,
            type,
            start_time: start,
            end_time: end,
            add_eur_per_kwh: Number(addPrice),
            simulated: true,
          });
        } else if (type === "CHARGER_RECOVERED") {
          onSubmit({
            event_id,
            type,
            charger_id: chargerId,
            time: start,
            simulated: true,
          });
        } else {
          onSubmit({
            event_id,
            type,
            charger_id: chargerId,
            start_time: start,
            end_time: end,
            simulated: true,
          });
        }
      }}
    >
      <div className="grid gap-2">
        <Label htmlFor="event-type">Simulated event</Label>
        <select
          id="event-type"
          className="h-10 rounded-md border border-border bg-card px-3 text-sm"
          value={type}
          disabled={busy}
          onChange={(e) => setType(e.target.value)}
        >
          <option value="CHARGER_FAILED">Charger unavailable</option>
          <option value="CHARGER_RECOVERED">Charger recovered</option>
          <option value="PRICE_CHANGED">Electricity price increase</option>
        </select>
      </div>
      {type !== "PRICE_CHANGED" ? (
        <div className="grid gap-2">
          <Label htmlFor="event-charger">Charger</Label>
          <select
            id="event-charger"
            className="h-10 rounded-md border border-border bg-card px-3 text-sm"
            value={chargerId}
            disabled={busy}
            onChange={(e) => setChargerId(e.target.value)}
          >
            {chargers.map((c) => (
              <option key={c.charger_id} value={c.charger_id}>
                {c.charger_id} {c.available ? "" : "(disabled)"}
              </option>
            ))}
          </select>
        </div>
      ) : null}
      <div className="grid gap-2">
        <Label htmlFor="event-start">{type === "CHARGER_RECOVERED" ? "Recovery time (UTC)" : "Start (UTC)"}</Label>
        <Input id="event-start" type="datetime-local" step={1} value={utcInput(start)} required disabled={busy} onChange={e => setStart(utcTime(e.target.value))} />
      </div>
      {type !== "CHARGER_RECOVERED" ? (
        <div className="grid gap-2">
          <Label htmlFor="event-end">End (UTC)</Label>
          <Input id="event-end" type="datetime-local" step={1} value={utcInput(end)} required disabled={busy} onChange={e => setEnd(utcTime(e.target.value))} />
        </div>
      ) : null}
      {type === "PRICE_CHANGED" ? (
        <div className="grid gap-2">
          <Label htmlFor="event-price">Add EUR/kWh</Label>
          <Input
            id="event-price"
            type="number"
            step="0.01"
            value={addPrice}
            disabled={busy}
            onChange={(e) => setAddPrice(e.target.value)}
          />
        </div>
      ) : null}
      <Button type="submit" variant="secondary" disabled={busy}>
        Apply event & re-optimize
      </Button>
      <p className="text-xs text-muted-foreground">Labeled simulated — updates in-memory conditions only.</p>
    </form>
  );
}
