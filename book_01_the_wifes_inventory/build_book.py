#!/usr/bin/env python3
"""Build KDP-ready EPUB, Print DOCX, and Print PDF files for The Wife's Inventory by David Seelmann."""

import html
import os
import re
import subprocess
import tempfile
import uuid
import xml.etree.ElementTree as ET
import zipfile
from PIL import Image, ImageFilter
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt


BOOK_TITLE = "The Wife's Inventory"
BOOK_SUBTITLE = "A Gripping Domestic Psychological Thriller"
BOOK_SERIES = "A Tessa Calder Thriller — Book 1"
BOOK_AUTHOR = "David Seelmann"
BOOK_COPYRIGHT = "© 2026 David Seelmann"
BOOK_UUID = str(uuid.uuid5(uuid.NAMESPACE_DNS, "the-wifes-inventory-david-seelmann-book-1"))

COVER_PATH = "cover_1.jpg"
MAP_PATH = "Gemini_Generated_Image_texmwatexmwatexm.jpg"
MAP_TITLE = "Salt Point Estate Map"
EPUB_OUTPUT = "The_Wifes_Inventory.epub"
DOCX_OUTPUT = "The_Wifes_Inventory_print.docx"
PDF_OUTPUT = "The_Wifes_Inventory_print.pdf"


def ensure_cover_1600x2560(cover_path: str):
    """Verify cover_final.jpg exists and is a 1600x2560 RGB JPEG, upscaling if needed."""
    assert os.path.exists(cover_path), f"Cover file not found: {cover_path}"
    src_path = os.path.realpath(cover_path)
    with Image.open(src_path) as im:
        rgb = im.convert("RGB")
        w, h = rgb.size
        if (w, h) != (1600, 2560):
            # Scale proportionally to height 2560 (or width 1600), then center-fit/crop to 1600x2560
            scale = max(1600 / w, 2560 / h)
            new_w, new_h = int(round(w * scale)), int(round(h * scale))
            resized = rgb.resize((new_w, new_h), Image.Resampling.LANCZOS)
            left = max(0, (new_w - 1600) // 2)
            top = max(0, (new_h - 2560) // 2)
            final_im = resized.crop((left, top, left + 1600, top + 2560))
            final_im = final_im.filter(ImageFilter.UnsharpMask(radius=1.2, percent=110, threshold=2))
        else:
            final_im = rgb.copy()

    if os.path.islink(cover_path):
        os.unlink(cover_path)
    final_im.save(cover_path, format="JPEG", quality=95, subsampling=0, dpi=(300, 300))
    with Image.open(cover_path) as verify_im:
        assert verify_im.format == "JPEG"
        assert verify_im.mode == "RGB"
        assert verify_im.size == (1600, 2560)
        print(f"COVER VERIFIED: {cover_path} -> {verify_im.format}, {verify_im.mode}, {verify_im.size}")


def parse_markdown_chapters(manuscript_path: str):
    """Parse full_manuscript.md into a list of (title, blocks) tuples."""
    with open(manuscript_path, "r", encoding="utf-8") as f:
        raw = f.read()

    sections = [s.strip() for s in re.split(r"(?m)^---\s*$", raw) if s.strip()]
    chapters = []
    for sec in sections:
        lines = [line.strip() for line in sec.splitlines() if line.strip()]
        if not lines:
            continue
        if lines[0].startswith("# The Wife's Inventory"):
            continue
        title = lines[0].lstrip("#").strip()
        body_lines = sec.splitlines()[1:]
        paragraphs = []
        buf = []
        for line in body_lines:
            stripped = line.strip()
            if not stripped:
                if buf:
                    paragraphs.append("\n".join(buf))
                    buf = []
            else:
                buf.append(stripped)
        if buf:
            paragraphs.append("\n".join(buf))
        chapters.append((title, paragraphs))
    return chapters


def parse_back_matter(preview_path: str):
    """Parse back_matter_book2_preview.md into (title, subtitle, blocks)."""
    with open(preview_path, "r", encoding="utf-8") as f:
        raw = f.read().strip()

    lines = raw.splitlines()
    title = "Sneak Peek: The Caretaker's Ledger"
    subtitle = "A Tessa Calder Thriller — Book 2 by David Seelmann (Chapter 1 Preview)"
    body_lines = []
    for line in lines:
        s = line.strip()
        if s.startswith("# ") or s.startswith("### ") or s.startswith("## Chapter 1"):
            continue
        body_lines.append(line)

    paragraphs = []
    buf = []
    for line in body_lines:
        stripped = line.strip()
        if not stripped:
            if buf:
                paragraphs.append("\n".join(buf))
                buf = []
        else:
            buf.append(stripped)
    if buf:
        paragraphs.append("\n".join(buf))
    return title, subtitle, paragraphs


def inline_md_to_xhtml(text: str) -> str:
    """Convert inline markdown (**bold**, *italic*, `code`) to valid XHTML."""
    escaped = html.escape(text, quote=False)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", escaped)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    return escaped.replace("\n", "<br/>")


def blocks_to_xhtml(blocks) -> str:
    """Convert paragraph blocks into XHTML body paragraphs."""
    out = []
    first_para = True
    for b in blocks:
        if b.strip() == "***":
            out.append('<p class="scene-break">* * *</p>')
            first_para = True
            continue
        if b.startswith(">"):
            quote_lines = [
                inline_md_to_xhtml(line.lstrip(">").strip())
                for line in b.splitlines()
                if line.strip()
            ]
            joined_q = "<br/>".join(quote_lines)
            out.append(f"<blockquote><p>{joined_q}</p></blockquote>")
            first_para = False
            continue
        cls = ' class="first-para"' if first_para else ""
        out.append(f"<p{cls}>{inline_md_to_xhtml(b)}</p>")
        first_para = False
    return "\n".join(out)


def wrap_xhtml_doc(title: str, body_inner: str) -> str:
    return f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="en" lang="en">
<head>
  <meta charset="utf-8"/>
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" type="text/css" href="styles.css"/>
</head>
<body>
{body_inner}
</body>
</html>
"""


def build_epub(chapters, preview_data, cover_path: str, output_path: str):
    """Build a valid EPUB 3 archive with embedded cover_final.jpg and David Seelmann metadata."""
    css = """
body {
  font-family: Georgia, "Times New Roman", serif;
  line-height: 1.55;
  margin: 5%;
  color: #111111;
}
body.cover-body {
  margin: 0;
  padding: 0;
  text-align: center;
}
img.cover-img {
  max-width: 100%;
  max-height: 100%;
  height: auto;
  width: auto;
}
h1, h2, h3 {
  font-family: "Helvetica Neue", Arial, sans-serif;
  text-align: center;
  page-break-after: avoid;
}
h1 {
  font-size: 1.8em;
  margin-top: 2em;
  margin-bottom: 0.8em;
  letter-spacing: 0.04em;
}
h2 {
  font-size: 1.2em;
  font-weight: normal;
  margin-bottom: 1.5em;
  color: #444444;
}
p {
  margin: 0;
  text-indent: 1.4em;
  text-align: justify;
}
p.first-para, .front-matter p {
  text-indent: 0;
}
p.scene-break {
  text-indent: 0;
  text-align: center;
  margin: 1.4em 0;
  letter-spacing: 0.25em;
}
blockquote {
  margin: 1em 1.5em;
  font-style: italic;
}
blockquote p {
  text-indent: 0;
}
.title-box {
  text-align: center;
  margin-top: 18%;
}
.title-box p {
  text-indent: 0;
  text-align: center;
  margin: 0.6em 0;
}
.author-name {
  font-size: 1.35em;
  letter-spacing: 0.08em;
  margin-top: 2em;
}
.map-page {
  text-align: center;
  margin: 0;
  padding: 0;
}
.map-img {
  max-width: 100%;
  max-height: 92vh;
  height: auto;
  display: block;
  margin: 0 auto;
}
"""

    cover_xhtml = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="en" lang="en">
<head>
  <meta charset="utf-8"/>
  <title>Cover</title>
  <link rel="stylesheet" type="text/css" href="styles.css"/>
</head>
<body class="cover-body" epub:type="cover">
  <div>
    <img class="cover-img" src="cover.jpg" alt="The Wife's Inventory by David Seelmann"/>
  </div>
</body>
</html>
"""

    title_xhtml = wrap_xhtml_doc(
        BOOK_TITLE,
        f"""<div class="title-box">
  <h1>{html.escape(BOOK_TITLE)}</h1>
  <h2>{html.escape(BOOK_SUBTITLE)}</h2>
  <p><strong>{html.escape(BOOK_SERIES)}</strong></p>
  <p class="author-name"><strong>{html.escape(BOOK_AUTHOR)}</strong></p>
</div>""",
    )

    copyright_xhtml = wrap_xhtml_doc(
        "Copyright Page",
        f"""<div class="front-matter">
  <h1>Copyright</h1>
  <p><strong>{html.escape(BOOK_TITLE)}: {html.escape(BOOK_SUBTITLE)}</strong></p>
  <p>{html.escape(BOOK_SERIES)}</p>
  <p><strong>{html.escape(BOOK_COPYRIGHT)}</strong></p>
  <p>Author: {html.escape(BOOK_AUTHOR)}</p>
  <p>First Digital &amp; Print Edition — 2026</p>
  <p>Original suspense fiction by {html.escape(BOOK_AUTHOR)}. Characters, locales, and incidents portrayed in this novel are fictitious.</p>
</div>""",
    )

    map_xhtml = wrap_xhtml_doc(
        MAP_TITLE,
        f"""<div class="map-page">
  <img class="map-img" src="map.jpg" alt="{html.escape(MAP_TITLE)}"/>
</div>""",
    )

    manifest_items = [
        'id="css" href="styles.css" media-type="text/css"',
        'id="cover-image" href="cover.jpg" media-type="image/jpeg" properties="cover-image"',
        'id="map-image" href="map.jpg" media-type="image/jpeg"',
        'id="coverpage" href="cover.xhtml" media-type="application/xhtml+xml"',
        'id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"',
        'id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"',
        'id="titlepage" href="title.xhtml" media-type="application/xhtml+xml"',
        'id="copyrightpage" href="copyright.xhtml" media-type="application/xhtml+xml"',
        'id="mappage" href="map.xhtml" media-type="application/xhtml+xml"',
    ]
    spine_items = [
        '<itemref idref="coverpage" linear="yes"/>',
        '<itemref idref="titlepage"/>',
        '<itemref idref="copyrightpage"/>',
        '<itemref idref="mappage"/>',
    ]
    nav_links = [
        '<li><a href="cover.xhtml">Cover</a></li>',
        '<li><a href="title.xhtml">Title Page</a></li>',
        '<li><a href="copyright.xhtml">Copyright</a></li>',
        f'<li><a href="map.xhtml">{html.escape(MAP_TITLE)}</a></li>',
    ]
    ncx_points = []
    play_order = 1

    def add_ncx(point_id, label, src):
        nonlocal play_order
        ncx_points.append(
            f"""    <navPoint id="{point_id}" playOrder="{play_order}">
      <navLabel><text>{html.escape(label)}</text></navLabel>
      <content src="{src}"/>
    </navPoint>"""
        )
        play_order += 1

    add_ncx("nav-cover", "Cover", "cover.xhtml")
    add_ncx("nav-title", "Title Page", "title.xhtml")
    add_ncx("nav-copyright", "Copyright", "copyright.xhtml")
    add_ncx("nav-map", MAP_TITLE, "map.xhtml")

    chapter_files = {}
    for idx, (ch_title, ch_blocks) in enumerate(chapters, 1):
        fname = f"chapter_{idx:02d}.xhtml"
        item_id = f"ch{idx:02d}"
        body = f'<section epub:type="chapter">\n<h1>{html.escape(ch_title)}</h1>\n{blocks_to_xhtml(ch_blocks)}\n</section>'
        chapter_files[fname] = wrap_xhtml_doc(ch_title, body)
        manifest_items.append(f'id="{item_id}" href="{fname}" media-type="application/xhtml+xml"')
        spine_items.append(f'<itemref idref="{item_id}"/>')
        nav_links.append(f'<li><a href="{fname}">{html.escape(ch_title)}</a></li>')
        add_ncx(f"nav-{item_id}", ch_title, fname)

    prev_title, prev_sub, prev_blocks = preview_data
    prev_fname = "book2_preview.xhtml"
    prev_body = (
        f'<section epub:type="backmatter">\n'
        f"<h1>{html.escape(prev_title)}</h1>\n"
        f"<h2>{html.escape(prev_sub)}</h2>\n"
        f"{blocks_to_xhtml(prev_blocks)}\n</section>"
    )
    chapter_files[prev_fname] = wrap_xhtml_doc(prev_title, prev_body)
    manifest_items.append(f'id="book2preview" href="{prev_fname}" media-type="application/xhtml+xml"')
    spine_items.append('<itemref idref="book2preview"/>')
    nav_links.append(f'<li><a href="{prev_fname}">{html.escape(prev_title)}</a></li>')
    add_ncx("nav-book2preview", prev_title, prev_fname)

    nav_links_str = "\n    ".join(nav_links)
    nav_xhtml = wrap_xhtml_doc(
        "Table of Contents",
        f"""<nav epub:type="toc" id="toc">
  <h1>Table of Contents</h1>
  <ol>
    {nav_links_str}
  </ol>
</nav>""",
    )

    ncx_points_str = "\n".join(ncx_points)
    toc_ncx = f"""<?xml version="1.0" encoding="utf-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head>
    <meta name="dtb:uid" content="urn:uuid:{BOOK_UUID}"/>
    <meta name="dtb:depth" content="1"/>
    <meta name="dtb:totalPageCount" content="0"/>
    <meta name="dtb:maxPageNumber" content="0"/>
  </head>
  <docTitle><text>{html.escape(BOOK_TITLE)} — {html.escape(BOOK_AUTHOR)}</text></docTitle>
  <navMap>
{ncx_points_str}
  </navMap>
</ncx>
"""

    manifest_str = "\n    ".join(f"<item {item}/>" for item in manifest_items)
    spine_str = "\n    ".join(spine_items)
    content_opf = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="pub-id">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="pub-id">urn:uuid:{BOOK_UUID}</dc:identifier>
    <dc:title>{html.escape(BOOK_TITLE)}: {html.escape(BOOK_SUBTITLE)}</dc:title>
    <dc:creator>{html.escape(BOOK_AUTHOR)}</dc:creator>
    <dc:rights>{html.escape(BOOK_COPYRIGHT)}</dc:rights>
    <dc:language>en</dc:language>
    <meta property="dcterms:modified">2026-11-17T00:00:00Z</meta>
    <meta name="cover" content="cover-image"/>
  </metadata>
  <manifest>
    {manifest_str}
  </manifest>
  <spine toc="ncx">
    {spine_str}
  </spine>
</package>
"""

    container_xml = """<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""

    with open(cover_path, "rb") as cf:
        cover_bytes = cf.read()
    with open(MAP_PATH, "rb") as mf:
        map_bytes = mf.read()

    with zipfile.ZipFile(output_path, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        zf.writestr("META-INF/container.xml", container_xml, compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr("OEBPS/styles.css", css.strip(), compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr("OEBPS/cover.jpg", cover_bytes, compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr("OEBPS/map.jpg", map_bytes, compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr("OEBPS/cover.xhtml", cover_xhtml, compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr("OEBPS/content.opf", content_opf, compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr("OEBPS/toc.ncx", toc_ncx, compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr("OEBPS/nav.xhtml", nav_xhtml, compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr("OEBPS/title.xhtml", title_xhtml, compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr("OEBPS/copyright.xhtml", copyright_xhtml, compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr("OEBPS/map.xhtml", map_xhtml, compress_type=zipfile.ZIP_DEFLATED)
        for fname, content in chapter_files.items():
            zf.writestr(f"OEBPS/{fname}", content, compress_type=zipfile.ZIP_DEFLATED)


def add_formatted_runs(para, text: str):
    """Add text with inline **bold**, *italic*, and `code` runs to a python-docx paragraph."""
    token_re = re.compile(r"(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)")
    pos = 0
    for m in token_re.finditer(text):
        if m.start() > pos:
            para.add_run(text[pos : m.start()])
        tok = m.group(0)
        if tok.startswith("**") and tok.endswith("**"):
            r = para.add_run(tok[2:-2])
            r.bold = True
        elif tok.startswith("*") and tok.endswith("*"):
            r = para.add_run(tok[1:-1])
            r.italic = True
        elif tok.startswith("`") and tok.endswith("`"):
            r = para.add_run(tok[1:-1])
            r.font.name = "Courier New"
            r.font.size = Pt(10)
        pos = m.end()
    if pos < len(text):
        para.add_run(text[pos:])


def build_docx(chapters, preview_data, output_path: str):
    """Build a KDP 5.5 x 8.5 trade paperback print DOCX with David Seelmann front/back matter."""
    doc = Document()
    doc.core_properties.title = f"{BOOK_TITLE}: {BOOK_SUBTITLE}"
    doc.core_properties.author = BOOK_AUTHOR
    doc.core_properties.comments = BOOK_COPYRIGHT

    section = doc.sections[0]
    section.page_width = Inches(5.5)
    section.page_height = Inches(8.5)
    section.top_margin = Inches(0.75)
    section.bottom_margin = Inches(0.75)
    section.left_margin = Inches(0.8)
    section.right_margin = Inches(0.65)

    normal_style = doc.styles["Normal"]
    normal_style.font.name = "Georgia"
    normal_style.font.size = Pt(11)
    normal_style.paragraph_format.line_spacing = 1.25
    normal_style.paragraph_format.space_before = Pt(0)
    normal_style.paragraph_format.space_after = Pt(0)

    # Title Page
    tp_title = doc.add_paragraph()
    tp_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    tp_title.paragraph_format.space_before = Pt(108)
    tp_title.paragraph_format.space_after = Pt(12)
    r_title = tp_title.add_run(BOOK_TITLE.upper())
    r_title.bold = True
    r_title.font.size = Pt(22)

    tp_sub = doc.add_paragraph()
    tp_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    tp_sub.paragraph_format.space_after = Pt(20)
    r_sub = tp_sub.add_run(BOOK_SUBTITLE)
    r_sub.italic = True
    r_sub.font.size = Pt(12)

    tp_ser = doc.add_paragraph()
    tp_ser.alignment = WD_ALIGN_PARAGRAPH.CENTER
    tp_ser.paragraph_format.space_after = Pt(72)
    r_ser = tp_ser.add_run(BOOK_SERIES)
    r_ser.bold = True
    r_ser.font.size = Pt(11)

    tp_auth = doc.add_paragraph()
    tp_auth.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_auth = tp_auth.add_run(BOOK_AUTHOR.upper())
    r_auth.bold = True
    r_auth.font.size = Pt(14)

    doc.add_page_break()

    # Copyright Page
    cp_head = doc.add_paragraph()
    cp_head.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cp_head.paragraph_format.space_before = Pt(72)
    cp_head.paragraph_format.space_after = Pt(16)
    r_ch = cp_head.add_run(BOOK_COPYRIGHT)
    r_ch.bold = True
    r_ch.font.size = Pt(11)

    for line in [
        f"{BOOK_TITLE}: {BOOK_SUBTITLE}",
        f"{BOOK_SERIES} by {BOOK_AUTHOR}",
        "First Print & Digital Edition — 2026",
        f"Original suspense fiction by {BOOK_AUTHOR}. Characters, institutions, and events in this novel are fictitious.",
    ]:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(8)
        r = p.add_run(line)
        r.font.size = Pt(9.5)

    # Map Page
    doc.add_section(WD_SECTION.NEW_PAGE)
    p_map = doc.add_paragraph()
    p_map.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_map.paragraph_format.space_before = Pt(24)
    p_map.add_run().add_picture(MAP_PATH, width=Inches(4.0))

    def render_section(heading_text: str, subheading_text, blocks):
        doc.add_section(WD_SECTION.NEW_PAGE)
        h = doc.add_paragraph()
        h.alignment = WD_ALIGN_PARAGRAPH.CENTER
        h.paragraph_format.space_before = Pt(48)
        h.paragraph_format.space_after = Pt(18 if not subheading_text else 6)
        rh = h.add_run(heading_text.upper())
        rh.bold = True
        rh.font.size = Pt(15)

        if subheading_text:
            sh = doc.add_paragraph()
            sh.alignment = WD_ALIGN_PARAGRAPH.CENTER
            sh.paragraph_format.space_after = Pt(18)
            rsh = sh.add_run(subheading_text)
            rsh.italic = True
            rsh.font.size = Pt(11)

        first_para = True
        for b in blocks:
            if b.strip() == "***":
                sb = doc.add_paragraph()
                sb.alignment = WD_ALIGN_PARAGRAPH.CENTER
                sb.paragraph_format.space_before = Pt(10)
                sb.paragraph_format.space_after = Pt(10)
                sb.paragraph_format.first_line_indent = Inches(0)
                sb.add_run("* * *")
                first_para = True
                continue
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            if b.startswith(">"):
                p.paragraph_format.left_indent = Inches(0.35)
                p.paragraph_format.right_indent = Inches(0.25)
                p.paragraph_format.space_before = Pt(4)
                p.paragraph_format.space_after = Pt(4)
                p.paragraph_format.first_line_indent = Inches(0)
                clean_q = " ".join(line.lstrip(">").strip() for line in b.splitlines())
                add_formatted_runs(p, clean_q)
                first_para = False
                continue
            p.paragraph_format.first_line_indent = Inches(0 if first_para else 0.25)
            add_formatted_runs(p, b)
            first_para = False

    for ch_title, ch_blocks in chapters:
        render_section(ch_title, None, ch_blocks)

    prev_title, prev_sub, prev_blocks = preview_data
    render_section(prev_title, prev_sub, prev_blocks)

    doc.save(output_path)


def tex_escape(text: str) -> str:
    """Escape special LaTeX characters and convert inline markdown (**bold**, *italic*, `code`)."""
    placeholders = {}

    def stash(val: str) -> str:
        key = f"ZZZPLACEHOLDER{len(placeholders)}ZZZ"
        placeholders[key] = val
        return key

    # Stash inline formatting before escaping raw text
    def repl_bold(m):
        return stash(r"\textbf{" + tex_escape_plain(m.group(1)) + "}")

    def repl_italic(m):
        return stash(r"\textit{" + tex_escape_plain(m.group(1)) + "}")

    def repl_code(m):
        return stash(r"\texttt{" + tex_escape_plain(m.group(1)) + "}")

    s = re.sub(r"\*\*([^*]+)\*\*", repl_bold, text)
    s = re.sub(r"\*([^*]+)\*", repl_italic, s)
    s = re.sub(r"`([^`]+)`", repl_code, s)
    s = tex_escape_plain(s)
    for k, v in placeholders.items():
        s = s.replace(k, v)
    return s


def tex_escape_plain(s: str) -> str:
    s = s.replace("\\", r"\textbackslash{}")
    for ch, rep in [
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
        ("~", r"\textasciitilde{}"),
        ("^", r"\textasciicircum{}"),
    ]:
        s = s.replace(ch, rep)
    s = s.replace("—", "---").replace("–", "--").replace("…", r"\ldots{}")
    return s


def build_pdf(chapters, preview_data, output_path: str) -> int:
    """Compile a KDP-ready 5.5x8.5 print PDF via pdflatex and return exact page count."""
    tex_parts = [
        r"""\documentclass[11pt,twoside,openany]{book}
\usepackage[paperwidth=5.5in,paperheight=8.5in,top=0.75in,bottom=0.75in,inner=0.8in,outer=0.65in]{geometry}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{mathptmx}
\usepackage{microtype}
\usepackage{setspace}
\usepackage{graphicx}
\setstretch{1.15}
\setlength{\parindent}{0.25in}
\setlength{\parskip}{0pt}
\clubpenalty=10000
\widowpenalty=10000
\raggedbottom

\makeatletter
\renewcommand{\@makechapterhead}[1]{%
  \vspace*{36\p@}%
  {\parindent \z@ \centering \normalfont
    \Large\bfseries \MakeUppercase{#1}\par\nobreak
    \vskip 24\p@
  }}
\makeatother

\begin{document}
\pagestyle{empty}
\begin{center}
\vspace*{1.4in}
{\Huge\bfseries THE WIFE'S INVENTORY\par}
\vspace{0.2in}
{\large\itshape A Gripping Domestic Psychological Thriller\par}
\vspace{0.25in}
{\normalsize\bfseries A Tessa Calder Thriller --- Book 1\par}
\vfill
{\Large\bfseries DAVID SEELMANN\par}
\vspace*{0.8in}
\end{center}
\clearpage

\begin{center}
\vspace*{1.6in}
{\bfseries \copyright\ 2026 David Seelmann\par}
\vspace{0.2in}
{\small The Wife's Inventory: A Gripping Domestic Psychological Thriller\par}
{\small A Tessa Calder Thriller --- Book 1 by David Seelmann\par}
\vspace{0.15in}
{\footnotesize First Print \& Digital Edition --- 2026\par}
\vspace{0.15in}
{\footnotesize Original suspense fiction by David Seelmann. Characters, locales, and incidents portrayed in this novel are fictitious.\par}
\end{center}
\clearpage
\thispagestyle{empty}
\begin{center}
\vspace*{\fill}
\includegraphics[width=\textwidth,height=0.92\textheight,keepaspectratio]{map.jpg}
\vspace*{\fill}
\end{center}
\clearpage
\pagestyle{plain}
"""
    ]

    def append_blocks(blocks):
        first_para = True
        for b in blocks:
            if b.strip() == "***":
                tex_parts.append("\n\\medskip\\noindent\\centerline{*\\quad *\\quad *}\\medskip\n")
                first_para = True
                continue
            if b.startswith(">"):
                clean_q = " ".join(line.lstrip(">").strip() for line in b.splitlines())
                tex_parts.append(f"\n\\begin{{quote}}\n{tex_escape(clean_q)}\n\\end{{quote}}\n")
                first_para = False
                continue
            prefix = r"\noindent " if first_para else ""
            lines_escaped = [tex_escape(line) for line in b.splitlines()]
            tex_parts.append("\n" + prefix + r"\\ ".join(lines_escaped) + "\n")
            first_para = False

    for ch_title, ch_blocks in chapters:
        tex_parts.append(f"\n\\chapter*{{{tex_escape_plain(ch_title)}}}\n")
        append_blocks(ch_blocks)

    prev_title, prev_sub, prev_blocks = preview_data
    tex_parts.append(
        f"\n\\chapter*{{{tex_escape_plain(prev_title)}}}\n"
        f"\\begin{{center}}\\textit{{{tex_escape_plain(prev_sub)}}}\\end{{center}}\\vspace{{12pt}}\n"
    )
    append_blocks(prev_blocks)
    tex_parts.append("\n\\end{document}\n")

    tex_source = "".join(tex_parts)
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(MAP_PATH, "rb") as mf, open(os.path.join(tmpdir, "map.jpg"), "wb") as out_mf:
            out_mf.write(mf.read())
        tex_file = os.path.join(tmpdir, "book.tex")
        with open(tex_file, "w", encoding="utf-8") as f:
            f.write(tex_source)
        res = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "book.tex"],
            cwd=tmpdir,
            capture_output=True,
            text=True,
        )
        assert res.returncode == 0, f"pdflatex failed:\n{res.stdout[-2000:]}"
        pdf_tmp = os.path.join(tmpdir, "book.pdf")
        assert os.path.exists(pdf_tmp), "PDF output missing"
        with open(pdf_tmp, "rb") as src_f, open(output_path, "wb") as dst_f:
            dst_f.write(src_f.read())

        m = re.search(r"Output written on book\.pdf \((\d+) pages", res.stdout)
        assert m, "Could not parse page count from pdflatex output"
        return int(m.group(1))


def validate_outputs(epub_path: str, docx_path: str, pdf_path: str, expected_chapters: int, page_count: int):
    """Validate EPUB, DOCX, and PDF outputs and verify David Seelmann metadata and zero broken markdown."""
    assert os.path.exists(epub_path) and os.path.getsize(epub_path) > 100_000, "EPUB missing or too small"
    with zipfile.ZipFile(epub_path, "r") as zf:
        names = zf.namelist()
        assert names[0] == "mimetype", f"First entry in EPUB must be mimetype, got {names[0]}"
        assert zf.read("mimetype") == b"application/epub+zip", "Invalid mimetype content"
        assert "OEBPS/cover.jpg" in names, "cover.jpg missing from EPUB"
        assert "OEBPS/cover.xhtml" in names, "cover.xhtml missing from EPUB"

        opf_text = zf.read("OEBPS/content.opf").decode("utf-8")
        assert "<dc:creator>David Seelmann</dc:creator>" in opf_text, "Author David Seelmann missing in OPF"
        assert "© 2026 David Seelmann" in opf_text, "Copyright David Seelmann missing in OPF"
        assert 'properties="cover-image"' in opf_text, "cover-image property missing in OPF"

        forbidden_token = "[" + "Author Pen Name" + "]"
        for name in names:
            if name.endswith((".xml", ".opf", ".ncx", ".xhtml")):
                data = zf.read(name)
                ET.fromstring(data)
                txt = data.decode("utf-8")
                assert forbidden_token not in txt, f"Placeholder found in {name}"
                # Check that no raw unparsed **bold**, *italic*, or `backtick` markdown remains in rendered XHTML
                if name.endswith(".xhtml"):
                    cleaned_xhtml = txt.replace("* * *", "")
                    assert "*" not in cleaned_xhtml, f"Unrendered * markdown found in {name}"
                    assert "`" not in cleaned_xhtml, f"Unrendered backtick markdown found in {name}"

    assert os.path.exists(docx_path) and os.path.getsize(docx_path) > 100_000, "DOCX missing or too small"
    check_doc = Document(docx_path)
    assert check_doc.core_properties.author == "David Seelmann"
    assert len(check_doc.sections) == expected_chapters + 3
    full_docx_text = "\n".join(p.text for p in check_doc.paragraphs)
    assert "DAVID SEELMANN" in full_docx_text
    assert "© 2026 David Seelmann" in full_docx_text
    assert "THE CARETAKER'S LEDGER" in full_docx_text
    assert forbidden_token not in full_docx_text
    cleaned_docx = full_docx_text.replace("* * *", "")
    assert "*" not in cleaned_docx, "Unrendered * markdown in DOCX"
    assert "`" not in cleaned_docx, "Unrendered ` markdown in DOCX"

    assert os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 100_000, "PDF missing or too small"

    spine_cream_in = page_count * 0.0025
    spine_white_in = page_count * 0.002252
    print(
        f"VALIDATION PASS:\n"
        f"  - Author: {BOOK_AUTHOR} ({BOOK_COPYRIGHT})\n"
        f"  - {epub_path}: {os.path.getsize(epub_path):,} bytes (cover.jpg embedded, all XML/XHTML valid, 0 markdown leaks)\n"
        f"  - {docx_path}: {os.path.getsize(docx_path):,} bytes ({len(check_doc.sections)} print sections, {len(check_doc.paragraphs)} paragraphs)\n"
        f"  - {pdf_path}: {os.path.getsize(pdf_path):,} bytes | EXACT PRINT PAGE COUNT: {page_count} pages (5.5\" x 8.5\" trim)\n"
        f"  - KDP Paperback Spine Widths ({page_count} pages): Cream Paper = {spine_cream_in:.3f}\" ({spine_cream_in * 25.4:.2f} mm) | White Paper = {spine_white_in:.3f}\" ({spine_white_in * 25.4:.2f} mm)"
    )


def main():
    ensure_cover_1600x2560(COVER_PATH)
    chapters = parse_markdown_chapters("full_manuscript.md")
    assert len(chapters) == 23, f"Expected 23 chapters, got {len(chapters)}"
    preview_data = parse_back_matter("back_matter_book2_preview.md")

    build_epub(chapters, preview_data, COVER_PATH, EPUB_OUTPUT)
    build_docx(chapters, preview_data, DOCX_OUTPUT)
    page_count = build_pdf(chapters, preview_data, PDF_OUTPUT)
    validate_outputs(EPUB_OUTPUT, DOCX_OUTPUT, PDF_OUTPUT, expected_chapters=23, page_count=page_count)


if __name__ == "__main__":
    main()
