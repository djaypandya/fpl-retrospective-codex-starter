# Gameweek 4 Wildcard: Revised Draft

You asked me to find five managers with a better long-run record than the best five in your league, check what they built after their wildcard, and revise your squad to match.

I found the managers. **But not one of them has played a wildcard.** That turned out to be the most useful thing in this whole exercise, so it comes first.

---

## 1. The headline: elite managers are not wildcarding

I searched **1,100 of the highest-ranked managers in the world**, pulled each one's season history from the official game data, and kept those whose **median finish over five seasons** beats the best manager in your league (151,489).

| What I looked for | How many |
|---|---|
| Managers checked | 1,100 |
| With at least three past seasons on record | 725 |
| **Median finish better than your league's best (151,489)** | **58** |
| Of those 58, how many have played their wildcard | **0** |
| Median finish better than your league's fifth (360,721) | 151 |
| Of those 151, how many have played their wildcard | **1** |

Read that again. **Fifty-eight managers with a stronger five-year record than anyone in your league. Not one has used a wildcard.**

Here is what they have used instead, across the top 15:

| Chip | How many of the 15 played it |
|---|---|
| Bench Boost | **15 of 15** |
| Triple Captain | 8 of 15 |
| Free Hit | 7 of 15 |
| **Wildcard** | **0 of 15** |

They are spending the chips that buy points in one good week, and holding the chip that fixes a broken squad. Your squad is not broken. You sit 10th of 22 and dead level with the league average.

**This is not me telling you not to wildcard.** It is your chip and your call. But the strongest evidence I could find says the best managers in the game are keeping theirs, and you asked me to follow that template rather than break it.

---

## 2. How I found them, and why I skipped the creator hunt

Your guide suggested tracking down content creators' team IDs from tracker sites and social posts. I went a different way, and I want to be straight about why.

That method depends on somebody else's list being current and correctly matched to the right person. Team IDs reset every season and creator lists go stale.

Instead I used the game's own **Overall league**, which ranks every entry in the world. From there I pulled each manager's real season history from the official API. Every name below is verified from FPL's own data, with no third party in the middle. You can rerun it any week:

```bash
python3.12 scripts/find_elite_managers.py --pages 22 --median-better-than 151489 --require-wildcard
```

The trade-off is honest: I cannot tell you which of these people are famous. I can tell you exactly how good they are, which is what you actually asked for.

---

## 3. What the elite managers actually own

The 15 strongest records, using their real squad. Seven of them played a Free Hit in Gameweek 3, which is a one-week team that reverts, so for those I used their Gameweek 2 squad instead.

| Player | Position | Price | In elite squads | In your league |
|---|---|---|---|---|
| **Calafiori** | DEF | £5.7m | **15 of 15** | 13 of 22 |
| **João Pedro** | FWD | £7.7m | **15 of 15** | 15 of 22 |
| **Calvert-Lewin** | FWD | £6.0m | 14 of 15 | 9 of 22 |
| **B.Fernandes** | MID | £12.0m | 13 of 15 | 10 of 22 |
| Verbruggen | GK | £4.5m | 13 of 15 *(bench)* | 6 of 22 |
| **Mbeumo** | MID | £7.9m | 12 of 15 | 9 of 22 |
| **White** | DEF | £5.5m | 11 of 15 | 2 of 22 |
| Raya | GK | £6.0m | 9 of 15 | 7 of 22 |
| Isak | FWD | £9.0m | 8 of 15 | 8 of 22 |
| Palmer | MID | £9.6m | 8 of 15 | 4 of 22 |
| **Haaland** | FWD | £15.5m | **5 of 15** | **19 of 22** |

**Look at the last row.** Haaland is in 86% of squads in your league and only a third of elite squads. The best managers in the game have largely decided he is not worth £15.5m.

**And look at Ben White.** Eleven of fifteen elite managers own him. Two of twenty-two in your league do. That is the biggest gap in the table, and it is the kind of pick that quietly separates good managers from average ones.

---

## 4. How they spend their money

| Position | Elite 15 | Your league's top 5 | My first draft |
|---|---|---|---|
| Goalkeeper | £5.3m | £5.1m | £4.6m |
| Defence | £17.2m | £17.6m | £14.6m |
| Midfield | £36.4m | £36.3m | £33.1m |
| Attack | £21.5m | £21.1m | **£30.7m** |
| Bench | £20.0m | £19.9m | £17.6m |

Two completely separate groups of good managers landed in almost exactly the same place. That is about as strong as evidence gets in this game.

My first draft was the odd one out in attack, by about £9m, and that was Haaland.

They also all use **three players from one club**. Every single one of the 15. Your antifragile rule of two per club is stricter than what the best managers do. I kept your rule, but you should know they go the other way.

Their formations: eight play 3-4-3, five play 3-5-2, two play 4-4-2.

---

## 5. The revised squad

Built to the elite spending shape, keeping every constraint you gave me.

### Starting eleven

| Pos | Player | Club | Price | Form |
|---|---|---|---|---|
| GK | **Tzolakis** | Hull City | £4.6m | 8.7 |
| DEF | **Calafiori** | Arsenal | £5.7m | 7.3 |
| DEF | **Virgil** | Liverpool | £6.5m | 3.0 |
| DEF | **Konsa** | Arsenal | £4.4m | 1.7 |
| MID | **B.Fernandes** | Man Utd | £12.0m | 9.0 |
| MID | **Palmer** | Chelsea | £9.6m | 7.0 |
| MID | **Mbeumo** | Man Utd | £7.9m | 7.0 |
| MID | **Semenyo** | Man City | £8.4m | 4.3 |
| FWD | **Isak** | Liverpool | £9.0m | 7.7 |
| FWD | **João Pedro** | Chelsea | £7.7m | 7.0 |
| FWD | **Wissa** | Newcastle | £6.2m | 4.3 |

### Bench, unchanged as you asked

Janelt · Egan · Thomas *(Bobby Thomas, Coventry)* · Kinsky

**Spend £99.6m. Split: £4.6m goalkeeper, £16.6m defence, £37.9m midfield, £22.9m attack.** That sits right on the elite shape.

### What changed from the first draft

| Out | In |
|---|---|
| Haaland (£15.5m) | João Pedro (£7.7m) |
| Gakpo | Palmer |
| Scott | Semenyo |
| Bogle | Virgil |

---

## 6. Two honest problems with this revision

**Problem one: it scores worse on your own rules.**

Your method ranks players by form. The first draft scored **78.3** across the eleven. This one scores **67.0**. Matching the elite spending shape forces you into Virgil (form 3.0) and Semenyo (form 4.3) to hit the defence and midfield spending floors.

There is a real caveat here that helps you. Back in the Gameweek 1 work, I tested how well form predicts future scoring, and it came out weak, around 0.20. Points per 90 and expected goal involvement both did better. **So an 11-point form gap is a lot less meaningful than it looks.** It is mostly noise. I would not let it decide this on its own.

**Problem two: dropping Haaland is the biggest risk you can take in your league.**

Nineteen of your 22 rivals own him. Elite managers mostly do not. Both of those things are true at once.

- If you drop him and he hauls, you lose ground to almost everyone at the same time.
- If you keep him and he is merely fine, you bleed slowly against a squad that spends that £8m better.

The elite evidence says sell. Your league's ownership says the downside is brutal and immediate. That is your judgement call, not mine to make for you.

---

## 7. What I would do

**Do not play the wildcard this week.** Fifty-eight managers with better five-year records than anyone in your league are all still holding theirs. Your squad is mid-table, not broken. Save it for an injury crisis or a blank gameweek.

**If you play it anyway, take the revised squad**, because it matches what two independent groups of good managers do with their money, and the form gap against the first draft is inside the noise.

**Either way, look hard at Ben White.** Eleven of fifteen elite managers own him at £5.5m. Two of twenty-two in your league do. That is the clearest single gap between you and the people who finish well, and it costs almost nothing to fix.

---

*Elite manager data pulled from the official FPL API on 7 September 2026. Full working in `outputs/elite_managers/`. Rerun with `scripts/find_elite_managers.py`.*
