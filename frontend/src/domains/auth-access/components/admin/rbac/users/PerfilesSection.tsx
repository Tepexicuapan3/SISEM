import { type UseFormReturn } from "react-hook-form";
import {
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
import { Switch } from "@shared/ui/switch";
import { CatalogCombobox, type CatalogOption } from "@/domains/auth-access/components/admin/rbac/users/CatalogCombobox";
import type { UserDetailsFormValues } from "@/domains/auth-access/types/rbac/users.schemas";

interface AreaClinicaOption {
  id: number;
  name: string;
}

interface PerfilesSectionProps {
  form: UseFormReturn<UserDetailsFormValues>;
  especialidadOptions?: CatalogOption[];
  areaClinicaOptions?: AreaClinicaOption[];
  isEditable?: boolean;
}

const NIVEL_LABELS = {
  GENERAL: "General",
  ESPECIALISTA: "Especialista",
  JEFE_PISO: "Jefe de Piso",
} as const;

export function PerfilesSection({
  form,
  especialidadOptions = [],
  areaClinicaOptions = [],
  isEditable = true,
}: PerfilesSectionProps) {
  const medicoEnabled = form.watch("perfilMedico.enabled");
  const enfermeriaEnabled = form.watch("perfilEnfermeria.enabled");
  const administrativoEnabled = form.watch("perfilAdministrativo.enabled");

  return (
    <div className="space-y-6">
      <Separator />
      <p className="text-xs font-semibold tracking-wide text-txt-muted uppercase">
        Perfiles profesionales
      </p>

      {/* Perfil Médico */}
      <div className="space-y-3 rounded-xl border border-line-struct/60 p-4">
        <div className="flex items-center justify-between">
          <p className="text-sm font-medium">Perfil médico</p>
          <FormField
            control={form.control}
            name="perfilMedico.enabled"
            render={({ field }) => (
              <Switch
                checked={field.value}
                onCheckedChange={field.onChange}
                disabled={!isEditable}
                aria-label="Activar perfil médico"
              />
            )}
          />
        </div>
        {medicoEnabled ? (
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField
              control={form.control}
              name="perfilMedico.cedulaProfesional"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Cédula profesional</FormLabel>
                  <FormControl>
                    <Input
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
            <FormField
              control={form.control}
              name="perfilMedico.cedulaEspecialidad"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Cédula de especialidad</FormLabel>
                  <FormControl>
                    <Input
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
            <FormField
              control={form.control}
              name="perfilMedico.especialidadId"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Especialidad</FormLabel>
                  <FormControl>
                    <CatalogCombobox
                      value={field.value ?? null}
                      onChange={field.onChange}
                      options={especialidadOptions}
                      disabled={!isEditable}
                      placeholder="Selecciona especialidad"
                      emptyLabel="Sin especialidad"
                      searchPlaceholder="Buscar especialidad..."
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="perfilMedico.tipoAdscripcion"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Tipo de adscripción</FormLabel>
                  <Select
                    value={field.value ?? undefined}
                    onValueChange={(v) => field.onChange(v || null)}
                    disabled={!isEditable}
                  >
                    <FormControl>
                      <SelectTrigger className="h-11">
                        <SelectValue placeholder="Selecciona tipo" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value="CLINICA">Clínica</SelectItem>
                      <SelectItem value="HOSPITAL">Hospital</SelectItem>
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>
        ) : null}
      </div>

      {/* Perfil Enfermería */}
      <div className="space-y-3 rounded-xl border border-line-struct/60 p-4">
        <div className="flex items-center justify-between">
          <p className="text-sm font-medium">Perfil enfermería</p>
          <FormField
            control={form.control}
            name="perfilEnfermeria.enabled"
            render={({ field }) => (
              <Switch
                checked={field.value}
                onCheckedChange={field.onChange}
                disabled={!isEditable}
                aria-label="Activar perfil enfermería"
              />
            )}
          />
        </div>
        {enfermeriaEnabled ? (
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField
              control={form.control}
              name="perfilEnfermeria.cedulaEnfermeria"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Cédula de enfermería</FormLabel>
                  <FormControl>
                    <Input
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
            <FormField
              control={form.control}
              name="perfilEnfermeria.nivel"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Nivel</FormLabel>
                  <Select
                    value={field.value ?? undefined}
                    onValueChange={(v) => field.onChange(v || null)}
                    disabled={!isEditable}
                  >
                    <FormControl>
                      <SelectTrigger className="h-11">
                        <SelectValue placeholder="Selecciona nivel" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {Object.entries(NIVEL_LABELS).map(([value, label]) => (
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
            <FormField
              control={form.control}
              name="perfilEnfermeria.areaClinicaId"
              render={({ field }) => (
                <FormItem className="sm:col-span-2">
                  <FormLabel>Área clínica</FormLabel>
                  <FormControl>
                    <CatalogCombobox
                      value={field.value ?? null}
                      onChange={field.onChange}
                      options={areaClinicaOptions.map((o) => ({ ...o, isActive: true }))}
                      disabled={!isEditable}
                      placeholder="Selecciona área clínica"
                      emptyLabel="Sin área"
                      searchPlaceholder="Buscar por nombre..."
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>
        ) : null}
      </div>

      {/* Perfil Administrativo */}
      <div className="space-y-3 rounded-xl border border-line-struct/60 p-4">
        <div className="flex items-center justify-between">
          <p className="text-sm font-medium">Perfil administrativo</p>
          <FormField
            control={form.control}
            name="perfilAdministrativo.enabled"
            render={({ field }) => (
              <Switch
                checked={field.value}
                onCheckedChange={field.onChange}
                disabled={!isEditable}
                aria-label="Activar perfil administrativo"
              />
            )}
          />
        </div>
        {administrativoEnabled ? (
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField
              control={form.control}
              name="perfilAdministrativo.puesto"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Puesto</FormLabel>
                  <FormControl>
                    <Input
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
            <FormField
              control={form.control}
              name="perfilAdministrativo.areaAdministrativa"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Área administrativa</FormLabel>
                  <FormControl>
                    <Input
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
        ) : null}
      </div>
    </div>
  );
}
