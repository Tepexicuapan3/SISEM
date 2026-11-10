import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import { render, screen, within } from "@/test/utils";
import type { SeguimientoPendienteItem } from "@api/types";
import { SeguimientosPorAgendar } from "@features/recepcion/modules/agenda/components/SeguimientosPorAgendar";
import { useSeguimientosPendientes } from "@features/recepcion/modules/citas/queries/useSeguimientosPendientes";
import { useAgendarSeguimiento } from "@features/recepcion/modules/citas/mutations/useCitaMutations";
import { useMedicosDisponibles } from "@features/admin/modules/medicos/hooks/useMedicos";
import { useSlotsMedico } from "@features/recepcion/modules/adscripcion/queries/useAdscripcionQueries";

vi.mock("@features/recepcion/modules/citas/queries/useSeguimientosPendientes", () => ({
  useSeguimientosPendientes: vi.fn(),
}));
vi.mock("@features/recepcion/modules/citas/mutations/useCitaMutations", () => ({
  useAgendarSeguimiento: vi.fn(),
}));
vi.mock("@features/admin/modules/medicos/hooks/useMedicos", () => ({
  useMedicosDisponibles: vi.fn(),
}));
vi.mock("@features/recepcion/modules/adscripcion/queries/useAdscripcionQueries", () => ({
  useSlotsMedico: vi.fn(),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const iso = (dias: number) => {
  const d = new Date();
  d.setDate(d.getDate() + dias);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

const buildItem = (overrides: Partial<SeguimientoPendienteItem> = {}): SeguimientoPendienteItem => ({
  visitId: 10, visitFolio: "VIS-D74A", idPaciente: 55, noExp: "40488", pkNum: 0,
  fechaSeguimiento: iso(7), fechaConsulta: iso(-1), medicoUsuarioId: 3, medicoNombre: "Dra. Ruiz",
  centroId: 1, serviceType: "medicina_general", pacienteNombre: "PEREZ LOPEZ JUAN", vencido: false,
  ...overrides,
});

function mockLista(items: SeguimientoPendienteItem[], extra: Record<string, unknown> = {}) {
  vi.mocked(useSeguimientosPendientes).mockReturnValue({
    data: { items, page: 1, pageSize: 25, total: items.length, totalPages: items.length ? 1 : 0 },
    isLoading: false, isError: false, refetch: vi.fn(), ...extra,
  } as unknown as ReturnType<typeof useSeguimientosPendientes>);
}

describe("SeguimientosPorAgendar", () => {
  const mutateAsync = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useAgendarSeguimiento).mockReturnValue({
      mutateAsync, isPending: false,
    } as unknown as ReturnType<typeof useAgendarSeguimiento>);
    vi.mocked(useMedicosDisponibles).mockReturnValue({
      data: { fecha: iso(7), centroId: 1, medicos: [
        { medicoId: 9, usuarioId: 3, nombreCompleto: "Dra. Ruiz", disponible: true, consultorioId: 25 },
      ] },
      isFetching: false,
    } as unknown as ReturnType<typeof useMedicosDisponibles>);
    vi.mocked(useSlotsMedico).mockReturnValue({
      data: { slots: [{ hora: "08:00" }] }, isFetching: false,
    } as unknown as ReturnType<typeof useSlotsMedico>);
    mutateAsync.mockResolvedValue({ folio: "CIT-NUEVA" });
  });

  it("lista los seguimientos con paciente, fecha, quién lo indicó y los vencidos", () => {
    mockLista([buildItem(), buildItem({ visitId: 11, visitFolio: "VIS-OLD", fechaSeguimiento: iso(-2), vencido: true })]);
    render(<SeguimientosPorAgendar enabled />);

    expect(screen.getAllByText("PEREZ LOPEZ JUAN")).toHaveLength(2);
    expect(screen.getAllByText(/Indicó: Dra\. Ruiz/)).toHaveLength(2);
    const vencido = screen.getByText(/VIS-OLD/).closest("li") as HTMLElement;
    expect(within(vencido).getByText("Atrasado")).toBeInTheDocument();
  });

  it("sin pendientes lo dice", () => {
    mockLista([]);
    render(<SeguimientosPorAgendar enabled />);
    expect(screen.getByText(/No hay seguimientos por agendar/)).toBeInTheDocument();
  });

  it("agenda la cita de seguimiento enlazada a su consulta", async () => {
    mockLista([buildItem()]);
    const user = userEvent.setup();
    render(<SeguimientosPorAgendar enabled />);

    await user.click(screen.getByRole("button", { name: "Agendar" }));
    await user.click(screen.getByRole("radio", { name: "Dra. Ruiz" }));
    await user.click(screen.getByRole("radio", { name: "08:00" }));
    await user.click(screen.getByRole("button", { name: "Agendar cita" }));

    expect(mutateAsync).toHaveBeenCalledWith({
      idPaciente: 55, noExp: "40488", pkNum: 0, medicoId: 9, consultorioId: 25,
      fechaHora: `${iso(7)}T08:00`, servicioTipo: "medicina_general",
      // El backend arma el motivo y las notas que la enlazan a la consulta.
      seguimientoVisitId: 10,
    });
    expect(toast.success).toHaveBeenCalled();
  });
});
