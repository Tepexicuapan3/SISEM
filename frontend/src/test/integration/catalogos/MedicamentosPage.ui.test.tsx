import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen } from "@/test/utils";
import MedicamentosPage from "@features/admin/modules/catalogos/medicamentos/pages/MedicamentosPage";
import { usePermissions } from "@/domains/auth-access/hooks/usePermissions";
import { useMedicamentosList } from "@features/admin/modules/catalogos/medicamentos/queries/useMedicamentosList";
import { useUpdateMedicamento } from "@features/admin/modules/catalogos/medicamentos/mutations/useUpdateMedicamento";
import { useDeleteMedicamento } from "@features/admin/modules/catalogos/medicamentos/mutations/useDeleteMedicamento";
import type { MedicamentoListItem } from "@api/types";

vi.mock("@shared/hooks/useDebounce", () => ({
  useDebounce: (value: string) => value,
}));

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

vi.mock(
  "@features/admin/modules/catalogos/medicamentos/components/MedicamentoDetailsDialog",
  () => ({
    MedicamentoDetailsDialog: ({ open }: { open: boolean }) =>
      open ? <div>Detalles medicamento abierto</div> : null,
  }),
);

vi.mock(
  "@features/admin/modules/catalogos/medicamentos/components/MedicamentoCreateDialog",
  () => ({
    MedicamentoCreateDialog: ({ open }: { open: boolean }) =>
      open ? <div>Crear medicamento abierto</div> : null,
  }),
);

vi.mock(
  "@features/admin/modules/catalogos/shared/import/CatalogImportDialog",
  () => ({
    CatalogImportDialog: ({ open, config }: { open: boolean; config: { slug: string } }) =>
      open ? <div>Importar {config.slug}</div> : null,
  }),
);

vi.mock("@/domains/auth-access/hooks/usePermissions", () => ({
  usePermissions: vi.fn(),
}));

vi.mock(
  "@features/admin/modules/catalogos/medicamentos/queries/useMedicamentosList",
  () => ({ useMedicamentosList: vi.fn() }),
);
vi.mock(
  "@features/admin/modules/catalogos/medicamentos/mutations/useUpdateMedicamento",
  () => ({ useUpdateMedicamento: vi.fn() }),
);
vi.mock(
  "@features/admin/modules/catalogos/medicamentos/mutations/useDeleteMedicamento",
  () => ({ useDeleteMedicamento: vi.fn() }),
);

const med = (overrides: Partial<MedicamentoListItem> = {}): MedicamentoListItem => ({
  id: 1,
  code: "010.000.0104.00",
  name: "PARACETAMOL 500 MG",
  genericName: "PARACETAMOL",
  presentation: "TABLETA. CAJA CON 10",
  cuadroBasico: "BASICO",
  isControlled: false,
  maxQuantity: 2,
  isActive: true,
  ...overrides,
});

describe("MedicamentosPage UI", () => {
  beforeEach(() => {
    vi.mocked(useMedicamentosList).mockImplementation((params) => ({
      data: {
        items: [
          med(),
          med({ id: 2, code: null, name: "CLONAZEPAM 2 MG", cuadroBasico: "ESPECIAL", isControlled: true }),
        ],
        page: params?.page ?? 1,
        pageSize: params?.pageSize ?? 10,
        total: 2,
        totalPages: 1,
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    }) as unknown as ReturnType<typeof useMedicamentosList>);
    vi.mocked(usePermissions).mockReturnValue({
      permissions: ["*"],
      hasPermission: () => true,
      hasAnyPermission: () => true,
      hasAllPermissions: () => true,
      isAdmin: () => true,
    });
    vi.mocked(useUpdateMedicamento).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useUpdateMedicamento>);
    vi.mocked(useDeleteMedicamento).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useDeleteMedicamento>);
  });

  it("lista clave, nombre, cuadro y si es controlado", () => {
    render(<MedicamentosPage />);

    expect(screen.getByRole("heading", { name: "Medicamentos" })).toBeVisible();
    expect(screen.getByText("010.000.0104.00")).toBeVisible();
    expect(screen.getByText("CLONAZEPAM 2 MG")).toBeVisible();
    expect(screen.getByText("Especial")).toBeVisible();
    expect(screen.getByText("Controlado")).toBeVisible();
  });

  it("busca tambien por clave y generico", async () => {
    const user = userEvent.setup();
    render(<MedicamentosPage />);

    await user.type(screen.getByPlaceholderText("Buscar en la tabla"), "0104");

    expect(screen.getByText("PARACETAMOL 500 MG")).toBeVisible();
    expect(screen.queryByText("CLONAZEPAM 2 MG")).toBeNull();
  });

  it("abre el alta y la importacion de Excel del catalogo de medicamentos", async () => {
    const user = userEvent.setup();
    render(<MedicamentosPage />);

    await user.click(screen.getByRole("button", { name: "Nuevo" }));
    expect(screen.getByText("Crear medicamento abierto")).toBeVisible();

    await user.click(screen.getByRole("button", { name: /opciones/i }));
    await user.click(screen.getByRole("menuitem", { name: "Importar Excel" }));
    expect(screen.getByText("Importar medications")).toBeVisible();
  });

  it("no ofrece Exportar (no hace nada)", async () => {
    const user = userEvent.setup();
    render(<MedicamentosPage />);

    await user.click(screen.getByRole("button", { name: /opciones/i }));
    expect(screen.queryByRole("menuitem", { name: "Exportar" })).toBeNull();
  });

  it("abre el detalle al hacer clic en una fila", async () => {
    const user = userEvent.setup();
    render(<MedicamentosPage />);

    await user.click(screen.getByText("PARACETAMOL 500 MG"));

    expect(screen.getByText("Detalles medicamento abierto")).toBeVisible();
  });
});
