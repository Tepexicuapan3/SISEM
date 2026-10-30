import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen, waitFor } from "@/test/utils";
import { ReasignarAdscripcionDialog } from "@features/recepcion/modules/adscripcion/components/ReasignarAdscripcionDialog";
import { adscripcionAPI } from "@api/resources/adscripcion.api";
import { citasAPI } from "@api/resources/citas.api";
import { visitsAPI } from "@api/resources/visits.api";
import { ApiError } from "@api/utils/errors";
import type {
  AdscribirResponse,
  OpcionesAdscripcionResponse,
  PatientMember,
  PrevisualizarAdscripcionResponse,
} from "@api/types";

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

// Radix Select no es operable en happy-dom: se reemplaza por un <select> nativo.
vi.mock("@shared/ui/select", () => ({
  Select: ({
    value,
    onValueChange,
    children,
  }: {
    value: string;
    onValueChange: (value: string) => void;
    children: React.ReactNode;
  }) => (
    <select aria-label="Motivo de cancelación" value={value} onChange={(e) => onValueChange(e.target.value)}>
      <option value="">Selecciona</option>
      {children}
    </select>
  ),
  SelectTrigger: () => null,
  SelectValue: () => null,
  SelectContent: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  SelectItem: ({ value, children }: { value: string; children: React.ReactNode }) => (
    <option value={value}>{children}</option>
  ),
}));

const miembro: PatientMember = {
  noExp: "104523",
  pkNum: 2,
  idPaciente: 77,
  nombre: "HERNANDEZ RAMIREZ LUIS",
  edad: 12,
  fechaNac: null,
  parentesco: "HIJO",
  estatus: "ACTIVO",
  cdClinica: "7",
  foto: null,
  adscripcion: null,
};

const opciones: OpcionesAdscripcionResponse = {
  estado: "NO_COINCIDE",
  idCentroSermed: 7,
  opciones: [
    { consultorioId: 41, consultorio: "Consultorio 4", numero: 4, turnoId: 1, turno: "Matutino", carga: 3, capacidadMaxima: null, esDeLaFamilia: true, sugerida: true },
    { consultorioId: 42, consultorio: "Consultorio 5", numero: 5, turnoId: 2, turno: "Vespertino", carga: 0, capacidadMaxima: 100, esDeLaFamilia: false, sugerida: false },
  ],
};

const vistaSinCitas: PrevisualizarAdscripcionResponse = {
  estado: "SIN_ADSCRIPCION", sinCambios: false, idAdscripcionActual: null, adscripcionActual: null, citasACancelar: [],
};

const vistaConCitas: PrevisualizarAdscripcionResponse = {
  estado: "NO_COINCIDE",
  sinCambios: false,
  idAdscripcionActual: 9,
  adscripcionActual: null,
  citasACancelar: [
    { idCita: 501, folio: "CIT-A", fechaHora: "2026-11-04T10:20:00-06:00", estatus: "agendada", idConsultorio: 2, consultorio: "Consultorio 2", idMedico: 8 },
  ],
};

const respuesta = { sinCambios: false, adscripcion: { idAdscripcion: 10 }, citasCanceladas: [], citasPorReagendar: [] } as unknown as AdscribirResponse;

const renderDialog = (member: PatientMember = miembro) => {
  const onAdscrito = vi.fn();
  const onOpenChange = vi.fn();
  render(<ReasignarAdscripcionDialog open member={member} onOpenChange={onOpenChange} onAdscrito={onAdscrito} />);
  return { onAdscrito, onOpenChange };
};

describe("ReasignarAdscripcionDialog", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(adscripcionAPI, "getOpciones").mockResolvedValue(opciones);
    vi.spyOn(citasAPI, "getMotivosCancelacion").mockResolvedValue({
      results: [
        { id: 2, name: "Cancelada por el paciente" },
        { id: 9, name: "Cambio de consultorio familiar" },
      ],
    });
  });

  it("preselecciona la sugerida y confirma sin citas", async () => {
    vi.spyOn(adscripcionAPI, "previsualizar").mockResolvedValue(vistaSinCitas);
    const adscribir = vi.spyOn(adscripcionAPI, "adscribir").mockResolvedValue(respuesta);
    const { onAdscrito, onOpenChange } = renderDialog();

    expect(await screen.findByText("Su familia")).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /Cons\. 4/ })).toBeChecked();
    await waitFor(() => expect(adscripcionAPI.previsualizar).toHaveBeenCalledWith({ idPaciente: 77, consultorioId: 41 }));

    await userEvent.setup().click(screen.getByRole("button", { name: "Confirmar consultorio" }));

    await waitFor(() => expect(adscribir).toHaveBeenCalledTimes(1));
    expect(adscribir).toHaveBeenCalledWith({
      idPaciente: 77,
      consultorioId: 41,
      idAdscripcionEsperada: null,
      citasACancelar: [],
      motivoCancelacionId: null,
      origen: "CHECKIN",
      fueSugerida: true,
    });
    expect(onAdscrito).toHaveBeenCalledWith(respuesta.adscripcion);
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("muestra las citas a cancelar con el motivo precargado y las envía", async () => {
    vi.spyOn(adscripcionAPI, "previsualizar").mockResolvedValue(vistaConCitas);
    const adscribir = vi.spyOn(adscripcionAPI, "adscribir").mockResolvedValue(respuesta);
    renderDialog();

    expect(await screen.findByText(/Se cancelarán 1 cita/)).toBeInTheDocument();
    expect(screen.getByText(/CIT-A/)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText("Motivo de cancelación")).toHaveValue("9"));

    await userEvent.setup().click(screen.getByRole("button", { name: "Confirmar consultorio" }));

    await waitFor(() => expect(adscribir).toHaveBeenCalledTimes(1));
    expect(adscribir).toHaveBeenCalledWith(
      expect.objectContaining({ idAdscripcionEsperada: 9, citasACancelar: [501], motivoCancelacionId: 9 }),
    );
  });

  it("si elige otro consultorio no lo marca como sugerido", async () => {
    vi.spyOn(adscripcionAPI, "previsualizar").mockResolvedValue(vistaSinCitas);
    const adscribir = vi.spyOn(adscripcionAPI, "adscribir").mockResolvedValue(respuesta);
    renderDialog();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("radio", { name: /Cons\. 5/ }));
    await waitFor(() => expect(adscripcionAPI.previsualizar).toHaveBeenLastCalledWith({ idPaciente: 77, consultorioId: 42 }));
    await user.click(screen.getByRole("button", { name: "Confirmar consultorio" }));

    await waitFor(() => expect(adscribir).toHaveBeenCalledWith(expect.objectContaining({ consultorioId: 42, fueSugerida: false })));
  });

  it("si las citas cambiaron vuelve a previsualizar y no cierra", async () => {
    const previsualizar = vi.spyOn(adscripcionAPI, "previsualizar").mockResolvedValue(vistaSinCitas);
    vi.spyOn(adscripcionAPI, "adscribir").mockRejectedValue(
      new ApiError("CITAS_MODIFICADAS", "Las citas del paciente cambiaron.", 409),
    );
    const { onOpenChange } = renderDialog();

    await waitFor(() => expect(previsualizar).toHaveBeenCalledTimes(1));
    await userEvent.setup().click(screen.getByRole("button", { name: "Confirmar consultorio" }));

    await waitFor(() => expect(previsualizar).toHaveBeenCalledTimes(2));
    expect(onOpenChange).not.toHaveBeenCalledWith(false);
  });

  it("abre el registro del paciente que nunca se atendió", async () => {
    const abrir = vi.spyOn(visitsAPI, "openPatient").mockResolvedValue({ idPaciente: 88 } as never);
    vi.spyOn(adscripcionAPI, "previsualizar").mockResolvedValue(vistaSinCitas);
    renderDialog({ ...miembro, idPaciente: null });

    await waitFor(() => expect(abrir).toHaveBeenCalledWith("104523", 2));
    await waitFor(() => expect(adscripcionAPI.getOpciones).toHaveBeenCalledWith(88, undefined));
  });
});
