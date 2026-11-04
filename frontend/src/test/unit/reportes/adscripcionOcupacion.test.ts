import { describe, expect, it } from "vitest";
import { ocupacionConsultorio } from "@features/admin/modules/reportes/domain/adscripcionOcupacion";

describe("ocupacionConsultorio", () => {
  it("sin tope no hay ocupación que medir", () => {
    expect(ocupacionConsultorio(40, null)).toBeNull();
    expect(ocupacionConsultorio(40, 0)).toBeNull();
  });

  it("calcula el porcentaje y el nivel", () => {
    expect(ocupacionConsultorio(60, 200)).toEqual({ porcentaje: 30, nivel: "normal" });
    expect(ocupacionConsultorio(160, 200)).toEqual({ porcentaje: 80, nivel: "alto" });
    expect(ocupacionConsultorio(200, 200)).toEqual({ porcentaje: 100, nivel: "lleno" });
  });

  it("pasado el tope sigue lleno y el porcentaje real se conserva", () => {
    expect(ocupacionConsultorio(230, 200)).toEqual({ porcentaje: 115, nivel: "lleno" });
  });
});
