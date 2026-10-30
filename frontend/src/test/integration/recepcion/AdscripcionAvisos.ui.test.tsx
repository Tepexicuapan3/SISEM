import { describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen } from "@/test/utils";
import { AdscripcionAviso, AdscripcionBadge } from "@features/recepcion/modules/adscripcion/components/AdscripcionAviso";
import { ConflictoConsultorioAviso } from "@features/recepcion/modules/adscripcion/components/ConflictoConsultorioAviso";
import type { AdscripcionResumen } from "@api/types";

const resumen = (cambios: Partial<AdscripcionResumen>): AdscripcionResumen => ({
  estado: "VIGENTE",
  requiereReasignar: false,
  idCentroSermed: 5,
  idAdscripcion: 10,
  idConsultorio: 3,
  consultorio: "Consultorio 3",
  numeroConsultorio: 3,
  turno: "Matutino",
  idCentroAdscripcion: 5,
  sinMedicoActivo: false,
  citasFuturas: 0,
  ...cambios,
});

describe("AdscripcionBadge", () => {
  it("muestra el consultorio cuando está vigente", () => {
    render(<AdscripcionBadge resumen={resumen({})} />);
    expect(screen.getByText("Cons. 3 · Matutino")).toBeInTheDocument();
  });

  it("no muestra nada si P-03 no aplica", () => {
    const { container } = render(<AdscripcionBadge resumen={resumen({ estado: "P03_INACTIVO" })} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("AdscripcionAviso", () => {
  it("vigente sin novedades: no muestra aviso", () => {
    const { container } = render(<AdscripcionAviso resumen={resumen({})} puedeAsignar onAccion={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("no coincide: avisa y ofrece reasignar", async () => {
    const onAccion = vi.fn();
    render(
      <AdscripcionAviso
        resumen={resumen({ estado: "NO_COINCIDE", requiereReasignar: true, citasFuturas: 2 })}
        puedeAsignar
        onAccion={onAccion}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(/se cancelarán 2 citas futuras/);
    await userEvent.setup().click(screen.getByRole("button", { name: "Revisar y reasignar" }));
    expect(onAccion).toHaveBeenCalledTimes(1);
  });

  it("sin adscripción: ofrece asignar", () => {
    render(<AdscripcionAviso resumen={resumen({ estado: "SIN_ADSCRIPCION" })} puedeAsignar onAccion={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Asignar consultorio" })).toBeInTheDocument();
  });

  it("sin permiso: avisa pero no ofrece la acción", () => {
    render(<AdscripcionAviso resumen={resumen({ estado: "SIN_ADSCRIPCION" })} puedeAsignar={false} onAccion={vi.fn()} />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});

describe("ConflictoConsultorioAviso", () => {
  const conflicto = {
    estado: "VIGENTE" as const,
    idConsultorioFamiliar: 3,
    idConsultorioSolicitado: 4,
    mensaje: "Este paciente tiene otro consultorio familiar.",
  };

  it("ofrece reasignar o atender con excepción y exige el motivo", async () => {
    const onReasignar = vi.fn();
    const onExcepcion = vi.fn();
    render(
      <ConflictoConsultorioAviso
        conflicto={conflicto}
        puedeReasignar
        puedeExcepcion
        enviando={false}
        onReasignar={onReasignar}
        onExcepcion={onExcepcion}
      />,
    );
    const user = userEvent.setup();
    expect(screen.getByRole("alert")).toHaveTextContent("Este paciente tiene otro consultorio familiar.");

    const atender = screen.getByRole("button", { name: "Atender con excepción" });
    expect(atender).toBeDisabled();
    await user.type(screen.getByLabelText("Motivo de la excepción"), "  Médico ausente  ");
    await user.click(atender);
    expect(onExcepcion).toHaveBeenCalledWith("Médico ausente");

    await user.click(screen.getByRole("button", { name: "Revisar y reasignar" }));
    expect(onReasignar).toHaveBeenCalledTimes(1);
  });

  it("sin permiso de excepción no ofrece atender", () => {
    render(
      <ConflictoConsultorioAviso
        conflicto={conflicto}
        puedeReasignar
        puedeExcepcion={false}
        enviando={false}
        onReasignar={vi.fn()}
        onExcepcion={vi.fn()}
      />,
    );
    expect(screen.queryByRole("button", { name: "Atender con excepción" })).not.toBeInTheDocument();
  });
});
