"""Run configuration: immutability, coercion, validation and run keys."""

from __future__ import annotations

import dataclasses

import pytest

from fds.config import RunConfig, load_config, parse_set_overrides


def test_overrides_return_a_new_config_and_leave_the_original_intact():
    cfg = RunConfig()
    changed = cfg.with_overrides({"graph.hub_max_degree": "500"})
    assert changed.graph.hub_max_degree == 500
    assert cfg.graph.hub_max_degree == 10


def test_string_overrides_are_coerced_to_the_declared_type():
    """`from __future__ import annotations` turns field types into strings, so
    naive type comparison silently leaves every --set value a str."""
    cfg = RunConfig().with_overrides({"graph.hub_max_degree": "500", "seed": "7"})
    assert isinstance(cfg.graph.hub_max_degree, int)
    assert isinstance(cfg.seed, int)


def test_run_key_changes_with_configuration_and_is_stable_otherwise():
    a = RunConfig()
    b = RunConfig().with_overrides({"uid.recipe_name": "v3_plus_email"})
    assert a.run_key() == RunConfig().run_key()
    assert a.run_key() != b.run_key()


@pytest.mark.parametrize(
    "override",
    [
        {"uid.recipe_name": "not_a_recipe"},
        {"graph.hub_min_degree": "1"},
        {"graph.hub_max_degree": "1"},
        {"graph.min_edge_weight": "0"},
        {"snapshots.cadence_days": "0"},
        {"graph.nonexistent": "3"},
        {"nosuch.key": "3"},
    ],
)
def test_invalid_configuration_is_rejected(override):
    with pytest.raises((ValueError, KeyError)):
        RunConfig().with_overrides(override)


def test_config_is_frozen():
    cfg = RunConfig()
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.seed = 1


def test_default_toml_loads_and_matches_code_defaults():
    cfg = load_config("configs/default.toml")
    assert cfg.uid.recipe_name == "v1_card1_addr1_d1n"
    assert cfg.model.params["objective"] == "binary"


def test_malformed_override_is_reported():
    with pytest.raises(ValueError, match="malformed"):
        parse_set_overrides(["no_equals_sign"])


def test_dataclass_defaults_match_the_shipped_config():
    """The fallback a [model]-only config inherits.

    configs/tuned/*.toml carry only a [model] section, so every other value
    comes from the dataclass defaults rather than from configs/default.toml.
    When those two drifted apart, `--config configs/tuned/m1.toml` silently
    selected a different graph than the repo documents.
    """
    coded, shipped = RunConfig(), load_config("configs/default.toml")
    assert coded.graph.hub_min_degree == shipped.graph.hub_min_degree
    assert coded.graph.hub_max_degree == shipped.graph.hub_max_degree
    assert coded.graph.min_edge_weight == shipped.graph.min_edge_weight
    assert coded.graph.link_types == shipped.graph.link_types
    assert coded.snapshots.cadence_days == shipped.snapshots.cadence_days
    assert coded.snapshots.first_end_day == shipped.snapshots.first_end_day
