import { describe, expect, it, vi } from "vitest";
import type { Mock } from "vitest";
import { render, screen } from "@/test/utils";
import { usePermissions } from "@/domains/auth-access/hooks/usePermissions";
import AutorizadoresPage from "@features/admin/modules/autorizadores/pages/AutorizadoresPage";

// Regresion: el frontend trata todo "admin.*" como capability estricta, asi que
// un admin con "*" veia "No tienes acceso" (2026-10-27). La pagina evalua
// permisos atomicos y debe respetar el comodin.

vi.mock("@/domains/auth-access/hooks/usePermissions", () => ({ usePermissions: vi.fn() }));

vi.mock("@features/admin/modules/autorizadores/queries/useAutorizadores", () => ({
  useAutorizadoresList: () => ({
    data: { items: [], page: 1, pageSize: 10, total: 0, totalPages: 1 },
    isLoading: false,
    isFetching: false,
    error: null,
    refetch: vi.fn(),
  }),
  useCatalogosAutorizacion: () => ({ data: { tipos: [], motivos: [] } }),
  useAutorizadorDetail: () => ({ data: undefined, isLoading: false, isError: false, refetch: vi.fn() }),
  useAutorizadorHistorial: () => ({ data: undefined, isLoading: false, isError: false, refetch: vi.fn() }),
  useUsuariosElegibles: () => ({ data: undefined, isLoading: false, isError: false }),
}));

vi.mock("@features/admin/modules/catalogos/centros-atencion/queries/useCentrosAtencionList", () => ({
  useCentrosAtencionList: () => ({ data: { items: [] } }),
}));

const sesion = (permisos: string[]) => {
  (usePermissions as unknown as Mock).mockReturnValue({
    permissions: permisos,
    effectivePermissions: permisos,
    capabilities: {},
    permissionDependenciesVersion: "v1",
    strictCapabilityPrefixes: ["flow.recepcion."],
    hasPermission: vi.fn(() => false),
    hasAnyPermission: vi.fn(() => false),
    hasAllPermissions: vi.fn(() => false),
    isAdmin: vi.fn(() => permisos.includes("*")),
  } as unknown as ReturnType<typeof usePermissions>);
};

describe("AutorizadoresPage: acceso por permisos", () => {
  it("un admin con '*' puede consultar y dar de alta", () => {
    sesion(["*"]);
    render(<AutorizadoresPage />);

    expect(screen.queryByText(/No tienes acceso para consultar/i)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Nuevo autorizador/i })).toBeVisible();
  });

  it("con solo lectura consulta pero no da de alta", () => {
    sesion(["admin:autorizadores:read"]);
    render(<AutorizadoresPage />);

    expect(screen.queryByText(/No tienes acceso para consultar/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Nuevo autorizador/i })).not.toBeInTheDocument();
  });

  it("sin permiso muestra el aviso", () => {
    sesion([]);
    render(<AutorizadoresPage />);

    expect(screen.getByText(/No tienes acceso para consultar/i)).toBeVisible();
  });
});
