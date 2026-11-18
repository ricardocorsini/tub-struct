# -*- coding: utf-8 -*-
"""
Desenho do tubulão curto em DWG TQS (formas e armação), com PDF e DXF, a partir do resultado do tubulao_core.

Conteúdo: elevação (terreno, escavação, folga preenchida, anéis com as juntas, concreto de enchimento, lastro, NA,
pilar ou poste, marcas de nível e cotas), planta, as colunas das sondagens de cálculo à esquerda (as funções do app
de estacas, alinhadas por cota), a fretagem e as barras longitudinais como ferros inteligentes do TQS (a tabela de
ferros desenhada usa os comprimentos calculados pelo TQS), as tabelas de quantitativos e do resumo do cálculo, as
notas e o bloco $QUANT (volume de concreto das N unidades, lido pelo quantitativos.py). Escala padrão 1:25.

Reaproveita o app de estacas: estaca_core (primitivas, níveis, textos para o TQS, tabela) e estaca_dwg (criação dos
ferros, leitura da tabela do TQS, $QUANT, PDF, DXF com as cores da plotagem e a recusa de elementos nos níveis 1-199).

Cópia portátil (14/11/2026): os módulos das estacas estão nesta pasta (estaca_core, estaca_sondagem e estaca_previa
do _apps\\EstacaEscavada; estaca_dwg da cópia portátil das estacas, que funciona com o pacote do TQS V25 e V26). Sem o
pacote ou sem o TQS instalado, gerar() diz o que falta (dependencias.py) antes de gravar qualquer arquivo.

Uso: python tubulao_dwg.py <parametros.json> [--saida PASTA]
"""
import os, re, sys, math, json, glob, textwrap, argparse

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import dependencias                                         # noqa: E402
import estaca_core as ec                                    # noqa: E402
import estaca_sondagem as es                                # noqa: E402
import tubulao_core as tcore                                # noqa: E402
import tubulao_sondagem as ts                               # noqa: E402
import tubulao_concreto as tc                               # noqa: E402

NV_SOLO = ec.NV_SOLO          # 208: terreno e hachura do solo
NV_OCULTO = 210               # linhas tracejadas (folga, poste embutido)
TIPOS_FOLGA = {"autoadensavel": "PREENCHIMENTO AUTOADENSÁVEL (SOLO-CIMENTO PLÁSTICO, CONCRETO MAGRO OU ARGAMASSA FLUIDA)",
               "solo_cimento_compactado": "ATERRO DE SOLO-CIMENTO COMPACTADO EM CAMADAS", "nenhuma": ""}


def br(v, c=2):
    return ec.br(v, c)


def notas(res):
    p = res["p"]
    g, cm, mt, fo = p["geometria"], p["camisa"], p["materiais"], p["folga"]
    ap0 = res["analises"][0]
    sadm = min(a["sigma_adm"] for a in res["analises"])
    pc = res.get("concreto_6122") or {}
    if cm["usar"]:
        conc = (f"CONCRETO DE ENCHIMENTO C{mt['fck']:g} (CLASSE DE AGRESSIVIDADE {mt['caa']}), A/C <= "
                f"{br(pc.get('ac_max', 0.6), 2)} (NBR 6118, TABELA 7.1); AÇO CA-{mt['fyk'] / 10:g}; COBRIMENTO "
                f"{br(mt['cobrimento'] * 100, 0)} cm.")
    else:
        tr = tc.traco_anexo_b(mt["fck"], mt["caa"])
        conc = (f"CONCRETO DO TUBULÃO C{mt['fck']:g} (CLASSE DE AGRESSIVIDADE {mt['caa']}; NBR 6122, TABELA 4 E ANEXO B, LINHA "
                f"{tr['classe']}): ABATIMENTO {tr['abatimento']}, AGREGADO {tr['agregado']}, EXSUDAÇÃO {tr['exsudacao']}, "
                f"CIMENTO >= {tr['cimento']} kg/m3, A/C <= {br(tr['ac'], 2)}; LANÇADO COM FUNIL DE NO MÍNIMO 1,5 m, SEM VIBRADOR. "
                f"AÇO CA-{mt['fyk'] / 10:g}; COBRIMENTO {br(mt['cobrimento'] * 100, 0)} cm.")
    out = [f"MEDIDAS EM CENTÍMETROS E COTAS EM METROS, EXCETO ONDE INDICADO.",
           conc,
           f"TENSÃO ADMISSÍVEL ADOTADA NA BASE: {br(sadm / 98.0665, 2)} kgf/cm² ({br(sadm, 0)} kPa). O SOLO DA BASE (COTA "
           f"{br(g['cota_base'])}) DEVE SER APROVADO POR PROFISSIONAL HABILITADO ANTES DA CONCRETAGEM (NBR 6122, 9.2.1).",
           f"LASTRO DE {br(p['lastro']['espessura'] * 100, 0)} cm DE {p['lastro']['material'].upper()} NO FUNDO DA ESCAVAÇÃO, "
           "LIMPO E NIVELADO."]
    if cm["usar"]:
        out.append(f"CAMISA DE ANÉIS PRÉ-MOLDADOS DN {br(cm['DN'] * 100, 0)} x {br(cm['altura'] * 100, 0)} cm, PAREDE "
                   f"{br(cm['espessura'] * 100, 0)} cm, COM ENCAIXE MACHO E FÊMEA, APRUMADOS E CENTRADOS. OS ANÉIS SÃO FORMA "
                   "PERDIDA (NÃO ESTRUTURAIS).")
        if fo["preenchimento"] != "nenhuma":
            txt = ("PREENCHER A FOLGA ENTRE OS ANÉIS E O SOLO COM MATERIAL AUTOADENSÁVEL (SOLO-CIMENTO PLÁSTICO, CONCRETO MAGRO "
                   "OU ARGAMASSA FLUIDA), LANÇADO DE BAIXO PARA CIMA E SEM VAZIOS: A REAÇÃO LATERAL DO SOLO DEPENDE DESSE "
                   "CONTATO. NÃO USAR REATERRO SOLTO.") if fo["preenchimento"] == "autoadensavel" else \
                  (f"ATERRO DA FOLGA COM SOLO-CIMENTO COMPACTADO EM CAMADAS DE NO MÁXIMO 20 cm, COM FOLGA MÍNIMA DE "
                   f"{br(fo['folga_min_compactacao'] * 100, 0)} cm PARA O COMPACTADOR. A REAÇÃO LATERAL DO SOLO DEPENDE DESSE CONTATO.")
            out.append(txt)
    if p["apoio"]["tipo"] == "pilar":
        out.append("ARRANQUE E ANCORAGEM DO PILAR CONFORME O PROJETO ESTRUTURAL.")
    elif p["apoio"]["tipo"] == "poste":
        out.append(f"POSTE EMBUTIDO {br(p['apoio']['embutimento'] * 100, 0)} cm, APRUMADO E TRAVADO ATÉ A CURA DO CONCRETO "
                   "(ENGASTAMENTO CONFORME O FABRICANTE E A CONCESSIONÁRIA).")
    out.append("MANTER A ESCAVAÇÃO SECA E LIMPA; CONCRETAR LOGO APÓS A LIBERAÇÃO DO FUNDO.")
    out.append("VER A MEMÓRIA DE CÁLCULO DO TUBULÃO.")
    return out


def _marca_nivel(m, x, y, txt, lado=1):
    P = m.P
    t = P(0.18)
    m.poli([(x, y), (x - t, y + t * 1.4), (x + t, y + t * 1.4), (x, y)], ec.NV_COTA)
    m.linha(x, y, x + lado * P(2.0), y, ec.NV_CHAMADA)
    m.texto(x + (P(0.25) if lado > 0 else -P(0.25)), y + P(0.12), txt, P(ec.H_TXT), alin="esq" if lado > 0 else "dir")


def _niveis(m, niveis, x_face, xlv):
    """Marcas de nível à direita da elevação, como nas estacas: linha de chamada desde a face, triângulo em xlv e o
    texto; textos próximos descem para não se sobreporem."""
    P = m.P
    h, ytx = P(ec.H_TXT), math.inf
    for y, txt in sorted(niveis, key=lambda v: -v[0]):
        ytx = min(y + P(0.08), ytx - P(0.45))
        a = P(0.12)
        m.linha(x_face + P(ec.FOLGA), y, xlv + P(0.3), y, ec.NV_CHAMADA)
        m.poli([(xlv, y), (xlv - a, y + 1.6 * a), (xlv + a, y + 1.6 * a), (xlv, y)], ec.NV_COTA, cheio=True)
        if abs(ytx - y - P(0.08)) > 1e-6:
            m.linha(xlv + P(0.3), y, xlv + P(0.45), ytx + h / 2, ec.NV_CHAMADA)
        m.texto(xlv + P(0.5), ytx, txt, h)


def _secao(m, x, y, De, D, Dc, camisa):
    """Contorno do tubulão em planta (escavação e, com a camisa, os anéis), os eixos e a cota do diâmetro."""
    P = m.P
    m.circulo(x, y, De / 2, ec.NV_CONTORNO)
    if camisa:
        m.circulo(x, y, D / 2, ec.NV_CONTORNO)
        m.circulo(x, y, Dc / 2, ec.NV_CONTORNO)
    m.linha(x - De / 2 - P(0.6), y, x + De / 2 + P(0.6), y, ec.NV_EIXO, estilo=3)
    m.linha(x, y - De / 2 - P(0.6), x, y + De / 2 + P(0.6), ec.NV_EIXO, estilo=3)
    m.cota(x - De / 2, y, x + De / 2, y, y - De / 2 - P(1.0), vertical=False)


def _marcas(m, lista, xt, yt):
    """Identificações curtas (marca, bitola e, conforme o ferro, a quantidade ou o espaçamento) empilhadas à direita
    da vista, com a linha de chamada até o ferro: a descrição completa fica nos detalhes e na barra destacada. Na
    ordem da altura dos pontos, para as linhas de chamada não se cruzarem."""
    for f, pt, nfr, esp in sorted(lista, key=lambda v: -v[1][1]):
        m.marca(f, xt, yt, [pt], nfr=nfr, esp=esp)
        yt -= m.P(0.6)


def montar(res, tabela=None):
    p = res["p"]
    g, cm, apo, mt = p["geometria"], p["camisa"], p["apoio"], p["materiais"]
    E = float(p["saidas"]["escala"])
    m = ec.Modelo(E)
    P = m.P
    cm2 = 100.0
    D, Dc, De, L = g["D"] * cm2, g["D_estrutura"] * cm2, g["D_escavacao"] * cm2, g["L"] * cm2
    la = p["lastro"]["espessura"] * cm2
    yv = lambda c: (c - g["cota_topo"]) * cm2
    yT, yB, yTer = 0.0, -L, yv(g["cota_terreno"])
    N = p["quantidade"]
    cob = mt["cobrimento"] * cm2

    # ---------------------------------------------------------------- elevação
    larg_t = De / 2 + P(2.5)
    m.linha(-larg_t, yTer, -De / 2, yTer, NV_SOLO)
    m.linha(De / 2, yTer, larg_t, yTer, NV_SOLO)
    for k in range(int((larg_t - De / 2) / P(0.35))):                      # hachura do terreno
        for s in (-1, 1):
            x0 = s * (De / 2 + P(0.35) * (k + 0.5))
            m.linha(x0, yTer, x0 - P(0.25), yTer - P(0.25), NV_SOLO)
    # escavação (contorno até o fundo do lastro)
    m.poli([(-De / 2, yTer), (-De / 2, yB - la), (De / 2, yB - la), (De / 2, yTer)], ec.NV_CONTORNO)
    m.linha(-De / 2, yB, De / 2, yB, ec.NV_CONTORNO)                      # topo do lastro
    if cm["usar"]:
        n_an = math.ceil(L / (cm["altura"] * cm2) - 1e-6)
        for s in (-1, 1):
            m.linha(s * D / 2, yT, s * D / 2, yB, ec.NV_CONTORNO)
            m.linha(s * Dc / 2, yT, s * Dc / 2, yB, ec.NV_CONTORNO)
        for i in range(n_an + 1):
            y = max(yT - i * cm["altura"] * cm2, yB)
            for s in (-1, 1):
                m.linha(s * Dc / 2, y, s * D / 2, y, ec.NV_CONTORNO)
        m.linha(-D / 2, yT, D / 2, yT, ec.NV_CONTORNO)
        # folga preenchida: tracejado no meio da folga
        if De > D + 1:
            for s in (-1, 1):
                m.linha(s * (D + De) / 4, yT, s * (D + De) / 4, yB, NV_OCULTO, estilo=1)
    else:
        m.poli([(-D / 2, yT), (-D / 2, yB), (D / 2, yB), (D / 2, yT), (-D / 2, yT)], ec.NV_CONTORNO)
    # apoio
    h_ap = P(2.4)
    if apo["tipo"] == "pilar":
        a = (apo["a"] if apo["secao"] == "retangular" else apo["d"]) * cm2
        m.poli([(-a / 2, yT), (-a / 2, yT + h_ap), (a / 2, yT + h_ap), (a / 2, yT)], ec.NV_CONTORNO)
        m.onda(-a / 2 - P(0.2), a / 2 + P(0.2), yT + h_ap, P(0.12))
        m.texto(a / 2 + P(0.3), yT + h_ap - P(0.3), "PILAR (VER PROJETO ESTRUTURAL)", P(ec.H_TXT))
    elif apo["tipo"] == "poste":
        a = 35.0
        emb = min(apo["embutimento"] * cm2, L)
        m.poli([(-a / 2, yT), (-a / 2, yT + h_ap), (a / 2, yT + h_ap), (a / 2, yT)], ec.NV_CONTORNO)
        m.poli([(-a / 2, yT), (-a / 2, yT - emb), (a / 2, yT - emb), (a / 2, yT)], NV_OCULTO, estilo=1)
        m.onda(-a / 2 - P(0.2), a / 2 + P(0.2), yT + h_ap, P(0.12))
        m.texto(a / 2 + P(0.3), yT + h_ap - P(0.3), f"POSTE EMBUTIDO {br(emb, 0)} cm", P(ec.H_TXT))
    # cotas
    if cm["usar"]:
        m.cota(-D / 2, yT, -D / 2, yT - cm["altura"] * cm2, -D / 2 - P(1.2))
    m.cota(-De / 2, yB - la, -De / 2, yB, -De / 2 - P(1.2), txt=f"{br(la, 0)}")
    m.cota(-D / 2, yB, D / 2, yB, yB - la - P(1.0), vertical=False)
    if De > D + 1:
        m.cota(-De / 2, yB, De / 2, yB, yB - la - P(1.8), vertical=False)
    if cm["usar"]:
        m.cota(-Dc / 2, yT, Dc / 2, yT, yT + P(0.9) if apo["tipo"] == "nenhum" else yT + h_ap + P(0.6), vertical=False)
    na = res["solo"]["na"]
    if na is not None and yv(na) > yB - P(4):
        _marca_nivel(m, -De / 2 - P(0.8), yv(na), f"NA {ec.cota(na)}", lado=-1)
    # rótulos
    if cm["usar"]:
        m.texto(-De / 2 - P(0.3), yB + P(1.6), f"ANÉIS DN {br(cm['DN'] * 100, 0)} x {br(cm['altura'] * 100, 0)} cm", P(ec.H_TXT), alin="dir")
        if p["folga"]["preenchimento"] != "nenhuma":
            m.texto(-De / 2 - P(0.3), yB + P(1.1), f"FOLGA {br(p['folga']['largura'] * 100, 0)} cm PREENCHIDA (VER NOTAS)", P(ec.H_TXT), alin="dir")
    m.texto(0, yB - la - P(2.7), "ELEVAÇÃO", P(ec.H_SUB), ec.NV_CORTE, alin="centro")
    m.texto(0, yB - la - P(3.15), f"ESC. 1:{E:g}", P(ec.H_TXT), ec.NV_ESCALA, alin="centro")

    # ---------------------------------------------------------------- armaduras na elevação (ferros inteligentes)
    # Como nas estacas: dentro do perfil só o desenho das armaduras; fora dele, à direita, a cota das camadas da
    # grelha, as faixas dos estribos, o comprimento total, as marcas de nível e a barra vertical destacada com a
    # cadeia de cotas. A identificação completa de cada ferro fica nos detalhes (estribos e grampos) ou na barra
    # destacada; na planta e no corte, só a marca.
    est = res["estrutura"]
    pos_comp = {t["mark"]: t["comp"] for t in (tabela or [])}
    bloco = est.get("bloco") or {}
    fr, gr = bloco.get("fretagem"), bloco.get("grelha")
    arm = est.get("armadura")
    es_ = arm.get("estribo") if arm else None
    mo = est.get("montagem")
    x_ = De / 2
    if gr:
        xg = x_ = x_ + P(1.2)                                           # camadas da grelha
    if fr or es_:
        xb = x_ = x_ + P(1.8 if gr else 1.2)                            # faixas dos estribos
    xr = x_ + (P(2.0) if x_ > De / 2 else P(1.2))                       # comprimento total
    xlv = xr + P(1.2)                                                   # marcas de nível
    niveis = [(yT, f"TOPO {ec.cota(g['cota_topo'])}"), (yB, f"BASE {ec.cota(g['cota_base'])}")]
    if abs(yTer - yT) > 1:
        niveis.append((yTer, f"TERRENO {ec.cota(g['cota_terreno'])}"))
    mark = 1
    f_fr = f_e = f_l = f_m = None
    grs, dest = [], None
    if fr:
        z1, z2 = fr["z1"] * cm2, fr["z2"] * cm2
        f_fr = dict(chave="FRET", tipo="circ", mark=mark, quant=fr["n"], bitola=fr["bitola"], aco="CA50", espac=round(fr["s"] * cm2, 1),
                    cover=cob, comment="CINTAMENTO" if fr.get("construtivo") else "FRETAGEM", raio=Dc / 2, blong=fr["bitola"],
                    comp=pos_comp.get(mark, 0.0), marcas=[],
                    faixas=[dict(x=xb, y1=yT - z2, y2=yT - z1, s=round(fr["s"] * cm2, 1), inicio=True, n=fr["n"], nman=fr["n"],
                                 xcot=xb, cotar=1)], ins=[])
        f_fr["desc"] = ec._descricao(f_fr) if f_fr["comp"] else f"{fr['n']} N{mark} {{{fr['bitola']:g} C/{fr['s'] * 100:.0f}"
        m.ferros.append(f_fr)
        for i in range(fr["n"]):                                         # estribos em vista na elevação
            y = yT - (z1 + (z2 - z1) * i / max(fr["n"] - 1, 1))
            m.linha(-Dc / 2 + cob, y, Dc / 2 - cob, y, ec.NV_FERRO_INT)
        mark += 1
    if gr:                                                               # grelha de fretagem sob o pilar: grampos
        phg = gr["bitola"] / 10
        rh = 3.5 * phg                                                   # raio externo do gancho no desenho do TQS
        lista = gr.get("grampos") or tc.grampos(gr, gr["r_int"], 10.0)
        for c_ in gr.get("comps") or sorted({q["comp"] for q in lista}, reverse=True):
            gps = [q for q in lista if abs(q["comp"] - c_) < 1e-9]
            main = round(c_ * cm2, 1)
            fg = dict(chave=f"GR{mark}", tipo="reto", mark=mark, quant=len(gps) * gr["n_camadas"], bitola=gr["bitola"], aco="CA50",
                      espac=0.0, cover=cob, comment="GRAMPO", main=main, dobra=0.0, zona="pos", comp=pos_comp.get(mark, main),
                      faixas=[], marcas=[], ins=[], ganchos=gr.get("ganchos"))
            fg["desc"] = ec._descricao(fg)
            m.ferros.append(fg)
            grs.append((fg, gps))
            mark += 1
        gx = [q for q in lista if q["dir"] == "X"]
        gy = [q for q in lista if q["dir"] == "Y"]
        x_l = max(q["comp"] for q in gx) * cm2 / 2 if gx else Dc / 2 - cob
        nc, sc = gr["n_camadas"], gr["s_camadas"] * cm2
        for i in range(nc):                                              # grampos em x em vista, em y em corte (logo abaixo)
            y = yT - (gr["z1"] * cm2 + sc * i)
            m.linha(-x_l, y, x_l, y, ec.NV_FERRO_INT)
            for q in gy:
                m.fercor(q["bx"] * cm2 + rh - phg / 2, y - phg, max(phg, P(0.06)))
        y1g, y2g = yT - gr["z1"] * cm2, yT - gr["z2"] * cm2
        m.cota(x_l, yT, x_l, y1g, xg, txt=f"{gr['z1'] * cm2:.0f}")
        m.cota(x_l, y1g, x_l, y2g, xg, txt=f"{nc - 1}x{sc:g}={(nc - 1) * sc:g}")
        nomes = " E ".join("N%d" % f_["mark"] for f_, _ in grs)
        m.texto(xg + P(0.45), (y1g + y2g) / 2, f"GRELHA {nomes} {{{ec.bt(gr['bitola'])}: {nc} CAMADAS", P(ec.H_TXT), ec.NV_COTA,
                ang=90.0, alin="centro")
    if arm:
        main = arm.get("comprimento", g["L"] - 2 * mt["cobrimento"]) * cm2      # do cobrimento do topo ao fim das barras
        y_fim = yT - cob - main
        r = arm.get("raio", Dc / 200 - mt["cobrimento"] - arm["bitola"] / 2000) * cm2     # eixo das barras, por dentro dos estribos
        f_l = dict(chave="LONG", tipo="reto", mark=mark, quant=arm["n"], bitola=arm["bitola"], aco="CA50", espac=0.0, cover=cob,
                   comment="", main=main, dobra=0.0, zona="pos", comp=pos_comp.get(mark, main), faixas=[], marcas=[],
                   ins=[dict(x=-r, y=y_fim, ang=90.0, esc=1.0, ident=0, idobra=0, ipatas=1, nv=ec.NV_FERRO_INT),
                        dict(x=r, y=y_fim, ang=90.0, esc=1.0, ident=0, idobra=0, ipatas=4, nv=ec.NV_FERRO_INT)])
        if not arm.get("inteiro", True):                                 # barras só no trecho necessário: marca do fim
            niveis.append((y_fim, f"FIM N{mark} {ec.cota(g['cota_topo'] - arm['z_fim'])}"))
        f_l["desc"] = ec._descricao(f_l)
        m.ferros.append(f_l)
        dest = (f_l, y_fim)
        mark += 1
        if es_:                                                          # estribos construtivos do fuste armado
            z1, z2 = es_["z1"] * cm2, es_["z2"] * cm2
            f_e = dict(chave="EST", tipo="circ", mark=mark, quant=es_["n"], bitola=es_["bitola"],
                       aco="CA60" if es_["bitola"] < 6 else "CA50", espac=round(es_["s"] * cm2, 1), cover=cob, comment="",
                       raio=Dc / 2, blong=arm["bitola"], comp=pos_comp.get(mark, 0.0), marcas=[],
                       faixas=[dict(x=xb, y1=yT - z2, y2=yT - z1, s=round(es_["s"] * cm2, 1), inicio=True, n=es_["n"], nman=es_["n"],
                                    xcot=xb, cotar=1)], ins=[])
            f_e["desc"] = ec._descricao(f_e) if f_e["comp"] else f"{es_['n']} N{mark} {{{es_['bitola']:g} C/{es_['s'] * 100:.0f}"
            m.ferros.append(f_e)
            for i in range(es_["n"]):                                    # estribos em vista na elevação
                y = yT - (z1 + (z2 - z1) * i / max(es_["n"] - 1, 1))
                m.linha(-Dc / 2 + cob, y, Dc / 2 - cob, y, ec.NV_FERRO_INT)
            mark += 1
    if mo:                                                               # barras de montagem (porta-estribos) da fretagem
        mainm = mo["comp"] * cm2
        y_fm = yT - cob - mainm
        rm = mo["raio"] * cm2
        f_m = dict(chave="MONT", tipo="reto", mark=mark, quant=mo["n"], bitola=mo["bitola"], aco="CA50", espac=0.0, cover=cob,
                   comment="MONTAGEM", main=mainm, dobra=0.0, zona="pos", comp=pos_comp.get(mark, mainm), faixas=[], marcas=[],
                   ins=[dict(x=-rm, y=y_fm, ang=90.0, esc=1.0, ident=0, idobra=0, ipatas=1, nv=ec.NV_FERRO_INT),
                        dict(x=rm, y=y_fm, ang=90.0, esc=1.0, ident=0, idobra=0, ipatas=4, nv=ec.NV_FERRO_INT)])
        f_m["desc"] = ec._descricao(f_m)
        m.ferros.append(f_m)
        dest = (f_m, y_fm)
        mark += 1
    _niveis(m, niveis, De / 2, xlv)
    m.cota(De / 2, yT, De / 2, yB, xr)
    if dest:                                     # barra vertical destacada: cadeia de cotas, a barra e o texto dela
        f_d, y_d = dest
        x_dl = m.caixa[2] + P(1.2)
        x_d = x_dl + P(1.0)
        f_d["ins"].append(dict(x=x_d, y=y_d, ang=90.0, esc=1.0, ident=1, idobra=1, ipatas=1))
        ys_ = [yT, yT - cob, y_d] + ([yB] if y_d > yB + 1 else [])
        for a_, b_ in zip(ys_, ys_[1:]):
            m.cota(x_d - P(0.3), a_, x_d - P(0.3), b_, x_dl)
        m._cx((x_d, y_d), (x_d + P(0.7), yT))

    # ---------------------------------------------------------------- planta do topo
    xp = m.caixa[2] + P(2.5) + De / 2
    yp = yT - De / 2 - P(0.5)
    _secao(m, xp, yp, De, D, Dc, cm["usar"])
    if apo["tipo"] == "pilar":
        if apo["secao"] == "retangular":
            a, b = apo["a"] * cm2, apo["b"] * cm2
            m.poli([(xp - a / 2, yp - b / 2), (xp + a / 2, yp - b / 2), (xp + a / 2, yp + b / 2), (xp - a / 2, yp + b / 2), (xp - a / 2, yp - b / 2)], ec.NV_CONTORNO)
        else:
            m.circulo(xp, yp, apo["d"] * cm2 / 2, ec.NV_CONTORNO)
    elif apo["tipo"] == "poste":
        m.poli([(xp - 17.5, yp - 12.5), (xp + 17.5, yp - 12.5), (xp + 17.5, yp + 12.5), (xp - 17.5, yp + 12.5), (xp - 17.5, yp - 12.5)], ec.NV_CONTORNO)
    if cm["usar"]:
        m.cota(xp - D / 2, yp, xp + D / 2, yp, yp - De / 2 - P(1.7), vertical=False)
    m.texto(xp, yp - De / 2 - P(2.6), "PLANTA", P(ec.H_SUB), ec.NV_CORTE, alin="centro")
    m.texto(xp, yp - De / 2 - P(3.05), f"ESC. 1:{E:g}", P(ec.H_TXT), ec.NV_ESCALA, alin="centro")
    pl = []                                      # marcas da planta: (ferro, ponto, com a quantidade, com o espaçamento)
    if f_fr:
        # fechamento do estribo (ganchos do TQS) fora dos ganchos dos grampos, que ficam perto dos eixos
        f_fr["ins"].append(dict(x=xp, y=yp, ang=30.0, esc=1.0, ident=0, idobra=0, ipatas=1, explode=1, nv=ec.NV_FERRO_INT))
        rr, a_ = Dc / 2 - cob - fr["bitola"] / 20, math.radians(25)
        pl.append((f_fr, (xp + rr * math.cos(a_), yp + rr * math.sin(a_)), 0, 1))
    for fg, gps in grs:                          # cada grampo com os ganchos nas barras verticais que ele abraça
        for q in gps:
            if q["dir"] == "X":
                fg["ins"].append(dict(x=xp - fg["main"] / 2, y=yp + q["by"] * cm2 - rh, ang=0.0, esc=1.0, ident=0, idobra=0,
                                      ipatas=1, nv=ec.NV_FERRO_INT))
            else:
                fg["ins"].append(dict(x=xp + q["bx"] * cm2 + rh, y=yp - fg["main"] / 2, ang=90.0, esc=1.0, ident=0, idobra=0,
                                      ipatas=1, nv=ec.NV_FERRO_INT))
        q = next((q for q in gps if q["dir"] == "X"), gps[0])
        pl.append((fg, (xp + 0.55 * q["bx"] * cm2, yp + q["by"] * cm2 - rh) if q["dir"] == "X"
                   else (xp + q["bx"] * cm2 + rh, yp + 0.55 * q["by"] * cm2), 0, 0))
    if f_m:                                      # montagem em corte (no tamanho real, para os ganchos a abraçarem)
        d_ = max(mo["bitola"] / 10, P(0.04))
        for x_, y_ in mo["pos"]:
            m.fercor(xp + x_ * cm2, yp + y_ * cm2, d_)
        x_, y_ = max(mo["pos"], key=lambda v: v[0] + v[1])
        pl.append((f_m, (xp + x_ * cm2, yp + y_ * cm2), 1, 0))
    if f_l:                                      # barras longitudinais em corte no topo
        d_ = max(arm["bitola"] / 10, P(0.04))
        bar_xy = [(xp + r * math.cos(2 * math.pi * k / arm["n"]), yp + r * math.sin(2 * math.pi * k / arm["n"])) for k in range(arm["n"])]
        for x_, y_ in bar_xy:
            m.fercor(x_, y_, d_)
        pl.append((f_l, max(bar_xy, key=lambda v: (v[0] - xp) + (v[1] - yp)), 1, 0))
    _marcas(m, pl, xp + De / 2 + P(1.2), yp + De / 2 * 0.8)
    if grs:                                      # composição da grelha abaixo do título
        cont = {}
        for fg, gps in grs:
            for q in gps:
                cont[(q["dir"], fg["mark"])] = cont.get((q["dir"], fg["mark"]), 0) + 1
        por = " E ".join(" + ".join(f"{n} N{mk}" for (d, mk), n in sorted(cont.items()) if d == dr) + f" EM {dr}"
                         for dr in ("X", "Y"))
        m.texto(xp, yp - De / 2 - P(3.6), f"GRELHA: {nc} CAMADAS C/{sc:g} DE {br(gr['z1'] * cm2, 0)} A {br(gr['z2'] * cm2, 0)} cm "
                "ABAIXO DO TOPO", P(ec.H_TXT), alin="centro")
        m.texto(xp, yp - De / 2 - P(4.0), "POR CAMADA: " + por, P(ec.H_TXT), alin="centro")

    # ---------------------------------------------------------------- corte A-A no trecho dos estribos do fuste armado
    if f_l:
        z_cut = ((es_["z1"] + es_["z2"]) / 2 if es_ else g["L"] / 2) * cm2
        y_cut = yT - z_cut
        for sg in (-1, 1):
            m.linha(sg * (De / 2 + P(0.15)), y_cut, sg * (De / 2 + P(0.6)), y_cut, ec.NV_CORTE)
            m.texto(sg * (De / 2 + P(0.38)), y_cut + P(0.12), "A", P(ec.H_SUB), ec.NV_CORTE, alin="centro")
        ya = yp - De - P(5.0)
        _secao(m, xp, ya, De, D, Dc, cm["usar"])
        bar_xy = [(xp + r * math.cos(2 * math.pi * k / arm["n"]), ya + r * math.sin(2 * math.pi * k / arm["n"])) for k in range(arm["n"])]
        d_ = max(arm["bitola"] / 10, P(0.04))
        for x_, y_ in bar_xy:
            m.fercor(x_, y_, d_)
        pc = [(f_l, max(bar_xy, key=lambda v: (v[0] - xp) + (v[1] - ya)), 1, 0)]
        if f_e:
            f_e["ins"].append(dict(x=xp, y=ya, ang=0.0, esc=1.0, ident=0, idobra=0, ipatas=1, explode=1, nv=ec.NV_FERRO_INT))
            re_, a_ = Dc / 2 - cob - es_["bitola"] / 20, math.radians(25)
            pc.append((f_e, (xp + re_ * math.cos(a_), ya + re_ * math.sin(a_)), 0, 1))
        _marcas(m, pc, xp + De / 2 + P(1.2), ya + De / 2 * 0.8)
        m.texto(xp, ya - De / 2 - P(2.6), "CORTE A-A", P(ec.H_SUB), ec.NV_CORTE, alin="centro")
        m.texto(xp, ya - De / 2 - P(3.05), f"ESC. 1:{E:g}", P(ec.H_TXT), ec.NV_ESCALA, alin="centro")

    # ---------------------------------------------------------------- detalhes das armaduras, fora das seções
    circ = [(f_, d_) for f_, d_ in ((f_fr, fr), (f_e, es_)) if f_]
    if circ or grs:
        # escala de cada detalhe: a do desenho ou a metade, a um quarto...; o estribo em até 6,5 cm de plotagem e os
        # grampos em até 8,5 cm, para os ganchos ficarem legíveis
        esc_ = lambda dims, lim: next((kk for kk in (1.0, 0.5, 0.25) if max(dims, default=0.0) * kk / E <= lim), 0.2)
        dc = [2 * (f_["raio"] - f_["cover"]) for f_, _ in circ]
        dg = [fg["main"] for fg, _ in grs]
        k, kg = esc_(dc, 6.5), esc_(dg, 8.5)
        xd = m.caixa[2] + P(2.5) + max(max(dc, default=0.0) * k / 2, max(dg, default=0.0) * kg / 2, P(3.0))
        yd = yT
        e_det = E / k
        for f_, d_ in circ:                      # estribo circular: o ferro, o diâmetro externo cotado e o título
            re_ = (f_["raio"] - f_["cover"]) * k
            yc_ = yd - P(0.9) - re_
            f_["ins"].append(dict(x=xd, y=yc_, ang=0.0, esc=k, ident=1, idobra=0, ipatas=1, explode=1))
            m.cota(xd - re_, yc_, xd + re_, yc_, yc_ + re_ + P(0.5), vertical=False, fator=1 / k)
            m._cx((xd - re_, yc_ - re_ - P(0.8)), (xd + re_, yc_ + re_))
            yt_ = yc_ - re_ - P(1.4)
            m.texto(xd, yt_, f"DETALHE DO ESTRIBO N{f_['mark']}", P(ec.H_SUB), ec.NV_CORTE, alin="centro")
            m.texto(xd, yt_ - P(0.45), f"ESTRIBO CIRCULAR {{{ec.bt(f_['bitola'])} - DIÂMETRO EXTERNO {br(2 * (f_['raio'] - f_['cover']), 0)} cm",
                    P(ec.H_TXT), alin="centro")
            m.texto(xd, yt_ - P(0.9), f"ESC. 1:{e_det:g}", P(ec.H_TXT), ec.NV_ESCALA, alin="centro")
            yd = yt_ - P(1.5)
        if grs:                                  # grampos: comprimento reto (face externa dos ganchos) e os ganchos
            e_det = E / kg
            for fg, _ in grs:
                yg = yd - P(1.0)
                fg["ins"].append(dict(x=xd - fg["main"] * kg / 2, y=yg, ang=0.0, esc=kg, ident=1, idobra=1, ipatas=1))
                m._cx((xd - fg["main"] * kg / 2, yg - P(0.7)), (xd + fg["main"] * kg / 2, yg + P(0.5) + 7 * phg * kg))
                yd = yg - P(0.6)
            apoio = f_l or f_m
            yt_ = yd - P(0.8)
            m.texto(xd, yt_, ("DETALHE DO GRAMPO " if len(grs) == 1 else "DETALHE DOS GRAMPOS ")
                    + " E ".join("N%d" % fg["mark"] for fg, _ in grs), P(ec.H_SUB), ec.NV_CORTE, alin="centro")
            info = [f"GANCHOS DE 180 GRAUS NAS PONTAS (PINO 5{{), ABRAÇANDO AS BARRAS N{apoio['mark']}" if apoio
                    else "GANCHOS DE 180 GRAUS NAS PONTAS (PINO 5{)",
                    "COMPRIMENTO RETO MEDIDO ENTRE AS FACES EXTERNAS DOS GANCHOS"]
            for j, s_ in enumerate(info):
                m.texto(xd, yt_ - P(0.45) * (j + 1), s_, P(ec.H_TXT), alin="centro")
            m.texto(xd, yt_ - P(0.45) * (len(info) + 1), f"ESC. 1:{e_det:g}", P(ec.H_TXT), ec.NV_ESCALA, alin="centro")

    # ---------------------------------------------------------------- sondagens à esquerda
    perfis_des = []
    s = res["solo"]
    cota_min = g["cota_base"] - max(2 * g["D"], 3.0)            # a sondagem desenhada vai até 2·D (mín. 3 m) abaixo da base
    corta = lambda cams: [c for c in cams if c["cota_m"] - 1.0 >= cota_min - 1e-6 or c["cota_m"] > cota_min]
    for pf in s["perfis"]:
        if pf["chave"] == "media":
            d = ts.para_desenho("MÉDIA", "media", corta(s["perfis_geospt"]["media"]["camadas"]))
            if d:
                d["obs"] = p["sondagem"]["submodo"]
        elif pf["chave"] == "envoltoria":
            d = ts.para_desenho("MÍNIMA", "envoltoria", corta(s["perfis_geospt"]["envoltoria"]))
        else:
            fn = pf["chave"][5:]
            f = dict(s["sondagens"][fn])
            f["leituras"] = [l for l in f["leituras"] if f["cotaTopo_m"] - l["profundidade_m"] > cota_min - 1e-6]
            f["profundidadeFinal_m"] = min(f["profundidadeFinal_m"], f["cotaTopo_m"] - cota_min)
            d = ts.para_desenho(fn, "furo", None, sond={fn: f})
        if d:
            perfis_des.append(es.normalizar_perfil(d))
    if not p["saidas"].get("sondagens_desenho", True):              # opção do usuário: desenho sem as sondagens
        perfis_des = []
    x_esq = -De / 2
    if perfis_des:
        w = es.desenhar_colunas(m, perfis_des, g["cota_topo"], -De / 2 - P(3.5), face=lambda y: -De / 2)
        x_esq = -De / 2 - P(3.5) - w

    # ---------------------------------------------------------------- tabelas e notas (coluna à direita da planta)
    xC = m.caixa[2] + P(2.5)
    yC = yT + P(1.0)
    h = P(ec.H_TAB)
    q = res["quantitativos"]
    lin = [["CONCRETO DE ENCHIMENTO C%g (m3)" % mt["fck"], br(q["concreto_enchimento"]), br(q["concreto_enchimento"] * N)],
           ["ESCAVAÇÃO (m3)", br(q["escavacao"]), br(q["escavacao"] * N)],
           ["LASTRO (m3)", br(q["lastro"]), br(q["lastro"] * N)]]
    if cm["usar"]:
        lin += [["ANÉIS DN %s x %s cm (un.)" % (br(cm["DN"] * 100, 0), br(cm["altura"] * 100, 0)), str(q["aneis"]), str(q["aneis"] * N)],
                ["PREENCHIMENTO DA FOLGA (m3)", br(q["folga"]), br(q["folga"] * N)]]
    if tabela:
        peso = sum(ec.massa_linear(t["bitola"]) * t["quant"] * t["comp"] / 100 for t in tabela)
        lin.append(["AÇO CA-50 (kg)", br(peso, 1), br(peso * N, 1)])
    _, yC = ec._tabela(m, xC, yC, "QUANTITATIVOS", ["ITEM", "1 TUBULÃO", f"{N} TUBULÕES"], lin, h)
    yC -= P(0.8)
    if tabela:
        lt = [[f"N{t['mark']}", f"{t['bitola']:g}", str(t["quant"]), str(int(round(t["comp"]))),
               br(t["quant"] * t["comp"] / 100, 2)] for t in tabela]
        _, yC = ec._tabela(m, xC, yC, "TABELA DE FERROS (1 TUBULÃO)", ["POS", "{ (mm)", "QUANT", "COMP (cm)", "TOTAL (m)"], lt, h)
        yC -= P(0.8)
    # resumo do cálculo
    lr = []
    for ap in res["analises"]:
        e = max(ap["servico"], key=lambda x: x["theta"])
        fs = min(x["lam"] for x in ap["servico"])
        lr.append([ap["rotulo"].upper()[:28], br(ap["sigma_adm"], 0), br(max(x["p_max"] for x in ap["servico"]), 0),
                   br(fs, 2) if math.isfinite(fs) else "> 20", br(e["theta"] * 1000, 2), br(max(max(x["mob"]) for x in ap["servico"]), 2)])
    _, yC = ec._tabela(m, xC, yC, "RESUMO DO CÁLCULO (COMBINAÇÕES DE SERVIÇO)",
                       ["PERFIL", "TENS.ADM.(kPa)", "TENS.MÁX.(kPa)", "FS TOMB.", "ROT.(x0,001 rad)", "MOBIL."], lr, h)
    yC -= P(0.9)
    m.texto(xC, yC, "NOTAS", P(ec.H_SUB))
    yC -= P(0.55)
    for i, nt in enumerate(notas(res), 1):
        for j, ln in enumerate(textwrap.wrap(nt, 64)):
            m.texto(xC, yC, (f"{i}. " if j == 0 else "   ") + ln, P(ec.H_TXT))
            yC -= P(0.4)
    if p["saidas"]["quant_resumo"]:
        yC -= P(0.4)
        m.prims.append(dict(t="quant", nv=ec.NV_QUANT, x=xC, y=yC, esc=E, area_est=0.0, area_for=0.0,
                            volume=round(q["concreto_enchimento"] * N, 2)))
        m._cx((xC, yC - P(ec.QUANT_ALT)), (xC + P(ec.QUANT_LARG), yC))

    # ---------------------------------------------------------------- título
    xt = m.caixa[0]
    yt = m.caixa[3] + P(1.6)
    m.texto(xt, yt, f"TUBULÃO {p['nome']}".upper(), P(ec.H_TIT), ec.NV_TITULO)
    m.texto(xt, yt - P(0.5), f"(ESCALA 1:{E:g})", P(ec.H_TXT * 1.25), ec.NV_CONTORNO)
    m.texto(xt + P(4.0), yt - P(0.5), f"TUBULÃO CURTO {{{br(g['D'] * 100, 0)} cm - L = {br(g['L'])} m - BASE {ec.cota(g['cota_base'])}"
            + (f" - ANÉIS DN {br(cm['DN'] * 100, 0)}" if cm["usar"] else ""), P(ec.H_TXT))
    m.texto(xt, yt - P(1.1), f"{N}x", P(ec.H_TXT * 1.25), ec.NV_MULT)
    return m


def _pdfs(pasta):
    """{caminho: (data em ns, tamanho)} dos PDFs da pasta."""
    out = {}
    for f in glob.glob(os.path.join(glob.escape(pasta), "*.PDF")):
        try:
            st = os.stat(f)
            out[f] = (st.st_mtime_ns, st.st_size)
        except OSError:
            pass
    return out


def _pdf_novo(pasta, nome, antes):
    """PDF que o SaveAs do TQS acabou de gravar para o desenho <nome> (novo ou mudado em relação à listagem antes,
    como no app de telas), com a revisão levada para o fim do nome. O TQS põe a revisão ("-R00") no meio dos nomes
    longos: depois do 15º caractere na V25 ("T1-POSTE-DT600-12" -> "T1-POSTE-DT600--R0012.PDF", conferido em
    14/11/2026) e do 23º na V26 (17/10/2026, app de telas). Até 14/11/2026 o app procurava só "<nome>*.PDF" e, na V25, indicava o PDF da memória.
    None: o TQS não gravou o PDF (aberto em outro programa, ele falha sem avisar)."""
    alvo = nome.upper()
    for f, est in _pdfs(pasta).items():
        if antes.get(f) == est:
            continue
        st, ext = os.path.splitext(os.path.basename(f))
        for m in re.finditer(r"-R\d{2}", st):
            if (st[:m.start()] + st[m.end():]).upper() == alvo:
                if m.end() == len(st):
                    return f
                dest = os.path.join(pasta, st[:m.start()] + st[m.end():] + m.group(0) + ext)
                try:
                    os.replace(f, dest)
                    return dest
                except OSError:                    # o destino aberto em outro programa: fica o nome do TQS
                    return f
    return None


def gerar(res, pasta):
    """Grava <nome>.DWG (+ PDF e DXF conforme os parâmetros). Devolve dict(arquivos, tabela, avisos)."""
    itens = dependencias.conferir(tqs=True)        # antes de criar a pasta ou gravar qualquer arquivo
    if dependencias.faltas(itens):
        raise RuntimeError(dependencias.mensagem_faltas(itens, "gravar o DWG"))
    from TQS import TQSDwg, TQSUtil
    import estaca_dwg as ed
    p = res["p"]
    pasta = os.path.abspath(pasta)
    os.makedirs(pasta, exist_ok=True)
    base = os.path.join(pasta, ec.limpar_nome(p["nome"]))
    avisos = []
    mascara = ed._ler_mascara_quant() if p["saidas"]["quant_resumo"] else None
    if p["saidas"]["quant_resumo"] and not mascara:
        avisos.append("Modelo MASQUANT.DWG não encontrado: $QUANT não gravado.")
    m1 = montar(res)
    dwg = TQSDwg.Dwg()
    dwg.file.New()
    s = dwg.settings
    s.systemId, s.subSystemId, s.scale = TQSDwg.IEDTAB, 13, float(p["saidas"]["escala"])
    fermor = os.path.join(TQSUtil.SupportFolder(), "PILAR", "FERCOR", "FERMOR1.DWG")
    fermor_ok = os.path.exists(fermor) and dwg.draw.BlockLoadFromDwg(fermor) == 0
    pares = [(ed._criar_ferro(dwg, f), f) for f in m1.ferros]
    tabela = ed._ler_tabela(pares)
    m2 = montar(res, tabela)
    ed._desenhar(dwg, m2.prims, fermor_ok, mascara)
    ruins = ed._fora_do_padrao(dwg)
    if ruins:
        dwg.file.Close()
        raise RuntimeError(f"Desenho não gravado: elementos nos níveis 1-199 (reservados às armaduras): {ruins[:5]}")
    arquivos = dict(dwg=base + ".DWG")
    cwd = os.getcwd()
    os.chdir(pasta)
    try:
        dwg.file.SaveAs(base + ".DWG")
        if p["saidas"]["pdf"]:
            antes = _pdfs(pasta)
            dwg.file.SaveAs(base + ".PDF")
            pdf = _pdf_novo(pasta, os.path.basename(base), antes)
            if pdf:
                arquivos["pdf"] = pdf
            else:
                avisos.append("O TQS não gravou o PDF do desenho (está aberto em outro programa?): feche-o e gere de novo.")
        if p["saidas"]["dxf"]:
            dwg.file.SaveAs(base + ".DXF")
            if os.path.exists(base + ".DXF"):
                arquivos["dxf"] = base + ".DXF"
                ed._dxf_continuo(base + ".DXF")
                if p["saidas"]["dxf_plotagem"]:
                    try:
                        ed._dxf_com_cores(base + ".DXF", ed._cores_plotagem(dwg))
                    except (OSError, ValueError, IndexError) as e:
                        avisos.append(f"DXF com as cores do desenho: não li a tabela de penas ({e}).")
    finally:
        dwg.file.Close()
        os.chdir(cwd)
    return dict(arquivos=arquivos, tabela=tabela, avisos=avisos, modelo=m2)


def main():
    ap = argparse.ArgumentParser(description="Desenho do tubulão curto em DWG TQS")
    ap.add_argument("json")
    ap.add_argument("--saida")
    a = ap.parse_args()
    sys.stdout.reconfigure(errors="replace")
    itens = dependencias.conferir(tqs=True)        # antes de calcular e de gravar qualquer arquivo
    if dependencias.faltas(itens):
        print(dependencias.mensagem_faltas(itens, "gravar o DWG"))
        return 1
    try:
        par = json.load(open(a.json, encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"Não consegui ler {a.json}: {e}")
        return 1
    try:
        res = tcore.calcular(par, os.path.dirname(os.path.abspath(a.json)))
        r = gerar(res, a.saida or os.path.join(tcore.SAIDAS, res["p"]["nome"]))
    except (ValueError, RuntimeError) as e:          # dados com erro ou TQS indisponível: diz o quê, sem traceback
        print(f"Desenho não gravado:\n{e}")
        return 1
    for k, v in r["arquivos"].items():
        print(f"{k.upper():5s} {v}")
    for t in r["tabela"]:
        print(f"  N{t['mark']} {t['quant']} ø{t['bitola']:g} C={t['comp']:.0f}")
    for av in r["avisos"]:
        print("  [aviso]", av)
    return 0


if __name__ == "__main__":
    sys.exit(main())
