/** Los consultorios suelen llamarse igual ("Medicina general"): lo que los distingue es el número. */
export const etiquetaConsultorio = (numero: number | null, nombre: string) =>
  numero != null ? `Consultorio ${numero}` : nombre;
