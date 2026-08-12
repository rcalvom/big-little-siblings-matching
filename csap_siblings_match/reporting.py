"""Deterministic private report writers."""

from __future__ import annotations

import csv
import io
import json
import os
import tempfile
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable

import yaml

from .manifest import fraction_text, manifest_json
from .models import OptimizationResult, PairScore, ReviewCase, ValidationResult
from .optimizer import id_key


def _decimal(value: Fraction) -> str:
    return f"{float(value):.6f}"


def _safe_cell(value: object) -> object:
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return value


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.link(temporary, path)
        os.unlink(temporary)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _write_csv(
    path: Path, fieldnames: list[str], rows: Iterable[dict[str, object]]
) -> None:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: _safe_cell(row.get(field, "")) for field in fieldnames})
    _atomic_write_text(path, buffer.getvalue())


def write_validation_report(result: ValidationResult, destination: str | Path) -> None:
    payload = {
        "error_count": len(result.errors),
        "warning_count": len(result.warnings),
        "issues": [issue.as_dict() for issue in result.issues],
    }
    _atomic_write_text(
        Path(destination), json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )


def _score_row(score: PairScore) -> dict[str, object]:
    row: dict[str, object] = {
        "little_id": score.little_id,
        "big_id": score.big_id,
        "total_score": _decimal(score.total),
        "total_score_fraction": fraction_text(score.total),
    }
    for name, value in score.components().items():
        row[name] = _decimal(value)
        row[f"{name}_fraction"] = fraction_text(value)
    return row


def _write_candidate_scores(
    destination: Path,
    pair_scores: list[PairScore],
    result: OptimizationResult,
) -> None:
    selected_matches = result.matches if result.is_complete else result.declared_assignments
    selected = {
        (match.little_id, match.big_id): match.assignment_type
        for match in selected_matches
    }
    component_fields = [
        "priority_alignment",
        "bachelor_degree",
        "undergrad_university",
        "home_location",
        "purdue_college",
        "advisor",
    ]
    rows = []
    for score in sorted(
        pair_scores,
        key=lambda item: (id_key(item.little_id), id_key(item.big_id)),
    ):
        row = _score_row(score)
        row["selected_as"] = selected.get((score.little_id, score.big_id), "")
        rows.append(row)
    fields = [
        "little_id",
        "big_id",
        "selected_as",
        "total_score",
        "total_score_fraction",
    ]
    for component in component_fields:
        fields.extend((component, f"{component}_fraction"))
    _write_csv(destination / "candidate_scores.csv", fields, rows)


def _write_exclusions(
    destination: Path, exclusions: Iterable[dict[str, str]]
) -> None:
    rows = sorted(
        exclusions,
        key=lambda row: (id_key(row["little_id"]), id_key(row["big_id"]), row["reason"]),
    )
    _write_csv(
        destination / "eligibility_exclusions.csv",
        ["little_id", "big_id", "reason"],
        rows,
    )


def _write_audit_files(
    destination: Path, config: dict[str, Any], manifest: dict[str, Any]
) -> None:
    _atomic_write_text(
        destination / "effective_policy.yaml",
        yaml.safe_dump(config, sort_keys=True),
    )
    _atomic_write_text(destination / "run_manifest.json", manifest_json(manifest))


def _write_declared_relationships(
    destination: Path, result: OptimizationResult
) -> None:
    rows = [
        {
            "little_id": match.little_id,
            "big_id": match.big_id,
            "reason": match.note,
        }
        for match in result.declared_assignments
    ]
    _write_csv(
        destination / "declared_relationships.csv",
        ["little_id", "big_id", "reason"],
        rows,
    )


def write_matching_reports(
    result: OptimizationResult,
    bigs: list[dict[str, str]],
    littles: list[dict[str, str]],
    pair_scores: list[PairScore],
    review_cases: list[ReviewCase],
    output_dir: str | Path,
    *,
    config: dict[str, Any],
    manifest: dict[str, Any],
    include_contacts: bool = False,
    exclusions: Iterable[dict[str, str]] = (),
) -> None:
    if not result.is_complete:
        raise ValueError("Complete matching reports require a feasible result.")
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    big_by_id = {big["big_id"]: big for big in bigs}
    little_by_id = {little["little_id"]: little for little in littles}

    match_rows = []
    for match in result.matches:
        row = _score_row(match.pair_score)
        row.update(
            {
                "assignment_type": match.assignment_type,
                "reason": match.note,
            }
        )
        match_rows.append(row)
    fields = [
        "little_id",
        "big_id",
        "assignment_type",
        "total_score",
        "total_score_fraction",
        "priority_alignment",
        "priority_alignment_fraction",
        "bachelor_degree",
        "bachelor_degree_fraction",
        "undergrad_university",
        "undergrad_university_fraction",
        "home_location",
        "home_location_fraction",
        "purdue_college",
        "purdue_college_fraction",
        "advisor",
        "advisor_fraction",
        "reason",
    ]
    _write_csv(destination / "matches.csv", fields, match_rows)

    review_rows = [
        {
            "little_id": case.little_id,
            "big_id": case.big_id,
            "assignment_type": case.assignment_type,
            "total_score": _decimal(case.total_score),
            "total_score_fraction": fraction_text(case.total_score),
            "candidate_count": case.candidate_count,
            "regret": _decimal(case.regret),
            "regret_fraction": fraction_text(case.regret),
            "sensitivity": _decimal(case.sensitivity),
            "sensitivity_fraction": fraction_text(case.sensitivity),
            "exception_risk": _decimal(case.exception_risk),
            "exception_risk_fraction": fraction_text(case.exception_risk),
            "combined_risk": _decimal(case.combined_risk),
            "combined_risk_fraction": fraction_text(case.combined_risk),
        }
        for case in review_cases
    ]
    _write_csv(
        destination / "review_queue.csv",
        [
            "little_id",
            "big_id",
            "assignment_type",
            "total_score",
            "total_score_fraction",
            "candidate_count",
            "regret",
            "regret_fraction",
            "sensitivity",
            "sensitivity_fraction",
            "exception_risk",
            "exception_risk_fraction",
            "combined_risk",
            "combined_risk_fraction",
        ],
        review_rows,
    )
    _write_candidate_scores(destination, pair_scores, result)
    _write_exclusions(destination, exclusions)
    _write_declared_relationships(destination, result)

    summary = {
        "status": "complete",
        "assigned_littles": len(result.matches),
        "declared_assignments": sum(
            match.assignment_type == "declared" for match in result.matches
        ),
        "optimized_assignments": sum(
            match.assignment_type == "optimized" for match in result.matches
        ),
        "bigs_newly_covered": result.big_coverage,
        "bottleneck_score": fraction_text(result.bottleneck_score),
        "ordinary_total_score": fraction_text(result.ordinary_total_score),
    }
    _atomic_write_text(
        destination / "summary.json",
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
    )
    _write_audit_files(destination, config, manifest)

    if include_contacts:
        contact_rows = []
        for match in result.matches:
            big = big_by_id[match.big_id]
            little = little_by_id[match.little_id]
            contact_rows.append(
                {
                    "little_id": match.little_id,
                    "little_name": f"{little['first_name']} {little['last_name']}",
                    "little_email": little["email"],
                    "big_id": match.big_id,
                    "big_name": f"{big['first_name']} {big['last_name']}",
                    "big_email": big["email"],
                }
            )
        _write_csv(
            destination / "coordinator_contacts.csv",
            [
                "little_id",
                "little_name",
                "little_email",
                "big_id",
                "big_name",
                "big_email",
            ],
            contact_rows,
        )


def write_infeasibility_reports(
    result: OptimizationResult,
    pair_scores: list[PairScore],
    output_dir: str | Path,
    *,
    config: dict[str, Any],
    manifest: dict[str, Any],
    exclusions: Iterable[dict[str, str]] = (),
) -> None:
    if result.is_complete or result.diagnostic is None:
        raise ValueError("Infeasibility reports require an incomplete result.")
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    _atomic_write_text(
        destination / "infeasibility.json",
        json.dumps(result.diagnostic.as_dict(), indent=2, sort_keys=True) + "\n",
    )
    _write_candidate_scores(destination, pair_scores, result)
    _write_exclusions(destination, exclusions)
    _write_declared_relationships(destination, result)
    summary = {
        "status": "infeasible",
        "declared_assignments": len(result.declared_assignments),
        "required_flow": result.diagnostic.required_flow,
        "maximum_flow": result.diagnostic.maximum_flow,
        "deficit": result.diagnostic.deficit,
    }
    _atomic_write_text(
        destination / "summary.json",
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
    )
    _write_audit_files(destination, config, manifest)
