import { useEffect } from "react";
import { type UseFormReturn } from "react-hook-form";
import { ShieldCheck, UserRound } from "lucide-react";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@shared/ui/form";
import { Input } from "@shared/ui/input";
import { Separator } from "@shared/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@shared/ui/select";
import type { CentroAtencionListItem, UserDetail } from "@api/types";
import type { UserDetailsFormValues } from "@/domains/auth-access/types/rbac/users.schemas";
import { CatalogCombobox, type CatalogOption } from "@/domains/auth-access/components/admin/rbac/users/CatalogCombobox";
import { CedulasSection } from "@/domains/auth-access/components/admin/rbac/users/CedulasSection";
import { PerfilesSection } from "@/domains/auth-access/components/admin/rbac/users/PerfilesSection";
import { useAreaClinicasByClinic } from "@/domains/auth-access/hooks/rbac/users/useAreaClinicasByClinic";

interface AreaClinicaOption {
  id: number;
  name: string;
}

interface UserDetailsGeneralTabProps {
  form: UseFormReturn<UserDetailsFormValues>;
  formId: string;
  clinicOptions: CentroAtencionListItem[];
  areaClinicaOptions?: AreaClinicaOption[];
  escolaridadOptions?: CatalogOption[];
  escuelaOptions?: CatalogOption[];
  tipoPersonalOptions?: CatalogOption[];
  especialidadOptions?: CatalogOption[];
  isClinicsCatalogLoading?: boolean;
  userDetail: UserDetail;
  accountIsActive: boolean;
  onSubmit: (values: UserDetailsFormValues) => void;
  onAccountStatusChange: (nextActive: boolean) => void;
  isEditable?: boolean;
  canChangeAccountStatus?: boolean;
}

const ACCOUNT_STATUS = {
  ACTIVE: "active",
  INACTIVE: "inactive",
} as const;

type AccountStatusValue = (typeof ACCOUNT_STATUS)[keyof typeof ACCOUNT_STATUS];

interface ClinicSelectOption {
  id: number;
  name: string;
  code: string;
  isActive: boolean;
}

export function UserDetailsGeneralTab({
  form,
  formId,
  clinicOptions,
  areaClinicaOptions = [],
  escolaridadOptions = [],
  escuelaOptions = [],
  tipoPersonalOptions = [],
  especialidadOptions = [],
  isClinicsCatalogLoading = false,
  userDetail,
  accountIsActive,
  onSubmit,
  onAccountStatusChange,
  isEditable = true,
  canChangeAccountStatus = true,
}: UserDetailsGeneralTabProps) {
  const accountStatusValue: AccountStatusValue = accountIsActive
    ? ACCOUNT_STATUS.ACTIVE
    : ACCOUNT_STATUS.INACTIVE;

  const clinicSelectOptions: ClinicSelectOption[] = clinicOptions.map(
    (clinic) => ({ id: clinic.id, name: clinic.name, code: clinic.code, isActive: clinic.isActive }),
  );
  const currentClinic = userDetail.clinic;
  if (
    currentClinic &&
    !clinicSelectOptions.some((clinic) => clinic.id === currentClinic.id)
  ) {
    clinicSelectOptions.unshift({ id: currentClinic.id, name: currentClinic.name, code: "", isActive: true });
  }

  const currentArea = userDetail.areaClinica;
  const allAreaOptions = [...areaClinicaOptions];
  if (currentArea && !allAreaOptions.some((a) => a.id === currentArea.id)) {
    allAreaOptions.unshift({ id: currentArea.id, name: currentArea.name });
  }

  // Asegurar que los valores guardados (aunque inactivos) estén en las opciones
  const allEscolaridadOptions = [...escolaridadOptions];
  const currentEscolaridad = userDetail.escolaridad;
  if (currentEscolaridad && !allEscolaridadOptions.some((e) => e.id === currentEscolaridad.id)) {
    allEscolaridadOptions.unshift({ id: currentEscolaridad.id, name: currentEscolaridad.name, isActive: currentEscolaridad.isActive });
  }

  const allEscuelaOptions = [...escuelaOptions];
  const currentEscuela = userDetail.escuela;
  if (currentEscuela && !allEscuelaOptions.some((e) => e.id === currentEscuela.id)) {
    allEscuelaOptions.unshift({ id: currentEscuela.id, name: currentEscuela.name, code: currentEscuela.code, isActive: currentEscuela.isActive });
  }

  const allTipoPersonalOptions = [...tipoPersonalOptions];
  const currentTipoPersonal = userDetail.tipoPersonal;
  if (currentTipoPersonal && !allTipoPersonalOptions.some((t) => t.id === currentTipoPersonal.id)) {
    allTipoPersonalOptions.unshift({ id: currentTipoPersonal.id, name: currentTipoPersonal.name, isActive: currentTipoPersonal.isActive });
  }

  const watchedClinicId = form.watch("clinicId");
  const { options: filteredAreaOptions, isLoading: isLoadingAreas } =
    useAreaClinicasByClinic(watchedClinicId, allAreaOptions);

  const currentAreaClinicaId = form.getValues("areaClinicaId");
  useEffect(() => {
    if (!watchedClinicId || isLoadingAreas) return;
    if (
      currentAreaClinicaId &&
      !filteredAreaOptions.some((a) => a.id === currentAreaClinicaId)
    ) {
      form.setValue("areaClinicaId", null);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [watchedClinicId, isLoadingAreas]);

  return (
    <Form {...form}>
      <form
        id={formId}
        onSubmit={form.handleSubmit(onSubmit)}
        className="space-y-6"
      >
        {/* Usuario + Rol (solo lectura) */}
        <div className="mx-auto w-full max-w-[480px]">
          <div className="relative h-11 rounded-2xl bg-subtle/20 ring-1 ring-line-struct/70">
            <div className="flex h-full items-center">
              <div className="flex min-w-0 flex-1 items-center gap-2 px-4 text-sm text-txt-body">
                <UserRound className="size-4 shrink-0 text-txt-muted" />
                <span className="truncate" title={userDetail.username}>
                  {userDetail.username}
                </span>
              </div>
              <div className="flex min-w-0 shrink-0 items-center gap-1.5 border-l border-line-struct/70 pl-2 pr-4 text-sm text-txt-body">
                <ShieldCheck className="size-4 shrink-0 text-txt-muted" />
                <span
                  className="truncate"
                  title={userDetail.primaryRole || "Sin rol"}
                >
                  {userDetail.primaryRole || "Sin rol"}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* No. Expediente SERMED (solo lectura: clave de vínculo con SERMED, no editable) */}
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            control={form.control}
            name="noExp"
            render={() => (
              <FormItem>
                <FormLabel>No. Expediente SERMED</FormLabel>
                <FormControl>
                  <Input
                    value={userDetail.noExp ?? "Sin expediente asignado"}
                    disabled
                  />
                </FormControl>
              </FormItem>
            )}
          />
        </div>

        {/* Datos personales */}
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            control={form.control}
            name="firstName"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Nombre</FormLabel>
                <FormControl>
                  <Input {...field} disabled={!isEditable} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="paternalName"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Apellido paterno</FormLabel>
                <FormControl>
                  <Input {...field} disabled={!isEditable} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="maternalName"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Apellido materno</FormLabel>
                <FormControl>
                  <Input {...field} disabled={!isEditable} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="email"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Correo</FormLabel>
                <FormControl>
                  <Input type="email" {...field} disabled={!isEditable} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="cdLaboral"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Clave laboral</FormLabel>
                <FormControl>
                  <Input
                    {...field}
                    value={field.value ?? ""}
                    onChange={(e) => field.onChange(e.target.value || null)}
                    placeholder="Ej. HON, BASE..."
                    disabled={!isEditable}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="telefono"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Teléfono</FormLabel>
                <FormControl>
                  <Input
                    {...field}
                    value={field.value ?? ""}
                    onChange={(e) => field.onChange(e.target.value || null)}
                    placeholder="Ej. 5512345678"
                    disabled={!isEditable}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="sexo"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Sexo</FormLabel>
                <Select
                  value={field.value ?? undefined}
                  onValueChange={(v) => field.onChange(v || null)}
                  disabled={!isEditable}
                >
                  <FormControl>
                    <SelectTrigger className="h-11">
                      <SelectValue placeholder="No registrado" />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    <SelectItem value="M">Masculino</SelectItem>
                    <SelectItem value="F">Femenino</SelectItem>
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="fechaNac"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Fecha de nacimiento <span className="text-txt-muted text-xs">(opcional)</span></FormLabel>
                <FormControl>
                  <Input
                    type="date"
                    {...field}
                    value={field.value ?? ""}
                    onChange={(e) => field.onChange(e.target.value || null)}
                    disabled={!isEditable}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        {/* Centro + Estado + Área clínica */}
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            control={form.control}
            name="clinicId"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Centro de atención</FormLabel>
                {isClinicsCatalogLoading ? (
                  <FormControl>
                    <Input
                      value={userDetail.clinic?.name ?? "Sin centro"}
                      disabled
                    />
                  </FormControl>
                ) : (
                  <FormControl>
                    <CatalogCombobox
                      value={field.value ?? null}
                      onChange={field.onChange}
                      options={clinicSelectOptions}
                      disabled={!isEditable}
                      placeholder="Selecciona un centro"
                      emptyLabel="Sin centro"
                      searchPlaceholder="Buscar por nombre..."
                    />
                  </FormControl>
                )}
                {isClinicsCatalogLoading ? (
                  <p className="text-xs text-txt-muted">
                    Cargando catálogo de centros...
                  </p>
                ) : null}
                <FormMessage />
              </FormItem>
            )}
          />

          <div className="space-y-2">
            <p
              id="user-account-status-label"
              className="text-xs font-semibold tracking-wide text-txt-muted uppercase"
            >
              Estado de la cuenta
            </p>
            <Select
              value={accountStatusValue}
              onValueChange={(value) =>
                onAccountStatusChange(value === ACCOUNT_STATUS.ACTIVE)
              }
              disabled={!canChangeAccountStatus}
            >
              <FormControl>
                <SelectTrigger
                  className="h-11"
                  aria-labelledby="user-account-status-label"
                >
                  <SelectValue placeholder="Selecciona estado" />
                </SelectTrigger>
              </FormControl>
              <SelectContent>
                <SelectItem value={ACCOUNT_STATUS.ACTIVE}>Activo</SelectItem>
                <SelectItem value={ACCOUNT_STATUS.INACTIVE}>Inactivo</SelectItem>
              </SelectContent>
            </Select>
            {!canChangeAccountStatus && isEditable ? (
              <p className="text-xs text-txt-muted">
                No puedes desactivar tu propia cuenta.
              </p>
            ) : null}
          </div>

          <FormField
            control={form.control}
            name="areaClinicaId"
            render={({ field }) => (
              <FormItem className="sm:col-span-2">
                <FormLabel>
                  Área clínica
                  {watchedClinicId ? " (del centro seleccionado)" : ""}
                </FormLabel>
                <FormControl>
                  <CatalogCombobox
                    value={field.value ?? null}
                    onChange={field.onChange}
                    options={filteredAreaOptions.map((o) => ({ ...o, isActive: true }))}
                    disabled={!isEditable || isLoadingAreas}
                    emptyLabel="Sin área"
                    searchPlaceholder="Buscar por nombre..."
                    placeholder={
                      isLoadingAreas
                        ? "Cargando áreas..."
                        : watchedClinicId
                          ? "Selecciona área del centro"
                          : "Selecciona área clínica"
                    }
                  />
                </FormControl>
                {watchedClinicId && !isLoadingAreas && filteredAreaOptions.length === 0 ? (
                  <p className="text-xs text-txt-muted">
                    El centro seleccionado no tiene áreas clínicas asignadas.
                  </p>
                ) : null}
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        {/* Escolaridad + Escuela */}
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            control={form.control}
            name="escolaridadId"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Escolaridad</FormLabel>
                <FormControl>
                  <CatalogCombobox
                    value={field.value ?? null}
                    onChange={field.onChange}
                    options={allEscolaridadOptions}
                    disabled={!isEditable}
                    placeholder="Selecciona escolaridad"
                    emptyLabel="Sin escolaridad"
                    searchPlaceholder="Buscar escolaridad..."
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="escuelaId"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Escuela</FormLabel>
                <FormControl>
                  <CatalogCombobox
                    value={field.value ?? null}
                    onChange={field.onChange}
                    options={allEscuelaOptions}
                    disabled={!isEditable}
                    placeholder="Selecciona escuela"
                    emptyLabel="Sin escuela"
                    showCode
                    searchPlaceholder="Buscar por siglas o nombre..."
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        {/* Tipo personal */}
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            control={form.control}
            name="tipoPersonalId"
            render={({ field }) => (
              <FormItem className="sm:col-span-2">
                <FormLabel>Tipo de personal</FormLabel>
                <FormControl>
                  <CatalogCombobox
                    value={field.value ?? null}
                    onChange={field.onChange}
                    options={allTipoPersonalOptions}
                    disabled={!isEditable}
                    placeholder="Selecciona tipo de personal"
                    emptyLabel="Sin tipo de personal"
                    searchPlaceholder="Buscar tipo..."
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        <Separator />

        {/* Cédulas profesionales */}
        <CedulasSection form={form} isEditable={isEditable} />

        {/* Perfiles por tipo de personal (médico/enfermería/administrativo) */}
        <PerfilesSection
          form={form}
          especialidadOptions={especialidadOptions}
          areaClinicaOptions={allAreaOptions}
          isEditable={isEditable}
        />
      </form>
    </Form>
  );
}
