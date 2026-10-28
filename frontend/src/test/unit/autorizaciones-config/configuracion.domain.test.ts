import { describe, expect, it } from "vitest";
import {
  motivoSchema,
  normalizarClaveMotivo,
  reglaCentroSchema,
  tipoSchema,
} from "@features/admin/modules/autorizaciones-config/domain/configuracion.schemas";

// Replica en UX las reglas C1-C4 del backend (el servidor decide).

const tipoValido = {
  modalidadPredeterminada: "PRIMERO_VALIDO" as const,
  aprobacionesRequeridas: 1,
  horasVigenciaSolicitud: 72,
  horasEscalamiento: 24,
  permiteRechazo: true,
  rechazoResuelveSolicitud: true,
  requiereCedula: true,
};

describe("tipoSchema", () => {
  it("acepta la configuracion sembrada", () => {
    expect(tipoSchema.safeParse(tipoValido).success).toBe(true);
  });

  it("primero valido exige una sola aprobacion", () => {
    const resultado = tipoSchema.safeParse({ ...tipoValido, aprobacionesRequeridas: 2 });
    expect(resultado.success).toBe(false);
  });

  it("aprobaciones entre 1 y 10", () => {
    for (const valor of [0, 11]) {
      expect(
        tipoSchema.safeParse({ ...tipoValido, modalidadPredeterminada: "MULTIPLE", aprobacionesRequeridas: valor })
          .success,
      ).toBe(false);
    }
  });

  it("el escalamiento ocurre antes del vencimiento", () => {
    const resultado = tipoSchema.safeParse({ ...tipoValido, horasEscalamiento: 72 });
    expect(resultado.success).toBe(false);
  });
});

describe("reglaCentroSchema", () => {
  it("necesita al menos un valor propio", () => {
    const resultado = reglaCentroSchema.safeParse({
      tipoId: 1,
      centroId: 2,
      modalidad: null,
      aprobacionesRequeridas: null,
      horasVigenciaSolicitud: null,
    });
    expect(resultado.success).toBe(false);
  });

  it("acepta solo horas propias", () => {
    const resultado = reglaCentroSchema.safeParse({
      tipoId: 1,
      centroId: 2,
      modalidad: null,
      aprobacionesRequeridas: null,
      horasVigenciaSolicitud: 12,
    });
    expect(resultado.success).toBe(true);
  });

  it("pide tipo y centro", () => {
    const resultado = reglaCentroSchema.safeParse({
      tipoId: 0,
      centroId: 0,
      modalidad: "MULTIPLE",
      aprobacionesRequeridas: 2,
      horasVigenciaSolicitud: null,
    });
    expect(resultado.success).toBe(false);
  });
});

describe("motivos", () => {
  it("normaliza la clave como el backend", () => {
    expect(normalizarClaveMotivo("  dosis excesiva ")).toBe("DOSIS_EXCESIVA");
  });

  it("valida clave y descripcion", () => {
    expect(
      motivoSchema.safeParse({ ambito: "RECHAZO", clave: "X", descripcion: "", requiereDescripcionLibre: false })
        .success,
    ).toBe(false);
    expect(
      motivoSchema.safeParse({
        ambito: "RECHAZO",
        clave: "DOSIS",
        descripcion: "Dosis excesiva",
        requiereDescripcionLibre: false,
      }).success,
    ).toBe(true);
  });
});
