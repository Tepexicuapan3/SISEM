import { useId, type ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@shared/utils/styling/cn";

interface DeskPanelProps {
  icon:       LucideIcon;
  title:      string;
  count?:     number;
  /** Una linea que dice para que sirve el panel. */
  hint?:      string;
  className?: string;
  testId?:    string;
  children:   ReactNode;
}

/** Panel de Mi consultorio: mismo encabezado en las tres columnas para leerlas igual. */
export function DeskPanel({ icon: Icon, title, count, hint, className, testId, children }: DeskPanelProps) {
  const headingId = useId();
  return (
    <section
      aria-labelledby={headingId}
      data-testid={testId}
      className={cn("rounded-xl border border-line-struct bg-paper", className)}
    >
      <header className="flex items-start gap-2.5 border-b border-line-hairline px-4 py-3">
        <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-lg bg-brand/10 text-brand">
          <Icon className="size-4" />
        </span>
        <div className="min-w-0">
          <h2 id={headingId} className="text-sm font-semibold text-txt-body">
            {title}
            {count !== undefined ? (
              <>
                {" "}
                <span className="font-mono text-txt-muted tabular-nums">({count})</span>
              </>
            ) : null}
          </h2>
          {hint ? <p className="text-xs leading-snug text-txt-muted">{hint}</p> : null}
        </div>
      </header>
      <div className="p-3">{children}</div>
    </section>
  );
}
