"""Phase 2: green-sloth's own `model.ts` files against their mxl-models originals.

green-sloth authors its models independently (green-sloth ADR 0002, mxl-models
ADR 0004), so their ids differ from the mxl-models ones. `maps/<slug>.json`
records which green-sloth id corresponds to which mxl-models id; the
comparison only diagnoses where the two have drifted apart.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from e2e.pipeline import BUILD, ROOT

if TYPE_CHECKING:
    from pathlib import Path

GREENSLOTH = ROOT.parents[1] / "pages" / "green-sloth"
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

    def from_mxlmodels(self, ids: list[str]) -> dict[str, str]:
        """mxl-models id -> green-sloth id; ids without a counterpart map to a marker."""
        inverse = {v: k for k, v in self.to_mxlmodels.items()}
        return {i: inverse.get(i, f"<no green-sloth id for {i!r}>") for i in ids}


def stage(slug: str) -> Path:
    """Copy green-sloth's `model.ts` (and the names it imports) into the build dir."""
    out = BUILD / "greensloth" / slug
    out.mkdir(parents=True, exist_ok=True)
    lib = GREENSLOTH / "src" / "lib"
    shutil.copyfile(lib / "names.ts", out / "names.ts")
    source = (lib / "models" / slug / "model.ts").read_text()
    (out / "model.ts").write_text(source.replace('"#lib/names.js"', '"./names.ts"'))
    return out
