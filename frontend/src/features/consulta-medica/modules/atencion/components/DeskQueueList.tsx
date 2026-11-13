import { AlarmClock, ChevronRight } from "lucide-react";
import { VISIT_STATUS, type VisitQueueItem } from "@api/types";
import { cn } from "@shared/utils/styling/cn";
import { AppointmentAlertBadge, ConsultationElapsedBadge } from "./ConsultationBadges";
import { formatArrivalTypeLabel, getMinutesUntilAppointment } from "../pages/DoctorConsultationPage.helpers";

type Urgency = "attending" | "now" | "soon" | "later";

/** Misma escala que AppointmentAlertBadge: "¡Ahora!" a ±5 min, aviso a 15. */
function urgencyOf(visit: VisitQueueItem, minutesUntil: number | null): Urgency {
  if (visit.status === VISIT_STATUS.EN_CONSULTA) return "attending";
  if (minutesUntil !== null && minutesUntil >= -30 && minutesUntil <= 5) return "now";
  if (minutesUntil !== null && minutesUntil <= 15 && minutesUntil > 5) return "soon";
  return "later";
}

const ACCENT: Record<Urgency, string> = {
  attending: "before:bg-brand",
  now: "before:bg-status-critical",
  soon: "before:bg-status-alert",
  later: "before:bg-line-struct",
};

/** En consulta primero; luego por hora de cita (sin hora al final). */
function sortForDesk(visits: VisitQueueItem[]): VisitQueueItem[] {
  const rank = (visit: VisitQueueItem) => (visit.status === VISIT_STATUS.EN_CONSULTA ? 0 : 1);
  return [...visits].sort(
    (a, b) => rank(a) - rank(b) || (a.horaConsulta ?? "99:99").localeCompare(b.horaConsulta ?? "99:99"),
  );
}

interface DeskQueueListProps {
  visits:                         VisitQueueItem[];
  now:                            Date;
  consultationStartedAtByVisitId: Record<number, Date>;
  selectedVisitId:                number | null;
  onSelectVisit:                  (visitId: number) => void;
}

/** Cola de Mi consultorio: barra de color por urgencia y el paciente abierto marcado. */
export function DeskQueueList({
  visits,
  now,
  consultationStartedAtByVisitId,
  selectedVisitId,
  onSelectVisit,
}: DeskQueueListProps) {
  return (
    <ul className="space-y-2">
      {sortForDesk(visits).map((visit) => {
        const isSelected = visit.id === selectedVisitId;
        const minutesUntil = getMinutesUntilAppointment(visit.horaConsulta, now);
        const urgency = urgencyOf(visit, minutesUntil);
        return (
          <li key={visit.id}>
            <button
              type="button"
              data-testid={`doctor-visit-card-${visit.id}`}
              data-visit-folio={visit.folio}
              data-urgency={urgency}
              aria-current={isSelected ? "true" : undefined}
              onClick={() => onSelectVisit(visit.id)}
              className={cn(
                "group relative w-full overflow-hidden rounded-lg border bg-paper py-2.5 pr-3 pl-4 text-left transition",
                "before:absolute before:inset-y-0 before:left-0 before:w-1",
                "hover:border-brand/50 focus-visible:ring-2 focus-visible:ring-brand/40 focus-visible:outline-none",
                ACCENT[urgency],
                isSelected ? "border-brand bg-brand/5 shadow-sm" : "border-line-hairline",
              )}
            >
              <div className="flex items-start justify-between gap-2">
                <p data-testid="desk-queue-name" className="min-w-0 truncate text-sm font-semibold text-txt-body">
                  {visit.nombrePaciente || `Exp. ${visit.noExp}`}
                </p>
                {visit.horaConsulta ? (
                  <span className="shrink-0 font-mono text-base leading-none font-bold text-txt-body tabular-nums">
                    {visit.horaConsulta}
                  </span>
                ) : null}
              </div>
              <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                {urgency === "attending" ? (
                  <ConsultationElapsedBadge startedAt={consultationStartedAtByVisitId[visit.id]} now={now} />
                ) : (
                  <AppointmentAlertBadge minutesUntil={minutesUntil} />
                )}
                <span className="truncate text-xs text-txt-muted">
                  Exp. {visit.noExp} · {formatArrivalTypeLabel(visit.arrivalType)}
                </span>
              </div>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

interface NextAppointmentNoticeProps {
  visit:        VisitQueueItem;
  minutesUntil: number;
  onOpen:       (visitId: number) => void;
}

/** Proxima cita (<= 15 min), compacta y con un clic para abrir al paciente. */
export function NextAppointmentNotice({ visit, minutesUntil, onOpen }: NextAppointmentNoticeProps) {
  const isNow = minutesUntil <= 5;
  const when =
    minutesUntil <= 0
      ? `empezó hace ${Math.abs(minutesUntil)} min`
      : `en ${minutesUntil} min`;
  return (
    <button
      type="button"
      onClick={() => onOpen(visit.id)}
      className={cn(
        "flex w-full items-center gap-2.5 rounded-lg border px-3 py-2 text-left transition hover:shadow-sm",
        "focus-visible:ring-2 focus-visible:ring-brand/40 focus-visible:outline-none",
        isNow ? "border-status-critical/40 bg-status-critical/10" : "border-status-alert/40 bg-status-alert/10",
      )}
    >
      <AlarmClock className={cn("size-4 shrink-0", isNow ? "animate-pulse text-status-critical" : "text-status-alert")} />
      <span className="min-w-0 flex-1">
        <span className={cn("block text-xs font-semibold", isNow ? "text-status-critical" : "text-status-alert")}>
          Próxima cita {when}
        </span>
        <span className="block truncate text-sm font-medium text-txt-body">
          {visit.nombrePaciente || `Exp. ${visit.noExp}`}
        </span>
      </span>
      <ChevronRight className="size-4 shrink-0 text-txt-muted" />
    </button>
  );
}
