import { useEffect, useRef, useState } from "react";
import { CheckCircle2, Globe, Loader2, RotateCcw, Search, UserRound } from "lucide-react";
import { toast } from "sonner";
import { Alert, AlertDescription, AlertTitle } from "@shared/ui/alert";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@shared/ui/card";
import { Input } from "@shared/ui/input";
import { Label } from "@shared/ui/label";
import { useDebounce } from "@shared/hooks/useDebounce";
import type { CheckinCandidato, FichaQRResponse } from "@api/types";
import { useCheckinCandidatos } from "@features/recepcion/modules/checkin/queries/useCheckinCandidatos";
import { useConfirmarFolioCheckin } from "@features/recepcion/modules/checkin/mutations/useConfirmarFolioCheckin";
import {
  buildConfirmedFichaFromCandidato,
  resolveCheckinSearchParams,
} from "@features/recepcion/modules/checkin/domain/checkinSearch";
import { resolveQrCheckinErrorMessage } from "@features/recepcion/modules/checkin/domain/qrCheckin.errors";
import {
  autorizacionVigenciaCompleta,
  buildConfirmarCheckinOptions,
  esErrorSinVigencia,
} from "@features/recepcion/modules/checkin/domain/checkinVigencia";
import { AutorizacionVigenciaField } from "@features/recepcion/modules/checkin/components/AutorizacionVigenciaField";
import {
  FichaCheckinCard,
  formatFichaFechaHora,
} from "@features/recepcion/modules/checkin/components/FichaCheckinCard";

interface BusquedaCheckinPanelProps {
  canConfirmCheckin: boolean;
}

/**
 * Buscador de check-in por nombre del paciente o folio de la cita —
 * alternativa al escaneo de QR para cuando el paciente no trae el
 * comprobante a mano. Ver `resolveCheckinSearchParams` para la decisión de
 * usar un solo campo con detección automática de formato en vez de un
 * selector explícito "nombre" / "folio".
 *
 * A diferencia del flujo de QR (verificar -> mostrar ficha -> confirmar),
 * acá no hay payload firmado que re-validar en dos pasos: la fila de la
 * lista YA es la confirmación visual (folio, paciente, hora, consultorio,
 * médico a la vista), así que un clic dispara directamente
 * `POST /citas/checkin/confirmar-folio` y se muestra el resultado con el
 * mismo `FichaCheckinCard` que usa el flujo de QR.
 */
export function BusquedaCheckinPanel({ canConfirmCheckin }: BusquedaCheckinPanelProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  const [query, setQuery] = useState("");
  const [confirmingFolio, setConfirmingFolio] = useState<string | null>(null);
  const [confirmedFicha, setConfirmedFicha] = useState<FichaQRResponse | null>(null);
  const [confirmError, setConfirmError] = useState<string | null>(null);
  // Candidato sin vigencia esperando el motivo u oficio de Capital Humano.
  const [pendienteVigencia, setPendienteVigencia] = useState<CheckinCandidato | null>(null);
  const [autorizacionVigencia, setAutorizacionVigencia] = useState("");

  const debouncedQuery = useDebounce(query, 400);
  const searchParams = confirmedFicha ? null : resolveCheckinSearchParams(debouncedQuery);

  const candidatosQuery = useCheckinCandidatos(searchParams);
  const confirmarFolio = useConfirmarFolioCheckin();

  useEffect(() => {
    if (!confirmedFicha) {
      inputRef.current?.focus();
    }
  }, [confirmedFicha]);

  const handleReset = () => {
    setQuery("");
    setConfirmedFicha(null);
    setConfirmError(null);
    setConfirmingFolio(null);
    cerrarAutorizacion();
    requestAnimationFrame(() => inputRef.current?.focus());
  };

  const cerrarAutorizacion = () => {
    setPendienteVigencia(null);
    setAutorizacionVigencia("");
  };

  const confirmarCandidato = async (candidato: CheckinCandidato) => {
    setConfirmError(null);
    setConfirmingFolio(candidato.folio);

    try {
      const result = await confirmarFolio.mutateAsync({
        folio: candidato.folio,
        ...buildConfirmarCheckinOptions(candidato.vigenciaActiva, autorizacionVigencia),
      });
      const ficha = buildConfirmedFichaFromCandidato(candidato, result);
      setConfirmedFicha(ficha);
      cerrarAutorizacion();
      toast.success("Check-in confirmado", {
        description: `${result.paciente || candidato.pacienteNombre} — folio ${result.folio}.`,
      });
    } catch (error) {
      if (esErrorSinVigencia(error)) {
        // Perdió la vigencia después de la búsqueda: se pide la autorización.
        setPendienteVigencia({ ...candidato, vigenciaActiva: false });
      }
      setConfirmError(resolveQrCheckinErrorMessage(error));
    } finally {
      setConfirmingFolio(null);
    }
  };

  const handleSelectCandidato = (candidato: CheckinCandidato) => {
    if (!canConfirmCheckin || confirmingFolio) {
      return;
    }

    if (!candidato.vigenciaActiva) {
      setConfirmError(null);
      setAutorizacionVigencia("");
      setPendienteVigencia(candidato);
      return;
    }

    cerrarAutorizacion();
    void confirmarCandidato(candidato);
  };

  const candidatos = candidatosQuery.data?.candidatos ?? [];
  const showEmptyState =
    !confirmedFicha &&
    searchParams !== null &&
    candidatosQuery.isSuccess &&
    candidatos.length === 0;

  return (
    <div className="space-y-4">
      <Card className="max-w-xl">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Search className="size-4" />
            Buscar cita de hoy
          </CardTitle>
          <CardDescription>
            Escribe el nombre del paciente o el folio de la cita (ej.
            CIT-XXXXXXXXXX). Solo se muestran citas de hoy pendientes de
            check-in.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="checkin-search-input">Nombre o folio</Label>
            <Input
              id="checkin-search-input"
              ref={inputRef}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Nombre del paciente o folio CIT-..."
              disabled={!!confirmedFicha}
              autoComplete="off"
            />
          </div>

          {!canConfirmCheckin ? (
            <Alert variant="warning">
              <AlertTitle>Sin permiso para confirmar</AlertTitle>
              <AlertDescription>
                Tu usuario no tiene permiso para registrar check-ins. Pide a
                un compañero con permisos de recepción que confirme.
              </AlertDescription>
            </Alert>
          ) : null}

          {confirmError ? (
            <Alert variant="critical">
              <AlertTitle>No se pudo confirmar el check-in</AlertTitle>
              <AlertDescription>{confirmError}</AlertDescription>
            </Alert>
          ) : null}

          {!confirmedFicha && candidatosQuery.isFetching ? (
            <p className="flex items-center gap-2 text-sm text-txt-muted">
              <Loader2 className="size-4 animate-spin" /> Buscando...
            </p>
          ) : null}

          {!confirmedFicha && candidatosQuery.isError ? (
            <Alert variant="critical">
              <AlertTitle>No se pudo buscar</AlertTitle>
              <AlertDescription>
                {resolveQrCheckinErrorMessage(candidatosQuery.error)}
              </AlertDescription>
            </Alert>
          ) : null}

          {showEmptyState ? (
            <p className="text-sm text-txt-muted">
              No se encontraron citas de hoy pendientes de check-in con ese
              criterio.
            </p>
          ) : null}

          {!confirmedFicha && candidatos.length > 0 ? (
            <ul className="divide-y divide-line-hairline rounded-xl border border-line-struct">
              {candidatos.map((candidato) => {
                const isConfirmingThis = confirmingFolio === candidato.folio;
                return (
                  <li key={candidato.folio}>
                    <button
                      type="button"
                      onClick={() => handleSelectCandidato(candidato)}
                      disabled={!canConfirmCheckin || !!confirmingFolio}
                      className="flex w-full items-start justify-between gap-3 px-4 py-3 text-left transition-colors hover:bg-subtle disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      <div className="flex items-start gap-3">
                        <UserRound className="mt-0.5 size-4 shrink-0 text-txt-muted" />
                        <div>
                          <p className="flex items-center gap-2 font-medium text-txt-body">
                            {candidato.pacienteNombre || "—"}
                            {candidato.origenCanal === "PORTAL" ? (
                              <Badge variant="info" className="gap-1 text-xs">
                                <Globe className="size-3" /> En línea
                              </Badge>
                            ) : null}
                            {!candidato.vigenciaActiva ? (
                              <Badge variant="alert" className="text-xs">
                                Sin vigencia
                              </Badge>
                            ) : null}
                          </p>
                          <p className="text-xs text-txt-muted">
                            <span className="font-mono">{candidato.folio}</span>
                            {" · "}
                            {formatFichaFechaHora(candidato.fechaHora)}
                            {" · "}
                            {candidato.medicoNombre}
                            {candidato.consultorioNombre
                              ? ` · ${candidato.consultorioNombre}`
                              : ""}
                          </p>
                        </div>
                      </div>
                      {isConfirmingThis ? (
                        <Loader2 className="size-4 shrink-0 animate-spin text-txt-muted" />
                      ) : null}
                    </button>
                  </li>
                );
              })}
            </ul>
          ) : null}

          {!confirmedFicha && pendienteVigencia ? (
            <div className="space-y-3 rounded-xl border border-line-struct p-4">
              <p className="text-sm text-txt-body">
                <span className="font-medium">{pendienteVigencia.pacienteNombre || "—"}</span>
                {" · "}
                <span className="font-mono">{pendienteVigencia.folio}</span>
              </p>
              <AutorizacionVigenciaField
                id="busqueda-autorizacion-vigencia"
                value={autorizacionVigencia}
                onChange={setAutorizacionVigencia}
                disabled={!!confirmingFolio}
              />
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  onClick={() => void confirmarCandidato(pendienteVigencia)}
                  disabled={
                    !canConfirmCheckin ||
                    !!confirmingFolio ||
                    !autorizacionVigenciaCompleta(false, autorizacionVigencia)
                  }
                >
                  {confirmingFolio ? (
                    <>
                      <Loader2 className="size-4 animate-spin" /> Confirmando...
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="size-4" /> Confirmar check-in
                    </>
                  )}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={cerrarAutorizacion}
                  disabled={!!confirmingFolio}
                >
                  Cancelar
                </Button>
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>

      {confirmedFicha ? (
        <FichaCheckinCard
          ficha={confirmedFicha}
          title="Check-in confirmado"
          description="El paciente ya quedó registrado en la fila de espera."
          showYaVerificadaAlert={false}
        >
          <Alert variant="success">
            <CheckCircle2 className="size-4" />
            <AlertTitle>Check-in registrado correctamente</AlertTitle>
            <AlertDescription>
              Puedes buscar al siguiente paciente cuando quieras.
            </AlertDescription>
          </Alert>

          <Button type="button" variant="ghost" onClick={handleReset} className="mt-4">
            <RotateCcw className="size-4" /> Buscar otro paciente
          </Button>
        </FichaCheckinCard>
      ) : null}
    </div>
  );
}
