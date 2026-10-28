import type { ReactNode } from "react";
import { Badge } from "@shared/ui/badge";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@shared/ui/dialog";
import {
  describirEstatusSolicitud,
  formatFechaHora,
} from "@features/autorizaciones/domain/solicitud.format";
import {
  ESTATUS_DESTINATARIO,
  etiquetaEvento,
  hashCorto,
  SELECCION,
} from "@features/admin/modules/autorizaciones-auditoria/domain/auditoria.format";
import { useLineaDeTiempo } from "@features/admin/modules/autorizaciones-auditoria/queries/useAuditoria";
import { getCatalogErrorMessage } from "@features/admin/modules/catalogos/shared/utils/catalog-feedback";

interface LineaDeTiempoDialogProps {
  uuid: string | null;
  onClose: () => void;
}

function Seccion({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <section className="space-y-2">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-txt-muted">{titulo}</h3>
      {children}
    </section>
  );
}

function Dato({ etiqueta, children }: { etiqueta: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-txt-muted">{etiqueta}</dt>
      <dd className="text-sm text-txt-body break-words">{children ?? "—"}</dd>
    </div>
  );
}

export function LineaDeTiempoDialog({ uuid, onClose }: LineaDeTiempoDialogProps) {
  const { data, isLoading, error } = useLineaDeTiempo(uuid ?? undefined);

  return (
    <Dialog open={Boolean(uuid)} onOpenChange={(abierto) => !abierto && onClose()}>
      <DialogContent className="max-h-[90vh] w-[95vw] max-w-none overflow-y-auto rounded-3xl bg-paper sm:max-w-none lg:w-[56rem]">
        <DialogHeader>
          <DialogTitle>{data ? `Solicitud ${data.solicitud.folio}` : "Solicitud"}</DialogTitle>
          <DialogDescription>
            Trazabilidad completa: quién la creó, a quién se envió, cuándo se escaló y quién firmó, con su cédula, IP
            y el hash del contenido firmado.
          </DialogDescription>
        </DialogHeader>

        {isLoading ? <p className="text-sm text-txt-muted">Cargando…</p> : null}
        {error ? (
          <p className="text-sm text-status-critical">
            {getCatalogErrorMessage(error, "No se pudo cargar la línea de tiempo.", {})}
          </p>
        ) : null}

        {data ? (
          <div className="space-y-6">
            <Seccion titulo="Resumen">
              <dl className="grid gap-3 sm:grid-cols-3">
                <Dato etiqueta="Tipo">{data.solicitud.tipoNombre}</Dato>
                <Dato etiqueta="Centro">{`${data.solicitud.centroNombre} (${data.solicitud.clues})`}</Dato>
                <Dato etiqueta="Estatus">
                  <Badge variant={describirEstatusSolicitud(data.solicitud.estatus).variante}>
                    {describirEstatusSolicitud(data.solicitud.estatus).etiqueta}
                  </Badge>
                </Dato>
                <Dato etiqueta="Folio de origen">{data.solicitud.folioOrigen}</Dato>
                <Dato etiqueta="Conceptos">{data.solicitud.totalItems}</Dato>
                <Dato etiqueta="Aprobaciones">
                  {`${data.solicitud.aprobaciones ?? 0} de ${data.solicitud.aprobacionesRequeridas}`}
                </Dato>
                <Dato etiqueta="Hash del contenido">
                  <code title={data.solicitud.hashContenido} className="text-xs">
                    {hashCorto(data.solicitud.hashContenido)}
                  </code>
                </Dato>
              </dl>
            </Seccion>

            <Seccion titulo="Línea de tiempo">
              <ol className="space-y-2 border-l border-line-struct pl-4">
                {data.eventos.map((evento, indice) => (
                  <li key={`${evento.evento}-${indice}`} className="text-sm">
                    <span className="font-medium text-txt-body">{etiquetaEvento(evento.evento)}</span>
                    <span className="text-txt-muted">
                      {` · ${formatFechaHora(evento.fecha)} · ${evento.usuarioNombre ?? "Proceso automático"}`}
                    </span>
                  </li>
                ))}
              </ol>
            </Seccion>

            <Seccion titulo="Decisiones firmadas">
              {data.decisiones.length === 0 ? (
                <p className="text-sm text-txt-muted">Sin decisiones.</p>
              ) : (
                data.decisiones.map((decision, indice) => (
                  <dl
                    key={`${decision.fechaFirma}-${indice}`}
                    className="grid gap-3 rounded-xl border border-line-struct p-3 sm:grid-cols-3"
                  >
                    <Dato etiqueta="Autorizador">{decision.autorizadorNombre}</Dato>
                    <Dato etiqueta="Cédula">{decision.numeroCedula}</Dato>
                    <Dato etiqueta="Decisión">
                      <Badge variant={decision.decision === "APROBAR" ? "stable" : "critical"}>
                        {decision.decision === "APROBAR" ? "Aprobó" : "Rechazó"}
                      </Badge>
                    </Dato>
                    <Dato etiqueta="Firmada">{formatFechaHora(decision.fechaFirma)}</Dato>
                    <Dato etiqueta="Motivo">{decision.motivo}</Dato>
                    <Dato etiqueta="Detalle del motivo">{decision.descripcionMotivo}</Dato>
                    <Dato etiqueta="IP">{decision.ipOrigen}</Dato>
                    <Dato etiqueta="Navegador">{decision.agenteUsuario}</Dato>
                    <Dato etiqueta="Firma">
                      <Badge variant={decision.firmaVigente ? "stable" : "alert"}>
                        {decision.firmaVigente ? "Firma vigente" : "Firmó un contenido anterior"}
                      </Badge>
                    </Dato>
                  </dl>
                ))
              )}
            </Seccion>

            <Seccion titulo="Destinatarios">
              <ul className="space-y-1 text-sm">
                {data.destinatarios.map((destinatario, indice) => (
                  <li key={`${destinatario.autorizadorNombre}-${indice}`}>
                    <span className="font-medium text-txt-body">{destinatario.autorizadorNombre ?? "—"}</span>
                    <span className="text-txt-muted">
                      {` · ${SELECCION[destinatario.tipoSeleccion] ?? destinatario.tipoSeleccion}`}
                      {` · ${ESTATUS_DESTINATARIO[destinatario.estatus] ?? destinatario.estatus}`}
                      {` · enviada ${formatFechaHora(destinatario.fechaEnvio)}`}
                      {destinatario.fechaVisto ? ` · vista ${formatFechaHora(destinatario.fechaVisto)}` : ""}
                    </span>
                  </li>
                ))}
              </ul>
            </Seccion>
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
