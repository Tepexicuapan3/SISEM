import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
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
import { visitsAPI } from "@api/resources/visits.api";
import { usePrintDocument } from "@shared/hooks/usePrintDocument";
import type { PrescriptionItem } from "@api/types";
import { useConsultationLayoutStore } from "@features/consulta-medica/modules/atencion/state/consultationLayoutStore";

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

// 5.3: la sugerencia de "primera vez / subsecuente" llama a la API real.
vi.mock("@api/resources/visits.api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@api/resources/visits.api")>();
  return {
    ...actual,
    visitsAPI: { ...actual.visitsAPI, getMorbiditySuggestion: vi.fn(), getPrescriptionItems: vi.fn() },
  };
});

vi.mock("@shared/hooks/usePrintDocument", () => ({
  usePrintDocument: vi.fn(),
}));

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

// El formulario siempre envia los 4 apartados SOAP (vacios si no se
// capturan), mas morbilidad y seguimiento (5.3; null si no se capturan).
const EMPTY_NOTE_FIELDS = {
  subjective: "",
  objective: "",
  assessment: "",
  plan: "",
  morbidity: null,
  followUpDate: null,
};

describe("DoctorConsultationPage UI", () => {
  const startMutateAsync = vi.fn();
  const saveDiagnosisMutateAsync = vi.fn();
  const savePrescriptionsMutateAsync = vi.fn();
  const closeMutateAsync = vi.fn();
  const printReceta = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    useConsultationLayoutStore.setState({ layout: "ventana" });
    vi.mocked(visitsAPI.getPrescriptionItems).mockResolvedValue({ items: [], total: 0 });
    vi.mocked(usePrintDocument).mockReturnValue({ print: printReceta, isPrinting: false });
    vi.mocked(visitsAPI.getMorbiditySuggestion).mockResolvedValue({
      cieCode: "A090",
      suggestion: "2",
      previousConsultations: 1,
    });

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
      screen.getByRole("button", { name: "Guardar indicaciones" }),
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
      // El encabezado muestra el folio solo (sin prefijo "Folio") desde el
      // rediseño del detalle de consulta.
      expect(screen.getByTestId("doctor-consultation-modal")).toHaveTextContent(
        "VST-2002",
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
      screen.getByLabelText(/S\s*Subjetivo/),
      "Evacuaciones liquidas de 2 dias.",
    );
    await user.type(screen.getByLabelText(/P\s*Plan$/), "Hidratacion oral.");
    expect(screen.queryByLabelText("Padecimiento actual")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Plan terapeutico")).not.toBeInTheDocument();

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
          subjective: "Evacuaciones liquidas de 2 dias.",
          plan: "Hidratacion oral.",
        },
      });
    });

    expect(toast.success).toHaveBeenCalledWith("Diagnostico guardado");
  });

  it("captura el SOAP en un apartado por letra y lo envia separado", async () => {
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

    await user.type(screen.getByLabelText("Diagnostico principal"), "Faringitis");
    await user.type(screen.getByLabelText("Nota final"), "Egreso a domicilio.");
    await user.type(screen.getByLabelText(/S\s*Subjetivo/), "Dolor de garganta");
    await user.type(screen.getByLabelText(/O\s*Objetivo/), "Faringe hiperemica");
    await user.type(screen.getByLabelText(/A\s*Análisis/), "Faringitis viral");
    await user.type(screen.getByLabelText(/P\s*Plan$/), "Liquidos y reposo");

    await user.click(screen.getByRole("button", { name: "Guardar diagnostico" }));

    await waitFor(() => {
      expect(saveDiagnosisMutateAsync).toHaveBeenCalledWith({
        visitId: 1,
        data: {
          primaryDiagnosis: "Faringitis",
          finalNote: "Egreso a domicilio.",
          ...EMPTY_NOTE_FIELDS,
          subjective: "Dolor de garganta",
          objective: "Faringe hiperemica",
          assessment: "Faringitis viral",
          plan: "Liquidos y reposo",
        },
      });
    });
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

  it("guarda las indicaciones generales, una por linea", async () => {
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
      screen.getByLabelText(/Indicaciones generales/),
      "Paracetamol 500mg cada 8h por 3 dias\nHidratacion oral libre",
    );

    await user.click(screen.getByRole("button", { name: "Guardar indicaciones" }));

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

    expect(toast.success).toHaveBeenCalledWith("Indicaciones guardadas");
  });

  it("ordena la consulta en apartados con titulo", () => {
    renderDoctorPage("/clinico/consultas/doctor/1");

    for (const title of ["Datos de la visita", "Diagnóstico", "Nota médica", "Receta", "Otros documentos"]) {
      expect(screen.getByRole("heading", { name: title })).toBeInTheDocument();
    }
  });

  it("con la consulta iniciada avisa que lo demas requiere guardar el diagnostico", () => {
    vi.mocked(useDoctorQueue).mockReturnValue({
      data: { items: [createVisit({ status: "en_consulta" })], page: 1, pageSize: 20, total: 1, totalPages: 1 },
      isLoading: false,
      isError: false,
      error: null,
    } as unknown as ReturnType<typeof useDoctorQueue>);

    renderDoctorPage("/clinico/consultas/doctor/1");

    expect(screen.getByText(/Al guardar el diagnóstico se crea la nota de la consulta/)).toBeInTheDocument();
  });

  it("aclara que los medicamentos no van en las indicaciones generales", () => {
    renderDoctorPage("/clinico/consultas/doctor/1");

    expect(
      screen.getByText(/Los medicamentos se agregan arriba, en Medicamentos/),
    ).toBeInTheDocument();
  });

  it("oculta Iniciar consulta cuando la consulta ya esta iniciada", () => {
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

    renderDoctorPage("/clinico/consultas/doctor/1");

    expect(screen.queryByRole("button", { name: "Iniciar consulta" })).toBeNull();
    expect(screen.getByRole("button", { name: "Finalizar consulta" })).toBeInTheDocument();
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

    // Legado (sw_morbi): tampoco se cierra sin "primera vez o subsecuente".
    expect(closeButton).toBeDisabled();
    await user.click(screen.getByLabelText("Primera vez de la enfermedad"));

    await waitFor(() => {
      expect(closeButton).toBeEnabled();
    });
  });

  it("sugiere primera vez o subsecuente segun el CIE y se puede aplicar", async () => {
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

    await user.type(screen.getByLabelText(/Buscar CIE/i), "A0");
    await user.click(await screen.findByRole("button", { name: /A090/i }));

    expect(
      await screen.findByText("Sugerido: subsecuente (1 consulta anterior con A090)."),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Usar sugerencia" }));

    expect(screen.getByLabelText("Subsecuente de la enfermedad")).toBeChecked();
    expect(visitsAPI.getMorbiditySuggestion).toHaveBeenCalledWith(1, "A090");
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
    await user.click(screen.getByLabelText("Subsecuente de la enfermedad"));

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
          morbidity: "2",
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
          morbidity: "2",
          followUpSlotId: null,
        },
      });
    });

    expect(toast.success).toHaveBeenCalledWith("Consulta cerrada", {
      description: undefined,
    });
  });

  const closeConsultationWithCie = async () => {
    vi.mocked(useCieSearch).mockReturnValue({
      data: {
        items: [{ code: "A090", description: "GASTROENTERITIS", version: "CIE-10" }],
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
    await user.type(screen.getByLabelText("Diagnostico principal"), "Dx final");
    await user.type(screen.getByLabelText("Nota final"), "Nota final de egreso");
    await user.type(screen.getByLabelText(/Buscar CIE/i), "A0");
    await user.click(await screen.findByRole("button", { name: /A090/i }));
    await user.click(screen.getByLabelText("Subsecuente de la enfermedad"));
    await waitFor(() => expect(visitsAPI.getPrescriptionItems).toHaveBeenCalledWith(1));
    await user.click(screen.getByRole("button", { name: "Finalizar consulta" }));
    await waitFor(() => expect(closeMutateAsync).toHaveBeenCalled());
  };

  it("al cerrar con medicamentos activos el aviso ofrece imprimir la receta", async () => {
    vi.mocked(visitsAPI.getPrescriptionItems).mockResolvedValue({
      items: [{ id: 5, visitId: 1, status: "activo" } as PrescriptionItem],
      total: 1,
    });

    await closeConsultationWithCie();

    await waitFor(() => {
      expect(toast.success).toHaveBeenCalledWith(
        "Consulta cerrada",
        expect.objectContaining({
          action: expect.objectContaining({ label: "Imprimir receta" }),
        }),
      );
    });
    const options = vi.mocked(toast.success).mock.calls.at(-1)?.[1] as {
      action: { onClick: () => void };
    };
    options.action.onClick();
    expect(printReceta).toHaveBeenCalledWith(1);
  });

  it("al cerrar con un especial o controlado avisa que la receta queda pendiente de autorizacion", async () => {
    vi.mocked(visitsAPI.getPrescriptionItems).mockResolvedValue({
      items: [{ id: 5, visitId: 1, status: "activo", requiresAuthorization: true } as PrescriptionItem],
      total: 1,
    });

    await closeConsultationWithCie();

    await waitFor(() => {
      expect(toast.success).toHaveBeenCalledWith(
        "Consulta cerrada",
        expect.objectContaining({
          description: expect.stringContaining("pendiente de autorización"),
        }),
      );
    });
    expect(vi.mocked(toast.success).mock.calls.at(-1)?.[1]).not.toHaveProperty("action");
  });

  it("al cerrar sin medicamentos activos el aviso no ofrece imprimir", async () => {
    vi.mocked(visitsAPI.getPrescriptionItems).mockResolvedValue({
      items: [{ id: 5, visitId: 1, status: "cancelado" } as PrescriptionItem],
      total: 1,
    });

    await closeConsultationWithCie();

    await waitFor(() => {
      expect(toast.success).toHaveBeenCalledWith("Consulta cerrada", { description: undefined });
    });
    expect(vi.mocked(toast.success).mock.calls.at(-1)?.[1]).not.toHaveProperty("action");
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
    await user.click(screen.getByLabelText("Primera vez de la enfermedad"));
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

  describe("vista escritorio (Fase 2, propuesta)", () => {
    const inConsultation = () =>
      vi.mocked(useDoctorQueue).mockReturnValue({
        data: { items: [createVisit({ status: "en_consulta" })], page: 1, pageSize: 20, total: 1, totalPages: 1 },
        isLoading: false,
        isError: false,
        error: null,
      } as unknown as ReturnType<typeof useDoctorQueue>);

    it("mi consultorio: cola, consulta y atendidas a la vez, sin ventana encima", () => {
      useConsultationLayoutStore.setState({ layout: "escritorio" });
      inConsultation();
      renderDoctorPage("/clinico/consultas/doctor/1");

      const workspace = screen.getByTestId("doctor-consultation-workspace");
      expect(workspace).toHaveTextContent("VST-2001");
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
      // La cola sigue a la izquierda, marcando al paciente abierto.
      expect(screen.getByTestId("doctor-visit-card-1")).toHaveAttribute("aria-current", "true");
      expect(screen.getByTestId("attended-today-panel")).toBeInTheDocument();

      const nav = screen.getByRole("navigation", { name: "Apartados de la consulta" });
      for (const name of ["Visita", "Diagnóstico", "Nota médica", "Receta", "Otros documentos"]) {
        expect(within(nav).getByRole("link", { name })).toBeInTheDocument();
      }
    });

    it("el selector cambia de ventana a escritorio y lo recuerda", async () => {
      const user = userEvent.setup();
      renderDoctorPage();
      expect(screen.getByRole("radio", { name: "Ventana" })).toHaveAttribute("aria-checked", "true");

      await user.click(screen.getByRole("radio", { name: "Escritorio" }));
      await user.click(screen.getByTestId("doctor-visit-card-1"));

      expect(screen.getByTestId("doctor-consultation-workspace")).toBeVisible();
      expect(screen.queryByTestId("doctor-consultation-modal")).not.toBeInTheDocument();
      expect(useConsultationLayoutStore.getState().layout).toBe("escritorio");
    });

    it("volver a bandeja deja la pagina en la cola", async () => {
      useConsultationLayoutStore.setState({ layout: "escritorio" });
      const user = userEvent.setup();
      renderDoctorPage("/clinico/consultas/doctor/1");
      expect(screen.getByTestId("doctor-consultation-workspace")).toBeVisible();

      await user.click(screen.getByRole("button", { name: "Volver a bandeja" }));

      await waitFor(() => {
        expect(screen.queryByTestId("doctor-consultation-workspace")).not.toBeInTheDocument();
      });
      expect(screen.getByTestId("doctor-visit-card-1")).toBeVisible();
      expect(screen.getByText(/Elegí un paciente de Por atender/)).toBeVisible();
    });

    it("sin paciente abierto muestra la cola, el lugar de la consulta y las atendidas", () => {
      useConsultationLayoutStore.setState({ layout: "escritorio" });
      renderDoctorPage();

      expect(screen.getByRole("heading", { name: /Por atender/ })).toBeInTheDocument();
      expect(screen.getByText(/Elegí un paciente de Por atender/)).toBeVisible();
      expect(screen.getByTestId("attended-today-panel")).toBeInTheDocument();
      expect(screen.queryByTestId("doctor-open-consultations-grid")).not.toBeInTheDocument();
    });

    it("sin pacientes en cola igual deja ver las atendidas", () => {
      useConsultationLayoutStore.setState({ layout: "escritorio" });
      vi.mocked(useDoctorQueue).mockReturnValue({
        data: { items: [], page: 1, pageSize: 20, total: 0, totalPages: 0 },
        isLoading: false,
        isError: false,
        error: null,
      } as unknown as ReturnType<typeof useDoctorQueue>);
      renderDoctorPage();

      expect(screen.getByText("No hay pacientes listos para doctor.")).toBeVisible();
      expect(screen.getByTestId("attended-today-panel")).toBeInTheDocument();
    });

    it("guarda el diagnostico desde la pagina", async () => {
      useConsultationLayoutStore.setState({ layout: "escritorio" });
      inConsultation();
      const user = userEvent.setup();
      renderDoctorPage("/clinico/consultas/doctor/1");

      await user.type(screen.getByLabelText("Diagnostico principal"), "Gastroenteritis aguda");
      await user.type(screen.getByLabelText("Nota final"), "Paciente estable.");
      await user.click(screen.getByRole("button", { name: "Guardar diagnostico" }));

      await waitFor(() => {
        expect(saveDiagnosisMutateAsync).toHaveBeenCalledWith({
          visitId: 1,
          data: { primaryDiagnosis: "Gastroenteritis aguda", finalNote: "Paciente estable.", ...EMPTY_NOTE_FIELDS },
        });
      });
    });

    it("con una consulta que ya no esta en la cola lo avisa en la pagina", () => {
      useConsultationLayoutStore.setState({ layout: "escritorio" });
      renderDoctorPage("/clinico/consultas/doctor/99");

      expect(screen.getByTestId("doctor-consultation-workspace")).toHaveTextContent(
        "La consulta seleccionada ya no esta disponible",
      );
    });
  });
});
