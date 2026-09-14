import type { ReactNode } from "react";
import { FileText } from "lucide-react";
import { CatalogDialogHeader } from "@features/admin/modules/catalogos/shared/components/CatalogDialogHeader";

interface Cie9McDialogHeaderProps {
  title: string;
  subtitle?: string | null;
  status?: ReactNode;
  meta?: ReactNode;
}

export function Cie9McDialogHeader({
  title,
  subtitle,
  status,
  meta,
}: Cie9McDialogHeaderProps) {
  return (
    <CatalogDialogHeader
      title={title}
      subtitle={subtitle}
      status={status}
      meta={meta}
      icon={<FileText className="size-7" />}
    />
  );
}
