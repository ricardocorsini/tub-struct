import { useRef, useState } from "react";
import { FileUp, Plus, Trash2 } from "lucide-react";
import { Field, Select, Toggle } from "./Fields";
import { Modal } from "./Modal";
import { request } from "../domain/api";
import { clone } from "../domain/project";
import type { Borehole, Parameters, Reading } from "../domain/types";

const soils = [
  "Areia",
  "Areia Siltosa",
  "Areia Silto-Argilosa",
  "Areia Argilo-Siltosa",
  "Areia Argilosa",
  "Silte Arenoso",
  "Silte Areno-Argiloso",
  "Silte",
  "Silte Argilo-Arenoso",
  "Silte Argiloso",
  "Argila Arenosa",
  "Argila Areno-Siltosa",
  "Argila Silto-Arenosa",
  "Argila Siltosa",
  "Argila",
];
export function SoilEditor({
  p,
  onChange,
  onClose,
}: {
  p: Parameters;
  onChange: (p: Parameters) => void;
  onClose: () => void;
}) {
  const [selected, setSelected] = useState(
    Object.keys(p.sondagem.sondagens || {})[0] || "",
  );
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const file = useRef<HTMLInputElement>(null);
  const holes = p.sondagem.sondagens || {},
    names = Object.keys(holes),
    name = holes[selected] ? selected : names[0],
    hole = holes[name];
  const updateHole = (next: Borehole) =>
    onChange({
      ...p,
      sondagem: {
        ...p.sondagem,
        arquivo: null,
        sondagens: { ...holes, [name]: next },
      },
    });
  const read = (index: number, key: keyof Reading, value: unknown) => {
    const next = clone(hole);
    next.leituras[index] = { ...next.leituras[index], [key]: value };
    if (key === "solo") delete next.leituras[index].familia;
    delete next.leituras[index].nspt_calculo;
    next.profundidadeFinal_m = Math.max(
      0,
      ...next.leituras.map((l) => l.profundidade_m),
    );
    updateHole(next);
  };
  const set = (key: string, value: unknown) =>
    onChange({ ...p, sondagem: { ...p.sondagem, [key]: value } });
  return (
    <Modal title="Sondagens e perfis de cálculo" wide onClose={onClose}>
      <p className="intro">
        Cadastre os furos ou importe um arquivo <b>GEOSPT obra 2.x</b> /{" "}
        <b>detalhamento 1.x</b>. As leituras ficam incorporadas ao projeto.
      </p>
      <input
        ref={file}
        type="file"
        accept=".json"
        hidden
        onChange={async (e) => {
          const f = e.target.files?.[0];
          e.target.value = "";
          if (!f) return;
          setBusy(true);
          setError("");
          try {
            if (f.size > 2_000_000) throw new Error("Arquivo maior que 2 MB.");
            const data = await request<Record<string, Borehole>>({
              action: "sondagem",
              data: JSON.parse(await f.text()),
            });
            onChange({
              ...p,
              sondagem: {
                ...p.sondagem,
                sondagens: data,
                arquivo: null,
                furos: null,
                perfis: ["media", "envoltoria"],
              },
            });
            setSelected(Object.keys(data)[0]);
          } catch (err) {
            setError((err as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      />
      {error && (
        <p role="alert" className="error-banner">
          {error}
        </p>
      )}
      <div className="soil-toolbar">
        <button
          className="secondary"
          disabled={busy}
          onClick={() => file.current?.click()}
        >
          <FileUp size={16} />
          {busy ? "Importando…" : "Importar GEOSPT (substitui furos)"}
        </button>
        <button
          className="secondary"
          onClick={() => {
            let n = 1;
            while (holes[`SP-${n}`]) n++;
            const key = `SP-${n}`;
            onChange({
              ...p,
              sondagem: {
                ...p.sondagem,
                sondagens: {
                  ...holes,
                  [key]: {
                    cotaTopo_m: p.geometria.cota_terreno,
                    naFinal_m: null,
                    leituras: [],
                  },
                },
              },
            });
            setSelected(key);
          }}
        >
          <Plus size={16} />
          Novo furo
        </button>
        <span>{names.length} furos no projeto</span>
      </div>
      <div className="soil-layout">
        <aside className="bore-list">
          {names.map((n) => (
            <button
              key={n}
              className={n === name ? "active" : ""}
              onClick={() => setSelected(n)}
            >
              <b>{n}</b>
              <span>{holes[n].leituras.length} leituras</span>
            </button>
          ))}
          <div className="soil-profiles">
            <b>Perfis considerados</b>
            {[
              ["media", "Sondagem média"],
              ["envoltoria", "Envoltória mínima"],
              ...names.map((n) => [`furo:${n}`, n]),
            ].map(([key, label]) => (
              <Toggle
                key={key}
                label={label}
                checked={p.sondagem.perfis.includes(key)}
                onChange={(v) =>
                  set(
                    "perfis",
                    v
                      ? [...p.sondagem.perfis, key]
                      : p.sondagem.perfis.filter((x) => x !== key),
                  )
                }
              />
            ))}
          </div>
        </aside>
        <div>
          {hole ? (
            <>
              <div className="bore-meta">
                <Field
                  label="Cota da boca"
                  unit="m"
                  value={hole.cotaTopo_m}
                  onChange={(v) => updateHole({ ...hole, cotaTopo_m: v || 0 })}
                />
                <Field
                  label="Nível d'água final (prof.)"
                  unit="m"
                  min={0}
                  nullable
                  value={hole.naFinal_m}
                  onChange={(v) =>
                    updateHole({ ...hole, naFinal_m: v, naInicial_m: v })
                  }
                />
                <button
                  className="danger-text"
                  title="Remover furo"
                  onClick={() => {
                    const next = { ...holes };
                    delete next[name];
                    onChange({
                      ...p,
                      sondagem: {
                        ...p.sondagem,
                        sondagens: next,
                        furos: null,
                        perfis: p.sondagem.perfis.filter(
                          (x) => x !== `furo:${name}`,
                        ),
                      },
                    });
                  }}
                >
                  <Trash2 size={16} />
                  Remover furo
                </button>
              </div>
              <div className="table-scroll soil-readings">
                <table>
                  <thead>
                    <tr>
                      <th>Profundidade (m)</th>
                      <th>NSPT</th>
                      <th>Solo</th>
                      <th>Impenetrável</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {hole.leituras.map((l, i) => (
                      <tr key={i}>
                        <td>
                          <Field
                            label={`Profundidade ${i + 1}`}
                            value={l.profundidade_m}
                            min={0.1}
                            onChange={(v) => read(i, "profundidade_m", v || 1)}
                          />
                        </td>
                        <td>
                          <Field
                            label={`NSPT ${i + 1}`}
                            value={l.nspt_real}
                            min={0}
                            onChange={(v) => read(i, "nspt_real", v || 0)}
                          />
                        </td>
                        <td>
                          <select
                            aria-label={`Solo da leitura ${i + 1}`}
                            value={l.solo}
                            onChange={(e) => read(i, "solo", e.target.value)}
                          >
                            {[...new Set([...soils, l.solo])].map((s) => (
                              <option key={s}>{s}</option>
                            ))}
                          </select>
                        </td>
                        <td>
                          <input
                            aria-label={`Impenetrável ${i + 1}`}
                            type="checkbox"
                            checked={l.impenetravel}
                            onChange={(e) =>
                              read(i, "impenetravel", e.target.checked)
                            }
                          />
                        </td>
                        <td>
                          <button
                            aria-label={`Remover leitura ${i + 1}`}
                            onClick={() => {
                              const leituras = hole.leituras.filter(
                                (_, j) => j !== i,
                              );
                              updateHole({
                                ...hole,
                                leituras,
                                profundidadeFinal_m: Math.max(
                                  0,
                                  ...leituras.map((l) => l.profundidade_m),
                                ),
                              });
                            }}
                          >
                            <Trash2 size={14} />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <button
                className="secondary"
                onClick={() => {
                  const depth =
                    Math.max(0, ...hole.leituras.map((l) => l.profundidade_m)) +
                    1;
                  updateHole({
                    ...hole,
                    profundidadeFinal_m: depth,
                    leituras: [
                      ...hole.leituras,
                      {
                        profundidade_m: depth,
                        nspt_real: 0,
                        solo: "Areia",
                        impenetravel: false,
                      },
                    ],
                  });
                }}
              >
                <Plus size={15} />
                Adicionar leitura
              </button>
            </>
          ) : (
            <div className="empty compact">
              Importe uma sondagem ou crie o primeiro furo.
            </div>
          )}
        </div>
      </div>
      <div className="soil-settings">
        <Select
          label="Perfil médio"
          value={p.sondagem.submodo}
          onChange={(v) => set("submodo", v)}
          options={[
            ["2.2_conservador", "2.2 · Conservador"],
            ["2.1_predominante", "2.1 · Família predominante"],
          ]}
        />
        <Field
          label="Janela de compatibilização"
          unit="m"
          min={0.05}
          value={p.sondagem.janela}
          onChange={(v) => set("janela", v)}
        />
        <Field
          label="Ajuste de cotas Δ"
          unit="m"
          value={p.sondagem.delta}
          onChange={(v) => set("delta", v)}
        />
        <Field
          label="Cota do NA manual (opcional)"
          unit="m"
          nullable
          value={p.sondagem.na}
          onChange={(v) => set("na", v)}
        />
      </div>
      <div className="modal-footer">
        <p className="hint">
          Campo NA vazio: usar a água registrada nos furos. Sem registro:
          nenhuma água considerada.
        </p>
        <button className="primary" onClick={onClose}>
          Concluir edição
        </button>
      </div>
    </Modal>
  );
}
