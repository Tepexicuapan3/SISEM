import {
  Building2, CalendarX2, ClipboardList, Stethoscope, UserRound, Users,
} from "lucide-react";
import { Badge }    from "@shared/ui/badge";
import { Button }   from "@shared/ui/button";
import { Skeleton } from "@shared/ui/skeleton";
import { AdminDetailsDialogShell }
  from "@features/admin/shared/components/details/AdminDetailsDialogShell";
import { useMedicoDetail }
  from "@features/admin/modules/medicos/hooks/useMedicos";
import { MedicoGeneralTab }
  from "@features/admin/modules/medicos/components/tabs/MedicoGeneralTab";
import { MedicoEspecialidadesTab }
  from "@features/admin/modules/medicos/components/tabs/MedicoEspecialidadesTab";
import { MedicoCentrosTab }
  from "@features/admin/modules/medicos/components/tabs/MedicoCentrosTab";
import { MedicoConsultoriosTab }
  from "@features/admin/modules/medicos/components/tabs/MedicoConsultoriosTab";
import { MedicoExcepcionesTab }
  from "@features/admin/modules/medicos/components/tabs/MedicoExcepcionesTab";
import { MedicoCoberturasTab }
  from "@features/admin/modules/medicos/components/tabs/MedicoCoberturasTab";
import type { EstatusMedico, TipoMedico } from "@api/types/medicos.types";
import type { MedicoListItem } from "@api/types/medicos.types";

// ─── Mapas de display ─────────────────────────────────────────────────────────

const ESTATUS_LABELS: Record<EstatusMedico, string> = {
  ACTIVO: "Activo", VACACIONES: "Vacaciones", INCAPACIDAD: "Incapacidad",
  SUSPENDIDO: "Suspendido", BAJA: "Baja",
};

const ESTATUS_VARIANT: Record<string, "stable"|"alert"|"secondary"|"critical"|"outline"> = {
  ACTIVO: "stable", VACACIONES: "alert", INCAPACIDAD: "alert",
  SUSPENDIDO: "critical", BAJA: "secondary",
};

const TIPO_LABEL: Record<TipoMedico, string> = {
  CLINICA: "Clínica", HOSPITAL: "Hospital", AMBOS: "Clínica / Hospital",
};

// ─── Header del dialog ────────────────────────────────────────────────────────

function MedicoDialogHeader({
  medicoSummary, tipo,
}: {
  medicoSummary: MedicoListItem | null;
  tipo?: TipoMedico;
}) {
  const initials = medicoSummary
    ? ([medicoSummary.nombre, medicoSummary.paterno]
        .filter(Boolean)
        .map((s) => s.charAt(0).toUpperCase())
        .join("")
        .slice(0, 2) || "M")
    : "M";

  return (
    <div className="flex items-center gap-4 pb-3">
      {/* Avatar con iniciales */}
      <div className="flex size-12 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-sm font-bold text-primary select-none">
        {initials}
      </div>

      {/* Info */}
      <div className="min-w-0 flex-1">
        <h2 className="truncate text-base font-semibold leading-snug text-txt-body">
          {medicoSummary?.nombreCompleto ?? "Médico"}
        </h2>
        <p className="truncate text-sm text-txt-muted">
          {medicoSummary?.username}
          {medicoSummary?.servicio ? ` · ${medicoSummary.servicio}` : ""}
        </p>
      </div>

      {/* Badges */}
      <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
        {tipo ? (
          <Badge variant="outline" className="text-xs">{TIPO_LABEL[tipo]}</Badge>
        ) : null}
        {medicoSummary ? (
          <Badge
            variant={ESTATUS_VARIANT[medicoSummary.estatusMedico] ?? "outline"}
            className="gap-1.5 text-xs"
          >
            <span className="size-1.5 shrink-0 rounded-full bg-current opacity-70" />
            {ESTATUS_LABELS[medicoSummary.estatusMedico] ?? medicoSummary.estatusMedico}
          </Badge>
        ) : null}
      </div>
    </div>
  );
}

// ─── Skeleton de carga ────────────────────────────────────────────────────────

function LoadingSkeleton() {
  return (
    <div className="space-y-3 pt-1">
      <Skeleton className="h-10 w-full rounded-xl" />
      <Skeleton className="h-24 w-full rounded-xl" />
      <Skeleton className="h-16 w-full rounded-xl" />
      <Skeleton className="h-16 w-full rounded-xl" />
      <Skeleton className="h-10 w-3/4 rounded-xl" />
    </div>
  );
}

// ─── Props ────────────────────────────────────────────────────────────────────

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  medicoSummary: MedicoListItem | null;
  canEdit: boolean;
}

// ─── Dialog principal ─────────────────────────────────────────────────────────

export function MedicoDetailsDialog({ open, onOpenChange, medicoSummary, canEdit }: Props) {
  const userId = medicoSummary?.id;
  const { data, isLoading, isError, refetch } = useMedicoDetail(userId, open && !!userId);
  const medico = data?.medico;

  const tipo      = medico?.tipoMedico ?? medicoSummary?.tipoMedico;
  const esClinica = tipo === "CLINICA" || tipo === "AMBOS";

  const sections = [
    {
      id:      "general",
      label:   "General",
      icon:    <UserRound    className="size-3.5" />,
      content: medico
        ? <MedicoGeneralTab medico={medico} isEditable={canEdit} />
        : null,
    },
    {
      id:      "especialidades",
      label:   "Especialidades",
      icon:    <Stethoscope  className="size-3.5" />,
      content: medico
        ? <MedicoEspecialidadesTab medico={medico} isEditable={canEdit} />
        : null,
    },
    {
      id:      "centros",
      label:   "Centros",
      icon:    <Building2   className="size-3.5" />,
      content: medico
        ? <MedicoCentrosTab medico={medico} isEditable={canEdit} />
        : null,
    },
    {
      id:      "consultorios",
      label:   "Consultorios",
      icon:    <ClipboardList className="size-3.5" />,
      hidden:  !esClinica,
      content: medico
        ? <MedicoConsultoriosTab
            medico={medico}
            isEditable={canEdit}
            onRefresh={() => void refetch()}
          />
        : null,
    },
    {
      id:      "excepciones",
      label:   "Excepciones",
      icon:    <CalendarX2  className="size-3.5" />,
      content: medico
        ? <MedicoExcepcionesTab medicoId={medico.id} isEditable={canEdit} />
        : null,
    },
    {
      id:      "coberturas",
      label:   "Coberturas",
      icon:    <Users className="size-3.5" />,
      content: medico
        ? <MedicoCoberturasTab medico={medico} isEditable={canEdit} />
        : null,
    },
  ];

  return (
    <AdminDetailsDialogShell
      open={open}
      onOpenChange={onOpenChange}
      onRequestClose={() => onOpenChange(false)}
      titleSrOnly={medicoSummary?.nombreCompleto ?? "Médico"}
      descriptionSrOnly="Detalles y configuración del médico"
      header={<MedicoDialogHeader medicoSummary={medicoSummary} tipo={tipo} />}
      sections={sections}
      isLoading={isLoading && !medico}
      loadingContent={<LoadingSkeleton />}
      isError={isError && !medico}
      errorContent={
        <div className="flex flex-col items-center gap-3 py-12 text-center">
          <p className="text-sm text-txt-muted">
            No se pudo cargar la información del médico.
          </p>
          <Button variant="outline" size="sm" onClick={() => void refetch()}>
            Reintentar
          </Button>
        </div>
      }
      showCloseButton
      footer={() => null}
    />
  );
}
