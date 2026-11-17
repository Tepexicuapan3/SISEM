import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen } from "@/test/utils";
import { CiesRegisteredSection } from "@features/admin/modules/catalogos/cies/components/CiesRegisteredSection";
import { usePermissions } from "@/domains/auth-access/hooks/usePermissions";
import { useCiesList } from "@features/admin/modules/catalogos/cies/queries/useCiesList";
import type { CiesListItem } from "@api/resources/catalogos/cies.api";

vi.mock("@shared/hooks/useDebounce", () => ({
  useDebounce: (value: string) => value,
}));

vi.mock("@/domains/auth-access/hooks/usePermissions", () => ({
  usePermissions: vi.fn(),
}));

vi.mock("@features/admin/modules/catalogos/cies/queries/useCiesList", () => ({
  useCiesList: vi.fn(),
}));

const cie = (overrides: Partial<CiesListItem> = {}): CiesListItem => ({
  code: "E119",
  name: "DIABETES MELLITUS NO INSULINODEPENDIENTE, SIN MENCIÓN DE COMPLICACIÓN",
  version: "CIE-10",
  isActive: true,
  ...overrides,
});

const grantPermissions = (granted: string[]) => {
  const has = (code: string) => granted.includes(code);
  vi.mocked(usePermissions).mockReturnValue({
    permissions: granted,
    hasPermission: has,
    hasAnyPermission: (codes: string[]) => codes.some(has),
    hasAllPermissions: (codes: string[]) => codes.every(has),
    isAdmin: () => false,
  });
};

describe("CiesRegisteredSection UI", () => {
  beforeEach(() => {
    vi.mocked(useCiesList).mockImplementation(
      (params) =>
        ({
          data: {
            items: [
              cie(),
              cie({ code: "K297", name: "GASTRITIS, NO ESPECIFICADA", isActive: false }),
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
        }) as unknown as ReturnType<typeof useCiesList>,
    );
    grantPermissions(["admin:catalogos:cies:read"]);
  });

  it("lista las claves guardadas con su version y estado", () => {
    render(<CiesRegisteredSection />);

    expect(screen.getByRole("heading", { name: "Claves registradas" })).toBeVisible();
    expect(screen.getByText("E119")).toBeVisible();
    expect(screen.getByText("GASTRITIS, NO ESPECIFICADA")).toBeVisible();
    expect(screen.getAllByText("CIE-10")).toHaveLength(2);
    expect(screen.getByText("Inactivo")).toBeVisible();
  });

  it("busca en el servidor por clave o descripcion", async () => {
    const user = userEvent.setup();
    render(<CiesRegisteredSection />);

    await user.type(screen.getByPlaceholderText("Buscar por clave o descripción"), "E11.9");

    expect(vi.mocked(useCiesList)).toHaveBeenLastCalledWith(
      expect.objectContaining({ search: "E11.9", page: 1, sortBy: "code" }),
      { enabled: true },
    );
  });

  it("sin permiso de lectura no consulta y avisa", () => {
    grantPermissions(["admin:catalogos:cies:upload"]);
    render(<CiesRegisteredSection />);

    expect(
      screen.getByText("No tienes acceso para consultar las claves registradas."),
    ).toBeVisible();
    expect(vi.mocked(useCiesList)).toHaveBeenLastCalledWith(
      expect.anything(),
      { enabled: false },
    );
  });
});
