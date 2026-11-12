import { Badge } from "@shared/ui/badge";
import type { PrescriptionAuthorizationState } from "@features/expedientes/domain/prescription-authorization";

interface PrescriptionAuthorizationBadgeProps {
  authorization: PrescriptionAuthorizationState;
}

/** En que va la autorizacion de la receta (solo si la pidio: especial o controlado). */
export function PrescriptionAuthorizationBadge({ authorization }: PrescriptionAuthorizationBadgeProps) {
  if (authorization === null) return null;

  if (authorization.status === "pendiente") {
    return (
      <Badge variant="alert" className="text-xs">
        Receta pendiente de autorización
      </Badge>
    );
  }
  if (authorization.status === "autorizada") {
    return (
      <Badge variant="stable" className="text-xs">
        Receta autorizada
      </Badge>
    );
  }
  return (
    <span className="inline-flex flex-wrap items-center gap-1.5">
      <Badge variant="critical" className="text-xs">
        Receta rechazada
      </Badge>
      {authorization.rejectionReason ? (
        <span className="text-xs break-words text-txt-muted">{authorization.rejectionReason}</span>
      ) : null}
    </span>
  );
}
