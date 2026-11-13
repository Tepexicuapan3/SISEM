import { useId, type ReactNode } from "react";
import { cn } from "@shared/utils/styling/cn";

interface ConsultationSectionProps {
  /** Ancla del apartado (indice de la vista escritorio). */
  id?: string;
  title: string;
  description?: string;
  /** Acciones del apartado, alineadas a la derecha del titulo. */
  actions?: ReactNode;
  className?: string;
  children: ReactNode;
}

/** Apartado de la consulta: titulo visible, descripcion corta y su contenido. */
export function ConsultationSection({
  id,
  title,
  description,
  actions,
  className,
  children,
}: ConsultationSectionProps) {
  const headingId = useId();

  return (
    <section
      id={id}
      aria-labelledby={headingId}
      className={cn("scroll-mt-36 space-y-4 rounded-xl border border-line-struct bg-paper p-4 sm:p-5", className)}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-0.5">
          <h3 id={headingId} className="text-base font-semibold text-txt-body">
            {title}
          </h3>
          {description ? (
            <p className="text-sm leading-relaxed text-txt-muted">{description}</p>
          ) : null}
        </div>
        {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
      </div>
      {children}
    </section>
  );
}
