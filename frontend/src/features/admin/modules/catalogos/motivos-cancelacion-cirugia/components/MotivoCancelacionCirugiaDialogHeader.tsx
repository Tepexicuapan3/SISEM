import type { ReactNode } from "react";
import { XCircle } from "lucide-react";
import { CatalogDialogHeader } from "@features/admin/modules/catalogos/shared/components/CatalogDialogHeader";

interface MotivoCancelacionCirugiaDialogHeaderProps {
  title: string;
  subtitle?: string | null;
  status?: ReactNode;
  meta?: ReactNode;
}

export function MotivoCancelacionCirugiaDialogHeader({
  title,
  subtitle,
  status,
  meta,
}: MotivoCancelacionCirugiaDialogHeaderProps) {
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
