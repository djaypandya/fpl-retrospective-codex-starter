# Counterfactual transfer rule replay

## Result

The replay analyzed **46 transfers** after excluding the 55 transfers made in chip GWs [6, 13, 23, 34]. A rule candidate was available for 43 transfers; 3 no-candidate rows were recorded as pushes and excluded from point aggregates.

The rule agreed with the actual incoming player 3 times: **6.5% of all analyzed transfers** and 7.0% of transfers with a candidate.

Across candidate-available transfers, actual picks scored **758 points** and rule picks scored **567 points** over identical actual holding windows. The rule-minus-actual delta was **-191 total points**, or **-4.44 points per scored transfer**.

Outcome count: **14 wins, 24 losses, and 5 ties**, plus 3 separately counted no-candidate pushes.

## Three biggest rule wins

- GW3: sold Palmer, actually bought Reijnders (21 pts), rule bought Semenyo (52 pts), delta +31.
- GW16: sold Mateta, actually bought Thiago (9 pts), rule bought Calvert-Lewin (30 pts), delta +21.
- GW27: sold Tarkowski, actually bought Mukiele (37 pts), rule bought Hill (51 pts), delta +14.

## Three biggest rule losses

- GW20: sold Guéhi, actually bought Gabriel (112 pts), rule bought Lewis-Potter (56 pts), delta -56.
- GW16: sold Ndiaye, actually bought Wilson (42 pts), rule bought Dewsbury-Hall (1 pts), delta -41.
- GW15: sold Enzo, actually bought Bruno G. (49 pts), rule bought Merino (9 pts), delta -40.

## Verification and data quirks

- Element-ID join: expected 0 unmatched incoming/outgoing IDs; actual 0 incoming and 0 outgoing. The three-transfer console sample prints the joined names and both recorded and feature prices.
- Price units: dividing transfer cost fields by 10 gives £m values. Across all transfer legs, the median absolute gap to the feature price is £0.20m after conversion versus 57.6 without conversion, confirming the tenths-to-£m conversion.
- Historical-price limitation: 0 players have more than one distinct `price` across their feature rows. Therefore the feature table contains a season-end/static price repeated across GWs, not true deadline prices. The replay nevertheless uses that field at/latest before T because the rule explicitly requires it. Recorded transfer costs are retained for actual buy/sell columns and verification.
- Chip exclusion: expected 101 total minus 55 chip-GW transfers = 46 analyzed; actual 46. Chip-GW counts were {6: 14, 13: 16, 23: 13, 34: 12}.
- Leak freedom: expected one four-GW prior-only window for every analyzed transfer; actual 46. Every window was asserted to be exactly `[T-4, T-1]`, so no form/minutes input touches GW T or later. Early-season nonexistent GW numbers count as zero.
- Squad sanity: expected 0 actual incoming players in the GW T-1 squad and 0 duplicated as a same-GW other incoming player; actual 0 and 0.
- Actual affordability: 23 of 46 actual buys had recorded `element_in_cost > element_out_cost`; this is legal with banked funds but violates this rule's outgoing-sale-price-only cap. Using the specified feature price instead, 23 actual incoming players were above the cap.
- Price fallback: 0 selected rule picks needed a latest-prior rather than exact-GW price row.
- Outcome blanks: missing player-GW rows are scored as zero. There were 0 missing actual-pick rows and 0 missing rule-pick rows inside the evaluated holding windows.
- `hold_end_gw` is the last included scoring GW (`T_sold - 1`), and `hold_gws` is the inclusive number of GWs from transfer GW through that end. If the actual incoming player was never sold later, the end is GW38.
- This is a deterministic retrospective comparison, not an estimate of causal points gained: it ignores transfer packages, bank allocation across simultaneous moves, squad/team limits beyond the stated exclusions, captaincy, benching, and whether the counterfactual player would have been started.

## Method note

For each non-chip transfer, candidates match the outgoing player's position, are absent from the prior-GW squad and the GW's other actual incoming players, cost no more than the recorded outgoing sale price, and average at least 45 minutes over the fixed four prior GWs. Ranking is by prior four-GW mean points, then mean minutes, lower price, and lower player ID. Both picks are scored over the actual incoming player's holding window with blank/missing rows worth zero.
