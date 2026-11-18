import { describe, it, expect } from "vitest";
import {
  blank,
  createProject,
  examples,
  parseProject,
} from "../src/domain/project";
import { csvCell } from "../src/domain/api";

describe("portabilidade e integridade do projeto", () => {
  it("preserva múltiplos tubulões e sondagens incorporadas", () => {
    const p = createProject(true);
    p.elements.push({
      id: "second",
      parameters: structuredClone(examples.armado),
    });
    expect(parseProject(JSON.stringify(p))).toEqual(p);
    expect(p.elements[1].parameters.sondagem.arquivo).toBeNull();
    expect(Object.keys(p.elements[1].parameters.sondagem.sondagens!)).toEqual([
      "SP-A",
      "SP-B",
    ]);
  });
  it("cria projeto vazio sem inventar cargas ou sondagens", () => {
    expect(blank().acoes).toEqual([]);
    expect(blank().sondagem.sondagens).toEqual({});
  });
  it("importa contrato legado sem inventar arquivo de sondagem", () => {
    const p = parseProject(
      JSON.stringify({
        nome: "T-antigo",
        geometria: { D: 1, L: 2 },
        camisa: { usar: false },
        acoes: [{ nome: "G", tipo: "permanente", N: 10 }],
        sondagem: { arquivo: "SP01.json" },
      }),
    );
    expect(p.elements[0].parameters.acoes[0].Hx).toBe(0);
    expect(p.elements[0].parameters.sondagem.sondagens).toEqual({});
    expect(p.elements[0].parameters.sondagem.arquivo).toBe("SP01.json");
  });
  it("rejeita versão desconhecida e ids duplicados", () => {
    const p = createProject();
    expect(() => parseProject(JSON.stringify({ ...p, version: 2 }))).toThrow(
      "Versão",
    );
    expect(() =>
      parseProject(
        JSON.stringify({ ...p, elements: [...p.elements, ...p.elements] }),
      ),
    ).toThrow("repetidos");
  });
  it("rejeita arquivos corrompidos antes de renderizar a geometria", () => {
    for (const text of [
      "null",
      "[]",
      '{"schema":"outro"}',
      JSON.stringify({ ...blank(), geometria: null }),
      JSON.stringify({
        ...blank(),
        geometria: { ...blank().geometria, L: "3" },
      }),
    ])
      expect(() => parseProject(text)).toThrow();
  });
  it("neutraliza células interpretadas como fórmulas no CSV", () => {
    expect(csvCell('=HYPERLINK("x")')).toBe('"\'=HYPERLINK(""x"")"');
    expect(csvCell("Escavação")).toBe('"Escavação"');
  });
});
