/**
 * f/content/daily_cycle — master daily flow (spec §22).
 * Orchestration only: each stage calls the Virexa API.
 *
 * Modules are individual Windmill scripts (f/content/*); this flow strings them
 * together with error isolation per stage.
 */

export async function main(stage: string = "all") {
  // Stage functions are small, auditable steps. In Windmill this flow calls
  // the individual scripts f/content/<stage> via `wmill.run_script` or the API.
  // Kept here as the canonical orchestration order.
  const order = [
    "discover",
    "research",
    "deduplicate",
    "score",
    "select",
    "strategy",
    "script",
    "video",
    "qc",
    "adapt",
    "publish",
  ];
  if (stage !== "all") return { order, selected: stage };
  return { order };
}
