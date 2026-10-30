import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen, waitFor, within } from "@/test/utils";
import { CitasPorReagendarCard } from "@features/recepcion/modules/adscripcion/components/CitasPorReagendarCard";
import { adscripcionAPI } from "@api/resources/adscripcion.api";
import { citasAPI } from "@api/resources/citas.api";
import { medicosAPI } from "@api/resources/medicos.api";
import type { CitaAfectada, CitaListItem } from "@api/types";

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const afectada: CitaAfectada = {
  idCitaAfectada: 31,
  idAdscripcion: 12,
  idPaciente: 77,
  idConsultorioNuevo: 42,
  consultorioNuevo: "Consultorio 5",
  idCentroAtencion: 7,
  estatus: "PENDIENTE",
  citaCancelada: {
    idCita: 501, folio: "CIT-A", fechaHora: "2026-11-04T10:20:00-06:00", estatus: "cancelada",
    idConsultorio: 2, consultorio: "Consultorio 2", idMedico: 8,
  },
  idCitaNueva: null,
  motivoDescarte: null,
  fechaCreacion: "2026-10-29T12:00:00-06:00",
};

describe("CitasPorReagendarCard", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(adscripcionAPI, "getCitasPorReagendar").mockResolvedValue({ items: [afectada] });
  });

  it("no muestra nada si no hay pendientes", async () => {
    vi.spyOn(adscripcionAPI, "getCitasPorReagendar").mockResolvedValue({ items: [] });
    const { container } = render(<CitasPorReagendarCard puedeEscribir />);
    await waitFor(() => expect(adscripcionAPI.getCitasPorReagendar).toHaveBeenCalledWith({}));
    expect(container).toBeEmptyDOMElement();
  });

  it("lista las pendientes con el consultorio nuevo", async () => {
    render(<CitasPorReagendarCard puedeEscribir />);
    expect(await screen.findByText(/Citas por reagendar \(1\)/)).toBeInTheDocument();
    expect(screen.getByText(/CIT-A/)).toBeInTheDocument();
    expect(screen.getByText(/Consultorio 5/)).toBeInTheDocument();
  });

  it("descartar exige el motivo", async () => {
    const descartar = vi.spyOn(adscripcionAPI, "descartarCitaAfectada").mockResolvedValue({ ...afectada, estatus: "DESCARTADA" });
    render(<CitasPorReagendarCard puedeEscribir />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Descartar" }));

    const confirmar = screen.getByRole("button", { name: "Confirmar descarte" });
    expect(confirmar).toBeDisabled();
    await user.type(screen.getByLabelText("Motivo del descarte"), "Ya no la necesita");
    await user.click(confirmar);
    await waitFor(() => expect(descartar).toHaveBeenCalledWith(31, "Ya no la necesita"));
  });

  it("reagenda con un médico del consultorio nuevo", async () => {
    vi.spyOn(medicosAPI, "getDisponibles").mockResolvedValue({
      medicos: [
        { medicoId: 5, usuarioId: 50, nombreCompleto: "Dra. Nueva", servicio: null, tipoMedico: "BASE", disponible: true, consultorioId: 42 },
        { medicoId: 6, usuarioId: 60, nombreCompleto: "Dr. Otro", servicio: null, tipoMedico: "BASE", disponible: true, consultorioId: 99 },
      ],
    } as never);
    vi.spyOn(citasAPI, "getSlots").mockResolvedValue({
      slots: [{ fecha: "2026-11-05", hora: "09:00", duracionMin: 20, consultorioId: 42 }],
    });
    const crear = vi.spyOn(citasAPI, "create").mockResolvedValue({ id: 900 } as CitaListItem);
    render(<CitasPorReagendarCard puedeEscribir />);
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Reagendar" }));
    const dialogo = await screen.findByRole("dialog");
    expect(within(dialogo).queryByText("Dr. Otro")).not.toBeInTheDocument();
    await user.click(await within(dialogo).findByRole("radio", { name: /Dra\. Nueva/ }));
    await user.click(await within(dialogo).findByRole("radio", { name: "09:00" }));
    await user.click(within(dialogo).getByRole("button", { name: "Reagendar cita" }));

    await waitFor(() => expect(crear).toHaveBeenCalledTimes(1));
    expect(crear).toHaveBeenCalledWith(
      expect.objectContaining({
        idPaciente: 77,
        medicoId: 5,
        consultorioId: 42,
        servicioTipo: "medicina_general",
        idCitaAfectada: 31,
        fechaHora: expect.stringMatching(/T09:00$/),
      }),
    );
  });

  it("sin permiso de escritura no ofrece acciones", async () => {
    render(<CitasPorReagendarCard puedeEscribir={false} />);
    expect(await screen.findByText(/CIT-A/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reagendar" })).not.toBeInTheDocument();
  });
});
