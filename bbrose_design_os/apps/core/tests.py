import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings


class ServeMediaTests(TestCase):
    """Milestone 8.1 — authenticated media downloads with traversal protection."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._tmp = tempfile.TemporaryDirectory()
        cls.media_root = Path(cls._tmp.name) / "media"
        (cls.media_root / "generated").mkdir(parents=True)
        (cls.media_root / "generated" / "test.png").write_bytes(b"PNGDATA")          # an untiered output
        # §BH54(b): the five cases under one door — a file under each reference folder, a tiered REFERENCE, a
        # tiered PRODUCTION, a sha256 the record gives two tiers, and the untiered output above
        for rel, data in (("references/ref.png", b"REF-FOLDER-BYTES"), ("web_quarantine/3/x.jpg", b"WQ-FOLDER-BYTES"),
                          ("concept_thumbs/t.png", b"THUMB-FOLDER-BYTES"), ("generated/reference.png", b"REFERENCE-BYTES"),
                          ("generated/production.png", b"PRODUCTION-BYTES"), ("generated/both.png", b"BOTH-TIERS")):
            (cls.media_root / rel).parent.mkdir(parents=True, exist_ok=True)
            (cls.media_root / rel).write_bytes(data)
        import hashlib as _hb
        import json as _js
        cls.tiers = Path(cls._tmp.name) / "materials_tiers.jsonl"
        cls.tiers.write_text("".join(_js.dumps({"relative_path": p, "tier": t, "sha256": _hb.sha256(b).hexdigest()}) + "\n"
                                     for p, t, b in (("materials/ref.png", "REFERENCE", b"REFERENCE-BYTES"),
                                                     ("materials/prod.png", "PRODUCTION", b"PRODUCTION-BYTES"),
                                                     ("materials/a.png", "PRODUCTION", b"BOTH-TIERS"),
                                                     ("materials/b.png", "REFERENCE", b"BOTH-TIERS"))))
        # A file OUTSIDE MEDIA_ROOT that a traversal attack would target.
        (Path(cls._tmp.name) / "secret.txt").write_text("top secret")
        cls._override = override_settings(MEDIA_ROOT=str(cls.media_root), HISTORY_TIER_RECORD=str(cls.tiers))
        cls._override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._override.disable()
        cls._tmp.cleanup()
        super().tearDownClass()

    def setUp(self):
        self.user = User.objects.create_user("designer", "d@bbrose.test", "pw-123456")

    def test_unauthenticated_request_is_rejected(self):
        res = self.client.get("/files/generated/test.png")
        self.assertIn(res.status_code, (302, 403))

    def test_authenticated_request_streams_file(self):
        self.client.force_login(self.user)
        res = self.client.get("/files/generated/test.png")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(b"".join(res.streaming_content), b"PNGDATA")

    def test_path_traversal_returns_404(self):
        self.client.force_login(self.user)
        res = self.client.get("/files/..%2Fsecret.txt")
        self.assertEqual(res.status_code, 404)

    def test_missing_file_returns_404(self):
        self.client.force_login(self.user)
        res = self.client.get("/files/generated/nope.png")
        self.assertEqual(res.status_code, 404)

    def test_local_media_url_routes_through_auth_view(self):
        from django.conf import settings
        self.assertEqual(settings.MEDIA_URL, "/files/")

    # §BH54(b), the five cases. "The door refuses a request when the file lies under the reference folders … or when
    # the file HAS a tier row that is not PRODUCTION. Everything else is served as today."
    def test_a_file_under_a_reference_folder_is_refused_by_name(self):
        self.client.force_login(self.user)
        for url, folder in (("/files/references/ref.png", "references"), ("/files/web_quarantine/3/x.jpg", "web_quarantine"),
                            ("/files/concept_thumbs/t.png", "concept_thumbs")):
            res = self.client.get(url)
            self.assertEqual(res.status_code, 403, url)
            self.assertEqual(res.content.decode(),
                             f"REFUSED_REFERENCE_FOLDER: {url.rsplit('/', 1)[1]} — under media/{folder}, a REFERENCE-class directory (§BH54(b))")
        # the predicate reads the resolved path by directory identity: a case variant and a dot-dot route into the
        # folder are refused; a dot-dot route out of it to an output is served
        import os as _os
        upper = self.media_root / "REFERENCES"
        if upper.exists() and _os.path.samefile(upper, self.media_root / "references"):     # a case-insensitive volume
            self.assertEqual(self.client.get("/files/REFERENCES/ref.png").status_code, 403)
        self.assertEqual(self.client.get("/files/generated/../references/ref.png").status_code, 403)
        self.assertEqual(self.client.get("/files/references/../generated/test.png").status_code, 200)
        self.assertEqual(self.client.get("/files/references/nope.png").status_code, 404)      # missing stays ahead

    def test_a_tiered_reference_is_refused_and_a_tiered_production_is_served(self):
        self.client.force_login(self.user)
        ref = self.client.get("/files/generated/reference.png")
        self.assertEqual(ref.status_code, 403)
        self.assertEqual(ref.content.decode(),
                         "REFUSED_REFERENCE_ASSET: reference.png — tier REFERENCE by the tier record; only PRODUCTION is served (§BH54(b))")
        both = self.client.get("/files/generated/both.png")
        self.assertEqual(both.status_code, 403)
        self.assertIn("tier PRODUCTION + REFERENCE by the tier record", both.content.decode())
        prod = self.client.get("/files/generated/production.png")
        self.assertEqual((prod.status_code, b"".join(prod.streaming_content)), (200, b"PRODUCTION-BYTES"))

    def test_an_untiered_output_is_served_with_or_without_a_readable_record(self):
        """"No tier row" is evidence of nothing about an output: served, as today — and with no readable record the
        tier clause has nothing to say while the folder clause still refuses."""
        self.client.force_login(self.user)
        res = self.client.get("/files/generated/test.png")
        self.assertEqual((res.status_code, b"".join(res.streaming_content)), (200, b"PNGDATA"))
        with override_settings(HISTORY_TIER_RECORD=str(Path(self._tmp.name) / "absent.jsonl")):
            self.assertEqual(self.client.get("/files/generated/test.png").status_code, 200)
            self.assertEqual(self.client.get("/files/generated/reference.png").status_code, 200)   # no record: no row
            self.assertEqual(self.client.get("/files/references/ref.png").status_code, 403)


class FilesDoorLivePagesTests(TestCase):
    """§BH54(b): "the Gate-1 grid, Gate-2 preview, Library and slice 1 media all still load, named one by one" — each
    page's own /files/ URL for an untiered output, fetched through the corrected door. Slice 1 is proved in
    HistorySliceTests beside its hrefs."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._tmpd = tempfile.TemporaryDirectory()
        cls.media = Path(cls._tmpd.name) / "media"
        for rel, data in (("generated/g.png", b"GRID-CONCEPT"), ("dielines/p.png", b"GATE2-PREVIEW"), ("generated/lib.png", b"LIBRARY-THUMB")):
            (cls.media / rel).parent.mkdir(parents=True, exist_ok=True)
            (cls.media / rel).write_bytes(data)
        cls._overrided = override_settings(MEDIA_ROOT=str(cls.media), HISTORY_TIER_RECORD=str(Path(cls._tmpd.name) / "no-record.jsonl"))
        cls._overrided.enable()

    @classmethod
    def tearDownClass(cls):
        cls._overrided.disable()
        cls._tmpd.cleanup()
        super().tearDownClass()

    def setUp(self):
        from django.contrib.auth.models import Group
        from apps.core.models import Brand
        from apps.pipeline.models import DesignTask, GeneratedImage, PackagingOutput
        from apps.pipeline.permissions import ROLE_DESIGNER
        group, _ = Group.objects.get_or_create(name=ROLE_DESIGNER)
        self.user = User.objects.create_user("designer54", "d54@bbrose.test", "pw-123456")
        self.user.groups.add(group)
        self.client.force_login(self.user)
        brand = Brand.objects.create(name="B54", master_brief="x")
        self.task = DesignTask.objects.create(brand=brand, task_text="a packaging task", status="completed")   # the default target
        self.image = GeneratedImage.objects.create(task=self.task, direction_name="d", prompt_used="p", image_file="generated/g.png")
        self.output = PackagingOutput.objects.create(task=self.task, approved_image=self.image, design_preview="dielines/p.png",
                                                     spec_sheet={}, is_final_approved=True)
        lib_task = DesignTask.objects.create(brand=brand, task_text="a library task", status="completed")
        lib_image = GeneratedImage.objects.create(task=lib_task, direction_name="d", prompt_used="p", image_file="generated/lib.png")
        self.lib_output = PackagingOutput.objects.create(task=lib_task, approved_image=lib_image, spec_sheet={}, is_final_approved=True)

    def _path(self, url):
        from urllib.parse import urlparse
        return urlparse(url).path

    def test_the_gate1_grid_images_still_load(self):
        data = self.client.get(f"/api/tasks/{self.task.pk}/status/").json()
        url = self._path(data["images"][0]["image_url_display"])
        self.assertEqual(url, "/files/generated/g.png")
        res = self.client.get(url)
        self.assertEqual((res.status_code, b"".join(res.streaming_content)), (200, b"GRID-CONCEPT"))

    def test_the_gate2_preview_still_loads(self):
        data = self.client.get(f"/api/tasks/{self.task.pk}/status/").json()
        url = self._path(data["packaging_output"]["design_preview_url"])
        self.assertEqual(url, "/files/dielines/p.png")
        res = self.client.get(url)
        self.assertEqual((res.status_code, b"".join(res.streaming_content)), (200, b"GATE2-PREVIEW"))

    def test_the_library_thumbnails_still_load(self):
        # [the clean-up of 2026-10-04 (E10b): the old /api/library/ list is gone; the Library's own Finished designs
        # page shows each finished design by its picture, read here from the page as he sees it] [the owner's goal of
        # 2026-10-29: the Library lists the rounds' made files; an old finished design keeps its own page, unlisted —
        # read there]
        import re
        html = "".join(self.client.get(f"/dashboard/library/finished/{o.pk}/").content.decode()
                       for o in (self.output, self.lib_output))
        urls = sorted({self._path(u) for u in re.findall(r'<img src="([^"]+)"', html) if "/files/" in u})
        # §BH55 Phase 3 p3-library: a finished design is shown by its own picture — here its Gate-2 preview — and a
        # design with none by its concept, as before (it was the concept for both); both still load through the door
        self.assertEqual(urls, ["/files/dielines/p.png", "/files/generated/lib.png"])
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 200, url)


class HealthzTests(TestCase):
    """Milestone 8.7 — /healthz probe."""

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_eager_mode_reports_eager(self):
        res = self.client.get("/healthz")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["celery"], "eager")
        self.assertEqual(data["db"], "ok")

    @override_settings(CELERY_TASK_ALWAYS_EAGER=False)
    @patch("apps.core.health.ping_workers", return_value=None)
    @patch("apps.core.health.check_redis", return_value="ok")
    def test_no_worker_returns_503(self, mock_redis, mock_ping):
        res = self.client.get("/healthz")
        self.assertEqual(res.status_code, 503)
        self.assertIn("error", res.json()["celery"])

    @override_settings(CELERY_TASK_ALWAYS_EAGER=False)
    @patch("apps.core.health.ping_workers", return_value={"worker@host": {"ok": "pong"}})
    @patch("apps.core.health.check_redis", return_value="ok")
    def test_live_worker_returns_200(self, mock_redis, mock_ping):
        res = self.client.get("/healthz")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["celery"], "ok")


class MigrationStateTests(TestCase):
    """`migration_state` must distinguish three states, not two.

    The function exists because two callers had each hand-rolled the same
    `executor.migration_plan(...)` call and the copies had already diverged
    (§AR2): one named the offending migrations, the other reduced everything —
    including a database that would not answer — to a bare False.
    """

    def _plan(self, *migrations):
        """A fake plan shaped like Django's: (migration, backwards) pairs."""
        class _M:
            def __init__(self, app_label, name):
                self.app_label, self.name = app_label, name
        return [(_M(a, n), False) for a, n in migrations]

    def test_a_clean_database_reports_ok(self):
        from apps.core.health import migration_state
        # The test database is migrated by the runner, so this is the real
        # measurement rather than a mocked one.
        self.assertEqual(migration_state(), "ok")

    def test_drift_names_the_migrations_rather_than_the_app(self):
        """Django's own startup notice says "app(s): dielines" and stops.

        With 8 dielines migrations on disk that does not identify which one is
        missing, and identifying it is the entire content of the incident this
        measurement exists for.
        """
        from apps.core import health
        with patch("django.db.migrations.executor.MigrationExecutor") as ex:
            ex.return_value.migration_plan.return_value = self._plan(
                ("dielines", "0008_alter_dielinejob_template_type"))
            state = health.migration_state()
        self.assertTrue(state.startswith("unapplied: 1 ("))
        self.assertIn("dielines.0008_alter_dielinejob_template_type", state)

    def test_an_unreadable_database_is_unknown_and_never_ok(self):
        """`manage.py migrate` fixes drift and is meaningless for this one, so
        a caller that cannot tell them apart advises the wrong command."""
        from apps.core import health
        with patch("django.db.migrations.executor.MigrationExecutor",
                   side_effect=RuntimeError("connection refused")):
            state = health.migration_state()
        self.assertTrue(state.startswith("unknown: "))
        self.assertIn("connection refused", state)
        self.assertNotEqual(state, "ok")

    def test_a_long_plan_is_truncated_and_says_so(self):
        from apps.core import health
        with patch("django.db.migrations.executor.MigrationExecutor") as ex:
            ex.return_value.migration_plan.return_value = self._plan(
                *[("pipeline", f"00{i}_x") for i in range(1, 8)])
            state = health.migration_state()
        self.assertTrue(state.startswith("unapplied: 7 ("))
        self.assertTrue(state.endswith(", …)"))
        self.assertIn("pipeline.005_x", state)
        self.assertNotIn("pipeline.006_x", state)

    def test_migration_state_is_not_wired_into_healthz(self):
        """§AY0(e) — the refusal is reported at the volume of an action.

        /healthz returns 503 when any value is not "ok"/"eager"
        (apps/core/views.py), so a migration entry there would pull a service
        out of rotation during exactly the rolling deploy where the new code
        is live and `migrate` has not run yet. Drift is a correctness signal
        for whoever is about to trust the schema, not a liveness signal.

        Asserted rather than left as a comment, because the tempting edit is
        one line and nothing else would catch it.
        """
        from apps.core.health import run_health_checks
        self.assertNotIn("migrations", run_health_checks())
        res = self.client.get("/healthz")
        self.assertNotIn("migrations", res.json())


class StartupMigrationDriftSurfaceTests(TestCase):
    """`ops.migration_guard`'s remaining 40% — a surface that REPORTS.

    The measurement (`migration_state`) has existed since the node opened and
    is tested above. What did not exist was anything that says it out loud at
    startup on this machine, and the node's own record said so in those words:
    "no startup surface reports drift on THIS machine".

    Observed firing before these tests were written, unforced — `manage.py
    check` and `manage.py runserver --noreload` both printed
    `core.migrations.W001` naming
    `dielines.0008_alter_dielinejob_template_type_and_more`, with no flag
    flipped and nothing stubbed. §AA is discharged by that observation; these
    tests are what stop it silently un-discharging.
    """

    _LOCAL = "LOCAL_DEVELOPMENT"

    def _run(self):
        from apps.core.checks import check_local_migration_drift
        return check_local_migration_drift(app_configs=None)

    def _behind(self):
        return "unapplied: 1 (dielines.0008_alter_dielinejob_template_type)"

    def test_the_check_is_registered_by_a_BARE_django_setup(self):
        """The whole of §AA in one assertion, and it took two attempts.

        Every other test in this class would pass with the module importing
        nowhere and the check firing on no machine, ever — they call the
        function directly. `84e0018` shipped a brand-string guard wired to
        exactly nothing and it took a later session to notice; the difference
        between that and this is one import in `apps/core/apps.py:ready()`.

        THE FIRST VERSION OF THIS TEST DID NOT WORK, AND THE WAY IT DID NOT
        WORK IS THE POINT. It read:

            from django.core.checks.registry import registry
            from apps.core.checks import check_local_migration_drift
            self.assertIn(check_local_migration_drift, registry.get_checks())

        That PASSES with `ready()` gutted — measured, by gutting it — because
        the test's own import executes `@register("core")` and registers the
        thing it is about to assert is registered. A test that satisfies its
        own precondition proves nothing about the running application. The
        test written to close the wired-to-nothing hole was itself wired to
        nothing, and only running the mutant showed it: seven of eight
        negative controls fired and this one sat silent.

        Asking in-process is unfixable here, because any sibling test that
        imports the module registers it for the rest of the session, so the
        result would depend on collection order. So the question is asked in a
        FRESH INTERPRETER that does nothing but `django.setup()` — no import
        of `apps.core.checks` anywhere in it. If `ready()` stops importing the
        module, this goes red, which is what a guard is.
        """
        import subprocess
        import sys
        from pathlib import Path

        root = Path(__file__).resolve().parents[2]
        probe = (
            "import os, django;"
            "os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings');"
            "django.setup();"
            "from django.core.checks.registry import registry;"
            "print(sorted(c.__module__ + '.' + c.__name__ "
            "for c in registry.get_checks()))"
        )
        out = subprocess.run([sys.executable, "-c", probe], cwd=root,
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr[-2000:])
        self.assertIn("apps.core.checks.check_local_migration_drift",
                      out.stdout)

    def test_it_is_not_tagged_database_or_it_would_stop_running_on_startup(
            self):
        """Django SKIPS `Tags.database` checks unless `--database` is passed.

        Tagging this one that way is the obvious tidy-up — it does touch the
        database — and it would delete the surface without failing anything.
        Silent removal by a plausible edit is the exact failure this node
        exists for, so the tag is asserted absent.
        """
        from django.core.checks import Tags

        from apps.core.checks import check_local_migration_drift

        self.assertEqual(check_local_migration_drift.tags, ("core",))
        self.assertNotIn(Tags.database, check_local_migration_drift.tags)

    def test_a_declared_local_machine_with_drift_NAMES_the_migration(self):
        """Django's own runserver notice says "app(s): dielines" and stops.

        With 8 dielines migrations on disk that does not identify which one is
        missing. Naming it is the entire content of the incident.
        """
        from apps.core import checks

        with override_settings(ENVIRONMENT=self._LOCAL), \
                patch.object(checks, "migration_state",
                             return_value=self._behind()):
            found = self._run()
        self.assertEqual(len(found), 1, found)
        self.assertEqual(found[0].id, checks.MIGRATION_DRIFT)
        self.assertIn("dielines.0008_alter_dielinejob_template_type",
                      found[0].msg)

    def test_an_UNCLASSIFIED_environment_is_silent_because_CI_never_migrates(
            self):
        """Measured 2026-08-22: `.github/workflows/ci.yml` contains the word
        `migrate` zero times and sets `ENVIRONMENT` zero times. CI's database
        is therefore legitimately unmigrated, and an ungated check would warn
        on every run there. A warning that fires every time is noise, and
        noise is how a real one gets missed.
        """
        from apps.core import checks

        with override_settings(ENVIRONMENT="UNCLASSIFIED"), \
                patch.object(checks, "migration_state",
                             return_value=self._behind()):
            self.assertEqual(self._run(), [])

    def test_the_gate_is_the_ENVIRONMENT_and_NOT_the_packaging_flag(self):
        """The reason this module exists at all.

        `apps/dielines/checks.py` has a migration arm that does the same job,
        and on this machine it has never once run: `check_standard_pipeline_
        activation` returns [] at its first two lines because
        STANDARD_VECTOR_PACKAGING_PIPELINE is False, before ENVIRONMENT is
        ever read. A packaging feature flag is the wrong question to ask about
        whether the schema is current. If this test ever fails, this surface
        has been quietly re-attached to that flag and is silent again.

        [The clean-up of 2026-10-04, his Q1 "remove the dormant packaging
        flow": the flag and that dielines arm left with the structure-
        confirmation flow, so there is no flag left to pin off; what stays
        pinned is that ENVIRONMENT alone gates this surface.]
        """
        from apps.core import checks

        with override_settings(ENVIRONMENT=self._LOCAL), \
                patch.object(checks, "migration_state",
                             return_value=self._behind()):
            found = self._run()
        self.assertEqual(len(found), 1, found)
        self.assertEqual(found[0].id, checks.MIGRATION_DRIFT)

    def test_an_unreadable_database_does_not_look_like_a_behind_one(self):
        """`migrate` fixes drift and is meaningless for an unreachable
        database, so a surface that collapses them advises the wrong command.
        Distinct id, and the drift id is asserted ABSENT rather than merely
        unmentioned."""
        from apps.core import checks

        with override_settings(ENVIRONMENT=self._LOCAL), \
                patch.object(checks, "migration_state",
                             return_value="unknown: connection refused"):
            found = self._run()
        self.assertEqual(len(found), 1, found)
        self.assertEqual(found[0].id, checks.MIGRATION_STATE_UNREADABLE)
        self.assertNotEqual(found[0].id, checks.MIGRATION_DRIFT)
        self.assertIn("connection refused", found[0].msg)

    def test_an_unreadable_database_is_not_SILENT_either(self):
        """Returning [] when the state could not be determined is the shape
        this tranche spent itself documenting: `git status --short` on a path
        absent from the root warns to stderr, prints nothing, exits 0, and
        reads as "clean". Silence from this check must mean exactly one thing
        — the database was read and it is current.
        """
        from apps.core import checks

        with override_settings(ENVIRONMENT=self._LOCAL), \
                patch.object(checks, "migration_state",
                             return_value="unknown: connection refused"):
            self.assertNotEqual(self._run(), [])

    def test_an_up_to_date_database_produces_nothing(self):
        from apps.core import checks

        with override_settings(ENVIRONMENT=self._LOCAL), \
                patch.object(checks, "migration_state", return_value="ok"):
            self.assertEqual(self._run(), [])

    def test_the_finding_is_a_WARNING_and_never_an_ERROR(self):
        """`migrate` skips system checks in Django 4.2
        (`requires_system_checks = []`), so an Error here would not deadlock
        the command that fixes the condition — but it WOULD stop `runserver`,
        `check` and every other checked command on the developer's machine
        over a notice. The surface exists to be read, not to stop work.
        """
        from django.core.checks import ERROR, WARNING

        from apps.core import checks

        with override_settings(ENVIRONMENT=self._LOCAL), \
                patch.object(checks, "migration_state",
                             return_value=self._behind()):
            found = self._run()
        self.assertEqual(found[0].level, WARNING)
        self.assertNotEqual(found[0].level, ERROR)

    def test_this_surface_did_not_get_wired_into_healthz_either(self):
        """§AY0(e), restated one level up. The refusal above protects
        `migration_state`; this protects the thing that now consumes it. The
        tempting edit is one line in `run_health_checks` and it would take a
        service out of rotation during exactly the rolling deploy where
        `migrate` has not run yet.
        """
        from apps.core import checks
        from apps.core.health import run_health_checks

        values = run_health_checks()
        self.assertNotIn("migrations", values)
        self.assertNotIn(checks.MIGRATION_DRIFT, str(values))

    def test_migrate_DOES_run_checks_which_is_why_an_Error_would_block_it(self):
        """The correction that an independent audit found, made into a guard.

        RENAMED. This was `..._which_is_why_Error_would_deadlock` until a
        third audit pointed out that the name asserted the very word its own
        final assertion exists to walk back. Renaming a test is what caused
        defect (3) of the first audit — a comment left pointing at a name that
        no longer existed — so every reference moves in the same commit as the
        name: this docstring, and `evidence_tests` on `ops.migration_guard`.

        This node's record shipped claiming `migrate` is opted out of system
        checks "exactly as `shell` is", on the strength of
        `requires_system_checks = []`. That attribute is set on `shell`,
        `migrate`, `check` AND `runserver` alike, so it does not decide
        whether checks RUN. The real discriminator there is whether the
        command calls `self.check()` itself, and `migrate` does, at the top of
        `handle()`, BEFORE it applies a single operation.

        Which inverts the argument for `Warning` over `Error` and makes it
        stronger: an Error here would raise `SystemCheckError` inside
        `migrate` before anything is applied, so a behind database would
        refuse to be migrated BECAUSE it is behind — the trap the original
        reasoning believed `requires_system_checks = []` had ruled out.
        Meanwhile `shell` would sail through, because `shell` is the one
        command of the four that genuinely never runs checks.

        NOT a deadlock, and the qualification is asserted below rather than
        left in prose: the call is conditional, and `--skip-checks` escapes
        it. But that flag is NOT universal, which is the third audit's find —
        it is registered at `base.py:361-366` behind
        `if self.requires_system_checks:`, so the same attribute that does not
        decide whether checks run DOES decide whether the flag to skip them
        exists. `migrate` carries it only because it re-adds the argument
        itself. `shell` and `check` reject it outright.

        Pinned against Django's source rather than described in a comment,
        because the false version WAS a comment and read exactly as
        authoritative as the true one. A Django upgrade that moves any of this
        fails here instead of silently making the record wrong again.
        """
        import inspect

        from django.core.management import load_command_class

        def calls_check(name, app="django.core"):
            # NOTE: class BODY only — inherited methods are not included. That
            # is fine for the three commands asserted below, each of which
            # defines its own handle(). It is NOT safe to extend this predicate
            # to `runserver`: the live one is
            # django.contrib.staticfiles's subclass, whose body has no
            # `self.check(` because it inherits handle() from core. It would
            # read as False and be wrong. Hence runserver is checked for the
            # ATTRIBUTE below but never through this predicate.
            src = inspect.getsource(load_command_class(app, name).__class__)
            return "self.check(" in src

        # The attribute that was cited as the discriminator, on all FOUR —
        # including the staticfiles runserver that actually runs, which does
        # not override it. This is the assertion that the cited discriminator
        # discriminates nothing.
        for name, app in (("shell", "django.core"), ("migrate", "django.core"),
                          ("check", "django.core"),
                          ("runserver", "django.contrib.staticfiles")):
            cmd = load_command_class(app, name)
            self.assertEqual(
                list(cmd.requires_system_checks), [],
                f"{name} was expected to declare requires_system_checks = []; "
                "if this changed, the reasoning recorded on the node changes")

        # The thing that ACTUALLY decides, and the asymmetry it creates.
        self.assertTrue(calls_check("migrate"),
                        "migrate no longer calls self.check() — the "
                        "Warning-not-Error argument on this node rests on it")
        self.assertTrue(calls_check("check"))
        self.assertFalse(
            calls_check("shell"),
            "shell now runs system checks — the honest scope limit recorded "
            "on ops.migration_guard would no longer be a gap")

        # And migrate checks BEFORE it migrates, which is what makes an Error
        # block the run rather than arrive as a late complaint.
        migrate_src = inspect.getsource(
            load_command_class("django.core", "migrate").__class__)
        body = migrate_src[migrate_src.index("def handle("):]
        self.assertLess(
            body.index("self.check("), body.index("connection.prepare_database"),
            "migrate's self.check() is no longer ahead of the work it guards")

        # THE ESCAPE HATCH, pinned because the record first called this an
        # outright "deadlock" and that was one word too strong. The call is
        # conditional, and `--skip-checks` is public on every command, so an
        # Error would block `manage.py migrate` — the thing the hint tells
        # people to run — but not `manage.py migrate --skip-checks`. Asserted
        # so that nobody re-derives the stronger claim from the line number
        # alone, which is exactly how the first wrong version was written.
        guard = body[:body.index("self.check(")]
        self.assertIn(
            'if not options["skip_checks"]', guard,
            "migrate's self.check() is no longer guarded by skip_checks — the "
            "record says an Error blocks the DEFAULT invocation only, and that "
            "qualification would now be wrong")

        # AND THE ESCAPE IS NOT UNIVERSAL — the third audit's find, pinned so
        # the qualification above cannot drift back into "every command has
        # --skip-checks". The flag is registered at base.py behind
        # `if self.requires_system_checks:`, which is falsy for all four of
        # these commands, so `migrate` carries it ONLY because it re-adds the
        # argument in its own add_arguments.
        def has_skip_flag(name, app="django.core"):
            parser = load_command_class(app, name).create_parser("m", name)
            return any("--skip-checks" in (a.option_strings or [])
                       for a in parser._actions)

        self.assertTrue(has_skip_flag("migrate"),
                        "migrate stopped re-adding --skip-checks itself; the "
                        "recorded escape hatch would no longer exist")
        for name in ("shell", "check"):
            self.assertFalse(
                has_skip_flag(name),
                f"{name} now offers --skip-checks — the record says the flag "
                "is NOT universal and is gated by requires_system_checks")


class ContentSecurityPolicyTests(TestCase):
    """The CSP is REPORT-ONLY, and these tests exist to keep it that way."""

    ENFORCING = "Content-Security-Policy"
    REPORT_ONLY = "Content-Security-Policy-Report-Only"

    def _run(self, content_type="text/html; charset=utf-8", preset=None):
        """Drive the middleware directly, with no URL routing in the way."""
        from django.http import HttpResponse

        from apps.core.middleware import ContentSecurityPolicyMiddleware

        def get_response(_request):
            res = HttpResponse(b"<html></html>", content_type=content_type)
            if preset:
                res[self.REPORT_ONLY] = preset
            return res

        mw = ContentSecurityPolicyMiddleware(get_response)
        return mw(None)

    def test_the_policy_is_report_only_and_never_enforcing(self):
        """The refusal, asserted (§AY0(e)).

        Enforcing CSP_POLICY would break the dashboard: 101 inline style
        attributes, 7 <style> blocks, 2 inline <script> blocks and 3 inline
        event handlers across the 20 templates Django loads. The tempting
        edit — dropping "-Report-Only" from one string — is invisible in
        review and would 500 nothing, it would silently stop the CSS from
        applying. Only a test catches that.
        """
        res = self._run()
        self.assertIn(self.REPORT_ONLY, res)
        self.assertNotIn(self.ENFORCING, res)

    def test_the_policy_never_permits_unsafe_inline_or_unsafe_eval(self):
        """A CSP with 'unsafe-inline' is a header that stops nothing.

        It would let the policy be enforced immediately, and would read to
        anyone auditing the response — or grepping for the header name — as
        though the application were protected. That converts an honest
        absence into a false positive, which is worse than no header.
        'unsafe-eval' is likewise absent and was measured to be unnecessary:
        no eval( or new Function in any of the 12 static JS files.
        """
        from apps.core.middleware import CSP_POLICY

        self.assertNotIn("unsafe-inline", CSP_POLICY)
        self.assertNotIn("unsafe-eval", CSP_POLICY)
        self.assertNotIn("*", CSP_POLICY)

    def test_blob_is_permitted_for_images_because_the_ui_measurably_needs_it(
            self):
        """static/js/staged_references.js:54 calls URL.createObjectURL(f) to
        preview staged references. Without blob: in img-src those previews
        are a violation. This is in the policy because it was measured, not
        because blob: is generally harmless — and the test names the caller
        so that if that line goes away, this widening can go with it.
        """
        from apps.core.middleware import CSP_POLICY

        img = [d for d in CSP_POLICY.split("; ") if d.startswith("img-src")]
        self.assertEqual(len(img), 1, CSP_POLICY)
        self.assertIn("blob:", img[0])

    def test_frame_ancestors_agrees_with_x_frame_options(self):
        """Two spellings of one decision — §AR2 says they will drift."""
        from django.conf import settings

        from apps.core.middleware import CSP_POLICY

        self.assertIn("frame-ancestors 'none'", CSP_POLICY)
        self.assertEqual(settings.X_FRAME_OPTIONS, "DENY")

    def test_non_html_responses_are_not_tagged(self):
        """A JSON reply or a PDF download has no document for the directives
        to govern, so tagging it is noise in every response rather than
        protection in any."""
        res = self._run(content_type="application/json")
        self.assertNotIn(self.REPORT_ONLY, res)
        self.assertNotIn(self.ENFORCING, res)

    def test_an_upstream_header_is_not_overwritten(self):
        res = self._run(preset="default-src 'none'")
        self.assertEqual(res[self.REPORT_ONLY], "default-src 'none'")

    def test_the_middleware_is_actually_installed(self):
        """The unit tests above would all pass with the middleware absent
        from MIDDLEWARE. This one drives a real request through the real
        stack, so "the class exists" cannot be mistaken for "it runs".
        """
        from apps.core.middleware import CSP_POLICY

        res = self.client.get("/accounts/login/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res[self.REPORT_ONLY], CSP_POLICY)
        self.assertNotIn(self.ENFORCING, res)

    def test_healthz_json_is_not_tagged_through_the_real_stack(self):
        res = self.client.get("/healthz")
        self.assertNotIn(self.REPORT_ONLY, res)


# ---- §BH39(a): brand_gov naming + roles — "Warm Gold" #CBA87D named by the owner's sentence, the eight measured roles the
# ---- brand's colour roles, the two seeded dark accents kept and holding no role. Data pins; nothing resolves through them yet.

import json as _json39
from pathlib import Path as _Path39

_BRAND_GOV = _Path39(__file__).resolve().parents[2] / "docs" / "brand_gov" / "colour_roles_1_0.json"   # the inner root


def _seed_palettes():
    from apps.core.management.commands import seed_bbrose as _seed
    src = _Path39(_seed.__file__).read_text(encoding="utf-8")
    return src


def test_warm_gold_is_named_in_both_canonical_systems_of_the_seed():
    src = _seed_palettes()
    assert src.count('"name": "Warm Gold"') == 2
    assert src.count('"hex": "#CBA87D"') == 2
    assert "§BH39(a)" in src and "docs/brand_gov/colour_roles_1_0.json" in src


def test_the_colour_roles_record_carries_the_eight_measured_roles_and_warm_gold_with_its_provenance():
    rec = _json39.loads(_BRAND_GOV.read_text(encoding="utf-8"))
    assert rec["schema_version"] == "brand_colour_roles/1.0"
    names = [r["role"] for r in rec["roles"]]
    assert names == ["ground_cream", "ground_gold", "ground_blush", "accent_light", "accent_blush", "accent_nude", "accent_dark", "ink"]
    gold = next(r for r in rec["roles"] if r["role"] == "ground_gold")
    assert gold["brand_swatch"]["name"] == "Warm Gold" and gold["brand_swatch"]["hex"] == "#CBA87D" == rec["warm_gold"]["hex"]
    assert rec["warm_gold"]["files"] and all(p.startswith("materials/historical AI production designs/") for p in rec["warm_gold"]["files"])
    assert "§BH39(a)" in rec["warm_gold"]["provenance"]
    assert {d["name"] for d in rec["no_role"]} == {"Deep Rose", "Cocoa Rose"}
    for r in rec["roles"]:
        if r["brand_swatch"]:
            assert r["brand_swatch"]["name"] not in {"Deep Rose", "Cocoa Rose"}      # the dark accents hold no role
    assert rec["authority"].startswith("brand_gov FIRST")


def test_seeding_folds_warm_gold_into_the_live_brand_gov_record(db):
    from django.core.management import call_command
    from apps.core.models import Brand, ColorSystem
    from apps.pipeline.services.brand_context import get_brand_hexes
    call_command("seed_bbrose", verbosity=0)
    brand = Brand.objects.get(name="BBROSE")
    systems = list(ColorSystem.objects.filter(brand=brand, status="canonical").order_by("system_id"))
    assert [cs.system_id for cs in systems] == ["CS-001", "CS-002"]
    for cs in systems:
        gold = [sw for sw in cs.palette if sw.get("name") == "Warm Gold"]
        assert len(gold) == 1 and gold[0]["hex"] == "#CBA87D" and gold[0]["role"] == "Ground" and "§BH39(a)" in gold[0]["provenance"]
    assert "#CBA87D" in get_brand_hexes(brand.id)                                    # the QA palette check now sees it
    call_command("seed_bbrose", verbosity=0)                                          # idempotent: still exactly one Warm Gold per system
    assert all(sum(1 for sw in cs.palette if sw.get("name") == "Warm Gold") == 1 for cs in ColorSystem.objects.filter(brand=brand))


# §BH52(b) SLICE 1 — HISTORY. The history pages are code, in the gated suite; every page is a GET that writes no
# governed record, serves no REFERENCE-class byte, links no control that decides or spends, and withholds a stored
# name that escapes MEDIA_ROOT. The database here is the test database the suite builds: every row is made below.
import hashlib as _hashlib52  # noqa: E402
import json as _json52  # noqa: E402
import re as _re52  # noqa: E402


def _governed_rows_digest52():
    """sha256 of every model's rows, in primary-key order — counts and in-place updates alike."""
    from django.apps import apps as _apps
    from django.db import DatabaseError, transaction
    digest = {}
    for model in _apps.get_models():
        if model._meta.label == "sessions.Session":
            continue
        try:
            with transaction.atomic():
                rows = list(model.objects.order_by("pk").values())
        except DatabaseError:
            continue
        digest[model._meta.label] = _hashlib52.sha256(
            _json52.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()
    return digest


class TierRecordIsTrackedTests(TestCase):
    """§BH55 Phase 4, his first named item — "the untracked tier record". The record that decides WHICH governed file
    may be placed in a design (4,832 rows, 1.4 MB) lived under var/, which .gitignore ignores whole: it was in no
    commit, a fresh clone had no rights record at all, and a change to it left no trace. It is tracked evidence now,
    beside the caption record §BH43(a) tracked, and every reader reads the tracked one."""

    def test_the_record_read_by_default_is_the_tracked_one_and_it_is_there(self):
        import json as _json_p4a

        from apps.dashboard import history
        with override_settings(HISTORY_TIER_RECORD=None):
            path = history.tier_record_path()
        assert path.parts[-3:] == ("design_intelligence", "tiers", "materials_tiers.jsonl"), path
        assert "var" not in path.parts, path            # not the ignored audit output
        assert path.exists(), path                      # it is in the repository, not only on this machine
        first = _json_p4a.loads(path.read_text().splitlines()[0])
        assert first["relative_path"] and first["sha256"] and first["tier"] in ("PRODUCTION", "REFERENCE")

    def test_a_record_named_in_the_settings_still_wins(self):
        # every test that supplies its own record relies on this, and so does a machine that keeps its own copy
        from apps.dashboard import history
        with override_settings(HISTORY_TIER_RECORD="/tmp/a-record-of-its-own.jsonl"):
            assert str(history.tier_record_path()) == "/tmp/a-record-of-its-own.jsonl"


class HistorySliceTests(TestCase):
    """§BH52(b): every past task reachable, read-only, from its rows."""

    FORBIDDEN_LINKS = ("/admin/", "download_spec", "vq1/decision", "concept_references", "palette/intent-confirmation",
                       "gate1-regeneration/confirm")

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._tmp52 = tempfile.TemporaryDirectory()
        root = Path(cls._tmp52.name)
        cls.media = root / "media"
        for rel, data in (("generated/c52.png", b"PNG-CONCEPT"), ("dielines/r52.png", b"PNG-RENDER"),
                          ("dielines/r52_old.png", b"PNG-REJECTED"), ("dielines/r52.ai", b"%PDF-AI"),
                          ("web_quarantine/3/page.html", b"<html><script></script></html>"),
                          ("references/ref_1.png", b"PNG-REFERENCE")):
            (cls.media / rel).parent.mkdir(parents=True, exist_ok=True)
            (cls.media / rel).write_bytes(data)
        (root / "outside.ai").write_bytes(b"OUTSIDE")
        cls.tiers = root / "materials_tiers.jsonl"
        cls.tiers.write_text(_json52.dumps({"relative_path": "materials/x.png", "tier": "PRODUCTION",
                                            "sha256": _hashlib52.sha256(b"PNG-RENDER").hexdigest()}) + "\n")
        cls._override52 = override_settings(MEDIA_ROOT=str(cls.media), HISTORY_TIER_RECORD=str(cls.tiers),
                                            EXPLORATION_STORE=str(root / "no-store"), ROUND_ARTIFACT_ROOT=root / "rounds")
        cls._override52.enable()

    @classmethod
    def tearDownClass(cls):
        cls._override52.disable()
        cls._tmp52.cleanup()
        super().tearDownClass()

    def setUp(self):
        from apps.core.models import Brand, Product
        from apps.pipeline.models import AgentLog, DesignTask, GateDecision, GeneratedImage, PackagingOutput
        from apps.dashboard import board
        self.enterContext(patch.dict(board.OWNER_FOLD, {}, clear=True))    # a test database's numbers are not his
        self.user = User.objects.create_user("viewer52", "v@bbrose.test", "pw-123456")
        brand = Brand.objects.create(name="B52", master_brief="x")
        product = Product.objects.create(brand=brand, product_id="SK-52", name="Night Oil 52", category="SK",
                                         year=2026, product_type="serum")
        self.task = DesignTask.objects.create(
            brand=brand, product=product, design_target="product_container", status="container_stage_visually_rejected",
            task_text="A dropper bottle brief whose first sixty characters say nothing at all, then: amethystine.")
        image = GeneratedImage.objects.create(task=self.task, direction_name="Dusk", prompt_used="a dusk prompt",
                                              image_file="generated/c52.png", is_approved=True,
                                              user_rejection_label="REJECTED_BY_USER — TOO_DARK")
        self.output = PackagingOutput.objects.create(
            task=self.task, approved_image=image, design_preview="dielines/r52.png",
            design_preview_ai="../outside.ai",
            spec_sheet={"container_reconstruction": {"status": "RECONSTRUCTED", "blockers": []},   # §BH50(g)(4): a legacy spec
                        "container_reconstruction_rejected_x": {
                            "codes": ["ZZ_UNIQUE_REJECTION_CODE"], "decided_by": "admin", "decided_at": "2026-07-27",
                            "rejected_output": {"design_preview": "dielines/r52_old.png"}},
                        "rejected_outputs": [{"label": "REJECTED — ref", "files": {"x": "references/ref_1.png"}}],
                        "web": {"quarantine_path": "web_quarantine/3/page.html"}})
        GateDecision.objects.create(task=self.task, gate="gate_2", decision="reject", notes="the collar reads copper",
                                    decided_by=None)
        AgentLog.objects.create(task=self.task, agent_name="ARIA", action="Composed the sheet",
                                payload={"panel": "hero"})

    def test_a_designs_record_says_itself_in_words_its_codes_one_click_under(self):
        # [the owner's answer to the UI directions of 2026-09-25, (d) "Plain words everywhere. No engine codes on
        # screen." — the record page ("Everything on record") showed each code beside its words]
        import re
        from html.parser import HTMLParser

        from apps.pipeline.models import DesignTask

        class Shown(HTMLParser):                  # what a page shows at rest: a fold's summary, never its body
            def __init__(self):
                super().__init__()
                self.depth, self.in_summary, self.out = 0, 0, []

            def handle_starttag(self, tag, attrs):
                self.depth += tag == "details"
                self.in_summary += tag == "summary"

            def handle_endtag(self, tag):
                self.depth -= tag == "details"
                self.in_summary -= tag == "summary"

            def handle_data(self, data):
                if self.depth == 0 or self.in_summary:
                    self.out.append(data)

        stopped = DesignTask.objects.create(brand=self.task.brand, product=self.task.product, status="failed",
                                            design_target="packaging", task_text="a stopped carton",
                                            error_message="Direction planning failed validation: TYPOGRAPHY_NOT_DISTINCT")
        self.client.force_login(self.user)
        for task, words in ((stopped, "their type was too alike"), (self.task, "What its review finds, read now")):
            html = self.client.get(f"/dashboard/history/tasks/{task.pk}/").content.decode()
            parser = Shown()
            parser.feed(html)
            shown = " ".join(parser.out)
            self.assertIn(words, shown)
            self.assertNotRegex(shown, r"\b[A-Z][A-Z0-9]+(?:_[A-Z0-9]{2,})+\b")          # no code shown …
            self.assertNotRegex(shown, r"\d{4}-\d\d-\d\d \d\d:\d\d|\d{4}-\d\d-\d\dT")      # … nor a machine's time
            self.assertNotIn("container_reconstruction", shown)                      # nor a record's own key
        self.assertIn("TYPOGRAPHY_NOT_DISTINCT", self.client.get(f"/dashboard/history/tasks/{stopped.pk}/").content.decode())

    def test_the_record_lists_say_their_codes_in_words(self):
        # [the owner's answer to the UI directions of 2026-09-25, (d) "Plain words everywhere. No engine codes on screen."]
        from apps.dashboard.templatetags.plain_words import plain, when
        self.client.force_login(self.user)
        concepts = self.client.get("/dashboard/history/concepts/").content.decode()
        self.assertIn("rejected by user — too dark", concepts)
        self.assertNotIn("REJECTED_BY_USER", concepts)
        self.assertEqual(plain("REJECTED — GATE1_SET_REJECTED (UNAPPROVED_REFERENCE_GROUNDING)"),
                         "REJECTED — concept set rejected (unapproved reference grounding)")
        self.assertEqual(plain("straight_tuck_end_carton"), "straight tuck end carton")
        self.assertEqual(plain("BBR-SK-201 · BBROSE · VQ-1"), "BBR-SK-201 · BBROSE · VQ-1")   # his own names stay
        # [the owner's goal of 2026-09-25, (d): a fingerprint and the engine's "GATE_2" in a record's text, said too]
        self.assertEqual(plain("draft 9b3603e17e85746c -> confirmed 59d20e35f04554fd"), "draft … -> confirmed …")
        self.assertEqual(plain("(UNCONFIRMED, hash dc9d799dea50a7441979ea9b2b505241)"), "(UNCONFIRMED, …)")
        self.assertEqual(plain("does not open GATE_2"), "does not open review")
        self.assertEqual(when("2026-09-17T08:55:11Z"), "17 September 2026, 08:55")
        self.assertEqual(when("2026-07-27"), "27 July 2026")                            # a date alone stays a date

    def _urls(self):
        return ["/dashboard/history/", "/dashboard/history/?q=amethystine", "/dashboard/find/?q=amethystine",
                f"/dashboard/history/tasks/{self.task.pk}/", "/dashboard/history/concepts/",
                "/dashboard/history/projects/", "/dashboard/history/dieline-jobs/"]

    def test_a_past_design_reads_in_a_designers_words_and_opens_the_live_one(self):
        """§BH55 Phase 3: History spoke the engine's — "Task #53", the raw target, the model's own status labels,
        "QA passed", "gate_1 · approve", each reference's stored codes, a notification's kind, a provider operation and
        "tier: PRODUCTION". It says each in the words the rest of the site uses, and every record keeps its own."""
        from apps.pipeline.models import ApiCallRecord, ConceptReference, Notification
        ConceptReference.objects.create(task=self.task, source_type="MATERIAL_LIBRARY", library_item_id="materials:x",
                                        title="a gold pattern", ownership_status="UNKNOWN",
                                        rights_status="UNVERIFIED", image_root="materials", image_path="materials/x.png")
        Notification.objects.create(task=self.task, recipient=self.user, kind="awaiting_gate_2",
                                    message="Design #1: review the design")
        ApiCallRecord.objects.create(task=self.task, provider="openai", model="gpt-image", operation="image:Dusk",
                                     image_count=1, cost_usd="0.25")
        self.client.force_login(self.user)
        html = self.client.get(f"/dashboard/history/tasks/{self.task.pk}/").content.decode()
        self.assertIn(f"Design #{self.task.pk}", html)
        self.assertNotIn("Task #", html)
        self.assertIn("Product", html)                     # its kind, in the start form's own words
        self.assertIn("Rejected at review", html)                    # its state, in the words the site uses
        self.assertIn("Quality not checked", html)                   # a check that never ran is not a failure
        self.assertIn("The design", html)                            # the decision's gate, in words
        self.assertIn("changes asked for", html)
        self.assertIn("from the materials library", html)            # the reference, in words
        self.assertIn("whose it is: unknown", html)
        self.assertIn("offered — not approved", html)
        self.assertIn("Review the design", html)                     # the notification's kind, in words
        self.assertIn("drew a concept — Dusk", html)                 # what the paid call did
        self.assertIn(f"/dashboard/designs/{self.task.pk}/", html)   # the way to the design itself
        rows = self.client.get("/dashboard/history/").content.decode()
        self.assertIn('<h1 class="h1">Designs</h1>', rows)  # [the owner's answer to the UI directions of 2026-09-25: History is C's Designs]
        self.assertNotIn("Task #", rows)
        # [the owner's goal of 2026-10-29: Designs on the chain's rounds] the old task is on its own record page, not here
        self.assertNotIn(f"/dashboard/history/tasks/{self.task.pk}/", rows)

    def test_anonymous_is_sent_to_login(self):
        for url in self._urls():
            self.assertEqual(self.client.get(url).status_code, 302, url)

    def test_every_page_reads_and_writes_no_governed_record(self):
        from django.core.files.storage import FileSystemStorage
        self.client.force_login(self.user)                  # login moves last_login: the snapshot is taken after it
        before = _governed_rows_digest52()
        media_before = sorted(str(p) for p in self.media.rglob("*"))
        tiers_before = self.tiers.read_bytes()
        with patch.object(FileSystemStorage, "_save", side_effect=AssertionError("history wrote a file")), \
                patch("tempfile.mkdtemp", side_effect=AssertionError("history made a temp dir")):
            for url in self._urls():
                self.assertEqual(self.client.get(url).status_code, 200, url)
        self.assertEqual(_governed_rows_digest52(), before)
        self.assertEqual(sorted(str(p) for p in self.media.rglob("*")), media_before)
        self.assertEqual(self.tiers.read_bytes(), tiers_before)

    def test_no_page_accepts_a_post_or_carries_a_decision_control(self):
        self.client.force_login(self.user)
        for url in self._urls():
            self.assertEqual(self.client.post(url.split("?")[0]).status_code, 405, url)
            html = self.client.get(url).content.decode()
            self.assertIsNone(_re52.search(r"<form[^>]*method=\"post\"", html, _re52.I), url)
            for link in self.FORBIDDEN_LINKS:
                self.assertNotIn(link, html, (url, link))

    def test_the_task_page_shows_its_records_and_serves_no_reference_byte(self):
        self.client.force_login(self.user)
        html = self.client.get(f"/dashboard/history/tasks/{self.task.pk}/").content.decode()
        self.assertIn('href="/files/dielines/r52.png"', html)
        # §BH55 Phase 3: the tier where a row exists, in the words the materials record's own page uses
        self.assertIn("may be placed in a design", html)
        self.assertIn('href="/files/generated/c52.png"', html)
        self.assertIn("no tier row", html)                               # and said where none does
        self.assertIn('href="/files/dielines/r52_old.png"', html)        # the rejected render beside the current one
        self.assertIn("ZZ_UNIQUE_REJECTION_CODE", html)
        self.assertIn("the collar reads copper", html)
        self.assertIn("(none recorded)", html)                            # a decision with no actor says so
        self.assertIn("&quot;panel&quot;: &quot;hero&quot;", html)       # the log's payload is drawn
        self.assertIn("WITHHELD — the stored name resolves outside media root", html)   # [2026-09-25, (d): MEDIA_ROOT, in words]
        self.assertNotIn("/files/../", html)
        self.assertIn("WITHHELD — a REFERENCE-class directory", html)
        self.assertIsNone(_re52.search(r'(href|src)="/files/(web_quarantine|references|concept_thumbs)/', html))
        media = self.client.get("/dashboard/history/").content.decode()
        self.assertIsNone(_re52.search(r'(href|src)="/files/(web_quarantine|references|concept_thumbs)/', media))

    def test_the_task_page_marks_a_stale_spec_and_shows_the_readers_verdict_and_writes_nothing(self):
        """§BH50(g)(4), re-typed §BH53(a): "A STALE SPEC NEVER SHOWS AS CURRENT." The fixture's reconstructed spec
        carries none of the twelve declared sections: the task page marks it STALE with the dates its checks predate
        and shows the Gate-2 reader's own verdict, derived at readiness-read; the project page carries the same reader
        per stage; and the read writes nothing (the no-write test covers these pages)."""
        self.client.force_login(self.user)
        html = self.client.get(f"/dashboard/history/tasks/{self.task.pk}/").content.decode()
        self.assertIn("What its review finds, read now", html)           # §BH55 Phase 3: the same reading, in words
        self.assertIn("STALE", html)
        # [the owner's answer to the UI directions of 2026-09-25, (d): the section is named in words — 'front copy', it
        # read 'front_copy' — its own key folded under "What the record says"]
        self.assertIn("readiness section &#x27;front copy&#x27; — §BH50(f)(3), 2026-09-17", html)
        self.assertIn("readiness section &#x27;front_copy&#x27;", html)
        self.assertIn("readiness section &#x27;font&#x27; — 2B-3D, 2026-07-24", html)
        self.assertIn("nothing rewritten, nothing newly blocking", html)
        from apps.ire.container_production_readiness import build_readiness
        for code in build_readiness(self.output.spec_sheet)["blocking_codes"][:3]:
            self.assertIn(code, html)
        self.output.refresh_from_db()
        self.assertNotIn("container_production_readiness/1.0", self.output.spec_sheet)      # nothing persisted
        projects = self.client.get("/dashboard/history/projects/").content.decode()
        self.assertEqual(self.client.get("/dashboard/history/projects/").status_code, 200, projects[:80])

    def test_the_record_page_says_the_makers_specification_as_production_notes_apart_from_what_refuses(self):
        """The owner's answer of 2026-09-27: the maker's printing specification is shown as a production note, never
        a blocker — on the record page in words, apart from what stands in its way, its code one click under."""
        from django.test import override_settings

        from apps.ire.container_production_readiness import build_readiness
        self.client.force_login(self.user)
        with override_settings(PRODUCTION_ICC_PROFILE_PATH=""):
            html = self.client.get(f"/dashboard/history/tasks/{self.task.pk}/").content.decode()
            verdict = build_readiness(self.output.spec_sheet)
        self.assertIn("Production notes, for the printer", html)
        self.assertIn("the print shop&#x27;s colour profile goes into the file before it prints", html)
        self.assertFalse(any(c.startswith("MISSING_OUTPUT_INTENT") for c in verdict["blocking_codes"]))
        self.assertTrue(any(c.startswith("MISSING_OUTPUT_INTENT") for c in verdict["production_notes"]))
        self.assertIn(f'{len(verdict["blocking_codes"])} thing', html)             # what stands counts no note

    def test_the_record_page_says_what_is_not_measured_yet_apart_from_what_refuses(self):
        """§BH71 (0a), the owner's goal of 2026-09-28: "Unmeasured checks … show as a warning beside Approve, never a
        block." On the record page in words, one line per kind, apart from what stands in its way — every code
        one click under."""
        from django.test import override_settings

        from apps.ire.container_production_readiness import build_readiness
        self.client.force_login(self.user)
        with override_settings(PRODUCTION_ICC_PROFILE_PATH=""):
            html = self.client.get(f"/dashboard/history/tasks/{self.task.pk}/").content.decode()
            verdict = build_readiness(self.output.spec_sheet)
        self.assertTrue(verdict["acceptance_warnings"])
        self.assertIn("Not measured yet — shown beside Approve and kept with an approval, never a reason the design "
                      "is refused", html)
        self.assertIn("whether the front copy fits its zone — not measured yet", html)
        for code in verdict["acceptance_warnings"]:
            self.assertIn(code, html)                                          # one click under
            self.assertNotIn(code, verdict["blocking_codes"])
        self.assertIn(f'{len(verdict["blocking_codes"])} thing', html)          # what stands counts no warning

    def test_the_record_page_says_the_shades_unconfirmed_arabic_apart_from_what_is_not_measured(self):
        """His answer of 2026-09-29 to the §BH71 report, (4): the record's shade drawn with an Arabic the executor wrote
        is said on the record page as words not confirmed yet — apart from the checks not measured yet, and from what
        stands in the design's way."""
        from django.test import override_settings
        code = ("CONTAINER_SHADE_ARABIC_UNCONFIRMED: the shade's Arabic 'طبيعي' was written by the executor and nobody "
                "has confirmed it — Product.shade_names")
        spec = dict(self.output.spec_sheet)
        codes = dict(spec.get("container_production_readiness_codes") or {})
        codes["content"] = list(codes.get("content") or []) + [code]
        spec["container_production_readiness_codes"] = codes
        self.output.spec_sheet = spec
        self.output.save(update_fields=["spec_sheet"])
        self.client.force_login(self.user)
        with override_settings(PRODUCTION_ICC_PROFILE_PATH=""):
            html = self.client.get(f"/dashboard/history/tasks/{self.task.pk}/").content.decode()
        self.assertIn("Not confirmed yet — words the executor wrote that you have not confirmed", html)
        self.assertIn("Arabic, written by the executor — not confirmed yet", html)
        self.assertIn("Not measured yet — shown beside Approve", html)                  # the unmeasured, still apart
        self.assertIn("CONTAINER_SHADE_ARABIC_UNCONFIRMED", html)                        # its code one click under

    def test_the_record_page_reads_his_acceptance_for_the_picture_it_names(self):
        """§BH71, after (0a): an acceptance given for an earlier picture counts for nothing, and the record page says
        so in words; the same bytes read accepted."""
        import hashlib

        from apps.ire.container_production_readiness import ACCEPTANCE_KEY
        self.client.force_login(self.user)
        spec = dict(self.output.spec_sheet)
        spec[ACCEPTANCE_KEY] = {"state": "ACCEPTED", "decided_by": "owner", "preview_sha256": "0" * 64}
        self.output.spec_sheet = spec
        self.output.save(update_fields=["spec_sheet"])
        html = self.client.get(f"/dashboard/history/tasks/{self.task.pk}/").content.decode()
        self.assertIn("given for an earlier picture, so it counts for nothing now", html)
        spec[ACCEPTANCE_KEY]["preview_sha256"] = hashlib.sha256(b"PNG-RENDER").hexdigest()
        self.output.spec_sheet = spec
        self.output.save(update_fields=["spec_sheet"])
        html = self.client.get(f"/dashboard/history/tasks/{self.task.pk}/").content.decode()
        self.assertNotIn("given for an earlier picture", html)
        self.assertIn("acceptance of the design: ACCEPTED", html)

    def test_slice_one_media_still_loads_through_the_corrected_door(self):
        """§BH54(b): slice 1's hrefs — a PRODUCTION-tiered render, an untiered concept, an untiered rejected render —
        load through the door; the two reference-folder files it never links are refused by name."""
        self.client.force_login(self.user)
        for url, data in (("/files/dielines/r52.png", b"PNG-RENDER"), ("/files/generated/c52.png", b"PNG-CONCEPT"),
                          ("/files/dielines/r52_old.png", b"PNG-REJECTED")):
            res = self.client.get(url)
            self.assertEqual((res.status_code, b"".join(res.streaming_content)), (200, data), url)
        for url in ("/files/references/ref_1.png", "/files/web_quarantine/3/page.html"):
            res = self.client.get(url)
            self.assertEqual(res.status_code, 403, url)
            self.assertTrue(res.content.decode().startswith("REFUSED_REFERENCE_FOLDER: "), url)

    def test_search_reaches_past_the_first_sixty_characters_and_into_the_records(self):
        # [the owner's goal of 2026-10-29: Designs lists the chain's rounds] the search reaches the whole brief — its
        # name, its product, its shape and material, its shades — not its first words alone
        record = _designer_round(self.user, name="Gloss 52")
        tile = f'<a class="frame" href="/dashboard/rounds/{record.pk}/">'
        self.client.force_login(self.user)
        for q in ("gloss 52", "doe-foot wand", "clear acrylic", "lip gloss"):
            html = self.client.get("/dashboard/history/", {"q": q}).content.decode()
            self.assertIn(tile, html, q)
        html = self.client.get("/dashboard/history/", {"q": "no-such-thing-52"}).content.decode()
        self.assertNotIn(tile, html)
        self.assertIn("No design matches.", html)
        for old in ({"product": str(self.task.product_id), "rejections": "1"}, {"from": "not a date"}):
            res = self.client.get("/dashboard/history/", old)                  # the old tasks' filters: left out, no fault
            self.assertEqual(res.status_code, 200, old)
            self.assertIn(tile, res.content.decode(), old)

    def test_designs_are_by_month_each_a_tile_that_opens_the_design_with_its_record_below(self):
        # [the owner's goal of 2026-10-29: Designs lists the chain's rounds] a tile opens the round; a made round's
        # faces and files are one link below
        record, made = _designer_round(self.user), _designer_round(self.user, name="A made gloss", made=True)
        self.client.force_login(self.user)
        html = self.client.get("/dashboard/history/").content.decode()
        self.assertIn(record.created_at.strftime("%B %Y"), html)                          # its month
        self.assertIn(f'<a class="frame" href="/dashboard/rounds/{record.pk}/">', html)    # the tile opens the round
        self.assertIn(f'href="/dashboard/rounds/{made.pk}/built-files/">Its faces and files</a>', html)
        self.assertIn('<span class="tag wait">', html)                                   # where it stands, as a tag
        self.assertIn(">Pick one design</span>", html)
        finished = self.client.get("/dashboard/history/", {"state": "finished"}).content.decode()
        self.assertNotIn(f'<a class="frame" href="/dashboard/rounds/{record.pk}/">', finished)   # by where it stands
        self.assertIn(f'<a class="frame" href="/dashboard/rounds/{made.pk}/">', finished)

    def test_the_systems_own_tests_are_folded_away_unless_asked_for(self):
        # his fold (a691f56): "They are tests, not my work" — the old tasks' fold; [the owner's goal of 2026-10-29] on the
        # rounds, a retired round is not a design here, asked for or not (the round list says what it was)
        from uuid import uuid4

        from apps.pipeline.models import Round
        retired = Round.objects.create(slug="retired-52", request_key=str(uuid4()), created_by=self.user,
                                       product_brief={"name": "A retired gloss"}, state="failed")
        self.client.force_login(self.user)
        for asked in ({}, {"tests": "1"}):
            html = self.client.get("/dashboard/history/", asked).content.decode()
            self.assertNotIn(f'href="/dashboard/rounds/{retired.pk}/"', html, asked)
            self.assertNotIn("Show the system's own tests", html)

    def test_find_reaches_designs_products_and_colours_and_starts_a_design_with_the_words(self):
        from apps.core.models import ColorSystem
        ColorSystem.objects.create(brand=self.task.brand, name="Blush Core", system_id="CS-001", status="canonical",
                                   palette=[{"name": "Amethyst Rose", "role": "Accent", "hex": "#8B3A52"}],
                                   image_generation_context="x")
        self.client.force_login(self.user)
        html = self.client.get("/dashboard/find/", {"q": "amethys"}).content.decode()
        self.assertIn(f'href="/dashboard/designs/{self.task.pk}/"', html)                 # by its brief, on record
        self.assertIn("Amethyst Rose", html)                                             # a colour, by its name
        self.assertIn('href="/dashboard/new/?brief=amethys"', html)
        from django.contrib.auth.models import Group                  # New design starts a paid round: a role opens it
        self.user.groups.add(Group.objects.get_or_create(name="Designer")[0])
        start = self.client.get("/dashboard/new/", {"brief": "amethys"}).content.decode()   # [the designer flow of 2026-10-27]
        self.assertRegex(start, r'<textarea name="bar"[^>]*>\s*amethys</textarea>')         # the words already in
        self.assertIn("SK-52", self.client.get("/dashboard/find/", {"q": "Night Oil"}).content.decode())
        self.assertIn('action="/dashboard/find/"', self.client.get("/dashboard/").content.decode())   # the one box
        self.assertIn("Type in the search box above", self.client.get("/dashboard/find/").content.decode())

    def test_history_is_reached_by_clicking_from_the_dashboard(self):
        self.client.force_login(self.user)
        self.assertIn('href="/dashboard/history/"', self.client.get("/dashboard/").content.decode())


# §BH52(d) — THE INTERFACE IS CODE AND IS GATED; EXPLORATION INSIDE IT IS NOT. Both halves on slice 1.
# HALF ONE is shown by behaviour, never by reading source: the gate tool runs apps, every history and exploration
# view is a module under apps/, this file is in the declared suite manifest, and the manifest's digest is the pinned
# extent. HALF TWO: seeing explorations in history changes nothing the gate reads — no governed row, no governed file,
# no tracked file, no brain source, no media byte, no store byte — and an exploration's record claims no state.
# NOT CLAIMED HERE, owed to slice 2: the acceptance direction of the §BH51(a) seam (his identity, the time and the
# sha256 of what he accepted), and the refusal of a REFERENCE asset placed in an exploration — slice 1 composes nothing.
import inspect as _inspect52  # noqa: E402
import os as _os52  # noqa: E402
import subprocess as _subprocess52  # noqa: E402


class ExplorationSeamTests(TestCase):
    """§BH52(d): the interface is gated like all code; exploration inside it is not."""

    STATUS = "EXPLORATION — never verified, never accepted, never evidence"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._tmpx = tempfile.TemporaryDirectory()
        root = Path(cls._tmpx.name)
        cls.media = root / "media"
        cls.media.mkdir()
        cls.store = root / "explorations"
        study = cls.store / "seam-study"
        study.mkdir(parents=True)
        cls.study = study
        cls._overridex = override_settings(MEDIA_ROOT=str(cls.media), EXPLORATION_STORE=str(cls.store),
                                           OWNER_ACCOUNT="owner52")           # §BH54(i)
        cls._overridex.enable()

    @classmethod
    def tearDownClass(cls):
        cls._overridex.disable()
        cls._tmpx.cleanup()
        super().tearDownClass()

    def setUp(self):
        from apps.core.models import Brand
        from apps.pipeline.models import DesignTask
        self.user = User.objects.create_user("owner52", "o@bbrose.test", "pw-123456")      # §BH54(i): the owner, no role, no group
        self.other = User.objects.create_user("plain52", "p@bbrose.test", "pw-123456")     # another signed-in account
        self.super_ = User.objects.create_superuser("runtest52", "r@bbrose.test", "pw-123456")   # a superuser, not the owner
        brand = Brand.objects.create(name="BX", master_brief="x")
        self.task = DesignTask.objects.create(brand=brand, task_text="a container task", design_target="product_container")
        pictures = {
            "T0": {"what_changed": "no change — today's render", "task": self.task.pk},
            "W1": {"what_changed": "ROSE_GOLD_BASE → ground_gold", "task": self.task.pk,
                   "codes_on_the_drawing": ["CONTAINER_BACK_PANEL_COPY_EXCEEDS_PANEL"]},   # blocks acceptance, not a look
            "BAD": {"what_changed": "a record that claims", "task": self.task.pk, "accepted": True},
        }
        index = {"status": self.STATUS, "made_at": "2026-09-17T00:00:00Z", "drawn_from_head": "abc1234",
                 "pictures": [{"picture": k} for k in pictures]}
        (self.study / "index.json").write_text(_json52.dumps(index))
        for name, body in pictures.items():
            (self.study / f"{name}.json").write_text(_json52.dumps(dict(body, status=self.STATUS)))
            (self.study / f"{name}.png").write_bytes(b"\x89PNG\r\n\x1a\n" + name.encode())

    def _urls(self):
        return ["/dashboard/history/explorations/", "/dashboard/history/explorations/seam-study/",
                "/dashboard/history/explorations/seam-study/T0.png", "/dashboard/history/explorations/seam-study/W1.png",
                f"/dashboard/history/tasks/{self.task.pk}/", "/dashboard/history/"]

    # ---------------------------------------------------------------------------------------------- HALF ONE
    def test_half_one_the_interface_is_code_the_gate_runs(self):
        import importlib.util
        from django.conf import settings
        from django.urls import resolve
        from apps.pipeline.services.palette_powder_protocol import EXTENT_DIGESTS
        base = Path(settings.BASE_DIR).resolve()
        spec = importlib.util.spec_from_file_location("tier2_gate_bh52", base / "tools" / "tier2_gate.py")
        gate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gate)
        self.assertIn("apps", gate.PYTEST)                                       # TIER_2 runs the apps tree
        for url in self._urls() + ["/dashboard/history/concepts/", "/dashboard/history/projects/",
                                   "/dashboard/history/dieline-jobs/"]:
            view = _inspect52.unwrap(resolve(url.split("?")[0]).func)
            self.assertTrue(Path(_inspect52.getfile(view)).resolve().is_relative_to(base / "apps"), url)
        declared = _json52.loads(Path(gate.MANIFEST).read_text(encoding="utf-8"))["files"]
        self.assertIn(_os52.path.relpath(Path(__file__).resolve(), base), declared)   # this test is in the extent
        self.assertEqual(gate.manifest_digest(), EXTENT_DIGESTS["suite_file_manifest"])

    # ---------------------------------------------------------------------------------------------- HALF TWO
    def _governed_files(self):
        from django.conf import settings
        base = Path(settings.BASE_DIR).resolve()
        outer = base.parent
        paths = [outer / "OWNER_BLOCKER_CLEARANCE.md", outer / "OWNER_REVIEW_QUEUE.md",
                 base / "docs/roadmap/palt_m6/record_gate_ledger.jsonl",
                 base / "docs/roadmap/palt_m6/suite_file_manifest.json",
                 base / "docs/roadmap/palt_m6/record_digest_manifest.json",
                 base / "docs/roadmap/palt_m7/ai_emission/m7_ai_emission_record.json",
                 base / "docs/visual_quality/vq1/vq1_human_structural_review.json",
                 base / "docs/roadmap/acceptance/product_container_acceptance_rejection.json",
                 base / "docs/brand_gov/colour_roles_1_0.json",
                 base / "apps/ire/container_font_owner_grant.py", base / "apps/ire/materials_owner_grant.py",
                 outer / "var/design_intelligence/audits/dip0/tiers/materials_tiers.jsonl"]
        digest = {str(p): (_hashlib52.sha256(p.read_bytes()).hexdigest() if p.is_file() else None) for p in paths}
        import importlib.util
        spec = importlib.util.spec_from_file_location("brain_sources_bh52", outer / "bbrose_design_os" / "tools" / "brain" / "sources.py")
        if spec and Path(spec.origin).is_file():
            brain = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(brain)
            digest["brain sources"] = _hashlib52.sha256(
                _json52.dumps(brain.current_source_hashes(), sort_keys=True).encode()).hexdigest()
        digest["tracked tree"] = _subprocess52.run(["git", "status", "--porcelain", "--untracked-files=no"],
                                                   cwd=str(outer), capture_output=True, text=True).stdout
        return digest

    def _store_digest(self):
        return {str(p): _hashlib52.sha256(p.read_bytes()).hexdigest() for p in sorted(self.store.rglob("*")) if p.is_file()}

    def test_half_two_seeing_explorations_writes_nothing_the_gate_reads(self):
        from django.core.files.storage import FileSystemStorage
        from apps.dashboard import explorations
        self.client.force_login(self.user)                                       # login moves last_login: snapshot after
        rows, files, store = _governed_rows_digest52(), self._governed_files(), self._store_digest()
        media = sorted(str(p) for p in self.media.rglob("*"))
        with patch.object(FileSystemStorage, "_save", side_effect=AssertionError("an exploration wrote media")), \
                patch("tempfile.mkdtemp", side_effect=AssertionError("an exploration made a temp dir")):
            for url in self._urls():
                self.assertEqual(self.client.get(url).status_code, 200, url)
        self.assertEqual(_governed_rows_digest52(), rows)
        self.assertEqual(self._governed_files(), files)
        self.assertEqual(self._store_digest(), store)
        self.assertEqual(sorted(str(p) for p in self.media.rglob("*")), media)
        self.assertTrue(explorations.store_is_outside_governed_roots())
        from django.conf import settings
        base = Path(settings.BASE_DIR).resolve()
        for root in (base, base.parent, Path(settings.MEDIA_ROOT).resolve(), base / "var", base.parent / "var",
                     Path.home() / ".claude"):
            self.assertFalse(self.store.resolve().is_relative_to(root), root)

    def test_half_two_an_exploration_claims_no_state_and_a_claim_is_refused_by_name(self):
        from apps.dashboard import explorations
        record = _json52.loads((self.study / "W1.json").read_text())
        self.assertEqual(record["status"], self.STATUS)
        self.assertEqual(explorations.claims(record), "")

        def keys(v):
            if isinstance(v, dict):
                for k, x in v.items():
                    yield str(k).lower()
                    yield from keys(x)
            elif isinstance(v, list):
                for x in v:
                    yield from keys(x)
        found = set(keys(record))
        self.assertFalse(found & explorations.CLAIM_KEYS)
        self.assertFalse({k for k in found if k.startswith(("verif", "accept", "approv"))})
        self.assertIn("REFUSED", explorations.claims(dict(record, verification="PASSED")))
        self.assertIn("REFUSED", explorations.claims(dict(record, state="VERIFIED_FOR_PRODUCTION")))
        self.assertIn("REFUSED", explorations.claims(dict(record, status="ACCEPTED")))
        self.client.force_login(self.user)
        page = self.client.get("/dashboard/history/explorations/seam-study/").content.decode()
        self.assertIn("REFUSED — the record carries a key that claims a state: accepted", page)
        self.assertEqual(self.client.get("/dashboard/history/explorations/seam-study/BAD.png").status_code, 404)

    def test_half_two_an_exploration_is_seen_by_the_owner_alone_labelled_and_never_among_outputs(self):
        """§BH52(d) as narrowed by §BH54(i): the OWNER's login sees an exploration, labelled, never among outputs."""
        self.client.force_login(self.user)
        page = self.client.get("/dashboard/history/explorations/seam-study/").content.decode()
        self.assertIn(self.STATUS, page)
        self.assertIn('src="/dashboard/history/explorations/seam-study/W1.png"', page)   # blocking codes: still seen
        task = self.client.get(f"/dashboard/history/tasks/{self.task.pk}/").content.decode()
        self.assertIn("Explorations — not outputs", task)
        outputs = task.split('id="outputs"')[1].split('id="decisions"')[0]
        self.assertNotIn("/dashboard/history/explorations/", outputs)
        for url in self._urls():
            if url.endswith(".png"):
                self.assertEqual(self.client.post(url).status_code, 405, url)
                continue
            self.assertEqual(self.client.post(url).status_code, 405, url)
            html = self.client.get(url).content.decode()
            self.assertIsNone(_re52.search(r"<form[^>]*method=\"post\"", html, _re52.I), url)
            for link in HistorySliceTests.FORBIDDEN_LINKS:
                self.assertNotIn(link, html, (url, link))
        self.client.logout()
        for url in self._urls():
            self.assertEqual(self.client.get(url).status_code, 302, url)

    def test_half_two_explorations_are_the_owners_and_another_account_is_refused_by_name(self):
        """§BH54(i): "EXPLORATIONS ARE MINE. Served to the owner account only; any other signed-in account is refused by
        name. A test proves both." The owner (no role, no group) is served; another signed-in account — and a
        superuser that is not the owner — is refused by name with the code, before any picture byte is read; the task
        page shows that account the refusal and no picture; an unset OWNER_ACCOUNT serves nobody and says so; and a
        refused read writes nothing the gate reads."""
        from django.core.files.storage import FileSystemStorage
        pictures = ["/dashboard/history/explorations/seam-study/T0.png", "/dashboard/history/explorations/seam-study/W1.png"]
        pages = ["/dashboard/history/explorations/", "/dashboard/history/explorations/seam-study/"]
        self.client.force_login(self.user)                                      # the owner
        for url in pages + pictures:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.assertEqual(b"".join(self.client.get(pictures[0]).streaming_content), b"\x89PNG\r\n\x1a\nT0")
        for account in (self.other, self.super_):
            self.client.force_login(account)                                     # login moves last_login: snapshot after
            rows, files, store = _governed_rows_digest52(), self._governed_files(), self._store_digest()
            with patch.object(FileSystemStorage, "_save", side_effect=AssertionError("a refusal wrote media")), \
                    patch("builtins.open", side_effect=AssertionError("a refused picture was opened")) as opened:
                for url in pages + pictures:
                    res = self.client.get(url)
                    self.assertEqual(res.status_code, 403, (account.username, url))
                    body = res.content.decode()
                    self.assertTrue(body.startswith("EXPLORATIONS_OWNER_ONLY: REFUSED"), body)
                    self.assertIn(account.username, body)
                    self.assertNotIn(b"PNG", res.content)
                self.assertFalse(opened.called)
            task = self.client.get(f"/dashboard/history/tasks/{self.task.pk}/")
            self.assertEqual(task.status_code, 200)
            html = task.content.decode()
            self.assertIn("EXPLORATIONS_OWNER_ONLY", html)
            self.assertIn(account.username, html)
            self.assertNotIn("/dashboard/history/explorations/seam-study/", html)
            self.assertEqual((_governed_rows_digest52(), self._governed_files(), self._store_digest()),
                             (rows, files, store), account.username)      # a refusal writes nothing the gate reads
        with override_settings(OWNER_ACCOUNT=""):                                # fail-closed control
            self.client.force_login(self.user)
            res = self.client.get(pages[0])
            self.assertEqual(res.status_code, 403)
            self.assertTrue(res.content.decode().startswith("EXPLORATIONS_OWNER_UNSET: REFUSED"))
        self.client.logout()
        for url in pages + pictures:
            self.assertEqual(self.client.get(url).status_code, 302, url)


def _design_page_as_shown(client, task_id) -> str:
    """A design's page as its browser ends up showing it: [his last goal before the pitch, 2026-10-16, Step 1 (6): "The
    design page loads with the drawing visible fast"] its Adjust panel's controls and the library's tries arrive after
    the page (``dashboard:design_adjust``), and static/js/adjust.js puts them in place — as this does."""
    import re as _re
    html = client.get(f"/dashboard/designs/{task_id}/").content.decode()
    if 'id="adjust" aria-labelledby="adjust-h" data-src="' not in html:
        return html
    data = client.get(f"/dashboard/designs/{task_id}/adjust/").json()
    html = _re.sub(r'<section class="adjust" id="adjust"[^>]*data-src="[^"]*">.*?</section>', lambda m: data["adjust"],
                   html, count=1, flags=_re.S)
    return _re.sub(r'<aside class="lib" id="library-panel".*?</aside>', lambda m: data["library"], html, count=1,
                   flags=_re.S)


def _design_page_data(response) -> dict:
    """The data a design's page hands its scripts (templates/dashboard/design.html, json_script "design-page")."""
    import json as _json
    import re as _re
    found = _re.search(r'<script id="design-page" type="application/json">(.*?)</script>', response.content.decode(),
                       _re.S)
    return _json.loads(found.group(1)) if found else {}


def _designer_round(user, state="awaiting_pick", name="Lip gloss — product and counter stand", made=False, **brief):
    """A round of the designer flow (the chain) as its worker leaves it — Home, Designs and the Library read rounds since
    the owner's goal of 2026-10-29. ``made``: its pick recorded and Make my files done (files.zip on its files build)."""
    from uuid import uuid4

    from apps.pipeline.models import Round, RoundMaster
    from apps.pipeline.services import round_designer, round_files_gate
    record = Round.objects.create(
        slug="fixture-%s" % uuid4().hex[:10], request_key=str(uuid4()), created_by=user, budget_usd=10,
        product_brief=dict(round_designer.gloss_brief(), flow=round_designer.DESIGNER_FLOW, name=name, **brief),
        state="complete" if made else state, current_step="pick" if made or state != "awaiting_board_pick" else "board_pick")
    if made:
        # a build whose steps are all done; read-only on its page as a build from before the owner gate is, so the
        # page needs no die record in the fixture's folder
        steps = {name: {"state": "complete"} for name in round_files_gate.V1_STEPS}
        RoundMaster.objects.create(round=record, state="complete", current_step="files", budget_usd=10, steps=steps,
                                   inputs={"schema": round_files_gate.FILES_SCHEMA, "picture_sha256": "0" * 64},
                                   publication={"download": "files.zip", "report": "README.md",
                                                "files": {"files.zip": "0" * 64}})
    return record


class DesignAddressTests(TestCase):
    """§BH55 Phase 3 — a design has its own address: /dashboard/designs/<id>/ opens it; every row of the list links to
    its design; the home opens no one's design; someone not signed in is asked to sign in first."""

    def setUp(self):
        from django.contrib.auth.models import Group

        from apps.core.models import Brand
        from apps.pipeline.models import DesignTask
        from apps.pipeline.permissions import ROLE_DESIGNER
        self.user = User.objects.create_user("designer-p3a", "d@example.com", None)
        self.user.groups.add(Group.objects.get_or_create(name=ROLE_DESIGNER)[0])
        self.brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.other = Brand.objects.create(name="Second", master_brief="y")
        self.task = DesignTask.objects.create(brand=self.brand, task_text="a carton for the night oil",
                                              status="awaiting_gate_1")
        self.elsewhere = DesignTask.objects.create(brand=self.other, task_text="a jar", status="completed")

    def test_a_design_opens_at_its_own_address_and_the_home_opens_none(self):
        self.client.force_login(self.user)
        res = self.client.get(f"/dashboard/designs/{self.task.pk}/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(_design_page_data(res)["task_id"], self.task.pk)  # [the owner's answer to the UI directions of 2026-09-25: C's design page hands its design over as data]
        self.assertIsNone(_design_page_data(self.client.get("/dashboard/new/classic/"))["task_id"])  # [the owner's answer to the UI directions of 2026-09-25: C's start page replaced the old single page]

    def test_every_row_of_the_list_is_a_link_to_its_design(self):
        # [the owner's goal of 2026-10-29: Home switched to the chain] each card of the board is a round, a link to its
        # own page; the old task keeps its address, off the board
        record = _designer_round(self.user)
        self.client.force_login(self.user)
        html = self.client.get("/dashboard/").content.decode()  # [the owner's answer to the UI directions of 2026-09-25: C's start page replaced the old single page]
        board = html.partition('<main id="main"')[2]               # the board itself, below the one top bar
        self.assertIn(f'<a class="nm" href="/dashboard/rounds/{record.pk}/"', board)      # each card of the board
        self.assertNotIn(f'href="/dashboard/designs/{self.task.pk}/"', board)

    def test_a_design_of_another_brand_opens_with_its_brand(self):
        self.client.force_login(self.user)
        res = self.client.get(f"/dashboard/designs/{self.elsewhere.pk}/")
        self.assertEqual(_design_page_data(res)["brand_id"], self.other.pk)  # [the owner's answer to the UI directions of 2026-09-25: C's design page hands its design over as data]
        self.assertEqual(self.client.session["brand_id"], self.other.pk)            # its brand becomes the active one

    def test_an_unknown_design_is_not_found_and_someone_signed_out_signs_in_first(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get("/dashboard/designs/999999/").status_code, 404)
        self.client.logout()
        res = self.client.get(f"/dashboard/designs/{self.task.pk}/")
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res["Location"], f"/accounts/login/?next=/dashboard/designs/{self.task.pk}/")


class FrontDoorTests(TestCase):
    """§BH55 Phase 3 — the front door: the home's center asks, in a designer's words, what they are designing, what it
    should be and for which product, and starts it; the list is "Your designs", each row saying where its design
    stands, in the one map of words (apps/dashboard/words.py) the design's own header reads too."""

    def setUp(self):
        from django.contrib.auth.models import Group

        from apps.core.models import Brand
        from apps.pipeline.models import DesignTask
        from apps.pipeline.permissions import ROLE_DESIGNER
        self.user = User.objects.create_user("designer-p3b", "d@example.com", None)
        self.user.groups.add(Group.objects.get_or_create(name=ROLE_DESIGNER)[0])
        brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.task = DesignTask.objects.create(brand=brand, task_text="a carton", status="awaiting_gate_1")
        self.client.force_login(self.user)

    def test_the_home_asks_what_to_design_in_a_designers_words(self):
        html = self.client.get("/dashboard/new/classic/").content.decode()  # [the owner's answer to the UI directions of 2026-09-25: the home is the board; the start form is at New design]
        for words in ("Start a new design", "What are you designing?", "Describe it", "For which product?",
                      ">Start the design</button>", "New design"):  # [the owner's answer to the UI directions of 2026-09-25: C's start page replaced the old single page]
            self.assertIn(words, html)
        for engine in ("Give ARIA a task", "Start Pipeline", "Select a task or start a new pipeline",
                       "BRAND INTELLIGENCE"):
            self.assertNotIn(engine, html)

    def test_each_row_says_where_its_design_stands(self):
        from apps.dashboard.words import STATUS_WORDS
        from apps.pipeline.models import TASK_STATUS
        self.assertEqual(set(STATUS_WORDS), {k for k, _ in TASK_STATUS})          # every state has its words
        _designer_round(self.user, state="awaiting_board_pick")       # [the owner's goal of 2026-10-29: Home on the rounds]
        html = self.client.get("/dashboard/").content.decode()  # [the owner's answer to the UI directions of 2026-09-25: C's start page replaced the old single page]
        self.assertIn(">Pick one mood board <svg", html)                               # each card says it, on the board
        self.assertIn('id="status-words"', self.client.get("/dashboard/new/classic/").content.decode())   # the same map, handed over

    def test_the_home_shows_no_template_comment_as_text(self):
        # §BH55 Phase 3 p3-walk: a {# #} comment holds one line; one written over three showed on the home as text
        html = self.client.get("/dashboard/").content.decode()
        self.assertNotIn("{#", html)
        self.assertNotIn("#}", html)

    def test_a_finished_design_starts_a_new_one_filled_in(self):
        # §BH55 Phase 3 p3-library: the Library's "Start from this design" spent on one click, made a packaging task
        # whatever the design was, and ran none of the create door's checks; it now opens this page filled in
        from apps.core.models import Product
        from apps.pipeline.models import DesignTask, GeneratedImage, PackagingOutput
        product = Product.objects.create(brand=self.task.brand, product_id="BBR-P3D-1", name="Night Oil",
                                         category="CO", year=2026)
        done = DesignTask.objects.create(brand=self.task.brand, product=product, task_text="A poster for the night oil",
                                         design_target="marketing_material", status="completed")
        concept = GeneratedImage.objects.create(task=done, direction_name="Nocturne", prompt_used="p")
        out = PackagingOutput.objects.create(task=done, approved_image=concept, spec_sheet={}, is_final_approved=True)
        html = self.client.get(f"/dashboard/new/classic/?from={out.pk}").content.decode()  # [the owner's answer to the UI directions of 2026-09-25: the home is the board; the start form is at New design]
        self.assertIn('id="start-from"', html)
        self.assertIn(">A poster for the night oil</textarea>", html)
        self.assertIn(f'<option value="{product.pk}" selected>', html)
        self.assertRegex(html, r'class="target-chip[^"]*\bactive\b[^"]*"[^>]*data-target="marketing_material"')  # [the owner's answer to the UI directions of 2026-09-25: C's start page replaced the old single page]
        for missing in (f"/dashboard/new/classic/?from={out.pk + 1000}", "/dashboard/new/classic/?from=x"):   # nothing finished: nothing filled in
            plain = self.client.get(missing).content.decode()
            self.assertNotIn('id="start-from"', plain)
            self.assertIn('anything it must say…"></textarea>', plain)
        out.is_final_approved = False                                                # not finished: not offered
        out.save()
        self.assertNotIn('id="start-from"', self.client.get(f"/dashboard/new/classic/?from={out.pk}").content.decode())

    def test_a_designs_status_carries_its_target_and_the_servers_own_redraw_limit(self):
        # §BH55 Phase 3 p3-steps: the step line reads the target; the page counts redraws from the server's own limit
        from django.conf import settings
        data = self.client.get(f"/api/tasks/{self.task.pk}/status/").json()
        self.assertEqual(data["design_target"], self.task.design_target)
        self.assertEqual(data["image_rerun_cap"], settings.MAX_REVISION_PASSES)


class BrandLibraryTests(TestCase):
    """§BH55 Phase 3 p3-brand — the brand's own library, read-only: its colours and the part each plays, its type and its
    faces, its mark and what a design is told about it (/dashboard/brand/); the house's past designs, described and
    never pictured (/dashboard/brand/references/) — read from the records that govern them (apps/dashboard/brand_library.py)."""

    def setUp(self):
        from django.contrib.auth.models import Group

        from apps.core.models import AestheticLanguage, Brand, ColorSystem, DesignReference
        from apps.pipeline.permissions import ROLE_DESIGNER
        self.user = User.objects.create_user("designer-p3d2", "d2@example.com", None)
        self.user.groups.add(Group.objects.get_or_create(name=ROLE_DESIGNER)[0])
        brand = Brand.objects.create(name="BBROSE", master_brief="soft luxury for the night", what_we_are_not="loud",
                                     positioning="a quiet house")
        ColorSystem.objects.create(brand=brand, name="Blush Core", system_id="CS-001",
                                   image_generation_context="soft blush light",
                                   palette=[{"name": "Blush", "hex": "#F2C4CE", "role": "Primary", "pantone": "698 C"},
                                            {"name": "Rose Gold", "hex": "Metallic 10122 C", "role": "Accent"}])
        AestheticLanguage.objects.create(brand=brand, name="Soft Luxury", aesthetic_id="AL-001",
                                         core_description="quiet, warm", prompt_seed_product="soft window light",
                                         prompt_seed_campaign="a campaign seed no design reads")
        DesignReference.objects.create(name="REF-GOLD", image_path="references/ref_REF-GOLD.png",
                                       product_type="concealer", tags=["gold foil"], summary="a gold foil carton",
                                       anatomy={"finishes": ["gold foil"], "palette_hex": ["#E8C4A8"],
                                                "typography": {"weights": ["Bold", "Light"]}})
        self.client.force_login(self.user)

    def test_the_brand_page_shows_its_colours_their_parts_its_type_and_its_mark_in_words(self):
        from django.utils.html import escape

        from apps.dashboard.brand_library import COLOUR_ROLE_WORDS, TYPE_ROLE_WORDS
        html = self.client.get("/dashboard/brand/").content.decode()
        for words in ("Blush Core", "#F2C4CE", "Pantone 698 C", "no brand colour", "Granted for production",
                      "The text itself, exactly as a design is given it", "On record, but given to no design",
                      "a campaign seed no design reads", "a quiet house",
                      *COLOUR_ROLE_WORDS.values(), *TYPE_ROLE_WORDS.values()):
            self.assertIn(escape(words), html)
        self.assertIn("Metallic 10122 C — a metallic ink, shown without a screen colour", html)   # no guessed colour
        self.assertIn('<img src="/dashboard/brand/mark.png"', html)
        self.assertIn("extracted from the approved artwork, confirmed by the owner", html)   # each part's provenance
        for engine in ("VERIFIED_FOR_PRODUCTION", "SURFACE_FALLBACK", "BRAND_GOV", "REFUSED"):
            self.assertNotIn(engine, html)

    def test_the_brand_page_names_its_systems_without_their_record_ids(self):
        # [the owner's answer to the UI directions of 2026-09-25, (d) "Plain words everywhere. No engine codes on screen."]
        import re
        html = self.client.get("/dashboard/brand/").content.decode()
        shown = re.sub(r"<[^>]+>", " ", re.sub(r"<details.*?</details>", "", html, flags=re.S))
        self.assertIn("Blush Core", shown)
        for rid in ("CS-001", "AL-001"):
            self.assertNotIn(rid, shown, rid)

    def test_a_face_is_shown_by_a_specimen_drawn_on_the_server_never_by_its_file(self):
        from apps.ire import font_roles
        stem = font_roles.CHAINS["body"][0]                                  # the running text's first face
        res = self.client.get(f"/dashboard/brand/faces/{stem}.png")
        self.assertEqual((res.status_code, res["Content-Type"]), (200, "image/png"))
        self.assertTrue(res.content.startswith(b"\x89PNG"))
        self.assertEqual(self.client.get("/dashboard/brand/faces/NoSuchFace.png").status_code, 404)
        html = self.client.get("/dashboard/brand/").content.decode()
        self.assertNotIn(".ttf", html)
        self.assertNotIn("static/fonts", html)

    def test_the_mark_is_shown_in_the_product_ink_never_the_guidelines_cyan(self):
        import io

        from PIL import Image
        res = self.client.get("/dashboard/brand/mark.png")
        self.assertEqual(res.status_code, 200)
        im = Image.open(io.BytesIO(res.content))
        self.assertEqual(im.mode, "RGB")                                     # opaque: its record prohibits transparency
        colours = {c for _, c in im.getcolors(1 << 22)}
        self.assertIn((0x50, 0x25, 0x25), colours)                           # the product ink
        self.assertFalse(any(b > 200 and g > 180 and r < 150 for r, g, b in colours))   # no guideline cyan anywhere

    def test_house_references_are_described_never_pictured(self):
        html = self.client.get("/dashboard/brand/references/").content.decode()
        for words in ("REF-GOLD", "a gold foil carton", "concealer", "weights: Bold, Light", "#E8C4A8",
                      "reference files are never served"):
            self.assertIn(words, html)
        self.assertNotIn("<img", html)
        self.assertNotIn("ref_REF-GOLD.png", html)
        self.assertIn("REF-GOLD", self.client.get("/dashboard/brand/references/?q=foil").content.decode())
        self.assertNotIn("REF-GOLD", self.client.get("/dashboard/brand/references/?q=zzzz").content.decode())

    def test_someone_signed_out_signs_in_first(self):
        self.client.logout()
        for url in ("/dashboard/brand/", "/dashboard/brand/references/", "/dashboard/brand/mark.png",
                    "/dashboard/brand/faces/Poppins-Regular.png"):
            res = self.client.get(url)
            self.assertEqual(res.status_code, 302, url)
            self.assertIn("login", res["Location"])


class MaterialsLibraryTests(TestCase):
    """§BH55 Phase 3 p3-materials — the governed materials, read-only (/dashboard/materials/): each file with whether it
    may be placed, its grant and credit, what it shows and its measured colours, searchable by words and by colour — read
    from the tier record and the caption record, never the brain; a picture drawn only for a placeable file whose own bytes
    carry no other tier (§BH54(b)), a reference never pictured (§BH53(b))."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        import hashlib
        import io
        import json

        from PIL import Image
        cls._tmpd = tempfile.TemporaryDirectory()
        root = Path(cls._tmpd.name)

        def picture(rel, colour):
            buf = io.BytesIO()
            Image.new("RGB", (40, 30), colour).save(buf, format="PNG")
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_bytes(buf.getvalue())
            return hashlib.sha256(buf.getvalue()).hexdigest()

        cls.pic = picture("materials/own/pic.png", (203, 168, 125))
        cls.look = picture("materials/ref/look.png", (0, 0, 255))
        cls.twin = picture("materials/both/twin.png", (10, 200, 10))
        (root / "materials/ref/twin.png").write_bytes((root / "materials/both/twin.png").read_bytes())
        own = {"tier": "PRODUCTION", "tier_source": "OWNER_GRANT", "condition": "", "granted_by": "BBrose",
               "granted_at": "2026-09-08", "terms_class": "OWNER_DECLARATION",
               "evidence": "docs/design_intelligence/dip0a/own_work_declaration_bh39.json sha256:abc"}
        ref = {"tier": "REFERENCE", "tier_source": "MACHINE", "condition": "", "granted_by": "", "granted_at": "",
               "evidence": ""}
        rows = [dict(own, relative_path="materials/own/pic.png", sha256=cls.pic),
                dict(own, relative_path="materials/free/pack.jpg", sha256="f" * 64, terms_class="ATTRIBUTION-REQUIRED",
                     condition='<a href="https://example.test">x</a> | "Designed by macrovector / Freepik"'),
                dict(ref, relative_path="materials/ref/look.png", sha256=cls.look),
                dict(own, relative_path="materials/both/twin.png", sha256=cls.twin),
                dict(ref, relative_path="materials/ref/twin.png", sha256=cls.twin)]
        (root / "tiers.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        caps = [{"sha256": cls.pic, "paths": ["materials/own/pic.png"],
                 "caption": {"subject": "a gold foil carton", "product_form": "carton", "finish": "foil"},
                 "palette": [{"hex": "#CBA87D", "share": 0.4}]},
                {"sha256": cls.look, "paths": ["materials/ref/look.png"],
                 # the captioner writes several values as a list (237 fields of his record, 2026-09-26)
                 "caption": {"subject": "a rival's lipstick box", "product_form": ["tube", "carton box"],
                             "finish": ["matte", "gloss"]}, "palette": [{"hex": "#0000FF", "share": 0.5}]}]
        (root / "captions.jsonl").write_text("".join(json.dumps(c) + "\n" for c in caps))
        cls._override = override_settings(HISTORY_TIER_RECORD=str(root / "tiers.jsonl"),
                                          MATERIALS_CAPTIONS=str(root / "captions.jsonl"), MATERIALS_REPO_ROOT=str(root))
        cls._override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._override.disable()
        cls._tmpd.cleanup()
        super().tearDownClass()

    def setUp(self):
        from django.contrib.auth.models import Group

        from apps.pipeline.permissions import ROLE_DESIGNER
        self.user = User.objects.create_user("designer-p3d3", "d3@example.com", None)
        self.user.groups.add(Group.objects.get_or_create(name=ROLE_DESIGNER)[0])
        self.client.force_login(self.user)

    def _index(self):
        """[D-D7-1, Day 7 §5] the page reads the library INDEX (what each file shows, measured colours, surfaces, rights
        tier) — a fixture index beside the tier record; no house index, no previews on this machine."""
        import json
        root = Path(self._tmpd.name)
        rows = [{"sha256": self.pic, "name": "pic.png", "paths": ["materials/own/pic.png"], "extension": ".png", "file_kind": "raster", "kind": "pattern",
                 "subject": "A gold foil carton pattern", "tags": ["gold", "foil", "carton", "pattern", "luxury"], "style": ["luxury"],
                 "colours": [{"hex": "#CBA87D", "lab": [70.5, 5.2, 28.1], "share": 0.4}], "text_present": False, "text_seen": [], "language": "none",
                 "surfaces": ["carton", "pattern-fill"], "preview": False, "caption_source": "day7-haiku",
                 "rights": {"tier": "house", "excluded": False, "basis": "D-D7-1: house library, licensed for generation"}},
                {"sha256": self.look, "name": "look.png", "paths": ["materials/ref/look.png"], "extension": ".png", "file_kind": "raster", "kind": "photo",
                 "subject": "A rival's lipstick box", "tags": ["lipstick", "box", "tube", "carton"], "style": [], "colours": [{"hex": "#0000FF", "lab": [32.3, 79.2, -107.9], "share": 0.5}],
                 "text_present": False, "text_seen": [], "language": "none", "surfaces": ["mockup-scene"], "preview": False, "caption_source": "day5-brain-captions",
                 "rights": {"tier": "house", "excluded": False, "basis": "D-D7-1: house library, licensed for generation"}},
                {"sha256": "e" * 64, "name": "Mystery.ttf", "paths": ["materials/fonts/Mystery.ttf"], "extension": ".ttf", "kind": "font", "family": "Mystery",
                 "faces": [{"full_name": "Mystery Regular", "weight_class": 400, "italic": False, "scripts": ["latin"]}], "arabic": False, "variable": False,
                 "subject": "Mystery: 1 face, latin", "tags": ["font", "mystery", "latin"], "style": [], "colours": [], "text_present": False, "text_seen": [],
                 "language": "none", "surfaces": ["specimen"], "preview": False, "caption_source": "day6-font-census",
                 "rights": {"tier": "UNVERIFIED", "excluded": True, "basis": "excluded under D-D7-1: no licence evidence (UNVERIFIED pool)"}}]
        (root / "materials-index.json").write_text(json.dumps({"schema": "day7_materials_index/1", "items": rows}))
        return override_settings(MATERIALS_INDEX_PATH=str(root / "materials-index.json"), HOUSE_INDEX_PATH=str(root / "no-house-index.json"),
                                 MATERIALS_PREVIEWS_ROOT=str(root / "no-previews"))

    def test_files_are_listed_by_kind_with_what_they_show_their_colours_surfaces_and_rights(self):
        from django.utils.html import escape
        with self._index():
            html = self.client.get("/dashboard/materials/").content.decode()
        for words in ("pic.png", "A gold foil carton pattern", "#CBA87D", "House library — licensed for generation (D-D7-1)", "pattern (1)",
                      "photo (1)", "font (1)", "Suits: carton, pattern fill", "Excluded fonts (no licence evidence)", "1 excluded fonts"):
            self.assertIn(escape(words), html, words)
        self.assertNotIn("tier_source", html)
        self.assertNotIn("REFUSED_", html)
        self.assertNotIn(self.pic, html.split("<article")[0])                # no hash in the page's words

    def test_it_is_searched_by_what_a_file_shows_by_surface_by_tier_and_by_a_colour(self):
        with self._index():
            self.assertIn("pic.png", self.client.get("/dashboard/materials/?q=gold").content.decode())
            self.assertIn("No material matches", self.client.get("/dashboard/materials/?q=zzzz").content.decode())
            self.assertIn("pic.png", self.client.get("/dashboard/materials/?colour=%23CBA87D").content.decode())
            self.assertNotIn("pic.png", self.client.get("/dashboard/materials/?colour=%23000000").content.decode())
            self.assertIn("is not a colour", self.client.get("/dashboard/materials/?colour=gold").content.decode())
            self.assertIn("look.png", self.client.get("/dashboard/materials/?surface=mockup-scene").content.decode())
            excluded = self.client.get("/dashboard/materials/?tier=excluded").content.decode()
            self.assertIn("Mystery.ttf", excluded)
            self.assertIn("Excluded font — no licence evidence (D-D7-1)", excluded)
            self.assertNotIn("pic.png", excluded)

    def test_a_picture_is_drawn_only_for_a_placeable_file_whose_own_bytes_carry_no_other_tier(self):
        res = self.client.get(f"/dashboard/materials/pictures/0-{self.pic}.png")
        self.assertEqual((res.status_code, res["Content-Type"]), (200, "image/png"))
        self.assertTrue(res.content.startswith(b"\x89PNG"))
        for url in (f"/dashboard/materials/pictures/2-{self.look}.png",      # a reference
                    f"/dashboard/materials/pictures/3-{self.twin}.png",      # its bytes also carry a reference row
                    f"/dashboard/materials/pictures/0-{self.look}.png",      # a row named by another file's hash
                    f"/dashboard/materials/pictures/99-{self.pic}.png"):     # no such row
            self.assertEqual(self.client.get(url).status_code, 404, url)

    def test_a_file_has_a_detail_view_with_its_rights_what_it_shows_and_where_it_was_used(self):
        with self._index():
            html = self.client.get("/dashboard/materials/%s/" % self.pic).content.decode()
            for words in ("Rights", "D-D7-1", "A gold foil carton pattern", "gold · foil · carton", "Used in", "Not yet offered or pinned",
                          "Its tier record: PRODUCTION", "Described by the vision model on Day 7"):
                self.assertIn(words, html, words)
            self.assertNotIn(self.pic, html.replace("/dashboard/materials/previews/", ""))   # the hash is in the record, not on the page
            self.assertEqual(self.client.get("/dashboard/materials/%s/" % ("0" * 64)).status_code, 404)

    def test_without_the_index_the_page_says_so_and_someone_signed_out_signs_in_first(self):
        with override_settings(MATERIALS_INDEX_PATH=str(Path(self._tmpd.name) / "absent-index.json")):
            self.assertIn("The library index is not on this machine",
                          self.client.get("/dashboard/materials/").content.decode())
        self.client.logout()
        for url in ("/dashboard/materials/", f"/dashboard/materials/pictures/0-{self.pic}.png", f"/dashboard/materials/{self.pic}/",
                    f"/dashboard/materials/previews/{self.pic}.png"):
            res = self.client.get(url)
            self.assertEqual(res.status_code, 302, url)
            self.assertIn("login", res["Location"])


class ProductsLibraryTests(TestCase):
    """§BH55 Phase 3 p3-products — the products and their sizes (/dashboard/products/): each says what its size decides
    (read, or a paid estimate); a designer sets a product's size and what it is, refused with its words and nothing
    half-saved; the start form's product menu shows each size."""

    def setUp(self):
        from django.contrib.auth.models import Group

        from apps.core.models import Brand, Product
        from apps.pipeline.permissions import ROLE_DESIGNER
        brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.sized = Product.objects.create(brand=brand, product_id="BBR-P3D4-1", name="Night Oil", category="SK",
                                            year=2026, width_mm=40, depth_mm=40, height_mm=110, product_type="carton")
        self.bare = Product.objects.create(brand=brand, product_id="BBR-P3D4-2", name="Outer Glow", category="CO",
                                           year=2026)
        self.user = User.objects.create_user("designer-p3d4", "d4@example.com", None)
        self.user.groups.add(Group.objects.get_or_create(name=ROLE_DESIGNER)[0])
        self.client.force_login(self.user)

    def test_each_product_says_what_its_size_decides(self):
        from apps.dashboard.products import NO_SIZE_WORDS
        html = self.client.get("/dashboard/products/").content.decode()
        self.assertIn("40 × 40 × 110 mm", html)
        self.assertIn(NO_SIZE_WORDS, html)
        self.assertIn("Save its size", html)

    def test_a_designer_sets_a_size_and_the_start_form_shows_it(self):
        res = self.client.post(f"/dashboard/products/{self.bare.pk}/size/",
                               {"width_mm": "36.5", "depth_mm": "36.5", "height_mm": "95", "product_type": "palette box"})
        self.assertEqual(res.status_code, 302)
        self.bare.refresh_from_db()
        self.assertEqual((str(self.bare.width_mm), str(self.bare.depth_mm), str(self.bare.height_mm)),
                         ("36.50", "36.50", "95.00"))
        self.assertEqual(self.bare.product_type, "palette box")
        self.assertIn("Saved", self.client.get(res["Location"]).content.decode())
        home = self.client.get("/dashboard/new/classic/").content.decode()  # [the owner's answer to the UI directions of 2026-09-25: the home is the board; the start form is at New design]
        self.assertIn("Outer Glow · 36.5 × 36.5 × 95 mm", home)
        self.assertIn("Night Oil · 40 × 40 × 110 mm", home)

    def test_a_size_is_refused_with_its_words_and_nothing_is_half_saved(self):
        from django.utils.html import escape
        res = self.client.post(f"/dashboard/products/{self.sized.pk}/size/",
                               {"width_mm": "0", "depth_mm": "abc", "height_mm": "12.345"})
        self.assertEqual(res.status_code, 400)
        html = res.content.decode()
        for words in ("Nothing was saved", "Width must be more than 0 mm", "is not a number of millimetres",
                      "Height takes at most two decimals"):
            self.assertIn(escape(words), html)
        self.sized.refresh_from_db()
        self.assertEqual((str(self.sized.width_mm), str(self.sized.height_mm)), ("40.00", "110.00"))

    def test_clearing_a_size_says_the_carton_will_be_estimated(self):
        from apps.dashboard.products import NO_SIZE_WORDS
        res = self.client.post(f"/dashboard/products/{self.sized.pk}/size/",
                               {"width_mm": "", "depth_mm": "", "height_mm": "", "product_type": "carton"})
        self.assertEqual(res.status_code, 302)
        self.sized.refresh_from_db()
        self.assertIsNone(self.sized.width_mm)
        self.assertEqual(self.client.get(res["Location"]).content.decode().count(NO_SIZE_WORDS), 2)

    def test_only_a_designer_sets_a_size_and_someone_signed_out_signs_in_first(self):
        from django.contrib.auth.models import Group

        from apps.pipeline.permissions import ROLE_REVIEWER
        reviewer = User.objects.create_user("reviewer-p3d4", "r4@example.com", None)
        reviewer.groups.add(Group.objects.get_or_create(name=ROLE_REVIEWER)[0])
        self.client.force_login(reviewer)
        url = f"/dashboard/products/{self.bare.pk}/size/"
        self.assertEqual(self.client.post(url, {"width_mm": "1", "depth_mm": "1", "height_mm": "1"}).status_code, 403)
        html = self.client.get("/dashboard/products/").content.decode()
        self.assertNotIn("Save its size", html)
        self.assertIn("Setting a product's size is for a designer.", html)
        self.client.logout()
        for res in (self.client.get("/dashboard/products/"), self.client.post(url, {})):
            self.assertEqual(res.status_code, 302)
            self.assertIn("login", res["Location"])


class LibraryPageTests(TestCase):
    """THE LIBRARY — C's (the owner's answer to the UI directions of 2026-09-25): everything a design is made from on one
    page — the brand's colours, the faces its type is set in, its mark, the materials that can be placed (each artwork
    once), the granted faces, the products and their sizes, the finished designs — and the finished designs within it,
    each at its own address, where they were a page of their own outside the shell. Read-only."""

    def setUp(self):
        from django.contrib.auth.models import Group

        from apps.core.models import Brand, ColorSystem, Product
        from apps.dashboard import board
        from apps.pipeline.models import DesignTask, GateDecision, GeneratedImage, PackagingOutput
        from apps.pipeline.permissions import ROLE_DESIGNER
        self.enterContext(patch.dict(board.OWNER_FOLD, {}, clear=True))    # a test database's numbers are not his
        self.user = User.objects.create_user("designer-lib", "lib@example.com", None)
        self.user.groups.add(Group.objects.get_or_create(name=ROLE_DESIGNER)[0])
        self.brand = Brand.objects.create(name="BBROSE", master_brief="x")
        ColorSystem.objects.create(brand=self.brand, name="Blush Core", system_id="CS-001", status="canonical",
                                   palette=[{"name": "Amethyst Rose", "role": "Accent", "hex": "#8B3A52"}],
                                   image_generation_context="x")
        self.product = Product.objects.create(brand=self.brand, product_id="BBR-LIB-1", name="Night Oil", name_ar="زيت",
                                              category="CO", year=2026, width_mm=35, depth_mm=35, height_mm=100)
        self.task = DesignTask.objects.create(brand=self.brand, product=self.product, design_target="packaging",
                                              task_text="A carton for the night oil", status="complete")
        concept = GeneratedImage.objects.create(task=self.task, direction_name="Nocturne", prompt_used="p")
        # its number told apart from its design's: "Start a new design from this one" names the finished design
        self.output = PackagingOutput.objects.create(pk=self.task.pk + 1000, task=self.task, approved_image=concept,
                                                     spec_sheet={}, is_final_approved=True)
        GateDecision.objects.create(task=self.task, gate="gate_2", decision="approve", decided_by=self.user)
        # [the owner's goal of 2026-10-29: the Library's finished designs are the rounds whose files are made]
        self._rounds = tempfile.TemporaryDirectory()
        self.addCleanup(self._rounds.cleanup)
        self.enterContext(override_settings(ROUND_ARTIFACT_ROOT=Path(self._rounds.name)))
        self.made = _designer_round(self.user, name="Night gloss", made=True)
        self.client.force_login(self.user)

    def test_the_library_is_everything_a_design_is_made_from_on_one_page(self):
        html = self.client.get("/dashboard/library/").content.decode()
        self.assertIn('<h1 class="h1">Library</h1>', html)
        for part in ("colours", "faces", "mark", "materials", "all-faces", "products", "finished"):
            self.assertIn(f'id="{part}"', html, part)
        self.assertIn("Amethyst Rose", html)                                          # a colour, by its name
        self.assertIn("#8B3A52", html)
        self.assertIn("35 × 35 × 100 mm", html)                                     # a product, by its size
        # a finished design: a round whose files are made, opening its faces and files, its zip a click away; the old
        # approved output keeps its own page, unlisted (the owner's goal of 2026-10-29)
        self.assertIn(f'href="/dashboard/rounds/{self.made.pk}/built-files/"', html)
        self.assertIn(f'href="/dashboard/rounds/{self.made.pk}/built-files/download/files.zip" download>', html)
        self.assertNotIn(f'href="/dashboard/library/finished/{self.output.pk}/"', html)
        self.assertIn('aria-current="page">All</a>', html)
        self.assertIn('href="/dashboard/library/finished/">Finished designs</a>', html)
        self.assertIn('href="/dashboard/library/"', self.client.get("/dashboard/").content.decode())   # the bar's Library
        self.assertNotIn("product_container", html)

    def test_each_artwork_shows_once_however_many_files_it_is_on(self):
        from apps.dashboard.views import artworks
        rows = [{"n": 0, "sha": "a" * 64, "name": "G01.ai", "folder": "own", "drawable": True},
                {"n": 1, "sha": "b" * 64, "name": "G01.jpg", "folder": "own", "drawable": True},
                {"n": 2, "sha": "c" * 64, "name": "G01.jpg", "folder": "other", "drawable": True},
                {"n": 3, "sha": "d" * 64, "name": "notes.txt", "folder": "own", "drawable": False},
                {"n": 4, "sha": "e" * 64, "name": "Notes.JPG", "folder": "own", "drawable": True}]
        arts = artworks(rows)
        self.assertEqual([(a["folder"], a["name"], a["kinds"]) for a in arts],
                         [("own", "G01.ai", ["AI", "JPG"]), ("other", "G01.jpg", ["JPG"]), ("own", "notes.txt", ["TXT", "JPG"])])
        self.assertEqual((arts[2]["n"], arts[2]["drawable"]), (4, True))   # shown by its first file drawn here

    def test_a_finished_design_has_its_own_page_with_the_way_back_and_a_new_design_from_it(self):
        html = self.client.get(f"/dashboard/library/finished/{self.output.pk}/").content.decode()
        self.assertIn("A carton for the night oil", html)
        self.assertIn(f'href="/dashboard/designs/{self.task.pk}/">Open the design</a>', html)
        self.assertNotIn("Start a new design from this one", html)   # [the designer flow of 2026-10-27: a classic path, unlinked]
        self.assertIn("Design approved", html)                                      # an approval, in words
        self.assertIn("Nocturne", html)                                             # the direction chosen
        self.assertIn("No files on record", html)
        from apps.pipeline.models import PackagingOutput
        PackagingOutput.objects.filter(pk=self.output.pk).update(is_final_approved=False)
        self.assertEqual(self.client.get(f"/dashboard/library/finished/{self.output.pk}/").status_code, 404)

    def test_finished_designs_are_found_by_words_brand_category_and_date(self):
        # [the owner's goal of 2026-10-29] the made rounds, found by the words of their brief and the day they were made;
        # the old outputs' brand and category went with them, and a value the page cannot hold is left out, never a fault
        card = f'href="/dashboard/rounds/{self.made.pk}/built-files/"'
        for q in ("night gloss", "doe-foot wand"):
            self.assertIn(card, self.client.get("/dashboard/library/finished/", {"q": q}).content.decode(), q)
        none = self.client.get("/dashboard/library/finished/", {"q": "zzzz"}).content.decode()
        self.assertNotIn(card, none)
        self.assertIn("No finished design matches", none)
        later = self.client.get("/dashboard/library/finished/", {"date_from": "2999-01-01"}).content.decode()
        self.assertNotIn(card, later)
        for bad in ({"brand": "x"}, {"category": "ZZ"}, {"date_from": "not a date"}, {"page": "x"}):
            res = self.client.get("/dashboard/library/finished/", bad)                # left out, never a fault
            self.assertEqual(res.status_code, 200, bad)
            self.assertIn(card, res.content.decode(), bad)
        self.assertNotIn(f'href="/dashboard/library/finished/{self.output.pk}/"', self.client.get(
            "/dashboard/library/finished/").content.decode())

    def test_a_product_made_only_for_the_systems_own_tests_is_kept_apart(self):
        from apps.core.models import Product
        from apps.dashboard import board
        from apps.pipeline.models import DesignTask
        walk = Product.objects.create(brand=self.brand, product_id="CO-ACC-x", name="Acceptance walk", category="CO",
                                      year=2026)
        folded = DesignTask.objects.create(brand=self.brand, product=walk, design_target="packaging", task_text="w")
        Product.objects.create(brand=self.brand, product_id="BBR-LIB-2", name="Outer Glow", category="CO", year=2026)
        with patch.dict(board.OWNER_FOLD, {folded.pk: "acceptance walkthrough"}, clear=True):
            for url in ("/dashboard/library/", "/dashboard/products/"):
                html = self.client.get(url).content.decode()
                his, _, kept = html.partition("kept apart from the brand's products")
                self.assertIn("1 test record", his, url)
                self.assertNotIn("Acceptance walk", his, url)                      # not among his products
                self.assertIn("Acceptance walk", kept, url)                        # kept apart, one click away
                self.assertIn("Outer Glow", his, url)                             # a product with no design is his
                self.assertIn("Night Oil", his, url)                              # one with a design of his is his
        html = self.client.get("/dashboard/library/").content.decode()             # its design no longer folded
        self.assertNotIn("test record", html)

    def test_home_designs_and_library_read_the_rounds_and_each_shows_this_one(self):
        """The owner's goal of 2026-10-29, §0: "Keep Home, Designs and Library, switched to the chain engines" — signed
        in, each page opens (200) and shows the one round of the designer flow on record; the old task is on none."""
        pages = {"/dashboard/": f'<a class="nm" href="/dashboard/rounds/{self.made.pk}/built-files/"',
                 "/dashboard/history/": f'<a class="frame" href="/dashboard/rounds/{self.made.pk}/">',
                 "/dashboard/library/": f'<a class="frame" href="/dashboard/rounds/{self.made.pk}/built-files/">'}
        for url, shown in pages.items():
            res = self.client.get(url)
            self.assertEqual(res.status_code, 200, url)
            html = res.content.decode().partition('<main id="main"')[2]   # the page itself, below the one top bar
            self.assertIn(shown, html, url)
            self.assertIn("Night gloss", html, url)
            self.assertNotIn(f"/dashboard/designs/{self.task.pk}/", html, url)
        home = self.client.get("/dashboard/").content.decode()
        self.assertIn(">Files made</h2>", home)                                       # its lane: the files are made
        from apps.dashboard import board
        from apps.pipeline import autopilot
        self.assertEqual(board.AUTOPILOT_OPTION, autopilot.OPTION)   # the fold reads the pitch run's own key, unimported

    def test_step1_7_every_face_specimen_is_asked_for_as_its_page_opens_and_kept_for_the_day(self):
        """[His last goal before the pitch, 2026-10-16, Step 1 (7): "Library: every font specimen shows its sample
        (Poppins is blank)."] no specimen waits to be scrolled to — a lazy picture in a scrolled or hidden panel can stay
        unasked — and each is kept by the browser, so a page of them is drawn at once."""
        import re as _re
        for page in ("/dashboard/library/", "/dashboard/brand/"):
            html = self.client.get(page).content.decode()
            specimens = _re.findall(r'<img class="spec(?:imen)?" src="/dashboard/brand/faces/[^"]+"[^>]*>', html)
            self.assertTrue(specimens, page)
            self.assertFalse([i for i in specimens if 'loading="lazy"' in i], page)
            self.assertTrue(any("Poppins" in i for i in specimens), page)
        res = self.client.get("/dashboard/brand/faces/Poppins-Regular.png", {"show": "name"})
        self.assertEqual(res.status_code, 200)
        self.assertIn("max-age", res["Cache-Control"])

    def test_a_face_specimen_is_drawn_in_the_pages_deep_rose_so_it_reads_on_their_cream(self):
        # it was drawn in the old dark pages' cream: on C's cream, in the Library, on the brand's page, beside a design
        # and in Find, every specimen read as nothing
        import io

        from PIL import Image

        from apps.ire import font_roles
        url = f"/dashboard/brand/faces/{font_roles.CHAINS['body'][0]}.png"
        # whole (the brand's page); a product's name, set large (a face's card); two letters (a small row); any other
        # value, whole
        for show, size in (("", (960, 150)), ("name", (560, 100)), ("glyph", (168, 120)), ("x", (960, 150))):
            im = Image.open(io.BytesIO(self.client.get(url, {"show": show} if show else {}).content)).convert("RGBA")
            self.assertEqual(im.size, size, show)
            self.assertEqual({px[:3] for px in im.getdata() if px[3] == 255}, {(139, 58, 82)}, show)
        arabic = self.client.get(f"/dashboard/brand/faces/{font_roles.CHAINS['arabic-body'][0]}.png", {"show": "name"})
        self.assertEqual(Image.open(io.BytesIO(arabic.content)).size, (560, 100))

    def test_an_account_with_no_role_is_told_and_shown_no_finished_design(self):
        self.client.force_login(User.objects.create_user("no-role", "nr@example.com", None))
        for url in ("/dashboard/library/finished/", f"/dashboard/library/finished/{self.output.pk}/"):
            res = self.client.get(url)
            self.assertEqual(res.status_code, 403, url)
            self.assertIn("Your account has no role", res.content.decode())
            self.assertNotIn("A carton for the night oil", res.content.decode())
        html = self.client.get("/dashboard/library/").content.decode()
        self.assertIn("Your account has no role", html)
        self.assertNotIn(f'href="/dashboard/library/finished/{self.output.pk}/"', html)


class StatusPageTests(TestCase):
    """§BH55 Phase 3 p3-status — slice 4 of §BH51, the system as it stands (/dashboard/status/): what is waiting and on
    whom, what has stopped and what it said, what cannot move here and why; where the production gates stand; spend on
    the budget refusal's own clock; health, with the worker probed only when asked; how cartons are drawn; the last
    checks — each read now, and nothing written."""

    def setUp(self):
        from django.contrib.auth.models import Group

        from apps.core.models import Brand
        from apps.pipeline.models import DesignTask
        from apps.pipeline.permissions import ROLE_DESIGNER
        from apps.dashboard import board
        self.enterContext(patch.dict(board.OWNER_FOLD, {}, clear=True))    # a test database's numbers are not his
        self.user = User.objects.create_user("designer-p3e1", "e1@example.com", None)
        self.user.groups.add(Group.objects.get_or_create(name=ROLE_DESIGNER)[0])
        brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.waiting = DesignTask.objects.create(brand=brand, task_text="a carton at its concepts", status="awaiting_gate_1")
        self.held = DesignTask.objects.create(brand=brand, task_text="a carton at its structure",
                                              status="awaiting_structure_confirmation")
        self.stopped = DesignTask.objects.create(brand=brand, task_text="a stopped poster", status="failed",
                                                 error_message="Missing API key(s): ANTHROPIC_API_KEY")
        self.client.force_login(self.user)

    def test_how_cartons_are_drawn_and_the_checks_are_said_in_words_their_settings_folded(self):
        # [the owner's answer to the UI directions of 2026-09-25, (d) "Plain words everywhere. No engine codes on screen."]
        import re
        html = self.client.get("/dashboard/status/").content.decode()
        shown = re.sub(r"<[^>]+>", " ", re.sub(r'<details class="tech">.*?</details>', "", html, flags=re.S))
        # [the clean-up of 2026-10-04, his Q1 "remove the dormant packaging flow": the switches listed here left with
        # the ways they chose, and the one way is said]
        self.assertIn("A carton is drawn one way here: from the design map of the concept you chose, on a die the "
                      "dieline generator draws.", html)
        for code in ("semantic_encoder.py", "reference_index.py", "gate1_prompts.py"):
            self.assertNotIn(code, shown, code)
        self.assertNotRegex(shown, r"\d{4}-\d\d-\d\dT\d\d")                           # a time is a date and a time

    def test_what_is_waiting_is_said_in_words_with_the_way_to_each_design(self):
        html = self.client.get("/dashboard/status/").content.decode()
        # [the owner's answer to the UI directions of 2026-09-25: B's Status — a stopped design under "Needs attention",
        # its recorded error put into words (words.stop_words)]
        for words in ("Choose a concept", "a carton at its concepts", f'href="/dashboard/designs/{self.waiting.pk}/"',
                      "Needs attention", "The writing service had no key, so nothing was written",
                      # [the owner's answer of 2026-09-27: what a container waits on, said as it now stands]
                      # [§BH71 (0a) and (0b): it read "Cannot be finished yet", "Its finish waits on checks not built
                      # yet" — measured after both, a container is finished when the owner accepts it]
                      "Finished when the owner accepts it and a reviewer approves it",
                      "What is not measured yet is shown beside Approve as a warning, never a block."):
            self.assertIn(words, html)
        self.assertNotIn("awaiting_gate_1", html)

    def test_a_design_that_cannot_move_here_says_why(self):
        html = self.client.get("/dashboard/status/").content.decode()
        # [B's Status; the clean-up of 2026-10-04, his Q1 "remove the dormant packaging flow": it read "Its structure
        # step needs the vector path, which this site does not run" — the step is gone, and a design recorded at it
        # waits on nothing]
        self.assertIn("Paused at a structure check this site no longer runs — nothing waits on you", html)

    def test_the_production_gates_are_derived_now_and_nothing_is_written(self):
        from apps.pipeline.services import production_authority_gates as pag
        from apps.pipeline.services import spec_pack_intake as spi
        watched = [Path(p) for p in (pag.OUT, spi.OUT_STATE, spi.OUT_PROVENANCE) if Path(p).exists()]
        before = {p: (p.stat().st_mtime_ns, p.read_bytes()) for p in watched}
        html = self.client.get("/dashboard/status/").content.decode()
        self.assertEqual(before, {p: (p.stat().st_mtime_ns, p.read_bytes()) for p in watched})
        for words in ("Production gates", "Gate A — the Illustrator file executes", "Gate B — supplier geometry",
                      "The system never contacts suppliers", "The spec pack's"):
            self.assertIn(words, html)

    def test_spend_is_read_on_the_refusals_own_clock(self):
        from decimal import Decimal

        from django.utils import timezone

        from apps.pipeline.models import ApiCallRecord
        old = ApiCallRecord.objects.create(task=self.waiting, provider="anthropic", model="claude-x",
                                           operation="plan", cost_usd=Decimal("7.00"))
        ApiCallRecord.objects.filter(pk=old.pk).update(created_at=timezone.now() - timezone.timedelta(hours=25))
        ApiCallRecord.objects.create(task=self.waiting, provider="openai", model="gpt-image-x", operation="render",
                                     cost_usd=Decimal("2.50"))
        html = self.client.get("/dashboard/status/").content.decode()
        self.assertIn("In the last 24 hours: <strong>$2.50</strong>", html)       # the 25-hour-old call is outside it
        self.assertIn("gpt-image-x", html)
        self.assertIn("Not counted toward the caps", html)
        # the old page's side panel said the same clock; it is retired with the page, and Status says it (above)  # [the owner's answer to the UI directions of 2026-09-25: C's start page replaced the old single page]

    def test_the_worker_is_probed_only_when_asked(self):
        from unittest.mock import patch
        with patch("apps.core.health.ping_workers") as ping, override_settings(CELERY_TASK_ALWAYS_EAGER=False):
            html = self.client.get("/dashboard/status/").content.decode()
            ping.assert_not_called()
            self.assertIn("Check the queue and the worker now", html)
        with patch("apps.core.health.ping_workers", return_value={"w@host": {"ok": "pong"}}), \
                patch("apps.core.health.check_redis", return_value="ok"), \
                patch("apps.pipeline.tasks.report_worker_revision.delay") as delay, \
                patch("apps.pipeline.services.revision.current_revision", return_value="abc1234"), \
                override_settings(CELERY_TASK_ALWAYS_EAGER=False):
            delay.return_value.get.return_value = "abc1234"
            html = self.client.get("/dashboard/status/?probe=1").content.decode()
        self.assertIn("the same as this page's", html)

    def test_the_keys_that_let_it_spend_the_launch_checks_and_the_last_check_before_spending(self):
        # §BH55 Phase 3 (survey rows 1.16, 7.13): which keys are set — never their values — what a live machine wants,
        # and the last verdict recorded before any spending
        from apps.pipeline.models import AgentLog, DesignTask
        task = DesignTask.objects.create(brand=self.waiting.brand, task_text="a carton", status="running")
        AgentLog.objects.create(task=task, agent_name="ImageProducer",
                                action="Provider pre-spend validation FAILED — DUPLICATE_ACTIVE_GENERATION",
                                payload={"prespend": {"codes": ["DUPLICATE_ACTIVE_GENERATION"]}})
        with self.settings(ANTHROPIC_API_KEY="k", OPENAI_API_KEY="", DEBUG=False):
            html = self.client.get("/dashboard/status/").content.decode()
        self.assertIn("The provider keys", html)
        self.assertNotIn("k</span>", html)                       # a key's value never reaches the page
        self.assertIn("The last check before spending", html)
        self.assertIn("it refused", html)
        self.assertIn("DUPLICATE_ACTIVE_GENERATION", html)
        self.assertIn("Ready to run", html)
        self.assertIn("off, as a live machine wants it", html)
        self.assertIn("not set — no concept can be drawn", html)

    def test_the_brain_says_whether_it_still_matches_the_files_it_was_built_from(self):
        # §BH55 Phase 3 (survey rows 4.5, 5.1): the record lists every source with its hash; each is read and hashed
        import hashlib
        from django.core.cache import cache
        from apps.dashboard import status as st
        cache.delete("dashboard:brain_freshness/1")
        with tempfile.TemporaryDirectory() as tmp:
            same = Path(tmp) / "same.md"
            same.write_text("a ruling")
            moved = Path(tmp) / "moved.md"
            moved.write_text("a queue, changed since")
            record = {"sources": {str(same): hashlib.sha256(b"a ruling").hexdigest(),
                                  str(moved): hashlib.sha256(b"a queue").hexdigest(),
                                  str(Path(tmp) / "gone.md"): "0" * 64}}
            out = st._brain_freshness(record)
        assert out["measured"] == 3 and out["fresh"] is False
        assert out["changed"] == ["moved.md"] and out["changed_count"] == 1
        assert out["missing"] == ["gone.md"] and out["missing_count"] == 1
        cache.delete("dashboard:brain_freshness/1")

    def test_a_design_that_cannot_pass_its_review_says_why(self):
        # §BH55 Phase 3 (survey row 4.22): a container whose single readiness authority refuses says so where it waits
        from unittest import mock
        from apps.dashboard import status as st
        from apps.pipeline.models import DesignTask
        task = DesignTask.objects.create(brand=self.waiting.brand, task_text="a bottle", status="awaiting_gate_2",
                                         design_target="product_container")
        with mock.patch("apps.pipeline.services.reconstruction_status.build_container_gate2_readiness",
                        return_value={"ready": False, "reason_code": "VISUAL_QUALITY_GATE_FAILED"}):
            assert st._cannot_pass(task).startswith("its drawing has not passed the visual-quality gate")
            html = self.client.get("/dashboard/status/").content.decode()
        self.assertIn("its drawing has not passed the visual-quality gate", html)
        with mock.patch("apps.pipeline.services.reconstruction_status.build_container_gate2_readiness",
                        return_value={"ready": True}):
            assert st._cannot_pass(task) == ""
        task.design_target = "packaging"
        assert st._cannot_pass(task) == ""                       # a carton's review has no such authority

    def test_how_cartons_are_drawn_and_someone_signed_out_signs_in_first(self):
        html = self.client.get("/dashboard/status/").content.decode()
        self.assertIn("A carton is drawn one way here: from the design map of the concept you chose, on a die the "
                      "dieline generator draws.", html)
        # §BH55 Phase 3: what the paid steps use — the picture model, its size, the set's count, the redraws allowed
        from django.conf import settings as s
        self.assertIn("What the paid steps use", html)
        self.assertIn(s.IMAGE_MODEL, html)
        self.assertIn(s.IMAGE_SIZE, html)
        self.assertIn("three are drawn for the direction you choose", html)
        self.assertIn("how many times a set of concepts may be drawn again for one design", html)
        self.client.logout()
        res = self.client.get("/dashboard/status/")
        self.assertEqual(res.status_code, 302)
        self.assertIn("login", res["Location"])


class RulingsPageTests(TestCase):
    """§BH55 Phase 3 p3-rulings — the owner's register of rulings and his review queue on the site
    (/dashboard/status/rulings/): newest first, each section at its own address with its whole text, searchable by words;
    beside each ruling what the brain measured it to be, labelled as derived — read from files of the test's own."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        import sqlite3
        cls._tmpd = tempfile.TemporaryDirectory()
        root = Path(cls._tmpd.name)
        (root / "register.md").write_text(
            "# Register\n\n## 2026-09-01 — OWNER RULING §BH90: THE FIRST\n\nfirst ruling text about gold foil\n\n"
            "## 2026-09-02 — OWNER RULING §BH91: THE SECOND\n\nsecond ruling text\n")
        (root / "queue.md").write_text("# Queue\n\n## 2026-09-03 — A QUEUE ITEM\n\nwaiting for his eye\n")
        (root / "brain").mkdir()
        con = sqlite3.connect(root / "brain" / "brain.sqlite")
        con.execute("create table sections (id text, path text, status text, superseded_by text)")
        con.executemany("insert into sections values (?, ?, ?, ?)",
                        [("§BH90", "OWNER_BLOCKER_CLEARANCE.md", "SUPERSEDED-BY §BH91", "§BH91"),
                         ("§BH91", "OWNER_BLOCKER_CLEARANCE.md", "LIVE", None)])
        con.commit()
        con.close()
        (root / "brain" / "freshness.json").write_text('{"built_at": "2026-09-20T00:00:00Z"}')
        cls._override = override_settings(RULINGS_REGISTER=str(root / "register.md"),
                                          RULINGS_QUEUE=str(root / "queue.md"),
                                          RULINGS_BRAIN_DB=str(root / "brain" / "brain.sqlite"))
        cls._override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._override.disable()
        cls._tmpd.cleanup()
        super().tearDownClass()

    def setUp(self):
        self.client.force_login(User.objects.create_user("designer-p3e2", "e2@example.com", None))

    def test_the_register_is_newest_first_with_what_the_brain_measured(self):
        html = self.client.get("/dashboard/status/rulings/").content.decode()
        self.assertLess(html.index("§BH91"), html.index("§BH90"))
        self.assertIn("superseded by §BH91", html)
        self.assertIn("· live", html)
        # [the owner's goal of 2026-09-25, (d) "No engine codes on screen": the rebuild's time, said as a date]
        self.assertIn("20 September 2026, 00:00", html)                      # derived, and said when

    def test_a_ruling_opens_at_its_own_address_with_its_whole_text(self):
        res = self.client.get("/dashboard/status/rulings/register/3/")
        self.assertEqual(res.status_code, 200)
        html = res.content.decode()
        self.assertIn("first ruling text about gold foil", html)
        self.assertIn("§BH91 →", html)
        self.assertEqual(self.client.get("/dashboard/status/rulings/register/4/").status_code, 404)
        self.assertEqual(self.client.get("/dashboard/status/rulings/elsewhere/3/").status_code, 404)

    def test_it_is_searched_by_words_and_the_queue_is_read_too(self):
        html = self.client.get("/dashboard/status/rulings/?q=gold+foil").content.decode()
        self.assertIn("§BH90", html)
        self.assertNotIn("THE SECOND", html)
        self.assertIn("A QUEUE ITEM", self.client.get("/dashboard/status/rulings/?source=queue").content.decode())

    def test_without_its_file_it_says_so_and_someone_signed_out_signs_in_first(self):
        with override_settings(RULINGS_REGISTER=str(Path(self._tmpd.name) / "absent.md")):
            self.assertIn("This file is not on this machine",
                          self.client.get("/dashboard/status/rulings/").content.decode())
        self.client.logout()
        for url in ("/dashboard/status/rulings/", "/dashboard/status/rulings/register/3/"):
            self.assertEqual(self.client.get(url).status_code, 302, url)


# ---------------------------------------------------------------------------
# §BH55(a) — what the owner's Phase 1 brief says the pack must carry.
#
# Three things his brief names had no home in the record: shade names for the
# four pans, the four house claims, and the product's name in Arabic. The
# claims are the BRAND's ("that run on every product of ours"); the Arabic
# name and the shades are the PRODUCT's. Every bilingual row carries BOTH
# languages in ONE row, because he wrote that Arabic is not an afterthought
# and two parallel lists are how an afterthought is stored.
# ---------------------------------------------------------------------------


class BilingualPackCopyTests(TestCase):

    def _brand(self, **kw):
        from apps.core.models import Brand
        return Brand.objects.create(name="BBROSE", master_brief="x", **kw)

    def test_the_house_claims_live_on_the_brand_and_carry_both_languages(self):
        from apps.core.models import AR_UNCONFIRMED, bilingual
        brand = self._brand(claims=[
            {"en": "Cruelty-free", "ar": "\u062e\u0627\u0644\u064d \u0645\u0646 \u0627\u0644\u0642\u0633\u0648\u0629",
             "ar_source": AR_UNCONFIRMED},
            {"en": "100% vegan", "ar": "\u0646\u0628\u0627\u062a\u064a 100\u066a", "ar_source": AR_UNCONFIRMED},
        ])
        brand.refresh_from_db()
        assert bilingual(brand.claims, "en") == ["Cruelty-free", "100% vegan"]
        assert len(bilingual(brand.claims, "ar")) == 2
        assert all(r["ar"] for r in brand.claims)

    def test_a_brand_with_no_claims_reads_as_an_empty_list_not_as_none(self):
        brand = self._brand()
        brand.refresh_from_db()
        assert brand.claims == []

    def test_the_product_carries_an_arabic_name_and_its_shade_names(self):
        from apps.core.models import Brand, Product, bilingual
        brand = self._brand()
        p = Product.objects.create(
            brand=brand, product_id="BBR-CO-901", name="Rose Glow Palette",
            name_ar="\u0628\u0627\u0644\u064a\u062a \u0631\u0648\u0632 \u062c\u0644\u0648",
            category="CO", year=2026,
            shade_names=[{"en": "First Light", "ar": "\u0636\u0648\u0621 \u0623\u0648\u0644"},
                         {"en": "Petal", "ar": "\u0628\u062a\u0644\u0629"},
                         {"en": "Warm Rose", "ar": "\u0648\u0631\u062f\u064a \u062f\u0627\u0641\u0626"},
                         {"en": "Gilded", "ar": "\u0645\u0630\u0647\u0651\u0628"}])
        p.refresh_from_db()
        assert p.name == "Rose Glow Palette" and p.name_ar
        assert len(bilingual(p.shade_names, "en")) == 4
        assert len(bilingual(p.shade_names, "ar")) == 4
        assert isinstance(Brand.objects.get(pk=brand.pk).claims, list)

    def test_a_row_missing_its_arabic_is_skipped_as_a_row_and_shifts_nothing(self):
        """The reason a claim is ONE row with two languages: a shade with no Arabic must not silently move every
        later shade up by one, which is exactly what two parallel lists do."""
        from apps.core.models import bilingual
        rows = [{"en": "First Light", "ar": "A"}, {"en": "Petal"},
                {"en": "Warm Rose", "ar": "C"}, {"en": "Gilded", "ar": "D"}]
        assert bilingual(rows, "en") == ["First Light", "Petal", "Warm Rose", "Gilded"]
        assert bilingual(rows, "ar") == ["A", "C", "D"]

    def test_arabic_the_executor_wrote_is_marked_and_can_be_named(self):
        """It can reach a printed pack in a market he named, so it says whose it is rather than passing as his."""
        from apps.core.models import AR_UNCONFIRMED, unconfirmed_arabic
        rows = [{"en": "Cruelty-free", "ar": "A", "ar_source": AR_UNCONFIRMED},
                {"en": "100% vegan", "ar": "B", "ar_source": "OWNER_CONFIRMED"},
                {"en": "Long-wear"}]
        assert unconfirmed_arabic(rows) == ["Cruelty-free"]


class TheSuiteWritesIntoItsOwnMediaRootTests(SimpleTestCase):
    """THE OWNER'S SECOND ANSWER OF 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md, the block headed "Before I start
    testing"): "Measure how much of the media folder is test output, and stop the tests writing into the real
    folder. Delete nothing." Measured: of the folder's 969,714 files, 675,019 (11.2 GB) were named by no record and
    last written inside a gate window. config/settings.py now gives the suite a media root of its own."""

    def test_the_suites_media_root_is_its_own_and_outside_the_repository(self):
        from django.conf import settings
        root = Path(settings.MEDIA_ROOT).resolve()
        real = Path(settings.REAL_MEDIA_ROOT).resolve()
        assert root != real and not root.is_relative_to(real)
        assert not root.is_relative_to(Path(settings.BASE_DIR).resolve().parent)
        assert root.name.startswith("bbrose_test_media_") and root.is_dir()

    def test_a_file_the_storage_saves_lands_in_the_suites_root_and_never_in_the_real_folder(self):
        from django.conf import settings
        from django.core.files.base import ContentFile
        from django.core.files.storage import default_storage
        name = default_storage.save("suite_media_probe/probe.txt", ContentFile(b"probe"))
        assert Path(default_storage.path(name)).resolve().is_relative_to(Path(settings.MEDIA_ROOT).resolve())
        assert not (Path(settings.REAL_MEDIA_ROOT) / name).exists()

    def test_the_brand_mark_is_still_read_from_the_real_folder(self):
        """An input is not an output: the mark every composer draws keeps its own setting, resolved from the real
        root before the suite's root replaced it."""
        from django.conf import settings
        assert Path(settings.BRAND_LOGO_PATH).resolve() == (Path(settings.REAL_MEDIA_ROOT) / "brand" / "logo.png").resolve()
        assert Path(settings.BRAND_LOGO_PATH).is_file()


class BoardTests(TestCase):
    """THE BOARD (the owner's answer to the UI directions, 2026-09-25: B's board, "Build it."): ONE classification of
    every design — its step, what it waits on in words, whether it is folded away — and the top bar's three counts,
    read by every screen. It writes nothing. His fold is by task (53–57 and the demo carton) and by the planning
    probes' own project marker; a stopped try with a later try that went on is listed under that try, never hidden and
    never counted twice; a working design silent past the worker's hard time limit has stopped moving."""

    def setUp(self):
        from apps.core.models import Brand, Product
        from apps.dashboard import board
        self.enterContext(patch.dict(board.OWNER_FOLD, {}, clear=True))    # a test database's numbers are not his
        self.brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.powder = Product.objects.create(brand=self.brand, product_id="BBR-T-1", name="Focus Pressed Powder",
                                             name_ar="فوكس", category="CO", year=2026)

    def _task(self, status, **kw):
        from apps.pipeline.models import DesignTask
        kw.setdefault("task_text", "A pressed face powder for BBROSE.")
        kw.setdefault("design_target", "product_container")
        return DesignTask.objects.create(brand=self.brand, status=status, **kw)

    def _age(self, task, **delta):
        from django.utils import timezone

        from apps.pipeline.models import DesignTask
        then = timezone.now() - timezone.timedelta(**delta)
        DesignTask.objects.filter(pk=task.pk).update(created_at=then, updated_at=then)
        task.refresh_from_db()
        return task

    def _cards(self):
        from apps.dashboard import board
        return {c.task_id: c for c in board.classify()}

    def _output(self, task, spec):
        from apps.pipeline.models import GeneratedImage, PackagingOutput
        image = GeneratedImage.objects.create(task=task, direction_name="d", prompt_used="p", image_file="generated/g.png")
        return PackagingOutput.objects.create(task=task, approved_image=image, spec_sheet=spec)

    def test_every_status_has_one_place_and_says_it_in_words(self):
        from apps.dashboard import board
        from apps.pipeline.models import TASK_STATUS
        for value, _label in TASK_STATUS:
            self._task(value, product=self.powder)
        cards = board.classify()
        self.assertEqual(len(cards), len(TASK_STATUS))
        found = board.board(cards)
        groups = [found["attention"], found["tried_again"], *[c["cards"] for c in found["columns"]],
                  *[g["cards"] for g in found["folded"]]]
        placed = sum(len(group) for group in groups)
        self.assertEqual(placed, len(cards))                      # every design in exactly one place
        for card in cards:
            self.assertIn(card.lane, dict(board.LANES))
            self.assertTrue(card.next_words)
            self.assertNotRegex(card.next_words, r"[a-z]+_[a-z]+")    # no status name on the card

    def test_his_fold_and_the_planning_probes_count_nowhere(self):
        from apps.dashboard import board
        from apps.pipeline.models import DesignProject
        self.assertEqual(board.HIS_FOLD, {53: "acceptance walkthrough", 54: "acceptance walkthrough",
                                          55: "acceptance walkthrough", 56: "acceptance walkthrough",
                                          57: "acceptance walkthrough", 17: "demo carton"})
        self.assertEqual(board.OWNER_FOLD, {})                     # emptied for this class (setUp), never his
        walk = self._task("awaiting_gate_2", product=self.powder)
        demo = self._task("awaiting_dimensions", design_target="packaging", task_text="[DEMO] a carton")
        project = DesignProject.objects.create(brand=self.brand, brief="probe", design_target="product_container",
                                               metadata={"planning_probe": {"run": "r1"}})
        probe = self._task("awaiting_direction_selection", product=self.powder, project=project)
        mine = self._task("awaiting_gate_2", product=self.powder)
        fold = {walk.pk: "acceptance walkthrough", demo.pk: "demo carton"}
        with patch.dict(board.OWNER_FOLD, fold, clear=True):
            cards = self._cards()
            tally = board.counts()
        for folded, why in ((walk, "acceptance walkthrough"), (demo, "demo carton"), (probe, "planning test")):
            self.assertEqual((cards[folded.pk].state, cards[folded.pk].fold), (board.FOLDED, why))
        self.assertEqual(cards[mine.pk].state, board.WAITING)
        self.assertEqual((tally[board.WAITING], tally[board.WORKING], tally[board.ATTENTION]), (1, 0, 0))
        self.assertIn("tasks 53–57", board.OWNER_FOLD_WORDS)

    def test_step1_4_the_executors_tests_and_old_designs_fold_into_your_tests_his_live_work_stays(self):
        """[His last goal before the pitch, 2026-10-16, Step 1 (4): "Board: fold every design older than 7 days or started
        by the executor as a test into "Your tests"; Needs attention and Waiting show only live work."]"""
        import datetime as _dt

        from apps.dashboard import board
        from apps.pipeline.models import DesignProject, DesignTask
        mine = self._task("awaiting_gate_2", product=self.powder)
        test_run = self._task("awaiting_gate_2", product=self.powder, options={"test_run": "the executor's run"})
        project = DesignProject.objects.create(brand=self.brand, brief="b", design_target="complete_product")
        self._task("awaiting_gate_2", product=self.powder, project=project, stage="product_container",
                   options={"test_run": "his showcase run"})
        carton = self._task("awaiting_gate_2", product=self.powder, project=project, stage="packaging",
                            design_target="packaging")                              # the same test's next stage
        his_pitch_run = self._task("awaiting_gate_2", product=self.powder, options={"autopilot": {"on": True}})
        executor_pitch_run = self._task("awaiting_gate_2", product=self.powder, options={"autopilot": {"on": True}})
        DesignTask.objects.filter(pk=executor_pitch_run.pk).update(
            created_at=board.PITCH_RUN_TESTS_BEFORE - _dt.timedelta(hours=1))
        old = self._age(self._task("failed", product=self.powder, task_text="An old brief of his.",
                                   error_message="Missing API key(s): X"), days=8)
        cards = self._cards()
        for folded in (test_run, carton, executor_pitch_run, old):
            self.assertEqual((cards[folded.pk].state, cards[folded.pk].fold), (board.FOLDED, "test"), folded.pk)
        for live in (mine, his_pitch_run):                        # a pitch run he starts himself is his live work
            self.assertEqual(cards[live.pk].state, board.WAITING, live.pk)
        found = board.board(list(cards.values()))
        self.assertEqual(found["counts"][board.ATTENTION], 0)       # the old stop is no live work
        self.assertEqual({g["key"]: g["words"] for g in found["folded"]}["test"], "Your tests")
        # the Designs page and Find list every design: an old one there is where it stands, never folded as a test
        unfolded = {c.task_id: c for c in board.classify(fold_old=False)}
        self.assertEqual(unfolded[old.pk].state, board.ATTENTION)
        self.assertEqual(unfolded[test_run.pk].state, board.FOLDED)
        # its own page says where it stands, never "Folded away"
        from django.contrib.auth import get_user_model
        self.client.force_login(get_user_model().objects.create_user("step1-viewer", password="x", is_staff=True))
        html = self.client.get(f"/dashboard/designs/{test_run.pk}/").content.decode()
        self.assertIn('class="tag waiting"', html)
        self.assertNotIn("Folded away", html.split('id="task-status-badge"', 1)[1].split("</span>", 1)[0])

    def test_step1_3_a_design_is_named_by_its_product_never_its_briefs_first_sentence(self):
        """[His last goal before the pitch, 2026-10-16, Step 1 (3): "Design titles = the product name (e.g. "Midnight
        Fig — perfume"), never the brief's first sentence."]"""
        from apps.dashboard import board
        from apps.pipeline.models import CreativeBrief
        read = self._task("awaiting_gate_2", task_text="Hi team, we need the bottle artwork for a new eau de parfum, "
                                                       "50 ml, called \"Midnight Fig\".")
        CreativeBrief.objects.create(task=read, directions=[], design_intent={"brief": {
            "product_name": "BBROSE Midnight Fig", "brand": "BBROSE"}})
        unread = self._task("awaiting_gate_2", task_text="Can you design a round powder blush compact called "
                                                         "\"Coral Haze\"? Soft but modern.")
        house = self._task("awaiting_gate_2", task_text="BBROSE Cocoa Fondant Matte Lipstick, 3.5 g bullet.")
        neither = self._task("awaiting_gate_2", task_text="A pressed face powder for BBROSE.")
        cards = self._cards()
        self.assertTrue(cards[read.pk].title.startswith("Midnight Fig — "), cards[read.pk].title)
        self.assertTrue(cards[unread.pk].title.startswith("Coral Haze — "), cards[unread.pk].title)
        self.assertTrue(cards[house.pk].title.startswith("Cocoa Fondant Matte Lipstick"), cards[house.pk].title)
        self.assertTrue(cards[neither.pk].title.startswith("A pressed face powder for BBROSE"))   # the brief is all
        self.assertEqual(board.title_of(read), cards[read.pk].title)                             # one name everywhere

    def test_step1_2_the_designers_eye_answers_for_the_checks_not_measured_never_both(self):
        """[His last goal before the pitch, 2026-10-16, Step 1 (2): "One verdict: the designer's eye result replaces "Not
        measured yet" when it has run; never both, never contradicting."]"""
        from apps.pipeline.views import _acceptance_warnings
        unmeasured = {"front_type/1.0": {"codes": ["CARTON_FRONT_COPY_UNMEASURED:front"]}}
        for eye, kind in ((None, "unmeasured"), ({"state": "NOT_LOOKED"}, "unmeasured"),
                          ({"state": "DIFFERS"}, "eye"), ({"state": "PASS"}, "eye")):
            task = self._task("awaiting_gate_2", design_target="packaging", task_text="a carton %s" % kind)
            self._output(task, dict(unmeasured, **({"designers_eye/1.0": eye} if eye else {})))
            rows = _acceptance_warnings(task, None)
            self.assertTrue(rows, eye)
            self.assertEqual({r["kind"] for r in rows}, {kind}, eye)

    def test_step1_1_the_systems_own_notes_are_one_folded_sentence_never_a_line_each(self):
        """[His last goal before the pitch, 2026-10-16, Step 1 (1): "Never show raw engine lines on a design page ("A fault
        in the system itself — #E5DDE1:face-art-66" ×100s ...). Group internal faults into ONE plain sentence, folded;
        show only what a designer needs to judge, in words."]"""
        from apps.pipeline.gate2_problems import INTERNAL_CODE, _merged, _row
        rows = _merged([_row("CONTAINER_COLOUR_UNSOURCED:#%06X:face-art-%d" % (i, i)) for i in range(175)]
                       + [_row("CONTAINER_FRONT_COPY_EXCEEDS_SAFE_BAND:product-name-hero-0 +15.4873 mm"),
                          _row("CONTAINER_FRONT_COPY_EXCEEDS_SAFE_BAND:front-descriptor-1-0 +18.5961 mm")])
        internal = [r for r in rows if r.get("internal")]
        self.assertEqual(len(internal), 1)
        self.assertEqual(internal[0]["code"], INTERNAL_CODE)
        self.assertTrue(internal[0]["words"].startswith("175 things the system noted"), internal[0]["words"])
        self.assertEqual(len(internal[0]["details"]), 175)                 # every code kept, folded
        said = [r for r in rows if not r.get("internal")]
        self.assertEqual(len(said), 1)                                     # one check, its two lines folded
        self.assertNotRegex(said[0]["words"], r"#|\d+\.\d|hero-0")         # in words, never the record's names
        self.assertEqual(said[0]["details"], ["product-name-hero-0 +15.4873 mm", "front-descriptor-1-0 +18.5961 mm"])
        for r in rows:
            self.assertNotIn("a fault in the system itself", r["words"])

    def test_a_working_design_silent_past_the_workers_limit_has_stopped_moving(self):
        from apps.dashboard import board
        from apps.pipeline.models import AgentLog
        fresh = self._task("queued", product=self.powder)
        never = self._age(self._task("queued", design_target="packaging", task_text="a honey lip gloss"), hours=2)
        silent = self._age(self._task("running", product=self.powder), hours=2)
        AgentLog.objects.create(task=silent, agent_name="ARIA", action="ARIA: pipeline started")
        AgentLog.objects.filter(task=silent).update(timestamp=silent.updated_at)
        cards = self._cards()
        self.assertEqual(cards[fresh.pk].state, board.WORKING)
        self.assertEqual(cards[never.pk].state, board.ATTENTION)
        self.assertIn("never started", cards[never.pk].reason)
        self.assertEqual(cards[silent.pk].state, board.ATTENTION)
        self.assertIn("Stopped moving", cards[silent.pk].reason)
        with self.settings(CELERY_TASK_TIME_LIMIT=3 * 3600):             # the limit is read, never a literal here
            self.assertEqual(self._cards()[never.pk].state, board.WORKING)

    def test_a_stopped_try_is_listed_under_the_later_try_that_went_on(self):
        from apps.dashboard import board
        stopped = self._age(self._task("failed", product=self.powder,
                                       error_message="Direction planning failed validation: TYPOGRAPHY_NOT_DISTINCT; "
                                                     "PRODUCTION_RASTER_DEPENDENCY:direction[1]"), hours=3)
        alone = self._age(self._task("failed", design_target="packaging", task_text="a banana rice serum box",
                                     product=self.powder,
                                     error_message="Missing API key(s): ANTHROPIC_API_KEY (design directions + QA)."),
                          hours=3)
        self._task("awaiting_dimensions", design_target="packaging", task_text="a shampoo box", product=self.powder)
        later = self._task("awaiting_gate_2", product=self.powder)
        cards = self._cards()
        self.assertEqual((cards[stopped.pk].state, cards[stopped.pk].later_try), (board.TRIED_AGAIN, later.pk))
        self.assertEqual(cards[later.pk].earlier_stops, [stopped.pk])
        self.assertEqual(cards[stopped.pk].reason, "The three directions it wrote failed its own checks: their type "
                         "was too alike; a direction needed a photographic picture, which can't go into print-ready "
                         "artwork")
        self.assertEqual(cards[alone.pk].state, board.ATTENTION)
        self.assertEqual(cards[alone.pk].reason, "The writing service had no key, so nothing was written")
        self.assertEqual(board.counts()[board.ATTENTION], 1)

    def test_finding1_a_design_whose_planner_tried_twice_says_so_in_words(self):
        # his test day finding 1 (2026-09-29, design 116): "It stops only if it fails again, and says why in plain
        # words." It had tried twice and said so nowhere, and the required copy read "required copy missing"
        from apps.pipeline.models import AgentLog
        stopped = self._task("failed", product=self.powder,
                             error_message="Direction planning failed validation: PALETTE_SYSTEMS_NOT_DISTINCT; "
                                           "REQUIRED_COPY_MISSING:direction[0]; REQUIRED_COPY_MISSING:direction[1]")
        AgentLog.objects.create(task=stopped, agent_name="CreativeDirector",
                                action="Creative Director: generation metadata", payload={"attempts": 2})
        self.assertEqual(self._cards()[stopped.pk].reason, "It wrote the three directions twice, and both failed its "
                         "own checks: their colours were too alike; they left out copy your brief requires, word for "
                         "word")

    def test_a_stopped_design_with_no_recorded_error_is_read_from_its_own_failure_line(self):
        from apps.pipeline.models import AgentLog
        quiet = self._task("failed", design_target="packaging", task_text="an eyeliner carton")
        self.assertEqual(self._cards()[quiet.pk].reason, "It stopped with no reason recorded")
        AgentLog.objects.create(task=quiet, agent_name="ARIA",
                                action='ARIA: pipeline failed — "Could not resolve authentication method."')
        self.assertEqual(self._cards()[quiet.pk].reason, "The writing service had no key, so nothing was written")

    def test_a_design_rejected_at_review_waits_for_his_look_only_once_drawn_again(self):
        from apps.dashboard import board
        from apps.pipeline.models import AgentLog
        task = self._task("container_stage_visually_rejected", product=self.powder)
        self._output(task, {"container_reconstruction_rejected_2026_07_27_gate2":
                            {"decided_at": "2026-07-27T07:07:54+00:00"}})
        self.assertEqual(self._cards()[task.pk].state, board.ATTENTION)
        AgentLog.objects.create(task=task, agent_name="Container", action="Container: reconstructed bottle concept sheet")
        card = self._cards()[task.pk]
        self.assertEqual((card.lane, card.state), ("review", board.WAITING))

    def test_a_step_this_site_cannot_move_is_said_and_never_counted_as_waiting(self):
        from apps.dashboard import board
        held = self._task("awaiting_structure_confirmation", design_target="packaging", task_text="a carton")
        palette = self._task("design_intent_confirmed", design_target="palette", task_text="M5 palette")
        cards = self._cards()
        self.assertEqual((cards[held.pk].state, cards[palette.pk].state), (board.STUCK, board.STUCK))
        self.assertEqual(board.counts()[board.WAITING], 0)

    def test_goal_1010_item2_a_palette_with_its_pans_is_named_lid_and_open_tray(self):
        """[His goal of 2026-10-10 (OWNER_BLOCKER_CLEARANCE.md), item 2: "The title says "— compact lid". A palette
        design must include the whole palette: the lid AND the open tray"] a compact whose brief names its pans is
        drawn open too, and its name says so; one that names none stays its lid."""
        palette = self._task("awaiting_gate_1", task_text=("Enchanted Rose Palette (test)\n\nType: eyeshadow palette, a "
                                                           "rectangular case, 18\nsquare pans in 3 rows of 6.\n"))
        self._output(palette, {"container_profile/1.0": {"archetype": "compact"}})
        lid = self._task("awaiting_gate_2", product=self.powder)
        self._output(lid, {"container_profile/1.0": {"archetype": "compact"}})
        cards = self._cards()
        self.assertEqual(cards[palette.pk].title, "Enchanted Rose Palette (test) — palette lid and open tray")
        self.assertEqual(cards[lid.pk].title, "Focus Pressed Powder — compact lid")

    def test_a_design_is_named_by_its_product_and_what_is_designed(self):
        from apps.dashboard import board
        lid = self._task("awaiting_gate_2", product=self.powder)
        self._output(lid, {"container_profile/1.0": {"archetype": "compact"}})
        carton = self._task("awaiting_gate_2", design_target="packaging",
                            task_text="Design the outer carton for BBROSE Velvet Bloom Serum — soft blush\nmore")
        cards = self._cards()
        self.assertEqual(cards[lid.pk].title, "Focus Pressed Powder — compact lid")
        dropper = self._task("awaiting_gate_2", product=self.powder)
        self._output(dropper, {"container_profile/1.0": {"archetype": "bottle",
                                                         "fields": {"cap_type": {"value": "dropper"}}}})
        self.assertEqual(self._cards()[dropper.pk].title, "Focus Pressed Powder — dropper bottle")
        from apps.core.models import Product
        serum = Product.objects.create(brand=self.brand, product_id="BBR-T-2", name="Velvet Bloom Serum Carton",
                                       category="SK", year=2026)
        boxed = self._task("awaiting_gate_2", design_target="packaging", product=serum)
        self.assertEqual(self._cards()[boxed.pk].title, "Velvet Bloom Serum Carton")
        self.assertEqual(cards[carton.pk].title, "Design the outer carton for BBROSE Velvet Bloom… — carton")

    def test_reading_the_board_writes_nothing(self):
        from apps.dashboard import board
        from apps.pipeline.models import AgentLog, DesignTask, PackagingOutput
        self._age(self._task("queued", product=self.powder), hours=5)
        self._task("failed", product=self.powder)
        before = (DesignTask.objects.count(), AgentLog.objects.count(), PackagingOutput.objects.count(),
                  list(DesignTask.objects.order_by("pk").values_list("status", "updated_at")))
        board.board()
        after = (DesignTask.objects.count(), AgentLog.objects.count(), PackagingOutput.objects.count(),
                 list(DesignTask.objects.order_by("pk").values_list("status", "updated_at")))
        self.assertEqual(before, after)


class ShellAndBoardTests(TestCase):
    """THE ONE SHELL AND THE BOARD (the owner's answer to the UI directions of 2026-09-25: "B's board, C's design page",
    "C's look" — "Build it."). Every page draws one top bar with the three counts his rule (d) keeps always visible,
    from the board's one classification; the home is the board; Status is B's, in words; New design is where a design
    is started. Nothing here writes, and no page of the shell carries an inline style or an inline script."""

    PAGES = ("/dashboard/", "/dashboard/status/", "/dashboard/history/", "/dashboard/brand/", "/dashboard/materials/",
             "/dashboard/products/", "/dashboard/status/rulings/",
             "/dashboard/library/", "/dashboard/library/finished/",   # the Library's page and its finished designs
             # the programme's pages, in the one shell since the owner's goal of 2026-09-25
             "/dashboard/visual-quality/vq1/", "/dashboard/visual-quality/rbv3/", "/dashboard/design-requests/")

    def setUp(self):
        from django.contrib.auth.models import Group

        from apps.core.models import Brand, Product
        from apps.pipeline.models import DesignTask
        from apps.pipeline.permissions import ROLE_DESIGNER
        from apps.dashboard import board
        self.enterContext(patch.dict(board.OWNER_FOLD, {}, clear=True))    # a test database's numbers are not his
        self.user = User.objects.create_user("designer-shell", "shell@example.com", None)
        self.user.groups.add(Group.objects.get_or_create(name=ROLE_DESIGNER)[0])
        brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.powder = Product.objects.create(brand=brand, product_id="BBR-S-1", name="Focus Pressed Powder",
                                             name_ar="فوكس", category="CO", year=2026)
        self.review = DesignTask.objects.create(brand=brand, product=self.powder, design_target="product_container",
                                                task_text="A pressed face powder for BBROSE.", status="awaiting_gate_2")
        self.stopped = DesignTask.objects.create(brand=brand, design_target="packaging", status="failed",
                                                 task_text="a banana rice serum box",
                                                 error_message="Missing API key(s): ANTHROPIC_API_KEY (design directions)")
        self.choose = DesignTask.objects.create(brand=brand, design_target="packaging", status="awaiting_gate_1",
                                                task_text="a carton at its concepts")
        self.client.force_login(self.user)

    def test_every_page_draws_the_one_shell_with_the_three_counts(self):
        for url in self.PAGES:
            html = self.client.get(url).content.decode()
            self.assertIn('class="bar"', html, url)
            for words, n in (("Working on it", 0), ("Waiting for you", 2), ("Needs attention", 1)):
                self.assertRegex(html, r'%s <span class="n" data-count="[a-z]+">%d</span>' % (words, n), url)
            for place in ("Home", "Designs", "Library", "Status", "New design"):
                self.assertIn(">%s<" % place if place != "New design" else "New design</a>", html, url)

    def test_the_programmes_pages_say_where_they_stand_their_record_folded_and_a_closed_page_says_why(self):
        # [the owner's goal of 2026-09-25, (c) "One clean visual system" and (d) "Plain words everywhere": the programme's
        # pages were pages of their own; a page closed to an account was Django's bare "403 Forbidden"]
        import re
        vq1 = self.client.get("/dashboard/visual-quality/vq1/").content.decode()
        self.assertIn('<h1 class="h1">The bottle', vq1)
        self.assertIn('name="state" value="ACCEPTED"', vq1)                       # his decision, as it was
        self.assertIn('<details class="tech vq-fold">', vq1)                      # every stage, one click under
        rbv3 = self.client.get("/dashboard/visual-quality/rbv3/").content.decode()
        self.assertNotIn("ABSENT_BLOCKED", re.sub(r"<details.*?</details>", "", rbv3, flags=re.S))
        self.assertIn("ABSENT_BLOCKED", rbv3)
        self.assertIn('href="/intelligence/reviews/"', self.client.get("/dashboard/status/").content.decode())
        closed = self.client.get("/intelligence/reviews/")                         # this account is no reviewer
        self.assertEqual(closed.status_code, 403)
        page = closed.content.decode()
        self.assertIn('class="bar"', page)
        self.assertIn("It is for a design-intelligence reviewer", page)
        self.assertIn("REVIEWER_PROFILE_MISSING", page)                            # folded, still on the page

    def test_the_pills_open_their_short_lists_and_the_pulse_answers_with_the_same_counts(self):
        html = self.client.get("/dashboard/status/").content.decode()
        self.assertIn('id="drop-attn"', html)
        self.assertIn("The writing service had no key, so nothing was written", html)
        self.assertIn('href="/dashboard/designs/%d/"' % self.stopped.pk, html)
        # [the checklist of 2026-09-26: the pulse also carries the bell's number, pinned in WhatTheOldDashboardReachedTests]
        self.assertEqual(self.client.get("/dashboard/pulse/").json()["counts"], {"run": 0, "wait": 2, "attn": 1})

    def test_the_home_is_the_board(self):
        # [the owner's goal of 2026-10-29: Home switched to the chain] the board's cards are the rounds, on the lanes of
        # the designer flow, the stopped ones in Needs attention on top; the old tasks are Status's
        from apps.pipeline.models import Round
        drawing = _designer_round(self.user, name="A gloss being drawn")
        Round.objects.filter(pk=drawing.pk).update(state="running", current_step="designs")
        board_pick = _designer_round(self.user, state="awaiting_board_pick", name="A gloss at its boards")
        stopped = _designer_round(self.user, name="A stopped gloss")
        Round.objects.filter(pk=stopped.pk).update(state="failed", error_message="The designs could not be drawn.")
        made = _designer_round(self.user, name="A made gloss", made=True)
        html = self.client.get("/dashboard/").content.decode().partition('<main id="main"')[2]
        for words in ("Board", "Research and boards", "Designs and your pick", "Faces and files", "Files made",
                      "Needs attention", "Drawing three designs", "Pick one mood board", "The designs could not be drawn.",
                      "A gloss being drawn", "A gloss at its boards", "A made gloss"):
            self.assertIn(words, html)
        for record in (drawing, board_pick, stopped):
            self.assertIn('href="/dashboard/rounds/%d/"' % record.pk, html)
        self.assertIn('href="/dashboard/rounds/%d/built-files/"' % made.pk, html)
        self.assertNotIn('href="/dashboard/designs/%d/"' % self.review.pk, html)
        self.assertNotIn("awaiting_board_pick", html)

    def test_the_folded_tests_sit_at_the_foot_in_his_words(self):
        # his fold of the old tasks, "They are tests, not my work", is Status's now; [the owner's goal of 2026-10-29] on
        # the rounds' board, the retired rounds sit folded at the foot, in words, each opening as it always did
        from uuid import uuid4

        from apps.pipeline.models import Round
        retired = Round.objects.create(slug="retired-shell", request_key=str(uuid4()), created_by=self.user,
                                       product_brief={"name": "A retired gloss"}, state="failed")
        html = self.client.get("/dashboard/").content.decode()
        self.assertIn("Retired rounds (1)", html)
        self.assertIn("they ran on the retired pipeline", html)
        self.assertIn('href="/dashboard/rounds/%d/"' % retired.pk, html)

    def test_new_design_is_where_a_design_is_started_and_an_old_start_link_goes_there(self):
        self.assertIn('class="btn primary sm new-btn" href="/dashboard/new/"', self.client.get("/dashboard/").content.decode())
        html = self.client.get("/dashboard/new/").content.decode()      # [the designer flow of 2026-10-27: New design]
        self.assertIn('id="round-intake"', html)
        self.assertIn(">Start</button>", html)
        self.assertNotIn('id="task-input"', html)
        classic = self.client.get("/dashboard/new/classic/").content.decode()   # the classic start, kept and unlinked
        self.assertIn('id="task-input"', classic)
        self.assertIn(">Start the design</button>", classic)
        response = self.client.get("/dashboard/?from=7")
        self.assertEqual((response.status_code, response["Location"]), (302, "/dashboard/new/classic/?from=7"))

    def test_status_says_each_count_in_words_with_one_thing_to_do(self):
        html = self.client.get("/dashboard/status/").content.decode()
        self.assertIn("In plain words:", html)
        self.assertIn("2 designs wait for you", html)
        self.assertIn("1 needs your attention", html)
        self.assertIn("The writing service had no key, so nothing was written", html)
        self.assertIn("See why", html)
        self.assertIn("More about the system", html)

    def test_no_page_of_the_shell_carries_an_inline_style_or_script(self):
        import re
        for url in self.PAGES:
            html = self.client.get(url).content.decode()
            self.assertNotRegex(html, r'\sstyle="', url)
            scripts = re.findall(r"<script\b([^>]*)>", html)
            self.assertTrue(all("src=" in attrs or 'type="application/json"' in attrs for attrs in scripts),
                            (url, scripts))

    def test_signing_out_is_asked_once_and_a_look_changes_nothing(self):
        page = self.client.get("/accounts/logout/")
        self.assertEqual(page.status_code, 200)
        self.assertRegex(page.content.decode(), r'<form method="post" action="/accounts/logout/">')
        self.assertEqual(self.client.get("/dashboard/pulse/").status_code, 200)       # still signed in after the look
        self.assertEqual(self.client.post("/accounts/logout/").status_code, 302)
        self.assertEqual(self.client.get("/dashboard/pulse/").status_code, 302)       # signed out by the POST alone

    def test_the_mark_is_the_approved_master_or_nothing(self):
        # the approval lookup is off under the suite (config/settings.py): nothing is served, and the bar keeps its link
        self.assertEqual(self.client.get("/dashboard/brand/mark.svg").status_code, 404)

    def test_the_shell_writes_nothing(self):
        from apps.pipeline.models import AgentLog, DesignTask
        before = (DesignTask.objects.count(), AgentLog.objects.count(),
                  list(DesignTask.objects.order_by("pk").values_list("status", "updated_at")))
        for url in self.PAGES:
            self.client.get(url)
        self.client.get("/dashboard/pulse/")
        self.assertEqual(before, (DesignTask.objects.count(), AgentLog.objects.count(),
                                  list(DesignTask.objects.order_by("pk").values_list("status", "updated_at"))))


#: what the design loop offers on a lid's face, in the shape `exploration_render.knob_offer` answers (read from design
#: 110's offer, 2026-09-26, and cut down) — for the design page's tests, which stand it in rather than compose a face
_LID_OFFER = {
    "form": "face",
    "elements": [
        {"element": "ground", "field": "colour_ground", "words": "the lid's ground", "paints": "the lid's face",
         "standing": {"hexes": ["#FAF3EC"], "words": "Warm Cream #FAF3EC (Blush Core, Ground)"},
         "can_take_a_colour": True, "why_not": None},
        {"element": "rule", "field": "colour_rule", "words": "the rule", "paints": "the concept's rule",
         "standing": {"hexes": ["#C9A24B"], "words": "Rose Gold #C9A24B (Blush Core, Metallic)"},
         "can_take_a_colour": False,
         "why_not": "it prints in the concept's own foil on this design, so a colour on it cannot be seen"},
    ],
    "palette": [
        {"hex": "#8B3A52", "name": "Deep Rose", "system": "Blush Core", "also_in": [],
         "words": "Deep Rose #8B3A52 (Blush Core, Accent)"},
        {"hex": "#C9A24B", "name": "Rose Gold", "system": "Blush Core", "also_in": ["Nude Warm"],
         "words": "Rose Gold #C9A24B (Blush Core, Metallic)"},
    ],
    "roles": [
        {"role": "name", "field": "face_name", "words": "the name", "standing": {"stem": "Poppins-Light"},
         "offer": ["Poppins-Light", "AmaticSC-Bold"], "not_offered": []},
        {"role": "name_ar", "field": "face_name_ar", "words": "the Arabic name",
         "standing": {"stem": "NotoNaskhArabic-Regular"}, "offer": ["NotoNaskhArabic-Regular"],
         "not_offered": [{"stem": "Cairo-Bold", "face": "Cairo Bold",
                          "why": "EXPLORATION_FACE_CANNOT_SET_THIS_ROLE: REFUSED — Cairo (Cairo-Bold) cannot set the "
                                 "Arabic name: it lacks 36 of the letter shapes"}]},
    ],
    "faces": [{"family": "Poppins", "stem": "Poppins-Light", "roles": ["name"]},
              {"family": "Amatic SC", "stem": "AmaticSC-Bold", "roles": ["name"]},
              {"family": "Noto Naskh Arabic", "stem": "NotoNaskhArabic-Regular", "roles": ["name_ar"]}],
}


class DesignPageTests(TestCase):
    """C'S DESIGN PAGE (the owner's answer to the UI directions of 2026-09-25: "C's design page — pick an element and try
    colours and faces from a library that stays open"). A design's own address shows what it is, where it stands and what
    it has spent against its cap; its step is drawn by the page's scripts into the containers they always drew into; its
    concepts sit beside it; the library is open beside it; Adjust says what the design loop can try on THIS design, or
    why not, in words. The page writes nothing and carries no inline style or inline script."""

    def setUp(self):
        from django.contrib.auth.models import Group

        from apps.core.models import Brand, ColorSystem, Product
        from apps.pipeline.models import DesignTask, GeneratedImage
        from apps.pipeline.permissions import ROLE_DESIGNER
        from apps.dashboard import board
        self.enterContext(patch.dict(board.OWNER_FOLD, {}, clear=True))    # a test database's numbers are not his
        self.user = User.objects.create_user("designer-dp", "dp@example.com", None)
        self.user.groups.add(Group.objects.get_or_create(name=ROLE_DESIGNER)[0])
        self.brand = Brand.objects.create(name="BBROSE", master_brief="x")
        ColorSystem.objects.create(brand=self.brand, name="Blush Core", system_id="CS-001", status="canonical",
                                   palette=[{"name": "Deep Rose", "role": "Accent", "hex": "#8B3A52"},
                                            {"name": "Rose Gold", "role": "Metallic", "hex": "Metallic 10122 C"}],
                                   image_generation_context="blush")
        self.powder = Product.objects.create(brand=self.brand, product_id="BBR-DP-1", name="Focus Pressed Powder",
                                             name_ar="فوكس", category="CO", year=2026)
        self.review = DesignTask.objects.create(brand=self.brand, product=self.powder, status="awaiting_gate_2",
                                                design_target="packaging", task_text="A pressed powder carton")
        self.choosing = DesignTask.objects.create(brand=self.brand, product=self.powder, status="awaiting_gate_1",
                                                  design_target="packaging", task_text="A pressed powder carton")
        from django.conf import settings
        pictures = Path(settings.MEDIA_ROOT) / "generated"                  # the suite's own media root
        pictures.mkdir(parents=True, exist_ok=True)
        for task in (self.review, self.choosing):
            name = "generated/dp-%d.png" % task.pk
            (Path(settings.MEDIA_ROOT) / name).write_bytes(b"\x89PNG\r\n\x1a\n")
            GeneratedImage.objects.create(task=task, direction_name="Veil", prompt_used="p", image_file=name,
                                          is_approved=task is self.review)
        self.client.force_login(self.user)

    def _html(self, task):
        # [re-pinned: his last goal before the pitch, 2026-10-16, Step 1 (6)] the page with its Adjust panel in place,
        # as the browser shows it once the panel's controls arrive (``_design_page_as_shown``)
        return _design_page_as_shown(self.client, task.pk)

    def test_step1_6_the_page_shows_before_its_adjust_controls_are_worked_out(self):
        """[His last goal before the pitch, 2026-10-16, Step 1 (6): "The design page loads with the drawing visible
        fast (no blank seconds ...)".] The design page never works out the Adjust panel's controls — a lid's compose
        its face again, 20 s cold on design 141 — it says they are coming, and its panel's own address answers them."""
        from apps.dashboard import exploration_render, explorations
        with patch.object(exploration_render, "knob_offer", side_effect=AssertionError("worked out with the page")), \
                patch.object(exploration_render, "explorable", side_effect=AssertionError("worked out with the page")):
            html = self.client.get(f"/dashboard/designs/{self.review.pk}/").content.decode()
        self.assertIn('data-src="/dashboard/designs/%d/adjust/"' % self.review.pk, html)
        self.assertIn("Getting the controls ready", html)
        self.assertIn('id="library-panel"', html)
        with patch.object(exploration_render, "explorable", return_value={"form": True}), \
                patch.object(exploration_render, "knob_offer", return_value={"form": "dropper"}), \
                patch.object(exploration_render, "standing_values", return_value={"product_name": "Focus"}), \
                patch.object(explorations, "owner_refusal", return_value=""):
            data = self.client.get(f"/dashboard/designs/{self.review.pk}/adjust/").json()
        self.assertIn('id="adjust-form"', data["adjust"])
        self.assertNotIn("data-src", data["adjust"])
        self.assertIn('id="lib-colours"', data["library"])

    def test_a_folded_test_that_stopped_says_why_in_words_and_the_library_names_no_record_id(self):
        # [the owner's answer to the UI directions of 2026-09-25, (d) "Plain words everywhere. No engine codes on screen."]
        # a folded test's stop reached its page as the raw error; the library named each colour system by its id
        from apps.dashboard import board
        from apps.pipeline.models import DesignTask
        probe = DesignTask.objects.create(brand=self.brand, status="failed", design_target="packaging", task_text="a probe",
                                          error_message="Direction planning failed validation: TYPOGRAPHY_NOT_DISTINCT")
        with patch.dict(board.OWNER_FOLD, {probe.pk: "planning test"}, clear=True):
            html = self._html(probe)
        import json
        import re
        data = json.loads(re.search(r'<script id="design-page" type="application/json">(.*?)</script>', html, re.S).group(1))
        self.assertIn("their type was too alike", data["reason"])               # what the step's script says, in words
        self.assertIn("Blush Core", self._html(self.review))
        self.assertNotIn("CS-001", self._html(self.review))                      # its name, not its record's id

    def test_it_says_what_the_design_is_where_it_stands_and_what_it_spent(self):
        from decimal import Decimal

        from apps.pipeline.models import ApiCallRecord
        ApiCallRecord.objects.create(task=self.review, provider="openai", model="m", operation="render",
                                     cost_usd=Decimal("1.24"))
        html = self._html(self.review)
        for words in ("Focus Pressed Powder — carton", "فوكس", "Review the design", "$1.24 spent", "of its $25.00 cap",
                      "No. %d" % self.review.pk):
            self.assertIn(words, html)
        for container in ("step-line", "gate2-state", "mockup-view", "direction-view", "image-gallery", "profile-view",
                          "complete-state", "panel-center"):
            self.assertIn('id="%s"' % container, html)
        self.assertNotIn("awaiting_gate_2", html.split('<script id="status-words"')[0])

    def test_the_library_is_open_beside_the_design(self):
        html = self._html(self.review)
        self.assertIn('id="library-panel"', html)
        self.assertIn("Stays open while you design", html)
        self.assertIn('fill="#8B3A52"', html)                  # a colour of his own system, drawn as a shape
        self.assertIn("Rose Gold", html)                       # a metallic ink, named, never guessed as a colour
        for tab in ("Colours", "Faces", "Materials", "Past designs"):
            self.assertIn(">%s</button>" % tab, html)

    def test_only_materials_that_can_be_placed_are_offered(self):
        rows = [{"n": 1, "sha": "a" * 64, "name": "placeable.png", "subject": "a placeable picture", "drawable": True},
                {"n": 2, "sha": "b" * 64, "name": "reference.png", "subject": "a reference", "drawable": False}]
        with patch("apps.dashboard.materials_library.search", return_value={"rows": rows, "counts": {"placeable": 1}}):
            html = self._html(self.review)
        self.assertIn("/dashboard/materials/pictures/1-%s.png" % ("a" * 64), html)
        self.assertNotIn("b" * 64, html)
        self.assertIn("1 can be placed", html)

    def test_adjust_says_why_the_loop_cannot_try_a_carton(self):
        html = self._html(self.review)
        self.assertIn('id="adjust"', html)
        self.assertIn("drawn by the picture service, which costs money on every try", html)
        self.assertNotIn("EXPLORATION_RENDER", html)

    def test_adjust_offers_the_loops_knobs_where_it_can_draw_the_design(self):
        from apps.dashboard import exploration_render, explorations
        with patch.object(exploration_render, "explorable", return_value={"form": True}), \
                patch.object(exploration_render, "knob_offer", return_value={"form": "dropper"}), \
                patch.object(exploration_render, "standing_values", return_value={"product_name": "Focus"}), \
                patch.object(explorations, "owner_refusal", return_value=""):
            html = self._html(self.review)
        self.assertIn('action="/dashboard/history/tasks/%d/explore/"' % self.review.pk, html)
        self.assertIn('name="product_name"', html)
        self.assertIn("Try it", html)
        self.assertIn("More adjustments", html)                                     # the loop page fits the dropper
        with patch.object(exploration_render, "explorable", return_value={"form": True}), \
                patch.object(explorations, "owner_refusal", return_value="OWNER_ONLY: refused"):
            self.assertIn("Trying designs is the owner&#x27;s alone", self._html(self.review))

    def test_on_a_lids_face_adjust_offers_a_colour_for_each_element_and_a_face_for_the_name(self):
        # his pick (2026-09-25): "pick an element and try colours and faces from a library that stays open" — what the
        # design loop offers on a lid's face (exploration_render.knob_offer, stood in here in its own shape)
        from apps.dashboard import exploration_render, explorations
        with patch.object(exploration_render, "explorable", return_value={"form": True}), \
                patch.object(exploration_render, "knob_offer", return_value=_LID_OFFER), \
                patch.object(explorations, "owner_refusal", return_value=""):
            html = self._html(self.review)
        self.assertIn('<select name="colour_ground" class="field" data-kind="colour"', html)
        self.assertIn("As it stands — Warm Cream #FAF3EC (Blush Core, Ground)", html)
        self.assertIn('<option value="#8B3A52">Deep Rose #8B3A52 (Blush Core, Accent)</option>', html)
        self.assertNotIn('name="colour_rule"', html)                                # it prints in foil: said, not offered
        self.assertIn("<b>The rule</b> — it prints in the concept&#x27;s own foil on this design", html)
        self.assertIn('<select name="face_name"', html)
        self.assertIn("As it stands — Poppins Light", html)
        self.assertIn('<option value="AmaticSC-Bold">Amatic SC Bold</option>', html)
        self.assertIn("<b>The face of the Arabic name</b> — it stays in Noto Naskh Arabic Regular", html)
        self.assertIn("Cairo Bold: Cairo (Cairo-Bold) cannot set the Arabic name", html)   # why not, in words
        self.assertNotIn("EXPLORATION_", html)                                      # the refusal's code is not shown
        self.assertNotIn("More adjustments", html)                                  # the loop page does not fit a lid
        # the library tries on the element picked in Adjust — a metallic ink at the flat colour the drawing paints
        self.assertIn('data-colour="#8B3A52"', html)
        self.assertIn('data-colour="#C9A24B"', html)
        self.assertIn('src="/static/js/adjust.js', html)

    def test_the_page_hands_its_script_the_reason_and_the_look_again(self):
        from apps.pipeline.models import AgentLog, DesignTask, GeneratedImage, PackagingOutput
        stopped = DesignTask.objects.create(brand=self.brand, status="failed", design_target="packaging",
                                            task_text="a carton", error_message="Missing API key(s): X")
        data = _design_page_data(self.client.get(f"/dashboard/designs/{stopped.pk}/"))
        self.assertEqual((data["reason"], data["look_again"]),
                         ("The writing service had no key, so nothing was written", False))
        turned = DesignTask.objects.create(brand=self.brand, status="container_stage_visually_rejected",
                                           design_target="product_container", task_text="a bottle")
        image = GeneratedImage.objects.create(task=turned, direction_name="d", prompt_used="p")
        PackagingOutput.objects.create(task=turned, approved_image=image, spec_sheet={
            "container_reconstruction_rejected_x": {"decided_at": "2026-07-27T07:07:54+00:00"}})
        self.assertFalse(_design_page_data(self.client.get(f"/dashboard/designs/{turned.pk}/"))["look_again"])
        AgentLog.objects.create(task=turned, agent_name="Container", action="Container: reconstructed bottle concept sheet")
        self.assertTrue(_design_page_data(self.client.get(f"/dashboard/designs/{turned.pk}/"))["look_again"])
        from django.conf import settings
        (Path(settings.MEDIA_ROOT) / "dielines").mkdir(parents=True, exist_ok=True)
        (Path(settings.MEDIA_ROOT) / "dielines" / "again.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        PackagingOutput.objects.filter(task=turned).update(design_preview="dielines/again.png")
        self.assertEqual(_design_page_data(self.client.get(f"/dashboard/designs/{turned.pk}/"))["look_again_picture"],
                         "/files/dielines/again.png")

    def test_at_its_concept_step_the_concepts_are_the_stage_not_a_rail(self):
        self.assertIn('class="concepts"', self._html(self.review))                      # past it: the rail
        self.assertIn("/files/generated/dp-%d.png" % self.review.pk, self._html(self.review))
        self.assertNotIn('class="concepts"', self._html(self.choosing))                  # at it: the stage alone

    def test_the_page_carries_no_inline_style_or_script_and_writes_nothing(self):
        import re

        from apps.pipeline.models import AgentLog, DesignTask
        before = (DesignTask.objects.count(), AgentLog.objects.count(),
                  list(DesignTask.objects.order_by("pk").values_list("status", "updated_at")))
        html = self._html(self.review)
        self.assertNotRegex(html, r'\sstyle="')
        scripts = re.findall(r"<script\b([^>]*)>", html)
        self.assertTrue(all("src=" in a or 'type="application/json"' in a for a in scripts), scripts)
        self.assertEqual(before, (DesignTask.objects.count(), AgentLog.objects.count(),
                                  list(DesignTask.objects.order_by("pk").values_list("status", "updated_at"))))


class HisRulesTests(TestCase):
    """HIS RULES FOR THE INTERFACE, HELD WHERE A TEST CAN HOLD THEM (the owner's goal of 2026-09-25, (d), c50abc7):
    "Everything reachable in two clicks from home." — "Plain words everywhere. No engine codes on screen." — "What is
    running, what is waiting for me, and what failed are always visible." A crawl from home, two clicks deep, signed in
    as the owner, over a record holding a design at each place on the board — at its concepts, stopped with the codes a
    planner writes, being drawn, finished and approved: every kind of screen is reached within two clicks, and every page
    reached draws the three counts, carries no inline style or inline script, and shows no engine code, no machine's
    time and no fingerprint at rest — a fold's body ("What the record says") is one click under, not on screen, and a
    file is named by its file name. The crawl writes nothing. What a design page's own scripts draw is held by their
    browser tests; the pages a record opens one click further (a ruling, a project, a study) are reached from their
    lists."""

    maxDiff = None                                    # a failure names every page and every code it found

    #: never followed: signing out, the admin, files and pictures (a design's inspiration picture is served under /api/,
    #: §BH69(2)), the counts' JSON, the worker's probe (it asks the queue), and a link that switches the active brand
    SKIP = ("/accounts/logout", "/admin", "/media/", "/files/", "/static/", "/api/", "/dashboard/pulse/", "probe=",
            "brand=")
    SKIP_EXT = (".png", ".svg", ".jpg", ".jpeg", ".pdf", ".ai", ".zip", ".json", ".webp", ".gif", ".psd", ".eps")
    #: an engine code (CAPS_WITH_UNDERSCORES, snake_case — neither the stem of a file's name), a machine's time, a
    #: fingerprint, and the engine's names for its two stops
    CODE = (r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b(?!\.\w)|\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b(?!\.\w)"
            r"|\b\d{4}-\d\d-\d\dT\d\d|\b[0-9a-f]{16,}\b(?!\.\w)|\b[Gg]ate ?[12]\b")
    #: every kind of screen, reached within two clicks from home (a numbered page by its pattern)
    SCREENS = ("/dashboard/", "/dashboard/new/", "/dashboard/find/", "/dashboard/history/", "/dashboard/library/",
               "/dashboard/status/", "/dashboard/designs/<n>/", "/dashboard/history/tasks/<n>/",
               "/dashboard/history/concepts/", "/dashboard/history/projects/", "/dashboard/history/dieline-jobs/",
               "/dashboard/history/explorations/", "/dashboard/brand/", "/dashboard/brand/references/",
               "/dashboard/materials/", "/dashboard/products/", "/dashboard/library/finished/",
               # [the owner's goal of 2026-10-29] a finished design is a round whose files are made: its page and its
               # faces and files, where the Library's old approved outputs keep their own pages, unlisted
               "/dashboard/rounds/<n>/", "/dashboard/rounds/<n>/built-files/",
               "/dashboard/status/rulings/", "/dashboard/visual-quality/vq1/",
               "/dashboard/visual-quality/rbv3/", "/dashboard/design-requests/", "/intelligence/reviews/",
               "/intelligence/corpus/", "/intelligence/search/")

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._tmpd = tempfile.TemporaryDirectory()      # the register, the brain and the explorations it reads: its own
        root = Path(cls._tmpd.name)
        (root / "register.md").write_text("# Register\n\n## 2026-09-01 — OWNER RULING §BH90: THE FIRST\n\nits text\n")
        (root / "queue.md").write_text("# Queue\n\n## 2026-09-03 — A QUEUE ITEM\n\nwaiting for his eye\n")
        import sqlite3
        (root / "brain").mkdir()
        con = sqlite3.connect(root / "brain" / "brain.sqlite")
        con.execute("create table sections (id text, path text, status text, superseded_by text)")
        con.execute("insert into sections values ('§BH90', 'OWNER_BLOCKER_CLEARANCE.md', 'LIVE', null)")
        con.commit()
        con.close()
        (root / "brain" / "freshness.json").write_text('{"built_at": "2026-09-20T00:00:00Z"}')
        cls._override = override_settings(RULINGS_REGISTER=str(root / "register.md"), RULINGS_QUEUE=str(root / "queue.md"),
                                          RULINGS_BRAIN_DB=str(root / "brain" / "brain.sqlite"),
                                          OWNER_ACCOUNT="owner-rules", EXPLORATION_STORE=str(root / "explorations"))
        cls._override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._override.disable()
        cls._tmpd.cleanup()
        super().tearDownClass()

    def setUp(self):
        from django.contrib.auth.models import Group

        from apps.core.models import Brand, ColorSystem, Product
        from apps.dashboard import board
        from apps.pipeline.models import (AgentLog, DesignTask, GateDecision, GeneratedImage, PackagingOutput,
                                          PaletteMaterialArtifact)
        from apps.pipeline.permissions import ROLE_DESIGNER
        self.enterContext(patch.dict(board.OWNER_FOLD, {}, clear=True))    # a test database's numbers are not his
        self.user = User.objects.create_user("owner-rules", "rules@example.com", None)
        self.user.groups.add(Group.objects.get_or_create(name=ROLE_DESIGNER)[0])
        brand = Brand.objects.create(name="BBROSE", master_brief="x")
        ColorSystem.objects.create(brand=brand, name="Blush Core", system_id="CS-001", status="canonical",
                                   palette=[{"name": "Deep Rose", "role": "Accent", "hex": "#8B3A52"}],
                                   image_generation_context="x")
        product = Product.objects.create(brand=brand, product_id="BBR-R-1", name="Night Oil", category="SK", year=2026,
                                         width_mm=35, depth_mm=35, height_mm=100)

        def make(**kw):
            return DesignTask.objects.create(brand=brand, product=product, design_target="packaging", **kw)

        concepts = make(task_text="A carton for the night oil, at its concepts", status="awaiting_gate_1")
        GeneratedImage.objects.create(task=concepts, direction_name="Quiet Bloom", prompt_used="p", variation_number=1)
        from django.core.files.base import ContentFile                    # §BH69(2): a kept inspiration picture, read

        from apps.pipeline.models import InspirationReading, TaskReference
        pin = b"\x89PNG\r\n\x1a\n" + b"\x05" * 32
        kept = TaskReference(task=concepts, kind="inspiration_picture", original_filename="dribbble-shot.png",
                             media_type="image/png", file_size=len(pin), sha256="9" * 64)
        kept.image.save("dribbble-shot.png", ContentFile(pin), save=True)
        InspirationReading.objects.create(sha256="9" * 64, reading={
            "layout": "one mark centred on a quiet field", "mood": "calm and luxurious", "finish": "soft-touch matte",
            "type_style": "thin serif capitals", "colour_words": "blush with warm gold",
            "take": "quiet space around one gold line", "seen_not_taken": ["LUMIERE PARIS"]})
        make(task_text="A carton that stopped at its directions", status="failed",
             error_message="Direction planning failed validation: TYPOGRAPHY_NOT_DISTINCT; "
                           "PRODUCTION_RASTER_DEPENDENCY:direction[0]")
        make(task_text="A carton with no key to write with", status="failed",
             error_message="Missing API key(s): ANTHROPIC_API_KEY (design directions)")
        drawing = make(task_text="A carton being drawn", status="running")
        AgentLog.objects.create(task=drawing, agent_name="ARIA", action="Retrieved 4 similar products", level="info")
        AgentLog.objects.create(task=drawing, agent_name="ImageProducer",       # a check before spending, refused
                                action="Provider pre-spend validation FAILED — DUPLICATE_ACTIVE_GENERATION",
                                payload={"prespend": {"codes": ["DUPLICATE_ACTIVE_GENERATION"]}})
        finished = make(task_text="A carton for the night oil, finished", status="complete")
        chosen = GeneratedImage.objects.create(task=finished, direction_name="Nocturne", prompt_used="p", is_approved=True)
        PackagingOutput.objects.create(pk=finished.pk + 1000, task=finished, approved_image=chosen, spec_sheet={},
                                       is_final_approved=True)
        GateDecision.objects.create(task=finished, gate="gate_1", decision="approve", decided_by=self.user)
        GateDecision.objects.create(task=finished, gate="gate_2", decision="approve", decided_by=self.user)
        palette = DesignTask.objects.create(brand=brand, product=product, design_target="palette",
                                            task_text="A palette for the night oil", status="design_intent_confirmed")
        for name in ("NEUTRAL_ABS_MATTE", "OWNER_SUBSTITUTED_COLOUR"):                # its material studies
            PaletteMaterialArtifact.objects.create(
                task=palette, variant_name=name, material_contract_identity="a" * 16, design_graph_identity="b" * 16,
                geometry_identity="c" * 16, scene_identity="d" * 16, render_identity="e" * 16,
                evidence_path="docs/study.png", evidence_sha256="f" * 64)
        GateDecision.objects.create(task=palette, gate="gate_1", decision="approve", decided_by=self.user,
                                    notes="M6 product realization trace | draft 9b3603e17e85746c -> confirmed "
                                          "59d20e35f04554fd. This does not open GATE_2.")
        AgentLog.objects.create(task=palette, agent_name="ARIA", level="info",
                                action="ste carton/0.1 structure presented for review (UNCONFIRMED, hash "
                                       "dc9d799dea50a7441979ea9b2b505241)")
        # [the owner's goal of 2026-10-29: Home, Designs and the Library read the chain's rounds] a round waiting for
        # its pick and one whose files are made, in their own folder
        self.enterContext(override_settings(ROUND_ARTIFACT_ROOT=Path(self._tmpd.name) / "rounds"))
        _designer_round(self.user, name="A gloss at its pick")
        _designer_round(self.user, name="A made gloss", made=True)
        self.client.force_login(self.user)

    def _links(self, html, here):
        """Where a page's links and its finding forms go: every <a href> but a download, and every form that does not
        post."""
        import re
        from urllib.parse import urljoin, urlparse
        found = []
        for tag in re.findall(r"<a\b[^>]*>", html):
            href = re.search(r'\shref="([^"]*)"', tag)
            if href and not re.search(r"\sdownload\b", tag):
                found.append(href.group(1))
        for tag in re.findall(r"<form\b[^>]*>", html):
            action = re.search(r'\saction="([^"]*)"', tag)
            if action and 'method="post"' not in tag.lower():
                found.append(action.group(1))
        out = []
        for href in found:
            if not href or href.startswith(("#", "javascript:", "mailto:")):
                continue
            u = urlparse(urljoin("http://testserver" + here, href.replace("&amp;", "&")))
            path = u.path + ("?" + u.query if u.query else "")
            if u.netloc == "testserver" and not any(s in path for s in self.SKIP) and \
                    not u.path.lower().endswith(self.SKIP_EXT):
                out.append(path)
        return out

    @staticmethod
    def _shown(html):
        """What a page shows at rest: its text, its title and its placeholders — less its scripts and styles and the
        body of every closed fold (a fold's summary shows; a fold inside a closed one does not)."""
        from html.parser import HTMLParser

        class Shown(HTMLParser):
            def __init__(self):
                super().__init__(convert_charrefs=True)
                self.folds, self.summary, self.hidden, self.out = [], 0, 0, []

            def handle_starttag(self, tag, attrs):
                if tag == "details":
                    self.folds.append(not any(name == "open" for name, _value in attrs))
                self.summary += tag == "summary"
                self.hidden += tag in ("script", "style", "template")
                if not self.hidden and not sum(self.folds):
                    self.out += [value for name, value in attrs if name == "placeholder" and value]

            def handle_endtag(self, tag):
                if tag == "details" and self.folds:
                    self.folds.pop()
                self.summary -= tag == "summary"
                self.hidden -= tag in ("script", "style", "template")

            def handle_data(self, data):
                if not self.hidden and not sum(self.folds[:-1] if self.summary else self.folds):
                    self.out.append(data)

        shown = Shown()
        shown.feed(html)
        return " ".join(shown.out)

    def _crawl(self):
        """Every page within two clicks of home — home, then one click, then two — by its path: (status, html)."""
        seen, frontier, pages = {"/dashboard/"}, ["/dashboard/"], {}
        for click in range(3):
            reached = []
            for path in frontier:
                res = self.client.get(path, follow=True)
                html = res.content.decode()
                pages[path] = (res.status_code, html)
                if click < 2:
                    for link in self._links(html, path):
                        if link not in seen:
                            seen.add(link)
                            reached.append(link)
            frontier = reached
        return pages

    def _held(self, pages):
        """His rules on every page: the three counts, no inline style or script, no engine code at rest."""
        import re
        code = re.compile(self.CODE)
        found = {}
        for path, (status, html) in pages.items():
            self.assertIn(status, (200, 403), path)              # a page closed to an account says so, in the shell
            for key in ("run", "wait", "attn"):                  # running, waiting for him, and failed: always visible
                self.assertIn('data-count="%s"' % key, html, path)
            self.assertNotRegex(html, r'\sstyle="', path)
            self.assertEqual([s for s in re.findall(r"<script\b([^>]*)>", html)
                              if "src=" not in s and 'type="application/json"' not in s], [], path)
            codes = sorted({m.group(0) for m in code.finditer(self._shown(html))})
            # Owner Days 3/4 require the exact pinned bottle revision on these
            # review pages. Permit only the two actual released proof identities;
            # all other fingerprints and processing codes still fail this rule.
            if re.fullmatch(r"/dashboard/(?:serum|stand)-master/(?:\d+/)?", path):
                proof_pins = {
                    "1b0d5a9c760fa03c2e2662f58f38f3f6b014874a09266533f25cfdefc17f6467",
                    "95abc4d39ec648c664985f5fdfadfe1bddb24b8ae7b011a3abb4dbb7aa84df61",
                }
                codes = [c for c in codes if c not in proof_pins]
            if codes:
                found[path] = codes
        self.assertEqual(found, {})

    def test_as_the_owner_every_screen_is_two_clicks_from_home_and_every_page_keeps_his_rules(self):
        import re

        from apps.pipeline.models import AgentLog, DesignTask
        before = (AgentLog.objects.count(), list(DesignTask.objects.order_by("pk").values_list("status", "updated_at")))
        pages = self._crawl()
        kinds = {re.sub(r"/\d+(?=/)", "/<n>", p.split("?")[0]) for p in pages}
        self.assertEqual([s for s in self.SCREENS if s not in kinds], [], sorted(kinds))
        self._held(pages)
        self.assertEqual(before, (AgentLog.objects.count(),                  # the crawl writes nothing
                                  list(DesignTask.objects.order_by("pk").values_list("status", "updated_at"))))

    def test_an_account_that_is_not_the_owners_meets_the_same_rules_on_every_page_it_reaches(self):
        # (e): "someone who has never seen it can too" — with an account of their own, a designer's and not his
        self.client.force_login(User.objects.create_user("designer-stranger", "stranger@example.com", None))
        from django.contrib.auth.models import Group

        from apps.pipeline.permissions import ROLE_DESIGNER
        User.objects.get(username="designer-stranger").groups.add(Group.objects.get_or_create(name=ROLE_DESIGNER)[0])
        self._held(self._crawl())


class WhatTheOldDashboardReachedTests(TestCase):
    """WHAT THE OLD DASHBOARD REACHED, REACHED AGAIN (the owner's goal of 2026-09-25, (c) "Replace the old dashboard",
    read in its transcription as "every capability the old dashboard reaches still reached", §BH51(b)'s checklist of 178,
    read at a691f56 and now on 2026-09-26): the notification bell, in the one top bar on every page; the brand switch,
    where a design is started and on the Library's pages; "Only the designs I started" and a brand on Designs; a concept
    redraw's direction, by name, on the record; the Complete Product's stages on New design."""

    def setUp(self):
        from django.contrib.auth.models import Group

        from apps.core.models import Brand, Product
        from apps.dashboard import board
        from apps.pipeline.models import DesignTask, Notification
        from apps.pipeline.permissions import ROLE_DESIGNER
        self.enterContext(patch.dict(board.OWNER_FOLD, {}, clear=True))    # a test database's numbers are not his
        role = Group.objects.get_or_create(name=ROLE_DESIGNER)[0]
        self.user = User.objects.create_user("designer-reach", "reach@example.com", None)
        self.other = User.objects.create_user("designer-other", "other@example.com", None)
        for u in (self.user, self.other):
            u.groups.add(role)
        self.house = Brand.objects.create(name="BBROSE", master_brief="x")
        self.second = Brand.objects.create(name="PW Brand", master_brief="y")
        self.oil = Product.objects.create(brand=self.house, product_id="BBR-R-1", name="Night Oil", category="SK",
                                          year=2026)
        self.balm = Product.objects.create(brand=self.second, product_id="PW-1", name="Lip Balm", category="CO",
                                           year=2026)
        self.mine = DesignTask.objects.create(brand=self.house, product=self.oil, design_target="packaging",
                                              task_text="A carton for the night oil", status="awaiting_gate_1",
                                              created_by=self.user)
        self.theirs = DesignTask.objects.create(brand=self.second, product=self.balm, design_target="packaging",
                                                task_text="A carton for the lip balm", status="awaiting_gate_1",
                                                created_by=self.other)
        Notification.objects.all().delete()                    # the statuses above told their owners; each test says
        self.client.force_login(self.user)

    @staticmethod
    def _bell(html):
        return html.split('id="drop-note"', 1)[1].split('<details class="me">', 1)[0]

    @staticmethod
    def _main(html):
        return html.split("<main", 1)[1]

    def test_the_bell_says_what_happened_to_your_designs_on_every_page_and_counts_what_is_unread(self):
        from apps.dashboard import board
        from apps.pipeline.models import DesignTask, Notification
        Notification.objects.create(recipient=self.user, task=self.mine, kind="awaiting_gate_1", message="m")
        Notification.objects.create(recipient=self.user, task=self.mine, kind="failed", message="m", is_read=True)
        Notification.objects.create(recipient=self.other, task=self.theirs, kind="completed", message="m")
        probe = DesignTask.objects.create(brand=self.house, task_text="a planning probe", status="failed")
        Notification.objects.filter(task=probe).delete()                 # what its status told its owners
        Notification.objects.create(recipient=self.user, task=probe, kind="awaiting_gate_2", message="m")
        self.enterContext(patch.dict(board.OWNER_FOLD, {probe.pk: "planning probe"}))   # his fold: a test, not his work
        for url in ("/dashboard/", "/dashboard/status/", "/dashboard/history/", "/dashboard/library/",
                    f"/dashboard/designs/{self.mine.pk}/", "/dashboard/new/"):
            html = self.client.get(url).content.decode()
            self.assertIn('aria-controls="drop-note"', html, url)
            self.assertIn('<span class="n" data-unread>1</span>', html, url)
        bell = self._bell(self.client.get("/dashboard/").content.decode())
        self.assertIn(board.title_of(self.mine), bell)
        self.assertIn("Its concepts are ready — choose one", bell)                  # what happened, in words
        self.assertIn(f'href="/dashboard/designs/{self.mine.pk}/" data-note=', bell)  # it opens its design
        self.assertIn("It stopped", bell)                                           # a read one stays, not new
        self.assertEqual(bell.count('<span class="new-tag">new</span>'), 1)
        self.assertNotIn("It is finished", bell)                                   # another account's is not yours
        self.assertNotIn("It is drawn — review it", bell)                          # nor a folded test's
        self.assertIn("data-notes-read", bell)
        self.assertEqual(self.client.get("/dashboard/pulse/").json()["unread"], 1)
        self.client.post("/api/notifications/mark_read/", {}, content_type="application/json")
        self.assertEqual(self.client.get("/dashboard/pulse/").json()["unread"], 0)
        self.assertNotIn("data-notes-read", self._bell(self.client.get("/dashboard/").content.decode()))
        Notification.objects.filter(recipient=self.user).delete()
        self.assertIn("Nothing has happened to your designs yet.", self._bell(self.client.get("/dashboard/").content.decode()))

    def test_the_brand_switch_is_where_a_design_is_started_and_on_the_librarys_pages(self):
        from apps.core.models import Brand
        for url in ("/dashboard/new/classic/", "/dashboard/library/", "/dashboard/brand/"):
            html = self.client.get(url).content.decode()
            self.assertIn('<form class="brand-switch" method="get"', html, url)
            self.assertIn(f'<option value="{self.second.pk}">PW Brand</option>', html, url)
        html = self.client.get("/dashboard/new/classic/", {"brand": self.second.pk}).content.decode()
        self.assertIn(f'<option value="{self.second.pk}" selected>PW Brand</option>', html)
        self.assertEqual(self.client.session["brand_id"], self.second.pk)            # remembered, as it always was
        self.assertIn('"brand_id": %d' % self.second.pk, html)                      # a design started now is PW's
        self.assertIn("Lip Balm", self._main(html))                                 # and its products follow
        self.assertNotIn("Night Oil", self._main(html))
        Brand.objects.filter(pk=self.second.pk).delete()
        self.assertNotIn('class="brand-switch"', self.client.get("/dashboard/new/classic/").content.decode())   # one brand

    def test_designs_finds_only_the_designs_i_started_and_one_brands_designs(self):
        # [the owner's goal of 2026-10-29: Designs lists the chain's rounds] "Only the designs I started" over the rounds
        # an admin sees (every round); a round names no brand, so the brand filter went with the old tasks
        self.user.is_staff = True
        self.user.save()
        mine, theirs = _designer_round(self.user, name="My gloss"), _designer_round(self.other, name="Their gloss")
        html = self.client.get("/dashboard/history/").content.decode()
        self.assertIn('name="mine"', html)
        self.assertNotIn('<select id="brand" name="brand"', html)
        every = self._main(html)
        self.assertIn(f"/dashboard/rounds/{mine.pk}/", every)
        self.assertIn(f"/dashboard/rounds/{theirs.pk}/", every)
        only = self._main(self.client.get("/dashboard/history/", {"mine": "1"}).content.decode())
        self.assertIn(f"/dashboard/rounds/{mine.pk}/", only)
        self.assertNotIn(f"/dashboard/rounds/{theirs.pk}/", only)
        self.assertEqual(self.client.session.get("brand_id"), None)                 # a filter, never a switch

    def test_a_concept_redraw_names_the_direction_it_drew_for_on_the_record(self):
        from apps.pipeline.models import CreativeBrief, Gate1RegenerationJob
        CreativeBrief.objects.create(task=self.mine, directions=[{"direction_id": "d2", "name": "Quiet Bloom"}])
        Gate1RegenerationJob.objects.create(task=self.mine, direction_id="d2", influence_plan_hash="a" * 64)
        html = self.client.get(f"/dashboard/history/tasks/{self.mine.pk}/").content.decode()
        self.assertIn("for the direction Quiet Bloom", html)
        self.assertIn("<p>direction d2</p>", html)                                  # its record, folded

    def test_new_design_loads_the_complete_products_stages_before_its_own_script(self):
        html = self.client.get("/dashboard/new/classic/").content.decode()
        self.assertIn("js/project.js", html)
        self.assertLess(html.index("js/project.js"), html.index("js/poll.js"))


class InspirationPictureTests(TestCase):
    """§BH69(2) — AN INSPIRATION PICTURE WHEN HE STARTS A DESIGN (the owner's goal of 2026-09-26): "An upload box on New
    design ... one or more pictures"; "The system reads each picture and shows me, in words, what it took from it
    (layout, colours, mood, finish, type style), before it designs"; "Tell me the cost per picture read." The start page
    carries one box for every kind of design; each picture is read at once into words — its colours as words, never as
    codes — and the read is on the ledger, unbound until Start joins it to its design; a picture read before costs
    nothing; what cannot be read is refused by name."""

    READING = {"layout": "a centred mark on a wide quiet field", "mood": "calm and luxurious",
               "finish": "soft-touch matte with a thin gold foil line", "type_style": "thin serif capitals",
               "colour_words": "blush with warm gold", "take": "quiet space around one gold line",
               "seen_not_taken": ["LUMIERE PARIS"]}

    def setUp(self):
        from django.contrib.auth.models import Group

        from apps.core.models import Brand, Product
        from apps.dashboard import board
        from apps.pipeline.permissions import ROLE_DESIGNER
        self.enterContext(patch.dict(board.OWNER_FOLD, {}, clear=True))
        from django.core.cache import cache
        cache.delete("pipeline:spend_estimates/2")          # the measured costs are cached for a minute
        self.user = User.objects.create_user("designer-inspire", "inspire@example.com", None)
        self.user.groups.add(Group.objects.get_or_create(name=ROLE_DESIGNER)[0])
        self.brand = Brand.objects.create(name="BBROSE", master_brief="x")
        Product.objects.create(brand=self.brand, product_id="BBR-I-1", name="Night Oil", category="SK", year=2026)
        self.client.force_login(self.user)

    @staticmethod
    def _png(colour=(242, 212, 215), size=(60, 40)):
        import io

        from PIL import Image
        out = io.BytesIO()
        Image.new("RGB", size, colour).save(out, format="PNG")
        return out.getvalue()

    def _reply(self):
        import json
        from unittest.mock import MagicMock
        return MagicMock(content=[MagicMock(type="text", text=json.dumps(self.READING))],
                         usage=MagicMock(input_tokens=1400, output_tokens=320))

    def _read(self, data, name="pin.png"):
        from django.core.files.uploadedfile import SimpleUploadedFile
        return self.client.post("/api/inspiration/read/", {"picture": SimpleUploadedFile(name, data, "image/png")})

    def test_new_design_offers_one_inspiration_box_for_every_kind_of_design_and_says_what_a_read_costs(self):
        html = self.client.get("/dashboard/new/classic/").content.decode()
        box = " ".join(html.split('id="inspiration-box"', 1)[1].split("</fieldset>", 1)[0].split())
        self.assertIn('data-kind="inspiration_picture"', html)
        self.assertIn("Reading is reserved within the rescue budget after Start", box)       # no read on the ledger yet
        self.assertIn("never drawn from", box)
        container_inputs = html.split('id="container-inputs"', 1)[1].split('id="ref-held-notice"', 1)[0]
        self.assertNotIn('id="inspiration-box"', container_inputs)                  # outside the container's inputs
        self.assertNotIn('data-kind="inspiration"', html)                           # the old zone is not drawn
        self.assertLess(html.index("js/inspiration.js"), html.index("js/poll.js"))

    def test_a_picture_is_read_into_words_its_colours_as_words_and_its_read_on_the_ledger(self):
        from apps.pipeline.models import ApiCallRecord, InspirationReading
        with patch("apps.pipeline.services.claude_service._get_client") as client, \
                override_settings(ANTHROPIC_API_KEY="k"):
            client.return_value.messages.create.return_value = self._reply()
            first = self._read(self._png())
            again = self._read(self._png(), name="the-same-picture.png")
        self.assertEqual(first.status_code, 200)
        data = first.json()
        self.assertEqual(data["taken"]["take"], "quiet space around one gold line")
        self.assertEqual(data["taken"]["colour_words"], "blush with warm gold")      # colours said in words,
        self.assertNotIn("colours", data["taken"])                                   # never as codes (§BH69(2),
        self.assertNotRegex(data["words"], r"#[0-9A-Fa-f]{6}")                       # withdrawn: see inspiration.py)
        self.assertEqual(data["seen_not_taken"], ["LUMIERE PARIS"])
        self.assertFalse(data["read_before"])
        call = ApiCallRecord.objects.get(operation="inspiration_read")
        self.assertIsNone(call.task_id)                                            # unbound until Start
        self.assertGreater(call.cost_usd, 0)
        self.assertEqual(data["cost_usd"], str(call.cost_usd))
        self.assertTrue(again.json()["read_before"])                                # the same picture: read once
        self.assertEqual(ApiCallRecord.objects.filter(operation="inspiration_read").count(), 1)
        self.assertEqual(InspirationReading.objects.count(), 1)
        sent = client.return_value.messages.create.call_args.kwargs
        self.assertLessEqual(max(__import__("json").dumps(sent).count("base64"), 1), 1)
        html = " ".join(self.client.get("/dashboard/new/classic/").content.decode().split())
        self.assertIn("Reading is reserved within the rescue budget after Start", html)

    def test_what_cannot_be_read_is_refused_by_name_and_nothing_is_spent(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from apps.pipeline.models import ApiCallRecord
        pdf = self.client.post("/api/inspiration/read/", {
            "picture": SimpleUploadedFile("brief.pdf", b"%PDF-1.4\n" + b"x" * 64, "application/pdf")})
        self.assertEqual(pdf.status_code, 400)
        self.assertIn("cannot be read as a picture", pdf.json()["words"])
        with patch("apps.pipeline.services.cost_ledger.daily_budget_exceeded", return_value=True), \
                override_settings(ANTHROPIC_API_KEY="k"):
            capped = self._read(self._png((10, 20, 30)))
        self.assertEqual(capped.status_code, 429)
        self.assertIn("rescue budget", capped.json()["words"])
        with override_settings(ANTHROPIC_API_KEY=""):
            keyless = self._read(self._png((30, 20, 10)))
        self.assertEqual((keyless.status_code, keyless.json()["error"]), (409, "NO_READING_KEY"))
        self.assertFalse(ApiCallRecord.objects.exists())

    def test_start_carries_the_pictures_with_any_design_and_their_reads_become_its_spend(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from apps.pipeline.models import ApiCallRecord, DesignTask, TaskReference
        png = self._png((200, 170, 120))
        with patch("apps.pipeline.services.claude_service._get_client") as client, \
                override_settings(ANTHROPIC_API_KEY="k"):
            client.return_value.messages.create.return_value = self._reply()
            self.assertEqual(self._read(png).status_code, 200)
        with patch("apps.core.health.worker_available", return_value=True), \
                patch("apps.pipeline.tasks.run_aria_pipeline.delay"), \
                patch("django.db.transaction.on_commit", side_effect=lambda f: f()):
            made = self.client.post("/api/tasks/create/", {
                "task_text": "a carton for the night oil", "brand_id": self.brand.pk, "design_target": "packaging",
                "inspiration_picture": SimpleUploadedFile("pin.png", png, "image/png")})
        self.assertEqual(made.status_code, 201)
        task = DesignTask.objects.get(pk=made.json()["task_id"])
        ref = TaskReference.objects.get(task=task)
        self.assertEqual((ref.kind, len(ref.sha256)), ("inspiration_picture", 64))
        self.assertEqual(ApiCallRecord.objects.get(operation="inspiration_read").task_id, task.pk)
        seven = [SimpleUploadedFile("p%d.png" % i, self._png((i, i, i)), "image/png") for i in range(7)]
        with patch("apps.core.health.worker_available", return_value=True):
            over = self.client.post("/api/tasks/create/", {"task_text": "x", "brand_id": self.brand.pk,
                                                           "design_target": "packaging", "inspiration_picture": seven})
        self.assertEqual(over.status_code, 400)
        self.assertIn("at most 6", over.json()["words"])

    # --- §BH69(2) on a design: kept with it, seen on its page and its record, and added on its Adjust panel ---------

    def _design(self, status, target="social_media", **kw):
        from apps.pipeline.models import DesignTask
        return DesignTask.objects.create(brand=self.brand, design_target=target, task_text="a post for the night oil",
                                         status=status, created_by=self.user, **kw)

    def _keep(self, task, data=None, name="pin.png"):
        """A kept inspiration picture with its reading — as Start or the Adjust panel leaves them."""
        from django.core.files.base import ContentFile

        from apps.pipeline.models import InspirationReading, TaskReference
        from apps.pipeline.services import inspiration
        data = data or self._png()
        ref = TaskReference(task=task, kind=inspiration.KIND, original_filename=name, media_type="image/png",
                            file_size=len(data), sha256=inspiration.sha256_of(data))
        ref.image.save(name, ContentFile(data), save=True)
        InspirationReading.objects.get_or_create(sha256=ref.sha256, defaults={"reading": dict(self.READING)})
        return ref

    @staticmethod
    def _section(html, start, end):
        return " ".join(html.split(start, 1)[1].split(end, 1)[0].split())

    def test_a_design_shows_its_kept_pictures_with_what_was_taken_on_its_page_and_its_record(self):
        from django.contrib.auth.models import Group

        from apps.pipeline.permissions import ROLE_DESIGNER
        task = self._design("awaiting_gate_1")
        ref = self._keep(task, name="dribbble-shot.png")
        url = "/api/tasks/%d/references/%d/" % (task.pk, ref.pk)
        for page, end in (("/dashboard/designs/%d/" % task.pk, "</section>"),
                          ("/dashboard/history/tasks/%d/" % task.pk, '<h2 id="concepts">')):
            html = self.client.get(page).content.decode()
            kept = self._section(html, 'id="inspiration"', end)
            self.assertIn("dribbble-shot.png", kept, page)
            self.assertIn("What the design takes: quiet space around one gold line", kept, page)
            self.assertIn("Seen, and never copied: LUMIERE PARIS", kept, page)
            self.assertIn("blush with warm gold", kept, page)            # its colours, in words
            self.assertIn('src="%s"' % url, kept, page)                  # served to whoever started it — never /files/
            self.assertNotIn("/files/", kept, page)
        design = self.client.get("/dashboard/designs/%d/" % task.pk).content.decode()
        self.assertNotIn('id="inspiration-box"', design)                 # no Adjust panel at its concepts: no box
        other = User.objects.create_user("designer-other", "other@example.com", None)
        other.groups.add(Group.objects.get_or_create(name=ROLE_DESIGNER)[0])
        self.client.force_login(other)
        kept = self._section(self.client.get("/dashboard/designs/%d/" % task.pk).content.decode(),
                             'id="inspiration"', "</section>")
        self.assertIn("quiet space around one gold line", kept)          # its words, to anyone
        self.assertNotIn(url, kept)                                      # its picture, to those it is served to
        self.assertIn("shown to the person who started this design", kept)

    def test_the_adjust_panel_offers_the_box_outside_its_free_form_and_says_what_a_picture_added_there_does(self):
        from apps.dashboard import views as dashboard_views
        from apps.pipeline.services import inspiration
        self.assertEqual(tuple(dashboard_views.ADJUSTABLE_STATUSES), tuple(inspiration.ADD_STATUSES))
        cases = ((self._design("awaiting_gate_2"), "Its words go into new concepts if you ask for changes"),
                 (self._design("awaiting_gate_2", target="packaging"), "nothing from here draws a new one"),
                 (self._design("container_stage_visually_rejected", target="product_container"),
                  "This design goes no further as it is"))
        for task, said in cases:
            # [re-pinned: Step 1 (6)] the panel as the browser shows it once its controls arrive
            html = _design_page_as_shown(self.client, task.pk)
            panel = self._section(html, 'id="adjust"', "</section>")
            box = self._section(panel, 'id="inspiration-box"', "</fieldset>")
            self.assertIn(said, box, task.design_target)
            self.assertIn("Reading is reserved within the rescue budget when you add a picture", box)
            self.assertIn('data-task="%d"' % task.pk, panel)
            self.assertIn("js/inspiration.js", html)
        tried = dict(shown=True, available=True, form="dropper", reason="", notes=[], tries=0,
                     loop_url="/dashboard/history/tasks/%d/loop/" % cases[0][0].pk,
                     knobs=[{"name": "product_name", "label": "The name", "standing": "Night Oil"}])
        with patch.object(dashboard_views, "_adjust_offer", return_value=tried):
            html = _design_page_as_shown(self.client, cases[0][0].pk)           # [re-pinned: Step 1 (6)]
        form = html.split('id="adjust-form"', 1)[1].split("</form>", 1)[0]
        self.assertNotIn('type="file"', form)                            # a try never carries a picture
        self.assertLess(html.index("</form>", html.index('id="adjust-form"')), html.index('id="inspiration-box"'))
        self.assertIn("a try above stays free and never uses it", " ".join(html.split()))

    def test_a_picture_added_on_the_adjust_panel_is_read_against_the_design_and_kept_once_read(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from apps.pipeline.models import AgentLog, ApiCallRecord, TaskReference
        task = self._design("awaiting_gate_2")
        door = "/api/tasks/%d/inspiration/" % task.pk

        def add(data, name="pin.png"):
            return self.client.post(door, {"picture": SimpleUploadedFile(name, data, "image/png")})
        with patch("apps.pipeline.services.claude_service._get_client") as client, \
                override_settings(ANTHROPIC_API_KEY="k"):
            client.return_value.messages.create.return_value = self._reply()
            first = add(self._png())
            again = add(self._png(), name="the-same.png")
            client.return_value.messages.create.side_effect = RuntimeError("the reading service is down")
            failed = add(self._png((1, 2, 3)))
        self.assertEqual(first.status_code, 200)
        data = first.json()
        ref = TaskReference.objects.get(task=task)
        self.assertEqual((ref.kind, ref.sha256), ("inspiration_picture", data["sha256"]))
        self.assertEqual(data["url"], "/api/tasks/%d/references/%d/" % (task.pk, ref.pk))
        self.assertEqual(data["taken"]["take"], "quiet space around one gold line")
        call = ApiCallRecord.objects.get(operation="inspiration_read")
        self.assertEqual(call.task_id, task.pk)                          # the design's own spend
        self.assertTrue(AgentLog.objects.filter(task=task, action__contains="inspiration picture was added").exists())
        self.assertEqual((again.status_code, again.json()["error"]), (409, "INSPIRATION_KEPT_ALREADY"))
        self.assertEqual(failed.status_code, 502)                        # a read that fails keeps nothing
        self.assertEqual(TaskReference.objects.filter(task=task).count(), 1)
        self.assertEqual(ApiCallRecord.objects.filter(operation="inspiration_read").count(), 1)

    def test_the_adjust_panels_door_refuses_by_name_before_any_read(self):
        from django.contrib.auth.models import Group
        from django.core.files.uploadedfile import SimpleUploadedFile

        from decimal import Decimal

        from apps.pipeline.models import ApiCallRecord, TaskReference
        from apps.pipeline.permissions import ROLE_DESIGNER
        from apps.pipeline.services import inspiration

        def add(task):
            return self.client.post("/api/tasks/%d/inspiration/" % task.pk,
                                    {"picture": SimpleUploadedFile("pin.png", self._png((9, 9, 9)), "image/png")})
        at_concepts = self._design("awaiting_gate_1")
        full = self._design("awaiting_gate_2")
        for i in range(inspiration.MAX_PICTURES):
            self._keep(full, data=self._png((i, 40, 40)), name="p%d.png" % i)
        spent = self._design("awaiting_gate_2")
        ApiCallRecord.objects.create(task=spent, provider="openai", model="gpt-image-1", operation="image_generation",
                                     cost_usd=Decimal("99"))
        with patch("apps.pipeline.services.claude_service._get_client") as client, \
                override_settings(ANTHROPIC_API_KEY="k"):
            client.return_value.messages.create.return_value = self._reply()
            self.assertEqual(add(at_concepts).json()["error"], "INSPIRATION_NOT_ON_THIS_STEP")
            self.assertIn("at most 6", add(full).json()["words"])
            self.assertEqual(add(spent).json()["error"], "TASK_BUDGET_EXCEEDED")
            other = User.objects.create_user("designer-not-his", "nh@example.com", None)
            other.groups.add(Group.objects.get_or_create(name=ROLE_DESIGNER)[0])
            self.client.force_login(other)
            self.assertEqual(add(self._design("awaiting_gate_2")).status_code, 403)
            client.return_value.messages.create.assert_not_called()
        self.assertFalse(ApiCallRecord.objects.filter(operation="inspiration_read").exists())
        self.assertEqual(TaskReference.objects.filter(task=full).count(), inspiration.MAX_PICTURES)


class HisFoldOfDesign118Tests(SimpleTestCase):
    """His word after the fix for design 118, 2026-10-03 (OWNER_BLOCKER_CLEARANCE.md): "Fold 118 away as a test." """

    def test_his_word_design_118_is_folded_away_as_a_test(self):
        """Design 118 — his Rose Glaze Lip Gloss, started as Packaging where he meant a Complete Product — is folded
        away as his tests are: in his fold by its number, under its own group's words, his fold of 2026-09-25 as it
        was; nothing of it deleted (the fold is a reading of the board, never a write)."""
        from apps.dashboard import board
        assert board.HIS_FOLD_2026_10_03 == {118: "test"}
        assert board.OWNER_FOLD[118] == "test" and board.FOLD_GROUP_WORDS["test"] == "Your tests"
        assert {k: v for k, v in board.OWNER_FOLD.items() if k not in (118, 120, 121)} == board.HIS_FOLD

    def test_his_goal_of_2026_10_06_item_4_design_120_is_folded_away_as_a_test(self):
        """His goal of 2026-10-06, item 4: "Fold design 120 away as a test." Folded as 118 is: by its number, under
        "Your tests", nothing of it deleted — and nothing else of his fold moves."""
        from apps.dashboard import board
        assert board.HIS_FOLD_2026_10_06 == {120: "test"}
        assert board.OWNER_FOLD[120] == "test" and board.OWNER_FOLD[118] == "test"
        assert {k: v for k, v in board.OWNER_FOLD.items() if k not in (118, 120, 121)} == board.HIS_FOLD

    def test_his_word_of_2026_10_07_design_121_is_folded_away_as_a_test(self):
        """His word after the fixes for design 121, 2026-10-07: "Fold 121 away as a test." Folded as 118 and 120 are: by
        its number, under "Your tests", nothing of it deleted — and nothing else of his fold moves."""
        from apps.dashboard import board
        assert board.HIS_FOLD_2026_10_07 == {121: "test"}
        assert [board.OWNER_FOLD[n] for n in (118, 120, 121)] == ["test"] * 3
        assert board.FOLD_GROUP_WORDS["test"] == "Your tests"
        assert {k: v for k, v in board.OWNER_FOLD.items() if k not in (118, 120, 121)} == board.HIS_FOLD
