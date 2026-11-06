import { useState } from "react";
import { toast } from "sonner";
import { CalendarX2, Stethoscope, Users } from "lucide-react";
import { Button } from "@shared/ui/button";
import { ApiError } from "@api/utils/errors";
import type {
  FamiliaAdscripcionResponse,
  MiembroFamiliaAdscripcion,
  OpcionConsultorio,
  ResultadoAsignacionFamilia,
} from "@api/types";
import { useMotivosCancelacion } from "@features/recepcion/modules/citas/queries/useMotivosCancelacion";
import { useFamiliaAdscripcion } from "@features/recepcion/modules/adscripcion/queries/useAdscripcionQueries";
import { useAdscribirFamilia } from "@features/recepcion/modules/adscripcion/mutations/useAdscripcionMutations";
import { etiquetaConsultorio } from "@features/recepcion/modules/adscripcion/domain/adscripcionEstado";
import {
  armarAsignaciones,
  citasDelPlan,
  consultorioSugerido,
  eleccionInicial,
  textoRazon,
  textoSinOpciones,
  type EleccionFamilia,
} from "@features/recepcion/modules/adscripcion/domain/familiaAdscripcion";

/** Nombre del motivo que siembra la migración recepcion/0034. */
const MOTIVO_CAMBIO_CONSULTORIO = "Cambio de consultorio familiar";

const SELECT_CLASS =
  "h-9 w-full rounded-md border border-line-struct bg-paper px-2 text-sm disabled:cursor-not-allowed disabled:opacity-60";

const formatoFecha = (iso: string) =>
  new Date(iso).toLocaleString("es-MX", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });

const etiquetaOpcion = (o: OpcionConsultorio) =>
  [
    etiquetaConsultorio(o),
    o.capacidadMaxima != null ? `${o.carga}/${o.capacidadMaxima}` : `${o.carga} pacientes`,
    o.sugerida ? "Sugerido" : null,
    o.esDeLaFamilia ? "Su familia" : null,
  ]
    .filter(Boolean)
    .join(" · ");

const situacion = (m: MiembroFamiliaAdscripcion) => {
  if (m.razon) return textoRazon(m.razon);
  if (m.estado === "VIGENTE" && m.adscripcionActual) {
    return `${etiquetaConsultorio({ numero: m.adscripcionActual.numeroConsultorio, turno: m.adscripcionActual.turno })} · márcalo para moverlo`;
  }
  if (m.estado === "NO_COINCIDE") return "SERMED lo cambió de clínica";
  if (m.estado === "CONSULTORIO_INACTIVO") return "Su consultorio ya no está activo";
  return "Sin consultorio";
};

interface ConsultorioFamiliarPanelProps {
  noExp: string;
  /** Recibe un resultado por miembro asignado (para seguir con la ficha). */
  onAsignado: (resultados: ResultadoAsignacionFamilia[]) => void;
  onCerrar: () => void;
}

/**
 * P-03 · Consultorio familiar del núcleo en un solo paso, dentro del flujo de
 * la ficha. Abrirlo no registra a nadie: los pacientes se registran al
 * confirmar, todos o ninguno.
 */
export const ConsultorioFamiliarPanel = ({ noExp, onAsignado, onCerrar }: ConsultorioFamiliarPanelProps) => {
  const { data: familia, dataUpdatedAt, isLoading, isError, refetch } = useFamiliaAdscripcion(noExp);

  if (isLoading) {
    return <Marco><p className="text-sm text-txt-muted">Buscando consultorios de la familia...</p></Marco>;
  }
  if (isError || !familia) {
    return (
      <Marco>
        <p className="text-sm text-status-critical" role="alert">No se pudo cargar la familia.</p>
        <Button type="button" size="sm" variant="outline" onClick={() => void refetch()}>Reintentar</Button>
      </Marco>
    );
  }

  const sinConsultorio = familia.miembros.filter((m) => m.estado !== "VIGENTE").length;
  const resumen = `${sinConsultorio} de ${familia.miembros.length} sin consultorio`;
  const sugerido = consultorioSugerido(familia);

  if (familia.motivoSinOpciones || sugerido == null) {
    return (
      <Marco resumen={resumen}>
        <p className="text-sm text-status-critical" role="alert">
          {familia.motivoSinOpciones
            ? textoSinOpciones(familia.motivoSinOpciones)
            : "No hay consultorios familiares para esta familia."}{" "}
          Avise al administrador (Admin › Catálogos › Consultorio familiar).
        </p>
        <div className="flex justify-end">
          <Button type="button" size="sm" variant="outline" onClick={onCerrar}>Cerrar</Button>
        </div>
      </Marco>
    );
  }

  return (
    <Marco resumen={resumen}>
      {/* Cada respuesta nueva (al abrir o al recargar tras un conflicto) reinicia la elección. */}
      <EleccionFamiliaForm
        key={dataUpdatedAt}
        familia={familia}
        sugerido={sugerido}
        onAsignado={onAsignado}
        onCerrar={onCerrar}
        onRecargar={() => void refetch()}
      />
    </Marco>
  );
};

interface EleccionFamiliaFormProps {
  familia: FamiliaAdscripcionResponse;
  sugerido: number;
  onAsignado: (resultados: ResultadoAsignacionFamilia[]) => void;
  onCerrar: () => void;
  onRecargar: () => void;
}

const EleccionFamiliaForm = ({ familia, sugerido, onAsignado, onCerrar, onRecargar }: EleccionFamiliaFormProps) => {
  const { data: motivosData } = useMotivosCancelacion();
  const asignar = useAdscribirFamilia();

  const [eleccion, setEleccion] = useState<EleccionFamilia>(() => eleccionInicial(familia));
  const [consultorioFamilia, setConsultorioFamilia] = useState(sugerido);
  const [cambiando, setCambiando] = useState<number | null>(null);
  // null = sin tocar: vale el motivo "Cambio de consultorio familiar".
  const [motivoElegido, setMotivoElegido] = useState<string | null>(null);
  const motivoPorDefecto = motivosData?.results.find((m) => m.name === MOTIVO_CAMBIO_CONSULTORIO);
  const motivoId = motivoElegido ?? (motivoPorDefecto ? String(motivoPorDefecto.id) : "");

  const asignaciones = armarAsignaciones(familia, eleccion, consultorioFamilia);
  const citas = citasDelPlan(familia, eleccion, consultorioFamilia);
  const faltaMotivo = citas.length > 0 && !motivoId;

  const marcar = (pkNum: number, marcado: boolean) =>
    setEleccion((prev) => ({ ...prev, [pkNum]: { ...prev[pkNum], marcado } }));
  const elegirConsultorio = (pkNum: number, consultorioId: number | null) =>
    setEleccion((prev) => ({ ...prev, [pkNum]: { ...prev[pkNum], consultorioId } }));

  const confirmar = async () => {
    try {
      const respuesta = await asignar.mutateAsync({
        noExp: familia.noExp,
        asignaciones,
        motivoCancelacionId: citas.length > 0 && motivoId ? Number(motivoId) : null,
        origen: "CHECKIN",
      });
      const canceladas = respuesta.resultados.reduce((n, r) => n + r.citasCanceladas.length, 0);
      toast.success("Consultorio familiar asignado", {
        description: canceladas > 0 ? `Se cancelaron ${canceladas} citas; quedan en "Citas por reagendar".` : undefined,
      });
      onAsignado(respuesta.resultados);
    } catch (error) {
      if (error instanceof ApiError && ["CITAS_MODIFICADAS", "ADSCRIPCION_MODIFICADA"].includes(error.code)) {
        toast.error("La familia cambió mientras la revisaba", { description: "Revise y confirme otra vez." });
        onRecargar();
        return;
      }
      const pkNum = error instanceof ApiError ? (error.details as { pkNum?: number } | undefined)?.pkNum : undefined;
      const quien = familia.miembros.find((m) => m.pkNum === pkNum)?.nombre;
      toast.error(quien ? `No se pudo asignar a ${quien}` : "No se pudo asignar el consultorio", {
        description: error instanceof ApiError ? error.message : "Intente nuevamente.",
      });
    }
  };

  return (
    <div className="space-y-3">
      <div className="space-y-1">
        <label htmlFor="consultorio-familia" className="text-xs font-semibold text-txt-muted">
          Consultorio para la familia
        </label>
        <select
          id="consultorio-familia"
          className={SELECT_CLASS}
          value={consultorioFamilia}
          disabled={asignar.isPending}
          onChange={(e) => setConsultorioFamilia(Number(e.target.value))}
        >
          {familia.opciones.map((o) => (
            <option key={o.consultorioId} value={o.consultorioId}>{etiquetaOpcion(o)}</option>
          ))}
        </select>
      </div>

      {familia.familiaSeparada ? (
        <p className="rounded-lg border border-status-alert/40 bg-status-alert/10 px-3 py-2 text-xs text-status-alert" role="status">
          El consultorio donde ya está la familia no tiene lugar: con este, la familia quedará separada.
        </p>
      ) : null}

      <ul className="divide-y divide-line-struct rounded-lg border border-line-struct">
        {familia.miembros.map((m) => {
          const propia = eleccion[m.pkNum];
          const marcado = m.elegible && !!propia?.marcado;
          const destino = familia.opciones.find((o) => o.consultorioId === (propia?.consultorioId ?? consultorioFamilia));
          return (
            <li key={m.pkNum} className={["space-y-1.5 px-3 py-2", m.elegible ? "" : "opacity-60"].join(" ")}>
              <div className="flex items-start gap-2.5">
                <input
                  type="checkbox"
                  className="mt-1 size-4 accent-primary"
                  aria-label={`Asignar a ${m.nombre}`}
                  checked={marcado}
                  disabled={!m.elegible || asignar.isPending}
                  onChange={(e) => marcar(m.pkNum, e.target.checked)}
                />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-txt-body">
                    {m.nombre}
                    {m.pkNum === 0 ? <span className="ml-1 text-xs font-normal text-txt-muted">(titular)</span> : null}
                  </p>
                  <p className="text-xs text-txt-muted">{situacion(m)}</p>
                </div>
                {marcado && destino ? (
                  <div className="flex shrink-0 items-center gap-1.5 text-xs">
                    <span className="font-medium text-primary">→ {etiquetaConsultorio(destino)}</span>
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      className="h-7 px-2"
                      aria-label={`Cambiar consultorio de ${m.nombre}`}
                      onClick={() => setCambiando(cambiando === m.pkNum ? null : m.pkNum)}
                    >
                      Cambiar
                    </Button>
                  </div>
                ) : null}
              </div>
              {marcado && cambiando === m.pkNum ? (
                <select
                  aria-label={`Consultorio de ${m.nombre}`}
                  className={SELECT_CLASS}
                  value={propia?.consultorioId ?? ""}
                  onChange={(e) => elegirConsultorio(m.pkNum, e.target.value ? Number(e.target.value) : null)}
                >
                  <option value="">El de la familia</option>
                  {familia.opciones.map((o) => (
                    <option key={o.consultorioId} value={o.consultorioId}>{etiquetaOpcion(o)}</option>
                  ))}
                </select>
              ) : null}
            </li>
          );
        })}
      </ul>

      {citas.length > 0 ? (
        <div
          role="alert"
          aria-label="Citas que se cancelan"
          className="space-y-2 rounded-lg border border-status-alert/40 bg-status-alert/10 px-3 py-2.5"
        >
          <p className="flex items-center gap-2 text-sm font-semibold text-status-alert">
            <CalendarX2 className="size-4" />
            Se cancelarán {citas.length} {citas.length === 1 ? "cita" : "citas"}
          </p>
          <ul className="space-y-0.5 pl-6 text-xs text-txt-body">
            {citas.map(({ nombre, cita }) => (
              <li key={cita.idCita} className="list-disc">
                {nombre} · {formatoFecha(cita.fechaHora)} · {cita.consultorio ?? "Sin consultorio"} · {cita.folio}
              </li>
            ))}
          </ul>
          <p className="text-xs text-txt-muted">Quedarán en "Citas por reagendar".</p>
          <select
            aria-label="Motivo de cancelación"
            className={SELECT_CLASS}
            value={motivoId}
            onChange={(e) => setMotivoElegido(e.target.value)}
          >
            <option value="">Selecciona el motivo</option>
            {(motivosData?.results ?? []).map((motivo) => (
              <option key={motivo.id} value={String(motivo.id)}>{motivo.name}</option>
            ))}
          </select>
        </div>
      ) : null}

      <div className="flex justify-end gap-2">
        <Button type="button" variant="outline" size="sm" onClick={onCerrar} disabled={asignar.isPending}>
          Ahora no
        </Button>
        <Button
          type="button"
          size="sm"
          autoFocus
          disabled={asignaciones.length === 0 || faltaMotivo || asignar.isPending}
          onClick={() => void confirmar()}
        >
          Asignar y continuar ({asignaciones.length})
        </Button>
      </div>
    </div>
  );
};

const Marco = ({ resumen, children }: { resumen?: string; children: React.ReactNode }) => (
  <section aria-label="Consultorio familiar" className="space-y-3 rounded-xl border border-primary/40 bg-primary/5 px-3 py-3">
    <header className="flex items-center justify-between gap-2">
      <p className="flex items-center gap-2 text-sm font-semibold text-txt-body">
        <Stethoscope className="size-4 text-primary" />
        Consultorio familiar
      </p>
      {resumen ? (
        <span className="flex items-center gap-1 text-xs text-txt-muted">
          <Users className="size-3.5" />
          {resumen}
        </span>
      ) : null}
    </header>
    {children}
  </section>
);
