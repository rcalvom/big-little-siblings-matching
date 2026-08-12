from __future__ import annotations

from fractions import Fraction

from csap_siblings_match.scoring import (
    eligibility_reasons,
    priority_similarity,
    score_pair,
)

from .factories import big, little, reversed_ranking, synthetic_config


def test_priority_similarity_is_exact_normalized_spearman() -> None:
    assert priority_similarity(big(), little()) == 1
    assert priority_similarity(big(), little(**reversed_ranking())) == 0


def test_six_components_have_equal_initial_weight() -> None:
    config = synthetic_config()
    candidate = little(
        bachelor_degree="Electrical Engineering",
        undergrad_university="Synthetic University Regional Campus",
        home_location="Synthetic City B",
        purdue_college="Science",
        advisor="Faculty B",
    )

    score = score_pair(big(), candidate, config)

    assert score.priority_alignment == 1
    assert score.bachelor_degree == Fraction(2, 3)
    assert score.undergrad_university == Fraction(1, 2)
    assert score.home_location == Fraction(2, 3)
    assert score.purdue_college == 0
    assert score.advisor == 0
    assert score.total == sum(score.components().values(), Fraction()) / 6


def test_location_distinguishes_city_region_country() -> None:
    config = synthetic_config()

    assert (
        score_pair(big(), little(home_location="Synthetic City A"), config).home_location
        == 1
    )
    assert (
        score_pair(big(), little(home_location="Synthetic City B"), config).home_location
        == Fraction(2, 3)
    )
    assert (
        score_pair(big(), little(home_location="Synthetic City C"), config).home_location
        == Fraction(1, 3)
    )
    assert (
        score_pair(big(), little(home_location="Other Country City"), config).home_location
        == 0
    )


def test_same_gender_is_hard_only_when_either_side_requests_it() -> None:
    unrestricted = eligibility_reasons(
        big(gender_identity="cisgender_woman"), little(gender_identity="cisgender_man")
    )
    little_requires = eligibility_reasons(
        big(gender_identity="cisgender_woman"),
        little(gender_identity="cisgender_man", same_gender_mentorship="yes"),
    )

    assert "same_gender_requirement" not in unrestricted
    assert "same_gender_requirement" in little_requires


def test_nationality_and_availability_are_hard_rules() -> None:
    reasons = eligibility_reasons(
        big(
            accepts_non_colombian_little="no",
            can_commit_4_6_hours="no",
        ),
        little(is_colombian="no"),
    )

    assert reasons == ["big_unavailable", "big_requires_colombian_little"]
