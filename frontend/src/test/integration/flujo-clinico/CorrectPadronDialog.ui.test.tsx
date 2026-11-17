import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen, waitFor } from "@/test/utils";
import type { PadronEnrollment, PadronOption } from "@api/types/padrones.types";
import { CorrectPadronDialog } from "@features/padrones/components/CorrectPadronDialog";
import { useCorrectPadron, usePadronOptions } from "@features/padrones/queries/usePadrones";

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("@features/padrones/queries/usePadrones", () => ({
  useCorrectPadron: vi.fn(),
  usePadronOptions: vi.fn(),
}));

// Docs/plans/padrones-correccion-y-prioridad.md: corregir = baja "Registro erróneo" + alta nueva.
const ENROLLMENT: PadronEnrollment = {
  id: 7,
  registry: "cronicos",
  noExp: "777",
  pkNum: 0,
  patientName: "JUAN PEREZ LOPEZ",
  item: { id: "E11", code: "E11", description: "DIABETES TIPO 2", restricted: false },
  center: { id: 1, name: "Clínica Centro" },
  enrolledOn: "2026-01-10",
  enrolledBy: null,
  notes: "Referido",
  source: "manual",
  status: "activo",
  program: { code: "DIABETES", name: "Diabetes mellitus" },
  lastControl: null,
  discharge: null,
};

const OPTIONS: PadronOption[] = [
  { id: "E10", code: "E10", description: "DIABETES TIPO 1", program: { code: "DIABETES", name: "Diabetes mellitus" } },
];

const mutateAsync = vi.fn();

const renderDialog = () =>
  render(<CorrectPadronDialog open onOpenChange={vi.fn()} registry="cronicos" enrollment={ENROLLMENT} />);

describe("CorrectPadronDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mutateAsync.mockResolvedValue({});
    vi.mocked(usePadronOptions).mockImplementation((_registry, search: string) => ({
      data: search.trim().length >= 2 ? { items: OPTIONS } : undefined,
      isFetching: false,
    }) as unknown as ReturnType<typeof usePadronOptions>);
    vi.mocked(useCorrectPadron).mockReturnValue({
      mutateAsync,
      isPending: false,
    } as unknown as ReturnType<typeof useCorrectPadron>);
  });

  it("muestra lo capturado y explica que la original queda en el historial", () => {
    renderDialog();
    expect(screen.getByText(/E11/)).toBeInTheDocument();
    expect(screen.getByText(/Registro erróneo/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Observaciones/)).toHaveValue("Referido");
  });

  it("pide decir qué se corrigió", async () => {
    const user = userEvent.setup();
    renderDialog();
    await user.click(screen.getByRole("button", { name: "Corregir" }));
    expect(await screen.findByText("Indica qué se corrigió")).toBeInTheDocument();
    expect(mutateAsync).not.toHaveBeenCalled();
  });

  it("manda el padecimiento nuevo y el motivo de la corrección", async () => {
    const user = userEvent.setup();
    renderDialog();
    await user.type(screen.getByPlaceholderText(/Buscar CIE-10/), "diab");
    await user.click(await screen.findByRole("option", { name: /DIABETES TIPO 1/ }));
    await user.type(screen.getByLabelText(/Qué se corrigió/), "Era tipo 1");
    await user.click(screen.getByRole("button", { name: "Corregir" }));

    await waitFor(() => expect(mutateAsync).toHaveBeenCalledWith({
      id: 7,
      data: { itemId: "E10", enrolledOn: null, notes: "Referido", detail: "Era tipo 1" },
    }));
  });
});
