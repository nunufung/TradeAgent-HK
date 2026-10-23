# Reviewed upstream and CLI reference

Source: https://github.com/Graphify-Labs/graphify

Reviewed revision: `c588b72d936927790a87ad009955078ed40562a3` (default branch `v8`, 2026-10-23).

Package: `graphifyy==0.9.94`, Python >=3.10, Apache-2.0. This Skill is a concise host adaptation, not an official Graphify Labs integration. It uses upstream's executable rather than bundling its engine.

Primary references at this revision:
- [README](https://github.com/Graphify-Labs/graphify/blob/c588b72d936927790a87ad009955078ed40562a3/README.md)
- [Codex Skill template](https://github.com/Graphify-Labs/graphify/blob/c588b72d936927790a87ad009955078ed40562a3/graphify/skill-codex.md)
- [Extraction specification](https://github.com/Graphify-Labs/graphify/blob/c588b72d936927790a87ad009955078ed40562a3/graphify/skills/codex/references/extraction-spec.md)
- [Query reference](https://github.com/Graphify-Labs/graphify/blob/c588b72d936927790a87ad009955078ed40562a3/graphify/skills/codex/references/query.md)

Use `graphify --help` for installed-version flags. Confirmed: `extract ROOT --code-only --max-workers 2`, `query QUESTION --budget N --graph PATH`, `path A B --graph PATH`, `explain SYMBOL --graph PATH`, `export html --graph PATH`, and `export callflow-html`.

Set `GRAPHIFY_BACKEND=none` for deterministic local builds; it disables semantic providers and labeling fallback. Set `GRAPHIFY_QUERY_LOG_DISABLE=1` to avoid persistent question logging. No API key is required for code-only extraction. Document semantics and rendered web views are separate capabilities: a graph can exist even if an optional viewer/export dependency is unavailable.

The upstream README lists several headless providers while portions of the Codex template describe only Gemini or host-agent semantic extraction. Resolve this difference using the installed CLI and current source, and choose a backend explicitly. Do not treat the template's key-detection claims as the headless CLI contract.

