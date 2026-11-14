# Crónicos — Entrega 3: alta al padrón con identidad y origen del diagnóstico

Estado: en curso (2026-11-13). Rama `SISEM-15-07-2026`, commits locales sin push.
Sigue a [cronicos-control.md](cronicos-control.md).

## Qué resuelve

Revisión del formulario de alta de Padrones contra la NOM-024-SSA3-2012
(identificación unívoca del paciente, catálogos estándar, trazabilidad):

| # | Hueco | Riesgo |
|---|---|---|
| 1 | Se escribe expediente + "Familiar (0 = titular)" a mano y se inscribe sin ver a quién | Diagnóstico cargado al miembro equivocado de la familia |
| 2 | La inscripción no guarda de dónde salió el diagnóstico (consulta o captura manual) | Sin trazabilidad del dato clínico; solo la auditoría lo sabía |
| 3 | El buscador ofrece cualquier CIE-10 sin decir a qué programa pertenece | Padrón de crónicos con diagnósticos agudos; reportes contaminados |
| 4 | La fecha de inscripción no tiene límite hacia atrás | Fechas anteriores al nacimiento |

Regla: **solo agregar**. El POST de alta sigue recibiendo lo mismo; nada se
borra ni cambia de significado.

## Diseño

| Pieza | Decisión | Qué NO cambia |
|---|---|---|
| Miembros de la familia | `GET padrones/miembros?noExp=` con `clinico:padrones:write`. Lee por el contrato nuevo `recepcion/contracts/patient_lookup_contract.family_members` (reusa `lookup_patient`, sin fotos, solo vigentes). Devuelve idPaciente, nombre, parentesco, edad y fecha de nacimiento. | `/visits/patient-lookup` y su permiso de recepción |
| Selector en el alta | Se busca el expediente y se **elige a la persona**; el pkNum sale de la selección. El idPaciente se registra para que el guardado no vuelva a buscar. | El cuerpo del POST |
| Origen | Dos columnas que admiten vacío en `cns_padron_cronico`: `origen` (`consulta` / `manual`) e `id_visit`. El alta manual guarda `manual`; la de la consulta guarda `consulta` y la visita. Se devuelve `source` en el contrato. | Filas existentes: quedan con `origen` vacío |
| Programa en el buscador | Cada opción de CIE trae `program` (o `null`) con la regla de prefijos que ya existe. La pantalla muestra el programa y avisa si no tiene. No se bloquea (hay crónicos fuera de los 5 programas). | Qué CIE se ofrecen |
| Fecha | El backend rechaza una inscripción anterior a la fecha de nacimiento del paciente (si se conoce). La pantalla pone ese mínimo. | La regla de fecha no futura |

### Datos que escribe la migración

`padrones 0006`: agrega `origen` y `id_visit` (ambas admiten vacío) a
`cns_padron_cronico`. Solo esquema: no escribe datos.

## Tareas (TDD: pruebas primero)

1. [x] Pruebas backend (`test_alta_padron.py`): miembros (permiso, expediente vacío, sin fotos), origen manual y consulta, programa en opciones, fecha anterior al nacimiento.
2. [x] Contrato, caso de uso, vista, modelo y migración: `apps.padrones` 58/58 con el venv (SQLite en memoria, ver `docs/getting-started/setup.md`); `makemigrations --check` sin cambios.
3. [x] Prueba de UI del alta (rojo → verde, 8/8).
4. [x] Frontend: selector de familiar, programa en el buscador, mínimo de fecha (tsc y eslint limpios).
   La búsqueda del expediente es **automática**: se pide medio segundo después de dejar de escribir (una petición por expediente, no por tecla), sin botón.
5. [ ] Prueba manual en el navegador (usuario).
