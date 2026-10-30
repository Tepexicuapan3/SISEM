import { useEffect, useState } from "react";
import { toast } from "sonner";
import { CalendarX2, Users } from "lucide-react";
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
import { Label } from "@shared/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@shared/ui/select";
import { ApiError } from "@api/utils/errors";
import type { Adscripcion, OpcionConsultorio, PatientMember, PrevisualizarAdscripcionResponse } from "@api/types";
import { useMotivosCancelacion } from "@features/recepcion/modules/citas/queries/useMotivosCancelacion";
import { useOpcionesAdscripcion } from "@features/recepcion/modules/adscripcion/queries/useAdscripcionQueries";
import {
  useAbrirPaciente,
  useAdscribir,
  usePrevisualizarAdscripcion,
} from "@features/recepcion/modules/adscripcion/mutations/useAdscripcionMutations";
import { etiquetaConsultorio } from "@features/recepcion/modules/adscripcion/domain/adscripcionEstado";

/** Nombre del motivo que siembra la migración recepcion/0034. */
export const MOTIVO_CAMBIO_CONSULTORIO = "Cambio de consultorio familiar";

const formatoFecha = (iso: string) =>
  new Date(iso).toLocaleString("es-MX", {
    weekday: "short",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });

const agruparPorTurno = (opciones: OpcionConsultorio[]) => {
  const grupos = new Map<string, OpcionConsultorio[]>();
  for (const opcion of opciones) {
    grupos.set(opcion.turno, [...(grupos.get(opcion.turno) ?? []), opcion]);
  }
  return [...grupos.entries()];
};

interface ReasignarAdscripcionDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  member: PatientMember | null;
  onAdscrito?: (adscripcion: Adscripcion) => void;
}

/**
 * P-03 · Panel "Revisar y reasignar": comparación, turno y consultorio con la
 * sugerida marcada, advertencia de citas a cancelar y confirmación.
 */
export const ReasignarAdscripcionDialog = ({
  open,
  onOpenChange,
  member,
  onAdscrito,
}: ReasignarAdscripcionDialogProps) => {
  const [idPaciente, setIdPaciente] = useState<number | null>(null);
  const [consultorioId, setConsultorioId] = useState<number | null>(null);
  const [motivoId, setMotivoId] = useState<string>("");
  const [vista, setVista] = useState<PrevisualizarAdscripcionResponse | null>(null);

  const abrirPaciente = useAbrirPaciente();
  const previsualizar = usePrevisualizarAdscripcion();
  const adscribir = useAdscribir();
  const { data: opcionesData, isLoading: cargandoOpciones } = useOpcionesAdscripcion(open ? idPaciente : null);
  const { data: motivosData } = useMotivosCancelacion({ enabled: open });

  const opciones = opcionesData?.opciones ?? [];
  const sugerida = opciones.find((o) => o.sugerida) ?? null;
  const citas = vista?.citasACancelar ?? [];

  // Al abrir: el idPaciente del miembro, o se abre su registro si nunca se atendió.
  useEffect(() => {
    if (!open || !member) return;
    setConsultorioId(null);
    setVista(null);
    if (member.idPaciente) {
      setIdPaciente(member.idPaciente);
      return;
    }
    setIdPaciente(null);
    abrirPaciente
      .mutateAsync({ noExp: member.noExp, pkNum: member.pkNum })
      .then((r) => setIdPaciente(r.idPaciente))
      .catch(() => toast.error("No se pudo abrir el registro del paciente."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, member?.noExp, member?.pkNum, member?.idPaciente]);

  // La sugerida viene elegida.
  useEffect(() => {
    if (consultorioId == null && sugerida) setConsultorioId(sugerida.consultorioId);
  }, [sugerida, consultorioId]);

  // Motivo precargado: "Cambio de consultorio familiar".
  useEffect(() => {
    if (motivoId) return;
    const motivo = motivosData?.results.find((m) => m.name === MOTIVO_CAMBIO_CONSULTORIO);
    if (motivo) setMotivoId(String(motivo.id));
  }, [motivosData, motivoId]);

  const cargarVista = (id: number | null, consultorio: number | null) => {
    if (id == null || consultorio == null) return;
    previsualizar.mutate(
      { idPaciente: id, consultorioId: consultorio },
      { onSuccess: setVista, onError: () => setVista(null) },
    );
  };

  // Cada consultorio elegido se previsualiza (qué citas se cancelarían).
  useEffect(() => {
    cargarVista(idPaciente, consultorioId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idPaciente, consultorioId]);

  const confirmar = async () => {
    if (idPaciente == null || consultorioId == null || !vista) return;
    try {
      const resultado = await adscribir.mutateAsync({
        idPaciente,
        consultorioId,
        idAdscripcionEsperada: vista.idAdscripcionActual,
        citasACancelar: citas.map((c) => c.idCita),
        motivoCancelacionId: citas.length > 0 && motivoId ? Number(motivoId) : null,
        origen: "CHECKIN",
        fueSugerida: consultorioId === sugerida?.consultorioId,
      });
      toast.success("Consultorio familiar asignado", {
        description:
          resultado.citasCanceladas.length > 0
            ? `Se cancelaron ${resultado.citasCanceladas.length} citas; quedan en "Citas por reagendar".`
            : undefined,
      });
      onAdscrito?.(resultado.adscripcion);
      onOpenChange(false);
    } catch (error) {
      if (error instanceof ApiError && error.code === "CITAS_MODIFICADAS") {
        toast.error("Las citas del paciente cambiaron", { description: "Revise la lista y confirme otra vez." });
        cargarVista(idPaciente, consultorioId);
        return;
      }
      toast.error("No se pudo asignar el consultorio", {
        description: error instanceof ApiError ? error.message : "Intente nuevamente.",
      });
    }
  };

  const faltaMotivo = citas.length > 0 && !motivoId;
  const ocupado = adscribir.isPending || previsualizar.isPending || abrirPaciente.isPending;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Consultorio familiar</DialogTitle>
          <DialogDescription>{member?.nombre}</DialogDescription>
        </DialogHeader>

        {vista?.adscripcionActual ? (
          <p className="text-sm text-txt-muted">
            Actual:{" "}
            <span className="font-medium text-txt-body">
              {etiquetaConsultorio({ numero: vista.adscripcionActual.numeroConsultorio, turno: vista.adscripcionActual.turno })}
            </span>{" "}
            · {vista.adscripcionActual.centro}
          </p>
        ) : null}

        <div className="space-y-3">
          {cargandoOpciones || idPaciente == null ? (
            <p className="text-sm text-txt-muted">Buscando consultorios...</p>
          ) : opciones.length === 0 ? (
            <p className="text-sm text-status-critical" role="alert">
              No hay consultorios familiares con lugar en la clínica del paciente. Avise al administrador.
            </p>
          ) : (
            <div role="radiogroup" aria-label="Consultorio" className="space-y-3">
              {agruparPorTurno(opciones).map(([turno, grupo]) => (
                <div key={turno} className="space-y-1.5">
                  <p className="text-xs font-semibold uppercase tracking-wide text-txt-muted">{turno}</p>
                  {grupo.map((opcion) => {
                    const elegida = consultorioId === opcion.consultorioId;
                    return (
                      <button
                        key={opcion.consultorioId}
                        type="button"
                        role="radio"
                        aria-checked={elegida}
                        aria-label={`${etiquetaConsultorio(opcion)}, ${opcion.carga} pacientes`}
                        onClick={() => setConsultorioId(opcion.consultorioId)}
                        className={[
                          "flex w-full items-center justify-between gap-3 rounded-xl border px-3 py-2 text-left transition-colors",
                          elegida ? "border-primary bg-primary/5" : "border-line-struct hover:bg-subtle/40",
                        ].join(" ")}
                      >
                        <span className="text-sm font-medium text-txt-body">
                          {etiquetaConsultorio(opcion)}
                          <span className="ml-2 text-xs font-normal text-txt-muted">
                            {opcion.carga} pacientes
                            {opcion.capacidadMaxima != null ? ` de ${opcion.capacidadMaxima}` : ""}
                          </span>
                        </span>
                        <span className="flex gap-1">
                          {opcion.esDeLaFamilia ? (
                            <Badge variant="info" className="gap-1">
                              <Users className="size-3" />
                              Su familia
                            </Badge>
                          ) : null}
                          {opcion.sugerida ? <Badge variant="stable">Sugerido</Badge> : null}
                        </span>
                      </button>
                    );
                  })}
                </div>
              ))}
            </div>
          )}

          {vista?.sinCambios ? (
            <p className="text-sm text-txt-muted" role="status">
              Ya es su consultorio familiar; no hay cambios.
            </p>
          ) : null}

          {citas.length > 0 ? (
            <div className="space-y-2 rounded-xl border border-status-alert/40 bg-status-alert/10 px-3 py-2.5" role="alert">
              <p className="flex items-center gap-2 text-sm font-semibold text-status-alert">
                <CalendarX2 className="size-4" />
                Se cancelarán {citas.length} {citas.length === 1 ? "cita" : "citas"} del consultorio anterior
              </p>
              <ul className="space-y-0.5 pl-6 text-xs text-txt-body">
                {citas.map((cita) => (
                  <li key={cita.idCita} className="list-disc">
                    {formatoFecha(cita.fechaHora)} · {cita.consultorio ?? "Sin consultorio"} · {cita.folio}
                  </li>
                ))}
              </ul>
              <p className="text-xs text-txt-muted">Quedarán en "Citas por reagendar" para el consultorio nuevo.</p>
              <div className="space-y-1">
                <Label className="text-xs">Motivo de cancelación</Label>
                <Select value={motivoId} onValueChange={setMotivoId}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Selecciona el motivo" />
                  </SelectTrigger>
                  <SelectContent>
                    {(motivosData?.results ?? []).map((motivo) => (
                      <SelectItem key={motivo.id} value={String(motivo.id)}>
                        {motivo.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          ) : null}
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Ahora no
          </Button>
          <Button
            type="button"
            onClick={() => void confirmar()}
            disabled={ocupado || consultorioId == null || !vista || vista.sinCambios || faltaMotivo}
          >
            Confirmar consultorio
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
