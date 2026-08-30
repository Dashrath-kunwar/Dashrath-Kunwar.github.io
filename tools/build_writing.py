#!/usr/bin/env python3
# Renders ~/NOTES/Batcave/Writing/*.md (status: ready) into writing/<slug>.html
# and regenerates the entry list in writing.html. Nothing else in the repo is
# ever touched. Run with --check for a dry run (reports, writes nothing).
#
# One bad note aborts the whole run before anything is written — a personal
# essay site would rather fail loud than half-publish.

import html
import re
import sys
from datetime import datetime
from pathlib import Path

import markdown

REPO_ROOT = Path(__file__).resolve().parent.parent
VAULT_WRITING_DIR = Path.home() / "NOTES" / "Batcave" / "Writing"
WRITING_HTML = REPO_ROOT / "writing.html"
POSTS_DIR = REPO_ROOT / "writing"
TEMPLATE = REPO_ROOT / "tools" / "templates" / "post.html"

MD_EXTENSIONS = ["extra", "smarty", "sane_lists"]
BEGIN_MARK = "<!-- BEGIN ENTRIES -->"
END_MARK = "<!-- END ENTRIES -->"
GENERATED_PREFIX = "<!-- generated from Writing/"
GENERATED_SUFFIX = " by tools/build_writing.py — do not hand-edit -->\n"

SLUG_RE = re.compile(r"^[a-z0-9-]+$")
TYPES = {"essay", "poem", "note"}


class BuildError(Exception):
    pass


def parse_note(path):
    """Split a note into (frontmatter dict, body markdown). None if there's no frontmatter block."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None, None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None, None
    header, body = text[4:end], text[end + 5 :]
    fields = {}
    for line in header.splitlines():
        if not line.strip():
            continue
        key, _, value = line.partition(":")
        value = value.strip()
        value = re.sub(r"\s+#.*$", "", value)  # trailing ' # comment', not a bare #hashtag
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        fields[key.strip()] = value
    return fields, body.lstrip("\n")


def validate(path, fields):
    """Required-field and format checks for a status:ready note. Raises BuildError."""
    name = path.name
    for field in ("title", "slug", "date", "excerpt"):
        if not fields.get(field):
            raise BuildError(f"{name}: missing required field '{field}'")

    slug = fields["slug"]
    if not SLUG_RE.match(slug):
        raise BuildError(f"{name}: slug '{slug}' must match [a-z0-9-]+")

    try:
        datetime.strptime(fields["date"], "%Y-%m-%d")
    except ValueError:
        raise BuildError(f"{name}: date '{fields['date']}' must be YYYY-MM-DD")

    note_type = fields.get("type", "essay") or "essay"
    if note_type not in TYPES:
        raise BuildError(f"{name}: type '{note_type}' must be one of {sorted(TYPES)}")


# --- markdown -> site HTML -------------------------------------------------

PULL_QUOTE_RE = re.compile(r"^[ \t]*>\s*\[!pull\]\n(?:^[ \t]*>.*\n?)*", re.MULTILINE)
BLOCKQUOTE_RE = re.compile(r"(?:^[ \t]*>.*\n?)+", re.MULTILINE)
CITE_LINE_RE = re.compile(r"^—\s*(.+)$")


def render_inline(text):
    """Render a markdown fragment and strip the wrapping <p>...</p> — for text
    that needs bold/italic/links but has to end up inside something other than
    a bare paragraph (a pull-quote span, a citation)."""
    out = markdown.markdown(text.strip(), extensions=MD_EXTENSIONS)
    m = re.match(r"^<p>(.*)</p>\s*$", out, re.DOTALL)
    return m.group(1) if m else out


def strip_quote_prefix(block):
    lines = []
    for line in block.splitlines():
        lines.append(re.sub(r"^[ \t]*>\s?", "", line))
    return lines


def extract_pull_quotes(text):
    def repl(m):
        lines = strip_quote_prefix(m.group(0))[1:]  # drop the [!pull] line
        quote = render_inline(" ".join(l.strip() for l in lines if l.strip()))
        return f'\n<p class="pull-quote">{quote}</p>\n\n'

    return PULL_QUOTE_RE.sub(repl, text)


def extract_citations(text):
    """Blockquotes whose last line is '— source' get that line pulled out and
    replaced with a unique marker so it can be spliced back in as a real
    <cite> sibling after rendering, instead of ending up inside the <p>."""
    citations = {}
    counter = [0]

    def repl(m):
        lines = m.group(0).splitlines()
        stripped = strip_quote_prefix(m.group(0))
        last = stripped[-1].strip()
        cite_match = CITE_LINE_RE.match(last)
        if not cite_match:
            return m.group(0)
        marker = f"@@CITE{counter[0]}@@"
        citations[marker] = render_inline(cite_match.group(1))
        counter[0] += 1
        lines = lines[:-1]  # drop the citation line
        lines[-1] = lines[-1] + " " + marker
        return "\n".join(lines) + "\n"

    return BLOCKQUOTE_RE.sub(repl, text), citations


def splice_citations(body_html, citations):
    for marker, cite_html in citations.items():
        body_html = re.sub(
            r"\s*" + re.escape(marker) + r"\s*</p>",
            f"</p><cite>&mdash; {cite_html}</cite>",
            body_html,
        )
    return body_html


def apply_drop_cap(body_html):
    return re.sub(r"<p>", '<p class="drop">', body_html, count=1)


def apply_section_breaks(body_html):
    return body_html.replace("<p>⁂</p>", '<p class="section-break">⁂</p>')


IMAGE_OR_WIKILINK_RE = re.compile(r"!\[|\[\[")


def render_body(path, raw_body):
    if IMAGE_OR_WIKILINK_RE.search(raw_body):
        raise BuildError(
            f"{path.name}: images and [[wikilinks]] aren't supported by the "
            "writing pipeline yet — remove them or publish by hand"
        )
    text = extract_pull_quotes(raw_body)
    text, citations = extract_citations(text)
    body_html = markdown.markdown(text, extensions=MD_EXTENSIONS)
    body_html = splice_citations(body_html, citations)
    body_html = apply_drop_cap(body_html)
    body_html = apply_section_breaks(body_html)
    return body_html


# --- assembling pages / the entry list -------------------------------------


def tag_span(note_type, css_class="tag"):
    if note_type == "essay":
        return ""
    return f'<span class="{css_class} {css_class}-{note_type}">[{note_type}]</span>\n      '


def render_post_page(fields, body_html):
    template = TEMPLATE.read_text(encoding="utf-8")
    title = html.escape(fields["title"])
    date_dotted = fields["date"].replace("-", ".")
    note_type = fields.get("type", "essay") or "essay"
    page = template
    page = page.replace("{{TITLE}}", title)
    page = page.replace("{{DATE}}", date_dotted)
    page = page.replace("{{TAG_SPAN}}", tag_span(note_type))
    page = page.replace("{{BODY}}", body_html)
    marker = f"{GENERATED_PREFIX}{fields['_source_name']}{GENERATED_SUFFIX}"
    return marker + page


def render_entry(fields):
    slug = fields["slug"]
    title = html.escape(fields["title"])
    excerpt = html.escape(fields["excerpt"])
    date_dotted = fields["date"].replace("-", ".")
    note_type = fields.get("type", "essay") or "essay"
    tag = tag_span(note_type, css_class="tag").replace("\n      ", "\n          ")
    return (
        "      <li class=\"entry\">\n"
        "        <div class=\"entry-meta\">\n"
        f"          {tag}<time class=\"entry-date\">{date_dotted}</time>\n"
        "        </div>\n"
        f'        <h3><a href="writing/{slug}.html">{title}</a></h3>\n'
        f'        <p class="excerpt">{excerpt}</p>\n'
        "      </li>"
    )


# --- write-if-changed / orphan cleanup / region replace ---------------------


def sync_file(path, content, check, changes):
    existing = path.read_bytes() if path.exists() else None
    new_bytes = content.encode("utf-8")
    if existing == new_bytes:
        return
    changes.append(("write", path))
    if not check:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(new_bytes)


def clean_orphans(desired_slugs, check, changes):
    if not POSTS_DIR.exists():
        return
    for f in POSTS_DIR.glob("*.html"):
        try:
            first_line = f.read_text(encoding="utf-8").split("\n", 1)[0] + "\n"
        except UnicodeDecodeError:
            continue
        if not first_line.startswith(GENERATED_PREFIX):
            continue  # hand-written file, never touched by this script
        if f.stem in desired_slugs:
            continue
        changes.append(("delete", f))
        if not check:
            f.unlink()


def replace_entries_region(ready_notes, check, changes):
    text = WRITING_HTML.read_text(encoding="utf-8")
    if BEGIN_MARK not in text or END_MARK not in text:
        raise BuildError(
            f"writing.html: missing {BEGIN_MARK} / {END_MARK} markers — "
            "refusing to guess where the entry list goes"
        )
    ordered = sorted(ready_notes, key=lambda f: f["date"], reverse=True)
    block = "\n".join(render_entry(f) for f in ordered)
    inner = f"{BEGIN_MARK}\n{block}\n      {END_MARK}" if block else f"{BEGIN_MARK}\n      {END_MARK}"
    new_text = re.sub(
        re.escape(BEGIN_MARK) + r".*?" + re.escape(END_MARK),
        lambda _: inner,  # lambda so backslashes/etc in titles can't be read as backreferences
        text,
        flags=re.DOTALL,
    )
    sync_file(WRITING_HTML, new_text, check, changes)


# --- main --------------------------------------------------------------


def main():
    check = "--check" in sys.argv

    if not TEMPLATE.exists():
        print(f"error: missing template {TEMPLATE}", file=sys.stderr)
        return 1
    if not VAULT_WRITING_DIR.exists():
        print(f"error: vault folder not found: {VAULT_WRITING_DIR}", file=sys.stderr)
        return 1

    ready_notes = []
    rendered_bodies = {}
    seen_slugs = {}
    errors = []

    for path in sorted(VAULT_WRITING_DIR.glob("*.md")):
        fields, body = parse_note(path)
        if fields is None or fields.get("status") != "ready":
            continue
        fields["_source_name"] = path.name
        try:
            validate(path, fields)
        except BuildError as e:
            errors.append(str(e))
            continue
        if fields["slug"] in seen_slugs:
            errors.append(
                f"{path.name}: slug '{fields['slug']}' also used by {seen_slugs[fields['slug']]}"
            )
            continue
        seen_slugs[fields["slug"]] = path.name
        try:
            rendered_bodies[fields["slug"]] = render_body(path, body)
        except BuildError as e:
            errors.append(str(e))
            continue
        ready_notes.append(fields)

    if errors:
        for e in errors:
            print(f"error: {e}", file=sys.stderr)
        return 1

    changes = []
    try:
        for fields in ready_notes:
            page = render_post_page(fields, rendered_bodies[fields["slug"]])
            sync_file(POSTS_DIR / f"{fields['slug']}.html", page, check, changes)
        clean_orphans(seen_slugs.keys(), check, changes)
        replace_entries_region(ready_notes, check, changes)
    except BuildError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if not changes:
        print("nothing to do")
        return 0

    verb = "would" if check else "did"
    for action, path in changes:
        rel = path.relative_to(REPO_ROOT)
        print(f"{verb} {action}: {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
