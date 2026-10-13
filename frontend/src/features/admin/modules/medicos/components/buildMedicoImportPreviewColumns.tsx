import { AlertTriangle, CheckCircle2, Info } from "lucide-react";
import { Badge } from "@shared/ui/badge";
import type { EstatusMedico, MedicoImportRow } from "@api/types/medicos.types";
import { type DataTableColumn } from "@features/admin/shared/components/DataTable";

// Duplicados a propósito de los labels privados de
// `MedicoTableColumns.tsx` (mismo criterio de "duplicar, no extraer" que
// los helpers de `medicos.api.ts`).
const ESTATUS_MEDICO_LABELS: Record<EstatusMedico, string> = {
  ACTIVO: "Activo",
  VACACIONES: "Vacaciones",
  INCAPACIDAD: "Incapacidad",
  SUSPENDIDO: "Suspendido",
  BAJA: "Baja",
};

const SEXO_LABELS: Record<"M" | "F" | "O", string> = {
  M: "Masculino",
  F: "Femenino",
  O: "Otro",
};

// "1975-03-15" -> "15/03/1975" (sin pasar por Date: evita corrimientos de zona).
const formatFechaNac = (iso: string | null) => {
  if (!iso) return "—";
  const [y, m, d] = iso.slice(0, 10).split("-");
  return d && m && y ? `${d}/${m}/${y}` : iso;
};

const nombreCompleto =(row: MedicoImportRow) =>
  [row.data.nombre, row.data.paterno, row.data.materno]
    .filter(Boolean)
    .join(" ");

/**
 * Columnas de la tabla de vista previa de importación masiva de médicos.
 * Refleja el orden de la plantilla: No. Médico | Usuario | Nombre(s) y
 * Apellidos | Cédula | Escuela | Sexo | Fecha de Nacimiento | Especialidad |
 * Servicio | Estatus.
 * "Resultado" distingue errores (rojo, bloquean) de warnings (ámbar, no
 * bloquean).
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
      key: "noMedico",
      header: "No. Médico",
      align: "center",
      className: "w-[110px]",
      render: (row) => row.data.noMedico ?? "—",
    },
    {
      key: "usuario",
      header: "Usuario (Login del sistema)",
      className: "w-[140px]",
      render: (row) => row.data.usuario || "—",
    },
    {
      key: "nombre",
      header: "Nombre(s) y Apellidos",
      className: "w-[200px]",
      render: (row) => nombreCompleto(row) || "—",
    },
    {
      key: "cedulaProfesional",
      header: "Cédula Profesional",
      className: "w-[140px]",
      render: (row) => row.data.cedulaProfesional || "—",
    },
    {
      key: "escuela",
      header: "Escuela",
      className: "w-[170px]",
      render: (row) =>
        row.data.escuela
          ? `${row.data.escuela}${row.data.escuelaId ? "" : " (sin match)"}`
          : "—",
    },
    {
      key: "sexo",
      header: "Sexo",
      align: "center",
      className: "w-[110px]",
      render: (row) => (row.data.sexo ? SEXO_LABELS[row.data.sexo] : "—"),
    },
    {
      key: "fechaNac",
      header: "Fecha de Nacimiento",
      align: "center",
      className: "w-[130px]",
      render: (row) => formatFechaNac(row.data.fechaNac),
    },
    {
      key: "especialidad",
      header: "Especialidad",
      className: "w-[170px]",
      render: (row) =>
        row.data.especialidad
          ? `${row.data.especialidad}${row.data.especialidadId ? "" : " (sin match)"}`
          : "—",
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
      className: "w-[300px]",
      cellContentClassName: "mx-auto flex justify-center",
      truncate: false,
      render: (row) => {
        if (row.errors.length === 0 && row.warnings.length === 0) {
          return (
            <Badge variant="stable">
              <CheckCircle2 className="size-3" />
              Sin errores
            </Badge>
          );
        }

        return (
          <div className="flex flex-col items-center gap-1">
            {row.errors.map((message, index) => (
              <Badge
                key={`e-${index}`}
                variant="critical"
                className="max-w-full whitespace-normal text-left"
              >
                <AlertTriangle className="size-3 shrink-0" />
                <span>{message}</span>
              </Badge>
            ))}
            {row.warnings.map((message, index) => (
              <Badge
                key={`w-${index}`}
                variant="alert"
                className="max-w-full whitespace-normal text-left"
              >
                <Info className="size-3 shrink-0" />
                <span>{message}</span>
              </Badge>
            ))}
          </div>
        );
      },
    },
  ];
}
