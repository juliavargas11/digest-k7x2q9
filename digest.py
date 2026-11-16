"""Builds docs/index.html: a morning digest of what's spreading, urgent, or strange."""
import calendar, datetime as dt, html, re, socket
from pathlib import Path
import feedparser

HOURS = 30            # only look at stories newer than this
socket.setdefaulttimeout(20)

URGENT = ["evacuat", "outbreak", "emergency", "recall", "resign", "killed", "dead", "shooting",
          "explosion", "wildfire", "tornado", "hurricane", "earthquake", "missing", "arrest",
          "indict", "charged", "lockdown", "shutdown", "collapse", "crash", "investigation",
          "warning", "contaminat", "fraud", "verdict", "sentenced"]
ODD = ["first-ever", "first ever", "never before", "baffled", "unexplained", "mysterious",
       "record-breaking", "record breaking", "bizarre", "strange", "unusual", "rare ",
       "stunned", "viral", "found in", "discovered", "oldest", "largest ever", "unprecedented",
       "escaped", "loose", "stolen", "mystery", "ufo", "sinkhole", "bear", "alligator"]
STOP = set("the and for with that this from after over into about their they have will been were "
           "says said new more than what when who how its his her out but not are was has can may "
           "one two news".split())

def tokens(text):
    return {w for w in re.findall(r"[a-z0-9']+", text.lower()) if len(w) > 3 and w not in STOP}

def load_feeds():
    feeds = []
    for line in Path("feeds.txt").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) == 3:
                feeds.append(parts)
    return feeds

def fetch(feeds):
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=HOURS)
    items, failed = [], []
    for kind, name, url in feeds:
        try:
            d = feedparser.parse(url, agent="Mozilla/5.0 (news-digest personal reader)")
            if not d.entries:
                failed.append(f"{name} (no entries)")
                continue
            for e in d.entries:
                ts = e.get("published_parsed") or e.get("updated_parsed")
                when = dt.datetime.fromtimestamp(calendar.timegm(ts), dt.timezone.utc) if ts else None
                if when and when < cutoff:
                    continue
                title = html.unescape(e.get("title", "")).strip()
                summary = re.sub(r"<[^>]+>", " ", html.unescape(e.get("summary", "")))[:300].strip()
                if title:
                    items.append(dict(title=title, summary=summary, link=e.get("link", ""),
                                      source=name, kind=kind, when=when))
        except Exception as ex:
            failed.append(f"{name} ({type(ex).__name__})")
    return items, failed

def cluster(items):
    clusters = []
    for it in items:
        it["tok"] = tokens(it["title"])
        for c in clusters:
            inter = it["tok"] & c["tok"]
            union = it["tok"] | c["tok"]
            if union and len(inter) >= 3 and len(inter) / len(union) >= 0.35:
                c["items"].append(it)
                break
        else:
            clusters.append(dict(tok=it["tok"], items=[it]))
    return clusters

def hits(text, words):
    t = text.lower()
    return [w.strip() for w in words if w in t]

def score(c):
    text = " ".join(i["title"] + " " + i["summary"] for i in c["items"])
    c["sources"] = sorted({i["source"] for i in c["items"]})
    c["urgent"] = hits(text, URGENT)
    c["odd"] = hits(text, ODD)
    c["score"] = 3 * len(c["sources"]) + 2 * len(c["urgent"]) + 2 * len(c["odd"])
    c["lead"] = sorted(c["items"], key=lambda i: (i["kind"] != "national", -len(i["summary"])))[0]
    return c

def card(c):
    lead = c["lead"]
    others = "".join(f'<a href="{html.escape(i["link"])}">{html.escape(i["source"])}</a> '
                     for i in c["items"] if i is not lead)
    tags = "".join(f'<span class="tag">{html.escape(t)}</span>' for t in (c["urgent"][:3] + c["odd"][:3]))
    summ = f'<p>{html.escape(lead["summary"])}</p>' if lead["summary"] else ""
    also = f'<div class="also">Also: {others}</div>' if others else ""
    return (f'<div class="card"><a class="h" href="{html.escape(lead["link"])}">{html.escape(lead["title"])}</a>'
            f'<div class="meta">{html.escape(lead["source"])} &middot; {len(c["sources"])} outlet(s) {tags}</div>'
            f'{summ}{also}</div>')

def section(title, blurb, clusters, n=25):
    body = "".join(card(c) for c in clusters[:n]) or "<p class='meta'>Nothing today.</p>"
    return f"<h2>{title}</h2><p class='meta'>{blurb}</p>{body}"

def main():
    feeds = load_feeds()
    items, failed = fetch(feeds)
    clusters = [score(c) for c in cluster(items)]
    spreading = sorted([c for c in clusters if len(c["sources"]) >= 3], key=lambda c: -c["score"])
    used = {id(c) for c in spreading}
    urgent = sorted([c for c in clusters if id(c) not in used and c["urgent"]], key=lambda c: -c["score"])
    used |= {id(c) for c in urgent}
    strange = sorted([c for c in clusters if id(c) not in used and c["odd"]], key=lambda c: -c["score"])

    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=-5))).strftime("%A, %B %d, %Y %I:%M %p ET")
    page = f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Morning Digest</title>
<style>
:root{{--bg:#fafafa;--fg:#1a1a1a;--card:#fff;--mut:#666;--link:#0b57d0;--tag:#fde7c8}}
@media (prefers-color-scheme:dark){{:root{{--bg:#16181c;--fg:#eaeaea;--card:#20232a;--mut:#9aa;--link:#8ab4f8;--tag:#4a3a20}}}}
body{{font-family:system-ui,sans-serif;background:var(--bg);color:var(--fg);max-width:820px;margin:0 auto;padding:16px}}
.card{{background:var(--card);border-radius:8px;padding:12px 14px;margin:10px 0}}
.h{{font-weight:600;color:var(--link);text-decoration:none;font-size:1.05em}}
.meta{{color:var(--mut);font-size:.85em;margin-top:4px}} p{{margin:6px 0}}
.tag{{background:var(--tag);border-radius:4px;padding:1px 6px;margin-left:4px;font-size:.8em}}
.also a{{color:var(--link);font-size:.85em;margin-right:8px}} .also{{margin-top:6px;color:var(--mut)}}
</style></head><body>
<h1>Morning Digest</h1><p class="meta">Updated {now} &middot; {len(items)} stories from {len(feeds)} feeds, last {HOURS} hours</p>
{section("Spreading across outlets", "Same story at 3+ outlets. Likely already big or about to be.", spreading)}
{section("Urgent / breaking-type", "Urgency words, fewer outlets so far. Could be early.", urgent)}
{section("Strange and local-only", "Oddity words, little pickup. Possible hidden gems.", strange)}
<h2>Feeds that failed</h2><p class="meta">{html.escape(", ".join(failed)) or "None"}</p>
</body></html>"""
    Path("docs").mkdir(exist_ok=True)
    Path("docs/index.html").write_text(page, encoding="utf-8")
    print(f"{len(items)} stories, {len(clusters)} clusters, {len(failed)} failed feeds")

if __name__ == "__main__":
    main()
