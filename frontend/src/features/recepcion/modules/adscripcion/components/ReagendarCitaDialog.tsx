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
import type { CitaAfectada } from "@api/types";
import { useMedicosDisponibles } from "@features/admin/modules/medicos/hooks/useMedicos";
import { useSlotsMedico } from "@features/recepcion/modules/adscripcion/queries/useAdscripcionQueries";
import { useReagendarCita } from "@features/recepcion/modules/adscripcion/mutations/useAdscripcionMutations";

const fechaLocal = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

/** La fecha de la cita cancelada si todavía no pasó; si no, hoy. */
const fechaInicial = (afectada: CitaAfectada) => {
  const hoy = fechaLocal(new Date());
  const original = fechaLocal(new Date(afectada.citaCancelada.fechaHora));
  return original >= hoy ? original : hoy;
};

interface ReagendarCitaDialogProps {
  afectada: CitaAfectada | null;
  onOpenChange: (open: boolean) => void;
}

/**
 * P-03 · Reagendar en el consultorio nuevo una cita cancelada por el cambio:
 * solo médicos de ese consultorio y horarios libres; la cita nueva queda
 * ligada a la cancelada.
 */
export const ReagendarCitaDialog = ({ afectada, onOpenChange }: ReagendarCitaDialogProps) => {
  const [fecha, setFecha] = useState(() => (afectada ? fechaInicial(afectada) : fechaLocal(new Date())));
  const [medicoId, setMedicoId] = useState<number | null>(null);
  const [hora, setHora] = useState<string | null>(null);

  const reagendar = useReagendarCita();
  const { data: disponibles, isFetching: cargandoMedicos } = useMedicosDisponibles(
    afectada?.idCentroAtencion,
    fecha,
    afectada != null,
  );
  const { data: slotsData, isFetching: cargandoSlots } = useSlotsMedico(medicoId, fecha);

  const medicos = (disponibles?.medicos ?? []).filter(
    (m) => m.consultorioId === afectada?.idConsultorioNuevo,
  );
  const slots = slotsData?.slots ?? [];

  const confirmar = async () => {
    if (!afectada || medicoId == null || !hora) return;
    try {
      await reagendar.mutateAsync({
        idPaciente: afectada.idPaciente,
        medicoId,
        consultorioId: afectada.idConsultorioNuevo,
        fechaHora: `${fecha}T${hora}`,
        servicioTipo: "medicina_general",
        idCitaAfectada: afectada.idCitaAfectada,
      });
      toast.success("Cita reagendada", { description: `${fecha} a las ${hora} en ${afectada.consultorioNuevo}.` });
      onOpenChange(false);
    } catch (error) {
      toast.error("No se pudo reagendar", {
        description: error instanceof ApiError ? error.message : "Intente nuevamente.",
      });
    }
  };

  return (
    <Dialog open={afectada != null} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Reagendar cita</DialogTitle>
          <DialogDescription>
            {afectada ? `En ${afectada.consultorioNuevo} · antes folio ${afectada.citaCancelada.folio}` : null}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div className="space-y-1">
            <Label htmlFor="reagendar-fecha" className="text-xs">Fecha</Label>
            <Input
              id="reagendar-fecha"
              type="date"
              value={fecha}
              min={fechaLocal(new Date())}
              onChange={(e) => {
                setFecha(e.target.value);
                setHora(null);
              }}
              className="h-9"
            />
          </div>

          <div role="radiogroup" aria-label="Médico" className="space-y-1.5">
            {cargandoMedicos ? (
              <p className="text-sm text-txt-muted">Cargando médicos...</p>
            ) : medicos.length === 0 ? (
              <p className="text-sm text-txt-muted italic">Sin médicos del consultorio nuevo para esa fecha.</p>
            ) : (
              medicos.map((medico) => (
                <button
                  key={medico.medicoId}
                  type="button"
                  role="radio"
                  aria-checked={medicoId === medico.medicoId}
                  aria-label={medico.nombreCompleto}
                  onClick={() => {
                    setMedicoId(medico.medicoId);
                    setHora(null);
                  }}
                  className={[
                    "w-full rounded-xl border px-3 py-2 text-left text-sm transition-colors",
                    medicoId === medico.medicoId ? "border-primary bg-primary/5" : "border-line-struct hover:bg-subtle/40",
                  ].join(" ")}
                >
                  {medico.nombreCompleto}
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
            Cancelar
          </Button>
          <Button
            type="button"
            onClick={() => void confirmar()}
            disabled={reagendar.isPending || medicoId == null || !hora}
          >
            Reagendar cita
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
