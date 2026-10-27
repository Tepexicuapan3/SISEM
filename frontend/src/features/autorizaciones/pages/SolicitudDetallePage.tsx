import { useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { AlertTriangle, ArrowLeft, Check, FileCheck2, Send, X } from "lucide-react";
import type { DecisionSolicitud } from "@api/types/autorizaciones/solicitudes.types";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import { Skeleton } from "@shared/ui/skeleton";
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import { SolicitudDecisionDialog } from "@features/autorizaciones/components/SolicitudDecisionDialog";
import { SolicitudEnviarDialog } from "@features/autorizaciones/components/SolicitudEnviarDialog";
import {
  describirEstatusSolicitud,
  formatFechaHora,
  MOTIVOS,
  ORIGENES,
  RUTA_BANDEJA,
  tiempoRestante,
} from "@features/autorizaciones/domain/solicitud.format";
import { useSolicitudDetalle } from "@features/autorizaciones/queries/useSolicitudes";
import { getSolicitudErrorMessage } from "@features/autorizaciones/utils/solicitud.feedback";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";

const DESTINATARIO: Record<string, string> = {
  NOTIFICADO: "Notificado",
  VISTO: "La vio",
  DECIDIO: "Decidió",
  ATENDIDA_POR_OTRO: "Atendida por otro",
  INHABILITADO: "Inhabilitado",
  RETIRADO: "Retirado",
};

function Tarjeta({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <section className="min-w-0 space-y-3 rounded-2xl border border-line-struct bg-paper p-4">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-txt-muted">{titulo}</h2>
      {children}
    </section>
  );
}

function Dato({ etiqueta, children }: { etiqueta: string; children: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-txt-muted">{etiqueta}</dt>
      <dd className="break-words text-sm text-txt-body">{children}</dd>
    </div>
  );
}

/**
 * Destino del boton "Revisar y autorizar" de la notificacion. Abrir esta
 * pagina NO autoriza nada: solo consulta (y queda en la bitacora). Decidir
 * exige el dialogo de confirmacion con contraseña.
 */
export function SolicitudDetallePage() {
  const { uuid } = useParams<{ uuid: string }>();
  const { hasEffectiveRequirement } = usePermissionDependencies();
  const puedeDecidir = hasEffectiveRequirement({ allOf: ["clinico:autorizaciones:decide"] });
  const puedeEnviar = hasEffectiveRequirement({ allOf: ["clinico:autorizaciones:notify"] });

  const { data, isLoading, error, refetch } = useSolicitudDetalle(uuid);
  const [decision, setDecision] = useState<DecisionSolicitud | null>(null);
  const [enviando, setEnviando] = useState(false);

  const volver = (
    <Link to={RUTA_BANDEJA} className="inline-flex items-center gap-1 text-sm text-txt-muted hover:text-txt-body">
      <ArrowLeft className="size-4" />
      Bandeja de solicitudes
    </Link>
  );

  if (isLoading) {
    return (
      <div className="space-y-4 p-4 sm:p-6">
        {volver}
        <Skeleton className="h-24" />
        <Skeleton className="h-64" />
      </div>
    );
  }

  const solicitud = data?.solicitud;
  if (error || !solicitud) {
    return (
      <div className="space-y-4 p-4 sm:p-6">
        {volver}
        <div className="rounded-2xl border border-line-struct bg-paper p-6 text-center">
          <AlertTriangle className="mx-auto size-8 text-status-critical" />
          <p className="mt-3 font-semibold">No se pudo abrir la solicitud</p>
          <p className="mt-1 text-sm text-txt-muted">{getSolicitudErrorMessage(error, "Intenta nuevamente.")}</p>
          <Button variant="outline" size="sm" className="mt-4" onClick={() => void refetch()}>
            Reintentar
          </Button>
        </div>
      </div>
    );
  }

  const estatus = describirEstatusSolicitud(solicitud.estatus);
  const restante = solicitud.estatus === "PENDIENTE" ? tiempoRestante(solicitud.fechaLimite) : null;
  const { acciones } = solicitud;
  const mostrarAprobar = puedeDecidir && acciones.puedeAprobar;
  const mostrarRechazar = puedeDecidir && acciones.puedeRechazar;
  const mostrarEnviar = puedeEnviar && solicitud.estatus === "PENDIENTE";

  return (
    <div className="@container space-y-4 p-4 sm:p-6">
      {volver}

      {/* Encabezado */}
      <header className="flex flex-wrap items-start justify-between gap-4 rounded-2xl border border-line-struct bg-paper p-4 sm:p-5">
        <div className="flex min-w-0 items-start gap-3">
          <div className="flex size-12 shrink-0 items-center justify-center rounded-2xl bg-surface-hover">
            <FileCheck2 className="size-6" />
          </div>
          <div className="min-w-0">
            <h1 className="text-lg font-semibold tabular-nums text-txt-body">{solicitud.folio}</h1>
            <p className="text-sm text-txt-muted">
              {solicitud.tipo.nombre} · {solicitud.centro.nombre} ({solicitud.centro.clues})
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <Badge variant={estatus.variante}>{estatus.etiqueta}</Badge>
              {solicitud.prioridad === "URGENTE" ? <Badge variant="critical">Urgente</Badge> : null}
              {restante ? (
                <span className={restante.urgente ? "text-xs text-status-critical" : "text-xs text-txt-muted"}>
                  {restante.texto}
                </span>
              ) : null}
            </div>
          </div>
        </div>

        {mostrarAprobar || mostrarRechazar || mostrarEnviar ? (
          <div className="flex flex-wrap gap-2">
            {mostrarEnviar ? (
              <Button variant="outline" onClick={() => setEnviando(true)}>
                <Send className="size-4" />
                Enviar a autorizadores
              </Button>
            ) : null}
            {mostrarRechazar ? (
              <Button variant="outline" onClick={() => setDecision("RECHAZAR")}>
                <X className="size-4" />
                Rechazar
              </Button>
            ) : null}
            {mostrarAprobar ? (
              <Button onClick={() => setDecision("APROBAR")}>
                <Check className="size-4" />
                Autorizar
              </Button>
            ) : null}
          </div>
        ) : null}
      </header>

      {solicitud.estatus === "PENDIENTE" && acciones.mensajeBloqueo ? (
        <AdminReadOnlyNotice message={acciones.mensajeBloqueo} />
      ) : null}
      {solicitud.estatus === "PENDIENTE" && !puedeDecidir && acciones.puedeAprobar ? (
        <AdminReadOnlyNotice message="Tu rol no tiene permiso para decidir solicitudes de autorización." />
      ) : null}
      {solicitud.sinElegibles && solicitud.estatus === "PENDIENTE" ? (
        <AdminReadOnlyNotice message="Ningún autorizador vigente cubre este tipo y centro. Pide al área responsable que asigne uno." />
      ) : null}

      <div className="grid gap-4 @3xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Tarjeta titulo="Datos de la solicitud">
          <dl className="grid gap-3 @xl:grid-cols-2">
            <Dato etiqueta="Origen">
              {ORIGENES[solicitud.tipoOrigen] ?? solicitud.tipoOrigen}
              {solicitud.folioOrigen ? ` · ${solicitud.folioOrigen}` : ""}
            </Dato>
            <Dato etiqueta="Por qué requiere autorización">
              {solicitud.motivos.map((m) => MOTIVOS[m] ?? m).join(", ") || "—"}
            </Dato>
            <Dato etiqueta="Solicitada por">{solicitud.solicitadaPor?.name ?? "—"}</Dato>
            <Dato etiqueta="Fecha de solicitud">{formatFechaHora(solicitud.fechaCreacion)}</Dato>
            <Dato etiqueta="Fecha límite">{formatFechaHora(solicitud.fechaLimite)}</Dato>
            <Dato etiqueta="Modalidad">
              {solicitud.modalidad === "MULTIPLE"
                ? `Varias aprobaciones (${solicitud.aprobacionesVigentes} de ${solicitud.aprobacionesRequeridas})`
                : "Primer autorizador válido"}
            </Dato>
            {solicitud.resueltaPor ? (
              <Dato etiqueta="Resuelta por">
                {solicitud.resueltaPor.name} · {formatFechaHora(solicitud.fechaResolucion)}
              </Dato>
            ) : null}
            {solicitud.motivoCierre ? (
              <Dato etiqueta="Motivo">
                {solicitud.motivoCierre.descripcion}
                {solicitud.descripcionMotivoCierre ? ` — ${solicitud.descripcionMotivoCierre}` : ""}
              </Dato>
            ) : null}
          </dl>
        </Tarjeta>

        <Tarjeta titulo="Qué se autoriza">
          {solicitud.items.length === 0 ? (
            <p className="text-sm text-txt-muted">Sin elementos.</p>
          ) : (
            <ul className="divide-y divide-line-hairline">
              {solicitud.items.map((item, indice) => (
                <li key={`${item.descripcion}-${indice}`} className="flex flex-wrap items-baseline justify-between gap-2 py-2">
                  <span className="min-w-0 text-sm text-txt-body">{item.descripcion}</span>
                  <span className="text-xs text-txt-muted">
                    {item.cantidad !== null ? `Cant. ${item.cantidad}` : ""}
                    {item.motivo ? ` · ${MOTIVOS[item.motivo] ?? item.motivo}` : ""}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Tarjeta>

        <Tarjeta titulo="A quién se envió">
          {solicitud.destinatarios.length === 0 ? (
            <p className="text-sm text-txt-muted">Todavía no se envió a ningún autorizador.</p>
          ) : (
            <ul className="space-y-2">
              {solicitud.destinatarios.map((d) => (
                <li key={d.autorizador.id} className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-sm text-txt-body">{d.autorizador.nombre}</span>
                  <span className="flex gap-1">
                    {d.esObligatorio ? <Badge variant="info">Obligatorio</Badge> : null}
                    <Badge variant="outline">{DESTINATARIO[d.estatus] ?? d.estatus}</Badge>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Tarjeta>

        <Tarjeta titulo="Decisiones firmadas">
          {solicitud.decisiones.length === 0 ? (
            <p className="text-sm text-txt-muted">Aún no hay decisiones.</p>
          ) : (
            <ul className="space-y-3">
              {solicitud.decisiones.map((d, indice) => (
                <li key={`${d.autorizador.id}-${indice}`} className="space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={d.decision === "APROBAR" ? "stable" : "critical"}>
                      {d.decision === "APROBAR" ? "Aprobó" : "Rechazó"}
                    </Badge>
                    <span className="text-sm text-txt-body">{d.autorizador.nombre}</span>
                    <span className="text-xs text-txt-muted">{formatFechaHora(d.fechaFirma)}</span>
                    {!d.vigente ? <Badge variant="outline">Ya no cuenta (el documento cambió)</Badge> : null}
                  </div>
                  {d.motivo ? (
                    <p className="text-xs text-txt-muted">
                      {d.motivo.descripcion}
                      {d.descripcionMotivo ? ` — ${d.descripcionMotivo}` : ""}
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </Tarjeta>
      </div>

      {decision ? (
        <SolicitudDecisionDialog
          key={`${decision}-${solicitud.version}`}
          decision={decision}
          solicitud={solicitud}
          onClose={() => setDecision(null)}
        />
      ) : null}
      {enviando ? <SolicitudEnviarDialog solicitud={solicitud} onClose={() => setEnviando(false)} /> : null}
    </div>
  );
}

export default SolicitudDetallePage;
