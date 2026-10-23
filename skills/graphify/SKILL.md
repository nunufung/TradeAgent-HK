---
name: graphify
description: Build and query source-backed knowledge graphs with Graphify-Labs/graphify. Use when the user names Graphify, asks for a codebase dependency map, architecture or call-flow visualization, cross-file relationship tracing, or a queryable graph of project code and documents, including TradeAgent-HK Skills, analysts and reporting channels.
---

# Graphify

Map project relationships using the upstream `graphifyy` CLI. Read [references/upstream.md](references/upstream.md) for the reviewed version, installation and supported commands.

## Choose a scope

Resolve the repository or folder from the request. For TradeAgent-HK, use its current checkout, not a stale snapshot. Inspect repository instructions before working. Keep generated files under the selected project's `graphify-out/` unless another output location is requested.

For architecture questions, reuse `graphify-out/graph.json` when it matches the current revision. Query a specific symbol or file first; open cited source lines to confirm important findings. Rebuild when stale. Report missing nodes or ambiguous matches rather than guessing.

## Install and check

Use `graphify --help` to confirm the CLI. If missing, install the reviewed version in an isolated tool environment:

```bash
uv tool install 'graphifyy==0.9.94'
```

Use the executable returned by the installer. With uv this is commonly `~/.local/bin/graphify`; if it is absent from PATH, invoke that full path. Do not replace the application project's dependencies or automatically upgrade an existing Graphify installation.

## Build a local code graph

Start with deterministic AST extraction for code relationships. Pass the resolved root as a quoted argument and keep LLM processing disabled for this mode:

```bash
GRAPHIFY_BACKEND=none GRAPHIFY_QUERY_LOG_DISABLE=1 graphify extract /absolute/project/root --code-only --max-workers 2
```

The command writes `/absolute/project/root/graphify-out/graph.json` and analysis outputs. Check actual output files before claiming completion. If HTML was not produced, export it explicitly:

```bash
graphify export html --graph /absolute/project/root/graphify-out/graph.json
```

Run from the project root so exports land in its `graphify-out/` directory. For a compact architecture/call-flow presentation, use `graphify export callflow-html --help` or the pinned CLI reference before selecting options.

## Query and verify

```bash
GRAPHIFY_QUERY_LOG_DISABLE=1 graphify query 'daily_delivery' --budget 1500 --graph /absolute/project/root/graphify-out/graph.json
GRAPHIFY_QUERY_LOG_DISABLE=1 graphify explain 'SymbolName' --graph /absolute/project/root/graphify-out/graph.json
GRAPHIFY_QUERY_LOG_DISABLE=1 graphify path 'SourceSymbol' 'TargetSymbol' --graph /absolute/project/root/graphify-out/graph.json
```

Handle exit code 3 as ambiguous: select from returned candidates using source evidence. Handle code 4 as no match. Graph traversal retrieves evidence; it does not establish runtime health or prove that a channel delivered a message.

## Add document knowledge when requested

Distinguish AST code extraction from semantic document extraction. A code-only run does not capture the meaning of Markdown Skills, trading rules or private spreadsheets. For documents, read the current upstream extraction specification and command help before proceeding. Choose and state the semantic backend explicitly; keep private holdings and trade journals out of a public graph. Use host-agent extraction where supported or an already configured provider within the user's authorized scope. Do not silently select a provider based on environment keys.

For optional `.docx`/`.xlsx` support install the same version with `[office]`; for PDFs use `[pdf]`. Read the files with the relevant document or spreadsheet skill when their contents are needed. Preserve EXTRACTED versus INFERRED relationships and source attribution. Never invent correlations, trading performance, prices or operational status from a graph.

## Deliver

Report corpus scope, source revision, node/edge counts, output paths and limitations. Offer an interactive HTML map when requested. Distinguish verified source relationships from inferred design relationships. For TradeAgent-HK, explain the chain from inputs to analysts, Skills, risk gates and report delivery, while checking each connection in the actual sources.

Install Git hooks, persistent background watchers, MCP servers, cloud connections or always-on instruction files only when the user asks for those features. Adding this Skill alone does not enable them or alter daily report scheduling.
