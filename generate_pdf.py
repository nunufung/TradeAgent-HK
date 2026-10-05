#!/usr/bin/env python3
"""Create a compact, mobile-friendly TradeAgent-HK PDF from report_*.md files.

Usage:
    python generate_pdf.py --output-dir pdf_reports
    python generate_pdf.py --inputs report_0700.md report_2800.md --output-dir pdf_reports

The script deliberately leaves the original Markdown reports untouched.
"""

from __future__ import annotations

import argparse
import glob
import html
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


NAVY = colors.HexColor("#14213D")
BLUE = colors.HexColor("#2563EB")
TEAL = colors.HexColor("#0F766E")
GREEN = colors.HexColor("#15803D")
RED = colors.HexColor("#B91C1C")
AMBER = colors.HexColor("#B45309")
INK = colors.HexColor("#172033")
MUTED = colors.HexColor("#667085")
LINE = colors.HexColor("#D9E2EC")
PANEL = colors.HexColor("#F5F8FC")
WHITE = colors.white


@dataclass
class ReportSummary:
    filename: str
    ticker: str
    date: str
    action: str
    price: str
    confidence: str
    data_quality: str
    decision: str
    highlights: list[str]
    warnings: list[str]
    raw_text: str


def register_fonts() -> tuple[str, str]:
    candidates = [
        (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ),
        (
            "/usr/share/fonts/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
        ),
    ]
    for regular, bold in candidates:
        if os.path.exists(regular) and os.path.exists(bold):
            pdfmetrics.registerFont(TTFont("TAHK-Regular", regular))
            pdfmetrics.registerFont(TTFont("TAHK-Bold", bold))
            return "TAHK-Regular", "TAHK-Bold"
    return "Helvetica", "Helvetica-Bold"


FONT, FONT_BOLD = register_fonts()


def clean_markdown(text: str) -> str:
    text = text.replace("\r", "")
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.M)
    text = re.sub(r"^\s*[-*+]\s+", "- ", text, flags=re.M)
    text = text.replace("—", "-").replace("–", "-").replace("→", "->")
    text = text.replace("“", '"').replace("”", '"').replace("’", "'")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def compact(text: str, limit: int = 1100) -> str:
    text = re.sub(r"\s+", " ", clean_markdown(text)).strip()
    if len(text) <= limit:
        return text
    clipped = text[:limit].rsplit(" ", 1)[0]
    return clipped + "..."


def first_match(patterns: list[str], text: str, default: str = "-") -> str:
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.I | re.S)
        if m:
            return m.group(1).strip()
    return default


def extract_sentence(text: str, needles: tuple[str, ...], max_len: int = 240) -> str | None:
    cleaned = clean_markdown(text)
    sentences = re.split(r"(?<=[.!?])\s+|\n+", cleaned)
    patterns = []
    for needle in needles:
        if " " in needle:
            patterns.append(re.compile(re.escape(needle), re.I))
        else:
            patterns.append(re.compile(r"\b" + re.escape(needle) + r"\b", re.I))
    for sentence in sentences:
        if any(p.search(sentence) for p in patterns):
            sentence = re.sub(r"^[-|\s]+", "", sentence).strip()
            if 35 <= len(sentence) <= max_len:
                return sentence
    return None


def find_sidecar_log(report_path: str) -> str:
    stem = Path(report_path).stem.replace("report_", "")
    if not stem.isdigit():
        return ""
    target = str(int(stem))
    candidates = []
    for log_path in glob.glob("run_*.log"):
        log_stem = Path(log_path).stem.replace("run_", "")
        if log_stem.isdigit() and str(int(log_stem)) == target:
            candidates.append(log_path)
    if not candidates:
        return ""
    # The largest sidecar usually contains the complete TradingAgents trace.
    chosen = max(candidates, key=lambda p: os.path.getsize(p))
    return Path(chosen).read_text(encoding="utf-8", errors="replace")


def parse_report(path: str) -> ReportSummary:
    raw = Path(path).read_text(encoding="utf-8", errors="replace")
    text = raw.strip()
    sidecar = find_sidecar_log(path)
    source_text = text + ("\n\n" + sidecar if sidecar else "")

    ticker = first_match(
        [r"\b(\d{4}\.HK)\b", r"\b(\d{1,4})\s*->\s*(\d{4}\.HK)\b"],
        source_text,
        default="",
    )
    if not ticker:
        stem = Path(path).stem.replace("report_", "")
        if stem.isdigit():
            ticker = f"{int(stem):04d}.HK"
        else:
            ticker = stem.upper()
    elif "->" in ticker:
        ticker = ticker.split("->")[-1].strip()

    date = first_match([r"\b(20\d{2}-\d{2}-\d{2})\b"], source_text, default="-")
    action = first_match(
        [
            r"FINAL TRANSACTION PROPOSAL:\s*\*{0,2}(BUY|SELL|HOLD|WATCH|NO TRADE)\*{0,2}",
            r"\*\*Action\*\*:\s*(BUY|SELL|HOLD|WATCH|NO TRADE)",
            r"\bAction\s*:\s*(BUY|SELL|HOLD|WATCH|NO TRADE)\b",
        ],
        text,
        default="REVIEW",
    ).upper()

    price = first_match(
        [
            r"(?:closed?|price)\s+(?:at\s+)?HK\$\s*([0-9]+(?:\.[0-9]+)?)",
            r"(?:closed?|price)\s+(?:at\s+)?([0-9]+(?:\.[0-9]+)?)",
            r"at\s+HK\$\s*([0-9]+(?:\.[0-9]+)?)",
        ],
        source_text,
        default="-",
    )
    if price != "-":
        price = f"HK${price}"

    confidence = first_match(
        [r"Confidence\s*:\s*\*{0,2}(high|medium|low)\*{0,2}"],
        source_text,
        default="Not stated",
    ).title()

    warning_patterns = [
        ("NO_DATA_AVAILABLE", "Some market/fundamental data was unavailable."),
        ("HTTPError", "At least one external data source returned an HTTP error."),
        ("news unavailable", "Company/news coverage was incomplete."),
        ("UNAVAILABLE", "One or more data sources were unavailable."),
        ("information gap", "The analysis identified a material information gap."),
    ]
    warnings: list[str] = []
    low = source_text.lower()
    for needle, message in warning_patterns:
        if needle.lower() in low and message not in warnings:
            warnings.append(message)
    warnings = warnings[:4]
    data_quality = "GOOD" if not warnings else ("LIMITED" if len(warnings) <= 2 else "CAUTION")

    decision = first_match(
        [
            r"\*\*Reasoning\*\*:\s*(.*?)(?=\n\s*FINAL TRANSACTION PROPOSAL|\Z)",
            r"Reasoning\s*:\s*(.*?)(?=\n\s*FINAL TRANSACTION PROPOSAL|\Z)",
        ],
        text,
        default="",
    )
    if not decision:
        proposal_pos = text.upper().rfind("FINAL TRANSACTION PROPOSAL")
        if proposal_pos > 0:
            decision = text[max(0, proposal_pos - 1600):proposal_pos]
        else:
            decision = text[-1800:]
    decision = compact(decision, 1350)

    highlight_specs = [
        (("downtrend", "uptrend", "moving average", "macd", "rsi"), "Technical"),
        (("balance sheet", "cash flow", "margin", "valuation", "buyback"), "Fundamental"),
        (("macro", "rates", "yield", "fed", "recession"), "Macro"),
        (("news unavailable", "information gap", "coverage limitation"), "Data"),
    ]
    highlights: list[str] = []
    for needles, label in highlight_specs:
        sentence = extract_sentence(source_text, needles)
        if sentence:
            item = f"{label}: {sentence}"
            if item not in highlights:
                highlights.append(item)
    highlights = highlights[:4]
    if not highlights:
        highlights = ["See the decision section below for the model's key rationale."]

    return ReportSummary(
        filename=Path(path).name,
        ticker=ticker,
        date=date,
        action=action,
        price=price,
        confidence=confidence,
        data_quality=data_quality,
        decision=decision,
        highlights=highlights,
        warnings=warnings,
        raw_text=clean_markdown(text),
    )


def action_color(action: str):
    action = action.upper()
    if action == "BUY":
        return GREEN
    if action == "SELL":
        return RED
    if action in {"NO TRADE", "HOLD"}:
        return AMBER
    return BLUE


def escape(text: str) -> str:
    return html.escape(text or "-").replace("\n", "<br/>")


def build_styles():
    styles = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "Title",
            parent=styles["Title"],
            fontName=FONT_BOLD,
            fontSize=20,
            leading=24,
            textColor=WHITE,
            alignment=TA_LEFT,
            spaceAfter=2 * mm,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            parent=styles["Normal"],
            fontName=FONT,
            fontSize=9.5,
            leading=13,
            textColor=colors.HexColor("#DCE7F5"),
        ),
        "section": ParagraphStyle(
            "Section",
            parent=styles["Heading2"],
            fontName=FONT_BOLD,
            fontSize=11,
            leading=14,
            textColor=NAVY,
            spaceBefore=2 * mm,
            spaceAfter=2 * mm,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=styles["BodyText"],
            fontName=FONT,
            fontSize=8.7,
            leading=12.5,
            textColor=INK,
            spaceAfter=1.8 * mm,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=styles["BodyText"],
            fontName=FONT,
            fontSize=7.4,
            leading=10.2,
            textColor=MUTED,
        ),
        "metric_label": ParagraphStyle(
            "MetricLabel",
            parent=styles["BodyText"],
            fontName=FONT,
            fontSize=7.2,
            leading=9,
            textColor=MUTED,
            alignment=TA_CENTER,
        ),
        "metric_value": ParagraphStyle(
            "MetricValue",
            parent=styles["BodyText"],
            fontName=FONT_BOLD,
            fontSize=10.5,
            leading=13,
            textColor=NAVY,
            alignment=TA_CENTER,
        ),
        "badge": ParagraphStyle(
            "Badge",
            parent=styles["BodyText"],
            fontName=FONT_BOLD,
            fontSize=11,
            leading=13,
            textColor=WHITE,
            alignment=TA_CENTER,
        ),
        "bullet": ParagraphStyle(
            "Bullet",
            parent=styles["BodyText"],
            fontName=FONT,
            fontSize=8.5,
            leading=12,
            leftIndent=4 * mm,
            firstLineIndent=-3 * mm,
            textColor=INK,
            spaceAfter=1.5 * mm,
        ),
    }


def footer(canvas, doc):
    canvas.saveState()
    width, _ = A4
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.4)
    canvas.line(15 * mm, 11 * mm, width - 15 * mm, 11 * mm)
    canvas.setFont(FONT, 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(15 * mm, 7 * mm, "TradeAgent-HK | Generated automatically from TradingAgents output")
    canvas.drawRightString(width - 15 * mm, 7 * mm, f"Page {doc.page}")
    canvas.restoreState()


def metric_card(label: str, value: str, styles):
    data = [
        [Paragraph(escape(value), styles["metric_value"])],
        [Paragraph(escape(label), styles["metric_label"])],
    ]
    t = Table(data, colWidths=[39 * mm], rowHeights=[9 * mm, 7 * mm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PANEL),
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 2 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 1 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1 * mm),
            ]
        )
    )
    return t


def build_pdf(reports: list[ReportSummary], output_path: str, report_mode: str = "Daily Market Intelligence") -> None:
    styles = build_styles()
    doc = BaseDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=14 * mm,
        bottomMargin=17 * mm,
        title="TradeAgent-HK Daily Report",
        author="TradeAgent-HK",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    doc.addPageTemplates([PageTemplate(id="report", frames=[frame], onPage=footer)])

    now_hkt = datetime.now(ZoneInfo("Asia/Hong_Kong"))
    story = []

    header = Table(
        [
            [
                Paragraph("TradeAgent-HK", styles["title"]),
                Paragraph(
                    f"{escape(report_mode)}<br/>{now_hkt:%Y-%m-%d %H:%M HKT}",
                    styles["subtitle"],
                ),
            ]
        ],
        colWidths=[105 * mm, 72 * mm],
    )
    header.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), NAVY),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 5 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5 * mm),
            ]
        )
    )
    story += [header, Spacer(1, 5 * mm)]

    if len(reports) > 1:
        story.append(Paragraph("Report Overview", styles["section"]))
        rows = [["Ticker", "Decision", "Price", "Data quality"]]
        for r in reports:
            rows.append([r.ticker, r.action, r.price, r.data_quality])
        overview = Table(rows, colWidths=[42 * mm, 42 * mm, 42 * mm, 48 * mm], repeatRows=1)
        overview.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                    ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                    ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
                    ("FONTNAME", (0, 1), (-1, -1), FONT),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.5, LINE),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, PANEL]),
                    ("ALIGN", (1, 1), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 2.2 * mm),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2 * mm),
                ]
            )
        )
        story += [overview, Spacer(1, 4 * mm)]

    for idx, r in enumerate(reports):
        if idx > 0:
            story.append(PageBreak())

        badge = Table([[Paragraph(escape(r.action), styles["badge"])]], colWidths=[35 * mm], rowHeights=[11 * mm])
        badge.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), action_color(r.action)),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("BOX", (0, 0), (-1, -1), 0.5, action_color(r.action)),
                ]
            )
        )

        title_row = Table(
            [
                [
                    Paragraph(f"<b>{escape(r.ticker)}</b><br/><font size='8' color='#667085'>{escape(r.filename)}</font>", styles["section"]),
                    badge,
                ]
            ],
            colWidths=[139 * mm, 35 * mm],
        )
        title_row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
        story += [title_row, Spacer(1, 2 * mm)]

        metrics = Table(
            [[
                metric_card("Analysis date", r.date, styles),
                metric_card("Reference price", r.price, styles),
                metric_card("Confidence", r.confidence, styles),
                metric_card("Data quality", r.data_quality, styles),
            ]],
            colWidths=[44 * mm] * 4,
        )
        metrics.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 1 * mm), ("RIGHTPADDING", (0, 0), (-1, -1), 1 * mm)]))
        story += [metrics, Spacer(1, 4 * mm)]

        story.append(Paragraph("Decision Summary", styles["section"]))
        decision_box = Table([[Paragraph(escape(r.decision), styles["body"])]], colWidths=[174 * mm])
        decision_box.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), PANEL),
                    ("BOX", (0, 0), (-1, -1), 0.7, LINE),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
                    ("TOPPADDING", (0, 0), (-1, -1), 3 * mm),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
                ]
            )
        )
        story += [decision_box, Spacer(1, 3 * mm)]

        story.append(Paragraph("Key Signals", styles["section"]))
        for item in r.highlights:
            story.append(Paragraph("• " + escape(item), styles["bullet"]))

        story += [Spacer(1, 1 * mm), Paragraph("Data Quality & Risk Flags", styles["section"])]
        if r.warnings:
            for warning in r.warnings:
                story.append(Paragraph("• " + escape(warning), styles["bullet"]))
        else:
            story.append(Paragraph("No major data-source warning was detected in the generated report.", styles["body"]))

        note = (
            "Current TradingAgents output is a stock-level research decision. "
            "Verify market data before trading. Option selection should only be added after the separate HKEX option-rule gate validates DTE, delta, liquidity, margin and event risk."
        )
        story.append(Spacer(1, 2 * mm))
        note_table = Table([[Paragraph(escape(note), styles["small"])]], colWidths=[174 * mm])
        note_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF8E7")),
                    ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#E8C46B")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
                    ("TOPPADDING", (0, 0), (-1, -1), 2.5 * mm),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5 * mm),
                ]
            )
        )
        story.append(note_table)


    doc.build(story)


def discover_inputs(explicit: list[str] | None) -> list[str]:
    if explicit:
        files = [p for p in explicit if os.path.isfile(p)]
    else:
        files = sorted(glob.glob("report_*.md"))

    # Prefer the canonical four-digit ticker file when both report_700.md and
    # report_0700.md exist. This avoids turning verbose tee logs into duplicate PDFs.
    grouped: dict[str, list[str]] = {}
    others: list[str] = []
    for path in files:
        stem = Path(path).stem.replace("report_", "")
        if stem.isdigit():
            key = str(int(stem))
            grouped.setdefault(key, []).append(path)
        else:
            others.append(path)

    selected: list[str] = []
    for _, candidates in sorted(grouped.items(), key=lambda kv: int(kv[0])):
        canonical = [p for p in candidates if re.fullmatch(r"report_\d{4}\.md", Path(p).name)]
        pool = canonical or candidates
        # Among equally canonical candidates, the smaller file is usually the
        # final decision report rather than a verbose process log.
        selected.append(min(pool, key=lambda p: os.path.getsize(p)))
    selected.extend(sorted(others))
    return selected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", nargs="*", help="Markdown report files. Defaults to report_*.md")
    parser.add_argument("--output-dir", default="pdf_reports")
    parser.add_argument("--mode", default="Daily Market Intelligence")
    args = parser.parse_args()

    inputs = discover_inputs(args.inputs)
    if not inputs:
        print("No report_*.md files found; PDF generation skipped.")
        return 0

    reports = [parse_report(p) for p in inputs]
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    now_hkt = datetime.now(ZoneInfo("Asia/Hong_Kong"))
    output = out_dir / f"TradeAgent-HK_{now_hkt:%Y-%m-%d_%H%M}.pdf"
    build_pdf(reports, str(output), args.mode)
    print(f"PDF_REPORT={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
