from __future__ import annotations

from fractions import Fraction

import pytest

from csap_siblings_match.optimizer import solve_matching

from .factories import big, declared, little, pair


def assignment_map(result) -> dict[str, str]:
    return {match.little_id: match.big_id for match in result.matches}


def test_optimizer_maximizes_worst_match_before_total_score() -> None:
    bigs = [big("B-1"), big("B-2")]
    littles = [little("L-1"), little("L-2")]
    scores = [
        pair("L-1", "B-1", "0.9"),
        pair("L-1", "B-2", "0.6"),
        pair("L-2", "B-1", "0.6"),
        pair("L-2", "B-2", "0.4"),
    ]

    result = solve_matching(bigs, littles, scores, [])

    assert result.is_complete
    assert result.bottleneck_score == Fraction(3, 5)
    assert result.ordinary_total_score == Fraction(6, 5)
    assert assignment_map(result) == {"L-1": "B-2", "L-2": "B-1"}


def test_optimizer_maximizes_total_after_fixing_bottleneck() -> None:
    bigs = [big("B-1"), big("B-2")]
    littles = [little("L-1"), little("L-2")]
    scores = [
        pair("L-1", "B-1", "0.7"),
        pair("L-1", "B-2", "0.7"),
        pair("L-2", "B-1", "0.8"),
        pair("L-2", "B-2", "0.7"),
    ]

    result = solve_matching(bigs, littles, scores, [])

    assert result.bottleneck_score == Fraction(7, 10)
    assert result.ordinary_total_score == Fraction(3, 2)
    assert assignment_map(result) == {"L-1": "B-2", "L-2": "B-1"}


def test_declared_match_consumes_capacity_and_bypasses_ordinary_graph() -> None:
    bigs = [big("B-1", capacity="2"), big("B-2")]
    littles = [little("L-1"), little("L-2"), little("L-3")]
    scores = [
        pair("L-1", "B-1", "0.1"),
        pair("L-2", "B-1", "0.8"),
        pair("L-2", "B-2", "0.7"),
        pair("L-3", "B-1", "0.6"),
    ]

    result = solve_matching(bigs, littles, scores, [declared("L-1", "B-1")])

    # The declared pair takes one of B-1's two slots, L-3 has nowhere else to
    # go, and L-2 fills B-2 because reaching another Big outranks its own score.
    assert assignment_map(result) == {"L-1": "B-1", "L-2": "B-2", "L-3": "B-1"}
    assert result.bottleneck_score == Fraction(3, 5)


def test_spreading_across_bigs_outranks_both_score_objectives() -> None:
    bigs = [big("B-1", capacity="2"), big("B-2")]
    littles = [little("L-1"), little("L-2")]
    scores = [
        pair("L-1", "B-1", "0.9"),
        pair("L-2", "B-1", "0.9"),
        pair("L-2", "B-2", "0.2"),
    ]

    result = solve_matching(bigs, littles, scores, [])

    # Piling both onto B-1 would score 1.8 with a 0.9 bottleneck. Coverage is
    # the first objective, so the solver accepts 1.1 and a 0.2 bottleneck.
    assert assignment_map(result) == {"L-1": "B-1", "L-2": "B-2"}
    assert result.big_coverage == 2
    assert result.bottleneck_score == Fraction(1, 5)


def test_coverage_never_leaves_a_little_unassigned() -> None:
    bigs = [big("B-1", capacity="2"), big("B-2")]
    littles = [little("L-1"), little("L-2"), little("L-3")]
    scores = [
        pair("L-1", "B-1", "0.5"),
        pair("L-2", "B-1", "0.5"),
        pair("L-3", "B-2", "0.5"),
    ]

    result = solve_matching(bigs, littles, scores, [])

    assert len(result.matches) == 3
    assert result.big_coverage == 2


def test_infeasible_instance_returns_min_cut_and_no_partial_matches() -> None:
    result = solve_matching(
        [big("B-1")],
        [little("L-1"), little("L-2")],
        [pair("L-1", "B-1", 1), pair("L-2", "B-1", 1)],
        [],
    )

    assert not result.is_complete
    assert result.matches == ()
    assert result.diagnostic is not None
    assert result.diagnostic.required_flow == 2
    assert result.diagnostic.maximum_flow == 1
    assert result.diagnostic.cut_little_ids == ("L-1", "L-2")
    assert result.diagnostic.cut_big_ids == ("B-1",)


def test_exact_ties_use_id_order_independently_of_input_order() -> None:
    bigs = [big("B-2"), big("B-1")]
    littles = [little("L-2"), little("L-1")]
    scores = [
        pair("L-2", "B-2", 1),
        pair("L-1", "B-2", 1),
        pair("L-2", "B-1", 1),
        pair("L-1", "B-1", 1),
    ]

    result = solve_matching(bigs, littles, scores, [])
    reversed_result = solve_matching(
        list(reversed(bigs)), list(reversed(littles)), list(reversed(scores)), []
    )

    expected = {"L-1": "B-1", "L-2": "B-2"}
    assert assignment_map(result) == expected
    assert assignment_map(reversed_result) == expected


def test_big_may_hold_several_declared_littles_up_to_capacity() -> None:
    bigs = [big("B-1", capacity="2"), big("B-2")]
    littles = [little("L-1"), little("L-2"), little("L-3")]
    scores = [
        pair("L-1", "B-1", "0.1"),
        pair("L-2", "B-1", "0.1"),
        pair("L-3", "B-2", "0.9"),
    ]

    result = solve_matching(
        bigs, littles, scores, [declared("L-1", "B-1"), declared("L-2", "B-1")]
    )

    assert assignment_map(result) == {"L-1": "B-1", "L-2": "B-1", "L-3": "B-2"}
    assert len(result.declared_assignments) == 2


def test_declared_matches_may_not_exceed_declared_capacity() -> None:
    with pytest.raises(ValueError, match="capacity"):
        solve_matching(
            [big("B-1", capacity="1")],
            [little("L-1"), little("L-2")],
            [pair("L-1", "B-1", 1), pair("L-2", "B-1", 1)],
            [declared("L-1", "B-1"), declared("L-2", "B-1")],
        )


def test_declared_match_cannot_use_unavailable_big() -> None:
    with pytest.raises(ValueError, match="unavailable"):
        solve_matching(
            [big("B-1", can_commit_4_6_hours="no")],
            [little("L-1")],
            [pair("L-1", "B-1", 1)],
            [declared("L-1", "B-1")],
        )


def test_result_records_actual_integer_cost_denominator() -> None:
    scores = [
        pair("L-1", "B-1", Fraction(1, 2)),
        pair("L-1", "B-2", Fraction(1, 3)),
        pair("L-2", "B-1", Fraction(1, 4)),
        pair("L-2", "B-2", Fraction(1, 4)),
    ]

    result = solve_matching(
        [big("B-1"), big("B-2")],
        [little("L-1"), little("L-2")],
        scores,
        [],
    )

    assert result.integer_cost_denominator == 12


def test_infeasibility_preserves_declared_capacity_evidence() -> None:
    scores = [
        pair("L-1", "B-1", 1),
        pair("L-2", "B-1", 1),
        pair("L-3", "B-1", 1),
    ]
    result = solve_matching(
        [big("B-1", capacity="2")],
        [little("L-1"), little("L-2"), little("L-3")],
        scores,
        [declared("L-1", "B-1")],
    )

    assert not result.is_complete
    assert result.matches == ()
    assert len(result.declared_assignments) == 1
    assert result.diagnostic is not None
    assert result.diagnostic.residual_capacities == {"B-1": 1}


def test_numeric_id_tie_break_handles_multiple_digits() -> None:
    bigs = [big("B-10"), big("B-2")]
    littles = [little("L-10"), little("L-2")]
    scores = [
        pair(little_id, big_id, 1)
        for little_id in ("L-10", "L-2")
        for big_id in ("B-10", "B-2")
    ]

    result = solve_matching(bigs, littles, scores, [])

    assert assignment_map(result) == {"L-2": "B-2", "L-10": "B-10"}


def test_all_declared_case_has_no_ordinary_objective() -> None:
    result = solve_matching(
        [big("B-1"), big("B-2")],
        [little("L-1"), little("L-2")],
        [pair("L-1", "B-1", 1), pair("L-2", "B-2", 1)],
        [declared("L-1", "B-1"), declared("L-2", "B-2")],
    )

    assert result.is_complete
    assert result.bottleneck_score is None
    assert result.ordinary_total_score == 0
    assert result.integer_cost_denominator == 1
