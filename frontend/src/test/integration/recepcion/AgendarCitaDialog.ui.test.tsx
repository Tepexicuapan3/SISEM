import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import { render, screen } from "@/test/utils";
import { ApiError } from "@api/utils/errors";
import { AgendarCitaDialog } from "@features/recepcion/modules/agenda/components/AgendarCitaDialog";
import { useAgendarCita } from "@features/recepcion/modules/citas/mutations/useCitaMutations";
import { usePatientLookup } from "@features/recepcion/modules/checkin/queries/usePatientLookup";
import { useAdscripcionPermisos } from "@features/recepcion/modules/adscripcion/queries/useAdscripcionPermisos";

vi.mock("@features/recepcion/modules/citas/mutations/useCitaMutations", () => ({
  useAgendarCita: vi.fn(),
}));
vi.mock("@features/recepcion/modules/checkin/queries/usePatientLookup", () => ({
  usePatientLookup: vi.fn(),
}));
vi.mock("@features/recepcion/modules/adscripcion/queries/useAdscripcionPermisos", () => ({
  useAdscripcionPermisos: vi.fn(),
}));
vi.mock("@shared/hooks/useDebounce", () => ({ useDebounce: (v: string) => v }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const manana = new Date();
manana.setDate(manana.getDate() + 1);
const FECHA = `${manana.getFullYear()}-${String(manana.getMonth() + 1).padStart(2, "0")}-${String(manana.getDate()).padStart(2, "0")}`;

const slot = { medicoId: 3, medicoNombre: "Dra. Ana Ruiz", consultorioId: 12, fecha: FECHA, hora: "09:40" };

const miembro = (pkNum: number, nombre: string, idPaciente: number) => ({
  noExp: "40488", pkNum, idPaciente, nombre, edad: 40, fechaNac: null,
  parentesco: pkNum === 0 ? "TITULAR" : "HIJO", estatus: "A", cdClinica: null, foto: null,
});

describe("AgendarCitaDialog", () => {
  const mutateAsync = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useAgendarCita).mockReturnValue({
      mutateAsync, isPending: false,
    } as unknown as ReturnType<typeof useAgendarCita>);
    vi.mocked(usePatientLookup).mockReturnValue({
      data: { titular: miembro(0, "Luis Pérez", 501), dependientes: [miembro(1, "Sofía Pérez", 502)] },
      isFetching: false, isError: false,
    } as unknown as ReturnType<typeof usePatientLookup>);
    vi.mocked(useAdscripcionPermisos).mockReturnValue({
      puedeLeer: true, puedeAsignar: false, puedeExcepcion: true,
    } as unknown as ReturnType<typeof useAdscripcionPermisos>);
    mutateAsync.mockResolvedValue({ folio: "CIT-NUEVA" });
  });

  it("muestra el horario elegido y no deja agendar sin paciente", () => {
    render(<AgendarCitaDialog slot={slot} onOpenChange={vi.fn()} canWrite />);

    expect(screen.getByText(/Dra\. Ana Ruiz/)).toBeInTheDocument();
    expect(screen.getByText("09:40")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Agendar cita" })).toBeDisabled();
  });

  it("agenda la cita para el miembro elegido en el horario del slot", async () => {
    const onOpenChange = vi.fn();
    const user = userEvent.setup();
    render(<AgendarCitaDialog slot={slot} onOpenChange={onOpenChange} canWrite />);

    await user.type(screen.getByLabelText("Número de expediente"), "40488");
    await user.click(screen.getByText("Sofía Pérez"));
    await user.type(screen.getByLabelText("Motivo"), "Control");
    await user.click(screen.getByRole("button", { name: "Agendar cita" }));

    expect(mutateAsync).toHaveBeenCalledWith({
      idPaciente: 502,
      noExp: "40488",
      pkNum: 1,
      medicoId: 3,
      consultorioId: 12,
      fechaHora: `${FECHA}T09:40`,
      servicioTipo: "medicina_general",
      motivo: "Control",
    });
    expect(toast.success).toHaveBeenCalled();
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("con otro consultorio familiar deja agendar con excepción y motivo", async () => {
    mutateAsync
      .mockRejectedValueOnce(
        new ApiError("CONSULTORIO_FAMILIAR_DIFERENTE", "Su consultorio familiar es otro.", 409, {
          estado: "VIGENTE", idConsultorioFamiliar: 4, idConsultorioSolicitado: 12,
        }),
      )
      .mockResolvedValueOnce({ folio: "CIT-NUEVA" });
    const user = userEvent.setup();
    render(<AgendarCitaDialog slot={slot} onOpenChange={vi.fn()} canWrite />);

    await user.type(screen.getByLabelText("Número de expediente"), "40488");
    await user.click(screen.getByText("Luis Pérez"));
    await user.click(screen.getByRole("button", { name: "Agendar cita" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Su consultorio familiar es otro.");
    await user.type(screen.getByLabelText("Motivo de la excepción"), "Lo pidió el paciente");
    await user.click(screen.getByRole("button", { name: "Atender con excepción" }));

    expect(mutateAsync).toHaveBeenLastCalledWith(
      expect.objectContaining({ pkNum: 0, excepcionConsultorioFamiliar: "Lo pidió el paciente" }),
    );
  });
});
