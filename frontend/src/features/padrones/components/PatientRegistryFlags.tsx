import { Accessibility, AlertTriangle, HeartPulse } from "lucide-react";
import { cn } from "@shared/utils/styling/cn";
import type { PadronEnrollment } from "@api/types/padrones.types";
import { usePatientRegistries } from "@features/padrones/queries/usePadrones";

// Distintivos de padron junto al nombre del paciente, en el expediente y en la
// barra fija de la consulta (docs/plans/padrones-alerta-expediente.md).
interface Props {
  noExp: string;
  pkNum: number;
  className?: string;
}

const FLAG = "inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-sm font-semibold [&>svg]:size-4 [&>svg]:shrink-0";

/** "2026-04-01" -> "01/04/2026" (fecha sin hora: sin pasar por Date, sin desfase de zona). */
const formatDate = (iso: string) => iso.split("-").reverse().join("/");

/** Un CIE restringido ya viene redactado y sin programa: solo "Cronico", sin delatarlo. */
const chronicName = ({ item, program }: PadronEnrollment) =>
  item.restricted ? null : (program?.name ?? item.code);

const chronicTitle = ({ item, lastControl }: PadronEnrollment) => {
  const diagnosis = item.restricted ? "Padrón de crónicos" : `${item.code} ${item.description}`;
  if (!lastControl) return `${diagnosis}. Sin control registrado.`;
  return `${diagnosis}. Próximo control: ${formatDate(lastControl.nextControlOn)}.`;
};

export function PatientRegistryFlags({ noExp, pkNum, className }: Props) {
  const { data } = usePatientRegistries(noExp, pkNum);
  const cronicos = data?.cronicos ?? [];
  const discapacidad = data?.discapacidad ?? [];
  if (cronicos.length === 0 && discapacidad.length === 0) return null;

  return (
    <ul aria-label="Padrones del paciente" className={cn("flex flex-wrap gap-2", className)}>
      {cronicos.map((enrollment) => {
        const overdue = Boolean(enrollment.lastControl?.overdue);
        const name = chronicName(enrollment);
        return (
          <li
            key={`c-${enrollment.id}`}
            data-overdue={overdue}
            title={chronicTitle(enrollment)}
            className={cn(
              FLAG,
              overdue
                ? "border-status-critical/40 bg-status-critical/10 text-status-critical"
                : "border-status-alert/40 bg-status-alert/10 text-status-alert",
            )}
          >
            {overdue ? <AlertTriangle aria-hidden /> : <HeartPulse aria-hidden />}
            {name ? `Crónico: ${name}` : "Crónico"}
            {overdue ? " · control vencido" : ""}
          </li>
        );
      })}
      {discapacidad.map((enrollment) => (
        <li
          key={`d-${enrollment.id}`}
          title="Padrón de discapacidad"
          className={cn(FLAG, "border-status-info/40 bg-status-info/10 text-status-info")}
        >
          <Accessibility aria-hidden />
          {`Discapacidad: ${enrollment.item.description}`}
        </li>
      ))}
    </ul>
  );
}
