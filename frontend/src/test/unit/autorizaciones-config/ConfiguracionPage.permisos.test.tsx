import { describe, expect, it, vi } from "vitest";
import type { Mock } from "vitest";
import { render, screen } from "@/test/utils";
import { usePermissions } from "@/domains/auth-access/hooks/usePermissions";
import ConfiguracionAutorizacionesPage from "@features/admin/modules/autorizaciones-config/pages/ConfiguracionAutorizacionesPage";

vi.mock("@/domains/auth-access/hooks/usePermissions", () => ({ usePermissions: vi.fn() }));

const TIPO = {
  id: 1,
  clave: "REC",
  nombre: "Recetas",
  version: 1,
  modalidadPredeterminada: "PRIMERO_VALIDO",
  aprobacionesRequeridas: 1,
  rechazoResuelveSolicitud: true,
  permiteRechazo: true,
  horasVigenciaSolicitud: 72,
  horasEscalamiento: 24,
  requiereCedula: true,
};

vi.mock("@features/admin/modules/autorizaciones-config/queries/useConfiguracion", () => ({
  useTiposConfiguracion: () => ({ data: { items: [TIPO] }, isLoading: false, error: null, refetch: vi.fn() }),
  useReglasCentro: () => ({ data: { items: [] }, isLoading: false, error: null, refetch: vi.fn() }),
  useMotivosConfiguracion: () => ({ data: { items: [] }, isLoading: false, error: null, refetch: vi.fn() }),
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

describe("ConfiguracionAutorizacionesPage: acceso por permisos", () => {
  it("un admin con '*' ve los tipos y puede editarlos", () => {
    sesion(["*"]);
    render(<ConfiguracionAutorizacionesPage />);

    expect(screen.getByText("Recetas")).toBeVisible();
    expect(screen.getByRole("button", { name: /Editar Recetas/i })).toBeVisible();
  });

  it("con solo lectura consulta pero no edita", () => {
    sesion(["admin:autorizaciones-config:read"]);
    render(<ConfiguracionAutorizacionesPage />);

    expect(screen.getByText("Recetas")).toBeVisible();
    expect(screen.queryByRole("button", { name: /Editar Recetas/i })).not.toBeInTheDocument();
  });

  it("sin permiso muestra el aviso y no carga datos", () => {
    sesion(["admin:autorizadores:read"]);
    render(<ConfiguracionAutorizacionesPage />);

    expect(screen.getByText(/No tienes acceso a la configuración/i)).toBeVisible();
    expect(screen.queryByText("Recetas")).not.toBeInTheDocument();
  });
});
