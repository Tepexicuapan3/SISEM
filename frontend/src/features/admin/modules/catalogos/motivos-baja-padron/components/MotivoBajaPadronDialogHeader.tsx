import type { ReactNode } from "react";
import { XCircle } from "lucide-react";
import { CatalogDialogHeader } from "@features/admin/modules/catalogos/shared/components/CatalogDialogHeader";

interface MotivoBajaPadronDialogHeaderProps {
  title: string;
  subtitle?: string | null;
  status?: ReactNode;
  meta?: ReactNode;
}

export function MotivoBajaPadronDialogHeader({
  title,
  subtitle,
  status,
  meta,
}: MotivoBajaPadronDialogHeaderProps) {
  return (
    <CatalogDialogHeader
      title={title}
      subtitle={subtitle}
      status={status}
      meta={meta}
      icon={<XCircle className="size-7" />}
    />
  );
}
