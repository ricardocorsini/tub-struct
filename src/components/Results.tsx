import { useMemo, useState } from "react";
import {
  CheckCircle2,
  AlertCircle,
  FileText,
  Download,
  Search,
  Printer,
  ArrowRight,
} from "lucide-react";
import { fmt, type Calculation, type View } from "../domain/types";
import { csvCell, desktop, safeName, saveText } from "../domain/api";

export function Checks({
  calculation: { result: r },
}: {
  calculation: Calculation;
}) {
  const [query, setQuery] = useState(""),
    [failedOnly, setFailedOnly] = useState(false);
  const [group, setGroup] = useState("");
  const filtered = useMemo(
    () =>
      r.verificacoes.filter(
        (c) =>
          (!failedOnly || !c.ok) &&
          (!group || c.grupo === group) &&
          `${c.nome} ${c.perfil} ${c.combinacao}`
            .toLowerCase()
            .includes(query.toLowerCase()),
      ),
    [r, query, failedOnly, group],
  );
  return (
    <div className="result-page">
      <div className="section-title">
        <div>
          <span className="eyebrow">RASTREABILIDADE DO CÁLCULO</span>
          <h2>Verificações</h2>
        </div>
        <span className={`pill ${r.ok ? "success" : "failed"}`}>
          {r.verificacoes.filter((c) => c.ok).length} / {r.verificacoes.length}{" "}
          atendidas
        </span>
      </div>
      <div className="result-filters">
        <label className="search">
          <Search size={15} />
          <input
            placeholder="Buscar verificação, perfil ou combinação…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        <select
          aria-label="Grupo de verificação"
          value={group}
          onChange={(e) => setGroup(e.target.value)}
        >
          <option value="">Todos os grupos</option>
          {[...new Set(r.verificacoes.map((c) => c.grupo))].map((g) => (
            <option key={g}>{g}</option>
          ))}
        </select>
        <label className="toggle">
          <input
            type="checkbox"
            checked={failedOnly}
            onChange={(e) => setFailedOnly(e.target.checked)}
          />
          Somente não atendidas
        </label>
      </div>
      <div className="table-scroll">
        <table className="checks">
          <thead>
            <tr>
              <th>Status</th>
              <th>Verificação / combinação</th>
              <th>Valor</th>
              <th>Limite</th>
              <th>Referência</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((c, i) => (
              <tr key={i}>
                <td>
                  <span className={`check-status ${c.ok ? "good" : "bad"}`}>
                    {c.ok ? (
                      <CheckCircle2 size={15} />
                    ) : (
                      <AlertCircle size={15} />
                    )}
                    <span>{c.ok ? "Atende" : "Não atende"}</span>
                  </span>
                </td>
                <td>
                  <b>{c.nome}</b>
                  <small>
                    {c.grupo} · {c.perfil}
                  </small>
                  <small>{c.combinacao}</small>
                  {c.detalhe && <small>{c.detalhe}</small>}
                </td>
                <td className="numeric">
                  {fmt(
                    c.valor,
                    typeof c.valor === "number" && Math.abs(c.valor) < 0.1
                      ? 5
                      : 2,
                  )}
                  <small>{c.unidade}</small>
                </td>
                <td className="numeric">
                  {fmt(
                    c.limite,
                    typeof c.limite === "number" && Math.abs(c.limite) < 0.1
                      ? 5
                      : 2,
                  )}
                  <small>{c.unidade}</small>
                </td>
                <td className="ref-cell">{c.ref}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!filtered.length && (
        <div className="empty compact">
          Nenhuma verificação corresponde aos filtros.
        </div>
      )}
    </div>
  );
}
export function Summary({
  calculation,
  onChecks,
}: {
  calculation?: Calculation;
  onChecks: () => void;
}) {
  if (!calculation)
    return (
      <div className="summary awaiting">
        <div className="awaiting-icon">
          <FileText size={24} />
        </div>
        <div>
          <b>Pronto para analisar o tubulão</b>
          <p>
            Confira os dados, cadastre as ações e sondagens e clique em
            Calcular.
          </p>
        </div>
        <span>Resultados atualizados a cada cálculo</span>
      </div>
    );
  const r = calculation.result,
    services = r.analises.flatMap((a) => a.servico);
  const max = (key: "u_topo" | "p_max" | "theta") =>
    Math.max(0, ...services.map((s) => s[key]));
  return (
    <div className="summary">
      <button
        className={`summary-status ${r.ok ? "good" : "bad"}`}
        onClick={onChecks}
      >
        {r.ok ? <CheckCircle2 size={23} /> : <AlertCircle size={23} />}
        <div>
          <b>{r.ok ? "Verificações atendidas" : "Revisão necessária"}</b>
          <small>
            {r.verificacoes.filter((c) => c.ok).length} de{" "}
            {r.verificacoes.length} verificações atendidas
          </small>
        </div>
        <ArrowRight size={16} />
      </button>
      <div className="metric">
        <small>Aproveitamento governante</small>
        <b>{fmt(r.governante?.aproveitamento, 2)}</b>
        <span title={r.governante?.nome}>{r.governante?.grupo || "—"}</span>
      </div>
      <div className="metric">
        <small>Pressão máxima na base</small>
        <b>
          {fmt(max("p_max"), 1)} <em>kPa</em>
        </b>
        <span>Envoltória de serviço</span>
      </div>
      <div className="metric">
        <small>Deslocamento no topo</small>
        <b>
          {fmt(max("u_topo") * 1000, 2)} <em>mm</em>
        </b>
        <span>Máximo entre perfis</span>
      </div>
    </div>
  );
}
export function QuantityView({ calculation }: { calculation: Calculation }) {
  const r = calculation.result,
    q = r.quantitativos;
  const rows: [string, number, string][] = [
    ["Concreto de enchimento", q.concreto_enchimento, "m³"],
    ["Escavação", q.escavacao, "m³"],
    ["Preenchimento da folga", q.folga, "m³"],
    ["Lastro", q.lastro, "m³"],
  ];
  if (q.aneis != null) rows.push(["Anéis pré-moldados", q.aneis, "un."]);
  const [message, setMessage] = useState("");
  return (
    <div className="result-page">
      <div className="section-title">
        <div>
          <span className="eyebrow">MATERIAIS DA SOLUÇÃO</span>
          <h2>Quantitativos</h2>
        </div>
        <button
          className="secondary"
          onClick={async () => {
            try {
              const csv = [
                ["Item", "Por unidade", "Quantidade", "Total", "Unidade"],
                ...rows.map(([label, value, unit]) => [
                  label,
                  value,
                  r.p.quantidade,
                  value * r.p.quantidade,
                  unit,
                ]),
              ]
                .map((row) => row.map(csvCell).join(";"))
                .join("\r\n");
              if (
                await saveText(
                  `${safeName(r.p.nome)}_quantitativos.csv`,
                  "\ufeff" + csv,
                  "text/csv;charset=utf-8",
                )
              )
                setMessage("CSV exportado.");
            } catch (e) {
              setMessage((e as Error).message);
            }
          }}
        >
          <Download size={15} />
          Exportar CSV
        </button>
      </div>
      <p>
        {r.p.nome} · {r.p.quantidade} unidades · D = {fmt(r.p.geometria.D)} m ·
        L = {fmt(r.p.geometria.L)} m
      </p>
      <table>
        <thead>
          <tr>
            <th>Material / serviço</th>
            <th>Por tubulão</th>
            <th>Total ({r.p.quantidade}×)</th>
            <th>Unidade</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([label, value, unit]) => (
            <tr key={label}>
              <td>{label}</td>
              <td>{fmt(value, unit === "un." ? 0 : 3)}</td>
              <td>{fmt(value * r.p.quantidade, unit === "un." ? 0 : 3)}</td>
              <td>{unit}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {q.aneis_desc && <p className="hint">{q.aneis_desc}</p>}
      <div className="info-card">
        <b>Armadura longitudinal</b>
        <p>
          {r.estrutura.armadura
            ? `${r.estrutura.armadura.n} barras Ø ${fmt(r.estrutura.armadura.bitola, 1)} mm · As = ${fmt((r.estrutura.armadura.As || 0) * 10000)} cm²`
            : "Fuste sem armadura longitudinal dimensionada."}
        </p>
        <p className="hint">
          Fretagem, montagem, estribos, comprimentos e hipóteses constam na
          memória de cálculo. A exportação com ferros inteligentes permanece
          disponível na integração TQS da base.
        </p>
      </div>
      {message && <p role="status">{message}</p>}
    </div>
  );
}
export function OutputView({
  calculation,
  view,
  adopt,
}: {
  calculation: Calculation;
  view: View;
  adopt: () => void;
}) {
  const [message, setMessage] = useState("");
  const r = calculation.result;
  if (view === "verificacoes") return <Checks calculation={calculation} />;
  if (view === "quantitativos")
    return <QuantityView calculation={calculation} />;
  if (view === "mapa")
    return (
      <div className="result-page">
        <div className="section-title">
          <div>
            <span className="eyebrow">VARREDURA DE SOLUÇÕES</span>
            <h2>Diâmetro × comprimento</h2>
          </div>
          {r.dimensionamento?.escolha && (
            <button className="primary" onClick={adopt}>
              Adotar geometria calculada
            </button>
          )}
        </div>
        {!r.dimensionamento ? (
          <div className="empty compact">
            Ative o dimensionamento automático nas propriedades e recalcule.
          </div>
        ) : (
          <>
            <p>
              {r.dimensionamento.mapa.filter((m) => m.ok).length} de{" "}
              {r.dimensionamento.mapa.length} candidatos passaram na triagem. A
              solução selecionada foi verificada pelo modelo completo.
            </p>
            {!r.dimensionamento.escolha && (
              <p className="error-banner">
                Nenhum candidato foi aprovado na varredura. Os resultados
                exibidos correspondem à geometria de entrada.
              </p>
            )}
            <table>
              <thead>
                <tr>
                  <th>D (m)</th>
                  <th>L (m)</th>
                  <th>Triagem</th>
                  <th>Volume (m³)</th>
                  <th>Governante da triagem</th>
                </tr>
              </thead>
              <tbody>
                {r.dimensionamento.mapa.map((m, i) => (
                  <tr
                    key={i}
                    className={
                      m.D === r.p.geometria.D && m.L === r.p.geometria.L
                        ? "selected-row"
                        : ""
                    }
                  >
                    <td>{fmt(m.D)}</td>
                    <td>{fmt(m.L)}</td>
                    <td className={m.ok ? "good" : "bad"}>
                      {m.ok ? "Atende" : "Não atende"}
                    </td>
                    <td>{fmt(m.volume)}</td>
                    <td>{m.governante}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </div>
    );
  const isReport = view === "memoria";
  const titles: Record<string, string> = {
    memoria: "Memória de cálculo",
    elevacao: "Corte do tubulão",
    esforcos: "Diagramas de esforços",
    sondagens: "Perfis de sondagem",
  };
  const html = isReport
    ? calculation.report
    : `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><style>body{font-family:system-ui;color:#29354c;margin:24px}svg{max-width:100%;height:auto}h3{font-size:15px}table{border-collapse:collapse}td,th{padding:5px;border:1px solid #dfe4ec}</style></head><body>${calculation.drawings[view] || ""}</body></html>`;
  return (
    <div className="document-view">
      <div className="document-toolbar">
        <b>{titles[view]}</b>
        <button
          className="secondary"
          onClick={async () => {
            try {
              if (
                await saveText(
                  `${safeName(r.p.nome)}_${view}.html`,
                  html,
                  "text/html",
                )
              )
                setMessage("Documento exportado.");
            } catch (e) {
              setMessage((e as Error).message);
            }
          }}
        >
          <Download size={15} />
          Salvar HTML
        </button>
        {isReport && !desktop() && (
          <button
            className="secondary"
            onClick={() => {
              const popup = window.open("", "_blank");
              if (!popup) {
                setMessage(
                  "Permita a abertura da memória para imprimir ou salve o HTML.",
                );
                return;
              }
              popup.document.write(html);
              popup.document.close();
              popup.focus();
              popup.print();
            }}
          >
            <Printer size={15} />
            Imprimir / PDF
          </button>
        )}
        {message && <small role="status">{message}</small>}
      </div>
      <iframe title={titles[view]} sandbox="" srcDoc={html} />
    </div>
  );
}
