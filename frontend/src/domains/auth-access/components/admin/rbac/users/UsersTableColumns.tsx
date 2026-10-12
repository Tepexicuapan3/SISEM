import { Eye, KeyRound, UserCheck, UserX } from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@shared/ui/avatar";
import { Badge } from "@shared/ui/badge";
import { Skeleton } from "@shared/ui/skeleton";
import type { UserListItem } from "@api/types";
import { getRoleBadgeVariant } from "@features/admin/shared/utils/roleBadge";
import { type DataTableColumn } from "@features/admin/shared/components/DataTable";
import { type TableColumnVisibilityItem } from "@features/admin/shared/components/TableColumnVisibility";
import {
  TableActionsHeader,
  TableToolbar,
  type TableAction,
} from "@features/admin/shared/components/TableToolbar";
import { resolveUserUiStatus } from "@/domains/auth-access/adapters/rbac/users/users.format";

interface BuildUsersTableColumnsOptions {
  canReadUser: boolean;
  canUpdateUser: boolean;
  isStatusPending: boolean;
  onOpenDetails: (user: UserListItem) => void;
  onToggleStatus: (user: UserListItem) => void;
  onRequestResetPassword: (user: UserListItem) => void;
}

const getInitials = (value: string) => {
  const parts = value.split(" ").filter(Boolean);
  if (parts.length === 0) return "??";
  return parts
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
};

const getAvatarUrl = (row: UserListItem) =>
  (row as { avatarUrl?: string | null }).avatarUrl ?? undefined;

export const buildUsersTableColumns = ({
  canReadUser,
  canUpdateUser,
  isStatusPending,
  onOpenDetails,
  onToggleStatus,
  onRequestResetPassword,
}: BuildUsersTableColumnsOptions): DataTableColumn<UserListItem>[] => {
  const baseColumns: DataTableColumn<UserListItem>[] = [
    {
      key: "user",
      header: "Usuario",
      className: "w-[210px]",
      skeleton: (
        <div className="flex items-center gap-3">
          <Skeleton className="size-8 rounded-full" />
          <div className="space-y-2">
            <Skeleton className="h-3 w-32" />
            <Skeleton className="h-3 w-20" />
          </div>
        </div>
      ),
      render: (row) => {
        const displayName = row.fullname || row.username;
        const initials = getInitials(displayName || row.username);
        const avatarUrl = getAvatarUrl(row);

        return (
          <div className="flex min-w-0 items-center gap-3">
            <Avatar className="h-8 w-8">
              {avatarUrl ? (
                <AvatarImage src={avatarUrl} alt={displayName} />
              ) : null}
              <AvatarFallback className="text-xs font-semibold text-txt-muted">
                {initials}
              </AvatarFallback>
            </Avatar>
            <div className="min-w-0">
              <div className="truncate text-sm font-medium text-txt-body">
                {displayName || "Sin nombre"}
              </div>
              <div className="truncate text-xs text-txt-muted">
                {row.username}
              </div>
            </div>
          </div>
        );
      },
    },
    {
      key: "email",
      header: "Correo",
      accessorKey: "email",
      className: "w-[190px]",
      cellContentClassName: "max-w-[170px]",
    },
    {
      key: "clinic",
      header: "Centro",
      accessorKey: "clinic",
      className: "w-[150px]",
      cellContentClassName: "max-w-[150px]",
      render: (row) => row.clinic?.name ?? "Sin centro",
    },
    {
      key: "areaClinica",
      header: "Área clínica",
      className: "w-[130px]",
      cellContentClassName: "max-w-[130px]",
      render: (row) => row.areaClinica?.name ?? (
        <span className="text-txt-muted">—</span>
      ),
    },
    {
      key: "cdLaboral",
      header: "Clave lab.",
      className: "w-[95px]",
      render: (row) => row.cdLaboral ? (
        <span className="font-mono text-xs">{row.cdLaboral}</span>
      ) : (
        <span className="text-txt-muted">—</span>
      ),
    },
    {
      key: "telefono",
      header: "Teléfono",
      className: "w-[110px]",
      render: (row) => row.telefono ? (
        <span className="text-xs">{row.telefono}</span>
      ) : (
        <span className="text-txt-muted">—</span>
      ),
    },
    {
      key: "sexo",
      header: "Sexo",
      align: "center" as const,
      className: "w-[70px]",
      render: (row) => row.sexo ? (
        <span className="text-xs">{row.sexo === "M" ? "Masc." : row.sexo === "F" ? "Fem." : "Otro"}</span>
      ) : (
        <span className="text-txt-muted">—</span>
      ),
    },
    {
      key: "escolaridad",
      header: "Escolaridad",
      className: "w-[120px]",
      cellContentClassName: "max-w-[120px]",
      render: (row) => row.escolaridad?.name ?? (
        <span className="text-txt-muted">—</span>
      ),
    },
    {
      key: "escuela",
      header: "Escuela",
      className: "w-[150px]",
      cellContentClassName: "max-w-[150px]",
      render: (row) => row.escuela ? (
        <span className="block truncate" title={row.escuela.code ? `${row.escuela.code} — ${row.escuela.name}` : row.escuela.name}>
          {row.escuela.code ?? row.escuela.name}
        </span>
      ) : (
        <span className="text-txt-muted">—</span>
      ),
    },
    {
      key: "cedulas",
      header: "Cédulas",
      align: "center" as const,
      className: "w-[80px]",
      render: (row) => {
        const count = row.cedulas?.length ?? 0;
        if (count === 0) return <span className="text-txt-muted">—</span>;
        return (
          <Badge variant="outline" className="gap-1 text-xs">
            {count} {count === 1 ? "cédula" : "cédulas"}
          </Badge>
        );
      },
    },
    {
      key: "tipoPersonal",
      header: "Tipo",
      align: "center" as const,
      className: "w-[120px]",
      render: (row) => {
        if (!row.tipoPersonal) return <span className="text-txt-muted">—</span>;
        return <span className="text-xs font-medium">{row.tipoPersonal.name}</span>;
      },
    },
    {
      key: "primaryRole",
      header: "Rol",
      align: "center",
      accessorKey: "primaryRole",
      className: "w-[130px]",
      render: (row) => {
        const roleLabel = row.primaryRole?.trim() || "Sin rol";
        const roleVariant = getRoleBadgeVariant(roleLabel);

        return (
          <Badge variant={roleVariant} className="max-w-35 truncate">
            {roleLabel}
          </Badge>
        );
      },
    },
    {
      key: "isActive",
      header: "Estado",
      align: "center",
      accessorKey: "isActive",
      className: "w-24",
      render: (row) => {
        const uiStatus = resolveUserUiStatus(row);

        if (uiStatus === "pending") {
          return (
            <Badge variant="alert" className="gap-2">
              <span className="size-1.5 shrink-0 rounded-full bg-status-alert" />
              Pendiente
            </Badge>
          );
        }

        return uiStatus === "active" ? (
          <Badge variant="stable" className="gap-2">
            <span className="size-1.5 shrink-0 rounded-full bg-status-stable" />
            Activo
          </Badge>
        ) : (
          <Badge variant="secondary" className="gap-2">
            <span className="size-1.5 shrink-0 rounded-full bg-txt-muted" />
            Inactivo
          </Badge>
        );
      },
    },
  ];

  const showActions = canReadUser || canUpdateUser;

  if (!showActions) {
    return baseColumns;
  }

  const actionColumn: DataTableColumn<UserListItem> = {
    key: "actions",
    header: <TableActionsHeader />,
    align: "center",
    className: "w-9 px-0",
    headerClassName: "w-9 px-0",
    render: (row) => {
      const actions: TableAction[] = [];

      if (canReadUser) {
        actions.push({
          id: `view-${row.id}`,
          label: "Ver detalles",
          icon: Eye,
          onSelect: () => onOpenDetails(row),
        });
      }

      if (canUpdateUser) {
        actions.push({
          id: `status-${row.id}`,
          label: row.isActive ? "Desactivar" : "Activar",
          icon: row.isActive ? UserX : UserCheck,
          variant: row.isActive ? "destructive" : "default",
          disabled: isStatusPending,
          onSelect: () => onToggleStatus(row),
        });

        actions.push({
          id: `reset-password-${row.id}`,
          label: "Restablecer contraseña",
          icon: KeyRound,
          variant: "destructive",
          onSelect: () => onRequestResetPassword(row),
        });
      }

      return actions.length > 0 ? (
        <div
          onClick={(event) => event.stopPropagation()}
          onKeyDown={(event) => event.stopPropagation()}
        >
          <TableToolbar actions={actions} />
        </div>
      ) : null;
    },
  };

  return [...baseColumns, actionColumn];
};

export const buildUsersVisibilityOptions = (
  showActions: boolean,
): TableColumnVisibilityItem[] => {
  const options: TableColumnVisibilityItem[] = [
    { key: "user", label: "Usuario" },
    { key: "email", label: "Correo" },
    { key: "clinic", label: "Centro" },
    { key: "areaClinica", label: "Área clínica" },
    { key: "cdLaboral", label: "Clave lab." },
    { key: "telefono",  label: "Teléfono" },
    { key: "sexo",      label: "Sexo" },
    { key: "escolaridad", label: "Escolaridad" },
    { key: "escuela", label: "Escuela" },
    { key: "cedulas", label: "Cédulas" },
    { key: "tipoPersonal", label: "Tipo" },
    { key: "primaryRole", label: "Rol" },
    { key: "isActive", label: "Estado" },
  ];

  if (showActions) {
    options.push({
      key: "actions",
      label: "Acciones",
      canHide: false,
    });
  }

  return options;
};
