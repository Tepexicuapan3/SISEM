import { describe, expect, it } from "vitest";
import type { AutorizadorItem, MotivoCatalogo } from "@api/types/autorizaciones/autorizadores.types";
import {
  buildAutorizadorSchema,
  type AutorizadorFormValues,
} from "@features/admin/modules/autorizadores/domain/autorizador.schemas";
import {
  accionesDisponibles,
  buildCambioEstatusSchema,
  buildRenovacionSchema,
} from "@features/admin/modules/autorizadores/domain/autorizador.estatus";
import {
  buildAltaPayload,
  buildEdicionPayload,
  buildEmptyAutorizadorValues,
  mapAutorizadorToFormValues,
} from "@features/admin/modules/autorizadores/utils/autorizador.transform";
import { describirVigencia } from "@features/admin/modules/autorizadores/utils/autorizador.format";

const CLAVES = ["LAB", "GAB", "REC", "CNO"] as const;

const valoresBase = (): AutorizadorFormValues => {
  const valores = buildEmptyAutorizadorValues([...CLAVES]);
  valores.usuarioId = 7;
  valores.fechaInicioVigencia = "2026-01-01";
  valores.fechaFinVigencia = "2026-12-31";
  valores.tipos = valores.tipos.map((tipo) =>
    tipo.clave === "REC"
      ? { ...tipo, seleccionado: true, alcance: { centros: [3], tiposCentro: [], global: false } }
      : tipo,
  );
  return valores;
};

const item = (cambios: Partial<AutorizadorItem> = {}): AutorizadorItem => ({
  id: 10,
  usuario: { id: 7, usuario: "dr.perez", nombreCompleto: "Ana Pérez", cedulas: [] },
  cargo: "Jefe de servicio",
  numeroOficio: "OF-1",
  estatus: "ACTIVO",
  estadoVigencia: "VIGENTE",
  fechaInicioVigencia: "2026-01-01",
  fechaFinVigencia: "2026-12-31",
  motivoEstatus: null,
  descripcionMotivoEstatus: null,
  fechaFinSuspension: null,
  tipos: [
    {
      id: 1,
      clave: "LAB",
      nombre: "Laboratorio",
      fechaInicioVigencia: null,
      fechaFinVigencia: null,
      alcance: { centros: [{ id: 3, nombre: "Clínica 3", clues: "C3" }], tiposCentro: [], global: false },
    },
  ],
  version: 4,
  creadoPor: null,
  fechaCreacion: null,
  modificadoPor: null,
  fechaModificacion: null,
  fechaBaja: null,
  ...cambios,
});

describe("esquema del formulario de autorizador", () => {
  const esquema = buildAutorizadorSchema({ canGrantGlobal: false, modo: "alta" });

  it("acepta un autorizador con un tipo y un centro", () => {
    expect(esquema.safeParse(valoresBase()).success).toBe(true);
  });

  it("exige elegir un usuario en el alta", () => {
    expect(esquema.safeParse({ ...valoresBase(), usuarioId: 0 }).success).toBe(false);
  });

  it("no acepta fin de vigencia anterior al inicio", () => {
    const resultado = esquema.safeParse({ ...valoresBase(), fechaFinVigencia: "2025-12-31" });
    expect(resultado.success).toBe(false);
  });

  it("exige al menos un tipo de autorización", () => {
    const valores = valoresBase();
    valores.tipos = valores.tipos.map((tipo) => ({ ...tipo, seleccionado: false }));
    expect(esquema.safeParse(valores).success).toBe(false);
  });

  it("cada tipo elegido necesita al menos un centro", () => {
    const valores = valoresBase();
    valores.tipos = valores.tipos.map((tipo) =>
      tipo.clave === "LAB" ? { ...tipo, seleccionado: true } : tipo,
    );
    const resultado = esquema.safeParse(valores);
    expect(resultado.success).toBe(false);
  });

  it("todos los centros exige el permiso global", () => {
    const valores = valoresBase();
    valores.tipos = valores.tipos.map((tipo) =>
      tipo.clave === "REC"
        ? { ...tipo, alcance: { centros: [], tiposCentro: [], global: true } }
        : tipo,
    );
    expect(esquema.safeParse(valores).success).toBe(false);
    expect(
      buildAutorizadorSchema({ canGrantGlobal: true, modo: "alta" }).safeParse(valores).success,
    ).toBe(true);
  });

  it("en la edición el usuario y la vigencia no se validan (no se editan ahí)", () => {
    const edicion = buildAutorizadorSchema({ canGrantGlobal: false, modo: "edicion" });
    expect(edicion.safeParse({ ...valoresBase(), usuarioId: 0, fechaFinVigencia: "" }).success).toBe(
      true,
    );
  });
});

describe("transformación formulario <-> API", () => {
  it("el alta solo envía los tipos elegidos y normaliza textos vacíos", () => {
    const payload = buildAltaPayload({ ...valoresBase(), cargo: "  ", numeroOficio: "" });
    expect(payload.tipos).toEqual([
      { claveTipo: "REC", alcance: { centros: [3], tiposCentro: [], global: false } },
    ]);
    expect(payload.cargo).toBeNull();
    expect(payload.numeroOficio).toBeNull();
    expect(payload.usuarioId).toBe(7);
  });

  it("todos los centros se envía sin centros ni tipos de centro", () => {
    const valores = valoresBase();
    valores.tipos = valores.tipos.map((tipo) =>
      tipo.clave === "REC"
        ? { ...tipo, alcance: { centros: [3], tiposCentro: ["CLINICA"], global: true } }
        : tipo,
    );
    expect(buildAltaPayload(valores).tipos[0].alcance).toEqual({
      centros: [],
      tiposCentro: [],
      global: true,
    });
  });

  it("la edición manda la versión que se está editando", () => {
    const payload = buildEdicionPayload(valoresBase(), 4);
    expect(payload.version).toBe(4);
    expect(payload).not.toHaveProperty("usuarioId");
  });

  it("un autorizador existente marca sus tipos con su alcance", () => {
    const valores = mapAutorizadorToFormValues(item(), [...CLAVES]);
    const lab = valores.tipos.find((tipo) => tipo.clave === "LAB");
    const rec = valores.tipos.find((tipo) => tipo.clave === "REC");
    expect(lab).toEqual({
      clave: "LAB",
      seleccionado: true,
      alcance: { centros: [3], tiposCentro: [], global: false },
    });
    expect(rec?.seleccionado).toBe(false);
    expect(valores.usuarioId).toBe(7);
  });
});

describe("acciones disponibles según estatus", () => {
  it("activo: editar, renovar, suspender y dar de baja", () => {
    expect(accionesDisponibles(item({ estatus: "ACTIVO" }))).toEqual({
      editar: true,
      renovar: true,
      suspender: true,
      reactivar: false,
      darDeBaja: true,
    });
  });

  it("suspendido: se puede reactivar pero no volver a suspender", () => {
    const acciones = accionesDisponibles(item({ estatus: "SUSPENDIDO" }));
    expect(acciones.reactivar).toBe(true);
    expect(acciones.suspender).toBe(false);
    expect(acciones.darDeBaja).toBe(true);
  });

  it("inactivo: la baja es terminal", () => {
    expect(Object.values(accionesDisponibles(item({ estatus: "INACTIVO" })))).not.toContain(true);
  });
});

describe("cambio de estatus y renovación", () => {
  const motivos: MotivoCatalogo[] = [
    { id: 1, ambito: "SUSPENSION", clave: "LICENCIA", descripcion: "Licencia", requiereDescripcionLibre: false },
    { id: 2, ambito: "SUSPENSION", clave: "OTRO", descripcion: "Otro motivo", requiereDescripcionLibre: true },
  ];
  const esquema = buildCambioEstatusSchema(motivos);

  it("exige motivo", () => {
    expect(esquema.safeParse({ motivoId: 0, descripcionMotivo: "", fechaFinSuspension: "" }).success).toBe(
      false,
    );
    expect(esquema.safeParse({ motivoId: 1, descripcionMotivo: "", fechaFinSuspension: "" }).success).toBe(
      true,
    );
  });

  it("el motivo 'Otro' exige descripción", () => {
    expect(esquema.safeParse({ motivoId: 2, descripcionMotivo: " ", fechaFinSuspension: "" }).success).toBe(
      false,
    );
    expect(
      esquema.safeParse({ motivoId: 2, descripcionMotivo: "Comisión", fechaFinSuspension: "" }).success,
    ).toBe(true);
  });

  it("renovar solo amplía la vigencia actual", () => {
    const renovar = buildRenovacionSchema("2026-12-31");
    expect(renovar.safeParse({ fechaFinVigencia: "2026-12-31" }).success).toBe(false);
    expect(renovar.safeParse({ fechaFinVigencia: "2027-12-31" }).success).toBe(true);
  });
});

describe("semáforo de vigencia", () => {
  it("distingue vigente, por vencer, vencido y pendiente", () => {
    expect(describirVigencia("VIGENTE")).toEqual({ etiqueta: "Vigente", variante: "stable" });
    expect(describirVigencia("POR_VENCER")).toEqual({ etiqueta: "Por vencer", variante: "alert" });
    expect(describirVigencia("VENCIDO")).toEqual({ etiqueta: "Vencido", variante: "critical" });
    expect(describirVigencia("PENDIENTE_INICIO")).toEqual({ etiqueta: "Por iniciar", variante: "info" });
  });
});
