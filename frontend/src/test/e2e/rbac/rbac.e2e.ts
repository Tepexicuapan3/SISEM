import { expect, test } from "@playwright/test";
import { RbacPage } from "./rbac-page";

const TEST_PASSWORD = "Sisem_123456";

test.describe("RBAC UI (MSW)", () => {
  test.describe.configure({ mode: "serial" });

  test.beforeEach(async ({ page }) => {
    await page.goto("/login");

    const response = await page.evaluate(async () => {
      for (let attempt = 0; attempt < 20; attempt += 1) {
        try {
          const request = await fetch(
            "http://localhost:5000/api/v1/auth/test-reset-state",
            {
              method: "POST",
              credentials: "include",
            },
          );

          return {
            ok: request.ok || request.status === 404,
            status: request.status,
          };
        } catch {
          await new Promise((resolve) => {
            setTimeout(resolve, 250);
          });
        }
      }

      return {
        ok: false,
        status: 0,
      };
    });

    expect(response.ok).toBeTruthy();
  });

  test(
    "RBAC-E2E-001 creates role and shows duplicate error",
    { tag: ["@critical", "@e2e", "@rbac", "@roles", "@RBAC-E2E-001"] },
    async ({ page }) => {
      const rbacPage = new RbacPage(page);
      const roleName = `RBAC_E2E_ROLE_${Date.now()}`;

      await rbacPage.login({
        username: "admin_roles_manager",
        password: TEST_PASSWORD,
      });
      await rbacPage.navigateToRoles();
      await rbacPage.openRoleCreateDialog();

      const dialog = page.getByRole("dialog", { name: "Nuevo rol" });
      await dialog.getByLabel("Nombre del rol").fill(roleName);
      await dialog.getByLabel("Descripcion").fill("Rol de prueba E2E");
      await dialog.getByLabel("Landing route").fill("/admin/roles");
      await dialog.getByRole("button", { name: "Crear rol" }).click();

      await expect(dialog.getByText("Rol creado")).toBeVisible();
      await rbacPage.expectToastContains("Rol creado");

      await dialog.getByLabel("Nombre del rol").fill(roleName);
      await dialog.getByLabel("Descripcion").fill("Rol duplicado");
      await dialog.getByRole("button", { name: "Crear rol" }).click();

      await rbacPage.expectToastContains("Ya existe un rol con ese nombre.");
    },
  );

  test(
    "RBAC-E2E-002 blocks invalid read permission removal dependencies",
    { tag: ["@high", "@e2e", "@rbac", "@roles", "@RBAC-E2E-002"] },
    async ({ page }) => {
      const rbacPage = new RbacPage(page);

      await rbacPage.login({
        username: "admin_roles_manager",
        password: TEST_PASSWORD,
      });
      await rbacPage.navigateToRoles();

      const seedStatus = await page.evaluate(async () => {
        const response = await fetch(
          "http://localhost:5000/api/v1/permissions/assign",
          {
            method: "POST",
            credentials: "include",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              roleId: 6,
              permissionIds: [5, 6, 7],
            }),
          },
        );

        return response.status;
      });

      expect(seedStatus).toBe(200);
      await rbacPage.openRoleDetails("Auditoria");

      const dialog = page.getByRole("dialog", { name: "Detalle de rol" });
      await dialog.getByRole("tab", { name: /^Permisos(?!\s+por)/i }).click();
      await dialog
        .getByRole("button", {
          name: "Remover permiso admin:gestion:roles:read",
        })
        .click();

      await rbacPage.expectToastContains(
        "No puedes revocar :read mientras existan permisos de escritura del mismo recurso.",
      );
    },
  );

  test(
    "RBAC-E2E-003 shows explicit catalog error for readonly role manager",
    { tag: ["@high", "@e2e", "@rbac", "@roles", "@RBAC-E2E-003"] },
    async ({ page }) => {
      const rbacPage = new RbacPage(page);

      await rbacPage.login({
        username: "admin_roles_readonly",
        password: TEST_PASSWORD,
      });
      await rbacPage.navigateToRoles();
      await rbacPage.openRoleDetails("Auditoria");

      const dialog = page.getByRole("dialog", { name: "Detalle de rol" });
      await expect(
        dialog.getByText(
          "Solo lectura: no puedes actualizar este rol porque es de sistema o no tienes permisos.",
        ),
      ).toBeVisible();

      await dialog.getByRole("tab", { name: /^Permisos(?!\s+por)/i }).click();
      await expect(
        dialog.getByText(
          "Solo lectura: no puedes actualizar este rol porque es de sistema o no tienes permisos.",
        ),
      ).toBeVisible();
      await expect(
        dialog.getByText("No hay permisos disponibles para agregar."),
      ).toBeVisible();
    },
  );

  test(
    "RBAC-E2E-004 enforces readonly users detail when update permission is missing",
    { tag: ["@critical", "@e2e", "@rbac", "@users", "@RBAC-E2E-004"] },
    async ({ page }) => {
      const rbacPage = new RbacPage(page);

      await rbacPage.login({
        username: "admin_usuarios_readonly",
        password: TEST_PASSWORD,
      });
      await rbacPage.navigateToUsers();

      await expect(page.getByRole("button", { name: "Nuevo" })).toHaveCount(0);

      await rbacPage.openFirstUserDetails();

      const dialog = page.getByRole("dialog", { name: "Detalle de usuario" });
      await expect(
        dialog.getByText(
          "Solo lectura: no puedes actualizar este usuario porque no tienes permisos.",
        ),
      ).toBeVisible();
      await expect(dialog.getByLabel("Correo")).toBeDisabled();
      await expect(
        dialog.getByRole("button", { name: "Guardar" }),
      ).toBeDisabled();

      await dialog.getByRole("tab", { name: /^Roles/ }).click();
      await expect(
        dialog.getByRole("button", { name: "Agregar" }),
      ).toBeDisabled();

      await dialog.getByRole("tab", { name: /^Permisos(?!\s+por)/ }).click();
      await expect(
        dialog.getByText(
          "Solo lectura: no puedes actualizar este usuario porque no tienes permisos.",
        ),
      ).toBeVisible();
      await expect(
        dialog.getByText("No hay permisos disponibles para agregar override."),
      ).toBeVisible();
    },
  );

  test(
    "RBAC-E2E-005 creates user and shows explicit duplicate error",
    { tag: ["@critical", "@e2e", "@rbac", "@users", "@RBAC-E2E-005"] },
    async ({ page }) => {
      const rbacPage = new RbacPage(page);
      const username = `rbac_ui_${Date.now()}`;
      const email = `${username}@metro.cdmx.gob.mx`;

      await rbacPage.login({ username: "admin", password: TEST_PASSWORD });
      await rbacPage.navigateToUsers();
      await rbacPage.openUserCreateDialog();

      const dialog = page.getByRole("dialog", { name: "Nuevo usuario" });
      await dialog.getByLabel("Nombre").fill("Rbac");
      await dialog.getByLabel("Apellido paterno").fill("E2E");
      await dialog.getByLabel("Apellido materno").fill("Tests");
      await dialog.getByLabel("Correo").fill(email);
      await dialog.getByLabel("Usuario").fill(username);

      const roleCombobox = dialog.getByRole("combobox", {
        name: "Rol primario",
      });
      await roleCombobox.click();
      await page.keyboard.press("ArrowDown");
      await page.keyboard.press("Enter");
      await expect(roleCombobox).not.toContainText("Selecciona un rol");

      await dialog.getByRole("button", { name: "Crear usuario" }).click();

      await expect(dialog.getByText("Acceso generado")).toBeVisible();
      await expect(dialog.getByText(username)).toBeVisible();
      await expect(dialog.getByText("TempPassword123!")).toBeVisible();

      await dialog.getByLabel("Nombre").fill("Rbac");
      await dialog.getByLabel("Apellido paterno").fill("E2E");
      await dialog.getByLabel("Apellido materno").fill("Tests");
      await dialog.getByLabel("Correo").fill(email);
      await dialog.getByLabel("Usuario").fill(username);

      await roleCombobox.click();
      await page.keyboard.press("ArrowDown");
      await page.keyboard.press("Enter");
      await expect(roleCombobox).not.toContainText("Selecciona un rol");

      await dialog.getByRole("button", { name: "Crear usuario" }).click();
      await rbacPage.expectToastContains(
        "El usuario o el correo ya estan registrados.",
      );
    },
  );

  test(
    "RBAC-E2E-006 adds and removes user overrides",
    { tag: ["@high", "@e2e", "@rbac", "@users", "@RBAC-E2E-006"] },
    async ({ page }) => {
      const rbacPage = new RbacPage(page);

      await rbacPage.login({ username: "admin", password: TEST_PASSWORD });
      await rbacPage.navigateToUsers();
      await rbacPage.openFirstUserDetails();

      const dialog = page.getByRole("dialog", { name: "Detalle de usuario" });
      await dialog.getByRole("tab", { name: /^Permisos(?!\s+por)/ }).click();

      await dialog
        .getByRole("button", {
          name: "Agregar override admin:gestion:usuarios:read",
        })
        .click();
      await rbacPage.expectToastContains("Override agregado");

      await dialog
        .getByRole("button", { name: /Eliminar override/ })
        .first()
        .click();
      await rbacPage.expectToastContains("Override eliminado");
    },
  );

  test(
    "RBAC-E2E-007 redirects to login when session expires in user detail flow",
    { tag: ["@high", "@e2e", "@rbac", "@users", "@RBAC-E2E-007"] },
    async ({ page }) => {
      const rbacPage = new RbacPage(page);

      await rbacPage.login({ username: "admin", password: TEST_PASSWORD });
      await rbacPage.navigateToUsers();

      await page.evaluate(async () => {
        await fetch("http://localhost:5000/api/v1/auth/logout", {
          method: "POST",
          credentials: "include",
        });
      });

      await page.locator("tbody tr").first().click();

      await expect(page).toHaveURL(/\/login$/);
      await rbacPage.expectToastContains(
        "Tu sesión ha expirado. Por favor ingresa nuevamente.",
      );
    },
  );

  test(
    "RBAC-E2E-008 keeps clean detail state and blocks self deactivation",
    { tag: ["@critical", "@e2e", "@rbac", "@users", "@RBAC-E2E-008"] },
    async ({ page }) => {
      const rbacPage = new RbacPage(page);

      await rbacPage.login({ username: "admin", password: TEST_PASSWORD });
      await rbacPage.navigateToUsers();

      await page.getByPlaceholder("Buscar en la tabla").fill("admin");

      const adminRow = page.getByRole("row", { name: /\badmin\b/i }).first();
      await expect(adminRow).toBeVisible();
      await adminRow.click();

      const dialog = page.getByRole("dialog", { name: "Detalle de usuario" });
      await expect(dialog).toBeVisible();
      await expect(dialog.getByText("Sin cambios")).toBeVisible();
      await expect(
        dialog.getByRole("combobox", { name: "Estado de la cuenta" }),
      ).toHaveCount(0);
      await dialog.getByRole("tab", { name: /Seguridad/i }).click();
      await expect(
        dialog.getByRole("button", { name: "Desactivar" }),
      ).toHaveCount(0);
      await expect(
        dialog.getByRole("button", { name: "Generar y mostrar" }),
      ).toHaveCount(0);

      await page.keyboard.press("Escape");
      await expect(dialog).not.toBeVisible();
      await expect(
        page.getByRole("alertdialog", { name: "Salir sin guardar" }),
      ).toHaveCount(0);
    },
  );
});
