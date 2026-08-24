/**
 * f/system/daily_report — summarize the last 24h for the operator.
 */
import { get } from "../lib/api";

export async function main() {
  const [health, stats, budgets] = await Promise.all([
    get("/health"),
    get("/content/stats"),
    get("/settings/budgets"),
  ]);
  return {
    ts: new Date().toISOString(),
    api: health?.status,
    content_by_state: stats?.by_state,
    spent_today: budgets?.spent_today,
  };
}
