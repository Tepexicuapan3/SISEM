# Tablas que NO se modifican al contraer la llave vieja

> **Pendiente de revisión por el usuario.** Lista acordada el 2026-10-27 dentro del plan
> [contraer-llave-paciente.md](contraer-llave-paciente.md). Estas tablas conservan `no_exp` /
> `pk_num` por el motivo indicado; cualquier cambio a esta lista se decide al revisarla.

## Las que NO toco (y por qué)

| Tabla | Por qué se queda |
|---|---|
| `cns_paciente`, `cns_identificador_paciente` | Son la identidad: ahí vive la llave, una sola vez |
| `cns_paciente_provisional`, `cns_paciente_sermed`, `cns_persona_descarte` | Guardan datos del **titular** o del **candidato** de SERMED, no del paciente atendido |
| Réplica de Expedientes (`cat_empleados`, `cat_familiar`, fotos) | Es la copia de SERMED |
| `bitacora_acceso`, `bitacora_sync_expediente`, `imp_bitacora_impresion` | Bitácoras: dejan constancia de qué expediente se consultó o imprimió |
| `solicitudes_arco` | Las puede pedir alguien que nunca se atendió |
| `portal_miembros` | La cuenta del portal se liga a un familiar de SERMED que quizá todavía no existe en SIRES |
| `det_usuarios` | Es el expediente del **usuario del sistema** (empleado), no de un paciente |
| `cns_legacy_consultation_record`, `cns_nota_historica`, `cns_signos_vitales_legado`, `cns_conflicto_migracion` | Del legado viejo: se retiran aparte, con el nuevo diseño |

## Revisión

- [ ] Revisada por el usuario (fecha: ____ ) — cambios acordados:
