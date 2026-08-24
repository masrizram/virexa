/**
 * f/content/discovery_daily — discovery stage.
 * Calls POST /pipeline/discover on the Virexa API; connector failures are
 * isolated inside the API (each connector errors independently).
 */
import { post } from "../../lib/api";

export async function main(brand: string = "default", limitPerSource: number = 20) {
  const result = await post("/pipeline/discover", {
    brand,
    sources: ["hackernews", "reddit:technology", "reddit:artificial", "rss"],
    limit_per_source: limitPerSource,
  });
  return result; // { created, duplicates, errors }
}
