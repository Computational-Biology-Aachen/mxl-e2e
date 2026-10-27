"""green-sloth's models, generated from their mxl-models originals.

For every model in both collections, green-sloth's `model.ts` is mxlpy's
mxlweb export of the mxl-models model (`regenerate`), so the two are the same
model. `tests/test_greensloth.py` checks that the committed `model.ts` still is
what the codegen produces.

`maps/<slug>.json` record the ids green-sloth's hand-written models used where
the generated id differs (old id -> generated id), for the four models whose
ids changed when they were first generated. `migrate_ids` uses them to move
green-sloth's own references (`meta.ts`) over to the generated ids.
"""

from __future__ import annotations

import importlib
import inspect
import json
import re
import shutil
import warnings
from typing import TYPE_CHECKING

from mxlpy import meta

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
    path = MAPS / f"{slug}.json"
    renames: dict[str, str] = json.loads(path.read_text()) if path.exists() else {}
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
