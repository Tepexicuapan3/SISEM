import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { CheckCircle2, Loader2, QrCode, RotateCcw, ScanLine, Search } from "lucide-react";
import { toast } from "sonner";
import { BarcodeScannerInput } from "@shared/ui/BarcodeScannerInput";
import { Button } from "@shared/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@shared/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@shared/ui/alert";
import { Label } from "@shared/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@shared/ui/tabs";
import type { FichaQRResponse } from "@api/types";
import { useVerificarQR } from "@features/recepcion/modules/checkin/mutations/useVerificarQR";
import { useConfirmarQRCheckin } from "@features/recepcion/modules/checkin/mutations/useConfirmarQRCheckin";
import { resolveQrCheckinErrorMessage } from "@features/recepcion/modules/checkin/domain/qrCheckin.errors";
import { RECEPCION_WRITE_PERMISSION_REQUIREMENT } from "@features/recepcion/shared/domain/recepcion.permissions";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import { FichaCheckinCard } from "@features/recepcion/modules/checkin/components/FichaCheckinCard";
import { BusquedaCheckinPanel } from "@features/recepcion/modules/checkin/components/BusquedaCheckinPanel";
import { AutorizacionVigenciaField } from "@features/recepcion/modules/checkin/components/AutorizacionVigenciaField";
import { ConflictoCheckin } from "@features/recepcion/modules/adscripcion/components/ConflictoCheckin";
import {
  conflictoConsultorioFamiliar,
  type ConflictoConsultorioFamiliar,
} from "@features/recepcion/modules/adscripcion/domain/adscripcionEstado";
import {
  autorizacionVigenciaCompleta,
  buildConfirmarCheckinOptions,
  esErrorSinVigencia,
} from "@features/recepcion/modules/checkin/domain/checkinVigencia";

const CHECKIN_TAB = {
  QR: "qr",
  BUSQUEDA: "busqueda",
} as const;

/**
 * Check-in por QR (Fase 7 "Citas en Línea").
 *
 * Flujo: el personal escanea el comprobante con un lector físico
 * (keyboard-wedge: "tipea" el código y envía Enter) o lo pega a mano si el
 * lector falla. Cada envío llama a `POST /citas/verificar-qr` para mostrar
 * la ficha y confirmar visualmente al paciente; "Confirmar check-in" reenvía
 * el MISMO payload crudo a `POST /citas/verificar-qr/confirmar` (el backend
 * re-valida la firma HMAC en cada paso, nunca se reenvía un folio suelto).
 *
 * Pensado para uso repetido: al confirmar (o cancelar) se limpia el campo y
 * vuelve a enfocarse para el siguiente paciente.
 */
export const QrCheckinPage = () => {
  const inputRef = useRef<HTMLInputElement>(null);

  const [payloadValue, setPayloadValue] = useState("");
  const [verifiedPayload, setVerifiedPayload] = useState<string | null>(null);
  const [ficha, setFicha] = useState<FichaQRResponse | null>(null);
  const [verifyError, setVerifyError] = useState<string | null>(null);
  const [confirmError, setConfirmError] = useState<string | null>(null);
  const [autorizacionVigencia, setAutorizacionVigencia] = useState("");
  const [conflictoP03, setConflictoP03] = useState<ConflictoConsultorioFamiliar | null>(null);

  const { hasCapability } = usePermissionDependencies();
  const canConfirmCheckin = hasCapability(
    "flow.recepcion.queue.write",
    RECEPCION_WRITE_PERMISSION_REQUIREMENT,
  );

  const verificarQR = useVerificarQR();
  const confirmarCheckin = useConfirmarQRCheckin();

  const isVerifying = verificarQR.isPending;
  const isConfirming = confirmarCheckin.isPending;

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const focusInputSoon = () => {
    requestAnimationFrame(() => inputRef.current?.focus());
  };

  const resetForNextScan = () => {
    setPayloadValue("");
    setVerifiedPayload(null);
    setFicha(null);
    setConflictoP03(null);
    setVerifyError(null);
    setConfirmError(null);
    setAutorizacionVigencia("");
    focusInputSoon();
  };

  const handleVerify = async (rawPayload: string) => {
    const payload = rawPayload.trim();
    if (!payload) {
      return;
    }

    setVerifyError(null);
    setConfirmError(null);
    setFicha(null);
    setVerifiedPayload(null);
    setAutorizacionVigencia("");

    try {
      const result = await verificarQR.mutateAsync(payload);
      setFicha(result);
      setVerifiedPayload(payload);
    } catch (error) {
      setVerifyError(resolveQrCheckinErrorMessage(error));
      setPayloadValue("");
      focusInputSoon();
    }
  };

  // Fallback para cuando el código se pega a mano: BarcodeScannerInput solo
  // dispara `onScan` si detecta las teclas del payload (scanner o tipeo
  // caracter por caracter). Un paste no genera esos keydown individuales, así
  // que en ese caso el Enter cae al submit nativo del <form> y lo tomamos acá
  // con el valor controlado actual.
  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void handleVerify(payloadValue);
  };

  const handleConfirm = async (excepcionConsultorioFamiliar?: string) => {
    if (!verifiedPayload || !ficha) {
      return;
    }

    setConfirmError(null);

    try {
      const result = await confirmarCheckin.mutateAsync({
        payload: verifiedPayload,
        ...buildConfirmarCheckinOptions(ficha.vigenciaActiva, autorizacionVigencia),
        ...(excepcionConsultorioFamiliar ? { excepcionConsultorioFamiliar } : {}),
      });
      toast.success("Check-in confirmado", {
        description: `${result.paciente || "Paciente"} — folio ${result.folio}.`,
      });
      setConflictoP03(null);
      resetForNextScan();
    } catch (error) {
      // P-03: la cita es de otro consultorio que el familiar.
      const conflicto = conflictoConsultorioFamiliar(error);
      if (conflicto) {
        setConflictoP03(conflicto);
        return;
      }
      if (esErrorSinVigencia(error)) {
        // Perdió la vigencia después de escanear: se pide la autorización.
        setFicha({ ...ficha, vigenciaActiva: false });
      }
      setConfirmError(resolveQrCheckinErrorMessage(error));
    }
  };

  const puedeConfirmar =
    !!ficha && autorizacionVigenciaCompleta(ficha.vigenciaActiva, autorizacionVigencia);

  return (
    <section className="space-y-5 p-6">
      <header className="space-y-2 rounded-xl border border-line-struct bg-paper p-5">
        <div className="inline-flex items-center gap-2 rounded-full border border-line-hairline bg-subtle px-3 py-1 text-xs font-medium text-txt-muted">
          <QrCode className="size-3.5" />
          Recepción · Check-in
        </div>
        <h1 className="text-2xl font-semibold text-txt-body">
          Check-in de citas
        </h1>
        <p className="max-w-2xl text-sm text-txt-muted">
          Escanea el código QR del comprobante, o busca al paciente por
          nombre o folio si no lo trae a la mano.
        </p>
      </header>

      <Tabs defaultValue={CHECKIN_TAB.QR} className="w-full">
        <TabsList>
          <TabsTrigger value={CHECKIN_TAB.QR}>
            <ScanLine className="size-4" /> Escanear QR
          </TabsTrigger>
          <TabsTrigger value={CHECKIN_TAB.BUSQUEDA}>
            <Search className="size-4" /> Buscar por nombre o folio
          </TabsTrigger>
        </TabsList>

        <TabsContent value={CHECKIN_TAB.QR} className="mt-4 space-y-5">
          <Card className="max-w-xl">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ScanLine className="size-4" />
                Escanear comprobante
              </CardTitle>
              <CardDescription>
                El campo se mantiene enfocado para escaneos consecutivos, uno
                por paciente.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <form onSubmit={handleSubmit} className="space-y-2">
                <Label htmlFor="qr-payload-input">Código del comprobante</Label>
                <BarcodeScannerInput
                  id="qr-payload-input"
                  ref={inputRef}
                  value={payloadValue}
                  onChange={setPayloadValue}
                  onScan={(scanned) => void handleVerify(scanned)}
                  placeholder="Escanea o pega el código aquí..."
                  disabled={isVerifying || isConfirming}
                  autoComplete="off"
                />
              </form>

              {isVerifying ? (
                <p className="flex items-center gap-2 text-sm text-txt-muted">
                  <Loader2 className="size-4 animate-spin" /> Validando código...
                </p>
              ) : null}

              {verifyError ? (
                <Alert variant="critical">
                  <AlertTitle>No se pudo validar el código</AlertTitle>
                  <AlertDescription>{verifyError}</AlertDescription>
                </Alert>
              ) : null}
            </CardContent>
          </Card>

          {ficha ? (
            <FichaCheckinCard
              ficha={ficha}
              title="Confirmar datos del paciente"
              description="Verifica que la persona frente a ti coincida con estos datos antes de confirmar el check-in."
            >
              {confirmError ? (
                <Alert variant="critical">
                  <AlertTitle>No se pudo confirmar el check-in</AlertTitle>
                  <AlertDescription>{confirmError}</AlertDescription>
                </Alert>
              ) : null}

              {!canConfirmCheckin ? (
                <Alert variant="warning">
                  <AlertTitle>Sin permiso para confirmar</AlertTitle>
                  <AlertDescription>
                    Tu usuario no tiene permiso para registrar check-ins. Pide
                    a un compañero con permisos de recepción que confirme.
                  </AlertDescription>
                </Alert>
              ) : null}

              {conflictoP03 ? (
                <ConflictoCheckin
                  conflicto={conflictoP03}
                  idPaciente={ficha.idPaciente}
                  nombre={ficha.paciente}
                  enviando={isConfirming}
                  onExcepcion={(motivo) => void handleConfirm(motivo)}
                  onReasignado={() => {
                    setConflictoP03(null);
                    toast.success("Consultorio familiar reasignado", {
                      description: "Si la cita era del consultorio anterior, quedó en \"Citas por reagendar\".",
                    });
                  }}
                />
              ) : null}

              {!ficha.vigenciaActiva ? (
                <AutorizacionVigenciaField
                  id="qr-autorizacion-vigencia"
                  value={autorizacionVigencia}
                  onChange={setAutorizacionVigencia}
                  disabled={!canConfirmCheckin || isConfirming}
                />
              ) : null}

              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  onClick={() => void handleConfirm()}
                  disabled={!canConfirmCheckin || isConfirming || !puedeConfirmar}
                >
                  {isConfirming ? (
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
                  onClick={resetForNextScan}
                  disabled={isConfirming}
                >
                  <RotateCcw className="size-4" /> Escanear otro
                </Button>
              </div>
            </FichaCheckinCard>
          ) : null}
        </TabsContent>

        <TabsContent value={CHECKIN_TAB.BUSQUEDA} className="mt-4">
          <BusquedaCheckinPanel canConfirmCheckin={canConfirmCheckin} />
        </TabsContent>
      </Tabs>
    </section>
  );
};

export default QrCheckinPage;
