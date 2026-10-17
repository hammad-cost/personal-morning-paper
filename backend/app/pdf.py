"""The printed newspaper for one edition, made with ReportLab.

Page 1 is the front cover: the Vale brand strip, the reader's own masthead, the lead story
with a big photo, an "Inside today" index with page numbers, and a "What Vale has learned
about you" chart. Later pages run the other stories in three ruled columns under a small
running head. Every story has a photo, a QR code and a printed citation; headlines link to
the original articles. Skipped stories are left out. No quizzes or study boxes: it reads
like a newspaper.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import date as date_cls
from io import BytesIO
from urllib.parse import urlsplit
from xml.sax.saxutils import escape

from app import images, photos

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    FrameBreak,
    Image,
    KeepInFrame,
    KeepTogether,
    NextPageTemplate,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

BRAND = "Vale"
TAGLINE = "One calm paper a day, made for you."
PAGE_W, PAGE_H = A4
MARGIN = 36
GUTTER = 14
COLS = 3
FULL_W = PAGE_W - 2 * MARGIN
COL_W = (FULL_W - (COLS - 1) * GUTTER) / COLS
COVER_HEAD_H = 150  # brand strip + masthead on the cover
RUNNING_HEAD_H = 26

# Ink & Blue: slate ink, slate grey, soft grey rules, deep blue accent.
INK = colors.HexColor("#1E293B")
MUTED = colors.HexColor("#64748B")
RULE = colors.HexColor("#E2E8F0")
ACCENT = colors.HexColor("#1D4ED8")
SKY = colors.HexColor("#3B82F6")
SOFT = colors.HexColor("#EFF4FF")

STYLES = {
    "kicker": ParagraphStyle("kicker", fontName="Helvetica-Bold", fontSize=6.5, leading=8, textColor=ACCENT, spaceAfter=2),
    "cover_kicker": ParagraphStyle("cover_kicker", fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=ACCENT, spaceAfter=3),
    "cover_lead": ParagraphStyle("cover_lead", fontName="Times-Bold", fontSize=24, leading=26, textColor=INK, spaceAfter=6),
    "cover_body": ParagraphStyle("cover_body", fontName="Times-Roman", fontSize=11, leading=14.5, textColor=INK, spaceAfter=4),
    "cover_why": ParagraphStyle("cover_why", fontName="Times-Italic", fontSize=10, leading=13, textColor=MUTED),
    "headline": ParagraphStyle("headline", fontName="Times-Bold", fontSize=12, leading=14, textColor=INK, spaceAfter=2),
    "body": ParagraphStyle("body", fontName="Times-Roman", fontSize=9.2, leading=11.8, textColor=INK, spaceAfter=2),
    "why": ParagraphStyle("why", fontName="Times-Italic", fontSize=8.5, leading=10.5, textColor=MUTED, spaceAfter=2),
    "section": ParagraphStyle("section", fontName="Helvetica-Bold", fontSize=7.5, leading=9, textColor=colors.white,
                              backColor=INK, borderPadding=(2, 3, 2, 3), spaceBefore=6, spaceAfter=6),
    "part": ParagraphStyle("part", fontName="Helvetica-Bold", fontSize=9, leading=11, textColor=ACCENT, spaceBefore=8, spaceAfter=6),
    "box_title": ParagraphStyle("box_title", fontName="Helvetica-Bold", fontSize=7.5, leading=9, textColor=ACCENT, spaceAfter=4),
    "index_section": ParagraphStyle("index_section", fontName="Helvetica-Bold", fontSize=6.5, leading=8, textColor=ACCENT),
    "index_item": ParagraphStyle("index_item", fontName="Times-Roman", fontSize=7.6, leading=9.2, textColor=INK),
    "index_page": ParagraphStyle("index_page", fontName="Helvetica-Bold", fontSize=7, leading=9.2, textColor=ACCENT, alignment=TA_RIGHT),
    "note": ParagraphStyle("note", fontName="Helvetica", fontSize=6.3, leading=8, textColor=MUTED),
    "cite": ParagraphStyle("cite", fontName="Helvetica", fontSize=6.3, leading=7.8, textColor=MUTED),
    "credit": ParagraphStyle("credit", fontName="Helvetica", fontSize=5.5, leading=7, textColor=MUTED, spaceAfter=3),
    "footer": ParagraphStyle("footer", fontName="Helvetica", fontSize=6.5, leading=8, textColor=MUTED, alignment=TA_CENTER),
}


def _plain(text) -> str:
    """Only characters the built-in PDF fonts can draw (others would print as black boxes)."""
    return str(text or "").encode("cp1252", errors="ignore").decode("cp1252").strip()


def _t(text) -> str:
    """Escape text for ReportLab's mini-markup."""
    return escape(_plain(text))


def _link(url: str, text: str) -> str:
    return f'<link href="{escape(url, {chr(34): "&quot;"})}">{text}</link>' if url else text


def link_of(a: dict) -> str:
    """Straight to the publisher when we know it, else the feed link."""
    return a.get("publisher_url") or a.get("url", "")


def source_of(a: dict) -> str:
    """The publisher's name as it can be printed (falls back to its site)."""
    name = _plain(a.get("source_name"))
    if name:
        return name
    host = urlsplit(link_of(a)).netloc.removeprefix("www.")
    return host if host and host != "news.google.com" else "Source"


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


def _vale_mark(c, x, y, size):
    """The Vale tile: a white V with a blue line under it, on slate."""
    k = size / 64
    c.setFillColor(INK)
    c.roundRect(x, y, size, size, 14 * k, stroke=0, fill=1)
    c.setStrokeColor(colors.white)
    c.setLineWidth(7 * k)
    c.setLineCap(1)
    c.setLineJoin(1)
    path = c.beginPath()
    path.moveTo(x + 18 * k, y + size - 15 * k)
    path.lineTo(x + 32 * k, y + size - 45 * k)
    path.lineTo(x + 46 * k, y + size - 15 * k)
    c.drawPath(path, stroke=1, fill=0)
    c.setFillColor(SKY)
    c.roundRect(x + 17 * k, y + size - 54 * k, 30 * k, 4 * k, 2 * k, stroke=0, fill=1)


def _footer(c, doc, meta):
    c.setFont("Helvetica", 6.5)
    c.setFillColor(MUTED)
    c.drawCentredString(PAGE_W / 2, MARGIN - 6,
                        f"{meta['title']}  ·  Edition No. {meta['number']}  ·  page {doc.page}  ·  {meta['printed_for']}")


def _cover_page(c, doc, meta):
    c.saveState()
    top = PAGE_H - MARGIN
    # Brand strip: the Vale mark and name on the left, who it's printed for on the right.
    _vale_mark(c, MARGIN, top - 24, 24)
    c.setFillColor(INK)
    c.setFont("Times-Bold", 17)
    c.drawString(MARGIN + 31, top - 15, BRAND)
    v_w = stringWidth("V", "Times-Bold", 17)
    c.setFillColor(ACCENT)
    c.rect(MARGIN + 31, top - 19, v_w, 1.6, stroke=0, fill=1)  # the blue line under the V
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 6.5)
    c.drawString(MARGIN + 31, top - 26, TAGLINE)
    c.setFont("Helvetica-Bold", 7)
    c.setFillColor(INK)
    c.drawRightString(PAGE_W - MARGIN, top - 11, meta["printed_for"].upper())
    c.setFont("Helvetica", 7)
    c.setFillColor(MUTED)
    c.drawRightString(PAGE_W - MARGIN, top - 21, meta["count_line"].upper())
    c.setFillColor(ACCENT)
    c.rect(MARGIN, top - 34, FULL_W, 2.2, stroke=0, fill=1)

    # Masthead: the reader's own paper name between double rules.
    head_top = top - 44
    _double_rule(c, head_top)
    size = 50
    while size > 18 and stringWidth(meta["title"], "Times-Bold", size) > FULL_W:
        size -= 1
    c.setFillColor(INK)
    c.setFont("Times-Bold", size)
    c.drawCentredString(PAGE_W / 2, head_top - 12 - size * 0.78, meta["title"])
    meta_y = top - COVER_HEAD_H + 18
    c.setLineWidth(0.6)
    c.setStrokeColor(INK)
    c.line(MARGIN, meta_y + 11, PAGE_W - MARGIN, meta_y + 11)
    c.setFont("Helvetica", 7)
    c.setFillColor(MUTED)
    c.drawCentredString(PAGE_W / 2, meta_y + 2, meta["line"].upper())
    _double_rule(c, top - COVER_HEAD_H + 10)
    _footer(c, doc, meta)
    c.restoreState()


def _later_page(c, doc, meta):
    c.saveState()
    top = PAGE_H - MARGIN
    _vale_mark(c, MARGIN, top - 14, 14)
    c.setFont("Times-Bold", 11)
    c.setFillColor(INK)
    c.drawString(MARGIN + 20, top - 11, meta["title"])
    c.setFont("Helvetica", 7)
    c.setFillColor(MUTED)
    c.drawRightString(PAGE_W - MARGIN, top - 10, meta["line"].upper())
    _double_rule(c, top - RUNNING_HEAD_H + 8)
    _column_rules(c, top - RUNNING_HEAD_H)
    _footer(c, doc, meta)
    c.restoreState()


# ---------- pieces ----------

PHOTOS_IN_PDF = 20  # every story in a 20-story paper
QR_SIZE = 44  # points; scans easily from a printed page


class _PageMark(Flowable):
    """Invisible marker that records which page a story landed on (for the cover index)."""

    def __init__(self, key: str, pages: dict):
        super().__init__()
        self.key, self.pages = key, pages
        self.width = self.height = 0

    def wrap(self, *args):
        return 0, 0

    def draw(self):
        self.pages[self.key] = self.canv.getPageNumber()


_crops: dict = {}


def _photo(jpeg: bytes, width: float, height: float):
    """The photo cropped from its centre to exactly width x height, like a newspaper picture box."""
    key = (hash(jpeg), round(width), round(height))
    if key not in _crops:
        from PIL import Image as PILImage

        img = PILImage.open(BytesIO(jpeg))
        w, h = img.size
        target = width / height
        if w / h > target:  # too wide: trim the sides
            new_w = int(h * target)
            img = img.crop(((w - new_w) // 2, 0, (w + new_w) // 2, h))
        else:  # too tall: trim top and bottom, keeping a little more of the top (faces, headlines)
            new_h = int(w / target)
            top = int((h - new_h) * 0.35)
            img = img.crop((0, top, w, top + new_h))
        out = BytesIO()
        img.convert("RGB").save(out, "JPEG", quality=82, optimize=True)
        _crops[key] = out.getvalue()
        if len(_crops) > 200:
            _crops.pop(next(iter(_crops)))
    picture = Image(BytesIO(_crops[key]), width=width, height=height)
    picture.hAlign = "LEFT"
    return picture


def _qr(url: str, size: float = QR_SIZE) -> Drawing:
    """A QR code that opens the original article when scanned."""
    widget = QrCodeWidget(url, barLevel="M")
    x0, y0, x1, y1 = widget.getBounds()
    drawing = Drawing(size, size, transform=[size / (x1 - x0), 0, 0, size / (y1 - y0), 0, 0])
    drawing.add(widget)
    return drawing


def short_link(url: str, limit: int = 38) -> str:
    """reuters.com/technology/… — readable in print."""
    parts = urlsplit(url)
    if parts.netloc == "news.google.com":
        return "Original article (via Google News)"
    text = (parts.netloc.removeprefix("www.") + parts.path).rstrip("/")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _citation(a: dict, width: float = COL_W) -> Table:
    """QR code + printed citation: source, date and a short link to the original."""
    url = link_of(a)
    when = (a.get("published_at") or "")[:10]
    words = (f"<b>Scan for the original</b><br/>{_t(source_of(a))}"
             + (f" · {when}" if when else "") + f"<br/>{_link(url, _t(short_link(url)))}")
    table = Table([[_qr(url), Paragraph(words, STYLES["cite"])]], colWidths=[QR_SIZE + 4, width - QR_SIZE - 4], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return table


def _credit(a: dict) -> Paragraph:
    return Paragraph(_t(a.get("image_credit") or f"Photo: {source_of(a)}"), STYLES["credit"])


def _story(a: dict, pages: dict, section: str | None = None, jpeg: bytes | None = None) -> KeepTogether:
    # A section header travels with its first story so it is never stranded at a column foot.
    parts = [_PageMark(a["id"], pages)]
    parts += [Paragraph(f"&nbsp;{_t(section).upper()}&nbsp;", STYLES["section"])] if section else []
    if a.get("is_explore"):
        parts.append(Paragraph(_t(a.get("label") or "Something new").upper(), STYLES["kicker"]))
    elif a.get("swapped"):
        parts.append(Paragraph("EDITOR'S SWAP", STYLES["kicker"]))
    if jpeg:
        parts += [_photo(jpeg, COL_W, COL_W * 2 / 3), _credit(a)]
    parts += [
        Paragraph(_link(link_of(a), _t(a["headline"])), STYLES["headline"]),
        Paragraph(_t(a.get("summary")), STYLES["body"]),
    ]
    if a.get("why_it_matters"):
        parts.append(Paragraph(f"Why it matters to you: {_t(a['why_it_matters'])}", STYLES["why"]))
    parts += [_citation(a), Spacer(1, 10)]
    return KeepTogether(parts)


def _cover_lead(a: dict, pages: dict, jpeg: bytes | None) -> list:
    flow = [_PageMark(a["id"], pages), Spacer(1, 4)]
    if jpeg:
        flow += [_photo(jpeg, FULL_W, 158), _credit(a)]
    flow += [
        Paragraph(f"{_t(a['topic']).upper()}  ·  TODAY'S LEAD STORY", STYLES["cover_kicker"]),
        Paragraph(_link(link_of(a), _t(a["headline"])), STYLES["cover_lead"]),
    ]
    words = [Paragraph(_t(a.get("summary")), STYLES["cover_body"])]
    if a.get("why_it_matters"):
        words.append(Paragraph(f"Why it matters to you: {_t(a['why_it_matters'])}", STYLES["cover_why"]))
    cite_w = 170
    body = Table([[words, _citation(a, cite_w)]], colWidths=[FULL_W - cite_w - 16, cite_w + 16], hAlign="LEFT")
    body.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (0, 0), 16),
        ("RIGHTPADDING", (1, 0), (1, 0), 0),
        ("LINEBEFORE", (1, 0), (1, 0), 0.6, RULE),
        ("LEFTPADDING", (1, 0), (1, 0), 10),
    ]))
    return flow + [body, Spacer(1, 12)]


INDEX_CHARS = 40  # one line per story in the cover index


def _index(stories: list[dict], pages: dict, width: float) -> Table:
    """'Inside today': every other story by section, with the page it's on."""
    rows = []
    section = None
    for a in stories:
        if a["topic"] != section:
            section = a["topic"]
            rows.append([Paragraph(_t(section).upper(), STYLES["index_section"]), ""])
        headline = _plain(a["headline"])
        headline = headline if len(headline) <= INDEX_CHARS else headline[: INDEX_CHARS - 1].rstrip() + "…"
        rows.append([Paragraph(escape(headline), STYLES["index_item"]), Paragraph(f"p.{pages.get(a['id'], '')}", STYLES["index_page"])])
    half = (len(rows) + 1) // 2
    left, right = rows[:half], rows[half:]
    right += [["", ""]] * (len(left) - len(right))
    col = (width - 12) / 2
    grid = Table([l + [""] + r for l, r in zip(left, right)], colWidths=[col - 22, 22, 12, col - 22, 22], hAlign="LEFT")
    grid.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 0.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5),
    ]))
    return Table([[Paragraph("INSIDE TODAY", STYLES["box_title"])], [grid]], colWidths=[width], hAlign="LEFT",
                 style=TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                   ("LINEABOVE", (0, 0), (-1, 0), 1.4, INK), ("TOPPADDING", (0, 0), (0, 0), 5)]))


def interest_rows(weights: dict | None, limit: int = 6) -> list[tuple[str, float]]:
    """The reader's strongest interests, biggest first."""
    return sorted(((t, w) for t, w in (weights or {}).items() if w > 0), key=lambda tw: -tw[1])[:limit]


def _interests(weights: dict | None, width: float) -> Table | None:
    """'What Vale has learned about you': a small bar chart of the reader's topics."""
    rows = interest_rows(weights)
    if not rows:
        return None
    bar_h, gap, label_w, num_w = 8, 6, 78, 16
    height = len(rows) * (bar_h + gap)
    chart = Drawing(width, height)
    top_weight = rows[0][1]
    track = width - label_w - num_w
    for i, (topic, weight) in enumerate(rows):
        y = height - (i + 1) * (bar_h + gap) + gap / 2
        label = _plain(topic)
        while label and stringWidth(label, "Helvetica", 7) > label_w - 4:
            label = label[:-2] + "…" if len(label) > 2 else ""
        chart.add(String(0, y + 1, label, fontName="Helvetica", fontSize=7, fillColor=INK))
        chart.add(Rect(label_w, y, track, bar_h, fillColor=SOFT, strokeColor=None))
        chart.add(Rect(label_w, y, max(4, track * weight / top_weight), bar_h, fillColor=ACCENT, strokeColor=None))
        chart.add(String(width, y + 1, f"{weight:g}", fontName="Helvetica-Bold", fontSize=7, fillColor=ACCENT, textAnchor="end"))
    return Table(
        [[Paragraph("WHAT VALE HAS LEARNED ABOUT YOU", STYLES["box_title"])], [chart],
         [Paragraph("Every story you read, like or skip tunes tomorrow's paper. This chart is yours alone.", STYLES["note"])]],
        colWidths=[width], hAlign="LEFT",
        style=TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                          ("LINEABOVE", (0, 0), (-1, 0), 1.4, INK), ("TOPPADDING", (0, 0), (0, 0), 5),
                          ("TOPPADDING", (0, 2), (0, 2), 4)]),
    )


# ---------- the paper ----------

def build_pdf(edition: dict, paper_title: str, compress: bool = True, fetch_image=None,
              weights: dict | None = None, reader: str | None = None) -> bytes:
    """Render the edition to PDF bytes. fetch_image(url) -> bytes is replaceable for tests."""
    fetch_image = fetch_image or images.fetch_image
    stories = reading_order(edition)
    with_photo = [a for a in stories if a.get("image_url")][:PHOTOS_IN_PDF]

    def load(a):
        # Stored pictures come from disk; older editions may still point at the web.
        if photos.is_local(a["image_url"]):
            data = photos.read_local(a["image_url"])
        else:
            data = fetch_image(a["image_url"])
        jpeg = images.to_jpeg(data, max_width=800) if data else None  # keeps the PDF light
        return jpeg.getvalue() if jpeg else None

    with ThreadPoolExecutor(max_workers=4) as pool:
        jpegs = dict(zip([a["id"] for a in with_photo], pool.map(load, with_photo)))

    minutes = edition.get("reading_minutes")
    name = _plain(reader)
    meta = {
        "title": _plain(paper_title or BRAND).upper() or BRAND.upper(),
        "number": edition.get("edition_number"),
        "printed_for": f"Printed for {name} by {BRAND}" if name else f"Printed by {BRAND}",
        "count_line": "  ·  ".join(filter(None, [f"{len(stories)} stories", f"{minutes} min read" if minutes else None])),
        "line": "  ·  ".join(filter(None, [
            "Vol. 1",
            f"Edition No. {edition.get('edition_number')}",
            _long_date(edition["date"]) if edition.get("date") else None,
        ])),
    }

    def render(pages: dict) -> bytes:
        buf = BytesIO()
        doc = BaseDocTemplate(
            buf, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=MARGIN, bottomMargin=MARGIN,
            title=f"{meta['title']} — Edition No. {meta['number']}", author=BRAND,
            pageCompression=1 if compress else 0,
        )
        cover_h = PAGE_H - 2 * MARGIN - COVER_HEAD_H - 14
        cover = Frame(MARGIN, MARGIN + 14, FULL_W, cover_h, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id="cover")
        later_top = PAGE_H - MARGIN - RUNNING_HEAD_H
        columns = [
            Frame(MARGIN + i * (COL_W + GUTTER), MARGIN + 14, COL_W, later_top - MARGIN - 14,
                  leftPadding=0, rightPadding=0, topPadding=4, bottomPadding=0, id=f"l{i}")
            for i in range(COLS)
        ]
        doc.addPageTemplates([
            PageTemplate("cover", [cover], onPage=lambda c, d: _cover_page(c, d, meta)),
            PageTemplate("later", columns, onPage=lambda c, d: _later_page(c, d, meta)),
        ])

        flow = [NextPageTemplate("later")]
        if stories:
            lead, rest = stories[0], stories[1:]
            front = _cover_lead(lead, pages, jpegs.get(lead["id"]))
            chart_w = 170
            interests = _interests(weights, chart_w)
            index_w = FULL_W - (chart_w + 18 if interests else 0)
            boxes = [_index(rest, pages, index_w)] if rest else []
            if interests:
                boxes.append(interests)
            if boxes:
                # Index on the left, interests chart on the right, 18pt apart.
                row = Table([boxes], colWidths=[index_w + 18, chart_w] if len(boxes) == 2 else [FULL_W], hAlign="LEFT")
                row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                         ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                         *([("RIGHTPADDING", (0, 0), (0, 0), 18)] if len(boxes) == 2 else [])]))
                front.append(row)
            flow.append(KeepInFrame(FULL_W, cover_h, front, mode="shrink"))
            flow.append(FrameBreak())

            section = None
            for i, a in enumerate(rest):
                if a.get("part", 1) == 2 and (i == 0 or rest[i - 1].get("part", 1) != 2):
                    flow.append(Paragraph("MORE FOR YOU · PART 2", STYLES["part"]))
                    section = None  # repeat the section header inside part 2
                header = a["topic"] if a["topic"] != section else None
                section = a["topic"]
                flow.append(_story(a, pages, section=header, jpeg=jpegs.get(a["id"])))
        flow.append(Spacer(1, 6))
        flow.append(Paragraph(f"Every headline links to the original article. Printed by {BRAND}.", STYLES["footer"]))
        doc.build(flow)
        return buf.getvalue()

    # Two passes: the first finds the page each story lands on, the second prints the index.
    pages: dict = {}
    render(pages)
    return render(dict(pages))


def filename_for(edition: dict, paper_title: str) -> str:
    slug = "".join(ch if ch.isalnum() else "-" for ch in (paper_title or "morning-paper").lower()).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return f"{slug}-edition-{edition.get('edition_number')}.pdf"
