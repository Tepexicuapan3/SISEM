import { describe, expect, it } from "vitest";

import type { FamiliaAdscripcionResponse, MiembroFamiliaAdscripcion } from "@api/types";
import {
  armarAsignaciones,
  centroDeLaClinica,
  citasDelPlan,
  consultorioSugerido,
  eleccionInicial,
  textoRazon,
  textoSinOpciones,
} from "@features/recepcion/modules/adscripcion/domain/familiaAdscripcion";

const cita = (idCita: number) => ({
  idCita, folio: `CIT-${idCita}`, fechaHora: "2026-11-20T10:00:00-06:00", estatus: "agendada",
  idConsultorio: 42, consultorio: "Consultorio 5", idMedico: 8,
});

const miembro = (pkNum: number, extra: Partial<MiembroFamiliaAdscripcion> = {}): MiembroFamiliaAdscripcion => ({
  noExp: "3498", pkNum, idPaciente: null, nombre: `MIEMBRO ${pkNum}`, parentesco: null, provisional: false,
  estado: "SIN_ADSCRIPCION", elegible: true, razon: null, preseleccionado: true,
  idAdscripcionActual: null, idConsultorioActual: null, adscripcionActual: null, citasACancelarPorConsultorio: {},
  ...extra,
});

const familia: FamiliaAdscripcionResponse = {
  noExp: "3498",
  idCentroAtencion: 1,
  miembros: [
    miembro(0),
    miembro(1, {
      estado: "VIGENTE", preseleccionado: false, idPaciente: 70, idAdscripcionActual: 9, idConsultorioActual: 42,
      citasACancelarPorConsultorio: { "41": [cita(501)], "42": [] },
    }),
    miembro(2, { elegible: false, razon: "NO_VIGENTE", preseleccionado: false, estado: "NO_VIGENTE" }),
  ],
  opciones: [
    { consultorioId: 41, consultorio: "Consultorio 4", numero: 4, turnoId: 1, turno: "Matutino", carga: 3, capacidadMaxima: null, esDeLaFamilia: false, sugerida: true },
    { consultorioId: 42, consultorio: "Consultorio 5", numero: 5, turnoId: 2, turno: "Vespertino", carga: 9, capacidadMaxima: 10, esDeLaFamilia: true, sugerida: false },
  ],
  motivoSinOpciones: null,
  familiaSeparada: false,
};

describe("eleccionInicial", () => {
  it("marca solo a los elegibles preseleccionados, todos con el consultorio de la familia", () => {
    expect(eleccionInicial(familia)).toEqual({
      0: { marcado: true, consultorioId: null },
      1: { marcado: false, consultorioId: null },
      2: { marcado: false, consultorioId: null },
    });
  });
});

describe("consultorioSugerido", () => {
  it("es la opción sugerida, o null sin opciones", () => {
    expect(consultorioSugerido(familia)).toBe(41);
    expect(consultorioSugerido({ ...familia, opciones: [] })).toBeNull();
  });
});

describe("armarAsignaciones", () => {
  it("manda a los marcados al consultorio de la familia como sugerido", () => {
    expect(armarAsignaciones(familia, eleccionInicial(familia), 41)).toEqual([
      { pkNum: 0, consultorioId: 41, idAdscripcionEsperada: null, citasACancelar: [], fueSugerida: true },
    ]);
  });

  it("al mover a quien ya tenía consultorio manda su adscripción y sus citas", () => {
    const eleccion = { ...eleccionInicial(familia), 1: { marcado: true, consultorioId: null } };

    expect(armarAsignaciones(familia, eleccion, 41)[1]).toEqual({
      pkNum: 1, consultorioId: 41, idAdscripcionEsperada: 9, citasACancelar: [501], fueSugerida: true,
    });
  });

  it("un miembro con otro consultorio no va como sugerido", () => {
    const eleccion = { ...eleccionInicial(familia), 0: { marcado: true, consultorioId: 42 } };

    expect(armarAsignaciones(familia, eleccion, 41)[0]).toMatchObject({ consultorioId: 42, fueSugerida: false });
  });

  it("nunca manda a un miembro no elegible aunque llegue marcado", () => {
    const eleccion = { ...eleccionInicial(familia), 2: { marcado: true, consultorioId: null } };

    expect(armarAsignaciones(familia, eleccion, 41).map((a) => a.pkNum)).toEqual([0]);
  });
});

describe("citasDelPlan", () => {
  it("junta las citas que se cancelan con el consultorio elegido de cada uno", () => {
    const eleccion = { ...eleccionInicial(familia), 1: { marcado: true, consultorioId: null } };

    expect(citasDelPlan(familia, eleccion, 41)).toEqual([{ nombre: "MIEMBRO 1", cita: cita(501) }]);
    expect(citasDelPlan(familia, eleccion, 42)).toEqual([]);
  });
});

describe("textos", () => {
  it("explica por qué no se puede asignar y por qué no hay opciones", () => {
    expect(textoRazon("OTRA_CLINICA")).toMatch(/otra clínica/i);
    expect(textoRazon("NO_VIGENTE")).toMatch(/no vigente/i);
    expect(textoSinOpciones("SIN_MEDICO")).toMatch(/médico activo/i);
    expect(textoSinOpciones("TODOS_LLENOS")).toMatch(/llenos/i);
    expect(textoSinOpciones("SIN_CONSULTORIOS")).toMatch(/consultorios familiares/i);
  });
});

describe("centroDeLaClinica", () => {
  const centros = [{ id: 1, name: "CUAUHTÉMOC" }, { id: 7, name: "ZARAGOZA" }];

  it("usa el centro que resolvió la equivalencia de P-03", () => {
    // La clave SERMED "1" coincide con el id de CUAUHTÉMOC, pero la equivalencia dice ZARAGOZA.
    const paciente = { cdClinica: "1", adscripcion: { idCentroSermed: 7 } };

    expect(centroDeLaClinica(paciente, centros)?.name).toBe("ZARAGOZA");
  });

  it("sin equivalencia compara la clave con el id del centro", () => {
    expect(centroDeLaClinica({ cdClinica: "1", adscripcion: null }, centros)?.name).toBe("CUAUHTÉMOC");
    expect(centroDeLaClinica({ cdClinica: "99", adscripcion: null }, centros)).toBeUndefined();
    expect(centroDeLaClinica({ cdClinica: null, adscripcion: null }, centros)).toBeUndefined();
  });
});
