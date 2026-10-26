let version = null;

async function request(path, options = {}) {
  const headers = { ...options.headers };
  if (version !== null && options.method && options.method !== "GET") headers["If-Match"] = String(version);
  const response = await fetch(`/api${path}`, { ...options, headers });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map(e => e.message || (e.msg ? `${e.loc?.slice(1).join(".") || "Input"}: ${e.msg}` : JSON.stringify(e))).join("; ")
          : response.statusText;
    const error = new Error(message || "Request failed");
    error.status = response.status;
    throw error;
  }
  const next = data.workspace || data;
  if (next.state_version !== undefined) version = next.state_version;
  return data;
}

export const api = {
  getState: () => request("/state"),
  getAnalytics: () => request("/analytics"),
  optimize: async (onProgress = () => {}) => {
    const response = await fetch("/api/optimize/stream", { method: "POST", headers: version === null ? {} : { "If-Match": String(version) } });
    if (!response.ok) throw new Error((await response.json()).detail || "Could not start planning");
    const reader = response.body.getReader(), decoder = new TextDecoder();
    let buffer = "", workspace;
    try {
      while (true) {
        const { value, done } = await reader.read();
        buffer += decoder.decode(value, { stream: !done });
        let boundary;
        while ((boundary = buffer.indexOf("\n\n")) >= 0) {
          const event = JSON.parse(buffer.slice(0, boundary).replace(/^data: /, ""));
          buffer = buffer.slice(boundary + 2);
          if (event.type === "error") throw new Error(event.message);
          if (event.type === "result") workspace = event.workspace;
          else await onProgress(event);
        }
        if (done) break;
      }
    } finally { reader.releaseLock(); }
    if (!workspace) throw new Error("The planning stream ended before a checked result arrived");
    version = workspace.state_version;
    return workspace;
  },
  updateScenario: draft => request("/scenario", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(draft) }),
  capacity: (counts) =>
    request("/capacity", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(counts ? { counts } : {}),
    }),
  reset: () => request("/reset", { method: "POST" }),
  updateStation: (station) =>
    request("/station", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ station }),
    }),
  upload: async (sessionsFile, pricesFile) => {
    const form = new FormData();
    form.append("sessions", sessionsFile);
    if (pricesFile) form.append("prices", pricesFile);
    return request("/upload", { method: "POST", body: form });
  },
  simulateEvent: async (event, reoptimize = true, onProgress) => {
    const result = await request("/events", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ event, reoptimize: false }),
    });
    return reoptimize && result.event_result.applied ? { ...await api.optimize(onProgress), event_result: result.event_result } : result;
  },
  chat: (message, allow_changes = false) =>
    request("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, allow_changes }),
    }),
  agentStatus: () => request("/agent/status"),
};
