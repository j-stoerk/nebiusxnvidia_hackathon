import type { Workspace } from "./types";

export async function api<T>(
  path: string,
  body?: unknown,
  method = "POST",
): Promise<T> {
  const form = body instanceof FormData;
  const response = await fetch("/api" + path, {
    method: body === undefined && method === "POST" ? "GET" : method,
    headers:
      body !== undefined && !form
        ? { "Content-Type": "application/json" }
        : undefined,
    body: body === undefined ? undefined : form ? body : JSON.stringify(body),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const detail = payload.detail;
    const message = Array.isArray(detail)
      ? detail
          .slice(0, 8)
          .map(
            (e: {
              row?: number;
              column?: string;
              message?: string;
              msg?: string;
            }) =>
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

export const createWorkspace = (demo = "normal") =>
  api<Workspace>("/workspaces", { demo });
