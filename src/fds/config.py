"""Run configuration.

Three tiers, and the boundary between them is the design (D-14):

* **Code constants** — split boundaries, column groups, the ``day`` derivation.
  In ``splits.py`` and ``schema.py``, not here. They are never legitimately
  swept, and as config values they could drift by a one-line edit.
* **Swept parameters** — this module. uid recipe, hub band, snapshot cadence,
  model hyperparameters, seed. Frozen, resolved once at the top of a script,
  logged, and threaded down as an argument.
* **Environment** — data root, Neo4j URI and credentials, thread counts. Read
  from the environment, never committed, and deliberately excluded from the run
  key so the same experiment does not get two keys on two machines.

There is no module-level ``CONFIG`` singleton and there will not be one. A mutable
global is what makes a result depend on import order.

Config files are TOML, read with the stdlib ``tomllib`` — no YAML dependency, and
the format already appears in this repo as ``pyproject.toml``.
"""

from __future__ import annotations

import json
import tomllib
from dataclasses import asdict, dataclass, field, fields, replace
from functools import cache
from hashlib import sha256
from pathlib import Path
from typing import Any, get_origin, get_type_hints

from fds.entities import DEFAULT_RECIPE, UID_RECIPES
from fds.links import IDENTITY_LINK_COLUMNS

RUN_KEY_LENGTH = 8


@dataclass(frozen=True)
class UidConfig:
    recipe_name: str = DEFAULT_RECIPE

    def __post_init__(self) -> None:
        if self.recipe_name not in UID_RECIPES:
            raise ValueError(
                f"unknown uid recipe {self.recipe_name!r}; "
                f"registered: {sorted(UID_RECIPES)}. Recipes are defined in code "
                f"(fds.entities.UID_RECIPES), not in config."
            )


@dataclass(frozen=True)
class GraphConfig:
    """Hub pruning and which shared attributes may link clients.

    The degree band is a *reported parameter* (plan.md §Part 3): chosen by looking
    at the profiled degree distribution, not auto-derived, because a threshold
    nobody chose is a threshold nobody can defend.

    Note the band is applied to **snapshot-local** degrees, never global ones
    (D-07) — otherwise whether an entity is pruned at day 30 depends on day-180
    data, which is a forward leak baked into the topology where no row-level
    timestamp check can see it.
    """

    hub_min_degree: int = 2
    hub_max_degree: int = 10
    min_edge_weight: int = 1
    # Single source of truth lives in fds.links. Duplicating the tuple here is
    # what let the gate scripts drift away from the pipeline.
    link_types: tuple[str, ...] = IDENTITY_LINK_COLUMNS

    def __post_init__(self) -> None:
        if self.hub_min_degree < 2:
            raise ValueError(
                "hub_min_degree below 2 admits degree-1 entities, which link nothing "
                "and only inflate the node count"
            )
        if self.hub_max_degree <= self.hub_min_degree:
            raise ValueError("hub_max_degree must exceed hub_min_degree")
        if self.min_edge_weight < 1:
            raise ValueError("min_edge_weight must be at least 1")


@dataclass(frozen=True)
class SnapshotConfig:
    """Expanding-window graph snapshots (plan.md Trap B).

    Cadence 7 gives 24 snapshots over the 182-day span. It is chosen over 14
    because a client only receives structure if it transacted strictly before a
    boundary that is itself at or before the target day, so a coarse cadence
    strands short-lived clients: 39.5% of rows get a snapshot at cadence 7
    against 35.4% at 14.

    These defaults must match configs/default.toml. A config file carrying only
    a [model] section inherits *these* values, not that file's, so a divergence
    silently selects a different graph.
    """

    cadence_days: int = 7
    first_end_day: int = 14  # no snapshot before there is enough history to be meaningful

    def __post_init__(self) -> None:
        if self.cadence_days < 1:
            raise ValueError("cadence_days must be at least 1")
        if self.first_end_day < self.cadence_days:
            raise ValueError("first_end_day must be at least one full cadence in")


@dataclass(frozen=True)
class ModelConfig:
    kind: str = "lightgbm"
    num_boost_round: int = 2000
    early_stopping_rounds: int = 100
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RunConfig:
    uid: UidConfig = field(default_factory=UidConfig)
    graph: GraphConfig = field(default_factory=GraphConfig)
    snapshots: SnapshotConfig = field(default_factory=SnapshotConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    seed: int = 20260921

    # --- resolution ----------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def canonical_json(self) -> str:
        """Stable serialisation: sorted keys, no incidental whitespace."""
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), default=str)

    def run_key(self) -> str:
        """Short content hash of the resolved config — the artefact partition key."""
        return sha256(self.canonical_json().encode()).hexdigest()[:RUN_KEY_LENGTH]

    def with_overrides(self, overrides: dict[str, Any]) -> RunConfig:
        """Return a new config with dotted-path values replaced.

        Frozen in, frozen out: overrides never mutate an existing config.
        """
        return _apply(self, overrides)


_SECTIONS: dict[str, type] = {
    "uid": UidConfig,
    "graph": GraphConfig,
    "snapshots": SnapshotConfig,
    "model": ModelConfig,
}


@cache
def _field_types(cls: type) -> dict[str, Any]:
    """Resolved field types for a dataclass.

    ``from __future__ import annotations`` leaves ``Field.type`` as a *string*,
    so comparing it against ``int`` silently never matches and every ``--set``
    value stays a string. Resolving the hints is what makes coercion work at all.
    """
    hints = get_type_hints(cls)
    return {f.name: hints[f.name] for f in fields(cls)}


def _coerce(target_type: Any, raw: Any) -> Any:
    """Coerce a string from the command line to the field's declared type."""
    if not isinstance(raw, str):
        return raw
    if target_type is int:
        return int(raw)
    if target_type is float:
        return float(raw)
    if target_type is bool:
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    if target_type is tuple or get_origin(target_type) is tuple:
        return tuple(part.strip() for part in raw.split(",") if part.strip())
    return raw


def _apply(cfg: RunConfig, overrides: dict[str, Any]) -> RunConfig:
    changes: dict[str, Any] = {}
    for dotted, value in overrides.items():
        if "." not in dotted:
            top_types = _field_types(RunConfig)
            if dotted not in top_types:
                raise KeyError(f"unknown config key {dotted!r}")
            changes[dotted] = _coerce(top_types[dotted], value)
            continue
        section, key = dotted.split(".", 1)
        if section not in _SECTIONS:
            raise KeyError(f"unknown config section {section!r} in {dotted!r}")
        current = changes.get(section, getattr(cfg, section))
        declared = _field_types(_SECTIONS[section])
        if key not in declared:
            raise KeyError(f"unknown key {key!r} in section {section!r}")
        changes[section] = replace(current, **{key: _coerce(declared[key], value)})
    return replace(cfg, **changes)


def _build_section(cls: type, raw: dict[str, Any]) -> Any:
    declared = {f.name for f in fields(cls)}
    unknown = sorted(set(raw) - declared)
    if unknown:
        raise KeyError(f"unknown keys {unknown} in [{cls.__name__}] section")
    kwargs = dict(raw)
    for name, value in kwargs.items():
        if isinstance(value, list):
            kwargs[name] = tuple(value)
    return cls(**kwargs)


def load_config(
    path: Path | str | None = None, overrides: dict[str, Any] | None = None
) -> RunConfig:
    """Build a fully resolved, immutable config from a TOML file plus overrides.

    Called once, at the top of a script. The result is logged as
    ``canonical_json()`` and passed down explicitly from there.
    """
    raw: dict[str, Any] = {}
    if path is not None:
        with Path(path).open("rb") as fh:
            raw = tomllib.load(fh)

    sections = {name: _build_section(cls, raw.get(name, {})) for name, cls in _SECTIONS.items()}
    top = {k: v for k, v in raw.items() if k not in _SECTIONS}
    unknown = sorted(set(top) - {f.name for f in fields(RunConfig)})
    if unknown:
        raise KeyError(f"unknown top-level config keys {unknown}")

    cfg = RunConfig(**sections, **top)
    return cfg.with_overrides(overrides) if overrides else cfg


def parse_set_overrides(pairs: list[str]) -> dict[str, Any]:
    """Turn ``--set graph.hub_max_degree=500`` arguments into an override dict."""
    out: dict[str, Any] = {}
    for pair in pairs:
        if "=" not in pair:
            raise ValueError(f"malformed override {pair!r}; expected key=value")
        key, value = pair.split("=", 1)
        out[key.strip()] = value.strip()
    return out
