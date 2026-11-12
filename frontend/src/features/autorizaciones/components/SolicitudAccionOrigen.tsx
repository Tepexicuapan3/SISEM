import { Printer } from "lucide-react";
import { Button } from "@shared/ui/button";
import { usePrintDocument } from "@shared/hooks/usePrintDocument";
import { PRINT_CAPABILITIES } from "@shared/components/print/printCapabilities";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import type { SolicitudAccionOrigen as Accion } from "@api/types/autorizaciones/solicitudes.types";

interface SolicitudAccionOrigenProps {
  accion: Accion | null | undefined;
}

/**
 * Lo que el origen permite hacer con el resultado: hoy, imprimir la receta
 * autorizada. El backend vuelve a validar permiso y estado al imprimir.
 */
export function SolicitudAccionOrigen({ accion }: SolicitudAccionOrigenProps) {
  const { hasCapability } = usePermissionDependencies();
  const { print, isPrinting } = usePrintDocument("receta");

  if (!accion || accion.tipo !== "IMPRIMIR_RECETA") return null;
  if (!hasCapability(PRINT_CAPABILITIES.receta.key, PRINT_CAPABILITIES.receta.fallback)) return null;

  return (
    <Button type="button" disabled={isPrinting} onClick={() => void print(accion.visitId)}>
      <Printer className="mr-2 size-4" />
      Imprimir receta
    </Button>
  );
}
