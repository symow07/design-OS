"""§BH54(b) (k) 3 — THE OWNER'S CHANNEL: the records of acts that are the owner's alone.

"ACCEPTANCE is my act alone, through the §BH26(a)-shaped channel, carrying my identity, the time, and the sha256 of
exactly what I accepted. The machine may never write it." (OWNER RULING §BH54(b), the second block, (k) 3.)

The §BH26(a) shape, measured on the font grant (apps/ire/container_font_owner_grant.py): owner data, keyed by the sha256
of the exact thing, who and when, re-verified on every read, VOID on mismatch and never an error-shaped pass, conferring
nothing on what it does not name. A row here is written by ONE door — apps/dashboard/owner_channel.py, called by the
owner's own signed-in click — and the three fields are not nullable at the database either: a row lacking one cannot exist.
Rows are never updated: a second act is a second row.
"""
from django.conf import settings
from django.db import models
from django.db.models import Q

SHA256_RE = r"^[0-9a-f]{64}$"


class OwnerAcceptance(models.Model):
    """One act of the owner on one picture he looked at in the design loop: ACCEPTED or REJECTED, by eye."""

    ACCEPTED, REJECTED = "ACCEPTED", "REJECTED"
    DECISIONS = [(ACCEPTED, "Accepted"), (REJECTED, "Rejected")]

    task = models.ForeignKey("pipeline.DesignTask", on_delete=models.PROTECT, related_name="owner_acceptances")
    study = models.CharField(max_length=100)
    picture = models.CharField(max_length=40)
    decision = models.CharField(max_length=10, choices=DECISIONS)
    # the three fields — none nullable, none blank
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    decided_at = models.DateTimeField()
    picture_sha256 = models.CharField(max_length=64)      # the sha256 of exactly what he accepted: the PNG's bytes
    # what the picture was drawn from, beside it
    inputs_sha256 = models.CharField(max_length=64)
    knobs = models.JSONField(default=dict, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-decided_at", "-pk"]
        constraints = [
            models.CheckConstraint(check=Q(picture_sha256__regex=SHA256_RE), name="owner_acceptance_picture_sha256"),
            models.CheckConstraint(check=Q(inputs_sha256__regex=SHA256_RE), name="owner_acceptance_inputs_sha256"),
            models.CheckConstraint(check=Q(decision__in=["ACCEPTED", "REJECTED"]), name="owner_acceptance_decision"),
        ]

    def __str__(self):
        return f"{self.decision} {self.study}/{self.picture} {self.picture_sha256[:16]} by {self.decided_by_id}"


COPY_PIECES = ("DESCRIPTION", "INGREDIENTS", "DIRECTIONS", "WARNINGS", "MANUFACTURER", "NET CONTENT")


class OwnerCopy(models.Model):
    """§BH54(b) (k) 4 — THE COPY CHANNEL: one piece of the back panel's copy, typed by the owner into the product from
    the loop page — "the words landing as my act with the same three fields": who typed them, when, and the sha256 of
    exactly those words. The newest row of a piece is the product's copy for it; earlier rows are its history. A row is
    never updated, and the governed path reads a piece as written ONLY through a row whose words still hash to its
    sha256 — anything else stays CONTENT_VERIFICATION_REQUIRED."""

    PIECES = COPY_PIECES

    product = models.ForeignKey("core.Product", on_delete=models.PROTECT, related_name="owner_copy")
    piece = models.CharField(max_length=20, choices=[(p, p.title()) for p in COPY_PIECES])
    text = models.TextField()
    # the three fields — none nullable, none blank
    typed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    typed_at = models.DateTimeField()
    text_sha256 = models.CharField(max_length=64)          # the sha256 of exactly the words he typed (UTF-8)

    class Meta:
        ordering = ["-typed_at", "-pk"]
        constraints = [
            models.CheckConstraint(check=Q(text_sha256__regex=SHA256_RE), name="owner_copy_text_sha256"),
            models.CheckConstraint(check=Q(piece__in=COPY_PIECES), name="owner_copy_piece"),
            models.CheckConstraint(check=~Q(text=""), name="owner_copy_words"),
        ]

    def __str__(self):
        return f"{self.piece} of product {self.product_id} {self.text_sha256[:16]} by {self.typed_by_id}"


class DesignAcceptance(models.Model):
    """§BH55 PHASE 1 — HIS ACCEPTANCE OF A GOVERNED DESIGN: one act of the owner on the design a pipeline stage produced
    (its governed output), ACCEPTED or REJECTED by eye, carrying the three fields — his identity, the time, and the
    sha256 of exactly the preview he looked at. §BH55 clause 6: "Acceptance is my act and carries my identity, the time
    and the hash." Written by ONE door (owner_channel.record_design_acceptance, called by his signed-in click); rows are
    never updated — a second act is a second row; re-verified against the preview's bytes on every read."""

    ACCEPTED, REJECTED = "ACCEPTED", "REJECTED"
    DECISIONS = [(ACCEPTED, "Accepted"), (REJECTED, "Rejected")]

    task = models.ForeignKey("pipeline.DesignTask", on_delete=models.PROTECT, related_name="design_acceptances")
    output = models.ForeignKey("pipeline.PackagingOutput", on_delete=models.PROTECT, related_name="design_acceptances")
    decision = models.CharField(max_length=10, choices=DECISIONS)
    # the three fields — none nullable, none blank
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    decided_at = models.DateTimeField()
    preview_sha256 = models.CharField(max_length=64)       # the sha256 of the preview PNG's bytes, as he saw them
    preview_name = models.CharField(max_length=255)        # which file that was — the name travels, the bytes decide
    note = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-decided_at", "-pk"]
        constraints = [
            models.CheckConstraint(check=Q(preview_sha256__regex=SHA256_RE), name="design_acceptance_preview_sha256"),
            models.CheckConstraint(check=Q(decision__in=["ACCEPTED", "REJECTED"]), name="design_acceptance_decision"),
            models.CheckConstraint(check=~Q(preview_name=""), name="design_acceptance_preview_name"),
        ]

    def __str__(self):
        return f"{self.decision} output {self.output_id} {self.preview_sha256[:16]} by {self.decided_by_id}"
