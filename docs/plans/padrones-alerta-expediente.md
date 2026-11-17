# Padrones — alerta de crónico / discapacidad en el expediente

Estado: en curso (2026-11-17). Rama `SISEM-15-07-2026`.
Sigue a [cronicos-gestion-padron.md](cronicos-gestion-padron.md). Hallazgos B1/B2
de la revisión funcional de crónicos.

## Qué resuelve

La tarjeta "Alertas Médicas → Padecimientos Crónicos" del expediente
(`ExpedienteDetailPage.tsx`) estaba fija en vacío: no tenía fuente. El aviso de
crónicos solo aparecía dentro de una consulta (pide la visita). Quien abre el
expediente no se enteraba de que el paciente está en un padrón.

Regla: **solo agregar**. Si el paciente no está en ningún padrón, la tarjeta no
aparece, como hoy. No hay migración ni escritura de datos.

## Diseño

| Pieza | Decisión | Qué NO cambia |
|---|---|---|
| Endpoint | `GET pacientes/<idPaciente>/padrones` → `{cronicos: [...], discapacidad: [...]}`, solo inscripciones **activas**, con el mismo contrato de fila del listado (programa y último control en crónicos) | Listado, alta, baja, aviso de la consulta |
| Permiso | Cualquiera de `clinico:expedientes:read`, `clinico:consultas:read`, `clinico:padrones:read` (quien ya ve el expediente o atiende) | `clinico:padrones:read` sigue siendo el del listado completo |
| CIE sensible | Se redacta igual que en el resto del expediente; sin programa visible | — |
| Paciente sin registro / id desconocido | Listas vacías (no 404: no confirma si el id existe) | — |
| Pantalla | La tarjeta "Alertas Médicas" muestra crónicos (CIE, programa, control vencido) y discapacidades del miembro elegido | Alergias, pestañas |

Fuera de esta entrega: auditoría de lectura del expediente y alcance por centro
(ver revisión de seguridad del expediente, pendiente de decisión).

## PROPUESTA para la Gerencia: dónde se muestra la leyenda y quién la ve

**Ninguna norma fija el lugar en pantalla.** La NOM-004 y la NOM-024 no tienen
disposiciones sobre alertas visuales; establecen qué consta en el expediente y
quién puede acceder. El lugar lo decide la institución, y la decisión queda
escrita aquí.

### Fundamento (verificado contra el texto oficial el 2026-11-17)

| Norma | Numeral | Qué dice | Consecuencia |
|---|---|---|---|
| NOM-004-SSA3-2012, expediente clínico (DOF 15/10/2012) | 6.1.1 | El interrogatorio de la historia clínica incluye los antecedentes personales patológicos | Que el paciente es crónico es información que el médico debe tener presente |
| NOM-004-SSA3-2012 | 5.5, 5.5.1 y 5.7 | Los datos que identifican al paciente son confidenciales (secreto médico); la información "será manejada con discreción y confidencialidad, por todo el personal del establecimiento" | Solo la ve el personal que atiende; nunca en pantallas públicas |
| NOM-024-SSA3-2012, SIRES (DOF 30/11/2012) | 6.6.4 | "Los SIRES deben implementar mecanismos de autorización basada en roles"; los perfiles los define el prestador | Quién la ve se decide por permiso, no por pantalla |
| NOM-024-SSA3-2012 | 6.6.1 y 3.42 | Asegurar confidencialidad, integridad, disponibilidad, **trazabilidad** y no repudio; la bitácora es el "registro cronológico de actividades de los usuarios" | Fundamenta la auditoría de lectura del expediente (pendiente) |
| Ley General de Protección de Datos Personales en Posesión de Sujetos Obligados | art. 3 (fracción X en el texto consultado, última reforma DOF 14/11/2025) | Los datos de salud son **datos personales sensibles** (esfera más íntima; su mal uso puede discriminar) | Principio de mínimo necesario: mostrar solo lo que hace falta para atender |

Pendiente que confirme jurídico o el área de protección de datos: la fracción
del art. 3 (la ley se reexpidió en 2025 y algunas fuentes citan otra numeración)
y si a la institución le aplica esta ley o la LFPDPPP (particulares).

### Lo que se propone

1. **Dónde:** junto al nombre del paciente en el encabezado del expediente y en
   la barra fija de la consulta; el detalle va en la tarjeta "Alertas
   Médicas". **Nunca** en recepción, agenda, sala de espera, turneros ni
   impresos que entrega el paciente.
2. **Quién:** quien tenga `clinico:expedientes:read`, `clinico:consultas:read`
   o `clinico:padrones:read` (personal que interviene en la atención). Para
   restringir más, por ejemplo si un perfil no debe ver discapacidad, basta
   con cambiar `PATIENT_REGISTRIES_REQUIREMENT` en
   `padron_usecase.py`, sin tocar pantallas.
3. **Qué muestra:** el programa ("Crónico: Diabetes mellitus"), si el control
   está vencido y la discapacidad. Un diagnóstico sensible (p. ej. VIH) sin
   permiso solo dice "Crónico".
4. **Trazabilidad:** registrar quién abrió cada expediente (NOM-024 6.6.1),
   como siguiente entrega.

## Tareas (TDD: pruebas primero)

1. [x] Pruebas backend (`test_padrones_paciente.py`, 5): activas de ambos padrones, sin las de baja, sin las de otro paciente, permiso por cualquiera de los tres, 403 sin ninguno, CIE redactado, id inexistente → vacío, API. Rojo: las 5 fallan.
2. [x] Caso de uso `patient_registries`, vista y ruta: `apps.padrones` 74/74 (las 69 anteriores sin cambios).
3. [x] Pruebas de UI (rojo → verde): `PatientRegistriesAlert.ui.test.tsx` (3) y un caso de API en `unit/padrones/padrones.test.ts` (por idPaciente; sin id no pregunta).
4. [x] Frontend: tipos, `padronesAPI.patientRegistries` (con `rutaPaciente`), `usePatientRegistries` (sin reintentos: un 403 solo oculta la alerta), `PatientRegistriesAlert`, y la tarjeta "Alertas Médicas" del expediente. flujo-clinico + unit/padrones 144/144; tsc y eslint limpios.
5. [x] Más visible: `PatientRegistryFlags`, distintivos junto al nombre del paciente en el encabezado del expediente y en la barra fija de la consulta ("Crónico: Diabetes mellitus", rojo con "· control vencido", "Discapacidad: …"; el detalle va en el tooltip; un CIE restringido solo dice "Crónico"). Prueba `PatientRegistryFlags.ui.test.tsx` (3, rojo → verde). La tarjeta "Alertas Médicas" se mantiene como detalle.
6. [ ] Prueba manual (usuario).
