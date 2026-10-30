# API Docs - SISEM

Documentacion de contratos REST consumidos por frontend y otros clientes internos.

## Fuente de Verdad

- Estandares globales: `docs/api/standards.md`
- Modulos por dominio: `docs/api/modules/*.md`
- Implementacion real: `backend/apps/**`

Si hay desalineacion entre docs y codigo, corregir primero el contrato o implementar ajuste con plan explicito; no mantener divergencia silenciosa.

## Estructura

```txt
docs/api/
├── README.md
├── standards.md
└── modules/
    ├── auth.md
    ├── rbac.md
    ├── catalogos.md
    ├── adscripcion.md      # P-03 consultorio familiar
    └── doc_front.md
```

## Reglas de Contrato

- Prefijo de rutas: `api/v1/`
- Metodos HTTP semanticos (`GET`, `POST`, `PATCH`, `DELETE`)
- Requests mutantes con CSRF (`X-CSRF-TOKEN`)
- Responses de error consistentes:
  - `code`, `message`, `status`, opcional `details`, opcional `requestId`
- Campos expuestos al frontend en `camelCase`
- Aclarar en cada modulo que la logica critica de negocio pertenece a `application/domain`, no a serializers/views.
- Documentar anti-patrones relevantes cuando apliquen (ej. reglas de negocio en transporte).

### Part 2 obligatorio en contratos API

- Comunicacion inter-dominio: explicitar si el endpoint usa contrato query/service, orquestador o eventos.
- Realtime: documentar solo si hay justificacion de negocio, con contrato de canal/auth/mensaje estandarizado.
- Auditoria: para operaciones sensibles/criticas, incluir campos auditables minimos (`actor`, `timestamp`, `action`, `domain`, `resource`, `result`, `contextId/requestId`).
- Permisos: declarar permisos atomicos requeridos por endpoint; roles se documentan solo como agrupadores.

### Part 3 obligatorio en contratos API

- Politica DB reconciliada: documentar que hoy hay una sola fuente operativa en PostgreSQL con ownership por dominio y aislamiento logico; separacion fisica despues por criterios formales.
- En endpoints criticos/mutantes, explicitar expectativas de integridad de datos y estrategia transaccional/concurrencia cuando impacte el contrato.
- Si cambia un contrato con impacto de limites o gobernanza, actualizar en el mismo PR las referencias de arquitectura/DoD.
- Definir expectativas de pruebas por riesgo para endpoints criticos (auth/authz, auditoria, transiciones de estado, concurrencia).
- Evitar riesgos top: acoplamiento cross-domain oculto, concurrencia no documentada y rediseños de contrato por moda.

## Flujo de Mantenimiento

1. Ajustar `docs/api/standards.md` si cambia una regla transversal.
2. Ajustar el modulo afectado en `docs/api/modules/`.
3. Verificar coherencia con:
   - `frontend/src/api/resources/`
   - `frontend/src/api/types/`
   - `backend/apps/**`
4. Agregar ejemplo request/response cuando se introduce un contrato nuevo.
5. Incluir nota de "cuando usar / cuando no usar" si se propone un patron nuevo (repository, eventos, politicas).
6. Si es endpoint sensible o cross-domain, validar que queden explicitos contrato de comunicacion, auditoria y permisos atomicos.
7. Para endpoints criticos, validar que queden documentadas expectativas de integridad, transaccion/concurrencia y testing por riesgo.

## Enlaces Relacionados

- Reglas de docs API para agentes: `docs/api/AGENTS.md`
- Guia general de documentacion: `docs/README.md`
