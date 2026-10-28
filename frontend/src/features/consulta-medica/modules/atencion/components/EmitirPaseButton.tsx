import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Send, Loader2 } from "lucide-react";
import * as z from "zod";
import { ApiError } from "@api/utils/errors";
import { avisoAutorizacionPaseEmitido } from "@features/autorizaciones/domain/pase-autorizacion.format";
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
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@shared/ui/form";
import { Textarea } from "@shared/ui/textarea";
import { Checkbox } from "@shared/ui/checkbox";
import { Label } from "@shared/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@shared/ui/select";
import { especialidadesAPI } from "@api/resources/catalogos/especialidades.api";
import { centrosAtencionAPI } from "@api/resources/catalogos/centros-atencion.api";
import { estudiosMedicosAPI } from "@api/resources/catalogos/estudios-medicos.api";
import { useCreateReferral } from "@features/consulta-medica/modules/atencion/mutations/useCreateReferral";
import type { ReferralType } from "@api/types";

const EMITIR_PASE_DOMAIN_ERROR_MESSAGE: Record<string, string> = {
  ROLE_NOT_ALLOWED: "No tenes permiso para emitir pases.",
  VISIT_NOT_FOUND: "La visita ya no existe o fue cerrada por otro usuario.",
  CONSULTATION_NOT_FOUND: "Primero guarda el diagnostico de esta consulta.",
  REFERRAL_ALREADY_EXISTS: "Ya existe un pase activo de este tipo para esta consulta.",
  VALIDATION_ERROR: "Revisa los datos capturados antes de emitir.",
  PERMISSION_DENIED: "No tenes permiso para ejecutar esta accion.",
};

const FALLBACK_EMITIR_PASE_ERROR_MESSAGE =
  "No se pudo emitir el pase. Intenta nuevamente.";

const resolveEmitirPaseError = (error: unknown): string => {
  if (!(error instanceof ApiError)) {
    return FALLBACK_EMITIR_PASE_ERROR_MESSAGE;
  }
  return (
    EMITIR_PASE_DOMAIN_ERROR_MESSAGE[error.code] ||
    error.message ||
    FALLBACK_EMITIR_PASE_ERROR_MESSAGE
  );
};

const REFERRAL_TYPE_LABEL: Record<ReferralType, string> = {
  laboratorio: "Laboratorio",
  gabinete: "Gabinete",
  especialidad: "Especialidad",
  hospitalizacion: "Hospitalización",
  tercer_nivel: "Tercer Nivel",
};

const STUDY_REFERRAL_TYPES = new Set<ReferralType>(["laboratorio", "gabinete"]);

const emitirPaseSchema = z
  .object({
    referralType: z.enum(
      ["laboratorio", "gabinete", "especialidad", "hospitalizacion", "tercer_nivel"],
      { error: "Selecciona un tipo de pase" },
    ),
    destinationCenterId: z.string().optional(),
    specialtyId: z.string().optional(),
    requestedCare: z.string().optional(),
    visitType: z.enum(["primera_vez", "subsecuente"]).optional(),
    studyTypeIds: z.array(z.string()).optional(),
  })
  .superRefine((values, ctx) => {
    if (STUDY_REFERRAL_TYPES.has(values.referralType)) {
      if (!values.studyTypeIds || values.studyTypeIds.length === 0) {
        ctx.addIssue({
          code: "custom",
          path: ["studyTypeIds"],
          message: "Selecciona al menos un estudio.",
        });
      }
      return;
    }

    if (values.referralType === "especialidad") {
      if (!values.destinationCenterId) {
        ctx.addIssue({
          code: "custom",
          path: ["destinationCenterId"],
          message: "Selecciona el hospital de referencia.",
        });
      }
      if (!values.specialtyId) {
        ctx.addIssue({
          code: "custom",
          path: ["specialtyId"],
          message: "Selecciona la especialidad.",
        });
      }
      if (!values.requestedCare?.trim()) {
        ctx.addIssue({
          code: "custom",
          path: ["requestedCare"],
          message: "Indica la atención solicitada.",
        });
      }
      return;
    }

    if (values.referralType === "hospitalizacion") {
      if (!values.destinationCenterId) {
        ctx.addIssue({
          code: "custom",
          path: ["destinationCenterId"],
          message: "Selecciona el hospital destino.",
        });
      }
      if (!values.specialtyId) {
        ctx.addIssue({
          code: "custom",
          path: ["specialtyId"],
          message: "Selecciona el servicio.",
        });
      }
      return;
    }

    if (values.referralType === "tercer_nivel") {
      if (!values.destinationCenterId) {
        ctx.addIssue({
          code: "custom",
          path: ["destinationCenterId"],
          message: "Selecciona el instituto destino.",
        });
      }
    }
  });

type EmitirPaseFormValues = z.infer<typeof emitirPaseSchema>;

const buildDefaultValues = (): EmitirPaseFormValues => ({
  referralType: "laboratorio",
  destinationCenterId: "",
  specialtyId: "",
  requestedCare: "",
  visitType: undefined,
  studyTypeIds: [],
});

interface EmitirPaseButtonProps {
  visitId: number;
  disabled?: boolean;
}

export function EmitirPaseButton({ visitId, disabled }: EmitirPaseButtonProps) {
  const [open, setOpen] = useState(false);
  const createReferral = useCreateReferral();

  const form = useForm<EmitirPaseFormValues>({
    resolver: zodResolver(emitirPaseSchema),
    defaultValues: buildDefaultValues(),
  });

  const referralType = form.watch("referralType");
  const isStudyReferral = STUDY_REFERRAL_TYPES.has(referralType);
  const needsDestinationCenter =
    referralType === "especialidad" ||
    referralType === "hospitalizacion" ||
    referralType === "tercer_nivel";
  const needsSpecialty =
    referralType === "especialidad" || referralType === "hospitalizacion";

  const { data: especialidades } = useQuery({
    queryKey: ["catalogos", "especialidades", "options"],
    queryFn: () => especialidadesAPI.getAll({ pageSize: 200 }),
    enabled: open && needsSpecialty,
  });

  const { data: centros } = useQuery({
    queryKey: ["catalogos", "centros-atencion", "options"],
    queryFn: () => centrosAtencionAPI.getAll({ pageSize: 200 }),
    enabled: open && needsDestinationCenter,
  });

  const { data: tiposEstudio } = useQuery({
    queryKey: ["catalogos", "estudios-medicos", "options"],
    queryFn: () => estudiosMedicosAPI.getAll({ pageSize: 200 }),
    enabled: open && isStudyReferral,
  });

  const centrosFiltrados = (centros?.items ?? []).filter((centro) => {
    if (referralType === "tercer_nivel") return centro.centerType === "INSTITUTO";
    if (referralType === "especialidad" || referralType === "hospitalizacion") {
      return centro.centerType === "HOSPITAL";
    }
    return true;
  });

  const handleOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) {
      form.reset(buildDefaultValues());
    }
    setOpen(nextOpen);
  };

  const onSubmit = async (values: EmitirPaseFormValues) => {
    try {
      const referral = await createReferral.mutateAsync({
        visitId,
        data: {
          referralType: values.referralType,
          destinationCenterId: values.destinationCenterId
            ? Number(values.destinationCenterId)
            : undefined,
          specialtyId: values.specialtyId ? Number(values.specialtyId) : undefined,
          requestedCare: values.requestedCare?.trim() || undefined,
          visitType: values.visitType,
          studies: isStudyReferral
            ? (values.studyTypeIds ?? []).map((id) => ({ studyTypeId: Number(id) }))
            : undefined,
        },
      });
      toast.success("Pase emitido", {
        description:
          `Folio ${referral.folio} — ${REFERRAL_TYPE_LABEL[referral.referralType]}.` +
          // Motor de autorizaciones: avisa si los estudios marcados quedaron por autorizar.
          avisoAutorizacionPaseEmitido(referral.authorizationStatus),
      });
      handleOpenChange(false);
    } catch (error) {
      toast.error("No se pudo emitir el pase", {
        description: resolveEmitirPaseError(error),
      });
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button type="button" variant="outline" disabled={disabled}>
          <Send className="mr-2 size-4" />
          Emitir pase
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Emitir pase / referencia</DialogTitle>
          <DialogDescription>
            Se emite sobre el diagnóstico ya guardado de esta consulta. Solo un
            pase activo por tipo.
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="referralType"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Tipo de pase</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="Selecciona un tipo" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {Object.entries(REFERRAL_TYPE_LABEL).map(([value, label]) => (
                        <SelectItem key={value} value={value}>
                          {label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            {isStudyReferral ? (
              <FormField
                control={form.control}
                name="studyTypeIds"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Estudios solicitados</FormLabel>
                    <div className="max-h-48 space-y-2 overflow-y-auto rounded-lg border p-3">
                      {(tiposEstudio?.items ?? []).map((tipo) => {
                        const value = String(tipo.id);
                        const checked = (field.value ?? []).includes(value);
                        return (
                          <div key={tipo.id} className="flex items-center gap-2">
                            <Checkbox
                              checked={checked}
                              onCheckedChange={(next) => {
                                const current = field.value ?? [];
                                field.onChange(
                                  next
                                    ? [...current, value]
                                    : current.filter((item) => item !== value),
                                );
                              }}
                            />
                            <Label className="font-normal">{tipo.name}</Label>
                          </div>
                        );
                      })}
                    </div>
                    <FormMessage />
                  </FormItem>
                )}
              />
            ) : null}

            {needsDestinationCenter ? (
              <FormField
                control={form.control}
                name="destinationCenterId"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      {referralType === "tercer_nivel" ? "Instituto destino" : "Hospital destino"}
                    </FormLabel>
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Selecciona un destino" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {centrosFiltrados.map((centro) => (
                          <SelectItem key={centro.id} value={String(centro.id)}>
                            {centro.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
            ) : null}

            {needsSpecialty ? (
              <FormField
                control={form.control}
                name="specialtyId"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      {referralType === "hospitalizacion" ? "Servicio" : "Especialidad"}
                    </FormLabel>
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Selecciona una opción" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {(especialidades?.items ?? []).map((especialidad) => (
                          <SelectItem key={especialidad.id} value={String(especialidad.id)}>
                            {especialidad.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
            ) : null}

            {referralType === "especialidad" ? (
              <FormField
                control={form.control}
                name="requestedCare"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Atención solicitada</FormLabel>
                    <FormControl>
                      <Textarea {...field} rows={2} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            ) : null}

            {referralType === "especialidad" || referralType === "tercer_nivel" ? (
              <FormField
                control={form.control}
                name="visitType"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Tipo de cita en destino (opcional)</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Selecciona una opción" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="primera_vez">Primera Vez</SelectItem>
                        <SelectItem value="subsecuente">Subsecuente</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
            ) : null}

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => handleOpenChange(false)}
              >
                Cancelar
              </Button>
              <Button type="submit" disabled={createReferral.isPending}>
                {createReferral.isPending ? (
                  <Loader2 className="mr-2 size-4 animate-spin" />
                ) : null}
                Emitir
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
