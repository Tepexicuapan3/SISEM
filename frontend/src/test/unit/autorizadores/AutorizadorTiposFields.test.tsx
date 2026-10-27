import { useState } from "react";
import { describe, expect, it } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen } from "@/test/utils";
import { AutorizadorTiposFields } from "@features/admin/modules/autorizadores/components/AutorizadorTiposFields";
import type { TipoFormValue } from "@features/admin/modules/autorizadores/domain/autorizador.schemas";

const catalogo = [
  { clave: "LAB" as const, nombre: "Laboratorio" },
  { clave: "GAB" as const, nombre: "Gabinete" },
  { clave: "REC" as const, nombre: "Recetas" },
];
const centros = [
  { id: 1, name: "Clínica Norte" },
  { id: 2, name: "Hospital Sur" },
];
const vacio = { centros: [], tiposCentro: [], global: false };

function Harness({ inicial }: { inicial?: TipoFormValue[] }) {
  const [valor, setValor] = useState<TipoFormValue[]>(
    inicial ?? catalogo.map((t) => ({ clave: t.clave, seleccionado: false, alcance: vacio })),
  );
  return (
    <>
      <AutorizadorTiposFields
        value={valor}
        onChange={setValor}
        tiposCatalogo={catalogo}
        centers={centros}
        canGrantGlobal={false}
      />
      <output data-testid="estado">{JSON.stringify(valor)}</output>
    </>
  );
}

const estado = () => JSON.parse(screen.getByTestId("estado").textContent ?? "[]") as TipoFormValue[];

describe("AutorizadorTiposFields", () => {
  it("permite combinar tipos de forma independiente", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.click(screen.getByLabelText("Laboratorio"));
    await user.click(screen.getByLabelText("Recetas"));

    expect(estado().filter((t) => t.seleccionado).map((t) => t.clave)).toEqual(["LAB", "REC"]);
  });

  it("muestra los centros solo del tipo que se está editando", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    expect(screen.queryByText(/Centros donde autoriza/i)).not.toBeInTheDocument();
    await user.click(screen.getByLabelText("Gabinete"));
    expect(screen.getByText("Centros donde autoriza Gabinete")).toBeVisible();
    expect(screen.getAllByLabelText("Todas las clínicas")).toHaveLength(1);
  });

  it("asigna un tipo de centro al tipo abierto", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.click(screen.getByLabelText("Laboratorio"));
    await user.click(screen.getByLabelText("Todos los hospitales"));

    expect(estado()[0].alcance.tiposCentro).toEqual(["HOSPITAL"]);
  });

  it("con 'mismos centros' el cambio se replica en todos los tipos elegidos", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.click(screen.getByLabelText("Laboratorio"));
    await user.click(screen.getByLabelText("Recetas"));
    await user.click(screen.getByLabelText("Usar los mismos centros en todos los tipos"));
    await user.click(screen.getByLabelText("Todas las clínicas"));

    const elegidos = estado().filter((t) => t.seleccionado);
    expect(elegidos.every((t) => t.alcance.tiposCentro.includes("CLINICA"))).toBe(true);
  });

  it("sin permiso global no ofrece 'Todos los centros'", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    await user.click(screen.getByLabelText("Laboratorio"));
    expect(screen.queryByLabelText("Todos los centros")).not.toBeInTheDocument();
  });
});
