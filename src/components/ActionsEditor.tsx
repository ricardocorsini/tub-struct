import { Plus, Trash2 } from "lucide-react";
import { Field } from "./Fields";
import { Modal } from "./Modal";
import type { Action, Parameters } from "../domain/types";

export function ActionsEditor({
  p,
  onChange,
  onClose,
}: {
  p: Parameters;
  onChange: (p: Parameters) => void;
  onClose: () => void;
}) {
  const update = (index: number, key: keyof Action, value: unknown) =>
    onChange({
      ...p,
      acoes: p.acoes.map((a, i) => {
        if (i !== index) return a;
        const next = { ...a, [key]: value };
        if (key === "tipo" && value === "variavel" && !next.categoria) {
          next.categoria = "vento";
        }
        return next;
      }),
    });
  return (
    <Modal title="Ações características no topo" onClose={onClose} wide>
      <p className="intro">
        Informe cargas em <b>kN</b> e momentos em <b>kN·m</b>. N positivo
        comprime a base. Hx e My positivos tombam no mesmo sentido; Hy e Mx
        negativos tombam no mesmo sentido.
      </p>
      <p className="hint">
        Ações variáveis com o mesmo grupo são alternativas exclusivas. Os
        momentos devem incluir o transporte das forças até o topo; a altura de
        aplicação não acrescenta H × h automaticamente.
      </p>
      <div className="table-scroll">
        <table className="actions-table">
          <thead>
            <tr>
              <th>Ação</th>
              <th>Tipo / categoria</th>
              <th>Grupo</th>
              {["N", "Hx", "Hy", "Mx", "My"].map((k) => (
                <th key={k}>{k}</th>
              ))}
              <th />
            </tr>
          </thead>
          <tbody>
            {p.acoes.map((a, i) => (
              <tr key={i}>
                <td>
                  <input
                    aria-label={`Nome da ação ${i + 1}`}
                    value={a.nome}
                    maxLength={120}
                    onChange={(e) => update(i, "nome", e.target.value)}
                  />
                </td>
                <td>
                  <select
                    aria-label={`Tipo da ação ${i + 1}`}
                    value={a.tipo}
                    onChange={(e) => update(i, "tipo", e.target.value)}
                  >
                    <option value="permanente">Permanente</option>
                    <option value="variavel">Variável</option>
                  </select>
                  {a.tipo === "variavel" && (
                    <select
                      aria-label={`Categoria da ação ${i + 1}`}
                      value={a.categoria}
                      onChange={(e) => update(i, "categoria", e.target.value)}
                    >
                      {[
                        ["vento", "Vento"],
                        ["edificacao", "Edificação"],
                        ["edificacao_predominancia", "Grande concentração"],
                        ["biblioteca_garagem", "Biblioteca / garagem"],
                        ["temperatura", "Temperatura"],
                        ["equipamento", "Equipamento"],
                      ].map(([v, t]) => (
                        <option key={v} value={v}>
                          {t}
                        </option>
                      ))}
                    </select>
                  )}
                </td>
                <td>
                  <input
                    aria-label={`Grupo da ação ${i + 1}`}
                    value={a.grupo || ""}
                    onChange={(e) => update(i, "grupo", e.target.value)}
                  />
                </td>
                {(["N", "Hx", "Hy", "Mx", "My"] as const).map((key) => (
                  <td key={key}>
                    <Field
                      label={`${key} · ação ${i + 1}`}
                      value={a[key]}
                      onChange={(v) => update(i, key, v || 0)}
                    />
                  </td>
                ))}
                <td>
                  <button
                    aria-label={`Remover ação ${i + 1}`}
                    className="danger-text"
                    onClick={() =>
                      onChange({
                        ...p,
                        acoes: p.acoes.filter((_, j) => j !== i),
                      })
                    }
                  >
                    <Trash2 size={16} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!p.acoes.length && (
        <div className="empty compact">
          Cadastre as ações permanentes e variáveis deste tubulão.
        </div>
      )}
      <div className="modal-footer">
        <button
          className="secondary"
          disabled={p.acoes.length >= 12}
          onClick={() => {
            let n = 1;
            while (p.acoes.some((a) => a.nome === `Ação ${n}`)) n++;
            onChange({
              ...p,
              acoes: [
                ...p.acoes,
                {
                  nome: `Ação ${n}`,
                  tipo: "permanente",
                  categoria: "vento",
                  grupo: `Ação ${n}`,
                  N: 0,
                  Hx: 0,
                  Hy: 0,
                  Mx: 0,
                  My: 0,
                },
              ],
            });
          }}
        >
          <Plus size={16} />
          Adicionar ação
        </button>
        <button className="primary" onClick={onClose}>
          Concluir edição
        </button>
      </div>
    </Modal>
  );
}
