# -*- coding: utf-8 -*-
# Cópia portátil dos tubulões (14/11/2026): copiado de _apps\_comum\cad_icones.py, sem alterações no código.
# Motor e ícones comuns tirados de _apps\TelaSoldada\tela_icones.py em 09/11/2026 (código idêntico), para os apps de
# telas, tubulões e punção (Punção\PLANO_Puncao.md, seção 6.2). Os ícones próprios de cada app ficam no módulo dele,
# registrados no mesmo ICONES.
r"""
Ícones das janelas no estilo dos editores do TQS (ribbon, barra de acesso rápido e árvore), desenhados com o Pillow:
traço preto, poucas cores de destaque. Cada ícone é desenhado numa grade de 32 x 32 com supersampling de 4x e
reduzido para 32 ou 16 px.

- ICONES: nome -> função de desenho; cada app acrescenta os seus (tela_icones, tubulao_app, puncao_icones).
- foto("abrir", 32) -> ImageTk.PhotoImage, em cache (para o Tk não o perder); o cache é refeito com outra raiz Tk no
  mesmo processo (testes).
- python cad_icones.py -> grava a folha com os ícones comuns em saidas\icones_comuns.png (conferência).
"""
import os, math
from PIL import Image, ImageDraw, ImageFont

SS = 4                                          # supersampling
PRETO, AZUL, AZUL_C, VERM, AMAR, VERDE = "#1b1b1b", "#1f5fbf", "#5b9bd5", "#d23b2f", "#f2c12e", "#2e9d48"
CINZA, CINZA_C, LARANJA, CIANO, LILAS = "#6e6e6e", "#bdbdbd", "#e8832a", "#1aa3b8", "#8e5cc4"
FUNDO_TELA = "#dfeef0"

_FONTES = {}


def _fonte(tam, negrito=True):
    k = (tam, negrito)
    if k not in _FONTES:
        nomes = ["segoeuib.ttf", "arialbd.ttf"] if negrito else ["segoeui.ttf", "arial.ttf"]
        for n in nomes:
            try:
                _FONTES[k] = ImageFont.truetype(os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", n), tam)
                break
            except OSError:
                continue
        else:
            _FONTES[k] = ImageFont.load_default()
    return _FONTES[k]


class D:
    """Desenho na grade 32 x 32 (y para baixo, como na tela)."""

    def __init__(self):
        self.im = Image.new("RGBA", (32 * SS, 32 * SS), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.im)

    def _p(self, pts):
        return [(x * SS, y * SS) for x, y in pts]

    def linha(self, pts, cor=PRETO, w=1.6):
        self.d.line(self._p(pts), fill=cor, width=max(1, round(w * SS)), joint="curve")

    def ret(self, x0, y0, x1, y1, cor=PRETO, fundo=None, w=1.6):
        self.d.rectangle([x0 * SS, y0 * SS, x1 * SS, y1 * SS], outline=cor, fill=fundo, width=max(1, round(w * SS)))

    def poli(self, pts, cor=PRETO, fundo=None, w=1.6):
        self.d.polygon(self._p(pts), outline=cor, fill=fundo, width=max(1, round(w * SS)))

    def elipse(self, x0, y0, x1, y1, cor=PRETO, fundo=None, w=1.6):
        self.d.ellipse([x0 * SS, y0 * SS, x1 * SS, y1 * SS], outline=cor, fill=fundo, width=max(1, round(w * SS)))

    def ponto(self, x, y, r=1.2, cor=PRETO):
        self.d.ellipse([(x - r) * SS, (y - r) * SS, (x + r) * SS, (y + r) * SS], fill=cor)

    def seta(self, x0, y0, x1, y1, cor=PRETO, w=1.8, cab=3.6):
        self.linha([(x0, y0), (x1, y1)], cor, w)
        a = math.atan2(y1 - y0, x1 - x0)
        p1 = (x1 - cab * math.cos(a - 0.5), y1 - cab * math.sin(a - 0.5))
        p2 = (x1 - cab * math.cos(a + 0.5), y1 - cab * math.sin(a + 0.5))
        self.poli([(x1, y1), p1, p2], cor, cor, 0.5)

    def texto(self, x, y, s, cor=PRETO, tam=11, negrito=True, ancora="mm"):
        self.d.text((x * SS, y * SS), s, fill=cor, font=_fonte(round(tam * SS), negrito), anchor=ancora)

    def tracejado(self, x0, y0, x1, y1, cor=PRETO, w=1.6, traco=3.0, vao=2.0):
        L = math.hypot(x1 - x0, y1 - y0)
        ux, uy = (x1 - x0) / L, (y1 - y0) / L
        t = 0.0
        while t < L:
            t1 = min(t + traco, L)
            self.linha([(x0 + ux * t, y0 + uy * t), (x0 + ux * t1, y0 + uy * t1)], cor, w)
            t = t1 + vao


# ----------------------------------------------------------------------------------------------- desenhos


# ------------------------------------------------------------------------------------------------------- desenhos
def _folha(d, x0=7, y0=3, x1=25, y1=29, dobra=6, fundo="white"):
    d.poli([(x0, y0), (x1 - dobra, y0), (x1, y0 + dobra), (x1, y1), (x0, y1)], PRETO, fundo, 1.4)
    d.linha([(x1 - dobra, y0), (x1 - dobra, y0 + dobra), (x1, y0 + dobra)], PRETO, 1.2)


def _pasta(d, aberta=False):
    d.poli([(3, 9), (12, 9), (14, 12), (28, 12), (28, 27), (3, 27)], "#b8860b", "#f6d365", 1.4)
    if aberta:
        d.poli([(3, 27), (8, 15), (31, 15), (27, 27)], "#b8860b", "#fbe39b", 1.4)


def _tela(d, x0, y0, x1, y1, fundo=FUNDO_TELA, w=1.6):
    d.ret(x0, y0, x1, y1, PRETO, fundo, w)
    d.linha([(x0, y1), (x1, y0)], VERM, w * 0.9)


def i_novo(d):
    _folha(d)


def i_abrir(d):
    _pasta(d, True)


def i_salvar(d):
    d.poli([(4, 4), (24, 4), (28, 8), (28, 28), (4, 28)], "#173f7a", AZUL, 1.2)
    d.ret(9, 4, 22, 12, "#173f7a", "#e9eef5", 1.0)
    d.ret(18, 5.5, 20.5, 10.5, "#173f7a", "#173f7a", 0.6)
    d.ret(8, 17, 24, 28, "#173f7a", "white", 1.0)
    for y in (20.5, 23.5):
        d.linha([(11, y), (21, y)], CINZA_C, 1.0)


def i_salvar_como(d):
    i_salvar(d)
    d.linha([(17, 29), (29, 17)], AMAR, 3.4)
    d.linha([(17, 29), (29, 17)], "#7a5c00", 0.8)


def i_dxf(d):
    _folha(d, 5, 2, 23, 28)
    d.linha([(8, 12), (13, 8), (18, 12), (13, 16), (8, 12)], AZUL, 1.3)
    d.ret(10, 18, 31, 29, VERM, VERM, 0.8)
    d.texto(20.5, 23.6, "DXF", "white", 8.5)


def i_recarregar(d):
    for a0, a1, cor in ((200, 340, VERDE), (20, 160, VERDE)):
        d.d.arc([6 * SS, 6 * SS, 26 * SS, 26 * SS], a0, a1, fill=cor, width=round(2.4 * SS))
    d.poli([(25.5, 8.5), (28.5, 16.5), (20.5, 15.0)], VERDE, VERDE, 0.5)
    d.poli([(6.5, 23.5), (3.5, 15.5), (11.5, 17.0)], VERDE, VERDE, 0.5)


def i_verificar(d):
    d.elipse(3, 3, 19, 19, PRETO, "#eef6ff", 2.2)
    d.linha([(16.5, 16.5), (27, 27)], PRETO, 4.0)
    d.texto(11, 11.2, "!", VERM, 13)
    d.linha([(25, 5), (25, 14)], VERM, 2.6)
    d.ponto(25, 18, 1.5, VERM)


def i_regerar(d):
    cx, cy = 16, 16
    for k in range(12):
        a = k * math.pi / 6
        d.linha([(cx + 9 * math.cos(a), cy + 9 * math.sin(a)), (cx + 14.5 * math.cos(a), cy + 14.5 * math.sin(a))],
                "#e09b00", 2.2)
    d.elipse(7, 7, 25, 25, "#d08a00", AMAR, 1.4)
    d.texto(16, 16.6, "R", VERM, 13)


def i_parametros(d):
    _folha(d, 7, 3, 27, 29, 6, "#fffaf2")
    d.texto(16.5, 18, "Pa", VERM, 12.5)


def i_filtro(d):
    d.poli([(4, 5), (28, 5), (19, 17), (19, 27), (13, 30), (13, 17)], "#555555", "#d9d9d9", 1.4)


def i_listar(d):
    d.ret(5, 3, 27, 29, PRETO, "white", 1.6)
    for y in (9, 14, 19, 24):
        d.ponto(9.5, y, 1.3)
        d.linha([(13, y), (23.5, y)], PRETO, 1.8)


def i_tabela(d):
    d.ret(4, 5, 28, 27, PRETO, "white", 1.4)
    d.ret(4, 5, 28, 10, PRETO, "#c6dbf6", 1.4)
    for y in (15, 21):
        d.linha([(4, y), (28, y)], CINZA, 1.0)
    for x in (12, 20):
        d.linha([(x, 5), (x, 27)], CINZA, 1.0)


def i_enquadrar(d):
    d.ret(8, 8, 24, 24, CINZA, None, 1.0)
    for (x, y, dx, dy) in ((3, 3, 1, 1), (29, 3, -1, 1), (3, 29, 1, -1), (29, 29, -1, -1)):
        d.linha([(x, y + 7 * dy), (x, y), (x + 7 * dx, y)], PRETO, 2.0)
    d.seta(13, 13, 8.5, 8.5, AZUL, 1.6, 3.0)
    d.seta(19, 19, 23.5, 23.5, AZUL, 1.6, 3.0)


def _lupa(d):
    d.elipse(3, 3, 21, 21, PRETO, "#eef6ff", 2.2)
    d.linha([(18.5, 18.5), (28, 28)], PRETO, 4.0)


def i_ampliar(d):
    _lupa(d)
    d.linha([(7.5, 12), (16.5, 12)], AZUL, 2.4)
    d.linha([(12, 7.5), (12, 16.5)], AZUL, 2.4)


def i_reduzir(d):
    _lupa(d)
    d.linha([(7.5, 12), (16.5, 12)], AZUL, 2.4)


def i_fundo(d):
    d.elipse(4, 4, 28, 28, PRETO, "white", 1.6)
    d.d.pieslice([4 * SS, 4 * SS, 28 * SS, 28 * SS], 90, 270, fill=PRETO)


def i_prancha(d):
    d.ret(2, 5, 30, 27, PRETO, "white", 1.4)
    d.ret(4, 7, 19, 25, CINZA_C, "#eef3f8", 0.8)
    _tela(d, 6, 9, 13, 15, w=1.0)
    _tela(d, 6, 16, 13, 22, w=1.0)
    for y in (9, 12, 15):
        d.linha([(21, y), (28, y)], CINZA, 1.0)
    d.ret(21, 20, 28, 25, PRETO, "#d9d9d9", 0.8)


def i_previa(d):
    i_prancha(d)
    d.elipse(14, 13, 26, 25, AZUL, "#ffffffcc", 2.0)
    d.linha([(24, 23), (30, 29)], AZUL, 3.0)


def i_gerar(d):
    d.poli([(4, 4), (24, 4), (28, 8), (28, 28), (4, 28)], "#8f1d14", VERM, 1.2)
    d.ret(9, 4, 22, 12, "#8f1d14", "#fbe9e7", 1.0)
    d.ret(8, 16, 24, 28, "#8f1d14", "white", 1.0)
    d.texto(16, 22.5, "DWG", VERM, 7)


def i_pdf(d):
    _folha(d, 5, 2, 23, 28)
    d.ret(9, 16, 31, 28, "#b3261e", "#b3261e", 0.8)
    d.texto(20, 22.4, "PDF", "white", 8.5)


def i_pasta(d):
    _pasta(d)


def i_notas(d):
    d.texto(16, 16.5, "T", AZUL, 24)


def i_copiar(d):
    d.ret(4, 3, 19, 21, PRETO, "white", 1.4)
    d.ret(12, 10, 27, 28, PRETO, "white", 1.4)
    for y in (15, 19, 23):
        d.linha([(15, y), (24, y)], CINZA, 1.2)


def i_ajuda(d):
    d.elipse(3, 3, 29, 29, AZUL, AZUL, 1.0)
    d.texto(16, 16.8, "?", "white", 17)


def i_sair(d):
    d.ret(6, 3, 21, 29, PRETO, "#e9e9e9", 1.4)
    d.seta(14, 16, 29, 16, VERM, 2.4, 5)


def i_pilar(d):
    d.ret(9, 9, 23, 23, PRETO, "#9e9e9e", 1.6)
    d.linha([(9, 9), (23, 23)], PRETO, 1.0)
    d.linha([(9, 23), (23, 9)], PRETO, 1.0)


def i_aviso(d):
    d.poli([(16, 3), (30, 28), (2, 28)], "#a35a00", "#ffd24d", 1.6)
    d.texto(16, 19, "!", PRETO, 13)


def i_ok(d):
    d.linha([(5, 17), (13, 25), (28, 7)], VERDE, 4.0)


def i_desfazer(d):
    d.d.arc([6 * SS, 8 * SS, 28 * SS, 28 * SS], 200, 360, fill=AZUL, width=round(2.6 * SS))
    d.d.arc([6 * SS, 8 * SS, 28 * SS, 28 * SS], 0, 90, fill=AZUL, width=round(2.6 * SS))
    d.poli([(3, 12), (11, 9), (9.5, 18)], AZUL, AZUL, 0.5)


def i_guia(d):
    d.poli([(4, 5), (15, 7), (15, 29), (4, 27)], "#173f7a", "#e9eef5", 1.2)
    d.poli([(28, 5), (17, 7), (17, 29), (28, 27)], "#173f7a", "#e9eef5", 1.2)
    for y in (12, 16, 20):
        d.linha([(6.5, y), (13, y + 0.6)], CINZA, 1.0)
        d.linha([(25.5, y), (19, y + 0.6)], CINZA, 1.0)

ICONES = {k[2:]: v for k, v in globals().items() if k.startswith("i_") and callable(v)}
_CACHE = {}
_RAIZ = [None]


def imagem(nome, tam=32):
    d = D()
    ICONES[nome](d)
    return d.im.resize((tam, tam), Image.LANCZOS)


def foto(nome, tam=32):
    """PhotoImage do ícone, em cache. As imagens pertencem ao interpretador Tk em que foram criadas: com outra raiz
    no mesmo processo (testes), o cache é refeito."""
    import tkinter as tk
    from PIL import ImageTk
    if tk._default_root is not _RAIZ[0]:
        _CACHE.clear()
        _RAIZ[0] = tk._default_root
    k = (nome, tam)
    if k not in _CACHE:
        _CACHE[k] = ImageTk.PhotoImage(imagem(nome, tam))
    return _CACHE[k]


def folha(arq, nomes=None):
    """Os ícones em 32 e 16 px, com o nome (conferência visual)."""
    nomes = sorted(nomes or ICONES)
    col = 8
    lin = math.ceil(len(nomes) / col)
    W, H = 120, 70
    im = Image.new("RGB", (col * W, lin * H), "white")
    dr = ImageDraw.Draw(im)
    for i, n in enumerate(nomes):
        x, y = (i % col) * W, (i // col) * H
        im.paste(imagem(n, 32), (x + 10, y + 8), imagem(n, 32))
        im.paste(imagem(n, 16), (x + 52, y + 16), imagem(n, 16))
        dr.text((x + 10, y + 48), n, fill="black", font=_fonte(11, False))
    im.save(arq)
    return arq


if __name__ == "__main__":
    pasta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saidas")
    os.makedirs(pasta, exist_ok=True)
    print(folha(os.path.join(pasta, "icones_comuns.png")))
