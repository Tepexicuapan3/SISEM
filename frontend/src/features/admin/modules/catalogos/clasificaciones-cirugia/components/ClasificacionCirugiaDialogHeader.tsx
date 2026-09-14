import type { ReactNode } from "react";
import { ListChecks } from "lucide-react";
import { CatalogDialogHeader } from "@features/admin/modules/catalogos/shared/components/CatalogDialogHeader";

interface ClasificacionCirugiaDialogHeaderProps {
  title: string;
  subtitle?: string | null;
  status?: ReactNode;
  meta?: ReactNode;
}

export function ClasificacionCirugiaDialogHeader({
  title,
  subtitle,
  status,
  meta,
}: ClasificacionCirugiaDialogHeaderProps) {
  return (
    <CatalogDialogHeader
      title={title}
      subtitle={subtitle}
      status={status}
      meta={meta}
      icon={<ListChecks className="size-7" />}
    />
  );
}
