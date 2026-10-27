"""
Curation serializers.

E52 — Community submission intake (SubmissionRequestSerializer,
       SubmissionResponseSerializer)
E54 — Dataset diff endpoint (DatasetDiffResponseSerializer)
"""

from __future__ import annotations

from rest_framework import serializers

from apps.curation.models import CommunitySubmission

# ---------------------------------------------------------------------------
# E52 — Community submissions
# ---------------------------------------------------------------------------


class SubmissionRequestSerializer(serializers.Serializer):
    """
    Validates an incoming community submission.

    submission_type  — must be 'dish', 'ingredient' or 'pairing'
    payload          — non-empty dict; schema is type-specific
    submitter_note   — optional free text
    """

    submission_type = serializers.ChoiceField(
        choices=CommunitySubmission.SubmissionType.choices,
        help_text="Type of content being submitted: dish, ingredient or pairing.",
    )
    payload = serializers.DictField(
        child=serializers.JSONField(),
        allow_empty=False,
        help_text="Raw submission data. Must be a non-empty object.",
    )
    submitter_note = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=2000,
        help_text="Optional note from the submitter.",
    )

    def validate_payload(self, value: dict) -> dict:
        if not value:
            raise serializers.ValidationError("Payload must not be empty.")
        return value


class SubmissionResponseSerializer(serializers.ModelSerializer):
    """Minimal response returned after a successful submission."""

    class Meta:
        model = CommunitySubmission
        fields = ["id", "submission_type", "status", "created_at"]
        read_only_fields = fields


# ---------------------------------------------------------------------------
# E54 — Dataset diff
# ---------------------------------------------------------------------------


class DiffItemSerializer(serializers.Serializer):
    """A single added/changed/removed item in the diff."""

    slug = serializers.CharField()
    name_en = serializers.CharField()
    changed_at = serializers.DateTimeField(source="updated_at", default=None)


class DatasetDiffResponseSerializer(serializers.Serializer):
    """Response shape for GET /v1/datasets/diff."""

    since_version = serializers.CharField()
    current_version = serializers.CharField()
    generated_at = serializers.DateTimeField()
    dishes = serializers.DictField()    # {added: [...], changed: [...], removed: [...]}
    ingredients = serializers.DictField()  # {added: [...], removed: [...]}
