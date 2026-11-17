import { useEffect, useRef, useState } from "react";
import { CheckCircle2, FileSpreadsheet, RotateCcw, Upload } from "lucide-react";
import { toast } from "sonner";
import { Alert, AlertDescription, AlertTitle } from "@shared/ui/alert";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import {
  type CiesPreviewResponse,
  type CiesUploadRow,
} from "@api/resources/catalogos/cies.api";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import { useCiesConfirmImport } from "@features/admin/modules/catalogos/cies/mutations/useCiesConfirmImport";
import { CatalogModuleLayout } from "@features/admin/modules/catalogos/shared/components/CatalogModuleLayout";
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import { DataTable } from "@features/admin/shared/components/DataTable";
import { TableHeaderBar } from "@features/admin/shared/components/TableHeaderBar";
import {
  TableOptionsMenu,
  type TableOptionItem,
} from "@features/admin/shared/components/TableOptionsMenu";
import { TableSearch } from "@features/admin/shared/components/TableSearch";
import {
  CiesUploadForm,
  type CiesUploadFormRef,
} from "@features/admin/modules/catalogos/cies/components/CiesUploadForm";
import { CIES_PREVIEW_COLUMNS } from "@features/admin/modules/catalogos/cies/components/CiesPreviewTableColumns";
import { CiesRegisteredSection } from "@features/admin/modules/catalogos/cies/components/CiesRegisteredSection";

const DEFAULT_PAGE_SIZE = 10;

const normalizeValue = (value: string | null | undefined) =>
  String(value ?? "")
    .trim()
    .toLowerCase();

const getPreviewAlertProps = (
  result: CiesPreviewResponse,
  confirmed: boolean,
): {
  variant: "success" | "critical" | "warning" | "info";
  title: string;
  description: string;
} => {
  const validRows = result.total_records - result.total_errores;

  if (confirmed) {
    return {
      variant: "success",
      title: "Importacion completada",
      description:
        result.total_errores > 0
          ? `Se importaron ${validRows} registros validos y se omitieron ${result.total_errores} con error.`
          : `Se importaron ${validRows} registros sin errores.`,
    };
  }

  if (result.total_errores === result.total_records) {
    return {
      variant: "critical",
      title: "No hay filas validas para importar",
      description:
        "Corrige el archivo y vuelve a ejecutar la vista previa para continuar.",
    };
  }

  if (result.total_errores === 0) {
    return {
      variant: "info",
      title: "Vista previa lista",
      description: `Todas las filas (${result.total_records}) son validas para importar.`,
    };
  }

  return {
    variant: "warning",
    title: "Vista previa con observaciones",
    description: `Se detectaron ${result.total_errores} filas con error. Se pueden importar ${validRows} filas validas.`,
  };
};

export function CiesPage() {
  const uploadRef = useRef<CiesUploadFormRef>(null);
  const { hasCapability } = usePermissionDependencies();
  const ciesConfirmImport = useCiesConfirmImport();

  const [previewResult, setPreviewResult] =
    useState<CiesPreviewResponse | null>(null);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [isPreviewPending, setIsPreviewPending] = useState(false);
  const [isConfirmPending, setIsConfirmPending] = useState(false);
  const [isConfirmed, setIsConfirmed] = useState(false);

  const canUploadCies = hasCapability("admin.catalogs.cies.upload", {
    allOf: ["admin:catalogos:cies:upload"],
  });

  const rows = previewResult?.rows ?? [];
  const normalizedSearch = search.trim().toLowerCase();
  const filteredRows =
    normalizedSearch.length === 0
      ? rows
      : rows.filter((row) => {
          const clave = normalizeValue(row.CLAVE);
          const descripcion = normalizeValue(row.DESCRIPCION);
          const error = normalizeValue(row.ERROR);
          return (
            clave.includes(normalizedSearch) ||
            descripcion.includes(normalizedSearch) ||
            error.includes(normalizedSearch)
          );
        });

  const totalFilteredRows = filteredRows.length;
  const totalPages = Math.max(1, Math.ceil(totalFilteredRows / pageSize));
  const pageStart = (page - 1) * pageSize;
  const pageRows = filteredRows.slice(pageStart, pageStart + pageSize);

  useEffect(() => {
    if (page <= totalPages) {
      return;
    }

    setPage(totalPages);
  }, [page, totalPages]);

  const validRows =
    previewResult === null
      ? 0
      : Math.max(previewResult.total_records - previewResult.total_errores, 0);
  const previewAlert = previewResult
    ? getPreviewAlertProps(previewResult, isConfirmed)
    : null;
  const canConfirmImport =
    canUploadCies &&
    previewResult !== null &&
    !isConfirmed &&
    previewResult.total_errores < previewResult.total_records;

  const handlePreview = async () => {
    if (!canUploadCies || isPreviewPending) {
      return;
    }

    setIsPreviewPending(true);
    setPreviewResult(null);
    setIsConfirmed(false);
    setSearch("");
    setPage(1);

    try {
      const response = await uploadRef.current?.preview();

      if (!response) {
        toast.error("No se pudo generar la vista previa", {
          description:
            "Verifica el archivo y la version antes de intentar de nuevo.",
        });
        return;
      }

      setPreviewResult(response);
      const nextValidRows = response.total_records - response.total_errores;

      toast.success("Vista previa generada", {
        description:
          response.total_errores > 0
            ? `${nextValidRows} filas validas y ${response.total_errores} con error.`
            : `${response.total_records} filas listas para importar.`,
      });
    } catch {
      toast.error("No se pudo procesar el archivo", {
        description: "Intenta nuevamente con un archivo valido.",
      });
    } finally {
      setIsPreviewPending(false);
    }
  };

  const handleConfirmImport = async () => {
    if (!previewResult || !canConfirmImport || isConfirmPending) {
      return;
    }

    setIsConfirmPending(true);

    try {
      const response = await ciesConfirmImport.mutateAsync(previewResult.rows);
      setIsConfirmed(true);
      toast.success("Importacion completada", {
        description:
          response.total_errores > 0
            ? `${response.inserted} filas importadas. ${response.total_errores} filas omitidas por error.`
            : `${response.inserted} filas importadas correctamente.`,
      });
    } catch {
      toast.error("No se pudo confirmar la importacion", {
        description:
          "El catalogo no se actualizo. Revisa la vista previa e intenta nuevamente.",
      });
    } finally {
      setIsConfirmPending(false);
    }
  };

  const handleReset = () => {
    setPreviewResult(null);
    setIsConfirmed(false);
    setSearch("");
    setPage(1);
    toast.message("Flujo limpiado", {
      description:
        "Puedes cargar un nuevo archivo para iniciar otra importacion.",
    });
  };

  const tableOptions: TableOptionItem[] = [];

  if (previewResult && !isConfirmed) {
    tableOptions.push({
      id: "refresh-preview",
      label: "Actualizar vista previa",
      icon: RotateCcw,
      isLoading: isPreviewPending,
      disabled: isPreviewPending,
      onSelect: () => handlePreview(),
    });
  }

  if (previewResult || isConfirmed) {
    tableOptions.push({
      id: "reset-flow",
      label: "Limpiar flujo",
      icon: RotateCcw,
      onSelect: handleReset,
    });
  }

  return (
    <CatalogModuleLayout
      title="Catalogo CIE"
      description="Claves CIE registradas y carga masiva por archivo con validacion previa."
      icon={<FileSpreadsheet className="size-12" />}
    >
      {!canUploadCies ? (
        <AdminReadOnlyNotice message="No tienes acceso para importar catalogos CIE." />
      ) : null}

      <section className="space-y-4 rounded-2xl border border-line-struct bg-paper p-4 sm:p-5">
        <CiesUploadForm ref={uploadRef} />

        <div className="flex flex-wrap items-center gap-2">
          <Button
            onClick={() => {
              void handlePreview();
            }}
            disabled={!canUploadCies || isPreviewPending}
          >
            <Upload className="size-4" />
            {isPreviewPending ? "Procesando..." : "Previsualizar informacion"}
          </Button>

          {canConfirmImport ? (
            <Button
              variant="secondary"
              onClick={() => {
                void handleConfirmImport();
              }}
              disabled={isConfirmPending}
            >
              <CheckCircle2 className="size-4" />
              {isConfirmPending
                ? "Importando..."
                : "Confirmar importacion de filas validas"}
            </Button>
          ) : null}

          {previewResult || isConfirmed ? (
            <Button variant="outline" onClick={handleReset}>
              <RotateCcw className="size-4" />
              Limpiar
            </Button>
          ) : null}
        </div>
      </section>

      {previewResult ? (
        <section className="space-y-4">
          <Alert variant={previewAlert?.variant}>
            <AlertTitle>{previewAlert?.title}</AlertTitle>
            <AlertDescription>{previewAlert?.description}</AlertDescription>
          </Alert>

          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-xl border border-line-struct bg-subtle/40 px-4 py-3">
              <p className="text-xs text-txt-muted">Total de filas</p>
              <p className="mt-1 text-lg font-semibold text-txt-body">
                {previewResult.total_records}
              </p>
            </div>
            <div className="rounded-xl border border-line-struct bg-subtle/40 px-4 py-3">
              <p className="text-xs text-txt-muted">Filas con error</p>
              <div className="mt-1 flex items-center gap-2">
                <p className="text-lg font-semibold text-txt-body">
                  {previewResult.total_errores}
                </p>
                <Badge
                  variant={
                    previewResult.total_errores > 0 ? "critical" : "secondary"
                  }
                >
                  {previewResult.total_errores > 0
                    ? "Con errores"
                    : "Sin errores"}
                </Badge>
              </div>
            </div>
            <div className="rounded-xl border border-line-struct bg-subtle/40 px-4 py-3">
              <p className="text-xs text-txt-muted">Filas validas</p>
              <div className="mt-1 flex items-center gap-2">
                <p className="text-lg font-semibold text-txt-body">
                  {validRows}
                </p>
                <Badge variant={validRows > 0 ? "stable" : "secondary"}>
                  {validRows > 0 ? "Listas" : "Sin filas validas"}
                </Badge>
              </div>
            </div>
          </div>

          <TableHeaderBar
            search={
              <TableSearch
                value={search}
                onChange={(nextValue) => {
                  setSearch(nextValue);
                  setPage(1);
                }}
                placeholder="Buscar por clave, descripcion o error"
                disabled={rows.length === 0}
              />
            }
            actions={<TableOptionsMenu options={tableOptions} />}
          />

          <DataTable<CiesUploadRow>
            columns={CIES_PREVIEW_COLUMNS}
            rows={pageRows}
            hasFilters={Boolean(normalizedSearch)}
            onClearFilters={() => {
              setSearch("");
              setPage(1);
            }}
            pagination={{
              page,
              pageSize,
              total: totalFilteredRows,
              totalPages,
              onPageChange: setPage,
              onPageSizeChange: (nextPageSize) => {
                setPageSize(nextPageSize);
                setPage(1);
              },
            }}
            getRowKey={(row, index) => `${row.CLAVE}-${index}`}
            emptyTitle="Sin filas para mostrar"
            emptyDescription="La vista previa no contiene filas procesadas."
            noResultsTitle="Sin coincidencias"
            noResultsDescription="Ajusta el termino de busqueda para ver resultados."
          />
        </section>
      ) : null}

      <CiesRegisteredSection />
    </CatalogModuleLayout>
  );
}

export default CiesPage;
