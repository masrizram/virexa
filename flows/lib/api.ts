/**
 * Shared helpers for Virexa Windmill flows.
 * All flows talk to the Virexa API (Fly private network) — business logic
 * lives in FastAPI (spec §19), Windmill only orchestrates.
 *
 * Env (Windmill variables, never hardcoded):
 *   VIREXA_API_BASE  → http://virexa-api.internal:8000 (private) or https://virexa-api.fly.dev
 *   VIREXA_SERVICE_TOKEN → bearer for the API in staging/production
 */
export async function api(
  path: string,
  init?: RequestInit,
  base = process.env.VIREXA_API_BASE || "http://localhost:8000",
  token = process.env.VIREXA_SERVICE_TOKEN || "",
): Promise<any> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string>),
  };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${base}${path}`, { ...init, headers });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`VirexaAPI ${res.status} ${path}: ${body.slice(0, 400)}`);
  }
  return res.json();
}

/** POST JSON helper. */
export async function post(path: string, body: unknown, base?: string, token?: string) {
  return api(path, { method: "POST", body: JSON.stringify(body) }, base, token);
}

/** GET helper. */
export async function get(path: string, base?: string, token?: string) {
  return api(path, { method: "GET" }, base, token);
}
