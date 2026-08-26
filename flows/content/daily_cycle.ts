/**
 * f/content/daily_cycle — master daily flow (spec §22/§57).
 *
 * Thin orchestrator only (§19): all business logic lives in the Virexa API's
 * POST /pipeline/run_cycle. The cycle is gated server-side by AUTONOMOUS_MODE
 * and safety state; this script adds nothing but scheduling and a compact
 * result summary for the run log.
 */
import { post } from "../../lib/api";

export async function main(
  brand: string = "default",
  limitPerSource: number = 20,
  minScore: number = 50,
) {
  const result = await post("/pipeline/run_cycle", {
    brand,
    limit_per_source: limitPerSource,
    min_score: minScore,
    platforms: ["youtube", "tiktok"],
  });
  // Compact summary: what was created and where content stopped.
  return {
    content_item_id: result.content_item_id,
    title: result.title,
    state: result.state,
    created: result.stages?.find((s: Any) => s.stage === "discover")?.created ?? null,
    note: result.note,
  };
}

// deno-lint-ignore no-explicit-any
type Any = any;
