import { useState } from "react";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import { Label } from "@shared/ui/label";
import { Textarea } from "@shared/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@shared/ui/select";
import { Popover, PopoverContent, PopoverTrigger } from "@shared/ui/popover";
import {
  useOdontogramVersions,
  usePatientOdontogram,
} from "@features/expedientes/queries/usePatientOdontogram";
import { useClinicalCatalogs } from "@features/expedientes/queries/useUnifiedHistory";
import { useUpdateOdontogramTooth } from "@features/expedientes/mutations/useUpdateOdontogramTooth";
import type {
  OdontogramDentition,
  OdontogramToothItem,
  OdontogramVersion,
  ToothCondition,
  ToothFace,
} from "@api/types";

interface ExpedienteOdontogramaTabProps {
  noExp: string;
  pkNum?: number;
}

// Nombres de respaldo -- la fuente real es `cat_estado_pieza` (catalogo
// administrable via /clinical-catalogs); si estomatologia agrega un estado
// nuevo, se muestra con su nombre del catalogo y el color neutro.
const FALLBACK_LABELS: Record<string, string> = {
  healthy: "Sano",
  caries: "Caries",
  filled: "Obturado",
  crown: "Corona",
  missing: "Ausente",
  extraction_needed: "Extracción Indicada",
  root_canal: "Endodoncia",
  sealant: "Sellante",
  fracture: "Fracturado",
  implant: "Implante",
};

const FACE_LABELS: Record<Exclude<ToothFace, "">, string> = {
  O: "Oclusal",
  M: "Mesial",
  D: "Distal",
  V: "Vestibular",
  L: "Lingual/Palatina",
};
const WHOLE_TOOTH = "whole";
const LATEST = "latest";
const NEUTRAL_TEXT = "text-txt-body";

// Todos los tonos son tokens reales del sistema de diseño (theme.css) --
// ninguno es un color "suelto" de Tailwind. Las condiciones dentales
// reutilizan la misma familia --color-area-* que ya usa el resto de la app
// para distinguir áreas clínicas (gyn/geriat/peds), sumadas a los 4 tonos
// clínicos (status-*) y el color de marca.
const CONDITION_COLORS: Record<string, string> = {
  healthy: "bg-status-stable/15 border-status-stable text-status-stable",
  caries: "bg-status-critical/15 border-status-critical text-status-critical",
  filled: "bg-status-info/15 border-status-info text-status-info",
  crown: "bg-area-peds/15 border-area-peds text-area-peds",
  missing: "bg-subtle border-line-struct text-txt-muted",
  extraction_needed: "bg-area-gral/15 border-area-gral text-area-gral",
  root_canal: "bg-area-gyn/15 border-area-gyn text-area-gyn",
  sealant: "bg-area-geriat/15 border-area-geriat text-area-geriat",
  fracture: "bg-status-alert/15 border-status-alert text-status-alert",
  implant: "bg-brand/15 border-brand text-brand",
};

// Solo el color de texto de cada condicion (mismos tokens que CONDITION_COLORS)
// -- el SVG del diente usa currentColor para trazo y relleno, asi que basta
// con la clase de texto en el contenedor.
const CONDITION_TEXT: Record<string, string> = {
  healthy: "text-status-stable",
  caries: "text-status-critical",
  filled: "text-status-info",
  crown: "text-area-peds",
  missing: "text-txt-muted",
  extraction_needed: "text-area-gral",
  root_canal: "text-area-gyn",
  sealant: "text-area-geriat",
  fracture: "text-status-alert",
  implant: "text-brand",
};

// Silueta generica de diente (corona + dos raices) reutilizada para las 32
// piezas -- el color viene de CONDITION_TEXT via currentColor. "Ausente"
// se dibuja hueca y punteada (convencion clinica estandar de odontograma).
function ToothShape({
  className,
  dashed,
}: {
  className?: string;
  dashed?: boolean;
}) {
  return (
    <svg
      viewBox="0 0 24 34"
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      <path
        d="M12 2 C7 2 4 5 4 9 C4 12 5 14 6 16 L7 26 C7 29 8 32 9.5 32 C10.5 32 11 30 11.5 27 L12 22 L12.5 27 C13 30 13.5 32 14.5 32 C16 32 17 29 17 26 L18 16 C19 14 20 12 20 9 C20 5 17 2 12 2 Z"
        fill={dashed ? "none" : "currentColor"}
        fillOpacity={dashed ? 1 : 0.18}
        stroke="currentColor"
        strokeWidth={1.5}
        strokeDasharray={dashed ? "2.5 2" : undefined}
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function ExpedienteOdontogramaTab({
  noExp,
  pkNum = 0,
}: ExpedienteOdontogramaTabProps) {
  const [dentition, setDentition] = useState<OdontogramDentition>("permanent");
  const [versionId, setVersionId] = useState<number | null>(null);
  const { data, isLoading, isError } = usePatientOdontogram(noExp, pkNum, dentition, versionId);
  const { data: versions } = useOdontogramVersions(noExp, pkNum);
  const { data: catalogs } = useClinicalCatalogs();

  const stateLabels: Record<string, string> = {
    ...FALLBACK_LABELS,
    ...Object.fromEntries((catalogs?.toothStates ?? []).map((state) => [state.code, state.name])),
  };
  const labelOf = (code: ToothCondition) => stateLabels[code] ?? code;
  const readOnly = versionId !== null;

  if (isLoading) {
    return (
      <p className="text-txt-muted text-sm py-12 text-center">
        Cargando odontograma...
      </p>
    );
  }

  if (isError) {
    return (
      <p className="text-status-critical text-sm py-12 text-center">
        No se pudo cargar el odontograma de este paciente.
      </p>
    );
  }

  const items = data?.items ?? [];
  const half = Math.ceil(items.length / 2);
  const upper = items.slice(0, half);
  const lower = items.slice(half);
  const version = data?.version ?? null;
  const stateCodes = Object.keys(stateLabels);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant={dentition === "permanent" ? "default" : "outline"}
            size="sm"
            onClick={() => setDentition("permanent")}
          >
            Dentición Permanente
          </Button>
          <Button
            type="button"
            variant={dentition === "deciduous" ? "default" : "outline"}
            size="sm"
            onClick={() => setDentition("deciduous")}
          >
            Dentición Infantil
          </Button>
        </div>
        <div className="flex items-center gap-2">
          <Label className="text-xs text-txt-muted">Versión</Label>
          <Select
            value={versionId === null ? LATEST : String(versionId)}
            onValueChange={(value) => setVersionId(value === LATEST ? null : Number(value))}
          >
            <SelectTrigger className="w-64"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value={LATEST}>Vigente</SelectItem>
              {(versions?.items ?? []).map((item) => (
                <SelectItem key={item.id} value={String(item.id)}>
                  {versionLabel(item)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {version ? <DmftSummary version={version} /> : (
        <p className="text-xs text-txt-muted">Sin registros: todas las piezas se muestran sanas.</p>
      )}
      {readOnly ? (
        <p className="text-xs text-txt-muted">
          Estás viendo una versión anterior (solo lectura). Los cambios se registran sobre la versión vigente.
        </p>
      ) : null}

      <div className="space-y-6">
        <ToothRow label="Arcada superior" teeth={upper} noExp={noExp} pkNum={pkNum} readOnly={readOnly} labelOf={labelOf} stateCodes={stateCodes} />
        <ToothRow label="Arcada inferior" teeth={lower} noExp={noExp} pkNum={pkNum} readOnly={readOnly} labelOf={labelOf} stateCodes={stateCodes} />
      </div>

      <div className="flex flex-wrap gap-3 pt-4 border-t border-line-struct">
        {stateCodes.map((value) => (
          <div key={value} className="flex items-center gap-1.5 text-xs text-txt-muted">
            <span className={`size-3 rounded border-2 ${CONDITION_COLORS[value] ?? "border-line-struct"}`} />
            {stateLabels[value]}
          </div>
        ))}
      </div>
    </div>
  );
}

function versionLabel(version: OdontogramVersion) {
  const date = new Date(version.createdAt).toLocaleDateString("es-MX");
  const origin = version.origin === "migrated" ? " · migrado" : "";
  return `${date} · CPOD ${version.dmft.index}${origin}`;
}

function DmftSummary({ version }: { version: OdontogramVersion }) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <span className="font-semibold text-txt-body">Índice CPOD: {version.dmft.index}</span>
      <Badge variant="outline">Cariados {version.dmft.decayed}</Badge>
      <Badge variant="outline">Perdidos {version.dmft.missing}</Badge>
      <Badge variant="outline">Obturados {version.dmft.filled}</Badge>
      <span className="text-xs text-txt-muted">
        Versión del {new Date(version.createdAt).toLocaleString("es-MX")}
      </span>
    </div>
  );
}

interface ToothRowProps {
  label: string;
  teeth: OdontogramToothItem[];
  noExp: string;
  pkNum: number;
  readOnly: boolean;
  labelOf: (code: ToothCondition) => string;
  stateCodes: string[];
}

function ToothRow({ label, teeth, ...rest }: ToothRowProps) {
  return (
    <div>
      <p className="text-xs text-txt-muted mb-2 text-center">{label}</p>
      <div className="flex flex-wrap gap-1.5 justify-center">
        {teeth.map((tooth) => (
          <ToothCell key={tooth.toothFdi} tooth={tooth} {...rest} />
        ))}
      </div>
    </div>
  );
}

function ToothCell({
  tooth,
  noExp,
  pkNum,
  readOnly,
  labelOf,
  stateCodes,
}: Omit<ToothRowProps, "label" | "teeth"> & { tooth: OdontogramToothItem }) {
  const [open, setOpen] = useState(false);
  const [face, setFace] = useState<string>(WHOLE_TOOTH);
  const [condition, setCondition] = useState<ToothCondition>(tooth.condition);
  const [notes, setNotes] = useState(tooth.notes ?? "");
  const updateTooth = useUpdateOdontogramTooth();

  const stateFor = (selectedFace: string) => {
    if (selectedFace === WHOLE_TOOTH) return { condition: tooth.condition, notes: tooth.notes };
    const current = tooth.faces.find((item) => item.face === selectedFace);
    return { condition: current?.condition ?? "healthy", notes: current?.notes ?? null };
  };

  const selectFace = (selectedFace: string) => {
    const state = stateFor(selectedFace);
    setFace(selectedFace);
    setCondition(state.condition);
    setNotes(state.notes ?? "");
  };

  const handleOpenChange = (nextOpen: boolean) => {
    if (nextOpen) selectFace(WHOLE_TOOTH);
    setOpen(nextOpen);
  };

  const handleSave = async () => {
    try {
      await updateTooth.mutateAsync({
        noExp,
        pkNum,
        toothFdi: tooth.toothFdi,
        data: {
          condition,
          notes: notes || null,
          face: face === WHOLE_TOOTH ? "" : (face as ToothFace),
        },
      });
      toast.success(`Pieza ${tooth.toothFdi} actualizada`);
      setOpen(false);
    } catch {
      toast.error("No se pudo actualizar la pieza", {
        description: "Intenta nuevamente en unos segundos.",
      });
    }
  };

  const facesSummary = tooth.faces
    .map((item) => `${item.face}: ${labelOf(item.condition)}`)
    .join(" · ");

  const trigger = (
    <button
      type="button"
      disabled={readOnly}
      className={`flex flex-col items-center gap-0.5 rounded-lg p-1 transition-opacity hover:opacity-80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand disabled:cursor-default disabled:hover:opacity-100 ${CONDITION_TEXT[tooth.condition] ?? NEUTRAL_TEXT}`}
      title={`Pieza ${tooth.toothFdi} · ${labelOf(tooth.condition)}${facesSummary ? ` · ${facesSummary}` : ""}`}
    >
      <ToothShape className="size-11" dashed={tooth.condition === "missing"} />
      <span className="text-[10px] font-semibold leading-none text-txt-muted">
        {tooth.toothFdi}
        {tooth.faces.length ? "*" : ""}
      </span>
    </button>
  );

  if (readOnly) return trigger;

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverTrigger asChild>{trigger}</PopoverTrigger>
      <PopoverContent className="w-72 space-y-3">
        <p className="text-sm font-semibold text-txt-body">Pieza {tooth.toothFdi}</p>
        {facesSummary ? <p className="text-xs text-txt-muted">Caras: {facesSummary}</p> : null}
        <div className="space-y-2">
          <Label>Cara</Label>
          <Select value={face} onValueChange={selectFace}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            {/* z-[150]: el Select vive dentro de un Popover (z-[140]). */}
            <SelectContent className="z-[150]">
              <SelectItem value={WHOLE_TOOTH}>Pieza completa</SelectItem>
              {Object.entries(FACE_LABELS).map(([value, label]) => (
                <SelectItem key={value} value={value}>{label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label>Condición</Label>
          <Select value={condition} onValueChange={(value) => setCondition(value as ToothCondition)}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent className="z-[150]">
              {stateCodes.map((value) => (
                <SelectItem key={value} value={value}>{labelOf(value)}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label>Notas (opcional)</Label>
          <Textarea value={notes} onChange={(event) => setNotes(event.target.value)} rows={2} maxLength={255} />
        </div>
        <Button
          type="button"
          className="w-full"
          size="sm"
          onClick={() => void handleSave()}
          disabled={updateTooth.isPending}
        >
          {updateTooth.isPending ? <Loader2 className="mr-2 size-4 animate-spin" /> : null}
          Guardar
        </Button>
      </PopoverContent>
    </Popover>
  );
}
