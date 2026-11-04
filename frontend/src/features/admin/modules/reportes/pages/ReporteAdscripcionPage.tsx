import { useState } from "react";
import { Download, Users } from "lucide-react";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import { Label } from "@shared/ui/label";
import { useDebounce } from "@shared/hooks/useDebounce";
import { DataTable, type DataTableColumn } from "@features/admin/shared/components/DataTable";
import { TableHeaderBar } from "@features/admin/shared/components/TableHeaderBar";
import { TableSearch } from "@features/admin/shared/components/TableSearch";
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import { CatalogModuleLayout } from "@features/admin/modules/catalogos/shared/components/CatalogModuleLayout";
import { SELECT_CLASS } from "@features/admin/modules/catalogos/consultorio-familiar/components/EquivalenciasSection";
import {
  ConsultorioCell,
  ResumenAdscripcionTable,
} from "@features/admin/modules/reportes/components/ResumenAdscripcionTable";
import { etiquetaConsultorio } from "@features/admin/modules/reportes/domain/consultorioEtiqueta";
import {
  useAdscripcionResumen,
  useAdscritosReport,
} from "@features/admin/modules/reportes/queries/useAdscripcionReport";
import { useExportAdscripcionReport } from "@features/admin/modules/reportes/mutations/useExportAdscripcionReport";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import type { Adscrito, ConteoAdscritos, TipoDerechohabiente } from "@api/types";

const PERMISO = "admin:reportes:adscripcion:read";
const TITULO = "Padrón de adscripción";
const DESCRIPCION = "Derechohabientes adscritos a su consultorio familiar, por centro, consultorio y turno.";

const TIPO_LABEL: Record<TipoDerechohabiente, string> = { TITULAR: "Titular", FAMILIAR: "Familiar" };

const formatDate = (iso: string) => {
  const [y, m, d] = iso.slice(0, 10).split("-");
  return `${d}/${m}/${y}`;
};

const toNumber = (value: string) => (value ? Number(value) : undefined);

function TotalCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-line-struct bg-background px-4 py-3">
      <p className="text-xs text-txt-muted">{label}</p>
      <p className="text-2xl font-semibold text-txt-body">{value}</p>
    </div>
  );
}

function Totales({ conteo }: { conteo: ConteoAdscritos }) {
  return (
    <section aria-label="Totales" className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      <TotalCard label="Total adscritos" value={conteo.total} />
      <TotalCard label="Titulares (trabajadores)" value={conteo.titulares} />
      <TotalCard label="Familiares" value={conteo.familiares} />
    </section>
  );
}

export function ReporteAdscripcionPage() {
  const { hasCapability } = usePermissionDependencies();
  const canRead = hasCapability(PERMISO, { allOf: [PERMISO] });

  const [centroId, setCentroId] = useState("");
  const [consultorioId, setConsultorioId] = useState("");
  const [turnoId, setTurnoId] = useState("");
  const [tipo, setTipo] = useState<TipoDerechohabiente | "">("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const debouncedQ = useDebounce(q, 400);

  const filtros = {
    centroId: toNumber(centroId),
    consultorioId: toNumber(consultorioId),
    turnoId: toNumber(turnoId),
    tipo: tipo || undefined,
    q: debouncedQ.trim() || undefined,
  };

  const resumen = useAdscripcionResumen({ enabled: canRead });
  const adscritos = useAdscritosReport({ ...filtros, page, pageSize }, { enabled: canRead });
  const { exportReport, isExporting } = useExportAdscripcionReport();

  const centros = resumen.data?.centros ?? [];
  const centrosVisibles = centroId ? centros.filter((c) => c.idCentroAtencion === Number(centroId)) : centros;
  const turnos = [
    ...new Map(centros.flatMap((c) => c.consultorios).map((c) => [c.turnoId, c.turno])).entries(),
  ].sort((a, b) => a[1].localeCompare(b[1]));
  const opcionesConsultorio = centrosVisibles.flatMap((centro) =>
    centro.consultorios.map((c) => ({
      id: c.consultorioId,
      etiqueta: [etiquetaConsultorio(c.numero, c.consultorio), c.turno, centroId ? null : centro.centro]
        .filter(Boolean)
        .join(" · "),
    })),
  );
  const conteo = centroId ? centrosVisibles[0] : resumen.data?.totales;

  const resetPage = () => setPage(1);
  const hasFilters = Boolean(centroId || consultorioId || turnoId || tipo || debouncedQ.trim());
  const clearFilters = () => {
    setCentroId("");
    setConsultorioId("");
    setTurnoId("");
    setTipo("");
    setQ("");
    resetPage();
  };

  const columnasAdscritos: DataTableColumn<Adscrito>[] = [
    {
      key: "paciente",
      header: "Derechohabiente",
      className: "w-[260px]",
      render: (row) => (
        <div className="min-w-0">
          <p className="font-medium text-txt-body">{row.nombre || "Sin nombre registrado"}</p>
          <p className="text-xs text-txt-muted">Exp. {row.noExp}</p>
        </div>
      ),
    },
    {
      key: "tipo",
      header: "Tipo",
      render: (row) => (
        <Badge variant={row.tipo === "TITULAR" ? "secondary" : "outline"}>{TIPO_LABEL[row.tipo]}</Badge>
      ),
    },
    { key: "centro", header: "Centro", className: "w-[180px]", render: (row) => row.centro },
    {
      key: "consultorio",
      header: "Consultorio",
      render: (row) => <ConsultorioCell numero={row.numeroConsultorio} nombre={row.consultorio} />,
    },
    { key: "turno", header: "Turno", render: (row) => row.turno },
    { key: "fechaInicio", header: "Adscrito desde", render: (row) => formatDate(row.fechaInicio) },
  ];

  if (!canRead) {
    return (
      <CatalogModuleLayout title={TITULO} description={DESCRIPCION} icon={<Users className="size-5" />}>
        <AdminReadOnlyNotice message="No tienes permiso para ver este reporte." />
      </CatalogModuleLayout>
    );
  }

  return (
    <CatalogModuleLayout title={TITULO} description={DESCRIPCION} icon={<Users className="size-5" />}>
      {conteo ? <Totales conteo={conteo} /> : null}

      <TableHeaderBar
        search={
          <div className="flex flex-wrap items-end gap-3">
            <TableSearch
              value={q}
              onChange={(value) => {
                setQ(value);
                resetPage();
              }}
              placeholder="Buscar por nombre o expediente"
            />
            <div className="flex flex-col gap-1">
              <Label htmlFor="reporte-adscripcion-centro">Centro</Label>
              <select
                id="reporte-adscripcion-centro"
                className={SELECT_CLASS}
                value={centroId}
                onChange={(e) => {
                  setCentroId(e.target.value);
                  setConsultorioId(""); // el consultorio elegido es de otro centro
                  resetPage();
                }}
              >
                <option value="">Todos</option>
                {centros.map((c) => (
                  <option key={c.idCentroAtencion} value={c.idCentroAtencion}>{c.centro}</option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <Label htmlFor="reporte-adscripcion-consultorio">Consultorio</Label>
              <select
                id="reporte-adscripcion-consultorio"
                className={SELECT_CLASS}
                value={consultorioId}
                onChange={(e) => {
                  setConsultorioId(e.target.value);
                  resetPage();
                }}
              >
                <option value="">Todos</option>
                {opcionesConsultorio.map((c) => (
                  <option key={c.id} value={c.id}>{c.etiqueta}</option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <Label htmlFor="reporte-adscripcion-turno">Turno</Label>
              <select
                id="reporte-adscripcion-turno"
                className={SELECT_CLASS}
                value={turnoId}
                onChange={(e) => {
                  setTurnoId(e.target.value);
                  resetPage();
                }}
              >
                <option value="">Todos</option>
                {turnos.map(([id, nombre]) => (
                  <option key={id} value={id}>{nombre}</option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <Label htmlFor="reporte-adscripcion-tipo">Tipo</Label>
              <select
                id="reporte-adscripcion-tipo"
                className={SELECT_CLASS}
                value={tipo}
                onChange={(e) => {
                  setTipo(e.target.value as TipoDerechohabiente | "");
                  resetPage();
                }}
              >
                <option value="">Todos</option>
                <option value="TITULAR">Titulares</option>
                <option value="FAMILIAR">Familiares</option>
              </select>
            </div>
          </div>
        }
        actions={
          <Button variant="outline" disabled={isExporting} onClick={() => void exportReport(filtros)}>
            <Download className="size-4" />
            Exportar Excel
          </Button>
        }
      />

      <ResumenAdscripcionTable
        centros={centrosVisibles}
        turnoId={toNumber(turnoId) ?? null}
        isLoading={resumen.isLoading}
        isError={resumen.isError}
        onRetry={() => void resumen.refetch()}
        onVerConsultorio={(consultorio, centro) => {
          setCentroId(String(centro.idCentroAtencion));
          setConsultorioId(String(consultorio.consultorioId));
          resetPage();
        }}
      />

      <DataTable
        ariaLabel="Adscritos"
        columns={columnasAdscritos}
        rows={adscritos.data?.items ?? []}
        isLoading={adscritos.isLoading}
        isError={adscritos.isError}
        errorTitle="No se pudo cargar la lista de adscritos"
        onRetry={() => void adscritos.refetch()}
        hasFilters={hasFilters}
        onClearFilters={clearFilters}
        getRowKey={(row) => row.idAdscripcion.toString()}
        emptyTitle="Sin adscritos"
        emptyDescription="Cuando recepción adscriba pacientes a su consultorio familiar aparecerán aquí."
        minWidthClassName="min-w-[1000px]"
        pagination={{
          page,
          pageSize,
          total: adscritos.data?.total ?? 0,
          totalPages: adscritos.data?.totalPages ?? 1,
          onPageChange: setPage,
          onPageSizeChange: (value) => {
            setPageSize(value);
            resetPage();
          },
        }}
      />
    </CatalogModuleLayout>
  );
}

export default ReporteAdscripcionPage;
