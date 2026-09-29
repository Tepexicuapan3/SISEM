import { useState } from "react";
import { Loader2 } from "lucide-react";
import { Button } from "@shared/ui/button";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@shared/ui/dialog";
import { Label } from "@shared/ui/label";
import { Textarea } from "@shared/ui/textarea";

interface ReasonDialogProps {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  destructive?: boolean;
  isPending?: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: (reason: string) => void | Promise<void>;
}

/**
 * Pide un motivo obligatorio antes de una baja o cambio de estado clinico:
 * en la historia clinica nada se borra sin dejar el porque (NOM-004/024).
 */
export function ReasonDialog({
  open, title, description, confirmLabel, destructive = false, isPending = false, onOpenChange, onConfirm,
}: ReasonDialogProps) {
  const [reason, setReason] = useState("");
  const trimmed = reason.trim();

  const handleOpenChange = (next: boolean) => {
    if (!next) setReason("");
    onOpenChange(next);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="w-[95vw] max-w-none rounded-3xl bg-paper sm:w-[80vw] lg:w-140">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <Label htmlFor="reason-dialog-text">Motivo</Label>
          <Textarea
            id="reason-dialog-text"
            rows={3}
            maxLength={500}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => handleOpenChange(false)}>
            Cancelar
          </Button>
          <Button
            type="button"
            variant={destructive ? "destructive" : "default"}
            disabled={!trimmed || isPending}
            onClick={async () => {
              await onConfirm(trimmed);
              setReason("");
            }}
          >
            {isPending ? <Loader2 className="mr-2 size-4 animate-spin" /> : null}
            {confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
