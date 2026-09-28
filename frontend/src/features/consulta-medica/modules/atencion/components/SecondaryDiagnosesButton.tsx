import { useEffect, useState } from "react";
import { toast } from "sonner";
import { ListPlus, Loader2, Lock, X } from "lucide-react";
import { ApiError } from "@api/utils/errors";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@shared/ui/dialog";
import { Input } from "@shared/ui/input";
import { Label } from "@shared/ui/label";
import { useCieSearch } from "@features/consulta-medica/modules/atencion/queries/useCieSearch";
import { useSecondaryDiagnoses } from "@features/consulta-medica/modules/atencion/queries/useSecondaryDiagnoses";
import { useAddSecondaryDiagnosis } from "@features/consulta-medica/modules/atencion/mutations/useAddSecondaryDiagnosis";
import { useCancelSecondaryDiagnosis } from "@features/consulta-medica/modules/atencion/mutations/useCancelSecondaryDiagnosis";

const SECONDARY_DIAGNOSIS_ERROR_MESSAGE: Record<string, string> = {
  ROLE_NOT_ALLOWED: "No tenes permiso para editar diagnosticos.",
  VISIT_NOT_FOUND: "La visita ya no existe o fue cerrada por otro usuario.",
  CONSULTATION_NOT_FOUND: "Primero guarda el diagnostico principal de esta consulta.",
  DIAGNOSIS_ALREADY_EXISTS: "Ese codigo CIE-10 ya esta agregado a esta consulta.",
  DIAGNOSIS_NOT_FOUND: "El diagnostico ya no existe.",
  VALIDATION_ERROR: "Revisa el codigo CIE-10 ingresado.",
  PERMISSION_DENIED: "No tenes permiso para ejecutar esta accion.",
};

const FALLBACK_ERROR_MESSAGE = "No se pudo completar la accion. Intenta nuevamente.";

const resolveError = (error: unknown): string => {
  if (!(error instanceof ApiError)) {
    return FALLBACK_ERROR_MESSAGE;
  }
  return (
    SECONDARY_DIAGNOSIS_ERROR_MESSAGE[error.code] ||
    error.message ||
    FALLBACK_ERROR_MESSAGE
  );
};

interface SecondaryDiagnosesButtonProps {
  visitId: number;
  disabled?: boolean;
}

export function SecondaryDiagnosesButton({
  visitId,
  disabled,
}: SecondaryDiagnosesButtonProps) {
  const [open, setOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [debouncedSearchTerm, setDebouncedSearchTerm] = useState("");
  const [selectedCieCode, setSelectedCieCode] = useState<string | null>(null);
  const [selectedCieLabel, setSelectedCieLabel] = useState<string | null>(null);

  useEffect(() => {
    const timeout = setTimeout(() => setDebouncedSearchTerm(searchTerm.trim()), 300);
    return () => clearTimeout(timeout);
  }, [searchTerm]);

  const { data: diagnosesData, isLoading: isLoadingDiagnoses } = useSecondaryDiagnoses(
    visitId,
    { enabled: open },
  );

  const { data: cieResults } = useCieSearch(
    { search: debouncedSearchTerm, limit: 8 },
    { enabled: open && debouncedSearchTerm.length >= 2 && !selectedCieCode },
  );

  const addDiagnosis = useAddSecondaryDiagnosis();
  const cancelDiagnosis = useCancelSecondaryDiagnosis();

  const handleOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) {
      setSearchTerm("");
      setDebouncedSearchTerm("");
      setSelectedCieCode(null);
      setSelectedCieLabel(null);
    }
    setOpen(nextOpen);
  };

  const handleAdd = async () => {
    if (!selectedCieCode) {
      toast.error("Selecciona un codigo CIE-10 antes de agregar.");
      return;
    }

    try {
      await addDiagnosis.mutateAsync({
        visitId,
        data: { cieCode: selectedCieCode },
      });
      toast.success("Diagnostico secundario agregado");
      setSearchTerm("");
      setDebouncedSearchTerm("");
      setSelectedCieCode(null);
      setSelectedCieLabel(null);
    } catch (error) {
      toast.error("No se pudo agregar el diagnostico", {
        description: resolveError(error),
      });
    }
  };

  const handleCancel = async (diagnosisId: number) => {
    try {
      await cancelDiagnosis.mutateAsync({ visitId, diagnosisId });
      toast.success("Diagnostico secundario quitado");
    } catch (error) {
      toast.error("No se pudo quitar el diagnostico", {
        description: resolveError(error),
      });
    }
  };

  const activeDiagnoses = diagnosesData?.items ?? [];

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button type="button" variant="outline" disabled={disabled}>
          <ListPlus className="mr-2 size-4" />
          Diagnósticos secundarios
          {activeDiagnoses.length > 0 ? (
            <Badge variant="secondary" className="ml-2">
              {activeDiagnoses.length}
            </Badge>
          ) : null}
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Diagnósticos secundarios / comorbilidades</DialogTitle>
          <DialogDescription>
            Complementan el diagnóstico principal ya guardado de esta consulta.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            {isLoadingDiagnoses ? (
              <p className="text-sm text-txt-muted">Cargando...</p>
            ) : activeDiagnoses.length === 0 ? (
              <p className="text-sm text-txt-muted">
                No hay diagnósticos secundarios agregados todavía.
              </p>
            ) : (
              <ul className="space-y-2">
                {activeDiagnoses.map((diagnosis) => (
                  <li
                    key={diagnosis.id}
                    className="flex items-center justify-between rounded-lg border p-2"
                  >
                    <span className="text-sm">
                      {diagnosis.restricted ? (
                        <span className="inline-flex items-center gap-1 italic text-txt-muted">
                          <Lock className="size-3.5" />
                          {diagnosis.cieDescription}
                        </span>
                      ) : (
                        <>
                          <strong>{diagnosis.cieCode}</strong> — {diagnosis.cieDescription}
                        </>
                      )}
                    </span>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      disabled={cancelDiagnosis.isPending}
                      onClick={() => handleCancel(diagnosis.id)}
                    >
                      <X className="size-4" />
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="space-y-2 border-t pt-4">
            <Label htmlFor="secondaryCieSearch">Agregar código CIE-10</Label>
            <Input
              id="secondaryCieSearch"
              value={searchTerm}
              placeholder="Ej. E119 o diabetes"
              onChange={(event) => {
                setSearchTerm(event.target.value);
                setSelectedCieCode(null);
                setSelectedCieLabel(null);
              }}
            />

            {selectedCieCode ? (
              <p className="text-sm text-txt-muted">
                Seleccionado: <strong>{selectedCieLabel}</strong>
              </p>
            ) : (cieResults?.items.length ?? 0) > 0 ? (
              <ul className="max-h-40 space-y-1 overflow-y-auto rounded-lg border p-2">
                {cieResults?.items.map((item) => (
                  <li key={item.code}>
                    <button
                      type="button"
                      className="w-full rounded-md px-2 py-1 text-left text-sm hover:bg-bg-soft"
                      onClick={() => {
                        setSelectedCieCode(item.code);
                        setSelectedCieLabel(`${item.code} — ${item.description}`);
                      }}
                    >
                      <strong>{item.code}</strong> — {item.description}
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => handleOpenChange(false)}>
            Cerrar
          </Button>
          <Button
            type="button"
            disabled={!selectedCieCode || addDiagnosis.isPending}
            onClick={handleAdd}
          >
            {addDiagnosis.isPending ? (
              <Loader2 className="mr-2 size-4 animate-spin" />
            ) : null}
            Agregar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
