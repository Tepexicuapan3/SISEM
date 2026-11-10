import { useState } from "react";
import { toast } from "sonner";
import { Clock } from "lucide-react";
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
import { ApiError } from "@api/utils/errors";
import type { SeguimientoPendienteItem } from "@api/types";
import { useMedicosDisponibles } from "@features/admin/modules/medicos/hooks/useMedicos";
import { useSlotsMedico } from "@features/recepcion/modules/adscripcion/queries/useAdscripcionQueries";
import { useAgendarSeguimiento } from "@features/recepcion/modules/citas/mutations/useCitaMutations";

const fechaLocal = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

interface Props {
  seguimiento:  SeguimientoPendienteItem | null;
  onOpenChange: (open: boolean) => void;
}

/**
 * Agendar la cita del seguimiento que indicó el médico: médico disponible del
 * centro, fecha (la indicada si no pasó) y horario libre. El backend valida
 * las reglas de una cita nueva (consultorio familiar incluido) y la enlaza a
 * la consulta, así sale de "Seguimientos por agendar".
 */
export function AgendarSeguimientoDialog({ seguimiento, onOpenChange }: Props) {
  if (!seguimiento) return null;
  // `key`: al abrir otro seguimiento el formulario arranca de cero.
  return <AgendarSeguimientoForm key={seguimiento.visitId} seguimiento={seguimiento} onOpenChange={onOpenChange} />;
}

function AgendarSeguimientoForm({
  seguimiento,
  onOpenChange,
}: {
  seguimiento:  SeguimientoPendienteItem;
  onOpenChange: (open: boolean) => void;
}) {
  const hoy = fechaLocal(new Date());
  const [fecha, setFecha] = useState(() => (seguimiento.fechaSeguimiento >= hoy ? seguimiento.fechaSeguimiento : hoy));
  const [medicoId, setMedicoId] = useState<number | null>(null);
  const [hora, setHora] = useState<string | null>(null);

  const agendar = useAgendarSeguimiento();
  const { data: disponibles, isFetching: cargandoMedicos } = useMedicosDisponibles(
    seguimiento.centroId ?? undefined,
    fecha,
  );
  const { data: slotsData, isFetching: cargandoSlots } = useSlotsMedico(medicoId, fecha);
  const medicos = (disponibles?.medicos ?? []).filter((m) => m.disponible);
  const medico = medicos.find((m) => m.medicoId === medicoId);
  const slots = slotsData?.slots ?? [];

  const confirmar = async () => {
    if (!medico || !hora) return;
    try {
      const cita = await agendar.mutateAsync({
        idPaciente: seguimiento.idPaciente,
        noExp: seguimiento.noExp,
        pkNum: seguimiento.pkNum,
        medicoId: medico.medicoId,
        consultorioId: medico.consultorioId,
        fechaHora: `${fecha}T${hora}`,
        servicioTipo: seguimiento.serviceType,
        seguimientoVisitId: seguimiento.visitId,
      });
      toast.success("Cita de seguimiento agendada", { description: `${fecha} a las ${hora} · folio ${cita.folio}.` });
      onOpenChange(false);
    } catch (error) {
      toast.error("No se pudo agendar", {
        description: error instanceof ApiError ? error.message : "Intente nuevamente.",
      });
    }
  };

  return (
    <Dialog open onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Agendar seguimiento</DialogTitle>
          <DialogDescription>
            {seguimiento.pacienteNombre || `Exp. ${seguimiento.noExp}`} · indicado para el{" "}
            {seguimiento.fechaSeguimiento} por {seguimiento.medicoNombre}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div className="space-y-1">
            <Label htmlFor="seguimiento-fecha" className="text-xs">Fecha</Label>
            <Input
              id="seguimiento-fecha"
              type="date"
              value={fecha}
              min={hoy}
              onChange={(e) => {
                setFecha(e.target.value);
                setMedicoId(null);
                setHora(null);
              }}
              className="h-9"
            />
          </div>

          <div role="radiogroup" aria-label="Médico" className="space-y-1.5">
            {cargandoMedicos ? (
              <p className="text-sm text-txt-muted">Cargando médicos...</p>
            ) : medicos.length === 0 ? (
              <p className="text-sm text-txt-muted italic">Sin médicos disponibles en el centro esa fecha.</p>
            ) : (
              medicos.map((m) => (
                <button
                  key={m.medicoId}
                  type="button"
                  role="radio"
                  aria-checked={medicoId === m.medicoId}
                  aria-label={m.nombreCompleto}
                  onClick={() => {
                    setMedicoId(m.medicoId);
                    setHora(null);
                  }}
                  className={[
                    "w-full rounded-xl border px-3 py-2 text-left text-sm transition-colors",
                    medicoId === m.medicoId ? "border-primary bg-primary/5" : "border-line-struct hover:bg-subtle/40",
                  ].join(" ")}
                >
                  {m.nombreCompleto}
                  {m.consultorioNombre ? <span className="ml-1 text-xs text-txt-muted">· {m.consultorioNombre}</span> : null}
                </button>
              ))
            )}
          </div>

          {medicoId != null ? (
            <div role="radiogroup" aria-label="Horario" className="flex flex-wrap gap-1.5">
              {cargandoSlots ? (
                <p className="text-sm text-txt-muted">Buscando horarios...</p>
              ) : slots.length === 0 ? (
                <p className="text-sm text-txt-muted italic">Sin horarios libres ese día.</p>
              ) : (
                slots.map((slot) => (
                  <button
                    key={slot.hora}
                    type="button"
                    role="radio"
                    aria-checked={hora === slot.hora}
                    aria-label={slot.hora}
                    onClick={() => setHora(slot.hora)}
                    className={[
                      "flex items-center gap-1 rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-colors",
                      hora === slot.hora ? "border-primary bg-primary text-txt-inverse" : "border-line-struct hover:bg-primary/5",
                    ].join(" ")}
                  >
                    <Clock className="size-3" />
                    {slot.hora}
                  </button>
                ))
              )}
            </div>
          ) : null}
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Cerrar
          </Button>
          <Button type="button" onClick={() => void confirmar()} disabled={agendar.isPending || !medico || !hora}>
            Agendar cita
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
