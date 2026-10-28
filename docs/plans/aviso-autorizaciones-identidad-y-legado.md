# Aviso para la conversación de autorizaciones: identidad del paciente, legado y C7

> Fecha: 2026-10-28. Para la conversación que trabaja `autorizaciones`, `autorizadores`, `notificaciones`
> y el envío de recetas y pases al motor de autorizaciones. Léelo **antes de seguir** y aplícalo a lo que
> ya hiciste.

## 1. Por qué te llega esto

En paralelo se cambió cómo SIRES identifica al paciente y cómo se trata el sistema legado. La usuaria
detectó que se migraron y llenaron tablas con datos del legado, y eso **va contra lo acordado**. Además,
en la próxima versión (C7) se **borran** columnas de 22 tablas. Si tu código las usa, se rompe.

## 2. Reglas acordadas (obligatorias)

### Legado (MySQL de SISEM y su copia nocturna `sisem_legado`)
1. **No se copia información del legado a SIRES de forma masiva.** No hay migraciones de datos, comandos
   ni scripts que pasen filas del legado a tablas de SIRES.
2. El legado se usa de dos formas, y nada más:
   - **Lectura en vivo, solo lectura**, desde la copia nocturna (`consulta_medica/services/legado_archivo.py`,
     alias de BD `legado`). Solo se muestra y no se guarda en SIRES.
   - **Confirmación del médico, por sección** (`consulta_medica/services/legado_confirmacion.py`). Un dato
     del legado entra a SIRES solo cuando un médico lo confirma en pantalla.
3. El código Java/JSP del legado **no se modifica**. Es solo de referencia.
4. Runbook del legado: [docs/runbooks/legado-tres-capas.md](../runbooks/legado-tres-capas.md). Del
   paso 2 en adelante está **pospuesto** por la usuaria.

### Otras fuentes
- **Oracle SERMED: solo SELECT.** Nunca UPDATE, INSERT ni DDL. Los diseños usan lo que Oracle ya tiene.
- **No se accede a la BD de producción.** Se trabaja con dump y código; a la usuaria se le dan SELECTs de
  solo lectura para que los corra ella.

### Forma de trabajo
- **Solo agregar.** Lo que falta se agrega; los cambios a código existente se **proponen** a la usuaria y
  se aplican cuando ella los aprueba.
- Commits en formato convencional, **sin `Co-Authored-By` ni ninguna atribución a IA**. Un commit y un
  push por bloque.
- No hacer build después de los cambios. Corre los tests del módulo mientras trabajas y las suites
  completas sin bloquear.
- Ante una decisión de diseño: preguntar y esperar la respuesta.

## 3. Cómo se identifica al paciente (ya desplegado, C0–C6)

| Tabla | Para qué |
|---|---|
| `cns_persona` (`id_persona`, uuid NOM-024) | La persona. La historia se lee **por persona**. |
| `cns_paciente` (`id_paciente`) | La afiliación atendida. Ahí vive la llave **una sola vez**: `no_exp`, `pk_num` (0 = titular), `cd_provisional` (recién nacido provisional), `cd_familiar` (solo familiares del legado). |
| `cns_identificador_paciente` | Identificadores: `NO_EXP`, `PK_NUM`, `CD_FAMILIAR` (legado), `PROVISIONAL`. |

Reglas:
- **Al guardar** un dato del paciente se guarda **solo `id_paciente`**. Nunca `no_exp`, `pk_num`,
  `cd_familiar` ni la clave provisional.
- `id_paciente` es **interno**: no se muestra ni se le pide al usuario. Las búsquedas en las que el usuario
  escribe el expediente del titular siguen igual.
- El frontend manda **`idPaciente`**. No se sobrecarga `pkNum` con otros códigos.
- Lo que se muestra (expediente, número de familiar) se obtiene de `cns_paciente` con
  `llave_publica(fila)`, no de columnas copiadas.
- Puerta única: `consulta_medica/services/paciente_entrada.py` (`resolver_paciente_en_datos`,
  `paciente_de_llave`, `llave_publica`, `q_registro`, `por_id_paciente`).

## 4. Qué se borra en C7 (próxima versión)

**Se eliminan las columnas `no_exp` y `pk_num`** (en contratos, `expediente`) de estas 22 tablas, junto
con sus índices y únicos viejos:

| Módulo | Tablas |
|---|---|
| Recepción | `rcp_visits`, `citas_medicas` |
| Somatometría | `smt_visit_vitals`, `smt_patient_latest_vitals` |
| Consulta médica | `cns_allergy`, `cns_medical_leave`, `cns_study_result`, `cns_stomatology_history`, `cns_odontograma`, `cns_clinical_history`, `cns_antecedente_personal`, `cns_antecedente_familiar`, `cns_antecedente_quirurgico`, `cns_habito`, `cns_tratamiento_dental` |
| Otros | `cir_surgery`, `hsp_admission`, `amb_request`, `ref_referral`, `contratos_oxigeno` |
| Padrones | `cns_padron_cronico`, `cns_padron_discapacidad` |

Desde C6 esas columnas **ya están vacías en las filas nuevas**: una señal las pone en NULL al guardar.

**También se retira:**
- El respaldo por llave vieja de `for_patient` y la función `keys_for_person`.
- Los importadores masivos del legado (`migrar_historial_clinico_legacy`, `migrar_notas_clinicas_legacy`,
  `migrar_diagnosticos_cie_legacy`, `migrar_historia_estomatologia_legacy`) y `corregir_llave_familiares_legacy`.
- La aceptación transitoria de `noExp`/`pkNum` en los serializers que ya reciben `idPaciente`.

## 5. Lo que vi de tu trabajo (revisado en el código el 2026-10-28)

Bien:
- `aut_solicitud` guarda `id_paciente`, no la llave vieja. C7 no lo rompe.
- `pases/services/autorizacion_motor_service.py` toma `id_paciente` de `referral.patient_id` o
  `visit.patient_id`. Correcto.
- `migrar_designaciones` lee `cat_designacion_autorizador`, que es una tabla **de SIRES** (SIRES → SIRES).
- Las tareas programadas nuevas (escalamiento, vigencias, vencimiento, reintento de correos) no leen
  ninguna base externa.

A revisar o reportar:
1. **Qué tablas llenaste con datos del legado, de dónde y cómo** (comando, SQL directo en el servidor,
   migración). En el repositorio no encontré código que lo haga, así que puede haberse hecho fuera de él.
   **No borres nada**: reporta a la usuaria y espera su decisión.
2. **`aut_solicitud.tabla_legado` / `id_legado`.** Si su idea es cargar el historial de autorizaciones del
   legado, eso choca con la regla 1. No lo cargues sin aprobación de la usuaria.
3. **`aut_solicitud.id_paciente` es `BigIntegerField`, no FK a `cns_paciente`.** Propuesta, a decidir por
   la usuaria: volverlo FK (`on_delete=PROTECT`) para tener integridad referencial, como en las 22 tablas.
4. No agregues **nunca** columnas `no_exp`/`pk_num` a tablas nuevas, y no filtres por ellas en las 22
   tablas de arriba. Usa `patient`/`id_paciente` y, para mostrar, `llave_publica`.

## 6. Checklist antes de tu próximo commit

- [ ] Ningún código, migración ni comando copia datos del legado a SIRES.
- [ ] Ninguna tabla nueva tiene `no_exp`/`pk_num`. El paciente va por `id_paciente`.
- [ ] Ninguna consulta filtra por `no_exp`/`pk_num` en las 22 tablas de C7.
- [ ] Se le reportó a la usuaria qué datos del legado se cargaron (punto 5.1).
- [ ] Commit convencional sin atribución a IA.

## Referencias

- [contraer-llave-paciente.md](contraer-llave-paciente.md): plan C0–C7 y decisiones.
- [contraer-llave-paciente-tablas-sin-cambio.md](contraer-llave-paciente-tablas-sin-cambio.md): tablas
  que no se tocan (pendiente de revisión de la usuaria).
- [identidad-paciente.md](identidad-paciente.md): plan de identidad completo.
- [docs/runbooks/legado-tres-capas.md](../runbooks/legado-tres-capas.md): diseño del legado.
