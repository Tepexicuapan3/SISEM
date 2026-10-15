import type { ReactNode } from "react";
import { UserCog } from "lucide-react";
import { CatalogDialogHeader } from "@features/admin/modules/catalogos/shared/components/CatalogDialogHeader";

interface DesignacionDialogHeaderProps {
  title: string;
  subtitle?: string | null;
  status?: ReactNode;
  meta?: ReactNode;
}

export function DesignacionDialogHeader({
  title,
  subtitle,
  status,
  meta,
}: DesignacionDialogHeaderProps) {
  return (
    <CatalogDialogHeader
      title={title}
      subtitle={subtitle}
      status={status}
      meta={meta}
      icon={<UserCog className="size-7" />}
    />
  );
}
