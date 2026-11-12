import type { ReactNode } from "react";
import { AdminDetailsHeader } from "@features/admin/shared/components/details/AdminDetailsHeader";

interface CatalogDialogHeaderProps {
  title: string;
  subtitle?: string | null;
  status?: ReactNode;
  meta?: ReactNode;
  icon: ReactNode;
  wrapTitle?: boolean;
}

export function CatalogDialogHeader({
  title,
  subtitle,
  status,
  meta,
  icon,
  wrapTitle,
}: CatalogDialogHeaderProps) {
  return (
    <AdminDetailsHeader
      title={title}
      wrapTitle={wrapTitle}
      subtitle={subtitle}
      status={status}
      meta={meta}
      leadingVisual={
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-line-struct/60 bg-subtle/50 text-brand">
          {icon}
        </div>
      }
    />
  );
}
