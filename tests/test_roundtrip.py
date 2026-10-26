"""mxl-models -> model.ts (mxlpy) -> model-gen.py (mxlweb-core): the same model?"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from e2e import compare, xfails
from e2e.models import MODELS

if TYPE_CHECKING:
    from conftest import RoundTrip


def models(check: str) -> pytest.MarkDecorator:
    return pytest.mark.parametrize(
        "roundtrip", xfails.params("roundtrip", list(MODELS), check), indirect=True
    )


def _check(diffs: list[str]) -> None:
    assert not diffs, "\n".join(diffs)


@models("structure")
def test_structure(roundtrip: RoundTrip) -> None:
    _check(
        compare.structure(roundtrip.reference, roundtrip.generated, roundtrip.name_map)
    )


@models("values")
def test_values(roundtrip: RoundTrip) -> None:
    _check(compare.values(roundtrip.reference, roundtrip.generated, roundtrip.name_map))


@models("args")
def test_args(roundtrip: RoundTrip) -> None:
    _check(compare.args(roundtrip.reference, roundtrip.generated, roundtrip.name_map))


@models("display_names")
def test_display_names(roundtrip: RoundTrip) -> None:
    _check(
        compare.display_names(
            roundtrip.reference, roundtrip.generated, roundtrip.name_map
        )
    )


@models("units")
def test_units(roundtrip: RoundTrip) -> None:
    _check(compare.units(roundtrip.reference, roundtrip.generated, roundtrip.name_map))
