"""Explainable hard eligibility and exact six-component scoring."""

from __future__ import annotations

from fractions import Fraction
from typing import Any, Iterable

from .config import COMPONENT_NAMES, catalog_entry, parse_fraction
from .data import parse_yes_no, priority_ranks
from .models import DeclaredMatch, PairScore


def priority_similarity(big: dict[str, str], little: dict[str, str]) -> Fraction:
    """Return normalized Spearman similarity for two complete five-item rankings."""

    squared_difference = sum(
        (big_rank - little_rank) ** 2
        for big_rank, little_rank in zip(priority_ranks(big), priority_ranks(little), strict=True)
    )
    return Fraction(1) - Fraction(squared_difference, 40)


def _degree_similarity(
    big: dict[str, str], little: dict[str, str], config: dict[str, Any]
) -> Fraction:
    left = catalog_entry(config, "bachelor_degree", big["bachelor_degree"])
    right = catalog_entry(config, "bachelor_degree", little["bachelor_degree"])
    values = config["similarity"]["bachelor_degree"]
    if left["detailed"] == right["detailed"]:
        return parse_fraction(values["detailed"])
    if left["narrow"] == right["narrow"]:
        return parse_fraction(values["narrow"])
    if left["broad"] == right["broad"]:
        return parse_fraction(values["broad"])
    return Fraction()


def _university_similarity(
    big: dict[str, str], little: dict[str, str], config: dict[str, Any]
) -> Fraction:
    left = catalog_entry(config, "undergrad_university", big["undergrad_university"])
    right = catalog_entry(config, "undergrad_university", little["undergrad_university"])
    values = config["similarity"]["undergrad_university"]
    left_system = left["system"]
    right_system = right["system"]
    if left_system == right_system and left["campus"] == right["campus"]:
        return parse_fraction(values["same_campus"])
    if left_system == right_system:
        return parse_fraction(values["same_system"])
    return Fraction()


def _location_similarity(
    big: dict[str, str], little: dict[str, str], config: dict[str, Any]
) -> Fraction:
    left = catalog_entry(config, "home_location", big["home_location"])
    right = catalog_entry(config, "home_location", little["home_location"])
    values = config["similarity"]["home_location"]
    left_country = left["country"]
    right_country = right["country"]
    left_region = left["region"]
    right_region = right["region"]
    if (
        left_country == right_country
        and left_region == right_region
        and left["city"] == right["city"]
    ):
        return parse_fraction(values["same_city"])
    if left_country == right_country and left_region == right_region:
        return parse_fraction(values["same_region"])
    if left_country == right_country:
        return parse_fraction(values["same_country"])
    return Fraction()


def _exact_catalog_similarity(
    catalog: str,
    field: str,
    big: dict[str, str],
    little: dict[str, str],
    config: dict[str, Any],
) -> Fraction:
    left = catalog_entry(config, catalog, big[field])
    right = catalog_entry(config, catalog, little[field])
    return Fraction(left == right)


def combine_components(
    components: dict[str, Fraction], weights: dict[str, Any]
) -> Fraction:
    parsed_weights = {name: parse_fraction(weights[name]) for name in COMPONENT_NAMES}
    denominator = sum(parsed_weights.values(), Fraction())
    return sum(
        components[name] * parsed_weights[name] for name in COMPONENT_NAMES
    ) / denominator


def score_pair(
    big: dict[str, str], little: dict[str, str], config: dict[str, Any]
) -> PairScore:
    components = {
        "priority_alignment": priority_similarity(big, little),
        "bachelor_degree": _degree_similarity(big, little, config),
        "undergrad_university": _university_similarity(big, little, config),
        "home_location": _location_similarity(big, little, config),
        "purdue_college": _exact_catalog_similarity(
            "purdue_college", "purdue_college", big, little, config
        ),
        "advisor": _exact_catalog_similarity("advisor", "advisor", big, little, config),
    }
    return PairScore(
        little_id=little["little_id"],
        big_id=big["big_id"],
        total=combine_components(components, config["weights"]),
        priority_alignment=components["priority_alignment"],
        bachelor_degree=components["bachelor_degree"],
        undergrad_university=components["undergrad_university"],
        home_location=components["home_location"],
        purdue_college=components["purdue_college"],
        advisor=components["advisor"],
    )


def reweight_score(score: PairScore, weights: dict[str, Any]) -> PairScore:
    return score.with_total(combine_components(score.components(), weights))


def eligibility_reasons(big: dict[str, str], little: dict[str, str]) -> list[str]:
    reasons: list[str] = []
    if parse_yes_no(big.get("can_commit_4_6_hours")) is not True:
        reasons.append("big_unavailable")

    big_requires_same = parse_yes_no(big.get("same_gender_mentorship")) is True
    little_requires_same = parse_yes_no(little.get("same_gender_mentorship")) is True
    if big_requires_same or little_requires_same:
        if big.get("gender_identity") != little.get("gender_identity"):
            reasons.append("same_gender_requirement")

    if (
        parse_yes_no(big.get("accepts_non_colombian_little")) is False
        and parse_yes_no(little.get("is_colombian")) is not True
    ):
        reasons.append("big_requires_colombian_little")
    return reasons


def build_candidate_scores(
    bigs: list[dict[str, str]],
    littles: list[dict[str, str]],
    config: dict[str, Any],
    declared_matches: Iterable[DeclaredMatch] = (),
) -> tuple[list[PairScore], list[dict[str, str]]]:
    """Score all ordinary eligible edges and every policy-forced edge."""

    declared_pairs = {
        (match.little_id, match.big_id) for match in declared_matches
    }
    scores: list[PairScore] = []
    exclusions: list[dict[str, str]] = []
    for little in sorted(littles, key=lambda record: record["little_id"]):
        for big in sorted(bigs, key=lambda record: record["big_id"]):
            pair = (little["little_id"], big["big_id"])
            reasons = eligibility_reasons(big, little)
            if pair in declared_pairs:
                scores.append(score_pair(big, little, config))
                exclusions.extend(
                    {
                        "little_id": pair[0],
                        "big_id": pair[1],
                        "reason": f"declared_bypass:{reason}",
                    }
                    for reason in reasons
                    if reason != "big_unavailable"
                )
            elif reasons:
                exclusions.extend(
                    {"little_id": pair[0], "big_id": pair[1], "reason": reason}
                    for reason in reasons
                )
            else:
                scores.append(score_pair(big, little, config))
    return scores, exclusions
