import { Badge } from "@shared/ui/badge";
import type { PadronEnrollment } from "@api/types/padrones.types";

// Alerta de padrones en el expediente (docs/plans/padrones-alerta-expediente.md).
interface Props {
  cronicos: PadronEnrollment[];
  discapacidad: PadronEnrollment[];
}

/** Un CIE restringido ya viene redactado y sin programa: se muestra tal cual. */
const chronicLabel = (enrollment: PadronEnrollment) => {
  const { item, program, lastControl } = enrollment;
  const base = item.restricted
    ? item.description
    : program
      ? `${program.name} · ${item.code}`
      : `${item.code} ${item.description}`;
  return lastControl?.overdue ? `${base} · control vencido` : base;
};

export function PatientRegistriesAlert({ cronicos, discapacidad }: Props) {
  return (
    <>
      {cronicos.length > 0 && (
        <div>
          <p className="text-sm font-semibold text-txt-body mb-2">Padrón de crónicos</p>
          <div className="flex flex-wrap gap-2">
            {cronicos.map((enrollment) => (
              <Badge key={enrollment.id} variant={enrollment.lastControl?.overdue ? "critical" : "alert"}>
                {chronicLabel(enrollment)}
              </Badge>
            ))}
          </div>
        </div>
      )}
      {discapacidad.length > 0 && (
        <div>
          <p className="text-sm font-semibold text-txt-body mb-2">Padrón de discapacidad</p>
          <div className="flex flex-wrap gap-2">
            {discapacidad.map((enrollment) => (
              <Badge key={enrollment.id} variant="alert">
                {enrollment.item.description}
              </Badge>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
