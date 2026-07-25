# Plan: Pick My GW1 Team for the 2026/27 Season

## The goal

Pick the strongest 15-player squad for Gameweek 1 of the new season. Stay inside the £100.0m budget. Follow the game rules: 2 goalkeepers, 5 defenders, 5 midfielders, and 3 forwards, with no more than 3 players from one club. The GW1 deadline is 21 August 2026.

## The data we will use

**New season data, from the FPL API.** The API gives us this season's facts:

- every player's price and position
- each player's club, including the three promoted clubs (Coventry, Hull, Ipswich)
- injury news and playing status
- the fixture list, so we know who each team plays first

**Last season data, already in this repo.** Our processed files hold the proof of what each player actually did:

- minutes played each week
- expected goal involvement (xGI) per 90 minutes — the goals and assists a player's chances *should* produce
- points per 90 minutes
- points per £1m spent, split by position

## How we will join the two seasons

Every player has a code number that never changes. The player `id` changes each season, but the `code` does not. We checked both files. Last season's raw file maps each `id` to its `code`. The new API lists each player's `code` too. So we join in two hops: last season stats → last season `code` → new season player.

After the join, every player lands in one of three groups:

1. **Full history.** They played in the league last season. We trust our stats for them.
2. **Moved clubs.** For example, Isak now plays for Liverpool. We keep their stats but flag them, because a new club can change a player's role and minutes.
3. **New to the league.** Promoted-club players and overseas signings. We have no data for them. Their price is the market's guess, not proof.

## The rules we will follow

These rules come from our season-long analysis. Each one earned its place with evidence.

1. **Minutes come first.** A player who does not play scores nothing. We drop anyone with an injury flag or no clear starting role.
2. **Ignore hot streaks.** Short-term form barely predicts next week's points. We will not chase it.
3. **For attackers, trust xGI.** Chances created and taken predict future points better than form does.
4. **Buy value in goal and defence.** Cheap goalkeepers and defenders return the most points per pound. Save money here.
5. **Buy ceiling in midfield and attack.** Spend the saved money on players who can produce huge weeks.
6. **Check the opening fixtures.** A kind first run of games adds a small edge. It breaks ties between players. It does not drive picks.
7. **Cover the template, then pick spots.** Own the popular stars most rivals own. Then add one or two low-owned picks we truly believe in.
8. **Be careful with new players.** No data means no proof. We will only pick a new-to-the-league player as a cheap bench option with a confirmed starting role.

## The steps, in order

1. **Pull and save the data.** Download the API files. Save a dated copy so anyone can repeat the work.
2. **Check the data.** Count the teams (20) and players. Spot-check prices against the FPL site. Confirm the join finds the players we expect, by name.
3. **Score every player.** Availability first. Then xGI per 90 and points per 90. Then value. Then fixtures. Score players within each position, not across positions.
4. **Build the squad.** Fill goal and defence cheaply. Spend up in midfield and attack. Obey the budget, the formation counts, and the 3-per-club rule.
5. **Pick the captain.** Use our ceiling-first rule: mostly points per 90 and xGI per 90, with a small nudge for the fixture.
6. **Stress-test the squad.** Swap each pick for its best cheaper rival. If the team does not get worse, take the cheaper player. Check that the bench can actually get on the pitch.
7. **Write up the team.** Show the 15 players, the captain, the bench order, and one plain reason for every pick.

## What could go wrong

- **Old stats can mislead.** A player who moved clubs may get a new role. We flag these players and lean on judgment for them.
- **News moves fast in August.** Injuries and transfers change daily in pre-season. We will re-pull the API close to the deadline and re-check every flag.
- **New players are a bet.** We have no league data on them. If we pick one, we will say so honestly.
- **The player list will grow.** The API lists 558 players today. More will register before GW1. We will re-pull before we lock the team.

Our rule from last season still applies here: the rules set the floor, and judgment sets the ceiling.
