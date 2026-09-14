import type { ReactNode } from "react";
import { Scissors } from "lucide-react";
import { CatalogDialogHeader } from "@features/admin/modules/catalogos/shared/components/CatalogDialogHeader";

interface TipoCirugiaDialogHeaderProps {
  title: string;
  subtitle?: string | null;
  status?: ReactNode;
  meta?: ReactNode;
}

export function TipoCirugiaDialogHeader({
  title,
  subtitle,
  status,
  meta,
}: TipoCirugiaDialogHeaderProps) {
  return (
    <CatalogDialogHeader
      title={title}
      subtitle={subtitle}
      status={status}
      meta={meta}
      icon={<Scissors className="size-7" />}
    />
  );
}
