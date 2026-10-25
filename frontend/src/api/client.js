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
          ? detail.map((e) => e.message || JSON.stringify(e)).join("; ")
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
  optimize: () => request("/optimize", { method: "POST" }),
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
  simulateEvent: (event, reoptimize = true) =>
    request("/events", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ event, reoptimize }),
    }),
  chat: (message, allow_changes = false) =>
    request("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, allow_changes }),
    }),
  agentStatus: () => request("/agent/status"),
};
