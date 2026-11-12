/**
 * TruncatedTooltip - Muestra tooltip solo cuando el texto está truncado.
 *
 * Usa ResizeObserver para detectar overflow y controla el tooltip condicionalmente.
 * Usa un wrapper span para capturar el ref sin necesidad de cloneElement.
 */

import { useLayoutEffect, useRef, useState, type ReactNode } from "react";

import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@shared/ui/tooltip";

interface TruncatedTooltipProps {
  /** Texto a mostrar en el tooltip */
  label: string;
  /** Contenido que puede truncarse */
  children: ReactNode;
  /** Posición del tooltip */
  side?: "top" | "right" | "bottom" | "left";
  /** Alineación del tooltip */
  align?: "start" | "center" | "end";
  /** Forzar tooltip siempre visible (para badges, etc.) */
  forceShow?: boolean;
  /** Clases CSS para el wrapper (debe incluir truncate) */
  className?: string;
}

/**
 * Hook para detectar si un elemento tiene overflow (texto truncado).
 */
const useIsOverflowed = () => {
  const ref = useRef<HTMLSpanElement>(null);
  const [isOverflowed, setIsOverflowed] = useState(false);

  useLayoutEffect(() => {
    const element = ref.current;
    if (!element) return undefined;

    const update = () => {
      // Horizontal (truncate) o vertical (line-clamp).
      const hasOverflow =
        element.scrollWidth > element.clientWidth ||
        element.scrollHeight > element.clientHeight;
      setIsOverflowed(hasOverflow);
    };

    // Medición inicial con rAF para asegurar layout completo
    const frame = requestAnimationFrame(update);

    // Observer para cambios de tamaño
    const resizeObserver = new ResizeObserver(update);
    resizeObserver.observe(element);

    return () => {
      cancelAnimationFrame(frame);
      resizeObserver.disconnect();
    };
  }, []);

  return { ref, isOverflowed };
};

/**
 * Componente que muestra tooltip solo cuando el contenido está truncado.
 * Usa un wrapper span interno para medir el overflow.
 */
export const TruncatedTooltip = ({
  label,
  children,
  side = "top",
  align = "start",
  forceShow = false,
  className,
}: TruncatedTooltipProps) => {
  const { ref, isOverflowed } = useIsOverflowed();

  // Determinar si el tooltip debe mostrarse
  const shouldShowTooltip = forceShow || isOverflowed;

  if (!shouldShowTooltip) {
    return (
      <span ref={ref} className={className}>
        {children}
      </span>
    );
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span ref={ref} className={className}>
          {children}
        </span>
      </TooltipTrigger>
      <TooltipContent side={side} align={align}>
        {label}
      </TooltipContent>
    </Tooltip>
  );
};
