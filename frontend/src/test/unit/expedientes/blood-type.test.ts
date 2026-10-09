import { describe, expect, it } from "vitest";
import type { BloodTypeRecord } from "@api/types";
import { bloodTypeSummary, classifyBloodTypeChange } from "@features/expedientes/domain/blood-type";

const vigente = (overrides: Partial<BloodTypeRecord> = {}): BloodTypeRecord => ({
  id: 1,
  bloodTypeId: 7,
  bloodTypeName: "O+",
  source: "L",
  labResultId: null,
  status: "A",
  createdAt: "2026-10-08T10:00:00Z",
  createdById: 3,
  updatedAt: "2026-10-08T10:00:00Z",
  ...overrides,
});

describe("bloodTypeSummary (header del expediente)", () => {
  it("muestra el tipo de laboratorio tal cual", () => {
    expect(bloodTypeSummary(vigente())).toBe("O+");
  });

  it("marca el declarado por el paciente", () => {
    expect(bloodTypeSummary(vigente({ source: "D" }))).toBe("O+ (declarado)");
  });

  it("sin registro devuelve null", () => {
    expect(bloodTypeSummary(null)).toBeNull();
    expect(bloodTypeSummary(undefined)).toBeNull();
  });
});

describe("classifyBloodTypeChange (cuando pedir motivo)", () => {
  it("sin vigente es primera captura, sin motivo", () => {
    expect(classifyBloodTypeChange(null, { bloodTypeId: 7, source: "D" })).toBe("capture");
  });

  it("sin tipo elegido no hay nada que guardar", () => {
    expect(classifyBloodTypeChange(null, { bloodTypeId: null, source: "D" })).toBe("none");
  });

  it("igual al vigente no cambia nada", () => {
    expect(classifyBloodTypeChange(vigente(), { bloodTypeId: 7, source: "L" })).toBe("none");
  });

  it("cambiar el tipo o la fuente es correccion (pide motivo)", () => {
    expect(classifyBloodTypeChange(vigente(), { bloodTypeId: 1, source: "L" })).toBe("correction");
    expect(classifyBloodTypeChange(vigente({ source: "D" }), { bloodTypeId: 7, source: "L" })).toBe("correction");
  });
});
