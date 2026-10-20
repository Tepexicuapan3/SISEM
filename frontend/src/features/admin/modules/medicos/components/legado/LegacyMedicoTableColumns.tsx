import { Badge } from "@shared/ui/badge";
import type { LegacyMedicoItem } from "@api/types/medicos.types";
import { type DataTableColumn } from "@features/admin/shared/components/DataTable";

const MUTED = <span className="text-txt-muted">—</span>;

const ESTATUS_LEGADO: Record<string, { label: string; variant: "stable" | "secondary" | "outline" }> = {
  A: { label: "A · Activo", variant: "stable" },
  B: { label: "B · Baja", variant: "secondary" },
};

const claveDescripcion = (v: LegacyMedicoItem["clinica"]) => {
  if (!v || (v.clave == null && !v.descripcion)) return MUTED;
  return (
    <span className="truncate text-sm">
      {v.descripcion ?? v.clave}
      {v.clave != null && v.descripcion ? (
        <span className="ml-1 text-xs text-txt-muted">({v.clave})</span>
      ) : null}
    </span>
  );
};

/** Columnas del archivo legado: solo lectura, sin columna de acciones. */
export const buildLegacyMedicosColumns = (): DataTableColumn<LegacyMedicoItem>[] => [
  {
    key: "noMedico",
    header: "No. Médico",
    className: "w-[100px]",
    render: (row) => <span className="font-mono text-sm text-txt-muted">{row.noMedico}</span>,
  },
  {
    key: "nombre",
    header: "Nombre",
    className: "w-[260px]",
    render: (row) => (
      <span className="truncate text-sm font-medium text-txt-body">
        {row.nombreCompleto || "—"}
      </span>
    ),
  },
  {
    key: "claveRh",
    header: "Clave RH",
    className: "w-[100px]",
    render: (row) => <span className="font-mono text-sm">{row.claveRh}</span>,
  },
  {
    key: "cedula",
    header: "Cédula",
    className: "w-[120px]",
    render: (row) => (row.cedula ? <span className="font-mono text-sm">{row.cedula}</span> : MUTED),
  },
  {
    key: "clinica",
    header: "Clínica",
    className: "w-[180px]",
    cellContentClassName: "max-w-[170px]",
    render: (row) => claveDescripcion(row.clinica),
  },
  {
    key: "especialidad",
    header: "Especialidad",
    className: "w-[180px]",
    cellContentClassName: "max-w-[170px]",
    render: (row) => claveDescripcion(row.especialidad),
  },
  {
    key: "estatus",
    header: "Estatus",
    align: "center",
    className: "w-[110px]",
    render: (row) => {
      const cfg = ESTATUS_LEGADO[row.estatus] ?? { label: row.estatus, variant: "outline" as const };
      return (
        <Badge variant={cfg.variant} className="text-xs">
          {cfg.label}
        </Badge>
      );
    },
  },
  {
    key: "medicoActual",
    header: "Médico actual",
    className: "w-[220px]",
    render: (row) =>
      row.medicoActual ? (
        <span className="truncate text-sm">{row.medicoActual.nombreCompleto}</span>
      ) : (
        MUTED
      ),
  },
];
