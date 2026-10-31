# The round's runner — quality

**Job:** each step of a designer round as a worker job, its records and its breaks.
File: `apps/pipeline/services/round_flow.py`.

**The bar, in numbers:** one step per worker delivery; a lost process resumes without buying a call twice; a retired
round answers in words, never runs; one kind of round.

**Before → after, same input.** `record_break` moved in identical to its donor (1 of 1, `runs/moved-parts.json`). The
designer flow's omnibus test and the round pages' tests pass before and after. The runner went from three kinds of
round (designer, twenty-design, whole-object) to one (`a634230`); a retired round's job is refused in words, and its
list and page answer (T/test_product_round_page.py::test_a_retired_round_answers_in_words_on_the_list_and_its_page_and_takes_no_action).

**Verdict: SAME.** Reason: for the designer rounds it runs, its behaviour is unchanged; what left was the two retired
kinds' branches (archived whole in archive/consolidation/retire/merged/round_flow_retired.py).

**Weakest point:** one omnibus test covers five hand-offs (research to the sealed pick); a regression in one of them
shows as that single test failing, not as the step that broke.
