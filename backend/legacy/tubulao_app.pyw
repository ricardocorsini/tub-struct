# -*- coding: utf-8 -*-
"""
Janela do app de tubulões curtos, no estilo do TQS (pedido do usuário: ribbon, árvore do projeto e propriedades à
esquerda, área gráfica de fundo preto, mensagens e barra de status). Reaproveita o ribbon e os ícones das janelas
no estilo do TQS (cad_ribbon.py e cad_icones.py), com ícones próprios acrescentados aqui.

Abas: Tubulão (geometria, materiais, apoio, calcular, dimensionar), Sondagem (cadastro dos furos no formato do
GEOSPT, importação e exportação, perfil de cálculo, parâmetros do solo), Cargas (ações e combinações), Critérios,
Exibir (elevação, base, ruptura, esforços, sondagens, mapa D x L, verificações) e Saídas (memória HTML/PDF, 3D,
DWG/PDF/DXF do TQS). O projeto é o mesmo JSON do lote (tubulao_core.py).

Cópia portátil (14/11/2026) do app de _apps\\TubulõesCurtos, com o mesmo cálculo e o mesmo desenho. Os módulos que o
original importava de outras pastas (ribbon e ícones do _apps\\_comum, desenho do app de estacas, three.js) estão
nesta pasta. Ao abrir, confere as dependências (dependencias.py) e diz o que falta, sem traceback.
"""
import os, sys, json, copy, math, threading, traceback, subprocess, re, queue

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import dependencias as dep                                    # noqa: E402

_itens = dep.conferir(janela=True, tqs=False)        # tkinter, matplotlib, numpy e Pillow: sem eles, a janela não abre
if dep.faltas(_itens):
    _msg = dep.mensagem_faltas(_itens, "abrir a janela do app")
    try:                                             # sem tkinter, a caixa de mensagem do próprio Windows
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, _msg, "Tubulões curtos", 0x10)
    except Exception:
        print(_msg)
    sys.exit(1)

import tkinter as tk                                          # noqa: E402
from tkinter import ttk, filedialog, messagebox               # noqa: E402
import cad_ribbon as rbn                                      # noqa: E402
import cad_icones as ic                                       # noqa: E402
import tubulao_core as tcore                                  # noqa: E402
import tubulao_sondagem as ts                                 # noqa: E402
import tubulao_solo as so                                     # noqa: E402
import matplotlib                                             # noqa: E402
matplotlib.use("TkAgg")
from matplotlib.figure import Figure                          # noqa: E402
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk  # noqa: E402
from matplotlib.patches import Rectangle, Polygon, Wedge, Circle  # noqa: E402
import numpy as np                                            # noqa: E402

APP = "Tubulões curtos"
TITULO = APP + " (cópia portátil)"
FONTE = ("Segoe UI", 9)
FUNDO_CAD = "#000000"
CORES = dict(s1="#3987e5", s2="#d95926", s3="#199e70", s4="#c98500", txt="#e6e6e6", grade="#333333", neutro="#8a8a8a",
             fam={"Granular": "#7a6338", "Intermediário": "#6e5644", "Coesivo": "#5a5651"}, conc="#9b9b96", anel="#c8c8c2",
             crit="#e66767", ok="#0ca30c")


# ------------------------------------------------------------------------------------------------ ícones próprios
def i_tubulao(d):
    for x in range(3, 30, 4):
        d.linha([(x, 10), (x - 3, 13)], ic.CINZA, 1.0)
    d.linha([(2, 10), (30, 10)], ic.PRETO, 1.6)
    d.ret(10, 5, 22, 28, ic.PRETO, "#d9d9d6", 1.6)
    for y in (12, 18, 24):
        d.linha([(10, y), (22, y)], ic.CINZA, 1.0)
    d.seta(2, 6, 9, 6, ic.VERM, 1.8, 3.2)


def i_sondagem(d):
    d.ret(18, 3, 26, 29, ic.PRETO, "#f3e3c3", 1.4)
    d.ret(18, 12, 26, 20, ic.PRETO, "#d9c9b8", 1.0)
    d.linha([(6, 4), (11, 9), (7, 14), (13, 20), (9, 25), (14, 29)], ic.CIANO, 2.0)
    d.linha([(4, 3), (4, 29)], ic.CINZA, 1.0)


def i_cargas(d):
    d.seta(16, 2, 16, 14, ic.VERM, 2.2, 4)
    d.seta(2, 18, 14, 18, ic.VERM, 2.2, 4)
    d.d.arc([18 * ic.SS, 14 * ic.SS, 30 * ic.SS, 26 * ic.SS], 180, 360, fill=ic.AZUL, width=round(2 * ic.SS))
    d.poli([(30, 20), (27, 16), (31.5, 16)], ic.AZUL, ic.AZUL, 0.5)
    d.ret(12, 22, 20, 30, ic.PRETO, "#d9d9d6", 1.2)


def i_solo(d):
    for y0, y1, c in ((4, 12, "#f3e3c3"), (12, 21, "#e3cdb6"), (21, 29, "#cfc9c0")):
        d.ret(3, y0, 29, y1, ic.PRETO, c, 1.2)
    d.texto(16, 16.5, "φ", ic.PRETO, 10)


def i_ruptura(d):
    d.linha([(2, 8), (30, 8)], ic.PRETO, 1.4)
    d.poli([(12, 3), (20, 4), (17, 28), (9, 27)], ic.PRETO, "#d9d9d6", 1.4)
    d.d.arc([10 * ic.SS, 10 * ic.SS, 30 * ic.SS, 30 * ic.SS], 280, 350, fill=ic.VERM, width=round(2 * ic.SS))
    d.texto(26, 26, "FS", ic.VERM, 8)


def i_tres_d(d):
    d.poli([(5, 11), (16, 5), (27, 11), (16, 17)], ic.PRETO, "#dbe8f7", 1.3)
    d.poli([(5, 11), (16, 17), (16, 29), (5, 23)], ic.PRETO, "#b9cfe9", 1.3)
    d.poli([(16, 17), (27, 11), (27, 23), (16, 29)], ic.PRETO, "#8fb3df", 1.3)
    d.texto(22, 22, "3D", ic.AZUL, 7.5)


def i_memoria(d):
    ic._folha(d, 5, 2, 25, 29)
    d.linha([(9, 22), (13, 16), (17, 19), (22, 10)], ic.AZUL, 1.8)
    for y in (7, 10):
        d.linha([(9, y), (16, y)], ic.CINZA, 1.0)


def i_dimensionar(d):
    for i in range(4):
        for j in range(4):
            cor = "#cfe9cf" if (i + j) >= 4 else "white"
            d.ret(3 + i * 6.5, 3 + j * 6.5, 9.5 + i * 6.5, 9.5 + j * 6.5, ic.CINZA, cor, 0.8)
    d.ret(16, 16, 22.5, 22.5, ic.VERDE, "#9fd59f", 1.8)


def i_calcular(d):
    d.poli([(8, 4), (27, 16), (8, 28)], "#1e7a32", ic.VERDE, 1.4)


# Os dois ícones do app de telas que a aba Exibir usa (vistas Base e Esforços), copiados de
# _apps\TelaSoldada\tela_icones.py (código idêntico): o original os recebia ao importar o tela_icones.
def i_placas(d):
    d.ret(3, 3, 29, 29, ic.PRETO, "#f4f1ea", 1.6)
    d.tracejado(16, 3, 16, 29, ic.AZUL, 1.6)
    d.tracejado(3, 15, 29, 15, ic.AZUL, 1.6)


def i_barra(d):
    d.tracejado(16, 3, 16, 29, ic.AZUL, 1.6, 3.0, 2.0)               # junta
    d.ret(4, 13, 28, 19, ic.PRETO, "white", 1.4)                     # barra de transferência
    for x in range(16, 28, 3):                                       # metade engraxada
        d.linha([(x, 19), (x + 3, 13)], ic.LARANJA, 1.2)


for _k, _f in dict(tubulao=i_tubulao, sondagem=i_sondagem, cargas=i_cargas, solo=i_solo, ruptura=i_ruptura,
                   tres_d=i_tres_d, memoria=i_memoria, dimensionar=i_dimensionar, calcular=i_calcular,
                   placas=i_placas, barra=i_barra).items():
    ic.ICONES[_k] = _f


# ------------------------------------------------------------------------------------------------ utilidades
def num(v):
    if v is None:
        return None
    s = str(v).strip().replace(",", ".")
    if s == "":
        return None
    return float(s)


def br(v, c=2):
    if v is None:
        return ""
    if isinstance(v, float) and math.isinf(v):
        return "> 20"
    return f"{v:.{c}f}".replace(".", ",")


def caminho_get(d, chave):
    for k in chave.split("."):
        d = d.get(k) if isinstance(d, dict) else None
    return d


def caminho_set(d, chave, v):
    ks = chave.split(".")
    for k in ks[:-1]:
        d = d.setdefault(k, {})
    d[ks[-1]] = v


class Formulario(tk.Toplevel):
    """Diálogo de campos: [(chave com pontos, rótulo, tipo, opções)], tipo float, int, str, bool, combo, info."""

    def __init__(self, master, titulo, par, campos, ao_ok=None, largura=460):
        super().__init__(master)
        self.title(titulo)
        self.transient(master)
        self.resizable(False, False)
        self.par, self.campos, self.ao_ok, self.vars = par, campos, ao_ok, {}
        fr = ttk.Frame(self, padding=12)
        fr.pack(fill="both", expand=True)
        r = 0
        for chave, rot, tipo, opc in campos:
            if tipo == "titulo":
                ttk.Label(fr, text=rot, font=("Segoe UI", 9, "bold")).grid(row=r, column=0, columnspan=2, sticky="w", pady=(8, 2))
                r += 1
                continue
            v = caminho_get(par, chave) if chave else None
            if tipo == "bool":
                var = tk.BooleanVar(value=bool(v))
                ttk.Checkbutton(fr, text=rot, variable=var).grid(row=r, column=0, columnspan=2, sticky="w", pady=1)
            else:
                ttk.Label(fr, text=rot).grid(row=r, column=0, sticky="w", padx=(0, 10), pady=1)
                var = tk.StringVar(value="" if v is None else (br(v, 4).rstrip("0").rstrip(",") if isinstance(v, float) else str(v)))
                if tipo == "combo":
                    w = ttk.Combobox(fr, textvariable=var, values=[o[1] if isinstance(o, tuple) else o for o in opc], state="readonly", width=34)
                    if isinstance(opc[0], tuple):
                        inv = {o[0]: o[1] for o in opc}
                        var.set(inv.get(v, opc[0][1]))
                else:
                    w = ttk.Entry(fr, textvariable=var, width=36)
                    if tipo == "info":
                        w.configure(state="readonly")
                w.grid(row=r, column=1, sticky="w", pady=1)
            self.vars[chave] = (var, tipo, opc)
            r += 1
        bt = ttk.Frame(fr)
        bt.grid(row=r, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(bt, text="OK", command=self.ok).pack(side="left", padx=4)
        ttk.Button(bt, text="Cancelar", command=self.destroy).pack(side="left")
        self.bind("<Return>", lambda e: self.ok())
        self.bind("<Escape>", lambda e: self.destroy())
        self.grab_set()

    def ok(self):
        try:
            for chave, (var, tipo, opc) in self.vars.items():
                if tipo in ("info", "titulo"):
                    continue
                v = var.get()
                if tipo == "bool":
                    val = bool(v)
                elif tipo == "float":
                    val = num(v)
                elif tipo == "int":
                    val = int(num(v)) if num(v) is not None else None
                elif tipo == "combo":
                    val = next((o[0] for o in opc if o[1] == v), v) if isinstance(opc[0], tuple) else v
                else:
                    val = v
                caminho_set(self.par, chave, val)
        except ValueError as e:
            messagebox.showerror(APP, f"Valor inválido: {e}", parent=self)
            return
        self.destroy()
        if self.ao_ok:
            self.ao_ok()


class Tabela(ttk.Frame):
    """Tabela editável (duplo clique na célula). colunas: [(chave, título, largura, tipo, opções)]."""

    def __init__(self, master, colunas, linhas, altura=12):
        super().__init__(master)
        self.colunas, self.linhas = colunas, linhas
        self.tv = ttk.Treeview(self, columns=[c[0] for c in colunas], show="headings", height=altura, selectmode="extended")
        for k, t, w, *_ in colunas:
            self.tv.heading(k, text=t)
            self.tv.column(k, width=w, anchor="center")
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=sb.set)
        self.tv.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        self.tv.bind("<Double-1>", self._editar)
        self.atualizar()

    def atualizar(self):
        self.tv.delete(*self.tv.get_children())
        for i, l in enumerate(self.linhas):
            self.tv.insert("", "end", iid=str(i), values=[self._fmt(l.get(c[0]), c) for c in self.colunas])

    def _fmt(self, v, c):
        if c[3] == "bool":
            return "sim" if v else ""
        if isinstance(v, float):
            return br(v, 3).rstrip("0").rstrip(",")
        return "" if v is None else str(v)

    def _editar(self, ev):
        it = self.tv.identify_row(ev.y)
        col = self.tv.identify_column(ev.x)
        if not it or not col:
            return
        j = int(col[1:]) - 1
        k, _, _, tipo, *opc = self.colunas[j]
        i = int(it)
        x, y, w, h = self.tv.bbox(it, col)
        if tipo == "bool":
            self.linhas[i][k] = not self.linhas[i].get(k)
            self.atualizar()
            return
        var = tk.StringVar(value=self._fmt(self.linhas[i].get(k), self.colunas[j]))
        if tipo == "combo":
            ed = ttk.Combobox(self.tv, textvariable=var, values=opc[0], state="readonly")
        else:
            ed = ttk.Entry(self.tv, textvariable=var)
        ed.place(x=x, y=y, width=max(w, 80), height=h)
        ed.focus_set()

        def fim(_=None, salvar=True):
            if salvar:
                v = var.get()
                try:
                    self.linhas[i][k] = num(v) if tipo == "float" else v
                except ValueError:
                    pass
                self.ao_mudar(i, k)
            ed.destroy()
            self.atualizar()
        ed.bind("<Return>", fim)
        ed.bind("<FocusOut>", fim)
        ed.bind("<Escape>", lambda e: fim(salvar=False))
        if tipo == "combo":
            ed.bind("<<ComboboxSelected>>", fim)

    def ao_mudar(self, i, k):
        pass

    def selecionadas(self):
        return sorted(int(i) for i in self.tv.selection())


# ------------------------------------------------------------------------------------------------ diálogos
class DlgAcoes(tk.Toplevel):
    COLS = [("nome", "Ação", 220, "str"), ("tipo", "Tipo", 90, "combo", ["permanente", "variavel"]),
            ("categoria", "Categoria (ψ)", 140, "combo", list(tcore.PSI)), ("grupo", "Grupo (alternativas)", 130, "str"),
            ("N", "N (kN)", 70, "float"), ("Hx", "Hx (kN)", 70, "float"), ("Hy", "Hy (kN)", 70, "float"),
            ("Mx", "Mx (kN.m)", 75, "float"), ("My", "My (kN.m)", 75, "float")]

    def __init__(self, master, par, ao_ok):
        super().__init__(master)
        self.title("Ações características no topo do tubulão")
        self.transient(master)
        self.par, self.ao_ok = par, ao_ok
        self.linhas = copy.deepcopy(par.get("acoes", []))
        f = ttk.Frame(self, padding=10)
        f.pack(fill="both", expand=True)
        ttk.Label(f, text="Cargas características (kN, kN·m) no topo. z para cima; Hx com My > 0 e Hy com Mx < 0 tombam no mesmo sentido. "
                          "Ações variáveis do mesmo grupo são alternativas (não se somam).", wraplength=820).pack(anchor="w")
        self.tab = Tabela(f, self.COLS, self.linhas, 10)
        self.tab.pack(fill="both", expand=True, pady=6)
        b = ttk.Frame(f)
        b.pack(fill="x")
        ttk.Button(b, text="+ Ação", command=self.nova).pack(side="left")
        ttk.Button(b, text="Remover", command=self.remover).pack(side="left", padx=4)
        ttk.Button(b, text="OK", command=self.ok).pack(side="right")
        ttk.Button(b, text="Cancelar", command=self.destroy).pack(side="right", padx=4)
        self.grab_set()

    def nova(self):
        self.linhas.append(dict(nome=f"Ação {len(self.linhas) + 1}", tipo="variavel", categoria="vento", grupo="vento",
                                N=0.0, Hx=0.0, Hy=0.0, Mx=0.0, My=0.0))
        self.tab.atualizar()

    def remover(self):
        for i in reversed(self.tab.selecionadas()):
            del self.linhas[i]
        self.tab.atualizar()

    def ok(self):
        for l in self.linhas:
            if l.get("tipo") == "permanente":
                l.pop("categoria", None)
                l.pop("grupo", None)
        self.par["acoes"] = self.linhas
        self.destroy()
        self.ao_ok()


class DlgSondagens(tk.Toplevel):
    """Cadastro dos furos no formato do GEOSPT (obra 2.x): furos, NA, critério e leituras."""
    COLS = [("profundidade_m", "Prof. (m)", 70, "float"), ("nspt_real", "NSPT", 60, "float"),
            ("impenetravel", "Imp.", 45, "bool"), ("solo", "Solo", 170, "combo", list(ts.SOLOS)),
            ("familia", "Família", 100, "str"), ("cor", "Cor (laudo)", 140, "str")]

    def __init__(self, master, par, ao_ok, pasta):
        super().__init__(master)
        self.title("Sondagens (cadastro como no GEOSPT)")
        self.transient(master)
        self.par, self.ao_ok, self.pasta = par, ao_ok, pasta
        s = par["sondagem"]
        try:
            if s.get("sondagens"):
                self.furos = ts.normalizar_sondagens(s["sondagens"])
            elif s.get("arquivo"):
                arq = s["arquivo"] if os.path.isabs(s["arquivo"]) else os.path.join(pasta, s["arquivo"])
                self.furos, _ = ts.ler_geospt(arq)
            else:
                self.furos = {}
        except (ValueError, OSError) as e:
            messagebox.showwarning(APP, f"Não li as sondagens: {e}", parent=master)
            self.furos = {}
        self.atual = None
        f = ttk.Frame(self, padding=10)
        f.pack(fill="both", expand=True)
        esq = ttk.Frame(f)
        esq.pack(side="left", fill="y")
        ttk.Label(esq, text="Furos").pack(anchor="w")
        self.lb = tk.Listbox(esq, height=16, width=16, exportselection=False)
        self.lb.pack(fill="y", expand=True)
        self.lb.bind("<<ListboxSelect>>", lambda e: self.mostrar())
        for txt, cmd in (("+ Furo", self.novo), ("Remover", self.remover), ("Importar GEOSPT...", self.importar),
                         ("Exportar GEOSPT...", self.exportar)):
            ttk.Button(esq, text=txt, command=cmd).pack(fill="x", pady=1)
        dir_ = ttk.Frame(f)
        dir_.pack(side="left", fill="both", expand=True, padx=(10, 0))
        cab = ttk.Frame(dir_)
        cab.pack(fill="x")
        self.vars = {}
        for i, (k, rot) in enumerate((("nome", "Nome"), ("cotaTopo_m", "Cota da boca (m)"), ("profundidadeFinal_m", "Prof. final (m)"),
                                      ("naInicial_m", "NA inicial (m)"), ("naFinal_m", "NA final (m)"), ("x", "x (m)"), ("y", "y (m)"))):
            ttk.Label(cab, text=rot).grid(row=i // 4, column=(i % 4) * 2, sticky="w", padx=(0, 4))
            v = tk.StringVar()
            ttk.Entry(cab, textvariable=v, width=10).grid(row=i // 4, column=(i % 4) * 2 + 1, sticky="w", padx=(0, 10), pady=1)
            self.vars[k] = v
        self.vars["criterio"] = tk.StringVar()
        ttk.Label(cab, text="Paralisação").grid(row=2, column=0, sticky="w")
        ttk.Combobox(cab, textvariable=self.vars["criterio"], values=list(ts.CRITERIOS), state="readonly", width=24).grid(
            row=2, column=1, columnspan=3, sticky="w")
        self.linhas = []
        self.tab = Tabela(dir_, self.COLS, self.linhas, 14)
        self.tab.ao_mudar = self._mudou
        self.tab.pack(fill="both", expand=True, pady=6)
        b = ttk.Frame(dir_)
        b.pack(fill="x")
        ttk.Button(b, text="+ Leitura", command=self.nova_leitura).pack(side="left")
        ttk.Button(b, text="Remover", command=self.remover_leitura).pack(side="left", padx=4)
        ttk.Button(b, text="Colar do Excel", command=self.colar).pack(side="left")
        ttk.Label(b, text="  (profundidade; NSPT; solo; cor — tabulação ou ponto e vírgula; '>=' antes do NSPT = impenetrável)",
                  foreground="#666").pack(side="left")
        ttk.Button(b, text="OK", command=self.ok).pack(side="right")
        ttk.Button(b, text="Cancelar", command=self.destroy).pack(side="right", padx=4)
        self.recarregar_lista()
        self.grab_set()

    def recarregar_lista(self):
        self.lb.delete(0, "end")
        for n in self.furos:
            self.lb.insert("end", n)
        if self.furos:
            self.lb.selection_set(0)
            self.mostrar()

    def _guardar(self):
        if self.atual is None or self.atual not in self.furos:
            return
        f = self.furos[self.atual]
        try:
            f["cotaTopo_m"] = num(self.vars["cotaTopo_m"].get()) or 0.0
            f["profundidadeFinal_m"] = num(self.vars["profundidadeFinal_m"].get()) or 0.0
            f["naInicial_m"] = num(self.vars["naInicial_m"].get())
            f["naFinal_m"] = num(self.vars["naFinal_m"].get())
            f["coordenadas"] = dict(x=num(self.vars["x"].get()) or 0.0, y=num(self.vars["y"].get()) or 0.0)
        except ValueError:
            pass
        f["criterioParalisacao"] = self.vars["criterio"].get()
        f["leituras"] = [dict(l) for l in self.linhas]
        novo = self.vars["nome"].get().strip()
        if novo and novo != self.atual and novo not in self.furos:
            self.furos = {(novo if k == self.atual else k): v for k, v in self.furos.items()}
            self.atual = novo

    def mostrar(self):
        self._guardar()
        sel = self.lb.curselection()
        if not sel:
            return
        n = self.lb.get(sel[0])
        self.atual = n
        f = self.furos[n]
        self.vars["nome"].set(n)
        for k in ("cotaTopo_m", "profundidadeFinal_m", "naInicial_m", "naFinal_m"):
            self.vars[k].set("" if f.get(k) is None else br(f[k], 2))
        self.vars["x"].set(br(f.get("coordenadas", {}).get("x", 0.0), 2))
        self.vars["y"].set(br(f.get("coordenadas", {}).get("y", 0.0), 2))
        self.vars["criterio"].set(f.get("criterioParalisacao") or "")
        self.linhas[:] = [dict(l) for l in f.get("leituras", [])]
        self.tab.atualizar()

    def _mudou(self, i, k):
        if k == "solo":
            self.linhas[i]["familia"] = ts.familia_do_solo(self.linhas[i]["solo"])

    def novo(self):
        self._guardar()
        n = f"SP-{len(self.furos) + 1:02d}"
        self.furos[n] = dict(cotaTopo_m=self.par["geometria"].get("cota_terreno") or self.par["geometria"]["cota_topo"],
                             profundidadeFinal_m=0.0, criterioParalisacao="", naInicial_m=None, naFinal_m=None,
                             coordenadas=dict(x=0.0, y=0.0), leituras=[])
        self.recarregar_lista()
        self.lb.selection_clear(0, "end")
        self.lb.selection_set("end")
        self.atual = None
        self.mostrar()

    def remover(self):
        sel = self.lb.curselection()
        if sel and messagebox.askyesno(APP, f"Remover o furo {self.lb.get(sel[0])}?", parent=self):
            self.furos.pop(self.lb.get(sel[0]), None)
            self.atual = None
            self.recarregar_lista()

    def nova_leitura(self):
        p = (self.linhas[-1]["profundidade_m"] + 1.0) if self.linhas else 1.0
        solo = self.linhas[-1]["solo"] if self.linhas else "Silte Arenoso"
        self.linhas.append(dict(profundidade_m=p, nspt_real=10.0, impenetravel=False, solo=solo,
                                familia=ts.familia_do_solo(solo), cor=""))
        self.tab.atualizar()

    def remover_leitura(self):
        for i in reversed(self.tab.selecionadas()):
            del self.linhas[i]
        self.tab.atualizar()

    def colar(self):
        try:
            txt = self.clipboard_get()
        except tk.TclError:
            return
        novas = []
        for lin in txt.splitlines():
            c = [x.strip() for x in re.split(r"[;\t]", lin)]
            if len(c) < 2:
                continue
            try:
                prof = num(c[0])
                imp = bool(re.match(r"^(>=|≥|>)", c[1]))
                n = num(re.sub(r"^(>=|≥|>)", "", c[1]))
            except ValueError:
                continue                                         # cabeçalho
            if prof is None or n is None:
                continue
            solo = c[2] if len(c) > 2 else ""
            novas.append(dict(profundidade_m=prof, nspt_real=n, impenetravel=imp or n > 50, solo=solo,
                              familia=ts.familia_do_solo(solo), cor=c[3] if len(c) > 3 else ""))
        if novas:
            self.linhas[:] = novas
            self.tab.atualizar()

    def importar(self):
        arq = filedialog.askopenfilename(parent=self, title="Arquivo do GEOSPT", filetypes=[("GEOSPT", "*.json"), ("Todos", "*.*")])
        if not arq:
            return
        try:
            self.furos, info = ts.ler_geospt(arq)
        except (ValueError, OSError, KeyError) as e:
            messagebox.showerror(APP, str(e), parent=self)
            return
        self.atual = None
        self.recarregar_lista()
        messagebox.showinfo(APP, f"{len(self.furos)} furos de {info.get('obra') or os.path.basename(arq)} ({info['esquema']} {info['versao']}).", parent=self)

    def exportar(self):
        self._guardar()
        arq = filedialog.asksaveasfilename(parent=self, title="Gravar no formato da obra do GEOSPT", defaultextension=".json",
                                           filetypes=[("GEOSPT", "*.json")])
        if arq:
            try:
                ts.gravar_geospt_obra(ts.normalizar_sondagens(self.furos), arq, self.par.get("descricao", ""))
            except ValueError as e:
                messagebox.showerror(APP, str(e), parent=self)

    def ok(self):
        self._guardar()
        try:
            furos = ts.normalizar_sondagens(self.furos)
        except ValueError as e:
            messagebox.showerror(APP, str(e), parent=self)
            return
        self.par["sondagem"]["sondagens"] = furos
        self.destroy()
        self.ao_ok()


class DlgSolo(tk.Toplevel):
    """Perfil de cálculo, métodos e parâmetros por camada (valores do SPT, edição livre)."""
    CAMPOS = [("gama", "γ (kN/m³)", 1), ("gama_sat", "γsat", 1), ("phi", "φ' (°)", 1), ("su", "Su (kPa)", 0),
              ("nh", "nh (kN/m³)", 0), ("kv", "kv (kN/m³)", 0), ("E", "E (kPa)", 0)]

    def __init__(self, master, par, res, ao_ok):
        super().__init__(master)
        self.title("Solo: perfil de cálculo e parâmetros")
        self.transient(master)
        self.par, self.ao_ok = par, ao_ok
        s, sl = par["sondagem"], par["solo"]
        f = ttk.Frame(self, padding=10)
        f.pack(fill="both", expand=True)
        top = ttk.Frame(f)
        top.pack(fill="x")
        self.v = {}
        def combo(r, c, rot, chave, valores, w=26):
            ttk.Label(top, text=rot).grid(row=r, column=c, sticky="w", padx=(0, 4))
            var = tk.StringVar(value=valores.get(caminho_get(par, chave), list(valores.values())[0]))
            ttk.Combobox(top, textvariable=var, values=list(valores.values()), state="readonly", width=w).grid(row=r, column=c + 1, sticky="w", padx=(0, 12), pady=1)
            self.v[chave] = (var, valores)
        def campo(r, c, rot, chave, w=10):
            ttk.Label(top, text=rot).grid(row=r, column=c, sticky="w", padx=(0, 4))
            x = caminho_get(par, chave)
            var = tk.StringVar(value="" if x is None else br(x, 3).rstrip("0").rstrip(","))
            ttk.Entry(top, textvariable=var, width=w).grid(row=r, column=c + 1, sticky="w", padx=(0, 12), pady=1)
            self.v[chave] = (var, None)
        combo(0, 0, "Ruptura lateral (p_u)", "solo.metodo_pu", so.METODOS_PU)
        combo(0, 2, "φ' pelo SPT", "solo.metodo_phi", so.METODOS_PHI, 34)
        combo(1, 0, "Sondagem média (submodo)", "sondagem.submodo", {k: k for k in ts.SUBMODOS})
        campo(1, 2, "Janela de compatibilização (m)", "sondagem.janela")
        campo(2, 0, "σadm (kPa; vazio = Alonso)", "solo.sigma_adm")
        campo(2, 2, "FS da base (q_ult = FS·σadm)", "solo.fs_base")
        campo(3, 0, "Cota do NA (vazio = dos furos)", "sondagem.na")
        campo(3, 2, "Δ nas cotas da sondagem (m)", "sondagem.delta")
        self.vm = tk.BooleanVar(value="media" in s["perfis"])
        self.ve = tk.BooleanVar(value="envoltoria" in s["perfis"])
        self.vas = tk.BooleanVar(value=sl["atrito_base_servico"])
        self.var_ = tk.BooleanVar(value=sl["atrito_base_ruptura"])
        cb = ttk.Frame(f)
        cb.pack(fill="x", pady=4)
        ttk.Label(cb, text="Perfis de cálculo:").pack(side="left")
        ttk.Checkbutton(cb, text="sondagem média", variable=self.vm).pack(side="left", padx=4)
        ttk.Checkbutton(cb, text="envoltória mínima", variable=self.ve).pack(side="left", padx=4)
        ttk.Label(cb, text="   Atrito na base:").pack(side="left")
        ttk.Checkbutton(cb, text="em serviço", variable=self.vas).pack(side="left", padx=4)
        ttk.Checkbutton(cb, text="na ruptura", variable=self.var_).pack(side="left", padx=4)
        # camadas do último cálculo, com as edições
        ed = {round(float(e["cota_m"]), 3): e for e in sl.get("edicoes", [])}
        self.linhas = []
        if res:
            pf = res["solo"]["perfis"][0]
            for c in pf["camadas"]:
                if c.get("extrapolada"):
                    continue
                e = ed.get(round(c["cota_m"], 3), {})
                l = dict(cota_m=c["cota_m"], N=c["nspt"], solo=c["solo"], comportamento=e.get("comportamento") or c["comportamento"])
                for k, _, _ in self.CAMPOS:
                    l[k] = e.get(k, round(c[k], 2))
                l["_calc"] = {k: round(c[k], 2) for k, _, _ in self.CAMPOS}
                l["_calc"]["comportamento"] = c["comportamento"]
                self.linhas.append(l)
        ttk.Label(f, text=f"Camadas ({res['solo']['perfis'][0]['rotulo'] if res else 'calcule antes para ver as camadas'}): duplo clique "
                          "para trocar um valor; o valor digitado vale nos dois perfis, na mesma cota.", foreground="#444").pack(anchor="w", pady=(6, 0))
        cols = [("cota_m", "Cota", 60, "info"), ("N", "N", 40, "info"), ("solo", "Solo", 140, "info"),
                ("comportamento", "Comportamento", 110, "combo", ["drenado", "nao_drenado"])] + \
               [(k, t, 80, "float") for k, t, _ in self.CAMPOS]
        self.tab = Tabela(f, cols, self.linhas, 12)
        self.tab.pack(fill="both", expand=True, pady=6)
        b = ttk.Frame(f)
        b.pack(fill="x")
        ttk.Button(b, text="Limpar edições", command=self.limpar).pack(side="left")
        ttk.Button(b, text="OK", command=self.ok).pack(side="right")
        ttk.Button(b, text="Cancelar", command=self.destroy).pack(side="right", padx=4)
        self.grab_set()

    def limpar(self):
        for l in self.linhas:
            for k, v in l["_calc"].items():
                l[k] = v
        self.tab.atualizar()

    def ok(self):
        for chave, (var, valores) in self.v.items():
            x = var.get()
            if valores:
                caminho_set(self.par, chave, next(k for k, v in valores.items() if v == x))
            else:
                try:
                    caminho_set(self.par, chave, num(x) if chave != "sondagem.delta" else (num(x) or 0.0))
                except ValueError:
                    messagebox.showerror(APP, f"Valor inválido em {chave}.", parent=self)
                    return
        perfis = (["media"] if self.vm.get() else []) + (["envoltoria"] if self.ve.get() else [])
        self.par["sondagem"]["perfis"] = perfis or ["envoltoria"]
        self.par["solo"]["atrito_base_servico"] = self.vas.get()
        self.par["solo"]["atrito_base_ruptura"] = self.var_.get()
        edicoes = []
        for l in self.linhas:
            e = {k: l[k] for k, _, _ in self.CAMPOS if l[k] is not None and abs(float(l[k]) - l["_calc"][k]) > 1e-6}
            if l["comportamento"] != l["_calc"]["comportamento"]:
                e["comportamento"] = l["comportamento"]
            if e:
                e["cota_m"] = l["cota_m"]
                edicoes.append(e)
        if self.linhas or not edicoes:
            self.par["solo"]["edicoes"] = edicoes
        self.destroy()
        self.ao_ok()


# ------------------------------------------------------------------------------------------------ janela
class App(tk.Tk):
    VISTAS = (("elevacao", "Elevação"), ("base", "Base"), ("ruptura", "Ruptura"), ("esforcos", "Esforços"),
              ("sondagens", "Sondagens"), ("mapa", "Mapa D x L"), ("desenho", "Desenho"), ("verificacoes", "Verificações"))

    def __init__(self, arquivo=None):
        super().__init__()
        self.title(TITULO)
        self.geometry("1500x920+30+20")
        try:
            self.iconphoto(True, ic.foto("tubulao", 32), ic.foto("tubulao", 16))
        except tk.TclError:
            pass
        self.par, self.arquivo, self.res, self.modificado, self.calculando = None, None, None, False, False
        self.mapa_dim, self.mapa_sig = None, None                     # última varredura D x L
        self.tabela_tqs, self.tx_prev = None, None                     # tabela de ferros do último DWG e textos da prévia
        self.vista, self.i_perfil, self.i_comb = "elevacao", 0, None
        self.fila = queue.Queue()                    # resultados das threads: só a thread principal mexe no Tk
        self._montar()
        self._job = self.after(100, self._sondar)
        self.after(50, lambda: self.state("zoomed"))
        if arquivo:
            self.abrir(arquivo)
        else:
            ex = os.path.join(AQUI, "exemplos", "T1_poste_DT600.json")
            self.abrir(ex) if os.path.exists(ex) else self.novo()
        self.after(300, self._avisar_tqs)

    def _avisar_tqs(self):
        """Sem o TQS pronto para gravar, avisa uma vez ao abrir: o cálculo, a memória, o 3D e a prévia funcionam."""
        itens = dep.conferir(tqs=True)
        if dep.faltas(itens):
            messagebox.showwarning(APP, dep.mensagem_faltas(itens, "gravar o DWG")
                                   + "\n\nO cálculo, a memória, o 3D e a prévia do desenho funcionam sem o TQS.", parent=self)

    # ---------------------------------------------------------------- montagem
    def _montar(self):
        st = ttk.Style(self)
        st.configure("Treeview", font=FONTE, rowheight=20)
        menu = tk.Menu(self, tearoff=0)
        for txt, cmd in (("Novo", self.novo), ("Abrir...", self.abrir), ("Salvar", self.salvar), ("Salvar como...", self.salvar_como),
                         (None, None), ("Abrir a pasta de saída", self.abrir_pasta), (None, None), ("Sair", self.sair)):
            menu.add_separator() if txt is None else menu.add_command(label=txt, command=cmd)
        topo = tk.Frame(self, bg=rbn.COR_FUNDO)
        topo.pack(side="top", fill="x")
        br_ = rbn.BarraRapida(topo)
        br_.pack(side="top", anchor="w")
        for icn, dica, cmd in (("novo", "Novo", self.novo), ("abrir", "Abrir", self.abrir), ("salvar", "Salvar (Ctrl+S)", self.salvar),
                               ("calcular", "Calcular (F5)", self.calcular)):
            br_.botao(icn, dica, cmd)
        rb = rbn.Ribbon(topo, menu_app=menu, rotulo_app="Tubulões")
        rb.pack(side="top", fill="x")
        a = rb.aba("Tubulão")
        g = a.grupo("Dados")
        g.grande("tubulao", "Geometria e camisa", self.dlg_geometria, dica="Diâmetro, comprimento, cotas, anéis, folga e lastro")
        c = g.coluna()
        c.pequeno("parametros", "Materiais...", self.dlg_materiais)
        c.pequeno("pilar", "Apoio (pilar ou poste)...", self.dlg_apoio)
        c.pequeno("notas", "Identificação...", self.dlg_ident)
        g = a.grupo("Cálculo")
        g.grande("calcular", "Calcular", self.calcular, dica="Calcula todas as verificações (F5)")
        g.grande("dimensionar", "Dimensionar D x L", self.dlg_dimensionar, dica="Varre diâmetros e comprimentos e escolhe a menor solução que passa")
        a = rb.aba("Sondagem")
        g = a.grupo("Sondagens")
        g.grande("sondagem", "Furos e leituras", self.dlg_sondagens, dica="Cadastro como no GEOSPT; importa e exporta o arquivo da obra")
        g.grande("solo", "Solo e parâmetros", self.dlg_solo, dica="Perfil de cálculo (média, mínima), métodos, σadm e parâmetros por camada")
        a = rb.aba("Cargas")
        g = a.grupo("Ações")
        g.grande("cargas", "Ações características", self.dlg_acoes, dica="N, H e M por ação; o app monta as combinações")
        g.grande("tabela", "Combinações", lambda: self.mostrar_vista("combinacoes"))
        a = rb.aba("Critérios")
        g = a.grupo("Verificações")
        g.grande("verificar", "Critérios e limites", self.dlg_criterios, dica="FS, limites de deslocamento, recalque, área comprimida")
        a = rb.aba("Exibir")
        g = a.grupo("Vistas")
        for k, t in self.VISTAS:
            ico = {"elevacao": "tubulao", "base": "placas", "ruptura": "ruptura", "esforcos": "barra", "sondagens": "sondagem",
                   "mapa": "dimensionar", "desenho": "prancha", "verificacoes": "ok"}[k]
            g.grande(ico, t, lambda k=k: self.mostrar_vista(k))
        a = rb.aba("Saídas")
        g = a.grupo("Gerar")
        g.grande("memoria", "Memória de cálculo", self.gerar_memoria, dica="HTML e PDF (sem referência à empresa)")
        g.grande("tres_d", "Ver em 3D", self.gerar_3d)
        g.grande("gerar", "DWG, PDF e DXF", self.gerar_dwg, dica="Desenho em DWG TQS com ferros inteligentes e $QUANT")
        g.grande("previa", "Gerar tudo", self.gerar_tudo)
        c = g.coluna()
        c.pequeno("pasta", "Abrir a pasta de saída", self.abrir_pasta)
        c.pequeno("parametros", "Opções de saída...", self.dlg_saidas)
        # corpo
        corpo = ttk.PanedWindow(self, orient="horizontal")
        corpo.pack(fill="both", expand=True)
        esq = ttk.PanedWindow(corpo, orient="vertical")
        corpo.add(esq, weight=0)
        fa = ttk.Frame(esq)
        ttk.Label(fa, text=" Projeto", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.arvore = ttk.Treeview(fa, show="tree", height=18)
        self.arvore.pack(fill="both", expand=True)
        self.arvore.bind("<<TreeviewSelect>>", self._sel_arvore)
        self.arvore.bind("<Double-1>", self._duplo_arvore)
        esq.add(fa, weight=3)
        fp = ttk.Frame(esq)
        ttk.Label(fp, text=" Propriedades", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.props = ttk.Treeview(fp, columns=("v",), show="tree headings", height=12)
        self.props.heading("#0", text="Item")
        self.props.heading("v", text="Valor")
        self.props.column("#0", width=170)
        self.props.column("v", width=150)
        self.props.pack(fill="both", expand=True)
        esq.add(fp, weight=2)
        centro = ttk.Frame(corpo)
        corpo.add(centro, weight=1)
        barra = ttk.Frame(centro)
        barra.pack(fill="x")
        ttk.Label(barra, text=" Perfil:").pack(side="left")
        self.cb_perfil = ttk.Combobox(barra, state="readonly", width=30)
        self.cb_perfil.pack(side="left")
        self.cb_perfil.bind("<<ComboboxSelected>>", lambda e: self._troca_perfil())
        ttk.Label(barra, text="  Combinação:").pack(side="left")
        self.cb_comb = ttk.Combobox(barra, state="readonly", width=70)
        self.cb_comb.pack(side="left")
        self.cb_comb.bind("<<ComboboxSelected>>", lambda e: self._troca_comb())
        self.lb_vista = ttk.Label(barra, text="", font=("Segoe UI", 9, "bold"))
        self.lb_vista.pack(side="right", padx=8)
        self.area = tk.Frame(centro, bg=FUNDO_CAD)
        self.area.pack(fill="both", expand=True)
        self.fig = Figure(facecolor=FUNDO_CAD)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.area)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        tb = NavigationToolbar2Tk(self.canvas, centro, pack_toolbar=False)
        tb.update()
        tb.pack(fill="x")
        self.tb = tb
        self._hover = self._click = self._hover_ann = None          # dica sob o mouse e clique, definidos por vista
        self.canvas.mpl_connect("motion_notify_event", self._mouse_move)
        self.canvas.mpl_connect("button_press_event", self._mouse_click)
        self.tab_frame = ttk.Frame(self.area)
        self.tab_tv = ttk.Treeview(self.tab_frame, show="headings")
        sb = ttk.Scrollbar(self.tab_frame, orient="vertical", command=self.tab_tv.yview)
        self.tab_tv.configure(yscrollcommand=sb.set)
        self.tab_tv.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        self.tab_tv.tag_configure("nok", foreground="#c62828")
        msg = ttk.Frame(self)
        msg.pack(fill="x")
        self.txt = tk.Text(msg, height=6, font=("Consolas", 9), bg="#fbfbfb", relief="flat")
        self.txt.pack(fill="x")
        self.txt.tag_configure("erro", foreground="#c62828")
        self.txt.tag_configure("aviso", foreground="#9a6700")
        self.txt.tag_configure("info", foreground="#555555")
        self.txt.tag_configure("ok", foreground="#1b7a2f")
        self.status = ttk.Label(self, text="", anchor="w", relief="sunken")
        self.status.pack(fill="x")
        self.bind("<F5>", lambda e: self.calcular())
        self.bind("<Control-s>", lambda e: self.salvar())
        self.protocol("WM_DELETE_WINDOW", self.sair)

    # ---------------------------------------------------------------- arquivo
    def pasta_base(self):
        return os.path.dirname(os.path.abspath(self.arquivo)) if self.arquivo else os.path.join(AQUI, "exemplos")

    def novo(self):
        if not self._descartar():
            return
        self.par = copy.deepcopy(tcore.PADROES)
        self.par["acoes"] = [dict(nome="G", tipo="permanente", N=100.0, Hx=0.0, Hy=0.0, Mx=0.0, My=0.0)]
        self.par["camisa"]["usar"] = False
        self.par["geometria"]["D"] = 1.0
        self.arquivo, self.res, self.modificado = None, None, False
        self.mapa_dim, self.mapa_sig = None, None
        self._titulo()
        self.atualizar_tudo()
        self.msg("Projeto novo: cadastre as sondagens (aba Sondagem) e as ações (aba Cargas) e calcule (F5).", "ok")

    def abrir(self, arq=None):
        if arq is None:
            if not self._descartar():
                return
            arq = filedialog.askopenfilename(title="Abrir projeto de tubulão", initialdir=os.path.join(AQUI, "exemplos"),
                                             filetypes=[("Projeto", "*.json"), ("Todos", "*.*")])
            if not arq:
                return
        try:
            self.par = tcore._mesclar(tcore.PADROES, json.load(open(arq, encoding="utf-8")))
        except (OSError, ValueError) as e:
            messagebox.showerror(APP, f"Não abri {arq}: {e}")
            return
        self.arquivo, self.res, self.modificado = arq, None, False
        self.mapa_dim, self.mapa_sig = None, None
        self._titulo()
        self.atualizar_tudo()
        self.calcular()

    def salvar(self):
        if not self.arquivo:
            return self.salvar_como()
        par = {k: v for k, v in self.par.items() if not k.startswith("_")}
        with open(self.arquivo, "w", encoding="utf-8") as f:
            json.dump(par, f, ensure_ascii=False, indent=2)
        self.modificado = False
        self._titulo()
        self.msg(f"Projeto gravado: {self.arquivo}", "ok")

    def salvar_como(self):
        arq = filedialog.asksaveasfilename(title="Salvar projeto", defaultextension=".json", initialfile=f"{self.par['nome']}.json",
                                           initialdir=self.pasta_base(), filetypes=[("Projeto", "*.json")])
        if arq:
            s = self.par["sondagem"]
            if s.get("arquivo") and not os.path.isabs(s["arquivo"]):           # caminho relativo à nova pasta
                s["arquivo"] = os.path.relpath(os.path.join(self.pasta_base(), s["arquivo"]), os.path.dirname(arq))
            self.arquivo = arq
            self.salvar()

    def _descartar(self):
        if self.modificado:
            r = messagebox.askyesnocancel(APP, "Gravar as alterações do projeto atual?")
            if r is None:
                return False
            if r:
                self.salvar()
        return True

    def sair(self):
        if self._descartar():
            self.destroy()

    def _titulo(self):
        nome = os.path.basename(self.arquivo) if self.arquivo else "(sem nome)"
        self.title(f"{TITULO} - [{self.par['nome']} - {nome}]" + (" *" if self.modificado else ""))

    def alterado(self):
        self.modificado = True
        self._titulo()
        self.atualizar_arvore()
        self.calcular()

    # ---------------------------------------------------------------- diálogos
    def dlg_ident(self):
        Formulario(self, "Identificação", self.par, [("nome", "Nome do tubulão", "str", None), ("descricao", "Descrição", "str", None),
                                                    ("quantidade", "Quantidade de tubulões iguais", "int", None)], self.alterado)

    def dlg_geometria(self):
        cat = [(c["DN"], f"DN {c['DN']:.2f} (parede {c['e'] * 100:.0f} cm)") for c in tcore.CATALOGO_ANEIS]
        Formulario(self, "Geometria e camisa", self.par, [
            ("", "Tubulão", "titulo", None),
            ("geometria.L", "Comprimento L (m)", "float", None),
            ("geometria.D", "Diâmetro D (m) — sem camisa", "float", None),
            ("geometria.cota_topo", "Cota do topo (m)", "float", None),
            ("geometria.cota_terreno", "Cota do terreno (m)", "float", None),
            ("geometria.desprezar_topo", "Trecho desprezado no topo (m)", "float", None),
            ("", "Camisa de anéis pré-moldados", "titulo", None),
            ("camisa.usar", "Usar camisa de anéis (forma perdida)", "bool", None),
            ("camisa.DN", "Anel (DN interno)", "combo", cat),
            ("camisa.espessura", "Parede do anel (m; vazio = catálogo)", "float", None),
            ("camisa.altura", "Altura do anel (m)", "float", None),
            ("folga.largura", "Folga anel-solo (m)", "float", None),
            ("folga.preenchimento", "Preenchimento da folga", "combo", [("autoadensavel", "autoadensável (padrão)"),
                                                                       ("solo_cimento_compactado", "solo-cimento compactado"),
                                                                       ("nenhuma", "sem folga")]),
            ("", "Lastro", "titulo", None),
            ("lastro.espessura", "Espessura (m)", "float", None),
            ("lastro.material", "Material", "str", None)], self.alterado)

    def dlg_materiais(self):
        Formulario(self, "Materiais", self.par, [
            ("materiais.fck", "fck (MPa)", "float", None), ("materiais.fyk", "fyk (MPa)", "float", None),
            ("materiais.cobrimento", "Cobrimento (m)", "float", None),
            ("materiais.caa", "Classe de agressividade", "combo", ["I", "II", "III", "IV"]),
            ("materiais.gama_c", "Peso específico do concreto (kN/m³)", "float", None),
            ("materiais.agregado", "Agregado (módulo)", "combo", ["granito", "gnaisse", "basalto", "diabasio", "calcario", "arenito"])],
            self.alterado)

    def dlg_apoio(self):
        Formulario(self, "Apoio no topo", self.par, [
            ("apoio.tipo", "Tipo", "combo", [("nenhum", "nenhum"), ("pilar", "pilar apoiado direto"), ("poste", "poste embutido")]),
            ("apoio.secao", "Seção do pilar", "combo", [("retangular", "retangular"), ("circular", "circular")]),
            ("apoio.a", "Pilar: lado em x (m)", "float", None), ("apoio.b", "Pilar: lado em y (m)", "float", None),
            ("apoio.d", "Pilar circular: diâmetro (m)", "float", None),
            ("apoio.h_aplicacao", "Altura do ponto de aplicação de H acima do topo (m)", "float", None),
            ("apoio.embutimento", "Poste: embutimento (m)", "float", None),
            ("apoio.area_secao", "Poste: área da seção (m²)", "float", None)], self.alterado)

    def dlg_criterios(self):
        Formulario(self, "Critérios e limites", self.par, [
            ("", "Ruptura e empuxo (NBR 6122:2022)", "titulo", None),
            ("criterios.tombamento", "Verificação ao tombamento", "combo",
             [("calculo", "valores de cálculo (6.2.1.1.2): λd ≥ γf"), ("global", "FS global mínimo")]),
            ("criterios.gama_m_solo", "γm da resistência do solo (6.2.1.1.2)", "float", None),
            ("criterios.gama_m_peso", "γm do peso favorável (6.2.1.1.2)", "float", None),
            ("criterios.gama_f_tombamento", "γf das ações (6.2.1.1.2)", "float", None),
            ("criterios.fs_tombamento", "FS global mínimo (opção global; referência)", "float", None),
            ("criterios.fs_passivo", "Redução do empuxo passivo (7.6.3)", "float", None),
            ("criterios.theta_ruptura", "Rotação convencional de ruptura (rad)", "float", None),
            ("criterios.fs_criterio", "λ adotado", "combo", [("min", "menor entre equilíbrio limite e pushover"),
                                                            ("le", "equilíbrio limite"), ("pushover", "pushover")]),
            ("", "Base (NBR 6122:2022)", "titulo", None),
            ("criterios.fator_sigma_vento", "Majoração de σadm com vento principal (6.3.2: até 1,15)", "float", None),
            ("criterios.vento_obra_lista", "Obra da lista do 6.3.2 (torres, galpões, silos...: até 1,30)", "bool", None),
            ("criterios.area_comprimida_min", "Área comprimida mínima, características (7.6.2: 2/3)", "float", None),
            ("criterios.area_comprimida_qp", "Área comprimida, quase permanente (critério do app)", "float", None),
            ("", "Deslocamentos e recalque", "titulo", None),
            ("criterios.rotacao_lim_poste", "Rotação máxima com poste (tg α; Sulzberger: 0,01)", "float", None),
            ("criterios.rotacao_lim", "Rotação máxima com pilar ou sem apoio (rad; padrão 1/200)", "float", None),
            ("criterios.desloc_aplicacao_lim", "Deslocamento no ponto de aplicação (m; vazio = não verifica)", "float", None),
            ("criterios.recalque_lim", "Recalque máximo (m)", "float", None),
            ("", "Estrutura", "titulo", None),
            ("criterios.concreto_simples", "Tentar concreto simples (NBR 6118, Seção 24)", "bool", None),
            ("criterios.as_min_fuste", "Armadura mínima do fuste armado (fração; NBR 6122 Tab. 4: 0,004)", "float", None),
            ("criterios.comp_min_armadura", "Comprimento mínimo da armadura (m; Tab. 4: 3,0)", "float", None),
            ("criterios.sacrificio_barras", "Redução do diâmetro das barras (mm; NBR 6122 8.6.2)", "float", None),
            ("", "Fretagem do topo (pilar apoiado direto)", "titulo", None),
            ("criterios.fretagem_arranjo", "Arranjo", "combo", [("auto", "automático: grelha se a/D < limite, senão anéis"),
                                                                ("aneis", "só anéis (fendilhamento anelar)"),
                                                                ("grelha", "grelha nas duas direções + anéis construtivos")]),
            ("criterios.fretagem_a_d_limite", "Limite a/D do automático", "float", None),
            ("criterios.grelha_espac_camadas", "Grelha: espaçamento das camadas (m)", "float", None),
            ("criterios.grelha_espac_barras", "Grelha: espaçamento das barras em planta (m)", "float", None),
            ("criterios.grelha_min_barras", "Grelha: mínimo de barras por camada e direção", "int", None),
            ("criterios.aneis_construtivos_s", "Anéis construtivos: espaçamento (m)", "float", None),
            ("criterios.montagem_bitola", "Barras de montagem: bitola (mm)", "float", None),
            ("criterios.montagem_espac_max", "Barras de montagem: espaçamento máximo (m)", "float", None),
            ("criterios.montagem_min", "Barras de montagem: quantidade mínima", "int", None),
            ("criterios.z_rigido", "Z máximo para corpo rígido", "float", None)], self.alterado)

    def dlg_dimensionar(self):
        dm = self.par["dimensionamento"]
        txt = "; ".join(br(d, 2) for d in (dm.get("D_lista") or []))
        par = {"automatico": True, "D": txt, "L_min": dm["L_min"], "L_max": dm["L_max"], "L_passo": dm.get("L_passo")}

        def ok():
            dm["automatico"] = bool(par["automatico"])
            try:
                dm["D_lista"] = [num(x) for x in re.split(r"[;\s]+", str(par["D"]).strip()) if x] or None
            except ValueError:
                dm["D_lista"] = None
            dm["L_min"], dm["L_max"], dm["L_passo"] = par["L_min"], par["L_max"], par["L_passo"]
            dm.pop("escolha_usuario", None)                            # nova varredura: volta à solução ótima
            self.alterado()
        Formulario(self, "Dimensionamento automático (D x L)", par, [
            ("automatico", "Dimensionar automaticamente ao calcular", "bool", None),
            ("D", "Diâmetros (m; vazio = catálogo de anéis ou 0,60 a 2,00)", "str", None),
            ("L_min", "L mínimo (m)", "float", None), ("L_max", "L máximo (m)", "float", None),
            ("L_passo", "Passo de L (m; vazio = altura do anel ou 0,25)", "float", None)], ok)

    def dlg_saidas(self):
        Formulario(self, "Opções de saída", self.par, [
            ("saidas.pasta", "Pasta de saída (vazio = saidas\\<nome>)", "str", None), ("saidas.escala", "Escala do desenho 1:", "float", None),
            ("saidas.pdf", "PDF do desenho", "bool", None), ("saidas.dxf", "DXF do desenho", "bool", None),
            ("saidas.dxf_plotagem", "DXF com as cores da plotagem", "bool", None), ("saidas.memoria_pdf", "PDF da memória", "bool", None),
            ("saidas.quant_resumo", "Bloco $QUANT no desenho", "bool", None),
            ("saidas.sondagens_desenho", "Sondagens ao lado da elevação no desenho", "bool", None)], self._saidas_alteradas)

    def _saidas_alteradas(self):
        self.modificado = True
        self._titulo()
        if self.res:                                                   # a prévia segue as opções sem recalcular
            for k in ("escala", "quant_resumo", "sondagens_desenho"):
                self.res["p"]["saidas"][k] = self.par["saidas"][k]
            self.tabela_tqs = None
            if self.vista == "desenho":
                self.desenhar()

    def dlg_acoes(self):
        DlgAcoes(self, self.par, self.alterado)

    def dlg_sondagens(self):
        DlgSondagens(self, self.par, self.alterado, self.pasta_base())

    def dlg_solo(self):
        DlgSolo(self, self.par, self.res, self.alterado)

    # ---------------------------------------------------------------- threads
    def _sondar(self):
        try:
            while True:
                f = self.fila.get_nowait()
                f()
        except queue.Empty:
            pass
        self._job = self.after(100, self._sondar)

    def destroy(self):
        try:
            self.after_cancel(self._job)
        except (tk.TclError, AttributeError):
            pass
        super().destroy()

    # ---------------------------------------------------------------- cálculo
    @staticmethod
    def _assinatura(par):
        q = copy.deepcopy(par)
        for k in ("dimensionamento", "saidas", "nome", "descricao", "quantidade"):
            q.pop(k, None)
        q.get("geometria", {}).pop("D", None)
        q.get("geometria", {}).pop("L", None)
        q.get("camisa", {}).pop("DN", None)
        q.get("camisa", {}).pop("espessura", None)
        return json.dumps(q, sort_keys=True, ensure_ascii=False, default=str)

    def _mapa_valido(self):
        return bool(self.mapa_dim) and self.mapa_sig == self._assinatura(self.par)

    def _anexar_mapa(self, res):
        """Põe no resultado a última varredura (se os dados não mudaram), marcando a célula da geometria atual."""
        if res.get("dimensionamento") or not self._mapa_valido():
            return
        g = res["p"]["geometria"]
        d = dict(self.mapa_dim)
        cel = next((m for m in d["mapa"] if abs(m["D"] - g["D"]) < 1e-6 and abs(m["L"] - g["L"]) < 1e-6), None)
        o = d.get("otima")
        d["escolha"] = cel
        d["usuario"] = bool(cel and o and (abs(cel["D"] - o["D"]) > 1e-6 or abs(cel["L"] - o["L"]) > 1e-6))
        res["dimensionamento"] = d
        if d["usuario"]:
            self.msg(f"Solução adotada no mapa D x L: D = {br(cel['D'])} m, L = {br(cel['L'])} m (a ótima é D = {br(o['D'])} m, "
                     f"L = {br(o['L'])} m).", "ok")

    def calcular(self):
        if self.calculando or self.par is None:
            return
        self.calculando = True
        self.status.configure(text="Calculando...")
        par = copy.deepcopy(self.par)
        base = self.pasta_base()

        def tarefa():
            try:
                res = tcore.calcular(par, base)
                self.fila.put(lambda: self._calculado(res, None))
            except Exception as e:                                     # noqa: BLE001 (mostrado ao usuário)
                tb = traceback.format_exc()
                self.fila.put(lambda: self._calculado(None, (e, tb)))
        threading.Thread(target=tarefa, daemon=True).start()

    def _calculado(self, res, erro):
        self.calculando = False
        self.txt.delete("1.0", "end")
        if erro:
            self.res = None
            self.msg(f"Erro no cálculo:\n{erro[0]}", "erro")
            self.status.configure(text="Erro no cálculo")
            self.atualizar_tudo()
            return
        self.res = res
        if res.get("dimensionamento"):
            self.mapa_dim = dict(res["dimensionamento"])
            self.mapa_dim.setdefault("otima", self.mapa_dim.get("escolha"))
            self.mapa_sig = self._assinatura(self.par)
        if res.get("dimensionamento") and res["dimensionamento"].get("escolha"):
            esc = res["dimensionamento"]["escolha"]
            self.par["geometria"]["L"] = esc["L"]
            if esc["DN"] is not None:
                self.par["camisa"]["DN"] = esc["DN"]
                self.par["camisa"]["espessura"] = None
            else:
                self.par["geometria"]["D"] = esc["D"]
            self.par["dimensionamento"]["automatico"] = False
            self.modificado = True
            self._titulo()
            self.msg(f"Dimensionamento: escolhida D = {br(esc['D'])} m, L = {br(esc['L'])} m (a varredura fica no mapa D x L, onde "
                     "um clique adota outra solução; o dimensionamento automático foi desligado para não refazer a cada mudança).", "ok")
        else:
            self._anexar_mapa(res)
        falhas = [c for c in res["verificacoes"] if not c["ok"]]
        self.msg(f"{'Tudo atende.' if res['ok'] else 'Há verificações não atendidas.'} {len(res['verificacoes'])} verificações, "
                 f"{len(falhas)} não atendidas ({res['tempo']:.1f} s).", "ok" if res["ok"] else "erro")
        vistos = set()
        for c in falhas:
            k = (c["nome"], c["perfil"])
            if k in vistos:
                continue
            vistos.add(k)
            self.msg(f"  NÃO ATENDE: {c['grupo']} — {c['nome']}: {c['valor']:.4g} (limite {c['limite']}) [{c['perfil']}]", "erro")
        for n, m in res["alertas"]:
            self.msg(f"  [{n}] {m}", "erro" if n == "erro" else ("info" if n == "info" else "aviso"))
        gv = res["governante"]
        self.status.configure(text=f"D = {br(res['p']['geometria']['D'])} m, L = {br(res['p']['geometria']['L'])} m — governa: "
                                   f"{gv['nome'] if gv else '—'} ({br(gv['aproveitamento']) if gv else ''})")
        self.atualizar_tudo()

    def msg(self, t, tag=None):
        self.txt.insert("end", t + "\n", tag)
        self.txt.see("end")

    # ---------------------------------------------------------------- árvore e propriedades
    def atualizar_tudo(self):
        self.atualizar_arvore()
        self.atualizar_combos()
        self.desenhar()

    def atualizar_arvore(self):
        a = self.arvore
        a.delete(*a.get_children())
        if not self.par:
            return
        p = self.par
        r = a.insert("", "end", "proj", text=f"Tubulão {p['nome']} ({p['quantidade']}x)", open=True)
        a.insert(r, "end", "geo", text="Geometria e camisa")
        a.insert(r, "end", "mat", text="Materiais")
        a.insert(r, "end", "apo", text=f"Apoio: {p['apoio']['tipo']}")
        ac = a.insert(r, "end", "acoes", text=f"Ações ({len(p['acoes'])})", open=True)
        for i, x in enumerate(p["acoes"]):
            a.insert(ac, "end", f"acao:{i}", text=x["nome"])
        sd = p["sondagem"]
        n = len(sd["sondagens"]) if sd.get("sondagens") else (os.path.basename(sd["arquivo"]) if sd.get("arquivo") else 0)
        a.insert(r, "end", "sond", text=f"Sondagens ({n})")
        a.insert(r, "end", "solo", text=f"Solo: {so.METODOS_PU.get(p['solo']['metodo_pu'], '')}")
        a.insert(r, "end", "crit", text="Critérios")
        if self.res:
            rr = a.insert(r, "end", "res", text="Resultados" + ("" if self.res["ok"] else "  (não atende)"), open=True)
            for i, ap in enumerate(self.res["analises"]):
                pf = a.insert(rr, "end", f"perfil:{i}", text=ap["rotulo"], open=False)
                for j, e in enumerate(ap["servico"]):
                    a.insert(pf, "end", f"comb:{i}:{j}", text=e["nome"])
            a.insert(rr, "end", "verif", text="Verificações")

    def _sel_arvore(self, _=None):
        sel = self.arvore.selection()
        if not sel:
            return
        k = sel[0]
        self.props.delete(*self.props.get_children())
        p = self.par
        def prop(t, v):
            self.props.insert("", "end", text=t, values=(v,))
        if k == "geo":
            g, cm = p["geometria"], p["camisa"]
            for t, v in (("L (m)", g["L"]), ("D (m)", g.get("D")), ("Cota do topo", g["cota_topo"]), ("Cota do terreno", g.get("cota_terreno")),
                         ("Camisa", "anéis DN %s" % cm.get("DN") if cm["usar"] else "não"), ("Folga (m)", p["folga"]["largura"]),
                         ("Preenchimento", p["folga"]["preenchimento"]), ("Lastro (m)", p["lastro"]["espessura"])):
                prop(t, v)
        elif k == "mat":
            for kk, v in p["materiais"].items():
                prop(kk, v)
        elif k == "apo":
            for kk, v in p["apoio"].items():
                prop(kk, v)
        elif k.startswith("acao:"):
            x = p["acoes"][int(k[5:])]
            for kk in ("tipo", "categoria", "grupo", "N", "Hx", "Hy", "Mx", "My"):
                if kk in x:
                    prop(kk, x[kk])
        elif k == "crit":
            for kk, v in p["criterios"].items():
                prop(kk, v)
        elif k == "solo":
            for kk in ("metodo_pu", "metodo_phi", "sigma_adm", "fs_base"):
                prop(kk, p["solo"][kk])
            prop("perfis", ", ".join(p["sondagem"]["perfis"]))
        elif k.startswith("perfil:") and self.res:
            ap = self.res["analises"][int(k[7:])]
            for t, v in (("σadm (kPa)", br(ap["sigma_adm"], 1)), ("q_ult (kPa)", br(ap["q_ult"], 1)), ("Z = L/T", br(ap["rigidez"]["Z"])),
                         ("Peso efetivo (kN)", br(ap["W"], 1)), ("kv (MN/m³)", br(ap["kv"] / 1000, 1))):
                prop(t, v)
            self.i_perfil = int(k[7:])
            self.atualizar_combos()
            self.desenhar()
        elif k.startswith("comb:") and self.res:
            _, i, j = k.split(":")
            self.i_perfil, self.i_comb = int(i), int(j)
            e = self.res["analises"][self.i_perfil]["servico"][self.i_comb]
            for t, v in (("Rotação (‰)", br(e["theta"] * 1000, 3)), ("u topo (mm)", br(e["u_topo"] * 1000, 2)),
                         ("z0 (m)", br(e["z0"]) if e["z0"] is not None else "—"), ("p máx (kPa)", br(e["p_max"], 1)),
                         ("Área comprimida (%)", br(e["area_comp"] * 100, 0)), ("Mobilização", br(max(e["mob"]), 3)),
                         ("FS global", br(e["lam"])), ("λd (valores de cálculo)", br(e.get("lam_d")))):
                prop(t, v)
            self.atualizar_combos()
            if self.vista not in ("elevacao", "base"):
                self.vista = "elevacao"
            self.desenhar()
        elif k == "verif":
            self.mostrar_vista("verificacoes")
        elif k == "sond":
            self.mostrar_vista("sondagens")

    def _duplo_arvore(self, _=None):
        sel = self.arvore.selection()
        if not sel:
            return
        k = sel[0]
        acao = {"geo": self.dlg_geometria, "mat": self.dlg_materiais, "apo": self.dlg_apoio, "acoes": self.dlg_acoes,
                "sond": self.dlg_sondagens, "solo": self.dlg_solo, "crit": self.dlg_criterios, "proj": self.dlg_ident}.get(k)
        if k.startswith("acao:"):
            acao = self.dlg_acoes
        if acao:
            acao()

    def atualizar_combos(self):
        if not self.res:
            self.cb_perfil["values"], self.cb_comb["values"] = [], []
            self.cb_perfil.set("")
            self.cb_comb.set("")
            return
        aps = self.res["analises"]
        self.i_perfil = min(self.i_perfil, len(aps) - 1)
        self.cb_perfil["values"] = [ap["rotulo"] for ap in aps]
        self.cb_perfil.current(self.i_perfil)
        serv = aps[self.i_perfil]["servico"]
        if self.i_comb is None or self.i_comb >= len(serv):
            self.i_comb = max(range(len(serv)), key=lambda j: serv[j]["theta"])
        self.cb_comb["values"] = [e["nome"] for e in serv]
        self.cb_comb.current(self.i_comb)

    def _troca_perfil(self):
        self.i_perfil = self.cb_perfil.current()
        self.i_comb = None
        self.atualizar_combos()
        self.desenhar()

    def _troca_comb(self):
        self.i_comb = self.cb_comb.current()
        self.desenhar()

    # ---------------------------------------------------------------- vistas
    def mostrar_vista(self, v):
        self.vista = v
        self.desenhar()

    def _eixos(self, n=1, **kw):
        self.fig.clear()
        self.fig.set_facecolor(FUNDO_CAD)
        axs = self.fig.subplots(1, n, **kw) if n > 1 else [self.fig.add_subplot(111)]
        for ax in axs:
            ax.set_facecolor(FUNDO_CAD)
            for s in ax.spines.values():
                s.set_color("#555555")
            ax.tick_params(colors=CORES["txt"], labelsize=8)
            ax.xaxis.label.set_color(CORES["txt"])
            ax.yaxis.label.set_color(CORES["txt"])
            ax.title.set_color(CORES["txt"])
            ax.grid(True, color=CORES["grade"], linewidth=0.6)
        return axs

    def desenhar(self):
        nomes = dict(self.VISTAS, combinacoes="Combinações")
        self.lb_vista.configure(text=nomes.get(self.vista, ""))
        tabela = self.vista in ("verificacoes", "combinacoes")
        if tabela:
            self.canvas.get_tk_widget().pack_forget()
            self.tab_frame.pack(fill="both", expand=True)
            self._tabela()
            return
        self.tab_frame.pack_forget()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self._hover = self._click = self._hover_ann = None
        self.fig.clear()
        try:
            if not self.res:
                ax = self._eixos()[0]
                ax.text(0.5, 0.5, "Sem resultados: complete os dados e calcule (F5).", color=CORES["txt"], ha="center",
                        transform=ax.transAxes)
            else:
                getattr(self, "_v_" + self.vista)()
        except Exception as e:                                         # noqa: BLE001
            ax = self._eixos()[0]
            ax.text(0.5, 0.5, f"Erro ao desenhar: {e}", color=CORES["crit"], ha="center", transform=ax.transAxes)
        self.fig.tight_layout()
        self.canvas.draw_idle()

    # ---------------------------------------------------------------- mouse
    def _ferramenta_ativa(self):
        modo = getattr(self.tb, "mode", "")                             # zoom ou deslocamento da barra do matplotlib
        return bool(getattr(modo, "value", modo))

    def _mouse_move(self, ev):
        txt = None
        if self._hover and ev.inaxes is not None and ev.xdata is not None:
            try:
                txt = self._hover(ev)
            except Exception:                                          # noqa: BLE001
                txt = None
        ann = self._hover_ann
        if not txt:
            if ann is not None and ann.get_visible():
                ann.set_visible(False)
                self.canvas.draw_idle()
            return
        if ann is None or ann.axes is not ev.inaxes:
            if ann is not None:
                ann.remove()
            ann = ev.inaxes.annotate("", xy=(0, 0), xytext=(14, 14), textcoords="offset points", fontsize=8, color="#111111",
                                     zorder=50, bbox=dict(boxstyle="round,pad=0.35", fc="#fff8d6", ec="#9a6700", alpha=0.95))
            self._hover_ann = ann
        w, h = self.canvas.get_width_height()
        dx = -14 if ev.x > 0.65 * w else 14
        dy = -14 if ev.y > 0.75 * h else 14
        ann.xy = (ev.xdata, ev.ydata)
        ann.set_position((dx, dy))
        ann.set_ha("right" if dx < 0 else "left")
        ann.set_va("top" if dy < 0 else "bottom")
        ann.set_text(txt)
        ann.set_visible(True)
        self.status.configure(text=txt.replace("\n", "  |  "))
        self.canvas.draw_idle()

    def _mouse_click(self, ev):
        if self._click and ev.button == 1 and ev.inaxes is not None and ev.xdata is not None and not self._ferramenta_ativa():
            self._click(ev)

    def report_callback_exception(self, exc, val, tb):
        """Erros dos botões e menus: na janela .pyw não há console, então aparecem nas mensagens, num aviso e no
        registro saidas\\erros_janela.log."""
        txt = "".join(traceback.format_exception(exc, val, tb))
        try:
            os.makedirs(tcore.SAIDAS, exist_ok=True)
            with open(os.path.join(tcore.SAIDAS, "erros_janela.log"), "a", encoding="utf-8") as fh:
                fh.write(txt + "\n")
            self.msg(f"Erro: {val}", "erro")
        except Exception:                                              # noqa: BLE001
            pass
        messagebox.showerror(APP, f"{val}\n\nDetalhes em saidas\\erros_janela.log.")

    def _ap_e(self):
        ap = self.res["analises"][self.i_perfil]
        return ap, ap["servico"][self.i_comb]

    def _v_elevacao(self):
        ap, e = self._ap_e()
        m = ap["modelo"]
        p = self.res["p"]
        g, cm = p["geometria"], p["camisa"]
        ax, ax2 = self._eixos(2, gridspec_kw=dict(width_ratios=[1.3, 1]))
        D, Dc, De, L = g["D"], g["D_estrutura"], g["D_escavacao"], g["L"]
        topo, terr = g["cota_topo"], g["cota_terreno"]
        larg = max(3.0 * De, 3.0)
        cams = [c for c in ap_camadas(self.res, ap) if c["base"] < terr and c["topo"] > g["cota_base"] - 1.5 * D]
        for c in cams:
            t, b = min(c["topo"], terr), max(c["base"], g["cota_base"] - 1.5 * D)
            ax.add_patch(Rectangle((-larg / 2, b), larg, t - b, fc=CORES["fam"].get(c["familia"], "#666"), alpha=0.55, ec="#8c7e6d", lw=0.6))
            ax.text(-larg / 2 + 0.05, (t + b) / 2, f"N {c['nspt']:.0f} {c['solo'][:14]}", color=CORES["txt"], fontsize=7, va="center")
        ax.axhline(terr, color="#cfcfcf", lw=1.2)
        na = self.res["solo"]["na"]
        if na is not None and na > g["cota_base"] - 1.5 * D:
            ax.axhline(na, color=CORES["s1"], lw=1, ls="--")
            ax.text(larg / 2, na, " NA", color=CORES["s1"], fontsize=8, va="bottom")
        # deformada exagerada (rotação no plano do tombamento)
        f = min(0.08 / e["theta"], 500) if e["theta"] > 0 else 1.0
        th = e["theta"] * f
        u0 = (e["ux"] * e["tx"] + e["uy"] * e["ty"]) / e["theta"] * f if e["theta"] > 0 else 0.0
        def pt(x, z):
            return (x + u0 - th * z, topo - z - x * th)
        ax.add_patch(Polygon([(-D / 2, topo), (D / 2, topo), (D / 2, topo - L), (-D / 2, topo - L)], closed=True, fill=False,
                             ec="#777", ls=":", lw=1))
        ax.add_patch(Polygon([pt(-Dc / 2, 0), pt(Dc / 2, 0), pt(Dc / 2, L), pt(-Dc / 2, L)], closed=True, fc=CORES["conc"], ec="#e0e0e0", lw=1))
        if cm["usar"]:
            for s in (-1, 1):
                x0, x1 = (Dc / 2, D / 2) if s > 0 else (-D / 2, -Dc / 2)
                ax.add_patch(Polygon([pt(x0, 0), pt(x1, 0), pt(x1, L), pt(x0, L)], closed=True, fc=CORES["anel"], ec="#e0e0e0", lw=0.8))
        if e.get("z0") is not None and 0 < e["z0"] < L:
            x, y = pt(0, e["z0"])
            ax.plot([x], [y], "o", color=CORES["crit"], ms=5)
            ax.text(x + 0.05, y, f" z0 = {br(e['z0'])} m", color=CORES["txt"], fontsize=8)
        ax.annotate("", xy=(-0.2, topo + 0.15), xytext=(-D / 2 - 0.9, topo + 0.15), arrowprops=dict(arrowstyle="->", color=CORES["crit"], lw=1.6))
        ax.set_xlim(-larg / 2, larg / 2)
        ax.set_ylim(g["cota_base"] - 1.5 * D, topo + 0.6)
        ax.set_aspect("equal")
        ax.set_title(f"Elevação — deformada ×{f:.0f}", fontsize=9)
        ax.set_ylabel("cota (m)")
        # diagrama da reação lateral
        thv = e["theta"]
        q = [(fx * e["tx"] + fy * e["ty"]) / thv / dz if thv > 0 else 0.0 for fx, fy, dz in zip(e["fx"], e["fy"], m.dz)]
        z = m.z
        pu = m.pu
        fs = p["criterios"]["fs_passivo"]
        ax2.fill_betweenx(z, -pu, pu, color=CORES["s2"], alpha=0.12)
        ax2.plot(pu, z, color=CORES["s2"], lw=1, label="linha cheia: resistência última do solo ± p_u")
        ax2.plot(-pu, z, color=CORES["s2"], lw=1)
        ax2.plot(pu / fs, z, color=CORES["s3"], lw=1, ls="--", label=f"tracejada: limite de serviço ± p_u/{br(fs, 1)} (NBR 6122, 7.6.3)")
        ax2.plot(-pu / fs, z, color=CORES["s3"], lw=1, ls="--")
        ax2.plot(q, z, color=CORES["s1"], lw=2.2, label="azul: reação do solo na combinação")
        qm = max(max(abs(v) for v in q), 1e-3)
        ax2.set_xlim(-min(pu.max(), 3 * qm), min(pu.max(), 3 * qm))
        ax2.set_ylim(L, 0)
        ax2.axvline(0, color="#777", lw=0.8)
        ax2.set_xlabel("reação lateral (kN/m)")
        ax2.set_ylabel("profundidade (m)")
        ax2.set_title(f"Mobilização máx. {br(max(e['mob']))}; FS = {br(e['lam'])}", fontsize=9)
        lg = ax2.legend(fontsize=7, facecolor=FUNDO_CAD, edgecolor="#555", loc="upper left", bbox_to_anchor=(0.0, -0.09),
                        borderaxespad=0.0)                     # fora do gráfico, abaixo do eixo
        for t in lg.get_texts():
            t.set_color(CORES["txt"])
        ax2.text(0.0, -0.27, f"A reação azul deve ficar entre as tracejadas (mobilização |q|/p_u ≤ {br(1 / fs)}).\n"
                 "Negativo: o solo empurra contra a carga, acima do ponto de rotação; abaixo dele a reação troca de sentido.",
                 transform=ax2.transAxes, ha="left", va="top", fontsize=6.8, color=CORES["txt"], zorder=15)
        # reação e mobilização máximas
        kq = int(np.argmax(np.abs(q)))
        km = int(np.argmax(e["mob"]))
        def etiqueta(k, txt, cor, marca):
            ax2.plot([q[k]], [z[k]], marca, color=cor, ms=5)
            baixo = z[k] > 0.8 * L                                      # perto da base: texto acima do ponto
            dx = -8 if q[k] >= 0 else 8
            ax2.annotate(txt, (q[k], z[k]), xytext=(dx, 8 if baixo else -8), textcoords="offset points", color=cor, fontsize=7,
                         ha="right" if dx < 0 else "left", va="bottom" if baixo else "top")
        etiqueta(kq, f"q máx. {br(abs(q[kq]), 1)} kN/m (z = {br(z[kq])} m)", CORES["txt"], "o")
        if km != kq:
            etiqueta(km, f"mobilização máx. {br(e['mob'][km])} (z = {br(z[km])} m)", CORES["s4"], "s")
        # deslocamentos máximos (combinação atual, valores reais)
        R = m.Dbase / 2
        ha_ = p["apoio"]["h_aplicacao"] or 0.0
        u_ap = e.get("u_aplicacao", e["u_topo"] + e["theta"] * ha_)
        u_base = math.hypot(e["ux"] - e["tx"] * L, e["uy"] - e["ty"] * L)
        w_b = e["w"] + e["theta"] * R
        w_min = e["w"] - e["theta"] * R
        linhas = [f"θ = {br(e['theta'] * 1000)} ‰", f"u topo = {br(e['u_topo'] * 1000, 1)} mm"]
        if ha_ > 0:
            linhas.append(f"u aplicação (+{br(ha_, 1)} m) = {br(u_ap * 1000, 1)} mm")
        linhas += [f"u base = {br(u_base * 1000, 1)} mm", f"recalque centro = {br(e['w'] * 1000, 1)} mm",
                   f"recalque borda = {br(w_b * 1000, 1)} mm" + (f" (outra sobe {br(-w_min * 1000, 1)})" if w_min < 0 else "")]
        ax.text(0.98, 0.02, "Deslocamentos (valores reais)\n" + "\n".join(linhas), transform=ax.transAxes, ha="right", va="bottom",
                fontsize=7, color="#111111", bbox=dict(boxstyle="round,pad=0.35", fc="#f2f2f2", ec="#888888", alpha=0.92), zorder=20)

        mob = e["mob"]
        def ponto(zz):
            if zz < m.z_ini - 1e-9 or zz > L + 1e-9:
                return None
            k = int(np.argmin(np.abs(z - zz)))
            u = math.hypot(e["ux"] - e["tx"] * zz, e["uy"] - e["ty"] * zz)
            return (f"z = {br(zz)} m (cota {br(topo - zz)})\ndesloc. horizontal {br(u * 1000, 1)} mm\n"
                    f"reação {br(abs(q[k]), 1)} kN/m; p_u {br(pu[k], 0)} kN/m\nmobilização {br(mob[k])} (limite {br(1 / fs)})")
        def hv(ev):
            if ev.inaxes is ax:
                zz = topo - ev.ydata
                if 0 <= zz <= L and abs(ev.xdata) <= larg / 2:
                    return ponto(zz) or (f"z = {br(zz)} m (acima do terreno)\ndesloc. horizontal "
                                         f"{br(math.hypot(e['ux'] - e['tx'] * zz, e['uy'] - e['ty'] * zz) * 1000, 1)} mm")
                return None
            if ev.inaxes is ax2:
                return ponto(ev.ydata)
            return None
        self._hover = hv

    def _v_base(self):
        ap, e = self._ap_e()
        m = ap["modelo"]
        p = self.res["p"]
        ax = self._eixos()[0]
        nr, nt = p["analise"]["n_aneis_base"], p["analise"]["n_setores_base"]
        pb = np.array(e["pb"]).reshape(nt, nr)
        R = m.Dbase / 2
        rr = R * np.sqrt(np.arange(nr + 1) / nr)
        cmap = matplotlib.colormaps["Blues"]
        pmax = max(pb.max(), 1e-9)
        for it in range(nt):
            for ir in range(nr):
                v = pb[it, ir]
                ax.add_patch(Wedge((0, 0), rr[ir + 1], 360 * it / nt, 360 * (it + 1) / nt, width=rr[ir + 1] - rr[ir],
                                   color=cmap(0.15 + 0.85 * v / pmax) if v > 1e-9 else "#2a2a2a", lw=0))
        ax.add_patch(Circle((0, 0), R, fill=False, ec="#e0e0e0", lw=1))
        ax.set_xlim(-1.2 * R, 1.2 * R)
        ax.set_ylim(-1.2 * R, 1.2 * R)
        ax.set_aspect("equal")
        ax.set_title(f"Pressões na base: máx. {e['p_max']:.0f} kPa (σadm {ap['sigma_adm']:.0f}); área comprimida "
                     f"{e['area_comp'] * 100:.0f} %", fontsize=9)
        sm = matplotlib.cm.ScalarMappable(cmap=cmap, norm=matplotlib.colors.Normalize(0, pmax))
        cb = self.fig.colorbar(sm, ax=ax, fraction=0.04)
        cb.ax.tick_params(colors=CORES["txt"], labelsize=8)
        cb.set_label("kPa", color=CORES["txt"])
        it_m, ir_m = np.unravel_index(int(np.argmax(pb)), pb.shape)
        rm, tm = (rr[ir_m] + rr[ir_m + 1]) / 2, 2 * math.pi * (it_m + 0.5) / nt
        ax.plot([rm * math.cos(tm)], [rm * math.sin(tm)], "x", color=CORES["crit"], ms=7, mew=2)
        linhas = [f"pressão máx. = {br(e['p_max'], 0)} kPa", f"pressão mín. = {br(max(e['p_min'], 0.0), 0)} kPa",
                  f"σadm = {br(ap['sigma_adm'], 0)} kPa", f"área comprimida = {br(e['area_comp'] * 100, 0)} %",
                  f"excentricidade = {br(e['e_base'], 3)} m" if math.isfinite(e["e_base"]) else "excentricidade —",
                  f"recalque no centro = {br(e['w'] * 1000, 1)} mm"]
        ax.text(0.02, 0.98, "\n".join(linhas), transform=ax.transAxes, ha="left", va="top", fontsize=7.5, color="#111111",
                bbox=dict(boxstyle="round,pad=0.4", fc="#f2f2f2", ec="#888888", alpha=0.92), zorder=20)

        def hv(ev):
            if ev.inaxes is not ax:
                return None
            x, y = ev.xdata, ev.ydata
            r = math.hypot(x, y)
            if r > R:
                return None
            ir = min(int(nr * (r / R) ** 2), nr - 1)
            it = min(int(nt * (math.atan2(y, x) % (2 * math.pi)) / (2 * math.pi)), nt - 1)
            v = pb[it, ir]
            return (f"x = {br(x)} m, y = {br(y)} m\npressão {br(v, 0)} kPa" + ("" if v > 1e-9 else " (sem contato)")
                    + f"\n{br(v / ap['sigma_adm'] * 100, 0)} % da σadm")
        self._hover = hv

    def _v_ruptura(self):
        ap, _ = self._ap_e()
        ax = self._eixos()[0]
        cr = self.res["p"]["criterios"]
        cores = [CORES["s1"], CORES["s2"], CORES["s3"], CORES["s4"]]
        calc = cr["tombamento"] == "calculo"
        k = 0
        for e in ap["servico"]:
            po = e.get("pushover")
            if not po or not po["curva"]:
                continue
            c = po["curva"]
            ax.plot([x[1] * 1000 for x in c], [x[0] for x in c], "-o", ms=3, color=cores[k % 4], label=f"{e['nome'][:60]} (FS {br(e['lam'])})")
            pd = e.get("pushover_d")
            if pd and pd["curva"]:
                c = pd["curva"]
                ax.plot([x[1] * 1000 for x in c], [x[0] for x in c], "--", lw=1.2, color=cores[k % 4],
                        label=f"  de cálculo (λd {br(e.get('lam_d'))})")
            k += 1
        lim = cr["gama_f_tombamento"] if calc else cr["fs_tombamento"]
        ax.axhline(lim, color="#bbbbbb", ls="--", lw=1)
        ax.text(ax.get_xlim()[1], lim, ("λd mín. = γf " if calc else "FS mín. ") + br(lim, 1), color="#bbbbbb", fontsize=7,
                ha="right", va="bottom")
        ax.axhline(1.0, color="#777", lw=0.8)
        ax.set_xlabel("rotação (‰)")
        ax.set_ylabel("λ sobre as ações horizontais")
        ax.set_title(f"Ruptura ao tombamento ({so.METODOS_PU[self.res['p']['solo']['metodo_pu']]})", fontsize=9)
        if k:
            lg = ax.legend(fontsize=7, facecolor=FUNDO_CAD, edgecolor="#555")
            for t in lg.get_texts():
                t.set_color(CORES["txt"])

    def _v_esforcos(self):
        env = self.res["estrutura"]["envelope"]
        axs = self._eixos(3, sharey=True)
        if not env:
            return
        zs = sorted(set(round(s["z"], 4) for s in env))
        for ax, k, t in zip(axs, ("N", "V", "M"), ("N (kN)", "V (kN)", "M (kN.m)")):
            v = [max(abs(s[k]) for s in env if abs(s["z"] - z) < 1e-6) for z in zs]
            ax.fill_betweenx(zs, 0, v, color=CORES["s1"], alpha=0.25)
            ax.plot(v, zs, color=CORES["s1"], lw=2)
            ax.set_xlabel(t)
            ax.set_title(f"máx. {max(v):.1f}", fontsize=9)
        axs[0].set_ylim(max(zs), 0)
        axs[0].set_ylabel("profundidade (m)")

    def _v_sondagens(self):
        s = self.res["solo"]
        comp = s["perfis_geospt"]["compatibilizacao"]["linhas"]
        ax = self._eixos()[0]
        cotas = [c["cotaRef_m"] for c in comp]
        for f in s["nomes"]:
            ax.plot([c["nsptPorSondagem"][f] if c["nsptPorSondagem"][f] is not None else np.nan for c in comp], cotas,
                    color=CORES["neutro"], lw=1, label=f)
        med = s["perfis_geospt"]["media"]["camadas"]
        env = s["perfis_geospt"]["envoltoria"]
        ax.plot([c["nspt"] for c in med], [c["cota_m"] for c in med], "-o", ms=3, color=CORES["s1"], lw=2, label="média")
        ax.plot([c["nspt"] for c in env], [c["cota_m"] for c in env], "-o", ms=3, color=CORES["s2"], lw=2, label="mínima")
        g = self.res["p"]["geometria"]
        ax.axhline(g["cota_base"], color="#bbbbbb", ls="--", lw=1)
        ax.text(1, g["cota_base"], " base", color=CORES["txt"], fontsize=8, va="bottom")
        ax.set_xlim(0, 52)
        ax.set_xlabel("NSPT")
        ax.set_ylabel("cota (m)")
        lg = ax.legend(fontsize=7, facecolor=FUNDO_CAD, edgecolor="#555")
        for t in lg.get_texts():
            t.set_color(CORES["txt"])

    def _tabela_previa(self, m):
        """Comprimentos dos ferros na prévia: os do TQS se o DWG deste cálculo já foi gerado; senão, aproximados (barra reta
        = trecho reto, mais cerca de 8,75·φ por gancho de 180°; estribo circular = perímetro pelo eixo + cerca de 75·φ de ganchos e transpasse, como o TQS dá)."""
        if self.tabela_tqs and self.tabela_tqs[0] is self.res:
            return self.tabela_tqs[1], True
        tab = []
        for f in m.ferros:
            if f["tipo"] == "reto":
                c = f["main"] + f.get("dobra", 0.0) + (2 * 8.75 * f["bitola"] / 10 if f.get("ganchos") == 180 else 0.0)
            elif f["tipo"] == "circ":
                c = 2 * math.pi * (f["raio"] - f["cover"] - f["bitola"] / 20) + 75 * f["bitola"] / 10
            else:
                c = f.get("comp") or 0.0
            tab.append(dict(mark=f["mark"], bitola=f["bitola"], quant=f["quant"], comp=float(round(c))))
        return tab, False

    def _v_desenho(self):
        import tubulao_dwg as td
        import estaca_previa as ev
        tab, do_tqs = self._tabela_previa(td.montar(self.res))
        m = td.montar(self.res, tab)
        self.fig.clear()
        self.fig.set_facecolor("white")
        ax = self.fig.add_subplot(111)
        self.tx_prev = ev.desenhar(ax, m.prims, m.ferros, float(self.res["p"]["saidas"]["escala"]), self.tx_prev)
        ax.set_title("Prévia do desenho — " + ("comprimentos do TQS (DWG deste cálculo já gerado)" if do_tqs else
                     "ferros e comprimentos aproximados; os finais são os do TQS ao gerar o DWG")
                     + ("" if self.res["p"]["saidas"].get("sondagens_desenho", True) else "; sem as sondagens (Saídas > Opções)"),
                     fontsize=9, color="#333333")

    def _v_mapa(self):
        ax = self._eixos()[0]
        d = self.res.get("dimensionamento")
        velho = False
        if not d and self.mapa_dim:
            d, velho = self.mapa_dim, True                              # os dados mudaram depois da varredura
        if not d:
            ax.text(0.5, 0.5, "Sem dimensionamento automático: use Tubulão > Dimensionar D x L.", color=CORES["txt"], ha="center",
                    transform=ax.transAxes)
            return
        Ds, Ls = sorted(set(m["D"] for m in d["mapa"])), d["Ls"]
        for m in d["mapa"]:
            i, j = Ls.index(m["L"]), Ds.index(m["D"])
            a = min(m["aproveitamento"], 9.99) if m["aproveitamento"] is not None else 9.99
            cor = "#1f6f2b" if m["ok"] else "#3a3a3a"
            ax.add_patch(Rectangle((i - 0.48, j - 0.48), 0.96, 0.96, color=cor))
            ax.text(i, j, "≥ 10" if a >= 9.99 else br(a), color=CORES["txt"], ha="center", va="center", fontsize=7)
        esc, oti = d.get("escolha"), d.get("otima")
        if oti and d.get("usuario"):
            ax.add_patch(Rectangle((Ls.index(oti["L"]) - 0.5, Ds.index(oti["D"]) - 0.5), 1, 1, fill=False, ec="#bbbbbb", lw=1.6, ls="--"))
        if esc:
            ax.add_patch(Rectangle((Ls.index(esc["L"]) - 0.5, Ds.index(esc["D"]) - 0.5), 1, 1, fill=False, ec="white", lw=2))

        def celula(ev):
            if ev.inaxes is not ax:
                return None
            i, j = int(round(ev.xdata)), int(round(ev.ydata))
            if not (0 <= i < len(Ls) and 0 <= j < len(Ds)):
                return None
            return next((m for m in d["mapa"] if abs(m["L"] - Ls[i]) < 1e-9 and abs(m["D"] - Ds[j]) < 1e-9), None)

        def hv(ev):
            m = celula(ev)
            if not m:
                return None
            a = m["aproveitamento"]
            t = (f"D = {br(m['D'])} m, L = {br(m['L'])} m" + (f" (anel DN {br(m['DN'])})" if m.get("DN") else "")
                 + f"\nvolume {br(m['volume'])} m3\naproveitamento {br(a) if a is not None and a < 9.99 else '≥ 10'}"
                 + (f"\ngoverna: {m['governante']}" if m.get("governante") else "")
                 + ("\npassa em tudo" if m["ok"] else "\nnão passa"))
            if oti and abs(m["D"] - oti["D"]) < 1e-9 and abs(m["L"] - oti["L"]) < 1e-9:
                t += " (ótima)"
            return t + "\nclique para adotar"

        def clique(ev):
            m = celula(ev)
            if not m:
                return
            if velho:
                messagebox.showinfo(APP, "Os dados mudaram depois da varredura: refaça o dimensionamento (Tubulão > Dimensionar "
                                         "D x L) antes de escolher outra solução.", parent=self)
                return
            if esc and abs(m["D"] - esc["D"]) < 1e-9 and abs(m["L"] - esc["L"]) < 1e-9:
                return
            sol = f"D = {br(m['D'])} m, L = {br(m['L'])} m"
            if m["ok"]:
                if not messagebox.askyesno(APP, f"Adotar {sol} (volume {br(m['volume'])} m3)?", parent=self):
                    return
            elif not messagebox.askyesno(APP, f"{sol} não passa: governa {m.get('governante') or '—'} (aproveitamento "
                                              f"{br(m['aproveitamento']) if m['aproveitamento'] is not None else '—'}).\n\n"
                                              "Adotar mesmo assim? As verificações não atendidas vão aparecer no resultado.",
                                         icon="warning", parent=self):
                return
            self.par["geometria"]["L"] = m["L"]                       # adota a célula sem refazer a varredura
            if m.get("DN") is not None:
                self.par["camisa"]["DN"], self.par["camisa"]["espessura"] = m["DN"], None
            else:
                self.par["geometria"]["D"] = m["D"]
            self.par["dimensionamento"]["automatico"] = False
            self.par["dimensionamento"].pop("escolha_usuario", None)
            self.vista = "mapa"
            self.msg(f"Solução adotada no mapa D x L: {sol}.", "ok")
            self.alterado()
        self._hover, self._click = hv, clique
        ax.set_xticks(range(len(Ls)), [br(L) for L in Ls])
        ax.set_yticks(range(len(Ds)), [br(D) for D in Ds])
        ax.set_xlim(-0.5, len(Ls) - 0.5)
        ax.set_ylim(-0.5, len(Ds) - 0.5)
        ax.set_xlabel("L (m)")
        ax.set_ylabel("D (m)")
        ax.set_title(("VARREDURA ANTERIOR (os dados mudaram: refaça o dimensionamento). " if velho else "")
                     + "Aproveitamento da verificação que governa (verde = passa em tudo; borda branca = adotada"
                     + ("; tracejada = ótima" if d.get("usuario") else "") + ")."
                     + ("" if velho else " Clique numa célula para adotar outra solução."), fontsize=9)
        ax.grid(False)

    def _tabela(self):
        tv = self.tab_tv
        tv.delete(*tv.get_children())
        if self.vista == "combinacoes":
            cols = [("nome", "Combinação", 520), ("tipo", "Tipo", 110), ("N", "N", 70), ("Hx", "Hx", 70), ("Hy", "Hy", 70),
                    ("Mx", "Mx", 70), ("My", "My", 70)]
            tv.configure(columns=[c[0] for c in cols])
            for k, t, w in cols:
                tv.heading(k, text=t)
                tv.column(k, width=w, anchor="w" if k == "nome" else "e")
            try:
                cb = tcore.combinacoes(tcore.normalizar(copy.deepcopy(self.par), self.pasta_base())["acoes"])
            except ValueError as e:
                tv.insert("", "end", values=(str(e),))
                return
            for tipo, lst in (("característica", cb["servico"]), ("quase permanente", cb["quase_permanente"]), ("última", cb["ultima"])):
                for c in lst:
                    tv.insert("", "end", values=[c["nome"], tipo] + [br(v, 1) for v in c["F"]])
            return
        cols = [("ok", "", 40), ("grupo", "Grupo", 90), ("nome", "Verificação", 330), ("perfil", "Perfil", 170), ("comb", "Combinação", 300),
                ("valor", "Valor", 90), ("lim", "Limite", 90), ("ref", "Critério", 260)]
        tv.configure(columns=[c[0] for c in cols])
        for k, t, w in cols:
            tv.heading(k, text=t)
            tv.column(k, width=w, anchor="w")
        if not self.res:
            return
        for c in sorted(self.res["verificacoes"], key=lambda c: c["ok"]):
            v = c["valor"]
            tv.insert("", "end", tags=() if c["ok"] else ("nok",),
                      values=["✓" if c["ok"] else "✗", c["grupo"], c["nome"], c["perfil"], c["combinacao"],
                              (f"{v:.4g}" if abs(v) > 1e-9 or v == 0 else "0") if isinstance(v, (int, float)) else v,
                              f"{c['limite']:.4g}" if isinstance(c["limite"], (int, float)) else (c["limite"] or "—"), c["ref"]])

    # ---------------------------------------------------------------- saídas
    def pasta_saida(self):
        p = self.res["p"] if self.res else self.par
        return p["saidas"].get("pasta") or os.path.join(tcore.SAIDAS, p["nome"])

    def _precisa_res(self):
        if not self.res:
            messagebox.showinfo(APP, "Calcule antes (F5).")
            return False
        return True

    def _em_thread(self, nome, func):
        self.status.configure(text=f"{nome}...")

        def tarefa():
            try:
                r = func()
                self.fila.put(lambda: (self.status.configure(text=f"{nome}: pronto"), r and self.msg(r, "ok")))
            except Exception as e:                                     # noqa: BLE001
                self.fila.put(lambda: (self.status.configure(text=f"{nome}: erro"), self.msg(f"{nome}: {e}", "erro")))
        threading.Thread(target=tarefa, daemon=True).start()

    def gerar_memoria(self, abrir=True):
        if not self._precisa_res():
            return
        import tubulao_memoria as tm
        res, pasta = self.res, self.pasta_saida()

        def f():
            out = tm.gerar(res, pasta, pdf=res["p"]["saidas"]["memoria_pdf"])
            if abrir:
                os.startfile(out["html"])
            return "Memória: " + ", ".join(v for k, v in out.items() if k in ("html", "pdf")) + \
                (f" (PDF: {out['erro_pdf']})" if out.get("erro_pdf") else "")
        self._em_thread("Memória de cálculo", f)

    def gerar_3d(self, abrir=True):
        if not self._precisa_res():
            return
        import tubulao_3d as t3
        try:
            c = t3.gravar(self.res, self.pasta_saida())
            if abrir:
                t3.abrir(c)
        except Exception as e:                                         # noqa: BLE001
            messagebox.showerror(APP, f"Não consegui gerar ou abrir o 3D:\n{e}", parent=self)
            self.msg(f"3D: erro: {e}", "erro")
            return
        self.msg(f"3D: {c}" + (" (aberto numa janela do Edge; se ela não aparecer, abra esse arquivo)" if abrir else ""), "ok")

    def _falta_tqs(self):
        """Texto do que falta para gravar o DWG neste computador (None se nada falta)."""
        itens = dep.conferir(tqs=True)
        return dep.mensagem_faltas(itens, "gravar o DWG") if dep.faltas(itens) else None

    def gerar_dwg(self):
        if not self._precisa_res():
            return
        falta = self._falta_tqs()                    # o que falta, antes de gravar qualquer arquivo
        if falta:
            messagebox.showerror(APP, falta, parent=self)
            self.msg("DWG/PDF/DXF não gerados: falta o TQS (Conferir instalacao.bat).", "erro")
            return
        import tubulao_dwg as td
        res, pasta = self.res, self.pasta_saida()

        def f():
            r = td.gerar(res, pasta)
            self.tabela_tqs = (res, r["tabela"])                       # a prévia passa a usar os comprimentos do TQS
            return "Desenho: " + ", ".join(r["arquivos"].values()) + "".join(f"\n  [aviso] {a}" for a in r["avisos"])
        self._em_thread("DWG/PDF/DXF", f)

    def gerar_tudo(self):
        if not self._precisa_res():
            return
        import tubulao_memoria as tm, tubulao_3d as t3, tubulao_dwg as td
        res, pasta = self.res, self.pasta_saida()
        falta = self._falta_tqs()                    # sem o TQS: a memória e o 3D saem, o DWG não

        def f():
            out = []
            m = tm.gerar(res, pasta, pdf=res["p"]["saidas"]["memoria_pdf"])
            out.append(m["html"])
            out.append(t3.gravar(res, pasta))
            if falta:
                return "Gerados:\n  " + "\n  ".join(out) + "\n  [aviso] DWG, PDF e DXF não gerados: falta o TQS " \
                                                             "(Conferir instalacao.bat)."
            r = td.gerar(res, pasta)
            self.tabela_tqs = (res, r["tabela"])
            out += list(r["arquivos"].values())
            return "Gerados:\n  " + "\n  ".join(out)
        self._em_thread("Gerar tudo", f)

    def abrir_pasta(self):
        pasta = self.pasta_saida()
        os.makedirs(pasta, exist_ok=True)
        os.startfile(pasta)


def ap_camadas(res, ap):
    for pf in res["solo"]["perfis"]:
        if pf["rotulo"] == ap["rotulo"]:
            return pf["camadas"]
    return res["solo"]["perfis"][0]["camadas"]


if __name__ == "__main__":
    App(sys.argv[1] if len(sys.argv) > 1 else None).mainloop()
