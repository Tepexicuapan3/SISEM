export {
  formatDate,
  formatDateTime,
} from "@/domains/auth-access/adapters/rbac/shared/rbac-format";

const USER_UI_STATUS = {
  PENDING: "pending",
  ACTIVE: "active",
  INACTIVE: "inactive",
} as const;

type UserUiStatus = (typeof USER_UI_STATUS)[keyof typeof USER_UI_STATUS];

interface UserStatusSource {
  isActive?: boolean;
  termsAccepted?: boolean;
  mustChangePassword?: boolean;
}

// La baja tiene prioridad: un usuario inactivo nunca se muestra como
// pendiente aunque aun no haya cambiado su clave ni aceptado terminos
// (caso tipico: importado por Excel con Estado "Dado de baja").
export const resolveUserUiStatus = (user: UserStatusSource): UserUiStatus => {
  if (!user.isActive) {
    return USER_UI_STATUS.INACTIVE;
  }

  if (user.mustChangePassword || user.termsAccepted === false) {
    return USER_UI_STATUS.PENDING;
  }

  return USER_UI_STATUS.ACTIVE;
};
