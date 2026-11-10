import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import { render, screen } from "@/test/utils";
import { ApiError } from "@api/utils/errors";
import { ReprogramarCitaDialog } from "@features/recepcion/modules/citas/components/ReprogramarCitaDialog";
import { useReprogramarCita } from "@features/recepcion/modules/citas/mutations/useCitaMutations";
import { useSlotsMedico } from "@features/recepcion/modules/adscripcion/queries/useAdscripcionQueries";

vi.mock("@features/recepcion/modules/citas/mutations/useCitaMutations", () => ({
  useReprogramarCita: vi.fn(),
}));
vi.mock("@features/recepcion/modules/adscripcion/queries/useAdscripcionQueries", () => ({
  useSlotsMedico: vi.fn(),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const manana = new Date();
manana.setDate(manana.getDate() + 1);
const FECHA = `${manana.getFullYear()}-${String(manana.getMonth() + 1).padStart(2, "0")}-${String(manana.getDate()).padStart(2, "0")}`;

const cita = { id: 7, folio: "CIT-ABC", noExp: "40488", fecha: FECHA, hora: "09:00", medicoId: 3 };

describe("ReprogramarCitaDialog", () => {
  const mutateAsync = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useReprogramarCita).mockReturnValue({
      mutateAsync, isPending: false,
    } as unknown as ReturnType<typeof useReprogramarCita>);
    vi.mocked(useSlotsMedico).mockReturnValue({
      data: { slots: [{ hora: "09:40" }, { hora: "10:00" }] }, isFetching: false,
    } as unknown as ReturnType<typeof useSlotsMedico>);
    mutateAsync.mockResolvedValue({ folio: "CIT-NUEVA" });
  });

  it("busca los horarios libres del mismo médico en la fecha de la cita", () => {
    render(<ReprogramarCitaDialog cita={cita} onOpenChange={vi.fn()} />);

    expect(vi.mocked(useSlotsMedico)).toHaveBeenLastCalledWith(3, FECHA);
    expect(screen.getByRole("button", { name: "Reprogramar" })).toBeDisabled();
  });

  it("reprograma al horario elegido con el motivo", async () => {
    const onOpenChange = vi.fn();
    const user = userEvent.setup();
    render(<ReprogramarCitaDialog cita={cita} onOpenChange={onOpenChange} />);

    await user.click(screen.getByRole("radio", { name: "09:40" }));
    await user.type(screen.getByLabelText(/Motivo/), "Lo pidió el paciente");
    await user.click(screen.getByRole("button", { name: "Reprogramar" }));

    expect(mutateAsync).toHaveBeenCalledWith({
      id: 7, fechaHora: `${FECHA}T09:40`, motivoDetalle: "Lo pidió el paciente",
    });
    expect(toast.success).toHaveBeenCalled();
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("si el backend la rechaza muestra el motivo", async () => {
    mutateAsync.mockRejectedValue(new ApiError("CITA_CON_FICHA", "La cita ya tiene ficha.", 409));
    const user = userEvent.setup();
    render(<ReprogramarCitaDialog cita={cita} onOpenChange={vi.fn()} />);

    await user.click(screen.getByRole("radio", { name: "10:00" }));
    await user.click(screen.getByRole("button", { name: "Reprogramar" }));

    expect(toast.error).toHaveBeenCalledWith("No se pudo reprogramar", { description: "La cita ya tiene ficha." });
  });
});
