import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { useAlcanceCentros } from "@/domains/auth-access/hooks/useAlcanceCentros";
import { useAuthSession } from "@/domains/auth-access/hooks/useAuthSession";
import type { AuthUser } from "@api/types";

vi.mock("@/domains/auth-access/hooks/useAuthSession", () => ({
  useAuthSession: vi.fn(),
}));

const CUAUHTEMOC = 1;
const TICOMAN = 3;

const sesion = (user: Partial<AuthUser> | null) => {
  vi.mocked(useAuthSession).mockReturnValue({ data: user } as ReturnType<typeof useAuthSession>);
};

const agendarOtros = { "recepcion:citas:agendar_otros_centros": { granted: true, missingAllOf: [], missingAnyOf: [] } };

describe("useAlcanceCentros", () => {
  beforeEach(() => vi.mocked(useAuthSession).mockReset());

  it("solo trabaja y agenda en su centro", () => {
    sesion({ alcanceCentros: { todos: false, centros: [{ id: CUAUHTEMOC, nombre: "CUAUHTÉMOC" }] }, capabilities: {} });

    const { result } = renderHook(() => useAlcanceCentros());

    expect(result.current.permite(CUAUHTEMOC)).toBe(true);
    expect(result.current.permite(TICOMAN)).toBe(false);
    expect(result.current.puedeAgendarEn(TICOMAN)).toBe(false);
    expect(result.current.centroPrincipal).toBe(CUAUHTEMOC);
  });

  it("con permiso de agendar en otros centros agenda en cualquiera, pero trabaja solo en el suyo", () => {
    sesion({
      alcanceCentros: { todos: false, centros: [{ id: CUAUHTEMOC, nombre: "CUAUHTÉMOC" }] },
      capabilities: agendarOtros,
    });

    const { result } = renderHook(() => useAlcanceCentros());

    expect(result.current.puedeAgendarEn(TICOMAN)).toBe(true);
    expect(result.current.permite(TICOMAN)).toBe(false);
  });

  it("con alcance de todos los centros permite todo", () => {
    sesion({ alcanceCentros: { todos: true, centros: [] }, capabilities: {} });

    const { result } = renderHook(() => useAlcanceCentros());

    expect(result.current.permite(TICOMAN)).toBe(true);
    expect(result.current.puedeAgendarEn(TICOMAN)).toBe(true);
    expect(result.current.centroPrincipal).toBeNull();
  });

  it("sin centro asignado no permite ninguno", () => {
    sesion({ alcanceCentros: { todos: false, centros: [] }, capabilities: {} });

    const { result } = renderHook(() => useAlcanceCentros());

    expect(result.current.permite(CUAUHTEMOC)).toBe(false);
    expect(result.current.puedeAgendarEn(CUAUHTEMOC)).toBe(false);
  });

  it("si la sesión no trae el alcance no filtra (el backend decide)", () => {
    sesion({ capabilities: {} });

    const { result } = renderHook(() => useAlcanceCentros());

    expect(result.current.permite(TICOMAN)).toBe(true);
    expect(result.current.puedeAgendarEn(TICOMAN)).toBe(true);
  });
});
