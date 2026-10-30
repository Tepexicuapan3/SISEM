import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen, waitFor } from "@/test/utils";
import { ConflictoCheckin } from "@features/recepcion/modules/adscripcion/components/ConflictoCheckin";
import { adscripcionAPI } from "@api/resources/adscripcion.api";
import { citasAPI } from "@api/resources/citas.api";

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

vi.mock("@features/recepcion/modules/adscripcion/queries/useAdscripcionPermisos", () => ({
  useAdscripcionPermisos: () => ({ puedeLeer: true, puedeAsignar: true, puedeExcepcion: true, puedeConfigurar: false }),
}));

const conflicto = {
  estado: "NO_COINCIDE" as const,
  idConsultorioFamiliar: 3,
  idConsultorioSolicitado: 3,
  mensaje: "Este paciente tiene otro consultorio familiar.",
};

describe("ConflictoCheckin", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(citasAPI, "getMotivosCancelacion").mockResolvedValue({ results: [] });
    vi.spyOn(adscripcionAPI, "getOpciones").mockResolvedValue({ estado: "NO_COINCIDE", idCentroSermed: 7, opciones: [] });
  });

  it("reintenta el check-in con la excepción", async () => {
    const onExcepcion = vi.fn();
    render(
      <ConflictoCheckin
        conflicto={conflicto}
        idPaciente={77}
        nombre="LUIS"
        enviando={false}
        onExcepcion={onExcepcion}
        onReasignado={vi.fn()}
      />,
    );
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Motivo de la excepción"), "Médico ausente");
    await user.click(screen.getByRole("button", { name: "Atender con excepción" }));
    expect(onExcepcion).toHaveBeenCalledWith("Médico ausente");
  });

  it("abre el panel de reasignación del paciente de la cita", async () => {
    render(
      <ConflictoCheckin
        conflicto={conflicto}
        idPaciente={77}
        nombre="LUIS"
        enviando={false}
        onExcepcion={vi.fn()}
        onReasignado={vi.fn()}
      />,
    );
    await userEvent.setup().click(screen.getByRole("button", { name: "Revisar y reasignar" }));
    expect(await screen.findByRole("dialog")).toHaveTextContent("Consultorio familiar");
    await waitFor(() => expect(adscripcionAPI.getOpciones).toHaveBeenCalledWith(77, undefined));
  });
});
