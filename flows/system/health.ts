/**
 * f/system/health — system health flow (spec §49).
 * Checks Windmill-reachable dependencies and reports to the API audit log.
 */
import { get, post } from "../../lib/api";

export async function main() {
  const checks: Record<string, unknown> = {};
  try {
    checks.api = await get("/health");
  } catch (e) {
    checks.api = { error: String(e) };
  }
  try {
    checks.ready = await get("/ready");
  } catch (e) {
    checks.ready = { error: String(e) };
  }
  return { ts: new Date().toISOString(), checks };
}
