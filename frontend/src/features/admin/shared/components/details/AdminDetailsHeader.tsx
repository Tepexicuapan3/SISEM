import type { ReactNode } from "react";

interface AdminDetailsHeaderProps {
  title: string;
  subtitle?: string | null;
  status?: ReactNode;
  meta?: ReactNode;
  leadingVisual?: ReactNode;
  /** Parte el titulo en lineas en vez de truncarlo (titulos largos tipo oracion). */
  wrapTitle?: boolean;
}

export function AdminDetailsHeader({
  title,
  subtitle,
  status,
  meta,
  leadingVisual,
  wrapTitle = false,
}: AdminDetailsHeaderProps) {
  return (
    <div className="flex min-w-0 flex-col gap-4">
      <div className="flex min-w-0 flex-col gap-4 sm:flex-row sm:items-center">
        {leadingVisual}
        <div className="flex min-h-16 min-w-0 flex-1 flex-col justify-center space-y-1">
          <div className="flex min-w-0 items-center gap-2">
            <span
              className={
                wrapTitle
                  ? "block max-w-full text-lg leading-snug font-semibold text-txt-body break-words"
                  : "block max-w-full truncate text-lg font-semibold text-txt-body"
              }
              title={title}
            >
              {title}
            </span>
          </div>
          {subtitle ? (
            <div className="truncate text-sm text-txt-muted" title={subtitle}>
              {subtitle}
            </div>
          ) : null}
          {status || meta ? (
            <div className="flex min-w-0 flex-wrap items-center gap-3 text-xs text-txt-muted">
              {status ? <div className="shrink-0">{status}</div> : null}
              {meta ? <div className="min-w-0 flex-1">{meta}</div> : null}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
