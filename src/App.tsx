import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type ComponentType,
} from "react";
import {
  ArrowDownToLine,
  ArrowUpRight,
  Box,
  Calculator,
  CheckCircle2,
  ChevronRight,
  CircleHelp,
  Copy,
  Download,
  FileJson,
  FilePlus2,
  FileText,
  FolderOpen,
  Layers3,
  ListChecks,
  LoaderCircle,
  PanelRightClose,
  Plus,
  Redo2,
  Save,
  Settings2,
  Shovel,
  SlidersHorizontal,
  Table2,
  Trash2,
  Undo2,
  X,
  AlertTriangle,
  Cylinder,
  FlaskConical,
  FolderPen,
} from "lucide-react";
import {
  clone,
  createProject,
  examples,
  id,
  KEY,
  blank,
  parseProject,
  restore,
} from "./domain/project";
import { desktop, request, safeName, saveText } from "./domain/api";
import {
  fmt,
  type Calculation,
  type Parameters,
  type Project,
  type View,
} from "./domain/types";
import { Properties } from "./components/Properties";
import { Viewer, type Layers } from "./components/Viewer";
import { ActionsEditor } from "./components/ActionsEditor";
import { SoilEditor } from "./components/SoilEditor";
import { Field, TextField, Toggle } from "./components/Fields";
import { Modal } from "./components/Modal";
import { OutputView, Summary } from "./components/Results";

type Icon = ComponentType<{ size?: number; strokeWidth?: number }>;
type Tool = {
  label: string;
  icon: Icon;
  run: () => void;
  disabled?: boolean;
  primary?: boolean;
  hint?: string;
};
const views: [View, string, Icon][] = [
  ["modelo", "Modelo 3D", Box],
  ["elevacao", "Corte", Cylinder],
  ["esforcos", "Esforços", ArrowUpRight],
  ["sondagens", "Sondagens", Layers3],
  ["verificacoes", "Verificações", ListChecks],
  ["memoria", "Memória", FileText],
  ["quantitativos", "Quantitativos", Table2],
  ["mapa", "D × L", Table2],
];

export default function App() {
  const [initial] = useState(restore);
  const [project, setProject] = useState(initial.project),
    [warning, setWarning] = useState(initial.warning);
  const [cache, setCache] = useState<
    Record<string, { stamp: string; data: Calculation }>
  >({});
  const [view, setView] = useState<View>("modelo"),
    [ribbon, setRibbon] = useState("Projeto");
  const [dialog, setDialog] = useState(""),
    [advanced, setAdvanced] = useState(""),
    [dialogError, setDialogError] = useState("");
  const [confirm, setConfirm] = useState<{
    title: string;
    message: string;
    action: () => void;
  } | null>(null);
  const [busy, setBusy] = useState(false),
    [motor, setMotor] = useState("Conectando…");
  const [error, setError] = useState(""),
    [toast, setToast] = useState(""),
    [dirty, setDirty] = useState(false),
    [autosave, setAutosave] = useState("Recuperação automática");
  const [right, setRight] = useState(true),
    [showAlerts, setShowAlerts] = useState(true);
  const [layers, setLayers] = useState<Layers>({
    soil: true,
    concrete: true,
    casing: true,
    steel: true,
    water: true,
    grid: true,
  });
  const file = useRef<HTMLInputElement>(null),
    history = useRef<Project[]>([]),
    future = useRef<Project[]>([]),
    latest = useRef(project),
    busyRef = useRef(false);
  latest.current = project;
  const element =
      project.elements.find((e) => e.id === project.selectedId) ||
      project.elements[0],
    p = element.parameters;
  const stamp = useMemo(() => JSON.stringify(p), [p]);
  const calculated =
    cache[element.id]?.stamp === stamp ? cache[element.id].data : undefined;
  const geometry = calculated?.result.p || p;
  const update = (next: Project, remember = true) => {
    if (remember) {
      history.current = [...history.current.slice(-39), clone(project)];
      future.current = [];
    }
    setProject(next);
    setDirty(true);
  };
  const edit = (next: Parameters) =>
    update({
      ...project,
      elements: project.elements.map((e) =>
        e.id === element.id ? { ...e, parameters: next } : e,
      ),
    });
  const reset = (next: Project) => {
    history.current = [];
    future.current = [];
    setProject(next);
    setCache({});
    setView("modelo");
    setDirty(false);
    setWarning("");
    setError("");
  };
  const protectedReplace = (title: string, action: () => void) => {
    if (dirty)
      setConfirm({
        title,
        message:
          "Há alterações ainda não exportadas para arquivo. Continuar substituirá o projeto aberto. Cancele e salve uma cópia se quiser preservá-las.",
        action,
      });
    else action();
  };
  const showDialog = (name: string) => {
    setDialogError("");
    if (name === "advanced") setAdvanced(JSON.stringify(p, null, 2));
    setDialog(name);
  };
  const calculate = async () => {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setError("");
    const elementId = element.id,
      source = stamp,
      parameters = clone(p);
    try {
      const data = await request<Calculation>({
        action: "calculate",
        parameters,
      });
      setCache((old) => ({ ...old, [elementId]: { stamp: source, data } }));
      setMotor("Motor local conectado");
      const current = latest.current.elements.find((e) => e.id === elementId);
      setToast(
        current && JSON.stringify(current.parameters) === source
          ? `Cálculo concluído em ${fmt(data.result.tempo, 1)} s.`
          : "Dados alterados durante a análise. Recalcule para atualizar os resultados.",
      );
    } catch (err) {
      setError((err as Error).message);
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  };
  const save = async () => {
    try {
      if (
        await saveText(
          `${safeName(project.name)}.tubstruct.json`,
          JSON.stringify(project, null, 2),
        )
      ) {
        setDirty(false);
        setToast("Projeto exportado com todos os dados e sondagens.");
      }
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const undo = () => {
    const next = history.current.pop();
    if (!next) return;
    future.current.push(clone(project));
    setProject(next);
    setDirty(true);
  };
  const redo = () => {
    const next = future.current.pop();
    if (!next) return;
    history.current.push(clone(project));
    setProject(next);
    setDirty(true);
  };
  const add = (example?: keyof typeof examples) => {
    if (project.elements.length >= 100) {
      setError("Limite de 100 tubulões por projeto.");
      return;
    }
    let n = 1;
    while (project.elements.some((e) => e.parameters.nome === `T${n}`)) n++;
    const newElement = {
      id: id(),
      parameters: example ? clone(examples[example]) : blank(`T${n}`),
    };
    update({
      ...project,
      elements: [...project.elements, newElement],
      selectedId: newElement.id,
      example: project.example || !!example,
    });
    setView("modelo");
    setDialog("");
  };
  const duplicate = () => {
    if (project.elements.length >= 100) return;
    const next = {
      id: id(),
      parameters: {
        ...clone(p),
        nome: `${p.nome.slice(0, 85)} · cópia ${project.elements.length}`,
      },
    };
    update({
      ...project,
      elements: [...project.elements, next],
      selectedId: next.id,
    });
  };
  const remove = () =>
    setConfirm({
      title: "Remover tubulão",
      message: `Remover ${p.nome} do projeto? Você poderá desfazer esta operação.`,
      action: () => {
        const elements = project.elements.filter((e) => e.id !== element.id);
        update({ ...project, elements, selectedId: elements[0].id });
      },
    });
  const exportResult = async () => {
    if (!calculated) return;
    try {
      if (
        await saveText(
          `${safeName(p.nome)}_resultado.json`,
          JSON.stringify(calculated.result, null, 2),
        )
      )
        setToast("Resultado exportado.");
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const export3d = async () => {
    if (!calculated || busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    try {
      const html = await request<string>({ action: "export3d", parameters: p });
      if (await saveText(`${safeName(p.nome)}_3D.html`, html, "text/html"))
        setToast("Modelo 3D independente exportado.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  };
  useEffect(() => {
    request<{ version: string }>({ action: "health" })
      .then(() => setMotor("Motor local conectado"))
      .catch(() => setMotor("Motor não conectado"));
  }, []);
  useEffect(() => {
    if (warning) return;
    const t = setTimeout(() => {
      try {
        localStorage.setItem(KEY, JSON.stringify(project));
        setAutosave("Cópia local atualizada");
      } catch {
        setAutosave("Falha na recuperação automática — salve um arquivo");
      }
    }, 500);
    return () => clearTimeout(t);
  }, [project, warning]);
  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (dirty) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(""), 5500);
    return () => clearTimeout(t);
  }, [toast]);
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (dialog || confirm) return;
      const editing = /INPUT|TEXTAREA|SELECT/.test(
        (e.target as HTMLElement)?.tagName,
      );
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        void save();
      } else if (e.key === "F9") {
        e.preventDefault();
        void calculate();
      } else if (
        !editing &&
        (e.ctrlKey || e.metaKey) &&
        e.key.toLowerCase() === "z"
      ) {
        e.preventDefault();
        e.shiftKey ? redo() : undo();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  });

  const tools: Record<string, { name: string; items: Tool[] }[]> = {
    Projeto: [
      {
        name: "Arquivo",
        items: [
          {
            label: "Novo projeto",
            icon: FilePlus2,
            run: () =>
              protectedReplace("Novo projeto", () => {
                reset(createProject());
                showDialog("project");
              }),
            hint: "Criar projeto vazio",
          },
          {
            label: "Abrir",
            icon: FolderOpen,
            run: () =>
              protectedReplace("Abrir projeto", () => file.current?.click()),
          },
          {
            label: "Salvar",
            icon: Save,
            run: save,
            hint: "Ctrl+S · Salvar cópia portátil",
          },
        ],
      },
      {
        name: "Tubulões",
        items: [
          { label: "Adicionar", icon: Plus, run: () => add() },
          { label: "Duplicar", icon: Copy, run: duplicate },
          {
            label: "Remover",
            icon: Trash2,
            run: remove,
            disabled: project.elements.length <= 1,
          },
        ],
      },
      {
        name: "Dados de entrada",
        items: [
          {
            label: "Ações",
            icon: ArrowDownToLine,
            run: () => showDialog("actions"),
          },
          { label: "Sondagens", icon: Layers3, run: () => showDialog("soil") },
          {
            label: "Identificação",
            icon: FolderPen,
            run: () => showDialog("project"),
          },
        ],
      },
      {
        name: "Análise",
        items: [
          {
            label: busy ? "Calculando…" : "Calcular",
            icon: busy ? LoaderCircle : Calculator,
            run: calculate,
            disabled: busy,
            primary: true,
            hint: "F9 · Calcular tubulão selecionado",
          },
          {
            label: "Exemplos",
            icon: FlaskConical,
            run: () => showDialog("examples"),
          },
        ],
      },
    ],
    Modelo: [
      {
        name: "Parâmetros",
        items: [
          { label: "Geometria", icon: Cylinder, run: () => setRight(true) },
          {
            label: "Ações",
            icon: ArrowDownToLine,
            run: () => showDialog("actions"),
          },
          { label: "Sondagens", icon: Layers3, run: () => showDialog("soil") },
          {
            label: "Critérios",
            icon: SlidersHorizontal,
            run: () => showDialog("advanced"),
          },
        ],
      },
      {
        name: "Vistas",
        items: [
          { label: "Modelo 3D", icon: Box, run: () => setView("modelo") },
          { label: "Corte", icon: Cylinder, run: () => setView("elevacao") },
        ],
      },
      {
        name: "Análise",
        items: [
          {
            label: busy ? "Calculando…" : "Calcular",
            icon: Calculator,
            run: calculate,
            disabled: busy,
            primary: true,
          },
        ],
      },
    ],
    Resultados: [
      {
        name: "Resultados",
        items: [
          {
            label: "Verificações",
            icon: ListChecks,
            run: () => setView("verificacoes"),
          },
          {
            label: "Esforços",
            icon: ArrowUpRight,
            run: () => setView("esforcos"),
          },
          { label: "Mapa D × L", icon: Table2, run: () => setView("mapa") },
        ],
      },
      {
        name: "Documentação",
        items: [
          { label: "Memória", icon: FileText, run: () => setView("memoria") },
          {
            label: "Quantitativos",
            icon: Table2,
            run: () => setView("quantitativos"),
          },
          {
            label: "Resultado JSON",
            icon: FileJson,
            run: exportResult,
            disabled: !calculated,
          },
          {
            label: "3D independente",
            icon: Box,
            run: export3d,
            disabled: !calculated || busy,
          },
        ],
      },
    ],
    Configurações: [
      {
        name: "Aplicativo",
        items: [
          {
            label: "Propriedades",
            icon: PanelRightClose,
            run: () => setRight(!right),
          },
          {
            label: "Parâmetros JSON",
            icon: FileJson,
            run: () => showDialog("advanced"),
          },
          {
            label: "Sobre / ajuda",
            icon: CircleHelp,
            run: () => showDialog("help"),
          },
        ],
      },
    ],
  };
  const output =
    view === "modelo" ? (
      <Viewer parameters={geometry} scene={calculated?.scene} layers={layers} />
    ) : calculated ? (
      <OutputView
        key={view + element.id + stamp}
        calculation={calculated}
        view={view}
        adopt={() => {
          const next = clone(calculated.result.p);
          next.dimensionamento.automatico = false;
          delete next.dimensionamento.escolha_usuario;
          edit(next);
          setToast(
            "Geometria adotada. Recalcule para verificar como geometria fixa.",
          );
        }}
      />
    ) : (
      <div className="empty">
        <Calculator size={42} />
        <h2>Calcule para visualizar os resultados</h2>
        <p>
          As saídas são atualizadas apenas para os dados atuais de {p.nome}.
        </p>
        <button className="primary" disabled={busy} onClick={calculate}>
          {busy ? "Calculando…" : "Calcular tubulão"}
        </button>
      </div>
    );
  return (
    <div className="app-shell">
      <header className="titlebar">
        <div className="brand">
          <img src="/tubstruct.svg" alt="" />
          <strong>
            Tub<span>Struct</span>
          </strong>
          <span className="version">0.1.0</span>
        </div>
        <div className="quick-tools">
          <button
            title="Salvar projeto (Ctrl+S)"
            aria-label="Salvar projeto"
            onClick={save}
          >
            <Save size={16} />
          </button>
          <button
            title="Desfazer"
            aria-label="Desfazer"
            disabled={!history.current.length}
            onClick={undo}
          >
            <Undo2 size={16} />
          </button>
          <button
            title="Refazer"
            aria-label="Refazer"
            disabled={!future.current.length}
            onClick={redo}
          >
            <Redo2 size={16} />
          </button>
        </div>
        <span className="window-project">
          {project.name}
          {dirty ? " •" : ""}
        </span>
        <a
          className="wordmark"
          href="https://openstruct.com.br"
          target="_blank"
          rel="noreferrer"
        >
          OPENSTRUCT
        </a>
        <button
          title="Ajuda"
          aria-label="Ajuda"
          onClick={() => showDialog("help")}
        >
          <CircleHelp size={18} />
        </button>
      </header>
      <div className="ribbon">
        <nav className="ribbon-tabs">
          {Object.keys(tools).map((name) => (
            <button
              key={name}
              className={ribbon === name ? "active" : ""}
              onClick={() => setRibbon(name)}
            >
              {name}
            </button>
          ))}
          <span className="ribbon-tag">
            <i />
            FUNDAÇÕES · TUBULÕES CURTOS
          </span>
        </nav>
        <div className="ribbon-content">
          {tools[ribbon].map((group) => (
            <div key={group.name} className="ribbon-group">
              <div>
                {group.items.map((t) => (
                  <button
                    key={t.label}
                    className={`ribbon-tool ${t.primary ? "primary-tool" : ""}`}
                    disabled={t.disabled}
                    onClick={t.run}
                    title={t.hint || t.label}
                  >
                    <t.icon size={23} strokeWidth={1.6} />
                    <span>{t.label}</span>
                  </button>
                ))}
              </div>
              <small>{group.name}</small>
            </div>
          ))}
          <div className="ribbon-note">
            <Cylinder size={29} strokeWidth={1} />
            <span>
              Corpo rígido
              <br />
              <b>Seção circular constante</b>
            </span>
          </div>
        </div>
      </div>
      <input
        ref={file}
        type="file"
        accept=".json"
        hidden
        onChange={async (e) => {
          const f = e.target.files?.[0];
          e.target.value = "";
          if (!f) return;
          try {
            if (f.size > 2_000_000) throw new Error("Arquivo maior que 2 MB.");
            const next = parseProject(await f.text());
            reset(next);
            if (
              next.elements.some(
                (e) =>
                  !Object.keys(e.parameters.sondagem.sondagens || {}).length,
              )
            )
              setToast(
                "Projeto aberto. Importe as sondagens referenciadas antes de calcular.",
              );
            else setToast("Projeto aberto. Recalcule para gerar resultados.");
          } catch (err) {
            setError((err as Error).message);
          }
        }}
      />
      {(error || warning) && (
        <div className="error-banner" role="alert">
          <AlertTriangle size={16} />
          <span>{error || warning}</span>
          <button
            aria-label="Fechar aviso"
            onClick={() => {
              setError("");
              if (warning) {
                setWarning("");
                setToast(
                  "Recuperação automática habilitada para o projeto atual.",
                );
              }
            }}
          >
            <X size={16} />
          </button>
        </div>
      )}
      <div className={`workspace ${right ? "" : "without-properties"}`}>
        <aside className="project-panel">
          <div className="panel-heading">
            <FolderOpen size={16} />
            <b>Explorador do projeto</b>
            <button aria-label="Adicionar tubulão" onClick={() => add()}>
              <Plus size={16} />
            </button>
          </div>
          <div className="project-tree">
            <button
              className="project-root"
              onClick={() => showDialog("project")}
            >
              <ChevronRight size={13} />
              <FolderOpen size={16} />
              <span>{project.name}</span>
            </button>
            <div className="tree-label">
              TUBULÕES <span>{project.elements.length}</span>
            </div>
            {project.elements.map((e) => {
              const c = cache[e.id];
              const current = c?.stamp === JSON.stringify(e.parameters);
              return (
                <button
                  key={e.id}
                  className={`tree-element ${e.id === element.id ? "selected" : ""}`}
                  onClick={() => setProject({ ...project, selectedId: e.id })}
                >
                  <Cylinder size={17} />
                  <span>
                    <b>{e.parameters.nome}</b>
                    <small>
                      {e.parameters.quantidade} un. · L{" "}
                      {fmt(e.parameters.geometria.L)} m
                    </small>
                  </span>
                  <i
                    className={`status-dot ${current ? (c.data.result.ok ? "pass" : "fail") : ""}`}
                    title={
                      current
                        ? c.data.result.ok
                          ? "Verificações atendidas"
                          : "Revisão necessária"
                        : "A calcular"
                    }
                  />
                </button>
              );
            })}
            <button className="tree-add" onClick={() => add()}>
              <Plus size={15} />
              Novo tubulão
            </button>
            <div className="tree-label">DADOS DO ELEMENTO</div>
            <button className="tree-link" onClick={() => showDialog("actions")}>
              <ArrowDownToLine size={16} />
              Ações características<span>{p.acoes.length}</span>
            </button>
            <button className="tree-link" onClick={() => showDialog("soil")}>
              <Layers3 size={16} />
              Furos de sondagem
              <span>{Object.keys(p.sondagem.sondagens || {}).length}</span>
            </button>
            <button
              className="tree-link"
              onClick={() => setView("verificacoes")}
            >
              <ListChecks size={16} />
              Verificações
            </button>
            <button className="tree-link" onClick={() => setView("memoria")}>
              <FileText size={16} />
              Memória de cálculo
            </button>
          </div>
          <div className="layer-panel">
            <div className="tree-label">VISIBILIDADE DO MODELO</div>
            {(
              [
                ["soil", "Camadas do solo"],
                ["concrete", "Concreto e lastro"],
                ["casing", "Anéis pré-moldados"],
                ["steel", "Armaduras calculadas"],
                ["water", "Nível d'água"],
                ["grid", "Grade de referência"],
              ] as [keyof Layers, string][]
            ).map(([key, label]) => (
              <Toggle
                key={key}
                label={label}
                checked={layers[key]}
                onChange={(v) => setLayers({ ...layers, [key]: v })}
              />
            ))}
            <p className="hint">Solo e armaduras aparecem após o cálculo.</p>
          </div>
          <div className="project-foot">
            <Shovel size={17} />
            <span>
              Fundação circular
              <br />
              <b>Sem base alargada</b>
            </span>
          </div>
        </aside>
        <main className="main-panel">
          <div className="contextbar">
            <span>
              Projeto <ChevronRight size={12} />
              <b>{p.nome}</b>
            </span>
            {project.example && (
              <span className="example-badge">
                <FlaskConical size={12} />
                Contém exemplo · sondagens fictícias
              </span>
            )}
            <button
              title="Mostrar ou ocultar propriedades"
              aria-label="Alternar propriedades"
              onClick={() => setRight(!right)}
            >
              <PanelRightClose size={16} />
            </button>
          </div>
          <nav className="view-tabs">
            {views.map(([key, label, Icon]) => (
              <button
                key={key}
                className={view === key ? "active" : ""}
                onClick={() => setView(key)}
              >
                <Icon size={14} />
                {label}
              </button>
            ))}
          </nav>
          <div className="viewport">
            {output}
            {busy && (
              <div className="calculation-progress" role="status">
                <LoaderCircle className="spin" size={17} />
                <span>
                  {p.dimensionamento.automatico
                    ? "Analisando candidatos e verificando a solução…"
                    : "Processando análise e verificações…"}
                </span>
              </div>
            )}
          </div>
          <Summary
            calculation={calculated}
            onChecks={() => setView("verificacoes")}
          />
          {calculated && (
            <div className="alerts-panel">
              <button onClick={() => setShowAlerts(!showAlerts)}>
                <AlertTriangle size={14} />
                {calculated.result.alertas.length} observações do cálculo
                <span>{showAlerts ? "Recolher" : "Expandir"}</span>
              </button>
              {showAlerts && (
                <div>
                  {calculated.result.alertas.map(([type, msg], i) => (
                    <p key={i} className={type === "erro" ? "bad" : ""}>
                      <span>
                        {type === "erro"
                          ? "ERRO"
                          : type === "aviso"
                            ? "ATENÇÃO"
                            : "INFO"}
                      </span>
                      {msg}
                    </p>
                  ))}
                </div>
              )}
            </div>
          )}
        </main>
        {right && (
          <Properties
            p={p}
            onChange={edit}
            onAdvanced={() => showDialog("advanced")}
          />
        )}
      </div>
      <footer className="statusbar">
        <span>
          <i
            className={`status-dot ${motor.includes("conectado") && !motor.includes("não") ? "pass" : ""}`}
          />
          {busy ? "Análise em andamento" : motor}
        </span>
        <span>{autosave}</span>
        <span>
          {calculated ? "Resultados dos dados atuais" : "Aguardando cálculo"} ·
          m / kN / MPa
        </span>
        <b>OpenStruct · TubStruct</b>
      </footer>
      {toast && (
        <div className="toast" role="status">
          <CheckCircle2 size={17} />
          {toast}
          <button aria-label="Fechar notificação" onClick={() => setToast("")}>
            <X size={15} />
          </button>
        </div>
      )}
      {dialog === "actions" && (
        <ActionsEditor p={p} onChange={edit} onClose={() => setDialog("")} />
      )}
      {dialog === "soil" && (
        <SoilEditor p={p} onChange={edit} onClose={() => setDialog("")} />
      )}
      {dialog === "project" && (
        <Modal title="Identificação do projeto" onClose={() => setDialog("")}>
          <TextField
            label="Nome do projeto"
            value={project.name}
            onChange={(name) => update({ ...project, name })}
          />
          <TextField
            label="Responsável"
            value={project.author}
            onChange={(author) => update({ ...project, author })}
          />
          <p className="hint">
            O arquivo .tubstruct.json reúne todos os tubulões e suas sondagens.
            Salve uma cópia para transferir o projeto entre computadores.
          </p>
          <div className="modal-footer">
            <button className="primary" onClick={() => setDialog("")}>
              Concluir
            </button>
          </div>
        </Modal>
      )}
      {dialog === "advanced" && (
        <Modal title="Parâmetros completos" wide onClose={() => setDialog("")}>
          <p className="intro">
            Edite todas as opções do contrato original, incluindo lista de
            diâmetros, discretização, coeficientes e parâmetros das camadas. A
            aplicação valida os dados antes de aplicá-los.
          </p>
          <textarea
            className="json-editor"
            aria-label="Parâmetros JSON"
            value={advanced}
            spellCheck={false}
            onChange={(e) => setAdvanced(e.target.value)}
          />
          {dialogError && (
            <p role="alert" className="error-banner">
              {dialogError}
            </p>
          )}
          <div className="modal-footer">
            <button className="secondary" onClick={() => setDialog("")}>
              Cancelar
            </button>
            <button
              className="primary"
              onClick={async () => {
                try {
                  const data = await request<Parameters>({
                    action: "normalize",
                    parameters: JSON.parse(advanced),
                  });
                  edit(data);
                  setDialog("");
                  setToast("Parâmetros validados e aplicados.");
                } catch (e) {
                  setDialogError((e as Error).message);
                }
              }}
            >
              Validar e aplicar
            </button>
          </div>
        </Modal>
      )}
      {dialog === "examples" && (
        <Modal title="Exemplos da base original" onClose={() => setDialog("")}>
          <p className="intro">
            Os três exemplos usam sondagens fictícias SP-A e SP-B. Cada exemplo
            será adicionado como um novo tubulão.
          </p>
          <div className="example-list">
            {(
              [
                [
                  "poste",
                  "01",
                  "Poste com anéis pré-moldados",
                  "Geometria fixa · DN 2,00 m · L 2,00 m",
                ],
                [
                  "pilar",
                  "02",
                  "Pilar com dimensionamento automático",
                  "Busca D × L · fretagem no topo",
                ],
                [
                  "armado",
                  "03",
                  "Fuste em concreto armado",
                  "Momento elevado · armadura longitudinal",
                ],
              ] as const
            ).map(([key, n, title, description]) => (
              <button key={key} onClick={() => add(key)}>
                <span>{n}</span>
                <div>
                  <b>{title}</b>
                  <small>{description}</small>
                </div>
                <ChevronRight size={18} />
              </button>
            ))}
          </div>
        </Modal>
      )}
      {dialog === "help" && (
        <Modal title="TubStruct · OpenStruct" onClose={() => setDialog("")}>
          <div className="about-brand">
            <img src="/tubstruct.svg" alt="" />
            <div>
              <h2>
                TubStruct <small>0.1.0</small>
              </h2>
              <p>Análise de tubulões curtos</p>
            </div>
          </div>
          <ol className="help-steps">
            <li>Crie o projeto e cadastre a geometria de cada tubulão.</li>
            <li>
              Informe ações características no topo e importe ou digite as
              sondagens.
            </li>
            <li>
              Confira materiais, critérios e hipóteses. Pressione <kbd>F9</kbd>{" "}
              para calcular.
            </li>
            <li>
              Revise verificações e observações. Exporte a memória e salve o
              projeto com <kbd>Ctrl+S</kbd>.
            </li>
          </ol>
          <div className="info-card">
            <b>Modelo e limites</b>
            <p>
              Corpo rígido com cinco graus de liberdade, seção circular sem base
              alargada, reação lateral limitada e base sem tração. O motor
              verifica rigidez e demais critérios apresentados na memória.
            </p>
            <p>
              Referências, hipóteses e coeficientes são os da base
              TubuloesCurtos_Portatil fornecida. A adaptação preserva o núcleo;
              não representa revisão normativa independente.
            </p>
          </div>
          <p>
            A memória HTML pode ser impressa em PDF pelo navegador. A integração
            original de DWG / DXF / PDF de desenho depende do TQS no Windows e
            está preservada em <code>backend/legacy</code>.
          </p>
          <p className="hint">
            Recuperação automática neste dispositivo. O botão Salvar gera uma
            cópia portátil; arquivos importados não são sobrescritos.
          </p>
          <a
            href="https://github.com/ricardocorsini/tub-struct"
            target="_blank"
            rel="noreferrer"
          >
            Código-fonte e contribuições ↗
          </a>
        </Modal>
      )}
      {confirm && (
        <Modal title={confirm.title} onClose={() => setConfirm(null)}>
          <p>{confirm.message}</p>
          <div className="modal-footer">
            <button className="secondary" onClick={() => setConfirm(null)}>
              Cancelar
            </button>
            <button
              className="primary"
              onClick={() => {
                confirm.action();
                setConfirm(null);
              }}
            >
              Continuar
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
