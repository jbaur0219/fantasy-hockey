# Stream the same spot twice in a week (branch `stream-chains`, builds on PR #2)

**What changes:** the plan can now add a streamer early in the week and swap him for another later (add A Monday,
drop A for B Wednesday). Before, a drop could only be someone already on your roster, so once a spot was streamed it
sat idle after the streamer's games were done, and weekly moves went unused or to weaker swaps.

**What you'd see:** a move like "Add B, drop A (Wed)" where A is the player an earlier move on the same plan adds. The
reason reads: "A is the stream you add earlier this week and has no games left that count; swap him for B, who has
2 games that count." Once you make the first move, A is on your roster and the second move is a normal drop.

**Guard rails**
- A second stream is only valid while the move that adds the first player stays on the plan. If the first one drops
  off (or you miss it), the swap after it goes too, and the "what changed" list says so.
- Dropping a streamer you added costs nothing long-term.
- The bar is now checked on the number you see as well as the move's value inside the whole plan, so a producer's
  drop can't clear his higher bar by riding on later moves. This also closes a gap that existed before this change
  (a later add that benches the dropped player's last game).

**Evidence**
- Rule test `test_streamer_can_be_dropped_for_a_later_stream` (A2) now passes: one open spot, A plays Mon/Tue, B plays
  Wed/Thu, the plan finds +8 (was +4 with a move unused). Full suite: 148 passed, 1 expected failure (B6, open).
- 300 simulated weeks, same inputs through PR #2's branch and this one: the plan changed in 90 weeks and used a second
  stream in 89. This-week points +0.16 a week on average (71 weeks better, 10 worse); plan value (points minus
  long-term cost) +0.20 (82 better, 4 worse, worst -1.3). The few worse weeks come from the search keeping a first
  stream in place while a second one depends on it.
- Not checked against real past weeks (their ESPN inputs were not saved) or live ESPN data.
