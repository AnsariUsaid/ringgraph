"""Deterministic seed derivation.

One master seed in the run config; every component derives its own from the
master plus its name. Two properties matter: adding a component never shifts the
seeds of existing ones (which would silently change results elsewhere), and the
global ``np.random.seed()`` is never touched — callers receive their own
``Generator``.
"""

from __future__ import annotations

from hashlib import blake2b

import numpy as np


def seed_for(component: str, master_seed: int) -> int:
    """Derive a stable 32-bit seed for a named component."""
    payload = f"{master_seed}:{component}".encode()
    return int.from_bytes(blake2b(payload, digest_size=4).digest(), "big")


def rng_for(component: str, master_seed: int) -> np.random.Generator:
    return np.random.default_rng(seed_for(component, master_seed))
