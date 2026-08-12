"""Strict ingestion and validation for canonical private CSV inputs."""

from __future__ import annotations

import csv
import hashlib
import io
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from .config import CATALOG_NAMES, catalog_entry
from .models import DeclaredMatch, ValidationResult


PRIORITY_FIELDS = (
    "priority_academic_mentoring_rank",
    "priority_emotional_support_rank",
    "priority_local_integration_rank",
    "priority_graduate_research_rank",
    "priority_social_activities_rank",
)

BIG_FIELDS = (
    "big_id",
    "first_name",
    "last_name",
    "email",
    "gender_identity",
    "same_gender_mentorship",
    "bachelor_degree",
    "undergrad_university",
    "home_location",
    "purdue_college",
    "advisor",
    *PRIORITY_FIELDS,
    "accepts_non_colombian_little",
    "can_commit_4_6_hours",
    "capacity",
)

LITTLE_FIELDS = (
    "little_id",
    "first_name",
    "last_name",
    "email",
    "gender_identity",
    "same_gender_mentorship",
    "is_colombian",
    "bachelor_degree",
    "undergrad_university",
    "home_location",
    "purdue_college",
    "advisor",
    *PRIORITY_FIELDS,
)

DECLARED_FIELDS = (
    "little_id",
    "big_id",
    "reason",
)

def parse_yes_no(value: Any) -> bool | None:
    if value == "yes":
        return True
    if value == "no":
        return False
    return None


def priority_ranks(record: dict[str, str]) -> tuple[int, ...]:
    return tuple(int(record[field]) for field in PRIORITY_FIELDS)


def _expected_fields(role: str) -> tuple[str, ...]:
    if role == "big":
        return BIG_FIELDS
    if role == "little":
        return LITTLE_FIELDS
    raise ValueError("role must be either 'big' or 'little'.")


def read_canonical_csv_with_hash(
    path: str | Path, role: str
) -> tuple[list[dict[str, str]], str]:
    source = Path(path)
    if source.suffix.lower() != ".csv":
        raise ValueError("Canonical participant inputs must be CSV files.")
    expected = list(_expected_fields(role))
    raw = source.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError(f"Canonical {role} CSV must be valid UTF-8.") from error
    try:
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        actual = list(reader.fieldnames or [])
        if actual != expected:
            raise ValueError(
                f"Canonical {role} CSV headers must exactly match the published schema "
                "and order."
            )
        rows: list[dict[str, str]] = []
        for row in reader:
            if None in row:
                raise ValueError(f"Canonical {role} CSV contains extra cell values.")
            record = {field: str(row.get(field) or "") for field in expected}
            rows.append(record)
    except csv.Error as error:
        raise ValueError(f"Canonical {role} CSV syntax is invalid.") from error
    return rows, hashlib.sha256(raw).hexdigest()


def read_canonical_csv(path: str | Path, role: str) -> list[dict[str, str]]:
    records, _ = read_canonical_csv_with_hash(path, role)
    return records


def load_bigs(path: str | Path) -> list[dict[str, str]]:
    return read_canonical_csv(path, "big")


def load_littles(path: str | Path) -> list[dict[str, str]]:
    return read_canonical_csv(path, "little")


def load_declared_matches_with_hash(
    path: str | Path | None,
) -> tuple[list[DeclaredMatch], str | None]:
    if path is None:
        return [], None
    source = Path(path)
    if not source.exists():
        raise ValueError(f"Declared-match file does not exist: {source}.")
    if source.suffix.lower() != ".csv":
        raise ValueError("Declared matches must be provided as a CSV file.")
    raw = source.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("Declared-match CSV must be valid UTF-8.") from error
    try:
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        actual = list(reader.fieldnames or [])
        if actual != list(DECLARED_FIELDS):
            raise ValueError(
                "Declared-match CSV headers must exactly match "
                f"{list(DECLARED_FIELDS)!r}."
            )
        matches: list[DeclaredMatch] = []
        for row in reader:
            if None in row:
                raise ValueError("Declared-match CSV contains extra cell values.")
            matches.append(
                DeclaredMatch(
                    little_id=str(row["little_id"] or ""),
                    big_id=str(row["big_id"] or ""),
                    reason=str(row["reason"] or ""),
                )
            )
    except csv.Error as error:
        raise ValueError("Declared-match CSV syntax is invalid.") from error
    return matches, hashlib.sha256(raw).hexdigest()


def load_declared_matches(path: str | Path | None) -> list[DeclaredMatch]:
    matches, _ = load_declared_matches_with_hash(path)
    return matches


def _add_required_and_clean_text_issues(
    records: list[dict[str, str]], role: str, id_field: str, result: ValidationResult
) -> None:
    expected = _expected_fields(role)
    for record in records:
        participant_id = record.get(id_field) or None
        for field in expected:
            value = record.get(field, "")
            if not value:
                result.add(
                    "error",
                    "missing_required_field",
                    "A canonical required field is empty.",
                    role,
                    participant_id,
                    field,
                )
                continue
            if value != value.strip() or unicodedata.normalize("NFC", value) != value:
                result.add(
                    "error",
                    "unclean_text",
                    "Canonical text must be trimmed and NFC-normalized.",
                    role,
                    participant_id,
                    field,
                )
            if any(
                unicodedata.category(char) in {"Cc", "Cs"} or char == "\ufeff"
                for char in value
            ):
                result.add(
                    "error",
                    "control_character",
                    "Canonical text must not contain control characters.",
                    role,
                    participant_id,
                    field,
                )


def _validate_unique_ids(
    records: list[dict[str, str]], role: str, id_field: str, result: ValidationResult
) -> None:
    prefix = "B" if role == "big" else "L"
    seen: set[str] = set()
    for record in records:
        participant_id = record.get(id_field, "")
        if participant_id and not re.fullmatch(rf"{prefix}-\d+", participant_id):
            result.add(
                "error",
                "invalid_id",
                f"Canonical {role} IDs must use the form {prefix}-<source number>.",
                role,
                participant_id or None,
                id_field,
            )
        if participant_id in seen:
            result.add(
                "error",
                "duplicate_id",
                "Participant IDs must be unique within each role.",
                role,
                participant_id or None,
                id_field,
            )
        seen.add(participant_id)


def _validate_common_record(
    record: dict[str, str],
    role: str,
    participant_id: str,
    config: dict[str, Any],
    result: ValidationResult,
) -> None:
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", record.get("email", "")):
        result.add(
            "error",
            "invalid_email",
            "A canonical contact email is required.",
            role,
            participant_id,
            "email",
        )

    same_gender = parse_yes_no(record.get("same_gender_mentorship"))
    if same_gender is None:
        result.add(
            "error",
            "invalid_same_gender_preference",
            "same_gender_mentorship must be yes or no.",
            role,
            participant_id,
            "same_gender_mentorship",
        )
    disclosed = set(config["gender"]["disclosed_values"])
    allowed_genders = disclosed | set(config["gender"]["not_disclosed_values"])
    gender = record.get("gender_identity", "")
    if gender and gender not in allowed_genders:
        result.add(
            "error",
            "invalid_gender_identity",
            "gender_identity is absent from the effective policy domain.",
            role,
            participant_id,
            "gender_identity",
        )
    if same_gender is True and gender not in disclosed:
        result.add(
            "error",
            "unresolvable_same_gender_preference",
            "A same-gender requirement needs a disclosed canonical gender identity.",
            role,
            participant_id,
            "gender_identity",
        )

    try:
        ranks = priority_ranks(record)
    except (KeyError, ValueError):
        ranks = ()
    if sorted(ranks) != [1, 2, 3, 4, 5]:
        result.add(
            "error",
            "invalid_priority_ranking",
            "The five priority ranks must be a permutation of 1 through 5.",
            role,
            participant_id,
            "priority_ranking",
        )


def _validate_catalog_values(
    record: dict[str, str],
    role: str,
    participant_id: str,
    config: dict[str, Any],
    result: ValidationResult,
) -> None:
    for catalog in CATALOG_NAMES:
        value = record.get(catalog, "")
        if not value:
            continue
        try:
            catalog_entry(config, catalog, value)
        except KeyError:
            result.add(
                "error",
                "unmapped_canonical_value",
                "Canonical value is absent from the effective policy catalog.",
                role,
                participant_id,
                catalog,
            )


def validate_participants(
    bigs: list[dict[str, str]],
    littles: list[dict[str, str]],
    declared_matches: Iterable[DeclaredMatch],
    config: dict[str, Any],
) -> ValidationResult:
    """Validate the complete canonical contract without inferring any value."""

    result = ValidationResult()
    if not bigs:
        result.add(
            "error",
            "empty_big_cohort",
            "At least one canonical Big record is required.",
            "big",
        )
    if not littles:
        result.add(
            "error",
            "empty_little_cohort",
            "At least one canonical Little record is required.",
            "little",
        )
    _add_required_and_clean_text_issues(bigs, "big", "big_id", result)
    _add_required_and_clean_text_issues(littles, "little", "little_id", result)
    _validate_unique_ids(bigs, "big", "big_id", result)
    _validate_unique_ids(littles, "little", "little_id", result)

    for big in bigs:
        big_id = big.get("big_id", "")
        _validate_common_record(big, "big", big_id, config, result)
        _validate_catalog_values(big, "big", big_id, config, result)
        for field in ("accepts_non_colombian_little", "can_commit_4_6_hours"):
            if parse_yes_no(big.get(field)) is None:
                result.add(
                    "error",
                    "invalid_yes_no",
                    "Canonical policy fields must be yes or no.",
                    "big",
                    big_id,
                    field,
                )
        try:
            capacity = int(big.get("capacity", ""))
            if capacity <= 0:
                raise ValueError
        except ValueError:
            result.add(
                "error",
                "invalid_capacity",
                "capacity must be a positive integer.",
                "big",
                big_id,
                "capacity",
            )

    for little in littles:
        little_id = little.get("little_id", "")
        _validate_common_record(little, "little", little_id, config, result)
        _validate_catalog_values(little, "little", little_id, config, result)
        if parse_yes_no(little.get("is_colombian")) is None:
            result.add(
                "error",
                "invalid_is_colombian",
                "is_colombian must be yes or no.",
                "little",
                little_id,
                "is_colombian",
            )

    _validate_declared_matches(bigs, littles, list(declared_matches), result)
    return result


def _validate_declared_matches(
    bigs: list[dict[str, str]],
    littles: list[dict[str, str]],
    matches: list[DeclaredMatch],
    result: ValidationResult,
) -> None:
    big_by_id = {big.get("big_id", ""): big for big in bigs}
    little_ids = {little.get("little_id", "") for little in littles}
    big_counts: Counter[str] = Counter()
    little_counts: Counter[str] = Counter()
    seen_pairs: set[tuple[str, str]] = set()

    for match in matches:
        metadata = {
            "little_id": match.little_id,
            "big_id": match.big_id,
            "reason": match.reason,
        }
        for field, value in metadata.items():
            if not value:
                result.add(
                    "error",
                    "missing_declared_metadata",
                    "Every declared-match field is required.",
                    "declared_match",
                    match.little_id or None,
                    field,
                )
            elif (
                value != value.strip()
                or unicodedata.normalize("NFC", value) != value
                or any(
                    unicodedata.category(char) in {"Cc", "Cs"}
                    or char == "\ufeff"
                    for char in value
                )
            ):
                result.add(
                    "error",
                    "unclean_declared_metadata",
                    "Declared-match text must use clean canonical values.",
                    "declared_match",
                    match.little_id or None,
                    field,
                )
        pair = (match.little_id, match.big_id)
        if pair in seen_pairs:
            result.add(
                "error",
                "duplicate_declared_match",
                "A declared relationship must appear only once.",
                "declared_match",
                match.little_id,
            )
        seen_pairs.add(pair)
        big_counts[match.big_id] += 1
        little_counts[match.little_id] += 1

        if match.little_id not in little_ids:
            result.add(
                "error",
                "unknown_declared_little",
                "Declared relationship references an unknown Little ID.",
                "declared_match",
                match.little_id,
                "little_id",
            )
        big = big_by_id.get(match.big_id)
        if big is None:
            result.add(
                "error",
                "unknown_declared_big",
                "Declared relationship references an unknown Big ID.",
                "declared_match",
                match.big_id,
                "big_id",
            )
        elif parse_yes_no(big.get("can_commit_4_6_hours")) is not True:
            result.add(
                "error",
                "declared_big_unavailable",
                "A declared relationship cannot use an unavailable Big.",
                "declared_match",
                match.big_id,
                "big_id",
            )

    for little_id, count in little_counts.items():
        if count > 1:
            result.add(
                "error",
                "conflicting_declared_little",
                "A Little may have at most one declared Big.",
                "declared_match",
                little_id,
                "little_id",
            )
    for big_id, count in big_counts.items():
        big = big_by_id.get(big_id)
        if big is not None and str(big.get("capacity", "")).isdigit():
            if count > int(big["capacity"]):
                result.add(
                    "error",
                    "declared_capacity_exceeded",
                    "Declared relationships exceed declared capacity.",
                    "big",
                    big_id,
                    "capacity",
                )
