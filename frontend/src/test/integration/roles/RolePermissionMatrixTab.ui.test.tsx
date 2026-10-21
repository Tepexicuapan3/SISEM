import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent, {
  PointerEventsCheckLevel,
} from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { render, screen, waitFor, within } from "@/test/utils";
import { server } from "@/test/mocks/server";
import { getApiUrl } from "@/test/mocks/urls";
import { setMockSessionUser } from "@/test/mocks/session";
import { createMockAuthUser } from "@/test/factories/users";
import {
  createMockRoleDetail,
  createMockRoleListItem,
  createMockRolePermission,
} from "@/test/factories/roles";
import { RoleDetailsDialog } from "@/domains/auth-access/components/admin/rbac/roles/RoleDetailsDialog";
import { toast } from "sonner";
import type { ModuleCatalogNodeDTO } from "@api/types/navigation.types";
import type { Permission } from "@api/types/permissions.types";
import type { RoleDetail, RolePermission } from "@api/types/roles.types";

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}));

/**
 * Tests de integracion de la tab "Permisos por modulo" (matriz) del detalle
 * de rol.
 *
 * A diferencia de `RoleDetailsDialog.ui.test.tsx` (que mockea los hooks de
 * React Query directamente), estos tests montan `RoleDetailsDialog` con los
 * hooks REALES (`useRoleDetail`, `usePermissionsCatalog`, `useModuleCatalog`,
 * `useAssignRolePermissions`, `useAuthSession`) y los ejercitan contra MSW,
 * mockeando `GET /api/v1/modules`, `GET /permissions` (con `dependsOn`) y
 * `POST /permissions/assign` por test via `server.use(...)`. Solo se mockea
 * `sonner` (no hay `Toaster` montado en `TestProviders`), igual que el resto
 * de la suite de roles.
 *
 * Fixture:
 * - `clinico:consultas` (read/update/cancel): modulo dueno "Bandeja de
 *   Consultas" (override); su `read` esta enlazado ademas a 3 modulos
 *   (colaterales). `cancel` cae en la columna "Otras".
 * - `clinico:reportes` (read/export): el modulo "Exportar Reportes" enlaza
 *   solo `export`; `read` no tiene modulo (sin colaterales).
 * - `admin:gestion:usuarios` (read/update) en la seccion "Panel de
 *   Administracion": `update` depende de roles:read y permisos:read, que no
 *   tienen modulo y viven en "Otros permisos" junto con `admin:reportes:read`.
 */

const CONSULTAS_READ = "clinico:consultas:read";
const CONSULTAS_UPDATE = "clinico:consultas:update";
const CONSULTAS_CANCEL = "clinico:consultas:cancel";
const REPORTES_READ = "clinico:reportes:read";
const REPORTES_EXPORT = "clinico:reportes:export";
const USUARIOS_READ = "admin:gestion:usuarios:read";
const USUARIOS_UPDATE = "admin:gestion:usuarios:update";
const ROLES_READ = "admin:gestion:roles:read";
const PERMISOS_READ = "admin:gestion:permisos:read";
const ORPHAN_REPORTES_READ = "admin:reportes:read";

const permission = (
  id: number,
  code: string,
  description: string,
  dependsOn: string[],
): Permission => ({ id, code, description, isSystem: true, dependsOn });

const PERMISSIONS_CATALOG: Permission[] = [
  permission(501, CONSULTAS_READ, "Ver consultas", []),
  permission(502, CONSULTAS_UPDATE, "Editar consultas", [CONSULTAS_READ]),
  permission(503, CONSULTAS_CANCEL, "Cancelar consultas", [CONSULTAS_READ]),
  permission(504, REPORTES_READ, "Ver reportes clinicos", []),
  permission(505, REPORTES_EXPORT, "Exportar reportes", [REPORTES_READ]),
  permission(601, ORPHAN_REPORTES_READ, "Ver reportes", []),
  permission(701, USUARIOS_READ, "Ver usuarios", []),
  permission(702, USUARIOS_UPDATE, "Editar usuarios", [
    PERMISOS_READ,
    ROLES_READ,
    USUARIOS_READ,
  ]),
  permission(703, ROLES_READ, "Ver roles", []),
  permission(704, PERMISOS_READ, "Ver permisos", []),
];

const leaf = (
  key: string,
  title: string,
  permissions: string[],
): ModuleCatalogNodeDTO => ({
  key,
  title,
  icon: "activity",
  url: `/${key.replace(/\./g, "/")}`,
  group: "primary",
  isSection: false,
  permissions,
  items: [],
});

const buildModuleTree = (): ModuleCatalogNodeDTO[] => [
  {
    key: "administracion.panel",
    title: "Panel de Administracion",
    icon: "settings",
    url: null,
    group: "primary",
    isSection: true,
    permissions: [],
    items: [
      leaf("administracion.panel.usuarios", "Usuarios", [
        USUARIOS_READ,
        USUARIOS_UPDATE,
      ]),
    ],
  },
  leaf("clinico.consultas.bandeja", "Bandeja de Consultas", [
    CONSULTAS_READ,
    CONSULTAS_UPDATE,
    CONSULTAS_CANCEL,
  ]),
  leaf("clinico.consultas.detalle", "Detalle de Consulta", [CONSULTAS_READ]),
  leaf("clinico.dashboard.widget", "Widget de Consultas", [CONSULTAS_READ]),
  leaf("reportes.consultas", "Reporte de Consultas", [CONSULTAS_READ]),
  leaf("clinico.reportes.export", "Exportar Reportes", [REPORTES_EXPORT]),
];

const mockModuleCatalog = () => {
  server.use(
    http.get(getApiUrl("modules"), () => {
      return HttpResponse.json({ modules: buildModuleTree() });
    }),
  );
};

const mockPermissionsCatalog = () => {
  server.use(
    http.get(getApiUrl("permissions"), () => {
      return HttpResponse.json({
        items: PERMISSIONS_CATALOG,
        total: PERMISSIONS_CATALOG.length,
      });
    }),
  );
};

const permissionToRolePermission = (item: Permission): RolePermission =>
  createMockRolePermission({
    id: item.id,
    code: item.code,
    description: item.description,
  });

const permissionsByCode = (...codes: string[]): RolePermission[] =>
  PERMISSIONS_CATALOG.filter((item) => codes.includes(item.code)).map(
    permissionToRolePermission,
  );

const onOpenChange = vi.fn();
const onClose = vi.fn();

const buildRole = (id: number, overrides: Partial<RoleDetail> = {}) => {
  const base = {
    id,
    name: "Rol Matriz",
    description: "Rol de prueba de la matriz",
    isSystem: false,
    isActive: true,
    ...overrides,
  };
  return {
    roleDetail: createMockRoleDetail(base),
    roleSummary: createMockRoleListItem(base),
  };
};

const mockRoleDetail = (
  roleDetail: RoleDetail,
  permissions: RolePermission[],
) => {
  server.use(
    http.get(getApiUrl("roles/:id"), () => {
      return HttpResponse.json({ role: roleDetail, permissions });
    }),
  );
};

/** Captura los `POST /permissions/assign` y responde con el set pedido. */
const mockAssignCapture = () => {
  const bodies: Array<{ roleId: number; permissionIds: number[] }> = [];
  server.use(
    http.post(getApiUrl("permissions/assign"), async ({ request }) => {
      const body = (await request.json()) as {
        roleId: number;
        permissionIds: number[];
      };
      bodies.push(body);
      return HttpResponse.json({
        roleId: body.roleId,
        permissions: PERMISSIONS_CATALOG.filter((item) =>
          body.permissionIds.includes(item.id),
        ).map(permissionToRolePermission),
      });
    }),
  );
  return bodies;
};

const setup = () =>
  userEvent.setup({ pointerEventsCheck: PointerEventsCheckLevel.Never });

const renderDialog = (
  roleSummary: ReturnType<typeof buildRole>["roleSummary"],
  extraProps: { canReadPermissionsCatalog?: boolean } = {},
) =>
  render(
    <RoleDetailsDialog
      open
      onOpenChange={onOpenChange}
      onClose={onClose}
      roleSummary={roleSummary}
      canEdit
      {...extraProps}
    />,
  );

const openMatrixTab = async (user: ReturnType<typeof setup>) => {
  await user.click(
    await screen.findByRole("tab", { name: /Permisos por módulo/i }),
  );
};

/**
 * `useAuthSession` (GET /auth/me) resuelve en paralelo con `useModuleCatalog`
 * (GET /modules) -- las celdas quedan disabled hasta que `actorPermissions`
 * carga (preflight por actor en `RolePermissionMatrixTab`). Si se clickea una
 * celda apenas aparece, el click es un no-op silencioso. Se espera
 * explicitamente a que quede habilitada antes de clickearla.
 */
const findEnabledCheckbox = async (name: string) => {
  await waitFor(() => {
    expect(screen.getByRole("checkbox", { name })).toBeEnabled();
  });
  return screen.getByRole("checkbox", { name });
};

const getRowOf = (checkboxName: string): HTMLElement => {
  const row = screen
    .getByRole("checkbox", { name: checkboxName })
    .closest("tr");
  if (!row) throw new Error(`No row found for "${checkboxName}"`);
  return row;
};

describe("RolePermissionMatrixTab integration (MSW)", () => {
  beforeEach(() => {
    onOpenChange.mockClear();
    onClose.mockClear();
    vi.mocked(toast.success).mockClear();
    vi.mocked(toast.error).mockClear();
    vi.mocked(toast.info).mockClear();
    mockModuleCatalog();
    mockPermissionsCatalog();
    setMockSessionUser(createMockAuthUser({ permissions: ["*"] }));
  });

  it("collateral impact dialog: cancel keeps draft untouched, confirm + Guardar sends ONE bulk assign with the full set", async () => {
    const { roleDetail, roleSummary } = buildRole(50, {
      name: "Clinico Editor",
    });
    mockRoleDetail(roleDetail, permissionsByCode(ORPHAN_REPORTES_READ));
    const bodies = mockAssignCapture();

    const user = setup();
    renderDialog(roleSummary);
    await openMatrixTab(user);

    const ownerReadName = "Ver consultas en Bandeja de Consultas";
    await user.click(await findEnabledCheckbox(ownerReadName));

    expect(
      screen.getByRole("heading", { name: /Efecto colateral en/ }),
    ).toBeVisible();
    expect(
      screen.getByText(
        "Este cambio también hará visibles: Detalle de Consulta, Widget de Consultas, Reporte de Consultas. ¿Confirmás el cambio?",
      ),
    ).toBeVisible();

    // Cancelar: el dialogo cierra sin mutar el draft.
    await user.click(screen.getByRole("button", { name: "Cancelar" }));

    expect(
      screen.queryByRole("heading", { name: /Efecto colateral en/ }),
    ).toBeNull();
    expect(
      screen.getByRole("checkbox", { name: ownerReadName }),
    ).not.toBeChecked();
    expect(bodies).toHaveLength(0);

    // Tildar de nuevo y esta vez confirmar el efecto colateral.
    await user.click(await findEnabledCheckbox(ownerReadName));
    await user.click(screen.getByRole("button", { name: "Confirmar" }));

    expect(screen.getByRole("checkbox", { name: ownerReadName })).toBeChecked();
    // El codigo compartido se ve tildado tambien en los modulos colaterales.
    expect(
      screen.getByRole("checkbox", {
        name: "Ver consultas en Detalle de Consulta",
      }),
    ).toBeChecked();
    // Confirmar solo muta el draft local -- no dispara red hasta "Guardar".
    expect(bodies).toHaveLength(0);

    await user.click(screen.getByRole("button", { name: "Guardar" }));

    await waitFor(() => {
      expect(bodies).toHaveLength(1);
    });
    expect(bodies[0]).toEqual({
      roleId: 50,
      permissionIds: expect.arrayContaining([601, 501]),
    });
    expect(bodies[0].permissionIds).toHaveLength(2);

    await waitFor(() => {
      expect(toast.success).toHaveBeenCalledWith(
        "Cambios guardados",
        expect.any(Object),
      );
    });
  });

  it("system role: matrix renders read-only with every checkbox disabled regardless of assigned permissions", async () => {
    const { roleDetail, roleSummary } = buildRole(1, {
      name: "Admin",
      description: "Rol de sistema",
      isSystem: true,
    });
    mockRoleDetail(roleDetail, permissionsByCode(CONSULTAS_READ));

    const user = setup();
    renderDialog(roleSummary);
    await openMatrixTab(user);

    expect(
      screen.getByText(
        "Solo lectura: no puedes actualizar este rol porque es de sistema o no tienes permisos.",
      ),
    ).toBeVisible();

    const checkboxes = await screen.findAllByRole("checkbox");
    expect(checkboxes.length).toBeGreaterThan(0);
    for (const checkbox of checkboxes) {
      expect(checkbox).toBeDisabled();
    }

    // Los modulos que comparten el permiso asignado se ven tildados pero
    // siguen disabled -- el estado real de permisos no habilita nada.
    await waitFor(() => {
      expect(
        screen.getByRole("checkbox", {
          name: "Ver consultas en Bandeja de Consultas",
        }),
      ).toBeChecked();
    });
    expect(
      screen.getByRole("checkbox", {
        name: "Ver consultas en Detalle de Consulta",
      }),
    ).toBeChecked();
    expect(
      screen.getByRole("checkbox", {
        name: "Export reportes en Exportar Reportes",
      }),
    ).not.toBeChecked();
  });

  it("admin role: every cell renders checked and disabled with the admin legend, regardless of RelRolPermiso", async () => {
    const { roleDetail, roleSummary } = buildRole(2, {
      name: "admin",
      description: "Administrador del dominio Auth-Access",
      isAdmin: true,
    });
    // RelRolPermiso vacio -- asi es en produccion para el rol admin, porque
    // el RBACResolver le da acceso via wildcard dinamico.
    mockRoleDetail(roleDetail, []);

    const user = setup();
    renderDialog(roleSummary);
    await openMatrixTab(user);

    expect(
      screen.getByText(
        "Este rol tiene acceso total automatico a todos los permisos y modulos -- no depende de asignaciones individuales.",
      ),
    ).toBeVisible();

    const checkboxes = await screen.findAllByRole("checkbox");
    expect(checkboxes.length).toBeGreaterThan(0);
    for (const checkbox of checkboxes) {
      expect(checkbox).toBeDisabled();
      expect(checkbox).toBeChecked();
    }
  });

  it("PERMISSION_GRANT_NOT_ALLOWED: shows the mapped message instead of a generic error and resyncs the cell", async () => {
    const { roleDetail, roleSummary } = buildRole(60, {
      name: "Auditoria QA",
    });
    mockRoleDetail(roleDetail, []);
    server.use(
      http.post(getApiUrl("permissions/assign"), () => {
        return HttpResponse.json(
          {
            code: "PERMISSION_GRANT_NOT_ALLOWED",
            message: "No puedes asignar permisos que no tienes.",
          },
          { status: 403 },
        );
      }),
    );

    const user = setup();
    renderDialog(roleSummary);
    await openMatrixTab(user);

    const exportName = "Export reportes en Exportar Reportes";
    await user.click(await findEnabledCheckbox(exportName));
    // Codigo sin colaterales: se aplica directo al draft sin dialogo.
    expect(screen.getByRole("checkbox", { name: exportName })).toBeChecked();

    await user.click(screen.getByRole("button", { name: "Guardar" }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        "No se pudieron guardar todos los cambios",
        expect.objectContaining({
          description: "No puedes asignar permisos que no tienes.",
        }),
      );
    });

    // Nunca se aplico un mensaje generico.
    expect(toast.error).not.toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        description: "No se pudieron guardar los cambios del rol.",
      }),
    );

    // El refetch tras el error resincroniza el draft con el servidor.
    await waitFor(() => {
      expect(
        screen.getByRole("checkbox", { name: exportName }),
      ).not.toBeChecked();
    });
  });

  it("auto-Ver: checking an action also checks Ver of the resource and informs via toast", async () => {
    const { roleDetail, roleSummary } = buildRole(61);
    mockRoleDetail(roleDetail, []);

    const user = setup();
    renderDialog(roleSummary);
    await openMatrixTab(user);

    const verName = "Ver reportes en Exportar Reportes";
    const exportName = "Export reportes en Exportar Reportes";
    await user.click(await findEnabledCheckbox(exportName));

    expect(screen.getByRole("checkbox", { name: exportName })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: verName })).toBeChecked();
    expect(toast.info).toHaveBeenCalledWith(
      expect.stringContaining(REPORTES_READ),
    );
  });

  it("unchecking Ver clears every action of the resource and reports what was removed", async () => {
    const { roleDetail, roleSummary } = buildRole(62);
    mockRoleDetail(
      roleDetail,
      permissionsByCode(REPORTES_READ, REPORTES_EXPORT),
    );

    const user = setup();
    renderDialog(roleSummary);
    await openMatrixTab(user);

    const verName = "Ver reportes en Exportar Reportes";
    const exportName = "Export reportes en Exportar Reportes";
    await waitFor(() => {
      expect(screen.getByRole("checkbox", { name: exportName })).toBeChecked();
    });

    await user.click(await findEnabledCheckbox(verName));

    expect(screen.getByRole("checkbox", { name: verName })).not.toBeChecked();
    expect(
      screen.getByRole("checkbox", { name: exportName }),
    ).not.toBeChecked();
    expect(toast.info).toHaveBeenCalledWith(
      expect.stringContaining(REPORTES_EXPORT),
    );
  });

  it("dependency auto-add: checking usuarios:update adds roles:read and permisos:read and shows a toast listing them", async () => {
    const { roleDetail, roleSummary } = buildRole(63);
    mockRoleDetail(roleDetail, []);
    const bodies = mockAssignCapture();

    const user = setup();
    renderDialog(roleSummary);
    await openMatrixTab(user);

    await user.click(await findEnabledCheckbox("Editar usuarios en Usuarios"));

    expect(
      screen.getByRole("checkbox", { name: "Editar usuarios en Usuarios" }),
    ).toBeChecked();
    expect(
      screen.getByRole("checkbox", { name: "Ver usuarios en Usuarios" }),
    ).toBeChecked();
    expect(
      screen.getByRole("checkbox", { name: `${ROLES_READ} en Otros permisos` }),
    ).toBeChecked();
    expect(
      screen.getByRole("checkbox", {
        name: `${PERMISOS_READ} en Otros permisos`,
      }),
    ).toBeChecked();
    expect(toast.info).toHaveBeenCalledWith(
      expect.stringContaining(ROLES_READ),
    );
    expect(toast.info).toHaveBeenCalledWith(
      expect.stringContaining(PERMISOS_READ),
    );

    await user.click(screen.getByRole("button", { name: "Guardar" }));
    await waitFor(() => {
      expect(bodies).toHaveLength(1);
    });
    expect([...bodies[0].permissionIds].sort()).toEqual([701, 702, 703, 704]);
  });

  it("cascade uncheck: unchecking a required dependency also unchecks its dependents and toasts the removal", async () => {
    const { roleDetail, roleSummary } = buildRole(64);
    mockRoleDetail(
      roleDetail,
      permissionsByCode(
        USUARIOS_READ,
        USUARIOS_UPDATE,
        ROLES_READ,
        PERMISOS_READ,
      ),
    );

    const user = setup();
    renderDialog(roleSummary);
    await openMatrixTab(user);

    const rolesReadName = `${ROLES_READ} en Otros permisos`;
    await waitFor(() => {
      expect(
        screen.getByRole("checkbox", { name: "Editar usuarios en Usuarios" }),
      ).toBeChecked();
    });

    await user.click(await findEnabledCheckbox(rolesReadName));

    // usuarios:update esta enlazado al modulo "Usuarios": la cascada abre el
    // dialogo de impacto antes de mutar el draft.
    expect(
      screen.getByRole("heading", { name: /Efecto colateral en/ }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Confirmar" }));

    expect(
      screen.getByRole("checkbox", { name: rolesReadName }),
    ).not.toBeChecked();
    expect(
      screen.getByRole("checkbox", { name: "Editar usuarios en Usuarios" }),
    ).not.toBeChecked();
    // Lo que no depende de lo quitado se conserva.
    expect(
      screen.getByRole("checkbox", { name: "Ver usuarios en Usuarios" }),
    ).toBeChecked();
    expect(toast.info).toHaveBeenCalledWith(
      expect.stringContaining(USUARIOS_UPDATE),
    );
  });

  it("disabled cell: the actor cannot toggle a permission whose dependency closure they do not own, with an explanatory tooltip", async () => {
    setMockSessionUser(
      createMockAuthUser({ permissions: [PERMISOS_READ, ROLES_READ] }),
    );
    const { roleDetail, roleSummary } = buildRole(65);
    mockRoleDetail(roleDetail, []);

    const user = setup();
    renderDialog(roleSummary);
    await openMatrixTab(user);

    // Espera a que la sesion cargue: el actor SI posee permisos:read.
    await findEnabledCheckbox(`${PERMISOS_READ} en Otros permisos`);

    const updateCell = screen.getByRole("checkbox", {
      name: "Editar usuarios en Usuarios",
    });
    expect(updateCell).toBeDisabled();

    await user.hover(updateCell.parentElement as HTMLElement);
    const tooltips = await screen.findAllByText(
      new RegExp(`Requiere: .*${USUARIOS_UPDATE}`),
    );
    expect(tooltips.length).toBeGreaterThan(0);
  });

  it("Otras column: non-CRUD actions render as labeled checkboxes only in the owner row; other modules show just the shared Ver", async () => {
    const { roleDetail, roleSummary } = buildRole(66);
    mockRoleDetail(roleDetail, []);

    const user = setup();
    renderDialog(roleSummary);
    await openMatrixTab(user);

    const cancelName = "Cancel consultas en Bandeja de Consultas";
    await findEnabledCheckbox(cancelName);
    const ownerRow = getRowOf(cancelName);
    expect(within(ownerRow).getByText("Cancel")).toBeVisible();
    expect(
      within(ownerRow).getByRole("checkbox", {
        name: "Editar consultas en Bandeja de Consultas",
      }),
    ).toBeVisible();

    const detailRow = getRowOf("Ver consultas en Detalle de Consulta");
    expect(
      within(detailRow).queryByRole("checkbox", { name: /Editar consultas/ }),
    ).toBeNull();
    expect(within(detailRow).getByText("Compartido")).toBeVisible();
  });

  it("Otros permisos: resources without a module are listed and preserved on save (full replace)", async () => {
    const { roleDetail, roleSummary } = buildRole(67);
    mockRoleDetail(roleDetail, permissionsByCode(ORPHAN_REPORTES_READ));
    const bodies = mockAssignCapture();

    const user = setup();
    renderDialog(roleSummary);
    await openMatrixTab(user);

    expect(await screen.findByText("Otros permisos")).toBeVisible();
    const orphanName = `${ORPHAN_REPORTES_READ} en Otros permisos`;
    await waitFor(() => {
      expect(screen.getByRole("checkbox", { name: orphanName })).toBeChecked();
    });

    await user.click(
      await findEnabledCheckbox("Export reportes en Exportar Reportes"),
    );
    await user.click(screen.getByRole("button", { name: "Guardar" }));

    await waitFor(() => {
      expect(bodies).toHaveLength(1);
    });
    // 601 (fuera de cualquier modulo) se conserva + export + su Ver.
    expect([...bodies[0].permissionIds].sort()).toEqual([504, 505, 601]);
  });

  it("section tri-state: partial selection is indeterminate and clicking it checks, then unchecks, every enabled cell", async () => {
    const { roleDetail, roleSummary } = buildRole(68);
    mockRoleDetail(roleDetail, permissionsByCode(USUARIOS_READ));

    const user = setup();
    renderDialog(roleSummary);
    await openMatrixTab(user);

    const sectionName = "Todos los permisos de Panel de Administracion";
    await waitFor(() => {
      expect(
        screen.getByRole("checkbox", { name: sectionName }),
      ).toBePartiallyChecked();
    });

    await user.click(await findEnabledCheckbox(sectionName));

    expect(screen.getByRole("checkbox", { name: sectionName })).toBeChecked();
    expect(
      screen.getByRole("checkbox", { name: "Editar usuarios en Usuarios" }),
    ).toBeChecked();

    // De todo a nada.
    await user.click(screen.getByRole("checkbox", { name: sectionName }));
    expect(
      screen.getByRole("checkbox", { name: sectionName }),
    ).not.toBeChecked();
  });

  it("missing actions render as an em dash instead of a checkbox", async () => {
    const { roleDetail, roleSummary } = buildRole(69);
    mockRoleDetail(roleDetail, []);

    const user = setup();
    renderDialog(roleSummary);
    await openMatrixTab(user);

    await findEnabledCheckbox("Ver usuarios en Usuarios");
    const usuariosRow = getRowOf("Ver usuarios en Usuarios");
    // usuarios solo tiene read/update: Crear, Eliminar y Otras son "—".
    const dashes = within(usuariosRow).getAllByLabelText("No disponible");
    expect(dashes).toHaveLength(3);
    for (const dash of dashes) {
      expect(dash).toHaveTextContent("—");
    }
    expect(
      within(usuariosRow).queryByRole("checkbox", { name: /Crear usuarios/ }),
    ).toBeNull();
  });

  it("catalog without access: shows the degraded message and renders no editable cells", async () => {
    const { roleDetail, roleSummary } = buildRole(70);
    mockRoleDetail(roleDetail, permissionsByCode(CONSULTAS_READ));

    const user = setup();
    renderDialog(roleSummary, { canReadPermissionsCatalog: false });
    await openMatrixTab(user);

    expect(
      await screen.findByText(
        "No tienes acceso al catalogo de permisos. Puedes gestionar solo los permisos ya asignados.",
      ),
    ).toBeVisible();
    expect(screen.queryAllByRole("checkbox")).toHaveLength(0);
  });
});
