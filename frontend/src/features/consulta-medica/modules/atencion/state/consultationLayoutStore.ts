import { create } from "zustand";
import { persist } from "zustand/middleware";

/**
 * Como se abre la consulta del medico (PROPUESTA, Fase 2):
 * - "ventana": el detalle en un modal sobre la bandeja (vista actual).
 * - "escritorio": el detalle ocupa la pagina, con indice de apartados.
 * Es preferencia de cada medico en su equipo; no cambia datos clinicos.
 */
export type ConsultationLayout = "ventana" | "escritorio";

interface ConsultationLayoutState {
  layout: ConsultationLayout;
  setLayout: (layout: ConsultationLayout) => void;
}

export const useConsultationLayoutStore = create<ConsultationLayoutState>()(
  persist(
    (set) => ({
      layout: "ventana",
      setLayout: (layout) => set({ layout }),
    }),
    {
      name: "consultation-layout",
      partialize: (state) => ({ layout: state.layout }),
    },
  ),
);
