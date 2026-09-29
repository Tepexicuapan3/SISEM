import { useState } from "react";
import { toast } from "sonner";
import { Loader2, Stethoscope } from "lucide-react";
import { ApiError } from "@api/utils/errors";
import { Button } from "@shared/ui/button";
import { Checkbox } from "@shared/ui/checkbox";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@shared/ui/dialog";
import { Label } from "@shared/ui/label";
import { Textarea } from "@shared/ui/textarea";
import { useBodyRegions, usePhysicalExam } from "@features/consulta-medica/modules/atencion/queries/usePhysicalExam";
import { useSavePhysicalExam } from "@features/consulta-medica/modules/atencion/mutations/useSavePhysicalExam";

interface PhysicalExamButtonProps {
  visitId: number;
  disabled?: boolean;
}

interface RegionDraft {
  included: boolean;
  isNormal: boolean;
  finding: string;
}

const ERROR_MESSAGES: Record<string, string> = {
  CONSULTATION_NOT_FOUND: "Primero inicia la consulta.",
  VISIT_STATE_INVALID: "La consulta ya se cerró: usa una nota de aclaración.",
  ROLE_NOT_ALLOWED: "No tenés permiso para registrar la exploración.",
};

/**
 * EXPLORACION_FISICA por region, ligada a ESTA consulta (historia clinica
 * unificada): antes vivia como texto en la historia y se pisaba en cada
 * edicion. Solo editable con la consulta abierta.
 */
export function PhysicalExamButton({ visitId, disabled }: PhysicalExamButtonProps) {
  const [open, setOpen] = useState(false);
  const [drafts, setDrafts] = useState<Record<number, RegionDraft>>({});
  const exam = usePhysicalExam(visitId, open);
  const regions = useBodyRegions(open);
  const save = useSavePhysicalExam(visitId);

  const handleOpenChange = (next: boolean) => {
    setOpen(next);
    if (!next) setDrafts({});
  };

  const draftFor = (regionId: number): RegionDraft => {
    if (drafts[regionId]) return drafts[regionId];
    const saved = exam.data?.items.find((item) => item.regionId === regionId);
    return saved
      ? { included: true, isNormal: saved.isNormal, finding: saved.finding ?? "" }
      : { included: false, isNormal: true, finding: "" };
  };

  const updateDraft = (regionId: number, patch: Partial<RegionDraft>) =>
    setDrafts((current) => ({ ...current, [regionId]: { ...draftFor(regionId), ...patch } }));

  const editable = exam.data?.editable ?? false;

  const handleSave = async () => {
    const findings = (regions.data ?? [])
      .map((region) => ({ region, draft: draftFor(region.id) }))
      .filter(({ draft }) => draft.included);
    const missing = findings.find(({ draft }) => !draft.isNormal && !draft.finding.trim());
    if (missing) {
      toast.error(`Describe el hallazgo anormal en ${missing.region.name}.`);
      return;
    }
    try {
      await save.mutateAsync({
        findings: findings.map(({ region, draft }) => ({
          regionId: region.id,
          isNormal: draft.isNormal,
          finding: draft.finding.trim() || null,
        })),
      });
      toast.success("Exploración física guardada");
      handleOpenChange(false);
    } catch (error) {
      const message = error instanceof ApiError ? ERROR_MESSAGES[error.code] ?? error.message : null;
      toast.error("No se pudo guardar la exploración", { description: message ?? undefined });
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button type="button" variant="outline" disabled={disabled}>
          <Stethoscope className="mr-2 size-4" />
          Exploración física
        </Button>
      </DialogTrigger>
      <DialogContent className="w-[95vw] max-w-none rounded-3xl bg-paper sm:w-[85vw] lg:w-180">
        <DialogHeader>
          <DialogTitle>Exploración física</DialogTitle>
          <DialogDescription>
            Marca las regiones exploradas en esta consulta. Una región anormal requiere describir el hallazgo.
          </DialogDescription>
        </DialogHeader>

        {exam.isLoading || regions.isLoading ? (
          <p className="text-sm text-txt-muted">Cargando...</p>
        ) : exam.isError ? (
          <p className="text-sm text-status-critical">
            {exam.error instanceof ApiError ? ERROR_MESSAGES[exam.error.code] ?? exam.error.message : "No se pudo cargar."}
          </p>
        ) : (
          <div className="max-h-[60vh] space-y-3 overflow-y-auto pr-1">
            {!editable ? (
              <p className="text-xs text-txt-muted">La consulta está cerrada: la exploración es de solo lectura.</p>
            ) : null}
            {(regions.data ?? []).map((region) => {
              const draft = draftFor(region.id);
              return (
                <div key={region.id} className="space-y-2 rounded-lg border border-line-struct p-3">
                  <div className="flex flex-wrap items-center gap-4">
                    <label className="flex items-center gap-2 text-sm font-semibold text-txt-body">
                      <Checkbox
                        checked={draft.included}
                        disabled={!editable}
                        onCheckedChange={(checked) => updateDraft(region.id, { included: checked === true })}
                      />
                      {region.name}
                    </label>
                    {draft.included ? (
                      <label className="flex items-center gap-2 text-sm text-txt-muted">
                        <Checkbox
                          checked={!draft.isNormal}
                          disabled={!editable}
                          onCheckedChange={(checked) => updateDraft(region.id, { isNormal: checked !== true })}
                        />
                        Anormal
                      </label>
                    ) : null}
                  </div>
                  {draft.included ? (
                    <div className="space-y-1">
                      <Label className="text-xs text-txt-muted">Hallazgo</Label>
                      <Textarea
                        rows={2}
                        disabled={!editable}
                        value={draft.finding}
                        placeholder={draft.isNormal ? "Sin alteraciones (opcional)" : "Describe el hallazgo"}
                        onChange={(event) => updateDraft(region.id, { finding: event.target.value })}
                      />
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        )}

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => handleOpenChange(false)}>
            Cerrar
          </Button>
          {editable ? (
            <Button type="button" onClick={() => void handleSave()} disabled={save.isPending}>
              {save.isPending ? <Loader2 className="mr-2 size-4 animate-spin" /> : null}
              Guardar exploración
            </Button>
          ) : null}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
