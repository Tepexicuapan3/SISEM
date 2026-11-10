import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen } from "@/test/utils";
import type { CitaHistorialItem } from "@api/types";
import { CitaMovimientos } from "@features/recepcion/modules/agenda/components/CitaMovimientos";
import { useCitaHistorial } from "@features/recepcion/modules/citas/queries/useCitaHistorial";

vi.mock("@features/recepcion/modules/citas/queries/useCitaHistorial", () => ({
  useCitaHistorial: vi.fn(),
}));

const items: CitaHistorialItem[] = [
  {
    id: 1, fromStatus: null, toStatus: "agendada", changedById: 5, changedByNombre: "Rosa Mora",
    changedAt: "2026-11-10T15:00:00Z", notes: "Cita agendada", canal: "RECEPCION",
  },
  {
    id: 2, fromStatus: "agendada", toStatus: "cancelada", changedById: null, changedByNombre: null,
    changedAt: "2026-11-10T16:00:00Z", notes: "Paciente lo solicitó", canal: "PORTAL",
  },
];

function mockHook(extra: Record<string, unknown> = {}) {
  vi.mocked(useCitaHistorial).mockReturnValue({
    data: items, isLoading: false, isError: false, ...extra,
  } as unknown as ReturnType<typeof useCitaHistorial>);
}

describe("CitaMovimientos", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockHook();
  });

  it("no pide el historial hasta abrirlo", () => {
    render(<CitaMovimientos citaId={9} />);

    expect(vi.mocked(useCitaHistorial)).toHaveBeenLastCalledWith(9, false);
    expect(screen.queryByText("Rosa Mora", { exact: false })).not.toBeInTheDocument();
  });

  it("muestra cada movimiento con quién lo hizo y el motivo", async () => {
    const user = userEvent.setup();
    render(<CitaMovimientos citaId={9} />);

    await user.click(screen.getByRole("button", { name: /Ver movimientos/ }));

    expect(vi.mocked(useCitaHistorial)).toHaveBeenLastCalledWith(9, true);
    expect(screen.getByText(/Rosa Mora · Recepción/)).toBeInTheDocument();
    expect(screen.getByText("Paciente lo solicitó")).toBeInTheDocument();
    // Sin usuario: el canal dice si fue el paciente (portal) o el sistema.
    expect(screen.getByText(/· Portal$/)).toBeInTheDocument();
    expect(screen.getByText("Cancelada")).toBeInTheDocument();
  });

  it("si falla lo dice", async () => {
    mockHook({ isError: true, data: undefined });
    const user = userEvent.setup();
    render(<CitaMovimientos citaId={9} />);

    await user.click(screen.getByRole("button", { name: /Ver movimientos/ }));

    expect(screen.getByText(/No se pudieron cargar los movimientos/)).toBeInTheDocument();
  });
});
