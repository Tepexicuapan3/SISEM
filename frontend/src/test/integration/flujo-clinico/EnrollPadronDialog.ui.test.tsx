import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen, waitFor } from "@/test/utils";
import type { PadronFamilyMember, PadronOption } from "@api/types/padrones.types";
import { EnrollPadronDialog } from "@features/padrones/components/EnrollPadronDialog";
import {
  useEnrollPadron,
  usePadronFamily,
  usePadronOptions,
} from "@features/padrones/queries/usePadrones";

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("@features/padrones/queries/usePadrones", () => ({
  useEnrollPadron: vi.fn(),
  usePadronFamily: vi.fn(),
  usePadronOptions: vi.fn(),
}));

// Docs/plans/cronicos-alta-padron.md: se elige a la persona, el pkNum no se escribe.
const MEMBERS: PadronFamilyMember[] = [
  { idPaciente: 10, noExp: "777", pkNum: 0, nombre: "PEREZ LOPEZ JUAN", parentesco: "TRABAJADOR", edad: 52, fechaNac: "1974-03-01" },
  { idPaciente: null, noExp: "777", pkNum: 2, nombre: "RUIZ SOTO MARIA", parentesco: "ESPOSA", edad: 49, fechaNac: "1977-06-10" },
];

const OPTIONS: PadronOption[] = [
  { id: "E11", code: "E11", description: "DIABETES TIPO 2", program: { code: "DIABETES", name: "Diabetes mellitus" } },
  { id: "J00", code: "J00", description: "RINOFARINGITIS AGUDA", program: null },
];

const mutateAsync = vi.fn();

function mockHooks() {
  vi.mocked(usePadronFamily).mockImplementation((noExp: string) => ({
    data: noExp ? { members: MEMBERS } : undefined,
    isFetching: false,
    isError: false,
    error: null,
  }) as unknown as ReturnType<typeof usePadronFamily>);
  vi.mocked(usePadronOptions).mockImplementation((_registry, search: string) => ({
    data: search.trim().length >= 2 ? { items: OPTIONS } : undefined,
    isFetching: false,
  }) as unknown as ReturnType<typeof usePadronOptions>);
  vi.mocked(useEnrollPadron).mockReturnValue({
    mutateAsync,
    isPending: false,
  } as unknown as ReturnType<typeof useEnrollPadron>);
}

const renderDialog = () =>
  render(<EnrollPadronDialog open onOpenChange={vi.fn()} registry="cronicos" />);

// La busqueda es automatica al dejar de escribir: no hay boton.
async function searchFamily(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("Expediente"), "777");
  await screen.findByRole("radio", { name: /PEREZ LOPEZ JUAN/ });
}

describe("EnrollPadronDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mutateAsync.mockResolvedValue({});
    mockHooks();
  });

  it("no pide el numero de familiar a mano ni un boton de buscar", () => {
    renderDialog();
    expect(screen.queryByLabelText(/Familiar/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Buscar" })).not.toBeInTheDocument();
  });

  it("busca solo despues de dejar de escribir, una vez por expediente", async () => {
    const user = userEvent.setup();
    renderDialog();
    await searchFamily(user);

    const searched = vi.mocked(usePadronFamily).mock.calls.map(([noExp]) => noExp).filter(Boolean);
    expect(new Set(searched)).toEqual(new Set(["777"]));
  });

  it("muestra a los miembros del expediente para elegir a la persona", async () => {
    const user = userEvent.setup();
    renderDialog();
    await searchFamily(user);

    expect(screen.getByRole("radio", { name: /PEREZ LOPEZ JUAN/ })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /RUIZ SOTO MARIA/ })).toHaveAccessibleName(/Esposa.*49 años/);
  });

  it("no inscribe sin elegir a la persona", async () => {
    const user = userEvent.setup();
    renderDialog();
    await searchFamily(user);
    await user.click(screen.getByRole("button", { name: "Inscribir" }));

    expect(await screen.findByText("Selecciona a la persona")).toBeInTheDocument();
    expect(mutateAsync).not.toHaveBeenCalled();
  });

  it("inscribe a la persona elegida con su pkNum y el CIE con su programa", async () => {
    const user = userEvent.setup();
    renderDialog();
    await searchFamily(user);
    await user.click(screen.getByRole("radio", { name: /RUIZ SOTO MARIA/ }));
    await user.type(screen.getByPlaceholderText(/Buscar CIE-10/), "diab");
    const option = await screen.findByRole("option", { name: /E11/ });
    expect(option).toHaveTextContent("Diabetes mellitus");
    await user.click(option);
    await user.click(screen.getByRole("button", { name: "Inscribir" }));

    await waitFor(() => expect(mutateAsync).toHaveBeenCalledWith({
      noExp: "777", pkNum: 2, itemId: "E11", enrolledOn: null, notes: null,
    }));
  });

  it("avisa cuando el CIE no pertenece a un programa, sin bloquear", async () => {
    const user = userEvent.setup();
    renderDialog();
    await user.type(screen.getByPlaceholderText(/Buscar CIE-10/), "rino");
    await user.click(await screen.findByRole("option", { name: /J00/ }));

    expect(screen.getByText(/no pertenece a ningún programa de crónicos/)).toBeInTheDocument();
  });

  it("la fecha de inscripcion no puede ser anterior al nacimiento", async () => {
    const user = userEvent.setup();
    renderDialog();
    await searchFamily(user);
    await user.click(screen.getByRole("radio", { name: /RUIZ SOTO MARIA/ }));

    expect(screen.getByLabelText(/Fecha de inscripción/)).toHaveAttribute("min", "1977-06-10");
  });

  it("cambiar el expediente borra la persona elegida", async () => {
    const user = userEvent.setup();
    renderDialog();
    await searchFamily(user);
    await user.click(screen.getByRole("radio", { name: /RUIZ SOTO MARIA/ }));
    expect(screen.getByRole("radio", { name: /RUIZ SOTO MARIA/ })).toBeChecked();
    await user.type(screen.getByLabelText("Expediente"), "8");

    await waitFor(() => expect(screen.getByRole("radio", { name: /RUIZ SOTO MARIA/ })).not.toBeChecked());
  });
});
