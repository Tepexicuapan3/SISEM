import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen, within } from "@/test/utils";
import type { ProximaCitaItem } from "@api/types";
import type { MedicoListItem } from "@api/types/medicos.types";
import { ProximasCitasView } from "@features/recepcion/modules/agenda/components/ProximasCitasView";
import { useProximasCitas } from "@features/recepcion/modules/citas/queries/useProximasCitas";

vi.mock("@features/recepcion/modules/citas/queries/useProximasCitas", () => ({
  useProximasCitas: vi.fn(),
}));

const manana = new Date();
manana.setDate(manana.getDate() + 1);
manana.setHours(8, 0, 0, 0);

const buildCita = (overrides: Partial<ProximaCitaItem> = {}): ProximaCitaItem => ({
  id: 1,
  folio: "CIT-7BC615566B",
  noExp: "40488",
  pkNum: 0,
  medicoId: 1,
  medicoNombre: "Dr. Ruiz",
  consultorioId: 25,
  consultorioNombre: "#1 — Consultorio A",
  fechaHora: manana.toISOString(),
  duracionMin: 20,
  servicioTipo: "medicina_general",
  estatus: "agendada",
  motivo: "Cita de seguimiento",
  notas: "Consulta VIS-D74A21EDB331",
  createdAt: new Date().toISOString(),
  origenCanal: "RECEPCION",
  pacienteNombre: "PEREZ LOPEZ JUAN",
  esSeguimiento: true,
  ...overrides,
});

const medicos = [{ id: 1, nombreCompleto: "Dr. Ruiz" }] as MedicoListItem[];

function mockHook(items: ProximaCitaItem[], extra: Record<string, unknown> = {}) {
  vi.mocked(useProximasCitas).mockReturnValue({
    data: { items, page: 1, pageSize: 25, total: items.length, totalPages: items.length ? 1 : 0 },
    isLoading: false,
    isFetching: false,
    isError: false,
    refetch: vi.fn(),
    ...extra,
  } as unknown as ReturnType<typeof useProximasCitas>);
}

describe("ProximasCitasView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("agrupa por día y muestra paciente, hora, médico y la marca de seguimiento", () => {
    mockHook([buildCita(), buildCita({ id: 2, folio: "CIT-2", esSeguimiento: false, motivo: "Control", notas: null })]);
    render(<ProximasCitasView allMedicos={medicos} enabled />);

    const dia = screen.getByRole("region", { name: /^Mañana/ });
    expect(within(dia).getAllByText("PEREZ LOPEZ JUAN")).toHaveLength(2);
    expect(within(dia).getAllByText("08:00")).toHaveLength(2);
    expect(within(dia).getAllByText(/Exp\. 40488/)).toHaveLength(2);
    expect(within(dia).getAllByText("Seguimiento")).toHaveLength(1);
    expect(within(dia).getByText("Desde la consulta VIS-D74A21EDB331")).toBeInTheDocument();
  });

  it("pide solo seguimientos y cambia el rango", async () => {
    mockHook([]);
    const user = userEvent.setup();
    render(<ProximasCitasView allMedicos={medicos} enabled />);

    await user.click(screen.getByRole("checkbox", { name: "Solo seguimientos" }));
    expect(vi.mocked(useProximasCitas)).toHaveBeenLastCalledWith(
      expect.objectContaining({ soloSeguimiento: true, page: 1 }),
      { enabled: true },
    );

    await user.click(screen.getByRole("button", { name: "Mañana" }));
    const params = vi.mocked(useProximasCitas).mock.lastCall?.[0];
    expect(params?.fechaDesde).toBe(params?.fechaHasta);
  });

  it("sin citas lo dice", () => {
    mockHook([]);
    render(<ProximasCitasView allMedicos={medicos} enabled />);
    expect(screen.getByText(/No hay citas agendadas en este rango/i)).toBeInTheDocument();
  });

  it("si falla lo dice y permite reintentar", () => {
    mockHook([], { isError: true, data: undefined });
    render(<ProximasCitasView allMedicos={medicos} enabled />);
    expect(screen.getByText(/No se pudieron cargar las próximas citas/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeInTheDocument();
  });
});
