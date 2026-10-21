import { describe, expect, it } from "vitest";
import {
  buildDependencyIndex,
  buildPermissionMatrix,
  buildResourceIndex,
  getDependencyClosure,
  getMissingDependencies,
  getReverseDependents,
  parseCode,
  planBatchToggle,
  planToggle,
  resolveCodesToIds,
  type MatrixRow,
} from "@/domains/auth-access/adapters/rbac/roles/roles.permission-matrix";
import type { ModuleCatalogNodeDTO, Permission } from "@api/types";

const node = (
  overrides: Partial<ModuleCatalogNodeDTO> & { key: string },
): ModuleCatalogNodeDTO => ({
  title: overrides.key,
  icon: null,
  url: null,
  group: "primary",
  isSection: false,
  permissions: [],
  items: [],
  ...overrides,
});

let nextId = 1;
const perm = (code: string, dependsOn?: string[]): Permission => ({
  id: nextId++,
  code,
  description: code,
  isSystem: false,
  ...(dependsOn ? { dependsOn } : {}),
});

const allRows = (groups: { rows: MatrixRow[] }[]) => groups.flatMap((g) => g.rows);

describe("parseCode", () => {
  it("parsea codigos de 3, 4 y 5 segmentos", () => {
    expect(parseCode("clinico:consultas:read")).toEqual({
      code: "clinico:consultas:read",
      resource: "clinico:consultas",
      action: "read",
    });
    expect(parseCode("admin:gestion:usuarios:update")?.resource).toBe(
      "admin:gestion:usuarios",
    );
    expect(parseCode("recepcion:fichas:medicina_general:create")).toMatchObject({
      resource: "recepcion:fichas:medicina_general",
      action: "create",
    });
  });

  it("devuelve null para codigos malformados", () => {
    expect(parseCode("flow.recepcion.queue.write")).toBeNull();
    expect(parseCode("a::read")).toBeNull();
    expect(parseCode("a:b:")).toBeNull();
    expect(parseCode("")).toBeNull();
  });

  it("recorta espacios y normaliza la accion a minusculas", () => {
    expect(parseCode("  clinico:notas:Read  ")).toEqual({
      code: "clinico:notas:Read",
      resource: "clinico:notas",
      action: "read",
    });
  });
});

describe("dependencias", () => {
  const catalog = [
    perm("a:usuarios:read", []),
    perm("a:usuarios:update", ["a:roles:read", "a:usuarios:read"]),
    perm("a:roles:read", []),
  ];

  it("calcula el cierre transitivo incluyendo el propio codigo", () => {
    const index = buildDependencyIndex([
      perm("x:a:update", ["x:b:update"]),
      perm("x:b:update", ["x:c:read"]),
      perm("x:c:read", []),
    ]);
    expect([...getDependencyClosure(["x:a:update"], index)].sort()).toEqual([
      "x:a:update",
      "x:b:update",
      "x:c:read",
    ]);
  });

  it("tolera ciclos", () => {
    const index = buildDependencyIndex([perm("x:a:read", ["x:b:read"]), perm("x:b:read", ["x:a:read"])]);
    expect([...getDependencyClosure(["x:a:read"], index)].sort()).toEqual([
      "x:a:read",
      "x:b:read",
    ]);
  });

  it("calcula dependientes inversos presentes en el draft", () => {
    const index = buildDependencyIndex(catalog);
    const draft = new Set(["a:usuarios:read", "a:usuarios:update", "a:roles:read"]);
    expect([...getReverseDependents(new Set(["a:roles:read"]), draft, index)]).toEqual([
      "a:usuarios:update",
    ]);
  });

  it("infiere X:read cuando falta dependsOn (fallback)", () => {
    const index = buildDependencyIndex([
      perm("a:b:create"),
      perm("a:b:authorize"),
      perm("a:b:manage"),
      perm("a:b:read"),
    ]);
    expect(index.deps.get("a:b:create")).toEqual(["a:b:read"]);
    expect(index.deps.get("a:b:manage")).toEqual(["a:b:read"]);
    expect(index.deps.get("a:b:authorize")).toEqual([]);
    expect(index.deps.get("a:b:read")).toEqual([]);
  });

  it("el fallback no infiere read para fichas:*:create (espejo del backend)", () => {
    const index = buildDependencyIndex([perm("recepcion:fichas:urgencias:create")]);
    expect(index.deps.get("recepcion:fichas:urgencias:create")).toEqual([]);
  });

  it("no infiere si dependsOn viene (aunque sea vacio)", () => {
    const index = buildDependencyIndex([perm("a:b:create", [])]);
    expect(index.deps.get("a:b:create")).toEqual([]);
  });

  it("detecta dependencias fuera del catalogo", () => {
    const index = buildDependencyIndex([
      perm("recepcion:fichas:urgencias:create", ["recepcion:fichas:urgencias:read"]),
    ]);
    expect(getMissingDependencies("recepcion:fichas:urgencias:create", index)).toEqual([
      "recepcion:fichas:urgencias:read",
    ]);
  });

  it("resolveCodesToIds separa ids de codigos inexistentes", () => {
    const result = resolveCodesToIds(["a:roles:read", "no:existe:read"], catalog);
    expect(result.ids).toEqual([catalog[2].id]);
    expect(result.missingCodes).toEqual(["no:existe:read"]);
  });
});

describe("planToggle", () => {
  const catalog = [
    perm("a:usuarios:read", []),
    perm("a:usuarios:update", ["a:roles:read", "a:usuarios:read"]),
    perm("a:usuarios:delete", ["a:usuarios:read"]),
    perm("a:usuarios:credenciales", []),
    perm("a:roles:read", []),
  ];
  const dependencyIndex = buildDependencyIndex(catalog);
  const resourceIndex = buildResourceIndex(catalog);
  const ctx = (draft: string[]) => ({
    draftCodes: new Set(draft),
    dependencyIndex,
    resourceIndex,
  });

  it("tildar agrega el cierre de dependencias", () => {
    const plan = planToggle("a:usuarios:update", true, ctx([]));
    expect(plan.add.sort()).toEqual(["a:roles:read", "a:usuarios:read", "a:usuarios:update"]);
  });

  it("tildar una accion 'otra' marca tambien Ver del recurso", () => {
    const plan = planToggle("a:usuarios:credenciales", true, ctx([]));
    expect(plan.add.sort()).toEqual(["a:usuarios:credenciales", "a:usuarios:read"]);
  });

  it("no agrega lo que ya esta en el draft", () => {
    const plan = planToggle("a:usuarios:update", true, ctx(["a:roles:read"]));
    expect(plan.add).not.toContain("a:roles:read");
  });

  it("destildar Ver limpia todo el recurso", () => {
    const plan = planToggle(
      "a:usuarios:read",
      false,
      ctx(["a:usuarios:read", "a:usuarios:update", "a:usuarios:delete", "a:roles:read"]),
    );
    expect(plan.remove.sort()).toEqual([
      "a:usuarios:delete",
      "a:usuarios:read",
      "a:usuarios:update",
    ]);
  });

  it("destildar una dependencia en cascada quita sus dependientes", () => {
    const plan = planToggle(
      "a:roles:read",
      false,
      ctx(["a:usuarios:read", "a:usuarios:update", "a:roles:read"]),
    );
    expect(plan.remove.sort()).toEqual(["a:roles:read", "a:usuarios:update"]);
  });

  it("planBatchToggle acumula sin duplicar", () => {
    const plan = planBatchToggle(
      ["a:usuarios:update", "a:usuarios:delete"],
      true,
      ctx([]),
    );
    expect(plan.add.sort()).toEqual([
      "a:roles:read",
      "a:usuarios:delete",
      "a:usuarios:read",
      "a:usuarios:update",
    ]);
    expect(plan.remove).toEqual([]);
  });
});

describe("buildPermissionMatrix", () => {
  const tree: ModuleCatalogNodeDTO[] = [
    node({
      key: "clinico",
      isSection: true,
      items: [
        node({
          key: "clinico.consultas",
          items: [
            node({ key: "clinico.consultas.panel", permissions: ["clinico:consultas:read"] }),
            node({ key: "clinico.consultas.bandeja", permissions: ["clinico:consultas:read"] }),
          ],
        }),
        node({ key: "clinico.ambulancias", permissions: ["clinico:ambulancias:read"] }),
      ],
    }),
    node({
      key: "recepcion",
      isSection: true,
      items: [
        node({
          key: "recepcion.agenda",
          permissions: [
            "recepcion:fichas:urgencias:create",
            "clinico:consultas:read",
          ],
        }),
        node({
          key: "recepcion.fichas",
          permissions: [
            "recepcion:fichas:urgencias:create",
            "clinico:consultas:read",
          ],
        }),
      ],
    }),
    node({
      key: "administracion",
      isSection: true,
      items: [
        node({ key: "administracion.reportes.ambulancias", permissions: ["clinico:ambulancias:read"] }),
        node({ key: "administracion.panel.usuarios", permissions: ["admin:gestion:usuarios:read"] }),
      ],
    }),
  ];

  const catalog = [
    perm("clinico:consultas:read"),
    perm("clinico:consultas:create"),
    perm("clinico:consultas:authorize"),
    perm("clinico:ambulancias:read"),
    perm("clinico:ambulancias:write"),
    perm("recepcion:fichas:urgencias:create"),
    perm("admin:gestion:usuarios:read"),
    perm("admin:gestion:usuarios:update"),
    perm("clinico:notas:read"),
    perm("flow.recepcion.queue.write"),
  ];

  const matrix = buildPermissionMatrix(tree, catalog);
  const rows = allRows(matrix.groups);
  const rowFor = (moduleKey: string, resource: string) =>
    rows.find((row) => row.module.key === moduleKey && row.resource === resource);

  it("OWNER_OVERRIDES fija el dueno de consultas en la bandeja", () => {
    expect(rowFor("clinico.consultas.bandeja", "clinico:consultas")?.isOwner).toBe(true);
    expect(rowFor("clinico.consultas.panel", "clinico:consultas")?.isOwner).toBe(false);
  });

  it("el dueno muestra todas las acciones del recurso; el resto solo lo enlazado", () => {
    const owner = rowFor("clinico.consultas.bandeja", "clinico:consultas");
    expect(owner?.cells.read?.code).toBe("clinico:consultas:read");
    expect(owner?.cells.create?.code).toBe("clinico:consultas:create");
    expect(owner?.other.map((cell) => cell.code)).toEqual(["clinico:consultas:authorize"]);

    const nonOwner = rowFor("recepcion.agenda", "clinico:consultas");
    expect(nonOwner?.cells.read).toBeDefined();
    expect(nonOwner?.cells.create).toBeUndefined();
    expect(nonOwner?.other).toEqual([]);
  });

  it("recursos de fichas resuelven por prefijo de override", () => {
    expect(rowFor("recepcion.fichas", "recepcion:fichas:urgencias")?.isOwner).toBe(true);
    const shared = rowFor("recepcion.agenda", "recepcion:fichas:urgencias");
    expect(shared?.isOwner).toBe(false);
    expect(shared?.cells.create?.isShared).toBe(true);
    expect(shared?.cells.create?.sharedWith.map((ref) => ref.key)).toEqual(["recepcion.fichas"]);
  });

  it("sin override: gana el modulo con mayor solapamiento de tokens", () => {
    const withoutOverride = buildPermissionMatrix(
      [
        node({
          key: "x",
          items: [
            node({ key: "x.reportes.zeta", permissions: ["clinico:widgets:read"] }),
            node({ key: "x.widgets", permissions: ["clinico:widgets:read"] }),
          ],
        }),
      ],
      [perm("clinico:widgets:read")],
    );
    const owner = allRows(withoutOverride.groups).find((row) => row.isOwner);
    expect(owner?.module.key).toBe("x.widgets");
  });

  it("tie-breaks: mas codigos enlazados, menor profundidad y luego key", () => {
    const build = (items: ModuleCatalogNodeDTO[]) =>
      allRows(
        buildPermissionMatrix(
          [node({ key: "r", items })],
          [perm("q:cosa:read"), perm("q:cosa:create")],
        ).groups,
      ).find((row) => row.isOwner)?.module.key;

    // (2) mas codigos del recurso enlazados
    expect(
      build([
        node({ key: "r.b", permissions: ["q:cosa:read"] }),
        node({ key: "r.a", permissions: ["q:cosa:read", "q:cosa:create"] }),
      ]),
    ).toBe("r.a");
    // (3) menor profundidad
    expect(
      build([
        node({ key: "r.a", items: [node({ key: "r.a.z", permissions: ["q:cosa:read"] })] }),
        node({ key: "r.b", permissions: ["q:cosa:read"] }),
      ]),
    ).toBe("r.b");
    // (4) key asc
    expect(
      build([
        node({ key: "r.b", permissions: ["q:cosa:read"] }),
        node({ key: "r.a", permissions: ["q:cosa:read"] }),
      ]),
    ).toBe("r.a");
  });

  it("recursos sin modulo y codigos malformados van a orphans", () => {
    expect(matrix.orphans.map((cell) => cell.code)).toEqual([
      "clinico:notas:read",
      "flow.recepcion.queue.write",
    ]);
  });

  it("agrupa por raiz y conserva el orden del arbol", () => {
    expect(matrix.groups.map((group) => group.key)).toEqual([
      "clinico",
      "recepcion",
      "administracion",
    ]);
  });

  it("ningun codigo del catalogo se pierde (suma de celdas de duenos + orphans)", () => {
    const codes = new Set<string>();
    for (const row of rows.filter((r) => r.isOwner)) {
      for (const cell of Object.values(row.cells)) if (cell) codes.add(cell.code);
      for (const cell of row.other) codes.add(cell.code);
    }
    for (const cell of matrix.orphans) codes.add(cell.code);

    expect([...codes].sort()).toEqual(catalog.map((p) => p.code).sort());
  });

  it("ignora codigos del arbol que no existen en el catalogo", () => {
    const result = buildPermissionMatrix(
      [node({ key: "m", permissions: ["fantasma:cosa:read"] })],
      [],
    );
    expect(result.groups).toEqual([]);
    expect(result.orphans).toEqual([]);
  });
});
