import { useState } from "react";
import { describe, expect, it } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen } from "@/test/utils";
import { ParametroValueInput } from "@features/admin/modules/catalogos/parametros/components/ParametroValueInput";
import type { ParametroTipo } from "@api/types/catalogos/parameters.types";

function Harness({ valueType, initial }: { valueType: ParametroTipo; initial: string }) {
  const [value, setValue] = useState(initial);
  return (
    <>
      <ParametroValueInput id="v" valueType={valueType} value={value} onChange={setValue} ariaLabel="Valor" />
      <output data-testid="value">{value}</output>
    </>
  );
}

describe("ParametroValueInput", () => {
  it("booleano: el interruptor guarda texto canónico true/false", async () => {
    const user = userEvent.setup();
    render(<Harness valueType="BOOLEANO" initial="false" />);

    expect(screen.getByText("No")).toBeVisible();
    await user.click(screen.getByRole("switch", { name: "Valor" }));
    expect(screen.getByTestId("value")).toHaveTextContent("true");
    expect(screen.getByText("Sí")).toBeVisible();
  });

  it("entero: campo de texto con teclado numérico", async () => {
    const user = userEvent.setup();
    render(<Harness valueType="ENTERO" initial="60" />);

    const input = screen.getByRole("textbox", { name: "Valor" });
    expect(input).toHaveAttribute("inputmode", "numeric");
    await user.clear(input);
    await user.type(input, "45");
    expect(screen.getByTestId("value")).toHaveTextContent("45");
  });

  it("texto: usa área de texto", () => {
    render(<Harness valueType="TEXTO" initial="CUIDA TU PESO" />);
    expect(screen.getByRole("textbox", { name: "Valor" }).tagName).toBe("TEXTAREA");
  });
});
