"""§BH55 PHASE 3 — THE ACTIVITY FEED IN A DESIGNER'S WORDS.

"Every capability the engine has is reachable and labelled in words a designer understands" (OWNER STANDING ORDER §BH55,
Phase 3). While a design runs, the feed showed the agents' own log — "ARIA: delegating to Creative Director", "Dieline:
scenario A determined", "QA Reviewer: 3/3 images passed". Every row stays as it was written (History shows it so; nothing
here changes a record): the feed shows beside it who is working and what is being done, read from the row by the first
rule below that matches it — or, where none does, the row itself without its agent's prefix. Reads a row; writes nothing.
"""
from __future__ import annotations

import re

#: who is working, by the name a row is logged under
WHO = {"ARIA": "Studio", "CreativeDirector": "Planning", "PromptEngineer": "Prompts", "ImageProducer": "Drawing",
       "QAReviewer": "Checking", "Dieline": "Making", "system_recovery": "Recovery"}

_PREFIX = re.compile(r"^(?:ARIA|Image Producer|Creative Director|QA Reviewer|Prompt Engineer|Dieline|Container|"
                     r"flat artwork):\s*")

#: (a row without its prefix, as written; what it says) — the first that matches; {1}, {2}… are its groups
RULES = [
    (r"pipeline started", "started"),
    (r"planning design directions \(no rendering yet\)", "planning three directions — nothing is drawn yet"),
    (r"applying replan feedback to direction planning", "planning again, with what you said"),
    (r"delegating to Creative Director", "planning the directions"),
    (r"retrieving brand context", "reading the brand"),
    (r"finding similar products", "finding similar products"),
    (r"studying (\d+) reference designs?", "studying {1} earlier designs"),
    (r"generating design directions", "writing the directions"),
    (r"produced (\d+) directions?", "{1} directions written"),
    (r"structured directions validated", "the directions are checked"),
    (r"three design directions ready — awaiting your selection.*", "three directions are ready — choose one; nothing is drawn until you do"),
    (r"directions already planned — awaiting your selection.*", "the directions are ready — choose one"),
    (r"Direction '(.+)' \(d\d+\) selected — rendering three variations next", "“{1}” chosen — three concepts are drawn next"),
    (r"rendering three variations of your selected direction '(.+)' \(d\d+\)", "drawing three concepts of “{1}”"),
    (r"delegating to Prompt Engineer", "writing the prompts"),
    (r"building dieline-aware prompts", "writing prompts that fit the carton"),
    (r"built (\d+) prompts?", "{1} prompts written"),
    (r"applying revision feedback", "working in the changes you asked for"),
    (r"delegating to Image Producer", "drawing the concepts"),
    (r"Provider pre-spend validation PASSED", "the paid services answered — ready to draw"),
    (r"grounding generation in (\d+) reference design\(s\) \+ official logo.*", "drawing with {1} earlier designs and the logo in view"),
    (r"generating image (\d+) of (\d+)", "drawing concept {1} of {2}"),
    (r"saved variation (\d+)", "concept {1} saved"),
    (r"provider billing limit reached — aborting", "the image service's billing limit was reached — stopped"),
    (r"delegating to QA Reviewer", "checking the concepts"),
    (r"checking brand compliance.*", "checking the concepts against the brand"),
    (r"(\d+)/(\d+) images passed", "{1} of {2} concepts pass the check"),
    (r"revision pass (\d+) — regenerating to address QA feedback", "drawing again, to answer the check (pass {1})"),
    (r"superseded (\d+) image\(s\) from earlier passes", "{1} earlier concepts set aside"),
    (r"reached Gate 1 — three variations of '(.+)' awaiting your approval", "three concepts of “{1}” are ready — choose one"),
    (r"reached Gate 1 — awaiting (?:your|container) approval", "the concepts are ready — choose one"),
    (r"rerun complete — back at Gate 1", "drawn again — choose a concept"),
    (r"image-only rerun — regenerating from the current prompts.*", "drawing the concepts again from their prompts"),
    (r"Image-only rerun requested by (\S+)", "{1} asked for the concepts to be drawn again"),
    # [his test blocker on design 122, item 4] his redraw button
    (r"Concept redraw requested by (\S+) — '(.+)'", "{1} asked for “{2}” to be redrawn so it can be drawn"),
    (r"Gate 1 approved — image (\d+)", "a concept chosen"),
    (r"product identified from record — (.+?) \[\w+\].*", "the product: {1}"),
    (r"product identified from the task — (.+?) \[\w+\].*", "the product, as the brief names it: {1}"),
    (r"design-intelligence context \((\d+) reference\(s\), AUTHORIZED\)", "{1} designs from the design library considered"),
    (r"design-intelligence context \((\d+) reference\(s\), DENIED:.*\)", "the design library not used for this design"),
    (r"design-intelligence context unavailable.*", "the design library is not available — going on without it"),
    (r"label copy translated for the sticker \((.+)\)", "the label's text translated for the sticker ({1})"),
    (r"reached dimension gate — confirm carton dimensions.*", "the carton's size is ready to confirm"),
    (r"job \S+ created, awaiting dimension confirmation", "the carton's size is ready to confirm"),
    (r"scenario A determined", "the size comes from the product's record"),
    (r"scenario B determined", "the size is estimated from the concept"),
    (r"dimensions read from product record \(no AI needed\)", "the size read from the product's record — nothing spent"),
    (r"dimensions estimated from context", "the size estimated from the concept"),
    (r"some dimensions need manual entry", "some sizes need entering by hand"),
    (r"dimensions confirmed — generating dieline", "the size is confirmed — making the design on its dieline"),
    (r"running geometry engine", "drawing the dieline"),
    (r"extracting flat panel artwork from the approved design", "taking the artwork from the chosen concept"),
    (r"extracted (\w+) panel art from the approved concept", "the artwork taken from the concept ({1} panel)"),
    (r"matched motif background tone to (#[0-9A-Fa-f]{6})", "the motif's ground matched to {1}"),
    (r"design preview composited onto the dieline.*", "the design laid onto its dieline"),
    (r"SVG \+ CMYK production PDF generated and validated", "the dieline and its print PDF are made and checked"),
    (r"dieline ready — awaiting Gate 2 approval", "the design is ready for your review"),
    (r"container profile confirmed — reconstructing container \.ai", "the container's shape confirmed — drawing it"),
    (r"reconstructed bottle concept sheet.*", "the bottle is drawn — an editable .ai and a picture"),
    (r"reached container-profile gate.*", "the container's shape is ready to confirm"),
    (r"structure confirmed — composing native vector artwork", "the structure is confirmed — drawing the artwork in vector"),
    (r"native-vector deliverables ready — awaiting Gate 2", "the design is ready for your review"),
    (r"design \.ai built as NATIVE VECTOR artwork — (\d+) vector objects, (\d+) live text runs, (\d+) rasters.*",
     "the design built in vector — {1} shapes, {2} runs of live text, {3} pictures"),
    (r"reached Gate 2 — awaiting container approval", "the container is ready for your review"),
    (r"generation metadata", "the plan's details recorded"),
    (r"Gate-1 prompts: generation attempt (\d+) of (\d+)", "writing the prompts (try {1} of {2})"),
    (r"Gate-1 prompts: generation result", "the prompts are written"),
    (r"Gate-1 variation contract result", "the prompts checked — three different concepts"),
    # [his test findings on design 121, 2026-10-07, items 2 and 3] a refused check, said as refused
    (r"Gate-1 variation contract result — refused", "the prompts failed their checks — no concept picture drawn"),
    (r"Gate-1 prompts: the ids read by their slots — .*", "each concept named for its direction"),
    (r"Gate-1 prompts: reusing the VALIDATED checkpointed plan.*", "reusing the prompts already written — nothing spent"),
    (r"applying approved material-influence plan", "writing the prompts with the approved references"),
    (r"failed on variation (\d+) — (.+)", "concept {1} could not be drawn — {2}"),
    (r"(\d+) direction\(s\) reference an unrecognised palette", "{1} directions name a palette the brand does not have"),
    (r"rejected direction payloads", "the planner's directions refused by their checks"),
    # his test day finding 1, 2026-09-29: these two showed the engine's codes — now the design page's own words
    (r"directions failed validation — (.+)", "the directions failed their checks — {1:checks}"),
    (r"could not parse response — .*", "the answer could not be read"),
    (r"Direction set archived for replan", "the directions set aside, to plan again"),
    (r"(\d+) Gate-1 image\(s\) marked by (\S+): REJECTED_BY_USER — (.+)", "{2} turned down {1} concepts — {3}"),
    (r"Reference-grounded Gate-1 regeneration job \d+ created by (\S+) with (\d+) approved concept reference\(s\)",
     "{1} asked for the concepts to be drawn again with {2} references"),
    (r"reference-grounded Gate-1 regeneration of '(.+)' with (\d+) approved concept reference\(s\).*",
     "drawing “{1}” again with {2} approved references"),
    (r"reference-grounded regeneration complete — back at Gate 1.*", "drawn again with references — choose a concept"),
    (r"Dry-run regeneration diagnostic \S+ accepted for (\S+).*", "{1} tried drawing again as a trial — nothing drawn, nothing spent"),
    (r"STRUCTURAL_TEMPLATE_CONFIRMATION_REQUIRED — (.+)", "the carton's structure must be confirmed first — {1}"),
    (r"structure ready \((\S+), source [A-Z_]+\) — awaiting technical structure confirmation.*",
     "the carton's structure is ready to confirm ({1})"),
    (r"Structure confirmed by (\S+): (\S+) .*", "{1} confirmed the carton's structure ({2})"),
    (r"reconstructing the SELECTED variation .*", "drawing the chosen concept in vector"),
    (r"reconstruction failed — (.+)", "drawing it in vector failed — {1}"),
    (r"segmentation: (\d+) separate motif element\(s\)", "{1} separate motif pieces found"),
    (r"regenerated design preview \.ai as faithful approved-artwork composite", "the design's picture drawn again from the approved artwork"),
    (r"design \.ai exported as editable components", "the design's .ai made in editable pieces"),
    (r"design \.ai built from the Design Graph \(editable objects\) — (\d+) cut motif elements",
     "the design's .ai built piece by piece — {1} motif pieces"),
    (r"design deliverable generated \(\.ai \+ PNG preview\)", "the design's files are made — an .ai and a picture"),
    (r"pipeline completed — all outputs saved", "finished — its files are saved"),
    # [his test blocker on design 122, 2026-10-07, items 2 and 4] the check before a concept is shown, and its redraws
    (r"checking each concept can be drawn before it is shown", "checking each concept can be drawn before it is shown"),
    (r"redrawing '(.+)' so it can be drawn, as you asked",
     "redrawing “{1}” so it can be drawn, as you asked"),
    (r"each concept checked before it is shown — (.+)", "each concept checked — {1}"),
    (r"'(.+)' redrawn on a plain (.+?) backdrop so it can be read, without (.+) — \$(\S+)",
     "“{1}” redrawn without {3}, on a plain {2} backdrop, so it can be drawn — ${4}"),
    (r"'(.+)' redrawn on a plain (.+) backdrop so it can be read — \$(\S+)",
     "“{1}” redrawn on a plain {2} backdrop so it can be drawn — ${3}"),
    (r"back at Gate 1 — the concept you asked to be redrawn is checked again",
     "back at your concepts — the one you asked to be redrawn is checked again"),
    (r"pipeline failed — Direction planning failed validation: (.+)",
     "stopped — the three directions failed its own checks: {1:checks}"),
    # [his test findings on design 121, item 3: "never engine codes"] the stop's reason in the design page's own words
    (r"pipeline failed — (.+)", "stopped — {1:reason}"),
    (r"Retry requested by (\S+) from status \"failed\"", "{1} asked to try again"),
    (r"Concept references approved by (\S+): \[[\d, ]*\].*", "{1} approved references for the concepts — for this design only"),
    (r"Native Illustrator handoff package generated.*", "the Illustrator package is made"),
]
_RULES = [(re.compile(rx + r"\Z", re.S), words) for rx, words in RULES]


def who(agent_name: str) -> str:
    """Who is working, in a word; a name without one is shown as it is."""
    return WHO.get(agent_name or "", agent_name or "")


def _reason_in_words(text: str) -> str:
    """A stop's reason in the design page's own words (apps/dashboard/words.reason_words), never its codes."""
    from apps.dashboard.words import reason_words
    words = reason_words(text)
    return words[:1].lower() + words[1:] if words else words


def _checks_in_words(codes: str) -> str:
    """A set of directions' failed checks, in the design page's own words (apps/dashboard/words), each said once."""
    from apps.dashboard.words import direction_check_words
    seen = []
    for code in codes.split(";"):
        words = direction_check_words(code)
        if words and words not in seen:
            seen.append(words)
    return "; ".join(seen)


def said(action: str) -> str:
    """What is being done, in words — the first rule that matches the row, else the row without its agent's prefix. A
    group marked ":checks" is a list of the planner's check codes, said in words."""
    text = _PREFIX.sub("", (action or "").strip(), count=1)
    for rx, words in _RULES:
        m = rx.match(text)
        if m:
            return re.sub(r"\{(\d)(:checks|:reason)?\}", lambda g: _checks_in_words(m.group(int(g.group(1))))
                          if g.group(2) == ":checks" else _reason_in_words(m.group(int(g.group(1))))
                          if g.group(2) == ":reason" else m.group(int(g.group(1))), words)
    return text
