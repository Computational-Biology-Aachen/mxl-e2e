"""green-sloth's own model.ts (via mxlweb-core) against the mxl-models originals.

Diagnostic: the two collections are authored independently, so differences
are expected. Each one is listed in `xfails.toml` with its reason; fixes go
into the codegen, never into either side's model files by hand.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from e2e import compare, greensloth, xfails

if TYPE_CHECKING:
    from conftest import RoundTrip


def models(check: str) -> pytest.MarkDecorator:
    return pytest.mark.parametrize(
        "greensloth_pair",
        xfails.params("greensloth", list(greensloth.SLUGS), check),
        indirect=True,
    )


def _check(diffs: list[str]) -> None:
    assert not diffs, "\n".join(diffs)


@models("structure")
def test_structure(greensloth_pair: RoundTrip) -> None:
    p = greensloth_pair
    _check(compare.structure(p.reference, p.generated, p.name_map))


@models("values")
def test_values(greensloth_pair: RoundTrip) -> None:
    p = greensloth_pair
    _check(compare.values(p.reference, p.generated, p.name_map))


@models("args")
def test_args(greensloth_pair: RoundTrip) -> None:
    p = greensloth_pair
    _check(compare.args(p.reference, p.generated, p.name_map))


@models("units")
@pytest.mark.xfail(raises=ImportError, reason=xfails.UNITS_PENDING, strict=True)
def test_units(greensloth_pair: RoundTrip) -> None:
    p = greensloth_pair
    _check(compare.units(p.reference, p.generated, p.name_map))
