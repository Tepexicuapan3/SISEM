import { useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  ShieldAlert,
  ShieldCheck,
  UserRound,
} from "lucide-react";
import { useForm, type Resolver } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import { Skeleton } from "@shared/ui/skeleton";
import { usePermissionsCatalog } from "@/domains/auth-access/hooks/rbac/permissions/usePermissionsCatalog";
import { UserDetailsFooter } from "@/domains/auth-access/components/admin/rbac/users/UserDetailsFooter";
import { UserDetailsGeneralTab } from "@/domains/auth-access/components/admin/rbac/users/UserDetailsGeneralTab";
import { UserDetailsPermissionsTab } from "@/domains/auth-access/components/admin/rbac/users/UserDetailsPermissionsTab";
import { UserDetailsRolesTab } from "@/domains/auth-access/components/admin/rbac/users/UserDetailsRolesTab";
import { UserDetailsSidePanel } from "@/domains/auth-access/components/admin/rbac/users/UserDetailsSidePanel";
import { UserDialogHeader } from "@/domains/auth-access/components/admin/rbac/users/UserDialogHeader";
import {
  userDetailsSchema,
  type UserDetailsFormValues,
} from "@/domains/auth-access/types/rbac/users.schemas";
import { useAddUserOverride } from "@/domains/auth-access/hooks/rbac/users/useAddUserOverride";
import { useActivateUser } from "@/domains/auth-access/hooks/rbac/users/useActivateUser";
import { useAssignRoles } from "@/domains/auth-access/hooks/rbac/users/useAssignRoles";
import { useDeactivateUser } from "@/domains/auth-access/hooks/rbac/users/useDeactivateUser";
import { useRemoveUserOverride } from "@/domains/auth-access/hooks/rbac/users/useRemoveUserOverride";
import { useRevokeUserRole } from "@/domains/auth-access/hooks/rbac/users/useRevokeUserRole";
import { useSetPrimaryRole } from "@/domains/auth-access/hooks/rbac/users/useSetPrimaryRole";
import { useUpdateUser } from "@/domains/auth-access/hooks/rbac/users/useUpdateUser";
import { useUserDetail } from "@/domains/auth-access/hooks/rbac/users/useUserDetail";
import {
  areUserOverridesEquivalent,
  areUserRolesEquivalent,
  buildUserOverridesDiff,
  buildUserRolesDiff,
} from "@/domains/auth-access/adapters/rbac/users/users.access-draft";
import {
  buildUserProfilePayload,
  addOverrideToDraft,
  addRoleToDraft,
  hasUserProfileChanges,
  mapUserDetailToFormValues,
  removeOverrideFromDraft,
  removeRoleFromDraft,
  setOverrideDateInDraft,
  setPrimaryRoleInDraft,
  toggleOverrideEffectInDraft,
} from "@/domains/auth-access/adapters/rbac/users/users.details-draft";
import { getUserErrorMessage } from "@/domains/auth-access/adapters/rbac/users/users.feedback";
import {
  applyUserDetailsSavePlan,
  hasUserDetailsChanges,
} from "@/domains/auth-access/adapters/rbac/users/users.details-save";
import {
  formatDateTime,
  resolveUserUiStatus,
} from "@/domains/auth-access/adapters/rbac/users/users.format";
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import { AdminDetailsDialogShell } from "@features/admin/shared/components/details/AdminDetailsDialogShell";
import { useDetailsDialogCloseGuard } from "@features/admin/shared/hooks/useDetailsDialogCloseGuard";
import type { AdminDetailsDialogSection } from "@features/admin/shared/types/details-dialog.types";
import type {
  CentroAtencionListItem,
  RoleListItem,
  UserListItem,
  UserOverride,
  UserRole,
} from "@api/types";

interface AreaClinicaOption {
  id: number;
  name: string;
}

interface CatalogOption {
  id: number;
  name: string;
  code?: string;
  isActive: boolean;
}

interface UserDetailsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onClose?: () => void;
  userSummary: UserListItem | null;
  roleOptions: RoleListItem[];
  clinicOptions: CentroAtencionListItem[];
  areaClinicaOptions?: AreaClinicaOption[];
  escolaridadOptions?: CatalogOption[];
  escuelaOptions?: CatalogOption[];
  tipoPersonalOptions?: CatalogOption[];
  especialidadOptions?: CatalogOption[];
  isClinicsCatalogLoading?: boolean;
  canEdit: boolean;
  canReadRolesCatalog?: boolean;
  canReadPermissionsCatalog?: boolean;
  currentUserId?: number | null;
}

const DEFAULT_FORM_VALUES: UserDetailsFormValues = {
  firstName: "",
  paternalName: "",
  maternalName: "",
  email: "",
  clinicId: null,
  noExp: null,
  cdLaboral: null,
  telefono: null,
  sexo: null,
  fechaNac: null,
  areaClinicaId: null,
  escolaridadId: null,
  escuelaId: null,
  tipoPersonalId: null,
  cedulas: [],
  perfilMedico: { enabled: false, cedulaProfesional: null, cedulaEspecialidad: null, especialidadId: null, tipoAdscripcion: null },
  perfilEnfermeria: { enabled: false, cedulaEnfermeria: null, nivel: null, areaClinicaId: null },
  perfilAdministrativo: { enabled: false, puesto: null, areaAdministrativa: null },
};

const DRAFT_ASSIGNER = {
  id: 0,
  name: "Tu (ahora)",
} as const;

const FORM_ID = "user-details-form";

export function UserDetailsDialog({
  open,
  onOpenChange,
  onClose,
  userSummary,
  roleOptions,
  clinicOptions,
  areaClinicaOptions = [],
  escolaridadOptions = [],
  escuelaOptions = [],
  tipoPersonalOptions = [],
  especialidadOptions = [],
  isClinicsCatalogLoading = false,
  canEdit,
  canReadRolesCatalog = true,
  canReadPermissionsCatalog = true,
  currentUserId = null,
}: UserDetailsDialogProps) {
  const { isClosing, markClosing, handleOpenChange } =
    useDetailsDialogCloseGuard(onOpenChange);
  const userId = userSummary?.id;
  const {
    data: userDetailResponse,
    isLoading,
    isError,
    error: userDetailError,
    refetch,
  } = useUserDetail(userId, open && Boolean(userId));
  const {
    data: permissionsData,
    isLoading: isLoadingPermissions,
    isError: isPermissionsCatalogError,
    error: permissionsCatalogError,
    refetch: refetchPermissionsCatalog,
  } = usePermissionsCatalog(open && canReadPermissionsCatalog);

  const userDetail = userDetailResponse?.user;
  const roles = userDetailResponse?.roles ?? [];
  const overrides = userDetailResponse?.overrides ?? [];

  const updateUser = useUpdateUser();
  const activateUser = useActivateUser();
  const deactivateUser = useDeactivateUser();
  const assignRoles = useAssignRoles();
  const setPrimaryRole = useSetPrimaryRole();
  const revokeUserRole = useRevokeUserRole();
  const addUserOverride = useAddUserOverride();
  const removeUserOverride = useRemoveUserOverride();

  const [draftRoles, setDraftRoles] = useState<UserRole[]>([]);
  const [draftOverrides, setDraftOverrides] = useState<UserOverride[]>([]);
  const [draftAccountIsActive, setDraftAccountIsActive] = useState<
    boolean | null
  >(null);
  const [draftUserId, setDraftUserId] = useState<number | null>(null);
  const [isSavingAll, setIsSavingAll] = useState(false);
  const draftOverrideIdRef = useRef(-1);

  const form = useForm<UserDetailsFormValues>({
    resolver: zodResolver(userDetailsSchema) as Resolver<UserDetailsFormValues>,
    defaultValues: DEFAULT_FORM_VALUES,
  });
  const [formHydrated, setFormHydrated] = useState(false);
  const prevOpenRef = useRef(false);
  const [
    draftFirstName,
    draftPaternalName,
    draftMaternalName,
    draftEmail,
    draftClinicId,
    draftNoExp,
    draftCdLaboral,
    draftTelefono,
    draftSexo,
    draftFechaNac,
    draftAreaClinicaId,
    draftEscolaridadId,
    draftEscuelaId,
    draftTipoPersonalId,
    draftCedulas,
    draftPerfilMedico,
    draftPerfilEnfermeria,
    draftPerfilAdministrativo,
  ] = form.watch([
    "firstName",
    "paternalName",
    "maternalName",
    "email",
    "clinicId",
    "noExp",
    "cdLaboral",
    "telefono",
    "sexo",
    "fechaNac",
    "areaClinicaId",
    "escolaridadId",
    "escuelaId",
    "tipoPersonalId",
    "cedulas",
    "perfilMedico",
    "perfilEnfermeria",
    "perfilAdministrativo",
  ]);

  const watchedFormValues: UserDetailsFormValues = {
    firstName: draftFirstName ?? "",
    paternalName: draftPaternalName ?? "",
    maternalName: draftMaternalName ?? "",
    email: draftEmail ?? "",
    clinicId: draftClinicId ?? null,
    noExp: draftNoExp ?? null,
    cdLaboral: draftCdLaboral ?? null,
    telefono: draftTelefono ?? null,
    sexo: draftSexo ?? null,
    fechaNac: draftFechaNac ?? null,
    areaClinicaId: draftAreaClinicaId ?? null,
    escolaridadId: draftEscolaridadId ?? null,
    escuelaId: draftEscuelaId ?? null,
    tipoPersonalId: draftTipoPersonalId ?? null,
    cedulas: draftCedulas ?? [],
    perfilMedico: draftPerfilMedico ?? DEFAULT_FORM_VALUES.perfilMedico,
    perfilEnfermeria: draftPerfilEnfermeria ?? DEFAULT_FORM_VALUES.perfilEnfermeria,
    perfilAdministrativo: draftPerfilAdministrativo ?? DEFAULT_FORM_VALUES.perfilAdministrativo,
  };
  const baselineFormValues = userDetail
    ? mapUserDetailToFormValues(userDetail)
    : DEFAULT_FORM_VALUES;
  const isFormDirty = userDetail
    ? hasUserProfileChanges(baselineFormValues, watchedFormValues)
    : false;

  const hasDraftForCurrentUser =
    userDetail !== undefined && draftUserId === userDetail.id;
  const workingRoles = hasDraftForCurrentUser ? draftRoles : roles;
  const workingOverrides = hasDraftForCurrentUser ? draftOverrides : overrides;
  const workingAccountIsActive = hasDraftForCurrentUser
    ? (draftAccountIsActive ?? userDetail?.isActive ?? false)
    : (userDetail?.isActive ?? false);
  const viewedUserId = userDetail?.id ?? userSummary?.id ?? null;
  const isSelfUser = viewedUserId !== null && currentUserId === viewedUserId;

  const rolesDirty = userDetail
    ? !areUserRolesEquivalent(roles, workingRoles)
    : false;
  const overridesDirty = userDetail
    ? !areUserOverridesEquivalent(overrides, workingOverrides)
    : false;
  const accountStatusDirty = userDetail
    ? workingAccountIsActive !== userDetail.isActive
    : false;
  const isDirty =
    isFormDirty || rolesDirty || overridesDirty || accountStatusDirty;

  useEffect(() => {
    const justOpened = open && !prevOpenRef.current;
    prevOpenRef.current = open;

    if (!open) {
      setFormHydrated(false);
      return;
    }
    if (userDetail && (justOpened || !formHydrated)) {
      form.reset(mapUserDetailToFormValues(userDetail));
      setFormHydrated(true);
    }
  }, [form, formHydrated, open, userDetail]);

  useEffect(() => {
    if (!open || !userDetailResponse) return;
    setDraftUserId(userDetailResponse.user.id);
    setDraftRoles(userDetailResponse.roles);
    setDraftOverrides(userDetailResponse.overrides);
    setDraftAccountIsActive(userDetailResponse.user.isActive);
  }, [open, userDetailResponse]);

  const closeDialog = () => {
    markClosing();
    form.reset(
      userDetail ? mapUserDetailToFormValues(userDetail) : DEFAULT_FORM_VALUES,
    );
    setDraftRoles([]);
    setDraftOverrides([]);
    setDraftAccountIsActive(null);
    setDraftUserId(null);
    onClose?.();
    onOpenChange(false);
  };

  const shouldShowLoading = open && isLoading && !isClosing;
  const shouldShowError =
    open && !isClosing && (isError || (!isLoading && !userDetail));

  const isEditable = canEdit;
  const readOnlyUserMessage =
    "Solo lectura: no puedes actualizar este usuario porque no tienes permisos.";
  const roleCatalogAccessMessage = canReadRolesCatalog
    ? null
    : "No tienes acceso al catalogo de roles. Puedes gestionar solo los roles ya asignados.";
  const permissionsCatalogAccessMessage = canReadPermissionsCatalog
    ? null
    : "No tienes acceso al catalogo de permisos. Puedes gestionar solo los overrides existentes.";

  const isAccessMutating =
    assignRoles.isPending ||
    setPrimaryRole.isPending ||
    revokeUserRole.isPending ||
    addUserOverride.isPending ||
    removeUserOverride.isPending;
  const isStatusMutating = activateUser.isPending || deactivateUser.isPending;
  const isSaving =
    isSavingAll || updateUser.isPending || isAccessMutating || isStatusMutating;

  const handleAccountStatusChangeDraft = (nextActive: boolean) => {
    if (!isEditable || !userDetail) return;
    if (isSelfUser && !nextActive) {
      toast.error("No puedes desactivar tu propia cuenta", {
        description:
          "Usa otra cuenta administradora para cambiar el estado de este usuario.",
      });
      return;
    }

    setDraftUserId(userDetail.id);
    setDraftAccountIsActive(nextActive);
  };

  const handleAddRoleDraft = (roleId: number) => {
    if (!isEditable || !userDetail) return;

    setDraftUserId(userDetail.id);
    setDraftRoles((previousRoles) => {
      const baseRoles = hasDraftForCurrentUser ? previousRoles : roles;
      return addRoleToDraft(baseRoles, roleOptions, roleId, DRAFT_ASSIGNER);
    });
  };

  const handleSetPrimaryRoleDraft = (roleId: number) => {
    if (!isEditable || !userDetail) return;

    setDraftUserId(userDetail.id);
    setDraftRoles((previousRoles) => {
      const baseRoles = hasDraftForCurrentUser ? previousRoles : roles;
      return setPrimaryRoleInDraft(baseRoles, roleId, DRAFT_ASSIGNER);
    });
  };

  const handleRemoveRoleDraft = (roleId: number) => {
    if (!isEditable || !userDetail) return;

    setDraftUserId(userDetail.id);
    setDraftRoles((previousRoles) => {
      const baseRoles = hasDraftForCurrentUser ? previousRoles : roles;
      return removeRoleFromDraft(baseRoles, roleId);
    });
  };

  const handleAddOverrideDraft = (permissionCode: string) => {
    if (!isEditable || !userDetail) return;

    setDraftUserId(userDetail.id);
    setDraftOverrides((previousOverrides) => {
      const baseOverrides = hasDraftForCurrentUser
        ? previousOverrides
        : overrides;

      const draftResult = addOverrideToDraft({
        baseOverrides,
        permissions: permissionsData?.items ?? [],
        permissionCode,
        nextOverrideId: draftOverrideIdRef.current,
        assigner: DRAFT_ASSIGNER,
      });
      draftOverrideIdRef.current = draftResult.nextOverrideId;
      return draftResult.overrides;
    });
  };

  const handleToggleOverrideDraft = (permissionCode: string) => {
    if (!isEditable || !userDetail) return;

    setDraftUserId(userDetail.id);
    setDraftOverrides((previousOverrides) => {
      const baseOverrides = hasDraftForCurrentUser
        ? previousOverrides
        : overrides;
      return toggleOverrideEffectInDraft(baseOverrides, permissionCode);
    });
  };

  const handleOverrideDateDraft = (permissionCode: string, value: string) => {
    if (!isEditable || !userDetail) return;

    setDraftUserId(userDetail.id);
    setDraftOverrides((previousOverrides) => {
      const baseOverrides = hasDraftForCurrentUser
        ? previousOverrides
        : overrides;
      return setOverrideDateInDraft(baseOverrides, permissionCode, value);
    });
  };

  const handleRemoveOverrideDraft = (permissionCode: string) => {
    if (!isEditable || !userDetail) return;

    setDraftUserId(userDetail.id);
    setDraftOverrides((previousOverrides) => {
      const baseOverrides = hasDraftForCurrentUser
        ? previousOverrides
        : overrides;
      return removeOverrideFromDraft(baseOverrides, permissionCode);
    });
  };

  const syncDraftStateFromServer = (nextData?: typeof userDetailResponse) => {
    if (!nextData) return false;

    form.reset(mapUserDetailToFormValues(nextData.user));
    setDraftUserId(nextData.user.id);
    setDraftRoles(nextData.roles);
    setDraftOverrides(nextData.overrides);
    setDraftAccountIsActive(nextData.user.isActive);
    return true;
  };

  const handleSave = async (values: UserDetailsFormValues) => {
    if (!userDetail || !isEditable || isSaving) return;

    const payload = buildUserProfilePayload(
      mapUserDetailToFormValues(userDetail),
      values,
    );

    const rolesDiff = buildUserRolesDiff(roles, workingRoles);
    const overridesDiff = buildUserOverridesDiff(overrides, workingOverrides);
    const hasStatusChanges = workingAccountIsActive !== userDetail.isActive;

    if (isSelfUser && hasStatusChanges && !workingAccountIsActive) {
      toast.error("No puedes desactivar tu propia cuenta", {
        description:
          "Usa otra cuenta administradora para cambiar el estado de este usuario.",
      });
      return;
    }

    const savePlan = {
      profilePayload: payload,
      hasStatusChanges,
      nextIsActive: workingAccountIsActive,
      rolesDiff,
      overridesDiff,
    };

    if (!hasUserDetailsChanges(savePlan)) {
      return;
    }

    setIsSavingAll(true);
    let completedGroups = 0;

    try {
      completedGroups = await applyUserDetailsSavePlan(savePlan, {
        updateProfile: (profilePayload) =>
          updateUser.mutateAsync({
            userId: userDetail.id,
            data: profilePayload,
          }),
        activateUser: () => activateUser.mutateAsync({ userId: userDetail.id }),
        deactivateUser: () =>
          deactivateUser.mutateAsync({ userId: userDetail.id }),
        assignRoles: (roleIds) =>
          assignRoles.mutateAsync({
            userId: userDetail.id,
            data: { roleIds },
          }),
        setPrimaryRole: (roleId) =>
          setPrimaryRole.mutateAsync({
            userId: userDetail.id,
            data: { roleId },
          }),
        revokeRole: (roleId) =>
          revokeUserRole.mutateAsync({ userId: userDetail.id, roleId }),
        upsertOverride: (overridePayload) =>
          addUserOverride.mutateAsync({
            userId: userDetail.id,
            data: overridePayload,
          }),
        removeOverride: (permissionCode) =>
          removeUserOverride.mutateAsync({
            userId: userDetail.id,
            permissionCode,
          }),
      });

      const refreshedDetail = await refetch();
      const refreshedData = refreshedDetail.data;

      if (!syncDraftStateFromServer(refreshedData)) {
        form.reset(values);
      }

      toast.success("Cambios guardados", {
        description:
          "Perfil, estado de cuenta, roles y permisos actualizados correctamente.",
      });
    } catch (error) {
      const fallbackMessage =
        completedGroups > 0
          ? "Se aplicaron cambios parciales. Revisa el detalle y vuelve a intentar."
          : "No se pudieron guardar los cambios del usuario.";

      toast.error("No se pudieron guardar todos los cambios", {
        description: getUserErrorMessage(error, fallbackMessage),
      });

      try {
        const refreshedDetail = await refetch();
        syncDraftStateFromServer(refreshedDetail.data);
      } catch {
        // Si el refetch falla, mantenemos estado local actual para no bloquear al usuario.
      }
    } finally {
      setIsSavingAll(false);
    }
  };

  const avatarUrl = (userSummary as { avatarUrl?: string | null })?.avatarUrl;
  const title =
    userDetail?.fullname ||
    userSummary?.fullname ||
    userSummary?.username ||
    "Usuario";
  const username = userDetail?.username || userSummary?.username || null;
  const subtitle = userDetail?.email || userSummary?.email || null;
  const primaryRoleLabel =
    userDetail?.primaryRole || userSummary?.primaryRole || "Sin rol";
  const clinicLabel =
    userDetail?.clinic?.name || userSummary?.clinic?.name || "-";
  const rolesCount = workingRoles.length;
  const overridesCount = workingOverrides.length;

  const statusSource = userDetail
    ? {
        isActive: workingAccountIsActive,
        termsAccepted: userDetail.termsAccepted,
        mustChangePassword: userDetail.mustChangePassword,
      }
    : userSummary;
  const uiStatus = statusSource ? resolveUserUiStatus(statusSource) : null;

  const statusBadge =
    uiStatus === "pending" ? (
      <Badge variant="alert" className="gap-2">
        <span className="size-1.5 shrink-0 rounded-full bg-status-alert" />
        Pendiente
      </Badge>
    ) : uiStatus === "active" ? (
      <Badge variant="stable" className="gap-2">
        <span className="size-1.5 shrink-0 rounded-full bg-status-stable" />
        Activo
      </Badge>
    ) : uiStatus === "inactive" ? (
      <Badge variant="secondary" className="gap-2">
        <span className="size-1.5 shrink-0 rounded-full bg-txt-muted" />
        Inactivo
      </Badge>
    ) : null;

  const lastLoginLabel = formatDateTime(userDetail?.lastLoginAt);
  const lastIpLabel = userDetail?.lastIp ?? "-";
  const createdByLabel = userDetail
    ? `${userDetail.createdBy?.name ?? "-"} ${formatDateTime(userDetail.createdAt)}`
    : "-";
  const updatedByLabel = userDetail
    ? `${userDetail.updatedBy?.name ?? "-"} ${formatDateTime(userDetail.updatedAt)}`
    : "-";

  const loadingContent = (
    <div className="space-y-4">
      <div className="flex items-center gap-4">
        <Skeleton className="size-12 rounded-full" />
        <div className="space-y-2">
          <Skeleton className="h-4 w-40" />
          <Skeleton className="h-3 w-64" />
        </div>
      </div>
      <div className="flex gap-3">
        {Array.from({ length: 3 }).map((_, index) => (
          <Skeleton key={`tab-skel-${index}`} className="h-9 w-28" />
        ))}
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {Array.from({ length: 4 }).map((_, index) => (
          <Skeleton key={`field-skel-${index}`} className="h-12" />
        ))}
      </div>
    </div>
  );

  const errorContent = (
    <div className="rounded-2xl border border-line-struct bg-paper p-6 text-center">
      <div className="mx-auto flex size-12 items-center justify-center rounded-full bg-status-critical/10 text-status-critical">
        <AlertTriangle className="size-6" />
      </div>
      <h3 className="mt-4 text-base font-semibold text-txt-body">
        No se pudo cargar el usuario
      </h3>
      <p className="mt-1 text-sm text-txt-muted">
        {getUserErrorMessage(
          userDetailError,
          "Intenta nuevamente para ver el detalle completo.",
        )}
      </p>
      <Button
        variant="outline"
        size="sm"
        className="mt-4"
        onClick={() => void refetch()}
      >
        Reintentar
      </Button>
    </div>
  );

  const sections: AdminDetailsDialogSection[] = (userDetail && formHydrated)
    ? [
        {
          id: "general",
          label: "General",
          icon: <UserRound className="size-4" />,
          content: (
            <>
              <UserDetailsGeneralTab
                form={form}
                formId={FORM_ID}
                clinicOptions={clinicOptions}
                areaClinicaOptions={areaClinicaOptions}
                escolaridadOptions={escolaridadOptions}
                escuelaOptions={escuelaOptions}
                tipoPersonalOptions={tipoPersonalOptions}
                especialidadOptions={especialidadOptions}
                isClinicsCatalogLoading={isClinicsCatalogLoading}
                userDetail={userDetail}
                accountIsActive={workingAccountIsActive}
                onSubmit={handleSave}
                onAccountStatusChange={handleAccountStatusChangeDraft}
                isEditable={isEditable}
                canChangeAccountStatus={isEditable && !isSelfUser}
              />
              {!isEditable ? (
                <AdminReadOnlyNotice
                  className="mt-4"
                  message={readOnlyUserMessage}
                />
              ) : null}
            </>
          ),
        },
        {
          id: "roles",
          label: "Roles",
          icon: <ShieldCheck className="size-4" />,
          badge: (
            <Badge
              variant="secondary"
              className="ml-1 h-5 min-w-5 rounded-full px-1 text-[10px]"
            >
              {rolesCount}
            </Badge>
          ),
          content: (
            <UserDetailsRolesTab
              roles={workingRoles}
              roleOptions={roleOptions}
              isEditable={isEditable}
              readOnlyMessage={readOnlyUserMessage}
              catalogAccessMessage={roleCatalogAccessMessage}
              isSaving={isSaving}
              onAddRole={handleAddRoleDraft}
              onSetPrimaryRole={handleSetPrimaryRoleDraft}
              onRemoveRole={handleRemoveRoleDraft}
            />
          ),
        },
        {
          id: "permissions",
          label: "Permisos",
          icon: <ShieldAlert className="size-4" />,
          badge: (
            <Badge
              variant="secondary"
              className="ml-1 h-5 min-w-5 rounded-full px-1 text-[10px]"
            >
              {overridesCount}
            </Badge>
          ),
          content: (
            <UserDetailsPermissionsTab
              overrides={workingOverrides}
              permissions={permissionsData?.items ?? []}
              isLoadingPermissions={isLoadingPermissions}
              isEditable={isEditable}
              readOnlyMessage={readOnlyUserMessage}
              isSaving={isSaving}
              catalogAccessMessage={permissionsCatalogAccessMessage}
              catalogErrorMessage={
                canReadPermissionsCatalog && isPermissionsCatalogError
                  ? getUserErrorMessage(
                      permissionsCatalogError,
                      "No se pudo cargar el catalogo de permisos. Verifica que tengas admin:gestion:permisos:read.",
                    )
                  : null
              }
              onRetryCatalog={
                canReadPermissionsCatalog
                  ? () => {
                      void refetchPermissionsCatalog();
                    }
                  : undefined
              }
              onAddOverride={handleAddOverrideDraft}
              onToggleOverride={handleToggleOverrideDraft}
              onOverrideDateChange={handleOverrideDateDraft}
              onRemoveOverride={handleRemoveOverrideDraft}
            />
          ),
        },
      ]
    : [];

  return (
    <AdminDetailsDialogShell
      open={open}
      onOpenChange={handleOpenChange}
      onRequestClose={closeDialog}
      titleSrOnly="Detalle de usuario"
      descriptionSrOnly="Gestiona perfil, roles y permisos desde un solo lugar."
      sidePanel={
        userSummary || userDetail ? (
          <UserDetailsSidePanel
            fullname={title}
            username={username}
            email={subtitle}
            avatarUrl={avatarUrl}
            status={statusBadge}
            primaryRole={primaryRoleLabel}
            clinicName={clinicLabel}
            termsAccepted={userDetail?.termsAccepted}
            mustChangePassword={userDetail?.mustChangePassword}
            lastLoginLabel={lastLoginLabel}
            lastIpLabel={lastIpLabel}
            createdByLabel={createdByLabel}
            updatedByLabel={updatedByLabel}
          />
        ) : null
      }
      sidePanelClassName="hidden min-h-0 w-[292px] shrink-0 border-r border-line-struct/70 bg-subtle/20 lg:flex"
      splitBodyClassName="flex h-full min-h-0"
      header={
        userSummary || userDetail ? (
          <div className="lg:hidden">
            <UserDialogHeader
              title={title}
              subtitle={subtitle}
              avatarUrl={avatarUrl}
              status={statusBadge}
              fallbackLabel={userSummary?.username || "Usuario"}
            />
          </div>
        ) : null
      }
      headerClassName="px-5 pt-5 lg:px-8 lg:pt-5"
      scrollAreaClassName="min-h-0 flex-1 px-5 pb-8 lg:px-8 lg:pb-10"
      contentClassName="min-w-0 space-y-5 overflow-x-auto pt-0"
      tabsContainerClassName="gap-3"
      tabsListClassName="h-auto w-full items-center gap-1 rounded-full border border-line-struct/60 bg-subtle/30 p-1"
      tabsTriggerClassName="h-8 min-w-0 flex-1 rounded-full border-0 px-3 text-sm font-semibold text-txt-muted shadow-none hover:text-txt-body data-[state=active]:bg-paper data-[state=active]:text-txt-body data-[state=active]:shadow-sm"
      tabsContentClassName="pt-5"
      isDirty={isDirty}
      isLoading={shouldShowLoading}
      isError={shouldShowError}
      loadingContent={loadingContent}
      errorContent={errorContent}
      sections={sections}
      defaultSectionId="general"
      dialogContentClassName="h-[70vh] max-h-[70vh] w-[96vw] max-w-none overflow-hidden rounded-3xl bg-paper p-0 sm:max-w-none lg:w-[980px] xl:w-[1060px]"
      showCloseButton={false}
      footer={({ onCancel }) => (
        <UserDetailsFooter
          isDirty={isDirty}
          isSaving={isSaving}
          formId={FORM_ID}
          onCancel={onCancel}
          onSave={() => {
            void form.handleSubmit(handleSave)();
          }}
          disableSave={!isEditable}
        />
      )}
    />
  );
}
