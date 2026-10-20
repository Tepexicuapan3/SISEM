import { Loader2, Printer } from "lucide-react";
import { Button } from "@shared/ui/button";
import type { PrintableDocument } from "@api/resources/impresion.api";
import { usePrintDocument } from "@shared/hooks/usePrintDocument";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import type { PermissionRequirement } from "@/domains/auth-access/types/permission-dependencies";

/**
 * Capability del backend por documento + fallback local (espejo de
 * CAPABILITY_REQUIREMENTS en permission_dependencies.py) para cuando la
 * proyeccion de capabilities aun no esta cargada.
 */
const PRINT_CAPABILITIES: Record<
  PrintableDocument,
  { key: string; fallback: PermissionRequirement }
> = {
  ficha: {
    key: "documentos.ficha.imprimir",
    fallback: {
      anyOf: [
        "recepcion:fichas:medicina_general:create",
        "recepcion:fichas:especialidad:create",
        "recepcion:fichas:urgencias:create",
        "clinico:consultas:read",
      ],
    },
  },
  receta: {
    key: "documentos.receta.imprimir",
    fallback: {
      anyOf: ["clinico:recetas:imprimir", "farmacia:recetas:dispensar"],
    },
  },
  nota: {
    key: "documentos.nota.imprimir",
    fallback: { allOf: ["clinico:consultas:read"] },
  },
};

interface PrintButtonProps {
  documento: PrintableDocument;
  /** visit_id para ficha / receta / nota. */
  resourceId: number;
  label?: string;
  printingLabel?: string;
  variant?: React.ComponentProps<typeof Button>["variant"];
  size?: React.ComponentProps<typeof Button>["size"];
  className?: string;
  disabled?: boolean;
}

export function PrintButton({
  documento,
  resourceId,
  label = "Imprimir",
  printingLabel = "Generando PDF...",
  variant,
  size,
  className,
  disabled = false,
}: PrintButtonProps) {
  const { hasCapability } = usePermissionDependencies();
  const { print, isPrinting } = usePrintDocument(documento);
  const capability = PRINT_CAPABILITIES[documento];

  if (!hasCapability(capability.key, capability.fallback)) return null;

  return (
    <Button
      type="button"
      variant={variant}
      size={size}
      className={className ? `gap-2 ${className}` : "gap-2"}
      disabled={disabled || isPrinting}
      onClick={() => void print(resourceId)}
    >
      {isPrinting ? (
        <Loader2 className="size-4 animate-spin" />
      ) : (
        <Printer className="size-4" />
      )}
      {isPrinting ? printingLabel : label}
    </Button>
  );
}
