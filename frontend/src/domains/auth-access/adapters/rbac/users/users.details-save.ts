import type { UpdateUserRequest } from "@api/types";
import type {
  UserOverrideUpsertPayload,
  UserOverridesDiff,
  UserRolesDiff,
} from "@/domains/auth-access/adapters/rbac/users/users.access-draft";

interface UserDetailsSavePlan {
  profilePayload: Partial<UpdateUserRequest>;
  hasStatusChanges: boolean;
  nextIsActive: boolean;
  rolesDiff: UserRolesDiff;
  overridesDiff: UserOverridesDiff;
}

interface UserDetailsSaveExecutors {
  updateProfile: (payload: Partial<UpdateUserRequest>) => Promise<unknown>;
  activateUser: () => Promise<unknown>;
  deactivateUser: () => Promise<unknown>;
  assignRoles: (roleIds: number[]) => Promise<unknown>;
  setPrimaryRole: (roleId: number) => Promise<unknown>;
  revokeRole: (roleId: number) => Promise<unknown>;
  upsertOverride: (payload: UserOverrideUpsertPayload) => Promise<unknown>;
  removeOverride: (permissionCode: string) => Promise<unknown>;
}

export const hasUserDetailsChanges = (plan: UserDetailsSavePlan) => {
  const hasProfileChanges = Object.keys(plan.profilePayload).length > 0;
  const hasRolesChanges =
    plan.rolesDiff.toAdd.length > 0 ||
    plan.rolesDiff.toRemove.length > 0 ||
    plan.rolesDiff.shouldSetPrimary;
  const hasOverridesChanges =
    plan.overridesDiff.toUpsert.length > 0 ||
    plan.overridesDiff.toRemove.length > 0;

  return (
    hasProfileChanges ||
    plan.hasStatusChanges ||
    hasRolesChanges ||
    hasOverridesChanges
  );
};

export const applyUserDetailsSavePlan = async (
  plan: UserDetailsSavePlan,
  executors: UserDetailsSaveExecutors,
) => {
  let completedGroups = 0;

  if (Object.keys(plan.profilePayload).length > 0) {
    await executors.updateProfile(plan.profilePayload);
    completedGroups += 1;
  }

  if (plan.hasStatusChanges) {
    if (plan.nextIsActive) {
      await executors.activateUser();
    } else {
      await executors.deactivateUser();
    }
    completedGroups += 1;
  }

  if (plan.rolesDiff.toAdd.length > 0) {
    await executors.assignRoles(plan.rolesDiff.toAdd);
    completedGroups += 1;
  }

  if (
    plan.rolesDiff.shouldSetPrimary &&
    plan.rolesDiff.primaryRoleId !== null
  ) {
    await executors.setPrimaryRole(plan.rolesDiff.primaryRoleId);
    completedGroups += 1;
  }

  if (plan.rolesDiff.toRemove.length > 0) {
    for (const roleId of plan.rolesDiff.toRemove) {
      await executors.revokeRole(roleId);
    }
    completedGroups += 1;
  }

  if (plan.overridesDiff.toUpsert.length > 0) {
    for (const override of plan.overridesDiff.toUpsert) {
      await executors.upsertOverride(override);
    }
    completedGroups += 1;
  }

  if (plan.overridesDiff.toRemove.length > 0) {
    for (const permissionCode of plan.overridesDiff.toRemove) {
      await executors.removeOverride(permissionCode);
    }
    completedGroups += 1;
  }

  return completedGroups;
};
