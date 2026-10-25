import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function EventSimulator({ station, onSubmit, busy }) {
  const [type, setType] = useState("CHARGER_FAILED");
  const [chargerId, setChargerId] = useState(station?.chargers?.[0]?.charger_id || "CH-01");
  const [start, setStart] = useState("2019-01-07T12:00:00Z");
  const [end, setEnd] = useState("2019-01-07T16:00:00Z");
  const [addPrice, setAddPrice] = useState(0.1);
  const chargers = station?.chargers || [];

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
        <Label>Simulated event</Label>
        <select
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
          <Label>Charger</Label>
          <select
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
        <Label>{type === "CHARGER_RECOVERED" ? "Recovery time (UTC ISO)" : "Start (UTC ISO)"}</Label>
        <Input value={start} disabled={busy} onChange={(e) => setStart(e.target.value)} />
      </div>
      {type !== "CHARGER_RECOVERED" ? (
        <div className="grid gap-2">
          <Label>End (UTC ISO)</Label>
          <Input value={end} disabled={busy} onChange={(e) => setEnd(e.target.value)} />
        </div>
      ) : null}
      {type === "PRICE_CHANGED" ? (
        <div className="grid gap-2">
          <Label>Add EUR/kWh</Label>
          <Input
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
