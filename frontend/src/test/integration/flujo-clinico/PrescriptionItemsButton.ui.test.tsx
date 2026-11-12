import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen, waitFor, within } from "@/test/utils";
import { PrescriptionItemsButton } from "@features/consulta-medica/modules/atencion/components/PrescriptionItemsButton";
import { usePrescriptionItems } from "@features/consulta-medica/modules/atencion/queries/usePrescriptionItems";
import { useAddPrescriptionItem } from "@features/consulta-medica/modules/atencion/mutations/useAddPrescriptionItem";
import { useCancelPrescriptionItem } from "@features/consulta-medica/modules/atencion/mutations/useCancelPrescriptionItem";
import { medicamentosAPI } from "@api/resources/catalogos/medicamentos.api";
import type { PrescriptionItem } from "@api/types";

vi.mock("@shared/hooks/useDebounce", () => ({
  useDebounce: (value: string) => value,
}));
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

const prescriptionItem = (overrides: Partial<PrescriptionItem> = {}): PrescriptionItem => ({
  id: 1,
  visitId: 7,
  prescriptionFolio: "RX-2026-1",
  medicationId: 10,
  medicationName: "Paracetamol 500mg",
  genericName: "Paracetamol",
  presentation: "Tableta",
  cuadroBasico: "BASICO",
  isControlled: false,
  requiresAuthorization: false,
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

const PARACETAMOL = {
  id: 10,
  code: null,
  name: "Paracetamol 500mg",
  genericName: "Paracetamol",
  presentation: "Tableta",
  cuadroBasico: "BASICO",
  isControlled: false,
  maxQuantity: 2,
  isActive: true,
};

describe("PrescriptionItemsButton", () => {
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
      items: [PARACETAMOL, { ...PARACETAMOL, id: 11, name: "Clonazepam 2mg", genericName: "Clonazepam", isControlled: true }],
    } as unknown as Awaited<ReturnType<typeof medicamentosAPI.getAll>>);
    mutateAsync.mockResolvedValue(prescriptionItem());
  });

  const openDialog = async () => {
    const user = userEvent.setup();
    render(<PrescriptionItemsButton visitId={7} />);
    await user.click(screen.getByRole("button", { name: /Agregar medicamento/ }));
    return { user, dialog: await screen.findByRole("dialog") };
  };

  const pickMedication = async (user: ReturnType<typeof userEvent.setup>, dialog: HTMLElement, name: RegExp) => {
    await user.type(within(dialog).getByLabelText("Buscar medicamento"), "par");
    await user.click(await within(dialog).findByRole("button", { name }));
  };

  it("busca el medicamento en el servidor por nombre, generico o clave", async () => {
    const { user, dialog } = await openDialog();

    await user.type(within(dialog).getByLabelText("Buscar medicamento"), "para");

    await waitFor(() => {
      expect(medicamentosAPI.getAll).toHaveBeenLastCalledWith(
        expect.objectContaining({ search: "para", isActive: true }),
      );
    });
    expect(await within(dialog).findByRole("button", { name: /Clonazepam 2mg/ })).toHaveTextContent("Controlado");
  });

  it("muestra el medicamento elegido con su tope de cajas", async () => {
    const { user, dialog } = await openDialog();
    await pickMedication(user, dialog, /Paracetamol 500mg/);

    expect(within(dialog).getByText(/Máximo 2 cajas por receta/)).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Cambiar" })).toBeInTheDocument();
  });

  it("no agrega el medicamento sin via, frecuencia y duracion", async () => {
    const { user, dialog } = await openDialog();
    await pickMedication(user, dialog, /Paracetamol 500mg/);
    await user.type(within(dialog).getByLabelText("Indicaciones"), "Despues de comer");

    await user.click(within(dialog).getByRole("button", { name: "Agregar" }));

    expect(await within(dialog).findByText("Selecciona la vía de administración")).toBeInTheDocument();
    expect(within(dialog).getByText("Ingresa la frecuencia")).toBeInTheDocument();
    expect(within(dialog).getByText("Ingresa la duración")).toBeInTheDocument();
    expect(mutateAsync).not.toHaveBeenCalled();
  });

  it("envia via, frecuencia y duracion; los atajos llenan frecuencia y duracion", async () => {
    const { user, dialog } = await openDialog();
    await pickMedication(user, dialog, /Paracetamol 500mg/);
    await user.click(within(dialog).getByRole("combobox"));
    await user.click(await screen.findByRole("option", { name: "Oral" }));
    await user.click(within(dialog).getByRole("button", { name: "Cada 8 horas" }));
    await user.click(within(dialog).getByRole("button", { name: "5 días" }));
    await user.type(within(dialog).getByLabelText("Indicaciones"), "Despues de comer");

    await user.click(within(dialog).getByRole("button", { name: "Agregar" }));

    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledWith({
        visitId: 7,
        data: expect.objectContaining({
          medicationId: 10,
          route: "oral",
          frequency: "Cada 8 horas",
          duration: "5 días",
          indications: "Despues de comer",
        }),
      });
    });
  });

  it("lista los agregados con via, frecuencia, duracion y si piden autorizacion", async () => {
    vi.mocked(usePrescriptionItems).mockReturnValue({
      data: {
        items: [
          prescriptionItem(),
          prescriptionItem({ id: 2, medicationName: "Clonazepam 2mg", isControlled: true, requiresAuthorization: true }),
        ],
        total: 2,
      },
      isLoading: false,
    } as unknown as ReturnType<typeof usePrescriptionItems>);

    const { dialog } = await openDialog();

    expect(within(dialog).getAllByText(/Oral · Cada 8 horas · 5 dias/)).toHaveLength(2);
    expect(within(dialog).getByText("Controlado")).toBeInTheDocument();
  });

  it("los medicamentos guardados antes de via/frecuencia/duracion se siguen mostrando", async () => {
    vi.mocked(usePrescriptionItems).mockReturnValue({
      data: { items: [prescriptionItem({ route: null, routeLabel: null, frequency: null, duration: null })], total: 1 },
      isLoading: false,
    } as unknown as ReturnType<typeof usePrescriptionItems>);

    const { dialog } = await openDialog();

    expect(within(dialog).getByText(/Despues de comer/)).toBeInTheDocument();
    expect(within(dialog).queryByText(/null/)).toBeNull();
  });
});
