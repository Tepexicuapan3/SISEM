import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { UserCheck } from "lucide-react";
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
import { CatalogDialogHeader } from "@features/admin/modules/catalogos/shared/components/CatalogDialogHeader";
import { AutorizadorFormFields } from "@features/admin/modules/autorizadores/components/AutorizadorFormFields";
import {
  buildAutorizadorSchema,
  type AutorizadorFormValues,
} from "@features/admin/modules/autorizadores/domain/autorizador.schemas";
import { useCreateAutorizador } from "@features/admin/modules/autorizadores/mutations/useAutorizadorMutations";
import { useCatalogosAutorizacion } from "@features/admin/modules/autorizadores/queries/useAutorizadores";
import { getAutorizadorErrorMessage } from "@features/admin/modules/autorizadores/utils/autorizador.feedback";
import {
  buildAltaPayload,
  buildEmptyAutorizadorValues,
} from "@features/admin/modules/autorizadores/utils/autorizador.transform";

interface AutorizadorCreateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** `admin:autorizadores:global` */
  canGrantGlobal: boolean;
}

const FORM_ID = "autorizador-create-form";

export function AutorizadorCreateDialog({ open, onOpenChange, canGrantGlobal }: AutorizadorCreateDialogProps) {
  const crear = useCreateAutorizador();
  const { data: catalogos } = useCatalogosAutorizacion(open);
  const tiposCatalogo = catalogos?.tipos ?? [];

  const form = useForm<AutorizadorFormValues>({
    resolver: zodResolver(buildAutorizadorSchema({ canGrantGlobal, modo: "alta" })),
    defaultValues: buildEmptyAutorizadorValues([]),
  });

  // Al abrir (y cuando llega el catalogo) el formulario arranca limpio con un renglon por tipo.
  useEffect(() => {
    if (!open || !catalogos) return;
    form.reset(buildEmptyAutorizadorValues(catalogos.tipos.map((tipo) => tipo.clave)));
  }, [open, catalogos, form]);

  const onSubmit = async (valores: AutorizadorFormValues) => {
    try {
      const respuesta = await crear.mutateAsync(buildAltaPayload(valores));
      toast.success("Autorizador registrado", {
        description: `${respuesta.autorizador.usuario.nombreCompleto} ya puede autorizar en los centros asignados.`,
      });
      onOpenChange(false);
    } catch (error) {
      toast.error("No se pudo registrar el autorizador", {
        description: getAutorizadorErrorMessage(error, "Error al guardar el autorizador"),
      });
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {/* sm:max-w-none anula el sm:max-w-lg (512px) del DialogContent base. */}
      <DialogContent className="w-[95vw] max-w-none rounded-3xl bg-paper p-0 sm:w-[92vw] sm:max-w-none lg:w-215 xl:w-235">
        <div className="flex max-h-[88vh] flex-col">
          <DialogHeader className="px-4 pt-6 sm:px-8 sm:pt-8">
            <DialogTitle className="sr-only">Nuevo autorizador</DialogTitle>
            <DialogDescription className="sr-only">
              Registra a un usuario de SIRES como médico autorizador con sus tipos de autorización,
              centros y vigencia.
            </DialogDescription>
            <CatalogDialogHeader
              title="Nuevo autorizador"
              subtitle="Elige al médico, qué puede autorizar, en qué centros y hasta cuándo"
              status={<Badge variant="outline">Nuevo</Badge>}
              icon={<UserCheck className="size-7" />}
            />
          </DialogHeader>

          <ScrollArea className="min-w-0 flex-1 px-4 pb-6 sm:px-8 sm:pb-8">
            <div className="min-w-0 pt-4">
              <div className="min-w-0 rounded-2xl border border-line-struct bg-paper p-4 sm:p-5">
                {open && tiposCatalogo.length > 0 ? (
                  <AutorizadorFormFields
                    form={form}
                    formId={FORM_ID}
                    onSubmit={onSubmit}
                    modo="alta"
                    tiposCatalogo={tiposCatalogo}
                    canGrantGlobal={canGrantGlobal}
                    enabled={open}
                  />
                ) : (
                  <p className="py-6 text-center text-sm text-txt-muted">Cargando tipos de autorización...</p>
                )}
              </div>
            </div>
          </ScrollArea>

          <DialogFooter className="flex flex-col gap-3 border-t border-line-struct px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-8">
            <div className="text-xs text-txt-muted">
              Toda alta queda registrada en el historial y la bitácora.
            </div>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                Cancelar
              </Button>
              <Button type="submit" form={FORM_ID} disabled={crear.isPending || tiposCatalogo.length === 0}>
                Registrar autorizador
              </Button>
            </div>
          </DialogFooter>
        </div>
      </DialogContent>
    </Dialog>
  );
}
