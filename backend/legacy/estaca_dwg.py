# -*- coding: utf-8 -*-
# Cópia portátil dos tubulões (14/11/2026): copiado de _apps\EstacaEscavada_Portatil\estaca_dwg.py, sem alterações no código.
"""
Grava o detalhe de estaca escavada em DWG TQS, com ferros inteligentes.

Fluxo: cria os ferros (IPOFER), lê de volta a tabela calculada pelo próprio TQS,
desenha tabelas e textos com esses valores e salva. Os ferros podem ser editados
no Editor de Armação, e a tabela de ferros do TQS pode ser gerada normalmente.

Uso:  python estaca_dwg.py <parametros.json> [--saida PASTA] [--png]
O JSON pode ter os parâmetros de uma estaca ou {"estacas": [{...}, {...}]}.
Grava <nome>.DWG (+ PDF/DXF se pedido nos parâmetros) e <nome>.json com os
parâmetros usados, para reabrir no aplicativo.

Cópia portátil (11/11/2026): funciona com o pacote do TQS V25 (TQSPythonInterface 2.1.x) e V26 (tqs 3.0.x); sem o
pacote ou sem o TQS instalado, diz o que falta (dependencias.py) antes de gravar qualquer arquivo.
"""
import os, sys, glob, json, math, argparse
import estaca_core as ec
import dependencias

try:                                             # sem o pacote do TQS, o erro vira mensagem em gerar() e main()
    from TQS import TQSDwg, TQSUtil
except Exception:
    TQSDwg = TQSUtil = None

PASTA_PADRAO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saidas")


def _exigir_tqs(acao="gravar o DWG"):
    """RuntimeError com o que falta (sem traceback útil ao usuário) se o TQS não estiver pronto para gravar."""
    itens = dependencias.conferir(tqs=True)
    if dependencias.faltas(itens) or TQSDwg is None:
        raise RuntimeError(dependencias.mensagem_faltas(itens, acao) if dependencias.faltas(itens) else
                           "O pacote do TQS não carregou neste Python. " + dependencias.COMO_INSTALAR_TQS)


def _distr_quantidade(r, n):
    """Fixa em n a quantidade da última faixa do ferro. No pacote da V25 (TQSPythonInterface 2.1.x) o método é
    RebarDistrQuantity; no da V26 (tqs 3.0.x) foi renomeado para RebarDistrAutoSum, com os mesmos parâmetros e a
    mesma rotina da DLL (IPOFER_FAIXDISTCALCNFAUTO; conferido nos fontes do 2.1.7 e do 3.0.18)."""
    f = getattr(r, "RebarDistrQuantity", None) or getattr(r, "RebarDistrAutoSum", None)
    if f is None:
        raise RuntimeError("O pacote do TQS instalado não tem RebarDistrQuantity nem RebarDistrAutoSum: não dá para "
                           "fixar a quantidade da faixa (anéis duplos nas pontas). Desmarque os anéis duplos.")
    f(1, 0, n)


# --------------------------------------------------------------------------- DXF com as cores da plotagem
# O "Salvar como DXF" da interface (g_salvarcomodxf) grava as cores de tela de cada nível e não segue a opção
# "Plotagem em desenho/DXF com regras de plotagem em impressora" do TQS (PLOTDES.DAT, iplotdesplt): ela é do
# plotador. Para ter no DXF as cores do PDF, o app troca a cor de cada camada (nível) pela da pena que a tabela de
# plotagem dá ao nível (tabplt_invpen), com as cores da tabela de penas usada no PDF (PENAS\PLOTPENA.PEN; conferido
# em 13/10/2026 nas cores do PDF gerado). O DXF do TQS é do formato AC1002, sem cor RGB: vale a cor mais próxima
# da paleta do AutoCAD (ACI). Pedido do usuário em 13/10/2026.
ARQ_PENAS_PDF = "PLOTPENA.PEN"


def _paleta_aci():
    """Cores RGB da paleta padrão do AutoCAD (índices 1 a 255)."""
    import colorsys
    pal = {1: (255, 0, 0), 2: (255, 255, 0), 3: (0, 255, 0), 4: (0, 255, 255), 5: (0, 0, 255), 6: (255, 0, 255),
           7: (255, 255, 255), 8: (128, 128, 128), 9: (192, 192, 192)}
    brilho = (255, 204, 153, 127, 76)
    for i in range(10, 250):
        h, k = (i - 10) // 10 * 15 / 360.0, i % 10
        v, s = brilho[k // 2] / 255.0, (1.0 if k % 2 == 0 else 0.5)
        pal[i] = tuple(round(c * 255) for c in colorsys.hsv_to_rgb(h, s, v))
    for i, g in zip(range(250, 256), (51, 91, 132, 173, 214, 255)):
        pal[i] = (g, g, g)
    return pal


def _aci_mais_proxima(rgb, pal=_paleta_aci()):
    if max(rgb) < 40:                            # preto: a cor 7, que sai preta no papel
        return 7
    return min((i for i in pal if i != 7), key=lambda i: sum((a - b) ** 2 for a, b in zip(pal[i], rgb)))


def _penas_pdf():
    """Cor RGB de cada pena da plotagem em PDF (0x00BBGGRR no arquivo de penas do TQS)."""
    arq = os.path.join(TQSUtil.SupportFolder(), "NGE", "PENAS", ARQ_PENAS_PDF)
    lin = open(arq, encoding="cp1252").read().splitlines()
    n = int(lin[0].split()[0])
    cores = []
    for i in range(n):
        c = int(lin[1 + 2 * i].split()[0], 16)
        cores.append((c & 0xFF, (c >> 8) & 0xFF, (c >> 16) & 0xFF))
    return cores


def _cores_plotagem(dwg):
    """Cor ACI de cada nível (0 a 255) pela tabela de plotagem do desenho e pela tabela de penas do PDF."""
    dwg.plotting.LoadPlottingTable()
    penas = _penas_pdf()
    out = {}
    for nv in range(256):
        ip = dwg.plotting.AttributeRead(nv)[0]
        if 0 <= ip < len(penas):
            out[nv] = _aci_mais_proxima(penas[ip])
    return out


def _dxf_com_cores(arq, cores):
    """Reescreve o DXF: cor de cada camada (tabela LAYER) pela pena do nível e, nas entidades com cor própria igual
    à cor original da camada (cor "do nível"), a mesma troca. As outras cores próprias ficam como o TQS gravou: são
    as cores especiais, como a dos ferros inteligentes por bitola (critérios de desenho de armaduras, DESARM.DAT:
    "Cor RGB por bitola"), que o PDF também usa (correção de 13/10/2026: antes os ferros ficavam pretos)."""
    lin = open(arq, encoding="latin-1", newline="").read().split("\n")
    eol = "\r" if lin and lin[0].endswith("\r") else ""
    val = lambda j: lin[j].rstrip("\r").strip()
    em_layer, nome, camada = False, None, None
    cor_orig = {}                                    # cor de cada camada antes da troca
    n_trocas = 0
    for j in range(0, len(lin) - 1, 2):
        cod, v = val(j), val(j + 1)
        if cod == "0":
            em_layer, nome, camada = v == "LAYER", None, None
        elif cod == "2" and em_layer:
            nome = v
        elif cod == "8":
            camada = v
        elif cod == "62":
            nv = nome if em_layer else camada
            if nv is None or not nv.isdigit() or int(nv) not in cores or v in ("0", "256"):
                continue
            if em_layer:
                cor_orig[nv] = abs(int(v))
            elif abs(int(v)) != cor_orig.get(nv):
                continue                             # cor especial (ferro por bitola etc.): fica
            sinal = -1 if v.startswith("-") else 1   # camada desligada: cor negativa
            lin[j + 1] = f"{sinal * cores[int(nv)]:6d}" + eol
            n_trocas += 1
    open(arq, "w", encoding="latin-1", newline="").write("\n".join(lin))
    return n_trocas


def _dxf_continuo(arq):
    """O "Salvar como DXF" do TQS grava na tabela LTYPE duas entradas CONTINUOUS: a primeira contínua ("Solid line")
    e, no fim, outra com traço 0,2 / -0,8. Os leitores que ficam com a última (ezdxf e visualizadores) desenham todas
    as linhas contínuas tracejadas. Tira as repetidas e mantém a primeira (26/10/2026). Os textos não precisam de
    troca: o TQS já grava a bitola ("{") como "%%c". Devolve o nº de entradas retiradas."""
    lin = open(arq, encoding="latin-1", newline="").read().split("\n")
    val = lambda j: lin[j].rstrip("\r").strip()
    tabela, entradas, ini = None, [], None           # entradas da tabela LTYPE: (linha inicial, linha final, nome)
    for j in range(0, len(lin) - 1, 2):
        cod, v = val(j), val(j + 1)
        if cod == "0":
            if ini is not None:
                entradas[-1][1] = j
                ini = None
            if v == "TABLE":
                tabela = ""
            elif v == "ENDTAB":
                tabela = None
            elif tabela == "LTYPE" and v == "LTYPE":
                ini = j
                entradas.append([j, None, None])
        elif cod == "2" and tabela == "":
            tabela = v
        elif cod == "2" and ini is not None and entradas[-1][2] is None:
            entradas[-1][2] = v.upper()
    tirar = [(a, b) for a, b, nome in entradas if nome == "CONTINUOUS" and b is not None][1:]
    for a, b in reversed(tirar):
        del lin[a:b]
    if tirar:
        open(arq, "w", encoding="latin-1", newline="").write("\n".join(lin))
    return len(tirar)



def _criar_ferro(dwg, f):
    r = TQSDwg.SmartRebar(dwg)
    r.type = {"reto": TQSDwg.ICPFRT, "anel": TQSDwg.ICPFGN, "gen": TQSDwg.ICPFGN}.get(f["tipo"], TQSDwg.ICPSTRGEN)
    r.mark, r.quantity, r.multiplier = f["mark"], f["quant"], 1
    r.diameter, r.spacing, r.cover = f["bitola"], f["espac"], f["cover"]
    if f["comment"]:
        r.comment = ec.txt_tqs(f["comment"])
    if f["tipo"] == "reto":
        r.straightBarMainLength = f["main"]
        r.straightBarRightLength = f["dobra"]
        r.straightBarZone = TQSDwg.ICPPOS if f["zona"] == "pos" else TQSDwg.ICPNEG
        if f.get("ganchos"):                     # grampo: ganchos nas duas pontas (tubulão: grelha de fretagem)
            r.leftHook = r.rightHook = {90: TQSDwg.ICP090, 135: TQSDwg.ICP135, 180: TQSDwg.ICP180}[f["ganchos"]]
            r.bendDimRadius = r.bendDimPerimeter = r.bendTickDisplay = 0   # sem as marcas de dobra nos ganchos
    elif f["tipo"] == "gen":
        # barra com o afunilamento: ferro genérico (trecho reto + inclinado), sem cota de raio de dobra
        r.leftHook = r.rightHook = TQSDwg.ICPSGA
        r.bendDimRadius = r.bendDimPerimeter = r.bendTickDisplay = 0
    elif f["tipo"] == "anel":
        # anel soldado: ferro genérico em arcos (o estribo circular do TQS sempre tem ganchos e transpasse próprio)
        r.leftHook = r.rightHook = TQSDwg.ICPSGA
        r.bendDimRadius = r.bendDimPerimeter = r.bendTickDisplay = 0
        r.leaderLine = 0                         # o texto fica logo abaixo da seção: sem linha de chamada
    else:
        r.genericStirrupType = TQSDwg.ICPEGENCIR
        r.circularStirrupRadius = f["raio"]
        r.genericStirrupLongDiameter = f["blong"]
    for fx in f["faixas"]:
        r.RebarDistrAdd(TQSDwg.ICPE1P if fx["inicio"] else TQSDwg.ICPESP, 90.0,
                        fx["x"], fx["y1"], fx["x"], fx["y2"], fx["xcot"], (fx["y1"] + fx["y2"]) / 2,
                        fx["cotar"], 1, 1, 1, 1, TQSDwg.ICPCENTR_CENTRAD, TQSDwg.ICPQUEBR_SALTONPOS,
                        "", 0, 0, 0, 0, 1, fx["s"], 1.0)
        if fx.get("nman"):                       # quantidade fixa (anéis duplos nas pontas)
            _distr_quantidade(r, fx["nman"])
    for j, i in enumerate(f["ins"]):
        r.RebarLine(i["x"], i["y"], i["ang"], i["esc"], i["ident"], i["idobra"], i["ipatas"],
                    i.get("explode", 0), i.get("nv", ec.NV_FERRO), -1, -1)
        if f["tipo"] == "gen" and j == 0:        # poligonal a partir do ponto de inserção
            for x, y in f["pontos"]:
                r.GenRebarPoint(x, y, 0.0, 0, 0, -1)
        if f["tipo"] == "anel" and j == 0:       # circunferência pelo eixo + o transpasse, em arcos de 90°
            ra, th = f["r_eixo"], f["transpasse"] / f["r_eixo"]
            pts = [(ra, 0.0), (0.0, ra), (-ra, 0.0), (0.0, -ra), (ra, 0.0)]
            r.GenRebarPoint(ra, 0.0, 0.0, 0, 0, -1)
            for x, y in pts[1:] + [(ra * math.cos(th), ra * math.sin(th))]:
                r.GenRebarPoint(0.0, 0.0, 0.0, 1, 0, -1)
                r.GenRebarPoint(x, y, 0.0, 0, 0, -1)
    if f.get("texto"):                           # texto em posição definida: sem linha de chamada
        r.leaderLine = 0
        alin = TQSDwg.ICPCENTR_ESQUERD if f["texto"].get("alin") == "esq" else TQSDwg.ICPCENTR_CENTRAD
        if f["texto"].get("cmp"):                # quantidade, posição, bitola e comprimento (o genérico omite o C=)
            r.RebarTextDisplaySelection(1, 1, 1, 0, 1, alin, TQSDwg.ICPQUEBR_SEMQUEBRA)
        r.RebarTextDisplayPosition(f["texto"]["x"], f["texto"]["y"], ec.H_TXT, f["texto"].get("ang", 0.0), 0,
                                   alin, TQSDwg.ICPQUEBR_SEMQUEBRA)
    for mk in f["marcas"]:
        r.RebarMarkIdentify(0, mk["xt"], mk["yt"], mk["nfr"], mk["pos"], mk["bit"], mk["esp"])
        for x, y in mk["pts"]:
            r.RebarMarkIdentifyPoint(x, y)
    return r


def _ler_tabela(pares):
    """Tabela de ferros como o TQS calculou (quantidade das faixas, comprimento com descontos)."""
    tab = {}
    for r, f in pares:
        for i in range(r.RebarScheduleNumDescr()):
            info = r.RebarScheduleInfo(i)
            ipos, bitola, nfer, mult, compr = info[0], info[1], info[2], info[3], info[8]
            t = tab.setdefault(ipos, dict(mark=ipos, aco=f["aco"], bitola=round(bitola, 1), quant=0,
                                          comp=round(compr), obs=f["comment"]))
            t["quant"] += nfer * mult
    return sorted(tab.values(), key=lambda t: t["mark"])


def _ler_mascara_quant():
    """Elementos de NGE\\MASCARAS2\\MASQUANT.DWG, o modelo do bloco $QUANT do editor (None se não existir)."""
    arq = os.path.join(TQSUtil.SupportFolder(), "NGE", "MASCARAS2", "MASQUANT.DWG")
    if not os.path.exists(arq):
        return None
    d = TQSDwg.Dwg()
    if d.file.Open(arq) != 0:
        return None
    it, elems = d.iterator, []
    it.Begin()
    while True:
        t = it.Next()
        if t == TQSDwg.DWGTYPE_EOF:
            break
        if t == TQSDwg.DWGTYPE_LINE:
            elems.append(("L", it.level, it.x1, it.y1, it.x2, it.y2))
        elif t == TQSDwg.DWGTYPE_TEXT:
            elems.append(("T", it.level, it.x1, it.y1, it.textHeight, it.textAngle, it.text))
    d.file.Close()
    return elems


def _bloco_quant(dwg, pr, mascara):
    """Bloco $QUANT idêntico ao gravado pelo diálogo "Quantitativos para o resumo estrutural":
    cópia do modelo com os marcadores retirados do lugar e os valores ("%.2f") acrescentados no fim."""
    valores = {"%AREAEST": f"{pr['area_est']:.2f}", "%AREAFOR": f"{pr['area_for']:.2f}",
               "%VOLFOR": f"{pr['volume']:.2f}", "%UNIDM2A": "m2", "%UNIDM2B": "m2", "%UNIDM3": "m3"}
    d = dwg.draw
    d.BlockOpen("$QUANT", 0.0, 0.0)
    marcadores = []
    for e in mascara:
        d.level = e[1]
        if e[0] == "L":
            d.Line(*e[2:])
        elif e[6].strip().startswith("%"):
            marcadores.append(e)
        else:
            d.Text(e[2], e[3], e[4], e[5], ec.txt_tqs(e[6]))
    for e in marcadores:
        d.level = e[1]
        d.Text(e[2], e[3], e[4], e[5], valores.get(e[6].strip(), ""))
    d.BlockClose()
    d.level = pr["nv"]
    d.BlockInsert("$QUANT", pr["x"], pr["y"], pr["esc"], pr["esc"], 0.0)


def _desenhar(dwg, prims, fermor_ok, mascara_quant=None):
    d, dm = dwg.draw, dwg.dim
    for pr in prims:
        t = pr["t"]
        if t == "quant":
            if mascara_quant:
                _bloco_quant(dwg, pr, mascara_quant)
            continue
        d.level, d.style, d.color = pr.get("nv", 0), pr.get("estilo", -1), -1
        if t == "linha":
            d.Line(*pr["p"])
        elif t == "poli":
            d.PolyEnterXY([list(v) for v in pr["xy"]])
            d.PolylineFilled() if pr["cheio"] else d.Polyline()
        elif t == "circ":
            d.Circle(pr["x"], pr["y"], pr["r"])
        elif t == "texto":
            d.Text(pr["x"], pr["y"], pr["h"], pr["ang"], ec.txt_tqs(pr["s"]))
        elif t == "cota":
            dm.idmniv, dm.dimlfc = pr["nv"], pr["fator"]
            if pr["txt"]:
                dm.dimtxu = ec.txt_tqs(pr["txt"])   # vale só para a próxima cota; "" apagaria o texto das seguintes
            x1, y1, x2, y2 = pr["p"]
            if pr["vert"]:
                dm.DimVertical(x1, y1, x2, y2, pr["pos"], y1)
            else:
                dm.DimHorizontal(x1, y1, x2, y2, x1, pr["pos"])
            dm.dimlfc = 1.0
        elif t == "fercor":
            if fermor_ok:
                d.BlockInsert("FERMOR1", pr["x"], pr["y"], pr["esc"], pr["esc"], 0.0)
            else:
                d.Circle(pr["x"], pr["y"], pr["esc"] / 2)


def _fora_do_padrao(dwg):
    """Elementos nos níveis 1-199 que não pertencem a ferro inteligente (reservados às armaduras identificadas)."""
    it, achados, objeto = dwg.iterator, [], []
    it.Begin()
    while True:
        t = it.Next()
        if t == TQSDwg.DWGTYPE_EOF:
            break
        if t == TQSDwg.DWGTYPE_OBJECT:
            objeto.append(it.objectName)
        elif t == TQSDwg.DWGTYPE_OBJECTEND:
            objeto.pop()
        elif it.level in ec.NV_RESERVADO and "IPOFER" not in objeto:
            achados.append((it.level, it.text if t == TQSDwg.DWGTYPE_TEXT else f"elemento tipo {t}"))
    return achados


def _comparar(res, tabela):
    est = {t["mark"]: t for t in ec.tabela_estimada(res)}
    dif = []
    for t in tabela:
        e = est.get(t["mark"])
        if e and (e["quant"] != t["quant"] or abs(e["comp"] - t["comp"]) > 1):
            dif.append(f"N{t['mark']}: prévia {e['quant']} x {e['comp']:.0f} cm, TQS {t['quant']} x {t['comp']:.0f} cm")
    return dif


def gerar(par, pasta=None, nome=None):
    """Gera o DWG. Devolve dict(res, tabela, arquivos, diferencas, modelo). ValueError se houver erro nos dados."""
    res = ec.calcular(par)
    if res["erros"]:
        raise ValueError("\n".join(res["erros"]))
    _exigir_tqs()                                # antes de criar a pasta ou gravar qualquer arquivo
    p = res["p"]
    pasta = os.path.abspath(pasta or PASTA_PADRAO)
    os.makedirs(pasta, exist_ok=True)
    base = os.path.join(pasta, ec.limpar_nome(nome or p["nome_arquivo"] or ec.nome_padrao(p, res)))

    mascara = _ler_mascara_quant() if p["quant_resumo"] else None   # antes de abrir o desenho novo
    if p["quant_resumo"] and not mascara:
        res["alertas"].append(("aviso", "Modelo MASQUANT.DWG não encontrado: quantitativos do resumo estrutural não gravados."))
    m1 = ec.montar_modelo(p, res)
    dwg = TQSDwg.Dwg()
    dwg.file.New()
    s = dwg.settings
    s.systemId, s.subSystemId, s.scale = TQSDwg.IEDTAB, 13, float(p["escala"])
    fermor = os.path.join(TQSUtil.SupportFolder(), "PILAR", "FERCOR", "FERMOR1.DWG")
    fermor_ok = os.path.exists(fermor) and dwg.draw.BlockLoadFromDwg(fermor) == 0
    pares = [(_criar_ferro(dwg, f), f) for f in m1.ferros]
    tabela = _ler_tabela(pares)
    m2 = ec.montar_modelo(p, res, tabela)          # tabelas e textos com os valores do TQS
    _desenhar(dwg, m2.prims, fermor_ok, mascara)
    ruins = _fora_do_padrao(dwg)
    if ruins:
        dwg.file.Close()
        raise RuntimeError("Desenho não gravado: há elementos nos níveis 1-199, reservados às armaduras "
                           f"identificadas: {ruins[:5]}")

    arquivos = dict(dwg=base + ".DWG")
    cwd = os.getcwd()
    os.chdir(pasta)                              # a plotagem em PDF procura o desenho na pasta atual
    try:
        dwg.file.SaveAs(base + ".DWG")
        if p["pdf"]:
            dwg.file.SaveAs(base + ".PDF")       # o TQS acrescenta a revisão: <nome>-R00.PDF
            pdfs = glob.glob(glob.escape(base) + "*.PDF")
            if pdfs:
                arquivos["pdf"] = max(pdfs, key=os.path.getmtime)
        if p["dxf"]:
            dwg.file.SaveAs(base + ".DXF")
            if os.path.exists(base + ".DXF"):
                arquivos["dxf"] = base + ".DXF"
                _dxf_continuo(base + ".DXF")
                if p["dxf_plotagem"]:                # cores da plotagem (como no PDF) em vez das do desenho
                    try:
                        _dxf_com_cores(base + ".DXF", _cores_plotagem(dwg))
                    except (OSError, ValueError, IndexError) as e:
                        res["alertas"].append(("aviso", f"DXF gravado com as cores do desenho: não li a tabela de penas "
                                                        f"{ARQ_PENAS_PDF} ({e})."))
    finally:
        dwg.file.Close()
        os.chdir(cwd)

    salvar = {k: v for k, v in p.items()}
    with open(base + ".json", "w", encoding="utf-8") as fp:
        json.dump(salvar, fp, ensure_ascii=False, indent=2)
    arquivos["json"] = base + ".json"
    return dict(res=res, tabela=tabela, arquivos=arquivos, diferencas=_comparar(res, tabela), modelo=m2)


def ler_primitivas(caminho):
    """Lê um DWG TQS e devolve primitivas no formato do estaca_core (para a prévia)."""
    _exigir_tqs("ler o DWG")
    dwg = TQSDwg.Dwg()
    if dwg.file.Open(caminho) != 0:
        raise IOError(f"Não abri {caminho}")
    it, prims = dwg.iterator, []
    it.Begin()
    while True:
        t = it.Next()
        if t == TQSDwg.DWGTYPE_EOF:
            break
        if t == TQSDwg.DWGTYPE_LINE:
            prims.append(dict(t="linha", nv=it.level, estilo=it.style, p=(it.x1, it.y1, it.x2, it.y2)))
        elif t in (TQSDwg.DWGTYPE_POLYLINE, TQSDwg.DWGTYPE_CURVE):
            prims.append(dict(t="poli", nv=it.level, estilo=it.style, xy=[(v[0], v[1]) for v in it.xy],
                              cheio=bool(it.isFilled)))
        elif t == TQSDwg.DWGTYPE_CIRCLE:
            prims.append(dict(t="circ", nv=it.level, estilo=it.style, x=it.xc, y=it.yc, r=it.radius))
        elif t == TQSDwg.DWGTYPE_ARC:
            prims.append(dict(t="arco", nv=it.level, x=it.xc, y=it.yc, r=it.radius, a1=it.startAngle, a2=it.endAngle))
        elif t == TQSDwg.DWGTYPE_TEXT:
            prims.append(dict(t="texto", nv=it.level, x=it.x1, y=it.y1, h=it.textHeight, ang=it.textAngle, s=it.text))
    escala = dwg.settings.scale
    dwg.file.Close()
    return prims, escala


def main():
    ap = argparse.ArgumentParser(description="Detalhe de estaca escavada em DWG TQS")
    ap.add_argument("json", help="parâmetros de uma estaca ou {\"estacas\": [...]}")
    ap.add_argument("--saida", help="pasta de saída (padrão: saidas\\ ao lado deste script)")
    ap.add_argument("--png", action="store_true", help="grava também uma prévia PNG do DWG gerado")
    a = ap.parse_args()
    itens = dependencias.conferir(tqs=True, png=a.png)    # antes de gravar qualquer arquivo
    if dependencias.faltas(itens):
        print(dependencias.mensagem_faltas(itens, "gravar o DWG"))
        return 1
    try:
        dados = json.load(open(a.json, encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"Não consegui ler {a.json}: {e}")
        return 1
    lista = dados["estacas"] if isinstance(dados, dict) and "estacas" in dados else \
        (dados if isinstance(dados, list) else [dados])
    for par in lista:
        try:
            r = gerar(par, a.saida)
        except (ValueError, RuntimeError) as e:          # dados com erro ou TQS indisponível: diz o quê e segue
            print(f"Estaca {par.get('tipo', '') if isinstance(par, dict) else ''} não gravada:\n{e}\n")
            continue
        print(ec.resumo_texto(r["res"], r["tabela"]))
        for n, msg in r["res"]["alertas"]:
            print(f"  [{n}] {msg}")
        for d in r["diferencas"]:
            print(f"  [prévia x TQS] {d}")
        for k, v in r["arquivos"].items():
            print(f"  {k.upper():5s} {v}")
        if a.png:
            import estaca_previa
            prims, esc = ler_primitivas(r["arquivos"]["dwg"])
            print("  PNG  ", estaca_previa.salvar_png(prims, (), os.path.splitext(r["arquivos"]["dwg"])[0] + ".png", esc))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
