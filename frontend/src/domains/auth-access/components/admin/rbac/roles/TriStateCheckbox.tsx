import type { ComponentPropsWithRef } from "react";
import * as CheckboxPrimitive from "@radix-ui/react-checkbox";
import { CheckIcon, MinusIcon } from "lucide-react";
import { cn } from "@shared/utils/styling/cn";

export type TriState = "checked" | "unchecked" | "indeterminate";

interface TriStateCheckboxProps
  extends Omit<
    ComponentPropsWithRef<typeof CheckboxPrimitive.Root>,
    "checked" | "onCheckedChange"
  > {
  state: TriState;
  onToggle: () => void;
}

/**
 * Checkbox con estado indeterminado para filas/secciones de la matriz.
 *
 * Local a `roles/` a proposito: `@shared/ui/checkbox` solo renderiza
 * `CheckIcon` y no estiliza `data-[state=indeterminate]`, y no se modifica
 * (regla add-only).
 */
export function TriStateCheckbox({
  state,
  onToggle,
  className,
  ...props
}: TriStateCheckboxProps) {
  return (
    <CheckboxPrimitive.Root
      data-slot="checkbox"
      checked={state === "indeterminate" ? "indeterminate" : state === "checked"}
      onCheckedChange={() => onToggle()}
      className={cn(
        "peer size-4 shrink-0 rounded-sm border border-line-struct shadow-xs transition-shadow outline-none",
        "focus-visible:ring-[3px] focus-visible:ring-brand/50 focus-visible:border-brand",
        "data-[state=checked]:bg-brand data-[state=checked]:text-txt-inverse data-[state=checked]:border-brand",
        "data-[state=indeterminate]:bg-brand data-[state=indeterminate]:text-txt-inverse data-[state=indeterminate]:border-brand",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    >
      <CheckboxPrimitive.Indicator
        data-slot="checkbox-indicator"
        className="grid place-content-center text-current transition-none"
      >
        {state === "indeterminate" ? (
          <MinusIcon className="size-3.5" />
        ) : (
          <CheckIcon className="size-3.5" />
        )}
      </CheckboxPrimitive.Indicator>
    </CheckboxPrimitive.Root>
  );
}
