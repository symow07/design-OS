"""Reviewer identity and role assignments (DIP-1A-2).

**The authoritative actor is `request.user.pk`.** These models attach *reviewer* meaning
to Django's existing `auth.User` by composition — they never duplicate credentials, and
they never introduce a second notion of "active".

Two separations do the work:

* **`User.is_active` is the account.** `ReviewerProfile.reviewer_enabled` is *participation
  in reviewer workflows*. A disabled reviewer is still a user who can log in; a disabled
  user is nobody at all. Two meanings, two fields, one direction of travel: **either one
  being false means no roles.**
* **Role validity is COMPUTED, never stored.** There is no `is_active` boolean on an
  assignment — a stored flag is a lie waiting to happen, because it has to be maintained
  by something, and that something is a cron job you forgot to run. Expiry and revocation
  are therefore inert **immediately**, with no background task, which is the same
  fail-closed discipline the audit ledger has used since C3b3.

**Nothing is ever deleted.** A revocation *appends state* to the assignment; a re-grant
creates a *new row*. History is the point — a role that was held and then revoked is a
fact about the past, and a system that erases it cannot answer the only question that
matters after an incident: *who could do this, and when?* That question is point-in-time,
so the resolver is point-in-time: `active_roles(user, at=T)` reports the roles that were
live *at T*, honouring the revocation boundary rather than treating every revocation as
retroactive to the beginning of time.
"""
from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from . import authz_policy as authz

# The role vocabulary is NOT redefined here, and — deliberately — it is NOT bound to the
# field as `choices`. `makemigrations` freezes a `choices` literal into 0001, so the day
# `authz.ROLES` changes, that frozen copy drifts and CI's `makemigrations --check` fails
# until a no-op AlterField is added. The migration file would then BE the "second copy
# that drifts" this module exists to avoid. Validity is enforced in `clean()` against the
# live policy instead; `apps/accounts/authz_policy.py` is the single source.

# Where an assignment came from. Free-form strings are refused: "who granted this, and
# through what path" is a security question, not a memo field.
GRANT_BOOTSTRAP = "BOOTSTRAP"
GRANT_MIGRATION = "MIGRATION"
GRANT_TEST_FIXTURE = "TEST_FIXTURE"
GRANT_AUTHORIZED_SERVICE = "AUTHORIZED_SERVICE"
# DIP-1A-BOOTSTRAP-CORR-2. A DISTINCT source, never the generic BOOTSTRAP: a reader must be
# able to tell a single-operator self-bootstrap from a two-person pre-ledger seed by the
# row alone, without reconstructing the ceremony from the chain.
GRANT_BOOTSTRAP_SINGLE_OPERATOR = "BOOTSTRAP_SINGLE_OPERATOR"
GRANT_OWNER_TEMPORARY_WEB_REVIEW = "OWNER_TEMPORARY_WEB_REVIEW"
GRANT_SOURCES = (
    (GRANT_BOOTSTRAP, "Bootstrap (pre-ledger)"),
    (GRANT_BOOTSTRAP_SINGLE_OPERATOR, "Bootstrap (single-operator local ceremony)"),
    (GRANT_MIGRATION, "Migration"),
    (GRANT_TEST_FIXTURE, "Test fixture"),
    (GRANT_AUTHORIZED_SERVICE, "Authorized service"),
    (GRANT_OWNER_TEMPORARY_WEB_REVIEW,
     "Owner-authorized temporary web-reference review ceremony"),
)
# The only source permitted to omit `granted_by`: the controlled bootstrap seeds the very
# first grants before any authenticated granter exists. Everything else must name a
# granter, enforced in the database.
GRANTER_OPTIONAL_SOURCES = (GRANT_BOOTSTRAP,)
# Sources that are NOT production authority. A revocation from one of these may omit a
# reason; a production revocation may not.
NON_PRODUCTION_SOURCES = (GRANT_TEST_FIXTURE,)


class ReviewerProfile(models.Model):
    """Reviewer participation. NOT an account, and not a credential store."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,          # deleting a user must not erase review history
        related_name="reviewer_profile",
    )
    display_name = models.CharField(max_length=150, blank=True)
    # DEFAULT FALSE. Creating a profile does not make someone a reviewer — a system that
    # enables authority as a side effect of a row appearing is a system that grants
    # authority by accident.
    reviewer_enabled = models.BooleanField(default=False)
    organization = models.CharField(max_length=150, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "reviewer profile"

    def __str__(self) -> str:
        state = "enabled" if self.reviewer_enabled else "disabled"
        return f"{self.user_id}:{self.display_name or self.user} ({state})"


class ReviewerRoleAssignmentQuerySet(models.QuerySet):
    def active_at(self, at):
        """Assignments live *at the instant* `at` — computed, never a stored flag.

        Revocation is a boundary in time, not a retroactive erasure: an assignment
        revoked at ``T_r`` was genuinely active for every instant before ``T_r``. So a
        revocation excludes the row only when ``at >= T_r`` (`revoked_at__gt=at`), which
        keeps the point-in-time question — *who could do this, and when?* — answerable for
        the past while still failing closed for the present.
        """
        return self.filter(
            models.Q(revoked_at__isnull=True) | models.Q(revoked_at__gt=at),
            granted_at__lte=at,
            expires_at__gt=at,
        )


class ReviewerRoleAssignment(models.Model):
    """One grant of one role to one user, for a bounded period.

    Rows are **append-only in spirit**: revocation writes `revoked_at`/`revoked_by`/reason
    onto the row rather than deleting it, and a re-grant is a *new* row. There is
    deliberately **no unique constraint on `(user, role)`** — that would forbid the normal
    lifecycle of grant → expire → re-grant, and destroy the history it depends on.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reviewer_role_assignments",
    )
    # No `choices=` — see the module-level note. Validity is checked against live policy.
    role = models.CharField(max_length=32)

    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,          # the granter must remain nameable, forever
        related_name="reviewer_roles_granted",
        null=True, blank=True,             # null ONLY for the controlled bootstrap
    )
    granted_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(
        help_text="Required. Indefinite reviewer authority is not a default.")

    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reviewer_roles_revoked",
        null=True, blank=True,
    )
    revocation_reason = models.TextField(blank=True)

    grant_source = models.CharField(max_length=32, choices=GRANT_SOURCES)
    grant_reason = models.TextField(
        help_text="Why this person holds this role. Required.")
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ReviewerRoleAssignmentQuerySet.as_manager()

    class Meta:
        verbose_name = "reviewer role assignment"
        indexes = [
            # supports active_roles(): user -> live assignments
            models.Index(fields=["user", "revoked_at", "expires_at"],
                         name="rra_user_live_idx"),
            models.Index(fields=["user", "role"], name="rra_user_role_idx"),
            models.Index(fields=["expires_at"], name="rra_expires_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(expires_at__gt=models.F("granted_at")),
                name="rra_expires_after_granted",
            ),
            models.CheckConstraint(
                check=(models.Q(revoked_at__isnull=True)
                       | models.Q(revoked_at__gte=models.F("granted_at"))),
                name="rra_revoked_not_before_granted",
            ),
            # A revocation with no revoker is an event with no actor. Refused in the
            # DATABASE, because that is the layer a stray script cannot talk its way past.
            models.CheckConstraint(
                check=(models.Q(revoked_at__isnull=True,
                                revoked_by__isnull=True)
                       | models.Q(revoked_at__isnull=False,
                                  revoked_by__isnull=False)),
                name="rra_revoked_requires_revoker",
            ),
            # Symmetric to the revoker rule: only the bootstrap may omit a granter. Every
            # production grant must name who performed it, enforced in the database rather
            # than trusted to the service layer.
            models.CheckConstraint(
                check=(models.Q(grant_source=GRANT_BOOTSTRAP)
                       | models.Q(granted_by__isnull=False)),
                name="rra_granter_required_unless_bootstrap",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.role} [{self.grant_source}]"

    # --- validation ---------------------------------------------------------------
    def clean(self):
        errors = {}

        if self.role not in authz.ROLES:
            errors["role"] = ValidationError(
                f"{self.role!r} is not in authz.ROLES ({list(authz.ROLES)}). The policy "
                "lives in apps/accounts/authz_policy.py and the database never redefines "
                "it.")

        if self.expires_at and self.granted_at and self.expires_at <= self.granted_at:
            errors["expires_at"] = ValidationError(
                "expires_at must be after granted_at — a role that expires before it "
                "is granted was never a grant.")

        if self.granted_by_id is None and self.grant_source not in GRANTER_OPTIONAL_SOURCES:
            errors["granted_by"] = ValidationError(
                "only the controlled bootstrap may omit a granter; every other grant "
                "must name who performed it.")

        if self.revoked_at:
            if self.granted_at and self.revoked_at < self.granted_at:
                errors["revoked_at"] = ValidationError(
                    "revoked_at cannot precede granted_at")
            # A revocation dated in the future is a scheduled revocation — a stored flag
            # that a future clock tick is supposed to honour, i.e. exactly the deferred
            # maintenance this model refuses. Revocation takes effect when it is recorded.
            if self.revoked_at > timezone.now():
                errors.setdefault("revoked_at", ValidationError(
                    "revoked_at cannot be in the future: revocation takes effect when it "
                    "is recorded, not on a schedule."))
            if self.revoked_by_id is None:
                errors["revoked_by"] = ValidationError(
                    "a revocation must name who performed it")
            if (not self.revocation_reason.strip()
                    and self.grant_source not in NON_PRODUCTION_SOURCES):
                errors["revocation_reason"] = ValidationError(
                    "a production revocation must record a reason")

        if not (self.grant_reason or "").strip():
            errors["grant_reason"] = ValidationError(
                "a grant must record why this person holds this role")

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # full_clean on save: these rows are security-sensitive, and the ~microseconds
        # cost is irrelevant next to a bad role slipping in through a shell one-liner.
        # Every writer (including the bootstrap command) MUST route through save(); a
        # bulk_create / QuerySet.update() would bypass this and the constraints' intent.
        self.full_clean()
        return super().save(*args, **kwargs)

    def is_active_at(self, at=None) -> bool:
        at = at or timezone.now()
        return (self.granted_at <= at < self.expires_at
                and (self.revoked_at is None or at < self.revoked_at))


# --- the canonical active-role resolver ------------------------------------------
def active_roles(user, at=None) -> tuple[str, ...]:
    """The roles this user held *at `at`* (default: now). **This authorizes nothing.**

    It answers one question — *which roles are live at this instant?* — and hands the
    answer to the authorization service (1A-3), which is the only thing permitted to
    consult the policy. Keeping the two apart means a resolver bug can never *grant*
    anything; it can only fail to grant.

    `at` is injectable so expiry is deterministic in tests, and so audit/authorization can
    ask the past-tense question honestly rather than racing the wall clock. There is **no
    cross-request cache**: a revocation must bite on the very next request, and a cache is
    just a window during which it does not.

    Fails closed on every axis — unauthenticated, inactive user, missing profile, disabled
    profile, expired, revoked, not yet started, or a stored role that is no longer in the
    policy.
    """
    at = at or timezone.now()

    if user is None or not getattr(user, "is_authenticated", False):
        return ()
    if not getattr(user, "is_active", False):
        return ()

    profile = getattr(user, "reviewer_profile", None)
    if profile is None or not profile.reviewer_enabled:
        return ()

    roles = (ReviewerRoleAssignment.objects
             .filter(user=user)
             .active_at(at)
             .values_list("role", flat=True))

    # A role stored in the DB that is no longer in the policy grants NOTHING. Deleting
    # the row would erase history; ignoring it fails closed and keeps the record.
    valid = {r for r in roles if r in authz.ROLES}
    # de-duplicated: two overlapping grants of LEGAL_REVIEWER are one authority, and both
    # rows are preserved for audit.
    return tuple(sorted(valid))


def overlapping_active_assignments(user, at=None) -> dict[str, int]:
    """Diagnostics: roles held via more than one live assignment at `at`.

    Not an error — the rows are legitimate history, and `active_roles` already collapses
    them to one authority. It is reported so the protected grant service (1A-5) can refuse
    to *create* new overlaps rather than silently accumulating them.
    """
    at = at or timezone.now()
    counts: dict[str, int] = {}
    for role in (ReviewerRoleAssignment.objects
                 .filter(user=user).active_at(at)
                 .values_list("role", flat=True)):
        counts[role] = counts.get(role, 0) + 1
    return {r: n for r, n in sorted(counts.items()) if n > 1}


# --- authorization audit (DIP-1A-3) ----------------------------------------------
RESULT_ALLOWED = "ALLOWED"
RESULT_DENIED = "DENIED"
RESULT_CHOICES = ((RESULT_ALLOWED, "Allowed"), (RESULT_DENIED, "Denied"))

USER_AGENT_MAX = 400          # cap: a UA header is unbounded attacker-controlled input
CORRELATION_ID_MAX = 64       # cap: same reason; the middleware does not bound it


class AppendOnlyViolation(RuntimeError):
    """Attempt to mutate or delete an append-only audit row through the ORM."""


class _AuthorizationAuditQuerySet(models.QuerySet):
    """Append-only at the ORM boundary. A correction is a NEW row, never an edit."""

    def update(self, *args, **kwargs):
        raise AppendOnlyViolation(
            "AuthorizationAudit is append-only — record a new row, do not update. "
            "(A DB superuser can still mutate the table directly; that is not "
            "cryptographically detectable in 1A-3. The signed decision chain in 1A-4 "
            "has stronger tamper evidence.)")

    def delete(self, *args, **kwargs):
        raise AppendOnlyViolation("AuthorizationAudit is append-only — rows are not "
                                  "deleted through the application.")


class AuthorizationAudit(models.Model):
    """Every authorization ATTEMPT — allowed or denied — that reached the enforcement
    boundary. This is evidence, not a cache: it is written on the server side, from the
    authenticated identity and the policy decision, and never from anything the client
    can dictate.

    It is **outside** the signed DecisionEvent chain (that is 1A-4). Within 1A-3 it is
    append-only through the application: the manager refuses `update()`/`delete()` and
    `save()` refuses to rewrite a loaded row. It is honestly NOT tamper-proof against a
    direct database superuser — that guarantee arrives with the HMAC chain in 1A-4.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,        # an audited actor must remain nameable, forever
        null=True, blank=True,           # NULL only for an unauthenticated attempt
        related_name="authorization_audits",
    )
    action = models.CharField(max_length=64)
    subject_type = models.CharField(max_length=64, blank=True, default="")
    subject_id = models.CharField(max_length=200, blank=True, default="")

    result = models.CharField(max_length=8, choices=RESULT_CHOICES)
    reason_code = models.CharField(max_length=40)
    active_roles = models.JSONField(default=list)
    authorizing_roles = models.JSONField(default=list)
    role_used = models.CharField(max_length=32, blank=True, default="")
    selection_rule = models.CharField(max_length=64, blank=True, default="")

    endpoint = models.CharField(max_length=200)
    request_method = models.CharField(max_length=8, blank=True, default="")
    correlation_id = models.CharField(max_length=CORRELATION_ID_MAX, blank=True,
                                      default="")
    source_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=USER_AGENT_MAX, blank=True, default="")
    # Tightly controlled: the writer builds this, never the raw request. No bodies, no
    # headers, no secrets — see record_authorization().
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = _AuthorizationAuditQuerySet.as_manager()

    class Meta:
        verbose_name = "authorization audit"
        indexes = [
            models.Index(fields=["user", "created_at"], name="aa_user_time_idx"),
            models.Index(fields=["action", "result"], name="aa_action_result_idx"),
            models.Index(fields=["reason_code"], name="aa_reason_idx"),
            models.Index(fields=["correlation_id"], name="aa_correlation_idx"),
            models.Index(fields=["created_at"], name="aa_time_idx"),
        ]
        constraints = [
            # An allow must name the role it was granted under; a denial must not. The
            # policy decision already guarantees this — the DB refuses a malformed row
            # written by anything that bypassed the service.
            models.CheckConstraint(
                check=(models.Q(result=RESULT_ALLOWED)
                       & ~models.Q(role_used="")
                       & models.Q(reason_code="AUTHORIZED"))
                      | (models.Q(result=RESULT_DENIED) & models.Q(role_used="")),
                name="aa_allow_iff_role_used",
            ),
        ]

    def __str__(self) -> str:
        who = self.user_id if self.user_id is not None else "anon"
        return f"{self.result} {self.action} by {who} ({self.reason_code})"

    def save(self, *args, **kwargs):
        # Append-only against a plain .save() on a loaded row, not just .update(). An audit
        # row is written once and never rewritten; a correction is a new row.
        if not self._state.adding:
            raise AppendOnlyViolation(
                "AuthorizationAudit rows are append-only and cannot be re-saved.")
        return super().save(*args, **kwargs)


# --- signed decision-event chain (DIP-1A-4) --------------------------------------
# The chain is the tamper-evident record of protected decisions. Two models with
# DELIBERATELY DIFFERENT write rules:
#   * DecisionEvent is INSERT-ONLY and immutable — never updated, never deleted.
#   * DecisionChainHead is a SERVICE-MANAGED singleton — the append service advances it.
# Both are writable only through the canonical append service (apps/accounts/
# decision_chain.py), which holds the one write-capability token below. Nothing else — not
# objects.create(), not a stray .save(), not the admin — can write them.
# v2.0 signs supersedes_event_id and signature_algorithm (DIP-1A-5 pre-correction). v1.0
# remains only for the frozen 1A-1 golden fixtures; no real event is v1.
DECISION_EVENT_SCHEMA = "decision_event/2.0"
CHAIN_HEAD_SCHEMA = "decision_chain_head/1.0"
SIGNATURE_ALGORITHM = "HMAC-SHA-256"


class ChainWriteViolation(RuntimeError):
    """Attempt to write the decision chain outside the canonical append service."""


# The single capability. Held privately; the append service imports it. Identity check
# (is), not equality — an attacker cannot forge object identity from request JSON.
_CHAIN_WRITE_TOKEN = object()


class _DecisionEventQuerySet(models.QuerySet):
    def update(self, *a, **k):
        raise ChainWriteViolation("DecisionEvent is append-only — no update().")

    def delete(self, *a, **k):
        raise ChainWriteViolation("DecisionEvent is append-only — no delete().")

    def bulk_create(self, *a, **k):
        raise ChainWriteViolation("DecisionEvent must be appended one-by-one via the "
                                  "canonical service (the chain head serialises it).")

    def bulk_update(self, *a, **k):
        raise ChainWriteViolation("DecisionEvent is immutable — no bulk_update().")


class _DecisionEventManager(models.Manager.from_queryset(_DecisionEventQuerySet)):
    def create(self, *a, **k):
        raise ChainWriteViolation(
            "do not create DecisionEvent directly — use "
            "apps.accounts.decision_chain.append_decision().")


class DecisionEvent(models.Model):
    """One signed, immutable link in the protected-decision chain.

    Every field that matters is covered by the 1A-1 HMAC over the canonical 12-field
    envelope (`SIGNED_FIELDS`). `supersedes_event` and `signature_algorithm` are
    **outside** that frozen envelope and are therefore UNSIGNED metadata in 1A-4 — a
    reviewer should know that a superseding *decision* (1A-5) will carry its reference
    inside the signed payload, and the verifier pins the algorithm rather than trusting
    the column (no downgrade path).
    """

    sequence_number = models.PositiveBigIntegerField(unique=True)
    event_id = models.CharField(max_length=64, unique=True)
    schema_version = models.CharField(max_length=40, default=DECISION_EVENT_SCHEMA)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="decision_events")
    role_used = models.CharField(max_length=32)
    action = models.CharField(max_length=64)
    subject_type = models.CharField(max_length=64, blank=True, default="")
    subject_id = models.CharField(max_length=200, blank=True, default="")
    payload = models.JSONField(default=dict)
    # None for the first event (matches the frozen golden vector's previous_event_hash:
    # null). Otherwise the CONTENT hash of the preceding event.
    previous_event_hash = models.CharField(max_length=64, null=True, blank=True)
    content_hash = models.CharField(max_length=64)
    hmac_signature = models.CharField(max_length=128)
    signing_key_id = models.CharField(max_length=64)
    signature_algorithm = models.CharField(max_length=32, default=SIGNATURE_ALGORITHM)
    supersedes_event = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True,
        related_name="superseded_by")
    # Generated ONCE by the append service and stored unchanged — never auto_now_add, so
    # the persisted timestamp is exactly the signed one.
    created_at = models.DateTimeField()

    objects = _DecisionEventManager()

    class Meta:
        verbose_name = "decision event"
        ordering = ["sequence_number"]
        indexes = [
            models.Index(fields=["actor"], name="de_actor_idx"),
            models.Index(fields=["action"], name="de_action_idx"),
            models.Index(fields=["subject_type", "subject_id"], name="de_subject_idx"),
            models.Index(fields=["created_at"], name="de_created_idx"),
            models.Index(fields=["supersedes_event"], name="de_supersedes_idx"),
            # NB: event_id and sequence_number are unique=True — their indexes are
            # created automatically; not duplicated here.
        ]
        constraints = [
            models.CheckConstraint(check=~models.Q(event_id=""), name="de_event_id_ne"),
            models.CheckConstraint(check=~models.Q(content_hash=""),
                                   name="de_content_hash_ne"),
            models.CheckConstraint(check=~models.Q(hmac_signature=""),
                                   name="de_hmac_ne"),
            models.CheckConstraint(check=~models.Q(signing_key_id=""),
                                   name="de_key_id_ne"),
        ]

    def __str__(self) -> str:
        return f"#{self.sequence_number} {self.action} ({self.event_id})"

    def save(self, *args, **kwargs):
        if kwargs.pop("_chain_write_token", None) is not _CHAIN_WRITE_TOKEN:
            raise ChainWriteViolation(
                "DecisionEvent is append-only — write it through "
                "apps.accounts.decision_chain.append_decision(), never .save().")
        if not self._state.adding:
            raise ChainWriteViolation("DecisionEvent rows are immutable once written.")
        return super().save(*args, **kwargs)


class _DecisionChainHeadQuerySet(models.QuerySet):
    def delete(self, *a, **k):
        raise ChainWriteViolation("the chain head is a permanent singleton.")


class _DecisionChainHeadManager(
        models.Manager.from_queryset(_DecisionChainHeadQuerySet)):
    def create(self, *a, **k):
        raise ChainWriteViolation(
            "the chain head singleton is created by migration genesis only.")


class DecisionChainHead(models.Model):
    """The signed terminal state of the chain — a single row (pk=1).

    Unlike DecisionEvent, the head is *advanced* by the append service on every append
    (under `select_for_update`). It is still not writable by anything else: `save()`
    requires the same capability token, and `create()`/`delete()` are blocked so the
    singleton can neither be duplicated nor removed. The migration seeds an UNSIGNED
    genesis (seq 0 / count 0 / terminal hash NULL / no signature); the first append
    validates that exact state and replaces it with a signed non-empty head in the same
    transaction.
    """

    id = models.PositiveSmallIntegerField(primary_key=True, default=1)
    chain_id = models.CharField(max_length=64, unique=True)
    terminal_sequence_number = models.PositiveBigIntegerField(default=0)
    terminal_event_hash = models.CharField(max_length=64, null=True, blank=True)
    event_count = models.PositiveBigIntegerField(default=0)
    schema_version = models.CharField(max_length=40, default=CHAIN_HEAD_SCHEMA)
    signing_key_id = models.CharField(max_length=64, blank=True, default="")
    head_signature = models.CharField(max_length=128, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)   # not signed; a bookkeeping stamp

    objects = _DecisionChainHeadManager()

    class Meta:
        verbose_name = "decision chain head"
        constraints = [
            models.CheckConstraint(check=models.Q(id=1), name="dch_singleton"),
        ]

    def __str__(self) -> str:
        return (f"head seq={self.terminal_sequence_number} count={self.event_count} "
                f"{'signed' if self.head_signature else 'GENESIS'}")

    @property
    def is_genesis(self) -> bool:
        return (self.event_count == 0 and self.terminal_sequence_number == 0
                and self.terminal_event_hash is None and not self.head_signature)

    def save(self, *args, **kwargs):
        if kwargs.pop("_chain_write_token", None) is not _CHAIN_WRITE_TOKEN:
            raise ChainWriteViolation(
                "the chain head is service-managed — advance it through "
                "apps.accounts.decision_chain, never .save().")
        return super().save(*args, **kwargs)


# --- bootstrap lifecycle (DIP-1A-5A) ---------------------------------------------
class BootstrapState(models.Model):
    """A dedicated, persisted record of whether pre-ledger bootstrap is still permitted.

    Bootstrap seeds the FIRST reviewer authority before any authorized granter exists — a
    genuine need, but also a standing elevation bypass if it never closes. So closure is a
    stored fact, not something re-derived from the current role rows each time (which could
    flap as assignments expire). Once the first PROTECTED role-management decision is
    recorded, this row is closed **permanently**; the closure only ever goes False->True,
    and re-opening is a deliberate, audited break-glass act. Singleton (pk=1).
    """

    id = models.PositiveSmallIntegerField(primary_key=True, default=1)
    closed = models.BooleanField(default=False)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by_event = models.ForeignKey(
        "DecisionEvent", on_delete=models.PROTECT, null=True, blank=True,
        related_name="+")
    # incremented each time a break-glass reopen occurs; never decremented
    break_glass_count = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "bootstrap state"
        constraints = [
            models.CheckConstraint(check=models.Q(id=1), name="bootstrap_singleton"),
        ]

    def __str__(self) -> str:
        return f"bootstrap {'CLOSED' if self.closed else 'OPEN'}"
