"""Steps 1 and 2 of the pipeline: mxlpy -> model.ts -> model-gen.py."""

from __future__ import annotations

import importlib.util
import subprocess
import traceback
from pathlib import Path
from typing import TYPE_CHECKING

from mxlpy import meta

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from mxlpy import Model

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"


def generate_ts(factory: Callable[[], Model], out: Path) -> None:
    """Write `out/model.ts` via mxlpy, or `out/generate-error.txt` if that fails."""
    out.mkdir(parents=True, exist_ok=True)
    for stale in ("model.ts", "model-gen.py", "generate-error.txt"):
        (out / stale).unlink(missing_ok=True)
    try:
        code = meta.generate_model_code_mxlweb(factory())
    except Exception:  # noqa: BLE001
        (out / "generate-error.txt").write_text(traceback.format_exc())
        return
    (out / "model.ts").write_text(code)


def _npm_run(script: str, dirs: Iterable[Path]) -> None:
    dirs = [str(d) for d in dirs if (d / "model.ts").exists()]
    if dirs:
        subprocess.run(  # noqa: S603
            ["npm", "run", "--silent", script, "--", *dirs],  # noqa: S607
            cwd=ROOT,
            check=True,
        )


def export_py(dirs: Iterable[Path]) -> None:
    """Run mxlweb-core's mxlpy export for every `dir/model.ts` in one Node process."""
    _npm_run("export-mxlpy", dirs)


def export_mxl_json(dirs: Iterable[Path]) -> None:
    """Write `dir/model.mxl.json` (mxlweb-core `buildMxlJson`) for every `dir/model.ts`."""
    _npm_run("export-mxl-json", dirs)


def load_generated(path: Path) -> Model:
    """Import `path` (a `buildMxlpy()` module) and build its model."""
    spec = importlib.util.spec_from_file_location(f"_e2e_{path.parent.name}", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.get_model()
