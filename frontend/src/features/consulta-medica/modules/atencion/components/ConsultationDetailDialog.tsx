import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@shared/ui/dialog";
import {
  ConsultationWorkspace,
  type ConsultationWorkspaceProps,
} from "./ConsultationWorkspace";

interface Props extends Omit<ConsultationWorkspaceProps, "variant"> {
  isDetailRoute:                     boolean;
  handleConsultationModalOpenChange: (open: boolean) => void;
}

export function ConsultationDetailDialog({
  isDetailRoute,
  handleConsultationModalOpenChange,
  ...workspaceProps
}: Props) {
  return (
    <Dialog
      open={isDetailRoute}
      onOpenChange={handleConsultationModalOpenChange}
    >
      <DialogContent
        className="max-h-[92vh] gap-0 overflow-y-auto p-0 sm:max-w-5xl"
        data-testid="doctor-consultation-modal"
      >
        <DialogHeader className="border-b border-line-hairline px-5 pt-5 pb-4 sm:px-6">
          <DialogTitle>Detalle de consulta medica</DialogTitle>
          <DialogDescription>
            Inicia la consulta, registra diagnostico, receta y finaliza la
            atencion clinica.
          </DialogDescription>
        </DialogHeader>

        <ConsultationWorkspace variant="dialog" {...workspaceProps} />
      </DialogContent>
    </Dialog>
  );
}
