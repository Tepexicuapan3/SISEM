import { useId } from "react";
import { cn } from "@shared/utils/styling/cn";
import {
  SOAP_SECTIONS,
  type SoapSectionName,
} from "@features/consulta-medica/modules/atencion/domain/consultation-soap";

interface Props {
  note: Partial<Record<SoapSectionName, string | null>>;
}

/** Nota SOAP de solo lectura: cada apartado con su letra y color. Omite los vacíos. */
export function SoapNoteView({ note }: Props) {
  const baseId = useId();
  const sections = SOAP_SECTIONS.filter(({ name }) => (note[name] ?? "").trim());
  if (sections.length === 0) return null;

  return (
    <div className="mt-1 space-y-1.5">
      {sections.map(({ name, letter, label, borderClass, badgeClass }) => {
        const labelId = `${baseId}-${name}`;
        return (
          <section
            key={name}
            role="group"
            aria-labelledby={labelId}
            className={cn("border-l-4 pl-2", borderClass)}
          >
            <p id={labelId} className="flex items-center gap-1.5 text-xs font-semibold text-txt-body">
              <span
                aria-hidden="true"
                className={cn(
                  "inline-flex size-5 items-center justify-center rounded text-[11px] font-bold text-txt-inverse",
                  badgeClass,
                )}
              >
                {letter}
              </span>
              <span className="sr-only">{letter} </span>
              {label}
            </p>
            <p className="whitespace-pre-wrap text-sm text-txt-muted">{note[name]}</p>
          </section>
        );
      })}
    </div>
  );
}
