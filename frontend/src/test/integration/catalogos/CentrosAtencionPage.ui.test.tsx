import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent, {
  PointerEventsCheckLevel,
} from "@testing-library/user-event";
import { fireEvent, render, screen, waitFor, within } from "@/test/utils";
import CentrosAtencionPage from "@features/admin/modules/catalogos/centros-atencion/pages/CentrosAtencionPage";
import { toast } from "sonner";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import { useCentrosAtencionList } from "@features/admin/modules/catalogos/centros-atencion/queries/useCentrosAtencionList";
import { useUpdateCentroAtencion } from "@features/admin/modules/catalogos/centros-atencion/mutations/useUpdateCentroAtencion";
import { useDeleteCentroAtencion } from "@features/admin/modules/catalogos/centros-atencion/mutations/useDeleteCentroAtencion";
import type { CentroAtencionListItem } from "@api/types";

vi.mock("@shared/hooks/useDebounce", () => ({
  useDebounce: (value: string) => value,
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

vi.mock(
  "@features/admin/modules/catalogos/centros-atencion/components/CentroAtencionDetailsDialog",
  () => ({
    CentroAtencionDetailsDialog: ({ open }: { open: boolean }) =>
      open ? <div>Detalles centro abierto</div> : null,
  }),
);

vi.mock(
  "@features/admin/modules/catalogos/centros-atencion/components/CentroAtencionCreateDialog",
  () => ({
    CentroAtencionCreateDialog: ({ open }: { open: boolean }) =>
      open ? <div>Crear centro abierto</div> : null,
  }),
);

vi.mock("@/domains/auth-access/hooks/usePermissionDependencies", () => ({
  usePermissionDependencies: vi.fn(),
}));

vi.mock(
  "@features/admin/modules/catalogos/centros-atencion/queries/useCentrosAtencionList",
  () => ({
    useCentrosAtencionList: vi.fn(),
  }),
);

vi.mock(
  "@features/admin/modules/catalogos/centros-atencion/mutations/useUpdateCentroAtencion",
  () => ({
    useUpdateCentroAtencion: vi.fn(),
  }),
);

vi.mock(
  "@features/admin/modules/catalogos/centros-atencion/mutations/useDeleteCentroAtencion",
  () => ({
    useDeleteCentroAtencion: vi.fn(),
  }),
);

// La página usa `hasCapability`, pero también renderiza `PermissionGate`, que
// consume `hasEffectivePermission` / `hasEffectiveRequirement` del MISMO hook.
// Un mock solo con `hasCapability` rompe con "is not a function": las tres
// responden con el mismo predicado.
const mockPermissionDependencies = (allows: (code: string) => boolean) =>
  ({
    hasCapability: allows,
    hasEffectivePermission: allows,
    hasEffectiveRequirement: () => true,
  }) as unknown as ReturnType<typeof usePermissionDependencies>;

const createCenter = (
  overrides: Partial<CentroAtencionListItem> = {},
): CentroAtencionListItem => ({
  id: 1,
  name: "Centro Central",
  code: "DFCEN001",
  centerType: "CLINICA",
  legacyFolio: "CEN",
  isExternal: false,
  isActive: true,
  ...overrides,
});

describe("CentrosAtencionPage UI", () => {
  const refetch = vi.fn();
  const updateMutate = vi.fn();
  const deleteMutate = vi.fn();

  beforeEach(() => {
    const firstCenter = createCenter({ id: 1, name: "Centro Central" });
    const secondCenter = createCenter({
      id: 2,
      name: "Hospital Norte",
      code: "DFHOR001",
      centerType: "HOSPITAL",
      legacyFolio: "HNO",
      isExternal: true,
      isActive: false,
    });

    vi.mocked(useCentrosAtencionList).mockReturnValue({
      data: {
        items: [firstCenter, secondCenter],
        page: 1,
        pageSize: 10,
        total: 2,
        totalPages: 1,
      },
      isLoading: false,
      isFetching: false,
      isError: false,
      error: null,
      refetch,
      status: "success",
      fetchStatus: "idle",
    } as unknown as ReturnType<typeof useCentrosAtencionList>);

    vi.mocked(usePermissionDependencies).mockReturnValue(
      mockPermissionDependencies(() => true),
    );

    vi.mocked(useUpdateCentroAtencion).mockReturnValue({
      mutateAsync: updateMutate,
      isPending: false,
    } as unknown as ReturnType<typeof useUpdateCentroAtencion>);

    vi.mocked(useDeleteCentroAtencion).mockReturnValue({
      mutateAsync: deleteMutate,
      isPending: false,
    } as unknown as ReturnType<typeof useDeleteCentroAtencion>);

    updateMutate.mockResolvedValue({
      careCenter: {
        id: 1,
        name: "Centro Central",
        code: "DFCEN001",
        centerType: "CLINICA",
        legacyFolio: "CEN",
        isExternal: false,
        isActive: false,
      },
    });
    deleteMutate.mockResolvedValue({ success: true });
    vi.mocked(toast.success).mockClear();
    vi.mocked(toast.error).mockClear();
  });

  it("renders centers table with data", () => {
    render(<CentrosAtencionPage />);

    expect(
      screen.getByRole("heading", { name: "Centros de atencion" }),
    ).toBeVisible();
    expect(screen.getByText("Centro Central")).toBeVisible();
    expect(screen.getByText("Hospital Norte")).toBeVisible();
  });

  it("opens create dialog from primary action", async () => {
    const user = userEvent.setup();
    render(<CentrosAtencionPage />);

    await user.click(screen.getByRole("button", { name: "Nuevo" }));

    expect(screen.getByText("Crear centro abierto")).toBeVisible();
  });

  it("opens details dialog when clicking a row", async () => {
    const user = userEvent.setup();
    render(<CentrosAtencionPage />);

    await user.click(screen.getByText("Centro Central"));

    expect(screen.getByText("Detalles centro abierto")).toBeVisible();
  });

  it("applies status and type filters in query params", async () => {
    const user = userEvent.setup();
    render(<CentrosAtencionPage />);

    await user.click(screen.getByRole("button", { name: /Filtros/ }));
    const menu = screen.getByRole("menu");
    await user.click(within(menu).getByText("Activos"));

    await waitFor(() => {
      expect(vi.mocked(useCentrosAtencionList)).toHaveBeenLastCalledWith(
        expect.objectContaining({ isActive: true }),
        expect.objectContaining({ enabled: true }),
      );
    });

    await user.click(screen.getByRole("button", { name: /Filtros/ }));
    const secondMenu = screen.getByRole("menu");
    await user.click(within(secondMenu).getByText("Externos"));

    await waitFor(() => {
      expect(vi.mocked(useCentrosAtencionList)).toHaveBeenLastCalledWith(
        expect.objectContaining({ isExternal: true }),
        expect.objectContaining({ enabled: true }),
      );
    });
  });

  it("shows minimal notice when catalog read access is missing", () => {
    vi.mocked(usePermissionDependencies).mockReturnValue(
      mockPermissionDependencies((cap) => cap !== "admin.catalogs.centers.read"),
    );

    render(<CentrosAtencionPage />);

    expect(
      screen.getByText("No tienes acceso para consultar este catalogo."),
    ).toBeVisible();
    expect(vi.mocked(useCentrosAtencionList)).toHaveBeenLastCalledWith(
      expect.any(Object),
      expect.objectContaining({ enabled: false }),
    );
  });

  it("executes status action from row menu", async () => {
    const user = userEvent.setup({
      pointerEventsCheck: PointerEventsCheckLevel.Never,
    });
    render(<CentrosAtencionPage />);

    const row = screen.getByText("Centro Central").closest("tr");
    expect(row).not.toBeNull();
    const actions = within(row as HTMLElement).getByLabelText("Acciones");

    fireEvent.pointerDown(actions);
    fireEvent.click(actions);
    await user.click(screen.getByRole("menuitem", { name: "Desactivar" }));

    await waitFor(() => {
      expect(updateMutate).toHaveBeenCalledWith({
        centerId: 1,
        data: { isActive: false },
      });
      expect(toast.success).toHaveBeenCalledWith("Centro desactivado");
    });
  });

  it("executes delete action", async () => {
    const user = userEvent.setup({
      pointerEventsCheck: PointerEventsCheckLevel.Never,
    });
    render(<CentrosAtencionPage />);

    const row = screen.getByText("Centro Central").closest("tr");
    expect(row).not.toBeNull();
    const actions = within(row as HTMLElement).getByLabelText("Acciones");

    fireEvent.pointerDown(actions);
    fireEvent.click(actions);
    await user.click(screen.getByRole("menuitem", { name: "Eliminar" }));
    await user.click(screen.getByRole("button", { name: "Confirmar" }));

    await waitFor(() => {
      expect(deleteMutate).toHaveBeenCalledWith({ centerId: 1 });
      expect(toast.success).toHaveBeenCalledWith(
        "Centro eliminado",
        expect.any(Object),
      );
    });
  });
});
