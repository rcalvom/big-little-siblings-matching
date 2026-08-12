from __future__ import annotations

from fractions import Fraction

from csap_siblings_match.optimizer import solve_matching
from csap_siblings_match.review import build_review_queue

from .factories import big, declared, little, pair, synthetic_config


def test_review_queue_combines_score_candidates_and_declared_exception() -> None:
    bigs = [big("B-1", capacity="2")]
    littles = [little("L-1"), little("L-2")]
    scores = [pair("L-1", "B-1", "0.9"), pair("L-2", "B-1", "0.5")]
    declared_matches = [declared("L-1", "B-1")]
    result = solve_matching(bigs, littles, scores, declared_matches)

    cases = build_review_queue(
        result, bigs, littles, scores, declared_matches, synthetic_config()
    )
    by_little = {case.little_id: case for case in cases}

    assert by_little["L-1"].exception_risk == 1
    assert by_little["L-2"].exception_risk == 0
    assert by_little["L-1"].sensitivity == 0
    assert all(Fraction() <= case.combined_risk <= 1 for case in cases)


def test_policy_can_disable_expensive_sensitivity_runs(monkeypatch) -> None:
    bigs = [big("B-1")]
    littles = [little("L-1")]
    scores = [pair("L-1", "B-1", 1)]
    result = solve_matching(bigs, littles, scores, [])
    config = synthetic_config()
    config["review"]["sensitivity_enabled"] = False

    def unexpected_solver_call(*args, **kwargs):
        raise AssertionError("sensitivity solver should not run")

    monkeypatch.setattr("csap_siblings_match.review.solve_matching", unexpected_solver_call)
    cases = build_review_queue(result, bigs, littles, scores, [], config)

    assert cases[0].sensitivity == 0
