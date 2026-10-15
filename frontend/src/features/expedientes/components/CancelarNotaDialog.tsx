import { useState } from "react";
import { AlertTriangle, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Alert, AlertDescription, AlertTitle } from "@shared/ui/alert";
import { Button } from "@shared/ui/button";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@shared/ui/dialog";
import { Input } from "@shared/ui/input";
import { Label } from "@shared/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@shared/ui/select";
import { Textarea } from "@shared/ui/textarea";
import { useMotivoCancelacionNotaList } from "@features/admin/modules/catalogos/motivos-cancelacion-nota/queries/useMotivoCancelacionNotaList";
import {
  describeBlocker,
  describeCascade,
  describePreviewRestriction,
  mapNoteCancellationError,
  type NoteCancellationErrorInfo,
} from "@features/expedientes/domain/note-cancellation";
import { useCancelConsultationNote } from "@features/expedientes/mutations/useCancelConsultationNote";
import { useNoteCancellationPreview } from "@features/expedientes/queries/useNoteCancellationPreview";

interface CancelarNotaDialogProps {
  visitId: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Etiqueta de la nota (fecha/medico) para el encabezado. */
  noteLabel?: string;
}

const MAX_DETAIL = 500;

/**
 * Cancelar una nota cerrada (cascada). Muestra el preview, pide motivo,
 * detalle opcional y la contrasena PROPIA del autorizador. La contrasena
 * vive solo en estado local y se limpia al cerrar / ante cualquier error.
 */
export function CancelarNotaDialog(props: CancelarNotaDialogProps) {
  // El cuerpo se monta solo mientras el modal esta abierto: cada apertura
  // arranca con estado limpio (nunca queda la contrasena anterior).
  return props.open ? <CancelarNotaDialogBody {...props} /> : null;
}

function CancelarNotaDialogBody({
  visitId, open, onOpenChange, noteLabel,
}: CancelarNotaDialogProps) {
  const [motivoId, setMotivoId] = useState("");
  const [detail, setDetail] = useState("");
  const [password, setPassword] = useState("");
  const [submitError, setSubmitError] = useState<NoteCancellationErrorInfo | null>(null);
  const [locked, setLocked] = useState(false);

  const preview = useNoteCancellationPreview(visitId, open);
  const { data: motivosData } = useMotivoCancelacionNotaList(
    { page: 1, pageSize: 200, isActive: true },
    { enabled: open },
  );
  const cancelNote = useCancelConsultationNote();

  const data = preview.data;
  const restriction = data ? describePreviewRestriction(data) : null;
  const previewBlockers = data?.blockers ?? [];
  const cascadeLines = data ? describeCascade(data.cascade) : [];
  const motivos = motivosData?.items ?? [];
  const formVisible = Boolean(data) && restriction === null && previewBlockers.length === 0;

  const canSubmit =
    formVisible &&
    Boolean(motivoId) &&
    password.length > 0 &&
    !locked &&
    !cancelNote.isPending;

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setSubmitError(null);
    try {
      await cancelNote.mutateAsync({
        visitId,
        data: {
          motivoId: Number(motivoId),
          motivoDetalle: detail.trim() || null,
          password,
        },
      });
      setPassword("");
      toast.success("Nota cancelada");
      onOpenChange(false);
    } catch (error) {
      const info = mapNoteCancellationError(error);
      setSubmitError(info);
      if (info.clearPassword) setPassword("");
      if (info.lockSubmit) setLocked(true);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(next) => { if (!cancelNote.isPending) onOpenChange(next); }}>
      <DialogContent className="w-[95vw] max-w-none rounded-3xl bg-paper sm:w-[80vw] lg:w-140">
        <DialogHeader>
          <DialogTitle>Cancelar nota</DialogTitle>
          <DialogDescription>
            {noteLabel ? `${noteLabel}. ` : ""}
            Esta accion cancela la nota y todo lo que se genero a partir de ella. No se puede deshacer.
          </DialogDescription>
        </DialogHeader>

        {preview.isLoading ? (
          <p className="flex items-center gap-2 text-sm text-txt-muted">
            <Loader2 className="size-4 animate-spin" /> Verificando que se puede cancelar...
          </p>
        ) : preview.isError ? (
          <Alert variant="destructive">
            <AlertTriangle className="size-4" />
            <AlertTitle>No se pudo verificar la nota</AlertTitle>
            <AlertDescription>
              {mapNoteCancellationError(preview.error).message}
            </AlertDescription>
          </Alert>
        ) : data ? (
          <div className="space-y-3 text-sm">
            {restriction ? (
              <Alert variant="destructive" data-testid="cancel-note-restriction">
                <AlertTriangle className="size-4" />
                <AlertTitle>No puedes cancelar esta nota</AlertTitle>
                <AlertDescription>{restriction}</AlertDescription>
              </Alert>
            ) : null}

            {previewBlockers.length > 0 ? (
              <Alert variant="destructive" data-testid="cancel-note-blockers">
                <AlertTriangle className="size-4" />
                <AlertTitle>La nota no se puede cancelar</AlertTitle>
                <AlertDescription>
                  <ul className="list-disc pl-4">
                    {previewBlockers.map((blocker) => (
                      <li key={blocker.code}>{describeBlocker(blocker)}</li>
                    ))}
                  </ul>
                </AlertDescription>
              </Alert>
            ) : null}

            {cascadeLines.length > 0 ? (
              <div data-testid="cancel-note-cascade">
                <p className="font-medium text-txt-body">Se cancelaran tambien:</p>
                <ul className="list-disc pl-5 text-txt-muted">
                  {cascadeLines.map((line) => <li key={line}>{line}</li>)}
                </ul>
              </div>
            ) : null}

            {data.fueraAdscripcion && restriction === null ? (
              <Alert variant="warning" data-testid="cancel-note-outside-assignment">
                <AlertTriangle className="size-4" />
                <AlertTitle>Fuera de tu adscripcion</AlertTitle>
                <AlertDescription>
                  Esta nota pertenece a un centro distinto al de tu adscripcion. Tu designacion
                  lo permite, pero la cancelacion quedara marcada en la auditoria.
                </AlertDescription>
              </Alert>
            ) : null}
          </div>
        ) : null}

        {formVisible ? (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="cancel-note-motivo">Motivo</Label>
              <Select value={motivoId} onValueChange={setMotivoId}>
                <SelectTrigger id="cancel-note-motivo" className="w-full">
                  <SelectValue placeholder="Selecciona un motivo" />
                </SelectTrigger>
                <SelectContent>
                  {motivos.map((item) => (
                    <SelectItem key={item.id} value={String(item.id)}>{item.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="cancel-note-detail">Detalle (opcional)</Label>
              <Textarea
                id="cancel-note-detail"
                rows={2}
                maxLength={MAX_DETAIL}
                value={detail}
                onChange={(event) => setDetail(event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="cancel-note-password">Tu contrasena</Label>
              <Input
                id="cancel-note-password"
                type="password"
                autoComplete="current-password"
                value={password}
                disabled={locked}
                onChange={(event) => setPassword(event.target.value)}
              />
              <p className="text-xs text-txt-muted">
                Confirma tu identidad como autorizador. No se guarda.
              </p>
            </div>
          </div>
        ) : null}

        {submitError ? (
          <Alert variant="destructive" data-testid="cancel-note-error">
            <AlertTriangle className="size-4" />
            <AlertTitle>{submitError.message}</AlertTitle>
            {submitError.blockers.length > 0 ? (
              <AlertDescription>
                <ul className="list-disc pl-4">
                  {submitError.blockers.map((blocker) => (
                    <li key={blocker.code}>{describeBlocker(blocker)}</li>
                  ))}
                </ul>
              </AlertDescription>
            ) : null}
          </Alert>
        ) : null}

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            disabled={cancelNote.isPending}
            onClick={() => onOpenChange(false)}
          >
            Cerrar
          </Button>
          <Button
            type="button"
            variant="destructive"
            disabled={!canSubmit}
            onClick={() => { void handleSubmit(); }}
          >
            {cancelNote.isPending ? <Loader2 className="mr-2 size-4 animate-spin" /> : null}
            Cancelar nota
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
