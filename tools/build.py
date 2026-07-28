#!/usr/bin/env python3
"""Build essay pages from Markdown and refresh the index, feed and sitemap.

Write a post in posts/, run this (or let the GitHub Action run it), and every
piece of bookkeeping updates itself:

    posts/2026-07-27-some-essay.md  ->  writings/some-essay.html
                                        writings.html   (entry added)
                                        feed.xml        (item added)
                                        sitemap.xml     (url added)
                                        sw.js           (cache bumped)

Only the regions between the BEGIN/END marker comments are touched, so the rest
of every file stays hand-written.

    python tools/build.py            # publish
    python tools/build.py --drafts   # include posts marked `draft: true`
    python tools/build.py --check    # report what would change, write nothing
"""

import argparse
import datetime as dt
import hashlib
import html
import os
import re
import sys
import urllib.parse

try:
    import markdown
except ImportError:
    sys.exit("Missing dependency. Run:  pip install markdown")

SITE_URL = "https://dashrathkunwar.in"

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                  # the web root (contains index.html)
POSTS = os.path.join(ROOT, "posts")
OUT = os.path.join(ROOT, "writings")
TEMPLATE = os.path.join(HERE, "templates", "post.html")

MD_EXTENSIONS = [
    "extra",       # tables, footnotes, definition lists, fenced code
    "smarty",      # curly quotes and proper em/en dashes
    "sane_lists",
]


# --------------------------------------------------------------------------
# Reading posts
# --------------------------------------------------------------------------

FILENAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)\.(?:md|markdown)$")


def parse_front_matter(raw):
    """Pull the `---` fenced key: value header off the top of a post."""
    meta, body = {}, raw
    if raw.lstrip().startswith("---"):
        raw = raw.lstrip()
        end = raw.find("\n---", 3)
        if end != -1:
            header = raw[3:end]
            body = raw[end + 4:].lstrip("\n")
            for line in header.strip().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or ":" not in line:
                    continue
                key, _, value = line.partition(":")
                value = value.strip()
                # Only unwrap a matched pair of quotes. Blindly stripping quote
                # characters would mangle a title like:  He said "hello"
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                    value = value[1:-1]
                meta[key.strip().lower()] = value
    return meta, body


def summarise(html_body, limit=160):
    """First sentence-ish of the post, for meta description and feed."""
    text = re.sub(r"<[^>]+>", " ", html_body)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut + "…"


def load_posts(include_drafts):
    if not os.path.isdir(POSTS):
        return [], []          # callers unpack two values

    posts, skipped = [], []
    for name in sorted(os.listdir(POSTS)):
        if not name.lower().endswith((".md", ".markdown")):
            continue
        if name.startswith("."):
            continue

        path = os.path.join(POSTS, name)
        raw = open(path, encoding="utf-8").read()
        meta, body = parse_front_matter(raw)

        if str(meta.get("draft", "")).lower() in ("true", "yes", "1") and not include_drafts:
            skipped.append(name)
            continue

        m = FILENAME_RE.match(name)
        date_str = meta.get("date") or (m.group(1) if m else "")
        slug = meta.get("slug") or (m.group(2) if m else os.path.splitext(name)[0])

        if not date_str:
            sys.exit(
                f"{name}: no date. Name the file YYYY-MM-DD-slug.md "
                f"or add `date: YYYY-MM-DD` to the front matter."
            )
        try:
            date = dt.date.fromisoformat(date_str)
        except ValueError:
            sys.exit(f"{name}: date '{date_str}' is not YYYY-MM-DD.")

        title = meta.get("title")
        if not title:
            sys.exit(f"{name}: no title. Add `title: ...` to the front matter.")

        content = markdown.markdown(body, extensions=MD_EXTENSIONS, output_format="html5")
        # Indent to sit neatly inside <article> in the template.
        content = "\n".join(("      " + l) if l.strip() else l for l in content.split("\n"))

        posts.append(
            {
                "file": name,
                "slug": slug,
                "date": date,
                "title": title,
                "description": meta.get("description") or summarise(content),
                "content": content,
                "url": f"writings/{slug}.html",
            }
        )

    posts.sort(key=lambda p: (p["date"], p["slug"]), reverse=True)   # newest first
    return posts, skipped


# --------------------------------------------------------------------------
# Writing output
# --------------------------------------------------------------------------

def replace_region(text, name, new_body):
    """Swap whatever sits between <!-- BEGIN name --> and <!-- END name -->."""
    pattern = re.compile(
        r"(<!--\s*BEGIN " + re.escape(name) + r".*?-->)(.*?)(<!--\s*END " + re.escape(name) + r"\s*-->)",
        re.DOTALL,
    )
    if not pattern.search(text):
        sys.exit(f"Could not find the '{name}' markers. Was the file edited by hand?")
    return pattern.sub(lambda m: m.group(1) + new_body + m.group(3), text)


def human_date(d):
    return f"{d.day} {d:%B %Y}"


def rfc822(d):
    return dt.datetime(d.year, d.month, d.day).strftime("%a, %d %b %Y 00:00:00 +0000")


def render_posts(posts, template):
    pages = {}
    for p in posts:
        canonical = f"{SITE_URL}/{p['url']}"
        page = template
        for key, value in {
            "{{title}}": html.escape(p["title"], quote=True),
            "{{description}}": html.escape(p["description"], quote=True),
            "{{canonical}}": canonical,
            # Percent-encoded for the no-JavaScript share link's query string.
            "{{canonical_url}}": urllib.parse.quote(canonical, safe=""),
            "{{title_url}}": urllib.parse.quote(p["title"], safe=""),
            "{{slug}}": p["slug"],
            "{{date_iso}}": p["date"].isoformat(),
            "{{date_human}}": human_date(p["date"]),
            "{{content}}": p["content"],
        }.items():
            page = page.replace(key, value)
        pages[os.path.join(OUT, f"{p['slug']}.html")] = page
    return pages


def build_entries(posts):
    if not posts:
        return '\n      <li class="empty">Nothing published yet.</li>\n      '
    rows = []
    for p in posts:
        rows.append(
            f'\n      <li>\n'
            f'        <a href="{p["url"]}">{html.escape(p["title"])}</a>\n'
            f'        <time datetime="{p["date"].isoformat()}">{human_date(p["date"])}</time>\n'
            f'      </li>'
        )
    return "".join(rows) + "\n      "


def build_feed_items(posts):
    if not posts:
        return "\n\n    "
    items = []
    for p in posts:
        url = f"{SITE_URL}/{p['url']}"
        items.append(
            f'\n    <item>\n'
            f'      <title>{html.escape(p["title"])}</title>\n'
            f'      <link>{url}</link>\n'
            f'      <guid isPermaLink="true">{url}</guid>\n'
            f'      <pubDate>{rfc822(p["date"])}</pubDate>\n'
            f'      <description>{html.escape(p["description"])}</description>\n'
            f'    </item>'
        )
    return "".join(items) + "\n\n    "


def build_sitemap_urls(posts):
    if not posts:
        return "\n  "
    urls = []
    for p in posts:
        urls.append(
            f'\n  <url>\n'
            f'    <loc>{SITE_URL}/{p["url"]}</loc>\n'
            f'    <lastmod>{p["date"].isoformat()}</lastmod>\n'
            f'    <priority>0.7</priority>\n'
            f'  </url>'
        )
    return "".join(urls) + "\n  "


def write_binary(path, data, changed, check):
    """Write bytes only when they differ, recording the change."""
    old = open(path, "rb").read() if os.path.exists(path) else None
    if old == data:
        return False
    changed.append(os.path.relpath(path, ROOT))
    if not check:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "wb").write(data)
    return True


def precached_paths(sw_text):
    """The asset list the service worker holds cache-first.

    Read straight out of sw.js so the two can't drift: anything the worker
    precaches must feed the hash below, or editing it would never reach a
    returning visitor.
    """
    block = re.search(r"const PRECACHE = \[(.*?)\];", sw_text, re.DOTALL)
    if not block:
        return []
    return [p for p in re.findall(r"'([^']+)'", block.group(1)) if not p.endswith("/")]


def cache_token(pages, writes, sw_text):
    """Short content hash, so the service worker invalidates on real changes.

    Reads pending content out of `writes` rather than off disk — hashing the
    old on-disk copy would leave the token one build behind and cause a second,
    empty commit every time.
    """
    h = hashlib.md5()
    tracked = set(precached_paths(sw_text))
    # The templates aren't precached but they change every generated page.
    tracked.update(["index.html", "writings.html", "style.css"])

    for path in sorted(tracked):
        full = os.path.join(ROOT, *path.split("/"))
        if full in writes:
            h.update(writes[full].encode("utf-8"))
        elif os.path.exists(full):
            h.update(open(full, "rb").read())
    for path in sorted(pages):
        h.update(pages[path].encode("utf-8"))
    return h.hexdigest()[:8]


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--drafts", action="store_true", help="include drafts")
    ap.add_argument("--check", action="store_true", help="report changes, write nothing")
    args = ap.parse_args()

    posts, skipped = load_posts(args.drafts)
    template = open(TEMPLATE, encoding="utf-8").read()
    pages = render_posts(posts, template)

    writes = dict(pages)

    index_path = os.path.join(ROOT, "writings.html")
    writes[index_path] = replace_region(
        open(index_path, encoding="utf-8").read(), "ENTRIES", build_entries(posts)
    )

    feed_path = os.path.join(ROOT, "feed.xml")
    feed = open(feed_path, encoding="utf-8").read()
    feed = replace_region(feed, "ITEMS", build_feed_items(posts))
    newest = posts[0]["date"] if posts else dt.date.today()
    feed = re.sub(r"<lastBuildDate>.*?</lastBuildDate>",
                  f"<lastBuildDate>{rfc822(newest)}</lastBuildDate>", feed)
    writes[feed_path] = feed

    sitemap_path = os.path.join(ROOT, "sitemap.xml")
    writes[sitemap_path] = replace_region(
        open(sitemap_path, encoding="utf-8").read(), "POSTS", build_sitemap_urls(posts)
    )

    sw_path = os.path.join(ROOT, "sw.js")
    sw = open(sw_path, encoding="utf-8").read()
    writes[sw_path] = re.sub(r"const CACHE = '[^']*';",
                             f"const CACHE = 'dk-{cache_token(pages, writes, sw)}';", sw)

    changed = []
    for path, content in writes.items():
        old = open(path, encoding="utf-8").read() if os.path.exists(path) else None
        if old != content:
            changed.append(os.path.relpath(path, ROOT))
            if not args.check:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                open(path, "w", encoding="utf-8", newline="\n").write(content)

    # ---- A PDF per essay, written next to its page.
    pdf_ok = True
    try:
        import pdfgen
    except ImportError:
        pdf_ok = False
        print("note: fpdf2 not installed, skipping PDFs (pip install fpdf2)")

    if pdf_ok:
        for p in posts:
            target = os.path.join(OUT, f"{p['slug']}.pdf")
            data = pdfgen.render_bytes(p["title"], human_date(p["date"]), p["content"])
            write_binary(target, data, changed, args.check)

    # Remove pages whose source Markdown is gone.
    if os.path.isdir(OUT):
        keep = {os.path.basename(p) for p in pages}
        keep_pdf = {os.path.splitext(k)[0] + ".pdf" for k in keep}
        for name in sorted(os.listdir(OUT)):
            if name.startswith("_"):
                continue          # files starting with _ are templates/mockups
            if name.endswith(".html") and name not in keep:
                stale = True
            elif name.endswith(".pdf") and name not in keep_pdf:
                stale = True
            else:
                stale = False
            if stale:
                changed.append(f"removed writings/{name}")
                if not args.check:
                    os.remove(os.path.join(OUT, name))

    # ---- No zip archives. Removed deliberately: the only download offered
    # anywhere on the site is the per-essay PDF above. Don't reinstate them
    # without asking. Clear out anything an older build left behind.
    if not args.check:
        downloads = os.path.join(ROOT, "downloads")
        if os.path.isdir(downloads):
            for name in sorted(os.listdir(downloads)):
                changed.append(f"removed downloads/{name}")
                os.remove(os.path.join(downloads, name))
            os.rmdir(downloads)

    print(f"{len(posts)} post(s) published" + (f", {len(skipped)} draft(s) skipped" if skipped else ""))
    for p in posts:
        print(f"  {p['date']}  {p['url']}")
    for s in skipped:
        print(f"  draft     posts/{s}")

    if not changed:
        print("\nNothing to update.")
    else:
        print(("\nWould change:" if args.check else "\nUpdated:"))
        for c in changed:
            print(f"  {c}")


if __name__ == "__main__":
    main()
