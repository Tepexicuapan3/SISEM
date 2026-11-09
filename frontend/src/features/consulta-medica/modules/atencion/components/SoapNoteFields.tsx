import type { UseFormReturn } from "react-hook-form";
import { Textarea } from "@shared/ui/textarea";
import { cn } from "@shared/utils/styling/cn";
import type {
  SaveDiagnosisFormInput,
  SaveDiagnosisFormValues,
} from "@features/consulta-medica/modules/atencion/domain/consultation.schemas";
import { SOAP_SECTIONS } from "@features/consulta-medica/modules/atencion/domain/consultation-soap";

interface Props {
  diagnosisForm: UseFormReturn<SaveDiagnosisFormInput, unknown, SaveDiagnosisFormValues>;
  disabled: boolean;
}

/** Nota SOAP: un apartado por letra, cada uno con su color. Opcionales. */
export function SoapNoteFields({ diagnosisForm, disabled }: Props) {
  return (
    <fieldset className="space-y-3 rounded-lg border border-line-struct p-3">
      <legend className="px-1 text-sm font-semibold text-txt-body">Nota SOAP</legend>
      {SOAP_SECTIONS.map(({ name, letter, label, hint, borderClass, badgeClass }) => (
        <div
          key={name}
          className={cn("space-y-1.5 border-l-4 pl-3", borderClass)}
        >
          <label htmlFor={name} className="flex items-center gap-2 text-sm font-medium text-txt-body">
            <span
              aria-hidden="true"
              className={cn(
                "inline-flex size-6 shrink-0 items-center justify-center rounded-md text-xs font-bold text-txt-inverse",
                badgeClass,
              )}
            >
              {letter}
            </span>
            <span className="sr-only">{letter} </span>
            {label}
          </label>
          <p className="text-xs text-txt-muted">{hint}</p>
          <Textarea id={name} rows={3} disabled={disabled} {...diagnosisForm.register(name)} />
        </div>
      ))}
    </fieldset>
  );
}
