/**
 * Shared helpers for Virexa Windmill flows.
 * All flows talk to the Virexa API — business logic lives in FastAPI (spec §19),
 * Windmill only orchestrates.
 *
 * Config resolution order (first hit wins):
 *   1. explicit `base` / `token` argument
 *   2. VIREXA_API_BASE / VIREXA_SERVICE_TOKEN environment variables
 *      (set on the worker container when available)
 *   3. Windmill variables u/virexa/virexa_api_base and
 *      u/virexa/virexa_service_token, fetched via the job's own WM_BASE_URL +
 *      WM_TOKEN (works inside every Windmill worker job)
 *   4. http://localhost:8000 with no auth (local dev)
 */
// deno-lint-ignore no-explicit-any
type Any = any;

const VAR_BASE = "u/virexa/virexa_api_base";
const VAR_TOKEN = "u/virexa/virexa_service_token";

/** Fetch a Windmill variable using the job's own session (WM_BASE_URL + WM_TOKEN). */
async function windmillVariable(path: string): Promise<string | undefined> {
  const env = (globalThis as Any).process?.env ?? {};
  const base = env.WM_BASE_URL;
  const token = env.WM_TOKEN;
  if (!base || !token) return undefined;
  try {
    const res = await fetch(
      `${base}/api/w/virexa/variables/get/${path}`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
    if (!res.ok) return undefined;
    const body = await res.json().catch(() => undefined as Any);
    const value = body?.value;
    return typeof value === "string" && value.length > 0 ? value : undefined;
  } catch {
    return undefined;
  }
}

let cachedBase: string | undefined;
let cachedToken: string | undefined;

async function resolveBase(): Promise<string> {
  if (cachedBase) return cachedBase;
  const env = (globalThis as Any).process?.env ?? {};
  cachedBase =
    env.VIREXA_API_BASE || (await windmillVariable(VAR_BASE)) ||
    "http://localhost:8000";
  return cachedBase;
}

async function resolveToken(): Promise<string> {
  if (cachedToken !== undefined) return cachedToken;
  const env = (globalThis as Any).process?.env ?? {};
  cachedToken = env.VIREXA_SERVICE_TOKEN ||
    (await windmillVariable(VAR_TOKEN)) || "";
  return cachedToken;
}

export async function api(
  path: string,
  init?: RequestInit,
  base?: string,
  token?: string,
  // deno-lint-ignore no-explicit-any
): Promise<any> {
  const b = base ?? (await resolveBase());
  const t = token ?? (await resolveToken());
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string>),
  };
  if (t) headers.Authorization = `Bearer ${t}`;
  const res = await fetch(`${b}${path}`, { ...init, headers });
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
