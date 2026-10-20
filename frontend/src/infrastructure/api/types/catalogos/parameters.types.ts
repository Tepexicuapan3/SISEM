// Parametros operativos por centro (backend `parameters/`, reemplazo de ope_param).

export type ParametroTipo = "ENTERO" | "DECIMAL" | "BOOLEANO" | "TEXTO";

export interface ParametroCentroValor {
  centerId: number;
  centerName: string;
  value: string;
  updatedAt: string;
}

export interface Parametro {
  key: string;
  description: string;
  module: string;
  valueType: ParametroTipo;
  /** Siempre texto canonico: "60", "true", "3000.50". */
  generalValue: string;
  minValue: number | null;
  maxValue: number | null;
  allowsCenterOverride: boolean;
  legacySource: string | null;
  updatedAt: string;
  centerValues: ParametroCentroValor[];
}

export interface ParametrosListResponse {
  items: Parametro[];
}

export interface ParametroDetailResponse {
  parameter: Parametro;
}

export interface ParametroValueRequest {
  value: string;
}
