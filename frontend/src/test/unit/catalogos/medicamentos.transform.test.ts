import { describe, expect, it } from "vitest";
import { medicamentoDetailsSchema } from "@features/admin/modules/catalogos/medicamentos/domain/medicamentos.schemas";
import {
  buildCreateMedicamentoPayload,
  buildUpdateMedicamentoPayload,
  mapMedicamentoDetailToFormValues,
} from "@features/admin/modules/catalogos/medicamentos/utils/medicamentos.transform";
import type { MedicamentoDetail } from "@api/types";

const VALUES = {
  name: " PARACETAMOL 500 MG ",
  code: "",
  genericName: "PARACETAMOL",
  presentation: "",
  cuadroBasico: "BASICO" as const,
  isControlled: false,
  maxQuantity: "2",
};

describe("medicamentos: esquema", () => {
  it("acepta un medicamento sin clave ni tope", () => {
    expect(
      medicamentoDetailsSchema.safeParse({ ...VALUES, maxQuantity: "" }).success,
    ).toBe(true);
  });

  it("exige nombre", () => {
    expect(medicamentoDetailsSchema.safeParse({ ...VALUES, name: " " }).success).toBe(false);
  });

  it.each(["0", "-1", "2.5", "dos"])("rechaza un tope de cajas invalido: %s", (value) => {
    expect(
      medicamentoDetailsSchema.safeParse({ ...VALUES, maxQuantity: value }).success,
    ).toBe(false);
  });
});

describe("medicamentos: payloads", () => {
  it("el alta manda null en los opcionales vacios y el tope como numero", () => {
    expect(buildCreateMedicamentoPayload(VALUES)).toEqual({
      name: "PARACETAMOL 500 MG",
      code: null,
      genericName: "PARACETAMOL",
      presentation: null,
      cuadroBasico: "BASICO",
      isControlled: false,
      maxQuantity: 2,
    });
  });

  it("la edicion solo manda lo que cambio", () => {
    expect(
      buildUpdateMedicamentoPayload(
        { ...VALUES, code: "010.000.0104.00", maxQuantity: "" },
        { code: true, maxQuantity: true },
      ),
    ).toEqual({ code: "010.000.0104.00", maxQuantity: null });
  });

  it("el detalle se pasa al formulario sin nulls", () => {
    const detail = {
      id: 1,
      name: "X",
      code: null,
      genericName: null,
      presentation: null,
      cuadroBasico: "ESPECIAL",
      isControlled: true,
      maxQuantity: null,
      isActive: true,
    } as MedicamentoDetail;
    expect(mapMedicamentoDetailToFormValues(detail)).toEqual({
      name: "X",
      code: "",
      genericName: "",
      presentation: "",
      cuadroBasico: "ESPECIAL",
      isControlled: true,
      maxQuantity: "",
    });
  });
});
