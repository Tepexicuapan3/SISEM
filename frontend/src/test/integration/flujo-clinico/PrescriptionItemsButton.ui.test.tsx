import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen, waitFor, within } from "@/test/utils";
import { PrescriptionItemsButton } from "@features/consulta-medica/modules/atencion/components/PrescriptionItemsButton";
import { usePrescriptionItems } from "@features/consulta-medica/modules/atencion/queries/usePrescriptionItems";
import { useAddPrescriptionItem } from "@features/consulta-medica/modules/atencion/mutations/useAddPrescriptionItem";
import { useCancelPrescriptionItem } from "@features/consulta-medica/modules/atencion/mutations/useCancelPrescriptionItem";
import { medicamentosAPI } from "@api/resources/catalogos/medicamentos.api";
import type { PrescriptionItem } from "@api/types";

vi.mock("@features/consulta-medica/modules/atencion/queries/usePrescriptionItems", () => ({
  usePrescriptionItems: vi.fn(),
}));
vi.mock("@features/consulta-medica/modules/atencion/mutations/useAddPrescriptionItem", () => ({
  useAddPrescriptionItem: vi.fn(),
}));
vi.mock("@features/consulta-medica/modules/atencion/mutations/useCancelPrescriptionItem", () => ({
  useCancelPrescriptionItem: vi.fn(),
}));
vi.mock("@api/resources/catalogos/medicamentos.api", () => ({
  medicamentosAPI: { getAll: vi.fn() },
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const item = (overrides: Partial<PrescriptionItem> = {}): PrescriptionItem => ({
  id: 1,
  visitId: 7,
  prescriptionFolio: "RX-2026-1",
  medicationId: 10,
  medicationName: "Paracetamol 500mg",
  genericName: "Paracetamol",
  presentation: "Tableta",
  dose: "1 tab",
  indications: "Despues de comer",
  route: "oral",
  routeLabel: "Oral",
  frequency: "Cada 8 horas",
  duration: "5 dias",
  quantity: 10,
  status: "activo",
  dispensedQuantity: 0,
  dispensationStatus: "pendiente",
  canCancel: true,
  createdAt: "2026-11-05T10:00:00Z",
  ...overrides,
});

describe("PrescriptionItemsButton - via, frecuencia y duracion", () => {
  const mutateAsync = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    Element.prototype.scrollIntoView = vi.fn();
    vi.mocked(usePrescriptionItems).mockReturnValue({
      data: { items: [], total: 0 },
      isLoading: false,
    } as unknown as ReturnType<typeof usePrescriptionItems>);
    vi.mocked(useAddPrescriptionItem).mockReturnValue({
      mutateAsync,
      isPending: false,
    } as unknown as ReturnType<typeof useAddPrescriptionItem>);
    vi.mocked(useCancelPrescriptionItem).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useCancelPrescriptionItem>);
    vi.mocked(medicamentosAPI.getAll).mockResolvedValue({
      items: [{ id: 10, name: "Paracetamol 500mg", presentation: "Tableta", maxQuantity: null }],
    } as unknown as Awaited<ReturnType<typeof medicamentosAPI.getAll>>);
    mutateAsync.mockResolvedValue(item());
  });

  const openDialog = async () => {
    const user = userEvent.setup();
    render(<PrescriptionItemsButton visitId={7} />);
    await user.click(screen.getByRole("button", { name: /Receta \(catálogo\)/ }));
    return { user, dialog: await screen.findByRole("dialog") };
  };

  const choose = async (user: ReturnType<typeof userEvent.setup>, combobox: HTMLElement, option: string) => {
    await user.click(combobox);
    await user.click(await screen.findByRole("option", { name: option }));
  };

  it("no agrega el medicamento sin via, frecuencia y duracion", async () => {
    const { user, dialog } = await openDialog();
    const [medicationSelect] = within(dialog).getAllByRole("combobox");
    await choose(user, medicationSelect, "Paracetamol 500mg (Tableta)");
    await user.type(within(dialog).getByLabelText("Indicaciones"), "Despues de comer");

    await user.click(within(dialog).getByRole("button", { name: "Agregar" }));

    expect(await within(dialog).findByText("Selecciona la vía de administración")).toBeInTheDocument();
    expect(within(dialog).getByText("Ingresa la frecuencia")).toBeInTheDocument();
    expect(within(dialog).getByText("Ingresa la duración")).toBeInTheDocument();
    expect(mutateAsync).not.toHaveBeenCalled();
  });

  it("envia via, frecuencia y duracion al agregar", async () => {
    const { user, dialog } = await openDialog();
    const [medicationSelect, routeSelect] = within(dialog).getAllByRole("combobox");
    await choose(user, medicationSelect, "Paracetamol 500mg (Tableta)");
    await choose(user, routeSelect, "Oral");
    await user.type(within(dialog).getByLabelText("Frecuencia"), "Cada 8 horas");
    await user.type(within(dialog).getByLabelText("Duración"), "5 dias");
    await user.type(within(dialog).getByLabelText("Indicaciones"), "Despues de comer");

    await user.click(within(dialog).getByRole("button", { name: "Agregar" }));

    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledWith({
        visitId: 7,
        data: expect.objectContaining({
          medicationId: 10,
          route: "oral",
          frequency: "Cada 8 horas",
          duration: "5 dias",
          indications: "Despues de comer",
        }),
      });
    });
  });

  it("muestra via, frecuencia y duracion de los medicamentos agregados", async () => {
    vi.mocked(usePrescriptionItems).mockReturnValue({
      data: { items: [item()], total: 1 },
      isLoading: false,
    } as unknown as ReturnType<typeof usePrescriptionItems>);

    const { dialog } = await openDialog();

    expect(within(dialog).getByText(/Oral · Cada 8 horas · 5 dias/)).toBeInTheDocument();
  });

  it("los medicamentos guardados antes de este cambio se siguen mostrando", async () => {
    vi.mocked(usePrescriptionItems).mockReturnValue({
      data: { items: [item({ route: null, routeLabel: null, frequency: null, duration: null })], total: 1 },
      isLoading: false,
    } as unknown as ReturnType<typeof usePrescriptionItems>);

    const { dialog } = await openDialog();

    expect(within(dialog).getByText(/Despues de comer/)).toBeInTheDocument();
    expect(within(dialog).queryByText(/null/)).toBeNull();
  });
});
