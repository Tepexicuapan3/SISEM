import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@/test/utils";
import { SinCentroAviso } from "@/domains/auth-access/components/shared/SinCentroAviso";
import { useAuthSession } from "@/domains/auth-access/hooks/useAuthSession";
import type { AuthUser } from "@api/types";

vi.mock("@/domains/auth-access/hooks/useAuthSession", () => ({
  useAuthSession: vi.fn(),
}));

const sesion = (alcanceCentros: AuthUser["alcanceCentros"]) => {
  vi.mocked(useAuthSession).mockReturnValue({
    data: { alcanceCentros } as AuthUser,
  } as ReturnType<typeof useAuthSession>);
};

describe("SinCentroAviso", () => {
  beforeEach(() => {
    vi.mocked(useAuthSession).mockReset();
  });

  it("avisa cuando el usuario no tiene centro de atención asignado", () => {
    sesion({ todos: false, centros: [] });

    render(<SinCentroAviso />);

    expect(screen.getByRole("alert")).toHaveTextContent(/no tienes un centro de atención asignado/i);
  });

  it("no avisa si el usuario tiene centro", () => {
    sesion({ todos: false, centros: [{ id: 3, nombre: "TICOMAN" }] });

    render(<SinCentroAviso />);

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("no avisa si ve todos los centros", () => {
    sesion({ todos: true, centros: [] });

    render(<SinCentroAviso />);

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("no avisa mientras la sesión no trae el alcance", () => {
    sesion(undefined);

    render(<SinCentroAviso />);

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
