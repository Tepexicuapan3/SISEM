import { HeartPulse } from "lucide-react";
import { toast } from "sonner";
import { Alert, AlertDescription, AlertTitle } from "@shared/ui/alert";
import { Button } from "@shared/ui/button";
import {
  useChronicVisitNotice,
  useEnrollChronicFromVisit,
} from "@features/padrones/queries/usePadrones";
import { getPadronesErrorMessage } from "@features/padrones/utils/padrones.feedback";
import { formatPadronDate } from "@features/padrones/utils/padrones.format";

interface Props {
  visitId: number;
  /** CIE-10 elegido en la consulta; el backend decide si sugiere inscribir. */
  cieCode: string;
}

/**
 * Aviso del padron de cronicos dentro de la consulta (P-04 del legado) y
 * sugerencia de inscripcion al elegir un diagnostico de un programa.
 * Ver docs/plans/cronicos-aviso-consulta.md.
 */
export function ChronicConditionsNotice({ visitId, cieCode }: Props) {
  const noticeQuery = useChronicVisitNotice(visitId, cieCode);
  const enroll = useEnrollChronicFromVisit(visitId);

  const notice = noticeQuery.data;
  if (noticeQuery.isError || !notice) {
    return null;
  }
  const { enrollments, suggestion, canEnroll } = notice;
  if (enrollments.length === 0 && !suggestion) {
    return null;
  }

  const handleEnroll = async () => {
    if (!suggestion) {
      return;
    }
    try {
      await enroll.mutateAsync({ itemId: suggestion.cie.code });
      toast.success("Paciente inscrito en el padrón de crónicos");
    } catch (error) {
      toast.error("No se pudo inscribir al paciente", {
        description: getPadronesErrorMessage(error, "Intenta nuevamente."),
      });
    }
  };

  return (
    <div className="space-y-2" data-testid="chronic-conditions-notice">
      {enrollments.length > 0 ? (
        <Alert variant="warning">
          <HeartPulse />
          <AlertTitle>Paciente en el padrón de crónicos</AlertTitle>
          <AlertDescription>
            <ul className="space-y-0.5">
              {enrollments.map((enrollment) => (
                <li key={enrollment.id}>
                  {enrollment.program ? (
                    <span className="font-semibold">{enrollment.program.name}: </span>
                  ) : null}
                  {enrollment.item.code
                    ? `${enrollment.item.code} · ${enrollment.item.description}`
                    : enrollment.item.description}
                  <span className="text-txt-muted"> · desde {formatPadronDate(enrollment.enrolledOn)}</span>
                </li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      ) : null}

      {suggestion ? (
        <Alert variant="info">
          <HeartPulse />
          <AlertTitle>¿Inscribir al padrón de crónicos?</AlertTitle>
          <AlertDescription>
            <p>
              {suggestion.cie.code} · {suggestion.cie.description} pertenece al programa{" "}
              {suggestion.program.name}.
              {canEnroll ? null : " Quien tenga permiso del padrón puede inscribirlo."}
            </p>
            {canEnroll ? (
              <Button
                type="button"
                size="sm"
                className="mt-2"
                onClick={() => void handleEnroll()}
                disabled={enroll.isPending}
              >
                Inscribir en el padrón
              </Button>
            ) : null}
          </AlertDescription>
        </Alert>
      ) : null}
    </div>
  );
}
