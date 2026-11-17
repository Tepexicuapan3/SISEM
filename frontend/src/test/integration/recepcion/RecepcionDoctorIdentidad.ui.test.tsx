import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen } from "@/test/utils";
import { DisponibilidadView } from "@features/recepcion/modules/agenda/components/DisponibilidadView";
import { buildDoctorFilterOptions } from "@features/recepcion/modules/agenda/pages/RecepcionAgendaPage.helpers";
import type { MedicoListItem } from "@api/types/medicos.types";
import { hoyLocal } from "@features/recepcion/modules/citas/utils/dates";

// IDs DIVERGENTES a propósito: No. Médico (512) != id de usuario (7).
const MEDICO_ID = 512;
const USUARIO_ID = 7;
// El slot de hoy genera ficha; el de otro día, cita. El mock clickea el que diga la prueba.
let fechaSlot = hoyLocal();

vi.mock("@features/recepcion/modules/citas/components/SlotCalendar", () => ({
  SlotCalendar: ({
    medicoId,
    onSlotClick,
  }: {
    medicoId: number;
    onSlotClick: (fecha: string, slot: Record<string, unknown>) => void;
  }) => (
    <button
      type="button"
      onClick={() => onSlotClick(fechaSlot, { hora: "09:00", consultorioId: 3 })}
    >
      slot-medico-{medicoId}
    </button>
  ),
}));

vi.mock(
  "@features/recepcion/modules/agenda/components/DisponibilidadMedicoCard",
  () => ({ DisponibilidadMedicoCard: () => null }),
);

const medico = (over: Partial<MedicoListItem>): MedicoListItem =>
  ({
    id: MEDICO_ID,
    usuarioId: USUARIO_ID,
    nombreCompleto: "Dra. Divergente",
    centros: [],
    ...over,
  }) as unknown as MedicoListItem;

const renderView = (
  calMedicoId: number,
  allMedicos: MedicoListItem[],
  onOpen = vi.fn(),
  onAgendarCita = vi.fn(),
) => {
  render(
    <DisponibilidadView
      centroOptions={[]}
      calCentroId={null}
      setCalCentroId={vi.fn()}
      calMedicoId={calMedicoId}
      setCalMedicoId={vi.fn()}
      calWeekStart="2026-10-12"
      setCalWeekStart={vi.fn()}
      medicoSearch=""
      setMedicoSearch={vi.fn()}
      disponibilidadMedicos={allMedicos}
      allMedicos={allMedicos}
      onOpenQuickCheckin={onOpen}
      onAgendarCita={onAgendarCita}
    />,
  );
  return onOpen;
};

describe("Recepción: espacios de identidad médico vs usuario", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fechaSlot = hoyLocal();
  });

  it("DisponibilidadView manda doctorId = usuarioId y la agenda usa medicoId", async () => {
    const user = userEvent.setup();
    const onOpen = renderView(MEDICO_ID, [medico({})]);

    await user.click(screen.getByRole("button", { name: `slot-medico-${MEDICO_ID}` }));

    expect(onOpen).toHaveBeenCalledTimes(1);
    expect(onOpen.mock.calls[0][0].doctorId).toBe(USUARIO_ID);
    expect(onOpen.mock.calls[0][0].doctorId).not.toBe(MEDICO_ID);
  });

  it("DisponibilidadView agenda cita (no ficha) en un horario de otro día, con el No. Médico", async () => {
    fechaSlot = "2099-01-15";
    const user = userEvent.setup();
    const onOpen = vi.fn();
    const onAgendarCita = vi.fn();
    renderView(MEDICO_ID, [medico({})], onOpen, onAgendarCita);

    await user.click(screen.getByRole("button", { name: `slot-medico-${MEDICO_ID}` }));

    expect(onOpen).not.toHaveBeenCalled();
    expect(onAgendarCita).toHaveBeenCalledWith({
      medicoId: MEDICO_ID,
      medicoNombre: "Dra. Divergente",
      consultorioId: 3,
      fecha: "2099-01-15",
      hora: "09:00",
    });
  });

  it("el filtro de médico usa usuarioId", () => {
    const options = buildDoctorFilterOptions([
      medico({}),
    ]);

    expect(options).toEqual([{ id: USUARIO_ID, nombre: "Dra. Divergente" }]);

    // Una visita con doctorId (espacio usuario) coincide con la opción por usuarioId.
    const visit = { doctorId: USUARIO_ID };
    expect(options.some((o) => visit.doctorId === o.id)).toBe(true);
    expect(options.some((o) => o.id === MEDICO_ID)).toBe(false);
  });
});
