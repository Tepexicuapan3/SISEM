import type { ReactNode } from "react";
import { Pill } from "lucide-react";
import { CatalogDialogHeader } from "@features/admin/modules/catalogos/shared/components/CatalogDialogHeader";

interface MedicamentoDialogHeaderProps {
  title: string;
  subtitle?: string | null;
  status?: ReactNode;
  meta?: ReactNode;
}

export function MedicamentoDialogHeader({
  title,
  subtitle,
  status,
  meta,
}: MedicamentoDialogHeaderProps) {
  return (
    <CatalogDialogHeader
      title={title}
      subtitle={subtitle}
      status={status}
      meta={meta}
      icon={<Pill className="size-7" />}
    />
  );
}
