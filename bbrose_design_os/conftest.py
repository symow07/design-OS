"""Pytest root conftest.

Belt-and-suspenders for eager Celery in tests: the authoritative guard lives
in config/settings.py (``"pytest" in sys.modules`` forces
CELERY_TASK_ALWAYS_EAGER) because pytest-django can import settings before
this conftest runs. The env var below covers any subprocess/edge path that
re-reads the environment.

§AY1 — THE OUTBOUND-CALL GUARD.

Why this exists. ``ANTHROPIC_API_KEY`` was exported into the shell at length
zero. ``environ.Env.read_env`` will not override a key already present in
``os.environ``, so the blank won and the 108-character credential in .env was
never read. Three tests failed on that blank for five tranches and were
recorded as inherited. They were not inherited (§AY1(d)).

Clearing the blank makes the credential live inside a 7,475-test suite that
has never had a net under it. §AE7(c) makes unattended spend a stop
condition, and a green suite bought with unguarded spend is an invoice with a
green suite attached (§AY1(c)). So the net is built and WATCHED FIRING before
the credential is cleared, never after — §AA: a guard nobody has seen fire is
not evidence of anything.

What is refused. Any socket connect to an address that is not loopback, PLUS
any connect to a proxy endpoint declared in the environment even though such
an endpoint is itself on loopback.

THE SECOND CLAUSE IS NOT THEORETICAL AND WAS NOT ANTICIPATED. The first
version of this guard permitted loopback unconditionally, on the reasoning
that the suite's real dependencies are local — Postgres on localhost:5432,
Redis on localhost:6379, both measured from .env. That reasoning was wrong
in this environment, and inspection would never have shown it. This machine
exports ``HTTPS_PROXY=http://127.0.0.1:3213``. Every HTTP client that honours
the environment therefore dials LOOPBACK, and a relay carries the call to the
internet. Watched, not reasoned about: ``urllib.request.urlopen`` reached
api.anthropic.com through that proxy and came back ``HTTP Error 401``, while
a raw ``socket.create_connection`` to the same host was correctly refused.
The guard was leaking every HTTP call in the suite while passing its own
direct-connection tests.

**On this machine, loopback is not a boundary. It is a doorway.**

So the guard now (a) refuses the proxy endpoints, derived from the
environment rather than hardcoded, before the loopback exemption is consulted,
and (b) removes the proxy variables from the environment for the duration of
the session, so clients fall back to connecting directly and are refused on
the IP. Both are needed: (b) covers clients that read the environment on each
call, (a) covers clients that captured it at import time.

EXTENT OF THE PROTECTION, stated because §AY0(d) requires an absence to carry
one: this refuses direct outbound connections by address, and relays declared
in the standard proxy environment variables. It would NOT catch a relay
configured somewhere this does not read — a system PAC file, a transparent
proxy, or a hardcoded local forwarder. It is a net, not a sealed room.

AF_UNIX is permitted: its "address" is a filesystem path and cannot leave the
machine.

Refusal is LOUD and names the destination. A guard that fails silently, or
that fails with a socket error indistinguishable from a flaky network, would
be unfalsifiable in exactly the way §AA is about.

THE ESCAPE HATCH IS EXPLICIT AND GREPPABLE. ``@pytest.mark.allow_outbound_
network`` lifts the guard for one test. It is registered in pytest.ini so it
cannot be used by accident, and ``grep -rn allow_outbound_network`` returns
every test that has ever been trusted with the network.

CORRECTED BEFORE COMMIT, AND THE CORRECTION IS THE THIRD OF ITS KIND IN THIS
TRANCHE. This paragraph read "There are currently none, and a reviewer can
verify that in one command." I had not run the command. There is exactly ONE:
``apps/pipeline/tests/test_ay1_outbound_guard.py:145``, the guard's own
escape-hatch test, which deliberately checks the PREDICATE rather than opening
a live connection. Nothing else in the tree carries the marker. The invitation
to verify in one command was sound; the answer I supplied alongside it was
imagined, in a file whose subject is exactly that error (§AY0(d), §AZ0(c)).
"""
import os
import socket

import pytest

os.environ["CELERY_EAGER"] = "true"


class OutboundCallRefused(RuntimeError):
    """A test tried to open a socket to something that is not loopback."""


# Flipped ONLY by the allow_outbound_network marker, and restored after the
# test that asked for it. Module-level rather than a fixture argument because
# the socket patch is installed once per session and has no other way to see
# per-test state.
_ALLOW_OUTBOUND = False

_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "::ffff:127.0.0.1",
                   "localhost", "localhost.localdomain", "0.0.0.0", ""}

# (host, port) pairs that relay off-machine despite being on loopback.
# Populated from the environment at session start — never hardcoded, because
# the port is this machine's accident and the next machine's will differ.
_PROXY_ENDPOINTS: set = set()

# THREE STATES, NOT TWO. An empty _PROXY_ENDPOINTS can mean "this machine has
# no proxy" or "the learning step below broke", and the first version of the
# §AY1 regression test read the second meaning into both — so it passed for
# five months on a machine that happened to have a relay configured and then
# failed, honestly but for the wrong reason, on the same machine once the
# relay went away. These two record which state actually obtained:
#   _PROXY_CONFIG_SEEN  what getproxies() returned BEFORE the strip
#   _PROXY_LEARNING_RAN set only after the loop completes, so a loop that
#                       raised is distinguishable from a machine with nothing
#                       to learn. Empty config + ran = nothing to test here.
#                       Non-empty config + empty endpoints = the step broke.
_PROXY_CONFIG_SEEN: dict = {}
_PROXY_LEARNING_RAN: bool = False

# Resolved-IP -> hostname, so a refusal can name "api.anthropic.com" and not
# only "160.79.104.10". By the time connect() is called the name is gone;
# getaddrinfo is the last place that still has it.
_RESOLVED_NAMES: dict = {}

_real_connect = socket.socket.connect
_real_connect_ex = socket.socket.connect_ex
_real_getaddrinfo = socket.getaddrinfo


def _permitted(address) -> bool:
    """True if ``address`` cannot leave this machine."""
    if _ALLOW_OUTBOUND:
        return True
    # AF_UNIX: the address is a path (str/bytes), not a (host, port) pair.
    if isinstance(address, (str, bytes)):
        return True
    try:
        host, port = address[0], address[1]
    except (TypeError, IndexError, KeyError):
        # An address shape this guard does not understand is NOT waved
        # through. Failing open here would be the whole defect again.
        return False
    # ORDER MATTERS. A declared proxy is refused BEFORE the loopback
    # exemption is consulted, because the proxy lives on loopback and that
    # is exactly how the first version of this guard leaked.
    if (host, port) in _PROXY_ENDPOINTS:
        return False
    if host in _LOOPBACK_HOSTS:
        return True
    # 127.0.0.0/8 is all loopback, not just 127.0.0.1.
    return isinstance(host, str) and host.startswith("127.")


def _guarded_getaddrinfo(host, port, *args, **kwargs):
    """Remember name -> address so the refusal message can be readable."""
    results = _real_getaddrinfo(host, port, *args, **kwargs)
    if isinstance(host, str):
        for entry in results:
            try:
                _RESOLVED_NAMES.setdefault(entry[4][0], host)
            except (IndexError, TypeError):
                pass
    return results


def _describe(address) -> str:
    try:
        host, port = address[0], address[1]
    except Exception:  # noqa: BLE001
        return repr(address)
    name = _RESOLVED_NAMES.get(host)
    detail = f"{host}:{port}"
    if name and name != host:
        detail = f"{detail} ({name})"
    if (host, port) in _PROXY_ENDPOINTS:
        detail = f"{detail} [DECLARED PROXY — on loopback but it relays]"
    return detail


def _refusal(address) -> OutboundCallRefused:
    return OutboundCallRefused(
        f"OUTBOUND_CALL_REFUSED: a test tried to connect to "
        f"{_describe(address)}. The test suite may not make network calls: "
        f"a live credential plus an unattended suite is §AE7(c) spend. If "
        f"this call is genuinely required, mark the test with "
        f"@pytest.mark.allow_outbound_network and say why in the tranche "
        f"report — do not remove this guard."
    )


def _guarded_connect(self, address, *args, **kwargs):
    if not _permitted(address):
        raise _refusal(address)
    return _real_connect(self, address, *args, **kwargs)


def _guarded_connect_ex(self, address, *args, **kwargs):
    if not _permitted(address):
        raise _refusal(address)
    return _real_connect_ex(self, address, *args, **kwargs)


@pytest.fixture(scope="session", autouse=True)
def _block_outbound_calls():
    """Install the guard for the whole session, and remove it after.

    ``socket.create_connection`` and every HTTP client in the dependency tree
    bottom out in ``socket.socket.connect``/``connect_ex``, so patching these
    two covers requests, httpx, urllib3 and the Anthropic and OpenAI SDKs
    without needing to know about any of them.

    The proxy handling is the part that was learned the hard way; see the
    module docstring.
    """
    import urllib.parse
    import urllib.request

    # 1. Learn the relays BEFORE stripping them, so they can be refused by
    #    address for any client that captured the config at import time.
    global _PROXY_LEARNING_RAN
    # getproxies() consults TWO sources on macOS — the environment first, and
    # the system network configuration (scutil --proxy) only if the
    # environment is empty. Recorded as one dict because the guard does not
    # care which source declared a relay, only that one was declared.
    _PROXY_CONFIG_SEEN.update(urllib.request.getproxies())
    for scheme, url in _PROXY_CONFIG_SEEN.items():
        # getproxies() smuggles NO_PROXY in under the key "no", and its value
        # is a comma-separated exemption list, not a URL. Parsing it as one
        # raises and takes the whole session fixture down with it — which is
        # how this line came to be written.
        if scheme == "no":
            continue
        try:
            parsed = urllib.parse.urlparse(
                url if "://" in url else f"http://{url}")
            if not parsed.hostname:
                continue
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
        except ValueError:
            continue
        _PROXY_ENDPOINTS.add((parsed.hostname, port))
        try:
            for entry in _real_getaddrinfo(parsed.hostname, port):
                _PROXY_ENDPOINTS.add((entry[4][0], port))
        except OSError:
            pass
    # Set LAST, and only on the normal exit from the loop. A learning step
    # that raised leaves this False, which is the state the test refuses on.
    _PROXY_LEARNING_RAN = True

    # 2. Remove the proxy configuration for the session, so well-behaved
    #    clients dial the real host and are refused on its address.
    stripped = {}
    for name in list(os.environ):
        if name.lower().endswith("_proxy"):
            stripped[name] = os.environ.pop(name)

    socket.socket.connect = _guarded_connect
    socket.socket.connect_ex = _guarded_connect_ex
    socket.getaddrinfo = _guarded_getaddrinfo
    try:
        yield
    finally:
        socket.socket.connect = _real_connect
        socket.socket.connect_ex = _real_connect_ex
        socket.getaddrinfo = _real_getaddrinfo
        os.environ.update(stripped)


@pytest.fixture(scope="session", autouse=True)
def _brand_mark_approval_lookup_off():
    """THE OWNER'S SECOND ANSWER OF 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md:23803, the block headed "Before I start
    testing"): "When I approve the logo trace, switch the mark to it so gold foil can print." The switch is thrown
    by one data-only act — his approved master placed at docs/brand/mark/ with its approval record — and no test may
    change that day. ``config/settings.py`` turns the approval lookup off when pytest is imported before the settings
    are; a runner that sets Django up FIRST (the scratch runners do) imports the settings before pytest, so the
    lookup is turned off here too, for the whole session. A test that wants the vector mark hands a composer a master
    of its own; one that reads an approval record turns the lookup on for itself."""
    from django.conf import settings
    if not settings.configured:
        yield
        return
    previous = getattr(settings, "BRAND_MARK_APPROVAL_LOOKUP", None)
    settings.BRAND_MARK_APPROVAL_LOOKUP = False
    try:
        yield
    finally:
        if previous is None:
            del settings.BRAND_MARK_APPROVAL_LOOKUP
        else:
            settings.BRAND_MARK_APPROVAL_LOOKUP = previous


@pytest.fixture(scope="session", autouse=True)
def _refuse_the_real_media_root():
    """THE CLEAN-UP OF 2026-10-04 (his "tests never write into media/"). ``config/settings.py`` gives the suite a
    media folder of its own when pytest is imported before the settings; a runner that sets Django up FIRST imports
    the settings before pytest, and then MEDIA_ROOT is still the real media/ folder — every test that saves a file
    would write into his designs' store. Refused loudly, before any test runs, rather than patched behind its back."""
    from django.conf import settings
    if settings.configured and not hasattr(settings, "REAL_MEDIA_ROOT"):
        pytest.exit("REFUSED: the settings were loaded before pytest, so MEDIA_ROOT is the real media folder "
                    f"({settings.MEDIA_ROOT}); run the tests under pytest (python -m pytest …) so the suite gets "
                    "its own media folder.", returncode=3)
    yield


@pytest.fixture(autouse=True)
def _the_test_database_ends_at_head(request):
    """THE CLEAN-UP OF 2026-10-04 (his "tests never leave the test database at an old migration"). After every
    database-resetting test (TransactionTestCase and its live-server kin; a plain TestCase runs inside a transaction
    and cannot move the schema), the schema must be at the head of every app's migrations. A test that leaves it
    behind is failed by name here, and the head is restored so the rest of the run is not poisoned by it."""
    yield
    cls = getattr(request.node, "cls", None)
    if cls is None:
        return
    from django.test import TestCase, TransactionTestCase
    if not issubclass(cls, TransactionTestCase) or issubclass(cls, TestCase):
        return
    from apps.core.migration_head import at_head, restore_head
    if not at_head():
        restore_head()
        pytest.fail("%s left the test database at an old migration (restored to head for the rest of the run)"
                    % request.node.nodeid, pytrace=False)


@pytest.fixture(autouse=True)
def _honour_allow_outbound_network(request):
    """Lift the guard for a test that explicitly asked for the network."""
    global _ALLOW_OUTBOUND
    marked = request.node.get_closest_marker("allow_outbound_network")
    if marked is None:
        yield
        return
    _ALLOW_OUTBOUND = True
    try:
        yield
    finally:
        _ALLOW_OUTBOUND = False


@pytest.fixture(autouse=True)
def isolated_rescue_spend(monkeypatch, tmp_path):
    """Use one undo stack so optional settings and patched composers restore together."""
    from django.conf import settings
    monkeypatch.setattr(settings, 'RESCUE_SPEND_ROOT', tmp_path / 'rescue_spend', raising=False)
