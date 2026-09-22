"""Model matrices.

Deliberately *not* cached to disk (D-10). A stored ``X_train.parquet`` is the
canonical stale-artefact bug: add a feature, forget to invalidate, and the model
trains on last week's columns while every log line claims otherwise. The matrix
is a column projection of the base frame plus config, so it is rebuilt every
time; the resolved feature list goes into the run manifest, which is what
reproducibility actually needs.
"""

from __future__ import annotations

import pandas as pd

from fds import schema
from fds.splits import Split, assign_split


def tabular_feature_columns(df: pd.DataFrame) -> list[str]:
    """Every column a tabular model may see.

    Includes the identity block (``DeviceInfo``, ``id_*``) on purpose. The
    baseline has to be the strongest honest tabular model available, or the
    later M2-M1 comparison measures categorical encoding rather than structure —
    and a lazy baseline invalidates the headline result more thoroughly than a
    weak graph model would.
    """
    candidates = [c for c in df.columns if c not in schema.FEATURE_DENY_LIST]
    schema.assert_no_denied_features(candidates)
    return candidates


def categorical_columns(df: pd.DataFrame, features: list[str]) -> list[str]:
    return [c for c in features if str(df[c].dtype) == "category"]


def split_frames(
    df: pd.DataFrame, features: list[str]
) -> dict[Split, tuple[pd.DataFrame, pd.Series]]:
    """Slice the frame into train/val/test by day, with no shuffling anywhere."""
    splits = assign_split(df[schema.DAY])
    out: dict[Split, tuple[pd.DataFrame, pd.Series]] = {}
    for split in Split:
        mask = (splits == str(split)).to_numpy()
        out[split] = (df.loc[mask, features], df.loc[mask, schema.TARGET])
    return out


def prediction_frame(df: pd.DataFrame, scores_by_split: dict[Split, pd.Series]) -> pd.DataFrame:
    """The artefact every downstream metric is a pure function of (D-11).

    Keyed on TransactionID so paired tests between models are correct by
    construction rather than by careful alignment.
    """
    splits = assign_split(df[schema.DAY])
    frames = []
    for split, scores in scores_by_split.items():
        mask = (splits == str(split)).to_numpy()
        frames.append(
            pd.DataFrame(
                {
                    schema.KEY: df.loc[mask, schema.KEY].to_numpy(),
                    "split": str(split),
                    "y_true": df.loc[mask, schema.TARGET].to_numpy(),
                    "y_score": scores.to_numpy(),
                }
            )
        )
    return pd.concat(frames, ignore_index=True)
