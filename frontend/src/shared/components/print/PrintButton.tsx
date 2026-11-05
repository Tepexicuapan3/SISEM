import { Loader2, Printer } from "lucide-react";
import { Button } from "@shared/ui/button";
import type { PrintableDocument } from "@api/resources/impresion.api";
import { usePrintDocument } from "@shared/hooks/usePrintDocument";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import { PRINT_CAPABILITIES } from "./printCapabilities";

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
