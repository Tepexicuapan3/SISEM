import { useEffect, useRef, useState } from "react";
import { useForm, type Resolver } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import { useDebounce } from "@shared/hooks/useDebounce";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@shared/ui/dialog";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@shared/ui/form";
import { Input } from "@shared/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@shared/ui/select";
import { ScrollArea } from "@shared/ui/ScrollArea";
import type { CentroAtencionListItem, RoleListItem } from "@api/types";
import { useCreateUser } from "@/domains/auth-access/hooks/rbac/users/useCreateUser";
import { useEmpleadoSermedLookup } from "@/domains/auth-access/hooks/rbac/users/useEmpleadoSermedLookup";
import { useAreaClinicasByClinic } from "@/domains/auth-access/hooks/rbac/users/useAreaClinicasByClinic";
import { UserCreateSidePanel } from "@/domains/auth-access/components/admin/rbac/users/UserCreateSidePanel";
import {
  createUserSchema,
  type CreateUserFormValues,
} from "@/domains/auth-access/types/rbac/users.schemas";
import { getUserErrorMessage } from "@/domains/auth-access/adapters/rbac/users/users.feedback";
import { UserDialogHeader } from "@/domains/auth-access/components/admin/rbac/users/UserDialogHeader";
import { CatalogCombobox, type CatalogOption } from "@/domains/auth-access/components/admin/rbac/users/CatalogCombobox";
import { CedulasSection } from "@/domains/auth-access/components/admin/rbac/users/CedulasSection";

interface AreaClinicaOption {
  id: number;
  name: string;
}

interface UserCreateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  roleOptions: RoleListItem[];
  clinicOptions: CentroAtencionListItem[];
  areaClinicaOptions?: AreaClinicaOption[];
  escolaridadOptions?: CatalogOption[];
  escuelaOptions?: CatalogOption[];
  tipoPersonalOptions?: CatalogOption[];
}

const DEFAULT_VALUES: CreateUserFormValues = {
  username: "",
  firstName: "",
  paternalName: "",
  maternalName: "",
  email: "",
  clinicId: null,
  primaryRoleId: 0,
  noExp: null,
  cdLaboral: null,
  telefono: null,
  sexo: null,
  fechaNac: null,
  areaClinicaId: null,
  escolaridadId: null,
  escuelaId: null,
  tipoPersonalId: null,
  cedulas: [],
};

const FORM_ID = "user-create-form";

export function UserCreateDialog({
  open,
  onOpenChange,
  roleOptions,
  clinicOptions,
  areaClinicaOptions = [],
  escolaridadOptions = [],
  escuelaOptions = [],
  tipoPersonalOptions = [],
}: UserCreateDialogProps) {
  const createUser = useCreateUser();

  const form = useForm<CreateUserFormValues>({
    resolver: zodResolver(createUserSchema) as Resolver<CreateUserFormValues>,
    defaultValues: DEFAULT_VALUES,
  });

  // SERMED lookup — automático: se dispara solo al dejar de tipear el expediente
  const NO_EXP_MIN_LENGTH = 4;
  const {
    lookup,
    reset: resetLookup,
    isLoading: isLookingUp,
    result: lookupResult,
    error: lookupError,
  } = useEmpleadoSermedLookup();
  const [lookupAttempted, setLookupAttempted] = useState(false);
  const lastLookedUpRef = useRef<string | null>(null);

  const watchedNoExp = form.watch("noExp");
  const debouncedNoExp = useDebounce(watchedNoExp ?? "", 500);

  useEffect(() => {
    const trimmed = debouncedNoExp?.trim() ?? "";

    if (trimmed.length < NO_EXP_MIN_LENGTH) {
      lastLookedUpRef.current = null;
      if (!trimmed) {
        setLookupAttempted(false);
        resetLookup();
      }
      return;
    }

    if (lastLookedUpRef.current === trimmed) return;
    lastLookedUpRef.current = trimmed;

    setLookupAttempted(true);
    void lookup(trimmed).then((found) => {
      if (found) {
        if (found.firstName) form.setValue("firstName", found.firstName);
        if (found.paternalName) form.setValue("paternalName", found.paternalName);
        if (found.maternalName) form.setValue("maternalName", found.maternalName);
        if (found.cdLaboral) form.setValue("cdLaboral", found.cdLaboral);
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedNoExp]);

  // Filter areas by selected clinic
  const watchedClinicId = form.watch("clinicId");
  const { options: filteredAreaOptions, isLoading: isLoadingAreas } =
    useAreaClinicasByClinic(watchedClinicId, areaClinicaOptions);

  // Clear areaClinicaId when clinic changes and the area is no longer in list
  const currentAreaClinicaId = form.watch("areaClinicaId");
  useEffect(() => {
    if (!watchedClinicId || isLoadingAreas) return;
    if (
      currentAreaClinicaId &&
      !filteredAreaOptions.some((a) => a.id === currentAreaClinicaId)
    ) {
      form.setValue("areaClinicaId", null);
    }
  }, [watchedClinicId, currentAreaClinicaId, filteredAreaOptions, isLoadingAreas]);

  const handleDialogOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) {
      form.reset(DEFAULT_VALUES);
      setLookupAttempted(false);
      lastLookedUpRef.current = null;
      resetLookup();
    }
    onOpenChange(nextOpen);
  };

  const onSubmit = async (values: CreateUserFormValues) => {
    try {
      const result = await createUser.mutateAsync({
        data: {
          username: values.username,
          firstName: values.firstName,
          paternalName: values.paternalName,
          maternalName: values.maternalName,
          email: values.email || undefined,
          clinicId: values.clinicId ?? null,
          primaryRoleId: values.primaryRoleId,
          noExp: values.noExp ?? null,
          cdLaboral: values.cdLaboral ?? null,
          telefono: values.telefono ?? null,
          sexo: values.sexo ?? null,
          fechaNac: values.fechaNac ?? null,
          areaClinicaId: values.areaClinicaId ?? null,
          escolaridadId: values.escolaridadId ?? null,
          escuelaId: values.escuelaId ?? null,
          tipoPersonalId: values.tipoPersonalId ?? null,
          cedulas: values.cedulas.length > 0 ? values.cedulas : undefined,
        },
      });

      toast.success("Usuario creado", {
        description: `El usuario ${result.username} se creó correctamente.`,
      });
      handleDialogOpenChange(false);
    } catch (error) {
      toast.error("No se pudo crear el usuario", {
        description: getUserErrorMessage(error, "Error al crear usuario"),
      });
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleDialogOpenChange}>
      <DialogContent
        showCloseButton={false}
        className="h-[70vh] max-h-[70vh] w-[96vw] max-w-none overflow-hidden rounded-3xl bg-paper p-0 sm:max-w-none lg:w-[980px] xl:w-[1060px]"
      >
        <div className="flex h-full min-h-0">
          <UserCreateSidePanel />

          <div className="flex min-h-0 min-w-0 flex-1 flex-col">
            <DialogHeader className="px-5 pt-5 lg:px-8 lg:pt-5">
              <DialogTitle className="sr-only">Nuevo usuario</DialogTitle>
              <DialogDescription className="sr-only">
                Crea un usuario con acceso a RBAC.
              </DialogDescription>
              <div className="lg:hidden">
                <UserDialogHeader
                  title="Nuevo usuario"
                  subtitle="Completa los datos para generar acceso"
                  status={<Badge variant="outline">Plantilla</Badge>}
                />
              </div>
            </DialogHeader>

            <ScrollArea
              className="min-h-0 flex-1 px-5 pb-6 lg:px-8 lg:pb-8"
              viewportClassName="overflow-x-auto"
            >
              <div className="space-y-5 pt-0">
                <div className="rounded-2xl border border-line-struct bg-paper p-4">
                  <Form {...form}>
                    <form
                      id={FORM_ID}
                      onSubmit={form.handleSubmit(onSubmit)}
                      className="space-y-6"
                    >
                      {/* No. expediente SERMED — primer campo: autocompleta el resto al escribir */}
                      <div className="grid gap-4 sm:grid-cols-2">
                        <FormField
                          control={form.control}
                          name="noExp"
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel>No. expediente SERMED</FormLabel>
                              <div className="relative">
                                <FormControl>
                                  <Input
                                    {...field}
                                    value={field.value ?? ""}
                                    onChange={(e) =>
                                      field.onChange(e.target.value || null)
                                    }
                                    placeholder="Ej. 123456"
                                    autoFocus
                                    className={isLookingUp ? "pr-9" : undefined}
                                  />
                                </FormControl>
                                {isLookingUp ? (
                                  <Loader2 className="absolute top-1/2 right-3 size-4 -translate-y-1/2 animate-spin text-txt-muted" />
                                ) : null}
                              </div>
                              {lookupAttempted && !isLookingUp && lookupResult ? (
                                <p className="text-xs text-status-stable">
                                  Encontrado:{" "}
                                  {[
                                    lookupResult.firstName,
                                    lookupResult.paternalName,
                                    lookupResult.maternalName,
                                  ]
                                    .filter(Boolean)
                                    .join(" ")}
                                </p>
                              ) : null}
                              {lookupAttempted && !isLookingUp && lookupError ? (
                                <p className="text-xs text-status-critical">
                                  {lookupError}
                                </p>
                              ) : null}
                              <FormMessage />
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
                                <Input {...field} />
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
                                <Input {...field} />
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
                                <Input {...field} />
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
                                <Input type="email" {...field} />
                              </FormControl>
                              <FormMessage />
                            </FormItem>
                          )}
                        />
                      </div>

                      {/* Cuenta + SERMED */}
                      <div className="grid gap-4 sm:grid-cols-2">
                        <FormField
                          control={form.control}
                          name="username"
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel>Usuario</FormLabel>
                              <FormControl>
                                <Input {...field} />
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
                              <FormLabel>Clave laboral SERMED</FormLabel>
                              <FormControl>
                                <Input
                                  {...field}
                                  value={field.value ?? ""}
                                  onChange={(e) =>
                                    field.onChange(e.target.value || null)
                                  }
                                  placeholder="Se llena al buscar expediente"
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
                              <FormLabel>Teléfono <span className="text-txt-muted text-xs">(opcional)</span></FormLabel>
                              <FormControl>
                                <Input
                                  {...field}
                                  value={field.value ?? ""}
                                  onChange={(e) => field.onChange(e.target.value || null)}
                                  placeholder="Ej. 5512345678"
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
                              <FormLabel>Sexo <span className="text-txt-muted text-xs">(opcional)</span></FormLabel>
                              <Select
                                value={field.value ?? ""}
                                onValueChange={(v) => field.onChange(v || null)}
                              >
                                <FormControl>
                                  <SelectTrigger className="h-11">
                                    <SelectValue placeholder="Selecciona" />
                                  </SelectTrigger>
                                </FormControl>
                                <SelectContent>
                                  <SelectItem value="M">Masculino</SelectItem>
                                  <SelectItem value="F">Femenino</SelectItem>
                                  <SelectItem value="O">Otro</SelectItem>
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
                                />
                              </FormControl>
                              <FormMessage />
                            </FormItem>
                          )}
                        />

                        {/* Centro de atención */}
                        <FormField
                          control={form.control}
                          name="clinicId"
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel>Centro de atención</FormLabel>
                              <FormControl>
                                <CatalogCombobox
                                  value={field.value}
                                  onChange={field.onChange}
                                  options={clinicOptions}
                                  placeholder="Selecciona un centro"
                                  emptyLabel="Sin centro"
                                  searchPlaceholder="Buscar por nombre..."
                                />
                              </FormControl>
                              <FormMessage />
                            </FormItem>
                          )}
                        />

                        {/* Área clínica filtrada por centro */}
                        <FormField
                          control={form.control}
                          name="areaClinicaId"
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel>
                                Área clínica
                                {watchedClinicId ? " (del centro)" : ""}
                              </FormLabel>
                              <FormControl>
                                <CatalogCombobox
                                  value={field.value ?? null}
                                  onChange={field.onChange}
                                  options={filteredAreaOptions.map((o) => ({ ...o, isActive: true }))}
                                  disabled={isLoadingAreas}
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
                              {watchedClinicId &&
                              !isLoadingAreas &&
                              filteredAreaOptions.length === 0 ? (
                                <p className="text-xs text-txt-muted">
                                  El centro no tiene áreas clínicas asignadas.
                                </p>
                              ) : null}
                              <FormMessage />
                            </FormItem>
                          )}
                        />
                      </div>

                      {/* Rol primario */}
                      <div className="grid gap-4 sm:grid-cols-2">
                        <FormField
                          control={form.control}
                          name="primaryRoleId"
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel>Rol primario</FormLabel>
                              <Select
                                value={
                                  field.value ? field.value.toString() : ""
                                }
                                onValueChange={(value) =>
                                  field.onChange(Number(value))
                                }
                              >
                                <FormControl>
                                  <SelectTrigger className="h-11">
                                    <SelectValue placeholder="Selecciona un rol" />
                                  </SelectTrigger>
                                </FormControl>
                                <SelectContent>
                                  {roleOptions.map((role) => (
                                    <SelectItem
                                      key={role.id}
                                      value={role.id.toString()}
                                    >
                                      {role.name}
                                    </SelectItem>
                                  ))}
                                </SelectContent>
                              </Select>
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
                                  options={escolaridadOptions}
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
                                  options={escuelaOptions}
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
                            <FormItem>
                              <FormLabel>Tipo de personal</FormLabel>
                              <FormControl>
                                <CatalogCombobox
                                  value={field.value ?? null}
                                  onChange={field.onChange}
                                  options={tipoPersonalOptions}
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

                      {/* Cédulas profesionales */}
                      <CedulasSection form={form} isEditable={true} />
                    </form>
                  </Form>
                </div>
              </div>
            </ScrollArea>

            <DialogFooter className="flex flex-col gap-3 border-t border-line-struct px-5 py-4 sm:flex-row sm:items-center sm:justify-between lg:px-8">
              <div className="text-xs text-txt-muted">
                Completa los campos requeridos.
              </div>
              <div className="flex flex-col gap-2 sm:flex-row">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => handleDialogOpenChange(false)}
                >
                  Cancelar
                </Button>
                <Button
                  type="submit"
                  form={FORM_ID}
                  disabled={createUser.isPending}
                >
                  Crear usuario
                </Button>
              </div>
            </DialogFooter>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
