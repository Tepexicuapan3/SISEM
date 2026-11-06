import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import { render, screen, waitFor, within } from "@/test/utils";
import { ConsultorioFamiliarPanel } from "@features/recepcion/modules/adscripcion/components/ConsultorioFamiliarPanel";
import { adscripcionAPI } from "@api/resources/adscripcion.api";
import { citasAPI } from "@api/resources/citas.api";
import { visitsAPI } from "@api/resources/visits.api";
import { ApiError } from "@api/utils/errors";
import type { AdscribirFamiliaResponse, FamiliaAdscripcionResponse, MiembroFamiliaAdscripcion } from "@api/types";

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const miembro = (pkNum: number, nombre: string, extra: Partial<MiembroFamiliaAdscripcion> = {}): MiembroFamiliaAdscripcion => ({
  noExp: "3498", pkNum, idPaciente: null, nombre, parentesco: pkNum === 0 ? "TRABAJADOR" : "HIJO", provisional: false,
  estado: "SIN_ADSCRIPCION", elegible: true, razon: null, preseleccionado: true,
  idAdscripcionActual: null, idConsultorioActual: null, adscripcionActual: null, citasACancelarPorConsultorio: {},
  ...extra,
});

const familia: FamiliaAdscripcionResponse = {
  noExp: "3498",
  idCentroAtencion: 1,
  miembros: [
    miembro(0, "PEREZ LOPEZ JUAN"),
    miembro(1, "PEREZ LOPEZ ANA"),
    miembro(2, "PEREZ LOPEZ SOFIA", {
      estado: "VIGENTE", preseleccionado: false, idPaciente: 70, idAdscripcionActual: 9, idConsultorioActual: 42,
      adscripcionActual: { numeroConsultorio: 5, turno: "Vespertino" } as MiembroFamiliaAdscripcion["adscripcionActual"],
      citasACancelarPorConsultorio: {
        "41": [{ idCita: 501, folio: "CIT-A", fechaHora: "2026-11-20T10:00:00-06:00", estatus: "agendada", idConsultorio: 42, consultorio: "Consultorio 5", idMedico: 8 }],
        "42": [],
      },
    }),
    miembro(3, "PEREZ LOPEZ PEDRO", { elegible: false, razon: "NO_VIGENTE", preseleccionado: false, estado: "NO_VIGENTE" }),
  ],
  opciones: [
    { consultorioId: 41, consultorio: "Consultorio 4", numero: 4, turnoId: 1, turno: "Matutino", carga: 12, capacidadMaxima: 37, esDeLaFamilia: false, sugerida: true },
    { consultorioId: 42, consultorio: "Consultorio 5", numero: 5, turnoId: 2, turno: "Vespertino", carga: 3, capacidadMaxima: null, esDeLaFamilia: true, sugerida: false },
  ],
  motivoSinOpciones: null,
  familiaSeparada: false,
};

const respuesta: AdscribirFamiliaResponse = {
  resultados: [
    { pkNum: 0, idPaciente: 80, sinCambios: false, adscripcion: { idAdscripcion: 20, idConsultorio: 41 } as AdscribirFamiliaResponse["resultados"][number]["adscripcion"], citasCanceladas: [] },
  ],
};

const renderPanel = (datos: FamiliaAdscripcionResponse = familia) => {
  vi.spyOn(adscripcionAPI, "getFamilia").mockResolvedValue(datos);
  const onAsignado = vi.fn();
  const onCerrar = vi.fn();
  render(<ConsultorioFamiliarPanel noExp="3498" onAsignado={onAsignado} onCerrar={onCerrar} />);
  return { onAsignado, onCerrar };
};

const confirmar = () => screen.getByRole("button", { name: /Asignar y continuar/ });

describe("ConsultorioFamiliarPanel", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.mocked(toast.error).mockClear();
    vi.spyOn(citasAPI, "getMotivosCancelacion").mockResolvedValue({
      results: [
        { id: 2, name: "Cancelada por el paciente" },
        { id: 9, name: "Cambio de consultorio familiar" },
      ],
    });
  });

  it("abrir no escribe nada y deja marcada a la familia sin consultorio", async () => {
    const abrir = vi.spyOn(visitsAPI, "openPatient");
    const asignar = vi.spyOn(adscripcionAPI, "adscribirFamilia");
    renderPanel();

    expect(await screen.findByRole("checkbox", { name: /JUAN/ })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: /ANA/ })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: /SOFIA/ })).not.toBeChecked();
    expect(screen.getByText(/3 de 4 sin consultorio/)).toBeInTheDocument();
    expect(confirmar()).toHaveTextContent("(2)");
    expect(abrir).not.toHaveBeenCalled();
    expect(asignar).not.toHaveBeenCalled();
  });

  it("un clic asigna a los marcados al sugerido y devuelve el resultado", async () => {
    const asignar = vi.spyOn(adscripcionAPI, "adscribirFamilia").mockResolvedValue(respuesta);
    const { onAsignado } = renderPanel();

    await screen.findByRole("checkbox", { name: /JUAN/ });
    expect(screen.getByLabelText("Consultorio para la familia")).toHaveValue("41");
    await userEvent.setup().click(confirmar());

    await waitFor(() => expect(asignar).toHaveBeenCalledTimes(1));
    expect(asignar).toHaveBeenCalledWith({
      noExp: "3498",
      asignaciones: [
        { pkNum: 0, consultorioId: 41, idAdscripcionEsperada: null, citasACancelar: [], fueSugerida: true },
        { pkNum: 1, consultorioId: 41, idAdscripcionEsperada: null, citasACancelar: [], fueSugerida: true },
      ],
      motivoCancelacionId: null,
      origen: "CHECKIN",
    });
    expect(onAsignado).toHaveBeenCalledWith(respuesta.resultados);
  });

  it("deja mandar a un miembro a otro consultorio", async () => {
    const asignar = vi.spyOn(adscripcionAPI, "adscribirFamilia").mockResolvedValue(respuesta);
    renderPanel();
    const user = userEvent.setup();

    await screen.findByRole("checkbox", { name: /ANA/ });
    await user.click(screen.getByRole("button", { name: /Cambiar consultorio de PEREZ LOPEZ ANA/ }));
    await user.selectOptions(screen.getByLabelText("Consultorio de PEREZ LOPEZ ANA"), "42");
    await user.click(confirmar());

    await waitFor(() => expect(asignar).toHaveBeenCalledTimes(1));
    expect(asignar.mock.calls[0][0].asignaciones[1]).toEqual(
      { pkNum: 1, consultorioId: 42, idAdscripcionEsperada: null, citasACancelar: [], fueSugerida: false },
    );
  });

  it("mover a quien ya tiene consultorio muestra sus citas y manda el motivo", async () => {
    const asignar = vi.spyOn(adscripcionAPI, "adscribirFamilia").mockResolvedValue(respuesta);
    renderPanel();
    const user = userEvent.setup();

    const sofia = await screen.findByRole("checkbox", { name: /SOFIA/ });
    expect(screen.getByText(/Cons\. 5 · Vespertino · márcalo para moverlo/)).toBeInTheDocument();
    await user.click(sofia);

    const aviso = await screen.findByRole("alert", { name: /citas que se cancelan/i });
    expect(within(aviso).getByText(/CIT-A/)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText("Motivo de cancelación")).toHaveValue("9"));
    await user.click(confirmar());

    await waitFor(() => expect(asignar).toHaveBeenCalledTimes(1));
    const enviado = asignar.mock.calls[0][0];
    expect(enviado.motivoCancelacionId).toBe(9);
    expect(enviado.asignaciones[2]).toEqual(
      { pkNum: 2, consultorioId: 41, idAdscripcionEsperada: 9, citasACancelar: [501], fueSugerida: true },
    );
  });

  it("el no elegible sale en gris con la razón", async () => {
    renderPanel();

    const pedro = await screen.findByRole("checkbox", { name: /PEDRO/ });
    expect(pedro).toBeDisabled();
    expect(screen.getByText(/no vigente/i)).toBeInTheDocument();
  });

  it("sin opciones explica por qué y no deja confirmar", async () => {
    renderPanel({ ...familia, opciones: [], motivoSinOpciones: "SIN_MEDICO" });

    expect(await screen.findByText(/no tienen médico activo/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Asignar y continuar/ })).not.toBeInTheDocument();
  });

  it("avisa cuando la familia quedará separada", async () => {
    renderPanel({ ...familia, familiaSeparada: true });

    expect(await screen.findByText(/quedará separada/i)).toBeInTheDocument();
  });

  it("si un miembro no entra, dice quién y no cierra", async () => {
    vi.spyOn(adscripcionAPI, "adscribirFamilia").mockRejectedValue(
      new ApiError("CONSULTORIO_LLENO", "El consultorio ya llegó a su capacidad. Elija otro.", 409, { pkNum: 1 }),
    );
    const { onAsignado } = renderPanel();

    await screen.findByRole("checkbox", { name: /ANA/ });
    await userEvent.setup().click(confirmar());

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith(
      "No se pudo asignar a PEREZ LOPEZ ANA",
      { description: "El consultorio ya llegó a su capacidad. Elija otro." },
    ));
    expect(onAsignado).not.toHaveBeenCalled();
  });
});
