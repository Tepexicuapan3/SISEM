import type { ReactNode } from "react";
import { Route } from "lucide-react";
import { CatalogDialogHeader } from "@features/admin/modules/catalogos/shared/components/CatalogDialogHeader";

interface MotivoTrasladoDialogHeaderProps {
  title: string;
  subtitle?: string | null;
  status?: ReactNode;
  meta?: ReactNode;
}

export function MotivoTrasladoDialogHeader({
  title,
  subtitle,
  status,
  meta,
}: MotivoTrasladoDialogHeaderProps) {
  return (
    <CatalogDialogHeader
      title={title}
      subtitle={subtitle}
      status={status}
      meta={meta}
      icon={<Route className="size-7" />}
    />
  );
}
