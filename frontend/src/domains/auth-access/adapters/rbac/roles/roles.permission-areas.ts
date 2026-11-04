import {
  comparePermissionCodesByHierarchy,
  formatPermissionSegment,
  parsePermissionCode,
} from "@/domains/auth-access/adapters/rbac/shared/permission-hierarchy";
import type { Permission } from "@api/types";

/**
 * Agrupa el catalogo de permisos por area (primer segmento del codigo) para
 * la pestaña "Permisos" del rol: nombres legibles, busqueda sin acentos y
 * filtro por asignados. La matriz por modulo vive en roles.permission-matrix.
 */

export type PermissionFilter = "todos" | "asignados" | "sin-asignar";

const AREA_LABELS: Record<string, string> = {
  admin: "Administración",
  alcance: "Alcance por centro",
  clinico: "Clínico",
  documentos: "Documentos",
  expedientes: "Expedientes",
  farmacia: "Farmacia",
  flow: "Flujo de atención",
  recepcion: "Recepción",
  servicios: "Servicios",
};

/**
 * Permisos que dejan ver o trabajar fuera del centro propio o saltar una
 * regla: se marcan para que no se asignen sin querer.
 */
const SENSITIVE_PATTERNS = [/^alcance:/, /todos_centros/, /otros_centros/, /:excepcion$/, /:global$/];

export const isSensitivePermission = (code: string) =>
  SENSITIVE_PATTERNS.some((pattern) => pattern.test(code));

const capitalize = (value: string) => (value ? value[0].toUpperCase() + value.slice(1) : value);

export const getAreaLabel = (area: string) =>
  AREA_LABELS[area] ?? capitalize(formatPermissionSegment(area));

const normalize = (value: string) =>
  value
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .trim();

export interface PermissionAreaItem {
  permission: Permission;
  /** Modulo dentro del area (segundo segmento), legible. */
  section: string;
  sensitive: boolean;
}

export interface PermissionArea {
  key: string;
  label: string;
  /** Items que pasan la busqueda y el filtro. */
  items: PermissionAreaItem[];
  /** Todos los permisos del area (para el contador y el "todo el area"). */
  all: Permission[];
  assignedCount: number;
}

interface BuildOptions {
  query: string;
  filter: PermissionFilter;
  isAssigned: (code: string) => boolean;
}

export const buildPermissionAreas = (
  catalog: Permission[],
  { query, filter, isAssigned }: BuildOptions,
): PermissionArea[] => {
  const needle = normalize(query);
  const areas = new Map<string, PermissionArea>();
  const sorted = [...catalog].sort((first, second) =>
    comparePermissionCodesByHierarchy(first.code, second.code),
  );

  for (const permission of sorted) {
    const path = parsePermissionCode(permission.code);
    const area =
      areas.get(path.group) ??
      areas
        .set(path.group, {
          key: path.group,
          label: getAreaLabel(path.group),
          items: [],
          all: [],
          assignedCount: 0,
        })
        .get(path.group)!;

    const assigned = isAssigned(permission.code);
    area.all.push(permission);
    if (assigned) area.assignedCount += 1;

    const matchesQuery =
      !needle ||
      normalize(permission.description).includes(needle) ||
      normalize(permission.code).includes(needle);
    const matchesFilter =
      filter === "todos" || (filter === "asignados" ? assigned : !assigned);
    if (matchesQuery && matchesFilter) {
      area.items.push({
        permission,
        section: capitalize(formatPermissionSegment(path.module)),
        sensitive: isSensitivePermission(permission.code),
      });
    }
  }

  return [...areas.values()].sort((first, second) =>
    first.label.localeCompare(second.label, "es", { sensitivity: "base" }),
  );
};
