import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bell, CheckCheck } from "lucide-react";
import type { Notificacion } from "@api/types/notificaciones/notificaciones.types";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@shared/ui/tabs";
import { DataTable, type DataTableColumn } from "@features/admin/shared/components/DataTable";
import { CatalogModuleLayout } from "@features/admin/modules/catalogos/shared/components/CatalogModuleLayout";
import { useMarcarLeida, useMarcarTodasLeidas } from "@features/notificaciones/mutations/useNotificacionMutations";
import { useNotificacionesList } from "@features/notificaciones/queries/useNotificaciones";

const formatFecha = (valor: string) =>
  new Date(valor).toLocaleString("es-MX", { dateStyle: "medium", timeStyle: "short" });

const COLUMNAS: DataTableColumn<Notificacion>[] = [
  {
    key: "estado",
    header: "",
    className: "w-8",
    render: (fila) =>
      fila.fechaLectura ? null : <span className="block size-2 rounded-full bg-status-info" aria-label="Sin leer" />,
  },
  {
    key: "notificacion",
    header: "Notificación",
    className: "min-w-[260px]",
    truncate: false,
    render: (fila) => (
      <div className="flex flex-col">
        <span className={fila.fechaLectura ? "text-txt-body" : "font-semibold text-txt-body"}>{fila.titulo}</span>
        <span className="text-xs text-txt-muted">{fila.cuerpo}</span>
      </div>
    ),
  },
  {
    key: "prioridad",
    header: "Prioridad",
    className: "min-w-[100px]",
    render: (fila) => (fila.prioridad === "URGENTE" ? <Badge variant="critical">Urgente</Badge> : null),
  },
  {
    key: "fecha",
    header: "Fecha",
    className: "min-w-[160px]",
    render: (fila) => formatFecha(fila.fechaCreacion),
  },
];

export function NotificacionesPage() {
  const navegar = useNavigate();
  const [soloNoLeidas, setSoloNoLeidas] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const { data, isLoading, isError, refetch } = useNotificacionesList({ page, pageSize, soloNoLeidas });
  const marcarLeida = useMarcarLeida();
  const marcarTodas = useMarcarTodasLeidas();

  return (
    <CatalogModuleLayout
      title="Notificaciones"
      description="Avisos de SIRES dirigidos a ti. Abre una notificación para ir a su detalle."
      icon={<Bell className="size-12" />}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Tabs
          value={soloNoLeidas ? "no-leidas" : "todas"}
          onValueChange={(valor) => {
            setSoloNoLeidas(valor === "no-leidas");
            setPage(1);
          }}
        >
          <TabsList>
            <TabsTrigger value="todas">Todas</TabsTrigger>
            <TabsTrigger value="no-leidas">Sin leer</TabsTrigger>
          </TabsList>
        </Tabs>
        <Button variant="outline" size="sm" disabled={marcarTodas.isPending} onClick={() => marcarTodas.mutate()}>
          <CheckCheck className="size-4" />
          Marcar todas como leídas
        </Button>
      </div>

      <DataTable
        columns={COLUMNAS}
        rows={data?.items ?? []}
        isLoading={isLoading}
        isError={isError}
        errorTitle="No se pudieron cargar las notificaciones"
        onRetry={() => void refetch()}
        onRowClick={(fila) => {
          if (!fila.fechaLectura) marcarLeida.mutate(fila.id);
          navegar(fila.urlAccion);
        }}
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
        getRowKey={(fila) => fila.id.toString()}
        emptyTitle={soloNoLeidas ? "Sin notificaciones por leer" : "Sin notificaciones"}
        emptyDescription="Cuando haya avisos para ti aparecerán aquí."
      />
    </CatalogModuleLayout>
  );
}

export default NotificacionesPage;
