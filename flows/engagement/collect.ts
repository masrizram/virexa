/**
 * f/engagement/collect — pull comments/mentions/DMs via the API and classify.
 * Classification + response policy live API-side (engines/engagement.py);
 * this only dispatches and reports.
 */
import { post } from "../lib/api";

export async function main(platform: string = "youtube", limit: number = 50) {
  return post("/pipeline/engagement/collect", { platform, limit });
}
