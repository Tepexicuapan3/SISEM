import type { ReactNode } from "react";
import { Truck } from "lucide-react";
import { CatalogDialogHeader } from "@features/admin/modules/catalogos/shared/components/CatalogDialogHeader";

interface TipoServicioAmbulanciaDialogHeaderProps {
  title: string;
  subtitle?: string | null;
  status?: ReactNode;
  meta?: ReactNode;
}

export function TipoServicioAmbulanciaDialogHeader({
  title,
  subtitle,
  status,
  meta,
}: TipoServicioAmbulanciaDialogHeaderProps) {
  return (
    <CatalogDialogHeader
      title={title}
      subtitle={subtitle}
      status={status}
      meta={meta}
      icon={<Truck className="size-7" />}
    />
  );
}
