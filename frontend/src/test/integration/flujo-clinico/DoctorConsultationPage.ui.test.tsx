import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { ApiError } from "@api/utils/errors";
import { toast } from "sonner";
import { TooltipProvider } from "@shared/ui/tooltip";
import DoctorConsultationPage from "@features/consulta-medica/modules/atencion/pages/DoctorConsultationPage";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import { useCloseVisit } from "@features/consulta-medica/modules/atencion/mutations/useCloseVisit";
import { useSaveDiagnosis } from "@features/consulta-medica/modules/atencion/mutations/useSaveDiagnosis";
import { useSavePrescriptions } from "@features/consulta-medica/modules/atencion/mutations/useSavePrescriptions";
import { useStartConsultation } from "@features/consulta-medica/modules/atencion/mutations/useStartConsultation";
import { useCieSearch } from "@features/consulta-medica/modules/atencion/queries/useCieSearch";
import { useDoctorQueue } from "@features/consulta-medica/modules/atencion/queries/useDoctorQueue";
import { useDoctorPipelineQueue } from "@features/consulta-medica/modules/atencion/queries/useDoctorPipelineQueue";
import {
  formatCapturedAtTime,
  formatServiceTypeLabel,
} from "@features/consulta-medica/modules/atencion/pages/DoctorConsultationPage.helpers";
import type { VisitQueueItem } from "@api/types";

vi.mock(
  "@features/consulta-medica/modules/atencion/queries/useDoctorQueue",
  () => ({
    useDoctorQueue: vi.fn(),
  }),
);

vi.mock(
  "@features/consulta-medica/modules/atencion/queries/useDoctorPipelineQueue",
  () => ({
    useDoctorPipelineQueue: vi.fn(),
  }),
);

vi.mock(
  "@features/consulta-medica/modules/atencion/queries/useCieSearch",
  () => ({
    useCieSearch: vi.fn(),
  }),
);

vi.mock(
  "@features/consulta-medica/modules/atencion/mutations/useStartConsultation",
  () => ({
    useStartConsultation: vi.fn(),
  }),
);

vi.mock(
  "@features/consulta-medica/modules/atencion/mutations/useSaveDiagnosis",
  () => ({
    useSaveDiagnosis: vi.fn(),
  }),
);

vi.mock(
  "@features/consulta-medica/modules/atencion/mutations/useSavePrescriptions",
  () => ({
    useSavePrescriptions: vi.fn(),
  }),
);

vi.mock(
  "@features/consulta-medica/modules/atencion/mutations/useCloseVisit",
  () => ({
    useCloseVisit: vi.fn(),
  }),
);

vi.mock("@/domains/auth-access/hooks/usePermissionDependencies", () => ({
  usePermissionDependencies: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}));

const createVisit = (
  overrides: Partial<VisitQueueItem> = {},
): VisitQueueItem => ({
  id:            1,
  folio:         "VST-2001",
  noExp:         "20001",
  pkNum:         0,
  arrivalType:   "appointment",
  serviceType:   "medicina_general",
  appointmentId: "APP-2001",
  doctorId:      77,
  notes:         "Paciente listo para valoracion",
  status:        "lista_para_doctor",
  vitals:        null,
  ...overrides,
});

const renderDoctorPage = (initialEntry = "/clinico/consultas/doctor") => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <TooltipProvider>
          <Routes>
            <Route
              path="/clinico/consultas/doctor"
              element={<DoctorConsultationPage />}
            />
            <Route
              path="/clinico/consultas/doctor/:visitId"
              element={<DoctorConsultationPage />}
            />
          </Routes>
        </TooltipProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
};

// his_notas ampliada: el formulario siempre envia los 4 campos (vacios si no se capturan).
const EMPTY_NOTE_FIELDS = {
  currentIllness: "",
  systemsReview: "",
  diagnosticPlan: "",
  therapeuticPlan: "",
};

describe("DoctorConsultationPage UI", () => {
  const startMutateAsync = vi.fn();
  const saveDiagnosisMutateAsync = vi.fn();
  const savePrescriptionsMutateAsync = vi.fn();
  const closeMutateAsync = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();

    vi.mocked(usePermissionDependencies).mockReturnValue({
      hasCapability: () => true,
    } as unknown as ReturnType<typeof usePermissionDependencies>);

    vi.mocked(useDoctorQueue).mockReturnValue({
      data: {
        items: [createVisit()],
        page: 1,
        pageSize: 20,
        total: 1,
        totalPages: 1,
      },
      isLoading: false,
      isError: false,
      error: null,
    } as unknown as ReturnType<typeof useDoctorQueue>);

    vi.mocked(useDoctorPipelineQueue).mockReturnValue({
      data: { items: [], page: 1, pageSize: 50, total: 0, totalPages: 0 },
      isLoading: false,
      isError: false,
      error: null,
    } as unknown as ReturnType<typeof useDoctorPipelineQueue>);

    vi.mocked(useCieSearch).mockReturnValue({
      data: {
        items: [],
        total: 0,
      },
      isLoading: false,
      isFetching: false,
      isError: false,
      error: null,
    } as unknown as ReturnType<typeof useCieSearch>);

    vi.mocked(useStartConsultation).mockReturnValue({
      mutateAsync: startMutateAsync,
      isPending: false,
    } as unknown as ReturnType<typeof useStartConsultation>);

    vi.mocked(useSaveDiagnosis).mockReturnValue({
      mutateAsync: saveDiagnosisMutateAsync,
      isPending: false,
    } as unknown as ReturnType<typeof useSaveDiagnosis>);

    vi.mocked(useSavePrescriptions).mockReturnValue({
      mutateAsync: savePrescriptionsMutateAsync,
      isPending: false,
    } as unknown as ReturnType<typeof useSavePrescriptions>);

    vi.mocked(useCloseVisit).mockReturnValue({
      mutateAsync: closeMutateAsync,
      isPending: false,
    } as unknown as ReturnType<typeof useCloseVisit>);

    startMutateAsync.mockResolvedValue({
      id:            1,
      folio:         "VST-2001",
      noExp:         "20001",
      pkNum:         0,
      arrivalType:   "appointment",
      serviceType:   "medicina_general",
      appointmentId: "APP-2001",
      doctorId:      77,
      notes:         "Paciente listo para valoracion",
      status:        "en_consulta",
      vitals:        null,
    });

    saveDiagnosisMutateAsync.mockResolvedValue({
      visitId: 1,
      status: "en_consulta",
      primaryDiagnosis: "Infeccion respiratoria",
      finalNote: "Paciente estable al egreso.",
    });

    savePrescriptionsMutateAsync.mockResolvedValue({
      visitId: 1,
      status: "en_consulta",
      items: ["Paracetamol 500mg cada 8h"],
    });

    closeMutateAsync.mockResolvedValue({
      visit: {
        id:            1,
        folio:         "VST-2001",
        noExp:         "20001",
        pkNum:         0,
        arrivalType:   "appointment",
        serviceType:   "medicina_general",
        appointmentId: "APP-2001",
        doctorId:      77,
        notes:         "Paciente listo para valoracion",
        status:        "cerrada",
      },
      consultation: {
        id: 900,
        visitId: 1,
        doctorId: 77,
        primaryDiagnosis: "Infeccion respiratoria",
        cieCode: null,
        finalNote: "Paciente estable al egreso.",
        isActive: true,
        createdAt: "2026-02-20T12:00:00Z",
        updatedAt: "2026-02-20T12:10:00Z",
      },
    });
  });

  it("deshabilita carga de cola cuando no tiene permiso de lectura", () => {
    vi.mocked(usePermissionDependencies).mockReturnValue({
      hasCapability: () => false,
    } as unknown as ReturnType<typeof usePermissionDependencies>);

    vi.mocked(useDoctorQueue).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
      error: null,
    } as unknown as ReturnType<typeof useDoctorQueue>);

    renderDoctorPage();

    expect(useDoctorQueue).toHaveBeenCalledWith({ enabled: false });
    expect(
      screen.getByText(
        "No tenes permisos completos para cargar la bandeja del doctor.",
      ),
    ).toBeVisible();
  });

  it("muestra aviso neutral y bloquea acciones clinicas cuando falta permiso de escritura", () => {
    vi.mocked(usePermissionDependencies).mockReturnValue({
      hasCapability: (capability: string) =>
        capability === "flow.doctor.queue.read",
    } as unknown as ReturnType<typeof usePermissionDependencies>);

    renderDoctorPage("/clinico/consultas/doctor/1");

    expect(
      screen.getByText(
        "No tenes permisos completos para registrar diagnostico, receta o cierre de consulta.",
      ),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Iniciar consulta" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Finalizar consulta" }),
    ).toBeDisabled();
  });

  it("muestra controles clinicos deshabilitados cuando falta permiso de escritura", async () => {
    vi.mocked(usePermissionDependencies).mockReturnValue({
      hasCapability: (capability: string) =>
        capability === "flow.doctor.queue.read",
    } as unknown as ReturnType<typeof usePermissionDependencies>);

    renderDoctorPage("/clinico/consultas/doctor/1");

    expect(
      screen.getByRole("button", { name: "Guardar diagnostico" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Guardar receta" }),
    ).toBeDisabled();
  });

  it("abre modal al seleccionar una card", async () => {
    vi.mocked(useDoctorQueue).mockReturnValue({
      data: {
        items: [
          createVisit(),
          createVisit({
            id:            2,
            folio:         "VST-2002",
            noExp:         "20002",
            appointmentId: "APP-2002",
            notes:         "Paciente con control de seguimiento",
          }),
        ],
        page: 1,
        pageSize: 20,
        total: 2,
        totalPages: 1,
      },
      isLoading: false,
      isError: false,
      error: null,
    } as unknown as ReturnType<typeof useDoctorQueue>);

    startMutateAsync.mockResolvedValueOnce({
      ...createVisit({
        id:            2,
        folio:         "VST-2002",
        noExp:         "20002",
        appointmentId: "APP-2002",
      }),
      status: "en_consulta",
    });

    const user = userEvent.setup();
    renderDoctorPage();

    await user.click(screen.getByTestId("doctor-visit-card-2"));

    await waitFor(() => {
      expect(screen.getByTestId("doctor-consultation-modal")).toHaveTextContent(
        "Folio VST-2002",
      );
    });
  });

  it("permite cerrar modal y volver a bandeja", async () => {
    const user = userEvent.setup();
    renderDoctorPage("/clinico/consultas/doctor/1");

    expect(screen.getByTestId("doctor-consultation-modal")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Volver a bandeja" }));

    await waitFor(() => {
      expect(
        screen.queryByTestId("doctor-consultation-modal"),
      ).not.toBeInTheDocument();
    });
  });

  it("muestra solo consultas abiertas en la bandeja", () => {
    vi.mocked(useDoctorQueue).mockReturnValue({
      data: {
        items: [
          createVisit({ id: 1, status: "lista_para_doctor" }),
          createVisit({ id: 2, folio: "VST-2002", status: "en_consulta" }),
          createVisit({ id: 3, folio: "VST-2003", status: "cerrada" }),
        ],
        page: 1,
        pageSize: 20,
        total: 3,
        totalPages: 1,
      },
      isLoading: false,
      isError: false,
      error: null,
    } as unknown as ReturnType<typeof useDoctorQueue>);

    renderDoctorPage();

    expect(screen.getByTestId("doctor-visit-card-1")).toBeVisible();
    expect(screen.getByTestId("doctor-visit-card-2")).toBeVisible();
    expect(screen.queryByTestId("doctor-visit-card-3")).not.toBeInTheDocument();
  });

  it("renderiza estado loading", () => {
    vi.mocked(useDoctorQueue).mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
    } as unknown as ReturnType<typeof useDoctorQueue>);

    renderDoctorPage();

    expect(screen.getByText("Cargando bandeja del doctor...")).toBeVisible();
  });

  it("renderiza estado empty", () => {
    vi.mocked(useDoctorQueue).mockReturnValue({
      data: { items: [], page: 1, pageSize: 20, total: 0, totalPages: 0 },
      isLoading: false,
      isError: false,
      error: null,
    } as unknown as ReturnType<typeof useDoctorQueue>);

    renderDoctorPage();

    expect(
      screen.getByText("No hay pacientes listos para doctor."),
    ).toBeVisible();
  });

  it("renderiza estado error", () => {
    vi.mocked(useDoctorQueue).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error("request failed"),
    } as unknown as ReturnType<typeof useDoctorQueue>);

    renderDoctorPage();

    expect(
      screen.getByText("No se pudo cargar la bandeja del doctor."),
    ).toBeVisible();
  });

  it("guarda diagnostico cuando la visita esta en consulta", async () => {
    vi.mocked(useDoctorQueue).mockReturnValue({
      data: {
        items: [createVisit({ status: "en_consulta" })],
        page: 1,
        pageSize: 20,
        total: 1,
        totalPages: 1,
      },
      isLoading: false,
      isError: false,
      error: null,
    } as unknown as ReturnType<typeof useDoctorQueue>);

    const user = userEvent.setup();
    renderDoctorPage("/clinico/consultas/doctor/1");

    await user.type(
      screen.getByLabelText("Diagnostico principal"),
      "Gastroenteritis aguda",
    );
    await user.type(
      screen.getByLabelText("Nota final"),
      "Paciente estable y con manejo ambulatorio.",
    );
    await user.type(
      screen.getByLabelText("Padecimiento actual"),
      "Evacuaciones liquidas de 2 dias.",
    );
    await user.type(
      screen.getByLabelText("Plan terapeutico"),
      "Hidratacion oral.",
    );

    await user.click(
      screen.getByRole("button", { name: "Guardar diagnostico" }),
    );

    await waitFor(() => {
      expect(saveDiagnosisMutateAsync).toHaveBeenCalledWith({
        visitId: 1,
        data: {
          primaryDiagnosis: "Gastroenteritis aguda",
          finalNote: "Paciente estable y con manejo ambulatorio.",
          ...EMPTY_NOTE_FIELDS,
          currentIllness: "Evacuaciones liquidas de 2 dias.",
          therapeuticPlan: "Hidratacion oral.",
        },
      });
    });

    expect(toast.success).toHaveBeenCalledWith("Diagnostico guardado");
  });

  it("permite buscar CIE y lo envia al guardar diagnostico", async () => {
    vi.mocked(useDoctorQueue).mockReturnValue({
      data: {
        items: [createVisit({ status: "en_consulta" })],
        page: 1,
        pageSize: 20,
        total: 1,
        totalPages: 1,
      },
      isLoading: false,
      isError: false,
      error: null,
    } as unknown as ReturnType<typeof useDoctorQueue>);

    vi.mocked(useDoctorPipelineQueue).mockReturnValue({
      data: { items: [], page: 1, pageSize: 50, total: 0, totalPages: 0 },
      isLoading: false,
      isError: false,
      error: null,
    } as unknown as ReturnType<typeof useDoctorPipelineQueue>);

    vi.mocked(useCieSearch).mockReturnValue({
      data: {
        items: [
          {
            code: "A090",
            description: "GASTROENTERITIS",
            version: "CIE-10",
          },
        ],
        total: 1,
      },
      isLoading: false,
      isFetching: false,
      isError: false,
      error: null,
    } as unknown as ReturnType<typeof useCieSearch>);

    const user = userEvent.setup();
    renderDoctorPage("/clinico/consultas/doctor/1");

    await user.type(screen.getByLabelText(/Buscar CIE/i), "A0");
    await user.click(await screen.findByRole("button", { name: /A090/i }));

    await user.clear(screen.getByLabelText("Diagnostico principal"));

    await user.type(
      screen.getByLabelText("Diagnostico principal"),
      "Gastroenteritis aguda",
    );
    await user.type(
      screen.getByLabelText("Nota final"),
      "Paciente estable y con manejo ambulatorio.",
    );

    await user.click(
      screen.getByRole("button", { name: "Guardar diagnostico" }),
    );

    await waitFor(() => {
      expect(saveDiagnosisMutateAsync).toHaveBeenCalledWith({
        visitId: 1,
        data: {
          primaryDiagnosis: "Gastroenteritis aguda",
          finalNote: "Paciente estable y con manejo ambulatorio.",
          cieCode: "A090",
          ...EMPTY_NOTE_FIELDS,
        },
      });
    });
  });

  it("guarda receta con una indicacion por linea", async () => {
    vi.mocked(useDoctorQueue).mockReturnValue({
      data: {
        items: [createVisit({ status: "en_consulta" })],
        page: 1,
        pageSize: 20,
        total: 1,
        totalPages: 1,
      },
      isLoading: false,
      isError: false,
      error: null,
    } as unknown as ReturnType<typeof useDoctorQueue>);

    const user = userEvent.setup();
    renderDoctorPage("/clinico/consultas/doctor/1");

    await user.type(
      screen.getByLabelText("Receta (una indicacion por linea)"),
      "Paracetamol 500mg cada 8h por 3 dias\nHidratacion oral libre",
    );

    await user.click(screen.getByRole("button", { name: "Guardar receta" }));

    await waitFor(() => {
      expect(savePrescriptionsMutateAsync).toHaveBeenCalledWith({
        visitId: 1,
        data: {
          items: [
            "Paracetamol 500mg cada 8h por 3 dias",
            "Hidratacion oral libre",
          ],
        },
      });
    });

    expect(toast.success).toHaveBeenCalledWith("Receta guardada");
  });

  it("bloquea cierre hasta iniciar consulta, completar diagnostico + nota final y elegir CIE", async () => {
    vi.mocked(useCieSearch).mockReturnValue({
      data: {
        items: [
          { code: "A090", description: "GASTROENTERITIS", version: "CIE-10" },
        ],
        total: 1,
      },
      isLoading: false,
      isFetching: false,
      isError: false,
      error: null,
    } as unknown as ReturnType<typeof useCieSearch>);

    const user = userEvent.setup();
    renderDoctorPage("/clinico/consultas/doctor/1");

    const closeButton = screen.getByRole("button", {
      name: "Finalizar consulta",
    });
    expect(closeButton).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Iniciar consulta" }));
    await waitFor(() => {
      expect(startMutateAsync).toHaveBeenCalledWith({ visitId: 1 });
    });

    await user.type(screen.getByLabelText("Diagnostico principal"), "Dx");
    await user.type(screen.getByLabelText("Nota final"), "Nota clinica");

    // cieCode obligatorio para cerrar (NOM-024) -- el boton sigue
    // deshabilitado hasta elegir un CIE, aunque diagnostico/nota ya esten.
    expect(closeButton).toBeDisabled();

    await user.type(screen.getByLabelText(/Buscar CIE/i), "A0");
    await user.click(await screen.findByRole("button", { name: /A090/i }));

    await waitFor(() => {
      expect(closeButton).toBeEnabled();
    });
  });

  it("sincroniza diagnostico antes de cierre y luego cierra consulta", async () => {
    vi.mocked(useCieSearch).mockReturnValue({
      data: {
        items: [
          { code: "A090", description: "GASTROENTERITIS", version: "CIE-10" },
        ],
        total: 1,
      },
      isLoading: false,
      isFetching: false,
      isError: false,
      error: null,
    } as unknown as ReturnType<typeof useCieSearch>);

    const user = userEvent.setup();
    renderDoctorPage("/clinico/consultas/doctor/1");

    await user.click(screen.getByRole("button", { name: "Iniciar consulta" }));
    await waitFor(() => {
      expect(startMutateAsync).toHaveBeenCalledWith({ visitId: 1 });
    });

    await user.type(screen.getByLabelText("Diagnostico principal"), "Dx final");
    await user.type(
      screen.getByLabelText("Nota final"),
      "Nota final de egreso",
    );
    await user.type(screen.getByLabelText(/Buscar CIE/i), "A0");
    await user.click(await screen.findByRole("button", { name: /A090/i }));

    await user.click(
      screen.getByRole("button", { name: "Finalizar consulta" }),
    );

    await waitFor(() => {
      expect(saveDiagnosisMutateAsync).toHaveBeenCalledWith({
        visitId: 1,
        data: {
          primaryDiagnosis: "Dx final",
          finalNote: "Nota final de egreso",
          cieCode: "A090",
          ...EMPTY_NOTE_FIELDS,
        },
      });
    });

    await waitFor(() => {
      expect(closeMutateAsync).toHaveBeenCalledWith({
        visitId: 1,
        data: {
          primaryDiagnosis: "Dx final",
          finalNote: "Nota final de egreso",
          cieCode: "A090",
          ...EMPTY_NOTE_FIELDS,
        },
      });
    });

    expect(toast.success).toHaveBeenCalledWith("Consulta cerrada");
  });

  it("mapea errores de dominio en cierre de consulta", async () => {
    closeMutateAsync.mockRejectedValueOnce(
      new ApiError(
        "VISIT_STATE_INVALID",
        "VISIT_STATE_INVALID",
        409,
        undefined,
        "req-test",
      ),
    );

    vi.mocked(useCieSearch).mockReturnValue({
      data: {
        items: [
          { code: "A090", description: "GASTROENTERITIS", version: "CIE-10" },
        ],
        total: 1,
      },
      isLoading: false,
      isFetching: false,
      isError: false,
      error: null,
    } as unknown as ReturnType<typeof useCieSearch>);

    const user = userEvent.setup();
    renderDoctorPage("/clinico/consultas/doctor/1");

    await user.click(screen.getByRole("button", { name: "Iniciar consulta" }));
    await waitFor(() => {
      expect(startMutateAsync).toHaveBeenCalledWith({ visitId: 1 });
    });

    await user.type(screen.getByLabelText("Diagnostico principal"), "Dx");
    await user.type(screen.getByLabelText("Nota final"), "Nota");
    await user.type(screen.getByLabelText(/Buscar CIE/i), "A0");
    await user.click(await screen.findByRole("button", { name: /A090/i }));
    await user.click(
      screen.getByRole("button", { name: "Finalizar consulta" }),
    );

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        "No se pudo cerrar la consulta",
        {
          description:
            "La visita ya no esta en un estado valido para cerrar consulta.",
        },
      );
    });
  });

  it("muestra signos vitales de somatometria capturados", () => {
    vi.mocked(useDoctorQueue).mockReturnValue({
      data: {
        items: [
          createVisit({
            status: "en_consulta",
            vitals: {
              weightKg: 70,
              heightCm: 172,
              temperatureC: 36.6,
              oxygenSaturationPct: 98,
              notes: "Paciente con ayuno de 8 horas.",
              bmi: 23.7,
              capturedAt: "2026-08-26T09:14:00Z",
              reusedFromVisitId: null,
              reusedFrom: null,
            },
          }),
        ],
        page: 1,
        pageSize: 20,
        total: 1,
        totalPages: 1,
      },
      isLoading: false,
      isError: false,
      error: null,
    } as unknown as ReturnType<typeof useDoctorQueue>);

    renderDoctorPage("/clinico/consultas/doctor/1");

    expect(screen.getByText("70 kg")).toBeVisible();
    expect(screen.getByText("172 cm")).toBeVisible();
    expect(screen.getByText("36.6 C")).toBeVisible();
    expect(screen.getByText("98 %")).toBeVisible();
    expect(screen.getByText("23.7")).toBeVisible();
    expect(screen.getByText("Paciente con ayuno de 8 horas.")).toBeVisible();

    // Regresion del WARNING de sdd-verify: el momento de captura debe
    // mostrarse correctamente (antes solo estaba implementado, sin test).
    const capturedAtIndicator = screen.getByTestId("vitals-captured-at");
    expect(capturedAtIndicator).toHaveTextContent(
      `Tomados ${formatCapturedAtTime("2026-08-26T09:14:00Z")}`,
    );
    // Sin reuso (`reusedFromVisitId`/`reusedFrom` en null) no debe
    // aparecer ningun aviso de reuso.
    expect(capturedAtIndicator).not.toHaveTextContent(/reusados/i);
  });

  it("muestra folio, especialidad y hora de origen cuando los vitales fueron reusados", () => {
    const capturedAt = "2026-08-26T09:14:00Z";
    const sourceCapturedAt = "2026-08-26T07:05:00Z";

    vi.mocked(useDoctorQueue).mockReturnValue({
      data: {
        items: [
          createVisit({
            status: "en_consulta",
            vitals: {
              weightKg: 70,
              heightCm: 172,
              temperatureC: 36.6,
              oxygenSaturationPct: 98,
              notes: "Paciente con ayuno de 8 horas.",
              bmi: 23.7,
              capturedAt,
              reusedFromVisitId: 555,
              reusedFrom: {
                sourceVisitId: 555,
                sourceFolio: "VST-000555",
                sourceServiceType: "urgencias",
                capturedAt: sourceCapturedAt,
              },
            },
          }),
        ],
        page: 1,
        pageSize: 20,
        total: 1,
        totalPages: 1,
      },
      isLoading: false,
      isError: false,
      error: null,
    } as unknown as ReturnType<typeof useDoctorQueue>);

    renderDoctorPage("/clinico/consultas/doctor/1");

    // Gap cerrado por Fase 3.9: la UI ya no solo avisa que hubo reuso --
    // muestra folio, especialidad y hora de la visita ORIGEN, no solo un
    // id crudo (`reused_from_visit`).
    const capturedAtIndicator = screen.getByTestId("vitals-captured-at");
    expect(capturedAtIndicator).toHaveTextContent(
      `Tomados ${formatCapturedAtTime(capturedAt)}`,
    );
    expect(capturedAtIndicator).toHaveTextContent("VST-000555");
    expect(capturedAtIndicator).toHaveTextContent(
      formatServiceTypeLabel("urgencias"),
    );
    expect(capturedAtIndicator).toHaveTextContent(
      formatCapturedAtTime(sourceCapturedAt),
    );
  });

  it("muestra aviso de correccion cuando los vitales fueron editados (Fase 3)", () => {
    const capturedAt = "2026-08-26T09:14:00Z";
    const updatedAt = "2026-08-26T10:30:00Z";

    vi.mocked(useDoctorQueue).mockReturnValue({
      data: {
        items: [
          createVisit({
            status: "en_consulta",
            vitals: {
              weightKg: 72,
              heightCm: 172,
              temperatureC: 36.8,
              oxygenSaturationPct: 97,
              notes: "Correccion por bascula mal calibrada.",
              bmi: 24.3,
              capturedAt,
              updatedAt,
              reusedFromVisitId: null,
              reusedFrom: null,
              capturedBy: { id: 10, nombre: "Enfermera A" },
              updatedBy: { id: 11, nombre: "Enfermera B" },
            },
          }),
        ],
        page: 1,
        pageSize: 20,
        total: 1,
        totalPages: 1,
      },
      isLoading: false,
      isError: false,
      error: null,
    } as unknown as ReturnType<typeof useDoctorQueue>);

    renderDoctorPage("/clinico/consultas/doctor/1");

    // Spec `consulta-medica/vitals-display`: un valor corregido NUNCA se
    // presenta como si fuera el original -- se avisa quien corrigio y
    // cuando, usando `updatedAt` (fch_modf), NO `capturedAt` (fch_alta,
    // que nunca cambia).
    const updatedByIndicator = screen.getByTestId("vitals-updated-by");
    expect(updatedByIndicator).toHaveTextContent("Corregido por Enfermera B");
    expect(updatedByIndicator).toHaveTextContent(
      formatCapturedAtTime(updatedAt),
    );
  });

  it("no muestra aviso de correccion cuando updatedBy es null", () => {
    vi.mocked(useDoctorQueue).mockReturnValue({
      data: {
        items: [
          createVisit({
            status: "en_consulta",
            vitals: {
              weightKg: 70,
              heightCm: 172,
              temperatureC: 36.6,
              oxygenSaturationPct: 98,
              bmi: 23.7,
              capturedAt: "2026-08-26T09:14:00Z",
              updatedAt: "2026-08-26T09:14:00Z",
              reusedFromVisitId: null,
              reusedFrom: null,
              capturedBy: { id: 10, nombre: "Enfermera A" },
              updatedBy: null,
            },
          }),
        ],
        page: 1,
        pageSize: 20,
        total: 1,
        totalPages: 1,
      },
      isLoading: false,
      isError: false,
      error: null,
    } as unknown as ReturnType<typeof useDoctorQueue>);

    renderDoctorPage("/clinico/consultas/doctor/1");

    expect(screen.queryByTestId("vitals-updated-by")).not.toBeInTheDocument();
  });

  it("muestra fallback claro cuando faltan signos vitales", () => {
    vi.mocked(useDoctorQueue).mockReturnValue({
      data: {
        items: [
          createVisit({
            status: "en_consulta",
            vitals: null,
          }),
        ],
        page: 1,
        pageSize: 20,
        total: 1,
        totalPages: 1,
      },
      isLoading: false,
      isError: false,
      error: null,
    } as unknown as ReturnType<typeof useDoctorQueue>);

    renderDoctorPage("/clinico/consultas/doctor/1");

    expect(screen.getAllByText("No registrado").length).toBeGreaterThanOrEqual(
      5,
    );
    expect(
      screen.getByText("Sin observaciones de somatometria registradas."),
    ).toBeVisible();
  });

  it("la pestana 'Pacientes en proceso' muestra el pipeline completo, sin filtrar por medico", async () => {
    vi.mocked(useDoctorPipelineQueue).mockReturnValue({
      data: {
        items: [
          createVisit({
            id: 501,
            folio: "VST-0501",
            status: "en_espera",
            doctorId: null,
            doctorNombre: null,
          }),
          createVisit({
            id: 502,
            folio: "VST-0502",
            status: "en_somatometria",
            doctorId: null,
            doctorNombre: null,
          }),
        ],
        page: 1,
        pageSize: 50,
        total: 2,
        totalPages: 1,
      },
      isLoading: false,
      isError: false,
      error: null,
    } as unknown as ReturnType<typeof useDoctorPipelineQueue>);

    const user = userEvent.setup();
    renderDoctorPage();

    // Por default se ve la cola de consulta, no el pipeline.
    expect(
      screen.queryByTestId("doctor-pipeline-view"),
    ).not.toBeInTheDocument();

    await user.click(screen.getByTestId("doctor-tab-pipeline"));

    expect(screen.getByTestId("doctor-pipeline-view")).toBeVisible();
    // Se ven visitas SIN medico asignado (doctorId null) en etapas
    // tempranas -- confirma que no se filtra por medico.
    expect(screen.getByTestId("doctor-pipeline-card-501")).toBeVisible();
    expect(screen.getByTestId("doctor-pipeline-card-502")).toBeVisible();
    expect(screen.getByText("VST-0501")).toBeVisible();
    expect(screen.getByText("VST-0502")).toBeVisible();
  });
});
