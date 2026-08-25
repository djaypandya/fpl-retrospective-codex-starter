SEASON DIARY
============

One plain-text entry per gameweek, kept in diary/<season>/gw<NN>.txt.

Each entry looks BACK at the gameweek just finished and FORWARD to the one
coming up. So gw02.txt reflects on GW1 and plans GW2.

Why it is built this way
------------------------

This is a decision journal, not a diary. A diary records what happened. A
decision journal records why you decided what you decided, written down BEFORE
you know the outcome, so that later you can grade the reasoning separately from
the result.

That separation matters because a good decision can lose and a bad decision can
win. If you only ever check the result, you learn the wrong lesson roughly half
the time. Writing the reasoning down first is the only way to tell them apart.

The "predictions to grade next week" section is the part that does the work.
Write things that can turn out false. Vague notes cannot be graded, so they
teach you nothing.

Each entry has
--------------

  WHAT HAPPENED         filled in automatically: score, rank, captain, bench
  YOUR CLUBS THIS WEEK  filled in automatically: fixtures and difficulty
  LOOKING BACK          your words: what you got right, wrong, and why
  DATA CHECK            filled in automatically where the calls can be scored
  PLAN                  your words: transfers, captain, chips, and what you
                        are deliberately not doing
  PREDICTIONS           your words: falsifiable claims for next week to grade

How to use it
-------------

Start next week's entry:

    python3.12 scripts/diary.py new --gw 3

See the season so far:

    python3.12 scripts/diary.py list

The script fills in every fact it can read from the archived gameweek data, so
the only thing left for you is the thinking. It will not overwrite an entry
that already exists.

Best time to write
------------------

After the gameweek is marked data_checked, so the scores you are reflecting on
are final, and before the next deadline, so the plan is still a plan rather
than a justification.
