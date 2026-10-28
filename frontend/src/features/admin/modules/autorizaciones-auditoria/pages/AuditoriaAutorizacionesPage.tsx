import { useState } from "react";
import { Download, ScrollText } from "lucide-react";
import { toast } from "sonner";
import type { AuditoriaFila, AuditoriaParams } from "@api/types/autorizaciones/auditoria.types";
import type { EstatusSolicitud } from "@api/types/autorizaciones/solicitudes.types";
import { auditoriaAutorizacionesAPI } from "@api/resources/autorizaciones/auditoria.api";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import { Input } from "@shared/ui/input";
import { Label } from "@shared/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@shared/ui/select";
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import { DataTable, type DataTableColumn } from "@features/admin/shared/components/DataTable";
import { CatalogModuleLayout } from "@features/admin/modules/catalogos/shared/components/CatalogModuleLayout";
import { useCentrosAtencionList } from "@features/admin/modules/catalogos/centros-atencion/queries/useCentrosAtencionList";
import { getCatalogErrorMessage } from "@features/admin/modules/catalogos/shared/utils/catalog-feedback";
import {
  describirEstatusSolicitud,
  formatFechaHora,
} from "@features/autorizaciones/domain/solicitud.format";
import { LineaDeTiempoDialog } from "@features/admin/modules/autorizaciones-auditoria/components/LineaDeTiempoDialog";
import { useAuditoriaSolicitudes } from "@features/admin/modules/autorizaciones-auditoria/queries/useAuditoria";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";

const TODOS = "TODOS";
const TIPOS = [
  { clave: "LAB", nombre: "Laboratorio" },
  { clave: "GAB", nombre: "Gabinete" },
  { clave: "REC", nombre: "Recetas" },
  { clave: "CNO", nombre: "Cancelación de nota" },
];
const ESTATUS: EstatusSolicitud[] = ["PENDIENTE", "AUTORIZADA", "RECHAZADA", "VENCIDA", "CANCELADA"];

type Filtros = Omit<AuditoriaParams, "page" | "pageSize">;

const descargar = (blob: Blob, nombre: string) => {
  const url = URL.createObjectURL(blob);
  const enlace = document.createElement("a");
  enlace.href = url;
  enlace.download = nombre;
  document.body.appendChild(enlace);
  enlace.click();
  enlace.remove();
  URL.revokeObjectURL(url);
};

export function AuditoriaAutorizacionesPage() {
  // Permisos atomicos evaluados directo (respeta "*"): ver AutorizadoresPage.
  const { hasEffectiveRequirement } = usePermissionDependencies();
  const canRead = hasEffectiveRequirement({ allOf: ["admin:autorizaciones-auditoria:read"] });
  const canExport = canRead && hasEffectiveRequirement({ allOf: ["admin:autorizaciones-auditoria:export"] });

  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [filtros, setFiltros] = useState<Filtros>({});
  const [abierta, setAbierta] = useState<string | null>(null);
  const [exportando, setExportando] = useState(false);

  const { data, isLoading, error, refetch } = useAuditoriaSolicitudes({ ...filtros, page, pageSize }, canRead);
  const { data: centrosData } = useCentrosAtencionList({ pageSize: 200, isActive: true }, { enabled: canRead });

  const cambiar = <K extends keyof Filtros>(campo: K, valor: Filtros[K]) => {
    setFiltros((actual) => ({ ...actual, [campo]: valor }));
    setPage(1);
  };

  const exportar = async () => {
    setExportando(true);
    try {
      descargar(await auditoriaAutorizacionesAPI.exportXlsx(filtros), "auditoria_autorizaciones.xlsx");
    } catch (err) {
      toast.error("No se pudo exportar", { description: getCatalogErrorMessage(err, "Intenta nuevamente.", {}) });
    } finally {
      setExportando(false);
    }
  };

  const columnas: DataTableColumn<AuditoriaFila>[] = [
    { key: "folio", header: "Folio", render: (f) => <span className="font-medium text-txt-body">{f.folio}</span> },
    { key: "tipo", header: "Tipo", render: (f) => f.tipoNombre },
    { key: "centro", header: "Centro", render: (f) => f.centroNombre, truncate: true },
    {
      key: "estatus",
      header: "Estatus",
      render: (f) => (
        <Badge variant={describirEstatusSolicitud(f.estatus).variante}>{describirEstatusSolicitud(f.estatus).etiqueta}</Badge>
      ),
    },
    { key: "aprobaciones", header: "Aprob.", align: "center", render: (f) => `${f.aprobaciones ?? 0}/${f.aprobacionesRequeridas}` },
    { key: "solicito", header: "Solicitó", render: (f) => f.solicitanteNombre ?? "—", truncate: true },
    { key: "creada", header: "Creada", render: (f) => formatFechaHora(f.fechaCreacion) },
    { key: "resolvio", header: "Resolvió", render: (f) => f.resolvioNombre ?? "—", truncate: true },
    { key: "resuelta", header: "Resuelta", render: (f) => formatFechaHora(f.fechaResolucion) },
  ];

  return (
    <CatalogModuleLayout
      title="Auditoría de autorizaciones"
      description="Trazabilidad de cada solicitud: creación, envío, escalamiento y decisiones firmadas con cédula, IP y hash. Sin datos clínicos del paciente."
      icon={<ScrollText className="size-12" />}
    >
      {!canRead ? (
        <AdminReadOnlyNotice message="No tienes acceso a la auditoría de autorizaciones." />
      ) : (
        <>
          <div className="flex flex-wrap items-end gap-3 rounded-xl border border-line-struct px-3 py-3">
            <div className="space-y-1">
              <Label htmlFor="auditoria-desde" className="text-xs text-txt-muted">Creada desde</Label>
              <Input
                id="auditoria-desde"
                type="date"
                className="h-9 w-40"
                value={filtros.fechaDesde ?? ""}
                onChange={(e) => cambiar("fechaDesde", e.target.value || undefined)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="auditoria-hasta" className="text-xs text-txt-muted">Hasta</Label>
              <Input
                id="auditoria-hasta"
                type="date"
                className="h-9 w-40"
                value={filtros.fechaHasta ?? ""}
                onChange={(e) => cambiar("fechaHasta", e.target.value || undefined)}
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs text-txt-muted">Tipo</Label>
              <Select value={filtros.tipo ?? TODOS} onValueChange={(v) => cambiar("tipo", v === TODOS ? undefined : v)}>
                <SelectTrigger className="h-9 w-48" aria-label="Tipo">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={TODOS}>Todos</SelectItem>
                  {TIPOS.map((t) => (
                    <SelectItem key={t.clave} value={t.clave}>{t.nombre}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label className="text-xs text-txt-muted">Estatus</Label>
              <Select
                value={filtros.estatus ?? TODOS}
                onValueChange={(v) => cambiar("estatus", v === TODOS ? undefined : (v as EstatusSolicitud))}
              >
                <SelectTrigger className="h-9 w-40" aria-label="Estatus">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={TODOS}>Todos</SelectItem>
                  {ESTATUS.map((e) => (
                    <SelectItem key={e} value={e}>{describirEstatusSolicitud(e).etiqueta}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label className="text-xs text-txt-muted">Centro</Label>
              <Select
                value={filtros.centroId ? String(filtros.centroId) : TODOS}
                onValueChange={(v) => cambiar("centroId", v === TODOS ? undefined : Number(v))}
              >
                <SelectTrigger className="h-9 w-56" aria-label="Centro">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={TODOS}>Todos</SelectItem>
                  {(centrosData?.items ?? []).map((c) => (
                    <SelectItem key={c.id} value={String(c.id)}>{c.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {canExport ? (
              <Button className="ml-auto" variant="outline" onClick={() => void exportar()} disabled={exportando}>
                <Download className="size-4" /> {exportando ? "Exportando…" : "Exportar a Excel"}
              </Button>
            ) : null}
          </div>

          <DataTable
            columns={columnas}
            rows={data?.items ?? []}
            isLoading={isLoading}
            isError={Boolean(error)}
            errorTitle="No se pudo cargar la auditoría"
            errorDescription={error ? getCatalogErrorMessage(error, "Intenta nuevamente.", {}) : undefined}
            hasFilters={Object.values(filtros).some(Boolean)}
            onClearFilters={() => {
              setFiltros({});
              setPage(1);
            }}
            onRetry={() => void refetch()}
            onRowClick={(fila) => setAbierta(fila.uuid)}
            getRowKey={(fila) => fila.uuid}
            emptyTitle="Sin solicitudes"
            emptyDescription="No hay solicitudes de autorización con estos filtros."
            minWidthClassName="min-w-[1000px]"
            pagination={{
              page,
              pageSize,
              total: data?.total ?? 0,
              totalPages: data?.totalPages ?? 1,
              onPageChange: setPage,
              onPageSizeChange: (valor) => {
                setPageSize(valor);
                setPage(1);
              },
            }}
          />

          <LineaDeTiempoDialog uuid={abierta} onClose={() => setAbierta(null)} />
        </>
      )}
    </CatalogModuleLayout>
  );
}

export default AuditoriaAutorizacionesPage;
