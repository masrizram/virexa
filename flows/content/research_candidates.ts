/**
 * f/content/research_candidates — research stage placeholder runner.
 * The heavy lifting (fetch, source provenance) is an API-side concern; this
 * script selects pending opportunities and dispatches research jobs.
 */
import { get, post } from "../../lib/api";

export async function main(limit: number = 10) {
  const opportunities = await get(`/opportunities?limit=${limit}`);
  return { candidates: opportunities.length, sample: opportunities.slice(0, 3) };
}
