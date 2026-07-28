"""Render an essay to a printable PDF.

Uses the site's own Crimson Pro so the download looks like the page it came
from. The static weights in tools/fonts/ were instantiated from Google's
variable originals; fpdf2 can't read a variable font directly.

Deliberately plain: black text on white, generous margins, no artwork. The
point is something pleasant to read on a device or on paper, not a facsimile
of the web page.
"""

import datetime as dt
import os
import re
from fpdf import FPDF
from fpdf.fonts import TextStyle

FONTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
SITE_NAME = "dashrathkunwar.in"


class Essay(FPDF):
    def __init__(self, title, date_human):
        super().__init__(format="A4", unit="mm")
        self.essay_title = title
        self.essay_date = date_human
        self.set_margins(28, 24, 28)
        self.set_auto_page_break(True, margin=24)
        self.add_font("Crimson", "", os.path.join(FONTS, "CrimsonPro-Regular.ttf"))
        self.add_font("Crimson", "B", os.path.join(FONTS, "CrimsonPro-Bold.ttf"))
        self.add_font("Crimson", "I", os.path.join(FONTS, "CrimsonPro-Italic.ttf"))
        self.set_font("Crimson", "", 12)

    def footer(self):
        # Page 1 carries the title block, so it doesn't need a running footer.
        if self.page_no() == 1:
            return
        self.set_y(-18)
        self.set_font("Crimson", "", 9)
        self.set_text_color(120)
        self.cell(0, 8, SITE_NAME, align="L")
        self.cell(0, 8, str(self.page_no()), align="R")
        self.set_text_color(0)


def _clean(body_html):
    """Trim the HTML down to what fpdf2's write_html actually understands."""
    html = body_html
    # Drop attributes it ignores but which confuse its parser.
    html = re.sub(r'\s+(?:class|id|datetime|loading|fetchpriority)="[^"]*"', "", html)
    # <cite> inside a blockquote becomes an attribution line.
    html = re.sub(r"<cite>(.*?)</cite>", r"<br><i>— \1</i>", html, flags=re.DOTALL)
    # It has no <pre> support worth the name; keep the code but as plain text.
    html = html.replace("<pre><code>", "<blockquote>").replace("</code></pre>", "</blockquote>")
    html = html.replace("<pre>", "<blockquote>").replace("</pre>", "</blockquote>")
    # Headings shift down one level: the essay title is the document's h1.
    # h3 first, so the h2 rewrite below doesn't collide with the result.
    html = re.sub(r"<(/?)h3>", r"<\1h4>", html)
    html = re.sub(r"<(/?)h2>", r"<\1h3>", html)
    return html


def render_bytes(title, date_human, body_html):
    """Build the PDF and hand back its bytes.

    A fixed creation date keeps the output byte-identical between builds —
    otherwise every run would produce a "changed" PDF and the Action would
    push an empty commit each time.
    """
    pdf = Essay(title, date_human)
    pdf.set_creation_date(dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc))
    pdf.set_title(title)
    pdf.set_author("Dashrath Kunwar")
    pdf.add_page()

    # --- title block
    pdf.set_font("Crimson", "B", 26)
    pdf.multi_cell(0, 11, title)
    pdf.ln(1)
    pdf.set_font("Crimson", "", 10.5)
    pdf.set_text_color(110)
    pdf.cell(0, 6, date_human.upper(), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0)
    pdf.ln(5)

    # --- body
    pdf.set_font("Crimson", "", 12)
    pdf.write_html(
        _clean(body_html),
        tag_styles={
            "h3": TextStyle(font_family="Crimson", font_style="B", font_size_pt=16,
                            t_margin=6, b_margin=2),
            "h4": TextStyle(font_family="Crimson", font_style="B", font_size_pt=13.5,
                            t_margin=5, b_margin=2),
            "blockquote": TextStyle(font_family="Crimson", font_style="I", font_size_pt=12,
                                    l_margin=10, t_margin=3, b_margin=3),
        },
    )

    # --- colophon
    pdf.ln(6)
    pdf.set_font("Crimson", "", 9.5)
    pdf.set_text_color(120)
    pdf.multi_cell(0, 5, f"Originally published at {SITE_NAME}")
    pdf.set_text_color(0)

    return bytes(pdf.output())
