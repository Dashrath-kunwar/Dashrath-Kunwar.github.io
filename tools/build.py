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


# The left pane, defined once. Every page carries a SIDEBAR marker region and
# the build stamps this into all of them, so adding a section is a one-line
# change here rather than an edit to seven files that will drift apart.
MENU = [
    ("home", "index.html", "home"),
    ("writing", "writings.html", "writing"),
    ("thumos", "https://thumospress.com", "thumos"),
    ("rss", "feed.xml", "rss"),
]

TAGLINE = (
    "Amateur &middot; HTML fundamentalist &middot; Aspiring flaneurer &middot;\n"
    "        Dead languages and dead people &middot; Primary accounts enjoyer &middot;\n"
    "        Conscious Artix sufferer &middot; Midnight Qabristan stroller"
)

# Running document pages: one Markdown file rendered straight into one page.
# Everything writable from Obsidian lives here — no HTML editing required.
DOCS = {
    "home": ("home.md", "index.html", "HOME"),
}

# Obsidian drops attachments in posts/images/. They get copied into the served
# tree so the pages can reach them, and both link styles are rewritten to match.
UPLOADS_SRC = os.path.join(POSTS, "images")
UPLOADS_REL = "img/uploads"
UPLOADS_DST = os.path.join(ROOT, "img", "uploads")

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
        # Running documents live in posts/ so Obsidian sees them, but they
        # are whole pages of their own, not essays.
        if name.lower() in {md for md, _, _ in DOCS.values()}:
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

        content = markdown.markdown(expand_obsidian(body), extensions=MD_EXTENSIONS,
                                    output_format="html5")
        # Essays sit one level down, so their attachment links need ../.
        content = fix_image_paths(content, "../")
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
            "{{sidebar}}": build_sidebar("../", "writing"),
            "{{content}}": p["content"],
        }.items():
            page = page.replace(key, value)
        pages[os.path.join(OUT, f"{p['slug']}.html")] = page
    return pages


def build_entries(posts, limit=None):
    """The <li> rows for a post list. `limit` trims it down for the homepage."""
    shown = posts[:limit] if limit else posts
    if not shown:
        return '\n          <li class="empty">Nothing published yet.</li>\n        '
    rows = []
    for p in shown:
        iso = p["date"].isoformat()
        rows.append(
            f'\n          <li>\n'
            f'            <a href="{p["url"]}">{html.escape(p["title"])}</a>\n'
            f'            <time datetime="{iso}">{iso}</time>\n'
            f'          </li>'
        )
    if limit and len(posts) > limit:
        rows.append('\n          <li><a href="writings.html">all writings &rarr;</a></li>')
    return "".join(rows) + "\n        "


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


def build_sidebar(prefix, current):
    """The left pane for one page.

    `prefix` is what a root-level link needs from where the page sits: ""
    for pages at the root, "../" for essays, "/" for 404.html (which the
    server can serve for a miss at any depth).
    """
    rows = []
    for label, href, key in MENU:
        target = href if href.startswith("http") else prefix + href
        mark = ' aria-current="page"' if key == current else ""
        if key == "thumos":
            rows.append(
                f'          <li><a class="thumos" href="{target}" target="_blank"'
                f' rel="noopener noreferrer">'
                f'<img src="{prefix}img/thumos.png" alt="" width="64" height="64">{label}</a></li>'
            )
        else:
            rows.append(f'          <li><a href="{target}"{mark}>{label}</a></li>')
    menu = "\n".join(rows)
    return f'''
      <div class="sidebar-top">
        <p class="sitename"><a href="{prefix or './'}">Dashrath Kunwar</a></p>
      </div>

      <p class="subtitle">
        {TAGLINE}
      </p>

      <div class="profile">
        <img src="{prefix}img/preacher-in-pixelated-inferno.webp" width="1024" height="1024"
             alt="Pixel-art preacher in black robes, one finger raised mid-sermon, before a burning city.">
      </div>

      <nav class="menu" aria-label="Sections">
        <ul>
{menu}
        </ul>
      </nav>

      <div class="sidebar-foot">
        <button type="button" class="theme-toggle" id="theme-toggle" hidden>light</button>
      </div>
    '''


# Which section each root page belongs to, for the filled button.
PAGE_SECTION = {
    "index.html": "home",
    "writings.html": "writing",
    "install.html": None,
    "404.html": None,
}


def expand_obsidian(body):
    """Turn Obsidian's own embed syntax into Markdown the renderer understands.

    Obsidian writes ![[photo.png]] when you drag a file in. Nothing else on
    earth reads that, so it becomes a normal image here rather than something
    the author has to remember to rewrite by hand every time.
    """
    def embed(m):
        target = m.group(1).split("|")[0].strip()      # ![[file.png|500]]
        name = os.path.basename(target)
        return f"![]({UPLOADS_REL}/{name})"
    return re.sub(r"!\[\[([^\]]+)\]\]", embed, body)


def fix_image_paths(html_text, prefix):
    """Point attachment links at the copies in the served tree.

    Also mark every image lazy: essay and doc images are attachments dropped
    in from Obsidian, never the above-the-fold banner or profile art (those
    live in the hand-written template, not here), so deferring them is safe.
    """
    html_text = re.sub(r'src="(?:\./)?images/', f'src="{prefix}{UPLOADS_REL}/', html_text)
    if prefix:
        html_text = re.sub(rf'src="{UPLOADS_REL}/', f'src="{prefix}{UPLOADS_REL}/', html_text)
    html_text = re.sub(r'<img(?![^>]*\bloading=)', '<img loading="lazy" decoding="async"', html_text)
    return html_text


def sync_uploads(changed, check):
    """Mirror posts/images into img/uploads, dropping anything deleted."""
    wanted = {}
    if os.path.isdir(UPLOADS_SRC):
        for name in sorted(os.listdir(UPLOADS_SRC)):
            path = os.path.join(UPLOADS_SRC, name)
            if os.path.isfile(path) and not name.startswith("."):
                wanted[name] = open(path, "rb").read()

    for name, data in wanted.items():
        write_binary(os.path.join(UPLOADS_DST, name), data, changed, check)

    if os.path.isdir(UPLOADS_DST):
        for name in sorted(os.listdir(UPLOADS_DST)):
            if name not in wanted:
                changed.append(f"removed {UPLOADS_REL}/{name}")
                if not check:
                    os.remove(os.path.join(UPLOADS_DST, name))


def render_doc(md_name, prefix=""):
    """A running document: the Markdown rendered as-is, comments stripped."""
    src = os.path.join(POSTS, md_name)
    if not os.path.exists(src):
        return None
    _, body = parse_front_matter(open(src, encoding="utf-8").read())
    body = expand_obsidian(body)
    out = markdown.markdown(body, extensions=MD_EXTENSIONS, output_format="html5")
    out = fix_image_paths(out, prefix)
    # Markdown passes HTML comments through; the notes-to-self at the top of
    # these files are for the author, not for anyone reading the page source.
    out = re.sub(r"<!--.*?-->", "", out, flags=re.DOTALL).strip()
    if not out:
        return '\n        <p class="empty">Nothing here yet.</p>\n      '
    out = "\n".join(("        " + l) if l.strip() else l for l in out.split("\n"))
    return "\n" + out + "\n      "


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

    # The homepage doubles as the blog front page: the most recent handful,
    # then a link through to the full archive.
    home_path = os.path.join(ROOT, "index.html")
    writes[home_path] = replace_region(
        open(home_path, encoding="utf-8").read(), "RECENT", build_entries(posts, limit=5)
    )

    # ---- Running documents: home, about, projects, bookmarks.
    for md_name, page_name, marker in DOCS.values():
        page = os.path.join(ROOT, page_name)
        rendered = render_doc(md_name)
        if rendered is None or not os.path.exists(page):
            continue
        current = writes.get(page) or open(page, encoding="utf-8").read()
        writes[page] = replace_region(current, marker, rendered)

    # ---- The left pane, stamped into every page from one definition.
    for page_name, section in PAGE_SECTION.items():
        page = os.path.join(ROOT, page_name)
        if not os.path.exists(page):
            continue
        prefix = "/" if page_name == "404.html" else ""
        current = writes.get(page) or open(page, encoding="utf-8").read()
        writes[page] = replace_region(current, "SIDEBAR", build_sidebar(prefix, section))

    feed_path = os.path.join(ROOT, "feed.xml")
    feed = open(feed_path, encoding="utf-8").read()
    feed = replace_region(feed, "ITEMS", build_feed_items(posts))
    # Stamp the newest post's date. With no posts, leave whatever is already
    # there — using today's date would rewrite the feed on every new day and
    # produce a commit that changes nothing anyone can see.
    if posts:
        feed = re.sub(r"<lastBuildDate>.*?</lastBuildDate>",
                      f"<lastBuildDate>{rfc822(posts[0]['date'])}</lastBuildDate>", feed)
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

    # ---- Obsidian attachments into the served tree.
    sync_uploads(changed, args.check)

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
