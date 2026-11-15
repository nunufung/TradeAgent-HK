import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

const query = process.argv[2]?.trim();
if (!query || query.length > 100 || /[\x00-\x1f\x7f]/.test(query)) {
  console.error("Provide a public search query of 1–100 characters without control characters.");
  process.exitCode = 2;
} else {
  const state = await mkdtemp(join(tmpdir(), "tradeagent-api-anything-"));
  const previousState = process.env.API_ANYTHING_HOME;
  process.env.API_ANYTHING_HOME = state;

  try {
    const { hostSite, planCall, callPlanned, closeHost } =
      await import("../.api-anything-upstream/dist/host.js");
    try {
      const site = "hacker-news";
      const operation = "searchByDate";
      if (hostSite(site).source !== "bundled") {
        throw new Error("Expected the bundled Hacker News operation.");
      }
      const plan = planCall(site, operation, { query, type: "story" }, { maxTier: 1 });
      if (!plan.ok || !plan.readOnly || plan.signedIn || plan.tier !== 1) {
        throw new Error("Expected an anonymous, read-only, plain HTTP plan.");
      }
      const result = await callPlanned(plan, { allowWrites: false, timeoutMs: 15_000 });
      if (!result.ok) {
        throw new Error("Public search failed (" + result.class + ").");
      }
      if (result.tier !== 1 || !Array.isArray(result.data)) {
        throw new Error("Public search returned an unexpected result.");
      }
      console.log(JSON.stringify({
        source: "Hacker News via Algolia",
        query,
        retrieved_at: new Date().toISOString(),
        stories: result.data,
      }, null, 2));
    } finally {
      await closeHost();
    }
  } finally {
    if (previousState === undefined) delete process.env.API_ANYTHING_HOME;
    else process.env.API_ANYTHING_HOME = previousState;
    await rm(state, { recursive: true, force: true });
  }
}
