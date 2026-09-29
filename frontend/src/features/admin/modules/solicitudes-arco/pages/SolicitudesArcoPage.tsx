import { useState } from "react";
import { FileLock2, Pencil, Plus } from "lucide-react";
import { useDebounce } from "@shared/hooks/useDebounce";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import { Input } from "@shared/ui/input";
import { Label } from "@shared/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@shared/ui/select";
import { DataTable, type DataTableColumn } from "@features/admin/shared/components/DataTable";
import { AdminPageIntro } from "@features/admin/shared/components/AdminPageIntro";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import { useSolicitudesArco } from "@features/admin/modules/solicitudes-arco/queries/useSolicitudesArco";
import { CreateSolicitudArcoDialog } from "@features/admin/modules/solicitudes-arco/components/CreateSolicitudArcoDialog";
import { ChangeSolicitudArcoStatusDialog } from "@features/admin/modules/solicitudes-arco/components/ChangeSolicitudArcoStatusDialog";
import {
  ARCO_STATUS_BADGE_VARIANT,
  ARCO_STATUS_LABELS,
  ARCO_TYPE_LABELS,
  formatArcoDate,
  isArcoRequestFinal,
} from "@features/admin/modules/solicitudes-arco/domain/arco.labels";
import type { ArcoRequestItem, ArcoRequestStatus, ArcoRequestType } from "@api/types";

const ALL = "all";

export function SolicitudesArcoPage() {
  const { hasCapability } = usePermissionDependencies();
  const canWrite = hasCapability("admin.arco.write", { allOf: ["admin:arco:write"] });

  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [estatus, setEstatus] = useState<ArcoRequestStatus | typeof ALL>(ALL);
  const [tipo, setTipo] = useState<ArcoRequestType | typeof ALL>(ALL);
  const [noExp, setNoExp] = useState("");
  const [soloVencidas, setSoloVencidas] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [statusTarget, setStatusTarget] = useState<ArcoRequestItem | null>(null);

  const debouncedNoExp = useDebounce(noExp.trim(), 400);

  const { data, isLoading, isFetching, error, refetch } = useSolicitudesArco({
    page,
    pageSize,
    estatus: estatus === ALL ? undefined : estatus,
    tipo: tipo === ALL ? undefined : tipo,
    noExp: debouncedNoExp || undefined,
    vencidas: soloVencidas || undefined,
  });

  const total = data?.total ?? 0;
  const hasFilters = estatus !== ALL || tipo !== ALL || Boolean(debouncedNoExp) || soloVencidas;

  const resetPage = () => setPage(1);
  const handleClearFilters = () => {
    setEstatus(ALL);
    setTipo(ALL);
    setNoExp("");
    setSoloVencidas(false);
    resetPage();
  };

  const columns: DataTableColumn<ArcoRequestItem>[] = [
    {
      key: "folio",
      header: "Folio",
      render: (row) => (
        <div className="flex flex-col">
          <span>{row.folio}</span>
          {row.transparencyFolio ? (
            <span className="text-xs text-txt-muted">UT: {row.transparencyFolio}</span>
          ) : null}
        </div>
      ),
    },
    { key: "type", header: "Derecho", render: (row) => ARCO_TYPE_LABELS[row.type] ?? row.type },
    { key: "patient", header: "Expediente", render: (row) => `${row.noExp} / ${row.pkNum}` },
    { key: "requesterName", header: "Solicitante", accessorKey: "requesterName" },
    { key: "receivedDate", header: "Recibida", render: (row) => formatArcoDate(row.receivedDate) },
    {
      key: "dueDate",
      header: "Vence",
      render: (row) => (
        <div className="flex items-center gap-2">
          <span>{formatArcoDate(row.dueDate)}</span>
          {row.isOverdue ? <Badge variant="critical" className="text-xs">Vencida</Badge> : null}
        </div>
      ),
    },
    {
      key: "status",
      header: "Estatus",
      align: "center",
      render: (row) => (
        <Badge variant={ARCO_STATUS_BADGE_VARIANT[row.status] ?? "outline"} className="text-xs">
          {ARCO_STATUS_LABELS[row.status] ?? row.status}
        </Badge>
      ),
    },
    {
      key: "actions",
      header: "",
      align: "center",
      render: (row) =>
        canWrite && !isArcoRequestFinal(row.status) ? (
          <Button
            variant="ghost"
            size="icon"
            title="Actualizar estatus"
            onClick={(e) => {
              e.stopPropagation();
              setStatusTarget(row);
            }}
          >
            <Pencil className="size-4" />
          </Button>
        ) : null,
    },
  ];

  return (
    <div className="mx-auto w-full space-y-6 px-4 pb-2 sm:px-6 lg:max-w-[1360px] lg:px-8 xl:px-10">
      <AdminPageIntro
        title="Solicitudes ARCO"
        description="Derechos de Acceso, Rectificación, Cancelación y Oposición sobre datos personales del expediente clínico."
        icon={<FileLock2 className="size-12" />}
      />

      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1">
            <Label>Estatus</Label>
            <Select
              value={estatus}
              onValueChange={(v) => { setEstatus(v as ArcoRequestStatus | typeof ALL); resetPage(); }}
            >
              <SelectTrigger className="w-44"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>Todos</SelectItem>
                {Object.entries(ARCO_STATUS_LABELS).map(([value, label]) => (
                  <SelectItem key={value} value={value}>{label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1">
            <Label>Derecho</Label>
            <Select
              value={tipo}
              onValueChange={(v) => { setTipo(v as ArcoRequestType | typeof ALL); resetPage(); }}
            >
              <SelectTrigger className="w-44"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>Todos</SelectItem>
                {Object.entries(ARCO_TYPE_LABELS).map(([value, label]) => (
                  <SelectItem key={value} value={value}>{label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="arco-no-exp">Expediente</Label>
            <Input
              id="arco-no-exp"
              className="w-36"
              value={noExp}
              onChange={(e) => { setNoExp(e.target.value); resetPage(); }}
            />
          </div>
          <Button
            variant={soloVencidas ? "default" : "outline"}
            onClick={() => { setSoloVencidas((prev) => !prev); resetPage(); }}
          >
            Solo vencidas
          </Button>
          <Button variant="outline" onClick={handleClearFilters} disabled={!hasFilters}>
            Limpiar filtros
          </Button>
        </div>
        {canWrite ? (
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="size-4" />
            Nueva solicitud
          </Button>
        ) : null}
      </div>

      <DataTable
        columns={columns}
        rows={data?.items ?? []}
        isLoading={isLoading}
        isError={Boolean(error)}
        errorTitle="No se pudieron cargar las solicitudes"
        errorDescription="Ocurrió un error al obtener la información. Intenta nuevamente."
        hasFilters={hasFilters}
        onRetry={() => void refetch()}
        onClearFilters={handleClearFilters}
        pagination={{
          page,
          pageSize,
          total,
          totalPages: Math.max(1, data?.totalPages ?? 1),
          onPageChange: setPage,
          onPageSizeChange: (value) => { setPageSize(value); resetPage(); },
        }}
        getRowKey={(row) => row.id.toString()}
        emptyTitle="Sin solicitudes"
        emptyDescription="Las solicitudes ARCO registradas aparecerán aquí."
        footerNote={isFetching ? "Actualizando…" : `${total} solicitud(es)`}
        minWidthClassName="min-w-[1000px]"
      />

      {canWrite ? (
        <>
          <CreateSolicitudArcoDialog open={createOpen} onOpenChange={setCreateOpen} />
          <ChangeSolicitudArcoStatusDialog
            open={Boolean(statusTarget)}
            onOpenChange={(next) => { if (!next) setStatusTarget(null); }}
            solicitud={statusTarget}
          />
        </>
      ) : null}
    </div>
  );
}

export default SolicitudesArcoPage;
