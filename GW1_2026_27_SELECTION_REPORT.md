# GW1 2026/27: My Starting Squad

**Built:** 25 July 2026 · **Deadline:** 21 August 2026, 17:30 UTC
**Spend:** £100.0m of £100.0m · **Formation:** 3-4-3 · **Captain:** Erling Haaland

Run it yourself: `python3.12 scripts/build_gw1_squad.py`
Full working: [`notebooks/gw1_2026_27_squad.ipynb`](notebooks/gw1_2026_27_squad.ipynb)

---

## 1. The team

### Starting XI

| Pos | Player | Club | Price | GW1 game | Owned |
|-----|--------|------|-------|----------|-------|
| GK | David Raya | Arsenal | £6.0m | Coventry (H) | 29.8% |
| DEF | Virgil van Dijk | Liverpool | £6.5m | Newcastle (A) | 15.3% |
| DEF | Marc Guéhi | Man City | £6.0m | Bournemouth (H) | 25.4% |
| DEF | James Tarkowski | Everton | £6.0m | Crystal Palace (H) | 10.9% |
| MID | Declan Rice | Arsenal | £7.5m | Coventry (H) | 22.5% |
| MID | Enzo Fernández | Chelsea | £7.0m | Fulham (A) | 5.1% |
| MID | Dominik Szoboszlai | Liverpool | £7.0m | Newcastle (A) | 40.4% |
| MID | James Garner | Everton | £6.0m | Crystal Palace (H) | 4.1% |
| FWD | **Erling Haaland (C)** | Man City | £15.5m | Bournemouth (H) | 73.5% |
| FWD | Igor Thiago | Brentford | £8.0m | Spurs (H) | 17.9% |
| FWD | Dominic Calvert-Lewin | Leeds | £6.0m | Nott'm Forest (A) | 17.5% |

### Bench, in order

| Order | Player | Club | Price |
|-------|--------|------|-------|
| 1 | Ethan Ampadu (MID) | Leeds | £5.5m |
| 2 | Tyrick Mitchell (DEF) | Crystal Palace | £4.5m |
| 3 | Luke Shaw (DEF) | Man Utd | £4.5m |
| GK | Martin Dubravka | Spurs | £4.0m |

Every player is fit and flagged available today. No club supplies more than two players, so the three-per-club limit is not close to binding.

---

## 2. What I did

I built the squad in five steps.

**Step one: I pulled the new season's data.** The API gave me 558 players, 20 clubs, and all 380 fixtures. The three promoted clubs are Coventry, Hull and Ipswich. Burnley, West Ham and Wolves went down.

**Step two: I joined the two seasons.** A player's `id` changes every year, but his `code` never does. Last season's file maps each `id` to a `code`, so I joined through that.

The join matched 454 of the 558 players. But 54 of those matched players never actually played a minute last season, so they carry no usable evidence. That leaves **378 players with a real record, 22 who have since changed clubs, and 158 with nothing to go on.**

Then I checked the join against a second source. The API still carries each player's 2025/26 totals. I compared those to the totals I computed myself from our own 29,747 match rows. **They matched exactly for 399 of 400 players** — same points, same minutes, same expected goal involvement. That is as strong a check as I could ask for.

**Step three: I let last season's data pick the weights.** I did not guess how much to trust each signal. I split last season in half, worked out each player's numbers from the first half, and then measured which of those numbers actually predicted the second half. Details in section 3.

**Step four: I projected each player's points.** For each player I estimated two things separately: how well he scores when he is on the pitch, and how much of each match he plays. Multiplying them gives expected points per game.

**Step five: I picked the squad with a solver.** I did not hand-pick anyone. I wrote the whole problem as a mixed integer linear program and let it find the best possible 15 players. This matters: a greedy "buy the best value player, repeat" approach gets stuck, because every pick changes what you can afford next. The solver looks at all the trade-offs at once and proves its answer is the best one available under the rules.

The solver reported **Optimal**, which means no other legal 15-player squad scores higher on my projection.

---

## 3. What the data actually said

I split the 2025/26 season in half and asked: which first-half number predicts second-half scoring? Here is the correlation between each signal and what happened next.

| Position | Points per 90 | Expected goal involvement per 90 |
|----------|---------------|----------------------------------|
| Goalkeeper | **−0.11** | (not meaningful) |
| Defender | 0.22 | 0.19 |
| Midfielder | 0.34 | **0.45** |
| Forward | 0.17 | **0.47** |

Three findings drove the whole build.

**Expected goal involvement beats raw points for attackers.** For forwards the gap is huge: 0.47 against 0.17. A forward's past goals barely predict his future goals, but the quality of chances he gets does. So I weighted xGI at 73% for forwards and 57% for midfielders, and I let those weights fall straight out of the numbers above rather than choosing them myself.

**You cannot predict a goalkeeper's scoring rate at all.** The correlation is slightly negative. A keeper who scored well in the first half was, if anything, marginally worse in the second. So I stopped trying. For keepers I use only two things: how much he plays, and how good the defence in front of him is. This is exactly why you should never spend big on a goalkeeper.

**Minutes matter more than any rate.** Across every position, minutes played in the first half predicted second-half points better than points per 90 did. Availability really does gate everything.

---

## 4. Does the method work?

A model that has never been tested is just an opinion. So I tested it.

I rebuilt the entire projection using only the first half of last season, then scored it against what players actually did in the second half. I compared it to four simpler methods.

| Method | Correlation with what happened | Average points scored by its top 20 picks |
|--------|-------------------------------|-------------------------------------------|
| **My projection** | **0.52** | **76.0** |
| Just use last season's points | 0.48 | 67.8 |
| Just use minutes played | 0.45 | 67.4 |
| Just use price | 0.29 | 75.7 |
| Just use points per 90 | 0.18 | 58.0 |

My projection won. Its top 20 players went on to score **76.0 points each**, against 67.8 for the obvious approach of ranking players by last season's points. That is a gap of about 8 points per player over 19 games.

I then ran a stricter test. I learned the weights on gameweeks 1–12, and scored the model on gameweeks 25–38 — a window the weights had never seen. The edge held: 0.52 against 0.50, and 57.8 points per top-20 pick against 54.8.

**Be honest about the size of this.** The out-of-sample edge is about **0.2 points per player per gameweek**. It is real and it points the same way in both tests, but it is not a licence to ignore what you can see with your own eyes.

One caveat worth stating: the forward weight is the least stable number in the model. There were only 32 forwards with enough minutes to measure, and the weight moved a lot between the two tests. Treat the forward picks as the shakiest part of the squad.

---

## 5. Why each player

**Erling Haaland (£15.5m, captain).** He scored 239 points last season, and both his points per 90 (7.28) and his xGI per 90 (0.86) are the best of any player in the game. He takes Man City's penalties. He costs 15.5% of the budget, and the solver still bought him — the captain's armband doubles his score, so his real value is twice everyone else's.

**Igor Thiago (£8.0m).** He played 3,282 minutes and started 37 games, so he is as close to guaranteed minutes as a forward gets. He takes Brentford's penalties. He is the best points-per-pound forward in the game on my numbers.

**Dominic Calvert-Lewin (£6.0m).** Now at Leeds, on penalties, with a healthy 0.55 xGI per 90 for £6.0m. He is the cheap third forward that makes the rest of the squad affordable.

**Declan Rice (£7.5m).** 184 points, set-piece duties, and 10.94 defensive contributions per 90.

**Dominik Szoboszlai (£7.0m).** 3,232 minutes, second on Liverpool's penalties, and Liverpool have the kindest opening five fixtures of any club in my squad.

**Enzo Fernández (£7.0m).** The best chance creator among my midfielders at 0.54 xGI per 90. He takes penalties and corners. Only 5.1% of managers own him.

**James Garner (£6.0m).** The quiet engine of the squad. He averages **12.08 defensive contributions per 90** — right on the threshold midfielders need to bank the 2-point defensive bonus, which means he collects it most weeks. He started all 38 games last season. Just 4.1% of managers own him.

**Virgil van Dijk (£6.5m).** He played 3,420 minutes, more than anyone else I picked, and started every single game.

**Marc Guéhi (£6.0m).** Now at Man City. His 5.11 points per 90 is the best of any defender in the squad.

**James Tarkowski (£6.0m).** He averages 10.16 defensive contributions per 90, just above the 10 that defenders need, so he banks the bonus regularly.

**David Raya (£6.0m).** Behind the best-rated defence in the game, and he started 37 matches. Since keeper scoring rates cannot be predicted, minutes and defensive quality are the only things worth paying for.

**The bench.** Ethan Ampadu (£5.5m) is a genuine sub — he averages 12.00 defensive contributions per 90, essentially matching Garner, at 1.3% ownership. Tyrick Mitchell and Luke Shaw both played over 3,200 minutes for £4.5m each. Martin Dubravka is a £4.0m keeper who started 35 games last season. The whole bench costs £18.5m and every player on it started at least 35 matches.

### The template, and the picks against it

I own the players most rivals own: Haaland (73.5%), Szoboszlai (40.4%), Raya (29.8%), Guéhi (25.4%) and Rice (22.5%). That protects me from falling behind when the popular pick returns.

My differentials are Garner (4.1%), Enzo Fernández (5.1%) and Ampadu (1.3%). All three are cheap, all three played nearly every minute last season, and all three earn points from defensive work that most managers ignore.

---

## 6. What the model refused to do, and why

The model only knows what happened last season. Three of its blind spots are worth your judgment.

**Alexander Isak (£9.0m, Liverpool).** He played just 694 minutes last season. My model has no evidence he plays, so it projects him at 2.5 points and leaves him out. If you know he is fit and starting for Liverpool, the model is wrong and you are right. This is the single biggest judgment call in the squad.

**Cole Palmer (£9.5m, Chelsea).** Same story, less extreme: 24 starts, 1,954 minutes. The model projects 3.1 points and passes.

**Everyone at Coventry, Hull and Ipswich.** 158 players have no Premier League record at all. I barred them from the starting XI on purpose. The model cannot tell a future star from a squad filler, and price is the only clue — which is not evidence. Removing that rule changed nothing: the solver picked the same 15 players anyway, so the rule cost me nothing this time.

---

## 7. How much of this is solid?

I re-ran the whole optimisation four ways to see what actually moves the answer.

| What I changed | Players changed | Captain |
|----------------|-----------------|---------|
| Let new players start | 0 of 15 | Haaland |
| Ignore fixtures completely | 1 of 15 | Haaland |
| Treat the bench as worthless | 5 of 15 | Haaland |
| Use FPL's own points forecast | 12 of 15 | Fernandes |

**The fixture rule is doing what it should.** Turning fixtures off changed one player. Fixtures break ties here; they do not drive the squad. That is what our earlier analysis said should happen, and it is what happened.

**The captain never moved.** Haaland is the captain under every version except one.

**The bench weighting is the real lever.** Deciding how much bench players are worth changes five of the fifteen. There is no data that settles this, so I made a judgment: bench players are worth about 12% of a starter, because that is roughly how often they come on. If you disagree, the squad changes.

**FPL's own forecast disagrees, but ignore that.** Their pre-season number is a placeholder — only 4 players in the entire game are rated above 3.3, and it barely distinguishes anyone. It is not a real benchmark yet.

I also tested every starter against the best cheaper player at the same position. Two calls are close enough to revisit: swapping Raya for Gianluigi Donnarumma saves £0.5m and costs 0.30 projected points, and swapping Enzo Fernández for Elliot Anderson saves £0.5m and costs 0.26. If news changes before the deadline, start there.

---

## 8. What could still go wrong

**The player list will grow.** 558 players are registered today. More will sign before 21 August, and some will be good.

**August news beats July data.** Injuries and transfers move fast in pre-season. Forty-six players already carry a flag: 25 are ruled out and 21 are doubts. That will change many times before the deadline.

**Last season's minutes are not this season's minutes.** Twenty-two of my matched players changed clubs. I discount those by 10%, but a discount is a guess, not knowledge.

**Five players have a broken record in our own files.** Our repo's id-to-code map has drifted for five players out of 454. I found them by checking our minutes against the API's, and I dropped their defensive numbers rather than trust them. The API's own figures are used everywhere else.

## What to do before the deadline

Re-run the script in the week of 17 August. It re-pulls the API automatically, so it will pick up new signings, price changes, and every injury flag. Then read section 6 again and decide the Isak question with your own eyes.

The rules set the floor. Your judgment sets the ceiling.
