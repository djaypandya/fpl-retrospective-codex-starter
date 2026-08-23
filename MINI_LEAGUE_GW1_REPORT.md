# Buy-in Baller League — Gameweek 1 Report

**Your team:** Numbers Don't Lie (Dhananjay Pandya) · **League:** 22 managers
**You are 6th on 32 points.** The leaders have 55.

> **Read this first.** Gameweek 1 is only part-played. Six of the ten matches are done. Four have not kicked off: Man City, Liverpool, Chelsea and Brighton all still play. Those four games hold most of what happens next, so treat every score below as a snapshot, not a result.

Re-run this report any week: `python3.12 scripts/league_report.py --league 14074 --entry 46116 --gw 1`

---

## 1. The template team in your league

These are the players the most managers own. I call this the template. If you own them, you move with the pack. If you don't, you either gain or lose ground fast.

| Pos | Player | Club | Owned by | Effective | GW1 pts | You? |
|-----|--------|------|----------|-----------|---------|------|
| GK | **Raya** | Arsenal | 41% | 41% | 6 | ✅ |
| GK | **Kinsky** | Spurs | 36% | 27% | 2 | ✅ |
| DEF | **Calafiori** | Arsenal | 59% | 59% | 9 | ✅ |
| DEF | Gabriel | Arsenal | 41% | 41% | 5 | ❌ |
| DEF | Shaw | Man Utd | 41% | 32% | 1 | ❌ |
| DEF | Diop | Ipswich | 32% | 9% | 2 | ❌ |
| DEF | Maguire | Man Utd | 32% | 27% | 1 | ❌ |
| MID | B.Fernandes | Man Utd | 64% | **86%** | 2 | ❌ |
| MID | **Groß** | Brighton | 50% | 32% | — | ✅ |
| MID | Mbeumo | Man Utd | 41% | 41% | 2 | ❌ |
| MID | Tzolis | Arsenal | 41% | 41% | 6 | ❌ |
| MID | Wirtz | Liverpool | 32% | 32% | — | ❌ |
| FWD | **Haaland** | Man City | 77% | **141%** | — | ✅ |
| FWD | **João Pedro** | Chelsea | 73% | 68% | — | ✅ |
| FWD | Calvert-Lewin | Leeds | 50% | 36% | 1 | ❌ |

"Effective" ownership counts a captain twice, because a captain scores double. Haaland sits at 141%. That is the number that matters most in this league.

**You own 6 of these 15.** That puts you joint 14th out of 22 for template coverage. You are one of the more contrarian managers here. That cuts both ways: you fall behind slower when the template blanks, and you climb slower when it hauls.

Three players are yours alone in this league: **Vuskovic, Ampadu and Mitchell.** Nobody else has them.

---

## 2. How you spend your money

This is the spend on your **starting eleven only**, split by position. Three managers played Bench Boost, so I scored everyone on slots 1–11 to keep the comparison fair.

| | You | League average | Difference |
|---|---|---|---|
| Goalkeeper | £6.0m | £5.2m | **+£0.8m** |
| Defence | £18.0m | £19.5m | −£1.5m |
| Midfield | **£24.5m** | £31.9m | **−£7.4m** |
| Attack | **£31.0m** | £24.1m | **+£6.9m** |
| Starting XI | £79.5m | £80.7m | −£1.2m |
| Bench | £19.5m | £18.8m | +£0.7m |

**You are built differently from almost everyone.** You have the second-lowest midfield spend in the league and the second-highest attack spend. Only Karan Yohannan spends less on midfield. Only Kieren Khatri spends more on attack.

That is not an accident. It is the direct result of buying Haaland at £15.5m. He alone is half your attack budget, and paying for him is why your midfield is thin.

Your bench is also slightly more expensive than average. You carry £19.5m there.

---

## 3. What the best managers do differently

I ranked all 22 managers by their **median overall finish across the last five seasons**. I used the median because it rewards being good every year, not one lucky spike. I needed at least four seasons of history, which 18 managers have.

| Rank | Manager | Median finish | Last five seasons |
|------|---------|---------------|-------------------|
| 1 | Will Kenji | 151k | 73k, 77k, 509k, 151k, 204k |
| 2 | harrison white | 152k | 369k, 151k, 47k, 41k, 452k |
| 3 | **Kieren Khatri** | 193k | 1009k, 192k, 316k, 167k, 83k |
| 4 | Wes Towner | 344k | 5648k, 2065k, 343k, 284k, 332k |
| 5 | Vishal Perera | 361k | 539k, 532k, 116k, 360k, 261k |
| 6 | **You** | 458k | 104k, 502k, **49k**, 804k, 457k |

Kieren Khatri lands 3rd, which matches the example you gave me. That is a good sign the measure is picking up what you meant by "best."

You sit 6th, just outside. Your best season was a 49k finish. Your problem is not your ceiling. It is that your results bounce around a lot.

### The one clear pattern

Here is how the top five split their starting eleven, next to you.

| | Top 5 | You | Your gap |
|---|---|---|---|
| Goalkeeper | £5.1m | £6.0m | +£0.9m |
| Defence | **£15.6m** | £18.0m | +£2.4m |
| Midfield | **£34.2m** | £24.5m | **−£9.7m** |
| Attack | £27.1m | £31.0m | +£3.9m |
| Starting XI | £82.0m | £79.5m | −£2.5m |

**All five of the best managers spend between £14.5m and £16.5m on defence.** Every single one. The rest of the league averages £20.8m. That is a tight, deliberate habit, not a coincidence.

**All five spend heavily on midfield**, from £30.5m up to £42.5m. You are below every one of them, by nearly £10m.

So the pattern is simple: **the best managers buy cheap defenders and expensive midfielders.** You do close to the opposite. You pay up in defence and in attack, and starve the middle.

They also put more of their money on the pitch. Their starting elevens cost £82.0m against your £79.5m. They waste less on the bench.

Five players show up in three or more of their teams that you do not own: **B.Fernandes, Mbeumo, Wirtz, Schade and Calvert-Lewin.** Four of those five are midfielders.

**One honest warning.** This is one gameweek. I checked whether spending more on any position actually links to more points so far. Nothing is statistically solid yet — every result could easily be chance, and the biggest attackers have not played. Come back to this after ten weeks. That is when the pattern will mean something.

---

## 4. Your biggest risks

A player hurts you when your rivals own him and you do not. I measured this by asking: for every point this player scores, how much ground do I lose to the average rival?

### Risks that already played out

| Player | Owned by rivals | GW1 points | What happened |
|--------|-----------------|------------|---------------|
| **B.Fernandes** | 64% (5 captained him) | **2** | Your single biggest exposure. He blanked. This was a big win for you. |
| Tzolis | 41% | 6 | Cost you a little. |
| Gabriel | 41% | 5 | Cost you a little. |
| Ødegaard | 18% | **11** | Hurt the most per player owned. |
| Mbeumo | 41% | 2 | Barely moved. |

You got lucky in the best possible way. The most-owned midfield captain in the league returned 2 points.

### Risks still live

These players have not kicked a ball yet. They are the real danger. I sorted them by how much ground each one costs you per point he scores, which counts captains twice.

| Player | Club | How many rivals hold him | You |
|--------|------|--------------------------|-----|
| **Isak** | Liverpool | owned by 27%, 2 captained him | none |
| **Wirtz** | Liverpool | owned by 32% | none |
| Verbruggen | Brighton | owned by 32%, many bench him | none |
| Semenyo | Man City | owned by 23% | none |
| O'Reilly | Man City | owned by 18% | none |
| Rogers | Chelsea | owned by 18% | none |
| Kerkez | Liverpool | owned by 14% | none |

**Newcastle vs Liverpool is your danger game.** Isak, Wirtz and Kerkez all play in it, and you own none of them. You do own Virgil and Szoboszlai, so a Liverpool clean sheet still helps you.

### The captain picture

| Captain | Managers |
|---------|----------|
| **Haaland** | 14 of 22 (64%) — including you |
| B.Fernandes | 5 (already played, 2 pts) |
| Isak | 2 |
| Igor Thiago | 1 |

You captained Haaland along with 13 rivals. That means a Haaland haul **protects** you more than it promotes you. You keep pace with two-thirds of the league. Your gains have to come from somewhere else.

---

## 5. Where you actually stand

Here is the good news, and it is better than the table suggests.

**Half your score is still to come.** You have 6 scoring units left out of 12. The two leaders have only 3 of 12 and 3 of 16.

Your remaining players: **Virgil, Groß, Szoboszlai, João Pedro, and Haaland (captain, counts double).**

**Against Andy Mcgoonface, the joint leader, you cannot lose ground from here.** Everything he has left — Groß, Haaland, João Pedro — you also own. And you captain Haaland while he does not. Barring a red card, every remaining point either helps you both equally or helps you more.

The same holds against Vishal Perera, the other leader, except he also has Gomez.

Here is how the gap moves:

| If the rest of the gameweek goes... | You finish | Leaders finish | Gap |
|---|---|---|---|
| Quietly (everyone 2 pts) | 44 | 61 | 17 (from 23) |
| Normally (everyone ~5, Haaland 6) | 64 | 71 | 7 |
| Haaland hauls 13 | 74 | 76 | **2** |
| Haaland blanks | 54 | 66 | 12 |

You close the gap in every case. You probably do not catch them this week. A 23-point hole is deep. But you climb, and if Haaland delivers you finish within touching distance.

---

## What to take from this

**Good news.** You dodged the biggest bullet in the league when B.Fernandes blanked for the 64% who own him. Half your team is still to play while the leaders are nearly done. You captained the right player.

**The real lesson.** Your budget shape is the outlier here, and not in the direction the winners lean. The five best managers in this league all keep defence cheap, around £15–16m, and pour money into midfield, around £34m. You spend £18m on defence and £24.5m on midfield. That is a £10m midfield gap against the people who win most often.

**What to watch.** Track your midfield spend against that £34m mark over the next few weeks. If the pattern holds once we have real data, that is the single change most likely to move you up. Do not act on one gameweek — but do start counting.

*Data pulled live during Gameweek 1, with 6 of 10 matches played and none finalised. Bonus points and scores can still change.*
