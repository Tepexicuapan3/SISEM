import { useState } from "react";
import { describe, expect, it } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen } from "@/test/utils";
import { DesignacionAlcanceFields } from "@features/admin/modules/catalogos/designacion-autorizadores/components/DesignacionAlcanceFields";
import type { ScopeSelection } from "@features/admin/modules/catalogos/designacion-autorizadores/domain/designacion.scope";

const centers = [
  { id: 1, name: "Clinica Norte" },
  { id: 2, name: "Hospital Sur" },
];

function Harness({
  canGrantGlobal,
  initial,
}: {
  canGrantGlobal: boolean;
  initial?: ScopeSelection;
}) {
  const [value, setValue] = useState<ScopeSelection>(
    initial ?? { centros: [], tiposCentro: [], global: false },
  );
  return (
    <DesignacionAlcanceFields
      value={value}
      onChange={setValue}
      centers={centers}
      canGrantGlobal={canGrantGlobal}
    />
  );
}

describe("DesignacionAlcanceFields", () => {
  it("S38: sin permiso global no muestra 'Todos los centros'", () => {
    render(<Harness canGrantGlobal={false} />);

    expect(screen.queryByLabelText("Todos los centros")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Todas las clínicas")).toBeVisible();
    expect(screen.getByLabelText("Todos los hospitales")).toBeVisible();
  });

  it("con permiso global muestra 'Todos los centros'", () => {
    render(<Harness canGrantGlobal />);
    expect(screen.getByLabelText("Todos los centros")).toBeVisible();
  });

  it("explica que 'Todas las clínicas' incluye futuras y elegir una a una congela la lista", () => {
    render(<Harness canGrantGlobal />);
    expect(screen.getByText(/incluye también las que se den de alta en el futuro/i)).toBeVisible();
    expect(screen.getByText(/congela la lista/i)).toBeVisible();
  });

  it("GLOBAL es exclusivo: al marcarlo limpia tipos y deshabilita los demas", async () => {
    const user = userEvent.setup();
    render(
      <Harness
        canGrantGlobal
        initial={{ centros: [1], tiposCentro: ["CLINICA"], global: false }}
      />,
    );

    expect(screen.getByLabelText("Todas las clínicas")).toBeChecked();

    await user.click(screen.getByLabelText("Todos los centros"));

    expect(screen.getByLabelText("Todos los centros")).toBeChecked();
    expect(screen.getByLabelText("Todas las clínicas")).not.toBeChecked();
    expect(screen.getByLabelText("Todas las clínicas")).toBeDisabled();
    expect(screen.getByLabelText("Todos los hospitales")).toBeDisabled();
    expect(screen.queryByText("Clinica Norte")).not.toBeInTheDocument();
  });

  it("desmarcar GLOBAL rehabilita las demas opciones", async () => {
    const user = userEvent.setup();
    render(<Harness canGrantGlobal initial={{ centros: [], tiposCentro: [], global: true }} />);

    await user.click(screen.getByLabelText("Todos los centros"));

    expect(screen.getByLabelText("Todas las clínicas")).toBeEnabled();
  });
});
