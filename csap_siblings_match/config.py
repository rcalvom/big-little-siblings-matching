"""Strict, versioned CSAP policy configuration."""

from __future__ import annotations

import re
import unicodedata
from copy import deepcopy
from fractions import Fraction
from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml


COMPONENT_NAMES = (
    "priority_alignment",
    "bachelor_degree",
    "undergrad_university",
    "home_location",
    "purdue_college",
    "advisor",
)
CATALOG_NAMES = (
    "bachelor_degree",
    "undergrad_university",
    "home_location",
    "purdue_college",
    "advisor",
)
TOP_LEVEL_KEYS = {
    "schema_version",
    "policy_version",
    "gender",
    "weights",
    "similarity",
    "catalogs",
    "review",
}
CANONICAL_CODE = re.compile(r"[a-z0-9][a-z0-9_-]*")


class UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate keys at every level."""


def _construct_unique_mapping(
    loader: UniqueKeyLoader, node: yaml.nodes.MappingNode, deep: bool = False
) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as error:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "mapping keys must be scalar",
                key_node.start_mark,
            ) from error
        if duplicate:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "duplicate mapping key",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping
)


def _load_yaml(stream) -> dict[str, Any]:
    try:
        loaded = yaml.load(stream, Loader=UniqueKeyLoader) or {}
    except yaml.YAMLError as error:
        raise ValueError(
            "Policy YAML is malformed or contains duplicate mapping keys."
        ) from error
    if not isinstance(loaded, dict):
        raise ValueError("The policy file must contain a mapping.")
    return loaded


def _is_clean_label(value: Any) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and value == value.strip()
        and value == unicodedata.normalize("NFC", value)
    )


def _is_code(value: Any) -> bool:
    return isinstance(value, str) and CANONICAL_CODE.fullmatch(value) is not None


def parse_fraction(value: Any) -> Fraction:
    if isinstance(value, bool):
        raise ValueError("Boolean values are not valid rational numbers.")
    try:
        result = value if isinstance(value, Fraction) else Fraction(str(value))
    except (ValueError, ZeroDivisionError) as error:
        raise ValueError(f"Invalid rational value: {value!r}.") from error
    return result


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def _require_exact_keys(mapping: Any, expected: set[str], context: str) -> None:
    if not isinstance(mapping, dict):
        raise ValueError(f"{context} must be a mapping.")
    if any(not isinstance(key, str) for key in mapping):
        raise ValueError(f"{context} contains a non-text key.")
    actual = set(mapping)
    if actual != expected:
        raise ValueError(
            f"{context} keys do not match the published schema "
            f"(missing={len(expected - actual)}, extra={len(actual - expected)})."
        )


def _validate_fraction_map(
    mapping: dict[str, Any], context: str, *, require_positive: bool
) -> None:
    values = [parse_fraction(value) for value in mapping.values()]
    if any(value < 0 for value in values):
        raise ValueError(f"{context} values must be non-negative.")
    if require_positive and any(value == 0 for value in values):
        raise ValueError(f"Every {context} value must be positive.")
    if not values or sum(values, Fraction()) <= 0:
        raise ValueError(f"At least one {context} value must be positive.")


def _validate_catalog(config: dict[str, Any], name: str) -> None:
    catalog = config["catalogs"][name]
    if not isinstance(catalog, dict):
        raise ValueError(f"catalogs.{name} must be a mapping.")
    for raw_value, entry in catalog.items():
        if not _is_clean_label(raw_value):
            raise ValueError(f"catalogs.{name} contains an invalid source label.")
        if name == "bachelor_degree":
            _require_exact_keys(
                entry,
                {"broad", "narrow", "detailed"},
                f"catalogs.{name} entry",
            )
        elif name == "undergrad_university":
            _require_exact_keys(
                entry, {"system", "campus"}, f"catalogs.{name} entry"
            )
        elif name == "home_location":
            _require_exact_keys(
                entry,
                {"country", "region", "city"},
                f"catalogs.{name} entry",
            )
        elif not isinstance(entry, str):
            raise ValueError(f"catalogs.{name} entries must resolve to text.")
        resolved = entry.values() if isinstance(entry, dict) else (entry,)
        if any(not _is_code(value) for value in resolved):
            raise ValueError(
                f"catalogs.{name} entries must use lowercase canonical codes."
            )

    if name == "bachelor_degree":
        detailed_paths: dict[str, tuple[str, str]] = {}
        narrow_paths: dict[str, str] = {}
        for entry in catalog.values():
            path = (entry["narrow"], entry["broad"])
            if entry["detailed"] in detailed_paths and detailed_paths[entry["detailed"]] != path:
                raise ValueError("Bachelor-degree detailed fields have inconsistent parents.")
            if entry["narrow"] in narrow_paths and narrow_paths[entry["narrow"]] != entry["broad"]:
                raise ValueError("Bachelor-degree narrow fields have inconsistent parents.")
            detailed_paths[entry["detailed"]] = path
            narrow_paths[entry["narrow"]] = entry["broad"]
    if name == "home_location":
        city_paths: dict[str, tuple[str, str]] = {}
        region_paths: dict[str, str] = {}
        for entry in catalog.values():
            path = (entry["region"], entry["country"])
            if entry["city"] in city_paths and city_paths[entry["city"]] != path:
                raise ValueError("Cities have inconsistent region or country parents.")
            if (
                entry["region"] in region_paths
                and region_paths[entry["region"]] != entry["country"]
            ):
                raise ValueError("Regions have inconsistent country parents.")
            city_paths[entry["city"]] = path
            region_paths[entry["region"]] = entry["country"]


def validate_config(config: dict[str, Any]) -> None:
    _require_exact_keys(config, TOP_LEVEL_KEYS, "configuration")
    if config["schema_version"] != "2.0":
        raise ValueError("Only canonical schema_version 2.0 is supported.")
    if not isinstance(config["policy_version"], str) or not re.fullmatch(
        r"[a-z0-9][a-z0-9._-]*", config["policy_version"]
    ):
        raise ValueError("policy_version must be a lowercase version identifier.")

    _require_exact_keys(
        config["gender"], {"disclosed_values", "not_disclosed_values"}, "gender"
    )
    disclosed = config["gender"]["disclosed_values"]
    not_disclosed = config["gender"]["not_disclosed_values"]
    if not isinstance(disclosed, list) or not isinstance(not_disclosed, list):
        raise ValueError("Gender value domains must be lists.")
    gender_values = disclosed + not_disclosed
    if not gender_values or any(not _is_code(value) for value in gender_values):
        raise ValueError("Gender values must be lowercase canonical codes.")
    if len(gender_values) != len(set(gender_values)):
        raise ValueError("Gender value domains must not overlap or contain duplicates.")

    _require_exact_keys(config["weights"], set(COMPONENT_NAMES), "weights")
    _validate_fraction_map(config["weights"], "weight", require_positive=True)

    _require_exact_keys(
        config["similarity"],
        {"bachelor_degree", "undergrad_university", "home_location"},
        "similarity",
    )
    expected_similarity = {
        "bachelor_degree": {"detailed", "narrow", "broad"},
        "undergrad_university": {"same_campus", "same_system"},
        "home_location": {"same_city", "same_region", "same_country"},
    }
    for name, expected in expected_similarity.items():
        values = config["similarity"][name]
        _require_exact_keys(values, expected, f"similarity.{name}")
        parsed = [parse_fraction(value) for value in values.values()]
        if any(value < 0 or value > 1 for value in parsed):
            raise ValueError(f"similarity.{name} values must be in [0, 1].")
    degree = config["similarity"]["bachelor_degree"]
    if not (
        parse_fraction(degree["detailed"])
        >= parse_fraction(degree["narrow"])
        >= parse_fraction(degree["broad"])
    ):
        raise ValueError("Bachelor-degree similarity must decrease by hierarchy level.")
    university = config["similarity"]["undergrad_university"]
    if parse_fraction(university["same_campus"]) < parse_fraction(
        university["same_system"]
    ):
        raise ValueError("University campus similarity must be at least system similarity.")
    location = config["similarity"]["home_location"]
    if not (
        parse_fraction(location["same_city"])
        >= parse_fraction(location["same_region"])
        >= parse_fraction(location["same_country"])
    ):
        raise ValueError("Location similarity must decrease by hierarchy level.")

    _require_exact_keys(config["catalogs"], set(CATALOG_NAMES), "catalogs")
    for name in CATALOG_NAMES:
        _validate_catalog(config, name)

    _require_exact_keys(
        config["review"],
        {"sensitivity_enabled", "weight_perturbation", "risk_weights"},
        "review",
    )
    if not isinstance(config["review"]["sensitivity_enabled"], bool):
        raise ValueError("review.sensitivity_enabled must be a YAML boolean.")
    perturbation = parse_fraction(config["review"]["weight_perturbation"])
    if perturbation <= 0 or perturbation >= 1:
        raise ValueError("review.weight_perturbation must be between 0 and 1.")
    risk_names = {"low_score", "candidate_count", "regret", "sensitivity", "exception"}
    _require_exact_keys(config["review"]["risk_weights"], risk_names, "review.risk_weights")
    _validate_fraction_map(
        config["review"]["risk_weights"], "review risk weight", require_positive=False
    )
    if not config["review"]["sensitivity_enabled"]:
        active_weight = sum(
            (
                parse_fraction(value)
                for name, value in config["review"]["risk_weights"].items()
                if name != "sensitivity"
            ),
            Fraction(),
        )
        if active_weight <= 0:
            raise ValueError(
                "Disabled sensitivity requires another positive review risk weight."
            )


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    resource = files("csap_siblings_match.policies").joinpath("default.yaml")
    with resource.open("r", encoding="utf-8") as stream:
        config = _load_yaml(stream)

    if path is not None:
        with Path(path).open("r", encoding="utf-8") as stream:
            override = _load_yaml(stream)
        config = _merge(config, override)
    validate_config(config)
    return config


def catalog_entry(config: dict[str, Any], catalog: str, raw_value: str) -> Any:
    try:
        return config["catalogs"][catalog][raw_value]
    except KeyError:
        raise KeyError(raw_value)
