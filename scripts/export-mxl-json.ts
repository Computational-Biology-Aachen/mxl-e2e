/**
 * Write `<dir>/model.mxl.json` (`buildMxlJson`) for every `<dir>/model.ts`
 * given on the command line: the canonical form of everything a model
 * defines (values, expressions, stoichiometry, units, display/LaTeX names,
 * sliders), used to compare two model.ts files semantically rather than by
 * text. A model that fails gets `<dir>/export-error.txt` instead.
 */
import { rmSync, writeFileSync } from "node:fs";
import { basename, resolve } from "node:path";
import { pathToFileURL } from "node:url";

type Exportable = { buildMxlJson(modelId: string): string };

for (const dir of process.argv.slice(2)) {
  const errorFile = resolve(dir, "export-error.txt");
  rmSync(errorFile, { force: true });
  try {
    const mod = (await import(pathToFileURL(resolve(dir, "model.ts")).href)) as {
      initModel(): Exportable;
    };
    const json = mod.initModel().buildMxlJson(basename(resolve(dir, "..")));
    writeFileSync(resolve(dir, "model.mxl.json"), json + "\n");
  } catch (err) {
    writeFileSync(errorFile, err instanceof Error ? (err.stack ?? err.message) : String(err));
  }
}
