import { Badge } from "@shared/ui/badge";

interface MedicationControlBadgesProps {
  isControlled: boolean;
  cuadroBasico: string;
}

/** Marca los medicamentos que piden autorizacion antes de imprimir la receta. */
export function MedicationControlBadges({ isControlled, cuadroBasico }: MedicationControlBadgesProps) {
  return (
    <>
      {isControlled ? <Badge variant="critical">Controlado</Badge> : null}
      {cuadroBasico === "ESPECIAL" ? <Badge variant="alert">Especial</Badge> : null}
    </>
  );
}
