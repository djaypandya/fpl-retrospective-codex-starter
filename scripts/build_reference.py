"""Build a season reference file that stops a model misplacing players.

The problem this solves: a language model's training data is older than the
current season. Ask it about an FPL video and it will confidently put Marc Guéhi
at Crystal Palace, Alexander Isak at Newcastle, and it will not know that
Coventry, Hull and Ipswich are in the league at all. Names spoken in a video get
silently mapped onto last season's reality.

This writes a single source of truth for the current season, ordered so that the
highest-risk facts come first:

  1. Players who changed club, written as explicit corrections
  2. New arrivals with no Premier League record
  3. The 20 clubs, with promoted and relegated marked
  4. Duplicate surnames, so "Palmer" resolves to the right person
  5. Every squad in full, with position, price and points so far
  6. Leading scorers

Each entry is a self-contained sentence or row, because retrieval tools chunk a
document and a chunk has to carry its own meaning.

Run::

    python3.12 scripts/build_reference.py            # writes .md and .pdf
    python3.12 scripts/build_reference.py --no-pdf
"""

from __future__ import annotations

import argparse
import json
import ssl
import subprocess
import urllib.request
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
API = "https://fantasy.premierleague.com/api/bootstrap-static/"
PRIOR = REPO / "data" / "raw" / "bootstrap_static_smoke.json"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
POS = {1: "Goalkeeper", 2: "Defender", 3: "Midfielder", 4: "Forward"}
POS_SHORT = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def fetch() -> dict:
    with urllib.request.urlopen(API, timeout=90, context=_ssl_context()) as r:
        return json.load(r)


def full_name(e: dict) -> str:
    name = f"{e['first_name']} {e['second_name']}".strip()
    return name if name and name != e["web_name"] else e["web_name"]


def build(bootstrap: dict, prior: dict) -> str:
    clubs = {t["id"]: t["name"] for t in bootstrap["teams"]}
    short = {t["id"]: t["short_name"] for t in bootstrap["teams"]}
    prior_clubs = {t["id"]: t["name"] for t in prior["teams"]}
    was_at = {e["code"]: prior_clubs[e["team"]] for e in prior["elements"]}

    els = bootstrap["elements"]
    finished = [e for e in bootstrap["events"] if e["finished"]]
    last_gw = max((e["id"] for e in finished), default=0)
    promoted = sorted(set(clubs.values()) - set(prior_clubs.values()))
    relegated = sorted(set(prior_clubs.values()) - set(clubs.values()))

    movers, arrivals = [], []
    for e in els:
        now = clubs[e["team"]]
        if e["code"] in was_at:
            if was_at[e["code"]] != now:
                movers.append((e, was_at[e["code"]], now))
        else:
            arrivals.append((e, now))
    movers.sort(key=lambda t: -t[0]["total_points"])
    arrivals.sort(key=lambda t: -t[0]["total_points"])

    dupes = {n for n, c in Counter(e["web_name"] for e in els).items() if c > 1}
    by_club = defaultdict(list)
    for e in els:
        by_club[clubs[e["team"]]].append(e)

    L = []
    a = L.append
    a("# Fantasy Premier League 2026/27 — Player and Club Reference")
    a("")
    a(f"**Season:** 2026/27 &nbsp;·&nbsp; **Data pulled:** {date.today().isoformat()} "
      f"&nbsp;·&nbsp; **Completed gameweeks:** {last_gw} &nbsp;·&nbsp; "
      f"**Players:** {len(els)} across {len(clubs)} clubs")
    a("")
    a("## How to use this file")
    a("")
    a("This file is the authority for the **2026/27** Premier League season. Where it "
      "disagrees with anything else, including your own prior knowledge of which club a "
      "player belongs to, **this file is correct and the prior knowledge is out of date.**")
    a("")
    a("When a video, article or transcript mentions a player by name:")
    a("")
    a("1. Find the name in this file to get their **2026/27 club**. Do not assume the club "
      "from memory; many players moved in the 2026 summer window.")
    a("2. If the surname appears in the duplicate-names section, use the position and club "
      "spoken in the source to pick the right person.")
    a("3. Points totals here are for the 2026/27 season only, through gameweek "
      f"{last_gw}.")
    a("")
    a("---")
    a("")

    a("## 1. Corrections: players who changed club")
    a("")
    a(f"These **{len(movers)} players are at a different club this season**. This is the "
      "single most common source of error, because their old club is what appears in "
      "older training data. Each line states the correction explicitly.")
    a("")
    a("| Player | Full name | Position | 2026/27 club | Previously | Price | Pts |")
    a("|---|---|---|---|---|---|---|")
    for e, was, now in movers:
        a(f"| **{e['web_name']}** | {full_name(e)} | {POS_SHORT[e['element_type']]} | "
          f"**{now}** | ~~{was}~~ | £{e['now_cost']/10:.1f}m | {e['total_points']} |")
    a("")
    a("Written out, so each statement stands alone:")
    a("")
    for e, was, now in movers[:25]:
        a(f"- **{full_name(e)} ({e['web_name']}) plays for {now} in 2026/27.** "
          f"He does not play for {was} any more. He is a {POS[e['element_type']].lower()} "
          f"priced at £{e['now_cost']/10:.1f}m and has {e['total_points']} points this season.")
    a("")
    a("---")
    a("")

    a("## 2. Players with no previous Premier League record")
    a("")
    a(f"These **{len(arrivals)} players did not appear in the Premier League in 2025/26**. "
      "They are new signings from abroad, promoted-club players, or young players making "
      "a debut season. A model with older training data may not recognise them at all, or "
      "may invent a club for them. The club listed here is correct.")
    a("")
    a("| Player | Full name | Position | 2026/27 club | Price | Pts |")
    a("|---|---|---|---|---|---|")
    for e, now in arrivals:
        if e["total_points"] > 0 or e["minutes"] > 0 or float(e["selected_by_percent"] or 0) >= 0.5:
            a(f"| **{e['web_name']}** | {full_name(e)} | {POS_SHORT[e['element_type']]} | "
              f"{now} | £{e['now_cost']/10:.1f}m | {e['total_points']} |")
    a("")
    a("*(Listed above: those who have played, scored, or are owned by at least 0.5% of "
      "managers. The full squad lists in section 5 include everyone else.)*")
    a("")
    a("---")
    a("")

    a("## 3. The 20 clubs in 2026/27")
    a("")
    a("| Club | Short | Status |")
    a("|---|---|---|")
    for cid, name in sorted(clubs.items(), key=lambda kv: kv[1]):
        status = "**Promoted this season**" if name in promoted else "In the league last season"
        a(f"| {name} | {short[cid]} | {status} |")
    a("")
    a(f"**Promoted into the Premier League for 2026/27:** {', '.join(promoted)}. "
      "These clubs were not in the Premier League in 2025/26.")
    a("")
    a(f"**Relegated after 2025/26, so NOT in the league this season:** {', '.join(relegated)}. "
      "Any reference to these clubs in a 2026/27 context is an error.")
    a("")
    a("---")
    a("")

    a("## 4. Duplicate surnames — read carefully")
    a("")
    a(f"**{len(dupes)} display names belong to more than one player.** Use the position and "
      "club to tell them apart.")
    a("")
    a("| Display name | Full name | Position | Club | Price | Pts |")
    a("|---|---|---|---|---|---|")
    for name in sorted(dupes):
        for e in sorted((x for x in els if x["web_name"] == name),
                        key=lambda x: -x["total_points"]):
            a(f"| {name} | **{full_name(e)}** | {POS_SHORT[e['element_type']]} | "
              f"{clubs[e['team']]} | £{e['now_cost']/10:.1f}m | {e['total_points']} |")
    a("")
    a("---")
    a("")

    a("## 5. Full squads by club")
    a("")
    a("Every registered player, grouped by club and ordered by points this season.")
    a("")
    for club in sorted(by_club):
        squad = sorted(by_club[club], key=lambda e: (e["element_type"], -e["total_points"]))
        tag = " *(promoted this season)*" if club in promoted else ""
        a(f"### {club}{tag}")
        a("")
        a("| Player | Full name | Pos | Price | Pts | Owned | Note |")
        a("|---|---|---|---|---|---|---|")
        for e in squad:
            note = ""
            if e["code"] in was_at and was_at[e["code"]] != club:
                note = f"joined from {was_at[e['code']]}"
            elif e["code"] not in was_at:
                note = "no 2025/26 PL record"
            if e["status"] != "a":
                flag = {"i": "injured", "s": "suspended", "u": "unavailable",
                        "d": "doubtful"}.get(e["status"], e["status"])
                note = f"{note}; {flag}".strip("; ")
            a(f"| {e['web_name']} | {full_name(e)} | {POS_SHORT[e['element_type']]} | "
              f"£{e['now_cost']/10:.1f}m | {e['total_points']} | "
              f"{e['selected_by_percent']}% | {note} |")
        a("")
    a("---")
    a("")

    a(f"## 6. Leading scorers after gameweek {last_gw}")
    a("")
    a("| # | Player | Club | Pos | Price | Pts |")
    a("|---|---|---|---|---|---|")
    for i, e in enumerate(sorted(els, key=lambda x: -x["total_points"])[:40], 1):
        a(f"| {i} | **{e['web_name']}** ({full_name(e)}) | {clubs[e['team']]} | "
          f"{POS_SHORT[e['element_type']]} | £{e['now_cost']/10:.1f}m | {e['total_points']} |")
    a("")
    a("---")
    a("")
    a(f"*Generated from the official Fantasy Premier League API on {date.today().isoformat()}. "
      "Rebuild with `python3.12 scripts/build_reference.py` to pick up January transfers, "
      "price changes and updated points.*")
    return "\n".join(L)


CSS = """
@page { size: A4; margin: 16mm 14mm; }
body { font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; color:#111;
  font-size: 9.5pt; line-height: 1.5; }
h1 { font-size: 20pt; margin: 0 0 4mm; letter-spacing:-0.3px; }
h2 { font-size: 13pt; margin: 8mm 0 3mm; padding-top: 2mm;
  border-top: 2px solid #111; page-break-after: avoid; }
h3 { font-size: 11pt; margin: 5mm 0 2mm; page-break-after: avoid; }
table { border-collapse: collapse; width: 100%; margin: 2mm 0 4mm;
  font-size: 8pt; page-break-inside: auto; }
th { text-align:left; border-bottom: 1.2px solid #111; padding: 3px 6px 3px 0; }
td { border-bottom: 1px solid #eee; padding: 3px 6px 3px 0; vertical-align: top; }
tr { page-break-inside: avoid; }
ul { padding-left: 5mm; } li { margin-bottom: 1.5mm; }
del { color:#999; }
hr { border:0; border-top:1px solid #ddd; margin: 6mm 0; }
code { background:#f2f2f0; padding:1px 3px; }
"""


def md_to_html(md: str) -> str:
    """Minimal, dependency-free markdown to HTML for the tables and headings used here."""
    import html as h
    import re
    out, in_table = [], False
    for line in md.split("\n"):
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if all(set(c) <= set("-: ") and c for c in cells):
                continue  # the |---| separator row
            if not in_table:
                out.append("<table>"); in_table = True
                out.append("<tr>" + "".join(f"<th>{inline(c)}</th>" for c in cells) + "</tr>")
            else:
                out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in cells) + "</tr>")
            continue
        if in_table:
            out.append("</table>"); in_table = False
        if line.startswith("### "): out.append(f"<h3>{inline(line[4:])}</h3>")
        elif line.startswith("## "): out.append(f"<h2>{inline(line[3:])}</h2>")
        elif line.startswith("# "): out.append(f"<h1>{inline(line[2:])}</h1>")
        elif line.startswith("- "): out.append(f"<li>{inline(line[2:])}</li>")
        elif line.strip() == "---": out.append("<hr>")
        elif line.strip(): out.append(f"<p>{inline(line)}</p>")
    if in_table:
        out.append("</table>")
    body = "\n".join(out)
    body = re.sub(r"(<li>.*?</li>\n?)+", lambda m: f"<ul>{m.group(0)}</ul>", body, flags=re.S)
    return f"<style>{CSS}</style>{body}"


def inline(t: str) -> str:
    import re
    t = t.replace("&nbsp;", " ")
    t = re.sub(r"~~(.+?)~~", r"<del>\1</del>", t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<em>\1</em>", t)
    t = re.sub(r"`(.+?)`", r"<code>\1</code>", t)
    return t


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-pdf", action="store_true")
    ap.add_argument("--stem", default="FPL_2026_27_REFERENCE")
    args = ap.parse_args()

    md = build(fetch(), json.loads(PRIOR.read_text()))
    md_path = REPO / f"{args.stem}.md"
    md_path.write_text(md)
    print(f"wrote {md_path.name} ({len(md)/1024:.0f} KB, {md.count(chr(10))+1} lines)")

    if not args.no_pdf:
        html = REPO / "outputs" / f"{args.stem}.html"
        html.parent.mkdir(parents=True, exist_ok=True)
        html.write_text(md_to_html(md))
        pdf = REPO / f"{args.stem}.pdf"
        subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={pdf}", f"file://{html}"],
                       check=True, capture_output=True, timeout=300)
        print(f"wrote {pdf.name} ({pdf.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
