import type { SimEvent, Workspace } from "./types";

export async function api<T>(path: string, body?: unknown, method = "POST"): Promise<T> {
  const form = body instanceof FormData;
  const response = await fetch("/api" + path, {
    method: body === undefined && method === "POST" ? "GET" : method,
    headers: body !== undefined && !form ? { "Content-Type": "application/json" } : undefined,
    body: body === undefined ? undefined : form ? body : JSON.stringify(body),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const detail = payload.detail;
    const message = Array.isArray(detail)
      ? detail
          .slice(0, 8)
          .map(
            (e: { row?: number; column?: string; message?: string; msg?: string }) =>
              `${e.row ? `Row ${e.row}: ` : ""}${e.column ? `${e.column}: ` : ""}${e.message || e.msg || "Invalid value"}`,
          )
          .join("\n")
      : typeof detail === "string"
        ? detail
        : `Request failed (${response.status})`;
    throw new Error(message);
  }
  return response.json();
}

export const createWorkspace = (demo = "capacity") => api<Workspace>("/workspaces", { demo });

/** Every state change carries the version that the operator actually viewed. */
export const updateWorkspace = (data: Workspace, endpoint: string, fields = {}, method = "POST") =>
  api<Workspace>(
    `/workspaces/${data.workspace_id}/${endpoint}`,
    { expected_version: data.state_version, ...fields },
    method,
  );

export async function guideStep(data: Workspace, step: number) {
  if (step === 0) return updateWorkspace(data, "optimize");
  const { scenarios } = await api<{ scenarios: Record<string, SimEvent[]> }>("/demo/scenarios");
  const offset =
    new Date(data.horizon_start).setUTCHours(0, 0, 0, 0) - Date.parse("2019-01-07T00:00:00Z");
  const source = step === 2 ? scenarios.price_spike[0] : scenarios.charger_outage[0];
  const event = Object.fromEntries(
    Object.entries(source).map(([key, value]) => [
      key,
      ["start_time", "end_time", "time"].includes(key) && value
        ? new Date(Date.parse(String(value)) + offset).toISOString()
        : value,
    ]),
  );
  // Reuse the original event ID for the replay; a new ID would apply it twice.
  const next = await updateWorkspace(data, "events", {
    event,
  });
  if (
    step === 3 &&
    (next.state_version !== data.state_version || next.schedule_version !== data.schedule_version)
  ) {
    throw new Error("Duplicate event replay unexpectedly changed the plan");
  }
  return next;
}
