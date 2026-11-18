import bundled from "../examples.json";
import defaults from "../defaults.json";
import type { Parameters, Project } from "./types";
export const examples = bundled as unknown as Record<
  "poste" | "pilar" | "armado",
  Parameters
>;
export const id = () => crypto.randomUUID();
export const clone = <T>(value: T): T => structuredClone(value);
export const KEY = "openstruct.tubstruct.project.v1";

export function blank(name = "T1"): Parameters {
  const p = clone(examples.poste);
  p.nome = name;
  p.descricao = "";
  p.quantidade = 1;
  p.geometria = {
    D: 1.2,
    L: 3,
    cota_topo: 0,
    cota_terreno: 0,
    desprezar_topo: 0,
  };
  p.camisa = {
    usar: false,
    DN: 1.2,
    espessura: 0.09,
    altura: 0.5,
    estrutural: false,
  };
  p.materiais = { ...p.materiais, cobrimento: 0.05, caa: "II" };
  p.apoio = {
    tipo: "pilar",
    secao: "retangular",
    a: 0.4,
    b: 0.4,
    d: 0.4,
    h_aplicacao: 0,
    embutimento: 0,
    area_secao: 0,
    ex: 0,
    ey: 0,
  };
  p.acoes = [];
  p.sondagem.sondagens = {};
  p.sondagem.arquivo = null;
  p.sondagem.furos = null;
  p.criterios.desloc_aplicacao_lim = null;
  return p;
}
export function createProject(example = false): Project {
  const element = {
    id: id(),
    parameters: example ? clone(examples.poste) : blank(),
  };
  return {
    schema: "openstruct.tubstruct",
    version: 1,
    name: example ? "Estudo de tubulões · exemplo" : "Novo projeto",
    author: "",
    example,
    elements: [element],
    selectedId: element.id,
  };
}
function merge(
  base: Record<string, unknown>,
  input: Record<string, unknown>,
): Record<string, unknown> {
  const output = { ...base };
  for (const [key, value] of Object.entries(input)) {
    if (["__proto__", "prototype", "constructor"].includes(key))
      throw new Error("Chave de arquivo inválida.");
    output[key] =
      value &&
      typeof value === "object" &&
      !Array.isArray(value) &&
      base[key] &&
      typeof base[key] === "object" &&
      !Array.isArray(base[key])
        ? merge(
            base[key] as Record<string, unknown>,
            value as Record<string, unknown>,
          )
        : value;
  }
  return output;
}
export function hydrateParameters(raw: unknown): Parameters {
  if (!raw || typeof raw !== "object" || Array.isArray(raw))
    throw new Error("Parâmetros de tubulão inválidos.");
  const p = merge(
    clone(defaults) as unknown as Record<string, unknown>,
    raw as Record<string, unknown>,
  ) as unknown as Parameters;
  if (
    p.geometria?.cota_terreno == null &&
    typeof p.geometria?.cota_topo === "number"
  )
    p.geometria.cota_terreno = p.geometria.cota_topo;
  if (p.sondagem && p.sondagem.sondagens == null) p.sondagem.sondagens = {};
  function checkTypes(template: unknown, value: unknown, path: string) {
    if (typeof value === "number" && !Number.isFinite(value))
      throw new Error(`${path}: número não finito.`);
    if (template === null || template === undefined) return;
    if (typeof template === "object" && !Array.isArray(template)) {
      if (!value || typeof value !== "object" || Array.isArray(value))
        throw new Error(`${path}: seção inválida.`);
      for (const [key, sample] of Object.entries(template))
        checkTypes(
          sample,
          (value as Record<string, unknown>)[key],
          `${path}.${key}`,
        );
    } else if (!Array.isArray(template) && typeof value !== typeof template)
      throw new Error(`${path}: tipo inválido.`);
  }
  checkTypes(defaults, p, "Tubulão");
  for (const [section, key] of [
    ["geometria", "D"],
    ["geometria", "cota_terreno"],
    ["camisa", "DN"],
    ["camisa", "espessura"],
    ["solo", "sigma_adm"],
    ["sondagem", "na"],
    ["criterios", "desloc_aplicacao_lim"],
    ["dimensionamento", "L_passo"],
  ]) {
    const value = (p[section] as Record<string, unknown>)[key];
    if (
      value !== null &&
      (typeof value !== "number" || !Number.isFinite(value))
    )
      throw new Error(`${section}.${key}: número inválido.`);
  }
  if (
    p.geometria.L <= 0 ||
    p.geometria.L > 30 ||
    (p.geometria.D !== null &&
      (typeof p.geometria.D !== "number" ||
        p.geometria.D <= 0 ||
        p.geometria.D > 10))
  )
    throw new Error("Dimensões fora dos limites de entrada.");
  for (const key of [
    "geometria",
    "camisa",
    "materiais",
    "apoio",
    "solo",
    "sondagem",
    "dimensionamento",
    "criterios",
    "folga",
    "lastro",
    "analise",
  ] as const) {
    if (!p[key] || typeof p[key] !== "object" || Array.isArray(p[key]))
      throw new Error(`Seção ${key} inválida.`);
  }
  if (
    typeof p.nome !== "string" ||
    !p.nome.trim() ||
    typeof p.descricao !== "string" ||
    !Array.isArray(p.acoes)
  )
    throw new Error("Identificação ou ações inválidas.");
  if (p.acoes.length > 12)
    throw new Error("O projeto admite até 12 ações por tubulão.");
  p.acoes = p.acoes.map((a) => {
    if (!a || typeof a !== "object") throw new Error("Ação inválida.");
    return {
      ...a,
      N: a.N ?? 0,
      Hx: a.Hx ?? 0,
      Hy: a.Hy ?? 0,
      Mx: a.Mx ?? 0,
      My: a.My ?? 0,
      categoria: a.categoria ?? "vento",
      grupo: a.grupo ?? a.nome,
    };
  });
  if (
    !Array.isArray(p.sondagem.perfis) ||
    (p.sondagem.sondagens !== null &&
      (typeof p.sondagem.sondagens !== "object" ||
        Array.isArray(p.sondagem.sondagens)))
  )
    throw new Error("Sondagens inválidas.");
  for (const f of Object.values(p.sondagem.sondagens || {})) {
    if (
      !f ||
      !Array.isArray(f.leituras) ||
      f.leituras.some((l) => !l || typeof l !== "object")
    )
      throw new Error("Leituras SPT inválidas.");
  }
  if (
    p.dimensionamento.D_lista !== null &&
    !Array.isArray(p.dimensionamento.D_lista)
  )
    throw new Error("Diâmetros candidatos inválidos.");
  return p;
}
export function parseProject(text: string): Project {
  if (new TextEncoder().encode(text).length > 2_000_000)
    throw new Error("Arquivo maior que 2 MB.");
  const raw = JSON.parse(text);
  if (!raw || typeof raw !== "object" || Array.isArray(raw))
    throw new Error("Arquivo de projeto inválido.");
  if (raw.schema === "openstruct.tubstruct") {
    if (raw.version !== 1) throw new Error("Versão de projeto não suportada.");
    if (
      !Array.isArray(raw.elements) ||
      !raw.elements.length ||
      raw.elements.length > 100
    )
      throw new Error("O projeto deve conter de 1 a 100 tubulões.");
    const elements = raw.elements.map(
      (e: { id: string; parameters: unknown }) => ({
        id: typeof e.id === "string" ? e.id : id(),
        parameters: hydrateParameters(e.parameters),
      }),
    );
    if (
      new Set(elements.map((e: { id: string }) => e.id)).size !==
      elements.length
    )
      throw new Error("Identificadores de tubulões repetidos.");
    return {
      schema: "openstruct.tubstruct",
      version: 1,
      name: typeof raw.name === "string" ? raw.name : "Projeto importado",
      author: typeof raw.author === "string" ? raw.author : "",
      example: !!raw.example,
      elements,
      selectedId: elements.some((e: { id: string }) => e.id === raw.selectedId)
        ? raw.selectedId
        : elements[0].id,
    };
  }
  if (raw.geometria && raw.acoes) {
    const e = { id: id(), parameters: hydrateParameters(raw) };
    return {
      schema: "openstruct.tubstruct",
      version: 1,
      name: raw.nome || "Projeto importado",
      author: "",
      example: false,
      elements: [e],
      selectedId: e.id,
    };
  }
  throw new Error(
    "Use um projeto .tubstruct.json ou um arquivo de parâmetros da base original.",
  );
}
export function restore(): { project: Project; warning: string } {
  try {
    const raw = localStorage.getItem(KEY);
    return {
      project: raw ? parseProject(raw) : createProject(true),
      warning: "",
    };
  } catch {
    return {
      project: createProject(true),
      warning:
        "A recuperação automática não pôde ser lida. O arquivo original permanece no armazenamento; abra uma cópia salva antes de continuar.",
    };
  }
}
