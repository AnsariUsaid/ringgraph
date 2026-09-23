"""The stale-artefact guard.

This module's entire purpose is catching a silent failure -- an artefact written
under a different column contract being loaded into code that expects the new
one -- and it had no test that it catches anything.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

from fds.artifacts import (
    MANIFEST_NAME,
    StaleArtifactError,
    file_digest,
    input_ref,
    read_manifest,
    read_parquet,
    verify_inputs,
    write_parquet,
)


@pytest.fixture
def frame() -> pd.DataFrame:
    return pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})


class TestManifest:
    def test_written_beside_the_parquet_by_the_same_call(self, tmp_path, frame):
        """Never a separate step: separate steps get skipped."""
        path = write_parquet(frame, tmp_path / "t.parquet", schema_version=1)
        manifest = read_manifest(path)
        assert manifest is not None
        assert manifest["schema_version"] == 1
        assert manifest["rows"] == 3
        assert manifest["columns"] == ["a", "b"]

    def test_records_the_resolved_params_that_produced_it(self, tmp_path, frame):
        path = write_parquet(
            frame, tmp_path / "t.parquet", schema_version=2, params={"ceiling": 10}
        )
        assert read_manifest(path)["params"] == {"ceiling": 10}


class TestSchemaVersionGuard:
    def test_refuses_an_artefact_from_a_different_contract(self, tmp_path, frame):
        path = write_parquet(frame, tmp_path / "t.parquet", schema_version=1)
        with pytest.raises(StaleArtifactError, match="schema_version"):
            read_parquet(path, expect_schema_version=2)

    def test_accepts_a_matching_contract(self, tmp_path, frame):
        path = write_parquet(frame, tmp_path / "t.parquet", schema_version=3)
        assert len(read_parquet(path, expect_schema_version=3)) == 3

    def test_warns_when_provenance_is_missing(self, tmp_path, frame):
        path = write_parquet(frame, tmp_path / "t.parquet", schema_version=1)
        (tmp_path / MANIFEST_NAME).unlink()
        with pytest.warns(UserWarning, match="provenance"):
            read_parquet(path)

    def test_strict_mode_refuses_missing_provenance(self, tmp_path, frame):
        path = write_parquet(frame, tmp_path / "t.parquet", schema_version=1)
        (tmp_path / MANIFEST_NAME).unlink()
        with pytest.raises(StaleArtifactError):
            read_parquet(path, strict=True)

    def test_missing_artefact_names_the_step_that_builds_it(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="earlier pipeline step"):
            read_parquet(tmp_path / "absent.parquet")


class TestInputVerification:
    def test_clean_when_inputs_are_unchanged(self, tmp_path, frame):
        source = tmp_path / "source.csv"
        source.write_text("a,b\n1,x\n")
        path = write_parquet(
            frame, tmp_path / "out.parquet", schema_version=1, inputs=[input_ref(source)]
        )
        assert verify_inputs(path) == []

    def test_detects_an_input_that_changed_after_the_write(self, tmp_path, frame):
        source = tmp_path / "source.csv"
        source.write_text("a,b\n1,x\n")
        path = write_parquet(
            frame, tmp_path / "out.parquet", schema_version=1, inputs=[input_ref(source)]
        )
        source.write_text("a,b\n9,z\n")  # the silent-staleness scenario
        problems = verify_inputs(path)
        assert len(problems) == 1
        assert "has changed" in problems[0]

    def test_detects_a_deleted_input(self, tmp_path, frame):
        source = tmp_path / "source.csv"
        source.write_text("a,b\n1,x\n")
        path = write_parquet(
            frame, tmp_path / "out.parquet", schema_version=1, inputs=[input_ref(source)]
        )
        source.unlink()
        assert "no longer exists" in verify_inputs(path)[0]

    def test_reports_rather_than_crashes_without_a_manifest(self, tmp_path, frame):
        path = write_parquet(frame, tmp_path / "t.parquet", schema_version=1)
        (tmp_path / MANIFEST_NAME).unlink()
        assert "cannot verify" in verify_inputs(path)[0]


def test_file_digest_is_content_based(tmp_path):
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    a.write_text("same")
    b.write_text("same")
    assert file_digest(a) == file_digest(b)
    b.write_text("different")
    assert file_digest(a) != file_digest(b)


def test_manifest_is_valid_json(tmp_path, frame):
    write_parquet(frame, tmp_path / "t.parquet", schema_version=1)
    json.loads((tmp_path / MANIFEST_NAME).read_text())
