import { describe, expect, it } from "vitest";
import { familyPresenceError, personalPresenceError } from "@features/expedientes/domain/record-presence";

describe("personalPresenceError (antecedente personal que el paciente niega)", () => {
  it("lo tiene: cualquier fecha vale", () => {
    expect(personalPresenceError({ presence: "S", diagnosisDate: "2020-01-01" })).toBeNull();
  });

  it("lo niega sin fecha: correcto", () => {
    expect(personalPresenceError({ presence: "N", diagnosisDate: null })).toBeNull();
  });

  it("lo niega con fecha de diagnostico: se contradice", () => {
    expect(personalPresenceError({ presence: "N", diagnosisDate: "2020-01-01" })).toContain("fecha");
  });
});

describe("familyPresenceError (antecedente familiar que el paciente niega)", () => {
  const base = { presence: "N" as const, cieCode: null, description: "Cáncer", isDeceased: false, causeOfDeath: null };

  it("lo niega con padecimiento: correcto", () => {
    expect(familyPresenceError(base)).toBeNull();
  });

  it("lo niega no lleva finado ni causa de muerte", () => {
    expect(familyPresenceError({ ...base, isDeceased: true })).toContain("finado");
    expect(familyPresenceError({ ...base, causeOfDeath: "Infarto" })).toContain("finado");
  });

  it("lo niega necesita saber que padecimiento", () => {
    expect(familyPresenceError({ ...base, description: null })).toContain("padecimiento");
  });

  it("lo tiene: no aplica la regla", () => {
    expect(familyPresenceError({ ...base, presence: "S", isDeceased: true, description: null })).toBeNull();
  });
});
