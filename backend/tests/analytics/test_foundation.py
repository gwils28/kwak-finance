"""The foundation models' weights (spec F-FCT-7): pinned, checked, read offline."""

import hashlib
import sys
import types
from pathlib import Path

import pytest
from kwak_analytics import foundation


def _hub(tmp_path: Path, content: bytes) -> types.ModuleType:
    """A stand-in for huggingface_hub: every file holds `content`."""

    def hf_hub_download(repo: str, file: str, *, revision: str, local_dir: Path) -> str:
        path = Path(local_dir) / file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return str(path)

    hub = types.ModuleType("huggingface_hub")
    hub.hf_hub_download = hf_hub_download  # type: ignore[attr-defined]
    return hub


def test_a_file_not_matching_its_checksum_fails_the_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "huggingface_hub", _hub(tmp_path, b"tampered"))
    with pytest.raises(SystemExit, match="checksum"):
        foundation.fetch(tmp_path)


def test_files_matching_their_checksums_are_kept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    digest = hashlib.sha256(b"weights").hexdigest()
    pinned = {
        name: foundation.Weights(w.repo, w.revision, dict.fromkeys(w.files, digest))
        for name, w in foundation.WEIGHTS.items()
    }
    monkeypatch.setattr(foundation, "WEIGHTS", pinned)
    monkeypatch.setitem(sys.modules, "huggingface_hub", _hub(tmp_path, b"weights"))
    foundation.fetch(tmp_path)
    assert (tmp_path / foundation.CHRONOS / "model.safetensors").read_bytes() == b"weights"


def test_not_available_without_the_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KWAK_FOUNDATION_DIR", raising=False)
    assert not foundation.available()
    assert foundation.revisions() == {}


def test_not_available_with_a_file_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KWAK_FOUNDATION_DIR", str(tmp_path))
    (tmp_path / foundation.CHRONOS).mkdir()
    (tmp_path / foundation.CHRONOS / "config.json").write_text("{}")
    assert not foundation.available()
