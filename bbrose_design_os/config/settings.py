"""Django settings for bbrose_design_os."""
import os
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

# The reviewer authorization policy is a pure-stdlib module INSIDE this app package
# (apps/accounts/authz_policy.py) — the deploy needs nothing beyond bbrose_design_os/.
# (DIP-1A-2 removed an earlier repo-root sys.path insert that had temporarily pointed the
# accounts app at tools/dip0c/authz.py; the audit tool now re-exports FROM the app.)

env = environ.Env(
    DEBUG=(bool, False),
)
ENV_FILE = BASE_DIR / ".env"

# A11 — OWNER RULED 2026-08-27, after the finding upgraded it from tidy-up to
# gate-blocking. `read_env` declines to overwrite a name that is ALREADY in
# os.environ, and a name can be present and EMPTY. A harness that exports
# `ANTHROPIC_API_KEY=` (present, zero-length) therefore shadows the real key in
# .env for the life of the process, and every credential-dependent read returns
# "". That was MEASURED, not supposed: with the tree otherwise untouched,
# unsetting the one variable turned three red suite tests green
# (test_composite_project's 409, and both test_vq2_* secret tests).
#
# A zero-length value carries no configuration. It is indistinguishable from
# absent at every `env(name, default=...)` call, and it is worse than absent at
# every call without a default, because it silences the .env file rather than
# falling back to it. So the empties are dropped BEFORE read_env and the file
# is allowed to win.
#
# Note what this deliberately is NOT: `read_env(..., overwrite=True)`. That
# would let .env beat a REAL exported value, which is the opposite of what an
# operator means by exporting one. The rule here is narrower and reads the same
# way in both directions — an empty export is not an instruction, a non-empty
# export still outranks the file.
for _empty_name in [_k for _k, _v in os.environ.items() if _v == ""]:
    del os.environ[_empty_name]

environ.Env.read_env(ENV_FILE)

SECRET_KEY = env("SECRET_KEY")

# --- DIP-1A: decision-event signing -------------------------------------------
# A DEDICATED secret, deliberately NOT SECRET_KEY. Reusing SECRET_KEY would mean that
# anything able to forge a session could also forge a decision event, and the two must
# fail independently.
#
# Shape: DECISION_EVENT_HMAC_KEYS is a JSON object {key_id: secret}; only
# DECISION_EVENT_ACTIVE_KEY_ID signs new events, while every other key stays
# VERIFICATION-ONLY so a rotation never invalidates history.
#
# Absent by default: an unconfigured instance CANNOT create decision events, and that is
# the correct failure mode. A system check reports it (error in production, warning in
# development).
DECISION_EVENT_HMAC_KEYS = env("DECISION_EVENT_HMAC_KEYS", default="")
DECISION_EVENT_ACTIVE_KEY_ID = env("DECISION_EVENT_ACTIVE_KEY_ID", default="")

# --- DIP-1A-5A: bootstrap lifecycle -------------------------------------------
# Pre-ledger reviewer bootstrap is a deliberate, deployment-gated ceremony, OFF by
# default: it must be explicitly enabled, run by a named active superuser, and it closes
# permanently after the first protected role-management decision. Break-glass reopening is
# a separate, also-off-by-default flag that produces a CRITICAL audit record.
BOOTSTRAP_ENABLED = env.bool("BOOTSTRAP_ENABLED", default=False)
BOOTSTRAP_BREAK_GLASS_ENABLED = env.bool("BOOTSTRAP_BREAK_GLASS_ENABLED", default=False)

# --- DIP-1A-BOOTSTRAP-CORR-2: single-operator local ceremony -------------------
# A SECOND, independent flag. The two-person ceremony and the single-operator one are
# different acts with different honesty properties, so enabling one must never enable the
# other. Both default off; system checks refuse this one outside a classified local
# development environment.
BOOTSTRAP_SINGLE_OPERATOR_ENABLED = env.bool(
    "BOOTSTRAP_SINGLE_OPERATOR_ENABLED", default=False)
# The environment's own declaration of what it is. Never inferred from DEBUG or from a
# loopback database address — a tunnelled production database also answers on loopback.
ENVIRONMENT = env("ENVIRONMENT", default="UNCLASSIFIED")
# §BH54(i), OWNER RULED 2026-09-18: "EXPLORATIONS ARE MINE. Served to the owner account only; any other signed-in
# account is refused by name." The system had no notion of an owner account (no setting, no group, the authz owner
# role never bound; every act of his on the record is by one username). This names it, by environment, never in the
# repository; UNSET means explorations are served to nobody — fail-closed, and the refusal says so.
OWNER_ACCOUNT = env("OWNER_ACCOUNT", default="")
# Databases the single-operator ceremony may run against. An exact allow-list: a name not
# listed here is refused even in a local environment.
LOCAL_DEVELOPMENT_DATABASES = env.list(
    "LOCAL_DEVELOPMENT_DATABASES", default=["bbrose_db"])

# Milestone 14.1: DEBUG is a plain boolean env var. env.bool coerces the usual
# truthy/falsey spellings (1/0/true/false/yes/no/on/off); the old ambient-value
# coercion shim is gone.
DEBUG = env.bool("DEBUG", default=False)

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "apps.core",
    "apps.pipeline",
    "apps.dashboard",
    "apps.accounts",
    "apps.dielines",
    "apps.ire",
    "apps.intelligence",
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "apps.core.middleware.RequestIDMiddleware",   # Milestone 14.1: request ids
    # REPORT-ONLY, never enforcing — see the class docstring for the 101
    # inline style attributes that are the reason, and for why no
    # `'unsafe-inline'` escape hatch is offered.
    "apps.core.middleware.ContentSecurityPolicyMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.pipeline.hybrid_boundary.HybridBoundaryMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# Day 2: bounded authored-serum preview. Existing tasks retain their legacy route.
HYBRID_BOTTLE_ENABLED = env.bool("HYBRID_BOTTLE_ENABLED", default=True)

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.pipeline.context_processors.frontend_build",
                # the owner's goal of 2026-09-25, (d): the three counts in every page's top bar (lazy — only a page
                # that draws the shell reads them)
                "apps.dashboard.context_processors.shell",
            ],
        },
    },
]

# 2A-6E-CORR-3 §7: Gate-1 reference regeneration mode. "dry_run" (default)
# validates the complete click-to-backend path and returns a diagnostic
# response WITHOUT creating a job, enqueuing Celery or calling a provider.
# Set GATE1_REGENERATION_MODE=live only after the user verifies
# DRY_RUN_ACCEPTED in a real browser.
GATE1_REGENERATION_MODE = env("GATE1_REGENERATION_MODE", default="dry_run")

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": env.db("DATABASE_URL"),
}

# --- database transport policy (Phase 2A-6B §8) ------------------------------
# libpq negotiates GSSAPI/Kerberos when opening a connection, and on macOS that
# path goes through XPC — which is NOT fork-safe. A Celery prefork child that
# opens a fresh connection dies with SIGSEGV in pg_GSS_have_cred_cache ->
# gss_acquire_cred -> xpc_connection_resume, with no Python traceback (found by
# the 2A-6A activation smoke test, confirmed from the macOS crash report).
#
# `gssencmode=disable` is the LOCAL fork-safety workaround. It must never
# become a silent universal production default: a shared deployment has to
# state its transport policy deliberately, and system checks refuse an
# ambiguous one (see apps/dielines/checks.py).
#
# TLS is configured INDEPENDENTLY via DB_SSLMODE — disabling GSS encryption
# says nothing about transport encryption, and the two must not be conflated.
DB_GSSENCMODE = env("DB_GSSENCMODE", default="").strip()
DB_SSLMODE = env("DB_SSLMODE", default="").strip()

if not DB_GSSENCMODE and ENVIRONMENT == "LOCAL_DEVELOPMENT":
    # Local development opts into the documented workaround by default; every
    # other environment must say what it wants.
    DB_GSSENCMODE = "disable"

_db_options = DATABASES["default"].setdefault("OPTIONS", {})
if DB_GSSENCMODE:
    _db_options.setdefault("gssencmode", DB_GSSENCMODE)
if DB_SSLMODE:
    _db_options.setdefault("sslmode", DB_SSLMODE)

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Non-admin login (Milestone 11.1 / audit H2): designers no longer need
# is_staff just to sign in. login_required routes here and back via ?next=.
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/accounts/login/"

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
# The hashed/compressed WhiteNoise manifest storage requires `collectstatic`
# to have run (it resolves {% static %} through staticfiles.json). That's right
# for production but breaks dev/tests where collectstatic hasn't run, so it is
# opt-in via USE_MANIFEST_STATIC (the prod entrypoint sets it and runs
# collectstatic). Dev/tests use the plain storage, which serves files directly.
_STATIC_BACKEND = (
    "whitenoise.storage.CompressedManifestStaticFilesStorage"
    if env.bool("USE_MANIFEST_STATIC", default=False)
    else "django.contrib.staticfiles.storage.StaticFilesStorage"
)
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": _STATIC_BACKEND,
    },
}

MEDIA_ROOT = BASE_DIR / env("MEDIA_ROOT", default="media/")

# --- Media storage (Milestone 8.1 / audit C1) -------------------------------
# STORAGE_BACKEND = "local" (default): media is served ONLY through the
#   authenticated /files/<path> view (apps.core.views.serve_media), in both
#   debug and production. Raw unauthenticated /media/ URLs are never mapped.
# STORAGE_BACKEND = "s3": media lives in a private S3 bucket; FileField.url
#   returns signed URLs (1 hour expiry). django-storages/boto3 are imported
#   lazily by Django on first storage access, so they are only required when
#   this backend is actually selected.
STORAGE_BACKEND = env("STORAGE_BACKEND", default="local")
if STORAGE_BACKEND == "s3":
    STORAGES["default"] = {"BACKEND": "storages.backends.s3boto3.S3Boto3Storage"}
    AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME")
    AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", default=None)
    AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID", default=None)
    AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY", default=None)
    AWS_DEFAULT_ACL = "private"
    AWS_QUERYSTRING_AUTH = True      # signed URLs
    AWS_QUERYSTRING_EXPIRE = 3600    # 1 hour expiry
    MEDIA_URL = "/media/"            # unused: S3 storage returns absolute URLs
else:
    # Every FileField.url resolves to the authenticated download route.
    MEDIA_URL = "/files/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# DIP-1B: import manifests name only logical roots and repository-relative paths.
# Resolution stays server-side and every resolved path must remain below one of these
# configured roots and prefixes; browser responses never expose these absolute values.
INTELLIGENCE_SOURCE_ROOTS = {
    "repository": BASE_DIR.parent,
}
INTELLIGENCE_ALLOWED_SOURCE_PREFIXES = {
    "repository": (
        "materials",
        "docs/design_intelligence/dip0c",
        "docs/design_intelligence/dip1/dip1b_brand_evidence_2_0.json",
        "var/design_intelligence/audits",
    ),
}

# --- AI model configuration (Milestone 8.5 / audit C7) ----------------------
# Env-driven so a model retirement is a config change, not a deploy. No model
# name literals live in apps/ — agents and services read these settings only.
CLAUDE_MODEL_HEAVY = env("CLAUDE_MODEL_HEAVY", default="claude-opus-4-7")
CLAUDE_MODEL_FAST = env("CLAUDE_MODEL_FAST", default="claude-sonnet-4-6")
CLAUDE_TIMEOUT_SECONDS = env.float("CLAUDE_TIMEOUT_SECONDS", default=180.0)
# Day 8 (2026-10-20, §0): the jury and the designer's eye use this model when its pre-flight probe answers
# (docs/audit/day-8/preflight/jury-model-probe.json); otherwise CLAUDE_MODEL_HEAVY. Never CLAUDE_MODEL_FAST for a verdict.
JURY_MODEL = env("JURY_MODEL", default="claude-opus-5-5")
# gpt-image family (2026-07-04): dall-e-3 is retired from the OpenAI account,
# so a GPT image model is the default. It returns base64 (handled by the
# image producer), supports sizes 1024x1024 / 1024x1536 / 1536x1024 and
# quality low|medium|high|auto. Legacy dall-e values ("1024x1792", "hd")
# remain valid only if IMAGE_MODEL is switched back to a dall-e model.
# gpt-image-2 (2026-07-07): newer generation model, confirmed compatible with
# the params this codebase sends (quality tiers, 1024x1536 size, no reliance
# on the native transparent-background param gpt-image-2 dropped support
# for). Real-world quality/cost were not something we could validate here —
# watch the first live run's
# cost ledger entry and compare renders before relying on it for production.
IMAGE_MODEL = env("IMAGE_MODEL", default="gpt-image-2")
IMAGE_SIZE = env("IMAGE_SIZE", default="1024x1536")
# --- Cost controls (2026-07-06) ---------------------------------------------
# Gate-1 concepts exist to CHOOSE a direction — medium (~$0.06/img) instead
# of high (~$0.25) cuts the biggest line item 4x. Set =high to restore max
# concept fidelity. [IMAGE_QUALITY, the quality of the post-approval artwork
# extractions, left with them in the clean-up of 2026-10-04 — nothing read it.]
# §BH57(a)2, OWNER RULING 2026-09-21: HIGH. That reasoning held while a concept
# existed only to pick a direction; it stopped holding when he began judging
# the concepts as designs — "I was judging $0.06 pictures as designs". Three
# concepts a run: $0.75 instead of $0.18, which he ruled explicitly.
IMAGE_QUALITY_CONCEPTS = env("IMAGE_QUALITY_CONCEPTS", default="high")
# Auto-revision passes after the first render set (each pass = up to 3 more
# images + QA). 1 keeps the safety net at half the previous worst-case cost.
MAX_REVISION_PASSES = env.int("MAX_REVISION_PASSES", default=2)
# QA vision scoring is advisory (a human decides at Gate 1) — sonnet-class is
# ~5x cheaper than opus and plenty for scoring. Empty = CLAUDE_MODEL_FAST.
QA_VISION_MODEL = env("QA_VISION_MODEL", default="")
# Reference designs (2026-07-04): how many imported past-production files
# (manage.py import_design_references) the Creative Director studies as
# vision blocks per run. Each adds ~1-1.5k input tokens; 0 disables.
MAX_DESIGN_REFERENCES = env.int("MAX_DESIGN_REFERENCES", default=4)
# Official brand logo (2026-07-04). When this file exists it is shown to the
# Creative Director as the canonical lockup, and the composers place it as the
# house mark (apps/ire/brand_mark.py) — the REAL wordmark, never the image
# model's re-drawn (and routinely misspelled) one. [It was also passed to the
# flat-artwork edit, removed in the clean-up of 2026-10-04.]
BRAND_LOGO_PATH = env("BRAND_LOGO_PATH", default=str(MEDIA_ROOT / "brand" / "logo.png"))
# THE OWNER'S SECOND ANSWER OF 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md:23803, the block headed "Before I start
# testing"): "When I approve the logo trace, switch the mark to it so gold foil can print." The composers draw the
# house mark from the approved vector master when docs/brand/mark/approval.json holds (apps/ire/brand_mark.py);
# BRAND_LOGO_PATH stays the PNG — what the image model is shown and what the reference resolver places (the
# flat-artwork edit that placed it too was removed in the clean-up of 2026-10-04). This setting decides whether that
# approval record is looked for at all: on everywhere, OFF under pytest (below), so no test moves the day the owner's
# approved master is placed.
BRAND_MARK_APPROVAL_LOOKUP = env.bool("BRAND_MARK_APPROVAL_LOOKUP", default=True)
# Product identification (2026-07-07): when a task has no Product record, one
# fast Claude call infers what the task is about (category, product type,
# physical carton form) so reference selection, prompt building and QA are
# grounded in the RIGHT product instead of guessing. Disabled under pytest
# below (with CELERY eager) so suite runs never hit the live API.
PRODUCT_INFERENCE = env.bool("PRODUCT_INFERENCE", default=True)
# Trilingual back-panel sticker (2026-07-07): one fast Claude call translates
# the English label copy to Spanish + Arabic at the dimension gate; the
# result is stored in the spec sheet so re-exports never re-call. Disabled
# under pytest below.
PANEL_TRANSLATE_ENABLED = env.bool("PANEL_TRANSLATE_ENABLED", default=True)
# [his review of 127, 130, 131 and 132, 2026-10-15, C (7): "NEVER AN EMPTY LABEL"] a label's pieces his brief and the
# product record leave empty written for the product's type by the strongest model (services/label_copy.py), once a
# design; off in the test suite as translation is (its type's standard copy stands in), on where a test turns it on
LABEL_COPY_WRITING = env.bool("LABEL_COPY_WRITING", default=True)
# [His go of 2026-10-02 (OWNER_BLOCKER_CLEARANCE.md, transcribed at a18911a): "build the map path to run on its own for
# every new design".] The approved concept's design map is read once per picture when a container design reaches its
# shape step — one vision call (concept_design_map.read_parts). Disabled under pytest below.
DESIGN_MAP_READ = env.bool("DESIGN_MAP_READ", default=True)
# [his final goal, 2026-10-05, C6: "EVERY ELEMENT IS ITS OWN PIECE"] the design's native, layered .ai built in Illustrator
# where Illustrator is on this machine (apps/ire/emitters/native_ai.py)
NATIVE_AI_BUILD = env.bool("NATIVE_AI_BUILD", default=True)
# [The clean-up of 2026-10-04 (E2 with F1-F5), approved by the owner: the carton's raster paths are removed, and
# with them FULL_SURFACE_ARTWORK, PRODUCTION_PDF_ARTWORK_UNDERLAY, DESIGN_PREVIEW_AI_MODE and IMAGE_QUALITY.]
# Motif segmentation (2026-07-07): each motif element its own movable object; knobs for the connected-component
# cut. Nothing calls the cut since the clean-up of 2026-10-04 — apps/pipeline/services/artwork_segments.py stays,
# with its own tests, and still reads these three.
SEGMENT_MAX_ELEMENTS = env.int("SEGMENT_MAX_ELEMENTS", default=30)
SEGMENT_MIN_AREA_FRAC = env.float("SEGMENT_MIN_AREA_FRAC", default=0.001)
SEGMENT_BG_THRESHOLD = env.int("SEGMENT_BG_THRESHOLD", default=28)

# ---------------------------------------------------------------------------
# Cost ledger & budget controls (Milestone 12.2)
# ---------------------------------------------------------------------------
# Claude prices are (input, output) USD per 1,000 tokens, keyed by model name.
# Unknown models fall back to CLAUDE_PRICE_DEFAULT. Kept in settings so a price
# change is config, not code; historical ledger rows store the computed cost.
CLAUDE_PRICES = {
    # published list price $5 / $25 per MTok
    "claude-opus-5":     (0.005, 0.025),
    # Day 8 (2026-10-20): the jury model. List price $4 / $20 per MTok, cache reads $0.20 per MTok
    # (Anthropic pricing page, https://www.anthropic.com/pricing, read 2026-10-20 via the claude-api skill's
    # model table); without this row the ledger would bill it at the $15 / $75 default and hit the day cap early.
    "claude-opus-5-5":   (0.004, 0.020),
    # Day 8 (2026-10-20): list price $5 / $25 per MTok (Anthropic model table, read 2026-10-20 via the claude-api
    # skill); the rows read $15 / $75 until today, billing every Opus 4.7 / 4.8 call at three times its price.
    "claude-opus-4-7":   (0.005, 0.025),
    "claude-opus-4-8":   (0.005, 0.025),
    "claude-sonnet-4-6": (0.003, 0.015),
    "claude-sonnet-5":   (0.003, 0.015),
    "claude-haiku-4-5":  (0.001, 0.005),   # list price $1 / $5 per MTok (Day 7 correction: was 0.0008/0.004, under-counting)
    # 2026-10-29 (the owner's $2 per design ruling): the reading and the research run on Sonnet 5.5. List price $2 / $10
    # per MTok, cache reads $0.20 (the claude-api skill's model table, cached 2026-10-06); without this row the ledger
    # would bill it at the $15 / $75 default and stop a $2.00 round early.
    "claude-sonnet-5-5": (0.002, 0.010),
}
# Unknown models fall back to OPUS-class pricing (the most expensive tier) so
# the ledger and budget caps err on over-counting, never under-counting: a new
# heavy model missing from the table must not be silently billed at 1/5 rate.
# apps.pipeline.apps warns at startup when a configured model isn't listed.
CLAUDE_PRICE_DEFAULT = (0.015, 0.075)
# Day 8 (2026-10-20): a cache read's price as a fraction of the input price (Anthropic prompt-caching economics, read
# 2026-10-20 via the claude-api skill: ~0.1x base input; 0.05x on Claude Opus 5.5, $0.20 per MTok; 0.025x on Claude
# Fable 5.1). Writes stay at 1.25x (5-minute TTL).
CLAUDE_CACHE_READ_MULTIPLIER = {"default": 0.1, "claude-opus-5-5": 0.05, "claude-fable-5-1": 0.025}
# Flat price per generated image. gpt-image-1 "high" at 1024x1536 ≈ $0.25
# (token-based; this is a deliberate slight over-estimate so budget caps err
# safe). Lower it if you drop IMAGE_QUALITY_CONCEPTS to medium (~$0.06) or low (~$0.02).
IMAGE_PRICE_PER_IMAGE = env.float("IMAGE_PRICE_PER_IMAGE", default=0.25)
# Day 8 (2026-10-20, D-D8-10): gpt-image calls are settled at usage price on the rescue ledger from the provider's own
# usage counts and these published STANDARD tariffs, USD per 1M tokens (https://developers.openai.com/api/docs/pricing,
# read 2026-10-20: gpt-image-2 image input $8 / text input $5 / image output $30; gpt-image-1 $10 / $5 / $40;
# gpt-image-1-mini $2.50 / $2 / $8). A model missing here, or a response without token details, keeps its reservation.
OPENAI_IMAGE_PRICES = {
    "gpt-image-2":      {"image_input": 8.0, "text_input": 5.0, "image_output": 30.0},
    "gpt-image-1":      {"image_input": 10.0, "text_input": 5.0, "image_output": 40.0},
    "gpt-image-1-mini": {"image_input": 2.5, "text_input": 2.0, "image_output": 8.0},
}
# §BH71 PART 2 — Tavily's pay-as-you-go price per API credit (https://www.tavily.com/pricing, read 2026-09-28):
# a basic search is 1 credit, an advanced one 2 (the credits page). Every search is a ledger row priced by it,
# so search spend counts against the design's cap, the day's cap and the design page's "spent" figure.
TAVILY_USD_PER_CREDIT = env.float("TAVILY_USD_PER_CREDIT", default=0.008)

# Budget guards. A task that exceeds MAX_COST_PER_TASK fails with a clear
# message; new task creation is blocked with a 429 once the rolling 24h spend
# reaches MAX_COST_PER_DAY. Set either to 0 to disable that guard.
MAX_COST_PER_TASK = env.float("MAX_COST_PER_TASK", default=25.0)
# [his goal for the pitch, 2026-10-15, B (5)] the designer's eye after every drawing — its model the strongest. On where
# designs are made for real: the worker and the site start with it (tools/restart_worker.sh, restart_site.sh); off in
# the test suite, which refuses every outbound call (conftest.py), save where a test turns it on (the wiring check)
DESIGNERS_EYE = env.bool("DESIGNERS_EYE", default=False)
DESIGNERS_EYE_MODEL = env("DESIGNERS_EYE_MODEL", default="")
# [his goal for the pitch, 2026-10-15, A (4)] a product drawn standing drawn from its printed face redrawn flat and
# traced in colour (targets/container/face_art.py) — paid once a concept; on where designs are made, as the eye is
FACE_ART = env.bool("FACE_ART", default=False)
MAX_COST_PER_DAY = env.float("MAX_COST_PER_DAY", default=25.0)
# [ESTIMATED_COST_PER_TASK, the batch fan-out pre-flight's per-task estimate, left with the batch API in the
# clean-up of 2026-10-04 (E10c, F8); an old .env that still sets it is ignored.]

# ---------------------------------------------------------------------------
# Notifications (Milestone 12.4)
# ---------------------------------------------------------------------------
# Console backend in dev (emails print to the worker log); override
# EMAIL_BACKEND + SMTP settings via env in production.
EMAIL_BACKEND = env(
    "EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend",
)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@bbrose.design")
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
# Absolute base for links in emails (dashboard task URLs).
NOTIFICATION_BASE_URL = env("NOTIFICATION_BASE_URL", default="http://localhost:8000")

ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", default="")
OPENAI_API_KEY = env("OPENAI_API_KEY", default="")
# An organisation admin key, only for reading OpenAI's usage when a call came back with nothing (the owner,
# 2026-10-30: "check its outcome with the provider before giving up, so it's never charged twice")
OPENAI_ADMIN_KEY = env("OPENAI_ADMIN_KEY", default="")

# PDF/X OutputIntent for the production PDF (Phase 2A-6 §11). WHICH CMYK
# profile is the print shop's decision, so there is no default: without a
# configured profile the Gate-2 validator reports MISSING_OUTPUT_INTENT
# rather than embedding a guessed colour space (a wrong intent is worse than
# none — the file would claim a space the plates were not built for).
# Point PRODUCTION_ICC_PROFILE_PATH at the shop's .icc (e.g. a FOGRA39 or
# GRACoL CMYK profile) to satisfy the check.
PRODUCTION_ICC_PROFILE_PATH = env("PRODUCTION_ICC_PROFILE_PATH", default="")
PRODUCTION_OUTPUT_CONDITION = env("PRODUCTION_OUTPUT_CONDITION", default="FOGRA39")
PRODUCTION_OUTPUT_REGISTRY = env("PRODUCTION_OUTPUT_REGISTRY",
                                 default="http://www.color.org")

# Directory the dieline exporters write SVG/AI files to. The agent saves the
# canonical copy onto PackagingOutput.dieline_file; this is just the exporters'
# scratch location.
DIELINE_EXPORT_DIR = BASE_DIR / "exports"

REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_TRACK_STARTED = True
# Hardening 2026-07-04: a full pipeline run is 2+ Claude calls + 3 gpt-image
# "high" renders (30-60s each) + vision QA + up to 2 revision passes — the old
# 600s hard limit could SIGKILL legitimate runs. Env-driven so ops can tune
# without a deploy; soft limit fires 60s before the hard kill so crash_safe
# records a clean failure instead of a worker corpse.
CELERY_TASK_TIME_LIMIT = env.int("CELERY_TASK_TIME_LIMIT", default=1800)
CELERY_TASK_SOFT_TIME_LIMIT = env.int("CELERY_TASK_SOFT_TIME_LIMIT", default=1740)
# Eager mode (Milestone 8.7 / audit H7): CELERY_EAGER decouples the run mode
# from DEBUG. When eager, .delay() runs tasks synchronously in-process (no
# Redis/worker needed — demo mode). When not eager, tasks enqueue to Redis and
# require `celery -A config worker`; /healthz and task creation verify a
# worker is actually alive. Default keeps backwards compat with DEBUG.
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_EAGER", default=DEBUG)
# Tests ALWAYS run eager (hardening 2026-07-04): the dev .env is now in worker
# mode, and with a live Redis the test suite's .delay() calls would otherwise
# enqueue into the void (no worker) — 9 pipeline tests silently no-op'd.
# Detecting pytest here is deterministic regardless of conftest import order.
import sys  # noqa: E402
if "pytest" in sys.modules:
    CELERY_TASK_ALWAYS_EAGER = True
    # Product inference is a live Claude call the agent mocks don't cover —
    # tests that exercise it opt back in with override_settings + a patch.
    PRODUCT_INFERENCE = False
    # Same reasoning for panel translation (one live Claude call per gate).
    PANEL_TRANSLATE_ENABLED = False
    # [his review of 127, 130, 131 and 132, 2026-10-15, C (7)] and for writing a label's missing pieces
    LABEL_COPY_WRITING = False
    # And for the design map's read (one live Claude call per approved concept).
    DESIGN_MAP_READ = False
    # [his final goal, C6] and Illustrator: no test drives the Illustrator on this machine
    NATIVE_AI_BUILD = False
    # THE OWNER'S SECOND ANSWER OF 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md, the block headed "Before I start
    # testing"): "Measure how much of the media folder is test output, and stop the tests writing into the real
    # folder. Delete nothing." Measured read-only at 2026-09-25T10:18Z (archive/work/bh69_rounds_logo_trace_ui_build/media/media_measure.json):
    # 969,714 files, 17.7 GB; 410 of them (0.49 GB) named by a record in the development database; 675,019 (11.2 GB)
    # named by none and last written inside a gate window (a record-gate ledger stamp, 2 minutes before to 60 after);
    # 294,285 (6.1 GB) named by none and written outside every such window. Counted over one gate (d1bc9b7,
    # 09:58:57Z-10:20:28Z): 1,190 files, 21.2 MB, written into the real folder — test-named (v<n>_, c_, concept_,
    # sheet_, bottle_, chips_, container_task_<n>_) — an upper bound, since two worktree test runs could also write
    # there. The suite now writes into a directory of its own for its whole length. It is made HERE, beside the eager
    # flag and for the same reason: this module is imported before any app module, so nothing can capture the real
    # root first.
    # Inputs keep their own settings: BRAND_LOGO_PATH was resolved above from the real root and still reads the real
    # mark. Nothing in the real folder is moved, rewritten or deleted; this directory leaves with the run (atexit, below).
    # EXTENT, stated as §AY1 states its own: this covers every writer in the suite's process that resolves
    # settings.MEDIA_ROOT (every production writer does — no literal "media" path was found outside the tests) and
    # every test that overrides it; a subprocess that loads these settings without pytest imported still reads the
    # real root, and none in the suite writes media.
    import tempfile  # noqa: E402
    REAL_MEDIA_ROOT = MEDIA_ROOT
    MEDIA_ROOT = Path(tempfile.mkdtemp(prefix="bbrose_test_media_"))
    # The clean-up of 2026-10-04 (his "tests never leave test media folders in the temp folder"): 2,986 of these
    # folders, ~3.5 GB, were left behind, one per run; the run's own folder is removed when the process ends.
    import atexit  # noqa: E402
    import shutil  # noqa: E402
    atexit.register(shutil.rmtree, MEDIA_ROOT, True)
    # The owner's second answer of 2026-09-25: a test never draws the approved master because it was placed on
    # file — only a master the test itself hands a composer (apps/ire/brand_mark.py; conftest.py holds the same
    # line for a runner that imports these settings before pytest).
    BRAND_MARK_APPROVAL_LOOKUP = False
# Always propagate eager task exceptions — silent failures masked dev bugs.
CELERY_TASK_EAGER_PROPAGATES = True


# ---------------------------------------------------------------------------
# Logging (Milestone 14.1): verbose text in dev, machine-parseable JSON in
# prod. Every record carries the request id (RequestIDMiddleware) for tracing.
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_id": {"()": "apps.core.middleware.RequestIDLogFilter"},
    },
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name} rid={request_id} {message}",
            "style": "{",
        },
        "json": {"()": "apps.core.middleware.JsonLogFormatter"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["request_id"],
            "formatter": "verbose" if DEBUG else "json",
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "apps.pipeline": {
            "handlers": ["console"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
        "apps.dielines": {
            "handlers": ["console"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
        # [the owner's goal of 2026-10-29, §0: the worker log] no handler of its own and propagating: in the worker,
        # Celery takes the root logger over and strips this logger's handler, and with propagate False every Celery
        # line (ready, Task received, succeeded, the revision stamp) was dropped. It now reaches the root's handler
        # (the console here, Celery's in the worker).
        "celery": {"level": "INFO", "propagate": True},
        "django.request": {
            "handlers": ["console"], "level": "WARNING", "propagate": False,
        },
    },
}

# ---------------------------------------------------------------------------
# Error monitoring (Milestone 14.1): Sentry is env-gated — no DSN, no import,
# so dev/tests never touch it. Covers both Django requests and Celery tasks.
# ---------------------------------------------------------------------------
SENTRY_DSN = env("SENTRY_DSN", default="")
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        traces_sample_rate=env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.0),
        send_default_pii=False,
        environment=env("SENTRY_ENVIRONMENT", default="production"),
    )

# ---------------------------------------------------------------------------
# Production security (Milestone 14.1): applied only when DEBUG is off so local
# dev over http still works. `manage.py check --deploy` should be clean with
# DEBUG=False. Header-level protections apply in every environment.
#
# THAT CLAIM WAS TESTED 2026-08-22 AND IS TRUE WITH ONE SURVIVOR: DEBUG=False
# takes `check --deploy` from 6 warnings to 1. The survivor is W009 — the
# local .env SECRET_KEY is Django's auto-generated dev key (48 chars, 20
# unique, `django-insecure-` prefix), which is correct FOR LOCAL DEV. What
# production supplies is not measurable from here and is not claimed.
#
# AND `check --deploy` IS BLIND TO CSP — Django ships no CSP check at all
# (verified against django/core/checks/security/base.py). So a clean
# `--deploy` run is not evidence of header-level hardening, and reading it
# that way is a green result whose extent does not cover the question. The
# Content-Security-Policy lives in apps.core.middleware and is REPORT-ONLY;
# its docstring carries the measured reason it cannot yet be enforced.
# ---------------------------------------------------------------------------
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

if not DEBUG:
    SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
    # HSTS starts conservative (1h); raise once you've confirmed HTTPS holds.
    SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=3600)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # Trust the proxy's X-Forwarded-Proto (nginx/traefik terminate TLS).
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# --- ARIA Web Research Gateway (2C-2A-CORR-2 §26) ----------------------------
# Governed, provenance-first public-web research. No provider configured →
# WEB_RESEARCH_NOT_CONFIGURED (never an uncontrolled fallback). Credentials
# are never persisted in records, prompts, logs or manifests.
WEB_SEARCH_PROVIDER = env("WEB_SEARCH_PROVIDER", default="")
WEB_SEARCH_API_KEY = env("WEB_SEARCH_API_KEY", default="")
WEB_RESEARCH_USER_AGENT = env(
    "WEB_RESEARCH_USER_AGENT",
    default="BBROSE-DesignOS-ResearchBot/1.0 (+bbrosedesign07@gmail.com)")
WEB_QUARANTINE_ROOT = env("WEB_QUARANTINE_ROOT", default="")

# §BH57(a)5 — may a DESIGN RUN open a governed inspiration session by itself?
# The owner ruled it connected ("inspiration that never runs is not
# inspiration"), so the default is on. It is a switch and not a constant
# because it is the one wire in §BH57(a) that spends: each run makes up to
# four Tavily search calls on the house key. Off, the design proceeds exactly
# as before and the run says which state it was in. Only ever
# VISUAL_INSPIRATION_DISCOVERY, only search (never fetch) — see
# apps/pipeline/agents/aria.py.
WEB_INSPIRATION_IN_GENERATION = env.bool(
    "WEB_INSPIRATION_IN_GENERATION", default=True)
# §BH71 PART 2 — THE TREND BOARD (apps/pipeline/services/trend_board.py): what each platform's finds may be —
# FETCH its pictures, every guard kept; LINK, a title and a link only; SKIP, not searched. Pinterest and Instagram
# refuse automated access in their robots.txt; The Dieline's and Behance's terms forbid automated collection though
# their robots.txt allows it, so they are links until the owner rules (the question is in the §BH71 report).
# He ruled on 2026-09-29 (his answer to that report, (1)): "The Dieline and Behance stay links. Respect their terms."
# Packaging of the World answered the one real board (2026-09-28) with a 307 and no Location instead of its page, as
# it had answered every page the research fetched, and its robots.txt asks 60 s between requests: the board's
# pictures waited out that minute for nothing, so its finds are links.
TREND_PLATFORM_MODES = {"pinterest": "LINK", "behance": "LINK", "dribbble": "FETCH", "instagram": "LINK",
                        "the_dieline": "LINK", "packaging_of_the_world": "LINK", "open_web": "FETCH",
                        # [his goal for the pitch, 2026-10-15, A (1)] brands' own sites: links, their words only
                        "beauty_brands": "LINK"}
TREND_PICTURES_MAX = 12            # pictures on one board
TREND_PICTURES_PER_PLATFORM = 3    # pictures from one named platform
TREND_OPEN_WEB_PER_DOMAIN = 2      # pictures from one site of the open web
TREND_OPEN_WEB_MAX = 6             # pictures from the open web in all
TREND_LINKS_PER_PLATFORM = 3       # link cards from one platform
# [§BH62 (d) "forty to sixty retained, not ten"; Day 8 §2b] the caps of a board a task asks to be made at the mood-board
# scale (options["trend_scale"] = "mood_board"; trend_board.caps_for) — a design's board keeps the caps above
TREND_MOOD_BOARD_CAPS = {"pictures": 70, "per_platform": 10, "per_domain": 4, "open_web": 60, "links": 8,
                         "fetch_budget_s": 900}
# the seconds a board's pictures may take to fetch — a host that would keep it waiting longer is deferred, said
TREND_FETCH_BUDGET_S = env.int("TREND_FETCH_BUDGET_S", default=90)
# the seconds a board takes unticks before the directions are made with the ticked pictures, unless he presses on
TREND_REVIEW_WINDOW_S = env.int("TREND_REVIEW_WINDOW_S", default=120)
