"""§BH41(3) — THE DRAINED LIVE SERVER: no flush starts while a request is mid-handling.

THE CAUSE THIS REMOVES (§BH41(2), measured): a live-server test's teardown closes its browser contexts and
Django's ``_post_teardown`` then flushes the test database with one ``TRUNCATE`` over every table
(django/core/management/commands/flush.py:73, the PostgreSQL ``sql_flush`` at
django/db/backends/postgresql/operations.py:210-224, the tables in ``set`` order). The live server
(django/test/testcases.py:1752 ``LiveServerThread`` → django/core/servers/basehttp.py:86
``ThreadedWSGIServer``) handles each request in its own thread with its OWN PostgreSQL connection, closed
only in ``close_request`` (basehttp.py:109-111) — AFTER the view has run its queries. Closing the browser
context ends the client side of a request; the server thread keeps running the view. A query of that
request that already holds an AccessShareLock on one table and asks for another, while the ``TRUNCATE``
holds the second and asks for the first, is the two-backend cycle PostgreSQL resolves by aborting the
``TRUNCATE``: ``DeadlockDetected`` → ``CommandError: … couldn't be flushed`` → the rows of the finished
test stay → the next test's ``setUp`` hits ``UniqueViolation``. Seven retained captures, all this shape.

THE SHAPE (§BH41(3), "closing the live-server thread's connection before flush"): the server counts
requests in flight from their accept; the test case waits, BEFORE the flush, until every ordinary request
has finished — its view run, its connection closed in ``close_request``, its locks released — and none has
arrived for a quiet window, then proves on the test's own connection that no other backend of the test
database holds a relation lock, and only then flushes. A streaming response whose client has gone (the task
page's server-sent-events stream, live_views.py) is tolerated once it is older than ``stream_seconds``:
measured on this host, a server thread learns of a gone client only at its SECOND write after the close, the
stream writes once per fifteen iterations, and a shutdown of its socket from the server side raises ENOTCONN
and changes nothing — so it ends by itself one to two ping intervals later, or at the flush (its task gone);
between its single-table statements it holds no lock, and the lock check catches a statement mid-flight.
Nothing is skipped, retried, widened or weakened: the flush still runs, every test still runs, the waits are
bounded and their expiry is a failure with its own name.

Every ``StaticLiveServerTestCase`` of the suite inherits ``DrainedStaticLiveServerTestCase`` instead.
"""
from __future__ import annotations

import select
import socket
import threading
import time

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.servers.basehttp import ThreadedWSGIServer
from django.test.testcases import LiveServerThread


class LiveServerNotDrained(AssertionError):
    """The named failure: a request was still mid-handling when the drain timeout expired."""


class DrainableWSGIServer(ThreadedWSGIServer):
    """``ThreadedWSGIServer`` that counts requests in flight and can be waited on."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._inflight = 0
        self._sockets = {}                      # request socket → (client address, accept time), while in flight
        self._drain_cv = threading.Condition()

    def process_request(self, request, client_address):
        # counted from the ACCEPT, in the server's own loop, so a request whose handler thread has not yet
        # started is already in flight for the drain; the socket is kept so an abandoned request can be ended
        with self._drain_cv:
            self._inflight += 1
            self._sockets[request] = (client_address, time.monotonic())
        try:
            super().process_request(request, client_address)      # starts the handler thread
        except BaseException:
            self._one_done(request)
            raise

    def process_request_thread(self, request, client_address):
        try:
            # socketserver runs finish_request (the view, its queries, the response) and, in its own
            # ``finally``, shutdown_request → close_request → connections.close_all(): when this returns,
            # the thread's database connection is closed and every lock it held is released.
            super().process_request_thread(request, client_address)
        finally:
            self._one_done(request)

    def _one_done(self, request):
        with self._drain_cv:
            self._inflight -= 1
            self._sockets.pop(request, None)
            self._drain_cv.notify_all()

    def _describe(self) -> str:
        """The in-flight requests, for the named failure: client, age, whether its client has gone, and where
        every request-handler thread of this server stands (its innermost frames)."""
        import sys, traceback
        now = time.monotonic()
        parts = ["%s:%s age=%.1fs client_gone=%s" % (addr[0], addr[1], now - t0, self._client_gone(sock))
                 for sock, (addr, t0) in list(self._sockets.items())]
        frames = sys._current_frames()
        for th in threading.enumerate():
            if th is threading.main_thread() or th.ident not in frames or "process_request_thread" not in th.name:
                continue
            stack = traceback.extract_stack(frames[th.ident])[-4:]
            parts.append("thread %s: %s" % (th.name, " <- ".join("%s:%d %s" % (f.filename.split("/")[-1], f.lineno, f.name) for f in reversed(stack))))
        return "; ".join(parts)

    @staticmethod
    def _client_gone(sock) -> bool:
        """True when the peer has closed its side: the socket is readable and a peek yields EOF. A live client
        that is merely waiting for its response is not readable and is never touched."""
        try:
            readable, _, _ = select.select([sock], [], [], 0)
            if not readable:
                return False
            return sock.recv(1, socket.MSG_PEEK) == b""
        except (OSError, ValueError):
            return True                          # already closed underneath us: nothing left to wait for

    @property
    def inflight(self) -> int:
        with self._drain_cv:
            return self._inflight

    #: the quiet window: in flight must be zero and STAY zero this long — a request the client sent just
    #: before its context closed can still be accepted a few milliseconds later
    settle_seconds = 0.05
    #: how often, while requests remain in flight, the drain looks for clients that have gone
    poll_seconds = 0.1

    #: a request older than this at drain time is a streaming response (an ordinary request takes
    #: milliseconds); once its client has gone it is shut down and tolerated — between its statements it holds
    #: no lock, and it ends at its next write
    stream_seconds = 2.0

    def blocking_requests(self):
        """The in-flight requests the flush must not race: every request younger than ``stream_seconds``, and
        every older one whose client is still connected."""
        now = time.monotonic()
        return [(sock, addr, now - t0) for sock, (addr, t0) in list(self._sockets.items())
                if now - t0 < self.stream_seconds or not self._client_gone(sock)]

    def wait_idle(self, timeout: float) -> float:
        """Block until no blocking request remains and none arrives for ``settle_seconds``; return the seconds
        waited. Raise ``LiveServerNotDrained`` when ``timeout`` expires first — the fast, named failure."""
        started = time.monotonic()
        deadline = started + timeout
        while True:
            with self._drain_cv:
                blocking = self.blocking_requests()
                if not blocking:
                    # zero now: hold for the quiet window; a new arrival restarts the wait
                    if not self._drain_cv.wait(self.settle_seconds) and not self.blocking_requests():
                        return time.monotonic() - started
                    continue
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise LiveServerNotDrained(
                        "LIVE_SERVER_NOT_DRAINED: %d request(s) still mid-handling after %.1fs — the "
                        "flush would race a live thread (§BH41): %s" % (len(blocking), timeout, self._describe()))
                self._drain_cv.wait(min(remaining, self.poll_seconds))


class DrainableLiveServerThread(LiveServerThread):
    server_class = DrainableWSGIServer


class DrainedStaticLiveServerTestCase(StaticLiveServerTestCase):
    """The suite's live-server base: the flush never starts while a request is mid-handling."""

    server_thread_class = DrainableLiveServerThread
    #: seconds a teardown may wait for the server to drain before failing by name. The bound must exceed
    #: the product's longest SILENT request: the task page's server-sent-events stream
    #: (apps/pipeline/live_views.py) sleeps a second between polls and writes a visible ping only every
    #: fifteen iterations, and a server thread learns that its client has gone only when a write fails —
    #: so a stream whose page just closed can stay mid-handling for up to ~16 s. Measured on the first
    #: negative-control run (E_after_fix/run_1): a 15 s bound expired on exactly that stream.
    live_server_drain_timeout = 25.0
    #: the seconds each teardown waited, kept on the class for the usage record (§BH41 goal report)
    drain_waits: list = []

    #: seconds the flush may wait for the other backends of the test database to hold no relation lock
    lock_quiet_timeout = 10.0

    def _wait_no_foreign_locks(self):
        """Right before the flush: wait until no OTHER backend of this database holds a relation lock, polled
        every 10 ms, so the TRUNCATE never begins beside a statement in flight. A tolerated stream between its
        statements holds nothing; a statement caught mid-flight finishes in milliseconds."""
        from django.db import connection
        deadline = time.monotonic() + self.lock_quiet_timeout
        sql = ("SELECT count(*) FROM pg_locks l JOIN pg_stat_activity a ON a.pid = l.pid "
               "WHERE a.datname = current_database() AND a.pid <> pg_backend_pid() "
               "AND l.locktype = 'relation' AND l.granted")
        with connection.cursor() as cur:
            while True:
                cur.execute(sql)
                if cur.fetchone()[0] == 0:
                    return
                if time.monotonic() > deadline:
                    raise LiveServerNotDrained("LIVE_SERVER_NOT_DRAINED: another backend still holds a relation "
                                               "lock after %.1fs — the flush would race it (§BH41)" % self.lock_quiet_timeout)
                time.sleep(0.01)

    def _post_teardown(self):
        # The flush ALWAYS runs: a drain that times out is reported by name AFTER the database is flushed,
        # never by skipping the flush — a skipped flush is the cascade this class exists to remove
        # (the next test's setUp would meet the rows this test left).
        httpd = getattr(getattr(self, "server_thread", None), "httpd", None)
        not_drained = None
        if httpd is not None:
            try:
                waited = httpd.wait_idle(self.live_server_drain_timeout)
                self._wait_no_foreign_locks()
            except LiveServerNotDrained as exc:
                not_drained = exc
                waited = self.live_server_drain_timeout
            type(self).drain_waits.append(waited)
        try:
            super()._post_teardown()
        finally:
            if not_drained is not None:
                raise not_drained
