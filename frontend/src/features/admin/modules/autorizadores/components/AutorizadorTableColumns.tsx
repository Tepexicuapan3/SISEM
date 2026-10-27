import { CalendarClock, Eye, Pause, Play, UserX } from "lucide-react";
import type { AutorizadorItem } from "@api/types/autorizaciones/autorizadores.types";
import { Badge } from "@shared/ui/badge";
import { type DataTableColumn } from "@features/admin/shared/components/DataTable";
import { type TableColumnVisibilityItem } from "@features/admin/shared/components/TableColumnVisibility";
import {
  TableActionsHeader,
  TableToolbar,
  type TableAction,
} from "@features/admin/shared/components/TableToolbar";
import type { AccionAutorizador } from "@features/admin/modules/autorizadores/components/AutorizadorEstatusDialog";
import { accionesDisponibles } from "@features/admin/modules/autorizadores/domain/autorizador.estatus";
import {
  describirAlcance,
  describirEstatus,
  describirVigencia,
  formatFecha,
} from "@features/admin/modules/autorizadores/utils/autorizador.format";

interface Opciones {
  canEdit: boolean;
  canChangeStatus: boolean;
  onOpenDetails: (item: AutorizadorItem) => void;
  onAccion: (accion: AccionAutorizador, item: AutorizadorItem) => void;
}

export const buildAutorizadorTableColumns = ({
  canEdit,
  canChangeStatus,
  onOpenDetails,
  onAccion,
}: Opciones): DataTableColumn<AutorizadorItem>[] => [
  {
    key: "autorizador",
    header: "Autorizador",
    className: "min-w-[200px]",
    truncate: false,
    render: (row) => (
      <div className="flex min-w-0 flex-col">
        <span className="font-medium leading-snug">{row.usuario.nombreCompleto}</span>
        <span className="text-xs text-txt-muted">
          {row.usuario.usuario}
          {row.cargo ? ` · ${row.cargo}` : ""}
        </span>
      </div>
    ),
  },
  {
    key: "tipos",
    header: "Puede autorizar",
    className: "min-w-[170px]",
    truncate: false,
    render: (row) => (
      <div className="flex flex-wrap gap-1">
        {row.tipos.map((tipo) => (
          <Badge key={tipo.clave} variant="outline">
            {tipo.nombre}
          </Badge>
        ))}
      </div>
    ),
  },
  {
    key: "centros",
    header: "Centros",
    className: "min-w-[180px] max-w-[260px]",
    truncate: false,
    render: (row) => {
      const etiquetas = Array.from(new Set(row.tipos.flatMap((tipo) => describirAlcance(tipo.alcance))));
      const visibles = etiquetas.slice(0, 2);
      return (
        <span className="line-clamp-2 text-sm" title={etiquetas.join(", ")}>
          {visibles.join(", ")}
          {etiquetas.length > visibles.length ? ` y ${etiquetas.length - visibles.length} más` : ""}
        </span>
      );
    },
  },
  {
    key: "vigencia",
    header: "Vigencia",
    className: "min-w-[170px]",
    truncate: false,
    render: (row) => {
      const vigencia = describirVigencia(row.estadoVigencia);
      return (
        <div className="flex flex-col gap-1">
          <span className="text-sm tabular-nums">
            {formatFecha(row.fechaInicioVigencia)} – {formatFecha(row.fechaFinVigencia)}
          </span>
          {row.estatus !== "INACTIVO" ? (
            <Badge variant={vigencia.variante} className="w-fit">
              {vigencia.etiqueta}
            </Badge>
          ) : null}
        </div>
      );
    },
  },
  {
    key: "estatus",
    header: "Estatus",
    align: "center",
    className: "min-w-[110px]",
    render: (row) => {
      const estatus = describirEstatus(row.estatus);
      return <Badge variant={estatus.variante}>{estatus.etiqueta}</Badge>;
    },
  },
  {
    key: "modificacion",
    header: "Última modificación",
    className: "min-w-[150px]",
    truncate: false,
    render: (row) => (
      <span className="text-xs text-txt-muted">
        {(row.modificadoPor ?? row.creadoPor)?.name ?? "—"}
        <br />
        {formatFecha(row.fechaModificacion ?? row.fechaCreacion ?? "")}
      </span>
    ),
  },
  {
    key: "actions",
    header: <TableActionsHeader />,
    align: "center",
    className: "w-9 px-0",
    headerClassName: "w-9 px-0",
    render: (row) => {
      const acciones = accionesDisponibles(row);
      const items: TableAction[] = [
        { id: `ver-${row.id}`, label: "Ver detalle", icon: Eye, onSelect: () => onOpenDetails(row) },
      ];
      if (canEdit && acciones.renovar) {
        items.push({
          id: `renovar-${row.id}`,
          label: "Renovar vigencia",
          icon: CalendarClock,
          onSelect: () => onAccion("renovar", row),
        });
      }
      if (canChangeStatus && acciones.reactivar) {
        items.push({ id: `reactivar-${row.id}`, label: "Reactivar", icon: Play, onSelect: () => onAccion("reactivar", row) });
      }
      if (canChangeStatus && acciones.suspender) {
        items.push({ id: `suspender-${row.id}`, label: "Suspender", icon: Pause, onSelect: () => onAccion("suspender", row) });
      }
      if (canChangeStatus && acciones.darDeBaja) {
        items.push({ id: `sep-${row.id}`, type: "separator" });
        items.push({
          id: `baja-${row.id}`,
          label: "Dar de baja",
          icon: UserX,
          variant: "destructive",
          onSelect: () => onAccion("baja", row),
        });
      }
      return (
        <div onClick={(event) => event.stopPropagation()} onKeyDown={(event) => event.stopPropagation()}>
          <TableToolbar actions={items} />
        </div>
      );
    },
  },
];

export const AUTORIZADOR_VISIBILITY_OPTIONS: TableColumnVisibilityItem[] = [
  { key: "autorizador", label: "Autorizador" },
  { key: "tipos", label: "Puede autorizar" },
  { key: "centros", label: "Centros" },
  { key: "vigencia", label: "Vigencia" },
  { key: "estatus", label: "Estatus" },
  { key: "modificacion", label: "Última modificación" },
  { key: "actions", label: "Acciones", canHide: false },
];
