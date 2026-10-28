import { describe, expect, it } from "vitest";
import {
  avisoAutorizacionPaseEmitido,
  ETIQUETA_AUTORIZACION_PASE,
} from "@features/autorizaciones/domain/pase-autorizacion.format";

describe("autorizacion de pases", () => {
  it("etiqueta cada estatus del motor", () => {
    expect(ETIQUETA_AUTORIZACION_PASE).toEqual({
      NO_REQUIERE: "No requiere",
      PENDIENTE: "Pendiente",
      AUTORIZADO: "Autorizado",
      RECHAZADO: "Rechazado",
      VENCIDO: "Vencido",
    });
  });

  it("al emitir, avisa solo si quedo pendiente de autorizar", () => {
    expect(avisoAutorizacionPaseEmitido("PENDIENTE")).toMatch(/Requiere autorización/);
    expect(avisoAutorizacionPaseEmitido("NO_REQUIERE")).toBe("");
    expect(avisoAutorizacionPaseEmitido(undefined)).toBe("");
  });
});
