import { FileText, Globe, Loader2, Search } from "lucide-react";
import { Badge } from "@shared/ui/badge";
import { Input } from "@shared/ui/input";
import { Label } from "@shared/ui/label";
import {
  ESTATUS_CITA,
  type CitaListItem,
  type PatientLookupResponse,
  type VisitQueueItem,
} from "@api/types";
import { formatCitaFechaHora } from "@features/recepcion/shared/utils/recepcion-format";
import { ESTATUS_LABEL, ESTATUS_VARIANT } from "../pages/RecepcionAgendaPage.helpers";
import { CitaMovimientos } from "./CitaMovimientos";
import { HistVisitCard } from "./HistVisitCard";

interface Props {
  histNoExp:            string;
  setHistNoExp:         (value: string) => void;
  histFechaDesde:       string;
  setHistFechaDesde:    (value: string) => void;
  histFechaHasta:       string;
  setHistFechaHasta:    (value: string) => void;
  histDebouncedNoExp:   string;
  histEnabled:          boolean;
  histPatient:          PatientLookupResponse | undefined;
  histSelectedPkNum:    number | null;
  setHistSelectedPkNum: (pkNum: number | null) => void;
  histTab:              "citas" | "visitas";
  setHistTab:           (tab: "citas" | "visitas") => void;
  histCitas:            CitaListItem[];
  histCitasLoading:     boolean;
  histVisits:           VisitQueueItem[];
  histVisitsLoading:    boolean;
}

export function HistorialView({
  histNoExp,
  setHistNoExp,
  histFechaDesde,
  setHistFechaDesde,
  histFechaHasta,
  setHistFechaHasta,
  histDebouncedNoExp,
  histEnabled,
  histPatient,
  histSelectedPkNum,
  setHistSelectedPkNum,
  histTab,
  setHistTab,
  histCitas,
  histCitasLoading,
  histVisits,
  histVisitsLoading,
}: Props) {
  return (
    <div className="space-y-5">

      {/* ── Búsqueda ──────────────────────────────────────────────── */}
      <div className="rounded-xl border border-line-struct bg-paper px-6 py-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <FileText className="size-4 text-primary" />
              <h2 className="text-base font-semibold text-txt-body">Historial de encuentros clínicos</h2>
            </div>
            <p className="text-xs text-txt-muted">NOM-024-SSA3-2012 · NOM-004-SSA3-2012 · Registro electrónico de salud</p>
          </div>
          <Badge variant="outline" className="text-xs shrink-0 font-mono">Sistema de información en salud</Badge>
        </div>
        <div className="mt-4 flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[220px] space-y-1">
            <Label className="text-xs">Número de expediente</Label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-txt-muted pointer-events-none" />
              <Input placeholder="Ej. 12345 (mín. 4 caracteres)" value={histNoExp}
                onChange={(e) => { setHistNoExp(e.target.value); setHistSelectedPkNum(null); }}
                className="pl-9 h-9" />
            </div>
          </div>
          <div className="space-y-1 w-36">
            <Label className="text-xs">Desde</Label>
            <Input type="date" value={histFechaDesde} onChange={(e) => setHistFechaDesde(e.target.value)} className="h-9" />
          </div>
          <div className="space-y-1 w-36">
            <Label className="text-xs">Hasta <span className="font-normal text-txt-muted">(opc.)</span></Label>
            <Input type="date" value={histFechaHasta} min={histFechaDesde} onChange={(e) => setHistFechaHasta(e.target.value)} className="h-9" />
          </div>
        </div>
        {histDebouncedNoExp.trim().length > 0 && histDebouncedNoExp.trim().length < 4 ? (
          <p className="mt-2 text-xs text-txt-muted italic">Ingresa al menos 4 caracteres para buscar.</p>
        ) : null}
      </div>

      {/* ── Selector de miembro del núcleo familiar ─────────────── */}
      {histPatient && histEnabled ? (() => {
        const allMembers = [
          ...(histPatient.titular ? [histPatient.titular] : []),
          ...histPatient.dependientes,
        ];
        return (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold uppercase tracking-wide text-txt-muted">
                Núcleo familiar · Expediente <span className="font-mono text-txt-body">{histDebouncedNoExp.trim()}</span>
              </p>
              <p className="text-xs text-txt-muted">{allMembers.length} miembro(s)</p>
            </div>
            <div className="grid gap-2 sm:grid-cols-2 md:grid-cols-3">
              {allMembers.map((member) => {
                const sel = histSelectedPkNum === member.pkNum;
                return (
                  <button
                    key={member.pkNum}
                    type="button"
                    onClick={() => { setHistSelectedPkNum(member.pkNum); setHistTab("citas"); }}
                    className={[
                      "flex items-start gap-3 rounded-xl border px-4 py-3 text-left transition-colors",
                      sel ? "border-primary bg-primary/5" : "border-line-struct hover:bg-subtle/40",
                    ].join(" ")}
                  >
                    <div className={[
                      "mt-0.5 flex size-4 shrink-0 items-center justify-center rounded-full border-2",
                      sel ? "border-primary bg-primary" : "border-line-struct",
                    ].join(" ")}>
                      {sel ? <span className="size-1.5 rounded-full bg-white" /> : null}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold text-txt-body">{member.nombre}</p>
                      <p className="text-xs text-txt-muted">
                        {member.pkNum === 0 ? "Titular" : (member.parentesco ?? "Familiar")}
                        {member.edad != null ? ` · ${member.edad} años` : ""}
                      </p>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        );
      })() : null}

      {/* ── Contenido del miembro seleccionado ──────────────────── */}
      {histSelectedPkNum !== null && histEnabled ? (
        <div className="space-y-4">

          {/* Inner tabs */}
          <div className="flex items-center gap-1 rounded-xl border border-line-struct p-1 bg-subtle/20 w-fit">
            {(["citas", "visitas"] as const).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setHistTab(t)}
                className={[
                  "rounded-lg px-4 py-1.5 text-xs font-medium transition-colors",
                  histTab === t ? "bg-paper text-txt-body shadow-sm" : "text-txt-muted hover:text-txt-body",
                ].join(" ")}
              >
                {t === "citas"
                  ? `Citas agendadas (${histCitas.length})`
                  : `Visitas y movimientos (${histVisits.length})`}
              </button>
            ))}
          </div>

          {/* ─ Tab: Citas ───────────────────────────────────────── */}
          {histTab === "citas" ? (
            histCitasLoading ? (
              <div className="flex items-center gap-2 text-sm text-txt-muted py-4">
                <Loader2 className="size-4 animate-spin" /> Cargando citas...
              </div>
            ) : histCitas.length === 0 ? (
              <div className="rounded-xl border border-line-struct bg-paper py-12 text-center">
                <FileText className="size-10 text-txt-muted/30 mx-auto mb-3" />
                <p className="text-sm text-txt-muted">Sin citas registradas para este paciente.</p>
              </div>
            ) : (
              <div className="relative pl-5 border-l-2 border-line-struct/60 space-y-4">
                {histCitas.map((cita: CitaListItem) => {
                  const dot =
                    cita.estatus === ESTATUS_CITA.ATENDIDA   ? "bg-green-500" :
                    cita.estatus === ESTATUS_CITA.CANCELADA  ? "bg-red-400"   :
                    cita.estatus === ESTATUS_CITA.NO_ASISTIO ? "bg-amber-400" :
                    cita.estatus === ESTATUS_CITA.CONFIRMADA ? "bg-primary"   :
                                                               "bg-txt-muted/40";
                  return (
                    <div key={cita.id} className="relative">
                      <div className={`absolute -left-[25px] top-4 size-3 rounded-full border-2 border-paper ${dot}`} />
                      <article className="rounded-xl border border-line-struct bg-paper overflow-hidden">
                        <div className="flex items-start justify-between gap-3 px-5 py-3 bg-subtle/20 border-b border-line-struct/50">
                          <div>
                            <p className="font-mono text-sm font-bold text-txt-body tracking-widest">{cita.folio}</p>
                            <p className="text-[10px] text-txt-muted mt-0.5">Identificador único de encuentro clínico</p>
                          </div>
                          <div className="flex items-center gap-1.5 shrink-0">
                            {cita.origenCanal === "PORTAL" ? (
                              <Badge variant="info" className="text-xs gap-1">
                                <Globe className="size-3" /> En línea
                              </Badge>
                            ) : null}
                            <Badge variant={ESTATUS_VARIANT[cita.estatus]} className="text-xs">
                              {ESTATUS_LABEL[cita.estatus]}
                            </Badge>
                          </div>
                        </div>
                        <div className="px-5 py-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                          <div>
                            <p className="text-[10px] font-semibold uppercase tracking-wide text-txt-muted mb-0.5">Fecha y hora</p>
                            <p className="text-sm font-semibold text-txt-body">{formatCitaFechaHora(cita.fechaHora)}</p>
                            <p className="text-xs text-txt-muted">{cita.duracionMin} min</p>
                          </div>
                          <div>
                            <p className="text-[10px] font-semibold uppercase tracking-wide text-txt-muted mb-0.5">Prestador del servicio</p>
                            <p className="text-sm font-semibold text-txt-body">{cita.medicoNombre}</p>
                            <p className="text-xs text-txt-muted capitalize">{cita.servicioTipo.replace("_", " ")}</p>
                          </div>
                          {cita.consultorioNombre ? (
                            <div>
                              <p className="text-[10px] font-semibold uppercase tracking-wide text-txt-muted mb-0.5">Unidad de atención</p>
                              <p className="text-sm font-semibold text-txt-body">{cita.consultorioNombre}</p>
                            </div>
                          ) : null}
                          {cita.motivo ? (
                            <div className="sm:col-span-2 lg:col-span-3">
                              <p className="text-[10px] font-semibold uppercase tracking-wide text-txt-muted mb-0.5">Motivo de consulta</p>
                              <p className="text-sm text-txt-body">{cita.motivo}</p>
                            </div>
                          ) : null}
                        </div>
                        <div className="px-5 py-2 border-t border-line-struct/40 bg-subtle/10 flex flex-wrap items-center justify-between gap-2">
                          <p className="text-[10px] text-txt-muted">
                            <span className="font-semibold">Registro:</span> {formatCitaFechaHora(cita.createdAt)}
                          </p>
                          <p className="text-[10px] font-mono text-txt-muted/70">Folio: {cita.folio}</p>
                        </div>
                        <CitaMovimientos citaId={cita.id} />
                      </article>
                    </div>
                  );
                })}
              </div>
            )
          ) : null}

          {/* ─ Tab: Visitas y movimientos ──────────────────────── */}
          {histTab === "visitas" ? (
            histVisitsLoading ? (
              <div className="flex items-center gap-2 text-sm text-txt-muted py-4">
                <Loader2 className="size-4 animate-spin" /> Cargando visitas...
              </div>
            ) : histVisits.length === 0 ? (
              <div className="rounded-xl border border-line-struct bg-paper py-12 text-center">
                <FileText className="size-10 text-txt-muted/30 mx-auto mb-3" />
                <p className="text-sm text-txt-muted">Sin visitas registradas para este paciente.</p>
                <p className="text-xs text-txt-muted/70 mt-1">Las visitas se generan en el módulo de check-in.</p>
              </div>
            ) : (
              <div className="relative pl-5 border-l-2 border-line-struct/60 space-y-4">
                {histVisits.map((visit) => (
                  <div key={visit.id} className="relative">
                    <div className={[
                      "absolute -left-[25px] top-4 size-3 rounded-full border-2 border-paper",
                      visit.status === "cerrada"  ? "bg-green-500" :
                      visit.status === "cancelada" || visit.status === "no_show" ? "bg-red-400" :
                      visit.status === "en_consulta" ? "bg-blue-500" :
                      "bg-txt-muted/40",
                    ].join(" ")} />
                    <HistVisitCard visit={visit} />
                  </div>
                ))}
              </div>
            )
          ) : null}

        </div>
      ) : histEnabled && !histPatient ? (
        <div className="rounded-xl border border-line-struct bg-paper py-12 text-center">
          <p className="text-sm text-txt-muted">Expediente no encontrado en el sistema.</p>
        </div>
      ) : null}

    </div>
  );
}
