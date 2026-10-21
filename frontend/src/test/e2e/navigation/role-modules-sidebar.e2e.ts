import { expect, test } from "@playwright/test";
import { NavigationMenuPage } from "./navigation-menu-page";
import { RoleModulesPage } from "./role-modules-page";

/**
 * E2E: menu-modulos-rol-ui (change `menu-modulos-rol-ui`, Fase 7 / tarea
 * 7.1). Cubre `sdd/menu-modulos-rol-ui/tasks` 7.1: "admin tilda un modulo
 * en un rol -> un usuario con ese rol lo ve en su sidebar".
 *
 * ══════════════════════════════════════════════════════════════════════
 * LIMITACIONES DOCUMENTADAS (leer antes de correr o extender este spec)
 * ══════════════════════════════════════════════════════════════════════
 *
 * 1. Igual que `navigation-menu.e2e.ts` (change `menu-modulos`, limitacion
 *    #1): el flag `NAVIGATION_MENU_SOURCE`/`NAVIGATION_MENU_DB_ENABLED` se
 *    lee UNA VEZ al arrancar el proceso Django (`config/settings.py`) -- no
 *    hay forma de togglearlo desde un test Playwright. Este spec verifica
 *    el flag ANTES de mutar nada (login real como `admin_roles`, lee el
 *    `source` que YA esta sirviendo el backend) y hace `test.skip()` con
 *    motivo explicito si no es `"db"`. Asi nunca se muta el rol sembrado
 *    si el test va a saltearse de todas formas -- evita dejar estado sucio
 *    en una corrida que no iba a verificar nada igual. El endpoint
 *    `GET /api/v1/modules` (catalogo de modulos de la tab "Permisos por modulo") NO
 *    depende de este flag -- siempre devuelve el arbol completo -- pero el
 *    SIDEBAR (`GET /api/v1/navigation-menu`) si depende de el.
 *
 * 2. "Un usuario con ese rol" se resuelve con la cuenta YA sembrada por
 *    `backend/seed_e2e.py` para el rol no-sistema `ADMIN_ROLES`
 *    (`desc_rol="Admin Roles"`): el usuario `admin_roles`
 *    (password `Sisem_123456`, la misma que usan `admin` y el resto de
 *    las cuentas de `seed_e2e.py`). No se inventa una cuenta nueva ni un
 *    mecanismo de "loguearse como el rol recien creado" -- ese rol YA
 *    tiene un usuario real y versionado en el seed. A diferencia del
 *    "usuario minimo/override" del E2E anterior (`navigation-menu.e2e.ts`,
 *    limitacion #3), aca SI hay una cuenta anclada en codigo del repo, asi
 *    que no hace falta gatear por env vars ni saltear ese aspecto.
 *
 * 3. El modulo elegido para tildar es "Usuarios"
 *    (`administracion.panel.usuarios`, permiso `admin:gestion:usuarios:read`
 *    en `backend/apps/administracion/management/seeds/navigation_seed.py`)
 *    porque el rol `ADMIN_ROLES` NO lo tiene en su set de permisos
 *    sembrado (`admin:gestion:roles:*` + `admin:gestion:permisos:read`,
 *    ver `ROLE_DEFS` en `seed_e2e.py`) y porque es el UNICO nodo del arbol
 *    que declara ese codigo de permiso -- tildarlo no dispara
 *    `ModuleImpactDialog` (sin colaterales), lo que simplifica el flujo
 *    principal. En la matriz "tildar el modulo" es tildar la celda
 *    "Ver usuarios en Usuarios" (ver `RoleModulesPage.moduleCheckbox`). `RoleModulesPage.setModuleChecked` igual maneja el dialogo
 *    si aparece, para no romper si el seed cambia y el permiso pasa a
 *    compartirse con otro nodo.
 *
 * 4. Este spec MUTA un rol sembrado real (`ADMIN_ROLES`) contra un backend
 *    real -- no es un fixture descartable como los roles que crea
 *    `rbac.e2e.ts` (`RBAC_E2E_ROLE_${Date.now()}`), porque ese spec corre
 *    contra el mock server MSW de `localhost:5000`, no contra Django real.
 *    Por eso el test revierte el cambio en un bloque `finally` (vuelve a
 *    destildar "Usuarios" y guarda) para dejar el rol como lo dejo el
 *    seed, incluso si la aserción del sidebar falla a mitad de camino.
 *    `setModuleChecked` es idempotente: si una corrida previa fallo antes
 *    de poder revertir, la siguiente corrida detecta el estado sucio (el
 *    checkbox ya tildado) y lo corrige sola en vez de asumir un estado
 *    inicial fijo.
 */

const TEST_PASSWORD = "Sisem_123456";
const TARGET_ROLE_NAME = "Admin Roles";
const TARGET_MODULE_TITLE = "Usuarios";
const TARGET_MODULE_HREF = "/admin/usuarios";

test.describe("Modulos por rol reflejados en el sidebar del usuario (tarea 7.1)", () => {
  test(
    "tildar un modulo en un rol lo hace aparecer en el sidebar de un usuario con ese rol",
    { tag: ["@e2e", "@navigation", "@rbac", "@modules-per-role"] },
    async ({ page, browser }) => {
      const navPage = new NavigationMenuPage(page);

      const realPayload = await navPage.loginAndCaptureMenuResponse({
        username: "admin_roles",
        password: TEST_PASSWORD,
      });

      test.skip(
        realPayload.source !== "db",
        `El backend respondio source="${realPayload.source}" (no "db"). ` +
          "Este entorno no tiene el flag de navegacion activo en BD y no hay forma de " +
          "togglearlo desde el test (ver limitacion #1 en el encabezado del spec). " +
          "Levantar el backend con NAVIGATION_MENU_SOURCE=db para correr esta prueba.",
      );

      const beforeLinks = await navPage.getSidebarLinks();
      expect(
        beforeLinks.some((link) => link.href === TARGET_MODULE_HREF),
        `Precondicion: el rol "${TARGET_ROLE_NAME}" no deberia tener ` +
          `"${TARGET_MODULE_TITLE}" visible todavia (ver limitacion #3). Si esto falla, ` +
          "una corrida anterior dejo el rol sucio -- el bloque de reversion de este " +
          `mismo spec deberia haberlo corregido; revisar manualmente el rol ` +
          `"${TARGET_ROLE_NAME}" en /admin/roles.`,
      ).toBe(false);

      // Sesion separada para el admin que edita el rol, para no pisar la
      // cookie de sesion de `admin_roles` ya capturada en `page`.
      const adminContext = await browser.newContext();
      const adminPage = await adminContext.newPage();
      const rolesPage = new RoleModulesPage(adminPage);

      await rolesPage.login({ username: "admin", password: TEST_PASSWORD });
      await rolesPage.navigateToRoles();

      try {
        await rolesPage.openRoleDetails(TARGET_ROLE_NAME);
        await rolesPage.openModulesTab();
        await rolesPage.setModuleChecked(TARGET_MODULE_TITLE, true);
        await rolesPage.saveRoleDetails();
        await rolesPage.expectToastContains("Cambios guardados");

        await page.reload({ waitUntil: "networkidle" });
        const afterLinks = await navPage.getSidebarLinks();

        expect(
          afterLinks.some(
            (link) =>
              link.href === TARGET_MODULE_HREF &&
              link.title === TARGET_MODULE_TITLE,
          ),
          `El sidebar de "admin_roles" deberia mostrar "${TARGET_MODULE_TITLE}" ` +
            "despues de que el admin lo tildo en el rol y guardo, sin build/deploy.",
        ).toBe(true);
      } finally {
        // Navegacion fresca antes de revertir: el dialogo puede haber
        // quedado abierto, cerrado, o a mitad de un tab dependiendo de en
        // que punto fallo el bloque `try` -- `goto` normaliza el punto de
        // partida sin importar donde se corto.
        await adminPage.goto("/admin/roles");
        await expect(
          adminPage.getByRole("heading", { name: "Roles" }),
        ).toBeVisible();

        await rolesPage.openRoleDetails(TARGET_ROLE_NAME);
        await rolesPage.openModulesTab();
        const reverted = await rolesPage.setModuleChecked(
          TARGET_MODULE_TITLE,
          false,
        );

        if (reverted) {
          await rolesPage.saveRoleDetails();
          await rolesPage.expectToastContains("Cambios guardados");
        }

        await adminContext.close();
      }
    },
  );
});
