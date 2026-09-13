import type {
  CedulaItem,
  Permission,
  PerfilAdministrativo,
  PerfilEnfermeria,
  PerfilMedico,
  RoleListItem,
  UserOverride,
  UserRole,
} from "@api/types";
import type { UpdateUserRequest } from "@api/types";
import type {
  CedulaFormItem,
  PerfilAdministrativoFormValues,
  PerfilEnfermeriaFormValues,
  PerfilMedicoFormValues,
  UserDetailsFormValues,
} from "@/domains/auth-access/types/rbac/users.schemas";

interface UserDetailFormSource {
  firstName?: string | null;
  paternalName?: string | null;
  maternalName?: string | null;
  email?: string | null;
  clinic?: { id: number } | null;
  noExp?: string | null;
  cdLaboral?: string | null;
  telefono?: string | null;
  sexo?: string | null;
  fechaNac?: string | null;
  areaClinica?: { id: number } | null;
  escolaridad?: { id: number } | null;
  escuela?: { id: number } | null;
  tipoPersonal?: { id: number } | null;
  cedulas?: CedulaItem[];
  perfilMedico?: PerfilMedico | null;
  perfilEnfermeria?: PerfilEnfermeria | null;
  perfilAdministrativo?: PerfilAdministrativo | null;
}

interface DraftAssigner {
  id: number;
  name: string;
}

interface AddOverrideToDraftParams {
  baseOverrides: UserOverride[];
  permissions: Permission[];
  permissionCode: string;
  nextOverrideId: number;
  assigner: DraftAssigner;
}

interface AddOverrideToDraftResult {
  overrides: UserOverride[];
  nextOverrideId: number;
}

export const mapUserDetailToFormValues = (
  detail?: UserDetailFormSource | null,
): UserDetailsFormValues => ({
  firstName: detail?.firstName ?? "",
  paternalName: detail?.paternalName ?? "",
  maternalName: detail?.maternalName ?? "",
  email: detail?.email ?? "",
  clinicId:
    typeof detail?.clinic?.id === "number" && detail.clinic.id > 0
      ? detail.clinic.id
      : null,
  noExp: detail?.noExp ?? null,
  cdLaboral: detail?.cdLaboral ?? null,
  telefono: detail?.telefono ?? null,
  sexo: (detail?.sexo as "M" | "F" | null) ?? null,
  fechaNac: detail?.fechaNac ?? null,
  areaClinicaId:
    typeof detail?.areaClinica?.id === "number" && detail.areaClinica.id > 0
      ? detail.areaClinica.id
      : null,
  escolaridadId:
    typeof detail?.escolaridad?.id === "number" && detail.escolaridad.id > 0
      ? detail.escolaridad.id
      : null,
  escuelaId:
    typeof detail?.escuela?.id === "number" && detail.escuela.id > 0
      ? detail.escuela.id
      : null,
  tipoPersonalId:
    typeof detail?.tipoPersonal?.id === "number" && detail.tipoPersonal.id > 0
      ? detail.tipoPersonal.id
      : null,
  cedulas: (detail?.cedulas ?? []).map(
    (c): CedulaFormItem => ({
      id: c.id,
      numero: c.numero,
      tipo: c.tipo,
      esPrincipal: c.esPrincipal,
    }),
  ),
  perfilMedico: {
    enabled: detail?.perfilMedico != null,
    cedulaProfesional: detail?.perfilMedico?.cedulaProfesional ?? null,
    cedulaEspecialidad: detail?.perfilMedico?.cedulaEspecialidad ?? null,
    especialidadId: detail?.perfilMedico?.especialidad?.id ?? null,
    tipoAdscripcion: detail?.perfilMedico?.tipoAdscripcion ?? null,
  },
  perfilEnfermeria: {
    enabled: detail?.perfilEnfermeria != null,
    cedulaEnfermeria: detail?.perfilEnfermeria?.cedulaEnfermeria ?? null,
    nivel: detail?.perfilEnfermeria?.nivel ?? null,
    areaClinicaId: detail?.perfilEnfermeria?.areaClinica?.id ?? null,
  },
  perfilAdministrativo: {
    enabled: detail?.perfilAdministrativo != null,
    puesto: detail?.perfilAdministrativo?.puesto ?? null,
    areaAdministrativa: detail?.perfilAdministrativo?.areaAdministrativa ?? null,
  },
});

const normalizeDraftText = (value: string | null | undefined) =>
  (value ?? "").trim();

const normalizeDraftClinicId = (value: number | null | undefined) =>
  typeof value === "number" && value > 0 && !Number.isNaN(value) ? value : null;

const normalizeCedulas = (cedulas: CedulaFormItem[]) =>
  JSON.stringify(
    cedulas.map((c) => ({
      numero: (c.numero ?? "").trim(),
      tipo: c.tipo,
      esPrincipal: c.esPrincipal,
    })),
  );

const normalizePerfilMedico = (value: PerfilMedicoFormValues) =>
  JSON.stringify(
    value.enabled
      ? {
          cedulaProfesional: normalizeDraftText(value.cedulaProfesional) || null,
          cedulaEspecialidad: normalizeDraftText(value.cedulaEspecialidad) || null,
          especialidadId: value.especialidadId ?? null,
          tipoAdscripcion: value.tipoAdscripcion,
        }
      : null,
  );

const normalizePerfilEnfermeria = (value: PerfilEnfermeriaFormValues) =>
  JSON.stringify(
    value.enabled
      ? {
          cedulaEnfermeria: normalizeDraftText(value.cedulaEnfermeria) || null,
          nivel: value.nivel,
          areaClinicaId: value.areaClinicaId ?? null,
        }
      : null,
  );

const normalizePerfilAdministrativo = (value: PerfilAdministrativoFormValues) =>
  JSON.stringify(
    value.enabled
      ? {
          puesto: normalizeDraftText(value.puesto) || null,
          areaAdministrativa: normalizeDraftText(value.areaAdministrativa) || null,
        }
      : null,
  );

export const buildUserProfilePayload = (
  baseline: UserDetailsFormValues,
  draft: UserDetailsFormValues,
): Partial<UpdateUserRequest> => {
  const payload: Partial<UpdateUserRequest> = {};

  if (
    normalizeDraftText(draft.firstName) !==
    normalizeDraftText(baseline.firstName)
  ) {
    payload.firstName = draft.firstName;
  }

  if (
    normalizeDraftText(draft.paternalName) !==
    normalizeDraftText(baseline.paternalName)
  ) {
    payload.paternalName = draft.paternalName;
  }

  if (
    normalizeDraftText(draft.maternalName) !==
    normalizeDraftText(baseline.maternalName)
  ) {
    payload.maternalName = draft.maternalName;
  }

  if (normalizeDraftText(draft.email) !== normalizeDraftText(baseline.email)) {
    payload.email = draft.email;
  }

  if (
    normalizeDraftClinicId(draft.clinicId) !==
    normalizeDraftClinicId(baseline.clinicId)
  ) {
    payload.clinicId = draft.clinicId;
  }

  if (normalizeDraftText(draft.noExp) !== normalizeDraftText(baseline.noExp)) {
    payload.noExp = draft.noExp?.trim() || null;
  }

  if (normalizeDraftText(draft.cdLaboral) !== normalizeDraftText(baseline.cdLaboral)) {
    payload.cdLaboral = draft.cdLaboral?.trim() || null;
  }

  if ((draft.telefono ?? null) !== (baseline.telefono ?? null)) {
    payload.telefono = draft.telefono?.trim() || null;
  }

  if ((draft.sexo ?? null) !== (baseline.sexo ?? null)) {
    payload.sexo = draft.sexo;
  }

  if ((draft.fechaNac ?? null) !== (baseline.fechaNac ?? null)) {
    payload.fechaNac = draft.fechaNac || null;
  }

  if (
    normalizeDraftClinicId(draft.areaClinicaId) !==
    normalizeDraftClinicId(baseline.areaClinicaId)
  ) {
    payload.areaClinicaId = draft.areaClinicaId;
  }

  if (
    normalizeDraftClinicId(draft.escolaridadId) !==
    normalizeDraftClinicId(baseline.escolaridadId)
  ) {
    payload.escolaridadId = draft.escolaridadId;
  }

  if (
    normalizeDraftClinicId(draft.escuelaId) !==
    normalizeDraftClinicId(baseline.escuelaId)
  ) {
    payload.escuelaId = draft.escuelaId;
  }

  if (
    normalizeDraftClinicId(draft.tipoPersonalId) !==
    normalizeDraftClinicId(baseline.tipoPersonalId)
  ) {
    payload.tipoPersonalId = draft.tipoPersonalId;
  }

  if (normalizeCedulas(draft.cedulas) !== normalizeCedulas(baseline.cedulas)) {
    payload.cedulas = draft.cedulas;
  }

  if (
    normalizePerfilMedico(draft.perfilMedico) !==
    normalizePerfilMedico(baseline.perfilMedico)
  ) {
    payload.perfilMedico = draft.perfilMedico.enabled
      ? {
          cedulaProfesional: draft.perfilMedico.cedulaProfesional?.trim() || null,
          cedulaEspecialidad: draft.perfilMedico.cedulaEspecialidad?.trim() || null,
          idEspecialidad: draft.perfilMedico.especialidadId,
          tipoAdscripcion: draft.perfilMedico.tipoAdscripcion,
        }
      : null;
  }

  if (
    normalizePerfilEnfermeria(draft.perfilEnfermeria) !==
    normalizePerfilEnfermeria(baseline.perfilEnfermeria)
  ) {
    payload.perfilEnfermeria = draft.perfilEnfermeria.enabled
      ? {
          cedulaEnfermeria: draft.perfilEnfermeria.cedulaEnfermeria?.trim() || null,
          nivel: draft.perfilEnfermeria.nivel,
          idAreaClinica: draft.perfilEnfermeria.areaClinicaId,
        }
      : null;
  }

  if (
    normalizePerfilAdministrativo(draft.perfilAdministrativo) !==
    normalizePerfilAdministrativo(baseline.perfilAdministrativo)
  ) {
    payload.perfilAdministrativo = draft.perfilAdministrativo.enabled
      ? {
          puesto: draft.perfilAdministrativo.puesto?.trim() || null,
          areaAdministrativa: draft.perfilAdministrativo.areaAdministrativa?.trim() || null,
        }
      : null;
  }

  return payload;
};

export const hasUserProfileChanges = (
  baseline: UserDetailsFormValues,
  draft: UserDetailsFormValues,
) => {
  return Object.keys(buildUserProfilePayload(baseline, draft)).length > 0;
};

export const addRoleToDraft = (
  baseRoles: UserRole[],
  roleOptions: RoleListItem[],
  roleId: number,
  assigner: DraftAssigner,
): UserRole[] => {
  const selectedRole = roleOptions.find((role) => role.id === roleId);
  if (!selectedRole) return baseRoles;
  if (baseRoles.some((role) => role.id === roleId)) return baseRoles;

  const hasPrimary = baseRoles.some((role) => role.isPrimary);

  return [
    ...baseRoles,
    {
      id: selectedRole.id,
      name: selectedRole.name,
      description: selectedRole.description,
      isPrimary: !hasPrimary,
      assignedAt: new Date().toISOString(),
      assignedBy: { ...assigner },
    },
  ];
};

export const setPrimaryRoleInDraft = (
  baseRoles: UserRole[],
  roleId: number,
  assigner: DraftAssigner,
): UserRole[] => {
  const now = new Date().toISOString();

  return baseRoles.map((role) => ({
    ...role,
    isPrimary: role.id === roleId,
    ...(role.id === roleId
      ? {
          assignedAt: now,
          assignedBy: { ...assigner },
        }
      : {}),
  }));
};

export const removeRoleFromDraft = (
  baseRoles: UserRole[],
  roleId: number,
): UserRole[] => {
  const remainingRoles = baseRoles.filter((role) => role.id !== roleId);

  if (remainingRoles.length === 0) return remainingRoles;
  if (remainingRoles.some((role) => role.isPrimary)) return remainingRoles;

  return [
    { ...remainingRoles[0], isPrimary: true },
    ...remainingRoles.slice(1),
  ];
};

export const addOverrideToDraft = ({
  baseOverrides,
  permissions,
  permissionCode,
  nextOverrideId,
  assigner,
}: AddOverrideToDraftParams): AddOverrideToDraftResult => {
  if (
    baseOverrides.some((override) => override.permissionCode === permissionCode)
  ) {
    return {
      overrides: baseOverrides,
      nextOverrideId,
    };
  }

  const permission = permissions.find((item) => item.code === permissionCode);

  return {
    overrides: [
      ...baseOverrides,
      {
        id: nextOverrideId,
        permissionCode,
        permissionDescription: permission?.description ?? permissionCode,
        effect: "ALLOW",
        expiresAt: null,
        isExpired: false,
        assignedAt: new Date().toISOString(),
        assignedBy: { ...assigner },
      },
    ],
    nextOverrideId: nextOverrideId - 1,
  };
};

export const toggleOverrideEffectInDraft = (
  baseOverrides: UserOverride[],
  permissionCode: string,
): UserOverride[] => {
  return baseOverrides.map((override) =>
    override.permissionCode === permissionCode
      ? {
          ...override,
          effect: override.effect === "ALLOW" ? "DENY" : "ALLOW",
        }
      : override,
  );
};

export const setOverrideDateInDraft = (
  baseOverrides: UserOverride[],
  permissionCode: string,
  value: string,
): UserOverride[] => {
  return baseOverrides.map((override) =>
    override.permissionCode === permissionCode
      ? {
          ...override,
          expiresAt: value || null,
        }
      : override,
  );
};

export const removeOverrideFromDraft = (
  baseOverrides: UserOverride[],
  permissionCode: string,
): UserOverride[] => {
  return baseOverrides.filter(
    (override) => override.permissionCode !== permissionCode,
  );
};
