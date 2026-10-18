#!/usr/bin/env python3
"""Runs on GitHub when a "New video" issue is opened. You never run this yourself.
Adds a video card at the top of the Learn grid in index.html, in the same style
as the existing asthma video card."""
import datetime, html, io, json, os, re, sys, urllib.request
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
TOKEN = os.environ.get("GH_TOKEN", "")
MARKER = "<!-- NEW VIDEOS GO HERE (added automatically) -->"


def fail(msg):
    print("ERROR: " + msg)
    sys.exit(1)


def section(body, label):
    m = re.search(r"###\s*" + re.escape(label) + r"\s*\n(.*?)(?=\n###\s|\Z)", body, re.S)
    v = m.group(1).strip() if m else ""
    return "" if v == "_No response_" else v


def fetch(url, auth=False):
    req = urllib.request.Request(url, headers={"User-Agent": "video-bot"})
    if auth and TOKEN:
        req.add_header("Authorization", "Bearer " + TOKEN)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def slugify(text):
    return (re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]) or "video"


def main():
    body = os.environ.get("ISSUE_BODY", "")
    url = section(body, "YouTube link")
    m = re.search(r"(?:v=|youtu\.be/|shorts/|embed/|live/)([A-Za-z0-9_-]{11})", url)
    if not m:
        fail("No YouTube video ID found in: " + url)
    yid = m.group(1)

    index = ROOT / "index.html"
    page = index.read_text(encoding="utf-8")
    if MARKER not in page:
        fail("Marker comment missing from index.html")
    if f'data-video="{yid}"' in page:
        fail("This video is already on the website.")

    title = section(body, "Title on the website")
    if not title:
        try:
            title = json.loads(fetch("https://www.youtube.com/oembed?format=json&url=https://www.youtube.com/watch?v=" + yid))["title"]
        except Exception:
            fail("No title given and YouTube didn't return one. Is the video public?")
    desc = section(body, "Short description") or "A one-minute explainer for patients (Urdu, with English captions)."
    desc = " ".join(desc.split())

    slug = slugify(title)
    (ROOT / "videos").mkdir(exist_ok=True)
    thumb_rel = f"videos/{slug}.jpg"

    thumb_md = section(body, "Thumbnail")
    tm = re.search(r'src="(https://[^"]+)"', thumb_md) or re.search(r"\((https://[^)\s]+)\)", thumb_md)
    raw = None
    if tm:
        try:
            raw = fetch(tm.group(1), auth=True)
        except Exception:
            raw = None
    if raw is None:
        for name in ("maxresdefault", "hqdefault"):
            try:
                raw = fetch(f"https://i.ytimg.com/vi/{yid}/{name}.jpg")
                break
            except Exception:
                pass
    if raw is None:
        fail("Could not get a thumbnail.")
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    if img.width > 1200:
        img = img.resize((1200, round(img.height * 1200 / img.width)), Image.LANCZOS)
    img.save(ROOT / thumb_rel, "JPEG", quality=85, optimize=True, progressive=True)

    t = html.escape(title, quote=True)
    d = html.escape(desc, quote=True)
    card = f'''{MARKER}
      <article class="learn-card video-card" data-type="video">
        <a class="card-link" href="https://www.youtube.com/watch?v={yid}" target="_blank" rel="noopener" aria-label="Watch on YouTube: {t}"></a>
        <div class="learn-media video-media" data-yt-preview="{yid}">
          <img src="{thumb_rel}" alt="Video thumbnail: {t}" loading="lazy" onerror="this.onerror=null;this.src='https://i.ytimg.com/vi/{yid}/hqdefault.jpg'">
          <span class="media-kind">Video</span>
          <button type="button" class="play-btn" data-video="{yid}" aria-label="Play the video here on the website"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5.5v13l11-6.5z" fill="currentColor"/></svg>Play here</button>
        </div>
        <div class="learn-body">
          <h3>{t}</h3>
          <p>{d}</p>
          <div class="learn-meta"><span>Video · 1 min</span><span class="yt-link">Watch on YouTube ↗</span></div>
        </div>
      </article>'''
    page = page.replace(MARKER, card, 1)
    index.write_text(page, encoding="utf-8")

    today = datetime.date.today().isoformat()
    sm = ROOT / "sitemap.xml"
    if sm.exists():
        xml = sm.read_text(encoding="utf-8")
        sm.write_text(re.sub(r"(<loc>https://drzainkhan\.com/?(?:index\.html)?</loc>\s*<lastmod>)[^<]*(</lastmod>)",
                             r"\g<1>" + today + r"\g<2>", xml, count=1), encoding="utf-8")

    with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a", encoding="utf-8") as f:
        f.write("title=" + " ".join(title.split()).replace('"', "'") + "\n")
    print(f"Added '{title}' ({yid})")


if __name__ == "__main__":
    main()
