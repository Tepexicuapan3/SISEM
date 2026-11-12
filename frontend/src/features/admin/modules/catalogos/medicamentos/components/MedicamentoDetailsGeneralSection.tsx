import type { UseFormReturn } from "react-hook-form";
import { Form } from "@shared/ui/form";
import { Input } from "@shared/ui/input";
import { Label } from "@shared/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@shared/ui/select";
import { Separator } from "@shared/ui/separator";
import type { MedicamentoDetail } from "@api/types";
import {
  CATALOG_STATUS,
  type CatalogStatus,
} from "@features/admin/modules/catalogos/shared/domain/catalog-status";
import { MedicamentoFormFields } from "@features/admin/modules/catalogos/medicamentos/components/MedicamentoFormFields";
import type { MedicamentoDetailsFormValues } from "@features/admin/modules/catalogos/medicamentos/domain/medicamentos.schemas";

interface MedicamentoDetailsGeneralSectionProps {
  form: UseFormReturn<MedicamentoDetailsFormValues>;
  formId: string;
  medicamentoDetail: MedicamentoDetail;
  onSubmit: (values: MedicamentoDetailsFormValues) => void;
  onStatusChange?: (nextActive: boolean) => void;
  isStatusPending?: boolean;
  isEditable?: boolean;
}

export function MedicamentoDetailsGeneralSection({
  form,
  formId,
  medicamentoDetail,
  onSubmit,
  onStatusChange,
  isStatusPending = false,
  isEditable = true,
}: MedicamentoDetailsGeneralSectionProps) {
  const statusValue: CatalogStatus = medicamentoDetail.isActive
    ? CATALOG_STATUS.ACTIVE
    : CATALOG_STATUS.INACTIVE;

  return (
    <Form {...form}>
      <form
        id={formId}
        onSubmit={form.handleSubmit(onSubmit)}
        className="space-y-6"
      >
        <MedicamentoFormFields form={form} disabled={!isEditable} />

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label>ID</Label>
            <Input value={medicamentoDetail.id.toString()} disabled />
          </div>
          <div className="space-y-2">
            <Label>Estado</Label>
            <Select
              value={statusValue}
              onValueChange={(value) => {
                if (!onStatusChange || !isEditable) return;
                if (value === statusValue) return;
                onStatusChange(value === CATALOG_STATUS.ACTIVE);
              }}
              disabled={!onStatusChange || isStatusPending || !isEditable}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={CATALOG_STATUS.ACTIVE}>Activo</SelectItem>
                <SelectItem value={CATALOG_STATUS.INACTIVE}>Inactivo</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <Separator />
      </form>
    </Form>
  );
}
