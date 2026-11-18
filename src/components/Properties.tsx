import { SlidersHorizontal } from "lucide-react";
import { Field, TextField, Select, Toggle, Section } from "./Fields";
import type { Parameters } from "../domain/types";
import { clone } from "../domain/project";

export function Properties({
  p,
  onChange,
  onAdvanced,
}: {
  p: Parameters;
  onChange: (p: Parameters) => void;
  onAdvanced: () => void;
}) {
  const set = (section: string, key: string, value: unknown) => {
    const next = clone(p);
    (next[section] as Record<string, unknown>)[key] = value;
    onChange(next);
  };
  const num = (
    section: string,
    key: string,
    label: string,
    unit?: string,
    min?: number,
    nullable = false,
  ) => (
    <Field
      key={key}
      label={label}
      unit={unit}
      min={min}
      nullable={nullable}
      value={(p[section] as Record<string, number | null>)[key]}
      onChange={(v) => set(section, key, v)}
    />
  );
  return (
    <aside className="properties">
      <div className="panel-heading">
        <SlidersHorizontal size={15} />
        <b>Propriedades</b>
        <span>{p.nome}</span>
      </div>
      <div className="properties-scroll">
        <Section title="Identificação">
          <TextField
            label="Identificador"
            value={p.nome}
            onChange={(v) => onChange({ ...p, nome: v })}
          />
          <Field
            label="Quantidade"
            value={p.quantidade}
            min={1}
            onChange={(v) => onChange({ ...p, quantidade: v || 1 })}
          />
          <TextField
            label="Descrição"
            value={p.descricao}
            max={4000}
            onChange={(v) => onChange({ ...p, descricao: v })}
          />
        </Section>
        <Section title="Geometria do tubulão">
          <Toggle
            label="Camisa de anéis pré-moldados"
            checked={p.camisa.usar}
            onChange={(v) => {
              const next = clone(p);
              next.camisa.usar = v;
              next.camisa.DN ||= 1.2;
              next.camisa.espessura ||= 0.09;
              next.geometria.D ||= 1.2;
              onChange(next);
            }}
          />
          {p.camisa.usar ? (
            <>
              {num("camisa", "DN", "Diâmetro interno DN", "m", 0.3)}
              {num("camisa", "espessura", "Parede do anel", "m", 0.01)}
              {num("camisa", "altura", "Altura do anel", "m", 0.1)}
              <Toggle
                label="Considerar camisa estrutural"
                checked={p.camisa.estrutural}
                onChange={(v) => set("camisa", "estrutural", v)}
              />
            </>
          ) : (
            num("geometria", "D", "Diâmetro D", "m", 0.3)
          )}
          {num("geometria", "L", "Comprimento L", "m", 0.2)}
          {num("geometria", "cota_topo", "Cota do topo", "m")}
          {num("geometria", "cota_terreno", "Cota do terreno", "m")}
          {num(
            "geometria",
            "desprezar_topo",
            "Desprezar reação no topo",
            "m",
            0,
          )}
          {num("lastro", "espessura", "Lastro de concreto magro", "m", 0)}
          {p.camisa.usar && (
            <>
              {num("folga", "largura", "Folga de escavação", "m", 0)}
              <Select
                label="Preenchimento da folga"
                value={p.folga.preenchimento}
                onChange={(v) => set("folga", "preenchimento", v)}
                options={[
                  ["autoadensavel", "Concreto autoadensável"],
                  ["solo_cimento_compactado", "Solo-cimento compactado"],
                  ["nenhuma", "Sem preenchimento"],
                ]}
              />
            </>
          )}
        </Section>
        <Section title="Materiais">
          <div className="field-pair">
            {num("materiais", "fck", "fck", "MPa", 20)}
            {num("materiais", "fyk", "fyk", "MPa", 250)}
          </div>
          {num("materiais", "cobrimento", "Cobrimento nominal", "m", 0.02)}
          <Select
            label="Classe de agressividade"
            value={p.materiais.caa}
            onChange={(v) => set("materiais", "caa", v)}
            options={["I", "II", "III", "IV"].map((v) => [v, `CAA ${v}`])}
          />
          {num(
            "materiais",
            "gama_c",
            "Peso específico do concreto",
            "kN/m³",
            15,
          )}
        </Section>
        <Section title="Apoio e aplicação das ações" open={false}>
          <Select
            label="Tipo de apoio"
            value={p.apoio.tipo}
            onChange={(v) => set("apoio", "tipo", v)}
            options={[
              ["nenhum", "Sem apoio definido"],
              ["pilar", "Pilar"],
              ["poste", "Poste"],
            ]}
          />
          {p.apoio.tipo === "pilar" && (
            <>
              <Select
                label="Seção do pilar"
                value={p.apoio.secao}
                onChange={(v) => set("apoio", "secao", v)}
                options={[
                  ["retangular", "Retangular"],
                  ["circular", "Circular"],
                ]}
              />
              {p.apoio.secao === "circular" ? (
                num("apoio", "d", "Diâmetro do pilar", "m", 0.05)
              ) : (
                <div className="field-pair">
                  {num("apoio", "a", "Lado a", "m", 0.05)}
                  {num("apoio", "b", "Lado b", "m", 0.05)}
                </div>
              )}
              <div className="field-pair">
                {num("apoio", "ex", "Excentricidade x", "m")}
                {num("apoio", "ey", "Excentricidade y", "m")}
              </div>
            </>
          )}
          {p.apoio.tipo === "poste" && (
            <>
              {num("apoio", "embutimento", "Embutimento do poste", "m", 0)}
              {num("apoio", "area_secao", "Área da seção do poste", "m²", 0)}
            </>
          )}
          {num("apoio", "h_aplicacao", "Altura do ponto de aplicação", "m", 0)}
          <p className="hint">
            Altura usada no limite de deslocamento. Informe forças e momentos já
            transportados ao topo do tubulão.
          </p>
        </Section>
        <Section title="Solo e resistência lateral" open={false}>
          <Select
            label="Modelo de resistência lateral"
            value={p.solo.metodo_pu}
            onChange={(v) => set("solo", "metodo_pu", v)}
            options={[
              ["brinch_hansen", "Brinch Hansen"],
              ["broms", "Broms"],
              ["rankine", "Rankine"],
            ]}
          />
          <Select
            label="Correlação de φ"
            value={p.solo.metodo_phi}
            onChange={(v) => set("solo", "metodo_phi", v)}
            options={[
              ["teixeira", "Teixeira"],
              ["godoy", "Godoy"],
            ]}
          />
          {num(
            "solo",
            "sigma_adm",
            "Tensão admissível (opcional)",
            "kPa",
            1,
            true,
          )}
          {num("solo", "fs_base", "FS da capacidade de base", "", 1)}
          <Toggle
            label="Atrito na base em serviço"
            checked={p.solo.atrito_base_servico}
            onChange={(v) => set("solo", "atrito_base_servico", v)}
          />
          <Toggle
            label="Atrito na base na ruptura"
            checked={p.solo.atrito_base_ruptura}
            onChange={(v) => set("solo", "atrito_base_ruptura", v)}
          />
        </Section>
        <Section title="Critérios de verificação" open={false}>
          <Select
            label="Verificação de tombamento"
            value={String(p.criterios.tombamento)}
            onChange={(v) => set("criterios", "tombamento", v)}
            options={[
              ["calculo", "Valores de cálculo"],
              ["global", "Fator global"],
            ]}
          />
          {num("criterios", "fs_tombamento", "FS global mínimo", "", 1)}
          {num(
            "criterios",
            "rotacao_lim",
            "Rotação limite (pilar)",
            "rad",
            0.00001,
          )}
          {num(
            "criterios",
            "rotacao_lim_poste",
            "Rotação limite (poste)",
            "rad",
            0.00001,
          )}
          {num("criterios", "recalque_lim", "Recalque limite", "m", 0.0001)}
          {num(
            "criterios",
            "desloc_aplicacao_lim",
            "Deslocamento na aplicação",
            "m",
            0.0001,
            true,
          )}
          <Toggle
            label="Permitir fuste em concreto simples"
            checked={!!p.criterios.concreto_simples}
            onChange={(v) => set("criterios", "concreto_simples", v)}
          />
        </Section>
        <Section
          title="Dimensionamento automático"
          open={p.dimensionamento.automatico}
        >
          <Toggle
            label="Buscar diâmetro e comprimento"
            checked={p.dimensionamento.automatico}
            onChange={(v) => set("dimensionamento", "automatico", v)}
          />
          <p className="hint">
            A solução de menor volume aprovada é reavaliada pelo modelo
            completo.
          </p>
          <div className="field-pair">
            {num("dimensionamento", "L_min", "L mínimo", "m", 0.2)}
            {num("dimensionamento", "L_max", "L máximo", "m", 0.2)}
          </div>
          {num("dimensionamento", "L_passo", "Passo de L", "m", 0.05, true)}
          <p className="hint">
            Diâmetros:{" "}
            {p.dimensionamento.D_lista?.join(" · ") ||
              (p.camisa.usar ? "Catálogo de anéis" : "0,60 a 2,00 m")}
            . Edite a lista em Parâmetros completos.
          </p>
        </Section>
        <button className="secondary full" onClick={onAdvanced}>
          Parâmetros completos (JSON)
        </button>
      </div>
    </aside>
  );
}
