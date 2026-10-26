"""Regenerate green-sloth's model.ts files from mxl-models.

    uv run python -m e2e.regenerate_greensloth [slug ...]

Writes `src/lib/models/<slug>/model.ts` in the sibling green-sloth checkout,
moves the id references in its `meta.ts` over to the generated ids, formats
the files with green-sloth's own prettier and refreshes `model.mxl.json`
(`npm run generate:mxl`). Review the green-sloth diff before committing, and
remove the slugs' `generated` entries from `xfails.toml`.
"""

from __future__ import annotations

import argparse
import subprocess

from e2e import greensloth


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("slugs", nargs="*", default=list(greensloth.SLUGS))
    args = parser.parse_args()

    files = []
    for slug in args.slugs:
        model_ts = greensloth.GREENSLOTH_MODELS / slug / "model.ts"
        model_ts.write_text(greensloth.generate(slug))
        renamed = greensloth.migrate_ids(slug)
        files += [model_ts, model_ts.with_name("meta.ts")]
        print(f"{slug}: model.ts regenerated, meta.ts ids renamed: {renamed}")  # noqa: T201

    cwd = greensloth.GREENSLOTH
    subprocess.run(  # noqa: S603
        ["npx", "prettier", "--write", *map(str, files)],  # noqa: S607
        cwd=cwd,
        check=True,
    )
    subprocess.run(["npm", "run", "generate:mxl"], cwd=cwd, check=True)  # noqa: S607


if __name__ == "__main__":
    main()
