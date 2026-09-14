import type { ReactNode } from "react";
import { MapPin } from "lucide-react";
import { CatalogDialogHeader } from "@features/admin/modules/catalogos/shared/components/CatalogDialogHeader";

interface DestinoAmbulanciaDialogHeaderProps {
  title: string;
  subtitle?: string | null;
  status?: ReactNode;
  meta?: ReactNode;
}

export function DestinoAmbulanciaDialogHeader({
  title,
  subtitle,
  status,
  meta,
}: DestinoAmbulanciaDialogHeaderProps) {
  return (
    <CatalogDialogHeader
      title={title}
      subtitle={subtitle}
      status={status}
      meta={meta}
      icon={<MapPin className="size-7" />}
    />
  );
}
