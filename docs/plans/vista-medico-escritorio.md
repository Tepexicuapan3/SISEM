# Vista del médico: escritorio de consulta — PROPUESTA (2026-11-13)

Propuesta funcional en desarrollo para presentar a la Gerencia de Salud.

## Problemas de la vista actual

1. La consulta vive en un modal (`ConsultationDetailDialog`, ~720 líneas) con modales encima (exploración, diagnósticos secundarios, medicamentos).
2. Orden forzado: la nota nace al guardar el diagnóstico.
3. La consulta cerrada desaparece de la cola y la receta solo se imprime desde el aviso de cierre o el expediente.
4. Varios botones "Guardar" y sin aviso de cambios sin guardar.
5. Sin resumen fijo del paciente (alergias, crónicos, última consulta).

## Fases

| Fase | Qué | Estado |
|---|---|---|
| 1. Mi jornada | "Atendidas hoy": consultas cerradas hoy por el médico, estado de la receta e imprimir | ✅ Implementada |
| 2. Escritorio en página | Secciones del modal a la página `/consulta/:visitId`, edición en línea | Pendiente |
| 3. Resumen del paciente | Alergias siempre visibles + panel con signos, crónicos y última consulta | Pendiente |
| 4. Orden libre | La nota se crea al iniciar la consulta | Pendiente (toca el flujo clínico) |
| 5. Autoguardado y cierre guiado | Borrador automático, aviso al salir, checklist y resumen de hojas a imprimir | Pendiente |
| 6. Atajos | Repetir receta, CIE frecuentes, teclado | Pendiente |
| 7. Bloqueo por inactividad | NOM-024: confidencialidad | Pendiente (verificar sesión) |

## Fase 1: contrato

`GET /api/v1/doctor/attended-today` (rol DOCTOR o `clinico:consultas:read`).

Devuelve solo las consultas **del médico autenticado**, **activas**, con visita **cerrada** y atendidas **hoy** (America/Mexico_City), las más recientes primero:

```json
{
  "items": [{
    "visitId": 31, "folio": "V-31", "nombrePaciente": "PEREZ LOPEZ JUAN",
    "noExp": "12345", "pkNum": 0, "attendedAt": "2026-11-13T16:10:00+00:00",
    "prescription": {
      "folio": "RX-2026-31", "medicationsCount": 2, "hasControlled": true,
      "authorization": {"status": "pendiente", "rejectionReason": null},
      "printable": false
    }
  }],
  "total": 1
}
```

`prescription` es `null` si no hay receta. `printable` aplica la misma regla que la impresión: con medicamentos activos y sin autorización pendiente ni rechazada.

**Normas:** NOM-024 (disponibilidad: la receta no depende de un aviso pasajero; confidencialidad: solo las consultas propias del día). Lo histórico queda en el expediente → Historial.

**Archivos:** `uses_case/attended_today_usecase.py`, `DoctorAttendedTodayView`, `components/AttendedTodayPanel.tsx` y `AttendedTodayList.tsx`, `queries/useDoctorAttendedToday.ts`. Tests: `test_doctor_attended_today.py`, `AttendedTodayList.ui.test.tsx`.
