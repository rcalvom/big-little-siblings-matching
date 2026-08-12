from __future__ import annotations

from fractions import Fraction

import pytest

from csap_siblings_match.config import (
    COMPONENT_NAMES,
    load_config,
    parse_fraction,
    validate_config,
)

from .factories import synthetic_config


def test_packaged_policy_uses_equal_exact_weights() -> None:
    config = load_config()

    assert {parse_fraction(config["weights"][name]) for name in COMPONENT_NAMES} == {
        Fraction(1)
    }


def test_config_rejects_unknown_keys() -> None:
    config = synthetic_config()
    config["unexpected"] = True

    with pytest.raises(ValueError, match="do not match the published schema"):
        validate_config(config)


def test_config_rejects_duplicate_yaml_keys(tmp_path) -> None:
    path = tmp_path / "duplicate.yaml"
    path.write_text(
        "weights:\n  advisor: '1'\n  advisor: '2'\n", encoding="utf-8"
    )

    with pytest.raises(ValueError, match="duplicate mapping keys"):
        load_config(path)


def test_config_requires_supported_schema_and_monotone_similarity() -> None:
    config = synthetic_config()
    config["schema_version"] = "999"
    with pytest.raises(ValueError, match="2.0"):
        validate_config(config)

    config = synthetic_config()
    config["similarity"]["home_location"]["same_country"] = "1"
    config["similarity"]["home_location"]["same_region"] = "1/2"
    with pytest.raises(ValueError, match="decrease"):
        validate_config(config)


def test_config_rejects_non_text_keys_without_echoing_them() -> None:
    config = synthetic_config()
    config[1] = "private-value"

    with pytest.raises(ValueError, match="non-text key") as captured:
        validate_config(config)

    assert "private-value" not in str(captured.value)


def test_disabled_sensitivity_requires_another_review_signal() -> None:
    config = synthetic_config()
    config["review"]["sensitivity_enabled"] = False
    config["review"]["risk_weights"] = {
        "low_score": "0",
        "candidate_count": "0",
        "regret": "0",
        "sensitivity": "1",
        "exception": "0",
    }

    with pytest.raises(ValueError, match="another positive"):
        validate_config(config)
