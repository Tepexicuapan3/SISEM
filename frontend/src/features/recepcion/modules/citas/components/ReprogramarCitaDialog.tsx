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
import { useSlotsMedico } from "@features/recepcion/modules/adscripcion/queries/useAdscripcionQueries";
import { useReprogramarCita } from "@features/recepcion/modules/citas/mutations/useCitaMutations";

export interface CitaAReprogramar {
  id:       number;
  folio:    string;
  noExp:    string;
  fecha:    string;  // YYYY-MM-DD
  hora:     string;  // HH:mm
  medicoId: number;
}

const fechaLocal = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

interface ReprogramarCitaDialogProps {
  cita:         CitaAReprogramar | null;
  onOpenChange: (open: boolean) => void;
}

/**
 * Reprogramar desde la agenda de recepción: mismo médico, otra fecha u
 * horario libre. El backend cancela la cita ("Reagendada") y agenda la nueva
 * enlazada en un solo paso; si la nueva no se puede, la anterior queda igual.
 */
export function ReprogramarCitaDialog({ cita, onOpenChange }: ReprogramarCitaDialogProps) {
  if (!cita) return null;
  // `key`: al abrir otra cita el formulario arranca de cero.
  return <ReprogramarCitaForm key={cita.id} cita={cita} onOpenChange={onOpenChange} />;
}

function ReprogramarCitaForm({ cita, onOpenChange }: { cita: CitaAReprogramar; onOpenChange: (open: boolean) => void }) {
  const hoy = fechaLocal(new Date());
  const [fecha, setFecha] = useState(() => (cita.fecha >= hoy ? cita.fecha : hoy));
  const [hora, setHora] = useState<string | null>(null);
  const [motivo, setMotivo] = useState("");

  const reprogramar = useReprogramarCita();
  const { data: slotsData, isFetching: cargandoSlots } = useSlotsMedico(cita.medicoId, fecha);
  const slots = slotsData?.slots ?? [];

  const confirmar = async () => {
    if (!hora) return;
    try {
      const nueva = await reprogramar.mutateAsync({
        id: cita.id,
        fechaHora: `${fecha}T${hora}`,
        motivoDetalle: motivo.trim() || undefined,
      });
      toast.success("Cita reprogramada", { description: `${fecha} a las ${hora} · folio ${nueva.folio}.` });
      onOpenChange(false);
    } catch (error) {
      toast.error("No se pudo reprogramar", {
        description: error instanceof ApiError ? error.message : "Intente nuevamente.",
      });
    }
  };

  return (
    <Dialog open onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Reprogramar cita</DialogTitle>
          <DialogDescription>
            {cita.folio} · Exp. {cita.noExp} · hoy el {cita.fecha} a las {cita.hora}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div className="space-y-1">
            <Label htmlFor="reprogramar-fecha" className="text-xs">Nueva fecha</Label>
            <Input
              id="reprogramar-fecha"
              type="date"
              value={fecha}
              min={hoy}
              onChange={(e) => {
                setFecha(e.target.value);
                setHora(null);
              }}
              className="h-9"
            />
          </div>

          <div role="radiogroup" aria-label="Horario" className="flex flex-wrap gap-1.5">
            {cargandoSlots ? (
              <p className="text-sm text-txt-muted">Buscando horarios...</p>
            ) : slots.length === 0 ? (
              <p className="text-sm text-txt-muted italic">Sin horarios libres del médico ese día.</p>
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

          <div className="space-y-1">
            <Label htmlFor="reprogramar-motivo" className="text-xs">Motivo (opcional)</Label>
            <Input
              id="reprogramar-motivo"
              value={motivo}
              maxLength={200}
              onChange={(e) => setMotivo(e.target.value)}
              placeholder="Ej. el paciente pidió otro día"
              className="h-9"
            />
          </div>
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Cerrar
          </Button>
          <Button type="button" onClick={() => void confirmar()} disabled={reprogramar.isPending || !hora}>
            Reprogramar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
