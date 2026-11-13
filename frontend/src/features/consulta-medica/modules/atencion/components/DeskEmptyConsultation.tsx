import { ArrowRight, Stethoscope } from "lucide-react";
import { VISIT_STATUS, type VisitQueueItem } from "@api/types";
import { Button } from "@shared/ui/button";

interface DeskEmptyConsultationProps {
  /** Siguiente paciente sugerido; null si la cola esta vacia. */
  nextVisit: VisitQueueItem | null;
  onOpen:    (visitId: number) => void;
}

/** Centro de Mi consultorio sin paciente abierto: el siguiente queda a un clic. */
export function DeskEmptyConsultation({ nextVisit, onOpen }: DeskEmptyConsultationProps) {
  const name = nextVisit ? nextVisit.nombrePaciente || `Exp. ${nextVisit.noExp}` : null;
  const isResume = nextVisit?.status === VISIT_STATUS.EN_CONSULTA;

  return (
    <div className="flex min-h-80 flex-col items-center justify-center gap-4 rounded-xl border border-dashed border-line-struct bg-paper p-8 text-center">
      <span className="flex size-12 items-center justify-center rounded-full bg-brand/10 text-brand">
        <Stethoscope className="size-6" />
      </span>
      <div className="space-y-1">
        <p className="text-base font-semibold text-txt-body">Ningún paciente abierto</p>
        <p className="max-w-sm text-sm text-txt-muted">
          Elegí un paciente de Por atender para empezar la consulta.
        </p>
      </div>
      {nextVisit && name ? (
        <Button type="button" onClick={() => onOpen(nextVisit.id)}>
          {isResume ? `Continuar con ${name}` : `Atender a ${name}`}
          <ArrowRight className="size-4" />
        </Button>
      ) : null}
    </div>
  );
}
