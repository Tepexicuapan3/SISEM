import { describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen, within } from "@/test/utils";
import { DeskQueueList, NextAppointmentNotice } from "@features/consulta-medica/modules/atencion/components/DeskQueueList";
import type { VisitQueueItem } from "@api/types";

const NOW = new Date(2026, 10, 13, 10, 0);

const visit = (overrides: Partial<VisitQueueItem> = {}): VisitQueueItem => ({
  id: 1, folio: "VST-1", noExp: "100", pkNum: 0, arrivalType: "appointment", serviceType: "medicina_general",
  appointmentId: null, doctorId: 7, notes: "", status: "lista_para_doctor", vitals: null,
  nombrePaciente: "PACIENTE UNO", horaConsulta: "11:30", ...overrides,
} as VisitQueueItem);

const renderList = (visits: VisitQueueItem[], selectedVisitId: number | null = null, onSelectVisit = vi.fn()) =>
  render(
    <DeskQueueList
      visits={visits}
      now={NOW}
      consultationStartedAtByVisitId={{}}
      selectedVisitId={selectedVisitId}
      onSelectVisit={onSelectVisit}
    />,
  );

describe("Mi consultorio: por atender", () => {
  it("pone arriba al que esta en consulta y luego por hora de cita", () => {
    renderList([
      visit({ id: 1, nombrePaciente: "TARDE", horaConsulta: "12:00" }),
      visit({ id: 2, nombrePaciente: "TEMPRANO", horaConsulta: "10:30" }),
      visit({ id: 3, nombrePaciente: "EN CURSO", horaConsulta: "11:00", status: "en_consulta" }),
    ]);
    const names = screen.getAllByRole("button").map((b) => within(b).getByTestId("desk-queue-name").textContent);
    expect(names).toEqual(["EN CURSO", "TEMPRANO", "TARDE"]);
  });

  it("marca la urgencia de cada paciente", () => {
    renderList([
      visit({ id: 1, horaConsulta: "10:02" }),
      visit({ id: 2, horaConsulta: "10:10" }),
      visit({ id: 3, horaConsulta: "13:00" }),
      visit({ id: 4, status: "en_consulta" }),
    ]);
    expect(screen.getByTestId("doctor-visit-card-1")).toHaveAttribute("data-urgency", "now");
    expect(screen.getByTestId("doctor-visit-card-2")).toHaveAttribute("data-urgency", "soon");
    expect(screen.getByTestId("doctor-visit-card-3")).toHaveAttribute("data-urgency", "later");
    expect(screen.getByTestId("doctor-visit-card-4")).toHaveAttribute("data-urgency", "attending");
  });

  it("abre al paciente y marca el abierto", async () => {
    const onSelect = vi.fn();
    const user = userEvent.setup();
    renderList([visit({ id: 5 })], 5, onSelect);

    expect(screen.getByTestId("doctor-visit-card-5")).toHaveAttribute("aria-current", "true");
    await user.click(screen.getByTestId("doctor-visit-card-5"));
    expect(onSelect).toHaveBeenCalledWith(5);
  });

  it("el aviso de proxima cita abre al paciente", async () => {
    const onOpen = vi.fn();
    const user = userEvent.setup();
    render(<NextAppointmentNotice visit={visit({ id: 8, nombrePaciente: "LUNA PEDRO" })} minutesUntil={4} onOpen={onOpen} />);

    await user.click(screen.getByRole("button", { name: /LUNA PEDRO/ }));
    expect(screen.getByText(/en 4 min/)).toBeInTheDocument();
    expect(onOpen).toHaveBeenCalledWith(8);
  });
});
