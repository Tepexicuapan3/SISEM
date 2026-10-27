import { describe, expect, it } from "vitest";
import type { TipoFormValue } from "@features/admin/modules/autorizadores/domain/autorizador.schemas";
import {
  alternarTipo,
  cambiarAlcance,
  unificarAlcance,
} from "@features/admin/modules/autorizadores/domain/autorizador.tipos";

const vacio = { centros: [], tiposCentro: [], global: false };

const tipos = (): TipoFormValue[] => [
  { clave: "LAB", seleccionado: true, alcance: { centros: [1, 2], tiposCentro: [], global: false } },
  { clave: "GAB", seleccionado: false, alcance: vacio },
  { clave: "REC", seleccionado: true, alcance: { centros: [], tiposCentro: ["HOSPITAL"], global: false } },
];

describe("selección de tipos de autorización", () => {
  it("al desmarcar un tipo se limpia su alcance", () => {
    const resultado = alternarTipo(tipos(), "LAB", false, { mismosCentros: false });
    expect(resultado[0]).toEqual({ clave: "LAB", seleccionado: false, alcance: vacio });
  });

  it("al marcar un tipo sin 'mismos centros' inicia vacío", () => {
    const resultado = alternarTipo(tipos(), "GAB", true, { mismosCentros: false });
    expect(resultado[1]).toEqual({ clave: "GAB", seleccionado: true, alcance: vacio });
  });

  it("al marcar un tipo con 'mismos centros' copia el alcance de los ya elegidos", () => {
    const resultado = alternarTipo(tipos(), "GAB", true, { mismosCentros: true });
    expect(resultado[1].alcance).toEqual({ centros: [1, 2], tiposCentro: [], global: false });
  });

  it("cambiar el alcance afecta solo a ese tipo", () => {
    const nuevo = { centros: [9], tiposCentro: [], global: false };
    const resultado = cambiarAlcance(tipos(), "LAB", nuevo, { mismosCentros: false });
    expect(resultado[0].alcance).toEqual(nuevo);
    expect(resultado[2].alcance.tiposCentro).toEqual(["HOSPITAL"]);
  });

  it("con 'mismos centros' el cambio se aplica a todos los tipos elegidos y no a los demás", () => {
    const nuevo = { centros: [9], tiposCentro: [], global: false };
    const resultado = cambiarAlcance(tipos(), "LAB", nuevo, { mismosCentros: true });
    expect(resultado[0].alcance).toEqual(nuevo);
    expect(resultado[2].alcance).toEqual(nuevo);
    expect(resultado[1].alcance).toEqual(vacio);
  });

  it("unificar copia el alcance del tipo de origen a todos los elegidos", () => {
    const resultado = unificarAlcance(tipos(), "REC");
    expect(resultado[0].alcance).toEqual({ centros: [], tiposCentro: ["HOSPITAL"], global: false });
    expect(resultado[1].alcance).toEqual(vacio);
  });

  it("las copias no comparten referencias (editar una no altera otra)", () => {
    const resultado = unificarAlcance(tipos(), "LAB");
    expect(resultado[2].alcance.centros).not.toBe(resultado[0].alcance.centros);
  });
});
