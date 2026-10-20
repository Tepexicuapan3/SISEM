import { useState } from "react";
import { ClipboardList, Lock, Plus, XCircle } from "lucide-react";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import { Label } from "@shared/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@shared/ui/select";
import { Tabs, TabsList, TabsTrigger } from "@shared/ui/tabs";
import { useDebounce } from "@shared/hooks/useDebounce";
import { DataTable, type DataTableColumn } from "@features/admin/shared/components/DataTable";
import { TableHeaderBar } from "@features/admin/shared/components/TableHeaderBar";
import { TableSearch } from "@features/admin/shared/components/TableSearch";
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import { CatalogModuleLayout } from "@features/admin/modules/catalogos/shared/components/CatalogModuleLayout";
import { DischargePadronDialog } from "@features/padrones/components/DischargePadronDialog";
import { EnrollPadronDialog } from "@features/padrones/components/EnrollPadronDialog";
import { usePadronList } from "@features/padrones/queries/usePadrones";
import { getPadronesErrorMessage } from "@features/padrones/utils/padrones.feedback";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import type { PadronEnrollment, PadronRegistry, PadronStatus } from "@api/types/padrones.types";

const STATUS_FILTER = { ALL: "all", ACTIVO: "activo", BAJA: "baja" } as const;
type StatusFilter = (typeof STATUS_FILTER)[keyof typeof STATUS_FILTER];

const formatDate = (iso: string | null | undefined) => {
  if (!iso) return "-";
  const [y, m, d] = iso.slice(0, 10).split("-");
  return `${d}/${m}/${y}`;
};

export function PadronesPage() {
  const { hasCapability } = usePermissionDependencies();
  const canRead = hasCapability("clinico.padrones.read", { allOf: ["clinico:padrones:read"] });
  const canWrite = hasCapability("clinico.padrones.write", { allOf: ["clinico:padrones:write"] });

  const [registry, setRegistry] = useState<PadronRegistry>("cronicos");
  const [noExp, setNoExp] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>(STATUS_FILTER.ACTIVO);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [enrollOpen, setEnrollOpen] = useState(false);
  const [dischargeTarget, setDischargeTarget] = useState<PadronEnrollment | null>(null);

  const debouncedNoExp = useDebounce(noExp, 400);
  const { data, isLoading, error, refetch } = usePadronList(
    registry,
    {
      noExp: debouncedNoExp.trim() || undefined,
      status: statusFilter === STATUS_FILTER.ALL ? undefined : (statusFilter as PadronStatus),
      page,
      pageSize,
    },
    { enabled: canRead },
  );

  const columns: DataTableColumn<PadronEnrollment>[] = [
    {
      key: "patient",
      header: "Paciente",
      className: "w-[240px]",
      render: (row) => (
        <div className="min-w-0">
          <p className="font-medium text-txt-body">{row.patientName ?? "Sin nombre registrado"}</p>
          <p className="text-xs text-txt-muted">
            Exp. {row.noExp}{row.pkNum ? ` · familiar ${row.pkNum}` : " · titular"}
          </p>
        </div>
      ),
    },
    {
      key: "item",
      header: registry === "cronicos" ? "Padecimiento" : "Discapacidad",
      className: "w-[280px]",
      render: (row) =>
        row.item.restricted ? (
          <span className="inline-flex items-center gap-1 italic text-txt-muted">
            <Lock className="size-3.5" />
            {row.item.description}
          </span>
        ) : (
          <span>
            <span className="font-mono text-xs text-txt-muted">{row.item.code}</span> {row.item.description}
          </span>
        ),
    },
    { key: "center", header: "Centro", className: "w-[180px]", render: (row) => row.center.name },
    { key: "enrolledOn", header: "Inscripción", render: (row) => formatDate(row.enrolledOn) },
    {
      key: "status",
      header: "Estado",
      render: (row) =>
        row.status === "activo" ? (
          <Badge variant="secondary">Activo</Badge>
        ) : (
          <div className="space-y-0.5">
            <Badge variant="outline">Baja</Badge>
            <p className="text-xs text-txt-muted">
              {formatDate(row.discharge?.on)} · {row.discharge?.reason ?? "-"}
            </p>
          </div>
        ),
    },
    {
      key: "actions",
      header: "",
      align: "center",
      render: (row) =>
        canWrite && row.status === "activo" ? (
          <Button
            variant="ghost"
            size="icon"
            title="Dar de baja"
            onClick={(e) => {
              e.stopPropagation();
              setDischargeTarget(row);
            }}
          >
            <XCircle className="size-4 text-status-critical" />
          </Button>
        ) : null,
    },
  ];

  if (!canRead) {
    return (
      <CatalogModuleLayout title="Padrones clínicos" description="Crónicos y discapacidad" icon={<ClipboardList className="size-5" />}>
        <AdminReadOnlyNotice message="No tienes permiso para consultar los padrones clínicos." />
      </CatalogModuleLayout>
    );
  }

  return (
    <CatalogModuleLayout
      title="Padrones clínicos"
      description="Pacientes inscritos al programa de control de crónico-degenerativos y al registro de discapacidad."
      icon={<ClipboardList className="size-5" />}
    >
      <Tabs
        value={registry}
        onValueChange={(value) => {
          setRegistry(value as PadronRegistry);
          setPage(1);
        }}
      >
        <TabsList>
          <TabsTrigger value="cronicos">Crónicos</TabsTrigger>
          <TabsTrigger value="discapacidad">Discapacidad</TabsTrigger>
        </TabsList>
      </Tabs>

      <TableHeaderBar
        search={
          <div className="flex flex-wrap items-end gap-3">
            <TableSearch
              value={noExp}
              onChange={(value) => {
                setNoExp(value);
                setPage(1);
              }}
              placeholder="Buscar por expediente"
            />
            <div className="flex flex-col gap-1">
              <Label>Estado</Label>
              <Select
                value={statusFilter}
                onValueChange={(value) => {
                  setStatusFilter(value as StatusFilter);
                  setPage(1);
                }}
              >
                <SelectTrigger className="w-36"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value={STATUS_FILTER.ACTIVO}>Activos</SelectItem>
                  <SelectItem value={STATUS_FILTER.BAJA}>Dados de baja</SelectItem>
                  <SelectItem value={STATUS_FILTER.ALL}>Todos</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        }
        actions={
          canWrite ? (
            <Button onClick={() => setEnrollOpen(true)}>
              <Plus className="size-4" />
              Inscribir
            </Button>
          ) : undefined
        }
      />

      <DataTable
        columns={columns}
        rows={data?.items ?? []}
        isLoading={isLoading}
        isError={Boolean(error)}
        errorTitle="No se pudo cargar el padrón"
        errorDescription={error ? getPadronesErrorMessage(error, "Intenta nuevamente.") : undefined}
        onRetry={() => void refetch()}
        hasFilters={Boolean(debouncedNoExp.trim()) || statusFilter !== STATUS_FILTER.ALL}
        onClearFilters={() => {
          setNoExp("");
          setStatusFilter(STATUS_FILTER.ALL);
        }}
        getRowKey={(row) => row.id.toString()}
        emptyTitle="Sin inscripciones"
        emptyDescription="Cuando inscribas pacientes al padrón aparecerán aquí."
        pagination={{
          page,
          pageSize,
          total: data?.total ?? 0,
          totalPages: data?.totalPages ?? 1,
          onPageChange: setPage,
          onPageSizeChange: (value) => {
            setPageSize(value);
            setPage(1);
          },
        }}
      />

      <EnrollPadronDialog open={enrollOpen} onOpenChange={setEnrollOpen} registry={registry} />
      <DischargePadronDialog
        open={dischargeTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDischargeTarget(null);
        }}
        registry={registry}
        enrollment={dischargeTarget}
      />
    </CatalogModuleLayout>
  );
}

export default PadronesPage;
