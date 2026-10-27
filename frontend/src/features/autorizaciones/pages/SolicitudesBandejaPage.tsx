import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Inbox } from "lucide-react";
import type { EstatusSolicitud, SolicitudResumen } from "@api/types/autorizaciones/solicitudes.types";
import { Badge } from "@shared/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@shared/ui/tabs";
import { useDebounce } from "@shared/hooks/useDebounce";
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import { DataTable, type DataTableColumn } from "@features/admin/shared/components/DataTable";
import { TableHeaderBar } from "@features/admin/shared/components/TableHeaderBar";
import { TableSearch } from "@features/admin/shared/components/TableSearch";
import { CatalogModuleLayout } from "@features/admin/modules/catalogos/shared/components/CatalogModuleLayout";
import {
  describirEstatusSolicitud,
  formatFechaHora,
  ORIGENES,
  rutaDetalle,
  tiempoRestante,
} from "@features/autorizaciones/domain/solicitud.format";
import { useSolicitudesList } from "@features/autorizaciones/queries/useSolicitudes";
import { getSolicitudErrorMessage } from "@features/autorizaciones/utils/solicitud.feedback";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";

const PESTANAS: { valor: EstatusSolicitud | "TODAS"; etiqueta: string }[] = [
  { valor: "PENDIENTE", etiqueta: "Pendientes" },
  { valor: "AUTORIZADA", etiqueta: "Autorizadas" },
  { valor: "RECHAZADA", etiqueta: "Rechazadas" },
  { valor: "VENCIDA", etiqueta: "Vencidas" },
  { valor: "TODAS", etiqueta: "Todas" },
];

const COLUMNAS: DataTableColumn<SolicitudResumen>[] = [
  {
    key: "folio",
    header: "Folio",
    className: "min-w-[150px]",
    truncate: false,
    render: (fila) => (
      <div className="flex flex-col">
        <span className="font-medium tabular-nums">{fila.folio}</span>
        <span className="text-xs text-txt-muted">
          {ORIGENES[fila.tipoOrigen] ?? fila.tipoOrigen}
          {fila.folioOrigen ? ` · ${fila.folioOrigen}` : ""}
        </span>
      </div>
    ),
  },
  {
    key: "tipo",
    header: "Tipo",
    className: "min-w-[120px]",
    render: (fila) => <Badge variant="outline">{fila.tipo.nombre}</Badge>,
  },
  {
    key: "centro",
    header: "Centro",
    className: "min-w-[180px]",
    truncate: false,
    render: (fila) => (
      <div className="flex flex-col">
        <span>{fila.centro.nombre}</span>
        <span className="text-xs text-txt-muted">{fila.centro.clues}</span>
      </div>
    ),
  },
  {
    key: "solicitada",
    header: "Solicitada",
    className: "min-w-[170px]",
    truncate: false,
    render: (fila) => (
      <div className="flex flex-col text-sm">
        <span>{formatFechaHora(fila.fechaCreacion)}</span>
        <span className="text-xs text-txt-muted">{fila.solicitadaPor?.name ?? "—"}</span>
      </div>
    ),
  },
  {
    key: "estatus",
    header: "Estatus",
    className: "min-w-[150px]",
    truncate: false,
    render: (fila) => {
      const estatus = describirEstatusSolicitud(fila.estatus);
      const restante = fila.estatus === "PENDIENTE" ? tiempoRestante(fila.fechaLimite) : null;
      return (
        <div className="flex flex-col gap-1">
          <Badge variant={estatus.variante} className="w-fit">
            {estatus.etiqueta}
          </Badge>
          {restante ? (
            <span className={restante.urgente ? "text-xs text-status-critical" : "text-xs text-txt-muted"}>
              {restante.texto}
            </span>
          ) : null}
          {fila.modalidad === "MULTIPLE" && fila.estatus === "PENDIENTE" ? (
            <span className="text-xs text-txt-muted">
              {fila.aprobacionesVigentes} de {fila.aprobacionesRequeridas} aprobaciones
            </span>
          ) : null}
        </div>
      );
    },
  },
];

export function SolicitudesBandejaPage() {
  const navegar = useNavigate();
  const { hasEffectiveRequirement } = usePermissionDependencies();
  const puedeLeer = hasEffectiveRequirement({ allOf: ["clinico:autorizaciones:read"] });

  const [pestana, setPestana] = useState<EstatusSolicitud | "TODAS">("PENDIENTE");
  const [folio, setFolio] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const folioDebounced = useDebounce(folio, 400);

  const { data, isLoading, error, refetch } = useSolicitudesList(
    {
      page,
      pageSize,
      estatus: pestana === "TODAS" ? undefined : pestana,
      folio: folioDebounced.trim() || undefined,
    },
    puedeLeer,
  );

  if (!puedeLeer) {
    return (
      <CatalogModuleLayout title="Solicitudes de autorización" description="" icon={<Inbox className="size-12" />}>
        <AdminReadOnlyNotice message="No tienes acceso a la bandeja de autorizaciones." />
      </CatalogModuleLayout>
    );
  }

  return (
    <CatalogModuleLayout
      title="Solicitudes de autorización"
      description="Recetas, estudios y cancelaciones que puedes autorizar según tus tipos y centros asignados."
      icon={<Inbox className="size-12" />}
    >
      <Tabs
        value={pestana}
        onValueChange={(valor) => {
          setPestana(valor as EstatusSolicitud | "TODAS");
          setPage(1);
        }}
      >
        <TabsList className="flex-wrap">
          {PESTANAS.map(({ valor, etiqueta }) => (
            <TabsTrigger key={valor} value={valor}>
              {etiqueta}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      <TableHeaderBar
        search={
          <TableSearch
            value={folio}
            onChange={(valor) => {
              setFolio(valor);
              setPage(1);
            }}
            placeholder="Buscar por folio de solicitud o de receta/pase"
          />
        }
      />

      <DataTable
        columns={COLUMNAS}
        rows={data?.items ?? []}
        isLoading={isLoading || folio.trim() !== folioDebounced.trim()}
        isError={Boolean(error)}
        errorTitle="No se pudo cargar la bandeja"
        errorDescription={error ? getSolicitudErrorMessage(error, "Intenta nuevamente.") : undefined}
        onRetry={() => void refetch()}
        onRowClick={(fila) => navegar(rutaDetalle(fila.uuid))}
        hasFilters={Boolean(folioDebounced.trim())}
        onClearFilters={() => setFolio("")}
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
        getRowKey={(fila) => fila.uuid}
        emptyTitle={pestana === "PENDIENTE" ? "Sin solicitudes pendientes" : "Sin solicitudes"}
        emptyDescription="Aquí aparecen las solicitudes de los tipos y centros que tienes asignados."
      />
    </CatalogModuleLayout>
  );
}

export default SolicitudesBandejaPage;
