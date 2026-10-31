"""THE SHELL's context: the three counts and their short lists, on every page (the owner's goal of 2026-09-25, "THE UI,
DESIGNED THIS TIME", (d): "What is running, what is waiting for me, and what failed are always visible.").

Lazy: computed only when a page draws the shell (templates/base.html), once per request, from the board's one
classification (apps/dashboard/board.py) — so the top bar, the board, Status and Designs never disagree. It reads rows and
writes nothing.
"""
from __future__ import annotations

from django.utils.functional import SimpleLazyObject

SHOWN = 6

#: the three pills, in the order the top bar draws them: (css key, board state, words, icon, nothing-here words)
PILLS = (
    ("run", "working", "Working on it", "i-arc", "Nothing is being worked on right now."),
    ("wait", "waiting", "Waiting for you", "i-clock", "Nothing is waiting for you."),
    ("attn", "attention", "Needs attention", "i-alert", "Nothing needs your attention."),
)

#: where each part of the site lives, for the top bar's one navigation
NAV = (("/dashboard/rounds/", "rounds"), ("/dashboard/history/", "designs"), ("/dashboard/designs/", "designs"), ("/dashboard/library/", "library"),
       ("/dashboard/brand/", "library"), ("/dashboard/materials/", "library"), ("/dashboard/products/", "library"),
       ("/dashboard/status/", "status"), ("/dashboard/new/", "new"), ("/dashboard/find/", "find"))


def nav_of(path: str) -> str:
    if path in ("/dashboard/", "/"):
        return "home"
    for prefix, key in NAV:
        if path.startswith(prefix):
            return key
    return ""


def round_activity(user) -> dict:
    """Only this account's active rounds enter its shell counts and links — classified as Home's board classifies them
    (apps/dashboard/views.py, round_card; the owner's goal of 2026-10-29), so the bar and Home never disagree: a round
    whose pick is recorded still waits for its owner while its faces wait for an Accept or its files for Make my files."""
    from django.db.models import Q
    from apps.dashboard.views import round_card
    from apps.pipeline.models import Round
    groups={key:[] for key in ('run','wait','attn')}
    if user is None or not getattr(user,'is_authenticated',False):
        return groups
    active=~Q(state='complete') | Q(master_build__isnull=True) | ~Q(master_build__state='complete')
    records=(Round.objects.filter(created_by=user).filter(active).select_related('master_build')
             .order_by('-updated_at','-pk'))
    shell={'working':'run','waiting':'wait','attention':'attn'}
    for record in records:
        card=round_card(record)
        if card['state'] in shell:
            groups[shell[card['state']]].append({'title':card['title'],'url':card['url'],'reason':card['reason'],
                'next_words':card['next_words'],'picture':card['picture'],'round_id':record.pk})
    return groups


def pills(cards=None, user=None) -> list[dict]:
    """The three pills with their short lists — newest first, as the board orders its cards."""
    from apps.dashboard import board
    cards = board.classify() if cards is None else cards
    by_state = {state: [c for c in cards if c.state == state] for _key, state, *_rest in PILLS}
    shown = [c for rows in by_state.values() for c in rows[:SHOWN]]
    pictures = board.pictures(shown)
    rounds = round_activity(user)
    out = []
    for key, state, words, icon, none in PILLS:
        rows = by_state[state]
        legacy_cards=[{"title": c.title, "url": c.url, "reason": c.reason, "next_words": c.next_words,
                       "picture": pictures.get(c.task_id)} for c in rows[:SHOWN]]
        out.append({
            "key": key, "state": state, "words": words, "icon": icon, "count": len(rows)+len(rounds[key]), "none": none,
            "cards": (rounds[key]+legacy_cards)[:SHOWN],
            "round_count": len(rounds[key]), "round_url": "/dashboard/rounds/",
            "all_url": "/dashboard/status/#%s" % state if state != "waiting" else "/dashboard/#board",
            "all_words": ("See all %d" % len(rows)) if len(rows) > SHOWN else "Open the board",
            "order_words": "Rounds, then designs" if rounds[key] else "Newest first",
        })
    return out


#: how many notifications the bell's short list shows
NOTES_SHOWN = 8


def _his(note, test_projects=None) -> bool:
    """A folded test's news is not his: the board leaves those designs out of every count (his fold, a691f56: "They
    are tests, not my work"), and so does the bell."""
    from apps.dashboard import board
    return not (note.task_id and board.fold_of(note.task, test_projects))


def _tests_among(notes) -> set:
    """[his last goal before the pitch, 2026-10-16, Step 1 (4)] the projects an executor's test runs in, read once for
    the bell's notes (board._test_projects) — never once a note."""
    from apps.dashboard import board
    return board._test_projects({n.task.project_id for n in notes if n.task_id})


def unread(user) -> int:
    from apps.pipeline.models import Notification
    notes = list(Notification.objects.filter(recipient=user, is_read=False).select_related("task__project"))
    tests = _tests_among(notes)
    return sum(1 for n in notes if _his(n, tests))


def notes(user) -> dict:
    """THE BELL — the old dashboard's, reached again (the checklist of 2026-09-26): how many notifications addressed to
    this account are unread, and the newest few, each by its design's name and what happened, in words, with when it
    came and whether it is new — a folded test's left out. It reads rows and writes nothing; a row is marked read by
    the account's own click."""
    from apps.dashboard import board
    from apps.dashboard.words import note_words
    from apps.pipeline.models import Notification
    newest = list(Notification.objects.filter(recipient=user).select_related("task", "task__product", "task__project")
                  .order_by("-created_at", "-id")[:NOTES_SHOWN * 8])
    tests = _tests_among(newest)
    rows = [{"id": n.pk, "url": "/dashboard/designs/%d/" % n.task_id if n.task_id else "",
             "title": board.title_of(n.task) if n.task_id else "A design", "words": note_words(n.kind),
             "when": n.created_at, "new": not n.is_read}
            for n in newest if _his(n, tests)][:NOTES_SHOWN]
    return {"unread": unread(user), "rows": rows}


def _shell(request) -> dict:
    from apps.dashboard import explorations
    return {
        "nav": nav_of(request.path),
        # whether this account is the owner's: what is his alone (the explorations) is offered to him alone (§BH54(i))
        "owner": not explorations.owner_refusal(request.user),
        "pills": pills(user=request.user),
        "notes": notes(request.user),
        "q": request.GET.get("q", "") if request.path.startswith("/dashboard/find/") else "",
        "new_url": "/dashboard/new/",
        "find_url": "/dashboard/find/",
        "library_url": "/dashboard/library/",
    }


def shell(request) -> dict:
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return {}
    return {"shell": SimpleLazyObject(lambda: _shell(request))}
