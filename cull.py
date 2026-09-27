#!/usr/bin/env python3
"""
cull - an agent that reads 100+ sources and decides what matters to you.

Built at the Own Your Intelligence Hackathon (YC, SF, Sept 27 2026).

The loop:
  1. pull today's items from Hacker News + arXiv (100+)
  2. score each against your taste memory
  3. write the 5 worth your time, with reasons
  4. your thumbs up/down rewrites the taste memory -> next run is sharper

Memory is plain markdown files you can open and edit, the GBrain model:
a brain is yours when you can read it. Set GBRAIN_API_URL + GBRAIN_API_KEY
to mirror every memory write to a hosted GBrain instance.

No dependencies. Python 3.8+.
"""
import json, os, re, sys, time, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from datetime import date
from math import log1p

HERE = os.path.dirname(os.path.abspath(__file__))
MEM = os.path.join(HERE, "memory")
TASTE = os.path.join(MEM, "taste.md")
JUDGMENTS = os.path.join(MEM, "judgments.md")
FEEDBACK = os.path.join(MEM, "feedback.md")
BRIEF = os.path.join(HERE, "briefing.md")

def http(url, timeout=10, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers=headers or {},
                                 method="POST" if data else "GET")
    req.add_header("User-Agent", "cull/0.1 (personal research tool; contact: user)")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def cached(name, fn, ttl=600):
    path = os.path.join(MEM, ".cache_%s.json" % name)
    try:
        if os.path.exists(path) and time.time() - os.path.getmtime(path) < ttl:
            return json.load(open(path))
    except Exception:
        pass
    got = fn()
    try:
        os.makedirs(MEM, exist_ok=True)
        json.dump(got, open(path, "w"))
    except Exception:
        pass
    return got

# ---------------- sources ----------------

def fetch_hn():
    raw = http("https://hn.algolia.com/api/v1/search?tags=front_page")
    out = []
    for h in json.loads(raw).get("hits", []):
        out.append({
            "source": "hn",
            "title": h.get("title", "").strip(),
            "url": h.get("url") or ("https://news.ycombinator.com/item?id=" + h.get("objectID", "")),
            "summary": "",
            "points": h.get("points") or 0,
        })
    return out

def fetch_arxiv(cats=("cs.AI", "cs.LG", "cs.CL"), max_results=90):
    q = "+OR+".join("cat:" + c for c in cats)
    url = ("http://export.arxiv.org/api/query?search_query=" + q +
           "&sortBy=submittedDate&sortOrder=descending&max_results=" + str(max_results))
    ns = {"a": "http://www.w3.org/2005/Atom"}
    out = []
    try:
        payload = http(url, timeout=15)
    except Exception:
        time.sleep(3)  # arxiv rate-limits; one polite retry
        payload = http(url, timeout=15)
    root = ET.fromstring(payload)
    for e in root.findall("a:entry", ns):
        title = " ".join((e.findtext("a:title", default="", namespaces=ns) or "").split())
        summ = " ".join((e.findtext("a:summary", default="", namespaces=ns) or "").split())
        link = e.findtext("a:id", default="", namespaces=ns) or ""
        out.append({"source": "arxiv", "title": title, "url": link.strip(),
                    "summary": summ, "points": 0})
    return out

# ---------------- memory (gbrain-shaped: plain files, yours) ----------------

def read_taste():
    """taste.md lines: '+ keyword:weight' boosts, '- keyword:weight' penalizes."""
    rules = []
    if os.path.exists(TASTE):
        for line in open(TASTE):
            m = re.match(r"\s*([+-])\s*(.+?)\s*:\s*(\d+(?:\.\d+)?)\s*$", line)
            if m:
                rules.append([m.group(1), m.group(2).lower(), float(m.group(3))])
    return rules

def write_taste(rules):
    with open(TASTE, "w") as f:
        f.write("# taste - what cull thinks you care about. edit me, i am yours.\n")
        for sign, kw, w in sorted(rules, key=lambda r: -r[2]):
            f.write("%s %s:%g\n" % (sign, kw, w))

def seen_titles():
    seen = set()
    if os.path.exists(JUDGMENTS):
        for line in open(JUDGMENTS):
            title = line.split("|", 1)[-1].strip()
            seen.add(re.sub(r"[^a-z0-9 ]", "", title.lower())[:80])
    return seen

def norm(t):
    return re.sub(r"[^a-z0-9 ]", "", t.lower())[:80]

def gbrain_mirror(note):
    """If hosted GBrain creds are set, mirror the note there. Local files stay source of truth."""
    api, key = os.environ.get("GBRAIN_API_URL"), os.environ.get("GBRAIN_API_KEY")
    if not (api and key):
        return False
    try:
        body = json.dumps({"note": note, "ts": time.time()}).encode()
        http(api, data=body, headers={"Authorization": "Bearer " + key,
                                      "Content-Type": "application/json"}, timeout=8)
        return True
    except Exception as e:
        print("(gbrain mirror failed, memory kept locally: %s)" % e, file=sys.stderr)
        return False

# ---------------- judgment ----------------

def score(item, rules, seen):
    text = (item["title"] + " " + item.get("summary", "")).lower()
    s, hits = 0.0, []
    for sign, kw, w in rules:
        if kw in text:
            s += w if sign == "+" else -w
            hits.append("%s%s (%+g)" % (kw, "" if len(kw) > 18 else "", w if sign == "+" else -w))
    s += 0.15 * log1p(item.get("points", 0))
    if norm(item["title"]) in seen:
        s -= 5
        hits.append("seen before (-5)")
    return s, hits

def llm_rerank(cands, rules):
    """Optional: if OPENAI_API_KEY is set, an LLM re-judges the shortlist. Falls back silently."""
    key = os.environ.get("OPENAI_API_KEY")
    if not key or not cands:
        return None
    taste = ", ".join("%s%s" % (sgn, kw) for sgn, kw, _ in rules[:20])
    listing = "\n".join("%d. %s - %s" % (i, c[0]["title"], c[0].get("summary", "")[:220])
                        for i, c in enumerate(cands))
    prompt = ("Taste profile (what this person cares about): %s\n\n"
              "Items:\n%s\n\nReply with JSON only: a list of the 5 best indexes "
              "(0-based) for this person, best first." % (taste, listing))
    body = json.dumps({
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
    }).encode()
    try:
        raw = http("https://api.openai.com/v1/chat/completions", data=body, timeout=20,
                   headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
        txt = json.loads(raw)["choices"][0]["message"]["content"]
        idx = json.loads(re.search(r"\[.*\]", txt, re.S).group(0))
        return [int(i) for i in idx][:5]
    except Exception as e:
        print("(llm rerank skipped: %s)" % e, file=sys.stderr)
        return None

# ---------------- commands ----------------

def cmd_run():
    os.makedirs(MEM, exist_ok=True)
    if not os.path.exists(TASTE):
        write_taste([["+", "mechanistic interpretability", 3], ["+", "interpretability", 2.5],
                     ["+", "agents", 2], ["+", "evals", 2.5], ["+", "retrieval", 2],
                     ["+", "llm", 1], ["+", "ai", 1], ["+", "open source", 1.5], ["+", "benchmark", 1.5], ["+", "alignment", 2],
                     ["-", "crypto", 2], ["-", "nft", 3], ["-", "web3", 2]])
    items, errors = [], []
    fetchers = [("hn", fetch_hn), ("arxiv", fetch_arxiv)]
    if os.environ.get("CULL_DEMO"):
        fetchers = [("hn", fetch_hn),
                    ("today's cached hn snapshot", lambda: json.load(open(os.path.join(HERE, "seed_items.json"))))]
    for name, fn in fetchers:
        try:
            got = cached(name, fn)
            items += got
            print("pulled %d from %s" % (len(got), name))
        except Exception as e:
            errors.append("%s: %s" % (name, e))
            print("source %s failed (%s) - continuing" % (name, e))
    if errors and os.path.exists(os.path.join(HERE, "seed_items.json")):
        snap_items = json.load(open(os.path.join(HERE, "seed_items.json")))
        have = {it["title"] for it in items}
        add = [it for it in snap_items if it["title"] not in have]
        items += add
        print("(+%d items from today's bundled snapshot, covering the failed source)" % len(add))
    uniq, seen_t = [], set()
    for it in items:
        n = norm(it["title"])
        if n and n not in seen_t:
            seen_t.add(n)
            uniq.append(it)
    items = uniq
    if not items:
        snap = os.path.join(HERE, "seed_items.json")
        if os.path.exists(snap):
            items = json.load(open(snap))
            print("live sources unreachable - using bundled snapshot from 2026-09-27 (stage-wifi mode)")
        else:
            sys.exit("no sources reachable; check network")
    rules, seen = read_taste(), seen_titles()
    scored = sorted(((score(it, rules, seen), it) for it in items),
                    key=lambda x: -x[0][0])
    order = llm_rerank(scored[:25], rules)
    top = [scored[i] for i in order] if order else scored[:5]

    lines = ["# cull briefing - %s" % date.today().isoformat(),
             "%d items read, %d worth your time:\n" % (len(items), len(top))]
    for i, ((s, hits), it) in enumerate(top, 1):
        lines.append("%d. **%s**\n   %s\n   why: %s\n" %
                     (i, it["title"], it["url"], "; ".join(hits[:3]) or "top of the pile"))
    if errors:
        lines.append("_(degraded: %s)_" % "; ".join(errors))
    text = "\n".join(lines)
    open(BRIEF, "w").write(text)
    with open(JUDGMENTS, "a") as f:
        for _, it in top:
            f.write("%s | %s\n" % (date.today().isoformat(), it["title"]))
    gbrain_mirror("cull briefing %s: %s" % (date.today().isoformat(),
                                            "; ".join(it["title"] for _, it in top)))
    print("\n" + text)
    print("\nnext: python3 cull.py feedback <1-%d> up|down  ->  rerun and watch it learn" % len(top))

def cmd_feedback(n, verdict):
    if not os.path.exists(BRIEF):
        sys.exit("run first: python3 cull.py run")
    lines = [l for l in open(BRIEF) if re.match(r"\d+\. \*\*", l)]
    if not (1 <= n <= len(lines)):
        sys.exit("no item %d in last briefing" % n)
    title = re.sub(r"^\d+\. \*\*|\*\*$", "", lines[n - 1]).strip()
    rules = read_taste()
    delta = 1.0 if verdict == "up" else -1.0
    words = [w for w in re.findall(r"[a-z][a-z\-]{3,}", title.lower())
             if w not in ("with", "from", "that", "this", "using", "via", "your", "their")]
    known = {kw for _, kw, _ in rules}
    touched = [w for w in words if w in known][:3] or words[:2]
    for w in touched:
        for r in rules:
            if r[1] == w:
                r[2] = max(0.5, r[2] + delta) if r[0] == "+" else r[2]
                break
        else:
            rules.append(["+" if delta > 0 else "-", w, 1.0])
    write_taste(rules)
    if verdict == "down":
        with open(JUDGMENTS, "a") as f:  # a downvote means "seen it, stop showing me"
            f.write("%s | %s\n" % (date.today().isoformat(), title))
    with open(FEEDBACK, "a") as f:
        f.write("%s | %s | %s | nudged: %s\n" % (date.today().isoformat(), verdict, title, ", ".join(touched)))
    gbrain_mirror("cull feedback: %s on '%s'" % (verdict, title))
    print("taste updated (%s: %s). rerun `python3 cull.py run` - the ranking moves." %
          (verdict, ", ".join(touched)))

if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "run":
        cmd_run()
    elif len(sys.argv) == 4 and sys.argv[1] == "feedback":
        cmd_feedback(int(sys.argv[2]), sys.argv[3])
    else:
        print(__doc__)
