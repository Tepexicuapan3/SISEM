import { CheckCircle2 } from "lucide-react";
import { usePrintDocument } from "@shared/hooks/usePrintDocument";
import { useDoctorAttendedToday } from "@features/consulta-medica/modules/atencion/queries/useDoctorAttendedToday";
import { AttendedTodayList } from "./AttendedTodayList";

interface AttendedTodayPanelProps {
  canPrint: boolean;
}

/**
 * Atendidas hoy: la consulta cerrada sale de la cola, pero el medico la sigue
 * viendo aqui e imprime la receta cuando quede lista (NOM-024: disponibilidad).
 */
export function AttendedTodayPanel({ canPrint }: AttendedTodayPanelProps) {
  const { data, isLoading, isError } = useDoctorAttendedToday();
  const { print, isPrinting } = usePrintDocument("receta");

  return (
    <section className="space-y-3" aria-labelledby="attended-today-title" data-testid="attended-today-panel">
      <h2 id="attended-today-title" className="flex items-center gap-2 text-sm font-semibold text-txt-body">
        <CheckCircle2 className="size-4 text-brand" />
        Atendidas hoy{data ? ` (${data.total})` : ""}
      </h2>
      {isLoading ? <p className="text-sm text-txt-muted">Cargando consultas de hoy...</p> : null}
      {isError ? <p className="text-sm text-status-alert">No se pudieron cargar las consultas de hoy.</p> : null}
      {data ? (
        <AttendedTodayList
          items={data.items}
          canPrint={canPrint}
          isPrinting={isPrinting}
          onPrint={(visitId) => void print(visitId)}
        />
      ) : null}
    </section>
  );
}
