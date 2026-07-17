# Bank-aware transfer rule replay

## Result

The primary bank-aware replay gives every transfer the outgoing sale price plus the manager's bank from the end of GW T-1. Across 45 candidate-available transfers, actual picks scored **784 points** and rule picks scored **587 points**. The rule-minus-actual result was **-197 points**, or **-4.38 per scored transfer**.

The sale-only baseline was **-191**. Adding the real bank changed 13 of 46 rule picks and made the rule **6 points worse**. A deficit of **197 points** still remained under a fair cap.

The new record was **18 wins, 22 losses, and 5 ties**, plus 1 no-candidate push. The rule agreed with the actual incoming player 3 times, or **6.5% of all 46 transfers**.

## Biggest new wins

- GW3: sold Palmer, actually bought Reijnders (21 pts), rule bought Semenyo (52 pts), delta +31.
- GW16: sold Mateta, actually bought Thiago (9 pts), rule bought Calvert-Lewin (30 pts), delta +21.
- GW27: sold Tarkowski, actually bought Mukiele (37 pts), rule bought Hill (51 pts), delta +14.

## Biggest new losses

- GW20: sold Guéhi, actually bought Gabriel (112 pts), rule bought Lewis-Potter (56 pts), delta -56.
- GW16: sold Ndiaye, actually bought Wilson (42 pts), rule bought Dewsbury-Hall (1 pts), delta -41.
- GW15: sold Enzo, actually bought Bruno G. (49 pts), rule bought Merino (9 pts), delta -40.

## Shared-bank sensitivity

There were **37 analyzed transfers in multi-transfer GWs**. In the conservative sensitivity, only the first transfer in each GW could add the bank. Later transfers used the sale price only.

That version scored actual picks at **758** and rule picks at **588**, for a **-170** delta across 43 candidate-available rows. It was **+27 points** different from the primary full-bank-per-transfer design.

## Verification and data quirks

- Bank join: each transfer at T reads `entry_history.bank` from `event_{T-1}.json`. The console prints three files and confirms the stored tenths are divided by 10 to get £m.
- Bank timing: expected one T-1 timing check for each of 46 transfers; actual 46. No event T or later file is used.
- Recorded-price affordability: expected 0 actual incoming costs above sale plus bank under the design premise; actual 4. These exceptions occur because another same-GW transfer leg released cash. The locked per-leg cap does not include those package proceeds.
- Actual-in-pool: 35 of 46 actual picks passed every candidate filter. There were 11 exceptions, including 10 rows where another candidate still made the row scorable. The console prints every reason.
- Chip exclusion: expected 46 analyzed after excluding GWs [6, 13, 23, 34]; actual 46. Chip-GW counts were {6: 14, 13: 16, 23: 13, 34: 12}.
- Leak freedom: expected 46 fixed windows `[T-4, T-1]`; actual 46. Every maximum source GW was asserted to be less than T.
- Outcome blanks: missing player-GW rows count as zero. Primary missing rows were 0 for actual picks and 0 for rule picks.
- Candidate price quirk: as in the verified baseline, the rule uses the feature-table price at or before T. Actual buy and sale columns use recorded transfer costs. This preserves the one-change design but means the actual recorded affordability check and the feature-price candidate check are not identical.
- The primary design intentionally lets each same-GW transfer see the full pre-deadline bank. It is a per-transfer affordability test, not a jointly optimized transfer package. The sensitivity shows the effect of a stricter shared-bank assumption.
- This is a descriptive counterfactual. It does not include team limits beyond the locked exclusions, captaincy, benching, hits, or whether a rule pick would have started.

## Method note

For each non-chip transfer at GW T, candidates match the outgoing player's position, are absent from the prior-GW squad and the GW's other actual incoming players, cost no more than the outgoing sale price plus the bank stored after GW T-1, and average at least 45 minutes over GWs T-4 through T-1. Ranking and tiebreaks are unchanged: prior four-GW mean points, higher mean minutes, lower price, then lower player ID. Both picks use the actual holding window, and missing gameweeks score zero.
