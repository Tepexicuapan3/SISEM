import { useState } from "react";
import { Plus, RotateCcw, UserCheck } from "lucide-react";
import type {
  AutorizadorItem,
  ClaveTipoAutorizacion,
  EstadoVigencia,
  EstatusAutorizador,
} from "@api/types/autorizaciones/autorizadores.types";
import { Input } from "@shared/ui/input";
import { Label } from "@shared/ui/label";
import { useDebounce } from "@shared/hooks/useDebounce";
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import { DataTable } from "@features/admin/shared/components/DataTable";
import {
  TableColumnVisibility,
  type ColumnVisibilityState,
} from "@features/admin/shared/components/TableColumnVisibility";
import { TableFilterMenu, type TableFilterSection } from "@features/admin/shared/components/TableFilterMenu";
import { TableHeaderBar } from "@features/admin/shared/components/TableHeaderBar";
import { TableOptionsMenu, type TableOptionItem } from "@features/admin/shared/components/TableOptionsMenu";
import { TablePrimaryAction } from "@features/admin/shared/components/TablePrimaryAction";
import { TableSearch } from "@features/admin/shared/components/TableSearch";
import { useTableDetailsDialog } from "@features/admin/shared/hooks/useTableDetailsDialog";
import { CatalogModuleLayout } from "@features/admin/modules/catalogos/shared/components/CatalogModuleLayout";
import { useCentrosAtencionList } from "@features/admin/modules/catalogos/centros-atencion/queries/useCentrosAtencionList";
import { AutorizadorCreateDialog } from "@features/admin/modules/autorizadores/components/AutorizadorCreateDialog";
import { AutorizadorDetailsDialog } from "@features/admin/modules/autorizadores/components/AutorizadorDetailsDialog";
import {
  AutorizadorEstatusDialog,
  type AccionAutorizador,
} from "@features/admin/modules/autorizadores/components/AutorizadorEstatusDialog";
import {
  AUTORIZADOR_VISIBILITY_OPTIONS,
  buildAutorizadorTableColumns,
} from "@features/admin/modules/autorizadores/components/AutorizadorTableColumns";
import {
  useAutorizadoresList,
  useCatalogosAutorizacion,
} from "@features/admin/modules/autorizadores/queries/useAutorizadores";
import { getAutorizadorErrorMessage } from "@features/admin/modules/autorizadores/utils/autorizador.feedback";
import {
  OPCIONES_ESTATUS,
  OPCIONES_VIGENCIA,
} from "@features/admin/modules/autorizadores/utils/autorizador.format";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";

interface Filtros {
  estatus?: EstatusAutorizador;
  vigencia?: EstadoVigencia;
  tipo?: ClaveTipoAutorizacion;
  centroId?: number;
  fechaInicioDesde: string;
  fechaFinHasta: string;
}

const FILTROS_VACIOS: Filtros = { fechaInicioDesde: "", fechaFinHasta: "" };

export function AutorizadoresPage() {
  // Permisos atomicos evaluados directo (respeta "*" y dependencias declaradas).
  // No se usa hasCapability: el frontend trata todo "admin.*" como capability
  // estricta y estas no estan registradas en la proyeccion del backend.
  const { hasEffectiveRequirement } = usePermissionDependencies();
  const puede = (permiso: string) => hasEffectiveRequirement({ allOf: [permiso] });
  const canRead = puede("admin:autorizadores:read");
  const canCreate = puede("admin:autorizadores:create");
  const canEdit = puede("admin:autorizadores:update");
  const canChangeStatus = puede("admin:autorizadores:status");
  const canGrantGlobal = puede("admin:autorizadores:global");

  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [search, setSearch] = useState("");
  const [filtros, setFiltros] = useState<Filtros>(FILTROS_VACIOS);
  const [columnVisibility, setColumnVisibility] = useState<ColumnVisibilityState>({});
  const [createOpen, setCreateOpen] = useState(false);
  const [accion, setAccion] = useState<{ tipo: AccionAutorizador; item: AutorizadorItem } | null>(null);

  const {
    open: detailsOpen,
    selectedItem,
    openDetails,
    closeDetails,
    setOpen: setDetailsOpen,
  } = useTableDetailsDialog<AutorizadorItem>();

  const debouncedSearch = useDebounce(search, 400);
  const { data: catalogos } = useCatalogosAutorizacion(canRead);
  const { data: centrosData } = useCentrosAtencionList({ pageSize: 200, isActive: true }, { enabled: canRead });

  const { data, isLoading, isFetching, error, refetch } = useAutorizadoresList(
    {
      page,
      pageSize,
      search: debouncedSearch.trim() || undefined,
      estatus: filtros.estatus,
      vigencia: filtros.vigencia,
      tipo: filtros.tipo,
      centroId: filtros.centroId,
      fechaInicioDesde: filtros.fechaInicioDesde || undefined,
      fechaFinHasta: filtros.fechaFinHasta || undefined,
    },
    { enabled: canRead },
  );

  const cambiarFiltro = <K extends keyof Filtros>(clave: K, valor: Filtros[K]) => {
    setFiltros((actual) => ({ ...actual, [clave]: actual[clave] === valor ? undefined : valor }));
    setPage(1);
  };

  const limpiarFiltros = () => {
    setSearch("");
    setFiltros(FILTROS_VACIOS);
    setPage(1);
  };

  const secciones: TableFilterSection[] = [
    {
      id: "estatus",
      label: "Estatus",
      options: OPCIONES_ESTATUS.map(({ valor, etiqueta }) => ({
        id: `estatus-${valor}`,
        label: etiqueta,
        selected: filtros.estatus === valor,
        onSelect: () => cambiarFiltro("estatus", valor),
      })),
    },
    {
      id: "vigencia",
      label: "Vigencia",
      options: OPCIONES_VIGENCIA.map(({ valor, etiqueta }) => ({
        id: `vigencia-${valor}`,
        label: etiqueta,
        selected: filtros.vigencia === valor,
        onSelect: () => cambiarFiltro("vigencia", valor),
      })),
    },
    {
      id: "tipo",
      label: "Tipo de autorización",
      options: (catalogos?.tipos ?? []).map((tipo) => ({
        id: `tipo-${tipo.clave}`,
        label: tipo.nombre,
        selected: filtros.tipo === tipo.clave,
        onSelect: () => cambiarFiltro("tipo", tipo.clave),
      })),
    },
    {
      id: "centro",
      label: "Centro de atención",
      options: (centrosData?.items ?? []).map((centro) => ({
        id: `centro-${centro.id}`,
        label: centro.name,
        selected: filtros.centroId === centro.id,
        onSelect: () => cambiarFiltro("centroId", centro.id),
      })),
    },
  ];

  const filtrosAplicados = [
    filtros.estatus,
    filtros.vigencia,
    filtros.tipo,
    filtros.centroId,
    filtros.fechaInicioDesde,
    filtros.fechaFinHasta,
  ].filter(Boolean).length;
  const isSearchPending = search.trim() !== debouncedSearch.trim();

  const opciones: TableOptionItem[] = [
    {
      id: "actualizar-autorizadores",
      label: "Actualizar",
      icon: RotateCcw,
      isLoading: isFetching,
      disabled: isFetching,
      onSelect: () => {
        if (!isFetching) void refetch();
      },
    },
  ];

  const abrirAccion = (tipo: AccionAutorizador, item: AutorizadorItem) => setAccion({ tipo, item });

  const columnas = buildAutorizadorTableColumns({
    canEdit,
    canChangeStatus,
    onOpenDetails: openDetails,
    onAccion: abrirAccion,
  }).filter((columna) => columnVisibility[columna.key] ?? true);

  return (
    <CatalogModuleLayout
      title="Autorizadores médicos"
      description="Médicos que pueden autorizar laboratorio, gabinete, recetas y cancelación de notas: qué autorizan, en qué centros y hasta cuándo."
      icon={<UserCheck className="size-12" />}
    >
      {!canRead ? (
        <AdminReadOnlyNotice message="No tienes acceso para consultar los autorizadores médicos." />
      ) : null}

      <TableHeaderBar
        search={
          <TableSearch
            value={search}
            onChange={(valor) => {
              setSearch(valor);
              setPage(1);
            }}
            placeholder="Buscar por nombre, usuario o cargo"
            disabled={!canRead}
          />
        }
        actions={
          <>
            {canRead ? (
              <TableFilterMenu sections={secciones} appliedCount={filtrosAplicados} onClear={limpiarFiltros} />
            ) : null}
            {canRead ? (
              <TableColumnVisibility
                columns={AUTORIZADOR_VISIBILITY_OPTIONS}
                visibility={columnVisibility}
                onVisibilityChange={setColumnVisibility}
              />
            ) : null}
            {canRead ? <TableOptionsMenu options={opciones} /> : null}
            {canCreate ? (
              <TablePrimaryAction
                permission="admin:autorizadores:create"
                dependencyAware
                label="Nuevo autorizador"
                icon={<Plus className="size-4" />}
                onClick={() => setCreateOpen(true)}
              />
            ) : null}
          </>
        }
      />

      {canRead ? (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl border border-line-struct px-3 py-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-txt-muted">Vigencia</span>
          <div className="flex items-center gap-2">
            <Label htmlFor="filtro-inicio-desde" className="text-xs font-normal text-txt-muted">
              Inicia desde
            </Label>
            <Input
              id="filtro-inicio-desde"
              type="date"
              className="h-8 w-40"
              value={filtros.fechaInicioDesde}
              onChange={(event) => {
                setFiltros((actual) => ({ ...actual, fechaInicioDesde: event.target.value }));
                setPage(1);
              }}
            />
          </div>
          <div className="flex items-center gap-2">
            <Label htmlFor="filtro-fin-hasta" className="text-xs font-normal text-txt-muted">
              Termina hasta
            </Label>
            <Input
              id="filtro-fin-hasta"
              type="date"
              className="h-8 w-40"
              value={filtros.fechaFinHasta}
              onChange={(event) => {
                setFiltros((actual) => ({ ...actual, fechaFinHasta: event.target.value }));
                setPage(1);
              }}
            />
          </div>
          {filtros.fechaInicioDesde || filtros.fechaFinHasta ? (
            <button
              type="button"
              className="text-xs text-txt-muted underline-offset-2 hover:text-txt-body hover:underline"
              onClick={() => {
                setFiltros((actual) => ({ ...actual, fechaInicioDesde: "", fechaFinHasta: "" }));
                setPage(1);
              }}
            >
              Quitar fechas
            </button>
          ) : null}
        </div>
      ) : null}

      <DataTable
        columns={columnas}
        rows={data?.items ?? []}
        isLoading={isLoading || isSearchPending}
        isError={canRead && Boolean(error)}
        errorTitle="No se pudo cargar los autorizadores"
        errorDescription={
          canRead && error
            ? getAutorizadorErrorMessage(error, "No se pudo obtener el listado. Intenta nuevamente.")
            : undefined
        }
        hasFilters={canRead && (Boolean(debouncedSearch.trim()) || filtrosAplicados > 0)}
        onRowClick={canRead ? openDetails : undefined}
        onRetry={() => void refetch()}
        onClearFilters={limpiarFiltros}
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
        getRowKey={(row) => row.id.toString()}
        emptyTitle="Sin autorizadores"
        emptyDescription="Registra a un médico desde “Nuevo autorizador” para que pueda autorizar solicitudes."
      />

      <AutorizadorDetailsDialog
        open={detailsOpen}
        onOpenChange={setDetailsOpen}
        onClose={closeDetails}
        resumen={selectedItem}
        tiposCatalogo={catalogos?.tipos ?? []}
        canEdit={canEdit}
        canChangeStatus={canChangeStatus}
        canGrantGlobal={canGrantGlobal}
        onAccion={abrirAccion}
      />

      <AutorizadorCreateDialog open={createOpen} onOpenChange={setCreateOpen} canGrantGlobal={canGrantGlobal} />

      <AutorizadorEstatusDialog
        key={accion ? `${accion.tipo}-${accion.item.id}-${accion.item.version}` : "cerrado"}
        accion={accion?.tipo ?? null}
        autorizador={accion?.item ?? null}
        motivos={catalogos?.motivos ?? []}
        onClose={() => setAccion(null)}
      />
    </CatalogModuleLayout>
  );
}

export default AutorizadoresPage;
