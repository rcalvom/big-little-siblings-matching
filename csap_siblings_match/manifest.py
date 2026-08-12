"""Reproducible, privacy-preserving run manifest."""

from __future__ import annotations

import hashlib
import json
import platform
from datetime import UTC, datetime
from fractions import Fraction
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Iterable

import networkx as nx
import yaml

from .models import OptimizationResult


def fraction_text(value: Fraction | None) -> str | None:
    if value is None:
        return None
    return f"{value.numerator}/{value.denominator}"


def config_sha256(config: dict[str, Any]) -> str:
    payload = yaml.safe_dump(config, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _package_version() -> str:
    try:
        return version("csap-siblings-match")
    except PackageNotFoundError:
        return "unknown"


def _package_code_sha256() -> str:
    root = Path(__file__).resolve().parent
    digest = hashlib.sha256()
    for path in sorted(
        candidate
        for candidate in root.rglob("*")
        if candidate.is_file() and candidate.suffix in {".py", ".yaml"}
    ):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def software_provenance() -> dict[str, str]:
    """Snapshot software provenance before the matching computation starts."""

    return {
        "package_version": _package_version(),
        "package_code_sha256": _package_code_sha256(),
        "python_version": platform.python_version(),
        "networkx_version": nx.__version__,
        "pyyaml_version": yaml.__version__,
    }


def _assignment_sha256(result: OptimizationResult) -> str | None:
    if not result.is_complete:
        return None
    rows = [
        "|".join(
            (
                match.little_id,
                match.big_id,
                match.assignment_type,
                fraction_text(match.pair_score.total) or "",
                match.note,
            )
        )
        for match in result.matches
    ]
    return hashlib.sha256("\n".join(rows).encode("utf-8")).hexdigest()


def build_run_manifest(
    result: OptimizationResult,
    *,
    input_hashes: dict[str, str | None],
    config: dict[str, Any],
    exclusions: Iterable[dict[str, str]],
    operator: str,
    include_contacts: bool,
    software: dict[str, str] | None = None,
) -> dict[str, Any]:
    exclusions = list(exclusions)
    declared_rows = [
        {
            "little_id": match.little_id,
            "big_id": match.big_id,
            "reason": match.note,
        }
        for match in result.declared_assignments
    ]
    return {
        "created_at_utc": datetime.now(UTC).isoformat(),
        "operator": operator,
        "schema_version": str(config["schema_version"]),
        "policy_version": str(config["policy_version"]),
        "status": "complete" if result.is_complete else "infeasible",
        "inputs": {
            "big_sha256": input_hashes["big_sha256"],
            "little_sha256": input_hashes["little_sha256"],
            "declared_sha256": input_hashes["declared_sha256"],
            "effective_policy_sha256": config_sha256(config),
        },
        "software": software or software_provenance(),
        "algorithm": {
            "feasibility": "maximum_flow_with_min_cut_certificate",
            "primary_objective": "maximum_bigs_with_at_least_one_little",
            "secondary_objective": "maximum_minimum_pair_score",
            "tertiary_objective": "maximum_total_pair_score",
            "tie_break": "lexicographic_by_canonical_ids",
            "score_arithmetic": "exact_rational",
            "integer_cost_denominator": result.integer_cost_denominator,
        },
        "objective": {
            "bigs_newly_covered": result.big_coverage,
            "bottleneck_score": fraction_text(result.bottleneck_score),
            "ordinary_total_score": fraction_text(result.ordinary_total_score),
        },
        "counts": {
            "matches": len(result.matches),
            "declared_matches": len(result.declared_assignments),
            "optimized_matches": sum(
                match.assignment_type == "optimized" for match in result.matches
            ),
            "eligibility_exclusions": len(exclusions),
        },
        "include_contacts": include_contacts,
        "assignment_sha256": _assignment_sha256(result),
        "declared_relationships": declared_rows,
        "feasibility_diagnostic": result.diagnostic.as_dict()
        if result.diagnostic
        else None,
    }


def manifest_json(manifest: dict[str, Any]) -> str:
    return json.dumps(manifest, indent=2, sort_keys=True) + "\n"
