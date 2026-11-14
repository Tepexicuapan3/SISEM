import { describe, expect, it } from "vitest";

import { ApiError } from "@api/utils/errors";
import type { AdscripcionResumen } from "@api/types";
import {
  conflictoConsultorioFamiliar,
  etiquetaConsultorio,
  presentarEstadoAdscripcion,
} from "@features/recepcion/modules/adscripcion/domain/adscripcionEstado";

const base: AdscripcionResumen = {
  estado: "VIGENTE",
  requiereReasignar: false,
  claveClinicaSermed: "1",
  idCentroSermed: 5,
  centroSermed: "CUAUHTÉMOC",
  idAdscripcion: 10,
  idConsultorio: 3,
  consultorio: "Consultorio 3",
  numeroConsultorio: 3,
  turno: "Matutino",
  idCentroAdscripcion: 5,
  centroAdscripcion: "CUAUHTÉMOC",
  sinMedicoActivo: false,
  citasFuturas: 0,
};

describe("presentarEstadoAdscripcion", () => {
  it("vigente: muestra el consultorio sin pedir acción", () => {
    const p = presentarEstadoAdscripcion(base);
    expect(p).toMatchObject({ variante: "stable", accion: null });
    expect(p?.etiqueta).toBe("Cons. 3 · Matutino");
  });

  it("vigente sin médico activo: avisa pero no pide reasignar", () => {
    const p = presentarEstadoAdscripcion({ ...base, sinMedicoActivo: true });
    expect(p?.accion).toBeNull();
    expect(p?.aviso).toMatch(/no tiene médico activo hoy/i);
  });

  it("sin adscripción: pide asignar", () => {
    const p = presentarEstadoAdscripcion({ ...base, estado: "SIN_ADSCRIPCION", idAdscripcion: null });
    expect(p).toMatchObject({ etiqueta: "Sin consultorio", variante: "alert", accion: "asignar" });
    expect(p?.aviso).toMatch(/^Clínica CUAUHTÉMOC\. No tiene consultorio familiar/);
  });

  it("no coincide: pide reasignar y cuenta las citas", () => {
    const p = presentarEstadoAdscripcion({ ...base, estado: "NO_COINCIDE", requiereReasignar: true, citasFuturas: 2 });
    expect(p).toMatchObject({ etiqueta: "No coincide", variante: "critical", accion: "reasignar" });
    expect(p?.aviso).toMatch(/2 citas/);
  });

  it("no coincide: dice de qué clínica a cuál lo cambiaron", () => {
    const p = presentarEstadoAdscripcion({
      ...base, estado: "NO_COINCIDE", requiereReasignar: true, idCentroSermed: 2, centroSermed: "TAXQUEÑA",
    });
    expect(p?.aviso).toMatch(/^Cambió de clínica en SERMED: CUAUHTÉMOC \(Cons\. 3 · Matutino\) → TAXQUEÑA\./);
    expect(p?.aviso).toMatch(/consultorio en TAXQUEÑA/);
  });

  it("sin nombres de clínica, los avisos no muestran huecos", () => {
    const sinNombres = { ...base, centroSermed: null, centroAdscripcion: null };
    expect(presentarEstadoAdscripcion({ ...sinNombres, estado: "SIN_ADSCRIPCION" })?.aviso)
      .toBe("No tiene consultorio familiar. Asígnele uno antes de la ficha de medicina general.");
    expect(presentarEstadoAdscripcion({ ...sinNombres, estado: "NO_COINCIDE" })?.aviso).not.toMatch(/null|undefined/);
  });

  it("consultorio inactivo: pide reasignar", () => {
    const p = presentarEstadoAdscripcion({ ...base, estado: "CONSULTORIO_INACTIVO", requiereReasignar: true });
    expect(p).toMatchObject({ variante: "alert", accion: "reasignar" });
  });

  it("clínica sin centro: avisa al administrador, sin acción de recepción", () => {
    const p = presentarEstadoAdscripcion({ ...base, estado: "CLINICA_SIN_CENTRO" });
    expect(p).toMatchObject({ etiqueta: "Clínica no registrada", accion: null });
    expect(p?.aviso).toMatch(/clínica 1 de SERMED/);
  });

  it("estados sin P-03 no muestran nada", () => {
    expect(presentarEstadoAdscripcion({ ...base, estado: "P03_INACTIVO" })).toBeNull();
    expect(presentarEstadoAdscripcion({ ...base, estado: "SIN_DATO_EXPEDIENTE" })).toBeNull();
    expect(presentarEstadoAdscripcion({ ...base, estado: "NO_VIGENTE" })).toBeNull();
    expect(presentarEstadoAdscripcion(null)).toBeNull();
    expect(presentarEstadoAdscripcion(undefined)).toBeNull();
  });
});

describe("etiquetaConsultorio", () => {
  it("usa número y turno", () => {
    expect(etiquetaConsultorio({ numero: 2, turno: "Vespertino" })).toBe("Cons. 2 · Vespertino");
  });
});

describe("conflictoConsultorioFamiliar", () => {
  it("reconoce el 409 de consultorio diferente con su detalle", () => {
    const error = new ApiError("CONSULTORIO_FAMILIAR_DIFERENTE", "Otro consultorio", 409, {
      estado: "VIGENTE",
      idConsultorioFamiliar: 3,
      idConsultorioSolicitado: 4,
    } as never);
    expect(conflictoConsultorioFamiliar(error)).toEqual({
      estado: "VIGENTE",
      idConsultorioFamiliar: 3,
      idConsultorioSolicitado: 4,
      mensaje: "Otro consultorio",
    });
  });

  it("ignora otros errores", () => {
    expect(conflictoConsultorioFamiliar(new ApiError("CITAS_MODIFICADAS", "x", 409))).toBeNull();
    expect(conflictoConsultorioFamiliar(new Error("x"))).toBeNull();
  });
});
