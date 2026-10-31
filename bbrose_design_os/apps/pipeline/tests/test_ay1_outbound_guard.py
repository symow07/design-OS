"""§AY1 — the outbound-call guard in the root conftest, watched firing.

§AA: a guard nobody has seen fire is not evidence of anything. These tests
make REAL outbound calls — to a host this machine can genuinely reach, which
was verified by connecting to it outside pytest before the guard was written
(api.anthropic.com:443, 0.242 s, peer 160.79.104.10) — and assert that the
guard stops them. Without that counterfactual the tests would pass just as
happily on an unplugged network cable, which is the failure mode §AA names.

CORRECTION, LEFT VISIBLE BECAUSE IT IS THE POINT OF THE FILE. This docstring
originally read "NO PACKET LEAVES THE MACHINE when these run", asserted before
it was measured. IT WAS FALSE. On the first run
``test_an_http_client_is_refused`` returned ``HTTP Error 401: Unauthorized``
from api.anthropic.com — the call went out, reached the provider and came
back, because this machine exports ``HTTPS_PROXY=http://127.0.0.1:3213`` and
the guard permitted loopback. A packet left the machine, through a hole in the
guard, inside the test written to prove the guard had no holes. It is true now
because the guard refuses declared proxy endpoints too, and that clause exists
only because this was RUN.

The claim survives in corrected form: no packet leaves the machine, and the
reason is now two clauses rather than one. §AA is not a slogan here — direct
connections were refused correctly from the first version, so every
inspection-based check would have passed.
"""
import socket
import urllib.error
import urllib.request

import pytest

from conftest import OutboundCallRefused, _permitted

EXTERNAL = ("api.anthropic.com", 443)


class TestTheGuardRefusesRealOutboundCalls:

    def test_a_raw_socket_to_a_reachable_external_host_is_refused(self):
        with pytest.raises(OutboundCallRefused):
            socket.create_connection(EXTERNAL, timeout=10)

    def test_connect_ex_is_refused_too(self):
        """connect_ex returns an error code rather than raising, so a guard
        that only patched connect() would leak every caller that uses it."""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            with pytest.raises(OutboundCallRefused):
                s.connect_ex(EXTERNAL)
        finally:
            s.close()

    def test_an_http_client_is_refused(self):
        """urllib bottoms out in socket.connect, which is why the guard does
        not need to know about any particular HTTP library."""
        with pytest.raises(OutboundCallRefused):
            urllib.request.urlopen("https://api.anthropic.com/v1/models",
                                   timeout=10)

    def test_the_refusal_names_the_destination_and_the_escape_hatch(self):
        with pytest.raises(OutboundCallRefused) as excinfo:
            socket.create_connection(EXTERNAL, timeout=10)
        message = str(excinfo.value)
        assert "OUTBOUND_CALL_REFUSED" in message
        # The name matters more than the number. By the time connect() runs,
        # the address is an IP; the guard hooks getaddrinfo purely so a human
        # reading this refusal is told WHO was being called. Asserted as two
        # facts rather than one formatted string because the first version of
        # this assertion tested a layout I had imagined, not the one the
        # guard produces: "160.79.104.10:443 (api.anthropic.com)".
        assert "api.anthropic.com" in message
        assert ":443" in message
        assert "allow_outbound_network" in message


class TestTheProxyHoleThatTheFirstVersionLeakedThrough:
    """The regression tests for the defect this file's first run exposed."""

    def test_the_declared_proxy_endpoint_is_refused_despite_being_loopback(
            self):
        # THE ASSERTION THIS REPLACES IS QUOTED HERE RATHER THAN DELETED,
        # because its message named its own defect and then made the mistake
        # anyway:
        #
        #     assert _PROXY_ENDPOINTS, (
        #         "no proxy endpoints were learned; on a machine with no
        #          proxy configured this assertion is the wrong test, but on
        #          THIS machine an empty set means the learning step silently
        #          broke")
        #
        # "on THIS machine" was true when it was written and is false now:
        # measured 2026-08-24, getproxies() returns {} from BOTH sources it
        # consults — the environment and, on macOS, the system network config
        # (scutil --proxy reports HTTPEnable 0, HTTPSEnable 0). The suite ran
        # green with this test at 04:03Z and 04:16Z the same day, so nothing
        # in the repository changed; the machine did. An instrument that
        # recognises its subject by an incidental feature of the environment
        # it was written in is AD0(b), and this is that.
        #
        # The register was the wrong relief: this failure is deterministic in
        # 0.08s, not a flake, and tier2_gate's own words are that "being
        # known about is not relief". Fixed at the premise instead.
        import conftest
        # Module attribute, not `from conftest import _PROXY_LEARNING_RAN` —
        # a from-import binds the value, and the point of this flag is that
        # it is written by a fixture that runs before this line.
        assert conftest._PROXY_LEARNING_RAN, (
            "the proxy learning step did not run to completion — it raised "
            "part-way, so an empty endpoint set proves nothing")
        if not conftest._PROXY_CONFIG_SEEN:
            pytest.skip(
                "no proxy is configured on this machine (getproxies() == {} "
                "from environment AND system config, measured at session "
                "start) — there is no relay for this test to demand a "
                "refusal of. NOT a pass: this path is unexercised here.")
        _PROXY_ENDPOINTS = conftest._PROXY_ENDPOINTS
        assert _PROXY_ENDPOINTS, (
            f"a proxy IS configured ({conftest._PROXY_CONFIG_SEEN}) but no "
            f"endpoints were learned from it — the learning step silently "
            f"broke, which is the failure the original assertion meant")
        for host, port in _PROXY_ENDPOINTS:
            assert not _permitted((host, port)), (
                f"{host}:{port} is a declared relay and must be refused "
                f"even though it is on loopback")

    def test_proxy_env_vars_are_stripped_for_the_session(self):
        """Belt to the braces above: a client that re-reads the environment
        must not find a relay to dial in the first place."""
        import os
        leaked = [k for k in os.environ if k.lower().endswith("_proxy")]
        assert leaked == [], f"proxy config still visible to clients: {leaked}"

    def test_an_http_client_is_refused_rather_than_returning_401(self):
        """The exact call that leaked. A 401 here means the guard is open
        again — the request reached the provider and was answered."""
        with pytest.raises(OutboundCallRefused):
            urllib.request.urlopen("https://api.anthropic.com/v1/models",
                                   timeout=10)


class TestTheGuardDoesNotBreakTheSuite:
    """The suite's real dependencies are local. If the guard took those down
    it would be traded for 7,000 failures, so this is not a formality."""

    def test_loopback_is_permitted(self):
        assert _permitted(("127.0.0.1", 5432))
        assert _permitted(("localhost", 6379))
        assert _permitted(("::1", 5432))

    def test_the_whole_127_block_is_loopback_not_just_127_0_0_1(self):
        assert _permitted(("127.0.1.1", 5432))

    def test_unix_socket_paths_are_permitted(self):
        """An AF_UNIX address is a filesystem path and cannot leave the box.
        Postgres uses one by default on macOS."""
        assert _permitted("/tmp/.s.PGSQL.5432")

    def test_a_real_loopback_connection_still_completes(self):
        """Not the predicate — an actual connection, through the patched
        socket, to the Postgres the suite is talking to anyway."""
        s = socket.create_connection(("127.0.0.1", 5432), timeout=5)
        s.close()


class TestTheGuardFailsClosed:

    def test_an_address_shape_the_guard_cannot_read_is_refused(self):
        """Failing OPEN on an unrecognised address would reintroduce the
        exact defect: a guard that waves through what it does not
        understand."""
        assert not _permitted(None)
        assert not _permitted(12345)

    def test_an_unmarked_test_does_not_have_the_hatch(self):
        assert not _permitted(EXTERNAL)


class TestTheEscapeHatch:

    @pytest.mark.allow_outbound_network
    def test_the_marker_lifts_the_guard(self):
        """Checks the predicate, deliberately not a live connection — see the
        module docstring. `grep -rn allow_outbound_network apps/` should
        return this test and nothing else."""
        assert _permitted(EXTERNAL)
