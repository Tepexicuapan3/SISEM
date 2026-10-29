import type { ComponentPropsWithRef } from "react";
import * as PopoverPrimitive from "@radix-ui/react-popover";

import { cn } from "@shared/utils/styling/cn";

function Popover({
  ...props
}: ComponentPropsWithRef<typeof PopoverPrimitive.Root>) {
  return <PopoverPrimitive.Root data-slot="popover" {...props} />;
}

function PopoverTrigger({
  ...props
}: ComponentPropsWithRef<typeof PopoverPrimitive.Trigger>) {
  return <PopoverPrimitive.Trigger data-slot="popover-trigger" {...props} />;
}

function PopoverContent({
  className,
  align = "center",
  sideOffset = 4,
  onWheel,
  onTouchMove,
  ...props
}: ComponentPropsWithRef<typeof PopoverPrimitive.Content> & {
  align?: "start" | "center" | "end";
  sideOffset?: number;
}) {
  return (
    <PopoverPrimitive.Portal>
      <PopoverPrimitive.Content
        data-slot="popover-content"
        align={align}
        sideOffset={sideOffset}
        // El Portal saca el popover fuera del Dialog modal, cuyo bloqueo de scroll
        // (react-remove-scroll, escucha en document) anula la rueda del mouse aqui.
        // Cortar la propagacion deja que el scroll nativo de las listas funcione.
        onWheel={(event) => {
          event.stopPropagation();
          onWheel?.(event);
        }}
        onTouchMove={(event) => {
          event.stopPropagation();
          onTouchMove?.(event);
        }}
        className={cn(
          "bg-paper-lift text-txt-body border border-line-struct shadow-modal data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2 z-[140] w-72 origin-[var(--radix-popover-content-transform-origin)] rounded-xl p-4 outline-none",
          className,
        )}
        {...props}
      />
    </PopoverPrimitive.Portal>
  );
}

export { Popover, PopoverTrigger, PopoverContent };
