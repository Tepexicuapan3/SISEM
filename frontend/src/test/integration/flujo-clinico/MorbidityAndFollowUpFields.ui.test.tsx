import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { render, screen, waitFor } from "@/test/utils";
import { visitsAPI } from "@api/resources/visits.api";
import { MorbidityAndFollowUpFields } from "@features/consulta-medica/modules/atencion/components/MorbidityAndFollowUpFields";
import {
  saveDiagnosisFormSchema,
  type SaveDiagnosisFormInput,
  type SaveDiagnosisFormValues,
} from "@features/consulta-medica/modules/atencion/domain/consultation.schemas";
import { DEFAULT_DIAGNOSIS_FORM_VALUES } from "@features/consulta-medica/modules/atencion/pages/DoctorConsultationPage.helpers";

vi.mock("@api/resources/visits.api", () => ({
  visitsAPI: {
    getFollowUpDays: vi.fn(),
    getFollowUpSlots: vi.fn(),
    getFollowUpNextDay: vi.fn(),
    getMorbiditySuggestion: vi.fn(),
  },
}));

function Wrapper() {
  const form = useForm<SaveDiagnosisFormInput, unknown, SaveDiagnosisFormValues>({
    resolver: zodResolver(saveDiagnosisFormSchema),
    mode: "onChange",
    defaultValues: { ...DEFAULT_DIAGNOSIS_FORM_VALUES, followUpEnabled: true },
  });
  const [followUpDate, followUpSlotId] = useWatch({
    control: form.control,
    name: ["followUpDate", "followUpSlotId"],
  });
  return (
    <>
      <MorbidityAndFollowUpFields visitId={1} cieCode="" diagnosisForm={form} disabled={false} />
      <output data-testid="follow-up-date">{followUpDate}</output>
      <output data-testid="follow-up-slot">{followUpSlotId}</output>
    </>
  );
}

describe("MorbidityAndFollowUpFields - cita de seguimiento", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(visitsAPI.getFollowUpDays).mockResolvedValue({ days: [], hasAgenda: true });
    vi.mocked(visitsAPI.getFollowUpSlots).mockResolvedValue({
      slots: [
        { slotId: 11, hora: "09:00", duracionMin: 20, consultorioNombre: "Consultorio 1", disponible: true },
        { slotId: 13, hora: "09:20", duracionMin: 20, consultorioNombre: "Consultorio 1", disponible: false },
        { slotId: 12, hora: "16:20", duracionMin: 20, consultorioNombre: "Consultorio 1", disponible: true },
      ],
    });
    vi.mocked(visitsAPI.getFollowUpNextDay).mockResolvedValue({ fecha: "2099-03-13" });
  });

  it("sin agenda de médico lo avisa y no ofrece horarios", async () => {
    vi.mocked(visitsAPI.getFollowUpDays).mockResolvedValue({ days: [], hasAgenda: false });
    render(<Wrapper />);

    expect(await screen.findByText(/no tiene agenda de médico/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Próximo disponible" })).not.toBeInTheDocument();
  });

  it("el atajo elige el día y los horarios se eligen con un clic, por turno", async () => {
    const user = userEvent.setup();
    render(<Wrapper />);

    await user.click(await screen.findByRole("button", { name: "Próximo disponible" }));

    await waitFor(() => expect(screen.getByTestId("follow-up-date")).toHaveTextContent("2099-03-13"));
    expect(await screen.findByText("Mañana")).toBeInTheDocument();
    expect(screen.getByText("Tarde")).toBeInTheDocument();

    const slot = screen.getByRole("button", { name: /16:20/ });
    await user.click(slot);

    expect(slot).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByTestId("follow-up-slot")).toHaveTextContent("12");
    expect(screen.getByText(/se agenda al finalizar la consulta/i)).toBeInTheDocument();
  });

  it("muestra los horarios ocupados con otro color, sin poder elegirlos, y la leyenda", async () => {
    const user = userEvent.setup();
    render(<Wrapper />);

    await user.click(await screen.findByRole("button", { name: "Próximo disponible" }));

    const ocupado = await screen.findByRole("button", { name: "09:20 ocupado" });
    expect(ocupado).toBeDisabled();
    expect(screen.getByRole("button", { name: "09:00 disponible" })).toBeEnabled();
    const leyenda = screen.getByRole("list", { name: "Leyenda de horarios" });
    expect(leyenda).toHaveTextContent("Disponible");
    expect(leyenda).toHaveTextContent("Ocupado");
  });

  it("si el atajo no encuentra lugar lo dice", async () => {
    vi.mocked(visitsAPI.getFollowUpNextDay).mockResolvedValue({ fecha: null });
    const user = userEvent.setup();
    render(<Wrapper />);

    await user.click(await screen.findByRole("button", { name: "1 mes" }));

    expect(await screen.findByText(/no hay horarios libres a partir de esa fecha/i)).toBeInTheDocument();
    expect(screen.getByTestId("follow-up-date")).toBeEmptyDOMElement();
  });
});
