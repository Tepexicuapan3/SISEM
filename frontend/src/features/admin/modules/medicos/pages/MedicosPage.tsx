import { useState } from "react";
import { Plus, RotateCcw, Stethoscope, Upload } from "lucide-react";
import { Button } from "@shared/ui/button";
import { useDebounce } from "@shared/hooks/useDebounce";
import { DataTable } from "@features/admin/shared/components/DataTable";
import {
  TableColumnVisibility,
  type ColumnVisibilityState,
} from "@features/admin/shared/components/TableColumnVisibility";
import { TableFilterMenu } from "@features/admin/shared/components/TableFilterMenu";
import { TableHeaderBar } from "@features/admin/shared/components/TableHeaderBar";
import {
  TableOptionsMenu,
  type TableOptionItem,
} from "@features/admin/shared/components/TableOptionsMenu";
import { TablePrimaryAction } from "@features/admin/shared/components/TablePrimaryAction";
import { TableSearch } from "@features/admin/shared/components/TableSearch";
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import { CatalogModuleLayout } from "@features/admin/modules/catalogos/shared/components/CatalogModuleLayout";
import { useTableDetailsDialog } from "@features/admin/shared/hooks/useTableDetailsDialog";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import { useMedicosList } from "@features/admin/modules/medicos/hooks/useMedicos";
import {
  buildMedicosTableColumns,
  buildMedicosVisibilityOptions,
} from "@features/admin/modules/medicos/components/MedicoTableColumns";
import { MedicoCreateDialog } from "@features/admin/modules/medicos/components/MedicoCreateDialog";
import { MedicoDetailsDialog } from "@features/admin/modules/medicos/components/MedicoDetailsDialog";
import { MedicoImportDialog } from "@features/admin/modules/medicos/components/MedicoImportDialog";
import type { MedicoListItem } from "@api/types/medicos.types";

const ESTATUS_FILTER_ALL = "all";
const TIPO_FILTER_ALL    = "all";

export function MedicosPage() {
  const { hasCapability } = usePermissionDependencies();
  const [search, setSearch] = useState("");
  const [estatusFilter, setEstatusFilter] = useState(ESTATUS_FILTER_ALL);
  const [tipoFilter, setTipoFilter]       = useState(TIPO_FILTER_ALL);
  const [createOpen, setCreateOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [columnVisibility, setColumnVisibility] = useState<ColumnVisibilityState>({
    nombre: true, tipoMedico: true, servicio: true,
    especialidades: true, estatusMedico: true, actions: true,
  });

  const {
    open: detailsOpen,
    selectedItem: selectedMedico,
    openDetails: handleOpenDetails,
    setOpen: setDetailsOpen,
  } = useTableDetailsDialog<MedicoListItem>();

  const debouncedSearch = useDebounce(search, 400);

  const canRead   = hasCapability("admin.medicos.read",   { allOf: ["admin:gestion:medicos:read"] });
  const canCreate = hasCapability("admin.medicos.create", { allOf: ["admin:gestion:medicos:create"] });
  const canUpdate = hasCapability("admin.medicos.update", { allOf: ["admin:gestion:medicos:update"] });

  const { data, isLoading, isFetching, error, refetch } = useMedicosList(
    {
      search: debouncedSearch || undefined,
      tipoMedico:    tipoFilter    !== TIPO_FILTER_ALL    ? tipoFilter    : undefined,
      estatusMedico: estatusFilter !== ESTATUS_FILTER_ALL ? estatusFilter : undefined,
    },
    { enabled: canRead },
  );

  const rows = data?.items ?? [];
  const showActions = canRead || canUpdate;

  const columns = buildMedicosTableColumns({
    canRead, canUpdate, onOpenDetails: handleOpenDetails,
  });
  const visibilityOptions = buildMedicosVisibilityOptions(showActions);
  const visibleColumns = columns.filter((c) => columnVisibility[c.key] ?? true);

  const appliedFiltersCount = [
    estatusFilter !== ESTATUS_FILTER_ALL,
    tipoFilter    !== TIPO_FILTER_ALL,
  ].filter(Boolean).length;

  const handleClearFilters = () => {
    setSearch("");
    setEstatusFilter(ESTATUS_FILTER_ALL);
    setTipoFilter(TIPO_FILTER_ALL);
  };

  const tableOptions: TableOptionItem[] = [
    {
      id: "refresh", label: "Actualizar", icon: RotateCcw,
      isLoading: isFetching, disabled: isFetching,
      onSelect: () => { if (!isFetching) void refetch(); },
    },
  ];

  const filterSections = [
    {
      id: "estatus",
      label: "Estatus",
      options: [
        { id: "ACTIVO",      label: "Activos",      selected: estatusFilter === "ACTIVO",      onSelect: () => setEstatusFilter("ACTIVO") },
        { id: "VACACIONES",  label: "Vacaciones",   selected: estatusFilter === "VACACIONES",  onSelect: () => setEstatusFilter("VACACIONES") },
        { id: "INCAPACIDAD", label: "Incapacidad",  selected: estatusFilter === "INCAPACIDAD", onSelect: () => setEstatusFilter("INCAPACIDAD") },
        { id: "SUSPENDIDO",  label: "Suspendidos",  selected: estatusFilter === "SUSPENDIDO",  onSelect: () => setEstatusFilter("SUSPENDIDO") },
        { id: "BAJA",        label: "Baja",         selected: estatusFilter === "BAJA",        onSelect: () => setEstatusFilter("BAJA") },
      ],
    },
    {
      id: "tipo",
      label: "Tipo",
      options: [
        { id: "CLINICA",  label: "Clínica",            selected: tipoFilter === "CLINICA",  onSelect: () => setTipoFilter("CLINICA") },
        { id: "HOSPITAL", label: "Hospital",            selected: tipoFilter === "HOSPITAL", onSelect: () => setTipoFilter("HOSPITAL") },
        { id: "AMBOS",    label: "Clínica y Hospital",  selected: tipoFilter === "AMBOS",    onSelect: () => setTipoFilter("AMBOS") },
      ],
    },
  ];

  return (
    <CatalogModuleLayout
      title="Médicos"
      description="Catálogo de médicos del sistema. Gestiona especialidades, centros, horarios y excepciones."
      icon={<Stethoscope className="size-12" />}
    >
      {!canRead ? (
        <AdminReadOnlyNotice message="No tienes acceso para consultar este catálogo." />
      ) : null}

      <TableHeaderBar
        search={
          <TableSearch
            value={search}
            onChange={(v) => setSearch(v)}
            placeholder="Buscar por nombre o usuario"
            disabled={!canRead}
          />
        }
        actions={
          <>
            {canRead ? (
              <TableFilterMenu
                sections={filterSections}
                appliedCount={appliedFiltersCount}
                onClear={handleClearFilters}
              />
            ) : null}
            {canRead ? (
              <TableColumnVisibility
                columns={visibilityOptions}
                visibility={columnVisibility}
                onVisibilityChange={setColumnVisibility}
              />
            ) : null}
            {canRead ? <TableOptionsMenu options={tableOptions} /> : null}
            {canCreate ? (
              <Button
                type="button"
                variant="outline"
                onClick={() => setImportOpen(true)}
              >
                <Upload className="size-4" />
                Importar
              </Button>
            ) : null}
            {canCreate ? (
              <TablePrimaryAction
                permission="admin:gestion:medicos:create"
                dependencyAware
                label="Nuevo"
                icon={<Plus className="size-4" />}
                onClick={() => setCreateOpen(true)}
              />
            ) : null}
          </>
        }
      />

      <DataTable
        columns={visibleColumns}
        rows={rows}
        isLoading={isLoading}
        isError={canRead && Boolean(error)}
        errorTitle="No se pudo cargar el catálogo de médicos"
        hasFilters={Boolean(debouncedSearch.trim()) || appliedFiltersCount > 0}
        onRowClick={canRead ? handleOpenDetails : undefined}
        onRetry={() => void refetch()}
        onClearFilters={handleClearFilters}
        getRowKey={(row) => row.id.toString()}
        emptyTitle="Sin médicos registrados"
        emptyDescription="Usa el botón «Nuevo» para registrar un médico. El usuario debe tener tipo de personal «Médico» configurado previamente."
      />

      <MedicoDetailsDialog
        open={detailsOpen}
        onOpenChange={setDetailsOpen}
        medicoSummary={selectedMedico}
        canEdit={canUpdate}
      />

      <MedicoCreateDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={(newMedico) => {
          setCreateOpen(false);
          // Abre automáticamente el formulario completo para terminar la configuración
          handleOpenDetails(newMedico);
        }}
      />

      <MedicoImportDialog open={importOpen} onOpenChange={setImportOpen} />
    </CatalogModuleLayout>
  );
}

export default MedicosPage;
