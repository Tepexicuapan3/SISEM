import { useState } from "react";
import { FileDown, Mail, Plus, RotateCcw, ShieldUser, Upload } from "lucide-react";
import { useAuthSession } from "@/domains/auth-access/hooks/useAuthSession";
import { useAuthCapabilities } from "@/domains/auth-access/hooks/useAuthCapabilities";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import { useDebounce } from "@shared/hooks/useDebounce";
import { Button } from "@shared/ui/button";
import { DataTable } from "@features/admin/shared/components/DataTable";
import {
  TableColumnVisibility,
  type ColumnVisibilityState,
} from "@features/admin/shared/components/TableColumnVisibility";
import { TableFilterMenu } from "@features/admin/shared/components/TableFilterMenu";
import { TableHeaderBar } from "@features/admin/shared/components/TableHeaderBar";
import {
  TableOptionsMenu,
  type TableOptionItem,
} from "@features/admin/shared/components/TableOptionsMenu";
import { TablePrimaryAction } from "@features/admin/shared/components/TablePrimaryAction";
import { TableSearch } from "@features/admin/shared/components/TableSearch";
import { AdminPageIntro } from "@features/admin/shared/components/AdminPageIntro";
import { useUsersList } from "@/domains/auth-access/hooks/rbac/users/useUsersList";
import { useExportUsers } from "@/domains/auth-access/hooks/rbac/users/useExportUsers";
import { useRolesList } from "@/domains/auth-access/hooks/rbac/roles/useRolesList";
import { useCentrosAtencionList } from "@features/admin/modules/catalogos/centros-atencion/queries/useCentrosAtencionList";
import { useAreasClinicasList } from "@features/admin/modules/catalogos/areas-clinicas/queries/useAreasClinicasList";
import { useEscolaridadList } from "@features/admin/modules/catalogos/escolaridad/queries/useEscolaridadList";
import { useEscuelasList } from "@features/admin/modules/catalogos/escuelas/queries/useEscuelasList";
import { useTipoPersonalList } from "@features/admin/modules/catalogos/tipo-personal/queries/useTipoPersonalList";
import { useEspecialidadesList } from "@features/admin/modules/catalogos/especialidades/queries/useEspecialidadesList";
import { useTableDetailsDialog } from "@features/admin/shared/hooks/useTableDetailsDialog";
import { UserDetailsDialog } from "@/domains/auth-access/components/admin/rbac/users/UserDetailsDialog";
import { UserCreateDialog } from "@/domains/auth-access/components/admin/rbac/users/UserCreateDialog";
import { UserNotifyDialog } from "@/domains/auth-access/components/admin/rbac/users/UserNotifyDialog";
import { UserImportDialog } from "@/domains/auth-access/components/admin/rbac/users/UserImportDialog";
import {
  buildUsersTableColumns,
  buildUsersVisibilityOptions,
} from "@/domains/auth-access/components/admin/rbac/users/UsersTableColumns";
import {
  createCapabilityResolver,
  RBAC_CAPABILITIES_DEGRADED_MESSAGE,
} from "@/domains/auth-access/adapters/rbac/capabilities-gating";
import { getUserErrorMessage } from "@/domains/auth-access/adapters/rbac/users/users.feedback";
import type { UserListItem } from "@api/types";

const USER_STATUS_FILTER = {
  ALL: "all",
  ACTIVE: "active",
  INACTIVE: "inactive",
  PENDING: "pending",
} as const;

const ROLE_FILTER_ALL = "all";
const CLINIC_FILTER_ALL = "all";
const TIPO_PERSONAL_ALL = "all";

type UserStatusFilter =
  (typeof USER_STATUS_FILTER)[keyof typeof USER_STATUS_FILTER];

export function UsersPage() {
  const { hasCapability } = usePermissionDependencies();
  const {
    isLoading: isCapabilitiesLoading,
    isError: isCapabilitiesError,
    refetch: refetchCapabilities,
  } = useAuthCapabilities();
  const { data: authUser } = useAuthSession();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<UserStatusFilter>(
    USER_STATUS_FILTER.ALL,
  );
  const [roleFilter, setRoleFilter] = useState(ROLE_FILTER_ALL);
  const [clinicFilter, setClinicFilter] = useState(CLINIC_FILTER_ALL);
  const [tipoPersonalFilter, setTipoPersonalFilter] = useState(TIPO_PERSONAL_ALL);
  const [columnVisibility, setColumnVisibility] =
    useState<ColumnVisibilityState>({
      user: true,
      email: true,
      clinic: true,
      areaClinica: true,
      cdLaboral: true,
      telefono: false,
      sexo: true,
      tipoPersonal: true,
      escolaridad: true,
      escuela: true,
      cedulas: true,
      primaryRole: true,
      isActive: true,
    });
  const [createOpen, setCreateOpen] = useState(false);
  const [notifyOpen, setNotifyOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const {
    open: detailsOpen,
    selectedItem: selectedUser,
    openDetails: handleOpenDetails,
    closeDetails: handleCloseDetails,
    setOpen: setDetailsOpen,
  } = useTableDetailsDialog<UserListItem>();
  const debouncedSearch = useDebounce(search, 400);
  const { exportUsers, isExporting } = useExportUsers();
  const { resolveCapability } = createCapabilityResolver({
    hasCapability,
    isCapabilitiesLoading,
    isCapabilitiesError,
  });

  const canReadRolesCatalog = resolveCapability(
    "admin.users.rolesCatalog.read",
    {
      allOf: ["admin:gestion:roles:read"],
    },
  );
  const canReadPermissionsCatalog = resolveCapability(
    "admin.users.permissionsCatalog.read",
    {
      allOf: ["admin:gestion:permisos:read"],
    },
  );
  const canReadClinicsCatalog = resolveCapability(
    "admin.users.clinicsCatalog.read",
    {
      allOf: ["admin:catalogos:centros_atencion:read"],
    },
  );

  const canCreateUser = resolveCapability("admin.users.create", {
    allOf: ["admin:gestion:usuarios:create"],
  });
  const canUpdateUser = resolveCapability("admin.users.update", {
    allOf: ["admin:gestion:usuarios:update"],
  });
  // Restablecer contraseña, forzar cierre de sesión y desbloquear: permiso
  // propio, separado de editar usuarios.
  const canManageCredentials = resolveCapability("admin.users.credentials", {
    allOf: ["admin:gestion:usuarios:credenciales"],
  });
  const canReadUser = resolveCapability("admin.users.read", {
    allOf: ["admin:gestion:usuarios:read"],
  });

  const { data, isLoading, isFetching, error, refetch } = useUsersList(
    {
      page,
      pageSize,
      search: debouncedSearch || undefined,
      status:
        statusFilter === USER_STATUS_FILTER.ALL ? undefined : statusFilter,
      roleId: roleFilter === ROLE_FILTER_ALL ? undefined : Number(roleFilter),
      clinicId:
        clinicFilter === CLINIC_FILTER_ALL ? undefined : Number(clinicFilter),
      tipoPersonalId:
        tipoPersonalFilter === TIPO_PERSONAL_ALL ? undefined : Number(tipoPersonalFilter),
    },
    {
      enabled: canReadUser,
    },
  );
  const rows = data?.items ?? [];

  const { data: rolesData } = useRolesList(
    {
      page: 1,
      pageSize: 100,
      isActive: true,
    },
    {
      enabled: canReadRolesCatalog,
    },
  );
  const {
    data: clinicsData,
    isLoading: isLoadingClinicsCatalog,
    isFetching: isFetchingClinicsCatalog,
  } = useCentrosAtencionList(
    {
      page: 1,
      pageSize: 100,
      isActive: true,
    },
    {
      enabled: canReadUser || canCreateUser || canUpdateUser,
    },
  );
  const { data: areasClinicasData } = useAreasClinicasList(
    { page: 1, pageSize: 100 },
    { enabled: canReadUser || canCreateUser || canUpdateUser },
  );
  const { data: escolaridadData } = useEscolaridadList(
    { page: 1, pageSize: 100, isActive: true },
    { enabled: canReadUser || canCreateUser || canUpdateUser },
  );
  const { data: escuelasData } = useEscuelasList(
    { page: 1, pageSize: 100, isActive: true },
    { enabled: canReadUser || canCreateUser || canUpdateUser },
  );
  const { data: tipoPersonalData } = useTipoPersonalList(
    { page: 1, pageSize: 100, isActive: true },
    { enabled: canReadUser || canCreateUser || canUpdateUser },
  );
  const { data: especialidadesData } = useEspecialidadesList(
    { page: 1, pageSize: 100, isActive: true },
    { enabled: canReadUser || canCreateUser || canUpdateUser },
  );
  const roleOptions = rolesData?.items ?? [];
  const clinicOptions = clinicsData?.items ?? [];
  const areaClinicaOptions = (areasClinicasData?.items ?? []).map((a) => ({
    id: a.id,
    name: a.name,
  }));
  const escolaridadOptions = (escolaridadData?.items ?? []).map((e) => ({
    id: e.id,
    name: e.name,
    isActive: e.isActive,
  }));
  const escuelaOptions = (escuelasData?.items ?? []).map((e) => ({
    id: e.id,
    name: e.name,
    code: e.code,
    isActive: e.isActive,
  }));
  const tipoPersonalOptions = (tipoPersonalData?.items ?? []).map((t) => ({
    id: t.id,
    name: t.name,
    isActive: t.isActive,
  }));
  const especialidadOptions = (especialidadesData?.items ?? []).map((e) => ({
    id: e.id,
    name: e.name,
    isActive: e.isActive,
  }));

  const canManageUsersFully = resolveCapability("admin.users.editFull", {
    allOf: [
      "admin:gestion:usuarios:read",
      "admin:gestion:usuarios:update",
      "admin:gestion:roles:read",
      "admin:gestion:permisos:read",
    ],
  });

  const canUpdateUserAccess = canManageUsersFully || canUpdateUser;
  const columns = buildUsersTableColumns();
  const visibilityOptions = buildUsersVisibilityOptions();

  const visibleColumns = columns.filter(
    (column) => columnVisibility[column.key] ?? true,
  );

  const appliedFiltersCount = [
    statusFilter !== USER_STATUS_FILTER.ALL,
    roleFilter !== ROLE_FILTER_ALL,
    clinicFilter !== CLINIC_FILTER_ALL,
    tipoPersonalFilter !== TIPO_PERSONAL_ALL,
  ].filter(Boolean).length;

  const isSearchPending = search.trim() !== debouncedSearch.trim();
  const hasFilters =
    Boolean(debouncedSearch.trim()) ||
    appliedFiltersCount > 0;
  const tableErrorDescription = error
    ? getUserErrorMessage(
        error,
        "No se pudo obtener el listado de usuarios. Intenta nuevamente.",
      )
    : undefined;
  const capabilityErrorDescription = RBAC_CAPABILITIES_DEGRADED_MESSAGE.users;

  const handleClearFilters = () => {
    setSearch("");
    setStatusFilter(USER_STATUS_FILTER.ALL);
    setRoleFilter(ROLE_FILTER_ALL);
    setClinicFilter(CLINIC_FILTER_ALL);
    setTipoPersonalFilter(TIPO_PERSONAL_ALL);
    setPage(1);
  };

  const tableOptions: TableOptionItem[] = [
    {
      id: "refresh-users",
      label: "Actualizar",
      icon: RotateCcw,
      isLoading: isFetching,
      disabled: isFetching || !canReadUser,
      onSelect: () => {
        if (isFetching || !canReadUser) {
          return;
        }

        void refetch();
      },
    },
    {
      id: "export-users",
      label: isExporting ? "Exportando..." : "Exportar Excel",
      icon: FileDown,
      isLoading: isExporting,
      loadingAnimation: "pulse",
      disabled: isExporting || !canReadUser,
      onSelect: () => {
        if (isExporting || !canReadUser) return;
        void exportUsers({
          search: debouncedSearch || undefined,
          status: statusFilter === USER_STATUS_FILTER.ALL ? undefined : statusFilter,
          roleId: roleFilter === ROLE_FILTER_ALL ? undefined : Number(roleFilter),
          clinicId: clinicFilter === CLINIC_FILTER_ALL ? undefined : Number(clinicFilter),
          tipoPersonalId: tipoPersonalFilter === TIPO_PERSONAL_ALL ? undefined : Number(tipoPersonalFilter),
        });
      },
    },
    {
      id: "import-users",
      label: "Importar usuarios",
      icon: Upload,
      disabled: !canCreateUser,
      onSelect: () => {
        if (!canCreateUser) return;
        setImportOpen(true);
      },
    },
  ];

  const filterSections = [
    {
      id: "status",
      label: "Estado",
      options: [
        {
          id: USER_STATUS_FILTER.ACTIVE,
          label: "Activos",
          selected: statusFilter === USER_STATUS_FILTER.ACTIVE,
          onSelect: () => {
            setStatusFilter(USER_STATUS_FILTER.ACTIVE);
            setPage(1);
          },
        },
        {
          id: USER_STATUS_FILTER.INACTIVE,
          label: "Inactivos",
          selected: statusFilter === USER_STATUS_FILTER.INACTIVE,
          onSelect: () => {
            setStatusFilter(USER_STATUS_FILTER.INACTIVE);
            setPage(1);
          },
        },
        {
          id: USER_STATUS_FILTER.PENDING,
          label: "Pendientes",
          selected: statusFilter === USER_STATUS_FILTER.PENDING,
          onSelect: () => {
            setStatusFilter(USER_STATUS_FILTER.PENDING);
            setPage(1);
          },
        },
      ],
    },
    ...(canReadRolesCatalog
      ? [
          {
            id: "role",
            label: "Rol",
            options: [
              ...roleOptions.map((role) => ({
                id: role.id.toString(),
                label: role.name,
                selected: roleFilter === role.id.toString(),
                onSelect: () => {
                  setRoleFilter(role.id.toString());
                  setPage(1);
                },
              })),
            ],
          },
        ]
      : []),
    ...(canReadClinicsCatalog
      ? [
          {
            id: "clinic",
            label: "Centro",
            options: [
              ...clinicOptions.map((clinic) => ({
                id: clinic.id.toString(),
                label: clinic.name,
                selected: clinicFilter === clinic.id.toString(),
                onSelect: () => {
                  setClinicFilter(clinic.id.toString());
                  setPage(1);
                },
              })),
            ],
          },
        ]
      : []),
    ...(tipoPersonalOptions.length > 0
      ? [
          {
            id: "tipoPersonal",
            label: "Tipo personal",
            options: tipoPersonalOptions.map((tp) => ({
              id: tp.id.toString(),
              label: tp.name,
              selected: tipoPersonalFilter === tp.id.toString(),
              onSelect: () => {
                setTipoPersonalFilter(tp.id.toString());
                setPage(1);
              },
            })),
          },
        ]
      : []),
  ];

  return (
    <div className="mx-auto w-full space-y-6 px-4 pb-2 sm:px-6 lg:max-w-[1360px] lg:px-8 xl:px-10">
      <AdminPageIntro
        title="Usuarios"
        description="Administra cuentas, rol primario y estado de acceso desde un solo tablero operativo."
        icon={<ShieldUser className="size-12" />}
      />

      <TableHeaderBar
        search={
          <TableSearch
            value={search}
            onChange={(value) => {
              setSearch(value);
              setPage(1);
            }}
            placeholder="Buscar en la tabla"
          />
        }
        actions={
          <>
            <TableFilterMenu
              sections={filterSections}
              appliedCount={appliedFiltersCount}
              onClear={handleClearFilters}
            />
            <TableColumnVisibility
              columns={visibilityOptions}
              visibility={columnVisibility}
              onVisibilityChange={setColumnVisibility}
            />
            <TableOptionsMenu options={tableOptions} />
            {canUpdateUser ? (
              <Button
                variant="outline"
                size="sm"
                className="h-9 gap-2"
                onClick={() => setNotifyOpen(true)}
              >
                <Mail className="size-4" />
                Notificar
              </Button>
            ) : null}
            {canCreateUser ? (
              <TablePrimaryAction
                permission="admin:gestion:usuarios:create"
                dependencyAware
                label="Nuevo"
                icon={<Plus className="size-4" />}
                onClick={() => setCreateOpen(true)}
              />
            ) : null}
          </>
        }
      />

      <DataTable
        columns={visibleColumns}
        rows={rows}
        isLoading={isCapabilitiesLoading || isLoading || isSearchPending}
        isError={isCapabilitiesError || Boolean(error)}
        errorTitle={
          isCapabilitiesError
            ? "No se pudo validar permisos"
            : "No se pudo cargar usuarios"
        }
        errorDescription={
          isCapabilitiesError
            ? capabilityErrorDescription
            : tableErrorDescription
        }
        hasFilters={hasFilters}
        onRowClick={canReadUser ? handleOpenDetails : undefined}
        onRetry={() => {
          if (isCapabilitiesError) {
            void refetchCapabilities();
            return;
          }
          void refetch();
        }}
        onClearFilters={handleClearFilters}
        pagination={{
          page,
          pageSize,
          total: data?.total ?? 0,
          totalPages: data?.totalPages ?? 1,
          onPageChange: setPage,
          onPageSizeChange: (value) => {
            setPageSize(value);
            setPage(1);
          },
        }}
        getRowKey={(row) => row.id.toString()}
        emptyTitle="Sin usuarios"
        emptyDescription="Cuando existan usuarios registrados se listarán aquí."
      />
      <UserDetailsDialog
        key={selectedUser?.id ?? "none"}
        open={detailsOpen}
        onOpenChange={setDetailsOpen}
        userSummary={selectedUser}
        roleOptions={roleOptions}
        clinicOptions={clinicOptions}
        areaClinicaOptions={areaClinicaOptions}
        escolaridadOptions={escolaridadOptions}
        escuelaOptions={escuelaOptions}
        tipoPersonalOptions={tipoPersonalOptions}
        especialidadOptions={especialidadOptions}
        isClinicsCatalogLoading={
          isLoadingClinicsCatalog || isFetchingClinicsCatalog
        }
        canEdit={canUpdateUserAccess}
        canManageCredentials={canManageCredentials}
        canReadRolesCatalog={canReadRolesCatalog}
        canReadPermissionsCatalog={canReadPermissionsCatalog}
        currentUserId={authUser?.id ?? null}
        onClose={handleCloseDetails}
      />
      <UserCreateDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        roleOptions={roleOptions}
        clinicOptions={clinicOptions}
        areaClinicaOptions={areaClinicaOptions}
        escolaridadOptions={escolaridadOptions}
        escuelaOptions={escuelaOptions}
        tipoPersonalOptions={tipoPersonalOptions}
      />
      <UserNotifyDialog
        open={notifyOpen}
        onOpenChange={setNotifyOpen}
        clinicOptions={clinicOptions}
      />
      <UserImportDialog open={importOpen} onOpenChange={setImportOpen} />
    </div>
  );
}

export default UsersPage;
