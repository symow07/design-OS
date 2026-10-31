# The paid boundary — quality

**Job:** every paid call a page or task can reach goes through one place, reserved before it is sent, settled at the
provider's usage, never bought twice. Files: `apps/pipeline/services/round_calls.py`, `spend_reservation.py`.

**The bar, in numbers:** one boundary; every call's hold ≥ what it cost; a claim's own cap refuses a call in words before
it is sent; a saved reply never re-bought; a lost call counted (unknown, at its hold), never sent again on its own.

**Before → after, same input.** Structure (the code that could spend): before, five places made paid calls of their own
(image_guard.guarded_call, round_ideas_calls, round_master_calls, the old image producer's download, the balm round's
text_call); after, one: round_calls + spend_reservation (the balm round archived with its pages, `ba16e80`). Every part
moved in is identical to its donor but `IdeasContext`, whose only change is that it now calls the image guard as its own
module's functions (`runs/moved-parts.json`). Since the merge (`d4981e0`, `261d9ce`): a hold scales with the canvas
(max($0.35, $0.35 × pixels / 1,572,864)), and each claim records its edit before sending it (`claimed_call`).

Round 3's real calls on the owner's $3 (attempt 3, the ledger `var/rescue_spend/ledger.sqlite3`, held → accounted):

| Call | Canvas | Held | Cost |
|---|---|---|---|
| whole-die painting | 1024×1536 | $0.35 | $0.198 |
| header, header back | 1408×1072, 1408×1088 | $0.35 each | $0.214, $0.217 |
| front strip (×2) | 1408×480 | $0.35 | $0.079, $0.080 |
| right side (×2), left side (×2) | 1104×1840 | $0.452 | $0.200 each |
| back (×2) | 1408×1840 | $0.5765 | $0.274, $0.275 |
| bottle net, cap net | 1024×1536, 1536×1024 | $0.35 | $0.187, $0.189 |
| the eye's notes (×2, outside the $3) | text | $0.41 | $0.025, $0.028 |

The claim spent $2.5137 of $3 over 13 edits; every hold covered its cost; the last panel redraw the owner might want
(the back, $0.5765 hold against $0.486 left) is refused in words before it is sent.

**Verdict: BETTER** — five spending paths to one, holds sized to the canvas, a claim's cap enforced before the call.

**Weakest point:** the eye's text calls are held at about $0.41 and cost about $0.03 — sixteen times over — which ties
up the round's cap while they run; and the cost of an image call is known only after it returns.
