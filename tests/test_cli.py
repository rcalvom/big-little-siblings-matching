from __future__ import annotations

import csv
import hashlib
import json

import pytest
import yaml

from csap_siblings_match.cli import build_parser, main
from csap_siblings_match.data import BIG_FIELDS, LITTLE_FIELDS

from .factories import big, little, synthetic_config


def _write_csv(path, fields, rows) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _inputs(tmp_path, *, littles=None, big_overrides=None):
    big_path = tmp_path / "bigs.csv"
    little_path = tmp_path / "littles.csv"
    config_path = tmp_path / "policy.yaml"
    _write_csv(big_path, BIG_FIELDS, [big(**(big_overrides or {}))])
    _write_csv(
        little_path, LITTLE_FIELDS, [little()] if littles is None else littles
    )
    config_path.write_text(
        yaml.safe_dump(synthetic_config(), sort_keys=True), encoding="utf-8"
    )
    return big_path, little_path, config_path


def test_cli_runs_complete_canonical_match(tmp_path) -> None:
    big_path, little_path, config_path = _inputs(tmp_path)
    output_dir = tmp_path / "output"

    status = main(
        [
            "match",
            "--big",
            str(big_path),
            "--little",
            str(little_path),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
            "--operator",
            "synthetic-test",
        ]
    )

    assert status == 0
    assert (output_dir / "matches.csv").exists()
    assert (output_dir / "review_queue.csv").exists()
    assert (output_dir / "candidate_scores.csv").exists()
    assert (output_dir / "run_manifest.json").exists()
    manifest = json.loads((output_dir / "run_manifest.json").read_text())
    assert manifest["status"] == "complete"
    algorithm = manifest["algorithm"]
    assert algorithm["primary_objective"] == "maximum_bigs_with_at_least_one_little"
    assert algorithm["secondary_objective"] == "maximum_minimum_pair_score"
    assert algorithm["tertiary_objective"] == "maximum_total_pair_score"
    assert manifest["inputs"]["big_sha256"] == hashlib.sha256(
        big_path.read_bytes()
    ).hexdigest()
    assert len(manifest["software"]["package_code_sha256"]) == 64
    assert len(manifest["assignment_sha256"]) == 64
    assert manifest["operator"] == "synthetic-test"


def test_infeasible_cli_writes_certificate_but_no_matching(tmp_path) -> None:
    big_path, little_path, config_path = _inputs(
        tmp_path, littles=[little("L-1"), little("L-2")]
    )
    output_dir = tmp_path / "output"

    status = main(
        [
            "match",
            "--big",
            str(big_path),
            "--little",
            str(little_path),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
            "--operator",
            "synthetic-test",
        ]
    )

    assert status == 3
    assert (output_dir / "infeasibility.json").exists()
    assert not (output_dir / "matches.csv").exists()
    assert not (output_dir / "review_queue.csv").exists()


def test_normalize_subcommand_no_longer_exists() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["normalize"])


def test_cli_rejects_nonempty_output_directory(tmp_path) -> None:
    big_path, little_path, config_path = _inputs(tmp_path)
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "old.txt").write_text("old", encoding="utf-8")

    status = main(
        [
            "match",
            "--big",
            str(big_path),
            "--little",
            str(little_path),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
            "--operator",
            "synthetic-test",
        ]
    )

    assert status == 2


def test_validate_cannot_overwrite_an_input(tmp_path) -> None:
    big_path, little_path, config_path = _inputs(tmp_path)
    original = big_path.read_bytes()

    status = main(
        [
            "validate",
            "--big",
            str(big_path),
            "--little",
            str(little_path),
            "--config",
            str(config_path),
            "--report",
            str(big_path),
        ]
    )

    assert status == 2
    assert big_path.read_bytes() == original


def test_failed_report_transaction_publishes_no_partial_directory(
    tmp_path, monkeypatch
) -> None:
    big_path, little_path, config_path = _inputs(tmp_path)
    output_dir = tmp_path / "output"

    def fail_reporting(*args, **kwargs):
        raise RuntimeError("synthetic reporting failure")

    monkeypatch.setattr("csap_siblings_match.cli.write_matching_reports", fail_reporting)
    status = main(
        [
            "match",
            "--big",
            str(big_path),
            "--little",
            str(little_path),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
            "--operator",
            "synthetic-test",
        ]
    )

    assert status == 2
    assert not output_dir.exists()
    assert not (tmp_path / ".output.lock").exists()


def test_contact_report_escapes_spreadsheet_formulas(tmp_path) -> None:
    big_path, little_path, config_path = _inputs(
        tmp_path,
        littles=[little(first_name="@Little")],
        big_overrides={"first_name": "=Big"},
    )
    output_dir = tmp_path / "output"

    status = main(
        [
            "match",
            "--big",
            str(big_path),
            "--little",
            str(little_path),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
            "--operator",
            "synthetic-test",
            "--include-contacts",
        ]
    )

    contacts = (output_dir / "coordinator_contacts.csv").read_text(encoding="utf-8")
    assert "'@Little" in contacts
    assert "'=Big" in contacts


def test_operator_must_be_nonempty_clean_text(tmp_path) -> None:
    big_path, little_path, config_path = _inputs(tmp_path)
    output_dir = tmp_path / "output"

    status = main(
        [
            "match",
            "--big",
            str(big_path),
            "--little",
            str(little_path),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
            "--operator",
            "   ",
        ]
    )

    assert status == 2
    assert not output_dir.exists()
