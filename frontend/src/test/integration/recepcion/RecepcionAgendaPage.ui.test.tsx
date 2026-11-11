import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import { render, screen, within } from "@/test/utils";
import RecepcionAgendaPage from "@features/recepcion/modules/agenda/pages/RecepcionAgendaPage";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import { useRecepcionAgendaQueue } from "@features/recepcion/modules/agenda/queries/useRecepcionAgendaQueue";
import { useVisitStatusAction } from "@features/recepcion/modules/checkin/mutations/useVisitStatusAction";
import type { VisitQueueItem } from "@api/types";

vi.mock("@/domains/auth-access/hooks/usePermissionDependencies", () => ({
  usePermissionDependencies: vi.fn(),
}));

vi.mock(
  "@features/recepcion/modules/agenda/queries/useRecepcionAgendaQueue",
  () => ({
    useRecepcionAgendaQueue: vi.fn(),
  }),
);

vi.mock(
  "@features/recepcion/modules/checkin/mutations/useVisitStatusAction",
  () => ({
    useVisitStatusAction: vi.fn(),
  }),
);

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

const createVisit = (
  overrides: Partial<VisitQueueItem> = {},
): VisitQueueItem => ({
  id:            1,
  folio:         "VST-001",
  noExp:         "10001",
  pkNum:         0,
  arrivalType:   "appointment",
  serviceType:   "medicina_general",
  appointmentId: "APP-1001",
  doctorId:      12,
  notes:         "Paciente puntual",
  status:        "en_espera",
  vitals:        null,
  ...overrides,
});

describe("RecepcionAgendaPage UI", () => {
  const mutateAsync = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();

    vi.mocked(usePermissionDependencies).mockReturnValue({
      hasCapability: () => true,
    } as unknown as ReturnType<typeof usePermissionDependencies>);

    vi.mocked(useRecepcionAgendaQueue).mockReturnValue({
      data: {
        items: [
          createVisit({ id: 1, folio: "VST-001" }),
          createVisit({
            id: 2,
            folio: "VST-002",
            serviceType: "especialidad",
          }),
          createVisit({
            id: 3,
            folio: "VST-003",
            arrivalType: "walk_in",
            serviceType: "urgencias",
            appointmentId: null,
          }),
        ],
        page: 1,
        pageSize: 50,
        total: 3,
        totalPages: 1,
      },
      isLoading: false,
      isError: false,
      error: null,
      connectionStatus: "connected",
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useRecepcionAgendaQueue>);

    vi.mocked(useVisitStatusAction).mockReturnValue({
      mutateAsync,
      isPending: false,
    } as unknown as ReturnType<typeof useVisitStatusAction>);

    mutateAsync.mockResolvedValue({ id: 1, status: "en_somatometria" });
  });

  it("deshabilita carga de agenda cuando no tiene permiso de lectura", () => {
    vi.mocked(usePermissionDependencies).mockReturnValue({
      hasCapability: () => false,
    } as unknown as ReturnType<typeof usePermissionDependencies>);

    vi.mocked(useRecepcionAgendaQueue).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
      error: null,
      connectionStatus: "idle",
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useRecepcionAgendaQueue>);

    render(<RecepcionAgendaPage />);

    expect(useRecepcionAgendaQueue).toHaveBeenCalledWith({ enabled: false });
    expect(
      screen.getByText(
        "No tienes permisos completos para ver la agenda de recepción. Pide a tu administrador que te los asigne.",
      ),
    ).toBeVisible();
  });

  it("renderiza panel operativo y filtros", async () => {
    // El boton "Generar ficha de consulta" del header se eliminó (pedido
    // explicito del usuario, sin reemplazo) -- el check-in manual sigue
    // existiendo via `?focus=checkin` y desde la vista de Disponibilidad.
    const user = userEvent.setup();
    render(<RecepcionAgendaPage />);

    expect(
      screen.getByRole("heading", { name: "Citas y check-in operativo" }),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Generar ficha de consulta" }),
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole("combobox", { name: "Servicio" }));
    await user.click(screen.getByRole("option", { name: "Urgencias" }));

    expect(screen.getByText("VST-003")).toBeVisible();
    expect(screen.queryByText("VST-001")).not.toBeInTheDocument();
  });

  it("prioriza urgencias y luego con cita dentro de visitas abiertas", () => {
    render(<RecepcionAgendaPage />);

    const folios = screen
      .getAllByText(/^VST-00[1-3]$/)
      .map((folioElement) => folioElement.textContent);

    expect(folios).toEqual(["VST-003", "VST-001", "VST-002"]);
  });

  it("marca Por llegar la ficha automática que espera al paciente", () => {
    vi.mocked(useRecepcionAgendaQueue).mockReturnValue({
      data: {
        items: [
          createVisit({ id: 1, folio: "VST-AUTO", numFicha: null, llegadaPendiente: true }),
          createVisit({ id: 2, folio: "VST-SALA", numFicha: 4, llegadaPendiente: false }),
        ],
        page: 1, pageSize: 50, total: 2, totalPages: 1,
      },
      isLoading: false, isError: false, error: null, connectionStatus: "connected", refetch: vi.fn(),
    } as unknown as ReturnType<typeof useRecepcionAgendaQueue>);

    render(<RecepcionAgendaPage />);

    const automatica = screen.getByText("VST-AUTO").closest("article") as HTMLElement;
    const enSala = screen.getByText("VST-SALA").closest("article") as HTMLElement;
    expect(within(automatica).getByText("Por llegar")).toBeVisible();
    expect(within(enSala).queryByText("Por llegar")).not.toBeInTheDocument();
    expect(within(enSala).getByText("#4")).toBeVisible();
  });

  it("muestra accion No llego solo para visitas con cita", () => {
    render(<RecepcionAgendaPage />);

    const walkInCard = screen.getByText("VST-003").closest("article");
    const appointmentCard = screen.getByText("VST-001").closest("article");

    expect(walkInCard).not.toBeNull();
    expect(appointmentCard).not.toBeNull();

    expect(
      within(walkInCard as HTMLElement).queryByRole("button", {
        name: "No llego",
      }),
    ).not.toBeInTheDocument();
    expect(
      within(appointmentCard as HTMLElement).getByRole("button", {
        name: "No llego",
      }),
    ).toBeVisible();
  });

  it("ejecuta accion Llego directo desde la tarjeta, sin dialogo de confirmacion", async () => {
    // "Llego" es frecuente y reversible (a diferencia de cancelar/no-show,
    // que si piden confirmacion por ser irreversibles) -- un solo click
    // envia a somatometria, sin paso intermedio.
    const user = userEvent.setup();
    render(<RecepcionAgendaPage />);

    const visitCard = screen.getByText("VST-001").closest("article");

    expect(visitCard).not.toBeNull();

    await user.click(
      within(visitCard as HTMLElement).getByRole("button", { name: "Llego" }),
    );

    expect(
      screen.queryByRole("button", { name: "Enviar a somatometria" }),
    ).not.toBeInTheDocument();

    expect(mutateAsync).toHaveBeenCalledWith({
      visitId: 1,
      targetStatus: "en_somatometria",
    });
    expect(toast.success).toHaveBeenCalledWith(
      "Paciente enviado a somatometria.",
      { description: "Folio VST-001." },
    );
  });
});
