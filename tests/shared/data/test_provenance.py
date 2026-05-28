from pathlib import Path
import shutil

import pytest

from shared.data.provenance import input_data_metadata, repo_key


SCRATCH_ROOT = Path(".test_artifacts/provenance_tests")


@pytest.fixture
def scratch(request):
    path = SCRATCH_ROOT / request.node.name
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
        for parent in (SCRATCH_ROOT, SCRATCH_ROOT.parent):
            try:
                parent.rmdir()
            except OSError:
                pass


def test_input_data_metadata_records_repo_relative_file(scratch: Path):
    input_file = scratch / "data" / "bars" / "sample.csv"
    input_file.parent.mkdir(parents=True)
    input_file.write_text("abc", encoding="utf-8")

    metadata = input_data_metadata([input_file], repo_root=scratch)

    assert metadata["is_repo_relative"] is True
    assert metadata["bytes"] == {"data/bars/sample.csv": 3}
    assert metadata["sha256"]["data/bars/sample.csv"] == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )
    assert metadata["non_reproducible_paths"] == []


def test_repo_key_marks_external_path_as_absolute(scratch: Path):
    external = scratch.parent / "external.csv"

    assert repo_key(external, repo_root=scratch) == str(external.resolve())
