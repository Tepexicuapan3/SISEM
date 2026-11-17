import { useState } from "react";
import { toast } from "sonner";
import { CalendarCheck, CheckCircle2, Clock } from "lucide-react";
import { Button } from "@shared/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@shared/ui/dialog";
import { Input } from "@shared/ui/input";
import { Label } from "@shared/ui/label";
import { Textarea } from "@shared/ui/textarea";
import { ApiError } from "@api/utils/errors";
import { visitsAPI } from "@api/resources/visits.api";
import type { PatientMember, VisitService } from "@api/types";
import { useDebounce } from "@shared/hooks/useDebounce";
import { PatientMemberCard } from "@features/recepcion/shared/components/PatientMemberCard";
import { resolveParentesco } from "@features/recepcion/shared/utils/recepcion-format";
import { usePatientLookup } from "@features/recepcion/modules/checkin/queries/usePatientLookup";
import { useAgendarCita } from "@features/recepcion/modules/citas/mutations/useCitaMutations";
import { ConflictoConsultorioAviso } from "@features/recepcion/modules/adscripcion/components/ConflictoConsultorioAviso";
import { useAdscripcionPermisos } from "@features/recepcion/modules/adscripcion/queries/useAdscripcionPermisos";
import {
  conflictoConsultorioFamiliar,
  type ConflictoConsultorioFamiliar,
} from "@features/recepcion/modules/adscripcion/domain/adscripcionEstado";

/** Horario libre elegido en Disponibilidad (medicoId: No. Médico, espacio de la agenda). */
export interface SlotParaCita {
  medicoId:       number;
  medicoNombre?:  string;
  consultorioId?: number;
  fecha:          string; // YYYY-MM-DD
  hora:           string; // HH:mm
}

interface Props {
  slot:         SlotParaCita | null;
  onOpenChange: (open: boolean) => void;
  canWrite:     boolean;
}

/**
 * Agendar una cita en un horario libre de otro día. La ficha es solo para el
 * paciente que está hoy en la sala; para otro día va una cita, y el día de la
 * cita el sistema genera su ficha automática. El backend valida las reglas de
 * una cita nueva (topes, horario libre, consultorio familiar).
 */
export function AgendarCitaDialog({ slot, onOpenChange, canWrite }: Props) {
  if (!slot) return null;
  // `key`: al abrir otro horario el formulario arranca de cero.
  return (
    <AgendarCitaForm
      key={`${slot.medicoId}-${slot.fecha}-${slot.hora}`}
      slot={slot}
      onOpenChange={onOpenChange}
      canWrite={canWrite}
    />
  );
}

function AgendarCitaForm({ slot, onOpenChange, canWrite }: Props & { slot: SlotParaCita }) {
  const [noExp, setNoExp] = useState("");
  const [elegido, setElegido] = useState<PatientMember | null>(null);
  const [servicio, setServicio] = useState<VisitService>("medicina_general");
  const [motivo, setMotivo] = useState("");
  const [conflicto, setConflicto] = useState<ConflictoConsultorioFamiliar | null>(null);

  const agendar = useAgendarCita();
  const permisosAdscripcion = useAdscripcionPermisos();
  const debouncedNoExp = useDebounce(noExp, 400);
  const { data: lookup, isFetching: buscando, isError: lookupFallo } = usePatientLookup(debouncedNoExp);
  const miembros: PatientMember[] = lookup
    ? [...(lookup.titular ? [lookup.titular] : []), ...lookup.dependientes]
    : [];
  const paciente = elegido ?? (miembros.length === 1 ? miembros[0] : null);

  const fechaLarga = new Date(`${slot.fecha}T00:00:00`).toLocaleDateString("es-MX", {
    weekday: "long", day: "2-digit", month: "long",
  });

  const confirmar = async (excepcionConsultorioFamiliar?: string) => {
    if (!paciente || !canWrite) return;
    try {
      // El miembro que nunca se atendió todavía no tiene idPaciente: se abre primero.
      const idPaciente =
        paciente.idPaciente ?? (await visitsAPI.openPatient(paciente.noExp, paciente.pkNum)).idPaciente;
      const motivoLimpio = motivo.trim();
      const cita = await agendar.mutateAsync({
        idPaciente,
        noExp: paciente.noExp,
        pkNum: paciente.pkNum,
        medicoId: slot.medicoId,
        ...(slot.consultorioId ? { consultorioId: slot.consultorioId } : {}),
        fechaHora: `${slot.fecha}T${slot.hora}`,
        servicioTipo: servicio,
        ...(motivoLimpio ? { motivo: motivoLimpio } : {}),
        ...(excepcionConsultorioFamiliar ? { excepcionConsultorioFamiliar } : {}),
      });
      toast.success("Cita agendada", {
        description: `${paciente.nombre} · ${fechaLarga} a las ${slot.hora} · folio ${cita.folio}. Ese día se genera su ficha sola.`,
      });
      onOpenChange(false);
    } catch (error) {
      // P-03: otro consultorio que el familiar → recepción decide con excepción.
      const conflictoP03 = conflictoConsultorioFamiliar(error);
      if (conflictoP03) {
        setConflicto(conflictoP03);
        return;
      }
      toast.error("No se pudo agendar la cita", {
        description: error instanceof ApiError ? error.message : "Intenta nuevamente.",
      });
    }
  };

  return (
    <Dialog open onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Agendar cita</DialogTitle>
          <DialogDescription>
            Es otro día: se agenda una cita y ese día se genera la ficha del paciente.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="rounded-xl border border-primary/30 bg-primary/5 px-4 py-3">
            <div className="flex items-center gap-2 text-sm font-semibold text-txt-body">
              <CalendarCheck className="size-4 shrink-0 text-primary" />
              <span className="capitalize">{fechaLarga}</span>
              <span className="flex items-center gap-1 font-mono">
                <Clock className="size-3" />
                {slot.hora}
              </span>
            </div>
            {slot.medicoNombre ? (
              <p className="mt-0.5 pl-6 text-xs text-txt-muted">{slot.medicoNombre}</p>
            ) : null}
          </div>

          <div className="space-y-2">
            <Label htmlFor="cita-noExp">Número de expediente</Label>
            <Input
              id="cita-noExp"
              placeholder="Ej. 12345"
              value={noExp}
              onChange={(e) => {
                setNoExp(e.target.value);
                setElegido(null);
                setConflicto(null);
              }}
              disabled={!canWrite || agendar.isPending}
            />
          </div>

          {debouncedNoExp.trim().length > 0 ? (
            <div className="space-y-1.5">
              {buscando ? (
                <p className="text-sm text-txt-muted">Buscando expediente...</p>
              ) : lookupFallo || miembros.length === 0 ? (
                <p className="text-sm text-status-critical">
                  {lookupFallo ? "Sin derecho al servicio o expediente no encontrado." : "Sin miembros activos."}
                </p>
              ) : paciente ? (
                <div className="flex items-start gap-3 rounded-xl border-2 border-primary bg-primary/5 px-4 py-3">
                  <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-primary" />
                  <div className="min-w-0 flex-1">
                    <p className="text-[11px] font-semibold tracking-wide text-primary uppercase">La cita es para</p>
                    <p className="text-base font-bold text-txt-body">{paciente.nombre}</p>
                    <p className="text-xs text-txt-muted">
                      {resolveParentesco(paciente.parentesco)}
                      {paciente.edad != null ? ` · ${paciente.edad} años` : ""}
                      {" · Exp. "}{paciente.noExp}
                    </p>
                  </div>
                  {miembros.length > 1 ? (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      disabled={agendar.isPending}
                      onClick={() => {
                        setElegido(null);
                        setConflicto(null);
                      }}
                    >
                      Cambiar
                    </Button>
                  ) : null}
                </div>
              ) : (
                <>
                  <p className="text-xs text-txt-muted">Elige a quién se le agenda la cita:</p>
                  {miembros.map((m) => (
                    <PatientMemberCard
                      key={`${m.noExp}-${m.pkNum}`}
                      member={m}
                      selected={false}
                      onSelect={() => setElegido(m)}
                    />
                  ))}
                </>
              )}
            </div>
          ) : null}

          <div className="space-y-1">
            <Label htmlFor="cita-servicio" className="text-xs">Servicio</Label>
            <select
              id="cita-servicio"
              className="h-9 w-full rounded-md border border-line-struct bg-paper px-3 text-sm"
              value={servicio}
              disabled={!canWrite || agendar.isPending}
              onChange={(e) => {
                setServicio(e.target.value as VisitService);
                setConflicto(null);
              }}
            >
              <option value="medicina_general">Medicina general</option>
              <option value="especialidad">Especialidad</option>
            </select>
          </div>

          <div className="space-y-1">
            <Label htmlFor="cita-motivo" className="text-xs">Motivo</Label>
            <Textarea
              id="cita-motivo"
              rows={2}
              maxLength={255}
              value={motivo}
              disabled={!canWrite || agendar.isPending}
              onChange={(e) => setMotivo(e.target.value)}
              placeholder="Opcional"
            />
          </div>

          {conflicto ? (
            <ConflictoConsultorioAviso
              conflicto={conflicto}
              puedeReasignar={false}
              puedeExcepcion={permisosAdscripcion.puedeExcepcion}
              enviando={agendar.isPending}
              onReasignar={() => undefined}
              onExcepcion={(motivoExcepcion) => void confirmar(motivoExcepcion)}
            />
          ) : null}

          {!canWrite ? (
            <p className="text-sm text-txt-muted" role="status">
              No tienes permiso para agendar citas.
            </p>
          ) : null}
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Cerrar
          </Button>
          <Button
            type="button"
            disabled={!canWrite || !paciente || agendar.isPending || conflicto !== null}
            onClick={() => void confirmar()}
          >
            Agendar cita
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
