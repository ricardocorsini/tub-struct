# -*- coding: utf-8 -*-
# Cópia portátil dos tubulões (14/11/2026): copiado de _apps\EstacaEscavada\estaca_previa.py, sem alterações no código.
"""
Prévia em matplotlib das primitivas do estaca_core (ou das lidas de um DWG TQS).

Os ferros inteligentes são aproximados (linha, dobra, círculo e descrição); o
desenho final é o que o TQS gerar. Os textos acompanham o zoom.
"""
import math
from matplotlib.collections import LineCollection
from matplotlib.patches import Circle, Polygon, Arc
import estaca_core as ec

COR = {ec.NV_CONTORNO: "#222222", ec.NV_MULT: "#b03a2e", ec.NV_EIXO: "#8c8c8c", ec.NV_ESCALA: "#444444",
       ec.NV_FERRO: "#c0392b", ec.NV_COTA: "#1f5fa8", ec.NV_TITULO: "#111111", ec.NV_FERCOR: "#c0392b",
       ec.NV_CORTE: "#111111", ec.NV_BLOCO: "#8a6d1d",
       ec.es.NV_SOND: "#7b4a12", ec.es.NV_SOND_GRAF: "#139fb0", ec.es.NV_SOND_GRADE: "#b3b3b3",
       ec.es.NV_SOND_TXT: "#222222", ec.es.NV_SOND_LIG: "#2e8b3a"}
# cores da tabela de plotagem do escritório nos níveis das hachuras de solo (o 206 é também o da escala de detalhe)
COR.update({206: "#e8901a", 250: "#e9806e", 214: "#8c8c8c"})
COR[ec.NV_ARM_BLOCO] = "#9a9a9a"           # armadura do bloco no detalhe da ancoragem (207, pena cinza)
COR[ec.NV_FERRO_DET] = "#0b97ab"           # armação das estacas no detalhe da ancoragem (234, pena 0,40)
COR[ec.NV_FERRO_INT] = "#139fb0"
ESPESSURA = {COR[ec.NV_FERRO_DET]: 1.8}    # linhas de pena grossa (as demais: 0,8)          # armadura desenhada por linhas (nível 239, ciano no TQS)
TRACO = {1: (0, (6, 4)), 2: (0, (2, 3)), 3: (0, (10, 3, 2, 3))}


def _cor(nv):
    return COR.get(nv, "#444444")

def _traco(pr):
    if pr.get("estilo", -1) in TRACO:
        return TRACO[pr["estilo"]]
    return TRACO[3] if pr.get("nv") == ec.NV_EIXO else "solid"


class Textos:
    """Textos com altura em unidades do desenho (cm), refeitos a cada zoom."""

    def __init__(self, ax):
        self.ax, self.itens, self.caixa = ax, [], []
        self.cids = [ax.callbacks.connect("xlim_changed", self.ajustar),
                     ax.callbacks.connect("ylim_changed", self.ajustar)]
        self.cid_fig = ax.figure.canvas.mpl_connect("resize_event", self.ajustar)

    def desligar(self):
        for cid in self.cids:
            self.ax.callbacks.disconnect(cid)
        self.ax.figure.canvas.mpl_disconnect(self.cid_fig)

    def add(self, x, y, s, h, ang=0.0, cor="#222", ha="left", va="baseline"):
        t = self.ax.text(x, y, s.replace("{", "ø"), rotation=ang, rotation_mode="anchor", ha=ha, va=va,
                         color=cor, family="monospace", fontsize=1, clip_on=True)
        self.itens.append((t, h))
        w = len(s) * h * {"left": 1.0, "center": 0.5}.get(ha, 1.0)
        a = math.radians(ang)
        self.caixa.extend([(x, y), (x + w * math.cos(a) - h * math.sin(a), y + w * math.sin(a) + h * math.cos(a)),
                           (x - w * math.cos(a), y - w * math.sin(a))] if ha == "center" else
                          [(x, y), (x + w * math.cos(a) - h * math.sin(a), y + w * math.sin(a) + h * math.cos(a))])

    def ajustar(self, *_):
        ax = self.ax
        # com escala igual nos dois eixos, o matplotlib só ajusta a caixa do eixo ao desenhar: sem isto, o
        # zoom por retângulo (ou só no y) media o texto com a largura antiga
        ax.apply_aspect()
        x0, x1 = ax.get_xlim()
        largura = ax.get_window_extent().width
        if x1 == x0 or largura <= 0:
            return
        k = largura / abs(x1 - x0) * 72 / ax.figure.dpi / 0.72      # altura de maiúscula ~0,72 em
        for t, h in self.itens:
            pt = h * k
            t.set_visible(pt >= 2.0)
            t.set_fontsize(max(pt, 1.0))


def _cota(pr, linhas, tx, E):
    x1, y1, x2, y2 = pr["p"]
    pos, h, c = pr["pos"], E * ec.H_TXT, _cor(ec.NV_COTA)
    tk = E * 0.08
    fg = E * ec.FOLGA                          # folga da linha de chamada (dim.dimexo do TQS)
    if pr["vert"]:
        med = abs(y2 - y1) * pr["fator"]
        for x, y in ((x1, y1), (x2, y2)):
            if abs(pos - x) > fg:
                linhas.append(((x + math.copysign(fg, pos - x), y), (pos + math.copysign(tk, pos - x), y), c, "solid"))
            linhas.append(((pos - tk, y - tk), (pos + tk, y + tk), c, "solid"))
        linhas.append(((pos, y1), (pos, y2), c, "solid"))
        tx.add(pos - 0.3 * h, (y1 + y2) / 2, pr["txt"] or f"{med:.0f}", h, 90.0, c, ha="center")
    else:
        med = abs(x2 - x1) * pr["fator"]
        for x, y in ((x1, y1), (x2, y2)):
            if abs(pos - y) > fg:
                linhas.append(((x, y + math.copysign(fg, pos - y)), (x, pos + math.copysign(tk, pos - y)), c, "solid"))
            linhas.append(((x - tk, pos - tk), (x + tk, pos + tk), c, "solid"))
        linhas.append(((x1, pos), (x2, pos), c, "solid"))
        tx.add((x1 + x2) / 2, pos + 0.3 * h, pr["txt"] or f"{med:.0f}", h, 0.0, c, ha="center")


def _quant(pr, linhas, tx):
    """Bloco $QUANT (geometria do modelo MASQUANT.DWG, em cm de plotagem)."""
    x0, y0, e, c = pr["x"], pr["y"], pr["esc"], "#555555"
    P = lambda x, y: (x0 + x * e, y0 + y * e)
    for y in (0.0, -0.88, -1.31, -1.75, -2.19, -2.62):
        linhas.append((P(0, y), P(ec.QUANT_LARG, y), c, "solid"))
    for x, ya in ((0.0, 0.0), (ec.QUANT_LARG, 0.0), (4.63, -0.88)):
        linhas.append((P(x, ya), P(x, -ec.QUANT_ALT), c, "solid"))
    tx.add(*P(1.07, -0.52), "Quantitativos de formas", 0.25 * e, 0.0, c)
    tx.add(*P(1.54, -1.21), "Item", 0.25 * e, 0.0, c)
    tx.add(*P(5.10, -1.23), "Valor", 0.25 * e, 0.0, c)
    for y, rot, v, un in ((-1.60, "Área estruturada", pr["area_est"], "m2"), (-2.04, "Área de formas", pr["area_for"], "m2"),
                          (-2.48, "Volume de concreto", pr["volume"], "m3")):
        tx.add(*P(0.34, y), rot, 0.2 * e, 0.0, c)
        tx.add(*P(4.97, y), f"{v:.2f}", 0.2 * e, 0.0, c)
        tx.add(*P(7.14, y), un, 0.2 * e, 0.0, c)


def _ganchos(linhas, xc, yc, r, fi, ang, c):
    """Ganchos do estribo circular como o TQS desenha o estribo explodido: pontas a 8,4° da inserção e
    40ø adiante (o transpasse), cada uma com dobra de 180° para dentro (raio 2,5ø) e perna de 11ø."""
    rb, perna = 2.5 * fi, 11 * fi
    th1 = math.radians(ang + 8.4)
    for th, s in ((th1, -1), (th1 + min(40 * fi / max(r, 1e-9), math.radians(200)), 1)):
        u, t = (math.cos(th), math.sin(th)), (-math.sin(th), math.cos(th))
        cx, cy = xc + (r - rb) * u[0], yc + (r - rb) * u[1]
        pts = [(cx + rb * (math.cos(a) * u[0] + s * math.sin(a) * t[0]), cy + rb * (math.cos(a) * u[1] + s * math.sin(a) * t[1]))
               for a in (k * math.pi / 8 for k in range(9))]
        pts.append((pts[-1][0] - s * perna * t[0], pts[-1][1] - s * perna * t[1]))
        linhas.extend((a, b, c, "solid") for a, b in zip(pts, pts[1:]))


def _ferro(ax, f, linhas, tx, E):
    c, h = _cor(ec.NV_FERRO), E * ec.H_TXT
    for i in f["ins"]:
        c = _cor(i.get("nv", ec.NV_FERRO))
        if f["tipo"] == "reto":
            a = math.radians(i["ang"])
            d = (math.cos(a), math.sin(a))
            p0 = (i["x"], i["y"])
            p1 = (p0[0] + f["main"] * i["esc"] * d[0], p0[1] + f["main"] * i["esc"] * d[1])
            if f.get("ganchos") == 180:
                # grampo, como o TQS: comprimento de face externa a face externa dos ganchos, gancho de raio externo
                # 3,5·φ (pino de 5·φ) sempre voltado para +90° do sentido da barra e ponta reta de 2·φ
                fi = f["bitola"] / 10 * i["esc"]
                rb, perna = 3.5 * fi, 2.0 * fi
                n = (-d[1], d[0])
                q0, q1 = (p0[0] + rb * d[0], p0[1] + rb * d[1]), (p1[0] - rb * d[0], p1[1] - rb * d[1])
                linhas.append((q0, q1, c, "solid"))
                for p, t in ((q0, (-d[0], -d[1])), (q1, d)):
                    c0 = (p[0] + rb * n[0], p[1] + rb * n[1])
                    pts = [(c0[0] + rb * (-n[0] * math.cos(a) + t[0] * math.sin(a)), c0[1] + rb * (-n[1] * math.cos(a) + t[1] * math.sin(a)))
                           for a in (k * math.pi / 8 for k in range(9))]
                    pts.append((pts[-1][0] - perna * t[0], pts[-1][1] - perna * t[1]))
                    linhas.extend((a_, b_, c, "solid") for a_, b_ in zip(pts, pts[1:]))
            else:
                linhas.append((p0, p1, c, "solid"))
            if f["dobra"] and i["ipatas"] in (1, 4):
                sn = (1 if f["zona"] == "pos" else -1) * (-1 if i["ipatas"] == 4 else 1)
                n = (-d[1] * sn, d[0] * sn)
                linhas.append((p1, (p1[0] + f["dobra"] * n[0], p1[1] + f["dobra"] * n[1]), c, "solid"))
            mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
            vert = abs(d[1]) > 0.7
            if i.get("idobra"):                  # o TQS cota o trecho reto: acima da barra (à esquerda, na vertical)
                if vert:
                    tx.add(mx - 0.6 * h, my, f"{f['main']:.0f}", h, 90.0, _cor(ec.NV_COTA), ha="center")
                else:
                    tx.add(mx, my + 0.4 * h, f"{f['main']:.0f}", h, 0.0, _cor(ec.NV_COTA), ha="center")
            if i["ident"] and not f.get("texto"):  # com texto posicionado, o TQS só escreve lá
                if vert:
                    tx.add(mx + 1.3 * h, my, f["desc"], h, 90.0, c, ha="center")
                elif i.get("idobra"):            # com a cota em cima, o texto vai embaixo da barra
                    tx.add(mx, my - 1.4 * h, f["desc"], h, 0.0, c, ha="center")
                else:
                    tx.add(p0[0], my + 0.5 * h, f["desc"], h, 0.0, c)
        elif f["tipo"] == "gen":                 # ferro genérico: poligonal a partir da inserção
            a = math.radians(i["ang"])
            pts = [(i["x"] + i["esc"] * (x * math.cos(a) - y * math.sin(a)),
                    i["y"] + i["esc"] * (x * math.sin(a) + y * math.cos(a))) for x, y in f["pontos"]]
            linhas.extend((p0, p1, c, "solid") for p0, p1 in zip(pts, pts[1:]))
            if i["ident"]:
                p0, p1 = max(zip(pts, pts[1:]), key=lambda q: math.dist(*q))
                tx.add((p0[0] + p1[0]) / 2 + 1.3 * h, (p0[1] + p1[1]) / 2, f["desc"], h, 90.0, c, ha="center")
        elif f["tipo"] == "anel":                # anel soldado: sem gancho
            ax.add_patch(Circle((i["x"], i["y"]), f["r_eixo"] * i["esc"], fill=False, ec=c, lw=0.9))
        else:
            r = (f["raio"] - f["cover"] - f["bitola"] / 20) * i["esc"]
            ax.add_patch(Circle((i["x"], i["y"]), r, fill=False, ec=c, lw=0.9))
            _ganchos(linhas, i["x"], i["y"], r, f["bitola"] / 10 * i["esc"], i["ang"], c)
            if i["ident"]:
                tx.add(i["x"], i["y"] - r - 1.5 * h, f["desc"], h, 0.0, c, ha="center")
    if f.get("texto"):
        tx.add(f["texto"]["x"], f["texto"]["y"], f["desc"], h, f["texto"].get("ang", 0.0), c,
               ha="left" if f["texto"].get("alin") == "esq" else "center")
    for fx in f.get("faixas", []):
        linhas.append(((fx["x"], fx["y1"]), (fx["x"], fx["y2"]), c, "solid"))
        for y in (fx["y1"], fx["y2"]):
            ax.add_patch(Circle((fx["x"], y), 0.06 * E, fc=c, ec=c))
        tx.add(fx["x"] + 1.3 * h, (fx["y1"] + fx["y2"]) / 2,
               f"{fx['n']} N{f['mark']} {{{ec.bt(f['bitola'])} C/{fx['s']:g}", h, 90.0, c, ha="center")
        if fx["cotar"]:                  # o TQS escreve "(comprimento)" ao lado da faixa
            tx.add(fx["x"] - 0.4 * h, (fx["y1"] + fx["y2"]) / 2, f"({abs(fx['y2'] - fx['y1']):.0f})", h, 90.0,
                   _cor(ec.NV_COTA), ha="center")
    for mk in f.get("marcas", []):
        pts = [(mk["xt"], mk["yt"])] + list(mk["pts"])
        for a, b in zip(pts, pts[1:]):
            linhas.append((a, b, _cor(ec.NV_COTA), "solid"))
        s = (f"{f['quant']} " if mk["nfr"] else "") + f"N{f['mark']}" + (f" {{{ec.bt(f['bitola'])}" if mk["bit"] else "")
        tx.add(mk["xt"], mk["yt"] + 0.3 * h, s, h, 0.0, c)


def desenhar(ax, prims, ferros=(), escala=50, textos_antigos=None):
    """Desenha no Axes. Devolve o objeto Textos (guarde e passe de volta no próximo desenho)."""
    if textos_antigos is not None:
        textos_antigos.desligar()
    ax.clear()
    ax.set_aspect("equal")
    ax.axis("off")
    tx = Textos(ax)
    ax._estaca_textos = tx           # o matplotlib guarda os callbacks como referência fraca: sem isto, se
                                     # quem chamou não guardar o retorno, o zoom deixa de reescalar os textos
    linhas = []
    for pr in prims:
        t = pr["t"]
        c = _cor(pr.get("nv", 0))
        if t == "linha":
            x1, y1, x2, y2 = pr["p"]
            linhas.append(((x1, y1), (x2, y2), c, _traco(pr)))
        elif t == "poli":
            if pr.get("cheio"):
                ax.add_patch(Polygon(pr["xy"], closed=True, fc=c, ec=c, lw=0.5))
            else:
                for a, b in zip(pr["xy"], pr["xy"][1:]):
                    linhas.append((a, b, c, _traco(pr)))
        elif t == "circ":
            ax.add_patch(Circle((pr["x"], pr["y"]), pr["r"], fill=False, ec=c, lw=0.9, ls=_traco(pr)))
        elif t == "arco":
            ax.add_patch(Arc((pr["x"], pr["y"]), 2 * pr["r"], 2 * pr["r"], theta1=pr["a1"], theta2=pr["a2"], ec=c, lw=0.9))
        elif t == "texto":
            tx.add(pr["x"], pr["y"], pr["s"], pr["h"], pr.get("ang", 0.0), c)
        elif t == "cota":
            _cota(pr, linhas, tx, escala)
        elif t == "fercor":
            ax.add_patch(Circle((pr["x"], pr["y"]), pr["esc"] / 2, fc=c, ec=c))
        elif t == "quant":
            _quant(pr, linhas, tx)
    for f in ferros:
        _ferro(ax, f, linhas, tx, escala)
    grupos = {}
    for a, b, c, ls in linhas:
        grupos.setdefault((c, ls), []).append((a, b))
    for (c, ls), segs in grupos.items():
        ax.add_collection(LineCollection(segs, colors=c, linewidths=ESPESSURA.get(c, 0.8), linestyles=ls))
    pts = [v for a, b, _, _ in linhas for v in (a, b)] + tx.caixa
    for pa in ax.patches:
        if isinstance(pa, (Circle, Arc)):
            (x, y), r = pa.center, (pa.radius if isinstance(pa, Circle) else pa.width / 2)
            pts.extend([(x - r, y - r), (x + r, y + r)])
        else:
            pts.extend(map(tuple, pa.get_xy()))
    if pts:
        xs, ys = [v[0] for v in pts], [v[1] for v in pts]
        mx, my = 0.02 * (max(xs) - min(xs) or 1), 0.02 * (max(ys) - min(ys) or 1)
        ax.set_xlim(min(xs) - mx, max(xs) + mx)
        ax.set_ylim(min(ys) - my, max(ys) + my)
    tx.ajustar()
    return tx


def salvar_png(prims, ferros, caminho, escala=50, largura_pol=16):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(largura_pol, largura_pol * 0.62))
    desenhar(ax, prims, ferros, escala)
    fig.savefig(caminho, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return caminho
