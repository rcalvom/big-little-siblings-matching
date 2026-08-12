from __future__ import annotations

from fractions import Fraction

from csap_siblings_match.manifest import build_run_manifest
from csap_siblings_match.optimizer import solve_matching

from .factories import big, declared, little, pair, synthetic_config


def test_manifest_records_solver_denominator_and_result_digest() -> None:
    result = solve_matching(
        [big("B-1"), big("B-2")],
        [little("L-1"), little("L-2")],
        [
            pair("L-1", "B-1", Fraction(1, 2)),
            pair("L-1", "B-2", Fraction(1, 3)),
            pair("L-2", "B-1", Fraction(1, 4)),
            pair("L-2", "B-2", Fraction(1, 4)),
        ],
        [],
    )

    manifest = build_run_manifest(
        result,
        input_hashes={
            "big_sha256": "a" * 64,
            "little_sha256": "b" * 64,
            "declared_sha256": None,
        },
        config=synthetic_config(),
        exclusions=[],
        operator="test",
        include_contacts=False,
    )

    assert manifest["algorithm"]["integer_cost_denominator"] == 12
    assert len(manifest["assignment_sha256"]) == 64


def test_infeasible_manifest_preserves_declared_relationship_evidence() -> None:
    declared_match = declared("L-1", "B-1")
    result = solve_matching(
        [big("B-1", capacity="2")],
        [little("L-1"), little("L-2"), little("L-3")],
        [
            pair("L-1", "B-1", 1),
            pair("L-2", "B-1", 1),
            pair("L-3", "B-1", 1),
        ],
        [declared_match],
    )

    manifest = build_run_manifest(
        result,
        input_hashes={
            "big_sha256": "a" * 64,
            "little_sha256": "b" * 64,
            "declared_sha256": "c" * 64,
        },
        config=synthetic_config(),
        exclusions=[],
        operator="test",
        include_contacts=False,
    )

    assert manifest["counts"]["declared_matches"] == 1
    assert manifest["declared_relationships"][0]["little_id"] == "L-1"
    assert manifest["feasibility_diagnostic"]["residual_capacities"] == {"B-1": 1}
    assert manifest["assignment_sha256"] is None
