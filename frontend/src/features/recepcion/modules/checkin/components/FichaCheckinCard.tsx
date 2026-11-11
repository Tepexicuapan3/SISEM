import type { ReactNode } from "react";
import { Globe } from "lucide-react";
import { Badge } from "@shared/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@shared/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@shared/ui/alert";
import type { FichaQRResponse } from "@api/types";
import { RECEPCION_SERVICE_PROFILES } from "@features/recepcion/shared/domain/recepcion.services";
import { formatFichaFechaHora } from "@features/recepcion/shared/utils/recepcion-format";

interface FichaCheckinCardProps {
  ficha: FichaQRResponse;
  title: ReactNode;
  description: ReactNode;
  /**
   * Alerta "esta cita ya fue verificada antes". Solo tiene sentido en el
   * flujo de QR, donde la ficha se muestra ANTES de confirmar (recepción
   * podría estar re-escaneando un comprobante ya usado). En el buscador de
   * nombre/folio el check-in ya se confirmó al hacer clic en el resultado,
   * así que no aplica — default `true` para no cambiar el comportamiento
   * existente del flujo de QR.
   */
  showYaVerificadaAlert?: boolean;
  /** Alertas/botones de acción específicos de cada flujo (QR vs búsqueda). */
  children?: ReactNode;
}

/**
 * Card con los datos de una cita para check-in — reusada por el flujo de QR
 * (`QrCheckinPage`) y por el buscador de check-in por nombre/folio
 * (`BusquedaCheckinPanel`). Mismo layout visual (badge "En línea", grid
 * folio/paciente/médico/consultorio/fecha/servicio/motivo) para que
 * recepción vea siempre la misma pantalla sin importar el método de
 * identificación usado.
 */
export function FichaCheckinCard({
  ficha,
  title,
  description,
  showYaVerificadaAlert = true,
  children,
}: FichaCheckinCardProps) {
  return (
    <Card className="max-w-xl">
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle>{title}</CardTitle>
            <CardDescription>{description}</CardDescription>
          </div>
          {ficha.origenCanal === "PORTAL" ? (
            <Badge variant="info" className="gap-1 shrink-0">
              <Globe className="size-3" /> En línea
            </Badge>
          ) : null}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {showYaVerificadaAlert && ficha.yaVerificada ? (
          <Alert variant="warning">
            <AlertTitle>Esta cita ya fue verificada antes</AlertTitle>
            <AlertDescription>
              Es posible que el check-in ya se haya registrado
              previamente. Si confirmas, el sistema lo indicará.
            </AlertDescription>
          </Alert>
        ) : null}

        <dl className="grid gap-3 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-[10px] font-semibold uppercase tracking-wide text-txt-muted">
              Folio
            </dt>
            <dd className="font-mono font-semibold text-txt-body">
              {ficha.folio}
            </dd>
          </div>
          <div>
            <dt className="text-[10px] font-semibold uppercase tracking-wide text-txt-muted">
              Paciente
            </dt>
            <dd className="font-medium text-txt-body">
              {ficha.paciente || "—"}
            </dd>
          </div>
          <div>
            <dt className="text-[10px] font-semibold uppercase tracking-wide text-txt-muted">
              Médico
            </dt>
            <dd className="font-medium text-txt-body">{ficha.medico}</dd>
          </div>
          <div>
            <dt className="text-[10px] font-semibold uppercase tracking-wide text-txt-muted">
              Consultorio
            </dt>
            <dd className="font-medium text-txt-body">
              {ficha.consultorio || "—"}
            </dd>
          </div>
          <div>
            <dt className="text-[10px] font-semibold uppercase tracking-wide text-txt-muted">
              Fecha y hora
            </dt>
            <dd className="font-medium text-txt-body">
              {formatFichaFechaHora(ficha.fechaHora)}
            </dd>
          </div>
          <div>
            <dt className="text-[10px] font-semibold uppercase tracking-wide text-txt-muted">
              Servicio
            </dt>
            <dd className="font-medium text-txt-body">
              {RECEPCION_SERVICE_PROFILES[ficha.servicioTipo]?.label ??
                ficha.servicioTipo}
            </dd>
          </div>
          {ficha.motivo ? (
            <div className="sm:col-span-2">
              <dt className="text-[10px] font-semibold uppercase tracking-wide text-txt-muted">
                Motivo
              </dt>
              <dd className="text-txt-body/80">{ficha.motivo}</dd>
            </div>
          ) : null}
        </dl>

        {children}
      </CardContent>
    </Card>
  );
}
