import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { FileUp, RefreshCw, ShieldCheck, X } from "lucide-react";
import type { Charger, SimEvent, Station, Workspace } from "../types";
import { isoInput, localInput } from "../format";

export function Modal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const focusable = () => [
      ...(dialog.current?.querySelectorAll<HTMLElement>(
        "button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href]",
      ) || []),
    ];
    focusable()[0]?.focus();
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      if (event.key === "Tab") {
        const nodes = focusable();
        const first = nodes[0],
          last = nodes[nodes.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }
    };
    window.addEventListener("keydown", handler);
    return () => {
      window.removeEventListener("keydown", handler);
      previous?.focus();
    };
  }, [onClose]);
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <section
        ref={dialog}
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-heading">
          <h2>{title}</h2>
          <button className="icon-button" aria-label="Close dialog" onClick={onClose}>
            <X size={20} />
          </button>
        </div>
        {children}
      </section>
    </div>
  );
}

export function UploadForm({
  disabled,
  onSubmit,
}: {
  disabled: boolean;
  onSubmit: (form: FormData) => void;
}) {
  return (
    <form
      className="form-stack"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit(new FormData(event.currentTarget));
      }}
    >
      <p className="muted">
        Upload 1–100 sessions. Each CSV can be up to 2 MiB. Times need explicit timezone offsets. A
        successful upload starts a fresh simulation.
      </p>
      <label>
        Charging sessions CSV
        <input name="sessions" type="file" accept=".csv,text/csv" required disabled={disabled} />
      </label>
      <div className="schema-example">
        vehicle_id, arrival_time, departure_time,
        <br />
        energy_required_kwh, max_charging_power_kw
      </div>
      <label>
        Prices CSV{" "}
        <span className="muted">(optional if the current price range covers your sessions)</span>
        <input name="prices" type="file" accept=".csv,text/csv" disabled={disabled} />
      </label>
      <p className="form-help">
        Price columns: timestamp, price_eur_per_kwh. Supply one price for every UTC quarter-hour in
        your session range.
      </p>
      <div className="download-links">
        <a href="/api/demo/sessions">Sample sessions</a>
        <a href="/api/demo/prices">Sample prices</a>
      </div>
      <button className="button primary" type="submit" disabled={disabled}>
        <FileUp size={17} />
        Validate & calculate
      </button>
    </form>
  );
}

export function StationForm({
  station,
  disabled,
  onSubmit,
}: {
  station: Station;
  disabled: boolean;
  onSubmit: (value: Station) => void;
}) {
  const [cap, setCap] = useState(station.station_power_limit_kw),
    [efficiency, setEfficiency] = useState(station.charging_efficiency);
  const [chargers, setChargers] = useState<Charger[]>(station.chargers.map((c) => ({ ...c })));
  function setCharger(index: number, value: Partial<Charger>) {
    setChargers((previous) => previous.map((c, i) => (i === index ? { ...c, ...value } : c)));
  }
  return (
    <form
      className="form-stack"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit({
          ...station,
          station_power_limit_kw: cap,
          charging_efficiency: efficiency,
          chargers,
        });
      }}
    >
      <p className="muted">
        Changes apply to future charging. Delivered energy is preserved and the new plan is checked
        before activation.
      </p>
      <div className="form-columns">
        <label>
          Station power limit (kW)
          <input
            type="number"
            min="0.1"
            max="10000"
            step="0.1"
            value={cap}
            onChange={(e) => setCap(Number(e.target.value))}
            required
          />
        </label>
        <label>
          Charging efficiency (0–1)
          <input
            type="number"
            min="0.01"
            max="1"
            step="0.01"
            value={efficiency}
            onChange={(e) => setEfficiency(Number(e.target.value))}
            required
          />
        </label>
      </div>
      <div className="charger-editor">
        {chargers.map((charger, index) => (
          <div key={charger.charger_id}>
            <label className="checkbox-label">
              <input
                type="checkbox"
                aria-label={`${charger.charger_id} available`}
                checked={charger.available}
                onChange={(e) => setCharger(index, { available: e.target.checked })}
              />
              {charger.charger_id}
            </label>
            <input
              aria-label={`${charger.charger_id} power kW`}
              type="number"
              min="0.1"
              max="1000"
              step="0.1"
              value={charger.max_power_kw}
              onChange={(e) => setCharger(index, { max_power_kw: Number(e.target.value) })}
              required
            />
            <span>kW</span>
            <select
              aria-label={`${charger.charger_id} connector`}
              value={charger.connector_type}
              onChange={(e) => setCharger(index, { connector_type: e.target.value })}
            >
              <option>Type2</option>
              <option>CCS</option>
              {!["Type2", "CCS"].includes(charger.connector_type) && (
                <option>{charger.connector_type}</option>
              )}
            </select>
          </div>
        ))}
      </div>
      <button className="button primary" type="submit" disabled={disabled}>
        <ShieldCheck size={17} />
        Save & replan
      </button>
    </form>
  );
}

export function EventForm({
  workspace,
  disabled,
  onSubmit,
}: {
  workspace: Workspace;
  disabled: boolean;
  onSubmit: (event: SimEvent) => void;
}) {
  const [type, setType] = useState<SimEvent["type"]>("CHARGER_FAILED");
  const [charger, setCharger] = useState(workspace.station.chargers[0].charger_id);
  const [start, setStart] = useState(localInput(workspace.now)),
    [end, setEnd] = useState(localInput(workspace.horizon_end)),
    [price, setPrice] = useState(0.2);
  useEffect(() => {
    const offset = type === "PRICE_CHANGED" ? 9 : 3;
    const begin = Math.max(
      Date.parse(workspace.now),
      Math.min(
        Date.parse(workspace.now) + offset * 3600000,
        Date.parse(workspace.horizon_end) - 900000,
      ),
    );
    setStart(localInput(new Date(begin).toISOString()));
    setEnd(
      localInput(
        new Date(Math.min(begin + 3 * 3600000, Date.parse(workspace.horizon_end))).toISOString(),
      ),
    );
  }, [type, workspace.now, workspace.horizon_end]);
  return (
    <form
      className="form-stack"
      onSubmit={(event) => {
        event.preventDefault();
        const value: SimEvent = { event_id: crypto.randomUUID(), type };
        if (type === "CHARGER_RECOVERED") {
          value.time = isoInput(start);
          value.charger_id = charger;
        } else {
          value.start_time = isoInput(start);
          value.end_time = isoInput(end);
          if (type === "CHARGER_FAILED") value.charger_id = charger;
          else value.add_eur_per_kwh = price;
        }
        onSubmit(value);
      }}
    >
      <p className="muted">
        Apply a future event to this simulation. Both schedules are recalculated under the same
        changed conditions.
      </p>
      <label>
        Event type
        <select value={type} onChange={(e) => setType(e.target.value as SimEvent["type"])}>
          <option value="CHARGER_FAILED">Charger outage</option>
          <option value="CHARGER_RECOVERED">Charger recovery</option>
          <option value="PRICE_CHANGED">Electricity price change</option>
        </select>
      </label>
      {type !== "PRICE_CHANGED" && (
        <label>
          Charger
          <select value={charger} onChange={(e) => setCharger(e.target.value)}>
            {workspace.station.chargers.map((c) => (
              <option key={c.charger_id}>{c.charger_id}</option>
            ))}
          </select>
        </label>
      )}
      <label>
        {type === "CHARGER_RECOVERED" ? "Recovery time" : "Start time"} (UTC)
        <input
          type="datetime-local"
          value={start}
          min={localInput(workspace.now)}
          max={localInput(workspace.horizon_end)}
          onChange={(e) => setStart(e.target.value)}
          required
        />
      </label>
      {type !== "CHARGER_RECOVERED" && (
        <label>
          End time (UTC)
          <input
            type="datetime-local"
            value={end}
            min={start}
            max={localInput(workspace.horizon_end)}
            onChange={(e) => setEnd(e.target.value)}
            required
          />
        </label>
      )}
      {type === "PRICE_CHANGED" && (
        <label>
          Price adjustment (EUR/kWh)
          <input
            type="number"
            value={price}
            min="-10"
            max="100"
            step="0.01"
            onChange={(e) => setPrice(Number(e.target.value))}
            required
          />
        </label>
      )}
      <button className="button primary" type="submit" disabled={disabled}>
        <RefreshCw size={17} />
        Apply event & replan
      </button>
    </form>
  );
}
