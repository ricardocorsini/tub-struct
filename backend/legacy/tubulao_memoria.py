# -*- coding: utf-8 -*-
"""
Memória de cálculo do tubulão curto: página HTML autocontida (gráficos SVG, modo claro e escuro, impressão em A4)
e PDF pelo Edge sem janela. Sem referência à empresa (pedido do usuário em 17/10/2026).

Gráficos: perfil de sondagem (furos, média e envoltória), elevação esquemática, reação lateral com a envoltória
p_u, pressões na base em planta, curva de ruptura (pushover), esforços no fuste, comparação dos métodos e mapa
D × L do dimensionamento. Cada gráfico tem a tabela correspondente na própria memória.

Uso: python tubulao_memoria.py <parametros.json> [--saida PASTA] [--sem-pdf]
"""
import os, sys, math, html, json, datetime, subprocess, tempfile, shutil
import dependencias                       # cópia portátil: sem o numpy, diz o que falta e sai
dependencias.exigir_calculo()
import numpy as np
import tubulao_core as tcore
import tubulao_solo as so

AQUI = os.path.dirname(os.path.abspath(__file__))
G = so.G
E = html.escape


# ------------------------------------------------------------------------------------------------ formatação
def n(v, c=2):
    if v is None:
        return "—"
    if isinstance(v, str):
        return v
    if isinstance(v, float) and math.isinf(v):
        return "> 20" if v > 0 else "—"
    return f"{v:,.{c}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def kpa(v):
    return f"{n(v, 1)} kPa ({n(v / 98.0665, 2)} kgf/cm²)"


def mm(v):
    return f"{n(v * 1000, 1)} mm"


def ok_txt(ok):
    return '<span class="st ok">✓ atende</span>' if ok else '<span class="st nok">✗ não atende</span>'


# ------------------------------------------------------------------------------------------------ SVG
def _nice(lo, hi, n_ticks=5):
    if hi - lo <= 0:
        hi = lo + 1
    span = hi - lo
    passo = 10 ** math.floor(math.log10(span / n_ticks))
    for f in (1, 2, 2.5, 5, 10):
        if span / (passo * f) <= n_ticks:
            passo *= f
            break
    a = math.floor(lo / passo) * passo
    b = math.ceil(hi / passo) * passo
    ticks, t = [], a
    while t <= b + passo * 1e-6:
        ticks.append(round(t, 10))
        t += passo
    return a, b, ticks


_N_GRAF = [0]


class Grafico:
    """Gráfico x-y em SVG com eixos, grade e marcas. y_prof=True: profundidade crescendo para baixo."""

    def __init__(self, xr, yr, w=640, h=420, rx="", ry="", y_prof=False, ml=64, mr=24, mt=16, mb=46, fx=None, fy=None):
        self.w, self.h, self.ml, self.mr, self.mt, self.mb = w, h, ml, mr, mt, mb
        self.x0, self.x1, self.xt = _nice(*xr)
        self.y0, self.y1, self.yt = _nice(*yr)
        self.y_prof, self.rx, self.ry = y_prof, rx, ry
        self.fx = fx or (lambda v: n(v, 0 if abs(self.x1 - self.x0) >= 10 else (1 if abs(self.x1 - self.x0) >= 1 else 3)))
        self.fy = fy or (lambda v: n(v, 0 if abs(self.y1 - self.y0) >= 10 else (1 if abs(self.y1 - self.y0) >= 1 else 3)))
        self.el = []
        _N_GRAF[0] += 1
        self.id = f"g{_N_GRAF[0]}"

    def X(self, v):
        return self.ml + (v - self.x0) / (self.x1 - self.x0) * (self.w - self.ml - self.mr)

    def Y(self, v):
        f = (v - self.y0) / (self.y1 - self.y0)
        if not self.y_prof:
            f = 1 - f
        return self.mt + f * (self.h - self.mt - self.mb)

    def linha(self, xs, ys, cls="s1", titulo=None, pontos=False, larg=2, tracejado=False, dica=None):
        pts = " ".join(f"{self.X(x):.1f},{self.Y(y):.1f}" for x, y in zip(xs, ys) if x is not None and y is not None)
        d = ' stroke-dasharray="6 4"' if tracejado else ""
        t = f"<title>{E(titulo)}</title>" if titulo else ""
        self.el.append(f'<polyline class="ln {cls}" points="{pts}" stroke-width="{larg}"{d} fill="none" '
                       f'clip-path="url(#{self.id})">{t}</polyline>')
        if pontos or dica:
            for i, (x, y) in enumerate(zip(xs, ys)):
                if x is None or y is None or not (min(self.x0, self.x1) <= x <= max(self.x0, self.x1)):
                    continue
                tt = dica(i) if dica else f"{titulo}: {self.fx(x)} / {self.fy(y)}"
                if pontos:
                    self.el.append(f'<circle class="pt {cls}" cx="{self.X(x):.1f}" cy="{self.Y(y):.1f}" r="4"><title>{E(tt)}</title></circle>')
                else:                                       # alvo invisível para a dica, sem anel
                    self.el.append(f'<circle class="hit" cx="{self.X(x):.1f}" cy="{self.Y(y):.1f}" r="7"><title>{E(tt)}</title></circle>')

    def area(self, xs, ys, cls="s1", base=0.0, titulo=None, vertical=False):
        """Área entre a curva e o eixo (vertical=True: entre a curva e x = base, para diagramas em profundidade)."""
        if vertical:
            pts = [(self.X(base), self.Y(ys[0]))] + [(self.X(x), self.Y(y)) for x, y in zip(xs, ys)] + [(self.X(base), self.Y(ys[-1]))]
        else:
            pts = [(self.X(xs[0]), self.Y(base))] + [(self.X(x), self.Y(y)) for x, y in zip(xs, ys)] + [(self.X(xs[-1]), self.Y(base))]
        t = f"<title>{E(titulo)}</title>" if titulo else ""
        self.el.append(f'<polygon class="ar {cls}" points="{" ".join(f"{a:.1f},{b:.1f}" for a, b in pts)}" '
                       f'clip-path="url(#{self.id})">{t}</polygon>')

    def vref(self, x, rot="", cls="ref"):
        self.el.append(f'<line class="{cls}" x1="{self.X(x):.1f}" x2="{self.X(x):.1f}" y1="{self.mt}" y2="{self.h - self.mb}"/>')
        if rot:
            self.el.append(f'<text class="rot" x="{self.X(x) + 4:.1f}" y="{self.mt + 12}">{E(rot)}</text>')

    def href(self, y, rot="", cls="ref", ancora="end"):
        self.el.append(f'<line class="{cls}" x1="{self.ml}" x2="{self.w - self.mr}" y1="{self.Y(y):.1f}" y2="{self.Y(y):.1f}"/>')
        if rot:
            xx = self.w - self.mr - 4 if ancora == "end" else self.ml + 4
            self.el.append(f'<text class="rot" text-anchor="{ancora}" x="{xx:.1f}" y="{self.Y(y) - 4:.1f}">{E(rot)}</text>')

    def texto(self, x, y, s, cls="rot", ancora="start", dx=0, dy=0):
        self.el.append(f'<text class="{cls}" text-anchor="{ancora}" x="{self.X(x) + dx:.1f}" y="{self.Y(y) + dy:.1f}">{E(s)}</text>')

    def svg(self, rotulo=""):
        g = []
        for t in self.xt:
            X = self.X(t)
            g.append(f'<line class="grd" x1="{X:.1f}" x2="{X:.1f}" y1="{self.mt}" y2="{self.h - self.mb}"/>')
            g.append(f'<text class="tk" text-anchor="middle" x="{X:.1f}" y="{self.h - self.mb + 16}">{E(self.fx(t))}</text>')
        for t in self.yt:
            Y = self.Y(t)
            g.append(f'<line class="grd" x1="{self.ml}" x2="{self.w - self.mr}" y1="{Y:.1f}" y2="{Y:.1f}"/>')
            g.append(f'<text class="tk" text-anchor="end" x="{self.ml - 6}" y="{Y + 4:.1f}">{E(self.fy(t))}</text>')
        g.append(f'<text class="ax" text-anchor="middle" x="{(self.ml + self.w - self.mr) / 2:.1f}" y="{self.h - 8}">{E(self.rx)}</text>')
        g.append(f'<text class="ax" text-anchor="middle" transform="translate(14 {(self.mt + self.h - self.mb) / 2:.1f}) rotate(-90)">{E(self.ry)}</text>')
        clip = (f'<clipPath id="{self.id}"><rect x="{self.ml}" y="{self.mt}" width="{self.w - self.ml - self.mr}" '
                f'height="{self.h - self.mt - self.mb}"/></clipPath>')
        return (f'<svg class="graf" viewBox="0 0 {self.w} {self.h}" role="img" aria-label="{E(rotulo)}"><defs>{clip}</defs>'
                + "".join(g) + "".join(self.el) + "</svg>")


def legenda(itens):
    """itens: [(classe, rótulo, tracejado)]"""
    out = []
    for cls, rot, tr in itens:
        d = ' stroke-dasharray="5 3"' if tr else ""
        out.append(f'<span class="lg"><svg width="22" height="10"><line class="ln {cls}" x1="1" x2="21" y1="5" y2="5" '
                   f'stroke-width="2.5"{d}/></svg>{E(rot)}</span>')
    return '<div class="legenda">' + "".join(out) + "</div>"


def figura(svg, titulo, nota="", leg=""):
    return (f'<figure><figcaption>{E(titulo)}</figcaption>{leg}{svg}'
            + (f'<p class="nota">{nota}</p>' if nota else "") + "</figure>")


# ------------------------------------------------------------------------------------------------ figuras
CORES_FAM = {"Granular": "fam-g", "Intermediário": "fam-i", "Coesivo": "fam-c"}


def fig_elevacao(res, ap):
    p = res["p"]
    g, cm, apo = p["geometria"], p["camisa"], p["apoio"]
    D, L, De, Dc = g["D"], g["L"], g["D_escavacao"], g["D_estrutura"]
    topo, base = g["cota_topo"], g["cota_base"]
    fundo = base - max(1.5 * D, 1.0)
    alto = topo + max(0.6, 0.25 * L)
    W, H = 640, 560
    largura = max(3.2 * De, 4.0)
    esc = min((W - 220) / largura, (H - 40) / (alto - fundo))
    cx = 330
    X = lambda x: cx + x * esc
    Y = lambda c: 20 + (alto - c) * esc
    el = []
    cams = [c for c in ap["camadas"] if c["base"] < g["cota_terreno"] and c["topo"] > fundo]
    for c in cams:
        y1, y2 = Y(min(c["topo"], g["cota_terreno"])), Y(max(c["base"], fundo))
        el.append(f'<rect class="{CORES_FAM.get(c["familia"], "fam-i")}" x="{X(-largura / 2):.1f}" y="{y1:.1f}" '
                  f'width="{largura * esc:.1f}" height="{y2 - y1:.1f}"><title>{E(c["solo"])} — N = {c["nspt"]:.0f}</title></rect>')
        el.append(f'<text class="tk" x="{X(-largura / 2) - 6:.1f}" y="{(y1 + y2) / 2 + 4:.1f}" text-anchor="end">N {c["nspt"]:.0f} · '
                  f'{E(c["solo"][:16])}</text>')
    el.append(f'<line class="terreno" x1="{X(-largura / 2):.1f}" x2="{X(largura / 2):.1f}" y1="{Y(g["cota_terreno"]):.1f}" '
              f'y2="{Y(g["cota_terreno"]):.1f}"/>')
    na = res["solo"]["na"]
    if na is not None and fundo < na < alto:
        el.append(f'<line class="na" x1="{X(-largura / 2):.1f}" x2="{X(largura / 2):.1f}" y1="{Y(na):.1f}" y2="{Y(na):.1f}"/>'
                  f'<text class="rot" x="{X(largura / 2) - 4:.1f}" y="{Y(na) - 4:.1f}" text-anchor="end">NA {n(na)}</text>')
    la = p["lastro"]["espessura"]
    # escavação e folga
    if cm["usar"]:
        el.append(f'<rect class="folga" x="{X(-De / 2):.1f}" y="{Y(topo):.1f}" width="{De * esc:.1f}" height="{(L + la) * esc:.1f}">'
                  f'<title>Folga preenchida: {E(p["folga"]["preenchimento"])}</title></rect>')
    el.append(f'<rect class="lastro" x="{X(-De / 2):.1f}" y="{Y(base):.1f}" width="{De * esc:.1f}" height="{la * esc:.1f}"/>')
    el.append(f'<rect class="concreto" x="{X(-Dc / 2):.1f}" y="{Y(topo):.1f}" width="{Dc * esc:.1f}" height="{L * esc:.1f}">'
              f'<title>Concreto de enchimento</title></rect>')
    if cm["usar"]:
        e_ = (D - Dc) / 2
        n_an = math.ceil(L / cm["altura"] - 1e-6)
        for i in range(n_an):
            c1 = topo - i * cm["altura"]
            c2 = max(topo - (i + 1) * cm["altura"], base)
            for s in (-1, 1):
                x0 = X(s * Dc / 2) if s > 0 else X(-D / 2)
                el.append(f'<rect class="anel" x="{x0:.1f}" y="{Y(c1):.1f}" width="{e_ * esc:.1f}" height="{(c1 - c2) * esc:.1f}">'
                          f'<title>Anel {i + 1}: DN {n(cm["DN"])} m × {n(cm["altura"])} m</title></rect>')
    else:
        el.append(f'<rect class="contorno" x="{X(-D / 2):.1f}" y="{Y(topo):.1f}" width="{D * esc:.1f}" height="{L * esc:.1f}"/>')
    # apoio
    if apo["tipo"] == "pilar":
        a = apo["a"] if apo["secao"] == "retangular" else apo["d"]
        el.append(f'<rect class="pilar" x="{X(-a / 2):.1f}" y="{Y(alto):.1f}" width="{a * esc:.1f}" height="{(alto - topo) * esc:.1f}"/>')
    elif apo["tipo"] == "poste":
        a = 0.35
        el.append(f'<rect class="pilar" x="{X(-a / 2):.1f}" y="{Y(alto):.1f}" width="{a * esc:.1f}" '
                  f'height="{(alto - topo + min(apo["embutimento"], L)) * esc:.1f}" fill-opacity="0.85"/>')
    # cargas
    yt = Y(topo)
    el.append(f'<line class="seta" x1="{X(-largura / 2) + 30:.1f}" x2="{X(0) - 8:.1f}" y1="{yt - 22:.1f}" y2="{yt - 22:.1f}" marker-end="url(#ponta)"/>'
              f'<text class="rot" x="{X(-largura / 2) + 30:.1f}" y="{yt - 28:.1f}">H</text>')
    el.append(f'<line class="seta" x1="{X(0):.1f}" x2="{X(0):.1f}" y1="{yt - 70:.1f}" y2="{yt - 30:.1f}" marker-end="url(#ponta)"/>'
              f'<text class="rot" x="{X(0) + 6:.1f}" y="{yt - 60:.1f}">N</text>')
    el.append(f'<path class="seta" d="M {X(0.6 * De):.1f} {yt - 40:.1f} A 26 26 0 0 1 {X(0.6 * De) + 26:.1f} {yt - 14:.1f}" '
              f'fill="none" marker-end="url(#ponta)"/><text class="rot" x="{X(0.6 * De) + 30:.1f}" y="{yt - 30:.1f}">M</text>')
    # cotas
    xc = X(De / 2) + 30
    el.append(f'<line class="cota" x1="{xc:.1f}" x2="{xc:.1f}" y1="{Y(topo):.1f}" y2="{Y(base):.1f}"/>'
              f'<text class="rot" x="{xc + 6:.1f}" y="{(Y(topo) + Y(base)) / 2:.1f}">L = {n(L)} m</text>')
    el.append(f'<text class="rot" x="{xc + 6:.1f}" y="{Y(topo) + 4:.1f}">topo {n(topo)}</text>'
              f'<text class="rot" x="{xc + 6:.1f}" y="{Y(base) + 4:.1f}">base {n(base)}</text>')
    yb = Y(base) + la * esc + 18
    el.append(f'<line class="cota" x1="{X(-D / 2):.1f}" x2="{X(D / 2):.1f}" y1="{yb:.1f}" y2="{yb:.1f}"/>'
              f'<text class="rot" x="{X(0):.1f}" y="{yb + 14:.1f}" text-anchor="middle">D = {n(D)} m'
              + (f" (anel DN {n(cm['DN'])} + 2 × {n(cm['espessura'] * 100, 0)} cm)" if cm["usar"] else "") + "</text>")
    defs = '<defs><marker id="ponta" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" class="seta-ponta"/></marker></defs>'
    return f'<svg class="graf" viewBox="0 0 {W} {H}" role="img" aria-label="Elevação esquemática">{defs}{"".join(el)}</svg>'


def fig_nspt(res):
    s = res["solo"]
    pg = s["perfis_geospt"]
    comp = pg["compatibilizacao"]["linhas"]
    furos = s["nomes"]
    g = res["p"]["geometria"]
    cotas = [c["cotaRef_m"] for c in comp]
    if not cotas:
        return ""
    nmax = max([v for c in comp for v in c["nsptPorSondagem"].values() if v is not None] + [10])
    gr = Grafico((0, min(50, nmax)), (min(cotas) - 1, max(cotas) + 1), w=620, h=520, rx="NSPT", ry="cota (m)", y_prof=False)
    for i, f in enumerate(furos):
        xs = [c["nsptPorSondagem"][f] for c in comp]
        gr.linha(xs, cotas, "neutro", f"furo {f}", larg=1.2, dica=lambda k, f=f, xs=xs: f"{f}, cota {cotas[k]}: N = {xs[k]}")
    med = pg["media"]["camadas"]
    gr.linha([c["nspt"] for c in med], [c["cota_m"] for c in med], "s1", "sondagem média", larg=2.5, pontos=True)
    env = pg["envoltoria"]
    gr.linha([c["nspt"] for c in env], [c["cota_m"] for c in env], "s2", "envoltória mínima", larg=2.5, pontos=True)
    gr.href(g["cota_terreno"], "terreno", ancora="start")
    gr.href(g["cota_base"], f"base do tubulão {n(g['cota_base'])}", cls="ref2", ancora="start")
    if s["na"] is not None and min(cotas) - 1 < s["na"] < max(cotas) + 1:
        gr.href(s["na"], "NA", cls="na2")
    leg = legenda([("neutro", "furos", False), ("s1", "sondagem média", False), ("s2", "envoltória mínima", False)])
    return figura(gr.svg("NSPT por cota"), "Sondagens compatibilizadas por cota (convenção do GEOSPT: o NSPT da cota c vale para [c, c − 1])", leg=leg)


def _q_assinado(ap, e):
    m = ap["modelo"]
    th = e["theta"]
    if th <= 0:
        return [0.0] * len(m.z)
    ex, ey = e["tx"] / th, e["ty"] / th
    return [(fx * ex + fy * ey) / dz for fx, fy, dz in zip(e["fx"], e["fy"], m.dz)]


def fig_lateral(res, ap, e):
    m = ap["modelo"]
    cr = res["p"]["criterios"]
    z = m.z.tolist()
    q = _q_assinado(ap, e)
    pu = m.pu.tolist()
    lim = [v / cr["fs_passivo"] for v in pu]
    ql = None
    if e.get("linear"):
        th = e["linear"]["theta"]
        # solução linear: q = -nh·zs·(u - θ·z) na direção da inclinação
        U = e["linear"]["U"]
        if th > 0:
            ex, ey = U[2] / th, U[3] / th
            u0 = U[0] * ex + U[1] * ey
            ql = [-(nh * zs) * (u0 - th * zz) for nh, zs, zz in zip(m.nh, m.zs, m.z)]
    qmax = max([abs(v) for v in q + (ql or [])] + [1e-3])
    vmax = min(max(pu + [1.0]), max(3.0 * qmax, 1.0))           # escala na reação; a envoltória p_u é recortada
    gr = Grafico((-vmax, vmax), (0, m.L), w=620, h=420, rx="reação do solo por metro de fuste (kN/m)",
                 ry="profundidade a partir do topo (m)", y_prof=True)
    gr.area(pu, z, "pu-env", base=0.0, vertical=True, titulo="p_u")
    gr.area([-v for v in pu], z, "pu-env", base=0.0, vertical=True, titulo="−p_u")
    gr.linha(pu, z, "s2", "p_u (último)", larg=1.6)
    gr.linha([-v for v in pu], z, "s2", "−p_u", larg=1.6)
    gr.linha(lim, z, "s3", f"p_u/{n(cr['fs_passivo'], 1)} (admissível)", larg=1.6, tracejado=True)
    gr.linha([-v for v in lim], z, "s3", "−p_u/FS", larg=1.6, tracejado=True)
    if ql:
        gr.linha(ql, z, "neutro", "solução linear (R01/R02)", larg=1.4, tracejado=True)
    gr.linha(q, z, "s1", "reação calculada (base sem tração, molas elastoplásticas)", larg=2.6,
             dica=lambda i: f"z = {n(z[i])} m: q = {n(q[i], 1)} kN/m; p_u = {n(pu[i], 1)} kN/m; mobilização {n(abs(q[i]) / max(pu[i], 1e-9), 2)}")
    if e.get("z0") is not None and 0 < e["z0"] < m.L:
        gr.href(e["z0"], f"ponto de rotação z0 = {n(e['z0'])} m", cls="ref2")
    gr.vref(0.0)
    leg = legenda([("s1", "reação do solo calculada", False), ("s2", "± p_u: resistência última do solo (ruptura)", False),
                   ("s3", f"± p_u/{n(cr['fs_passivo'], 1)}: limite de serviço (NBR 6122, 7.6.3)", True)]
                  + ([("neutro", "solução linear de R01/R02", True)] if ql else []))
    nota = ("Linha cheia (± p_u): a maior reação que o solo consegue dar em cada profundidade pelo método escolhido; se a reação "
            "chegar nela, a camada plastifica. Tracejada (± p_u/" + n(cr['fs_passivo'], 1) + "): o limite de serviço, com o empuxo "
            "passivo reduzido como manda a NBR 6122 (7.6.3); a reação calculada (azul) deve ficar entre as tracejadas, isto é, "
            "mobilização |q|/p_u ≤ " + n(1 / cr['fs_passivo'], 2) + ". Valores negativos: o solo empurra no sentido contrário à carga "
            "(acima do ponto de rotação); abaixo dele a reação troca de sentido. A escala segue a reação, por isso p_u sai do gráfico "
            "perto do topo; a faixa sombreada é a resistência última.")
    out = figura(gr.svg("Reação lateral"), f"Reação lateral do solo — {e['nome']}", nota, leg)
    mob = [abs(a) / max(b, 1e-9) for a, b in zip(q, pu)]
    g2 = Grafico((0, max(1.0, max(mob) * 1.1)), (0, m.L), w=620, h=300, rx="mobilização │q│/p_u", ry="profundidade (m)",
                 y_prof=True)
    g2.area(mob, z, "s1a", base=0.0, vertical=True)
    g2.linha(mob, z, "s1", "mobilização", larg=2.2, dica=lambda i: f"z = {n(z[i])} m: {n(mob[i], 3)}")
    g2.vref(1 / cr["fs_passivo"], f"limite 1/FS = {n(1 / cr['fs_passivo'], 2)}", cls="ref2")
    out += figura(g2.svg("Mobilização"), "Mobilização da resistência lateral ao longo do fuste",
                  f"Máximo {n(max(mob), 3)}; a NBR 6122 (7.6.3) reduz o empuxo passivo por no mínimo 2,0 "
                  f"(limite {n(1 / cr['fs_passivo'], 2)}).")
    return out


def fig_base(res, ap, e):
    m = ap["modelo"]
    R = m.Dbase / 2
    nr, nt = res["p"]["analise"]["n_aneis_base"], res["p"]["analise"]["n_setores_base"]
    pb = np.array(e["pb"]).reshape(nt, nr)
    W = 360
    cx = cy = W / 2
    esc = (W / 2 - 12) / R
    pmax = max(float(pb.max()), 1e-9)
    rampa = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
    el = []
    rr = R * np.sqrt(np.arange(nr + 1) / nr)
    for it in range(nt):
        a0, a1 = 2 * math.pi * it / nt, 2 * math.pi * (it + 1) / nt
        for ir in range(nr):
            r0, r1 = rr[ir] * esc, rr[ir + 1] * esc
            v = pb[it, ir]
            if v <= 1e-9:
                cls, cor = "semcontato", ""
            else:
                k = min(int(v / pmax * len(rampa)), len(rampa) - 1)
                cls, cor = "", f' fill="{rampa[k]}"'
            pts = [(cx + r0 * math.cos(a0), cy - r0 * math.sin(a0)), (cx + r1 * math.cos(a0), cy - r1 * math.sin(a0)),
                   (cx + r1 * math.cos(a1), cy - r1 * math.sin(a1)), (cx + r0 * math.cos(a1), cy - r0 * math.sin(a1))]
            el.append(f'<polygon class="cel {cls}"{cor} points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in pts)}">'
                      f'<title>{n(v, 1)} kPa</title></polygon>')
    el.append(f'<circle class="contorno" cx="{cx}" cy="{cy}" r="{R * esc:.1f}" fill="none"/>')
    th = e["theta"]
    if th > 0:
        ang = math.atan2(e["ty"], e["tx"])
        el.append(f'<line class="seta" x1="{cx:.1f}" y1="{cy:.1f}" x2="{cx + 0.8 * R * esc * math.cos(ang):.1f}" '
                  f'y2="{cy - 0.8 * R * esc * math.sin(ang):.1f}" marker-end="url(#ponta2)"/>')
    escala = "".join(f'<rect x="{10 + i * 40}" y="0" width="38" height="12" fill="{c}"/>' for i, c in enumerate(rampa))
    escala += "".join(f'<text class="tk" x="{10 + i * 40}" y="26">{n(pmax * i / len(rampa), 0)}</text>' for i in range(0, len(rampa) + 1, 2))
    defs = '<defs><marker id="ponta2" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" class="seta-ponta"/></marker></defs>'
    svg = (f'<svg class="graf base" viewBox="0 0 {W} {W}" role="img" aria-label="Pressões na base">{defs}{"".join(el)}</svg>'
           f'<svg class="escala" viewBox="0 0 320 30">{escala}</svg>')
    nota = (f"Pressão de contato em planta (kPa), máximo {n(pmax, 0)} kPa; branco hachurado: base sem contato (o solo não "
            f"resiste à tração). A seta indica o sentido do tombamento. Área comprimida: {n(e['area_comp'] * 100, 0)} %.")
    return figura(svg, f"Pressões na base — {e['nome']}", nota)


def fig_pushover(res, ap):
    cr = res["p"]["criterios"]
    calc = cr["tombamento"] == "calculo"
    chave = "lam_d" if calc else "lam"
    es = sorted([e for e in ap["servico"] if e.get("pushover") and e["pushover"]["curva"]],
                key=lambda e: e[chave] if math.isfinite(e[chave]) else 1e9)[:3]
    if not es:
        return ""
    curvas = []
    for i, e in enumerate(es):
        curvas.append((f"s{i + 1}", e["nome"], e["pushover"]["curva"], False))
        if e.get("pushover_d") and e["pushover_d"]["curva"]:
            curvas.append((f"s{i + 1}", e["nome"] + " — de cálculo", e["pushover_d"]["curva"], True))
    lim = cr["gama_f_tombamento"] if calc else cr["fs_tombamento"]
    tmax = max(c[-1][1] for _, _, c, _ in curvas) * 1000
    lmax = max(max(p[0] for p in c) for _, _, c, _ in curvas)
    gr = Grafico((0, max(tmax, 1)), (0, max(lmax, lim) * 1.1), w=620, h=380, rx="rotação do tubulão (‰)",
                 ry="fator λ sobre as ações horizontais")
    itens = []
    for cls, nome, c, tr in curvas:
        gr.linha([p[1] * 1000 for p in c], [p[0] for p in c], cls, nome, larg=2, pontos=not tr, tracejado=tr)
        itens.append((cls, nome, tr))
    if calc:
        gr.href(lim, f"λd mínimo = γf = {n(lim, 1)} (NBR 6122, 6.2.1.1.2)", cls="ref2")
    else:
        gr.href(lim, f"FS mínimo = {n(lim, 1)}", cls="ref2")
    gr.href(1.0, "carga de serviço (λ = 1)", cls="ref")
    nota = (f"λ multiplica as ações horizontais e os momentos da combinação, com a força normal fixa. A curva para na rotação "
            f"convencional de ruptura ({n(cr['theta_ruptura'], 2)} rad) ou no colapso numérico.")
    if calc:
        nota += (f" Tracejado: modelo de cálculo da NBR 6122 (6.2.1.1.2), com p_u, q_ult e o atrito da base divididos por "
                 f"{n(cr['gama_m_solo'], 1)} e o peso favorável por {n(cr['gama_m_peso'], 1)}; o tombamento atende se λd ≥ "
                 f"γf = {n(lim, 1)}.")
    return figura(gr.svg("Curva de ruptura"), f"Curva carga × rotação até a ruptura ({ap['rotulo']})", nota, legenda(itens))


def fig_esforcos(res):
    env = res["estrutura"]["envelope"]
    if not env:
        return ""
    zs = sorted(set(round(s["z"], 4) for s in env))
    def envol(k):
        return [max(abs(s[k]) for s in env if abs(s["z"] - z) < 1e-6) for z in zs]
    svgs = []
    for k, rot, un in (("N", "força normal de cálculo", "kN"), ("V", "cortante de cálculo", "kN"), ("M", "momento fletor de cálculo", "kN·m")):
        v = envol(k)
        gr = Grafico((0, max(v + [1.0])), (0, max(zs)), w=300, h=360, rx=f"{rot} ({un})", ry="profundidade (m)", y_prof=True,
                     ml=48, mr=14)
        gr.area(v, zs, "s1a", base=0.0, vertical=True)
        gr.linha(v, zs, "s1", rot, larg=2, dica=lambda i, v=v, un=un: f"z = {n(zs[i])} m: {n(v[i], 1)} {un}")
        i = int(np.argmax(v))
        gr.texto(v[i], zs[i], f"{n(v[i], 0)}", ancora="end", dx=-4, dy=-4)
        svgs.append(gr.svg(rot))
    return figura('<div class="trio">' + "".join(svgs) + "</div>", "Envoltória dos esforços de cálculo no fuste (todas as combinações últimas)")


def fig_metodos(res, e):
    if not e.get("metodos"):
        return ""
    cr = res["p"]["criterios"]
    nomes = list(e["metodos"])
    vals = [e["metodos"][k]["lam"] for k in nomes]
    vals0 = [e["metodos"][k]["lam_sem_base"] for k in nomes]
    nb = sum(1 for k in nomes for v in (e["metodos"][k]["lam"], e["metodos"][k]["lam_sem_base"]) if v is not None and math.isfinite(v))
    W, H, ml = 620, 70 + 24 * nb + 14 * len(nomes), 210
    vmax = max([v for v in vals + vals0 if v and math.isfinite(v)] + [cr["fs_tombamento"]]) * 1.1
    _, vmax, ticks = _nice(0, vmax)
    X = lambda v: ml + v / vmax * (W - ml - 30)
    el = []
    for t in ticks:
        el.append(f'<line class="grd" x1="{X(t):.1f}" x2="{X(t):.1f}" y1="20" y2="{H - 30}"/><text class="tk" text-anchor="middle" x="{X(t):.1f}" y="{H - 14}">{n(t, 1)}</text>')
    y = 30
    for k, v, v0 in zip(nomes, vals, vals0):
        nome = e["metodos"][k]["nome"]
        for val, cls, rot in ((v, "s1", "com a base"), (v0, "s3", "sem a base")):
            if val is None or not math.isfinite(val):
                continue
            el.append(f'<rect class="bar {cls}" x="{ml}" y="{y}" width="{X(val) - ml:.1f}" height="18" rx="3"><title>{E(nome)} {rot}: λ = {n(val, 2)}</title></rect>'
                      f'<text class="tk" x="{X(val) + 6:.1f}" y="{y + 13}">{n(val, 2)}</text>'
                      f'<text class="tk" text-anchor="end" x="{ml - 8}" y="{y + 13}">{E(nome)} — {rot}</text>')
            y += 24
        y += 14
    rot_fs = "FS mínimo" if cr["tombamento"] == "global" else "FS global de referência"
    el.append(f'<line class="ref2" x1="{X(cr["fs_tombamento"]):.1f}" x2="{X(cr["fs_tombamento"]):.1f}" y1="20" y2="{H - 30}"/>'
              f'<text class="rot" x="{X(cr["fs_tombamento"]) + 4:.1f}" y="16">{rot_fs} {n(cr["fs_tombamento"], 1)}</text>')
    svg = f'<svg class="graf" viewBox="0 0 {W} {H}" role="img" aria-label="Comparação dos métodos">{"".join(el)}</svg>'
    return figura(svg, f"λ de ruptura por equilíbrio limite, por método — {e['nome']}",
                  "Com a base: momento resistente da força normal no segmento comprimido com q_ult e atrito na base. "
                  "Sem a base: como nas soluções clássicas de estacas curtas (Broms, Brinch Hansen).",
                  legenda([("s1", "com a base", False), ("s3", "sem a base", False)]))


def tabela_mapa(dim):
    if not dim:
        return ""
    Ls = dim["Ls"]
    Ds = sorted(set(m["D"] for m in dim["mapa"]))
    esc = dim["escolha"]
    oti = dim.get("otima") if dim.get("usuario") else None
    h = ['<table class="mapa"><tr><th>D (m) \\ L (m)</th>' + "".join(f"<th>{n(L)}</th>" for L in Ls) + "</tr>"]
    for D in Ds:
        h.append(f"<tr><th>{n(D)}</th>")
        for L in Ls:
            m = next((x for x in dim["mapa"] if abs(x["D"] - D) < 1e-9 and abs(x["L"] - L) < 1e-9), None)
            if m is None:
                h.append("<td></td>")
                continue
            a = min(m["aproveitamento"], 9.99) if m["aproveitamento"] is not None else None
            cls = "ok" if m["ok"] else "nok"
            sel = " escolha" if esc and abs(esc["D"] - D) < 1e-9 and abs(esc["L"] - L) < 1e-9 else ""
            if oti and abs(oti["D"] - D) < 1e-9 and abs(oti["L"] - L) < 1e-9:
                sel += " otima"
            tit = E(f"governa: {m['governante']}") if m.get("governante") else ""
            txt = "≥ 10" if a is None or a >= 9.99 else n(a, 2)
            h.append(f'<td class="{cls}{sel}" title="{tit}">{"✓ " if m["ok"] else ""}{txt}</td>')
        h.append("</tr>")
    h.append("</table>")
    return "".join(h)


# ------------------------------------------------------------------------------------------------ HTML
CSS = """
:root{color-scheme:light;--surface:#fcfcfb;--surface-2:#f4f3ef;--text:#0b0b0b;--text-2:#52514e;--muted:#7a7974;--grid:#e6e5e1;
--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--s4:#eda100;--neutro:#9a9993;--good:#0ca30c;--crit:#d03b3b;--line:#d8d7d2;
--fam-g:#f6ead2;--fam-i:#efe4d8;--fam-c:#e3e0db;--conc:#d9d9d6;--anel:#a9a9a4;--na:#2a78d6}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])){color-scheme:dark;--surface:#1a1a19;--surface-2:#242422;
--text:#f0efec;--text-2:#c3c2b7;--muted:#97968e;--grid:#34332f;--s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;--neutro:#7d7c76;
--line:#3d3c38;--fam-g:#3a3326;--fam-i:#352f2a;--fam-c:#30302d;--conc:#4a4a47;--anel:#6e6e69;--na:#3987e5}}
:root[data-theme="dark"]{color-scheme:dark;--surface:#1a1a19;--surface-2:#242422;--text:#f0efec;--text-2:#c3c2b7;--muted:#97968e;
--grid:#34332f;--s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;--neutro:#7d7c76;--line:#3d3c38;--fam-g:#3a3326;--fam-i:#352f2a;
--fam-c:#30302d;--conc:#4a4a47;--anel:#6e6e69;--na:#3987e5}
*{box-sizing:border-box}
body{margin:0;background:var(--surface);color:var(--text);font:14px/1.5 "Segoe UI",Arial,sans-serif}
main{max-width:960px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:24px;margin:0 0 4px}h2{font-size:18px;margin:36px 0 10px;padding-bottom:4px;border-bottom:1px solid var(--line)}
h3{font-size:15px;margin:22px 0 8px}p{margin:6px 0 10px}
.sub{color:var(--text-2)}.nota{color:var(--text-2);font-size:12.5px}
table{border-collapse:collapse;width:100%;margin:8px 0 14px;font-size:12.5px;font-variant-numeric:tabular-nums}
th,td{border:1px solid var(--line);padding:4px 6px;text-align:left;vertical-align:top}
th{background:var(--surface-2);font-weight:600}
td.num,th.num{text-align:right}
.st{font-weight:600;white-space:nowrap}.st.ok{color:var(--good)}.st.nok{color:var(--crit)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin:12px 0}
.card{border:1px solid var(--line);border-radius:8px;padding:10px 12px;background:var(--surface-2)}
.card .v{font-size:20px;font-weight:600}.card .l{color:var(--text-2);font-size:12px}
figure{margin:14px 0 22px}figcaption{font-weight:600;margin-bottom:6px}
svg.graf{width:100%;height:auto;display:block}svg.graf.base{max-width:380px}svg.escala{width:320px;height:30px}
.trio{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.grd{stroke:var(--grid);stroke-width:1}.tk{fill:var(--text-2);font-size:11px}.ax{fill:var(--text-2);font-size:12px}
.rot{fill:var(--text);font-size:11.5px}
.ln{stroke-linecap:round;stroke-linejoin:round}.ln.s1{stroke:var(--s1)}.ln.s2{stroke:var(--s2)}.ln.s3{stroke:var(--s3)}
.ln.s4{stroke:var(--s4)}.ln.neutro{stroke:var(--neutro)}
.pt{stroke:var(--surface);stroke-width:2}.hit{fill:transparent;stroke:none}.pt.s1{fill:var(--s1)}.pt.s2{fill:var(--s2)}.pt.s3{fill:var(--s3)}.pt.neutro{fill:var(--neutro)}
.ar.pu-env{fill:var(--s2);fill-opacity:.08}.ar.s1a{fill:var(--s1);fill-opacity:.12}
.bar.s1{fill:var(--s1)}.bar.s3{fill:var(--s3)}
.ref{stroke:var(--muted);stroke-width:1}.ref2{stroke:var(--text-2);stroke-width:1.2;stroke-dasharray:5 4}
.na2{stroke:var(--na);stroke-width:1.2;stroke-dasharray:2 3}
.legenda{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:12px;color:var(--text-2);margin:2px 0 6px}
.lg{display:inline-flex;align-items:center;gap:6px}
.fam-g{fill:var(--fam-g)}.fam-i{fill:var(--fam-i)}.fam-c{fill:var(--fam-c)}
.terreno{stroke:var(--text);stroke-width:2}.na{stroke:var(--na);stroke-width:1.5;stroke-dasharray:6 3}
.concreto{fill:var(--conc);stroke:var(--text-2);stroke-width:1}.anel{fill:var(--anel);stroke:var(--text-2);stroke-width:.8}
.folga{fill:var(--surface-2);stroke:var(--text-2);stroke-width:.8;stroke-dasharray:3 2}.lastro{fill:var(--neutro);fill-opacity:.5}
.contorno{stroke:var(--text);stroke-width:1.5;fill:none}.pilar{fill:var(--text-2);fill-opacity:.55}
.seta{stroke:var(--crit);stroke-width:2;fill:none}.seta-ponta{fill:var(--crit)}.cota{stroke:var(--text-2);stroke-width:1}
.cel{stroke:var(--surface);stroke-width:.4}.cel.semcontato{fill:var(--surface-2)}
table.mapa td{text-align:center;font-size:12px}table.mapa td.ok{background:color-mix(in srgb,var(--good) 14%,transparent)}
table.mapa td.nok{color:var(--muted)}table.mapa td.escolha{outline:2px solid var(--text);font-weight:700}table.mapa td.otima{outline:2px dashed var(--text-2)}
.alerta{border-left:3px solid var(--crit);padding:4px 10px;margin:6px 0;background:var(--surface-2)}
.aviso{border-left:3px solid var(--s4);padding:4px 10px;margin:6px 0;background:var(--surface-2)}
.info{border-left:3px solid var(--muted);padding:4px 10px;margin:6px 0;background:var(--surface-2)}
.formula{font-family:Consolas,"Cambria Math",monospace;background:var(--surface-2);padding:6px 10px;border-radius:6px;display:block;margin:6px 0;white-space:pre-wrap}
@media print{:root{color-scheme:light}body{font-size:11px;background:#fff}main{max-width:none;padding:0}
h2,h3{break-after:avoid}figure,.formula{break-inside:avoid}tr{break-inside:avoid}.nopr{display:none}}
@page{size:A4;margin:15mm 12mm}
"""


def _tab(cab, linhas, nums=()):
    h = ["<table><tr>" + "".join(f'<th class="{"num" if i in nums else ""}">{c}</th>' for i, c in enumerate(cab)) + "</tr>"]
    for l in linhas:
        h.append("<tr>" + "".join(f'<td class="{"num" if i in nums else ""}">{c}</td>' for i, c in enumerate(l)) + "</tr>")
    return "".join(h) + "</table>"


def _comb_critica(ap):
    serv = [e for e in ap["servico"] if e["theta"] > 0]
    return max(serv, key=lambda e: e["theta"]) if serv else ap["servico"][0]


def montar_html(res):
    p = res["p"]
    g, cm, mt, apo, cr, sl = p["geometria"], p["camisa"], p["materiais"], p["apoio"], p["criterios"], p["solo"]
    agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    H = []
    ok = res["ok"]
    H.append(f"<h1>Memória de cálculo — tubulão {E(p['nome'])}</h1>")
    H.append(f'<p class="sub">{E(p["descricao"] or "")}<br>{p["quantidade"]} unidade(s). Gerada em {agora}. '
             f"Programa de tubulões curtos, versão {tcore.VERSAO}.</p>")
    gv = res["governante"]
    H.append('<div class="cards">'
             f'<div class="card"><div class="l">Diâmetro × comprimento</div><div class="v">{n(g["D"])} × {n(g["L"])} m</div></div>'
             f'<div class="card"><div class="l">Situação</div><div class="v">{ok_txt(ok)}</div></div>'
             f'<div class="card"><div class="l">Verificação que governa</div><div class="v" style="font-size:14px">{E(gv["nome"]) if gv else "—"}</div></div>'
             f'<div class="card"><div class="l">Aproveitamento máximo</div><div class="v">{n(gv["aproveitamento"], 2) if gv else "—"}</div></div>'
             "</div>")
    # 1
    H.append("<h2>1. Objetivo e método</h2>")
    H.append("<p>Dimensionamento e verificação de tubulão curto, rígido e sem base alargada, sob força vertical, força "
             "horizontal e momento no topo. O tubulão gira como corpo rígido e mobiliza a reação lateral do solo; a base "
             "reage com pressões verticais, sem tração.</p>")
    H.append("<p>Modelo (seção 6): corpo rígido em molas. A reação lateral cresce com a profundidade (q = n<sub>h</sub>·z·y, R01, "
             "Fórm. 6.9.2) e é limitada pela resistência última p<sub>u</sub>(z) do método escolhido. A base é discretizada em "
             "pontos com coeficiente de reação vertical, sem tração e limitada a q<sub>ult</sub>. Sem plastificação e com a base "
             "comprimida, o modelo coincide com a solução de Pfeil (R01, 6.10) e de Timerman (R02), validadas na seção 15.</p>")
    # 2
    H.append("<h2>2. Normas e referências</h2>")
    refs = [("R01", "PFEIL, W. <i>Pontes em Concreto Armado</i>, cap. 6 (tubulões; 6.10 tubulão curto)."),
            ("R02", "TIMERMAN, J. Cálculo de tubulões curtos. <i>Revista Estrutura</i>, n. 90, p. 8–27, mar. 1980."),
            ("R03", "MARTINS, C. V. A. <i>Formulário para cálculo de tubulões curtos</i>, 1997."),
            ("R07", "ABNT NBR 6118:2026 — Projeto de estruturas de concreto."),
            ("R08", "ABNT NBR 6122:2022 — Projeto e execução de fundações (3.27, 3.28, 6.2.1.1.2, 6.3.2, 7.6.2, 7.6.3, 7.7, 8.2.3, "
                    "8.6.1 a 8.6.4, Tabelas 1 e 4, Anexo B)."),
            ("R09", "SCHENBERGER, L.; TOLLER, M. Cálculo de fundaciones (método de Sulzberger). UTN, 2022 — limite de rotação "
                    "da fundação de poste, tg α ≤ 0,01."),
            ("—", "BRINCH HANSEN, J. (1961). The ultimate resistance of rigid piles against transversal forces."),
            ("—", "BROMS, B. B. (1964). Lateral resistance of piles in cohesionless and cohesive soils."),
            ("—", "Correlações com o SPT: Godoy (1972, 1983), Teixeira (1996), Teixeira e Godoy (1996); método de Alonso para a tensão admissível.")]
    H.append(_tab(["Código", "Referência"], [[a, b] for a, b in refs]))
    cl, pc = res.get("classificacao"), res.get("concreto_6122")
    H.append("<h3>Critérios da NBR 6122:2022 (R08)</h3>")
    if cl:
        H.append(f"<p><b>Classificação.</b> {E(cl['texto'])} Para tubulões, o 8.2.3 aplica à base as regras da fundação rasa "
                 "(7.2 a 7.6), qualquer que seja a classificação.</p>")
    crit = [["Tensão admissível na base", f"q<sub>ult</sub> = {n(sl['fs_base'], 1)}·σ<sub>adm</sub> (Tabela 1: FS<sub>g</sub> = 3,0 "
             "por método analítico ou semiempírico)", "7.3, Tabela 1 (por 8.2.3.2)"],
            ["Vento", (f"σ<sub>adm</sub> × {n(cr['fator_sigma_vento'], 2)} só nas combinações em que o vento é a ação variável "
                       f"principal, com FS ≥ 1,6" + (" (obra da lista do item: até 30 %)" if cr["vento_obra_lista"] else " (até 15 %)")),
             "6.3.2"],
            ["Área comprimida da base", ("≥ 2/3" if abs(cr["area_comprimida_min"] - 2 / 3) < 1e-6 else
                                         f"≥ {n(cr['area_comprimida_min'] * 100, 0)} %") + " da base nas combinações características "
             "(solo sem tração)", "7.6.2 (por 8.2.3.5)"],
            ["Empuxo passivo", f"reação lateral ≤ p<sub>u</sub>/{n(cr['fs_passivo'], 1)} em serviço", "7.6.3 (por 8.2.3.5)"],
            ["Tombamento", (f"valores de cálculo: p<sub>u</sub>, q<sub>ult</sub> e atrito ÷ {n(cr['gama_m_solo'], 1)}; peso favorável "
                            f"÷ {n(cr['gama_m_peso'], 1)}; ações × {n(cr['gama_f_tombamento'], 1)} (λ<sub>d</sub> ≥ "
                            f"{n(cr['gama_f_tombamento'], 1)})") if cr["tombamento"] == "calculo" else
             f"FS global ≥ {n(cr['fs_tombamento'], 1)} (escolha do projetista)", "6.2.1.1.2"]]
    if pc:
        crit.append(["Concreto do tubulão", E(pc["nota"]), "8.6.3, 8.6.4.1, Tabela 4"])
        crit.append(["Armadura, quando necessária", f"mínimo de {n(cr['as_min_fuste'] * 100, 1)} % da seção em {n(cr['comp_min_armadura'], 1)} m; "
                     f"barras {n(cr['sacrificio_barras'], 0)} mm mais finas no cálculo (alternativa à verificação de fissuração)",
                     "Tabela 4; 8.6.2"])
    rlim, _ = tcore.limite_rotacao(p)
    if apo["tipo"] == "poste":
        txt_rot = (f"rotação ≤ {n(rlim * 1000, 1)} ‰ com poste (tg α ≤ {n(rlim, 2)}, método de Sulzberger, R09, p. 7: limite para não "
                   "alterar a flecha e a tração dos condutores)")
    else:
        txt_rot = f"rotação ≤ {n(rlim * 1000, 1)} ‰ (limite do projetista; depende da estrutura apoiada)"
    crit.append(["Deslocamentos e recalques", f"a norma não fixa valores (6.2.2): {txt_rot}; recalque ≤ "
                 f"{n(cr['recalque_lim'] * 1000, 0)} mm (limite do projetista)", "6.2.2" + ("; R09" if apo["tipo"] == "poste" else "")])
    H.append(_tab(["Item", "Critério adotado", "R08"], crit))
    # 3
    H.append("<h2>3. Dados</h2>")
    H.append(figura(fig_elevacao(res, res["analises"][0]["camadas"] if False else dict(camadas=res["solo"]["perfis"][0]["camadas"])),
                    "Elevação esquemática (camadas da primeira sondagem de cálculo)"))
    lin = [["Diâmetro externo (contato lateral) D", f"{n(g['D'])} m"],
           ["Diâmetro do concreto estrutural", f"{n(g['D_estrutura'])} m" + (" (enchimento dos anéis; os anéis não são estruturais)" if cm["usar"] and not cm["estrutural"] else "")],
           ["Comprimento L", f"{n(g['L'])} m"], ["Cota do topo / do terreno / da base", f"{n(g['cota_topo'])} / {n(g['cota_terreno'])} / {n(g['cota_base'])}"],
           ["Trecho desprezado no topo (reação lateral)", f"{n(g['desprezar_topo'])} m"]]
    if cm["usar"]:
        lin += [["Camisa", f"anéis pré-moldados DN {n(cm['DN'])} m, parede {n(cm['espessura'] * 100, 0)} cm, altura {n(cm['altura'])} m"],
                ["Folga entre os anéis e o solo", f"{n(p['folga']['largura'] * 100, 0)} cm, {E({'autoadensavel': 'preenchimento autoadensável (solo-cimento plástico, concreto magro ou argamassa fluida)', 'solo_cimento_compactado': 'aterro de solo-cimento compactado', 'nenhuma': 'sem folga'}[p['folga']['preenchimento']])}"],
                ["Escavação", f"Ø {n(g['D_escavacao'])} m"]]
    lin += [["Lastro", f"{n(p['lastro']['espessura'] * 100, 0)} cm de {E(p['lastro']['material'])}"],
            ["Concreto", f"C{mt['fck']:g} (γ = {n(mt['gama_c'], 0)} kN/m³), CAA {E(mt['caa'])}, cobrimento {n(mt['cobrimento'] * 100, 0)} cm"],
            ["Aço", f"CA-{mt['fyk'] / 10:g}"]]
    if apo["tipo"] == "pilar":
        lin.append(["Apoio", f"pilar {'%s × %s cm' % (n(apo['a'] * 100, 0), n(apo['b'] * 100, 0)) if apo['secao'] == 'retangular' else 'Ø %s cm' % n(apo['d'] * 100, 0)} apoiado direto no topo"])
    elif apo["tipo"] == "poste":
        lin.append(["Apoio", f"poste embutido {n(apo['embutimento'])} m (ancoragem fora do escopo)"])
    if apo["h_aplicacao"]:
        lin.append(["Altura do ponto de aplicação das cargas horizontais acima do topo", f"{n(apo['h_aplicacao'])} m"])
    H.append(_tab(["Item", "Valor"], lin))
    H.append("<h3>Ações características (no topo do tubulão)</h3>")
    H.append("<p class='nota'>Eixo z para cima; M<sub>x</sub> em torno de x e M<sub>y</sub> em torno de y. H<sub>x</sub> com M<sub>y</sub> &gt; 0 e "
             "H<sub>y</sub> com M<sub>x</sub> &lt; 0 tombam no mesmo sentido.</p>")
    H.append(_tab(["Ação", "Tipo", "Categoria / grupo", "N (kN)", "Hx (kN)", "Hy (kN)", "Mx (kN·m)", "My (kN·m)"],
                  [[E(a["nome"]), a["tipo"], E(f"{a.get('categoria', '')} / {a.get('grupo', '')}" if a["tipo"] == "variavel" else ""),
                    n(a["N"], 1), n(a["Hx"], 1), n(a["Hy"], 1), n(a["Mx"], 1), n(a["My"], 1)] for a in p["acoes"]], nums=(3, 4, 5, 6, 7)))
    cb = res["combinacoes"]
    H.append("<h3>Combinações (NBR 6118:2026, Tabelas 11.1 e 11.2)</h3>")
    H.append("<p>Geotecnia (tensão admissível, deslocamentos, ruptura): combinações características G + Q₁ + Σψ₀·Q<sub>j</sub>, "
             "sem majoração. Recalque: quase permanentes G + Σψ₂·Q<sub>j</sub>. Estrutura: combinações últimas normais "
             "γ<sub>g</sub>·G + γ<sub>q</sub>·(Q₁ + Σψ₀·Q<sub>j</sub>), com γ<sub>g</sub> = 1,4 e 1,0 (permanentes favoráveis). "
             "Ações do mesmo grupo são alternativas e não se somam. A tensão admissível só é majorada nas combinações "
             "características em que o vento é a ação principal Q₁ (R08, 6.3.2).</p>")
    def tab_comb(lst, principal=False):
        cab = ["Combinação", "N", "Hx", "Hy", "Mx", "My"] + (["Vento principal"] if principal else [])
        return _tab(cab, [[E(c["nome"])] + [n(v, 1) for v in c["F"]] + (["sim" if c.get("vento_principal") else ""] if principal else [])
                          for c in lst], nums=(1, 2, 3, 4, 5))
    H.append("<p><b>Características</b></p>" + tab_comb(cb["servico"], principal=True))
    H.append("<p><b>Quase permanentes</b></p>" + tab_comb(cb["quase_permanente"]))
    H.append("<details><summary><b>Últimas</b> (" + str(len(cb["ultima"])) + ")</summary>" + tab_comb(cb["ultima"]) + "</details>")
    # 4 sondagens
    s = res["solo"]
    H.append("<h2>4. Sondagens</h2>")
    H.append(f"<p>Cadastro e compatibilização como no GEOSPT (motor 2.0.7): cada leitura na cota boca − profundidade; grade de "
             f"cotas inteiras; cada furo entra com a leitura mais próxima dentro de ± {n(p['sondagem']['janela'])} m; sondagem média "
             f"pelo submodo {E(p['sondagem']['submodo'])} e envoltória mínima (o menor N<sub>SPT,cálculo</sub> = min(N, 50) da cota, com solo e "
             f"cor do mesmo furo). Furos: {E(', '.join(s['nomes']))}. NA de cálculo: "
             f"{('cota ' + n(s['na'])) if s['na'] is not None else 'não encontrado'} ({E(p['sondagem']['na_criterio'].replace('_', ' '))}).</p>")
    H.append(fig_nspt(res))
    comp = s["perfis_geospt"]["compatibilizacao"]["linhas"]
    med = {c["cota_m"]: c for c in s["perfis_geospt"]["media"]["camadas"]}
    env = {c["cota_m"]: c for c in s["perfis_geospt"]["envoltoria"]}
    lin = []
    for c in comp:
        k = c["cotaRef_m"]
        lin.append([str(k)] + [n(c["nsptPorSondagem"][f], 0) if c["nsptPorSondagem"][f] is not None else "—" for f in s["nomes"]]
                   + [n(med[k]["nspt"], 0) if k in med else "—", E(med[k]["solo"]) if k in med else "",
                      "sim" if c["heterogeneo"] else "", n(env[k]["nspt"], 0) if k in env else "—", E(env[k]["furo"]) if k in env else ""])
    H.append("<details><summary>Tabela da compatibilização</summary>" +
             _tab(["Cota"] + [E(f) for f in s["nomes"]] + ["Média", "Solo (média)", "Het.", "Mínima", "Furo"], lin) + "</details>")
    # 5 parâmetros
    H.append("<h2>5. Parâmetros do solo</h2>")
    H.append("<p>Uma camada por metro do perfil de cálculo. Cada valor tem a sua fonte; os marcados como digitados vieram do usuário. "
             "A camada entre o terreno e a primeira leitura recebe os parâmetros da primeira leitura.</p>")
    for pf in s["perfis"]:
        lin = []
        for c in pf["camadas"]:
            if c["base"] > g["cota_base"] - 2 * g["D"] - 1:
                lin.append([f"{n(c['topo'])} a {n(c['base'])}", n(c["nspt"], 0), E(c["solo"]), c["comportamento"].replace("_", " "),
                            n(c["gama"], 0), n(c["phi"], 1), n(c["su"], 0), n(c["nh"] / 1000, 2), n(c["kv"] / 1000, 1),
                            n(c["E"] / 1000, 1), n(c["nu"], 2), E(", ".join(c["editados"]))])
        H.append(f"<h3>{E(pf['rotulo'])}</h3>")
        H.append(_tab(["Cotas", "N", "Solo", "Comportamento", "γ (kN/m³)", "φ' (°)", "Su (kPa)", "n<sub>h</sub> (MN/m³)",
                       "k<sub>v</sub> (MN/m³)", "E (MPa)", "ν", "Digitados"], lin, nums=(1, 4, 5, 6, 7, 8, 9, 10)))
    c0 = s["perfis"][0]["camadas"][0]
    H.append("<p class='nota'>Fontes (primeira camada): " + "; ".join(f"{k}: {E(v)}" for k, v in c0["fontes"].items()) + ".</p>")
    # 6 modelo
    H.append("<h2>6. Modelo de cálculo</h2>")
    H.append('<span class="formula">Deslocamento do fuste na profundidade z:   u(z) = u₀ − θ·z      (corpo rígido)\n'
             'Reação lateral por metro:                 q(z) = n_h·z_s·u(z),  │q│ ≤ p_u(z)\n'
             'Pressão na base:                          p(x, y) = k_v·(w + θx·x + θy·y),  0 ≤ p ≤ q_ult\n'
             'Equilíbrio:  F_ext + Σ Bᵀ·f_solo(U) = 0,  U = (ux, uy, θx, θy, w)  — Newton-Raphson com rigidez tangente</span>')
    H.append(f"<p>Discretização: {p['analise']['n_fatias']} fatias no fuste e {p['analise']['n_aneis_base'] * p['analise']['n_setores_base']} "
             f"pontos na base. Resistência lateral última: <b>{E(so.METODOS_PU[sl['metodo_pu']])}</b>. Atrito na base: "
             f"{'considerado' if sl['atrito_base_servico'] else 'desprezado'} em serviço, {'considerado' if sl['atrito_base_ruptura'] else 'desprezado'} na ruptura.</p>")
    H.append('<span class="formula">Brinch Hansen:  p_u = (σv\'·K_q + c·K_c)·D,  K_q e K_c função de φ e de z/D\n'
             "Broms:          p_u = 3·K_p·σv'·D (drenado);  9·Su·D abaixo de 1,5·D (não drenado)\n"
             "Rankine 2D:     p_u = (K_p − K_a)·σv'·D;  4·Su·D (não drenado)   — como R01 (Fórm. 6.10.4) e R02</span>")
    # 7 por perfil
    sec = 7
    for ap in res["analises"]:
        e = _comb_critica(ap)
        m = ap["modelo"]
        rg = ap["rigidez"]
        H.append(f"<h2>{sec}. Resultados — {E(ap['rotulo'])}</h2>")
        sec += 1
        H.append("<h3>Rigidez relativa</h3>")
        H.append(f'<span class="formula">E = {n(rg["E"] / 1e6, 1)} GPa;  I = π·{n(g["D_estrutura"])}⁴/64 = {n(rg["I"], 4)} m⁴;  '
                 f'n_h médio = {n(rg["nh"] / 1000, 2)} MN/m³\nT = (E·I/n_h)^(1/5) = {n(rg["T"])} m;   Z = L/T = {n(rg["Z"])} '
                 f'{"≤" if rg["Z"] <= cr["z_rigido"] else ">"} {n(cr["z_rigido"], 1)}  → {"corpo rígido (R01: L ≤ 2·L0)" if rg["Z"] <= cr["z_rigido"] else "não é rígido"}</span>')
        H.append("<h3>Tensão admissível e coeficientes da base</h3>")
        H.append(f"<p>σ<sub>adm</sub> = {kpa(ap['sigma_adm'])} — {E(ap['sigma_adm_nota'])}. q<sub>ult</sub> = {n(sl['fs_base'], 1)} · σ<sub>adm</sub> "
                 f"= {kpa(ap['q_ult'])}. k<sub>v</sub> = {n(ap['kv'] / 1000, 1)} MN/m³ ({E(m.cam_base['fontes']['kv'])}). "
                 f"Atrito: {E(ap['atrito_nota'])} (μ = {n(ap['mu'], 3)}). Peso efetivo do tubulão: {n(ap['W'], 1)} kN "
                 f"(enchimento {n(ap['peso_enchimento'], 1)} kN, anéis {n(ap['peso_camisa'], 1)} kN).</p>")
        H.append("<h3>Serviço (combinações características)</h3>")
        lin = []
        for x in ap["servico"]:
            ua = x.get("u_aplicacao", x["u_topo"] + x["theta"] * (apo["h_aplicacao"] or 0))
            lin.append([E(x["nome"]), n(x["theta"] * 1000, 2), mm(x["u_topo"]), mm(ua), n(x["z0"]) if x["z0"] is not None and x["theta"] > 0 else "—",
                        n(x["p_max"], 0), n(x["e_base"], 3) if math.isfinite(x["e_base"]) else "—", n(x["area_comp"] * 100, 0),
                        n(max(x["mob"]), 2), n(x["lam"], 2), n(x.get("lam_d"), 2)])
        H.append(_tab(["Combinação", "θ (‰)", "u topo", "u aplicação", "z0 (m)", "p máx (kPa)", "e base (m)", "Área comp. (%)",
                       "Mobilização", "FS global", "λd"], lin, nums=(1, 2, 3, 4, 5, 6, 7, 8, 9, 10)))
        H.append(f"<p>Combinação mais desfavorável para a rotação: <b>{E(e['nome'])}</b>.</p>")
        H.append(fig_lateral(res, ap, e))
        H.append(fig_base(res, ap, e))
        if e.get("linear"):
            lnr = e["linear"]
            H.append("<h3>Comparação com a solução linear de R01/R02</h3>")
            H.append(_tab(["Grandeza", "Linear (base com tração, sem plastificação)", "Calculada (base sem tração, molas elastoplásticas)"],
                          [["Rotação θ (‰)", n(lnr["theta"] * 1000, 3), n(e["theta"] * 1000, 3)],
                           ["Deslocamento do topo", mm(lnr["u_topo"]), mm(e["u_topo"])],
                           ["Ponto de rotação z0 (m)", n(lnr["z0"]), n(e["z0"])],
                           ["Pressão máxima na base (kPa)", n(lnr["p_max"], 1), n(e["p_max"], 1)],
                           ["Pressão mínima na base (kPa)", n(lnr["p_min"], 1) + (" (tração: o modelo linear não vale)" if lnr["p_min"] < 0 else ""), n(e["p_min"], 1)]]))
            rf = e.get("referencias")
            if rf:
                H.append(f"<p>Limite elástico de R01 (Fórm. 6.10.5): m = n<sub>h</sub>·Δx = {n(rf['m'], 1)} kN/m² "
                         f"{'≤' if rf['m_ok'] else '>'} γ·a·(k<sub>p</sub> − k<sub>a</sub>) = {n(rf['gama'], 0)} · {n(g['D'])} · "
                         f"({n(rf['kp'], 2)} − {n(rf['ka'], 2)}) = {n(rf['m_lim'], 1)} kN/m² — {ok_txt(rf['m_ok'])}. "
                         f"Coeficiente de Sherif (R02/R03, sobre a solução linear): CS = A₂/A₁ = {n(rf['cs'], 2)} com K<sub>p</sub> e "
                         f"{n(rf['cs_reduzido'], 2)} com K<sub>p</sub>/2 (critério de R05). Só para comparação com o método antigo.</p>")
        H.append("<h3>Ruptura (tombamento)</h3>")
        H.append('<span class="formula">Equilíbrio limite (mecanismo de rotação em torno de z_r, teorema do limite superior):\n'
                 "λ(z_r) = [Σ P_i·|z_r − z_i| + T·|z_r − L| + M_b] / (H·z_r + M),   λ_último = min λ(z_r)\n"
                 "M_b = V·x̄ (força normal no segmento da base comprimido com q_ult);  T = μ·V\n"
                 f"λ = {'menor entre o equilíbrio limite e o pushover' if cr['fs_criterio'] == 'min' else cr['fs_criterio']} "
                 f"(pushover até θ = {n(cr['theta_ruptura'], 2)} rad)\n"
                 f"Valores de cálculo (R08, 6.2.1.1.2): P_i, q_ult e μ ÷ {n(cr['gama_m_solo'], 1)};  V = (peso + permanentes) ÷ "
                 f"{n(cr['gama_m_peso'], 1)}, variáveis favoráveis desprezadas;  exige λd ≥ γf = {n(cr['gama_f_tombamento'], 1)}</span>")
        calc = cr["tombamento"] == "calculo"
        lim = cr["gama_f_tombamento"] if calc else cr["fs_tombamento"]
        lin = [[E(x["nome"]), n(x.get("lam_le"), 2), n(x.get("lam_pushover"), 2), n(x["lam"], 2), n(x.get("N_tombamento"), 0),
                n(x.get("lam_d_le"), 2), n(x.get("lam_d_pushover"), 2), n(x.get("lam_d"), 2),
                ok_txt((x.get("lam_d") if calc else x["lam"]) >= lim)]
               for x in ap["servico"] if math.isfinite(x["lam"]) or x.get("lam_pushover") is not None]
        H.append(_tab(["Combinação", "λ eq. limite", "λ pushover", "FS global", "V de cálculo (kN)", "λd eq. limite", "λd pushover",
                       "λd adotado", (f"λd ≥ {n(lim, 1)}" if calc else f"FS ≥ {n(lim, 1)}")], lin, nums=(1, 2, 3, 4, 5, 6, 7)))
        H.append(fig_pushover(res, ap))
        H.append(fig_metodos(res, e))
        H.append("<h3>Recalque (quase permanente)</h3>")
        lin = []
        for x in ap["qp"]:
            r = x["recalque_el"]
            lin.append([E(x["nome"]), mm(x["w"]), mm(r["w"]), n(r["dq"], 1), n((r["E_eq"] or 0) / 1000, 1) if r["E_eq"] else "—", E(r["nota"])])
        H.append('<span class="formula">Winkler: w = recalque do centro da base no modelo (k_v)\n'
                 "Elástico: w = (π/4)·Δq·D·(1 − ν²)/E_eq, E_eq ponderado pelo acréscimo de tensão sob o centro (Boussinesq)</span>")
        H.append(_tab(["Combinação", "Winkler", "Elástico", "Δq (kPa)", "E_eq (MPa)", "Observação"], lin, nums=(1, 2, 3, 4)))
    # estrutura
    est = res["estrutura"]
    H.append(f"<h2>{sec}. Estrutura (NBR 6118:2026)</h2>")
    sec += 1
    H.append(fig_esforcos(res))
    cs = est.get("simples")
    if cs:
        gcs = cs.get("gama_c", 1.68)
        pc = est.get("concreto_6122") or {}
        H.append(f"<h3>Concreto simples (Seção 24)</h3><p>O fuste tem confinamento lateral (24.2: “caso de estacas ou tubos”). "
                 f"γ<sub>c</sub> = {n(gcs, 2)} ({E(pc.get('nota', 'R07, 24.5.2.1'))}); f<sub>cd</sub> = {n(cs['fcd'] / 1000, 2)} MPa; "
                 f"f<sub>ctd</sub> = 0,7·0,3·f<sub>ck</sub><sup>2/3</sup>/{n(gcs, 2)} = "
                 f"{n(cs['fctd'] / 1000, 3)} MPa. Seção {n(cs['h'])} m{' (5 cm menor: concreto lançado contra o solo, 24.5.3)' if g['contra_solo'] else ''}. "
                 f"Seção crítica a z = {n(cs['z'])} m, {E(cs['comb'])}.</p>")
        sk = cs.get("sigma_k")
        H.append(_tab(["Verificação", "Atuante (kPa)", "Resistente (kPa)", "Situação"],
                      ([["Compressão simples característica N/A (R08, Tabela 4)", n(sk, 0), n(pc.get("sigma_sem_armar", 5000), 0),
                         ok_txt(sk <= pc.get("sigma_sem_armar", 5000))]] if sk is not None else []) +
                      [["Compressão na fibra (24.5.2.2)", n(cs["s_max"], 0), n(cs["sc_rd"], 0), ok_txt(cs["ok_comp"])],
                       ["Tração na fibra (24.5.2.2)", n(max(-cs["s_min"], 0), 0), n(cs["st_rd"], 0), ok_txt(cs["ok_trac"])],
                       ["Cisalhamento 4V/(3A) (24.5.2.3)", n(cs["tau"], 1), n(cs["tau_rd"], 1), ok_txt(cs["ok_cis"])]], nums=(1, 2)))
        if not cs.get("ok", True):
            H.append("<p><b>O fuste não passa em concreto simples e passa a ser armado</b> (R08, 8.6.3): armadura longitudinal e "
                     "estribos a seguir. As linhas “não atende” acima mostram só por que a armadura é necessária.</p>")
    if est.get("armadura"):
        a = est["armadura"]
        H.append(f"<h3>Armadura longitudinal</h3><p>{a['n']} ø{n(a['bitola'], 1)} mm no contorno (A<sub>s</sub> = {n(a['As'] * 1e4, 1)} cm², "
                 f"espaçamento {n(a['espac'] * 100, 0)} cm), diagrama parábola-retângulo (8.2.10.1) com γ<sub>c</sub> = "
                 f"{n(a.get('gama_c', 1.4), 2)} (R08, 8.6.3), barras {n(a.get('sacrificio', 0), 0)} mm mais finas no cálculo "
                 f"(R08, 8.6.2) e mínimo de {n(cr['as_min_fuste'] * 100, 2)} % da seção (R08, Tabela 4). "
                 + (f"M<sub>Sd</sub> = {n(abs(a['M_Sd']), 1)} kN·m ≤ M<sub>Rd</sub> = {n(a['M_Rd'], 1)} kN·m. " if a.get("M_Rd") else "")
                 + f"Eixo das barras a {n(a.get('raio', 0) * 100, 1)} cm do centro, por dentro do estribo mais grosso.</p>")
        if a.get("z_fim") is not None:
            H.append(f"<p><b>Comprimento das barras: {n(a['comprimento'])} m</b>, do cobrimento do topo até z = {n(a['z_fim'])} m"
                     + (" (todo o fuste)" if a.get("inteiro") else "") + ". "
                     f"O concreto simples reprova até z = {n(a['z_falha'])} m (primeira seção que passa depois da última reprovada). "
                     f"As barras vão até o maior entre o mínimo de {n(cr['comp_min_armadura'], 1)} m da Tabela 4 (R08) e esse ponto mais "
                     f"o comprimento de ancoragem básico ℓ<sub>b</sub> = (φ/4)·(f<sub>yd</sub>/f<sub>bd</sub>) ≥ 25φ = {n(a['lb'])} m "
                     "(R07, 9.4.2.4: barra nervurada vertical, boa aderência, f<sub>ctd</sub> com o γ<sub>c</sub> do tubulão), "
                     "arredondado a 5 cm e limitado ao cobrimento da base. "
                     + ("" if a.get("inteiro") else "Abaixo das barras o fuste continua em concreto simples (verificação no resumo).")
                     + "</p>")
        e_ = a.get("estribo")
        if e_:
            H.append(f"<p>Estribos do fuste: <b>{e_['n']} estribos circulares ø{n(e_['bitola'], 1)} c/{n(e_['s'] * 100, 0)}</b> entre "
                     f"{n(e_['z1'])} m e {n(e_['z2'])} m abaixo do topo, como estribos de pilar (R07, 18.4.3): φ<sub>t</sub> ≥ 5 mm e "
                     f"≥ φ<sub>l</sub>/4; s ≤ 20 cm, ≤ D e ≤ 12·φ<sub>l</sub> = {n(e_['s_max'] * 100, 1)} cm. "
                     + ("Acima deles, a fretagem do topo faz o mesmo papel. " if est.get("bloco") and est["bloco"].get("fretagem") else "")
                     + "A força cortante é verificada com a resistência do concreto sozinho (24.5.2.3), a favor da segurança; "
                     "os estribos são construtivos.</p>")
    if est.get("bloco"):
        b = est["bloco"]
        v, vt = b["verif"], b["verif_t"]
        fr = b["fretagem"]
        H.append("<h3>Topo: bloco parcialmente carregado (21.2.1) e fendilhamento (Seção 22)</h3>")
        H.append(f"<p class='nota'>f<sub>cd</sub> do tubulão com γ<sub>c</sub> = {n((est.get('concreto_6122') or {}).get('gc_armado', 1.4), 2)} "
                 "(R08, 8.6.3 e Tabela 4, ou 8.6.4.1 com camisa); o pilar fica com γ<sub>c</sub> = 1,4.</p>")
        H.append(f'<span class="formula">Ac0 = {n(v["Ac0"], 3)} m²;  Ac1 (homotética inscrita) = {n(v["Ac1"], 3)} m²\n'
                 f'f_lim = f_cd·√(Ac1/Ac0) ≤ 3,3·f_cd = {n(v["f_lim"] / 1000, 2)} MPa\n'
                 f'Pressão de cálculo sob o pilar ({E(b["comb"])}): σ = {n(v["s_max"] / 1000, 2)} MPa — {"atende" if v["ok"] else "NÃO ATENDE"}\n'
                 f'Tirante: T = 0,25·C·(1 − a_c/D);  Tx = {n(vt["Tx"], 0)} kN, Ty = {n(vt["Ty"], 0)} kN ({E(b["comb_t"])})\n'
                 f'A_s,fret = T_d/f_yd = {n(vt["As_fret"] * 1e4, 2)} cm²</span>')
        H.append("<p class='nota'>Fora do núcleo central, o binário do pilar é C = N/2 + M/z (z = 0,8·a) com a armadura do pilar "
                 "tracionada (ancoragem fora do escopo) e bloco comprimido em 0,85·f<sub>cd</sub> do pilar.</p>")
        gr = b.get("grelha")
        opc = {"auto": "automático (grelha quando a/D < " + n(cr["fretagem_a_d_limite"], 2) + ")", "aneis": "só anéis",
               "grelha": "grelha + anéis"}.get(b.get("arranjo_opcao", "aneis"), "")
        H.append(f"<p>Arranjo da fretagem: <b>{'grelha nas duas direções + anéis construtivos' if gr else 'anéis'}</b> "
                 f"(opção do projeto: {E(opc)}; pilar/tubulão a/D = {n(b.get('a_D', 0), 2)}). Com o pilar pequeno em relação ao "
                 "tubulão, a tração de fendilhamento se concentra perto do eixo, sob o pilar, e a grelha a resiste ali. Os anéis "
                 "(fendilhamento anelar, R07, Figura 21.1a) atendem o equilíbrio cruzando o plano diametral duas vezes, mas ficam na "
                 "periferia.</p>")
        if gr:
            H.append(f"<p>Grelha: <b>{gr['n_camadas']} camadas c/{n(gr['s_camadas'] * 100, 0)}</b> entre {n(gr['z1'])} m e "
                     f"{n(gr['z2'])} m abaixo do topo; em cada camada, <b>{gr['nx']} ø{n(gr['bitola'], 1)} em x e {gr['ny']} "
                     f"ø{n(gr['bitola'], 1)} em y</b> a cada {n(gr['s_barras'] * 100, 0)} cm, centradas sob o pilar"
                     + (" (nas longitudinais mais próximas desses afastamentos)" if gr.get("apoio_ganchos") == "longitudinais" else "")
                     + f": grampos com ganchos de 180° nas pontas (pino de 5ø, R07, Tabela 9.1), que abraçam "
                     f"{'as barras de montagem' if gr.get('apoio_ganchos') != 'longitudinais' else 'as barras longitudinais'} junto aos "
                     "estribos: cada barra fica dentro do gancho, encostada no fundo dele, e a face externa do gancho fica no lugar do "
                     "estribo, sem invadir o cobrimento. Comprimento reto medido entre as faces externas dos ganchos, como no TQS: "
                     f"{' e '.join(n(c * 100, 0) for c in gr.get('comps', [gr['comp']]))} cm (uma posição por comprimento). "
                     f"A<sub>s,x</sub> = T<sub>x</sub>/f<sub>yd</sub> = {n(gr['As_x'] * 1e4, 2)} cm² ≤ "
                     f"{n(gr['As_x_ef'] * 1e4, 2)} cm²; A<sub>s,y</sub> = {n(gr['As_y'] * 1e4, 2)} cm² ≤ {n(gr['As_y_ef'] * 1e4, 2)} cm² "
                     f"(mínimo de {cr['grelha_min_barras']} barras por camada e direção).</p>")
        if fr:
            if fr.get("construtivo"):
                H.append(f"<p>Anéis construtivos (cintamento): <b>{fr['n']} estribos circulares ø{n(fr['bitola'], 1)} c/"
                         f"{n(fr['s'] * 100, 0)}</b> entre {n(fr['z1'])} m e {n(fr['z2'])} m abaixo do topo, entre as camadas da "
                         "grelha; o tirante fica com a grelha.</p>")
            else:
                H.append(f"<p>Fretagem: <b>{fr['n']} estribos circulares ø{n(fr['bitola'], 1)} c/{n(fr['s'] * 100, 0)}</b> entre "
                         f"{n(fr['z1'])} m e {n(fr['z2'])} m abaixo do topo (cada estribo cruza o plano diametral duas vezes: "
                         f"A<sub>s,ef</sub> = {n(fr['As_ef'] * 1e4, 2)} cm²).</p>")
        mo = est.get("montagem")
        if mo:
            H.append(f"<p>Barras de montagem (porta-estribos, só construtivas): <b>{mo['n']} ø{n(mo['bitola'], 1)}</b> encostadas por "
                     "dentro dos estribos" + (f", {mo['n_pontas']} delas nas pontas dos grampos da grelha (os ganchos as abraçam)"
                                              if mo.get("n_pontas") else "")
                     + f"; vão máximo de {n(mo['espac'] * 100, 0)} cm; do cobrimento do topo até {n(mo['z_fim'])} m (C = "
                     f"{n(mo['comp'])} m). Com o fuste armado, a própria armadura longitudinal segura os estribos e os grampos.</p>")
    # dimensionamento
    if res.get("dimensionamento"):
        d = res["dimensionamento"]
        H.append(f"<h2>{sec}. Dimensionamento automático</h2>")
        sec += 1
        esc = d["escolha"]
        H.append(f"<p>Varredura de {len(d['Ds'])} diâmetros × {len(d['Ls'])} comprimentos com todas as verificações de serviço e "
                 f"ruptura por equilíbrio limite; a menor solução que passa (volume de concreto) é conferida com a análise completa. "
                 f"Escolhida: <b>{('D = %s m, L = %s m' % (n(esc['D']), n(esc['L']))) if esc else 'nenhuma'}</b>"
                 + (f" (escolha do projetista; a ótima é D = {n(d['otima']['D'])} m, L = {n(d['otima']['L'])} m, com borda tracejada)"
                    if d.get("usuario") and d.get("otima") else "") + ". "
                 f"Número na célula: aproveitamento da verificação que governa (≤ 1 atende); ✓ = passa em tudo.</p>")
        H.append(tabela_mapa(d))
    # verificações
    H.append(f"<h2>{sec}. Resumo das verificações</h2>")
    sec += 1
    piores = {}
    for c in res["verificacoes"]:
        a_ = c["aproveitamento"]
        if c["nome"].startswith("Tombamento") and c["valor"]:
            a_ = c["limite"] / c["valor"] if math.isfinite(c["valor"]) else 0.0
        k = (c["grupo"], c["nome"])
        chave = (0 if c["ok"] else 1, a_ if a_ is not None else 0.0)
        if k not in piores or chave > piores[k][0]:
            piores[k] = (chave, c, a_)
    lin = []
    for _, c, a_ in piores.values():
        val = n(c["valor"], 4) if isinstance(c["valor"], float) else n(c["valor"])
        limv = n(c["limite"], 4) if isinstance(c["limite"], float) else ("—" if c["limite"] is None else str(c["limite"]))
        lin.append([E(c["grupo"]), E(c["nome"]) + (f"<br><span class='nota'>{E(c['detalhe'])}</span>" if c.get("detalhe") else ""),
                    E(c["perfil"]) + "<br>" + E((c["combinacao"] or "")[:80]), val + (f" {E(c['unidade'])}" if c["unidade"] else ""),
                    limv, n(a_, 2) if a_ is not None else "—", ok_txt(c["ok"]), E(c["ref"])])
    nt = len(res["verificacoes"])
    nf = sum(1 for c in res["verificacoes"] if not c["ok"])
    H.append(f"<p>{nt} verificações ({nf} não atendidas). A tabela mostra o caso mais desfavorável de cada uma (perfil e "
             f"combinação); todos os casos estão no arquivo de resultados (JSON).</p>")
    H.append(_tab(["Grupo", "Verificação", "Perfil e combinação", "Valor", "Limite", "Aprov.", "Situação", "Critério"], lin,
                  nums=(3, 4, 5)))
    if res["alertas"]:
        H.append("<h3>Avisos</h3>" + "".join(f'<div class="{ {"erro": "alerta", "info": "info"}.get(t, "aviso") }">{E(msg)}</div>'
                                             for t, msg in res["alertas"]))
    # quantitativos
    q = res["quantitativos"]
    H.append(f"<h2>{sec}. Quantitativos</h2>")
    sec += 1
    lin = [["Concreto de enchimento", f"{n(q['concreto_enchimento'])} m³", f"{n(q['concreto_enchimento'] * p['quantidade'])} m³"],
           ["Escavação", f"{n(q['escavacao'])} m³", f"{n(q['escavacao'] * p['quantidade'])} m³"],
           ["Lastro", f"{n(q['lastro'])} m³", f"{n(q['lastro'] * p['quantidade'])} m³"]]
    if cm["usar"]:
        lin += [["Anéis pré-moldados", f"{q['aneis']} un. ({E(q['aneis_desc'])})", f"{q['aneis'] * p['quantidade']} un."],
                ["Preenchimento da folga", f"{n(q['folga'])} m³", f"{n(q['folga'] * p['quantidade'])} m³"]]
    H.append(_tab(["Item", "Por unidade", f"Total ({p['quantidade']} un.)"], lin))
    if q.get("aviso_aneis"):
        H.append(f'<div class="aviso">{E(q["aviso_aneis"])}</div>')
    # validação
    H.append(f"<h2>{sec}. Validação do programa</h2>")
    H.append("<p>O mesmo núcleo, nas hipóteses de cada referência, reproduz: R01 (Pfeil, Ex. 6.10.2.2: pressões de borda 107/103 tf/m², "
             "q = −0,63·z² + 3,11·z); R02 (Timerman, exemplo numérico: θ = 4,346·10⁻⁴, Δx = 3,117 mm, y₀ = 7,172 m, bordas 28,93/10,85 tf/m²) "
             "e R03 (momento de 65,34 tfm a 4,2 m, com o diâmetro do fuste); a rotina antiga de R05 (solução 03: θ = 0,004215 rad). "
             "A compatibilização das sondagens reproduz sem diferença a média e a envoltória exportadas pelo GEOSPT. "
             "Testes em <code>tubulao_testes.py</code>.</p>")
    corpo = "\n".join(H)
    return (f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>Memória {E(p['nome'])}</title><style>{CSS}</style></head><body><main>{corpo}</main></body></html>")


# ------------------------------------------------------------------------------------------------ arquivos
def edge():
    for raiz in (os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), os.environ.get("ProgramFiles", r"C:\Program Files")):
        f = os.path.join(raiz, "Microsoft", "Edge", "Application", "msedge.exe")
        if os.path.exists(f):
            return f
    return None


def gerar_pdf(html_path, pdf_path):
    exe = edge()
    if not exe:
        raise RuntimeError("Edge não encontrado: PDF da memória não gerado (o HTML pode ser impresso pelo navegador).")
    perfil = tempfile.mkdtemp(prefix="memoria_edge_")
    try:
        url = "file:///" + os.path.abspath(html_path).replace("\\", "/")
        subprocess.run([exe, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--user-data-dir={perfil}",
                        f"--print-to-pdf={os.path.abspath(pdf_path)}", url], check=True, capture_output=True, timeout=180)
    finally:
        shutil.rmtree(perfil, ignore_errors=True)
    if not os.path.exists(pdf_path):
        raise RuntimeError("O Edge não gravou o PDF da memória.")
    return pdf_path


def gerar(res, pasta, pdf=True):
    os.makedirs(pasta, exist_ok=True)
    nome = res["p"]["nome"]
    arq = os.path.join(pasta, f"{nome}_memoria.html")
    with open(arq, "w", encoding="utf-8") as f:
        f.write(montar_html(res))
    out = dict(html=arq)
    if pdf:
        try:
            out["pdf"] = gerar_pdf(arq, os.path.join(pasta, f"{nome}_memoria.pdf"))
        except (RuntimeError, subprocess.SubprocessError, OSError) as e:
            out["erro_pdf"] = str(e)
    return out


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Memória de cálculo do tubulão curto (HTML e PDF)")
    ap.add_argument("json")
    ap.add_argument("--saida")
    ap.add_argument("--sem-pdf", action="store_true")
    a = ap.parse_args()
    sys.stdout.reconfigure(errors="replace")
    par = json.load(open(a.json, encoding="utf-8"))
    res = tcore.calcular(par, os.path.dirname(os.path.abspath(a.json)))
    out = gerar(res, a.saida or os.path.join(tcore.SAIDAS, res["p"]["nome"]), pdf=not a.sem_pdf)
    for k, v in out.items():
        print(f"{k:8s} {v}")


if __name__ == "__main__":
    main()
