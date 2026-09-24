import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { Badge } from "@shared/ui/badge";
import type {
  EstatusMedico,
  MedicoImportRow,
  TipoMedico,
} from "@api/types/medicos.types";
import { type DataTableColumn } from "@features/admin/shared/components/DataTable";

// Duplicados a propósito de los labels privados de
// `MedicoTableColumns.tsx` (mismo criterio de "duplicar, no extraer" que
// los helpers de `medicos.api.ts`).
const TIPO_MEDICO_LABELS: Record<TipoMedico, string> = {
  CLINICA: "Clínica",
  HOSPITAL: "Hospital",
  AMBOS: "Clínica / Hospital",
};

const ESTATUS_MEDICO_LABELS: Record<EstatusMedico, string> = {
  ACTIVO: "Activo",
  VACACIONES: "Vacaciones",
  INCAPACIDAD: "Incapacidad",
  SUSPENDIDO: "Suspendido",
  BAJA: "Baja",
};

/**
 * Columnas de la tabla de vista previa de importación masiva de médicos.
 * Refleja el orden de la plantilla: ID del Médico | Usuario (Login del
 * sistema) | Nombre del Médico | Tipo de Médico | Servicio | Estatus del
 * Médico | Observaciones.
 */
export function buildMedicoImportPreviewColumns(): DataTableColumn<MedicoImportRow>[] {
  return [
    {
      key: "row",
      header: "Fila",
      align: "center",
      className: "w-[70px]",
      render: (row) => row.row,
    },
    {
      key: "legacyCdMedico",
      header: "ID del Médico",
      className: "w-[120px]",
      render: (row) => row.data.legacyCdMedico || "—",
    },
    {
      key: "usuario",
      header: "Usuario (Login del sistema)",
      className: "w-[140px]",
      render: (row) => row.data.usuario || "—",
    },
    {
      key: "nombreDisplay",
      header: "Nombre del Médico",
      className: "w-[200px]",
      render: (row) => row.data.nombreDisplay || "—",
    },
    {
      key: "tipoMedico",
      header: "Tipo de Médico",
      className: "w-[150px]",
      render: (row) => TIPO_MEDICO_LABELS[row.data.tipoMedico] || row.data.tipoMedico,
    },
    {
      key: "servicio",
      header: "Servicio",
      className: "w-[160px]",
      render: (row) => row.data.servicio || "—",
    },
    {
      key: "estatusMedico",
      header: "Estatus del Médico",
      align: "center",
      className: "w-[110px]",
      render: (row) => ESTATUS_MEDICO_LABELS[row.data.estatusMedico] || row.data.estatusMedico,
    },
    {
      key: "errors",
      header: "Resultado",
      align: "center",
      className: "w-[280px]",
      cellContentClassName: "mx-auto flex justify-center",
      truncate: false,
      render: (row) => {
        if (row.errors.length > 0) {
          return (
            <div className="flex flex-col items-center gap-1">
              {row.errors.map((message, index) => (
                <Badge
                  key={index}
                  variant="critical"
                  className="max-w-full whitespace-normal text-left"
                >
                  <AlertTriangle className="size-3 shrink-0" />
                  <span>{message}</span>
                </Badge>
              ))}
            </div>
          );
        }

        return (
          <Badge variant="stable">
            <CheckCircle2 className="size-3" />
            Sin errores
          </Badge>
        );
      },
    },
  ];
}
