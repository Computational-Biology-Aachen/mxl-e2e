from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
from mxlpy.meta import canonical_identifier_map

from e2e import greensloth, pipeline
from e2e.models import MODELS

if TYPE_CHECKING:
    from pathlib import Path

    from mxlpy import Model


@dataclass
class RoundTrip:
    """A reference mxl-models model, the model to compare, and reference id -> its id."""

    reference: Model
    generated: Model
    name_map: dict[str, str]


def _fail_on_error_file(path: Path) -> None:
    if path.exists():
        pytest.fail(path.read_text(), pytrace=False)


def _load(out: Path) -> Model:
    _fail_on_error_file(out / "generate-error.txt")
    _fail_on_error_file(out / "export-error.txt")
    return pipeline.load_generated(out / "model-gen.py")


def _reference(name: str) -> tuple[Model, dict[str, str]]:
    model = MODELS[name]()
    with warnings.catch_warnings():
        # Collisions are expected (and deterministic); the exporter warns too.
        warnings.simplefilter("ignore")
        return model, canonical_identifier_map(model.ids)


@pytest.fixture(scope="session")
def roundtrip_dirs() -> dict[str, Path]:
    """Steps 1 and 2 for every mxl-models model, once per session."""
    dirs = {name: pipeline.BUILD / "roundtrip" / name for name in MODELS}
    for name, factory in MODELS.items():
        pipeline.generate_ts(factory, dirs[name])
    pipeline.export_py(dirs.values())
    return dirs


@pytest.fixture(scope="session")
def greensloth_json() -> dict[str, tuple[Path, Path]]:
    """`buildMxlJson` of green-sloth's committed and of the generated model.ts, per slug."""
    dirs = {
        slug: (greensloth.stage(slug), greensloth.stage(slug, generated=True))
        for slug in greensloth.SLUGS
    }
    pipeline.export_mxl_json(d for pair in dirs.values() for d in pair)
    return dirs


@pytest.fixture
def roundtrip(
    request: pytest.FixtureRequest, roundtrip_dirs: dict[str, Path]
) -> RoundTrip:
    name = request.param
    generated = _load(roundtrip_dirs[name])
    reference, name_map = _reference(name)
    return RoundTrip(reference, generated, name_map)
