import { describe, expect, it } from "vitest";
import { habitError, habitYears, parseYear } from "@features/expedientes/domain/habit-rules";

const base = { status: "A" as const, frequency: null, quantity: null, since: null, until: null };

describe("parseYear", () => {
  it("vacío es null y un año de 4 dígitos es número", () => {
    expect(parseYear("")).toBeNull();
    expect(parseYear(" 2010 ")).toBe(2010);
  });

  it("cualquier otra cosa no es un año", () => {
    expect(parseYear("10")).toBeNaN();
    expect(parseYear("2O10")).toBeNaN();
  });
});

describe("habitError (mismas reglas que el backend)", () => {
  it("actual con desde: correcto", () => {
    expect(habitError({ ...base, since: 2010 }, 2026)).toBeNull();
  });

  it("año inválido o futuro", () => {
    expect(habitError({ ...base, since: Number.NaN }, 2026)).toContain("Desde");
    expect(habitError({ ...base, since: 2027 }, 2026)).toContain("2026");
  });

  it("lo niega no lleva cantidad ni años", () => {
    expect(habitError({ ...base, status: "N" }, 2026)).toBeNull();
    expect(habitError({ ...base, status: "N", quantity: "3 copas" }, 2026)).toContain("niega");
  });

  it("hasta solo con lo dejó, y no antes de desde", () => {
    expect(habitError({ ...base, until: 2020 }, 2026)).toContain("Lo dejó");
    expect(habitError({ ...base, status: "E", since: 2018, until: 2015 }, 2026)).toContain("antes de empezar");
    expect(habitError({ ...base, status: "E", since: 2005, until: 2015 }, 2026)).toBeNull();
  });
});

describe("habitYears", () => {
  it("arma el texto con lo que haya", () => {
    expect(habitYears({ since: 2010, until: 2020 })).toBe("desde 2010 · hasta 2020");
    expect(habitYears({ since: 2010, until: null })).toBe("desde 2010");
    expect(habitYears({ since: null, until: null })).toBeNull();
  });
});
