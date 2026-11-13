import {
  AlertTriangle,
  CalendarClock,
  CheckCircle2,
  Clock3,
  FileHeart,
  FileText,
  Printer,
  Send,
  XCircle,
  type LucideIcon,
} from "lucide-react";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import type { DoctorAttendedDocuments, DoctorAttendedItem, DoctorAttendedPrescription } from "@api/types";

interface AttendedTodayListProps {
  items: DoctorAttendedItem[];
  canPrint: boolean;
  onPrint: (visitId: number) => void;
  isPrinting?: boolean;
  canPrintNote?: boolean;
  onPrintNote?: (visitId: number) => void;
  /** "row": renglon ancho (vista Ventana). "card": tarjeta para la columna de Mi consultorio. */
  variant?: "row" | "card";
}

const timeOf = (iso: string | null): string => {
  if (!iso) return "";
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? ""
    : date.toLocaleTimeString("es-MX", { hour: "2-digit", minute: "2-digit", timeZone: "America/Mexico_City" });
};

const dateOf = (isoDate: string): string => {
  const date = new Date(`${isoDate}T12:00:00`);
  return Number.isNaN(date.getTime())
    ? isoDate
    : date.toLocaleDateString("es-MX", { day: "numeric", month: "short" });
};

const hasMedications = (prescription: DoctorAttendedPrescription | null): prescription is DoctorAttendedPrescription =>
  prescription !== null && prescription.medicationsCount > 0;

type PrescriptionTone = "none" | "pending" | "rejected" | "ready";

function prescriptionTone(prescription: DoctorAttendedPrescription | null): PrescriptionTone {
  if (!hasMedications(prescription)) return "none";
  if (prescription.authorization?.status === "pendiente") return "pending";
  if (prescription.authorization?.status === "rechazada") return "rejected";
  return "ready";
}

function PrescriptionState({ prescription }: { prescription: DoctorAttendedPrescription | null }) {
  const tone = prescriptionTone(prescription);
  if (tone === "none") {
    return <span className="text-xs text-txt-muted">Sin receta</span>;
  }
  if (tone === "pending") {
    return (
      <Badge variant="alert" className="text-xs">
        <Clock3 /> Pendiente de autorización
      </Badge>
    );
  }
  if (tone === "rejected") {
    const reason = prescription?.authorization?.rejectionReason;
    return (
      <span className="inline-flex flex-wrap items-center gap-1.5">
        <Badge variant="critical" className="text-xs">
          <XCircle /> Rechazada
        </Badge>
        {reason ? <span className="text-xs break-words text-txt-muted">{reason}</span> : null}
      </span>
    );
  }
  return (
    <Badge variant="stable" className="text-xs">
      <CheckCircle2 /> Lista para imprimir
    </Badge>
  );
}

interface DocumentChip {
  icon: LucideIcon;
  label: string;
}

function documentChips(documents: DoctorAttendedDocuments | undefined): DocumentChip[] {
  if (!documents) return [];
  const chips: DocumentChip[] = [];
  if (documents.medicalLeave) {
    chips.push({
      icon: FileHeart,
      label: `Incapacidad ${documents.medicalLeave.folio} · ${documents.medicalLeave.days} días`,
    });
  }
  for (const referral of documents.referrals) {
    chips.push({ icon: Send, label: `Pase ${referral.label ?? referral.type} ${referral.folio}` });
  }
  if (documents.followUpDate) {
    chips.push({ icon: CalendarClock, label: `Seguimiento ${dateOf(documents.followUpDate)}` });
  }
  return chips;
}

/** Incapacidad, pases y seguimiento: informativo, se consultan en el expediente. */
function OtherDocuments({ documents, className }: { documents: DoctorAttendedDocuments | undefined; className?: string }) {
  const chips = documentChips(documents);
  if (chips.length === 0) return null;
  return (
    <ul className={["flex flex-wrap gap-1.5", className].filter(Boolean).join(" ")} aria-label="Otros documentos">
      {chips.map(({ icon: Icon, label }) => (
        <li key={label} className="inline-flex items-center gap-1 rounded-md bg-subtle/50 px-1.5 py-0.5 text-xs text-txt-muted">
          <Icon className="size-3 shrink-0" aria-hidden />
          <span>{label}</span>
        </li>
      ))}
    </ul>
  );
}

/** Lo que requiere accion del medico, arriba de la lista. */
function PendingSummary({ items }: { items: DoctorAttendedItem[] }) {
  const pending = items.filter((item) => prescriptionTone(item.prescription) === "pending").length;
  const rejected = items.filter((item) => prescriptionTone(item.prescription) === "rejected").length;
  if (pending === 0 && rejected === 0) return null;
  const parts = [
    pending > 0 ? `${pending} por autorizar` : null,
    rejected > 0 ? `${rejected} ${rejected === 1 ? "rechazada" : "rechazadas"}` : null,
  ].filter(Boolean);
  return (
    <p
      role="status"
      className="flex items-start gap-2 rounded-lg border border-status-alert/40 bg-status-alert/10 px-3 py-2 text-xs text-txt-body"
    >
      <AlertTriangle className="mt-px size-3.5 shrink-0 text-status-alert" aria-hidden />
      <span>
        <span className="font-semibold">Recetas pendientes:</span> {parts.join(" · ")}
      </span>
    </p>
  );
}

interface ItemActionsProps {
  item: DoctorAttendedItem;
  canPrint: boolean;
  onPrint: (visitId: number) => void;
  isPrinting: boolean;
  canPrintNote: boolean;
  onPrintNote?: (visitId: number) => void;
  fullWidth?: boolean;
}

function ItemActions({ item, canPrint, onPrint, isPrinting, canPrintNote, onPrintNote, fullWidth = false }: ItemActionsProps) {
  const who = item.nombrePaciente || item.noExp;
  const showReceta = canPrint && item.prescription?.printable;
  const showNote = canPrintNote && onPrintNote && item.documents?.notePrintable;
  if (!showReceta && !showNote) return null;
  const width = fullWidth ? "flex-1" : undefined;
  return (
    <>
      {showReceta ? (
        <Button
          type="button"
          size="sm"
          variant={fullWidth ? "default" : "outline"}
          className={width}
          disabled={isPrinting}
          onClick={() => onPrint(item.visitId)}
          aria-label={`Imprimir receta de ${who}`}
        >
          <Printer className="size-3.5" /> {fullWidth ? "Receta" : "Imprimir receta"}
        </Button>
      ) : null}
      {showNote ? (
        <Button
          type="button"
          size="sm"
          variant={fullWidth ? "outline" : "ghost"}
          className={width}
          disabled={isPrinting}
          onClick={() => onPrintNote(item.visitId)}
          aria-label={`Imprimir nota de ${who}`}
        >
          <FileText className="size-3.5" /> Nota
        </Button>
      ) : null}
    </>
  );
}

const CARD_ACCENT: Record<PrescriptionTone, string> = {
  none: "before:bg-line-struct",
  ready: "before:bg-status-stable",
  pending: "before:bg-status-alert",
  rejected: "before:bg-status-critical",
};

/** Consultas que el medico cerro hoy, con el estado de su receta (Mi jornada). */
export function AttendedTodayList({
  items,
  canPrint,
  onPrint,
  isPrinting = false,
  canPrintNote = false,
  onPrintNote,
  variant = "row",
}: AttendedTodayListProps) {
  if (items.length === 0) {
    return <p className="text-sm text-txt-muted">Todavía no cerraste consultas hoy.</p>;
  }

  const actions = { canPrint, onPrint, isPrinting, canPrintNote, onPrintNote };

  if (variant === "card") {
    return (
      <div className="space-y-2">
        <PendingSummary items={items} />
        <ul className="space-y-2">
          {items.map((item) => {
            const { prescription } = item;
            return (
              <li
                key={item.visitId}
                className={[
                  "relative space-y-2 overflow-hidden rounded-lg border border-line-hairline bg-paper py-2.5 pr-3 pl-4",
                  "before:absolute before:inset-y-0 before:left-0 before:w-1",
                  CARD_ACCENT[prescriptionTone(prescription)],
                ].join(" ")}
              >
                <div className="flex items-baseline justify-between gap-2">
                  <p className="min-w-0 truncate text-sm font-semibold text-txt-body">
                    {item.nombrePaciente || `Exp. ${item.noExp}`}
                  </p>
                  <span className="shrink-0 font-mono text-xs text-txt-muted tabular-nums">{timeOf(item.attendedAt)}</span>
                </div>
                <p className="text-xs text-txt-muted">
                  Exp. {item.noExp}
                  {hasMedications(prescription) ? (
                    <>
                      {" · "}
                      <span className="font-mono">{prescription.folio}</span>
                      {prescription.hasControlled ? <span> (+ hoja de controlado)</span> : null}
                    </>
                  ) : null}
                </p>
                <PrescriptionState prescription={prescription} />
                <OtherDocuments documents={item.documents} />
                <div className="flex gap-2">
                  <ItemActions item={item} {...actions} fullWidth />
                </div>
              </li>
            );
          })}
        </ul>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <PendingSummary items={items} />
      <ul className="divide-y divide-line-hairline rounded-xl border border-line-struct bg-paper">
        {items.map((item) => {
          const { prescription } = item;
          return (
            <li key={item.visitId} className="flex flex-wrap items-center gap-x-3 gap-y-1.5 px-4 py-3">
              <span className="w-12 shrink-0 font-mono text-xs text-txt-muted">{timeOf(item.attendedAt)}</span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-txt-body">{item.nombrePaciente || `Exp. ${item.noExp}`}</p>
                <p className="flex flex-wrap items-center gap-1.5 text-xs text-txt-muted">
                  <span>Exp. {item.noExp}</span>
                  {hasMedications(prescription) ? (
                    <>
                      <span aria-hidden>·</span>
                      <span>{prescription.folio}</span>
                      {prescription.hasControlled ? <span>(+ hoja de controlado)</span> : null}
                    </>
                  ) : null}
                </p>
              </div>
              <PrescriptionState prescription={prescription} />
              <ItemActions item={item} {...actions} />
              <OtherDocuments documents={item.documents} className="w-full pl-15" />
            </li>
          );
        })}
      </ul>
    </div>
  );
}
