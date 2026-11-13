import { VISIT_STATUS, type VisitQueueItem } from "@api/types";
import { cn } from "@shared/utils/styling/cn";
import { AppointmentAlertBadge, ConsultationElapsedBadge } from "./ConsultationBadges";
import { getMinutesUntilAppointment } from "../pages/DoctorConsultationPage.helpers";

interface DeskQueueListProps {
  visits:                         VisitQueueItem[];
  now:                            Date;
  consultationStartedAtByVisitId: Record<number, Date>;
  selectedVisitId:                number | null;
  onSelectVisit:                  (visitId: number) => void;
}

/** Cola compacta de Mi consultorio: un renglon por paciente, el abierto marcado. */
export function DeskQueueList({
  visits,
  now,
  consultationStartedAtByVisitId,
  selectedVisitId,
  onSelectVisit,
}: DeskQueueListProps) {
  return (
    <ul className="space-y-1.5">
      {visits.map((visit) => {
        const isSelected = visit.id === selectedVisitId;
        const minutesUntil = getMinutesUntilAppointment(visit.horaConsulta, now);
        return (
          <li key={visit.id}>
            <button
              type="button"
              data-testid={`doctor-visit-card-${visit.id}`}
              data-visit-folio={visit.folio}
              aria-current={isSelected ? "true" : undefined}
              onClick={() => onSelectVisit(visit.id)}
              className={cn(
                "w-full rounded-lg border px-3 py-2 text-left transition hover:border-brand/50",
                isSelected ? "border-brand bg-brand/5" : "border-line-hairline bg-paper",
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <p className="truncate text-sm font-semibold text-txt-body">
                  {visit.nombrePaciente || `Exp. ${visit.noExp}`}
                </p>
                {visit.horaConsulta ? (
                  <span className="shrink-0 font-mono text-xs font-semibold text-primary">{visit.horaConsulta}</span>
                ) : null}
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-1.5">
                <span className="font-mono text-xs text-txt-muted">{visit.folio}</span>
                {visit.status === VISIT_STATUS.EN_CONSULTA ? (
                  <ConsultationElapsedBadge startedAt={consultationStartedAtByVisitId[visit.id]} now={now} />
                ) : (
                  <AppointmentAlertBadge minutesUntil={minutesUntil} />
                )}
              </div>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
