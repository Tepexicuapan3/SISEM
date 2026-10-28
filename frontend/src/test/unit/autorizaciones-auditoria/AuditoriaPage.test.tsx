import { describe, expect, it, vi } from "vitest";
import type { Mock } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen } from "@/test/utils";
import { usePermissions } from "@/domains/auth-access/hooks/usePermissions";
import AuditoriaAutorizacionesPage from "@features/admin/modules/autorizaciones-auditoria/pages/AuditoriaAutorizacionesPage";
import { etiquetaEvento } from "@features/admin/modules/autorizaciones-auditoria/domain/auditoria.format";

vi.mock("@/domains/auth-access/hooks/usePermissions", () => ({ usePermissions: vi.fn() }));

const FILA = {
  uuid: "11111111-2222-3333-4444-555555555555",
  folio: "AUT-2026-000001",
  folioOrigen: "RX-2026-000090",
  tipoOrigen: "RECETA",
  claveTipo: "REC",
  tipoNombre: "Recetas",
  centroNombre: "Clínica Norte",
  clues: "CLUES-1",
  estatus: "RECHAZADA",
  modalidad: "PRIMERO_VALIDO",
  aprobacionesRequeridas: 1,
  aprobaciones: 0,
  totalItems: 2,
  solicitanteNombre: "Dra. Solicitante",
  fechaCreacion: "2026-10-28T10:00:00Z",
  fechaLimite: "2026-10-31T10:00:00Z",
  fechaEscalamiento: null,
  fechaResolucion: "2026-10-28T11:00:00Z",
  resolvioNombre: "Dr. Autorizador",
  motivoCierre: "Otro motivo",
};

const LINEA = {
  solicitud: { ...FILA, hashContenido: "a".repeat(64) },
  eventos: [
    { fecha: "2026-10-28T10:00:00Z", evento: "CREADA", estatusAnterior: null, estatusNuevo: "PENDIENTE", usuarioNombre: "Dra. Solicitante", detalle: null },
    { fecha: "2026-10-28T11:00:00Z", evento: "RECHAZADA", estatusAnterior: "PENDIENTE", estatusNuevo: "RECHAZADA", usuarioNombre: "Dr. Autorizador", detalle: null },
  ],
  decisiones: [
    {
      fechaFirma: "2026-10-28T11:00:00Z",
      autorizadorNombre: "Dr. Autorizador",
      numeroCedula: "CED123",
      decision: "RECHAZAR",
      motivo: "Otro motivo",
      descripcionMotivo: "Fuera de cuadro básico",
      alcanceAplicado: "CENTRO",
      metodoFirma: "SIMPLE",
      hashContenido: "a".repeat(64),
      firmaVigente: true,
      ipOrigen: "10.0.0.1",
      agenteUsuario: "Firefox",
      identificadorPeticion: null,
    },
  ],
  destinatarios: [
    { autorizadorNombre: "Dr. Autorizador", tipoSeleccion: "ELEGIBLES", estatus: "DECIDIO", fechaEnvio: "2026-10-28T10:00:00Z", fechaVisto: null },
  ],
};

vi.mock("@features/admin/modules/autorizaciones-auditoria/queries/useAuditoria", () => ({
  useAuditoriaSolicitudes: () => ({
    data: { items: [FILA], page: 1, pageSize: 10, total: 1, totalPages: 1 },
    isLoading: false,
    isFetching: false,
    error: null,
    refetch: vi.fn(),
  }),
  useLineaDeTiempo: (uuid?: string) => ({ data: uuid ? LINEA : undefined, isLoading: false, error: null }),
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

describe("AuditoriaAutorizacionesPage", () => {
  it("sin permiso muestra el aviso", () => {
    sesion(["admin:autorizaciones-config:read"]);
    render(<AuditoriaAutorizacionesPage />);

    expect(screen.getByText(/No tienes acceso a la auditoría/i)).toBeVisible();
    expect(screen.queryByText(FILA.folio)).not.toBeInTheDocument();
  });

  it("con lectura lista sin boton de exportar", () => {
    sesion(["admin:autorizaciones-auditoria:read"]);
    render(<AuditoriaAutorizacionesPage />);

    expect(screen.getByText(FILA.folio)).toBeVisible();
    expect(screen.queryByRole("button", { name: /Exportar/i })).not.toBeInTheDocument();
  });

  it("con permiso de exportar ofrece Excel", () => {
    sesion(["admin:autorizaciones-auditoria:read", "admin:autorizaciones-auditoria:export"]);
    render(<AuditoriaAutorizacionesPage />);

    expect(screen.getByRole("button", { name: /Exportar/i })).toBeVisible();
  });

  it("abre la linea de tiempo con la firma", async () => {
    sesion(["*"]);
    render(<AuditoriaAutorizacionesPage />);

    await userEvent.click(screen.getByText(FILA.folio));

    expect(await screen.findByText("Fuera de cuadro básico")).toBeVisible();
    expect(screen.getByText("10.0.0.1")).toBeVisible();
    expect(screen.getByText("CED123")).toBeVisible();
    expect(screen.getByText(/Firma vigente/i)).toBeVisible();
  });
});

describe("etiquetaEvento", () => {
  it("traduce los eventos del motor", () => {
    expect(etiquetaEvento("CREADA")).toBe("Creada");
    expect(etiquetaEvento("ESCALADA")).toBe("Escalada sin respuesta");
    expect(etiquetaEvento("CANCELADA_ORIGEN")).toBe("Cancelada por el documento de origen");
    expect(etiquetaEvento("DESCONOCIDO")).toBe("DESCONOCIDO");
  });
});
