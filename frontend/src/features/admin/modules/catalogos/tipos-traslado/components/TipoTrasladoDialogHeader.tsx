import type { ReactNode } from "react";
import { Map } from "lucide-react";
import { CatalogDialogHeader } from "@features/admin/modules/catalogos/shared/components/CatalogDialogHeader";

interface TipoTrasladoDialogHeaderProps {
  title: string;
  subtitle?: string | null;
  status?: ReactNode;
  meta?: ReactNode;
}

export function TipoTrasladoDialogHeader({
  title,
  subtitle,
  status,
  meta,
}: TipoTrasladoDialogHeaderProps) {
  return (
    <CatalogDialogHeader
      title={title}
      subtitle={subtitle}
      status={status}
      meta={meta}
      icon={<Map className="size-7" />}
    />
  );
}
