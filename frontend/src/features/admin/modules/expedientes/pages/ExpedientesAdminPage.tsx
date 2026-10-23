import { useState } from "react";
import { Link } from "react-router-dom";
import { Search, RefreshCw, Stethoscope, UserCircle, X } from "lucide-react";
import { Button } from "@shared/ui/button";
import { Input } from "@shared/ui/input";
import { Badge } from "@shared/ui/badge";
import { useExpediente } from "../queries/useExpediente";
import { useBuscarPorNombre } from "../queries/useBuscarPorNombre";
import { useActualizarExpediente } from "../mutations/useActualizarExpediente";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import { formatCatalogDateTime } from "@features/admin/modules/catalogos/shared/utils/catalog-format";
import { ApiError } from "@api/utils/errors";
import type {
  EmpleadoResumen,
  UltimaActualizacionExpediente,
} from "@api/types/expedientes.types";

const esExpediente = (valor: string) => /^\d+$/.test(valor.trim());

export default function ExpedientesAdminPage() {
  const { hasCapability } = usePermissionDependencies();
  const canActualizar = hasCapability("admin.expedientes.update", {
    allOf: ["admin:gestion:expedientes:update"],
  });
  const [input, setInput] = useState("");
  const [busqueda, setBusqueda] = useState("");         // expediente activo → useExpediente
  const [busquedaNombre, setBusquedaNombre] = useState(""); // nombre activo → useBuscarPorNombre
  const [seleccionado, setSeleccionado] = useState<string | null>(null);

  const { data, isLoading, isFetching, error: errorExpediente } = useExpediente(busqueda);
  const {
    data: resultadosNombre,
    isLoading: isLoadingNombre,
    isFetching: isFetchingNombre,
    error: errorNombre,
  } = useBuscarPorNombre(busquedaNombre);
  // 404 = el expediente no existe. Cualquier otro error (p. ej. 503
  // EXPEDIENTES_NO_DISPONIBLE) es una falla tecnica: no decir "no encontrado".
  const errorTecnico = [errorExpediente, errorNombre].find(
    (e) => e && !(e instanceof ApiError && e.status === 404),
  );
  const actualizar = useActualizarExpediente();

  const personas = [
    ...(data?.empleados ?? []).map((e) => ({ ...e, _tipo: "empleado" as const })),
    ...(data?.familiares ?? []).map((f) => ({
      NO_EXP: f.NO_EXPF,
      DS_PATERNO: f.DS_PATERNO,
      DS_MATERNO: f.DS_MATERNO,
      DS_NOMBRE: f.DS_NOMBRE,
      CD_LABORAL: null,
      CVE_BAJA: null,
      FEC_BAJA: null,
      FE_NAC: f.FE_NAC,
      FEC_VIG: f.FEC_VIG,
      PARENTESCO: f.CD_PARENTESCO ?? "FAMILIAR",
      CLINICA: f.CLINICA,
      ESTATUS: f.ESTATUS as string,
      EDAD: f.EDAD,
      FOTO: f.FOTO,
      _tipo: "familiar" as const,
    })),
  ];

  const handleBuscar = () => {
    const val = input.trim();
    if (!val) return;

    setSeleccionado(null);

    if (esExpediente(val)) {
      setBusquedaNombre("");
      setBusqueda(val);
    } else {
      setBusqueda("");
      setBusquedaNombre(val);
    }
  };

  const handleSeleccionarEmpleado = (emp: EmpleadoResumen) => {
    const noExp = String(emp.NO_EXP);
    setSeleccionado(noExp);
    setBusqueda(noExp);
  };

  const handleActualizar = () => {
    if (!busqueda) return;
    actualizar.mutate({ expediente: busqueda });
  };

  const handleLimpiar = () => {
    setInput("");
    setBusqueda("");
    setBusquedaNombre("");
    setSeleccionado(null);
  };

  const modoNombre = busquedaNombre.length > 0;
  const modoExpediente = busqueda.length > 0 && !modoNombre;
  const cargando = isLoading || isFetching || isLoadingNombre || isFetchingNombre;
  const puedeActualizar =
    canActualizar && modoExpediente && !!busqueda && !actualizar.isPending;
  const motivoSinActualizar = !canActualizar
    ? "No tienes permiso para actualizar expedientes desde SERMED"
    : modoNombre
      ? "Solo se puede actualizar buscando por número de expediente"
      : "";

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold">Consulta de Expedientes</h1>
        <p className="text-txt-muted text-sm mt-1">
          Ingresá un número de expediente o un nombre para buscar.
        </p>
      </div>

      {/* Buscador único */}
      <div className="flex gap-2 max-w-2xl">
        <Input
          placeholder="Número de expediente o nombre / apellido"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleBuscar()}
        />
        <Button onClick={handleBuscar} disabled={!input.trim() || cargando}>
          <Search className="w-4 h-4 mr-2" />
          Buscar
        </Button>
        <Button
          variant="outline"
          onClick={handleActualizar}
          disabled={!puedeActualizar}
          title={motivoSinActualizar}
        >
          <RefreshCw
            className={`w-4 h-4 mr-2 ${actualizar.isPending ? "animate-spin" : ""}`}
          />
          Actualizar
        </Button>
        <Button
          variant="outline"
          onClick={handleLimpiar}
          disabled={!input && !busqueda && !busquedaNombre}
        >
          <X className="w-4 h-4 mr-2" />
          Limpiar
        </Button>
      </div>

      {cargando && <p className="text-txt-muted text-sm">Buscando...</p>}

      {!cargando && errorTecnico && (
        <div role="alert" className="rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800">
          {errorTecnico instanceof ApiError && errorTecnico.message
            ? errorTecnico.message
            : "No se pudo consultar SERMED en este momento. No significa que el expediente no exista: avisá a sistemas."}
        </div>
      )}

      {/* Resultados por nombre */}
      {!cargando && modoNombre && (
        <>
          {resultadosNombre?.length === 0 && (
            <p className="text-txt-muted text-sm">
              No se encontraron empleados para <strong>"{busquedaNombre}"</strong>.
            </p>
          )}

          {resultadosNombre && resultadosNombre.length > 0 && (
            <>
              <p className="text-txt-muted text-xs">
                {resultadosNombre.length} resultado(s)
                {seleccionado
                  ? ` — mostrando expediente ${seleccionado}`
                  : " — hacé clic en una fila para ver el expediente completo"}
              </p>
              <div className="overflow-x-auto rounded-lg border">
                <table className="w-full text-sm">
                  <thead className="bg-muted text-txt-muted">
                    <tr>
                      <th className="px-3 py-2 text-left">Expediente</th>
                      <th className="px-3 py-2 text-left">Nombre</th>
                      <th className="px-3 py-2 text-left">Calidad Laboral</th>
                      <th className="px-3 py-2 text-left">Clínica</th>
                      <th className="px-3 py-2 text-left">Estatus</th>
                    </tr>
                  </thead>
                  <tbody>
                    {resultadosNombre.map((emp) => (
                      <tr
                        key={emp.NO_EXP}
                        onClick={() => handleSeleccionarEmpleado(emp)}
                        className={`border-t cursor-pointer transition-colors ${
                          seleccionado === String(emp.NO_EXP)
                            ? "bg-primary/10 hover:bg-primary/15"
                            : "hover:bg-muted/60"
                        }`}
                      >
                        <td className="px-3 py-2 font-mono font-semibold">{emp.NO_EXP}</td>
                        <td className="px-3 py-2 font-medium">
                          {[emp.DS_PATERNO, emp.DS_MATERNO, emp.DS_NOMBRE].filter(Boolean).join(" ") || "—"}
                        </td>
                        <td className="px-3 py-2">{emp.CD_LABORAL ?? "—"}</td>
                        <td className="px-3 py-2">{emp.CLINICA ?? "—"}</td>
                        <td className="px-3 py-2">
                          <Badge variant={emp.ESTATUS === "ACTIVO" ? "stable" : "critical"}>
                            {emp.ESTATUS}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}

          {/* Expediente completo al seleccionar desde nombre */}
          {seleccionado && !isLoading && !isFetching && (
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <div className="h-px flex-1 bg-border" />
                <span className="text-xs text-txt-muted px-2">Expediente completo</span>
                <div className="h-px flex-1 bg-border" />
              </div>
              {personas.length > 0 && (
                <ExpedienteDetalle busqueda={seleccionado} personas={personas} data={data} />
              )}
            </div>
          )}
        </>
      )}

      {/* Resultados por expediente */}
      {!cargando && modoExpediente && (
        <>
          {personas.length === 0 && !errorTecnico && (
            <p className="text-txt-muted text-sm">
              No se encontraron registros para <strong>{busqueda}</strong>.
            </p>
          )}
          {personas.length > 0 && (
            <ExpedienteDetalle busqueda={busqueda} personas={personas} data={data} />
          )}
        </>
      )}
    </div>
  );
}

// ── Detalle reutilizable ──────────────────────────────────────────

type Persona = {
  NO_EXP: string;
  DS_PATERNO: string | null;
  DS_MATERNO: string | null;
  DS_NOMBRE: string | null;
  CD_LABORAL: string | null;
  FEC_VIG: string | null;
  PARENTESCO: string;
  CLINICA: string | null;
  ESTATUS: string;
  EDAD: number | null;
  FOTO: string | null;
  _tipo: "empleado" | "familiar";
};

function ExpedienteDetalle({
  busqueda,
  personas,
  data,
}: {
  busqueda: string;
  personas: Persona[];
  data:
    | {
        empleados: { CD_LABORAL: string | null }[];
        ultima_actualizacion?: UltimaActualizacionExpediente | null;
      }
    | undefined;
}) {
  const ultima = data?.ultima_actualizacion ?? null;
  return (
    <>
      <div className="flex flex-wrap items-center gap-x-6 gap-y-1 px-4 py-3 rounded-lg border bg-muted/40 text-sm">
        <span>
          <span className="text-txt-muted">Expediente:</span>{" "}
          <span className="font-semibold">{busqueda}</span>
        </span>
        {data?.empleados[0]?.CD_LABORAL && (
          <span>
            <span className="text-txt-muted">Calidad Laboral:</span>{" "}
            <span className="font-semibold">{data.empleados[0].CD_LABORAL}</span>
          </span>
        )}
        {/* Antes de confiar en el estatus: ¿qué tan reciente es la copia de SERMED? */}
        <span>
          <span className="text-txt-muted">Última actualización desde SERMED:</span>{" "}
          {ultima ? (
            <>
              <span className="font-semibold">{formatCatalogDateTime(ultima.fecha)}</span>
              <span className="text-txt-muted"> por </span>
              <span className="font-semibold">{ultima.usuario}</span>
              {ultima.resultado === "PARCIAL" && (
                <Badge variant="critical" className="ml-2">
                  Parcial
                </Badge>
              )}
            </>
          ) : (
            <span className="font-semibold">Sin registro en SIRES</span>
          )}
        </span>
      </div>

      <div className="overflow-x-auto rounded-lg border">
        <table className="w-full text-sm">
          <thead className="bg-muted text-txt-muted">
            <tr>
              <th className="px-3 py-2 text-left">#</th>
              <th className="px-3 py-2 text-left">Nombre</th>
              <th className="px-3 py-2 text-left">Edad</th>
              <th className="px-3 py-2 text-left">Parentesco</th>
              <th className="px-3 py-2 text-left">Estatus</th>
              <th className="px-3 py-2 text-left">Clínica</th>
              <th className="px-3 py-2 text-left">Vigencia</th>
              <th className="px-3 py-2 text-left">Foto</th>
            </tr>
          </thead>
          <tbody>
            {personas.map((p, i) => (
              <tr key={`${p.NO_EXP}-${i}`} className="border-t hover:bg-muted/40">
                <td className="px-3 py-2">{i + 1}</td>
                <td className="px-3 py-2 font-medium">
                  {[p.DS_PATERNO, p.DS_MATERNO, p.DS_NOMBRE].filter(Boolean).join(" ")}
                </td>
                <td className="px-3 py-2">{p.EDAD ?? "—"}</td>
                <td className="px-3 py-2">{p.PARENTESCO}</td>
                <td className="px-3 py-2">
                  <Badge variant={p.ESTATUS === "ACTIVO" ? "stable" : "critical"}>
                    {p.ESTATUS}
                  </Badge>
                </td>
                <td className="px-3 py-2">{p.CLINICA ?? "—"}</td>
                <td className="px-3 py-2">{p.FEC_VIG ?? "--/--"}</td>
                <td className="px-3 py-2">
                  <div className="flex items-center gap-2">
                    {p.FOTO ? (
                      <img
                        src={`data:image/jpeg;base64,${p.FOTO}`}
                        alt="Foto"
                        className="w-32 h-auto border rounded"
                      />
                    ) : (
                      <div className="w-14 h-16 border rounded flex items-center justify-center bg-muted">
                        <UserCircle className="w-6 h-6 text-txt-hint" />
                      </div>
                    )}
                    <Button
                      asChild
                      variant="outline"
                      size="icon-sm"
                      title="Ver expediente clínico"
                    >
                      <Link to={`/clinico/expedientes/${p.NO_EXP}`}>
                        <Stethoscope className="w-4 h-4" />
                      </Link>
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
