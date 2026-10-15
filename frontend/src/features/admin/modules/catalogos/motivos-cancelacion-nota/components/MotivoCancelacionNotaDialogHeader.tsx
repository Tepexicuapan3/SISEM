import type { ReactNode } from "react";
import { XCircle } from "lucide-react";
import { CatalogDialogHeader } from "@features/admin/modules/catalogos/shared/components/CatalogDialogHeader";

interface MotivoCancelacionNotaDialogHeaderProps {
  title: string;
  subtitle?: string | null;
  status?: ReactNode;
  meta?: ReactNode;
}

export function MotivoCancelacionNotaDialogHeader({
  title,
  subtitle,
  status,
  meta,
}: MotivoCancelacionNotaDialogHeaderProps) {
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
