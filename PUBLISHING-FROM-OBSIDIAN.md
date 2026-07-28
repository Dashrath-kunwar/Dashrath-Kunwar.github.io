# Writing in Obsidian and publishing to dashrathkunwar.in

This is the whole process, assuming you know nothing. Read it once end to end,
do the one-time setup, and after that publishing takes about forty seconds.

---

## Part 1 — One-time setup (about 10 minutes, you do this once, ever)

### 1.1 Install GitHub Desktop

This is the app that moves files from your computer to your website. You will
never need to type a git command.

1. Go to **desktop.github.com**.
2. Click **Download for Windows**.
3. Run the installer and open GitHub Desktop.
4. Click **Sign in to GitHub.com** and sign in with your GitHub account.

### 1.2 Get the website onto your computer

1. In GitHub Desktop, click **File** → **Clone repository**.
2. Click the **GitHub.com** tab.
3. Find **Dashrath-Kunwar.github.io** in the list and click it.
4. Look at **Local path**. That is the folder on your computer where the site
   will live. Note it down — you need it in the next step. Something like
   `C:\Users\You\Documents\GitHub\Dashrath-Kunwar.github.io`.
5. Click **Clone** and wait.

### 1.3 Point Obsidian at the posts folder

You want Obsidian writing straight into the site's `posts` folder, so there is
no copying files around later.

1. Open Obsidian.
2. Click **Open another vault** (the icon at the bottom-left that looks like a
   vault door).
3. Click **Open folder as vault**.
4. Navigate to the folder from step 1.2 and go **into** the `posts` folder.
5. Click **Select Folder**.

Obsidian is now editing the site's posts directly. Everything you write here is
one click away from being published.

### 1.4 Turn off one Obsidian default

Obsidian likes to put attachments in odd places. Fix that now:

1. **Settings** (the gear, bottom-left) → **Files and links**.
2. Set **Default location for new attachments** to
   **In subfolder under current folder**.
3. Set **Subfolder name** to `images`.

Setup is done. You never repeat any of Part 1.

---

## Part 2 — Writing a post

### 2.1 Make the file

In Obsidian press **Ctrl+N** for a new note. Name it like this:

```
2026-08-14-the-weight-of-a-small-room
```

**The name matters.** The rules:

- Start with the date, `YYYY-MM-DD`, then a hyphen.
- Then the words of the title, lowercase, hyphens instead of spaces.
- No spaces. No capitals. No apostrophes, commas, colons or question marks.

That name becomes the web address:
`dashrathkunwar.in/writings/the-weight-of-a-small-room.html`

### 2.2 The header block

At the very top of the note, before anything else, type this:

```markdown
---
title: The Weight of a Small Room
date: 2026-08-14
---
```

Rules for that block:

- Three hyphens on their own line to open, three to close.
- `title:` is the headline as you want it to appear — real capitals, spaces,
  punctuation all fine here.
- `date:` must be `YYYY-MM-DD` and should match the filename.
- Leave one blank line after the closing `---`, then start writing.

**If your title contains a colon**, wrap it in quotes:

```markdown
title: "The Room: A Study"
```

Two optional extras:

```markdown
description: One sentence used on Google and in the RSS feed.
draft: true
```

`draft: true` means "not ready" — the post stays on your computer and never
appears on the site. Delete that line when you want it published.

### 2.3 Writing the body

Everything below the header block is normal Markdown.

**Paragraphs.** Just type. Leave a blank line between paragraphs. One blank
line, not two.

```markdown
This is one paragraph.

This is a second paragraph.
```

**Sub-headings.** Two hashes and a space for a section, three for a
sub-section. Never use one hash — the title in your header block is already
the page's top heading.

```markdown
## A section heading

### A smaller heading underneath it
```

**Bold and italic.**

```markdown
**bold text** and *italic text*
```

**A quotation.** A `>` and a space at the start of the line:

```markdown
> The past does not only influence the future — it creates it.
```

**Lists.** A hyphen and a space for bullets, `1.` for numbers:

```markdown
- first thing
- second thing

1. first step
2. second step
```

**A link.** Square brackets for the words, round brackets for the address:

```markdown
[Thumos Press](https://thumospress.com)
```

**A dividing line.** Three hyphens on their own line, with blank lines above
and below:

```markdown
---
```

**Dashes and quotes.** Type two hyphens `--` for an em dash and it becomes —
automatically. Straight quotes `"like this"` become curly “like this”. You do
not need to do anything special.

### 2.4 Adding an image

1. Drag the image file straight into the Obsidian note where you want it.
2. Obsidian saves it into `posts/images/` and writes a link for you that looks
   like `![[my-photo.jpg]]`.
3. **Change that link.** Obsidian's `![[...]]` format is Obsidian-only and the
   website does not understand it. Rewrite it as:

```markdown
![A short description of the picture](images/my-photo.jpg)
```

The words inside the square brackets are the description read aloud to blind
readers. Write a real description, not "image".

**Before you drag it in**, make the picture smaller. A photo straight off a
phone is 4–8 MB and will make the page painfully slow. Aim for under 400 KB and
no wider than about 1600 pixels. Any free online image resizer will do it.

### 2.5 Check it before publishing

Read it once in Obsidian's reading view (**Ctrl+E** toggles). If the headings
and lists look right there, they will look right on the site.

---

## Part 3 — Publishing (about 40 seconds)

1. **Save** in Obsidian (**Ctrl+S**).
2. Open **GitHub Desktop**. Your new file is listed on the left.
3. Bottom-left, in the **Summary** box, type anything at all — `new post` is
   fine. It is just a note to yourself.
4. Click **Commit to main**.
5. Click **Push origin** at the top.

That is it. Wait about a minute, then open **dashrathkunwar.in/writings.html**
and your post is there.

### What happens in that minute

A robot on GitHub notices the new file and automatically:

- builds the essay page at `writings/your-post.html`
- makes a **PDF** of it that readers can download
- adds it to the **Writings** list, newest first
- adds it to the **RSS feed** so subscribers get it
- adds it to the **sitemap** so Google finds it
- rebuilds the **zip** of all essays
- updates the offline cache so returning readers see the new version

You do none of that by hand. Never edit `writings.html`, `feed.xml` or
`sitemap.xml` yourself — the robot overwrites them.

---

## Part 4 — When something goes wrong

**The post didn't appear after two minutes.**
Go to your repository on github.com and click the **Actions** tab. A green tick
means it worked (try a hard refresh: **Ctrl+Shift+R**). A red cross means the
build failed — click it to see why. It is nearly always one of the two problems
below.

**Red cross: "no title" or "no date".**
Your header block is wrong. Check that you have three hyphens above and below,
that `title:` and `date:` each have a colon and a space after them, and that the
date is `YYYY-MM-DD` with no slashes.

**Red cross: something about a colon.**
Your title has a colon in it and isn't in quotes. Change
`title: The Room: A Study` to `title: "The Room: A Study"`.

**GitHub Desktop says nothing has changed.**
You forgot to save in Obsidian. Press **Ctrl+S** and look again.

**The picture doesn't show up.**
You left Obsidian's `![[photo.jpg]]` format in. It must be
`![description](images/photo.jpg)`.

**I want to unpublish something.**
Delete the `.md` file in Obsidian, then commit and push in GitHub Desktop. The
page, its PDF and its feed entry all disappear on the next build.

---

## The cheat sheet

Everything you actually need, in one block:

```markdown
---
title: Your Headline Here
date: 2026-08-14
---

Opening paragraph.

## A section heading

Another paragraph with **bold**, *italic*, and a
[link](https://example.com).

### A smaller heading

- a bullet
- another bullet

> a quotation

![description of picture](images/photo.jpg)

Closing paragraph.
```

Save → GitHub Desktop → Summary → **Commit to main** → **Push origin** → done.
