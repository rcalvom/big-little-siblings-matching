"""Exact bottleneck-first capacitated bipartite matching."""

from __future__ import annotations

import math
import re
from collections import Counter
from fractions import Fraction
from typing import Iterable

import networkx as nx

from .data import parse_yes_no
from .models import (
    AssignedMatch,
    DeclaredMatch,
    FeasibilityDiagnostic,
    OptimizationResult,
    PairScore,
)


Node = tuple[str, str]
ScoreMap = dict[tuple[str, str], Fraction]


def id_key(value: str) -> tuple[str, int, str]:
    match = re.fullmatch(r"(.+?)-(\d+)", value)
    if match:
        return (match.group(1).casefold(), int(match.group(2)), value)
    return (value.casefold(), -1, value)


def _capacity(record: dict[str, str]) -> int:
    try:
        return int(record["capacity"])
    except (KeyError, ValueError):
        return 0


def build_feasibility_graph(
    little_ids: Iterable[str], capacities: dict[str, int], score_map: ScoreMap
) -> nx.DiGraph:
    little_ids = tuple(sorted(little_ids, key=id_key))
    source: Node = ("source", "")
    sink: Node = ("sink", "")
    graph = nx.DiGraph()
    graph.add_node(source)
    graph.add_node(sink)
    for little_id in little_ids:
        graph.add_edge(source, ("little", little_id), capacity=1)
    for big_id in sorted(capacities, key=id_key):
        if capacities[big_id] > 0:
            graph.add_edge(("big", big_id), sink, capacity=capacities[big_id])
    infinite_for_cut = len(little_ids) + 1
    for little_id, big_id in sorted(
        score_map, key=lambda pair: (id_key(pair[0]), id_key(pair[1]))
    ):
        if little_id in little_ids and capacities.get(big_id, 0) > 0:
            graph.add_edge(
                ("little", little_id),
                ("big", big_id),
                capacity=infinite_for_cut,
            )
    return graph


def diagnose_feasibility(
    little_ids: Iterable[str], capacities: dict[str, int], score_map: ScoreMap
) -> FeasibilityDiagnostic | None:
    little_ids = tuple(sorted(little_ids, key=id_key))
    graph = build_feasibility_graph(little_ids, capacities, score_map)
    source: Node = ("source", "")
    sink: Node = ("sink", "")
    maximum_flow = int(nx.maximum_flow_value(graph, source, sink, capacity="capacity"))
    if maximum_flow == len(little_ids):
        return None
    _, partition = nx.minimum_cut(graph, source, sink, capacity="capacity")
    source_side, _ = partition
    cut_littles = tuple(
        sorted(
            (node[1] for node in source_side if node[0] == "little"),
            key=id_key,
        )
    )
    cut_bigs = tuple(
        sorted(
            (node[1] for node in source_side if node[0] == "big"),
            key=id_key,
        )
    )
    return FeasibilityDiagnostic(
        required_flow=len(little_ids),
        maximum_flow=maximum_flow,
        cut_little_ids=cut_littles,
        cut_big_ids=cut_bigs,
        residual_capacities={
            big_id: capacities[big_id] for big_id in sorted(capacities, key=id_key)
        },
    )


def _is_feasible(
    little_ids: tuple[str, ...], capacities: dict[str, int], score_map: ScoreMap
) -> bool:
    return diagnose_feasibility(little_ids, capacities, score_map) is None


def _maximum_bottleneck(
    little_ids: tuple[str, ...],
    capacities: dict[str, int],
    score_map: ScoreMap,
    uncovered: frozenset[str],
    coverage: int,
) -> Fraction:
    candidates = sorted(set(score_map.values()))
    if not candidates:
        raise RuntimeError("A feasible non-empty matching must contain candidate scores.")
    low = 0
    high = len(candidates) - 1
    best = candidates[0]
    while low <= high:
        middle = (low + high) // 2
        threshold = candidates[middle]
        threshold_scores = {
            pair: score for pair, score in score_map.items() if score >= threshold
        }
        solution = _optimize(
            little_ids, capacities, threshold_scores, uncovered, use_scores=False
        )
        if solution is not None and solution[0] == coverage:
            best = threshold
            low = middle + 1
        else:
            high = middle - 1
    return best


def _score_denominator(scores: Iterable[Fraction]) -> int:
    denominator = 1
    for score in scores:
        denominator = math.lcm(denominator, score.denominator)
    return denominator


def _optimize(
    little_ids: tuple[str, ...],
    capacities: dict[str, int],
    score_map: ScoreMap,
    uncovered: frozenset[str],
    *,
    use_scores: bool,
) -> tuple[int, Fraction, dict[str, str], int] | None:
    """Solve one flow, maximizing Big coverage first and total score second.

    A Big that holds no declared relationship reaches the sink through a
    dedicated first slot carrying a bonus larger than any achievable total
    score. Min-cost flow therefore fills as many distinct Bigs as it can before
    it spends anything on quality, which makes the two objectives lexicographic
    rather than a weighted compromise.
    """

    if not little_ids:
        return 0, Fraction(), {}, 1
    denominator = _score_denominator(score_map.values()) if use_scores else 1
    # Strictly greater than the largest total the score term can contribute.
    bonus = len(little_ids) * denominator + 1

    source: Node = ("source", "")
    sink: Node = ("sink", "")
    graph = nx.DiGraph()
    graph.add_node(source, demand=-len(little_ids))
    graph.add_node(sink, demand=len(little_ids))
    for little_id in sorted(little_ids, key=id_key):
        node = ("little", little_id)
        graph.add_node(node, demand=0)
        graph.add_edge(source, node, capacity=1, weight=0)
    for big_id in sorted(capacities, key=id_key):
        capacity = capacities[big_id]
        if capacity <= 0:
            continue
        node = ("big", big_id)
        graph.add_node(node, demand=0)
        if big_id in uncovered:
            first: Node = ("first", big_id)
            graph.add_node(first, demand=0)
            graph.add_edge(node, first, capacity=1, weight=-bonus)
            graph.add_edge(first, sink, capacity=1, weight=0)
            if capacity > 1:
                graph.add_edge(node, sink, capacity=capacity - 1, weight=0)
        else:
            graph.add_edge(node, sink, capacity=capacity, weight=0)
    for (little_id, big_id), score in sorted(
        score_map.items(), key=lambda item: (id_key(item[0][0]), id_key(item[0][1]))
    ):
        if little_id in little_ids and capacities.get(big_id, 0) > 0:
            graph.add_edge(
                ("little", little_id),
                ("big", big_id),
                capacity=1,
                weight=-int(score * denominator) if use_scores else 0,
            )
    try:
        _, flow = nx.network_simplex(graph)
    except nx.NetworkXUnfeasible:
        return None

    assignment: dict[str, str] = {}
    for little_id in sorted(little_ids, key=id_key):
        selected = [
            node[1]
            for node, amount in flow[("little", little_id)].items()
            if node[0] == "big" and amount == 1
        ]
        if len(selected) != 1:
            raise RuntimeError("The min-cost flow did not assign every required Little.")
        assignment[little_id] = selected[0]
    coverage = sum(
        1
        for big_id in uncovered
        if flow.get(("big", big_id), {}).get(("first", big_id), 0) == 1
    )
    total = sum(
        (score_map[(little_id, big_id)] for little_id, big_id in assignment.items()),
        Fraction(),
    )
    return coverage, total, assignment, denominator


def _maximize_total_score(
    little_ids: tuple[str, ...],
    capacities: dict[str, int],
    score_map: ScoreMap,
    uncovered: frozenset[str] = frozenset(),
) -> tuple[Fraction, dict[str, str], int] | None:
    solution = _optimize(
        little_ids, capacities, score_map, uncovered, use_scores=True
    )
    if solution is None:
        return None
    _, total, assignment, denominator = solution
    return total, assignment, denominator


def _canonicalize_optimum(
    little_ids: tuple[str, ...],
    capacities: dict[str, int],
    score_map: ScoreMap,
    optimal_total: Fraction,
    uncovered: frozenset[str],
    optimal_coverage: int,
) -> dict[str, str]:
    fixed: dict[str, str] = {}
    fixed_counts: Counter[str] = Counter()
    fixed_total = Fraction()
    fixed_coverage = 0
    for little_id in sorted(little_ids, key=id_key):
        candidates = sorted(
            (big_id for candidate_little, big_id in score_map if candidate_little == little_id),
            key=id_key,
        )
        for big_id in candidates:
            if fixed_counts[big_id] >= capacities.get(big_id, 0):
                continue
            trial_counts = fixed_counts.copy()
            gained = 1 if big_id in uncovered and trial_counts[big_id] == 0 else 0
            trial_counts[big_id] += 1
            residual = {
                candidate_big: capacity - trial_counts[candidate_big]
                for candidate_big, capacity in capacities.items()
            }
            remaining = tuple(
                candidate
                for candidate in sorted(little_ids, key=id_key)
                if candidate not in fixed and candidate != little_id
            )
            remaining_scores = {
                pair: score
                for pair, score in score_map.items()
                if pair[0] in remaining and residual.get(pair[1], 0) > 0
            }
            # A Big already used by a fixed assignment is no longer uncovered.
            remaining_uncovered = frozenset(
                candidate for candidate in uncovered if trial_counts[candidate] == 0
            )
            remainder = _optimize(
                remaining,
                residual,
                remaining_scores,
                remaining_uncovered,
                use_scores=True,
            )
            if remainder is None:
                continue
            trial_coverage = fixed_coverage + gained + remainder[0]
            trial_total = fixed_total + score_map[(little_id, big_id)] + remainder[1]
            if trial_coverage == optimal_coverage and trial_total == optimal_total:
                fixed[little_id] = big_id
                fixed_counts = trial_counts
                fixed_total += score_map[(little_id, big_id)]
                fixed_coverage += gained
                break
        else:
            raise RuntimeError("Could not canonicalize an otherwise optimal matching.")
    return fixed


def _prepare_declared(
    bigs: list[dict[str, str]],
    littles: list[dict[str, str]],
    declared_matches: list[DeclaredMatch],
    pair_by_ids: dict[tuple[str, str], PairScore],
) -> tuple[list[AssignedMatch], dict[str, int], set[str], frozenset[str]]:
    big_by_id = {big["big_id"]: big for big in bigs}
    little_ids = {little["little_id"] for little in littles}
    big_counts: Counter[str] = Counter()
    forced_littles: set[str] = set()
    assignments: list[AssignedMatch] = []
    for declared in sorted(
        declared_matches, key=lambda match: (id_key(match.little_id), id_key(match.big_id))
    ):
        if declared.big_id not in big_by_id or declared.little_id not in little_ids:
            raise ValueError("Declared matches must reference known participant IDs.")
        if parse_yes_no(big_by_id[declared.big_id]["can_commit_4_6_hours"]) is not True:
            raise ValueError("A declared match cannot use an unavailable Big.")
        if declared.little_id in forced_littles:
            raise ValueError("A Little may have at most one declared Big.")
        big_counts[declared.big_id] += 1
        if big_counts[declared.big_id] > _capacity(big_by_id[declared.big_id]):
            raise ValueError("Declared matches exceed a Big's declared capacity.")
        pair_score = pair_by_ids.get((declared.little_id, declared.big_id))
        if pair_score is None:
            raise ValueError("Every declared pair must have a reportable pair score.")
        forced_littles.add(declared.little_id)
        assignments.append(
            AssignedMatch(
                little_id=declared.little_id,
                big_id=declared.big_id,
                assignment_type="declared",
                pair_score=pair_score,
                note=declared.reason,
            )
        )
    residual = {
        big_id: _capacity(big) - big_counts[big_id]
        for big_id, big in big_by_id.items()
        if parse_yes_no(big["can_commit_4_6_hours"]) is True
    }
    # A Big already holding a declared relationship is covered; only the others
    # can gain coverage from an ordinary assignment.
    uncovered = frozenset(
        big_id for big_id, capacity in residual.items()
        if capacity > 0 and big_counts[big_id] == 0
    )
    return assignments, residual, forced_littles, uncovered


def solve_matching(
    bigs: list[dict[str, str]],
    littles: list[dict[str, str]],
    pair_scores: list[PairScore],
    declared_matches: list[DeclaredMatch],
) -> OptimizationResult:
    """Solve complete matching, max-min quality, total quality, then ID order."""

    pair_by_ids: dict[tuple[str, str], PairScore] = {}
    for score in pair_scores:
        pair = (score.little_id, score.big_id)
        if pair in pair_by_ids:
            raise ValueError("Each Big-Little pair must have at most one score.")
        pair_by_ids[pair] = score

    declared_assignments, residual_capacity, forced_littles, uncovered = _prepare_declared(
        bigs, littles, declared_matches, pair_by_ids
    )
    remaining = tuple(
        sorted(
            (
                little["little_id"]
                for little in littles
                if little["little_id"] not in forced_littles
            ),
            key=id_key,
        )
    )
    ordinary_scores = {
        pair: score.total
        for pair, score in pair_by_ids.items()
        if pair[0] in remaining and residual_capacity.get(pair[1], 0) > 0
    }
    candidate_counts = Counter(little_id for little_id, _ in ordinary_scores)
    candidate_count_map = {
        little_id: candidate_counts[little_id] for little_id in remaining
    }
    if not remaining:
        return OptimizationResult(
            matches=tuple(sorted(declared_assignments, key=lambda match: id_key(match.little_id))),
            declared_assignments=tuple(
                sorted(declared_assignments, key=lambda match: id_key(match.little_id))
            ),
            candidate_counts={},
            bottleneck_score=None,
            ordinary_total_score=Fraction(),
            integer_cost_denominator=1,
        )

    diagnostic = diagnose_feasibility(remaining, residual_capacity, ordinary_scores)
    if diagnostic is not None:
        return OptimizationResult(
            matches=(),
            declared_assignments=tuple(
                sorted(declared_assignments, key=lambda match: id_key(match.little_id))
            ),
            candidate_counts=candidate_count_map,
            bottleneck_score=None,
            ordinary_total_score=Fraction(),
            integer_cost_denominator=None,
            diagnostic=diagnostic,
        )

    widest = _optimize(
        remaining, residual_capacity, ordinary_scores, uncovered, use_scores=False
    )
    if widest is None:
        raise RuntimeError("A feasible instance unexpectedly admitted no coverage solution.")
    coverage = widest[0]

    bottleneck = _maximum_bottleneck(
        remaining, residual_capacity, ordinary_scores, uncovered, coverage
    )
    threshold_scores = {
        pair: score for pair, score in ordinary_scores.items() if score >= bottleneck
    }
    optimum = _optimize(
        remaining, residual_capacity, threshold_scores, uncovered, use_scores=True
    )
    if optimum is None:
        raise RuntimeError("The bottleneck subgraph unexpectedly became infeasible.")
    achieved_coverage, optimal_total, _, integer_cost_denominator = optimum
    if achieved_coverage != coverage:
        raise RuntimeError("The bottleneck subgraph lost the maximum Big coverage.")
    assignment = _canonicalize_optimum(
        remaining,
        residual_capacity,
        threshold_scores,
        optimal_total,
        uncovered,
        coverage,
    )
    optimized = [
        AssignedMatch(
            little_id=little_id,
            big_id=big_id,
            assignment_type="optimized",
            pair_score=pair_by_ids[(little_id, big_id)],
        )
        for little_id, big_id in assignment.items()
    ]
    matches = tuple(
        sorted(declared_assignments + optimized, key=lambda match: id_key(match.little_id))
    )
    return OptimizationResult(
        matches=matches,
        declared_assignments=tuple(
            sorted(declared_assignments, key=lambda match: id_key(match.little_id))
        ),
        candidate_counts=candidate_count_map,
        bottleneck_score=bottleneck,
        ordinary_total_score=optimal_total,
        integer_cost_denominator=integer_cost_denominator,
        big_coverage=coverage,
    )
