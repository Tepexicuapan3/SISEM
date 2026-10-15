import type { DesignacionItem, DesignacionWriteRequest } from "@api/types";
import type { DesignacionFormValues } from "@features/admin/modules/catalogos/designacion-autorizadores/domain/designacion.schemas";

const todayIso = () => {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
};

export const buildEmptyDesignacionValues = (): DesignacionFormValues => ({
  userId: 0,
  tipoAutorizacionId: 0,
  cargo: "",
  fechaInicio: todayIso(),
  fechaFin: "",
  oficio: "",
  centros: [],
  tiposCentro: [],
  global: false,
});

export const mapDesignacionToFormValues = (
  item: DesignacionItem,
): DesignacionFormValues => ({
  userId: item.userId,
  tipoAutorizacionId: item.tipoAutorizacionId,
  cargo: item.cargo,
  fechaInicio: item.fechaInicio,
  fechaFin: item.fechaFin ?? "",
  oficio: item.oficio ?? "",
  centros: item.alcance.centros.map((c) => c.id),
  tiposCentro: [...item.alcance.tiposCentro],
  global: item.alcance.global,
});

/**
 * Form -> API. Si el alcance es GLOBAL se envian centros/tipos vacios: el
 * backend rechaza (400) GLOBAL combinado con cualquier otro item.
 */
export const buildDesignacionPayload = (
  values: DesignacionFormValues,
): DesignacionWriteRequest => ({
  userId: values.userId,
  tipoAutorizacionId: values.tipoAutorizacionId,
  cargo: values.cargo.trim(),
  fechaInicio: values.fechaInicio,
  fechaFin: values.fechaFin || null,
  oficio: values.oficio.trim() || null,
  alcance: values.global
    ? { centros: [], tiposCentro: [], global: true }
    : {
        centros: [...values.centros],
        tiposCentro: [...values.tiposCentro],
        global: false,
      },
});
