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
| 2. Escritorio en página | La consulta ocupa la página `/clinico/consultas/doctor/:visitId` con índice de apartados; selector Ventana/Escritorio | ✅ Implementada (sin modales anidados: pendiente) |
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
    },
    "documents": {
      "notePrintable": true,
      "medicalLeave": {"folio": "INC-12", "days": 3},
      "referrals": [{"folio": "PL-7", "type": "laboratorio", "label": "Laboratorio"}],
      "followUpDate": "2026-11-27"
    }
  }],
  "total": 1
}
```

`prescription` es `null` si no hay receta. `documents` (agregado con Mi consultorio): la nota cerrada siempre se puede reimprimir (`GET /impresion/nota/<visitId>`, con bitácora); incapacidad emitida, pases activos (leídos por `ReferralRepository`, el repositorio del dominio pases) y la fecha de seguimiento de la nota son informativos. `printable` aplica la misma regla que la impresión: con medicamentos activos y sin autorización pendiente ni rechazada.

**Normas:** NOM-024 (disponibilidad: la receta no depende de un aviso pasajero; confidencialidad: solo las consultas propias del día). Lo histórico queda en el expediente → Historial.

**Archivos:** `uses_case/attended_today_usecase.py`, `DoctorAttendedTodayView`, `components/AttendedTodayPanel.tsx` y `AttendedTodayList.tsx`, `queries/useDoctorAttendedToday.ts`. Tests: `test_doctor_attended_today.py`, `AttendedTodayList.ui.test.tsx`.

## Fase 2: escritorio en página

Selector **Vista de la consulta: Ventana / Escritorio** en el encabezado (preferencia de cada médico, guardada en su navegador; por default **Ventana**, la vista actual, hasta que la Gerencia decida).

- **Ventana:** igual que hoy, la consulta en un modal sobre la bandeja.
- **Escritorio:** al abrir una consulta, ocupa la página. Se ocultan la bandeja, el aviso de próxima cita y "Atendidas hoy" para concentrarse en el paciente. El encabezado del paciente queda fijo con el **índice de apartados** (Visita, Diagnóstico, Nota médica, Receta, Otros documentos) y las acciones (Guardar diagnóstico, Finalizar consulta, Volver a bandeja) quedan fijas abajo.

Las dos vistas usan el mismo componente (`ConsultationWorkspace`): mismas reglas, mismos permisos y mismos guardados. No cambia el backend ni el flujo clínico.

**Pendiente de esta fase:** exploración física, diagnósticos secundarios y medicamentos siguen abriendo su propia ventana. Pasarlos a edición en línea va junto con la Fase 4 (la nota se crea al iniciar), porque hoy dependen de que el diagnóstico esté guardado.

**Archivos:** `components/ConsultationWorkspace.tsx`, `components/ConsultationDetailDialog.tsx` (envoltorio del modal), `state/consultationLayoutStore.ts`, `pages/DoctorConsultationPage.tsx`. Tests: bloque "vista escritorio" en `DoctorConsultationPage.ui.test.tsx`.

## Mi consultorio (evolución de la vista Escritorio)

Con **Vista: Escritorio** la página es fija en tres columnas (≥ 1280 px; en pantallas angostas pasan a pestañas *Por atender · Consulta · Atendidas hoy*):

| Columna | Contenido |
|---|---|
| Por atender | Aviso de próxima cita y cola compacta; el paciente abierto queda marcado |
| Consulta | El workspace de la Fase 2, o "Elegí un paciente de Por atender" |
| Atendidas hoy | Resumen de recetas por autorizar y rechazadas; por paciente: imprimir receta, reimprimir nota, incapacidad, pases y seguimiento |

Al finalizar la consulta el paciente pasa de la izquierda a la derecha con sus documentos. **Ventana** sigue igual (solo suma el botón Nota en Atendidas hoy).

**Pendiente:** imprimir incapacidad y pase (no hay plantilla de impresión); la cita de seguimiento agendada vive en recepción y aquí solo se muestra la fecha indicada en la nota.

**Archivos:** `components/DoctorDeskLayout.tsx`, `components/DeskQueueList.tsx`, `AttendedTodayList.tsx` (documentos, nota, pendientes), `MedicalLeaveRepository.active_by_consultation`, `ReferralRepository.active_by_consultation`.

### Diseño de Mi consultorio

- **Tres paneles con el mismo encabezado** (ícono, título, contador y una línea de ayuda) para leerlos igual.
- **Barra de color a la izquierda** = urgencia o estado, con los tokens del sistema (funcionan en modo oscuro):
  - Por atender: azul en consulta, rojo "¡ahora!" (±5 min), ámbar ≤ 15 min.
  - Atendidas: verde lista, ámbar pendiente, rojo rechazada.
- **Por atender** ordena en consulta primero y luego por hora; la hora va grande. El aviso de próxima cita abre al paciente con un clic.
- **Consulta vacía:** botón "Atender a …" / "Continuar con …" con el siguiente sugerido (en consulta → próxima cita → primero que espera).
- **Atendidas hoy en tarjetas:** estado con ícono, documentos con ícono y botones Receta / Nota de ancho completo. La vista Ventana conserva su renglón.
