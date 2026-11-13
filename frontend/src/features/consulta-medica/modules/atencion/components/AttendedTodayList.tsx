import { FileText, Printer } from "lucide-react";
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
}

const timeOf = (iso: string | null): string => {
  if (!iso) return "";
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? ""
    : date.toLocaleTimeString("es-MX", { hour: "2-digit", minute: "2-digit", timeZone: "America/Mexico_City" });
};

function PrescriptionState({ prescription }: { prescription: DoctorAttendedPrescription | null }) {
  if (prescription === null || prescription.medicationsCount === 0) {
    return <span className="text-xs text-txt-muted">Sin receta</span>;
  }
  const { authorization } = prescription;
  if (authorization?.status === "pendiente") {
    return <Badge variant="alert" className="text-xs">Pendiente de autorización</Badge>;
  }
  if (authorization?.status === "rechazada") {
    return (
      <span className="inline-flex flex-wrap items-center gap-1.5">
        <Badge variant="critical" className="text-xs">Rechazada</Badge>
        {authorization.rejectionReason ? (
          <span className="text-xs break-words text-txt-muted">{authorization.rejectionReason}</span>
        ) : null}
      </span>
    );
  }
  return <Badge variant="stable" className="text-xs">Lista para imprimir</Badge>;
}

const dateOf = (isoDate: string): string => {
  const date = new Date(`${isoDate}T12:00:00`);
  return Number.isNaN(date.getTime())
    ? isoDate
    : date.toLocaleDateString("es-MX", { day: "numeric", month: "short" });
};

/** Incapacidad, pases y seguimiento: informativo, se consultan en el expediente. */
function OtherDocuments({ documents }: { documents: DoctorAttendedDocuments | undefined }) {
  if (!documents) return null;
  const chips = [
    documents.medicalLeave
      ? `Incapacidad ${documents.medicalLeave.folio} · ${documents.medicalLeave.days} días`
      : null,
    ...documents.referrals.map((referral) => `Pase ${referral.label ?? referral.type} ${referral.folio}`),
    documents.followUpDate ? `Seguimiento ${dateOf(documents.followUpDate)}` : null,
  ].filter((chip): chip is string => chip !== null);
  if (chips.length === 0) return null;
  return (
    <p className="flex w-full flex-wrap gap-1.5 pl-15">
      {chips.map((chip) => (
        <span key={chip} className="rounded-md bg-subtle/40 px-1.5 py-0.5 text-xs text-txt-muted">
          {chip}
        </span>
      ))}
    </p>
  );
}

/** Lo que requiere accion del medico, arriba de la lista. */
function PendingSummary({ items }: { items: DoctorAttendedItem[] }) {
  const pending = items.filter((item) => item.prescription?.authorization?.status === "pendiente").length;
  const rejected = items.filter((item) => item.prescription?.authorization?.status === "rechazada").length;
  if (pending === 0 && rejected === 0) return null;
  const parts = [
    pending > 0 ? `${pending} por autorizar` : null,
    rejected > 0 ? `${rejected} ${rejected === 1 ? "rechazada" : "rechazadas"}` : null,
  ].filter(Boolean);
  return (
    <p role="status" className="rounded-lg border border-status-alert/40 bg-status-alert/5 px-3 py-2 text-xs text-txt-body">
      <span className="font-semibold">Recetas pendientes:</span> {parts.join(" · ")}
    </p>
  );
}

/** Consultas que el medico cerro hoy, con el estado de su receta (Mi jornada). */
export function AttendedTodayList({
  items,
  canPrint,
  onPrint,
  isPrinting = false,
  canPrintNote = false,
  onPrintNote,
}: AttendedTodayListProps) {
  if (items.length === 0) {
    return <p className="text-sm text-txt-muted">Todavía no cerraste consultas hoy.</p>;
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
                {prescription && prescription.medicationsCount > 0 ? (
                  <>
                    <span aria-hidden>·</span>
                    <span>{prescription.folio}</span>
                    {prescription.hasControlled ? <span>(+ hoja de controlado)</span> : null}
                  </>
                ) : null}
              </p>
            </div>
            <PrescriptionState prescription={prescription} />
            {canPrint && prescription?.printable ? (
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={isPrinting}
                onClick={() => onPrint(item.visitId)}
                aria-label={`Imprimir receta de ${item.nombrePaciente || item.noExp}`}
              >
                <Printer className="size-3.5" /> Imprimir receta
              </Button>
            ) : null}
            {canPrintNote && onPrintNote && item.documents?.notePrintable ? (
              <Button
                type="button"
                size="sm"
                variant="ghost"
                disabled={isPrinting}
                onClick={() => onPrintNote(item.visitId)}
                aria-label={`Imprimir nota de ${item.nombrePaciente || item.noExp}`}
              >
                <FileText className="size-3.5" /> Nota
              </Button>
            ) : null}
            <OtherDocuments documents={item.documents} />
          </li>
        );
      })}
    </ul>
    </div>
  );
}
