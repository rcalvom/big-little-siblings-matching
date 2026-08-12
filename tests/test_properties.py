from __future__ import annotations

import itertools
import random
from collections import Counter
from fractions import Fraction

from csap_siblings_match.optimizer import solve_matching
from csap_siblings_match.scoring import (
    build_candidate_scores,
    priority_similarity,
)

from .factories import big, declared, little, pair, synthetic_config


def _oracle_id_key(value: str) -> tuple[str, int]:
    prefix, number = value.rsplit("-", 1)
    return prefix, int(number)


def _brute_force(
    little_ids: list[str], capacities: dict[str, int], scores: dict[tuple[str, str], Fraction]
):
    little_ids = sorted(little_ids, key=_oracle_id_key)
    choices = [
        sorted(
            (
                big_id
                for candidate_little, big_id in scores
                if candidate_little == little_id
            ),
            key=_oracle_id_key,
        )
        for little_id in little_ids
    ]
    best = None
    for selected in itertools.product(*choices):
        counts = Counter(selected)
        if any(counts[big_id] > capacities[big_id] for big_id in counts):
            continue
        values = [scores[(little_id, big_id)] for little_id, big_id in zip(little_ids, selected)]
        # Same lexicographic order the solver claims: spread across as many
        # Bigs as possible, then protect the weakest pair, then total quality.
        objective = (len(counts), min(values), sum(values, Fraction()))
        if (
            best is None
            or objective > best[0]
            or (
                objective == best[0]
                and tuple(_oracle_id_key(value) for value in selected)
                < tuple(_oracle_id_key(value) for value in best[1])
            )
        ):
            best = (objective, selected)
    return best


def test_optimizer_matches_independent_brute_force_oracle() -> None:
    randomizer = random.Random(20260808)
    score_values = [Fraction(), Fraction(1, 3), Fraction(1, 2), Fraction(2, 3), Fraction(1)]

    for _ in range(250):
        big_count = randomizer.randint(1, 3)
        little_count = randomizer.randint(1, 4)
        bigs = [
            big(f"B-{index}", capacity=str(randomizer.randint(1, 2)))
            for index in range(1, big_count + 1)
        ]
        littles = [little(f"L-{index}") for index in range(1, little_count + 1)]
        scores = []
        for little_record in littles:
            for big_record in bigs:
                if randomizer.random() < 0.7:
                    scores.append(
                        pair(
                            little_record["little_id"],
                            big_record["big_id"],
                            randomizer.choice(score_values),
                        )
                    )

        little_ids = sorted(
            (record["little_id"] for record in littles), key=_oracle_id_key
        )
        capacities = {record["big_id"]: int(record["capacity"]) for record in bigs}
        score_map = {(score.little_id, score.big_id): score.total for score in scores}
        expected = _brute_force(little_ids, capacities, score_map)
        result = solve_matching(bigs, littles, scores, [])

        if expected is None:
            assert not result.is_complete
            assert result.matches == ()
            continue
        objective, selected = expected
        assert result.is_complete
        assert result.big_coverage == objective[0]
        assert result.bottleneck_score == objective[1]
        assert result.ordinary_total_score == objective[2]
        assert tuple(match.big_id for match in result.matches) == selected


def test_all_priority_permutations_follow_exact_spearman_formula() -> None:
    reference = big()
    fields = [
        "priority_academic_mentoring_rank",
        "priority_emotional_support_rank",
        "priority_local_integration_rank",
        "priority_graduate_research_rank",
        "priority_social_activities_rank",
    ]
    observed = set()
    for permutation in itertools.permutations(range(1, 6)):
        candidate = little(**{field: str(rank) for field, rank in zip(fields, permutation)})
        expected = Fraction(1) - Fraction(
            sum((index - rank) ** 2 for index, rank in enumerate(permutation, start=1)),
            40,
        )
        score = priority_similarity(reference, candidate)
        assert score == expected
        assert Fraction() <= score <= 1
        observed.add(permutation)

    assert len(observed) == 120


def test_names_and_emails_cannot_change_scores_or_assignments() -> None:
    config = synthetic_config()
    bigs = [big("B-1"), big("B-2", advisor="Faculty B")]
    littles = [little("L-1"), little("L-2", advisor="Faculty B")]
    scores, _ = build_candidate_scores(bigs, littles, config)
    result = solve_matching(bigs, littles, scores, [])

    changed_bigs = [
        {
            **record,
            "first_name": "Changed",
            "last_name": "Identity",
            "email": "changed@example.test",
        }
        for record in bigs
    ]
    changed_littles = [
        {**record, "first_name": "Other", "last_name": "Person", "email": "other@example.test"}
        for record in littles
    ]
    changed_scores, _ = build_candidate_scores(changed_bigs, changed_littles, config)
    changed_result = solve_matching(changed_bigs, changed_littles, changed_scores, [])

    assert scores == changed_scores
    assert {
        match.little_id: match.big_id for match in result.matches
    } == {
        match.little_id: match.big_id for match in changed_result.matches
    }


def test_declared_pair_bypasses_gender_and_nationality_only() -> None:
    config = synthetic_config()
    bigs = [
        big(
            gender_identity="cisgender_woman",
            same_gender_mentorship="yes",
            accepts_non_colombian_little="no",
        )
    ]
    littles = [little(gender_identity="cisgender_man", is_colombian="no")]
    declared_matches = [declared("L-1", "B-1")]

    scores, exclusions = build_candidate_scores(
        bigs, littles, config, declared_matches
    )
    result = solve_matching(bigs, littles, scores, declared_matches)

    assert result.is_complete
    assert result.matches[0].assignment_type == "declared"
    assert {row["reason"] for row in exclusions} == {
        "declared_bypass:same_gender_requirement",
        "declared_bypass:big_requires_colombian_little",
    }


def test_min_cut_is_a_capacitated_hall_deficiency_witness() -> None:
    bigs = [big("B-1", capacity="1"), big("B-2", capacity="1")]
    littles = [little("L-1"), little("L-2"), little("L-3")]
    scores = [
        pair(little_id, big_id, 1)
        for little_id in ("L-1", "L-2", "L-3")
        for big_id in ("B-1", "B-2")
    ]

    result = solve_matching(bigs, littles, scores, [])
    assert result.diagnostic is not None
    witness_littles = set(result.diagnostic.cut_little_ids)
    witness_bigs = set(result.diagnostic.cut_big_ids)

    assert witness_littles == {"L-1", "L-2", "L-3"}
    assert witness_bigs == {"B-1", "B-2"}
    assert len(witness_littles) > sum(
        int(record["capacity"]) for record in bigs if record["big_id"] in witness_bigs
    )
