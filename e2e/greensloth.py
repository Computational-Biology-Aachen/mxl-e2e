"""green-sloth's models, generated from their mxl-models originals.

For every model in both collections, green-sloth's `model.ts` is mxlpy's
mxlweb export of the mxl-models model (`regenerate`), so the two are the same
model. `tests/test_greensloth.py` checks that the committed `model.ts` still is
what the codegen produces.

`maps/<slug>.json` record which id green-sloth's hand-written models used for
which mxl-models id; `migrate_ids` uses them to move green-sloth's own
references (`meta.ts`) over to the generated ids.
"""

from __future__ import annotations

import importlib
import inspect
import json
import re
import shutil
import warnings
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from mxlpy import meta
from mxlpy.meta import canonical_identifier_map

from e2e.models import MODELS
from e2e.pipeline import BUILD, ROOT

if TYPE_CHECKING:
    from pathlib import Path

GREENSLOTH = ROOT.parents[1] / "pages" / "green-sloth"
GREENSLOTH_MODELS = GREENSLOTH / "src" / "lib" / "models"
MAPS = ROOT / "maps"

# green-sloth slug -> e2e.models.MODELS key, for every model in both collections.
SLUGS: dict[str, str] = {
    "bellasio2019": "bellasio2019",
    "davis2017": "davis2017",
    "ebenhoeh2014": "ebenhoeh2014",
    "hahn1987": "hahn1987",
    "lam2026": "lam2026",
    "lazar1997": "lazar1997",
    "li2021": "li2021",
    "matuszynska2016": "matuszynska2016_npq",
    "matuszynska2019": "matuszynska2019",
    "morales2018": "morales2018",
    "poolman2000": "poolman2000",
    "saadat2021": "saadat2021",
    "salvatori2022": "salvatori2022",
    "yokota1985": "yokota1985",
    "zaks2012": "zaks2012",
    "zhu2005": "zhu2005",
    "zhu2009": "zhu2009",
}


@dataclass
class NameMap:
    """green-sloth id -> mxl-models id, plus the ids known to have no counterpart."""

    slug: str
    model: str
    to_mxlmodels: dict[str, str]
    only_greensloth: list[str] = field(default_factory=list)
    only_mxlmodels: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, slug: str) -> NameMap:
        data = json.loads((MAPS / f"{slug}.json").read_text())
        return cls(slug=slug, **data)

    def dump(self) -> None:
        MAPS.mkdir(exist_ok=True)
        data = {
            "model": self.model,
            "to_mxlmodels": dict(sorted(self.to_mxlmodels.items())),
            "only_greensloth": sorted(self.only_greensloth),
            "only_mxlmodels": sorted(self.only_mxlmodels),
        }
        (MAPS / f"{self.slug}.json").write_text(json.dumps(data, indent=2) + "\n")


def docstring(slug: str) -> str:
    """The model's mxl-models module docstring, as the JSDoc block above `initModel`."""
    doc = inspect.cleandoc(
        importlib.import_module(MODELS[SLUGS[slug]].__module__).__doc__ or ""
    )
    lines = [f" * {line}".rstrip() for line in doc.strip().splitlines()]
    return "\n".join(["/**", *lines, " */"])


def generate(slug: str) -> str:
    """green-sloth's `model.ts` for `slug`, generated from mxl-models."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return meta.generate_model_code_mxlweb(
            MODELS[SLUGS[slug]](), docstring=docstring(slug)
        )


def stage(slug: str, *, generated: bool = False) -> Path:
    """Copy green-sloth's committed (or a freshly generated) `model.ts` into the build dir."""
    out = BUILD / "greensloth" / slug / ("generated" if generated else "committed")
    out.mkdir(parents=True, exist_ok=True)
    if generated:
        (out / "model.ts").write_text(generate(slug))
        return out
    shutil.copyfile(GREENSLOTH / "src" / "lib" / "names.ts", out / "names.ts")
    source = (GREENSLOTH_MODELS / slug / "model.ts").read_text()
    (out / "model.ts").write_text(source.replace('"#lib/names.js"', '"./names.ts"'))
    return out


def migrate_ids(slug: str) -> dict[str, str]:
    """Rewrite id string literals in green-sloth's `meta.ts` from its old ids to the generated ones."""
    nm = NameMap.load(slug)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        canonical = canonical_identifier_map(MODELS[SLUGS[slug]]().ids)
    renames = {
        old: canonical[new]
        for old, new in nm.to_mxlmodels.items()
        if canonical[new] != old
    }
    path = GREENSLOTH_MODELS / slug / "meta.ts"
    text = path.read_text()
    done: dict[str, str] = {}

    def rename(m: re.Match[str]) -> str:
        if (new := renames.get(m.group(1))) is None:
            return m.group(0)
        done[m.group(1)] = new
        return json.dumps(new)

    path.write_text(re.sub(r'"([^"\\]*)"', rename, text))
    return done
