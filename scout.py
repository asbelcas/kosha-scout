#!/usr/bin/env python3
"""KOSHA cloud scout (GitHub Actions, free, always-on): fetches public prize/competition
sources daily, keeps zero-entry-cost candidates, appends to scout-log.md.
Failure-tolerant: a dead source logs itself, never kills the run."""
import json, re, urllib.request, datetime, pathlib

OUT = pathlib.Path("scout-log.md")
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36 kosha-scout/1.0"}
SCAM = re.compile(r"(?i)(buy|purchase|deposit|entry fee|pay to enter|crypto invest|guaranteed income|per day from home)")

def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", "replace")

def money_max(text):
    vals = [int(m.replace("$","").replace(",","")) for m in re.findall(r"\$([0-9,]+)", text)]
    return max(vals, default=0)

lines = [f"\n## {datetime.date.today().isoformat()}\n"]

# 1) Devpost hackathons RSS (Cloudflare-fronted; may fail from some IPs — logged)
try:
    body = fetch("https://devpost.com/hackathons.rss")
    items = re.findall(r"<item>.*?<title>(.*?)</title>.*?<link>(.*?)</link>(.*?)</item>", body, re.S)[:40]
    hits = []
    for t, l, rest in items:
        blob = re.sub(r"<[^>]+>", " ", rest)
        prize = money_max(blob)
        if prize >= 1000 and not SCAM.search(blob):
            hits.append(f"- [hackathon] {re.sub(chr(60)+'[^>]+'+chr(62),'',t).strip()} | top prize ${prize:,} | {l.strip()}")
    lines.append(f"### devpost — {len(hits)} zero-cost candidates\n" + ("\n".join(hits) if hits else "- none today"))
except Exception as e:
    lines.append(f"### devpost — FETCH FAILED: {e}")

# 2) Kaggle (needs account API creds as repo secrets = operator-gated; stub logs status)
import os
if os.environ.get("KAGGLE_USERNAME"):
    lines.append("### kaggle — creds present; parser TODO next iteration")
else:
    lines.append("### kaggle — SKIPPED (no creds; operator gate: add KAGGLE_USERNAME/KEY as repo secrets)")

# 3) DrivenData competitions (social-good data science, free entry)
try:
    body = fetch("https://www.drivendata.org/competitions/")
    rows = [(h,t) for h,t in re.findall(r'href="(/competitions/[0-9]+[^"]*)"[^>]*>([^<]{5,90})<', body)[:40] if t.strip()]
    hits = [f"- [drivendata] {t.strip()} | https://www.drivendata.org{h}" for h, t in rows if not SCAM.search(t)]
    lines.append(f"### drivendata — {len(hits)} listed\n" + ("\n".join(hits) if hits else "- none parsed"))
except Exception as e:
    lines.append(f"### drivendata — FETCH FAILED: {e}")


# 4) Zindi (Africa/global data-science competitions, free entry)
try:
    body = fetch("https://zindi.africa/competitions")
    hits = []
    for m in re.finditer(r'href="(/competitions/[^"]+)"[^>]*>\s*([^<]{5,90}?)\s*<', body):
        h, t = m.group(1), re.sub(r"\s+", " ", m.group(2)).strip()
        if t and not SCAM.search(t):
            hits.append(f"- [zindi] {t} | https://zindi.africa{h}")
    if not hits:
        blocks = re.findall(r"(.{0,200}?USD[^<]{0,40}|.{0,200}?\$[0-9,]{3,}.{0,120})", body)[:10]
        hits = [f"- [zindi] (prize-block) {re.sub(chr(60)+'[^>]+'+chr(62),' ',b)[:140]}" for b in blocks]
    lines.append(f"### zindi — {len(hits)} listed\n" + ("\n".join(dict.fromkeys(hits)) if hits else "- none parsed"))
except Exception as e:
    lines.append(f"### zindi — FETCH FAILED: {e}")

# 5) GitHub bounty-labeled issues (unauthenticated search API, 60 req/hr — 1/day fine)
try:
    req = urllib.request.Request("https://api.github.com/search/issues?q=label:bounty+state:open+no:assignee&sort=created&order=desc&per_page=15", headers={**UA, "Accept": "application/vnd.github+json"})
    data = json.loads(urllib.request.urlopen(req, timeout=40).read().decode())
    hits = []
    for it in data.get("items", []):
        blob = (it.get("title", "") + " " + (it.get("body") or ""))[:600]
        if SCAM.search(blob):
            continue
        amt = money_max(blob)
        hits.append(f"- [bounty:{it['repository_url'].split('/repos/')[-1]}] {it['title'][:80]} | {'$'+format(amt,',') if amt else 'see issue'} | {it['html_url']}")
    lines.append(f"### github-bounties — {len(hits)} open\n" + ("\n".join(hits) if hits else "- none"))
except Exception as e:
    lines.append(f"### github-bounties — FETCH FAILED: {e}")

OUT.open("a").write("\n".join(lines) + "\n")
print("\n".join(lines)[:1800])
