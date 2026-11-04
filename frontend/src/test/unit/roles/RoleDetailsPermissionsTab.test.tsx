import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen, within } from "@/test/utils";
import { RoleDetailsPermissionsTab } from "@/domains/auth-access/components/admin/rbac/roles/RoleDetailsPermissionsTab";
import type { Permission, RolePermission } from "@api/types";

const permiso = (id: number, code: string, description: string, dependsOn: string[] = []): Permission => ({
  id,
  code,
  description,
  isSystem: false,
  dependsOn,
});

const CATALOGO: Permission[] = [
  permiso(1, "recepcion:citas:read", "Ver citas"),
  permiso(2, "recepcion:citas:write", "Agendar citas", ["recepcion:citas:read"]),
  permiso(3, "alcance:centros:todos", "Ver y trabajar la información de todos los centros de atención"),
  permiso(4, "clinico:consultas:read", "Ver consultas médicas"),
];

const asignado = (permission: Permission): RolePermission => ({
  id: permission.id,
  code: permission.code,
  description: permission.description,
  assignedAt: "2026-10-30T00:00:00Z",
  assignedBy: { id: 1, name: "Admin" },
});

type Props = Partial<Parameters<typeof RoleDetailsPermissionsTab>[0]>;

describe("RoleDetailsPermissionsTab", () => {
  const onTogglePermissions = vi.fn();

  const renderTab = (props: Props = {}) =>
    render(
      <RoleDetailsPermissionsTab
        permissions={[asignado(CATALOGO[0])]}
        permissionCatalog={CATALOGO}
        isLoadingPermissions={false}
        actorPermissions={["*"]}
        onTogglePermissions={onTogglePermissions}
        {...props}
      />,
    );

  beforeEach(() => {
    onTogglePermissions.mockClear();
  });

  it("agrupa por área con nombres legibles y muestra la descripción como texto principal", () => {
    renderTab();

    expect(screen.getByRole("button", { name: /recepción/i })).toBeVisible();
    expect(screen.getByRole("button", { name: /clínico/i })).toBeVisible();
    expect(screen.getByRole("button", { name: /alcance por centro/i })).toBeVisible();
    expect(screen.getByText("Ver citas")).toBeVisible();
    expect(screen.getByText("recepcion:citas:read")).toBeVisible();
  });

  it("cuenta cuántos permisos tiene el rol", () => {
    renderTab();

    expect(screen.getByText("1 de 4 asignados")).toBeVisible();
  });

  it("al prender un permiso agrega también lo que necesita", async () => {
    const user = userEvent.setup();
    renderTab({ permissions: [] });

    await user.click(screen.getByRole("switch", { name: "Agendar citas" }));

    expect(onTogglePermissions).toHaveBeenCalledTimes(1);
    const [ids, nextChecked] = onTogglePermissions.mock.calls[0];
    expect(nextChecked).toBe(true);
    expect([...ids].sort()).toEqual([1, 2]);
  });

  it("al apagar un permiso lo quita junto con los que dependen de él", async () => {
    const user = userEvent.setup();
    renderTab({ permissions: [asignado(CATALOGO[0]), asignado(CATALOGO[1])] });

    await user.click(screen.getByRole("switch", { name: "Ver citas" }));

    const [ids, nextChecked] = onTogglePermissions.mock.calls[0];
    expect(nextChecked).toBe(false);
    expect([...ids].sort()).toEqual([1, 2]);
  });

  it("prende de una vez todos los permisos de un área", async () => {
    const user = userEvent.setup();
    renderTab({ permissions: [] });

    await user.click(screen.getByRole("checkbox", { name: "Todos los permisos de Recepción" }));

    const [ids, nextChecked] = onTogglePermissions.mock.calls[0];
    expect(nextChecked).toBe(true);
    expect([...ids].sort()).toEqual([1, 2]);
  });

  it("busca por descripción sin importar acentos ni mayúsculas", async () => {
    const user = userEvent.setup();
    renderTab();

    await user.type(screen.getByRole("searchbox", { name: "Buscar permiso" }), "MEDICAS");

    expect(screen.getByText("Ver consultas médicas")).toBeVisible();
    expect(screen.queryByText("Ver citas")).toBeNull();
  });

  it("avisa cuando la búsqueda no encuentra nada", async () => {
    const user = userEvent.setup();
    renderTab();

    await user.type(screen.getByRole("searchbox", { name: "Buscar permiso" }), "inexistente");

    expect(screen.getByText(/no hay permisos que coincidan/i)).toBeVisible();
  });

  it("filtra los que faltan asignar", async () => {
    const user = userEvent.setup();
    renderTab();

    await user.click(screen.getByRole("button", { name: "Sin asignar" }));

    expect(screen.queryByText("Ver citas")).toBeNull();
    expect(screen.getByText("Agendar citas")).toBeVisible();
  });

  it("marca como sensibles los permisos que amplían el alcance", () => {
    renderTab();

    const fila = screen.getByText("Ver y trabajar la información de todos los centros de atención").closest("li");
    expect(fila).not.toBeNull();
    expect(within(fila as HTMLElement).getByText("Sensible")).toBeVisible();
  });

  it("bloquea los permisos que quien edita no tiene", () => {
    renderTab({ actorPermissions: ["recepcion:citas:read"] });

    expect(screen.getByRole("switch", { name: "Ver citas" })).toBeEnabled();
    expect(screen.getByRole("switch", { name: "Agendar citas" })).toBeDisabled();
  });

  it("rol administrador: todo prendido, bloqueado y con su leyenda", () => {
    renderTab({ permissions: [], isAdmin: true, isEditable: false });

    expect(screen.getByText(/acceso total automatico/i)).toBeVisible();
    expect(screen.queryByText(/solo lectura/i)).toBeNull();
    for (const sw of screen.getAllByRole("switch")) {
      expect(sw).toBeChecked();
      expect(sw).toBeDisabled();
    }
  });

  it("solo lectura: avisa y bloquea los switches", () => {
    renderTab({ isEditable: false });

    expect(screen.getByText("Solo lectura: no puedes actualizar este rol porque no tienes permisos.")).toBeVisible();
    for (const sw of screen.getAllByRole("switch")) expect(sw).toBeDisabled();
  });

  it("error del catálogo: lo muestra y bloquea los cambios", () => {
    renderTab({ catalogErrorMessage: "No se pudo cargar el catalogo" });

    expect(screen.getByText("No se pudo cargar el catalogo")).toBeVisible();
    for (const sw of screen.getAllByRole("switch")) expect(sw).toBeDisabled();
  });

  it("sin acceso al catálogo: muestra ese contexto en vez del error y deja quitar lo asignado", async () => {
    const user = userEvent.setup();
    renderTab({
      permissionCatalog: [],
      catalogAccessMessage: "No tienes acceso al catalogo de permisos.",
      catalogErrorMessage: "No se pudo cargar el catalogo",
    });

    expect(screen.getByText("No tienes acceso al catalogo de permisos.")).toBeVisible();
    expect(screen.queryByText("No se pudo cargar el catalogo")).toBeNull();

    await user.click(screen.getByRole("switch", { name: "Ver citas" }));

    expect(onTogglePermissions).toHaveBeenCalledWith([1], false);
  });

  it("muestra skeletons mientras carga", () => {
    const { container } = renderTab({ isLoadingPermissions: true });

    expect(container.querySelectorAll(".animate-pulse").length).toBeGreaterThan(0);
  });
});
