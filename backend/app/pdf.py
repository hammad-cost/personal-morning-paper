"""Broadsheet PDF for one edition, made with ReportLab.

Page 1: Times-Bold masthead between double rules, meta line, a boxed "3 Things You
Learned Today" strip, then three columns with vertical rules. Later pages keep the
three columns under a small running head. Headlines and takeaways link to the
original articles. Skipped stories are left out.
"""

from datetime import date as date_cls
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (
    BaseDocTemplate,
    FrameBreak,
    Frame,
    KeepTogether,
    NextPageTemplate,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

BRAND = "Vale"
PAGE_W, PAGE_H = A4
MARGIN = 36
GUTTER = 14
COLS = 3
COL_W = (PAGE_W - 2 * MARGIN - (COLS - 1) * GUTTER) / COLS
MASTHEAD_H = 104  # title + rules + meta line on page 1
TAKEAWAYS_H = 96  # frame for the 3 Things strip on page 1
RUNNING_HEAD_H = 26

INK = colors.HexColor("#1A1917")
MUTED = colors.HexColor("#5C5852")
RULE = colors.HexColor("#D6D1C7")
ACCENT = colors.HexColor("#B93829")

STYLES = {
    "kicker": ParagraphStyle("kicker", fontName="Helvetica", fontSize=6.5, leading=8, textColor=MUTED, spaceAfter=1),
    "lead": ParagraphStyle("lead", fontName="Times-Bold", fontSize=17, leading=19, textColor=INK, spaceAfter=3),
    "headline": ParagraphStyle("headline", fontName="Times-Bold", fontSize=11.5, leading=13.5, textColor=INK, spaceAfter=2),
    "body": ParagraphStyle("body", fontName="Times-Roman", fontSize=9, leading=11.5, textColor=INK, spaceAfter=2),
    "why": ParagraphStyle("why", fontName="Times-Italic", fontSize=8.5, leading=10.5, textColor=MUTED, spaceAfter=2),
    "source": ParagraphStyle("source", fontName="Helvetica", fontSize=6.5, leading=8, textColor=MUTED),
    "section": ParagraphStyle("section", fontName="Helvetica-Bold", fontSize=7.5, leading=9, textColor=INK, spaceBefore=4, spaceAfter=3),
    "box_title": ParagraphStyle("box_title", fontName="Helvetica-Bold", fontSize=7, leading=9, textColor=INK),
    "box_body": ParagraphStyle("box_body", fontName="Times-Roman", fontSize=8.5, leading=10.5, textColor=INK),
    "box_num": ParagraphStyle("box_num", fontName="Times-Bold", fontSize=20, leading=20, textColor=ACCENT, alignment=TA_CENTER),
    "side_title": ParagraphStyle("side_title", fontName="Times-Bold", fontSize=11, leading=13, textColor=INK, spaceAfter=2),
    "footer": ParagraphStyle("footer", fontName="Helvetica", fontSize=6.5, leading=8, textColor=MUTED, alignment=TA_CENTER),
}


def _t(text) -> str:
    """Escape text for ReportLab's mini-markup."""
    return escape(str(text or ""))


def _link(url: str, text: str) -> str:
    return f'<link href="{escape(url, {chr(34): "&quot;"})}">{text}</link>' if url else text


def reading_order(edition: dict) -> list[dict]:
    """Lead first, then each section in the edition's order; skipped stories removed."""
    live = [a for a in edition["articles"] if not a.get("skipped")]
    if not live:
        return []
    lead = next((a for a in live if a.get("is_lead")), live[0])
    rest = [a for a in live if a is not lead]
    order = [s for s in edition.get("sections", []) if any(a["topic"] == s for a in rest)]
    order += [t for t in dict.fromkeys(a["topic"] for a in rest) if t not in order]
    return [lead] + [a for s in order for a in rest if a["topic"] == s]


def _long_date(iso: str) -> str:
    d = date_cls.fromisoformat(iso)
    return d.strftime("%A, %B ") + str(d.day) + d.strftime(", %Y")


# ---------- page decorations ----------

def _double_rule(c, y, x0=MARGIN, x1=PAGE_W - MARGIN):
    c.setStrokeColor(INK)
    c.setLineWidth(1.4)
    c.line(x0, y, x1, y)
    c.setLineWidth(0.5)
    c.line(x0, y - 2.5, x1, y - 2.5)


def _column_rules(c, top, bottom=MARGIN + 14):
    c.setStrokeColor(RULE)
    c.setLineWidth(0.6)
    for i in range(1, COLS):
        x = MARGIN + i * COL_W + (i - 0.5) * GUTTER
        c.line(x, bottom, x, top)


def _footer(c, doc, meta):
    c.setFont("Helvetica", 6.5)
    c.setFillColor(MUTED)
    c.drawCentredString(PAGE_W / 2, MARGIN - 6, f"{meta['title']}  ·  Edition No. {meta['number']}  ·  page {doc.page}  ·  printed by {BRAND}")


def _first_page(c, doc, meta):
    c.saveState()
    top = PAGE_H - MARGIN
    _double_rule(c, top)
    # Fit the title to the page width.
    size = 44
    width = PAGE_W - 2 * MARGIN
    while size > 18 and stringWidth(meta["title"], "Times-Bold", size) > width:
        size -= 1
    c.setFillColor(INK)
    c.setFont("Times-Bold", size)
    c.drawCentredString(PAGE_W / 2, top - 14 - size * 0.8, meta["title"])
    meta_y = top - MASTHEAD_H + 22
    c.setLineWidth(0.6)
    c.line(MARGIN, meta_y + 11, PAGE_W - MARGIN, meta_y + 11)
    c.setFont("Helvetica", 7)
    c.setFillColor(MUTED)
    c.drawCentredString(PAGE_W / 2, meta_y + 2, meta["line"].upper())
    _double_rule(c, top - MASTHEAD_H + 12)
    _column_rules(c, top - MASTHEAD_H - TAKEAWAYS_H - 4)
    _footer(c, doc, meta)
    c.restoreState()


def _later_page(c, doc, meta):
    c.saveState()
    top = PAGE_H - MARGIN
    c.setFont("Times-Bold", 11)
    c.setFillColor(INK)
    c.drawString(MARGIN, top - 11, meta["title"])
    c.setFont("Helvetica", 7)
    c.setFillColor(MUTED)
    c.drawRightString(PAGE_W - MARGIN, top - 10, meta["line"].upper())
    _double_rule(c, top - RUNNING_HEAD_H + 8)
    _column_rules(c, top - RUNNING_HEAD_H)
    _footer(c, doc, meta)
    c.restoreState()


# ---------- content ----------

def _takeaways_box(edition: dict, urls: dict) -> Table:
    cells = []
    for i, t in enumerate(edition.get("three_takeaways", [])[:3], start=1):
        text = _link(urls.get(t["article_id"], ""), _t(t["text"]))
        cells += [Paragraph(str(i), STYLES["box_num"]), Paragraph(text, STYLES["box_body"])]
    inner_w = PAGE_W - 2 * MARGIN - 12
    num_w = 20
    text_w = (inner_w - 3 * num_w) / 3
    grid = Table([cells], colWidths=[num_w, text_w] * (len(cells) // 2) or [inner_w])
    grid.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        *[("LINEAFTER", (c, 0), (c, 0), 0.5, RULE) for c in (1, 3) if c < len(cells) - 1],
    ]))
    box = Table(
        [[Paragraph("3 THINGS YOU LEARNED TODAY", STYLES["box_title"])], [grid]],
        colWidths=[PAGE_W - 2 * MARGIN],
    )
    box.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1.2, INK),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (0, 0), 6),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 6),
    ]))
    return box


def _story(a: dict, lead: bool, section: str | None = None) -> KeepTogether:
    # Regular stories sit under their section header, so only the lead and special stories get a kicker.
    kicker = None
    if a.get("is_explore"):
        kicker = f'<font color="#B93829">{_t(a.get("label") or "Something new").upper()}</font>'
    elif lead:
        kicker = f'<font color="#B93829">{_t(a["topic"]).upper()}  ·  LEAD STORY</font>'
    elif a.get("swapped"):
        kicker = "EDITOR'S SWAP"
    # A section header travels with its first story so it is never stranded at a column foot.
    parts = [Paragraph(_t(section).upper(), STYLES["section"])] if section else []
    parts += [Paragraph(kicker, STYLES["kicker"])] if kicker else []
    parts += [
        Paragraph(_link(a.get("url", ""), _t(a["headline"])), STYLES["lead" if lead else "headline"]),
        Paragraph(_t(a.get("summary")), STYLES["body"]),
    ]
    if a.get("why_it_matters"):
        parts.append(Paragraph(f"Why it matters to you: {_t(a['why_it_matters'])}", STYLES["why"]))
    parts.append(Paragraph(f"{_t(a.get('source_name'))}  ·  {_link(a.get('url', ''), 'Read original')}", STYLES["source"]))
    parts.append(Spacer(1, 9))
    return KeepTogether(parts)


def _side_boxes(edition: dict) -> list:
    flow = []
    dots = edition.get("connect_the_dots") or {}
    vitamin = edition.get("mind_vitamin") or {}
    for kicker, title, body in [
        ("EDITOR'S NOTE", "Connect the Dots", dots.get("text")),
        ("MORNING MIND VITAMIN", vitamin.get("title"), vitamin.get("content")),
    ]:
        if not body:
            continue
        box = Table(
            [[Paragraph(kicker, STYLES["kicker"])], [Paragraph(_t(title), STYLES["side_title"])], [Paragraph(_t(body), STYLES["body"])]],
            colWidths=[COL_W],
        )
        box.setStyle(TableStyle([
            ("LINEABOVE", (0, 0), (-1, 0), 1.4, INK),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        flow += [KeepTogether([box]), Spacer(1, 10)]
    return flow


def build_pdf(edition: dict, paper_title: str, compress: bool = True) -> bytes:
    """Render the edition to PDF bytes."""
    stories = reading_order(edition)
    urls = {a["id"]: a.get("url", "") for a in edition["articles"]}
    minutes = edition.get("reading_minutes")
    meta = {
        "title": (paper_title or BRAND).upper(),
        "number": edition.get("edition_number"),
        "line": "  ·  ".join(filter(None, [
            "Vol. 1",
            f"Edition No. {edition.get('edition_number')}",
            _long_date(edition["date"]) if edition.get("date") else None,
            f"Today's paper: {minutes} min" if minutes else None,
        ])),
    }

    buf = BytesIO()
    doc = BaseDocTemplate(
        buf, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=MARGIN, bottomMargin=MARGIN,
        title=f"{meta['title']} — Edition No. {meta['number']}", author=BRAND,
        pageCompression=1 if compress else 0,
    )

    def columns(top: float, prefix: str) -> list[Frame]:
        return [
            Frame(MARGIN + i * (COL_W + GUTTER), MARGIN + 14, COL_W, top - MARGIN - 14,
                  leftPadding=0, rightPadding=0, topPadding=4, bottomPadding=0, id=f"{prefix}{i}")
            for i in range(COLS)
        ]

    first_top = PAGE_H - MARGIN - MASTHEAD_H
    takeaways_frame = Frame(MARGIN, first_top - TAKEAWAYS_H, PAGE_W - 2 * MARGIN, TAKEAWAYS_H,
                            leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=8, id="takeaways")
    doc.addPageTemplates([
        PageTemplate("first", [takeaways_frame, *columns(first_top - TAKEAWAYS_H - 4, "c")],
                     onPage=lambda c, d: _first_page(c, d, meta)),
        PageTemplate("later", columns(PAGE_H - MARGIN - RUNNING_HEAD_H, "l"),
                     onPage=lambda c, d: _later_page(c, d, meta)),
    ])

    flow = [NextPageTemplate("later"), _takeaways_box(edition, urls), FrameBreak()]
    current_section = None
    for i, a in enumerate(stories):
        header = None
        if i > 0 and a["topic"] != current_section:
            current_section = header = a["topic"]
        flow.append(_story(a, lead=(i == 0), section=header))
    flow += _side_boxes(edition)
    flow.append(Paragraph(f"Every headline links to the original article. Printed by {BRAND}.", STYLES["footer"]))

    doc.build(flow)
    return buf.getvalue()


def filename_for(edition: dict, paper_title: str) -> str:
    slug = "".join(ch if ch.isalnum() else "-" for ch in (paper_title or "morning-paper").lower()).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return f"{slug}-edition-{edition.get('edition_number')}.pdf"
