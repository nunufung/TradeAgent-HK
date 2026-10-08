# Book to skill integration

Official converter: https://github.com/virgiliojr94/book-to-skill

The complete MIT-licensed toolkit is a pinned submodule at `tools/book-to-skill`.
Its skill is exposed at `.agents/skills/book-to-skill`. Existing recursive checkout
in daily, Futu and Telegram workflows retrieves it. Conversion happens during
knowledge preparation, not during daily market research.

## Convert a new source

```bash
git submodule update --init tools/book-to-skill
python scripts/extract-book.py /path/to/book.epub --mode text
python scripts/extract-book.py /path/to/rules.docx --mode text
```

Extraction reports a temporary work directory and metadata. It is extraction,
not automatic LLM synthesis. Follow `tools/book-to-skill/SKILL.md` to review the
source and synthesize a skill; validate and scan before loading it:

```bash
python tools/book-to-skill/tools/validate_skill.py /path/to/skill/SKILL.md
python tools/book-to-skill/tools/scan_generated_skill.py /path/to/skill
```

Keep private sources and full copyrighted book-derived packs private. Do not
commit extracted raw text, account data or credentials. XLSX trade logs are not
supported converter inputs; review them separately as historical data, not quotes.

## Knowledge used during research

`skills/runtime.json` explicitly selects reviewed knowledge. Currently it loads
the small existing Psychology of Money skill, corrected to remove unsupported
numeric R/R claims. This is a curated risk lens, not a full conversion of the book.
New documents do not become active merely by being extracted or uploaded.

Both `linked_stock_analysis.py` (daily and Futu) and `hk_adapter.py` (Telegram)
attach it to shared instrument context before propagation. TradingAgents v0.6
passes this context to all four analysts, investment debates, trader and risk
manager. Outputs record skill name, size and SHA256 in `stock_signals.json`;
research Markdown also identifies the loaded skill. Older cached research has
no such audit and must not be described as skill-aware.

Current user instructions and deterministic option checks take priority. Book
principles cannot open the option gate, supply prices, invent account capacity
or place orders. Runtime never loads the converter's procedural prompt.
