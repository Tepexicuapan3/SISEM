import { beforeEach, describe, expect, it } from "vitest";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { render, screen, waitFor } from "@/test/utils";
import { server } from "@/test/mocks/server";
import { getApiUrl } from "@/test/mocks/urls";
import { setMockSessionUser } from "@/test/mocks/session";
import { createMockAuthUser } from "@/test/factories/users";
import {
  createMockRoleDetail,
  createMockRoleListItem,
  createMockRolePermission,
} from "@/test/factories/roles";
import { RolePreviewPanel } from "@features/admin/modules/menus/components/RolePreviewPanel";
import type { NavigationMenuResponse } from "@api/types/navigation.types";
import type { RoleListItem } from "@api/types";

/**
 * Tests de integracion de Fase 7 (`RolePreviewPanel`, "Ver el menu como").
 * Monta el componente REAL con hooks REALES (`useRolesList`, `useRoleDetail`,
 * `useNavigationMenu`) contra MSW -- misma estrategia que
 * `RolePermissionMatrixTab.ui.test.tsx`. `filterNavigation` en si ya tiene
 * cobertura unitaria propia; lo que se prueba aca es el WIRING: que el rol
 * elegido se traduce correctamente en el arbol filtrado, incluyendo el caso
 * `isAdmin` (D5/design de `menu-modulos-crud-ui`).
 */

const grantedCapability = () => ({
  granted: true,
  missingAllOf: [] as string[],
  missingAnyOf: [] as string[],
});

const seedSession = () => {
  setMockSessionUser(
    createMockAuthUser({
      username: "menus_preview_tester",
      permissions: ["*"],
      capabilities: {
        "admin.roles.read": grantedCapability(),
        "admin.menus.read": grantedCapability(),
      },
    }),
  );
};

const buildNavigationMenu = (): NavigationMenuResponse => ({
  source: "db",
  sections: [
    {
      title: "Clinico",
      permissions: ["clinico:acceso"],
      items: [
        {
          title: "Consultas",
          icon: null,
          url: "/clinico/consultas",
          badge: null,
          permissions: ["clinico:consultas:read"],
        },
        {
          title: "Reportes",
          icon: null,
          url: "/clinico/reportes",
          badge: null,
          permissions: ["clinico:reportes:read"],
        },
      ],
    },
  ],
  secondaryItems: [],
});

const mockNavigationMenu = () => {
  server.use(
    http.get(getApiUrl("navigation-menu"), () => {
      return HttpResponse.json(buildNavigationMenu());
    }),
  );
};

const mockRoles = (roles: RoleListItem[]) => {
  server.use(
    http.get(getApiUrl("roles"), () => {
      return HttpResponse.json({
        items: roles,
        page: 1,
        pageSize: 100,
        total: roles.length,
        totalPages: 1,
      });
    }),
  );
};

const selectRole = async (
  user: ReturnType<typeof userEvent.setup>,
  roleName: string,
) => {
  await user.click(await screen.findByRole("combobox"));
  await user.click(await screen.findByText(roleName));
};

describe("RolePreviewPanel integration (MSW)", () => {
  beforeEach(() => {
    seedSession();
    mockNavigationMenu();
  });

  it("admin role (isAdmin=true): shows the full tree even with zero RelRolPermiso rows", async () => {
    const adminRole = createMockRoleListItem({
      id: 201,
      name: "Admin Total",
      isSystem: true,
      isAdmin: true,
    });
    mockRoles([adminRole]);
    server.use(
      http.get(getApiUrl("roles/:id"), () => {
        return HttpResponse.json({
          role: createMockRoleDetail(adminRole),
          // RelRolPermiso vacio -- el resolver le da acceso via wildcard,
          // no via estas filas (ver sires/rbac/admin-role-ui-display-fix).
          permissions: [],
        });
      }),
    );

    const user = userEvent.setup();
    render(<RolePreviewPanel />);

    await selectRole(user, "Admin Total");

    await waitFor(() => {
      expect(screen.getByText("Consultas")).toBeInTheDocument();
    });
    expect(screen.getByText("Reportes")).toBeInTheDocument();
    expect(screen.getByText("Clinico")).toBeInTheDocument();
  });

  it("role with partial permissions: shows only the subset it can see", async () => {
    const partialRole = createMockRoleListItem({
      id: 202,
      name: "Clinico Parcial",
      isSystem: false,
      isAdmin: false,
    });
    mockRoles([partialRole]);
    server.use(
      http.get(getApiUrl("roles/:id"), () => {
        return HttpResponse.json({
          role: createMockRoleDetail(partialRole),
          permissions: [
            createMockRolePermission({ code: "clinico:acceso" }),
            createMockRolePermission({ code: "clinico:consultas:read" }),
          ],
        });
      }),
    );

    const user = userEvent.setup();
    render(<RolePreviewPanel />);

    await selectRole(user, "Clinico Parcial");

    await waitFor(() => {
      expect(screen.getByText("Consultas")).toBeInTheDocument();
    });
    expect(screen.getByText("Clinico")).toBeInTheDocument();
    expect(screen.queryByText("Reportes")).not.toBeInTheDocument();
  });
});
