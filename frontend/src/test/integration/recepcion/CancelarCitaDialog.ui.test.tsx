import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen, waitFor } from "@/test/utils";
import { CancelarCitaDialog } from "@features/recepcion/modules/citas/components/CancelarCitaDialog";
import { citasAPI } from "@api/resources/citas.api";
import type { CitaListItem } from "@api/types";

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

// Radix Select no es operable en happy-dom: se reemplaza por un <select> nativo.
vi.mock("@shared/ui/select", () => ({
  Select: ({
    value,
    onValueChange,
    children,
  }: {
    value: string;
    onValueChange: (value: string) => void;
    children: React.ReactNode;
  }) => (
    <select
      aria-label="Motivo"
      value={value}
      onChange={(event) => onValueChange(event.target.value)}
    >
      <option value="">Selecciona</option>
      {children}
    </select>
  ),
  SelectTrigger: () => null,
  SelectValue: () => null,
  SelectContent: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  SelectItem: ({ value, children }: { value: string; children: React.ReactNode }) => (
    <option value={value}>{children}</option>
  ),
}));

const cita = { id: 5, folio: "C-0005", noExp: "40041", fecha: "2026-10-30", hora: "09:00" };

const renderDialog = (onOpenChange = vi.fn()) => {
  render(<CancelarCitaDialog cita={cita} onOpenChange={onOpenChange} />);
  return onOpenChange;
};

describe("CancelarCitaDialog", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(citasAPI, "getMotivosCancelacion").mockResolvedValue({
      results: [
        { id: 2, name: "Cancelada por el paciente" },
        { id: 4, name: "Reagendada" },
      ],
    });
  });

  it("envia el motivo del catalogo y el detalle libre (no texto libre como motivo)", async () => {
    const updateSpy = vi
      .spyOn(citasAPI, "updateEstatus")
      .mockResolvedValue({ id: 5, folio: "C-0005" } as CitaListItem);
    const onOpenChange = renderDialog();

    const user = userEvent.setup();
    await screen.findByRole("option", { name: "Reagendada" });
    await user.selectOptions(screen.getByLabelText("Motivo"), "4");
    await user.type(screen.getByLabelText("Detalle (opcional)"), "  pidio otra fecha  ");
    await user.click(screen.getByRole("button", { name: "Confirmar cancelacion" }));

    await waitFor(() => expect(updateSpy).toHaveBeenCalledTimes(1));
    expect(updateSpy).toHaveBeenCalledWith(5, {
      estatus: "cancelada",
      motivoCancelacionId: 4,
      motivoDetalle: "pidio otra fecha",
    });
    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
  });

  it("no habilita la confirmacion sin motivo, aunque haya detalle", async () => {
    renderDialog();

    const user = userEvent.setup();
    await screen.findByRole("option", { name: "Reagendada" });
    const submit = screen.getByRole("button", { name: "Confirmar cancelacion" });
    await user.type(screen.getByLabelText("Detalle (opcional)"), "texto");
    expect(submit).toBeDisabled();
    await user.selectOptions(screen.getByLabelText("Motivo"), "2");
    expect(submit).toBeEnabled();
  });
});
