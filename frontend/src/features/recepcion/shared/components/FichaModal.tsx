import { Loader2 } from "lucide-react";
import { Button } from "@shared/ui/button";
import { Badge }  from "@shared/ui/badge";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@shared/ui/dialog";
import type {
  VisitQueueItem, VisitService, VisitStatus, VisitStatusLogItem, VisitVitalsPayload,
} from "@api/types";
import { PrintButton } from "@shared/components/print/PrintButton";
import { usePatientLookupHistorico } from "@features/recepcion/modules/checkin/queries/usePatientLookup";
import { useVisitStatusLog } from "@features/recepcion/modules/checkin/queries/useVisitStatusLog";

// ─── Constantes ───────────────────────────────────────────────────────────────

const SERVICE_LABEL: Record<VisitService, string> = {
  medicina_general: "Medicina General",
  especialidad:     "Especialidad",
  urgencias:        "Urgencias",
};

const STATUS_LABEL: Record<VisitStatus, string> = {
  en_espera:         "En espera",
  en_somatometria:   "En somatometría",
  lista_para_doctor: "Lista para doctor",
  en_consulta:       "En consulta",
  cerrada:           "Cerrada",
  cancelada:         "Cancelada",
  no_show:           "No se presentó",
};

const STATUS_VARIANT: Record<VisitStatus,
  "outline" | "stable" | "alert" | "secondary" | "critical"
> = {
  en_espera:         "outline",
  en_somatometria:   "alert",
  lista_para_doctor: "alert",
  en_consulta:       "stable",
  cerrada:           "secondary",
  cancelada:         "critical",
  no_show:           "critical",
};

function formatFechaHora(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("es-MX", {
    day: "2-digit", month: "long", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

function formatHora(iso: string): string {
  return new Date(iso).toLocaleTimeString("es-MX", { hour: "2-digit", minute: "2-digit", hour12: false });
}

function formatFecha(iso: string | null | undefined): string {
  if (!iso) return "";
  // Agrega T00:00:00 si es solo fecha (YYYY-MM-DD) para evitar
  // que JS la interprete como UTC midnight y desfase la zona horaria.
  const d = iso.includes("T") ? new Date(iso) : new Date(iso + "T00:00:00");
  return d.toLocaleDateString("es-MX", { day: "2-digit", month: "2-digit", year: "numeric" });
}

function StatusLogEntry({ entry }: { entry: VisitStatusLogItem }) {
  return (
    <div className="flex items-start gap-3 py-2 border-b border-line-struct/30 last:border-0">
      <div className="mt-0.5 flex flex-col items-center gap-0.5">
        <div className="size-2 rounded-full bg-primary/60 shrink-0" />
        <div className="w-px flex-1 bg-line-struct/40 min-h-[12px]" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          {entry.fromStatus ? (
            <>
              <Badge variant={STATUS_VARIANT[entry.fromStatus as VisitStatus] ?? "outline"} className="text-[10px] py-0">
                {STATUS_LABEL[entry.fromStatus as VisitStatus] ?? entry.fromStatus}
              </Badge>
              <span className="text-txt-muted text-xs">→</span>
            </>
          ) : null}
          <Badge variant={STATUS_VARIANT[entry.toStatus as VisitStatus] ?? "outline"} className="text-[10px] py-0">
            {STATUS_LABEL[entry.toStatus as VisitStatus] ?? entry.toStatus}
          </Badge>
        </div>
        <p className="text-xs text-txt-muted mt-0.5">
          {formatHora(entry.changedAt)}
          {entry.changedByNombre ? ` · ${entry.changedByNombre}` : ""}
        </p>
        {entry.notes ? <p className="text-xs text-txt-body/70 mt-0.5 italic">{entry.notes}</p> : null}
      </div>
    </div>
  );
}

/**
 * Narrowing de recepcion (D3, somatometria-modulo-integral): un caller sin
 * capability de lectura de metricas (recepcion) recibe unicamente
 * `{hasVitals, capturedAt, reusedFromVisitId, reusedFrom}` -- SIN
 * "weightKg" ni ningun otro valor numerico. El chequeo es en runtime (no
 * en el tipo) porque `VisitVitalsPayload` sigue modelando el contrato
 * completo para el resto de los consumidores (enfermeria/medico), que
 * siempre reciben los valores completos.
 */
function hasVitalsValues(vitals: VisitVitalsPayload): boolean {
  return typeof (vitals as { weightKg?: unknown }).weightKg === "number";
}

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  if (!value) return null;
  return (
    <div className="flex items-start gap-3 border-b border-line-struct/40 py-2 last:border-0">
      <dt className="w-36 shrink-0 text-xs font-medium text-txt-muted uppercase tracking-wide">
        {label}
      </dt>
      <dd className="flex-1 text-sm font-medium text-txt-body">{value}</dd>
    </div>
  );
}

// ─── Props ────────────────────────────────────────────────────────────────────

interface FichaModalProps {
  open:         boolean;
  onOpenChange: (open: boolean) => void;
  visit:        VisitQueueItem | null;
}

// ─── Componente ───────────────────────────────────────────────────────────────

export function FichaModal({ open, onOpenChange, visit }: FichaModalProps) {
  const { data: patientData, isFetching: loadingPatient } = usePatientLookupHistorico(
    visit?.noExp ?? "",
    open && !!visit?.noExp,
  );

  const { data: statusLog, isFetching: loadingLog } = useVisitStatusLog(
    visit?.id,
    open && !!visit?.id,
  );

  const paciente = patientData
    ? [patientData.titular, ...patientData.dependientes]
        .filter(Boolean)
        .find((m) => m!.pkNum === visit?.pkNum) ?? null
    : null;

  if (!visit) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        showCloseButton
        className="w-[96vw] max-w-none overflow-hidden rounded-3xl bg-paper p-0 sm:max-w-[560px]"
      >
        <DialogHeader className="border-b border-line-struct px-6 pt-5 pb-4">
          <div className="flex items-center justify-between">
            <DialogTitle className="text-base font-semibold">
              Ficha de consulta
            </DialogTitle>
            <Badge variant={STATUS_VARIANT[visit.status]} className="text-xs">
              {STATUS_LABEL[visit.status]}
            </Badge>
          </div>
        </DialogHeader>

        {/* ── Contenido ─────────────────────────────────────────── */}
        <div className="px-6 py-4 max-h-[65vh] overflow-y-auto">

          {/* Folio + ficha */}
          <div className="mb-4 rounded-xl border border-line-struct/60 bg-subtle/20 px-4 py-3">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs text-txt-muted">Folio</p>
                <p className="text-xl font-bold text-txt-body font-mono tracking-widest">
                  {visit.folio}
                </p>
              </div>
              {visit.numFicha ? (
                <div className="text-right">
                  <p className="text-xs text-txt-muted">Ficha N°</p>
                  <p className="text-2xl font-bold text-primary">{visit.numFicha}</p>
                  {visit.turnoNombre ? (
                    <p className="text-xs text-txt-muted">{visit.turnoNombre}</p>
                  ) : null}
                </div>
              ) : null}
            </div>
            {visit.fechaAlta ? (
              <p className="mt-1 text-xs text-txt-muted">
                {formatFechaHora(visit.fechaAlta)}
              </p>
            ) : null}
          </div>

          {/* Datos */}
          <dl className="space-y-0">
            <InfoRow label="Paciente"    value={visit.nombrePaciente} />
            <InfoRow
              label="Expediente"
              value={
                visit.noExp ? (
                  <span className="font-mono">
                    {visit.noExp}
                    <span className="ml-2 font-sans text-xs text-txt-muted font-normal">
                      {visit.pkNum > 0 ? `Familiar #${visit.pkNum}` : "Titular"}
                    </span>
                  </span>
                ) : null
              }
            />
            <InfoRow
              label="Edad"
              value={
                loadingPatient
                  ? "Cargando..."
                  : paciente?.edad != null
                  ? `${paciente.edad} años`
                  : null
              }
            />
            <InfoRow label="Fecha nac."  value={loadingPatient ? "..." : paciente?.fechaNac} />
            <InfoRow label="Centro"      value={visit.centroNombre} />
            <InfoRow label="Médico"      value={visit.doctorNombre} />
            <InfoRow label="Consultorio" value={visit.consultorioNombre} />
            <InfoRow label="Servicio"    value={SERVICE_LABEL[visit.serviceType] ?? visit.serviceType} />
            <InfoRow label="Tipo de cita" value={visit.tipoCitaNombre ?? "—"} />
            <InfoRow
              label="Hora registro"
              value={
                visit.fechaAlta ? (
                  <span className="flex items-center gap-2">
                    <span className="font-mono font-bold">{formatHora(visit.fechaAlta)}</span>
                    <span className="text-txt-muted font-normal text-xs">{formatFecha(visit.fechaAlta)}</span>
                  </span>
                ) : null
              }
            />
            <InfoRow
              label="Hora cita"
              value={
                visit.horaConsulta ? (
                  <span className="flex items-center gap-2">
                    <span className="font-mono font-bold text-primary">{visit.horaConsulta}</span>
                    <span className="text-txt-muted font-normal text-xs">{formatFecha(visit.fechaConsulta ?? visit.fechaCita ?? visit.fechaAlta)}</span>
                  </span>
                ) : "—"
              }
            />
            {visit.appointmentId ? (
              <InfoRow label="ID Cita" value={<span className="font-mono">{visit.appointmentId}</span>} />
            ) : null}
            {(() => {
              const cierre = statusLog?.find((e) => e.toStatus === "cerrada");
              return cierre ? (
                <InfoRow
                  label="Hora cierre"
                  value={
                    <span className="flex items-center gap-2">
                      <span className="font-mono font-bold text-status-critical">{formatHora(cierre.changedAt)}</span>
                      <span className="text-txt-muted font-normal text-xs">{formatFecha(cierre.changedAt)}</span>
                    </span>
                  }
                />
              ) : null;
            })()}
            {visit.notes ? (
              <InfoRow label="Motivo" value={visit.notes} />
            ) : null}

            {/* Vitales */}
            {visit.vitals ? (
              <>
                <div className="pt-3 pb-1">
                  <p className="text-xs font-semibold uppercase tracking-wide text-txt-muted">
                    Signos vitales
                  </p>
                </div>
                {hasVitalsValues(visit.vitals) ? (
                  <>
                    <InfoRow label="Peso"       value={`${visit.vitals.weightKg} kg`} />
                    <InfoRow label="Talla"      value={`${visit.vitals.heightCm} cm`} />
                    <InfoRow label="IMC"        value={visit.vitals.bmi?.toFixed(1)} />
                    <InfoRow label="Temperatura" value={`${visit.vitals.temperatureC} °C`} />
                    <InfoRow label="Saturación" value={`${visit.vitals.oxygenSaturationPct} %`} />
                    {visit.vitals.heartRateBpm ? (
                      <InfoRow label="Frec. cardíaca" value={`${visit.vitals.heartRateBpm} lpm`} />
                    ) : null}
                    {visit.vitals.bloodPressureSystolic ? (
                      <InfoRow
                        label="Tensión arterial"
                        value={`${visit.vitals.bloodPressureSystolic}/${visit.vitals.bloodPressureDiastolic} mmHg`}
                      />
                    ) : null}
                    {visit.vitals.respiratoryRateBpm ? (
                      <InfoRow label="Frec. respiratoria" value={`${visit.vitals.respiratoryRateBpm} rpm`} />
                    ) : null}
                  </>
                ) : (
                  // Recepcion no tiene capability de lectura de metricas (D3):
                  // el contrato narrowed no trae valores, solo estado.
                  <InfoRow
                    label="Estado"
                    value={`Signos vitales capturados el ${formatFechaHora(visit.vitals.capturedAt)}`}
                  />
                )}
              </>
            ) : null}
          </dl>

          {/* ── Historial de estados (NOM-024) ───────────────────── */}
          <div className="mt-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-txt-muted mb-2">
              Historial de movimientos
            </p>
            {loadingLog ? (
              <div className="flex items-center gap-2 text-xs text-txt-muted py-2">
                <Loader2 className="size-3 animate-spin" />
                Cargando historial...
              </div>
            ) : statusLog && statusLog.length > 0 ? (
              <div>
                {statusLog.map((entry) => (
                  <StatusLogEntry key={entry.id} entry={entry} />
                ))}
              </div>
            ) : (
              <p className="text-xs text-txt-muted py-2 italic">Sin movimientos registrados.</p>
            )}
          </div>
        </div>

        {/* ── Footer ────────────────────────────────────────────── */}
        <div className="flex justify-between border-t border-line-struct px-6 py-3.5">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cerrar
          </Button>
          <PrintButton
            documento="ficha"
            resourceId={visit.id}
            label="Imprimir ficha"
          />
        </div>
      </DialogContent>
    </Dialog>
  );
}
