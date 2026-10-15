import { useEffect, useMemo } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@shared/ui/dialog";
import { ScrollArea } from "@shared/ui/ScrollArea";
import { DesignacionDialogHeader } from "@features/admin/modules/catalogos/designacion-autorizadores/components/DesignacionDialogHeader";
import { DesignacionFormFields } from "@features/admin/modules/catalogos/designacion-autorizadores/components/DesignacionFormFields";
import {
  buildDesignacionSchema,
  type DesignacionFormValues,
} from "@features/admin/modules/catalogos/designacion-autorizadores/domain/designacion.schemas";
import { useCreateDesignacion } from "@features/admin/modules/catalogos/designacion-autorizadores/mutations/useCreateDesignacion";
import { getDesignacionErrorMessage } from "@features/admin/modules/catalogos/designacion-autorizadores/utils/designacion.feedback";
import {
  buildDesignacionPayload,
  buildEmptyDesignacionValues,
} from "@features/admin/modules/catalogos/designacion-autorizadores/utils/designacion.transform";

interface DesignacionCreateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** `admin.catalogs.designacionAutorizadores.global` */
  canGrantGlobal: boolean;
}

const FORM_ID = "designacion-create-form";

export function DesignacionCreateDialog({
  open,
  onOpenChange,
  canGrantGlobal,
}: DesignacionCreateDialogProps) {
  const createDesignacion = useCreateDesignacion();

  const schema = useMemo(() => buildDesignacionSchema({ canGrantGlobal }), [canGrantGlobal]);

  const form = useForm<DesignacionFormValues>({
    resolver: zodResolver(schema),
    defaultValues: buildEmptyDesignacionValues(),
  });

  useEffect(() => {
    if (!open) return;
    form.reset(buildEmptyDesignacionValues());
  }, [open, form]);

  const onSubmit = async (values: DesignacionFormValues) => {
    try {
      await createDesignacion.mutateAsync({ data: buildDesignacionPayload(values) });
      toast.success("Designación creada");
      onOpenChange(false);
    } catch (error) {
      toast.error("No se pudo crear la designación", {
        description: getDesignacionErrorMessage(error, "Error al guardar la designación"),
      });
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-[95vw] max-w-none rounded-3xl bg-paper p-0 sm:w-[92vw] lg:w-215 xl:w-235">
        <div className="flex max-h-[88vh] flex-col">
          <DialogHeader className="px-8 pt-8">
            <DialogTitle className="sr-only">Nueva designación</DialogTitle>
            <DialogDescription className="sr-only">
              Designa a un usuario como autorizador de un tipo de autorización para un alcance de
              centros y una vigencia.
            </DialogDescription>
            <DesignacionDialogHeader
              title="Nueva designación"
              subtitle="Define quién autoriza, para qué centros y por cuánto tiempo"
              status={<Badge variant="outline">Plantilla</Badge>}
            />
          </DialogHeader>

          <ScrollArea className="flex-1 px-8 pb-8">
            <div className="space-y-6 pt-4">
              <div className="rounded-2xl border border-line-struct bg-paper p-4">
                {open ? (
                  <DesignacionFormFields
                    form={form}
                    formId={FORM_ID}
                    onSubmit={onSubmit}
                    canGrantGlobal={canGrantGlobal}
                  />
                ) : null}
              </div>
            </div>
          </ScrollArea>

          <DialogFooter className="flex flex-col gap-3 border-t border-line-struct px-8 py-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="text-xs text-txt-muted">Completa los campos requeridos.</div>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                Cancelar
              </Button>
              <Button type="submit" form={FORM_ID} disabled={createDesignacion.isPending}>
                Crear designación
              </Button>
            </div>
          </DialogFooter>
        </div>
      </DialogContent>
    </Dialog>
  );
}
