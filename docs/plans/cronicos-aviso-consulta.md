# Crónicos — Entrega 1: aviso en consulta y sugerencia de inscripción

Estado: en curso (2026-11-11). Rama `SISEM-15-07-2026`, commits locales sin push.

## Qué resuelve

Paridad con el legado (P-04 del mapa de procesos): si el paciente está en el
padrón de crónicos, **toda consulta muestra un aviso con sus padecimientos**.
Además, al elegir un diagnóstico que pertenece a un programa de crónicos, el
médico ve *"¿Inscribir al padrón?"* y lo inscribe con un clic, sin salir de
la consulta.

Fuera de alcance (entregas siguientes): control y semáforo, migración de
`det_cronicodeg`, tope de receta ampliado, receta de continuidad, tablero.

## Diseño

| Pieza | Dónde | Decisión |
|---|---|---|
| Programas de crónicos | `padrones` (`cat_programa_cronico`, `cat_programa_cronico_cie`) | Catálogo propio del dominio padrones. Un programa agrupa prefijos CIE-10; un prefijo pertenece a un solo programa. Gana el prefijo más largo. Se compara sin punto y en mayúsculas (`E11.9` = `E119`). |
| Aviso | `GET /api/v1/padrones/cronicos/visita/<visitId>/aviso?cie=<código>` | Lee la visita por el contrato `recepcion.contracts.visit_flow_contract.get_visit_by_id`, no por el modelo. Devuelve inscripciones **activas** del paciente, con su programa, y la sugerencia para el `cie` recibido. |
| Inscribir desde la consulta | `POST /api/v1/padrones/cronicos/visita/<visitId>` `{itemId, notes?}` | Paciente y centro salen de la visita (no del usuario). Mismas reglas que el alta del padrón (una activa por paciente y CIE). Auditado con `RegistryEnrollmentCreated` y `meta.source = "consulta"`. |
| Frontend | `ChronicConditionsNotice` en el diálogo de consulta | Componente de presentación; la regla de "a qué programa pertenece" vive en el backend. |

### Reglas de la sugerencia

Se sugiere solo si: el CIE existe y está activo, pertenece a un programa
activo, el usuario puede ver ese CIE (los sensibles redactados no se sugieren)
y el paciente **no** tiene una inscripción activa en el mismo programa.

### Permisos

- Aviso: `clinico:consultas:read` (el médico que atiende) o `clinico:padrones:read`.
- Inscribir: `clinico:padrones:write` (sin cambios). El aviso devuelve
  `canEnroll`; sin el permiso, la pantalla muestra la sugerencia como texto,
  sin botón.
- Diagnósticos sensibles: se redactan con `redact_cie_if_restricted`, igual
  que en el resto del expediente.

### Auditoría

- Inscripción: evento de auditoría con antes/después (igual que el alta del padrón).
- Lectura del aviso: **no** genera un evento por apertura. La lectura ocurre
  solo dentro de una visita que el médico ya atiende (la consulta queda
  registrada), y un evento por cada apertura del diálogo sería ruido sin valor
  de trazabilidad. Si cumplimiento lo pide, se agrega en el caso de uso.

### Datos que escribe la migración

`padrones 0004` crea las dos tablas de catálogo y siembra 5 programas con
13 prefijos (fuente: NOM-015, NOM-030, NOM-037, NOM-008 y ERC):

| Programa | Prefijos CIE-10 |
|---|---|
| Diabetes mellitus | E10, E11, E12, E13, E14 |
| Hipertensión arterial | I10, I11, I12, I13, I15 |
| Dislipidemias | E78 |
| Obesidad | E66 |
| Enfermedad renal crónica | N18 |

Solo inserta en las tablas nuevas; no toca datos de otros dominios. La lista
es un punto de partida: un médico la valida antes del despliegue.

## Tareas (TDD: pruebas primero)

1. [x] Pruebas del catálogo y del emparejamiento por prefijo (rojo).
2. [x] Pruebas del aviso y la sugerencia: activas, bajas excluidas, otro paciente, redacción, permisos, 404 (rojo).
3. [x] Pruebas de inscripción desde la visita: centro de la visita, duplicado 409, permiso 403, auditoría (rojo).
4. [x] Modelos, migración, caso de uso, vistas y rutas (verde).
5. [x] Frontend: tipos, API, query, mutación y componente, con prueba de UI.
6. [ ] Prueba manual en el navegador (usuario).
