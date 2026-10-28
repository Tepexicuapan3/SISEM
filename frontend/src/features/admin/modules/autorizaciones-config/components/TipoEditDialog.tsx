import { useState } from "react";
import { toast } from "sonner";
import type { Modalidad, TipoConfiguracion } from "@api/types/autorizaciones/configuracion.types";
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
import { Switch } from "@shared/ui/switch";
import { CampoNumero } from "@features/admin/modules/autorizaciones-config/components/CampoNumero";
import {
  DESCRIPCION_MODALIDAD,
  ETIQUETA_MODALIDAD,
} from "@features/admin/modules/autorizaciones-config/domain/configuracion.format";
import {
  erroresPorCampo,
  MODALIDADES,
  tipoSchema,
  type TipoFormValues,
} from "@features/admin/modules/autorizaciones-config/domain/configuracion.schemas";
import { useUpdateTipo } from "@features/admin/modules/autorizaciones-config/mutations/useConfiguracionMutations";
import { getConfiguracionErrorMessage } from "@features/admin/modules/autorizaciones-config/utils/configuracion.feedback";

interface TipoEditDialogProps {
  tipo: TipoConfiguracion;
  onClose: () => void;
}

const INTERRUPTORES: { campo: "permiteRechazo" | "rechazoResuelveSolicitud" | "requiereCedula"; label: string; ayuda: string }[] = [
  { campo: "permiteRechazo", label: "Permite rechazar", ayuda: "Si se apaga, el autorizador solo puede aprobar." },
  {
    campo: "rechazoResuelveSolicitud",
    label: "Un rechazo resuelve la solicitud",
    ayuda: "En modalidad múltiple, un solo rechazo la cierra como rechazada.",
  },
  {
    campo: "requiereCedula",
    label: "Exige cédula profesional",
    ayuda: "Solo autorizan quienes tienen cédula capturada en Usuarios. Aplica de inmediato.",
  },
];

/** El estado se reinicia remontando el dialogo: la pestaña le da una `key` por tipo. */
export function TipoEditDialog({ tipo, onClose }: TipoEditDialogProps) {
  const actualizar = useUpdateTipo();
  const [valores, setValores] = useState<TipoFormValues>({
    modalidadPredeterminada: tipo.modalidadPredeterminada,
    aprobacionesRequeridas: tipo.aprobacionesRequeridas,
    horasVigenciaSolicitud: tipo.horasVigenciaSolicitud,
    horasEscalamiento: tipo.horasEscalamiento,
    permiteRechazo: tipo.permiteRechazo,
    rechazoResuelveSolicitud: tipo.rechazoResuelveSolicitud,
    requiereCedula: tipo.requiereCedula,
  });
  const [errores, setErrores] = useState<Record<string, string>>({});

  const cambiar = <K extends keyof TipoFormValues>(campo: K, valor: TipoFormValues[K]) =>
    setValores((actual) => ({ ...actual, [campo]: valor }));

  const guardar = async () => {
    const resultado = tipoSchema.safeParse(valores);
    if (!resultado.success) {
      setErrores(erroresPorCampo(resultado.error.issues));
      return;
    }
    setErrores({});
    try {
      await actualizar.mutateAsync({ id: tipo.id, data: { ...resultado.data, version: tipo.version } });
      toast.success("Configuración guardada", { description: tipo.nombre });
      onClose();
    } catch (error) {
      toast.error("No se pudo guardar", { description: getConfiguracionErrorMessage(error, "Intenta nuevamente.") });
    }
  };

  return (
    <Dialog open onOpenChange={(abierto) => !abierto && onClose()}>
      <DialogContent className="max-w-xl rounded-3xl bg-paper sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>{tipo.nombre}</DialogTitle>
          <DialogDescription>
            Regla general del tipo para todos los centros. Los cambios aplican a las solicitudes nuevas; las
            pendientes terminan con las reglas con que se crearon.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="tipo-modalidad">Modalidad</Label>
            <Select
              value={valores.modalidadPredeterminada}
              onValueChange={(valor) => {
                const modalidad = valor as Modalidad;
                setValores((actual) => ({
                  ...actual,
                  modalidadPredeterminada: modalidad,
                  aprobacionesRequeridas: modalidad === "PRIMERO_VALIDO" ? 1 : actual.aprobacionesRequeridas,
                }));
              }}
            >
              <SelectTrigger id="tipo-modalidad">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {MODALIDADES.map((modalidad) => (
                  <SelectItem key={modalidad} value={modalidad}>
                    {ETIQUETA_MODALIDAD[modalidad]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-txt-muted">{DESCRIPCION_MODALIDAD[valores.modalidadPredeterminada]}</p>
          </div>

          <CampoNumero
            id="tipo-aprobaciones"
            label="Aprobaciones requeridas"
            value={valores.aprobacionesRequeridas}
            onChange={(valor) => cambiar("aprobacionesRequeridas", valor ?? 0)}
            disabled={valores.modalidadPredeterminada === "PRIMERO_VALIDO"}
            error={errores.aprobacionesRequeridas}
          />
          <CampoNumero
            id="tipo-vigencia"
            label="Vence a las (horas)"
            value={valores.horasVigenciaSolicitud}
            onChange={(valor) => cambiar("horasVigenciaSolicitud", valor ?? 0)}
            error={errores.horasVigenciaSolicitud}
          />
          <CampoNumero
            id="tipo-escalamiento"
            label="Escala sin respuesta a las (horas)"
            value={valores.horasEscalamiento}
            onChange={(valor) => cambiar("horasEscalamiento", valor ?? 0)}
            error={errores.horasEscalamiento}
            ayuda="Recordatorio y envío a los elegibles que faltaban."
          />

          <div className="space-y-3 sm:col-span-2">
            {INTERRUPTORES.map(({ campo, label, ayuda }) => (
              <div key={campo} className="flex items-start justify-between gap-4 rounded-xl border border-line-struct px-3 py-2">
                <div>
                  <Label htmlFor={`tipo-${campo}`}>{label}</Label>
                  <p className="text-xs text-txt-muted">{ayuda}</p>
                </div>
                <Switch
                  id={`tipo-${campo}`}
                  checked={valores[campo]}
                  onCheckedChange={(valor) => cambiar(campo, valor)}
                  disabled={campo === "rechazoResuelveSolicitud" && !valores.permiteRechazo}
                />
              </div>
            ))}
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={actualizar.isPending}>
            Cancelar
          </Button>
          <Button onClick={() => void guardar()} disabled={actualizar.isPending}>
            {actualizar.isPending ? "Guardando…" : "Guardar"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
