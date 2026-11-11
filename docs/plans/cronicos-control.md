# Crónicos — Entrega 2: control en la consulta con metas y semáforo

Estado: en curso (2026-11-11). Rama `SISEM-15-07-2026`, commits locales sin push.
Sigue a [cronicos-aviso-consulta.md](cronicos-aviso-consulta.md).

## Qué resuelve

Cuando un paciente inscrito en un programa llega a consulta, el médico ve en
un solo lugar sus valores de hoy contra la meta del programa, con un semáforo,
y registra el control con un clic. El sistema propone la fecha del próximo
control. El legado no hacía esto: es funcionalidad nueva, no hay nada que migrar.

Fuera de alcance: tablero por centro, laboratorio con valores automáticos,
corrección de un control ya registrado (se hará con addendum).

## Diseño

| Pieza | Decisión |
|---|---|
| Parámetros | Lista fija en código (`ControlParameter`): presión sistólica y diastólica, glucosa capilar, IMC, peso y cintura salen de **somatometría**; HbA1c, colesterol total, LDL y triglicéridos se **capturan a mano** (hoy el resultado de laboratorio es solo un archivo). |
| Metas | Catálogo `cat_meta_control_cronico` (programa + parámetro + mínimo/máximo), editable sin deploy. Cada programa trae `dias_control` (periodicidad). |
| Control | `cns_control_cronico`: paciente, programa, visita, centro, fecha, estado, próximo control, adherencia, notas, quién registra. Uno por programa y visita. |
| Mediciones | `cns_control_cronico_medicion`: valor, unidad, fuente (`somatometria` / `manual`) y **copia de la meta vigente** al registrar, para que el histórico no cambie si después se ajusta la meta. |
| Lectura de vitales | Contrato nuevo `apps/somatometria/contracts.py` (`vitals_for_visit`); padrones no lee la tabla de somatometría. Los valores de somatometría **los toma el backend**: el cliente no los manda. |
| Reglas | Funciones puras en `apps/padrones/domain/control_cronico.py`: semáforo por parámetro y estado general. |

### Estado del control

| Estado | Cuándo |
|---|---|
| `sin_datos` | Ningún parámetro con meta tiene valor. |
| `descontrolado` | Al menos un valor fuera de meta. |
| `incompleto` | Todo lo medido está en meta, pero falta algún parámetro con meta. |
| `controlado` | Todos los parámetros con meta medidos y en meta. |

Los límites son inclusivos (130 con meta máxima 130 está en meta).

### Reglas de registro

- Permiso nuevo `clinico:cronicos:control` (se asigna a mano al médico, como los del padrón).
- La visita debe estar `en_consulta` y el paciente inscrito (activo) en ese programa.
- Valores manuales solo para parámetros de captura manual con meta en el programa, entre 0 y 1000.
- Un control por programa y visita (409 si se repite). Es de solo agregar: no hay edición ni borrado.
- Próximo control = fecha del control + `dias_control` del programa.
- Auditoría: `ChronicControlRegistered` con el estado y los valores registrados.

### Metas iniciales (las valida un médico antes del despliegue)

| Programa | Metas | Cada |
|---|---|---|
| Diabetes (NOM-015) | HbA1c ≤ 7 %; glucosa capilar 70–130 mg/dL; TA ≤ 130/80 | 90 días |
| Hipertensión (NOM-030) | TA ≤ 140/90 | 90 días |
| Dislipidemias (NOM-037) | Colesterol total ≤ 200; LDL ≤ 130; triglicéridos ≤ 150 mg/dL | 180 días |
| Obesidad (NOM-008) | IMC 18.5–24.9 | 90 días |
| ERC | TA ≤ 130/80 | 90 días |

La cintura se muestra sin semáforo: su meta depende del sexo y queda para
cuando un médico la defina.

### Datos que escribe la migración

`padrones 0005` agrega `dias_control` a `cat_programa_cronico`, crea las 3
tablas nuevas y siembra 12 metas. Solo toca tablas de padrones.

## Tareas (TDD: pruebas primero)

1. [x] Pruebas de las reglas puras (semáforo y estado).
2. [x] Pruebas del panel: vitales de la visita, metas, último control, sin programa restringido, permisos.
3. [x] Pruebas del registro: estado calculado, copia de meta, próximo control, 409, visita no en consulta, valores inválidos, auditoría.
4. [x] Contrato de somatometría, modelos, migración, caso de uso, vistas (verde).
5. [x] Frontend: panel de control en la consulta, con prueba de UI.
6. [ ] Prueba manual en el navegador (usuario).
