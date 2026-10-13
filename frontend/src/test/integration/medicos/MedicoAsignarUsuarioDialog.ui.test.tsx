import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen, waitFor } from "@/test/utils";
import { toast } from "sonner";
import { MedicoAsignarUsuarioDialog } from "@features/admin/modules/medicos/components/MedicoAsignarUsuarioDialog";
import { useAsignarUsuario } from "@features/admin/modules/medicos/hooks/useMedicos";

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

vi.mock("@features/admin/modules/medicos/hooks/useMedicos", () => ({
  useAsignarUsuario: vi.fn(),
}));

// El picker real consulta usuarios por red; acá solo importa el contrato
// value/onChange, así que se reemplaza por un botón que "elige" el usuario 77.
vi.mock("@features/admin/modules/medicos/components/MedicoUsuarioPicker", () => ({
  MedicoUsuarioPicker: ({ onChange }: { onChange: (id: number) => void }) => (
    <button type="button" onClick={() => onChange(77)}>
      elegir usuario 77
    </button>
  ),
}));

const mutateAsync = vi.fn();

describe("MedicoAsignarUsuarioDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useAsignarUsuario).mockReturnValue({
      mutateAsync,
      isPending: false,
    } as unknown as ReturnType<typeof useAsignarUsuario>);
  });

  it("deshabilita Asignar hasta elegir un usuario", async () => {
    render(<MedicoAsignarUsuarioDialog medicoId={512} open onOpenChange={vi.fn()} />);

    const asignar = screen.getByRole("button", { name: "Asignar" });
    expect(asignar).toBeDisabled();

    await userEvent.click(screen.getByText("elegir usuario 77"));
    expect(asignar).toBeEnabled();
  });

  it("asigna el usuario elegido, avisa y cierra", async () => {
    mutateAsync.mockResolvedValue({ descartados: {} });
    const onOpenChange = vi.fn();
    render(<MedicoAsignarUsuarioDialog medicoId={512} open onOpenChange={onOpenChange} />);

    await userEvent.click(screen.getByText("elegir usuario 77"));
    await userEvent.click(screen.getByRole("button", { name: "Asignar" }));

    await waitFor(() => expect(mutateAsync).toHaveBeenCalledWith({ usuarioId: 77 }));
    expect(toast.success).toHaveBeenCalledWith("Usuario asignado al médico.", {
      description: undefined,
    });
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("informa los datos que el usuario ya tenía (descartados)", async () => {
    mutateAsync.mockResolvedValue({ descartados: { nombre: "JUAN", cedulaProfesional: "C1" } });
    render(<MedicoAsignarUsuarioDialog medicoId={512} open onOpenChange={vi.fn()} />);

    await userEvent.click(screen.getByText("elegir usuario 77"));
    await userEvent.click(screen.getByRole("button", { name: "Asignar" }));

    await waitFor(() =>
      expect(toast.success).toHaveBeenCalledWith("Usuario asignado al médico.", {
        description: expect.stringContaining("nombre, cédula profesional"),
      }),
    );
  });

  it("muestra error y no cierra si la asignación falla", async () => {
    mutateAsync.mockRejectedValue(new Error("boom"));
    const onOpenChange = vi.fn();
    render(<MedicoAsignarUsuarioDialog medicoId={512} open onOpenChange={onOpenChange} />);

    await userEvent.click(screen.getByText("elegir usuario 77"));
    await userEvent.click(screen.getByRole("button", { name: "Asignar" }));

    await waitFor(() => expect(toast.error).toHaveBeenCalled());
    expect(onOpenChange).not.toHaveBeenCalled();
  });
});
