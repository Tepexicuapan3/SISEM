import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen, waitFor, within } from "@/test/utils";
import { PrescriptionSummary } from "@features/consulta-medica/modules/atencion/components/PrescriptionSummary";
import { usePrescriptionItems } from "@features/consulta-medica/modules/atencion/queries/usePrescriptionItems";
import { useCancelPrescriptionItem } from "@features/consulta-medica/modules/atencion/mutations/useCancelPrescriptionItem";
import { useUpdatePrescriptionItem } from "@features/consulta-medica/modules/atencion/mutations/useUpdatePrescriptionItem";
import type { PrescriptionItem } from "@api/types";

vi.mock("@features/consulta-medica/modules/atencion/queries/usePrescriptionItems", () => ({
  usePrescriptionItems: vi.fn(),
}));
vi.mock("@features/consulta-medica/modules/atencion/mutations/useCancelPrescriptionItem", () => ({
  useCancelPrescriptionItem: vi.fn(),
}));
vi.mock("@features/consulta-medica/modules/atencion/mutations/useUpdatePrescriptionItem", () => ({
  useUpdatePrescriptionItem: vi.fn(),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const item = (overrides: Partial<PrescriptionItem>): PrescriptionItem =>
  ({
    id: 1, visitId: 7, prescriptionFolio: "RX-2026-1", medicationId: 10, medicationName: "Paracetamol 500mg",
    genericName: "Paracetamol", presentation: "Tableta", cuadroBasico: "BASICO", isControlled: false,
    requiresAuthorization: false, dose: "1 tab", indications: "Despues de comer", route: "oral",
    routeLabel: "Oral", frequency: "Cada 8 horas", duration: "5 dias", quantity: 1, status: "activo",
    dispensedQuantity: 0, dispensationStatus: "pendiente", canCancel: true, createdAt: "2026-11-05T10:00:00Z",
    ...overrides,
  }) as PrescriptionItem;

const mockItems = (items: PrescriptionItem[]) =>
  vi.mocked(usePrescriptionItems).mockReturnValue({
    data: { items, total: items.length },
    isLoading: false,
  } as unknown as ReturnType<typeof usePrescriptionItems>);

describe("PrescriptionSummary (medicamentos dentro de la consulta)", () => {
  const updateMutateAsync = vi.fn();

  beforeEach(() => {
    Element.prototype.scrollIntoView = vi.fn();
    updateMutateAsync.mockReset().mockResolvedValue({});
    vi.mocked(useUpdatePrescriptionItem).mockReturnValue({
      mutateAsync: updateMutateAsync,
      isPending: false,
    } as unknown as ReturnType<typeof useUpdatePrescriptionItem>);
    vi.mocked(useCancelPrescriptionItem).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useCancelPrescriptionItem>);
  });

  it("sin medicamentos recuerda guardar el diagnostico antes de recetar", () => {
    mockItems([]);
    render(<PrescriptionSummary visitId={7} />);

    expect(screen.getByText("Sin medicamentos todavía.")).toBeVisible();
    expect(screen.getByText(/Guarda el diagnóstico antes de agregar medicamentos/)).toBeVisible();
  });

  it("resume cuantos medicamentos hay y cuantos piden autorizacion", () => {
    mockItems([
      item({ id: 1 }),
      item({ id: 2, medicationName: "Clonazepam 2mg", isControlled: true, requiresAuthorization: true }),
      item({ id: 3, medicationName: "Insulina glargina", cuadroBasico: "ESPECIAL", requiresAuthorization: true }),
    ]);
    render(<PrescriptionSummary visitId={7} />);

    expect(screen.getByText("3 medicamentos")).toBeVisible();
    expect(screen.getByText("2 requieren autorización")).toBeVisible();
    expect(screen.getByText("Controlado")).toBeVisible();
    expect(screen.getByText("Especial")).toBeVisible();
  });

  it("los cancelados no cuentan", () => {
    mockItems([item({ id: 1 }), item({ id: 2, status: "cancelado" })]);
    render(<PrescriptionSummary visitId={7} />);

    expect(screen.getByText("1 medicamento")).toBeVisible();
    expect(screen.queryByText(/requiere/)).toBeNull();
  });

  it("corrige las indicaciones de un renglon sin quitarlo", async () => {
    mockItems([item({ id: 4, indications: "Despues de comr" })]);
    const user = userEvent.setup();
    render(<PrescriptionSummary visitId={7} />);

    await user.click(screen.getByRole("button", { name: "Editar Paracetamol 500mg" }));
    const dialog = await screen.findByRole("dialog");
    const indications = within(dialog).getByLabelText("Indicaciones");
    await user.clear(indications);
    await user.type(indications, "Despues de comer");
    await user.click(within(dialog).getByRole("button", { name: "Guardar cambios" }));

    await waitFor(() => {
      expect(updateMutateAsync).toHaveBeenCalledWith({
        visitId: 7,
        itemId: 4,
        data: expect.objectContaining({
          indications: "Despues de comer",
          route: "oral",
          frequency: "Cada 8 horas",
          duration: "5 dias",
          quantity: 1,
        }),
      });
    });
  });

  it("lo surtido no se edita", () => {
    mockItems([item({ id: 4, canCancel: false, dispensedQuantity: 1 })]);
    render(<PrescriptionSummary visitId={7} />);

    expect(screen.getByRole("button", { name: "Editar Paracetamol 500mg" })).toBeDisabled();
  });
});
