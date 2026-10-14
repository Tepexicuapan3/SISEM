import { spawnSync } from "node:child_process";
import path from "node:path";

import { describe, expect, it } from "vitest";

type NegativeGate = {
  readonly gate: string;
  readonly project: string;
  readonly fixture: string;
};

const NEGATIVE_GATES: ReadonlyArray<NegativeGate> = [
  {
    gate: "typecheck:tests",
    project: "tsconfig.tests.negative.json",
    fixture: "src/test/quality-gates/fixtures/negative-tests.fixture.ts",
  },
  {
    gate: "typecheck:e2e",
    project: "tsconfig.e2e.negative.json",
    fixture: "src/test/quality-gates/fixtures/negative-e2e.fixture.ts",
  },
] as const;

const FRONTEND_ROOT = process.cwd();

const runNegativeTypecheck = (projectPath: string) => {
  return spawnSync("pnpm", ["exec", "tsc", "-p", projectPath, "--noEmit"], {
    cwd: FRONTEND_ROOT,
    encoding: "utf-8",
    shell: process.platform === "win32",
  });
};

describe("TypeScript debt detection guard", () => {
  it.each(NEGATIVE_GATES)(
    "%s must fail when debt is present",
    ({ gate, project, fixture }) => {
      // Ruta RELATIVA a FRONTEND_ROOT (el cwd del proceso): en Windows el
      // spawn va por shell y una ruta absoluta con espacios
      // ("D:\PROYECTOS EN PRODUCCION\...") se parte en varios argumentos y
      // tsc falla con TS5042 en vez de detectar la deuda.
      const projectPath = path.relative(FRONTEND_ROOT, path.resolve(FRONTEND_ROOT, project));
      const result = runNegativeTypecheck(projectPath);
      const output = `${result.stdout}\n${result.stderr}`;

      expect(
        result.status,
        `${gate} should fail with injected TS debt`,
      ).not.toBe(0);
      expect(output).toContain(fixture);
      expect(output).toContain("TS2322");
    },
  );
});
