export interface Action {
  nome: string;
  tipo: "permanente" | "variavel";
  categoria: string;
  grupo: string;
  N: number;
  Hx: number;
  Hy: number;
  Mx: number;
  My: number;
}
export interface Reading {
  profundidade_m: number;
  nspt_real: number;
  nspt_calculo?: number;
  solo: string;
  familia?: string;
  cor?: string | null;
  impenetravel: boolean;
}
export interface Borehole {
  cotaTopo_m: number;
  profundidadeFinal_m?: number;
  naInicial_m?: number | null;
  naFinal_m: number | null;
  leituras: Reading[];
  [key: string]: unknown;
}
// Numerical options mirror the supplied Python JSON contract; extra options survive round trips.
export interface Parameters {
  nome: string;
  descricao: string;
  quantidade: number;
  geometria: {
    D: number | null;
    L: number;
    cota_topo: number;
    cota_terreno: number;
    desprezar_topo: number;
    D_estrutura?: number;
    D_escavacao?: number;
    cota_base?: number;
  };
  camisa: {
    usar: boolean;
    DN: number | null;
    espessura: number | null;
    altura: number;
    estrutural: boolean;
  };
  folga: {
    largura: number;
    preenchimento: string;
    folga_min_compactacao: number;
  };
  lastro: { espessura: number; material: string };
  materiais: {
    fck: number;
    fyk: number;
    cobrimento: number;
    caa: string;
    gama_c: number;
    agregado: string;
  };
  apoio: {
    tipo: string;
    secao: string;
    a: number;
    b: number;
    d: number;
    h_aplicacao: number;
    embutimento: number;
    area_secao: number;
    ex: number;
    ey: number;
  };
  acoes: Action[];
  sondagem: {
    arquivo: string | null;
    sondagens: Record<string, Borehole> | null;
    furos: string[] | null;
    perfis: string[];
    submodo: string;
    janela: number;
    delta: number;
    na: number | null;
    na_criterio: string;
  };
  solo: {
    metodo_pu: string;
    metodo_phi: string;
    sigma_adm: number | null;
    fs_base: number;
    atrito_base_servico: boolean;
    atrito_base_ruptura: boolean;
    edicoes: Record<string, unknown>[];
  };
  criterios: Record<string, number | boolean | string | null>;
  dimensionamento: {
    automatico: boolean;
    D_lista: number[] | null;
    L_min: number;
    L_max: number;
    L_passo: number | null;
    escolha_usuario?: { D: number; L: number };
  };
  analise: { n_fatias: number; n_aneis_base: number; n_setores_base: number };
  [key: string]: unknown;
}
export interface Element {
  id: string;
  parameters: Parameters;
}
export interface Project {
  schema: "openstruct.tubstruct";
  version: 1;
  name: string;
  author: string;
  example: boolean;
  elements: Element[];
  selectedId: string;
}
export interface Check {
  grupo: string;
  nome: string;
  valor: number | string | null;
  limite: number | string | null;
  unidade: string;
  ok: boolean;
  ref: string;
  detalhe: string;
  combinacao: string;
  perfil: string;
  aproveitamento: number | string | null;
}
export interface Service {
  nome: string;
  theta: number;
  u_topo: number;
  u_aplicacao: number;
  p_max: number;
  p_min: number;
  w: number;
  area_comp: number;
  lam: number | string;
  ok: boolean;
}
export interface Rebar {
  n: number;
  bitola: number;
  raio: number;
  z_fim?: number;
  z1?: number;
  z2?: number;
  s?: number;
  As?: number;
  estribo?: Rebar;
}
export interface Result {
  ok: boolean;
  p: Parameters;
  tempo: number;
  verificacoes: Check[];
  alertas: [string, string][];
  governante: Check | null;
  quantitativos: {
    concreto_enchimento: number;
    escavacao: number;
    folga: number;
    lastro: number;
    aneis?: number;
    aneis_desc?: string;
    peso_total: number;
    volume_aneis?: number;
  };
  estrutura: {
    armadura?: Rebar | null;
    simples?: { ok: boolean; aproveitamento: number };
    [key: string]: unknown;
  };
  analises: {
    rotulo: string;
    sigma_adm: number;
    servico: Service[];
    rigidez: { Z: number; tipo?: string };
  }[];
  dimensionamento: {
    mapa: {
      D: number;
      L: number;
      DN: number | null;
      ok: boolean;
      aproveitamento: number | string;
      governante: string;
      volume: number;
    }[];
    escolha: { D: number; L: number } | null;
    otima?: { D: number; L: number } | null;
  } | null;
  combinacoes: Record<
    string,
    { nome: string; F: number[]; parcelas: [number, string][] }[]
  >;
  classificacao: { tipo: string; texto: string };
}
export interface SceneData {
  armadura: Rebar | null;
  fretagem: Rebar | null;
  estribos: Rebar | null;
  montagem: Rebar | null;
  grelha: {
    n_camadas: number;
    z1: number;
    s_camadas: number;
    bitola: number;
    grampos: { dir: string; bx: number; by: number; comp: number }[];
  } | null;
  na: number | null;
  perfis: {
    rotulo: string;
    camadas: {
      topo: number;
      base: number;
      familia: string;
      solo: string;
      nspt: number;
    }[];
    combs: {
      nome: string;
      theta: number;
      ux: number;
      uy: number;
      w: number;
      ang: number;
    }[];
  }[];
}
export interface Calculation {
  version: string;
  result: Result;
  scene: SceneData;
  report: string;
  drawings: Record<string, string>;
  summary: string;
}
export type View =
  | "modelo"
  | "elevacao"
  | "esforcos"
  | "sondagens"
  | "verificacoes"
  | "memoria"
  | "quantitativos"
  | "mapa";
export const fmt = (value: unknown, digits = 2): string =>
  typeof value === "number" && Number.isFinite(value)
    ? value.toLocaleString("pt-BR", {
        maximumFractionDigits: digits,
        minimumFractionDigits: digits,
      })
    : value === "inf"
      ? "∞"
      : value === "-inf"
        ? "−∞"
        : "—";
