import { describe, expect, it } from "vitest";
import {
  curpBirthDate,
  curpMismatches,
  curpSex,
  describeProfileSaveError,
  formatBirthDate,
  isCurpFromSermed,
  patientFullName,
} from "@features/expedientes/domain/patient-identity";

const CURP_HOMBRE_1985 = "PEGJ850315HDFRRN09";
const CURP_MUJER_2005 = "LOMA050720MDFPRNA3";

describe("patient-identity (5.1: CURP y datos de SERMED)", () => {
  it("lee la fecha de nacimiento de la CURP usando la posicion 17 para el siglo", () => {
    expect(curpBirthDate(CURP_HOMBRE_1985)).toBe("1985-03-15");
    expect(curpBirthDate(CURP_MUJER_2005)).toBe("2005-07-20");
    expect(curpBirthDate("SIN CURP")).toBeNull();
  });

  it("lee el sexo de la CURP y lo convierte a la convencion de SERMED", () => {
    // CURP: H = Hombre, M = Mujer. SIRES: M = Masculino, F = Femenino.
    expect(curpSex(CURP_HOMBRE_1985)).toBe("M");
    expect(curpSex(CURP_MUJER_2005)).toBe("F");
    expect(curpSex("no es curp")).toBeNull();
  });

  it("detecta diferencias con el sexo y la fecha del paciente", () => {
    expect(curpMismatches(CURP_HOMBRE_1985, { sex: "M", birthDate: "1985-03-15" })).toEqual({});
    const errores = curpMismatches(CURP_HOMBRE_1985, { sex: "F", birthDate: "1990-01-01" });
    expect(errores.sex).toContain("masculino");
    expect(errores.birthDate).toContain("15/03/1985");
    // Lo que no se conoce no se compara.
    expect(curpMismatches(CURP_HOMBRE_1985, { sex: null, birthDate: null })).toEqual({});
  });

  it("arma el nombre copiado de SERMED o null si no se sincronizo", () => {
    expect(
      patientFullName({ firstName: "JUAN", paternalSurname: "PEREZ", maternalSurname: "GOMEZ" }),
    ).toBe("JUAN PEREZ GOMEZ");
    expect(patientFullName({ firstName: "ANA", paternalSurname: "LOPEZ", maternalSurname: null })).toBe(
      "ANA LOPEZ",
    );
    expect(patientFullName({ firstName: null, paternalSurname: null, maternalSurname: null })).toBeNull();
  });

  it("formatea la fecha de nacimiento como dd/mm/aaaa", () => {
    expect(formatBirthDate("1985-03-15")).toBe("15/03/1985");
    expect(formatBirthDate(null)).toBeNull();
  });

  it("solo la CURP de SERMED queda bloqueada", () => {
    expect(isCurpFromSermed({ curpSource: "O" })).toBe(true);
    expect(isCurpFromSermed({ curpSource: "C" })).toBe(false);
    expect(isCurpFromSermed({ curpSource: null })).toBe(false);
  });
});

describe("describeProfileSaveError (errores del backend al guardar la ficha)", () => {
  it("CURP de SERMED: no se edita en SIRES", () => {
    const result = describeProfileSaveError({ code: "CURP_FROM_SERMED", details: {} });
    expect(result.field).toBe("curp");
    expect(result.description).toContain("Capital Humano");
  });

  it("CURP de otro expediente: dice cual", () => {
    const result = describeProfileSaveError({
      code: "CURP_ALREADY_REGISTERED",
      details: { curp: ["CURP registrada en otro paciente."], noExp: "40488", pkNum: 0 },
    });
    expect(result.field).toBe("curp");
    expect(result.fieldMessage).toContain("40488");
  });

  it("CURP que no coincide con el sexo: el error va al campo sexo con el mensaje del backend", () => {
    const result = describeProfileSaveError({
      code: "VALIDATION_ERROR",
      details: { sex: ["La CURP indica sexo 'H', pero el paciente tiene 'M'."] },
    });
    expect(result.field).toBe("sex");
    expect(result.fieldMessage).toContain("La CURP indica sexo");
  });

  it("formato invalido de CURP", () => {
    const result = describeProfileSaveError({ code: "VALIDATION_ERROR", details: { curp: ["CURP con formato invalido."] } });
    expect(result.field).toBe("curp");
    expect(result.fieldMessage).toBe("CURP con formato inválido");
  });

  it("cualquier otro error: mensaje generico sin campo", () => {
    const result = describeProfileSaveError({});
    expect(result.field).toBeUndefined();
    expect(result.title).toBe("No se pudo guardar la ficha del paciente");
  });
});
