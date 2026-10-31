"""WI-S — the behavioural form of "this code path makes no provider call".

WHAT THE CONVERTED GUARDS ASSERTED, AND WHY IT WAS NOT ENOUGH
-------------------------------------------------------------
Eight tests in `apps/dielines/tests` opened the module under test with
``Path(mod.__file__).read_text()`` and asserted that the words ``anthropic``,
``openai``, ``ImageProducer``, ``ApiCallRecord`` and ``compose_vector_art``
did not appear in it. All eight are entries in §Y2's undeclared-guard
register. Their names promise "no provider calls"; the assertion is that five
words are absent from one file.

Three things are wrong with that, and the third is the one §AA names:

1. It is routed around by an alias, by ``importlib.import_module``, or by a
   helper that lives in a different file.
2. It goes green on a file full of comments about providers and red on a file
   whose docstring mentions one. It reads text, not code.
3. **It passes without the module ever running.** §AA: *a constraint the
   pipeline never reaches is a constraint nobody has tested.* A guard that
   never executes the thing it guards has not observed anything at all.

WHAT THIS ARMS INSTEAD — three layers, and the residual limit is named
----------------------------------------------------------------------
(a) **Execution tripwires.** Every provider boundary in the repo is replaced
    with something that raises the moment it is touched: the two SDK client
    constructors, `requests`, the image agent, the artwork composer, and the
    row the pipeline writes when it calls out. Underneath them all sits a
    `socket.connect` backstop that cannot be routed around by any library,
    because egress has to open a socket eventually.
(b) **A reached-lines counter.** The exercise is required to have executed
    lines in the module under test. This is the layer that answers §AA: a
    clean tripwire over a path that never ran is not a result, and the test
    now fails if the exercise stops reaching the module.
(c) **A runtime namespace census.** The module's own globals are checked for
    any object that IS a provider module or a banned callable — object
    identity, not spelling — so `from x import y as z` is caught under any
    name it is bound to.

WHAT THE MUTATION RUN ACTUALLY SHOWED — including where it did not hold
------------------------------------------------------------------------
Every module these tests watch was mutated on disk with a real provider call
inserted at the top of every function, and the watching test re-run. Twelve
modules, and the result was **11 caught by (a), 1 not**:
`qualification/domain.py` does all of its work at module level, so the
inserted call ran at IMPORT time — before any test could arm anything — and
the tripwire never saw it. Layer (c) does catch that module: mutated instead
with the shape real code takes, a module-level `import openai`, the census
fails it on object identity. So all twelve are covered, eleven of them by the
strongest layer, and the one exception is named here rather than averaged
into a score.

**The residual limit, stated rather than left to be discovered:** a provider
reached at import time by an expression that binds nothing —
`__import__("requests").get(...)` — is invisible to all three layers. (c)
does not see it because there is no module global to find; (a) and (b) do not
see it because it has already happened. That is the exact shape the mutation
used, chosen because it is the hardest case, and it is not a shape any real
call site takes. The same hole exists for a provider imported inside a
function body on a branch the exercise never reaches.

The honest claim these tests now make is *the exercised path makes no
provider call, the exercise reaches the module, and the module's namespace
holds no provider* — strictly more than the string search proved, and
strictly less than "this module can never call a provider".

A NOTE ON THE HARNESS, because it made the mistake it was checking for
----------------------------------------------------------------------
The first mutation harness classified a run as "caught" by grepping the
pytest output for a substring that a network stack trace also contained. It
credited `domain.py` with a catch that never happened, and the escape above
was only found by re-running that one module and reading the output. A
harness that reports on an instrument needs the same scepticism as the
instrument.

WHY IT LIVES HERE
-----------------
The batch WI-S converted is the `dielines` one. Everything below takes the
modules to watch as arguments and knows nothing about cartons, so the next
batch can move this file up a level without rewriting it.
"""
from __future__ import annotations

import contextlib
import socket
import sys
from unittest.mock import patch


class ProviderCalled(BaseException):
    """Raised AT the boundary, so the traceback names the calling line — the
    one piece of information a string search could never produce.

    **It derives from BaseException on purpose, and this is not a stylistic
    choice.** ``services/provisional_preview.py`` has five
    ``except Exception:`` handlers, and each files the error into a manifest
    key rather than letting it out::

        except Exception as exc:  # noqa: BLE001 — mockup is diagnostic
            manifest["artifacts"]["mockup_3d_error"] = str(exc)

    An ``AssertionError`` tripwire raised inside one of those ``try`` blocks
    becomes a string in a manifest key and the test goes green over a path
    that made the call — worse than the string search it replaces, because
    it looks like evidence. Every hit is ALSO recorded on the :class:`Watch`
    before it is raised, so a handler broad enough to catch even a
    BaseException still cannot produce a pass.

    **Three of the five are the ones that matter, and stating which took a
    second look.** The first version of this note cited lines 249 and 267,
    the folded-diagnostic and attachment-overlay handlers. Both sit behind
    ``if d["archetype"] == opposed_tuck.TEMPLATE_ID`` and the converted
    preview test builds an **STE** carton, so the exercise never reaches
    them — §AA's own finding, committed inside the instrument built to
    enforce it. The handlers this batch actually runs through are the three
    unconditional ones in the main flow: the ``fitz`` raster preview (133),
    the dimension-overlay PDF (161) and the 3D mockup (226).
    """


#: Loopback and unix sockets are NOT provider calls: the test database is on
#: one and no provider is. Naming the allowance here keeps it visible — a
#: tripwire with a quiet exemption list is the defect it exists to catch.
_LOOPBACK = {"127.0.0.1", "::1", "localhost", "0.0.0.0"}


def _is_local(address) -> bool:
    if not isinstance(address, tuple) or not address:
        return True                      # unix socket path
    return str(address[0]) in _LOOPBACK


class Watch:
    """What the exercise did, as counts rather than as an impression."""

    def __init__(self, modules):
        self._files = {m.__file__: m.__name__ for m in modules}
        self.lines: dict[str, int] = {}
        self.connections: list = []
        #: every boundary that fired, recorded as well as raised — see
        #: :class:`ProviderCalled` for why raising alone is not enough
        self.calls: list[str] = []

    def reached(self, module) -> int:
        """Lines executed in `module` while armed. Zero means the exercise
        never got there, which is a failed exercise, not a clean result."""
        return self.lines.get(module.__name__, 0)

    def _trace(self, frame, event, arg):
        name = self._files.get(frame.f_code.co_filename)
        if name is None:
            return None                  # not watched: no line events, cheap
        if event == "line":
            self.lines[name] = self.lines.get(name, 0) + 1
        return self._trace


def _raiser(watch, what):
    def boom(*args, **kwargs):
        watch.calls.append(what)
        raise ProviderCalled(f"the exercised path called {what}")
    return boom


#: ``"dotted.path", label`` for every provider boundary the repo has. Patched
#: at the DEFINING module, which is where a late `import x; x.f()` resolves.
#: A caller that bound the name at import time keeps its own binding and is
#: caught by the namespace census instead — the two layers cover each other.
BOUNDARIES = (
    ("anthropic.Anthropic", "the Anthropic client constructor"),
    ("openai.OpenAI", "the OpenAI client constructor"),
    ("requests.get", "requests.get"),
    ("requests.post", "requests.post"),
    ("requests.request", "requests.request"),
    ("requests.sessions.Session.request", "a requests Session"),
    ("apps.pipeline.agents.image_producer.ImageProducerAgent",
     "the image producer agent"),
    ("apps.ire.compose_vector_art.compose_vector_art_graph",
     "the vector artwork composer"),
    ("apps.pipeline.models.ApiCallRecord.objects.create",
     "ApiCallRecord.objects.create"),
)


@contextlib.contextmanager
def armed(*watching):
    """Arm every boundary and count lines executed in `watching`.

    Yields the :class:`Watch`. The socket backstop records every address the
    exercise opened, so a failure can say where it went.
    """
    watch = Watch(watching)
    real_connect = socket.socket.connect

    def connect(self, address, *a, **kw):
        watch.connections.append(address)
        if not _is_local(address):
            watch.calls.append(f"socket.connect{address!r}")
            raise ProviderCalled(
                f"the exercised path opened a socket to {address!r}; the only "
                "addresses that are not provider calls are loopback and unix "
                "sockets")
        return real_connect(self, address, *a, **kw)

    previous = sys.gettrace()
    with contextlib.ExitStack() as stack:
        for dotted, label in BOUNDARIES:
            stack.enter_context(patch(dotted, _raiser(watch, label)))
        stack.enter_context(patch.object(socket.socket, "connect", connect))
        sys.settrace(watch._trace)
        try:
            yield watch
        finally:
            sys.settrace(previous)


#: Module objects and callables that must not be reachable from a namespace.
_BANNED_NAMES = ("anthropic", "openai", "requests")


def provider_bindings(module) -> list[str]:
    """Names in `module`'s own globals bound to a provider, by IDENTITY.

    Same scope as the string search this replaces — that one file, not its
    imports — but it compares objects, so an alias is caught under whatever
    name it was given and a mention in a docstring is not a finding.
    """
    banned = {}
    for name in _BANNED_NAMES:
        found = sys.modules.get(name)
        if found is not None:
            banned[id(found)] = name
    for dotted, label in BOUNDARIES:
        head, _, attr = dotted.rpartition(".")
        owner = sys.modules.get(head)
        target = getattr(owner, attr, None) if owner is not None else None
        if target is not None:
            banned[id(target)] = label
    return sorted(
        f"{name} -> {banned[id(value)]}"
        for name, value in vars(module).items()
        if id(value) in banned)


def assert_clean(watch, *modules):
    """The three layers, in one call, in the order that matters.

    Call it AFTER the ``armed`` block has exited: inside it, every boundary
    is a raiser, so the identity census would be comparing the module's
    globals against the patches instead of against the real providers.

    The reached check comes before the "no calls" check on purpose. If the
    exercise never got to the module, "no boundary fired" is true and means
    nothing, and reporting it in that order would let the vacuous case pass
    as the good one.
    """
    unreached = [m.__name__ for m in modules if watch.reached(m) == 0]
    assert not unreached, (
        "the exercise executed no line in " + ", ".join(unreached) +
        " — §AA: a constraint the pipeline never reaches is a constraint "
        "nobody has tested, so a clean tripwire over a path that did not run "
        "is not a result. Fix the exercise, not this assertion.")
    assert watch.calls == [], watch.calls
    for module in modules:
        bound = provider_bindings(module)
        assert not bound, (module.__name__, bound)
