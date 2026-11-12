import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@/test/utils";
import { PrescriptionSummary } from "@features/consulta-medica/modules/atencion/components/PrescriptionSummary";
import { usePrescriptionItems } from "@features/consulta-medica/modules/atencion/queries/usePrescriptionItems";
import { useCancelPrescriptionItem } from "@features/consulta-medica/modules/atencion/mutations/useCancelPrescriptionItem";
import type { PrescriptionItem } from "@api/types";

vi.mock("@features/consulta-medica/modules/atencion/queries/usePrescriptionItems", () => ({
  usePrescriptionItems: vi.fn(),
}));
vi.mock("@features/consulta-medica/modules/atencion/mutations/useCancelPrescriptionItem", () => ({
  useCancelPrescriptionItem: vi.fn(),
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
  beforeEach(() => {
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
});
