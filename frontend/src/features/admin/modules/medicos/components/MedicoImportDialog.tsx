import { useId, useMemo, useState } from "react";
import { toast } from "sonner";
import {
  CircleAlert,
  Download,
  FileSpreadsheet,
  RotateCcw,
  Upload,
} from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@shared/ui/alert";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@shared/ui/dialog";
import { Input } from "@shared/ui/input";
import { Label } from "@shared/ui/label";
import { cn } from "@shared/utils/styling/cn";
import { DataTable } from "@features/admin/shared/components/DataTable";
import type { MedicoImportResult } from "@api/types/medicos.types";
import { useMedicoImportPreview } from "@features/admin/modules/medicos/hooks/useMedicoImportPreview";
import { useMedicoImportConfirm } from "@features/admin/modules/medicos/hooks/useMedicoImportConfirm";
import { useMedicoImportTemplateDownload } from "@features/admin/modules/medicos/hooks/useMedicoImportTemplateDownload";
import { buildMedicoImportPreviewColumns } from "@features/admin/modules/medicos/components/buildMedicoImportPreviewColumns";
// Reusa el resolver generico de codigo->mensaje ya usado por el import de
// usuarios (funcion pura y exportada, no un helper privado de
// `users.api.ts` -- no aplica el criterio de "duplicar" de ese archivo).
import { resolveApiErrorMessage } from "@/domains/auth-access/adapters/rbac/shared/rbac-feedback";

interface MedicoImportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const ACCEPTED_FILE = ".xlsx";
const DEFAULT_PAGE_SIZE = 10;

const MEDICO_IMPORT_ERROR_MESSAGES: Record<string, string> = {
  IMPORT_FILE_INVALID: "El archivo debe ser un Excel (.xlsx) válido.",
  IMPORT_HEADERS_MISMATCH:
    "Las columnas del archivo no coinciden con la plantilla de médicos.",
  IMPORT_TOO_MANY_ROWS: "El archivo excede el máximo de filas permitido.",
  IMPORT_HAS_ERRORS:
    "El archivo tiene filas con error. Corrígelas y volvé a subirlo.",
  MEDICO_IMPORT_RACE:
    "Algo cambió entre la vista previa y la confirmación. No se creó ningún médico; volvé a intentarlo.",
  VALIDATION_ERROR: "Revisa el archivo antes de continuar.",
};

const getMedicoImportErrorMessage = (error: unknown, fallback: string) =>
  resolveApiErrorMessage(error, fallback, MEDICO_IMPORT_ERROR_MESSAGES);

export function MedicoImportDialog({ open, onOpenChange }: MedicoImportDialogProps) {
  const fileInputId = useId();
  const preview = useMedicoImportPreview();
  const confirmImport = useMedicoImportConfirm();
  const { download, isDownloading } = useMedicoImportTemplateDownload();

  const [file, setFile] = useState<File | null>(null);
  const [previewResult, setPreviewResult] = useState<MedicoImportResult | null>(
    null,
  );
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);

  const columns = useMemo(() => buildMedicoImportPreviewColumns(), []);

  const rows = previewResult?.rows ?? [];
  const totalPages = Math.max(1, Math.ceil(rows.length / pageSize));
  const pageStart = (page - 1) * pageSize;
  const pageRows = rows.slice(pageStart, pageStart + pageSize);

  const resetFlow = () => {
    setFile(null);
    setPreviewResult(null);
    setPage(1);
    setPageSize(DEFAULT_PAGE_SIZE);
  };

  const handleDialogOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) {
      resetFlow();
    }
    onOpenChange(nextOpen);
  };

  const handlePreview = async () => {
    if (!file || preview.isPending) return;

    try {
      const result = await preview.mutateAsync({ file });
      setPreviewResult(result);
      setPage(1);

      const validRows = result.totalRecords - result.totalErrores;
      toast.success("Vista previa generada", {
        description:
          result.totalErrores > 0
            ? `${validRows} fila${validRows !== 1 ? "s" : ""} valida${validRows !== 1 ? "s" : ""} y ${result.totalErrores} con error.`
            : `${result.totalRecords} fila${result.totalRecords !== 1 ? "s" : ""} lista${result.totalRecords !== 1 ? "s" : ""} para importar.`,
      });
    } catch (error) {
      toast.error("No se pudo procesar el archivo", {
        description: getMedicoImportErrorMessage(
          error,
          "Verifica el archivo e intenta nuevamente.",
        ),
      });
    }
  };

  const canConfirm =
    previewResult !== null &&
    previewResult.totalRecords > 0 &&
    previewResult.totalErrores === 0;

  const handleConfirm = async () => {
    if (!file || !canConfirm || confirmImport.isPending) return;

    try {
      const result = await confirmImport.mutateAsync({ file });
      setPreviewResult(result);
      setPage(1);

      if (result.totalErrores > 0) {
        toast.error("La importacion tiene filas con error", {
          description:
            "No se creo ningun médico. Corrige el archivo y volve a subirlo.",
        });
        return;
      }

      toast.success("Médicos importados", {
        description: `${result.inserted} médico${result.inserted !== 1 ? "s" : ""} se ${result.inserted !== 1 ? "crearon" : "creo"} correctamente.`,
      });
      handleDialogOpenChange(false);
    } catch (error) {
      toast.error("No se pudo confirmar la importacion", {
        description: getMedicoImportErrorMessage(
          error,
          "No se creo ningun médico. Intenta nuevamente.",
        ),
      });
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleDialogOpenChange}>
      <DialogContent className="w-[95vw] max-w-none rounded-3xl bg-paper p-0 sm:w-[92vw] sm:max-w-[92vw] lg:w-215 lg:max-w-215 xl:w-235 xl:max-w-235">
        <div className="flex min-w-0 max-h-[88vh] flex-col">
          <DialogHeader className="px-8 pt-8">
            <DialogTitle>Importar médicos desde Excel</DialogTitle>
            <DialogDescription>
              Descarga la plantilla, completala y sube el archivo para
              previsualizar los médicos antes de confirmar la creacion.
            </DialogDescription>
          </DialogHeader>

          <div className="flex-1 space-y-6 overflow-y-auto px-8 pb-8 pt-4">
            <section className="space-y-4 rounded-2xl border border-line-struct bg-paper p-4 sm:p-5">
              <Button
                type="button"
                variant="outline"
                onClick={() => void download()}
                disabled={isDownloading}
              >
                <Download className="size-4" />
                {isDownloading ? "Descargando..." : "Descargar plantilla"}
              </Button>

              <div className="space-y-1.5 text-xs text-txt-muted">
                <p>
                  Columnas, en este orden:{" "}
                  <strong>ID del Médico</strong>,{" "}
                  <strong>Usuario (Login del sistema)</strong>, Nombre del
                  Médico, Tipo de Médico, Servicio, Estatus del Médico,
                  Observaciones.
                </p>
                <p>
                  Obligatorio: <strong>Usuario (Login del sistema)</strong>{" "}
                  (debe existir en el sistema y no tener ya un perfil de
                  médico). El resto es opcional.
                </p>
                <p>
                  ID del Médico identifica al médico en el sistema
                  legado; valores como &quot;S/C&quot;, &quot;SN&quot; o
                  vacío se interpretan como &quot;sin ID&quot; (no como
                  un ID literal).
                </p>
                <p>
                  Tipo de Médico acepta &quot;Clínica&quot;, &quot;Hospital&quot;
                  o &quot;Ambos&quot; (vacío se interpreta como Clínica).
                  Estatus del Médico acepta Activo, Vacaciones, Incapacidad,
                  Suspendido o Baja (vacío se interpreta como Activo).
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor={fileInputId}>Archivo Excel</Label>
                <label
                  htmlFor={fileInputId}
                  className={cn(
                    "group flex cursor-pointer items-center gap-2 rounded-2xl border border-dashed border-line-struct bg-subtle/40 px-4 py-3 transition-colors",
                    "hover:border-brand/60 hover:bg-brand/5",
                    file && "border-brand/50 bg-brand/5",
                  )}
                >
                  <FileSpreadsheet className="size-4 shrink-0 text-txt-muted transition-colors group-hover:text-brand" />
                  <span className="truncate text-sm text-txt-body">
                    {file ? file.name : "Seleccionar archivo .xlsx"}
                  </span>
                  <Input
                    id={fileInputId}
                    type="file"
                    accept={ACCEPTED_FILE}
                    className="sr-only"
                    onChange={(event) => {
                      setFile(event.target.files?.[0] ?? null);
                      setPreviewResult(null);
                    }}
                  />
                </label>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Button
                  type="button"
                  onClick={() => void handlePreview()}
                  disabled={!file || preview.isPending}
                >
                  <Upload className="size-4" />
                  {preview.isPending ? "Validando..." : "Validar archivo"}
                </Button>

                {previewResult ? (
                  <Button type="button" variant="outline" onClick={resetFlow}>
                    <RotateCcw className="size-4" />
                    Limpiar
                  </Button>
                ) : null}
              </div>
            </section>

            {previewResult ? (
              <section className="space-y-4">
                {previewResult.totalErrores > 0 ? (
                  <Alert variant="critical">
                    <CircleAlert className="size-4" />
                    <AlertTitle>La importacion tiene filas con error</AlertTitle>
                    <AlertDescription>
                      Corrige el archivo y volve a subirlo. Ningun médico se
                      crea hasta que el lote quede sin errores.
                    </AlertDescription>
                  </Alert>
                ) : (
                  <Alert variant="success">
                    <AlertTitle>Vista previa lista</AlertTitle>
                    <AlertDescription>
                      Todas las filas ({previewResult.totalRecords}) son
                      validas para importar.
                    </AlertDescription>
                  </Alert>
                )}

                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="rounded-xl border border-line-struct bg-subtle/40 px-4 py-3">
                    <p className="text-xs text-txt-muted">Total de filas</p>
                    <p className="mt-1 text-lg font-semibold text-txt-body">
                      {previewResult.totalRecords}
                    </p>
                  </div>
                  <div className="rounded-xl border border-line-struct bg-subtle/40 px-4 py-3">
                    <p className="text-xs text-txt-muted">Filas con error</p>
                    <div className="mt-1 flex items-center gap-2">
                      <p className="text-lg font-semibold text-txt-body">
                        {previewResult.totalErrores}
                      </p>
                      <Badge
                        variant={
                          previewResult.totalErrores > 0
                            ? "critical"
                            : "secondary"
                        }
                      >
                        {previewResult.totalErrores > 0
                          ? "Con errores"
                          : "Sin errores"}
                      </Badge>
                    </div>
                  </div>
                  <div className="rounded-xl border border-line-struct bg-subtle/40 px-4 py-3">
                    <p className="text-xs text-txt-muted">
                      Médicos creados
                    </p>
                    <p className="mt-1 text-lg font-semibold text-txt-body">
                      {previewResult.inserted}
                    </p>
                  </div>
                </div>

                <DataTable
                  columns={columns}
                  rows={pageRows}
                  minWidthClassName="min-w-[1440px]"
                  getRowKey={(row, index) => `${row.row}-${index}`}
                  getRowClassName={(row) =>
                    row.errors.length > 0
                      ? "bg-status-critical/5 hover:bg-status-critical/10"
                      : undefined
                  }
                  emptyTitle="Sin filas para mostrar"
                  emptyDescription="La vista previa no contiene filas procesadas."
                  pagination={{
                    page,
                    pageSize,
                    total: rows.length,
                    totalPages,
                    onPageChange: setPage,
                    onPageSizeChange: (nextPageSize) => {
                      setPageSize(nextPageSize);
                      setPage(1);
                    },
                  }}
                />
              </section>
            ) : null}
          </div>

          <DialogFooter className="flex flex-col gap-3 border-t border-line-struct px-8 py-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="text-xs text-txt-muted">
              {previewResult && previewResult.totalErrores > 0
                ? "Hay filas con error: corrige el archivo y volve a subirlo. No se puede confirmar parcialmente."
                : "La importacion es todo-o-nada: si hay filas con error, no se crea ningun médico."}
            </div>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Button
                type="button"
                variant="outline"
                onClick={() => handleDialogOpenChange(false)}
              >
                Cerrar
              </Button>
              <Button
                type="button"
                onClick={() => void handleConfirm()}
                disabled={!canConfirm || confirmImport.isPending}
              >
                {confirmImport.isPending
                  ? "Importando..."
                  : "Confirmar e importar"}
              </Button>
            </div>
          </DialogFooter>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default MedicoImportDialog;
