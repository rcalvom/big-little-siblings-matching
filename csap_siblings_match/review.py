"""Risk-based human review ranking for complete matching results."""

from __future__ import annotations

from collections import Counter
from fractions import Fraction
from typing import Any

from .config import COMPONENT_NAMES, parse_fraction
from .models import DeclaredMatch, OptimizationResult, PairScore, ReviewCase
from .optimizer import id_key, solve_matching
from .scoring import reweight_score


def _weight_scenarios(config: dict[str, Any]) -> list[dict[str, Fraction]]:
    if not config["review"]["sensitivity_enabled"]:
        return []
    base = {
        name: parse_fraction(config["weights"][name]) for name in COMPONENT_NAMES
    }
    delta = parse_fraction(config["review"]["weight_perturbation"])
    scenarios: list[dict[str, Fraction]] = []
    for name in COMPONENT_NAMES:
        for factor in (Fraction(1) - delta, Fraction(1) + delta):
            scenario = dict(base)
            scenario[name] *= factor
            scenarios.append(scenario)
    return scenarios


def build_review_queue(
    result: OptimizationResult,
    bigs: list[dict[str, str]],
    littles: list[dict[str, str]],
    pair_scores: list[PairScore],
    declared_matches: list[DeclaredMatch],
    config: dict[str, Any],
) -> list[ReviewCase]:
    if not result.is_complete:
        return []

    baseline = {match.little_id: match.big_id for match in result.matches}
    switch_counts = {little_id: 0 for little_id in baseline}
    scenarios = _weight_scenarios(config)
    for weights in scenarios:
        reweighted = [reweight_score(score, weights) for score in pair_scores]
        scenario_result = solve_matching(bigs, littles, reweighted, declared_matches)
        if not scenario_result.is_complete:
            raise RuntimeError("Weight perturbation changed hard matching feasibility.")
        scenario_map = {
            match.little_id: match.big_id for match in scenario_result.matches
        }
        for little_id, big_id in baseline.items():
            switch_counts[little_id] += scenario_map[little_id] != big_id

    declared_littles = {match.little_id for match in declared_matches}
    declared_big_counts = Counter(match.big_id for match in declared_matches)
    residual_capacity = {
        big["big_id"]: int(big["capacity"]) - declared_big_counts[big["big_id"]]
        for big in bigs
    }
    scores_by_little: dict[str, list[PairScore]] = {}
    for score in pair_scores:
        if (
            score.little_id not in declared_littles
            and residual_capacity.get(score.big_id, 0) > 0
        ):
            scores_by_little.setdefault(score.little_id, []).append(score)
    risk_weights = {
        name: parse_fraction(value)
        for name, value in config["review"]["risk_weights"].items()
    }

    cases: list[ReviewCase] = []
    for match in result.matches:
        score = match.pair_score
        candidates = scores_by_little.get(match.little_id, [])
        candidate_count = result.candidate_counts.get(
            match.little_id, len(candidates)
        )
        best = max((candidate.total for candidate in candidates), default=score.total)
        regret = (
            Fraction()
            if match.assignment_type == "declared"
            else max(Fraction(), best - score.total)
        )
        sensitivity = (
            Fraction(switch_counts[match.little_id], len(scenarios))
            if scenarios
            else Fraction()
        )
        exception = Fraction(match.assignment_type == "declared")
        signals = {
            "low_score": Fraction(1) - score.total,
            "candidate_count": Fraction(1, candidate_count)
            if candidate_count > 0
            else Fraction(1),
            "regret": regret,
            "sensitivity": sensitivity,
            "exception": exception,
        }
        active_risk_weights = dict(risk_weights)
        if not scenarios:
            active_risk_weights.pop("sensitivity")
        active_denominator = sum(active_risk_weights.values(), Fraction())
        combined = sum(
            signals[name] * active_risk_weights[name]
            for name in active_risk_weights
        ) / active_denominator
        cases.append(
            ReviewCase(
                little_id=match.little_id,
                big_id=match.big_id,
                assignment_type=match.assignment_type,
                total_score=score.total,
                candidate_count=candidate_count,
                regret=regret,
                sensitivity=sensitivity,
                exception_risk=exception,
                combined_risk=combined,
            )
        )
    return sorted(cases, key=lambda case: (-case.combined_risk, id_key(case.little_id)))
