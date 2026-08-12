from __future__ import annotations

from fractions import Fraction

from csap_siblings_match.config import load_config, validate_config
from csap_siblings_match.data import PRIORITY_FIELDS
from csap_siblings_match.models import DeclaredMatch, PairScore


def big(big_id: str = "B-1", **overrides: str) -> dict[str, str]:
    record = {
        "big_id": big_id,
        "first_name": "Big",
        "last_name": big_id,
        "email": f"{big_id.lower()}@example.test",
        "gender_identity": "cisgender_man",
        "same_gender_mentorship": "no",
        "bachelor_degree": "Mechanical Engineering",
        "undergrad_university": "Synthetic University Main Campus",
        "home_location": "Synthetic City A",
        "purdue_college": "Engineering",
        "advisor": "Faculty A",
        "priority_academic_mentoring_rank": "1",
        "priority_emotional_support_rank": "2",
        "priority_local_integration_rank": "3",
        "priority_graduate_research_rank": "4",
        "priority_social_activities_rank": "5",
        "accepts_non_colombian_little": "yes",
        "can_commit_4_6_hours": "yes",
        "capacity": "1",
    }
    record.update(overrides)
    return record


def little(little_id: str = "L-1", **overrides: str) -> dict[str, str]:
    record = {
        "little_id": little_id,
        "first_name": "Little",
        "last_name": little_id,
        "email": f"{little_id.lower()}@example.test",
        "gender_identity": "cisgender_man",
        "same_gender_mentorship": "no",
        "is_colombian": "yes",
        "bachelor_degree": "Mechanical Engineering",
        "undergrad_university": "Synthetic University Main Campus",
        "home_location": "Synthetic City A",
        "purdue_college": "Engineering",
        "advisor": "Faculty A",
        "priority_academic_mentoring_rank": "1",
        "priority_emotional_support_rank": "2",
        "priority_local_integration_rank": "3",
        "priority_graduate_research_rank": "4",
        "priority_social_activities_rank": "5",
    }
    record.update(overrides)
    return record


def reversed_ranking() -> dict[str, str]:
    return {field: str(5 - index) for index, field in enumerate(PRIORITY_FIELDS)}


def synthetic_config() -> dict:
    config = load_config()
    config["catalogs"] = {
        "bachelor_degree": {
            "Mechanical Engineering": {
                "broad": "engineering",
                "narrow": "engineering",
                "detailed": "mechanical_engineering",
            },
            "Electrical Engineering": {
                "broad": "engineering",
                "narrow": "engineering",
                "detailed": "electrical_engineering",
            },
            "Physics": {
                "broad": "natural_sciences",
                "narrow": "physical_sciences",
                "detailed": "physics",
            },
        },
        "undergrad_university": {
            "Synthetic University Main Campus": {
                "system": "synthetic_university",
                "campus": "main",
            },
            "Synthetic University Regional Campus": {
                "system": "synthetic_university",
                "campus": "regional",
            },
            "Other University": {"system": "other_university", "campus": "main"},
        },
        "home_location": {
            "Synthetic City A": {
                "country": "country_a",
                "region": "region_a",
                "city": "city_a",
            },
            "Synthetic City B": {
                "country": "country_a",
                "region": "region_a",
                "city": "city_b",
            },
            "Synthetic City C": {
                "country": "country_a",
                "region": "region_b",
                "city": "city_c",
            },
            "Other Country City": {
                "country": "country_b",
                "region": "region_z",
                "city": "city_z",
            },
        },
        "purdue_college": {
            "Engineering": "engineering",
            "Science": "science",
        },
        "advisor": {
            "Faculty A": "faculty_a",
            "Professor A": "faculty_a",
            "Faculty B": "faculty_b",
        },
    }
    validate_config(config)
    return config


def pair(little_id: str, big_id: str, value: str | int | Fraction) -> PairScore:
    score = value if isinstance(value, Fraction) else Fraction(str(value))
    return PairScore(
        little_id=little_id,
        big_id=big_id,
        total=score,
        priority_alignment=score,
        bachelor_degree=score,
        undergrad_university=score,
        home_location=score,
        purdue_college=score,
        advisor=score,
    )


def declared(little_id: str, big_id: str) -> DeclaredMatch:
    return DeclaredMatch(
        little_id=little_id,
        big_id=big_id,
        reason="known_relationship_from_big_form",
    )
