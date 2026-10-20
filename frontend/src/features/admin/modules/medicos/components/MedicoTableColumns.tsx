import { Eye, Pencil } from "lucide-react";
import { Badge } from "@shared/ui/badge";
import { Skeleton } from "@shared/ui/skeleton";
import type { MedicoListItem, EstatusMedico, TipoMedico } from "@api/types/medicos.types";
import { type DataTableColumn } from "@features/admin/shared/components/DataTable";
import { type TableColumnVisibilityItem } from "@features/admin/shared/components/TableColumnVisibility";
import {
  TableActionsHeader,
  TableToolbar,
  type TableAction,
} from "@features/admin/shared/components/TableToolbar";

const ESTATUS_BADGE: Record<EstatusMedico, { label: string; variant: "stable" | "alert" | "secondary" | "critical" | "outline" }> = {
  ACTIVO:      { label: "Activo",      variant: "stable" },
  VACACIONES:  { label: "Vacaciones",  variant: "alert" },
  INCAPACIDAD: { label: "Incapacidad", variant: "alert" },
  SUSPENDIDO:  { label: "Suspendido",  variant: "critical" },
  BAJA:        { label: "Baja",        variant: "secondary" },
};

const TIPO_BADGE: Record<TipoMedico, string> = {
  CLINICA:  "Clínica",
  HOSPITAL: "Hospital",
  AMBOS:    "Clínica / Hospital",
};

interface BuildOptions {
  canRead: boolean;
  canUpdate: boolean;
  onOpenDetails: (m: MedicoListItem) => void;
}

export const buildMedicosTableColumns = ({
  canRead,
  canUpdate,
  onOpenDetails,
}: BuildOptions): DataTableColumn<MedicoListItem>[] => {
  const base: DataTableColumn<MedicoListItem>[] = [
    {
      key: "id",
      header: "No. Médico",
      className: "w-[100px]",
      render: (row) => <span className="font-mono text-sm text-txt-muted">{row.id}</span>,
    },
    {
      key: "nombre",
      header: "Médico",
      className: "w-[280px]",
      skeleton: (
        <div className="flex items-center gap-3">
          <Skeleton className="size-8 shrink-0 rounded-lg" />
          <div className="space-y-1.5">
            <Skeleton className="h-3 w-36" />
            <Skeleton className="h-3 w-20" />
          </div>
        </div>
      ),
      render: (row) => {
        const initials = [row.nombre, row.paterno]
          .filter(Boolean)
          .map((s) => s.charAt(0).toUpperCase())
          .join("")
          .slice(0, 2) || "M";
        return (
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-xs font-semibold text-primary select-none">
              {initials}
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-txt-body">{row.nombreCompleto}</p>
              <p className="truncate text-xs text-txt-muted">{row.username}</p>
            </div>
          </div>
        );
      },
    },
    {
      key: "tipoMedico",
      header: "Tipo",
      className: "w-[140px]",
      render: (row) => (
        <Badge variant="outline" className="text-xs">
          {TIPO_BADGE[row.tipoMedico] ?? row.tipoMedico}
        </Badge>
      ),
    },
    {
      key: "servicio",
      header: "Servicio",
      className: "w-[160px]",
      cellContentClassName: "max-w-[150px]",
      render: (row) =>
        row.servicio ? (
          <span className="text-sm">{row.servicio}</span>
        ) : (
          <span className="text-txt-muted">—</span>
        ),
    },
    {
      key: "especialidades",
      header: "Especialidades",
      className: "w-[180px]",
      cellContentClassName: "max-w-[170px]",
      render: (row) => {
        const principal = row.especialidades.find((e) => e.esPrincipal) ?? row.especialidades[0];
        const extra = row.especialidades.length - 1;
        if (!principal) return <span className="text-txt-muted">—</span>;
        return (
          <span className="truncate text-sm">
            {principal.name}
            {extra > 0 ? <span className="ml-1 text-xs text-txt-muted">+{extra}</span> : null}
          </span>
        );
      },
    },
    {
      key: "estatusMedico",
      header: "Estatus",
      align: "center",
      className: "w-[120px]",
      render: (row) => {
        const cfg = ESTATUS_BADGE[row.estatusMedico] ?? { label: row.estatusMedico, variant: "outline" as const };
        return (
          <Badge variant={cfg.variant} className="gap-1.5 text-xs">
            <span className="size-1.5 shrink-0 rounded-full bg-current opacity-70" />
            {cfg.label}
          </Badge>
        );
      },
    },
  ];

  if (!canRead && !canUpdate) return base;

  const actions: DataTableColumn<MedicoListItem> = {
    key: "actions",
    header: <TableActionsHeader />,
    align: "center",
    className: "w-9 px-0",
    headerClassName: "w-9 px-0",
    render: (row) => {
      const items: TableAction[] = [];
      if (canRead) items.push({ id: `view-${row.id}`, label: "Ver detalles", icon: Eye, onSelect: () => onOpenDetails(row) });
      if (canUpdate) items.push({ id: `edit-${row.id}`, label: "Editar", icon: Pencil, onSelect: () => onOpenDetails(row) });
      return items.length > 0 ? (
        <div onClick={(e) => e.stopPropagation()} onKeyDown={(e) => e.stopPropagation()}>
          <TableToolbar actions={items} />
        </div>
      ) : null;
    },
  };

  return [...base, actions];
};

export const buildMedicosVisibilityOptions = (showActions: boolean): TableColumnVisibilityItem[] => {
  const opts: TableColumnVisibilityItem[] = [
    { key: "id",            label: "No. Médico" },
    { key: "nombre",        label: "Médico" },
    { key: "tipoMedico",    label: "Tipo" },
    { key: "servicio",      label: "Servicio" },
    { key: "especialidades",label: "Especialidades" },
    { key: "estatusMedico", label: "Estatus" },
  ];
  if (showActions) opts.push({ key: "actions", label: "Acciones", canHide: false });
  return opts;
};
