from __future__ import annotations

import csv
import hashlib

import pytest

from csap_siblings_match.data import (
    BIG_FIELDS,
    load_bigs,
    parse_yes_no,
    read_canonical_csv_with_hash,
    validate_participants,
)
from csap_siblings_match.models import DeclaredMatch
from .factories import big, declared, little, synthetic_config


def _write(path, fields, rows) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_reads_only_exact_canonical_csv_schema(tmp_path) -> None:
    path = tmp_path / "bigs.csv"
    _write(path, BIG_FIELDS, [big()])

    assert load_bigs(path) == [big()]

    wrong = tmp_path / "wrong.csv"
    _write(wrong, list(reversed(BIG_FIELDS)), [big()])
    with pytest.raises(ValueError, match="exactly match"):
        load_bigs(wrong)


def test_rejects_xlsx_inputs() -> None:
    with pytest.raises(ValueError, match="must be CSV"):
        load_bigs("responses.xlsx")


def test_validation_requires_mapped_complete_values() -> None:
    config = synthetic_config()
    validation = validate_participants(
        [big()],
        [little(email="", bachelor_degree="Unmapped Degree")],
        [],
        config,
    )

    codes = {issue.code for issue in validation.errors}
    assert "missing_required_field" in codes
    assert "invalid_email" in codes
    assert "unmapped_canonical_value" in codes


def test_priority_ranks_must_be_permutation() -> None:
    validation = validate_participants(
        [big()],
        [little(priority_social_activities_rank="1")],
        [],
        synthetic_config(),
    )

    assert any(issue.code == "invalid_priority_ranking" for issue in validation.errors)


def test_declared_relationship_requires_available_big_and_unique_little() -> None:
    validation = validate_participants(
        [big("B-1"), big("B-2", can_commit_4_6_hours="no")],
        [little("L-1"), little("L-2")],
        [
            declared("L-1", "B-1"),
            declared("L-2", "B-1"),
            declared("L-1", "B-2"),
        ],
        synthetic_config(),
    )

    codes = {issue.code for issue in validation.errors}
    assert "declared_capacity_exceeded" in codes
    assert "conflicting_declared_little" in codes
    assert "declared_big_unavailable" in codes


def test_a_big_may_declare_several_littles_within_capacity() -> None:
    validation = validate_participants(
        [big("B-1", capacity="2")],
        [little("L-1"), little("L-2")],
        [declared("L-1", "B-1"), declared("L-2", "B-1")],
        synthetic_config(),
    )

    assert validation.is_valid


def test_contact_fields_do_not_need_to_be_canonical_catalog_values() -> None:
    validation = validate_participants(
        [big(first_name="Synthetic Name")],
        [little(last_name="Synthetic Family")],
        [],
        synthetic_config(),
    )

    assert validation.is_valid


def test_canonical_booleans_are_literal_and_gender_domain_is_closed() -> None:
    assert parse_yes_no("yes") is True
    assert parse_yes_no("YES") is None

    validation = validate_participants(
        [big(gender_identity="prefer_not_to_self_describe")],
        [little()],
        [],
        synthetic_config(),
    )
    assert any(issue.code == "invalid_gender_identity" for issue in validation.errors)


def test_empty_cohorts_are_invalid() -> None:
    validation = validate_participants([], [], [], synthetic_config())

    assert {issue.code for issue in validation.errors} >= {
        "empty_big_cohort",
        "empty_little_cohort",
    }


def test_input_hash_covers_exact_parsed_bytes(tmp_path) -> None:
    path = tmp_path / "bigs.csv"
    _write(path, BIG_FIELDS, [big()])

    records, digest = read_canonical_csv_with_hash(path, "big")

    assert records == [big()]
    assert digest == hashlib.sha256(path.read_bytes()).hexdigest()


def test_catalog_matching_is_literal_not_implicit_fuzzy_matching() -> None:
    validation = validate_participants(
        [big()],
        [little(bachelor_degree="mechanical engineering")],
        [],
        synthetic_config(),
    )

    assert any(
        issue.code == "unmapped_canonical_value"
        and issue.field == "bachelor_degree"
        for issue in validation.errors
    )


def test_declared_relationship_requires_a_reason() -> None:
    validation = validate_participants(
        [big()],
        [little()],
        [DeclaredMatch("L-1", "B-1", "")],
        synthetic_config(),
    )

    assert any(
        issue.code == "missing_declared_metadata" for issue in validation.errors
    )


def test_delimiter_only_row_is_not_silently_dropped(tmp_path) -> None:
    path = tmp_path / "bigs.csv"
    _write(path, BIG_FIELDS, [{}])

    records = load_bigs(path)
    validation = validate_participants(records, [little()], [], synthetic_config())

    assert len(records) == 1
    assert any(issue.code == "missing_required_field" for issue in validation.errors)


def test_header_error_does_not_echo_private_first_row(tmp_path) -> None:
    path = tmp_path / "bigs.csv"
    private_value = "private-person@example.test"
    path.write_text(f"Private Name,{private_value}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="headers must exactly match") as captured:
        load_bigs(path)

    assert private_value not in str(captured.value)
