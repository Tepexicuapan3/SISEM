import { useState } from "react";
import { toast } from "sonner";
import type { Modalidad, ReglaCentro, TipoConfiguracion } from "@api/types/autorizaciones/configuracion.types";
import { Button } from "@shared/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@shared/ui/dialog";
import { Label } from "@shared/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@shared/ui/select";
import { CampoNumero } from "@features/admin/modules/autorizaciones-config/components/CampoNumero";
import { ETIQUETA_MODALIDAD } from "@features/admin/modules/autorizaciones-config/domain/configuracion.format";
import {
  erroresPorCampo,
  MODALIDADES,
  reglaCentroSchema,
  type ReglaCentroFormValues,
} from "@features/admin/modules/autorizaciones-config/domain/configuracion.schemas";
import {
  useCreateRegla,
  useUpdateRegla,
} from "@features/admin/modules/autorizaciones-config/mutations/useConfiguracionMutations";
import { getConfiguracionErrorMessage } from "@features/admin/modules/autorizaciones-config/utils/configuracion.feedback";

const HEREDA = "HEREDA";

interface ReglaCentroDialogProps {
  /** null = alta. */
  regla: ReglaCentro | null;
  tipos: TipoConfiguracion[];
  centros: { id: number; name: string }[];
  onClose: () => void;
}

/** El estado se reinicia remontando el dialogo: la pestaña le da una `key` por regla. */
export function ReglaCentroDialog({ regla, tipos, centros, onClose }: ReglaCentroDialogProps) {
  const crear = useCreateRegla();
  const actualizar = useUpdateRegla();
  const [valores, setValores] = useState<ReglaCentroFormValues>({
    tipoId: regla?.tipoId ?? 0,
    centroId: regla?.centroId ?? 0,
    modalidad: regla?.modalidad ?? null,
    aprobacionesRequeridas: regla?.aprobacionesRequeridas ?? null,
    horasVigenciaSolicitud: regla?.horasVigenciaSolicitud ?? null,
  });
  const [errores, setErrores] = useState<Record<string, string>>({});
  const tipo = tipos.find((t) => t.id === valores.tipoId);
  const enviando = crear.isPending || actualizar.isPending;

  const guardar = async () => {
    const resultado = reglaCentroSchema.safeParse(valores);
    if (!resultado.success) {
      setErrores(erroresPorCampo(resultado.error.issues));
      return;
    }
    setErrores({});
    const { tipoId, centroId, ...propios } = resultado.data;
    try {
      if (regla) {
        await actualizar.mutateAsync({ id: regla.id, data: { ...propios, version: regla.version } });
      } else {
        await crear.mutateAsync({ tipoId, centroId, ...propios });
      }
      toast.success(regla ? "Regla actualizada" : "Regla creada");
      onClose();
    } catch (error) {
      toast.error("No se pudo guardar la regla", {
        description: getConfiguracionErrorMessage(error, "Intenta nuevamente."),
      });
    }
  };

  return (
    <Dialog open onOpenChange={(abierto) => !abierto && onClose()}>
      <DialogContent className="max-w-xl rounded-3xl bg-paper sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>{regla ? "Editar regla del centro" : "Nueva regla por centro"}</DialogTitle>
          <DialogDescription>
            Excepción a la regla general del tipo para un centro. Lo que dejes vacío se toma del tipo. Aplica a las
            solicitudes nuevas.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="regla-tipo">Tipo de autorización</Label>
            <Select
              value={valores.tipoId ? String(valores.tipoId) : undefined}
              onValueChange={(valor) => setValores((actual) => ({ ...actual, tipoId: Number(valor) }))}
              disabled={Boolean(regla)}
            >
              <SelectTrigger id="regla-tipo" aria-invalid={Boolean(errores.tipoId)}>
                <SelectValue placeholder="Selecciona" />
              </SelectTrigger>
              <SelectContent>
                {tipos.map((t) => (
                  <SelectItem key={t.id} value={String(t.id)}>
                    {t.nombre}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {errores.tipoId ? <p className="text-xs text-status-critical">{errores.tipoId}</p> : null}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="regla-centro">Centro de atención</Label>
            <Select
              value={valores.centroId ? String(valores.centroId) : undefined}
              onValueChange={(valor) => setValores((actual) => ({ ...actual, centroId: Number(valor) }))}
              disabled={Boolean(regla)}
            >
              <SelectTrigger id="regla-centro" aria-invalid={Boolean(errores.centroId)}>
                <SelectValue placeholder="Selecciona" />
              </SelectTrigger>
              <SelectContent>
                {centros.map((centro) => (
                  <SelectItem key={centro.id} value={String(centro.id)}>
                    {centro.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {errores.centroId ? <p className="text-xs text-status-critical">{errores.centroId}</p> : null}
          </div>

          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="regla-modalidad">Modalidad</Label>
            <Select
              value={valores.modalidad ?? HEREDA}
              onValueChange={(valor) =>
                setValores((actual) => ({ ...actual, modalidad: valor === HEREDA ? null : (valor as Modalidad) }))
              }
            >
              <SelectTrigger id="regla-modalidad">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={HEREDA}>
                  {tipo ? `Del tipo (${ETIQUETA_MODALIDAD[tipo.modalidadPredeterminada]})` : "Del tipo"}
                </SelectItem>
                {MODALIDADES.map((modalidad) => (
                  <SelectItem key={modalidad} value={modalidad}>
                    {ETIQUETA_MODALIDAD[modalidad]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {errores.modalidad ? <p className="text-xs text-status-critical">{errores.modalidad}</p> : null}
          </div>

          <CampoNumero
            id="regla-aprobaciones"
            label="Aprobaciones requeridas"
            value={valores.aprobacionesRequeridas}
            onChange={(valor) => setValores((actual) => ({ ...actual, aprobacionesRequeridas: valor }))}
            placeholder={tipo ? `Del tipo: ${tipo.aprobacionesRequeridas}` : "Del tipo"}
            error={errores.aprobacionesRequeridas}
          />
          <CampoNumero
            id="regla-vigencia"
            label="Vence a las (horas)"
            value={valores.horasVigenciaSolicitud}
            onChange={(valor) => setValores((actual) => ({ ...actual, horasVigenciaSolicitud: valor }))}
            placeholder={tipo ? `Del tipo: ${tipo.horasVigenciaSolicitud}` : "Del tipo"}
            error={errores.horasVigenciaSolicitud}
          />
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={enviando}>
            Cancelar
          </Button>
          <Button onClick={() => void guardar()} disabled={enviando}>
            {enviando ? "Guardando…" : "Guardar"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
