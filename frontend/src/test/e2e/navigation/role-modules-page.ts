import { expect, type Page } from "@playwright/test";

interface LoginCredentials {
  username: string;
  password: string;
}

const ROLE_DETAILS_DIALOG_NAME = "Detalle de rol";
const IMPACT_DIALOG_NAME_PATTERN = /Efecto colateral/i;

/**
 * Page Object para el flujo "admin tilda/destilda un modulo en un rol"
 * dentro del detalle de rol (`RoleDetailsDialog` -> tab "Permisos por
 * modulo" -> `RolePermissionMatrixTab`), usado por el E2E de la tarea 7.1 de
 * `menu-modulos-rol-ui`: tildar un modulo en un rol lo hace aparecer en el
 * sidebar de un usuario con ese rol.
 *
 * Convenciones tomadas de `rbac-page.ts` (mismo selector de login,
 * `openRoleDetails`/`expectToastContains`) y de `navigation-menu-page.ts`
 * (Page Object standalone sin estado compartido con otras clases, mismo
 * estilo de comentarios explicando decisiones no obvias).
 */
export class RoleModulesPage {
  constructor(private readonly page: Page) {}

  get loginUsernameInput() {
    return this.page.getByLabel("No. Expediente o Usuario");
  }

  get loginPasswordInput() {
    return this.page.locator("input#password");
  }

  get loginButton() {
    return this.page.getByRole("button", { name: "Iniciar Sesión" });
  }

  get roleDetailsDialog() {
    return this.page.getByRole("dialog", { name: ROLE_DETAILS_DIALOG_NAME });
  }

  get impactDialog() {
    return this.page.getByRole("alertdialog", {
      name: IMPACT_DIALOG_NAME_PATTERN,
    });
  }

  async gotoLogin() {
    await this.page.goto("/login");
    await expect(this.loginUsernameInput).toBeVisible();
  }

  async login(credentials: LoginCredentials) {
    await this.gotoLogin();
    await this.loginUsernameInput.fill(credentials.username);
    await this.loginPasswordInput.fill(credentials.password);
    await this.loginButton.click();
    await this.page.waitForURL((url) => !url.pathname.includes("/login"), {
      timeout: 20000,
      waitUntil: "networkidle",
    });
  }

  async expandAdminPanel() {
    const panelButton = this.page.getByRole("button", { name: "Panel" });
    await expect(panelButton).toBeVisible();
    const isExpanded =
      (await panelButton.getAttribute("aria-expanded")) === "true";

    if (!isExpanded) {
      await panelButton.click();
    }
  }

  async navigateToRoles() {
    await this.expandAdminPanel();
    await this.page.getByRole("link", { name: /^Roles/ }).click();
    await expect(
      this.page.getByRole("heading", { name: "Roles" }),
    ).toBeVisible();
  }

  async openRoleDetails(roleName: string) {
    const row = this.page
      .getByRole("row", { name: new RegExp(roleName, "i") })
      .first();
    await expect(row).toBeVisible();
    await row.click();

    if (!(await this.roleDetailsDialog.isVisible({ timeout: 1500 }))) {
      await row.getByRole("button", { name: "Acciones" }).click();
      await this.page.getByRole("menuitem", { name: "Ver detalles" }).click();
    }

    await expect(this.roleDetailsDialog).toBeVisible();
  }

  async openModulesTab() {
    await this.roleDetailsDialog
      .getByRole("tab", { name: /Permisos por m[oó]dulo/i })
      .click();
  }

  /**
   * En la matriz, "tildar un modulo" equivale a tildar la celda "Ver" de su
   * fila: el aria-label es `"{Accion} {recurso} en {modulo}"` (ej. "Ver
   * usuarios en Usuarios"). Las celdas de escritura y los tri-estado de
   * fila/seccion no empiezan con "Ver ", asi que el patron es inequivoco.
   */
  moduleCheckbox(moduleTitle: string) {
    const escapedTitle = moduleTitle.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    return this.roleDetailsDialog.getByRole("checkbox", {
      name: new RegExp(`^Ver .+ en ${escapedTitle}$`, "i"),
    });
  }

  /**
   * Tilda/destilda un modulo por su titulo SOLO si su estado actual difiere
   * del deseado (idempotente -- si una corrida previa dejo el estado sucio
   * por un fallo a mitad de camino, este helper lo detecta solo y no
   * vuelve a clickear en la direccion equivocada). Devuelve `true` si hizo
   * falta un click, para que el caller sepa si debe guardar.
   *
   * Si el modulo comparte permiso con otros nodos del arbol,
   * `RolePermissionMatrixTab` abre `ModuleImpactDialog` ANTES de mutar el
   * draft -- este helper lo confirma automaticamente si aparece. El
   * modulo "Usuarios" usado en el spec no tiene colaterales (es el unico
   * nodo del seed con el permiso `admin:gestion:usuarios:read`), pero se
   * deja generico por si el arbol de navegacion cambia.
   */
  async setModuleChecked(
    moduleTitle: string,
    checked: boolean,
  ): Promise<boolean> {
    const checkbox = this.moduleCheckbox(moduleTitle);
    await expect(checkbox).toBeVisible({ timeout: 10000 });

    const isChecked = await checkbox.isChecked();
    if (isChecked === checked) return false;

    await checkbox.click();

    if (await this.impactDialog.isVisible({ timeout: 1000 })) {
      await this.impactDialog
        .getByRole("button", { name: "Confirmar" })
        .click();
    }

    return true;
  }

  async saveRoleDetails() {
    await this.roleDetailsDialog
      .getByRole("button", { name: "Guardar" })
      .click();
  }

  async expectToastContains(text: string) {
    const toast = this.page
      .locator("[data-sonner-toast]")
      .filter({ hasText: text })
      .first();
    await expect(toast).toBeVisible({ timeout: 10000 });
  }
}
