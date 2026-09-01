#!/usr/bin/env python3
# Renders ~/NOTES/Batcave/personal website/Writing/*.md (status: ready) into
# writing/<slug>.html and regenerates the marked entry-list region in
# writing.html; separately renders personal website/bookmarks.md (a single
# running file, no status gate -- it always mirrors) into the marked region
# of bookmarks.html. Nothing else in the repo is ever touched. Run with
# --check for a dry run (reports, writes nothing).
#
# One bad Writing/*.md note aborts the whole run before anything is written.
# bookmarks.md has no such gate -- malformed lines are just skipped, not
# fatal, since it's meant to be a low-friction running list.

import html
import re
import sys
from datetime import datetime
from pathlib import Path

import markdown

REPO_ROOT = Path(__file__).resolve().parent.parent
VAULT_ROOT = Path.home() / "NOTES" / "Batcave" / "personal website"
VAULT_WRITING_DIR = VAULT_ROOT / "Writing"
BOOKMARKS_MD = VAULT_ROOT / "bookmarks.md"

WRITING_HTML = REPO_ROOT / "writing.html"
BOOKMARKS_HTML = REPO_ROOT / "bookmarks.html"
POSTS_DIR = REPO_ROOT / "writing"
TEMPLATE = REPO_ROOT / "tools" / "templates" / "post.html"

MD_EXTENSIONS = ["extra", "smarty", "sane_lists"]

ENTRIES_BEGIN = "<!-- BEGIN ENTRIES -->"
ENTRIES_END = "<!-- END ENTRIES -->"
BOOKMARKS_BEGIN = "<!-- BEGIN BOOKMARKS -->"
BOOKMARKS_END = "<!-- END BOOKMARKS -->"
GENERATED_PREFIX = "<!-- generated from Writing/"
GENERATED_SUFFIX = " by tools/build.py — do not hand-edit -->\n"

SLUG_RE = re.compile(r"^[a-z0-9-]+$")
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sept", "Oct", "Nov", "Dec"]


class BuildError(Exception):
    pass


def display_date(iso):
    d = datetime.strptime(iso, "%Y-%m-%d")
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


# --- Writing/*.md ------------------------------------------------------


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
    """Required-field and format checks for a status:ready note. Raises BuildError.
    excerpt is optional -- the site omits the <p class="excerpt"> entirely when unset."""
    name = path.name
    for field in ("title", "slug", "date"):
        if not fields.get(field):
            raise BuildError(f"{name}: missing required field '{field}'")

    slug = fields["slug"]
    if not SLUG_RE.match(slug):
        raise BuildError(f"{name}: slug '{slug}' must match [a-z0-9-]+")

    try:
        datetime.strptime(fields["date"], "%Y-%m-%d")
    except ValueError:
        raise BuildError(f"{name}: date '{fields['date']}' must be YYYY-MM-DD")


IMAGE_OR_WIKILINK_RE = re.compile(r"!\[|\[\[")


def render_body(path, raw_body):
    if IMAGE_OR_WIKILINK_RE.search(raw_body):
        raise BuildError(
            f"{path.name}: images and [[wikilinks]] aren't supported by the "
            "writing pipeline yet — remove them or publish by hand"
        )
    # no pull-quote/citation/section-break handling: the current design
    # doesn't have those elements. drop cap is pure CSS
    # (.article > p:first-of-type::first-letter), nothing to do here for it.
    return markdown.markdown(raw_body, extensions=MD_EXTENSIONS)


def render_post_page(fields, body_html):
    template = TEMPLATE.read_text(encoding="utf-8")
    page = template
    page = page.replace("{{TITLE}}", html.escape(fields["title"]))
    page = page.replace("{{DATE}}", display_date(fields["date"]))
    page = page.replace("{{BODY}}", body_html)
    marker = f"{GENERATED_PREFIX}{fields['_source_name']}{GENERATED_SUFFIX}"
    return marker + page


def render_entry(fields):
    slug = fields["slug"]
    title = html.escape(fields["title"])
    date = display_date(fields["date"])
    excerpt = fields.get("excerpt", "").strip()
    excerpt_html = f'\n        <p class="excerpt">{html.escape(excerpt)}</p>' if excerpt else ""
    return (
        "      <li class=\"entry\">\n"
        f"        <span class=\"entry-date\">{date}</span>\n"
        f'        <h2><a href="writing/{slug}.html">{title}</a></h2>'
        f"{excerpt_html}\n"
        "      </li>"
    )


# --- bookmarks.md --------------------------------------------------------

BOOKMARK_HEADER_RE = re.compile(r"^##\s+(.+)$")
# [Text](url) or [Text](url) - a description, description optional either way
BOOKMARK_LINK_RE = re.compile(r"^\[(.+?)\]\((.+?)\)(?:\s*-\s*(.+))?$")
# **Text** or **Text** - a description, for an entry with no link at all
BOOKMARK_TITLE_RE = re.compile(r"^\*\*(.+?)\*\*(?:\s*-\s*(.+))?$")


def parse_bookmarks(text):
    """One category per `## Heading`. Under it, one bookmark per line, either
    `[Text](url)` (a real link) or `**Text**` (just a name, no link) --
    either form can carry an optional ` - description` tail. No blank line
    required between entries, unlike normal markdown paragraphs, so this
    stays a running list you can just add a line to. Anything that matches
    neither pattern (blank lines, stray notes) is silently skipped, not an
    error -- this file has no gate."""
    categories = []
    current = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m = BOOKMARK_HEADER_RE.match(line)
        if m:
            current = {"name": m.group(1).strip(), "items": []}
            categories.append(current)
            continue
        if current is None:
            continue
        m = BOOKMARK_LINK_RE.match(line)
        if m:
            text_, url, note = m.group(1).strip(), m.group(2).strip(), m.group(3)
            current["items"].append({"text": text_, "url": url, "note": note.strip() if note else None})
            continue
        m = BOOKMARK_TITLE_RE.match(line)
        if m:
            text_, note = m.group(1).strip(), m.group(2)
            current["items"].append({"text": text_, "url": None, "note": note.strip() if note else None})
    return categories


def render_bookmarks_region(categories):
    lines = []
    for cat in categories:
        lines.append(f'    <h2>{html.escape(cat["name"])}</h2>')
        for item in cat["items"]:
            if item["url"]:
                title_html = f'<a href="{html.escape(item["url"])}">{html.escape(item["text"])}</a>'
            else:
                title_html = f'<strong>{html.escape(item["text"])}</strong>'
            note_html = f' <span class="bookmark-note">- {html.escape(item["note"])}</span>' if item["note"] else ""
            lines.append(f"    <p>{title_html}{note_html}</p>")
    return "\n".join(lines)


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


def replace_region(target, begin, end, inner, check, changes):
    text = target.read_text(encoding="utf-8")
    if begin not in text or end not in text:
        raise BuildError(f"{target.name}: missing {begin} / {end} markers — refusing to guess where content goes")
    block = f"{begin}\n{inner}\n{end}" if inner else f"{begin}\n{end}"
    new_text = re.sub(
        re.escape(begin) + r".*?" + re.escape(end),
        lambda _: block,  # lambda so backslashes/etc can't be read as backreferences
        text,
        flags=re.DOTALL,
    )
    sync_file(target, new_text, check, changes)


# --- main --------------------------------------------------------------


def build_writing(check, changes):
    if not TEMPLATE.exists():
        raise BuildError(f"missing template {TEMPLATE}")
    if not VAULT_WRITING_DIR.exists():
        raise BuildError(f"vault folder not found: {VAULT_WRITING_DIR}")

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
            errors.append(f"{path.name}: slug '{fields['slug']}' also used by {seen_slugs[fields['slug']]}")
            continue
        seen_slugs[fields["slug"]] = path.name
        try:
            rendered_bodies[fields["slug"]] = render_body(path, body)
        except BuildError as e:
            errors.append(str(e))
            continue
        ready_notes.append(fields)

    if errors:
        raise BuildError("\n".join(errors))

    for fields in ready_notes:
        page = render_post_page(fields, rendered_bodies[fields["slug"]])
        sync_file(POSTS_DIR / f"{fields['slug']}.html", page, check, changes)
    clean_orphans(seen_slugs.keys(), check, changes)

    ordered = sorted(ready_notes, key=lambda f: f["date"], reverse=True)
    entries = "\n".join(render_entry(f) for f in ordered)
    replace_region(WRITING_HTML, ENTRIES_BEGIN, ENTRIES_END, entries, check, changes)


def build_bookmarks(check, changes):
    if not BOOKMARKS_MD.exists():
        raise BuildError(f"bookmarks file not found: {BOOKMARKS_MD}")
    categories = parse_bookmarks(BOOKMARKS_MD.read_text(encoding="utf-8"))
    region = render_bookmarks_region(categories)
    replace_region(BOOKMARKS_HTML, BOOKMARKS_BEGIN, BOOKMARKS_END, region, check, changes)


def main():
    check = "--check" in sys.argv
    changes = []
    try:
        build_writing(check, changes)
        build_bookmarks(check, changes)
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
