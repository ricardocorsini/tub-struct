# -*- coding: utf-8 -*-
# Cópia portátil dos tubulões (14/11/2026): copiado de _apps\EstacaEscavada\estaca_core.py, sem alterações no código.
"""
Detalhamento de estaca escavada: parâmetros, cálculo e modelo de desenho.

Não depende do TQS. Calcula as posições de ferro e monta o desenho como uma
lista de primitivas em cm reais. estaca_dwg.py grava essas primitivas em DWG
TQS (com ferros inteligentes) e estaca_app.pyw as usa na prévia.

Convenções do desenho:
  * x = 0 no eixo da estaca, y = 0 na cota de arrasamento (cm, positivo para cima);
  * tamanhos "de papel" (textos, afastamentos) são cm de plotagem x escala;
  * seção transversal e detalhes ampliados pelo fator k = escala / escala_secao;
  * "{" é o caractere de bitola (ø) nas fontes do TQS.
"""
import math, re, textwrap
import estaca_sondagem as es

# --------------------------------------------------------------------------- tabelas
BITOLAS = [5.0, 6.3, 8.0, 10.0, 12.5, 16.0, 20.0, 25.0, 32.0]
MASSA_NOMINAL = {5.0: 0.154, 6.3: 0.245, 8.0: 0.395, 10.0: 0.617, 12.5: 0.963, 16.0: 1.578,
                 20.0: 2.466, 22.0: 2.984, 25.0: 3.853, 32.0: 6.313, 40.0: 9.865}   # kg/m, NBR 7480
# Medidos no TQS V25 (só para a prévia; a tabela do DWG usa o comprimento calculado pelo TQS)
EXTRA_ESTRIBO_CIRC = {5.0: 39.50, 6.3: 46.13, 8.0: 56.80, 10.0: 71.00, 12.5: 90.17,  # cm além do perímetro
                      16.0: 115.42, 20.0: 147.70, 25.0: 184.62, 32.0: 236.32}
DESCONTO_DOBRA = {6.3: 2.0, 8.0: 2.0, 10.0: 2.0, 12.5: 2.0, 16.0: 4.0, 20.0: 6.0,     # cm por dobra a 90°
                  25.0: 8.0, 32.0: 10.0}

# Níveis 1 a 199: reservados às armaduras identificadas (textos dos ferros inteligentes).
# Os demais seguem os desenhos do TQS: tabela de ferros e textos no 0, escala de detalhe
# 206, título de corte 226 (folhas de armação da Garagem Moura e detalhes de estaca do TQS).
NV_RESERVADO = range(1, 200)
NV_CONTORNO = NV_TEXTO = NV_TABELA = 0
NV_MULT, NV_EIXO, NV_ESCALA, NV_FERRO, NV_COTA, NV_TITULO = 202, 204, 206, 220, 221, 222
NV_FERCOR, NV_CORTE, NV_BLOCO = 224, 226, 231
# Armadura desenhada por linhas (hélice, estribos, anéis e barras dentro da elevação, detalhes): nível 239 da tabela
# do escritório ("estribo dentro da seção", ciano, pena 0,15). O 220 (0,60) fica para os ferros identificados
# (pedido de 09/10/2026).
NV_FERRO_INT = 239
# Linhas de chamada das marcas de nível: cinza-claro, pena 0,10 (pedido de 09/10/2026: mais suaves que as cotas).
# Solo do detalhe da ancoragem: o marrom da faixa de solos das sondagens (208, pena 0,15).
NV_CHAMADA, NV_SOLO = 252, 208
# Folga entre a face tocada e o início das linhas de nível e das ligações das sondagens (cm de plotagem): a mesma
# folga das linhas de chamada das cotas no critério padrão do TQS (dim.dimexo = 0,15; pedido de 13/10/2026).
FOLGA = 0.15
# Armadura do bloco no detalhe da ancoragem (gaiola esquemática, só referência): nível 207, pena cinza (13/10/2026).
NV_ARM_BLOCO = 207
# Armação das estacas no detalhe da ancoragem (barras, dobras, estribos e anéis): nível 234, ciano, pena 0,40, regra
# criada pelo usuário em 13/10/2026 para destacá-la sobre a gaiola do bloco.
NV_FERRO_DET = 234
# Bloco $QUANT ("Quantitativos para o resumo estrutural" do editor): nível 219, tamanho do
# modelo NGE\MASCARAS2\MASQUANT.DWG em cm de plotagem.
NV_QUANT, QUANT_LARG, QUANT_ALT = 219, 8.06, 2.62

# Alturas de texto em cm de plotagem
H_TIT, H_SUB, H_TXT, H_TAB = 0.45, 0.25, 0.20, 0.18

NOTAS_PADRAO = [
    "MEDIDAS EM CENTÍMETROS E COTAS EM METROS, SALVO INDICAÇÃO.",
    "AÇO CA-50 E CA-60 CONFORME NBR 7480.",
    "COBRIMENTO DA ARMADURA: {cobrimento} cm (FACE EXTERNA DO ESTRIBO).",
    "ARRASAR O CONCRETO ACIMA DA COTA DE ARRASAMENTO SEM DANIFICAR A ARMAÇÃO.",
]

TIPOS_ESTACA = {"escavada": "ESCAVADA", "hélice contínua": "HÉLICE CONTÍNUA", "raiz": "RAIZ"}
# Estaca raiz: o estribo tem de caber no tubo de perfuração. Por diâmetro da estaca (cm): bitola do estribo (mm)
# e diâmetro externo do estribo (cm), espaçamento 20 cm. Tabela do escritório, de Urbano Alonso, "Reavaliação do
# dimensionamento estrutural da estaca-raiz face às exigências do ensaio MB-3462 da ABNT", Solos & Rochas 16, 1993.
RAIZ_ESTRIBO = {10: (None, 6.7), 12: (None, 6.7), 15: (5.0, 8.3), 16: (5.0, 8.3), 20: (6.3, 9.9),
                25: (6.3, 14.0), 31: (6.3, 19.0), 41: (6.3, 25.0), 50: (6.3, 34.0)}
OBS_ANEL = "ANEL ENRIJECEDOR SOLDADO"
# NBR 6122, Tabela 4 (estacas moldadas in loco): armadura mínima (% da seção) e comprimento útil mínimo da
# armadura (m, incluindo o trecho de ligação com o bloco; None = integral). Escavada: comprimento da escavada com
# fluido (escolha do usuário em 09/10/2026).
BARRAS_MIN, BITOLA_MIN = 6, 10.0           # regra do escritório (09/10/2026), em todos os tipos
NBR6122 = {"hélice contínua": dict(taxa=0.4, comp=4.0),
           "escavada": dict(taxa=0.4, comp=4.0),
           "raiz": dict(taxa=0.4, comp=None)}
# Concreto pela classe de agressividade (Tabela 4: classe mínima em CAA I e II / III e IV; na raiz, fak da argamassa)
# e anexo da NBR 6122 de cada tipo. A escavada segue o anexo I (sem fluido: C25 em CAA I e II), como nas notas do
# escritório (13/10/2026).
CAAS = ("I", "II", "III", "IV")
CONCRETO_6122 = {"hélice contínua": dict(anexo="N", classe=(30.0, 40.0)),
                 "escavada": dict(anexo="I", classe=(25.0, 40.0)),
                 "raiz": dict(anexo="K", classe=(20.0, 20.0))}
# Especificação do concreto por classe (anexos N, N.9, e I, I.8): abatimento (mm) e classe S, diâmetro do agregado (mm),
# consumo mínimo de cimento (kg/m3) e a/c máximo; teor de exsudação inferior a 4 % em todos.
ESPEC_6122 = {("hélice contínua", 30.0): dict(s=(220, 260, "S220"), agr=("4,75", "12,5"), cim=350, ac="0,60"),
              ("hélice contínua", 40.0): dict(s=(220, 260, "S220"), agr=("4,75", "12,5"), cim=350, ac="0,45"),
              ("escavada", 25.0): dict(s=(100, 160, "S100"), agr=("9,5", "25"), cim=280, ac="0,60"),
              ("escavada", 40.0): dict(s=(100, 160, "S100"), agr=("9,5", "25"), cim=360, ac="0,45")}


def fck_minimo(tipo, caa):
    """fck mínimo (MPa) da NBR 6122, Tabela 4, para o tipo de estaca e a classe de agressividade."""
    cl = CONCRETO_6122[tipo]["classe"]
    return cl[0] if caa in ("I", "II") else cl[1]

PADRAO = dict(
    obra="", tipo="E1", tipo_estaca="escavada", caa="II", quantidade=1,
    diametro=60.0, cota_arrasamento=-1.50, cota_ponta=-19.50, cota_terreno=None,
    prolongar=False, cota_perfuracao=None,
    bloco_informar=False, bloco_altura=None, fundo_variavel=False, fundo_variacao=None, blocos=[],
    embutimento=10.0, lastro=5.0, cobrimento=5.0, diam_estribo=None, fck=30.0,
    n_barras=8, bitola_long=16.0, aco_long="CA-50", comp_armacao=6.00,
    ancoragem=60.0, ancoragem_auto=False, dobra=0.0, dobra_sentido="fora", comp_max=1200.0, transpasse=0.0,
    estribo="circular", bitola_estr=6.3, aco_estr="CA-50", espac=20.0,
    zona_sup=1.00, espac_sup=10.0, dist_topo=5.0, dist_pe=5.0,
    voltas_fecho=1.0, transpasse_espiral=40.0,
    afunilar=False, afun_comp=1.00, afun_diam=15.0, afun_bitola=8.0, afun_aco="CA-50", afun_quant=2,
    afun_obs="ESTRIBO ENRIJECEDOR SOLDADO À ARMAÇÃO LONGITUDINAL",
    aneis=False, bitola_anel=12.5, aco_anel="CA-50", espac_anel=200.0, transpasse_anel=0.0, aneis_duplos=False,
    espacadores=True, rolete_n=4, rolete_espac=100.0, rolete_mm=None,
    escala=50, escala_secao=25, interromper=True, quant_resumo=True, detalhe_ancoragem=True,
    desenhar_sondagens=False, sondagens=[],
    notas=list(NOTAS_PADRAO), nome_arquivo="", pdf=True, dxf=False, dxf_plotagem=True,
)
_TEXTO = {"obra", "tipo", "tipo_estaca", "caa", "aco_long", "aco_estr", "aco_anel", "estribo", "dobra_sentido", "nome_arquivo", "afun_aco", "afun_obs"}
_BOOL = {"prolongar", "bloco_informar", "fundo_variavel", "ancoragem_auto", "detalhe_ancoragem", "aneis", "aneis_duplos", "espacadores", "interromper", "quant_resumo", "desenhar_sondagens", "afunilar", "pdf", "dxf", "dxf_plotagem"}
_INT = {"quantidade", "n_barras", "escala", "escala_secao", "afun_quant", "rolete_n"}
_OPCIONAL = {"ancoragem", "cota_terreno", "cota_perfuracao", "bloco_altura", "fundo_variacao", "diam_estribo", "comp_armacao", "rolete_mm"}

ROTULOS = dict(
    quantidade="quantidade", diametro="diâmetro", cota_arrasamento="cota de arrasamento",
    cota_ponta="cota de ponta", cota_terreno="cota do terreno", embutimento="embutimento",
    lastro="lastro", cobrimento="cobrimento", fck="fck", n_barras="número de barras",
    bitola_long="bitola longitudinal", comp_armacao="comprimento da armação",
    ancoragem="ancoragem", dobra="dobra", comp_max="comprimento máximo", transpasse="transpasse",
    bitola_estr="bitola do estribo", espac="espaçamento", zona_sup="trecho superior",
    espac_sup="espaçamento do trecho superior", dist_topo="1º estribo", dist_pe="último estribo",
    voltas_fecho="voltas de fechamento", transpasse_espiral="transpasse do estribo helicoidal",
    bitola_anel="bitola do anel", espac_anel="espaçamento dos anéis", transpasse_anel="transpasse soldado do anel",
    diam_estribo="diâmetro externo do estribo", rolete_n="roletes por seção", rolete_espac="espaçamento dos roletes",
    rolete_mm="diâmetro do rolete", cota_perfuracao="cota de início da perfuração", bloco_altura="altura do bloco",
    fundo_variacao="variação da cota de fundo dos blocos",
    escala="escala", escala_secao="escala da seção", afun_comp="comprimento do afunilamento",
    afun_diam="diâmetro do estribo da ponta", afun_bitola="bitola do estribo da ponta",
    afun_quant="quantidade de estribos da ponta")


# --------------------------------------------------------------------------- utilidades
def num(v):
    if v is None or isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", ".")
    return float(s) if s else None

def br(v, casas=2):
    """Número no formato das tabelas do escritório (vírgula decimal)."""
    return f"{v:.{casas}f}".replace(".", ",")

def cota(v):
    return ("+" if v > 0.004 else "") + br(v)

def bt(b):
    return f"{b:g}"

def teto5(v):
    return 5.0 * math.ceil(v / 5.0 - 1e-9)

def massa_linear(b):
    return MASSA_NOMINAL.get(b, 0.0061654 * b * b)

def nome_padrao(p, res):
    return f"{p['tipo'] or 'ESTACA'}-EST{p['diametro']:g}L{res['L'] / 100:g}"

# A interface do TQS grava os textos em latin-1, e as fontes do TQS não têm alguns caracteres (ª, º, ³, ≥...).
_TROCA_TQS = {"—": "-", "–": "-", "−": "-", "≥": ">=", "≤": "<=", "³": "3", "²": "2", "º": "o", "ª": "a", "“": '"',
              "”": '"', "‘": "'", "’": "'", "…": "...", "•": "-", "×": "x", "·": "."}

def txt_tqs(s):
    """Texto que o TQS consegue gravar: troca os caracteres acima e o que sobrar fora do latin-1 vira "?"
    (ex.: o "—" que o GEOSPT põe na família sem solo, em "C: — | G: Areia Argilosa")."""
    s = "".join(_TROCA_TQS.get(ch, ch) for ch in str(s))
    return s.encode("latin-1", "replace").decode("latin-1")

def limpar_nome(nome):
    """Nome de arquivo válido. Sem ponto: com ponto no nome, a plotagem em PDF do TQS falha."""
    return re.sub(r'[\\/:*?"<>|.]+', "_", nome).strip() or "ESTACA"

def comprimento_ancoragem(fck, bitola_mm):
    """lb básico (cm), NBR 6118 9.4.2.4: CA-50 nervurada, boa aderência (barra vertical)."""
    fctd = 0.15 * fck ** (2 / 3) if fck <= 50 else 0.21 * 2.12 * math.log(1 + 0.11 * fck) / 1.4
    eta3 = 1.0 if bitola_mm < 32 else (132 - bitola_mm) / 100
    fbd = 2.25 * 1.0 * eta3 * fctd
    return bitola_mm / 10 / 4 * (500 / 1.15) / fbd

def normalizar_blocos(v):
    """Tabela dos blocos onde a estaca é usada: [{bloco, estacas, fundo}], com fundo = cota do fundo do bloco (m,
    opcional). Aceita dicionários ou linhas [bloco, estacas, fundo]; ignora as linhas vazias."""
    out = []
    for i, b in enumerate(v or [], 1):
        if isinstance(b, dict):
            nome, n, f = b.get("bloco", ""), b.get("estacas", ""), b.get("fundo")
        else:
            nome, n, f = (list(b) + ["", "", ""])[:3]
        nome = "" if nome is None else str(nome).strip()
        if not nome and str(n if n is not None else "").strip() == "" and str(f if f is not None else "").strip() == "":
            continue
        try:
            nn = num(n)
        except ValueError:
            nn = None
        if nn is None or nn < 1 or abs(nn - round(nn)) > 1e-6:
            raise ValueError(f"Blocos, linha {i} ({nome or 'sem nome'}): informe o número de estacas (inteiro, pelo menos 1).")
        try:
            ff = num(f)
        except ValueError:
            raise ValueError(f"Blocos, linha {i} ({nome or 'sem nome'}): cota de fundo inválida ({f!r}).")
        out.append(dict(bloco=nome or f"BLOCO {i}", estacas=int(round(nn)), fundo=ff))
    return out

def normalizar(par):
    """Completa com os valores padrão e converte os tipos. ValueError cita o campo inválido."""
    p = dict(PADRAO)
    p.update({k: v for k, v in (par or {}).items() if k in PADRAO})
    for k, v in p.items():
        if k in _TEXTO:
            p[k] = "" if v is None else str(v).strip()
        elif k == "notas":
            p[k] = [str(n) for n in (v.splitlines() if isinstance(v, str) else v) if str(n).strip()]
        elif k == "sondagens":
            p[k] = [es.normalizar_perfil(s) for s in (v or [])]
        elif k == "blocos":
            p[k] = normalizar_blocos(v)
        elif k in _BOOL:
            p[k] = v.strip().lower() in ("1", "true", "sim", "s") if isinstance(v, str) else bool(v)
        else:
            try:
                x = num(v)
            except ValueError:
                raise ValueError(f"Valor inválido em '{ROTULOS.get(k, k)}': {v!r}")
            if x is None and k not in _OPCIONAL:
                raise ValueError(f"Preencha '{ROTULOS.get(k, k)}'")
            p[k] = int(round(x)) if (k in _INT and x is not None) else x
    if p["blocos"]:                                    # com a tabela de blocos, a quantidade é a soma dela
        p["quantidade"] = sum(b["estacas"] for b in p["blocos"])
    p["estribo"] = "helicoidal" if p["estribo"].lower().startswith("h") else "circular"
    p["dobra_sentido"] = "dentro" if p["dobra_sentido"].lower().startswith("d") else "fora"
    t = p["tipo_estaca"].lower()
    p["tipo_estaca"] = "raiz" if t.startswith("r") else ("hélice contínua" if t.startswith("h") else "escavada")
    caa = p["caa"].upper().replace("CAA", "").strip() or "II"
    caa = {"1": "I", "2": "II", "3": "III", "4": "IV"}.get(caa, caa)
    if caa not in CAAS:
        raise ValueError(f"Classe de agressividade ambiental inválida: {p['caa']!r} (use I, II, III ou IV)")
    p["caa"] = caa
    return p


# --------------------------------------------------------------------------- cálculo
def calcular(par):
    """Geometria, posições de ferro, quantidades e alertas. Não desenha."""
    p = normalizar(par)
    erros, alertas = [], []
    raiz = p["tipo_estaca"] == "raiz"
    Dest = None
    if raiz and p["diametro"] > 0:
        # o estribo tem de caber no tubo de perfuração: o diâmetro externo dele (informado ou da tabela) define
        # o cobrimento equivalente
        tab = RAIZ_ESTRIBO.get(round(p["diametro"])) if abs(p["diametro"] - round(p["diametro"])) < 1e-6 else None
        Dest = p["diam_estribo"] or (tab[1] if tab else None)
        if not Dest:
            erros.append(f"Estaca raiz ø{p['diametro']:g}: informe o diâmetro externo do estribo "
                         f"(a tabela do escritório tem ø{', ø'.join(str(k) for k in RAIZ_ESTRIBO)}).")
        elif Dest >= p["diametro"]:
            erros.append(f"Estaca raiz: o estribo (ø{Dest:g} cm) deve ser menor que a estaca (ø{p['diametro']:g} cm).")
        else:
            p["cobrimento"] = (p["diametro"] - Dest) / 2
            b_tab = tab[0] if tab else None
            alertas.append(("info", f"Estaca raiz: estribo de ø{Dest:g} cm externo" + (" (tabela do escritório)" if not p["diam_estribo"] else "")
                                    + f", cobrimento equivalente {br(p['cobrimento'], 2)} cm"
                                    + (f"; a tabela indica estribo ø{bt(b_tab)} c/20" if b_tab and (b_tab != p["bitola_estr"] or p["espac"] != 20) else "")
                                    + "."))
    D, c = p["diametro"], p["cobrimento"]
    R = D / 2
    fl, ft = p["bitola_long"] / 10, p["bitola_estr"] / 10
    L = round((p["cota_arrasamento"] - p["cota_ponta"]) * 100, 1)
    # blocos com cota de fundo variável: a cota de arrasamento é a do bloco mais alto e dv (cm), a variação. Um só
    # detalhe serve a todos: armação comp_armacao abaixo do arrasamento mais baixo e trecho superior de estribos
    # até zona_sup abaixo dele (o bloco mais rebaixado é o mais desfavorável)
    dv = round(p["fundo_variacao"] * 100, 1) if (p["fundo_variavel"] and p["fundo_variacao"]) else 0.0
    Larm = round(p["comp_armacao"] * 100 + dv, 1) if p["comp_armacao"] else L      # vazio: armação até a ponta
    Rl = R - c - ft - fl / 2               # eixo das barras longitudinais
    re = R - c - ft / 2                    # eixo do estribo
    res = dict(p=p, erros=erros, alertas=alertas, L=L, Larm=Larm, R=R, Rl=Rl, r_estr=re, diam_estribo=Dest, dv=dv)

    # perfuração a partir de uma cota acima do arrasamento (ex.: o 0,00 da arquitetura): a armação vai até ela e o
    # concreto acima do arrasamento é perdido (demolido no arrasamento)
    h_perd = 0.0
    if p["prolongar"]:
        if p["cota_perfuracao"] is None:
            erros.append("Informe a cota de início da perfuração (ou desmarque o prolongamento da armação).")
        else:
            h_perd = round((p["cota_perfuracao"] - p["cota_arrasamento"]) * 100, 1)
            if h_perd <= 0:
                erros.append("A cota de início da perfuração deve ficar acima da cota de arrasamento.")
    res["h_perd"] = max(h_perd, 0.0)
    if p["fundo_variavel"] and dv <= 0:
        erros.append("Informe a variação da cota de fundo dos blocos (ou desmarque o fundo variável).")
    elif dv > 0 and dv >= L:
        erros.append("A variação da cota de fundo dos blocos é maior que a estaca.")
    hb = None                                              # altura do bloco (cm), se informada
    if p["bloco_informar"]:
        if p["embutimento"] <= 0:
            alertas.append(("aviso", "Embutimento 0 (sem bloco): a altura do bloco foi ignorada."))
        elif not p["bloco_altura"] or p["bloco_altura"] <= p["embutimento"]:
            erros.append("Informe a altura do bloco, maior que o embutimento da estaca (ou desmarque a opção).")
        else:
            hb = p["bloco_altura"]
    res["h_bloco"] = hb
    if D <= 0: erros.append("Diâmetro deve ser positivo.")
    if L <= 0: erros.append("A cota de ponta deve ficar abaixo da cota de arrasamento.")
    if p["n_barras"] < 1: erros.append("Número de barras deve ser pelo menos 1.")
    if Rl <= 0: erros.append("Cobrimento e bitolas não cabem no diâmetro.")
    if Larm <= 0: erros.append("Comprimento da armação deve ser positivo.")
    if L > 0 and Larm > L: erros.append(f"Armação ({br(Larm / 100)} m" + (" com a variação do fundo dos blocos" if dv else "")
                                        + f") maior que a estaca ({br(L / 100)} m)"
                                        + ("; reduza a armação ou deixe o campo vazio (até a ponta)." if dv else "."))
    if p["espac"] <= 0: erros.append("Espaçamento (ou passo) dos estribos deve ser positivo.")
    if p["quantidade"] < 1: erros.append("Quantidade de estacas deve ser pelo menos 1.")
    if p["escala"] <= 0 or p["escala_secao"] <= 0: erros.append("Escalas devem ser positivas.")
    if erros:
        return res

    # --- armadura longitudinal
    lb = comprimento_ancoragem(p["fck"], p["bitola_long"])
    l0 = p["transpasse"] if p["transpasse"] > 0 else teto5(max(lb, 15 * fl, 20.0))
    res.update(lb=lb, l0=l0, l0_auto=p["transpasse"] <= 0)
    if p["ancoragem_auto"]:                                # automática: lb da NBR 6118 arredondado a 5 cm
        p["ancoragem"] = teto5(lb)
    elif p["ancoragem"] is None:
        erros.append("Preencha a ancoragem acima do arrasamento (ou marque a ancoragem automática).")
        return res
    # dobra do topo: com o prolongamento, as barras ficam retas no perfil (até o início da perfuração) e a dobra é feita
    # na ancoragem depois do arrasamento, só no detalhe; a barra tem de ter a ancoragem mais a dobra acima do arrasamento
    dobra_det = max(p["dobra"], 0.0)
    dobra = 0.0 if p["prolongar"] else dobra_det
    res["dobra_det"] = dobra_det
    if p["prolongar"] and dobra_det > 0:
        alertas.append(("info", f"Armação prolongada até o início da perfuração: barras retas no perfil; a dobra de {dobra_det:g} cm "
                                "é feita na ancoragem depois do arrasamento (detalhe da ancoragem)."))
    segs, y_top = [], max(p["ancoragem"] + (dobra_det if p["prolongar"] else 0.0), h_perd)
    while True:
        db = dobra if not segs else 0.0
        disp = p["comp_max"] - db
        if disp - l0 < 50:
            erros.append("Comprimento máximo da barra insuficiente para o transpasse.")
            return res
        if y_top + Larm <= disp + 1e-6:
            segs.append(dict(y_top=y_top, y_bot=-Larm, dobra=db))
            break
        segs.append(dict(y_top=y_top, y_bot=y_top - disp, dobra=db))
        y_top = y_top - disp + l0
        if len(segs) > 30:
            erros.append("Barras demais: revise o comprimento máximo.")
            return res

    esp_livre = 2 * math.pi * Rl / p["n_barras"] - fl
    As = p["n_barras"] * math.pi * fl ** 2 / 4
    res.update(segmentos=segs, esp_livre=esp_livre, As=As, taxa_geom=As / (math.pi * R * R) * 100)
    if esp_livre <= 0:
        erros.append(f"As {p['n_barras']} barras de {{{bt(p['bitola_long'])} não cabem na seção.")
        return res
    if p["n_barras"] > 1 and esp_livre < 10 and not raiz:      # na raiz (argamassa) o tubo condiciona a gaiola
        alertas.append(("aviso", f"Espaçamento livre entre barras {br(esp_livre, 1)} cm (< 10 cm, usual para concretagem submersa)."))
    if p["ancoragem"] < lb - 0.5:
        alertas.append(("aviso", f"Ancoragem acima do arrasamento ({p['ancoragem']:g} cm) menor que lb = {lb:.0f} cm (NBR 6118, boa aderência)."))
    if Larm > L - c and not raiz:                           # na raiz a armação vai até a ponta
        alertas.append(("aviso", "A armação termina a menos de um cobrimento da ponta da estaca."))
    nb = NBR6122[p["tipo_estaca"]]
    if p["n_barras"] < BARRAS_MIN or p["bitola_long"] < BITOLA_MIN - 1e-6:
        alertas.append(("aviso", f"Armadura longitudinal de {p['n_barras']} {{{bt(p['bitola_long'])}".replace("{", "ø")
                                 + f": o mínimo do escritório é {BARRAS_MIN} barras de ø{BITOLA_MIN:g} mm."))
    if res["taxa_geom"] < nb["taxa"] - 1e-6:
        alertas.append(("aviso", f"Armadura longitudinal de {br(res['taxa_geom'])} % da seção, abaixo do mínimo de "
                                 f"{br(nb['taxa'], 1)} % da NBR 6122 (Tabela 4)."))
    if nb["comp"] and Larm < L - 1e-6 and (Larm - dv + p["ancoragem"]) / 100 < nb["comp"] - 1e-6:
        alertas.append(("aviso", f"Armação de {br((Larm - dv + p['ancoragem']) / 100)} m com a ancoragem"
                                 + (" no bloco mais rebaixado" if dv else "") + ", abaixo do comprimento útil "
                                 f"mínimo de {br(nb['comp'], 1)} m da NBR 6122 (Tabela 4, incluindo a ligação com o bloco)."))
    if raiz and Larm < L - 1e-6:
        alertas.append(("aviso", "A NBR 6122 (Tabela 4) pede armadura integral na estaca raiz: a armação termina "
                                 f"{br((L - Larm) / 100)} m acima da ponta."))
    fmin = fck_minimo(p["tipo_estaca"], p["caa"])
    if p["fck"] < fmin - 1e-6:
        alertas.append(("aviso", f"fck de {p['fck']:g} MPa, abaixo do mínimo da NBR 6122 (Tabela 4) para estaca "
                                 f"{p['tipo_estaca']} em CAA {p['caa']}: " + (f"argamassa de {fmin:g} MPa." if raiz else f"C{fmin:g}.")))
    if raiz:                                     # nota c da Tabela 4: taxa máxima e espaço livre entre barras
        tmax = 8.0 if D <= 31 else (6.0 if D >= 40 else 8.0 - 2.0 * (D - 31) / 9)
        taxa_c = res["taxa_geom"] * (2 if len(segs) > 1 else 1)
        if taxa_c > tmax + 1e-6:
            alertas.append(("aviso", f"Taxa de armadura de {br(taxa_c)} %" + (" nas emendas" if len(segs) > 1 else "")
                                     + f", acima do máximo de {br(tmax, 1)} % da NBR 6122 (nota c da Tabela 4)."))
        livre = 2 * math.pi * Rl / (p["n_barras"] * (2 if len(segs) > 1 else 1)) - fl
        if p["n_barras"] > 1 and livre < max(fl, 2.0) - 1e-6:
            alertas.append(("aviso", f"Espaço livre entre barras de {br(livre, 1)} cm" + (" nas emendas" if len(segs) > 1 else "")
                                     + f", menor que {br(max(fl, 2.0), 1)} cm (NBR 6122, nota c da Tabela 4)."))
    if p["comp_max"] > 1200:
        alertas.append(("aviso", "Comprimento máximo acima de 12 m (barra comercial)."))
    if len(segs) > 1:
        alertas.append(("info", f"Barras longitudinais em {len(segs)} trechos, emenda por transpasse de {l0:g} cm"
                                 + (" (automático: lb para compressão)" if res["l0_auto"] else "") + "."))

    # --- estribos: trecho distribuído e zonas
    ys_top0, ys_bot = -p["dist_topo"], -Larm + p["dist_pe"]
    ys_top = ys_top0 + h_perd                              # 1º estribo: perto do início da perfuração, se prolongado
    if ys_top0 - ys_bot <= 0:
        erros.append("Distâncias do 1º e do último estribo maiores que a armação.")
        return res
    af = None
    if p["afunilar"]:
        # afunilamento: as barras convergem do eixo normal (Rl) no início do trecho até o estribo da ponta
        Laf, Dp, fp = p["afun_comp"] * 100, p["afun_diam"], p["afun_bitola"] / 10
        y_af, d_top = -Larm + Laf, D - 2 * c
        r_tip = Dp / 2 - fp - fl / 2                      # eixo das barras dentro do estribo da ponta
        if Laf <= p["dist_pe"] + 1 or y_af >= ys_top0 - 1:
            erros.append("O afunilamento deve ser maior que a distância do último estribo à base e menor que a armação.")
        if Dp >= d_top - 0.01:
            erros.append(f"O estribo da ponta (ø{Dp:g} cm) deve ser menor que o estribo normal (ø{d_top:g} cm, externo).")
        elif r_tip <= 0 or 2 * math.pi * r_tip / p["n_barras"] - fl < 0:
            erros.append(f"As {p['n_barras']} barras de {{{bt(p['bitola_long'])} não cabem no estribo da ponta de ø{Dp:g} cm.")
        if p["afun_quant"] < 1:
            erros.append("Quantidade de estribos da ponta deve ser pelo menos 1.")
        if erros:
            return res
        af = dict(Laf=Laf, y_af=y_af, Dp=Dp, d_top=d_top, r_tip=r_tip, fp=fp)
    y_lim = af["y_af"] if af else ys_bot                   # fim dos estribos normais
    Lr, Lr0 = ys_top - y_lim, ys_top0 - y_lim             # com e sem o trecho prolongado
    zonas = []
    if h_perd > 0:                                         # trecho a arrasar: espaçamento corrente
        zonas.append(dict(y_top=ys_top, y_bot=ys_top0, s=p["espac"], inicio=True))
    # trecho superior reduzido: do arrasamento do bloco mais alto até zona_sup abaixo do arrasamento do mais baixo
    z1 = min(p["zona_sup"] * 100 + dv, Lr0) if (p["zona_sup"] > 0 and p["espac_sup"] > 0) else 0.0
    if z1 > 0:
        zonas.append(dict(y_top=ys_top0, y_bot=ys_top0 - z1, s=p["espac_sup"], inicio=not zonas))
    if Lr0 - z1 > 1e-6:
        zonas.append(dict(y_top=ys_top0 - z1, y_bot=y_lim, s=p["espac"], inicio=not zonas))
    if h_perd > 0 and len(zonas) > 1 and zonas[1]["s"] == zonas[0]["s"]:   # mesmo espaçamento: uma faixa só
        zonas[0]["y_bot"] = zonas.pop(1)["y_bot"]
    for z in zonas:
        Lz = z["y_top"] - z["y_bot"]
        z["L"] = Lz
        z["nesp"] = max(1, math.ceil(Lz / z["s"] - 1e-6))
        z["n"] = z["nesp"] + (1 if z["inicio"] else 0)
        d = Lz / z["nesp"]
        z["ys"] = [z["y_top"] - j * d for j in range(0 if z["inicio"] else 1, z["nesp"] + 1)]
    if af:
        # estribos do afunilamento: mesmo espaçamento (ou passo) do último trecho; cada um abraça as barras na
        # sua altura (eixo das barras em reta de Rl, no início do afunilamento, a r_tip, no estribo da ponta).
        # Estribo helicoidal: continua em tronco de cone até o estribo da ponta (o único estribo à parte).
        s_f = zonas[-1]["s"] if zonas else p["espac"]
        Lf = af["y_af"] - ys_bot
        helic = p["estribo"] == "helicoidal"
        nf = 1 if helic else max(1, math.ceil(Lf / s_f - 1e-6))
        rb = lambda y: af["r_tip"] + (Rl - af["r_tip"]) * (y - ys_bot) / Lf
        af["rb"], af["r_base"] = rb, rb(-Larm)
        if helic:
            af["zona"] = dict(y_top=af["y_af"], y_bot=ys_bot, L=Lf, s=s_f, r_top=re, r_bot=rb(ys_bot) + fl / 2 + ft / 2)
        af["estribos"] = []
        for j in range(1, nf + 1):
            y, ponta = af["y_af"] - j * Lf / nf, j == nf
            fe = af["fp"] if ponta else ft
            af["estribos"].append(dict(y=y, ponta=ponta, dext=round(2 * (rb(y) + fl / 2 + fe), 1),
                                       bitola=p["afun_bitola"] if ponta else p["bitola_estr"],
                                       aco=p["afun_aco"] if ponta else p["aco_estr"],
                                       quant=p["afun_quant"] if ponta else 1))
    res.update(zonas=zonas, ys_top=ys_top, ys_top0=ys_top0, ys_bot=ys_bot, y_lim=y_lim, afun=af)

    posicoes, marca = [], 1
    chaves = {}
    for s in segs:
        main = s["y_top"] - s["y_bot"]
        if af and s["y_bot"] < af["y_af"] - 1e-6:       # trecho que converge no afunilamento: reto + inclinado
            r_y = lambda y: Rl if y >= af["y_af"] else af["rb"](y)
            ys_b = [s["y_top"]] + ([af["y_af"]] if s["y_bot"] < af["y_af"] < s["y_top"] else []) + [s["y_bot"]]
            main = sum(math.hypot(a - b, r_y(a) - r_y(b)) for a, b in zip(ys_b, ys_b[1:]))
            s["pontos"] = [(r_y(y) - r_y(s["y_top"]), y - s["y_top"]) for y in ys_b]   # x para dentro = negativo
        ch = (round(main, 1), s["dobra"])
        if ch not in chaves:
            chaves[ch] = marca
            marca += 1
            desc = DESCONTO_DOBRA.get(p["bitola_long"], 0.25 * p["bitola_long"] - 2) if s["dobra"] > 0 else 0
            posicoes.append(dict(mark=chaves[ch], papel="longitudinal", aco=p["aco_long"], bitola=p["bitola_long"],
                                 quant=0, comp=round(main + s["dobra"] - desc), obs=""))
        s["mark"] = chaves[ch]
        next(q for q in posicoes if q["mark"] == s["mark"])["quant"] += p["n_barras"]

    Dh = 2 * re
    if p["estribo"] == "circular":
        n = sum(z["n"] for z in zonas)
        comp = round(math.pi * Dh + EXTRA_ESTRIBO_CIRC.get(p["bitola_estr"], 7.1 * p["bitola_estr"]))
        res["estribo"] = dict(mark=marca, n=n, comp=comp)
        posicoes.append(dict(mark=marca, papel="estribo", aco=p["aco_estr"], bitola=p["bitola_estr"],
                             quant=n, comp=comp, obs=""))
        marca += 1
    else:
        voltas = sum(z["L"] / z["s"] for z in zonas)
        comp = sum(z["L"] / z["s"] * math.hypot(math.pi * Dh, z["s"]) for z in zonas)
        Dh_b = Dh
        if af:                                   # tronco de cone: comprimento da volta pelo diâmetro médio
            zf = af["zona"]
            v = zf["L"] / zf["s"]
            voltas += v
            comp += v * math.hypot(math.pi * (zf["r_top"] + zf["r_bot"]), zf["s"])
            Dh_b = 2 * zf["r_bot"]
        comp = math.ceil(comp + p["voltas_fecho"] * math.pi * (Dh + Dh_b))
        lap, Lmax = p["transpasse_espiral"], math.floor(p["comp_max"] + 1e-6)
        # peças: barras inteiras (comprimento máximo) e, se faltar, uma peça cortada para completar; assim não
        # sobram pedaços pequenos na obra. n inteiras + 1 cortada cobrem n.Lmax + resto - n.transpasse
        if comp <= Lmax:
            partes = [(1, comp)]
        else:
            if Lmax - lap < 100:
                erros.append("Comprimento máximo insuficiente para o transpasse do estribo helicoidal.")
                return res
            n = math.ceil((comp - Lmax) / (Lmax - lap) - 1e-9)
            resto = math.ceil(comp - n * (Lmax - lap) - 1e-9)
            partes = [(n + 1, Lmax)] if resto >= Lmax else [(n, Lmax), (1, resto)]
        k = sum(q for q, _ in partes)
        obs = f"ESTRIBO HELICOIDAL - TRANSPASSE {lap:g} cm" if k > 1 else "ESTRIBO HELICOIDAL"
        pecas = []
        for i, (q, Lp) in enumerate(partes):
            o = obs if i == 0 else "ESTRIBO HELICOIDAL - COMPLEMENTO"
            pecas.append(dict(mark=marca, quant=q, comp=Lp, obs=o, inteira=Lp >= Lmax))
            posicoes.append(dict(mark=marca, papel="espiral", aco=p["aco_estr"], bitola=p["bitola_estr"],
                                 quant=q, comp=Lp, obs=o))
            marca += 1
        res["espiral"] = dict(mark=pecas[0]["mark"], Dh=Dh, voltas=voltas, comp=comp, pecas=k, partes=pecas, obs=obs,
                              marcas=" E ".join(f"N{x['mark']}" for x in pecas))
        alertas.append(("info", f"Estribo helicoidal: {br(voltas, 1)} voltas + {p['voltas_fecho']:g} de fechamento em cada ponta, "
                                f"desenvolvido {br(comp / 100)} m = " + " + ".join(
                                    f"{x['quant']} barra(s) inteira(s) de {x['comp']} cm" if x["inteira"] else
                                    f"{x['quant']} peça cortada de {x['comp']} cm" for x in pecas) + "."))
    for e in (af["estribos"] if af else []):                # estribos variáveis e da ponta: uma posição cada
        b = e["bitola"]
        e["mark"], e["comp"] = marca, round(math.pi * (e["dext"] - b / 10) + EXTRA_ESTRIBO_CIRC.get(b, 7.1 * b))
        e["obs"] = p["afun_obs"] if e["ponta"] else ""
        posicoes.append(dict(mark=marca, papel="estribo_ponta" if e["ponta"] else "estribo_var", aco=e["aco"],
                             bitola=b, quant=e["quant"], comp=e["comp"], obs=e["obs"]))
        marca += 1
    if af and p["estribo"] == "helicoidal":
        alertas.append(("info", f"Afunilamento de {af['Laf']:.0f} cm: o estribo helicoidal acompanha as barras em tronco de cone "
                                f"(ø{br(2 * af['zona']['r_bot'] + ft, 1)} cm externo embaixo) até o estribo da ponta (ø{af['Dp']:g} cm)."))
    elif af:
        alertas.append(("info", f"Afunilamento de {af['Laf']:.0f} cm: {len(af['estribos']) - 1} estribo(s) variável(is) e o estribo "
                                f"da ponta (ø{af['Dp']:g} cm), cada um com a sua posição."))

    if p["aneis"]:
        fa = p["bitola_anel"] / 10
        r_anel = Rl - fl / 2 - fa / 2
        n = math.ceil(Lr / p["espac_anel"] - 1e-6) + 1 if p["espac_anel"] > 0 else 0
        if r_anel <= 0 or n < 1:
            erros.append("Anéis de enrijecimento não cabem (diâmetro ou espaçamento).")
            return res
        d = Lr / (n - 1) if n > 1 else 0
        ys_an = [ys_top - j * d for j in range(n)]
        if p["aneis_duplos"] and n > 1 and d > 10:          # um anel a mais em cada ponta, 5 cm para dentro
            ys_an = [ys_an[0], ys_an[0] - 5.0] + ys_an[1:-1] + [ys_an[-1] + 5.0, ys_an[-1]]
        # anel interno soldado: sem gancho (ferro genérico do TQS); comprimento pelo eixo + transpasse soldado,
        # como o TQS calcula (arredondado para baixo)
        # transpasse soldado: o informado ou 20ø arredondado a 5 cm; a NBR 6118 (9.5.4) pede dois cordões de 5ø
        # afastados de 5ø, ou seja, pelo menos 15ø de traspasse
        lap_an = p["transpasse_anel"] if p["transpasse_anel"] > 0 else teto5(20 * fa)
        if lap_an < 15 * fa - 1e-6:
            alertas.append(("aviso", f"Transpasse soldado do anel de {lap_an:g} cm, menor que 15ø ({15 * fa:g} cm): a NBR 6118 "
                                     f"(9.5.4) pede dois cordões de solda de 5ø afastados de 5ø."))
        comp = math.floor(2 * math.pi * r_anel + lap_an + 1e-6)
        res["aneis"] = dict(mark=marca, n=len(ys_an), n_faixa=n, r=r_anel, cover=c + ft + fl, comp=comp, ys=ys_an,
                            transpasse=lap_an)
        posicoes.append(dict(mark=marca, papel="anel", aco=p["aco_anel"], bitola=p["bitola_anel"],
                             quant=len(ys_an), comp=comp, obs=OBS_ANEL))
        marca += 1

    if p["espacadores"]:
        # roletes espaçadores: n por seção, seções distribuídas como os anéis (do 1º estribo ao fim do trecho reto;
        # no afunilamento a gaiola já se afasta da parede). O rolete é encaixado no estribo e o raio dele é o
        # cobrimento: diâmetro = 2 x cobrimento; na raiz, 50 mm (raio de 25 mm, os espaçadores do desenho do escritório)
        s_r = p["rolete_espac"]
        if p["rolete_n"] < 1 or s_r <= 0:
            erros.append("Roletes espaçadores: informe pelo menos 1 por seção e o espaçamento entre seções.")
            return res
        n_sec = math.ceil(Lr / s_r - 1e-6) + 1
        d_r = Lr / (n_sec - 1) if n_sec > 1 else 0
        mm = p["rolete_mm"] or (50.0 if raiz else round(2 * c * 10))
        res["roletes"] = dict(n=p["rolete_n"], secoes=n_sec, total=p["rolete_n"] * n_sec, mm=mm, espac=s_r,
                              ys=[ys_top - j * d_r for j in range(n_sec)])
        if p["rolete_n"] < 3:
            alertas.append(("aviso", f"{p['rolete_n']} rolete(s) por seção não centraliza(m) a gaiola: use pelo menos 3."))
        alertas.append(("info", f"Roletes espaçadores de {mm:g} mm: {p['rolete_n']} por seção em {n_sec} seções = "
                                f"{p['rolete_n'] * n_sec} por estaca."))

    vol = math.pi * R * R * L / 1e6
    vol_perd = math.pi * R * R * h_perd / 1e6              # concreto acima do arrasamento, demolido
    res.update(posicoes=posicoes, volume=vol, volume_perdido=vol_perd)
    A1 = math.pi * R * R / 1e6                              # m3 por cm de estaca
    ca, emb, y_bar = p["cota_arrasamento"], p["embutimento"], segs[0]["y_top"]
    if h_perd > 0:
        alertas.append(("info", f"Perfuração a partir da cota {cota(p['cota_perfuracao'])}: armação prolongada {h_perd:g} cm acima "
                                f"do arrasamento{' do bloco mais alto' if dv else ''}; concreto perdido no arrasamento "
                                f"{br(vol_perd, 3)} m3 por estaca" + (f" ({br(A1 * (h_perd + dv), 3)} no bloco mais baixo)" if dv else "") + "."))
    if dv > 0:
        alertas.append(("info", f"Blocos com fundo variável: arrasamento de {cota(ca - dv / 100)} a {cota(ca)}. Armação de "
                                f"{br(Larm / 100)} m abaixo do bloco mais alto ({br((Larm - dv) / 100)} m abaixo do mais baixo)"
                                + (f"; trecho superior de estribos de {z1:.0f} cm, até {p['zona_sup'] * 100:g} cm abaixo do "
                                   "arrasamento mais baixo" if z1 > 0 else "") + "."))
    # ancoragem no bloco: tem de caber na altura do bloco menos o cobrimento do topo
    if hb:
        livre = hb - emb - c                               # trecho das barras que cabe no bloco, acima do arrasamento
        if p["ancoragem"] > livre + 0.5:
            alertas.append(("aviso", f"A ancoragem de {p['ancoragem']:g} cm não cabe no bloco: com {hb:g} cm de altura, {emb:g} cm "
                                     f"de embutimento e {c:g} cm de cobrimento no topo, cabem {livre:g} cm."))
    # blocos onde a estaca é usada: com a cota de fundo de todos, os volumes das N estacas saem bloco a bloco
    blocos = []
    for b in p["blocos"]:
        bb = dict(b, arras=None, dif=None, L=None, perd=None)
        if b["fundo"] is not None:
            ca_i = round(b["fundo"] + emb / 100, 3)
            dif = round((ca - ca_i) * 100, 1)              # cm abaixo do arrasamento do detalhe
            bb.update(arras=ca_i, dif=dif, L=round((ca_i - p["cota_ponta"]) * 100, 1),
                      perd=round(h_perd + dif, 1) if h_perd > 0 else 0.0)
            if dif < -0.5 or dif > dv + 0.5:
                alertas.append(("aviso", f"Bloco {b['bloco']}: arrasamento na cota {cota(ca_i)} (fundo {cota(b['fundo'])} + "
                                         f"embutimento), " + (f"fora da faixa do detalhe ({cota(ca - dv / 100)} a {cota(ca)})." if dv else
                                                              f"diferente do arrasamento do detalhe ({cota(ca)}): marque o fundo variável.")))
        blocos.append(bb)
    com_cota = bool(blocos) and all(b["fundo"] is not None for b in blocos)
    N = p["quantidade"]
    if com_cota:
        vol_N = sum(b["estacas"] * A1 * b["L"] for b in blocos)
        perd_N = sum(b["estacas"] * A1 * b["perd"] for b in blocos)
    else:
        vol_N, perd_N = vol * N, vol_perd * N
    res.update(blocos=blocos, blocos_cota=com_cota, volume_N=vol_N, volume_perdido_N=perd_N)
    tab = tabela_estimada(res)
    kg = sum(t["quant"] * t["comp"] / 100 * massa_linear(t["bitola"]) for t in tab)
    res.update(kg=kg, taxa=kg / vol if vol else 0.0)
    alertas.append(("info", f"Taxa de armadura: {br(res['taxa_geom'])} % da seção, {kg / vol:.0f} kg/m3 de "
                            f"{'argamassa' if raiz else 'concreto'}."))
    if p["desenhar_sondagens"]:
        perfis = sondagens_desenhadas(p)
        if not perfis:
            alertas.append(("aviso", "Desenhar sondagens está ligado, mas nenhuma sondagem com leituras foi marcada para desenho."))
        for s in perfis:
            if es.cota_fim(s) > p["cota_arrasamento"] or es.cota_topo(s) < p["cota_ponta"]:
                alertas.append(("aviso", f"{es.TIPOS[s['tipo']].capitalize()} {s['nome']} (cotas {cota(es.cota_topo(s))} a "
                                         f"{cota(es.cota_fim(s))}) não alcança a estaca: confira o referencial das cotas."))
            elif es.cota_fim(s) > p["cota_ponta"] + 0.005:
                alertas.append(("aviso", f"{es.TIPOS[s['tipo']].capitalize()} {s['nome']} termina na cota "
                                         f"{cota(es.cota_fim(s))}, acima da ponta da estaca ({cota(p['cota_ponta'])})."))
            if s["tipo"] == "furo" and s["cota_boca"] < p["cota_arrasamento"] - 0.005:
                alertas.append(("aviso", f"{es.TIPOS[s['tipo']].capitalize()} {s['nome']} começa na cota "
                                         f"{cota(s['cota_boca'])}, abaixo do arrasamento: confira o referencial das cotas."))
    return res

def padroes_tipo(tipo, diametro, cobrimento=5.0, caa="II"):
    """Parâmetros iniciais de uma estaca do tipo: mínimos da NBR 6122 (Tabela 4) e padrões do escritório.
    Armadura: 0,4 % da seção com a menor bitola (de 10 mm em diante) que cumpre o mínimo com o número mínimo de
    barras: 6 em todos os tipos (regra do escritório; NBR 6118, 18.4.2.2, seções circulares), com eixos a no
    máximo 40 cm. Comprimento: o mínimo da tabela abaixo do arrasamento (raiz: até a ponta), mais a
    ancoragem lb no bloco. Estribo helicoidal, anéis soldados a cada 100 cm com dois nas pontas e, só na hélice
    contínua, afunilamento da ponta."""
    t = normalizar({"tipo_estaca": tipo})["tipo_estaca"]
    nb, D, raiz = NBR6122[t], float(diametro), t == "raiz"
    fck = fck_minimo(t, normalizar({"caa": caa})["caa"])            # concreto mínimo da Tabela 4 pela CAA
    out = dict(tipo_estaca=t, fck=fck, estribo="helicoidal", espac=20.0, aneis=True, espac_anel=100.0,
               aneis_duplos=True, afunilar=t == "hélice contínua", comp_armacao=nb["comp"],
               espacadores=True, rolete_n=4, rolete_espac=100.0, rolete_mm=50.0 if raiz else None)
    if raiz:
        tab = RAIZ_ESTRIBO.get(round(D)) if abs(D - round(D)) < 1e-6 else None
        b_est = tab[0] if tab and tab[0] else 5.0
        c = (D - tab[1]) / 2 if tab else cobrimento
        out.update(zona_sup=0.0, diam_estribo=None)
    else:
        b_est, c = 6.3, cobrimento
    area = lambda b: math.pi * (b / 10) ** 2 / 4
    As_min = nb["taxa"] / 100 * math.pi * D * D / 4
    n_base = max(BARRAS_MIN, math.ceil(2 * math.pi * max(D / 2 - c - b_est / 10 - 0.5, 1.0) / 40 - 1e-9))
    for b in (10.0, 12.5, 16.0, 20.0, 25.0, 32.0):
        if n_base * area(b) >= As_min - 1e-9:
            n = n_base
            break
    else:
        n = math.ceil(As_min / area(b) - 1e-9)
    if not raiz and b >= 32:
        b_est = 8.0                              # estribo de pelo menos 1/4 da bitola longitudinal
    out.update(n_barras=n, bitola_long=b, bitola_estr=b_est, ancoragem=teto5(comprimento_ancoragem(fck, b)), ancoragem_auto=True,
               bitola_anel=min(max(b, 10.0), 12.5), transpasse_anel=0.0)
    if out["afunilar"]:                          # estribo da ponta: 60 % da gaiola, com as barras cabendo nele
        Dc = D - 2 * c
        Dp = max(15.0, 5 * math.ceil(0.6 * Dc / 5 - 1e-9))
        Dp_min = 2 * (n * (b / 10 + 2) / (2 * math.pi) + b / 20 + out["bitola_anel"] / 10)
        Dp = max(Dp, 5 * math.ceil(Dp_min / 5 - 1e-9))
        if Dp < Dc - 2:
            out.update(afun_diam=Dp, afun_comp=1.0, afun_bitola=out["bitola_anel"], afun_quant=2)   # mesma bitola do superior
        else:
            out["afunilar"] = False
    return out

def sondagens_desenhadas(p):
    return [s for s in p["sondagens"] if s["desenhar"] and s["leituras"]] if p["desenhar_sondagens"] else []

def tabela_estimada(res):
    return [dict(mark=q["mark"], aco=q["aco"], bitola=q["bitola"], quant=q["quant"], comp=q["comp"], obs=q["obs"])
            for q in res["posicoes"]]

def resumo_aco(tabela):
    """{(aço, bitola): comprimento total em m} de uma estaca."""
    r = {}
    for t in tabela:
        ch = (t["aco"], t["bitola"])
        r[ch] = r.get(ch, 0.0) + t["quant"] * t["comp"] / 100
    return dict(sorted(r.items()))


# --------------------------------------------------------------------------- modelo de desenho
class Modelo:
    """Primitivas de desenho (cm reais) + especificação dos ferros inteligentes."""

    def __init__(self, escala):
        self.E = escala
        self.prims, self.ferros = [], []
        self.caixa = [math.inf, math.inf, -math.inf, -math.inf]

    def P(self, v):
        return v * self.E

    def _cx(self, *pts):
        for x, y in pts:
            c = self.caixa
            c[0], c[1], c[2], c[3] = min(c[0], x), min(c[1], y), max(c[2], x), max(c[3], y)

    def linha(self, x1, y1, x2, y2, nv=NV_CONTORNO, estilo=-1):
        self.prims.append(dict(t="linha", nv=nv, estilo=estilo, p=(x1, y1, x2, y2)))
        self._cx((x1, y1), (x2, y2))

    def poli(self, xy, nv=NV_CONTORNO, cheio=False, estilo=-1):
        self.prims.append(dict(t="poli", nv=nv, estilo=estilo, xy=[tuple(v) for v in xy], cheio=cheio))
        self._cx(*xy)

    def circulo(self, x, y, r, nv=NV_CONTORNO, estilo=-1):
        self.prims.append(dict(t="circ", nv=nv, estilo=estilo, x=x, y=y, r=r))
        self._cx((x - r, y - r), (x + r, y + r))

    def texto(self, x, y, s, h, nv=NV_TEXTO, ang=0.0, alin="esq"):
        """Fonte do TQS: cada caractere ocupa uma caixa de largura h."""
        w = len(s) * h
        dx = {"esq": 0.0, "centro": -w / 2, "dir": -w}[alin]
        a = math.radians(ang)
        x, y = x + dx * math.cos(a), y + dx * math.sin(a)
        self.prims.append(dict(t="texto", nv=nv, x=x, y=y, h=h, ang=ang, s=s))
        self._cx((x, y), (x + w * math.cos(a) - h * math.sin(a), y + w * math.sin(a) + h * math.cos(a)))

    def cota(self, x1, y1, x2, y2, pos, vertical=True, txt=None, fator=1.0):
        """Cotagem vertical (linha em x = pos) ou horizontal (linha em y = pos)."""
        self.prims.append(dict(t="cota", nv=NV_COTA, vert=vertical, p=(x1, y1, x2, y2), pos=pos,
                               txt=txt, fator=fator))
        h = self.P(H_TXT)
        self._cx(*(((pos - 2 * h, y1), (pos + h, y2)) if vertical else ((x1, pos - h), (x2, pos + 2 * h))))

    def fercor(self, x, y, esc):
        self.prims.append(dict(t="fercor", nv=NV_FERCOR, x=x, y=y, esc=esc))
        self._cx((x - esc / 2, y - esc / 2), (x + esc / 2, y + esc / 2))

    def marca(self, f, xt, yt, pts, nfr=1, pos=1, bit=1, esp=0):
        """Identificação de posição (texto + linha de chamada) associada ao ferro f."""
        f["marcas"].append(dict(xt=xt, yt=yt, pts=pts, nfr=nfr, pos=pos, bit=bit, esp=esp))
        self._cx((xt, yt), (xt + self.P(H_TXT) * 14, yt + self.P(H_TXT)))

    def onda(self, x1, x2, y, amp):
        n = 16
        self.poli([(x1 + (x2 - x1) * i / n, y + amp * math.sin(2 * math.pi * i / n)) for i in range(n + 1)])


def notas_tipo(p):
    """Notas do tipo de estaca (notas do escritório, 13/10/2026): concreto ou argamassa pela classe de agressividade
    (NBR 6122, Tabela 4 e anexos N e I) e o anexo da NBR 6122 a seguir."""
    t, caa, fck = p["tipo_estaca"], p["caa"], p["fck"]
    fmin = fck_minimo(t, caa)
    if t == "raiz":
        n1 = (f"CLASSE DE AGRESSIVIDADE AMBIENTAL {caa}: ARGAMASSA COM fak {fck:g} MPa; S100; 600 kg/m3 DE CIMENTO; "
              "0,50 <= a/c <= 0,60.")
    else:
        cl = 40.0 if (fck >= 40.0 - 1e-6 or caa in ("III", "IV")) else CONCRETO_6122[t]["classe"][0]
        e = ESPEC_6122[(t, cl)]
        n1 = (f"CLASSE DE AGRESSIVIDADE AMBIENTAL {caa}: CONCRETO C{fck:g}" + (f" (MÍNIMO C{fmin:g})" if fck > fmin + 1e-6 else "")
              + f", ABATIMENTO ENTRE {e['s'][0]} mm E {e['s'][1]} mm ({e['s'][2]}), DIÂMETRO DO AGREGADO DE {e['agr'][0]} mm "
              f"A {e['agr'][1]} mm, TEOR DE EXSUDAÇÃO INFERIOR A 4 %, CONSUMO MÍNIMO DE CIMENTO DE {e['cim']} kg/m3 E "
              f"FATOR a/c <= {e['ac']}.")
    return [n1, f"ESTACA {TIPOS_ESTACA[t]}: SEGUIR TODAS AS PRESCRIÇÕES DA ABNT NBR 6122 E SEU ANEXO {CONCRETO_6122[t]['anexo']}."]


def notas_gerais(p):
    """Notas gerais das estacas (notas do escritório, 13/10/2026)."""
    return [f"EXCENTRICIDADE LIMITE DE EXECUÇÃO (ABNT NBR 6122, 8.5.6.1): {br(0.1 * p['diametro'], 1)} cm. EXCENTRICIDADES "
            "SUPERIORES A ESTE LIMITE DEVEM SER INFORMADAS AO PROJETISTA.",
            "RECOMENDA-SE QUE AS ESTACAS SEJAM EXECUTADAS, PREFERENCIALMENTE, COM EXCEDENTE MÍNIMO DE 30 cm ACIMA DA COTA DE "
            "ARRASAMENTO INDICADA EM PROJETO. O MATERIAL EXCEDENTE DEVERÁ SER REMOVIDO, GARANTINDO-SE QUE A CABEÇA DA ESTACA "
            "APRESENTE CONCRETO OU ARGAMASSA ÍNTEGROS, SEM SEGREGAÇÕES OU CONTAMINAÇÕES, EM CONFORMIDADE COM A ABNT NBR 6122:2022.",
            "NÃO EXECUTAR ESTACAS COM ESPAÇAMENTO INFERIOR A CINCO DIÂMETROS EM INTERVALO INFERIOR A 12 h."]


def _detalhe_ancoragem(m, p, res, x0, y0):
    """Detalhe da ancoragem das estacas no bloco, depois do arrasamento (pedidos de 09/10/2026): bloco esquemático sobre
    duas estacas, com o arranque do pilar entre elas (como no detalhe do escritório), cava com talude e solo, lastro e,
    em cada estaca, as barras só com o comprimento da ancoragem e a dobra, se houver (com o prolongamento, a dobra só
    aparece aqui; o perfil fica reto); sem estribos dentro do bloco. Ancoragem cotada e marcas de nível à direita, com
    a cota de ancoragem mínima. Valores do bloco mais alto. Canto superior esquerdo em (x0, y0); retorna o y da base."""
    P, E = m.P, p["escala"]
    R, Rl, re = res["R"], res["Rl"], res["r_estr"]
    D, c, ca = p["diametro"], p["cobrimento"], p["cota_arrasamento"]
    emb, las, anc = p["embutimento"], p["lastro"], p["ancoragem"]
    hb, dv, h_perd = res["h_bloco"], res["dv"], res["h_perd"]
    dob, zona = res["dobra_det"], (1 if p["dobra_sentido"] == "fora" else -1)
    seg0 = res["segmentos"][0]
    # eixo das estacas: espaçamento de 2,5 D (esquemático), afastado o bastante para a dobra para fora não chegar ao
    # arranque do pilar; a face do bloco fica além da dobra externa, com folga
    d_fora = dob if zona > 0 else 0.0
    xp = max(1.25 * D, Rl + d_fora + 28.0)
    bw = xp + max(R + max(15.0, 0.5 * D), Rl + d_fora + 10.0)   # meia largura do bloco (esquemática)
    y_fb, y_lb = -emb, -emb - las
    y_tb = hb - emb if hb else anc + 25.0                # sem a altura, topo esquemático
    if h_perd > 0:
        y_ter, nome_ter = h_perd, "INÍCIO DA PERFURAÇÃO"
    elif p["cota_terreno"] is not None and (p["cota_terreno"] - ca) * 100 > y_lb + 10:
        y_ter, nome_ter = (p["cota_terreno"] - ca) * 100, "TERRENO"
    else:
        y_ter, nome_ter = None, ""
    y_sup = y_ter if y_ter is not None else y_tb + 15.0  # superfície do terreno desenhada
    xe = bw + 50.0                                       # pé do talude: folga de 50 cm para a fôrma
    xt = xe + max(y_sup - y_lb, 20.0) / 3                # crista (talude 3:1)
    xg = xt + 20.0                                       # fim da linha do terreno
    y_est = y_lb - max(40.0, 0.8 * D)                    # estacas interrompidas abaixo do lastro
    y_pil = y_tb + 45.0                                  # arranque do pilar acima do bloco
    y_max = max(y_sup, y_pil)
    # escala: a menor da lista em que o desenho cabe em 22 x 12 cm de papel
    esc = next((e for e in (20, 25, 50) if 2 * xg / e <= 22.0 and (y_max - y_est) / e <= 12.0), 75)
    k = E / esc
    cx, cy = x0 + xg * k, y0 - (y_max + 5) * k
    X, Y = (lambda x: cx + x * k), (lambda y: cy + y * k)
    estacas = (-xp, xp)

    def L_(x1, y1, x2, y2, nv=NV_CONTORNO, est=-1):
        m.linha(X(x1), Y(y1), X(x2), Y(y2), nv, estilo=est)

    def fora_das_estacas(a, b):                          # trechos de [a, b] fora das estacas
        cortes = [a] + [v for xc in estacas for v in (xc - R, xc + R)] + [b]
        return [(u, w) for u, w in zip(cortes[::2], cortes[1::2]) if w - u > 1e-6]

    # terreno e cava, com a hachura do lado do solo (à direita do percurso da esquerda para a direita)
    cava = [(-xg, y_sup), (-xt, y_sup), (-xe, y_lb), (xe, y_lb), (xt, y_sup), (xg, y_sup)]
    m.poli([(X(x), Y(y)) for x, y in cava])
    s_h, l_h = P(0.2), P(0.13)
    for (xa, ya), (xb, yb) in zip(cava, cava[1:]):
        ax, ay, bx, by = X(xa), Y(ya), X(xb), Y(yb)
        dl = math.hypot(bx - ax, by - ay)
        ux, uy = (bx - ax) / dl, (by - ay) / dl
        nx, ny = uy, -ux
        for j in range(int(dl / s_h)):
            px, py = ax + ux * (j + 0.5) * s_h, ay + uy * (j + 0.5) * s_h
            if abs(py - Y(y_lb)) < 1e-6 and any(X(xc - R) - P(0.05) < px < X(xc + R) + P(0.05) for xc in estacas):
                continue                                  # as estacas atravessam o fundo
            m.linha(px, py, px + (nx - ux) * l_h / math.sqrt(2), py + (ny - uy) * l_h / math.sqrt(2), NV_SOLO)
    # lastro (as estacas o atravessam) e bloco (com a altura informada, contorno real; sem ela, tracejado)
    if las > 0:
        for u, w in fora_das_estacas(-xe, xe):
            m.poli([(X(u), Y(y_lb)), (X(w), Y(y_lb)), (X(w), Y(y_fb)), (X(u), Y(y_fb)), (X(u), Y(y_lb))], NV_BLOCO)
    est_b = -1 if hb else 1
    for u, w in fora_das_estacas(-bw, bw):
        L_(u, y_fb, w, y_fb, NV_BLOCO)
    for s in (-1, 1):
        L_(s * bw, y_fb, s * bw, y_tb, NV_BLOCO, est_b)
    L_(-bw, y_tb, bw, y_tb, NV_BLOCO, est_b)
    # armadura do bloco (gaiola esquemática, nível 207): barras inferiores em U sobre as cabeças das estacas, barras
    # superiores com pernas, costelas e estribos verticais a cada ~20 cm; a real fica no projeto do bloco
    xa_, y_i, y_s = bw - c, 5.0, y_tb - c
    if y_s - y_i > 20:
        m.poli([(X(-xa_), Y(y_s - 10)), (X(-xa_), Y(y_i)), (X(xa_), Y(y_i)), (X(xa_), Y(y_s - 10))], NV_ARM_BLOCO)
        m.poli([(X(-xa_ + 2), Y(y_s - 15)), (X(-xa_ + 2), Y(y_s)), (X(xa_ - 2), Y(y_s)), (X(xa_ - 2), Y(y_s - 15))],
               NV_ARM_BLOCO)
        n_c = max(1, int((y_s - y_i) // 20))
        for j in range(1, n_c):
            y = y_i + j * (y_s - y_i) / n_c
            L_(-xa_ + 2, y, xa_ - 2, y, NV_ARM_BLOCO)
        n_e = max(2, round(2 * xa_ / 20))
        for j in range(n_e + 1):
            x = -xa_ + 4 + j * (2 * xa_ - 8) / n_e
            L_(x, y_i, x, y_s, NV_ARM_BLOCO)
    # estacas embutidas no bloco, interrompidas embaixo; barras só com a ancoragem (e a dobra); estribos e anéis
    # só fora do bloco
    helic = p["estribo"] == "helicoidal"
    for xc in estacas:
        for s in (-1, 1):
            L_(xc + s * R, y_est, xc + s * R, 0.0)
        L_(xc - R, 0.0, xc + R, 0.0)
        m.onda(X(xc - R), X(xc + R), Y(y_est), min(P(0.06), R * k / 4))
        for s in (-1, 1):
            L_(xc + s * Rl, y_est, xc + s * Rl, anc, NV_FERRO_DET)
            if dob > 0:
                L_(xc + s * Rl, anc, xc + s * (Rl + zona * dob), anc, NV_FERRO_DET)
        for z in res["zonas"]:
            for y in z["ys"]:
                if y_est + 2 < y < y_fb - 1:
                    L_(xc - re, y, xc + re, y - (z["s"] / 2 if helic else 0.0), NV_FERRO_DET)
        for y in (res["aneis"]["ys"] if p["aneis"] else []):
            if y_est + 2 < y < y_fb - 1:
                L_(xc - res["aneis"]["r"], y, xc + res["aneis"]["r"], y, NV_FERRO_DET, 1)
    # arranque do pilar entre as estacas (esquemático, tracejado: ver o projeto estrutural)
    a_p = min(12.0, xp - R - 8.0)
    pe = max(0.0, min(20.0, xp - R - a_p - 3.0))
    y_pb = y_fb + c + 5.0
    for s in (-1, 1):
        L_(s * a_p, y_pb, s * a_p, y_pil, NV_FERRO_INT, 1)
        if pe > 0:
            L_(s * a_p, y_pb, s * (a_p + pe), y_pb, NV_FERRO_INT, 1)
    h = P(H_TXT)
    x_ap = X(-a_p) - P(0.6)
    m.texto(x_ap, Y(y_pil) + P(0.05), "ARRANQUE DO PILAR", h, alin="dir")
    m.texto(x_ap, Y(y_pil) - P(0.3), "(VER O PROJETO ESTRUTURAL)", h, alin="dir")
    m.linha(x_ap + P(0.05), Y(y_pil) + P(0.1), X(-a_p), Y(y_pil - 10), NV_CHAMADA)
    if y_s - y_i > 20:                                   # chamada da armadura do bloco, à direita do pilar
        # o texto começa à direita do ponto tocado: a chamada desce para a esquerda sem cortar o texto
        x_alvo = X((a_p + xa_) / 2)
        x_ab = x_alvo + P(0.8)
        m.texto(x_ab, Y(y_pil) + P(0.05), "ARMADURA DO BLOCO", h)
        m.texto(x_ab, Y(y_pil) - P(0.3), "(VER O PROJETO ESTRUTURAL)", h)
        m.linha(x_ab - P(0.1), Y(y_pil) + P(0.1), x_alvo, Y(y_s), NV_CHAMADA)
    # cotas: ancoragem (no eixo da estaca da direita) e dobra, lastro e embutimento, folga e altura do bloco
    m.cota(X(xp), Y(0.0), X(xp), Y(anc), X(xp), fator=1 / k)
    if dob > 0:
        x_b = xp + Rl
        m.cota(X(x_b), Y(anc), X(x_b + zona * dob), Y(anc), Y(anc) + P(0.35), vertical=False, fator=1 / k)
    if las > 0:                                          # lastro e embutimento em linhas separadas (trechos curtos)
        m.cota(X(-xp - R), Y(y_lb), X(-xp - R), Y(y_fb), X(-bw - 10), fator=1 / k)
    m.cota(X(-xp - R), Y(y_fb), X(-xp - R), Y(0.0), X(-bw - 10) - P(0.45), fator=1 / k)
    m.cota(X(-xe), Y(y_lb), X(-bw), Y(y_fb), Y(y_fb) + P(1.0), vertical=False, txt=">=50", fator=1 / k)
    if hb:
        m.cota(X(bw), Y(y_fb), X(bw), Y(y_tb), X(bw + 20), fator=1 / k)
    # marcas de nível à direita, com chamadas no nível suave
    x_anc = xp + Rl + (dob if zona > 0 else 0.0)
    niv = ([(y_ter, nome_ter, X(xg))] if y_ter is not None else []) + ([(y_tb, "TOPO DO BLOCO", X(bw))] if hb else [])
    niv += [(anc, "ANCORAGEM MÍNIMA", X(x_anc)), (0.0, "ARRASAMENTO", X(xp + R)), (y_fb, "FUNDO DO BLOCO", X(bw))]
    niv.sort(key=lambda v: -v[0])
    ytx, xm, a = math.inf, X(xg) + P(0.6), P(0.1)
    for y, nome, x_ini in niv:
        yy = Y(y)
        ytx = min(yy + P(0.08), ytx - P(0.4))
        m.linha(x_ini + P(FOLGA), yy, xm + P(0.25), yy, NV_CHAMADA)
        m.poli([(xm, yy), (xm - a, yy + 1.6 * a), (xm + a, yy + 1.6 * a), (xm, yy)], NV_COTA, cheio=True)
        if abs(ytx - yy - P(0.08)) > 1e-6:
            m.linha(xm + P(0.25), yy, xm + P(0.4), ytx + h / 2, NV_CHAMADA)
        m.texto(xm + P(0.45), ytx, f"{cota(ca + y / 100)} {nome}", h)
    # rótulos
    m.texto(X(-bw) + P(0.15), Y(y_tb) - P(0.4), "BLOCO", h)
    yl = Y(y_lb) - P(0.9)
    m.texto(X(xp + R) + P(0.5), yl, "LASTRO DE CONCRETO MAGRO", h)
    m.linha(X((xp + R + xe) / 2), Y((y_lb + y_fb) / 2), X(xp + R) + P(0.45), yl + h / 2, NV_CHAMADA)
    m.texto(X(-xp - R) - P(0.5), Y(y_est) + P(0.25), f"ESTACA {{{D:g}", h, alin="dir")
    m.linha(X(-xp - R), Y(y_est) + P(0.55), X(-xp - R) - P(0.45), Y(y_est) + P(0.25) + h / 2, NV_CHAMADA)
    # título e informações
    xc0 = X(0.0)
    yt = Y(y_est) - P(1.0)
    m.texto(xc0, yt, "DETALHE DA ANCORAGEM NO BLOCO", P(H_SUB), NV_CORTE, alin="centro")
    m.texto(xc0, yt - P(0.45), f"ESC. 1:{esc:g}", P(H_TXT), NV_ESCALA, alin="centro")
    info = [f"ANCORAGEM DAS BARRAS N{seg0['mark']} NO BLOCO: {anc:g} cm ACIMA DO ARRASAMENTO (lb = {res['lb']:.0f} cm)",
            f"COTA DE ANCORAGEM MÍNIMA: {cota(ca + anc / 100)}"
            + (" NO BLOCO MAIS ALTO (NOS DEMAIS, NA TABELA DOS BLOCOS)" if dv else "")]
    if dob > 0:
        info.append(f"DOBRA DE {dob:g} cm NO TOPO DAS BARRAS, PARA {'FORA' if zona > 0 else 'DENTRO'} DA ESTACA")
    if h_perd > 0:
        info.append(f"BARRAS PROLONGADAS ATÉ A COTA {cota(ca + seg0['y_top'] / 100)}: DEPOIS DO ARRASAMENTO, CORTAR "
                    f"{anc + dob:g} cm ACIMA DELE" + (" E DOBRAR NA ANCORAGEM" if dob > 0 else ""))
    if hb:
        info.append(f"BLOCO{' MAIS ALTO' if dv else ''}: FUNDO {cota(ca - emb / 100)}, ALTURA {hb:g} cm, TOPO {cota(ca + y_tb / 100)}")
    info.append("BLOCO, ESTACAS E PILAR ESQUEMÁTICOS: DIMENSÕES E POSIÇÕES CONFORME O PROJETO DO BLOCO")
    info.append(f"EMBUTIMENTO DAS ESTACAS NO BLOCO: {emb:g} cm; LASTRO DE CONCRETO MAGRO: {las:g} cm")
    yt -= P(1.1)
    x_i = X(-xg)
    for s_ in info:
        for j, lin in enumerate(textwrap.wrap(s_, 70)):
            m.texto(x_i, yt, ("" if j == 0 else "   ") + lin, h)
            yt -= P(0.38)
    return yt

def _y_min_faixa(m, xa, xb, ignorar=()):
    """Menor y do que já está desenhado com alguma parte entre xa e xb (primitivas, inserções e marcas de ferro)."""
    h_ = m.P(H_TXT)
    ymin = math.inf

    def ver(x0, x1, y):
        nonlocal ymin
        if max(x0, x1) >= xa and min(x0, x1) <= xb:
            ymin = min(ymin, y)

    for pr in m.prims:
        t = pr["t"]
        if t == "linha":
            x1, y1, x2, y2 = pr["p"]
            ver(x1, x2, min(y1, y2))
        elif t == "poli":
            xs_, ys_ = [v[0] for v in pr["xy"]], [v[1] for v in pr["xy"]]
            ver(min(xs_), max(xs_), min(ys_))
        elif t in ("circ", "arco"):
            ver(pr["x"] - pr["r"], pr["x"] + pr["r"], pr["y"] - pr["r"])
        elif t == "texto":
            w = len(pr["s"]) * pr["h"]
            if abs(pr.get("ang", 0.0)) > 45:
                ver(pr["x"] - pr["h"], pr["x"], pr["y"])
            else:
                ver(pr["x"], pr["x"] + w, pr["y"])
        elif t == "cota":
            x1, y1, x2, y2 = pr["p"]
            if pr["vert"]:
                ver(min(x1, x2, pr["pos"]) - 2 * h_, max(x1, x2, pr["pos"]) + h_, min(y1, y2))
            else:
                ver(min(x1, x2), max(x1, x2), min(y1, y2, pr["pos"] - h_))
        elif t == "fercor":
            ver(pr["x"] - pr["esc"] / 2, pr["x"] + pr["esc"] / 2, pr["y"] - pr["esc"] / 2)
        elif t == "quant":
            ver(pr["x"], pr["x"] + m.P(QUANT_LARG), pr["y"] - m.P(QUANT_ALT))
    for f in m.ferros:
        if f in ignorar:
            continue
        for i in f["ins"]:
            ver(i["x"] - h_, i["x"] + h_, i["y"])
        for mk in f["marcas"]:
            ver(mk["xt"], mk["xt"] + 14 * h_, mk["yt"])
            for x, y in mk["pts"]:
                ver(x, x, y)
    return ymin

def _descricao(f):
    s = f"{f['quant']} N{f['mark']} {{{bt(f['bitola'])}"
    if f["espac"]:
        s += f" C/{f['espac']:g}"
    return s + f" C={f['comp']:.0f}" + (f" {f['comment']}" if f["comment"] else "")

def _tabela(m, x, y, titulo, cab, linhas, h):
    """Tabela com o canto superior esquerdo em (x, y). Retorna (largura, y da base)."""
    larg = [(max(len(str(l[j])) for l in [cab] + linhas) + 2) * h for j in range(len(cab))]
    falta = (len(titulo) + 2) * h - sum(larg)
    if falta > 0:
        larg[-1] += falta
    W, rh = sum(larg), 2.0 * h
    n = len(linhas) + 2
    yb = y - n * rh
    xs = [x]
    for w in larg:
        xs.append(xs[-1] + w)
    for i in range(n + 1):
        m.linha(x, y - i * rh, x + W, y - i * rh, NV_TABELA)
    m.linha(x, y, x, yb, NV_TABELA)
    m.linha(x + W, y, x + W, yb, NV_TABELA)
    for xc in xs[1:-1]:
        m.linha(xc, y - rh, xc, yb, NV_TABELA)
    m.texto(x + W / 2, y - 1.5 * h, titulo, h, alin="centro")
    for i, lin in enumerate([cab] + linhas):
        for j, v in enumerate(lin):
            m.texto((xs[j] + xs[j + 1]) / 2, y - (i + 1) * rh - 1.5 * h, str(v), h, alin="centro")
    return W, yb

def montar_modelo(par, res, tabela=None):
    """Monta o desenho. tabela: posições lidas do TQS (None = estimativa)."""
    p = res["p"]
    E = p["escala"]
    k = E / p["escala_secao"]
    m = Modelo(E)
    P = m.P
    D, R, c = p["diametro"], res["R"], p["cobrimento"]
    fl, ft = p["bitola_long"] / 10, p["bitola_estr"] / 10
    L, Larm, Rl, re = res["L"], res["Larm"], res["Rl"], res["r_estr"]
    segs, zonas, af = res["segmentos"], res["zonas"], res["afun"]
    tabela = tabela or tabela_estimada(res)
    pos_comp = {t["mark"]: t["comp"] for t in tabela}
    helic = p["estribo"] == "helicoidal"
    ca = p["cota_arrasamento"]
    y_bar = segs[0]["y_top"]
    emb = p["embutimento"]
    dv, hb = res["dv"], res["h_bloco"]
    det_anc = p["detalhe_ancoragem"] and emb > 0       # detalhe da ancoragem no bloco, em separado
    W = R + P(1.8)                                     # meia largura do bloco desenhado

    # ---------------------------------------------------------------- elevação
    marg = max(100.0, P(2.0))
    yq_sup, yq_inf = -Larm - marg, -L + marg
    perfis_sond = sondagens_desenhadas(p)
    # com sondagens, a elevação fica inteira: o perfil do solo ao longo do fuste não pode ser interrompido
    quebra = p["interromper"] and not perfis_sond and (yq_sup - yq_inf) > P(4.0)
    G = P(1.0)

    def yd(y):
        return y if (not quebra or y >= yq_sup) else y - yq_inf + yq_sup - G

    m.linha(-R, 0, R, 0)
    for s in (-1, 1):
        if quebra:
            m.linha(s * R, 0, s * R, yq_sup)
            m.linha(s * R, yd(yq_inf), s * R, yd(-L))
        else:
            m.linha(s * R, 0, s * R, -L)
    m.linha(-R, yd(-L), R, yd(-L))
    if quebra:
        amp = min(P(0.12), D / 6)
        m.onda(-R, R, yq_sup, amp)
        m.onda(-R, R, yd(yq_inf), amp)
        m.linha(0, y_bar + P(0.5), 0, yq_sup, NV_EIXO)
        m.linha(0, yd(yq_inf), 0, yd(-L) - P(0.5), NV_EIXO)
    else:
        m.linha(0, y_bar + P(0.5), 0, -L - P(0.5), NV_EIXO)

    y_topo = y_bar + P(0.8)
    h_perd = res["h_perd"]
    # bloco: com a altura informada, contorno real até o topo; sem ela, esquemático em volta da ancoragem
    y_blk = hb - emb if hb else min(y_bar, max(p["ancoragem"], emb)) + P(0.8)
    if h_perd > 0:                 # concreto a arrasar: do arrasamento ao início da perfuração (tracejado)
        for s in (-1, 1):
            m.linha(s * R, 0, s * R, h_perd, estilo=1)
        m.linha(-R, h_perd, R, h_perd, estilo=1)
        h_ = P(H_TXT)                  # rótulo à esquerda, acima do bloco, com chamada até a face do trecho
        y_r = max(h_perd, y_blk) + P(0.2)
        x_r = -R - P(0.25)
        m.texto(x_r, y_r + P(0.35), "CONCRETO", h_, alin="dir")
        m.texto(x_r, y_r, "A ARRASAR", h_, alin="dir")
        m.linha(x_r + P(0.05), y_r + P(0.1), -R, h_perd / 2, NV_COTA)
    if emb > 0:
        yfb = -emb
        for s in (-1, 1):
            m.linha(s * R, yfb, s * W, yfb, NV_BLOCO)
            m.linha(s * W, yfb, s * W, y_blk, NV_BLOCO, estilo=-1 if hb else 1)
            if p["lastro"] > 0:
                m.poli([(s * R, yfb), (s * W, yfb), (s * W, yfb - p["lastro"]), (s * R, yfb - p["lastro"]), (s * R, yfb)], NV_BLOCO)
            if dv > 0:                                 # fundo do bloco mais rebaixado (tracejado)
                m.linha(s * R, yfb - dv, s * W, yfb - dv, NV_BLOCO, estilo=1)
                if dv > p["lastro"]:
                    m.linha(s * W, yfb - p["lastro"], s * W, yfb - dv, NV_BLOCO, estilo=1)
        if hb:
            m.linha(-W, y_blk, W, y_blk, NV_BLOCO)
        m.texto(-W + P(0.25), y_blk - P(0.5), "BLOCO", P(H_TXT))
    if p["cota_terreno"] is not None:
        yt = (p["cota_terreno"] - ca) * 100
        if yt > 0:
            xe = W if emb > 0 else R
            for s in (-1, 1):
                m.linha(s * xe, yt, s * (xe + P(1.5)), yt)
                for i in range(6):
                    xi = s * (xe + P(0.25) * (i + 0.5))
                    m.linha(xi, yt, xi - s * P(0.15), yt - P(0.15))
            y_topo = max(y_topo, yt + P(0.3))

    # lado esquerdo só para as sondagens (a 1ª junto da estaca, ligada por pontilhado)
    terreno = p["cota_terreno"] is not None and p["cota_terreno"] > ca
    x_sond = -W - P(2.9 if terreno else 1.8)           # com terreno: a cota da ligação não cai na hachura

    # barras longitudinais: duas linhas na estaca; a barra destacada vai à direita, depois das marcas de nível
    zona = "pos" if p["dobra_sentido"] == "fora" else "neg"
    destacadas = []
    for i, s in enumerate(segs):
        off = P(0.07) if i % 2 else 0.0
        main = s["y_top"] - s["y_bot"]
        ins = [dict(x=-Rl + off, y=s["y_bot"], ang=90.0, esc=1.0, ident=0, idobra=0, ipatas=1, nv=NV_FERRO_INT),
               dict(x=Rl - off, y=s["y_bot"], ang=90.0, esc=1.0, ident=0, idobra=0, ipatas=4, nv=NV_FERRO_INT)]
        if af and s["y_bot"] < af["y_af"] - 1e-6:
            # trecho que entra no afunilamento: na estaca, linhas convergindo até a base (o ferro segue reto,
            # como no detalhe do escritório: a inclinação acrescenta menos de 1 cm)
            ins = []
            r_y = lambda y: Rl if y >= af["y_af"] else af["rb"](y)
            ys_b = [s["y_bot"]] + ([af["y_af"]] if s["y_bot"] < af["y_af"] < s["y_top"] else []) + [s["y_top"]]
            for sg in (-1, 1):
                pts = [(sg * (r_y(y) - off), y) for y in ys_b]
                if s["dobra"] > 0:
                    pts.append((sg * (Rl - off + (1 if zona == "pos" else -1) * s["dobra"]), s["y_top"]))
                m.poli(pts, NV_FERRO_INT)
        f = dict(chave=f"L{i + 1}", tipo="reto", mark=s["mark"], quant=p["n_barras"], bitola=p["bitola_long"],
                 aco=p["aco_long"], espac=0.0, cover=c, comment="", main=main, dobra=s["dobra"], zona=zona,
                 comp=pos_comp.get(s["mark"], main), faixas=[], marcas=[], ins=ins)
        if s.get("pontos"):                            # barra destacada com o afunilamento: ferro genérico do TQS
            dob = [((1 if zona == "pos" else -1) * s["dobra"], 0.0)] if s["dobra"] > 0 else []
            f.update(tipo="gen", pontos=dob + s["pontos"])
        f["desc"] = _descricao(f)
        m.ferros.append(f)
        destacadas.append((f, s))

    # colunas à direita da estaca
    xb = R + P(1.2)                                    # faixa de estribos
    xa = xb + P(1.8)                                   # faixa dos anéis
    xr = (xa if p["aneis"] else xb) + P(2.0)           # comprimento total
    xlv = xr + P(1.2)                                  # marcadores de cota

    # estribos na elevação
    if helic:
        # meias voltas em zigue-zague; no afunilamento, o raio acompanha as barras (tronco de cone)
        trechos = [(z["y_top"], z["L"], z["s"], re, re) for z in zonas]
        if af:
            zf = af["zona"]
            trechos.append((zf["y_top"], zf["L"], zf["s"], zf["r_top"], zf["r_bot"]))
        pts = [(-re, zonas[0]["y_top"]), (re, zonas[0]["y_top"])]
        lado = 1
        for y0, Lz, s_z, r0, r1 in trechos:
            nmeia = max(1, round(2 * Lz / s_z))
            d = Lz / nmeia
            for j in range(1, nmeia + 1):
                lado = -lado
                pts.append((lado * (r0 + (r1 - r0) * j / nmeia), y0 - j * d))
        pts.append((-pts[-1][0], pts[-1][1]))
        m.poli(pts, NV_FERRO_INT)
        esp = res["espiral"]
        for y0, Lz, s_z, r0, r1 in trechos:
            t = f"{Lz:.0f} PASSO {s_z:g}"
            m.cota(re, y0, re, y0 - Lz, xb, txt=t if len(t) * P(H_TXT) < 0.95 * Lz else f"{Lz:.0f} P={s_z:g}")
        m.texto(xb + P(0.45), (zonas[0]["y_top"] + res["ys_bot"]) / 2,
                f"ESTRIBO HELICOIDAL {esp['marcas']} {{{bt(p['bitola_estr'])}", P(H_TXT), NV_COTA, ang=90.0, alin="centro")
    else:
        for z in zonas:
            for y in z["ys"]:
                m.linha(-re, y, re, y, NV_FERRO_INT)
        if af:
            m.cota(re, af["y_af"], re, -Larm, xb, txt=f"{af['Laf']:.0f}")
    if af:
        for e in af["estribos"]:
            r_e = e["dext"] / 2 - e["bitola"] / 20
            m.linha(-r_e, e["y"], r_e, e["y"], NV_FERRO_INT)
    if p["aneis"]:
        an = res["aneis"]
        for y in an["ys"]:
            m.linha(-an["r"], y, an["r"], y, NV_FERRO_INT, estilo=1)
        if an["n"] != an["n_faixa"]:                   # anéis duplos no topo e na ponta: 2xNx
            h_ = P(H_TXT)
            for y1, y2, acima in ((an["ys"][0], an["ys"][1], False), (an["ys"][-2], an["ys"][-1], True)):
                yt_ = y1 + P(0.12) if acima else y2 - P(0.12) - h_
                m.linha(an["r"], (y1 + y2) / 2, R + P(0.15), yt_ + h_ / 2, NV_CHAMADA)
                m.texto(R + P(0.18), yt_, f"2xN{an['mark']}", h_)
    rol = res.get("roletes")
    if rol:                     # roletes das faces laterais, vistos de frente: centrados no estribo, até a face
        rr = rol["mm"] / 20
        for y in rol["ys"]:
            for s in (-1, 1):
                m.circulo(s * re, y, rr, NV_CONTORNO)

    # cotas de nível
    niveis = [(0.0, "ARRASAMENTO" + (" DO BLOCO MAIS ALTO" if dv else ""))]
    if dv:
        niveis.append((-dv, "ARRASAMENTO DO BLOCO MAIS BAIXO"))
    if h_perd > 0:
        niveis.append((h_perd, "INÍCIO DA PERFURAÇÃO"))
    if emb > 0:
        niveis.append((-emb, "FUNDO DO BLOCO" + (" MAIS ALTO" if dv else "")))
        if dv:
            niveis.append((-emb - dv, "FUNDO DO BLOCO MAIS BAIXO"))
        if hb:
            niveis.append((hb - emb, "TOPO DO BLOCO" + (" MAIS ALTO" if dv else "")))
        # com o detalhe da ancoragem, a ancoragem mínima fica nele
        if y_bar > p["ancoragem"] + 1 and not det_anc:   # barras além da ancoragem (prolongamento): onde ela termina
            niveis.append((p["ancoragem"], "ANCORAGEM MÍNIMA NO BLOCO"))
    if af:
        ev = af["estribos"]
        niveis.append((af["y_af"], "INÍCIO DO AFUNILAMENTO" + ("" if helic else f" (ESTRIBOS N{ev[0]['mark']}"
                                   + (f" A N{ev[-1]['mark']}" if len(ev) > 1 else "") + ")")))
    niveis.append((-Larm, "BASE DA ARMAÇÃO"))
    niveis.append((-L, "PONTA"))
    if p["cota_terreno"] is not None and p["cota_terreno"] > ca:
        niveis.append(((p["cota_terreno"] - ca) * 100, "TERRENO"))
    niveis.sort(key=lambda v: -v[0])
    h, ytx = P(H_TXT), math.inf
    for y, nome in niveis:
        yy = yd(y)
        ytx = min(yy + P(0.08), ytx - P(0.45))
        a = P(0.12)
        x_face = R if (y <= 0 or y == h_perd) else (W if emb > 0 else R)
        m.linha(x_face + P(FOLGA), yy, xlv + P(0.3), yy, NV_CHAMADA)
        m.poli([(xlv, yy), (xlv - a, yy + 1.6 * a), (xlv + a, yy + 1.6 * a), (xlv, yy)], NV_COTA, cheio=True)
        if abs(ytx - yy - P(0.08)) > 1e-6:
            m.linha(xlv + P(0.3), yy, xlv + P(0.45), ytx + h / 2, NV_CHAMADA)
        m.texto(xlv + P(0.5), ytx, f"{cota(ca + y / 100)} {nome}", h)
    if dv > 0:                                         # variação do fundo em cadeia com o comprimento da estaca
        m.cota(R, 0, R, -dv, xr, txt=f"{dv:.0f}")
        m.cota(R, -dv, R, yd(-L), xr, txt=f"{L - dv:.0f}")
    else:
        m.cota(R, 0, R, yd(-L), xr, txt=f"{L:.0f}")
    if h_perd > 0:                                     # trecho a arrasar, em cadeia com o comprimento da estaca
        m.cota(R, h_perd, R, 0, xr, txt=f"{h_perd:.0f}")

    # corte A-A
    y_cut = (res["ys_top0"] + res["y_lim"]) / 2
    cortes = [(y_cut, "A")] + ([(res["ys_bot"], "B")] if af else [])
    for y_c, letra in cortes:
        for s in (-1, 1):
            m.linha(s * (R + P(0.15)), y_c, s * (R + P(0.6)), y_c, NV_CORTE)
            m.texto(s * (R + P(0.38)), y_c + P(0.12), letra, P(H_SUB), NV_CORTE, alin="centro")

    # barra destacada à direita da elevação: cadeia de cotas, barras (uma por trecho) e o texto de cada uma
    D0 = segs[0]["dobra"]
    x_dl = m.caixa[2] + P(1.2)
    xdet = []
    for i, (f, s) in enumerate(destacadas):
        x_d = x_dl + P(1.0) + D0 + i * (P(1.3) + D0)
        xdet.append(x_d)
        if f["tipo"] == "gen":                         # pontos a partir do topo do trecho reto
            f["ins"].append(dict(x=x_d, y=s["y_top"], ang=0.0, esc=1.0, ident=0, idobra=1, ipatas=0))
            y_ret = af["y_af"] if s["y_bot"] < af["y_af"] < s["y_top"] else s["y_bot"]
            f["texto"] = dict(x=x_d + P(0.45), y=(s["y_top"] + y_ret) / 2, ang=90.0, cmp=True)   # como na barra reta
            dx = -f["pontos"][-1][0]                       # quanto a barra afunila (para dentro)
            if dx > 0.05:                                  # prolongamento do trecho reto e a cota do afunilamento
                m.linha(x_d, y_ret, x_d, s["y_bot"], NV_COTA, estilo=1)
                m.cota(x_d - dx, s["y_bot"], x_d, s["y_bot"], s["y_bot"] - P(0.6), vertical=False, txt=br(dx, 1))
        else:
            f["ins"].append(dict(x=x_d, y=s["y_bot"], ang=90.0, esc=1.0, ident=1, idobra=1, ipatas=1))
        m._cx((x_d - D0, yd(s["y_bot"])), (x_d + D0 + P(0.7), s["y_top"]))
    ys_cota = {round(y_bar, 1), 0.0, round(-Larm, 1)}
    if y_bar > p["ancoragem"] + 1:                     # prolongamento: a ancoragem no bloco em destaque na cadeia
        ys_cota.add(round(p["ancoragem"], 1))
    if dv > 0:                                         # e a variação do fundo
        ys_cota.add(round(-dv, 1))
    for a, b in zip(segs, segs[1:]):
        ys_cota.update((round(b["y_top"], 1), round(a["y_bot"], 1)))
    ys_cota = sorted(ys_cota, reverse=True)
    for ya, yb in zip(ys_cota, ys_cota[1:]):
        m.cota(min(xdet) - P(0.3), ya, min(xdet) - P(0.3), yb, x_dl)

    if perfis_sond:                                    # sondagens à esquerda da elevação, alinhadas por cota
        es.desenhar_colunas(m, perfis_sond, ca, x_sond, face=lambda y: -(W if emb > 0 and y > -emb else R))
    x_dir = m.caixa[2]
    x_esq = m.caixa[0]                                 # borda esquerda da elevação (com as sondagens)
    y_topo = max(y_topo, m.caixa[3])

    # ---------------------------------------------------------------- seção A-A e detalhes
    Rk = R * k
    xs = x_dir + P(2.5) + max(Rk, P(4.2))           # espaço para os títulos centrados
    ys = y_topo - P(1.2) - Rk
    m.circulo(xs, ys, Rk)
    esc_fc = max(fl * k, P(0.09))
    ang0 = math.pi / 2
    bar_xy = [(xs + Rl * k * math.cos(ang0 + 2 * math.pi * i / p["n_barras"]),
               ys + Rl * k * math.sin(ang0 + 2 * math.pi * i / p["n_barras"])) for i in range(p["n_barras"])]
    for x, y in bar_xy:
        m.fercor(x, y, esc_fc)
    m.cota(xs - Rk, ys, xs + Rk, ys, ys + Rk + P(0.5), vertical=False, fator=1 / k)
    alvo = max(bar_xy, key=lambda v: (v[0] - xs) + (v[1] - ys))          # barra perto de 45°
    seg_cut = next((s for s in segs if s["y_bot"] <= y_cut <= s["y_top"]), segs[0])
    f_cut = next(f for f in m.ferros if f["mark"] == seg_cut["mark"])
    x_id = xs + Rk + P(1.2)
    m.marca(f_cut, x_id + P(1.8), ys + Rk * 0.75, [alvo])
    m.texto(xs, ys - Rk - P(0.9), "SEÇÃO A-A", P(H_SUB), NV_CORTE, alin="centro")
    m.texto(xs, ys - Rk - P(1.35), f"ESC. 1:{p['escala_secao']:g}", P(H_TXT), NV_ESCALA, alin="centro")
    y_col = ys - Rk - P(2.6)
    if p["aneis"]:                                     # descrição do anel abaixo do título da seção
        y_txt_anel = ys - Rk - P(1.95)
        y_col -= P(0.5)

    if helic:
        esp = res["espiral"]
        m.circulo(xs, ys, re * k, NV_FERRO_INT)
        a = math.radians(-35)
        # detalhe do estribo helicoidal: duas voltas com passo do trecho principal
        s_det = zonas[-1]["s"]
        rk, sk = re * k, s_det * k
        yh = y_col - P(0.6)
        pts = [(xs - rk, yh), (xs + rk, yh)]
        lado = 1
        for j in range(1, 5):
            lado = -lado
            pts.append((xs + lado * rk, yh - j * sk / 2))
        m.poli(pts, NV_FERRO_INT)
        m.cota(xs - (R - c) * k, yh, xs + (R - c) * k, yh, yh + P(0.6), vertical=False, fator=1 / k)
        m.cota(xs + rk, yh - sk / 2, xs + rk, yh - 1.5 * sk, xs + rk + P(0.9), txt=f"P={s_det:g}")
        yt = yh - 2 * sk - P(0.9)
        m.texto(xs, yt, f"DETALHE DO ESTRIBO HELICOIDAL {esp['marcas']}", P(H_SUB), NV_CORTE, alin="centro")
        m.texto(xs, yt - P(0.45), f"ESC. 1:{p['escala_secao']:g}", P(H_TXT), NV_ESCALA, alin="centro")
        passo = f"PASSO {zonas[-1]['s']:g} cm"
        zr = [z for z in zonas if abs(z["s"] - zonas[-1]["s"]) > 1e-6]      # trecho reduzido (passo diferente)
        if zr:                                         # com o trecho a arrasar, ele começa no arrasamento
            passo += (f" ({br(zr[0]['L'] / 100)} m " + ("SUPERIORES" if zr[0] is zonas[0] else "ABAIXO DO ARRASAMENTO")
                      + f": {zr[0]['s']:g} cm)")
        info = [f"{{{bt(p['bitola_estr'])} - DIÂMETRO EXTERNO {D - 2 * c:g} cm",
                passo,
                *([f"AFUNILAMENTO NOS {br(af['Laf'] / 100)} m INFERIORES: {{EXTERNO ATÉ "
                   f"{br(2 * af['zona']['r_bot'] + ft, 1)} cm"] if af else []),
                f"{br(esp['voltas'], 1)} VOLTAS + {p['voltas_fecho']:g} DE FECHAMENTO EM CADA PONTA",
                f"DESENVOLVIDO {br(esp['comp'] / 100)} m: "
                + " + ".join(f"{x['quant']} N{x['mark']} C={x['comp']}" for x in esp["partes"])
                + (f", TRANSPASSE {p['transpasse_espiral']:g} cm" if esp["pecas"] > 1 else "")]
        yt -= P(1.1)
        for s_ in info:
            m.texto(xs - Rk - P(1.0), yt, s_, P(H_TXT))
            yt -= P(0.4)
        y_col = yt - P(0.4)
        for i, x in enumerate(esp["partes"]):           # uma posição por comprimento (inteiras e complemento)
            f_esp = dict(chave=f"ESP{i + 1}", tipo="reto", mark=x["mark"], quant=x["quant"], bitola=p["bitola_estr"],
                         aco=p["aco_estr"], espac=0.0, cover=c, comment=x["obs"], main=float(x["comp"]), dobra=0.0,
                         zona="pos", comp=pos_comp.get(x["mark"], x["comp"]), faixas=[], ins=[], marcas=[])
            f_esp["desc"] = _descricao(f_esp)
            m.ferros.append(f_esp)
            if i == 0:
                m.marca(f_esp, x_id + P(1.8), ys - max(Rk * 0.55, P(0.4)), [(xs + re * k * math.cos(a), ys + re * k * math.sin(a))], nfr=0)
    else:
        e = res["estribo"]
        yd_ = y_col - P(0.3) - Rk
        f_e = dict(chave="EST", tipo="circ", mark=e["mark"], quant=e["n"], bitola=p["bitola_estr"], aco=p["aco_estr"],
                   espac=zonas[-1]["s"], cover=c, comment="", raio=R, blong=p["bitola_long"],
                   comp=pos_comp.get(e["mark"], e["comp"]), marcas=[],
                   faixas=[dict(x=xb, y1=z["y_bot"], y2=z["y_top"], s=z["s"], inicio=z["inicio"], n=z["n"],
                                xcot=xb, cotar=1) for z in zonas],
                   ins=[dict(x=xs, y=ys, ang=0.0, esc=k, ident=0, idobra=0, ipatas=1, explode=1),
                        dict(x=xs, y=yd_, ang=0.0, esc=k, ident=1, idobra=1, ipatas=1, explode=1)])
        f_e["desc"] = _descricao(f_e)
        m.ferros.append(f_e)
        m._cx((xs - Rk, yd_ - Rk - P(0.8)), (xs + Rk, yd_ + Rk))
        m.texto(xs, yd_ - Rk - P(1.3), f"DETALHE DO ESTRIBO N{e['mark']}", P(H_SUB), NV_CORTE, alin="centro")
        m.texto(xs, yd_ - Rk - P(1.75), f"ESC. 1:{p['escala_secao']:g}", P(H_TXT), NV_ESCALA, alin="centro")
        y_col = yd_ - Rk - P(2.3)

    if af:
        # seção B-B no estribo da ponta: barras convergidas e o estribo da ponta (com a descrição abaixo)
        ysB = y_col - P(0.6) - Rk
        m.circulo(xs, ysB, Rk)
        for i in range(p["n_barras"]):
            t = ang0 + 2 * math.pi * i / p["n_barras"]
            m.fercor(xs + af["r_tip"] * k * math.cos(t), ysB + af["r_tip"] * k * math.sin(t), esc_fc)
        m.cota(xs - af["Dp"] / 2 * k, ysB, xs + af["Dp"] / 2 * k, ysB, ysB + Rk + P(0.5), vertical=False, fator=1 / k)
        m.texto(xs, ysB - Rk - P(0.9), "SEÇÃO B-B", P(H_SUB), NV_CORTE, alin="centro")
        m.texto(xs, ysB - Rk - P(1.35), f"ESC. 1:{p['escala_secao']:g}", P(H_TXT), NV_ESCALA, alin="centro")
        et = af["estribos"][-1]
        y_txt = ysB - Rk - P(1.95)
        f_t = dict(chave="EPONTA", tipo="circ", mark=et["mark"], quant=et["quant"], bitola=et["bitola"], aco=et["aco"],
                   espac=0.0, cover=R - et["dext"] / 2, comment=et["obs"], raio=R, blong=p["bitola_long"],
                   comp=pos_comp.get(et["mark"], et["comp"]), faixas=[], marcas=[],
                   ins=[dict(x=xs, y=ysB, ang=0.0, esc=k, ident=0, idobra=0, ipatas=1, explode=1)],
                   texto=dict(x=xs, y=y_txt))
        f_t["desc"] = _descricao(f_t)
        m.ferros.append(f_t)
        w2 = len(f_t["desc"]) * P(H_TXT) / 2
        m._cx((xs - w2, y_txt), (xs + w2, y_txt + P(H_TXT)))
        y_col = ysB - Rk - P(2.6)

        # detalhe do afunilamento: as barras convergindo, o estribo helicoidal em tronco de cone (ou os estribos
        # variáveis) e o diâmetro dos enrijecedores superior (anel no início do afunilamento) e da ponta
        yt0 = y_col - P(1.2)                                   # início do afunilamento
        yb0 = yt0 - af["Laf"] * k                              # base da armação
        yp = yt0 - (af["y_af"] - res["ys_bot"]) * k            # estribo da ponta
        for sg in (-1, 1):
            m.linha(xs + sg * Rl * k, yt0 + P(0.4), xs + sg * Rl * k, yt0, NV_FERRO_INT)
            m.linha(xs + sg * Rl * k, yt0, xs + sg * af["r_base"] * k, yb0, NV_FERRO_INT)
        if helic:
            zf = af["zona"]
            nmeia = max(2, round(2 * zf["L"] / zf["s"]))
            pts = [(xs + (1 if j % 2 else -1) * (zf["r_top"] + (zf["r_bot"] - zf["r_top"]) * j / nmeia) * k,
                    yt0 - zf["L"] * j / nmeia * k) for j in range(nmeia + 1)]
            m.poli(pts, NV_FERRO_INT)
        else:
            for e in af["estribos"][:-1]:
                r_e = (e["dext"] / 2 - e["bitola"] / 20) * k
                ye = yt0 - (af["y_af"] - e["y"]) * k
                m.linha(xs - r_e, ye, xs + r_e, ye, NV_FERRO_INT)
        an = res.get("aneis") if p["aneis"] else None
        et = af["estribos"][-1]
        if an:                                                 # anel interno no início do afunilamento
            d_sup, r_sup = 2 * an["r"] + p["bitola_anel"] / 10, an["r"]
            m.linha(xs - r_sup * k, yt0, xs + r_sup * k, yt0, NV_FERRO_INT, estilo=1)
            rot_sup = f"ENRIJECEDOR SUPERIOR N{an['mark']} {{{bt(p['bitola_anel'])} - {{{br(d_sup, 1)} cm (INTERNO)"
        else:
            d_sup, r_sup = D - 2 * c, re
            rot_sup = f"INÍCIO DO AFUNILAMENTO - {{{br(d_sup, 1)} cm (FACE EXTERNA DO ESTRIBO)"
        r_pt = et["dext"] / 2 - et["bitola"] / 20
        m.linha(xs - r_pt * k, yp, xs + r_pt * k, yp, NV_FERRO_INT)
        m.cota(xs - d_sup / 2 * k, yt0, xs + d_sup / 2 * k, yt0, yt0 + P(0.8), vertical=False,
               txt="{" + br(d_sup, 1), fator=1 / k)
        m.cota(xs - et["dext"] / 2 * k, yp, xs + et["dext"] / 2 * k, yp, yb0 - P(0.6), vertical=False,
               txt="{" + br(et["dext"], 1), fator=1 / k)
        m.cota(xs - Rl * k, yt0, xs - af["r_base"] * k, yb0, xs - Rl * k - P(0.9), txt=f"{af['Laf']:.0f}", fator=1 / k)
        xl = xs + Rl * k + P(0.8)
        rot_pt = f"ENRIJECEDOR DA PONTA {et['quant']} N{et['mark']} {{{bt(et['bitola'])} - {{{br(et['dext'], 1)} cm"
        for y_r, r_r, txt_r in ((yt0, r_sup, rot_sup), (yp, r_pt, rot_pt)):
            m.linha(xs + r_r * k, y_r, xl - P(0.1), y_r, NV_COTA)
            m.texto(xl, y_r - P(H_TXT) / 2, txt_r, P(H_TXT))
        y_low = yb0 - P(1.4)
        m.texto(xs, y_low - P(0.4), "DETALHE DO AFUNILAMENTO", P(H_SUB), NV_CORTE, alin="centro")
        m.texto(xs, y_low - P(0.85), f"ESC. 1:{p['escala_secao']:g}", P(H_TXT), NV_ESCALA, alin="centro")
        y_col = y_low - P(1.4)

    if af and len(af["estribos"]) > 1:
        # estribos variáveis: um detalhe para cada, em grade, com a descrição abaixo (concêntricos não se
        # distinguem: os diâmetros mudam menos de 1 cm de um para o outro)
        rk = af["d_top"] / 2 * k
        specs = []
        for j, e in enumerate(af["estribos"][:-1]):
            f_v = dict(chave=f"EV{j + 1}", tipo="circ", mark=e["mark"], quant=e["quant"], bitola=e["bitola"], aco=e["aco"],
                       espac=0.0, cover=R - e["dext"] / 2, comment=e["obs"], raio=R, blong=p["bitola_long"],
                       comp=pos_comp.get(e["mark"], e["comp"]), faixas=[], marcas=[], ins=[])
            f_v["desc"] = _descricao(f_v)
            specs.append(f_v)
        cel = max(2 * rk, max(len(f["desc"]) for f in specs) * P(H_TXT)) + P(0.6)
        ncol = min(3, len(specs))
        alt = 2 * rk + P(1.0)
        y0 = y_col - P(0.3) - rk
        for j, f_v in enumerate(specs):
            lin, col = divmod(j, ncol)
            cx, cy = xs + (col - (ncol - 1) / 2) * cel, y0 - lin * alt
            f_v["ins"].append(dict(x=cx, y=cy, ang=0.0, esc=k, ident=0, idobra=0, ipatas=1, explode=1))
            f_v["texto"] = dict(x=cx, y=cy - rk - P(0.45))
            m._cx((cx - cel / 2, cy - rk - P(0.45)), (cx + cel / 2, cy + rk))
            m.ferros.append(f_v)
        y_low = y0 - (math.ceil(len(specs) / ncol) - 1) * alt - rk - P(0.45)
        m.texto(xs, y_low - P(0.8), "ESTRIBOS VARIÁVEIS DO AFUNILAMENTO", P(H_SUB), NV_CORTE, alin="centro")
        m.texto(xs, y_low - P(1.25), f"ESC. 1:{p['escala_secao']:g}", P(H_TXT), NV_ESCALA, alin="centro")
        y_col = y_low - P(1.8)

    if rol:
        # detalhe dos roletes. O rolete é encaixado no estribo (o estribo passa no eixo da roda) e roda num plano
        # vertical e radial, com o raio igual ao cobrimento: na seção aparece de perfil (retângulo radial centrado
        # no estribo, metade para fora até a face, metade para dentro, entre as barras); ao lado, a vista do rolete
        esc_r = 10 if D <= 50 else (20 if D <= 100 else p["escala_secao"])      # vista do rolete: escala própria
        kr = E / esc_r
        Rkp = R * k                                            # seção na escala das seções (1:25)
        rr = rol["mm"] / 20                                    # raio do rolete (cm)
        tr = max(0.75, 0.15 * rr)                              # meia espessura da roda (cm)
        hv = rr + 4.0                                          # meia altura da vista do rolete (cm)
        yr = y_col - P(0.6) - max(Rkp, hv * kr)
        m.circulo(xs, yr, Rkp)
        m.circulo(xs, yr, re * k, NV_FERRO_INT)
        for i in range(p["n_barras"]):
            t = ang0 + 2 * math.pi * i / p["n_barras"]
            m.fercor(xs + Rl * k * math.cos(t), yr + Rl * k * math.sin(t), esc_fc)
        # giro dos roletes que os deixa o mais longe possível das barras (passo de 1 grau)
        barras_t = [ang0 + 2 * math.pi * i / p["n_barras"] for i in range(p["n_barras"])]
        dist = lambda a, b: abs((a - b + math.pi) % (2 * math.pi) - math.pi)
        th0 = max((ang0 + math.radians(g) for g in range(0, 360 // rol["n"] + 1)),
                  key=lambda t0: min(dist(t0 + 2 * math.pi * i / rol["n"], b) for i in range(rol["n"]) for b in barras_t))
        for i in range(rol["n"]):
            t = th0 + 2 * math.pi * i / rol["n"]
            u, v = (math.cos(t), math.sin(t)), (-math.sin(t), math.cos(t))
            cx, cy = xs + re * k * u[0], yr + re * k * u[1]
            m.poli([(cx + (a * rr * u[0] + b * tr * v[0]) * k, cy + (a * rr * u[1] + b * tr * v[1]) * k)
                    for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1), (-1, -1))], NV_CONTORNO)
        m.texto(xs, yr - Rkp - P(0.9), "DETALHE DOS ROLETES ESPAÇADORES", P(H_SUB), NV_CORTE, alin="centro")
        m.texto(xs, yr - Rkp - P(1.35), f"ESC. 1:{p['escala_secao']:g}", P(H_TXT), NV_ESCALA, alin="centro")

        # vista do rolete (de frente): face da estaca, barra longitudinal, estribo no eixo da roda e o raio = cobrimento
        xv = max(xs + Rkp + P(2.2) + (rr + (re - Rl) + fl) * kr, xs + P(7.6))   # títulos sem se encostar
        x_face = xv + (R - re) * kr
        m.linha(x_face, yr - hv * kr, x_face, yr + hv * kr)
        for j in range(7):                                     # solo do lado de fora da face
            yj = yr - hv * kr + (j + 0.5) * 2 * hv * kr / 7
            m.linha(x_face, yj, x_face + P(0.15), yj + P(0.15))
        for sg in (-1, 1):                                     # barra longitudinal, atrás da roda
            xb_ = xv + (Rl - re + sg * fl / 2) * kr
            m.linha(xb_, yr - hv * kr, xb_, yr + hv * kr, NV_FERRO_INT, estilo=1)
        m.circulo(xv, yr, rr * kr, NV_CONTORNO)                # roda
        m.circulo(xv, yr, 0.3 * rr * kr, NV_CONTORNO)          # cubo
        for j in range(6):                                     # raios da roda
            a = math.pi / 6 + j * math.pi / 3
            m.linha(xv + 0.3 * rr * kr * math.cos(a), yr + 0.3 * rr * kr * math.sin(a),
                    xv + 0.85 * rr * kr * math.cos(a), yr + 0.85 * rr * kr * math.sin(a), NV_CONTORNO)
        m.fercor(xv, yr, max(ft * kr, P(0.06)))                 # estribo passando no eixo
        m.cota(xv + ft / 2 * kr, yr, x_face, yr, yr - hv * kr - P(0.3), vertical=False, fator=1 / kr)
        m.cota(xv - rr * kr, yr - rr * kr, xv - rr * kr, yr + rr * kr, xv - (rr + (re - Rl) + fl) * kr - P(0.5),
               txt="{" + f"{rol['mm']:g}", fator=1 / kr)
        h_ = P(0.15)
        m.texto(x_face + P(0.25), yr + hv * kr - h_, "FACE DA ESTACA", h_)
        m.texto(xv + (Rl - re) * kr, yr + hv * kr + P(0.15), "BARRA", h_, alin="centro")
        m.linha(xv + P(0.05), yr - P(0.05), xv + P(0.6), yr - rr * kr - P(0.25), NV_COTA)
        m.texto(xv + P(0.65), yr - rr * kr - P(0.35), "ESTRIBO NO EIXO DO ROLETE", h_)
        m.texto(xv, yr - hv * kr - P(1.0), f"VISTA DO ROLETE {{{rol['mm']:g} mm", P(H_SUB), NV_CORTE, alin="centro")
        m.texto(xv, yr - hv * kr - P(1.45), f"ESC. 1:{esc_r:g}", P(H_TXT), NV_ESCALA, alin="centro")

        info = [f"{rol['n']} ROLETES {{{rol['mm']:g} mm POR SEÇÃO, A CADA {360 / rol['n']:g} GRAUS, ENCAIXADOS NO ESTRIBO",
                f"RAIO DO ROLETE = COBRIMENTO; SEÇÕES A CADA {rol['espac']:g} cm: {rol['secoes']} SEÇÕES",
                f"TOTAL: {rol['total']} ROLETES POR ESTACA" + (f" ({rol['total'] * p['quantidade']} NAS "
                                                                 f"{p['quantidade']} ESTACAS)" if p["quantidade"] > 1 else "")]
        yt = min(yr - Rkp, yr - hv * kr - P(0.6)) - P(1.9)
        for s_ in info:
            m.texto(xs - Rkp, yt, s_, P(H_TXT))
            yt -= P(0.4)
        y_col = yt - P(0.4)

    if p["aneis"]:
        an = res["aneis"]
        f_a = dict(chave="ANEL", tipo="anel", mark=an["mark"], quant=an["n"], bitola=p["bitola_anel"],
                   aco=p["aco_anel"], espac=p["espac_anel"], cover=an["cover"], comment=OBS_ANEL, r_eixo=an["r"],
                   transpasse=an["transpasse"], comp=pos_comp.get(an["mark"], an["comp"]),
                   faixas=[dict(x=xa, y1=res["y_lim"], y2=res["ys_top"], s=p["espac_anel"], inicio=True,
                                n=an["n"], xcot=xa, cotar=0, nman=an["n"] if an["n"] != an["n_faixa"] else None)],
                   ins=[dict(x=xs, y=ys, ang=0.0, esc=k, ident=0, idobra=0, ipatas=0, explode=0)], marcas=[],
                   texto=dict(x=xs, y=y_txt_anel))
        f_a["desc"] = _descricao(f_a)
        m.ferros.append(f_a)
        w2 = len(f_a["desc"]) * P(H_TXT) / 2
        m._cx((xs - w2, y_txt_anel), (xs + w2, y_txt_anel + P(H_TXT)))
        a = -0.25 * math.pi
        m.marca(f_a, x_id + P(1.8), ys - max(Rk * 0.95, P(0.85)), [(xs + an["r"] * k * math.cos(a), ys + an["r"] * k * math.sin(a))])

    # ---------------------------------------------------------------- tabelas, quantitativos e notas
    xC = m.caixa[2] + P(2.5)
    yC = y_topo
    h = P(H_TAB)
    N = p["quantidade"]
    linhas = [[t["aco"], f"N{t['mark']}", bt(t["bitola"]), t["quant"], f"{t['comp']:.0f}",
               f"{t['quant'] * t['comp']:.0f}"] for t in sorted(tabela, key=lambda t: t["mark"])]
    _, yC = _tabela(m, xC, yC, "TABELA DE FERROS - 1 ESTACA",
                    ["AÇO", "POS", "BIT(mm)", "QUANT", "UNIT(cm)", "TOTAL(cm)"], linhas, h)
    if af and not helic:
        lin_e = [[f"N{e['mark']}", e["quant"], bt(e["bitola"]), bt(e["dext"]), cota(ca + e["y"] / 100),
                  f"{pos_comp.get(e['mark'], e['comp']):.0f}"] for e in af["estribos"]]
        _, yC = _tabela(m, xC, yC - P(0.8), f"ESTRIBOS DO AFUNILAMENTO ({br(af['Laf'] / 100)} m) - 1 ESTACA",
                        ["POS", "QUANT", "BIT(mm)", "{EXT(cm)", "COTA(m)", "C(cm)"], lin_e, h)
    ra = resumo_aco(tabela)
    lin_r, kg1 = [], 0.0
    for (aco, b), comp_m in ra.items():
        kg = comp_m * massa_linear(b)
        kg1 += kg
        lin_r.append([aco, bt(b), br(comp_m), br(kg, 1), br(kg * N, 1)])
    lin_r.append(["TOTAL", "", "", br(kg1, 1), br(kg1 * N, 1)])
    _, yC = _tabela(m, xC, yC - P(0.8), "RESUMO DO AÇO",
                    ["AÇO", "BIT(mm)", "COMPR(m)", "PESO 1 EST(kg)", f"PESO {N} EST(kg)"], lin_r, h)
    vol, vol_perd = res["volume"], res["volume_perdido"]
    volN, perdN = res["volume_N"], res["volume_perdido_N"]       # N estacas: bloco a bloco, se a tabela tiver as cotas
    mat = "ARGAMASSA" if p["tipo_estaca"] == "raiz" else "CONCRETO"
    lin_q = [[f"{mat} (m3)", br(vol), br(volN)],
             *([[f"{mat} PERDIDO NO ARRASAMENTO (m3)", br(vol_perd), br(perdN)],
                [f"{mat} TOTAL LANÇADO (m3)", br(vol + vol_perd), br(volN + perdN)]] if vol_perd > 0 else []),
             ["AÇO (kg)", br(kg1, 1), br(kg1 * N, 1)],
             ["TAXA (kg/m3)", f"{kg1 / vol:.0f}", f"{kg1 * N / volN:.0f}"]]
    if rol:
        lin_q.append([f"ROLETES {{{rol['mm']:g} mm (un)", rol["total"], rol["total"] * N])
    _, yC = _tabela(m, xC, yC - P(0.8), f"QUANTITATIVOS - ESTACA {{{D:g} L={br(L / 100)} m",
                    ["ITEM", "1 ESTACA" + (" (BLOCO MAIS ALTO)" if dv else ""), f"{N} ESTACA{'S' if N > 1 else ''}"], lin_q, h)
    bl = res["blocos"]
    if bl:                                             # blocos onde a estaca é usada
        tem_cota = any(b["fundo"] is not None for b in bl)
        cab = (["BLOCO", "ESTACAS"] + (["FUNDO (m)", "ARRAS. (m)", "ANCOR. MÍN. (m)", "L (m)"] if tem_cota else [])
               + (["A ARRASAR (cm)"] if tem_cota and h_perd > 0 else []))
        lin_b = []
        for b in bl:
            ok = b["fundo"] is not None
            lin = [b["bloco"], b["estacas"]]
            if tem_cota:
                lin += ([cota(b["fundo"]), cota(b["arras"]), cota(b["arras"] + p["ancoragem"] / 100), br(b["L"] / 100)]
                        if ok else ["-", "-", "-", "-"])
                if h_perd > 0:
                    lin.append(f"{b['perd']:.0f}" if ok else "-")
            lin_b.append(lin)
        lin_b.append(["TOTAL", N] + [""] * (len(cab) - 2))
        _, yC = _tabela(m, xC, yC - P(0.8), f"BLOCOS COM A ESTACA {p['tipo']}".strip(), cab, lin_b, h)

    notas = [n.format(fck=f"{p['fck']:g}", cobrimento=f"{c:g}", diametro=f"{D:g}") for n in p["notas"]
             if not (rol and n.upper().startswith("ESPAÇADORES TIPO ROLETE"))       # a nota automática substitui
             and not n.upper().startswith("CONCRETO DA ESTACA")]                     # vira a nota do tipo (CAA)
    i_t = 1 if notas and notas[0].upper().startswith("MEDIDAS") else 0
    notas[i_t:i_t] = notas_tipo(p)                    # concreto pela CAA e anexo da NBR 6122, depois das medidas
    if h_perd > 0:
        dob = res["dobra_det"]
        notas.append(f"PERFURAÇÃO A PARTIR DA COTA {cota(p['cota_perfuracao'])}: ARMAÇÃO PROLONGADA ATÉ ESSA COTA, COM BARRAS "
                     f"RETAS; O CONCRETO ACIMA DO ARRASAMENTO ({br(vol_perd)} m3 POR ESTACA" + (" NO BLOCO MAIS ALTO" if dv else "")
                     + f") SERÁ DEMOLIDO NO ARRASAMENTO, E AS BARRAS, CORTADAS {p['ancoragem'] + dob:g} cm ACIMA DELE"
                     + (f" E DOBRADAS NA ANCORAGEM ({dob:g} cm)" if dob > 0 else "")
                     + (", CONFORME O DETALHE DA ANCORAGEM." if det_anc else "."))
    if dv > 0:
        notas.append(f"BLOCOS COM COTA DE FUNDO VARIÁVEL: ARRASAMENTO DE {cota(ca - dv / 100)} A {cota(ca)}. DETALHE PELO BLOCO "
                     f"MAIS ALTO; ARMAÇÃO ATÉ {br((Larm - dv) / 100)} m ABAIXO DO ARRASAMENTO MAIS BAIXO"
                     + (f" E TRECHO SUPERIOR DE ESTRIBOS ATÉ {br(p['zona_sup'])} m ABAIXO DELE"
                        if p["zona_sup"] > 0 and p["espac_sup"] > 0 else "") + ".")
    if det_anc:
        notas.append(f"ANCORAGEM DAS BARRAS LONGITUDINAIS NO BLOCO: NO MÍNIMO {p['ancoragem']:g} cm ACIMA DO ARRASAMENTO, "
                     "CONFORME O DETALHE DA ANCORAGEM.")
    elif emb > 0:                                      # ancoragem das barras no bloco, depois do arrasamento
        nt = (f"ANCORAGEM NO BLOCO: AS BARRAS LONGITUDINAIS DEVEM ENTRAR NO MÍNIMO {p['ancoragem']:g} cm NO BLOCO, ACIMA DA "
              f"COTA DE ARRASAMENTO (lb = {res['lb']:.0f} cm)")
        notas.append(nt + ".")
    if rol:
        notas.append(f"ROLETES ESPAÇADORES DE {rol['mm']:g} mm: {rol['n']} POR SEÇÃO, A CADA {br(rol['espac'] / 100)} m "
                     f"({rol['total']} POR ESTACA), CONFORME O DETALHE.")
    if len(segs) > 1:
        notas.append(f"EMENDAS DAS BARRAS LONGITUDINAIS POR TRANSPASSE DE {res['l0']:g} cm.")
    if helic:
        notas.append(f"ESTRIBO HELICOIDAL CONTÍNUO COM {p['voltas_fecho']:g} VOLTA(S) DE FECHAMENTO EM CADA PONTA"
                     + (f"; EMENDAS POR TRANSPASSE DE {p['transpasse_espiral']:g} cm." if res["espiral"]["pecas"] > 1 else "."))
    if p["aneis"]:
        notas.append(f"ANÉIS ENRIJECEDORES SOLDADOS INTERNAMENTE ÀS BARRAS LONGITUDINAIS, TRANSPASSE SOLDADO DE "
                     f"{res['aneis']['transpasse']:g} cm" + ("; ANÉIS DUPLOS NAS PONTAS." if res["aneis"]["n"] != res["aneis"]["n_faixa"] else "."))
    if res.get("diam_estribo"):
        notas.append(f"ESTACA RAIZ: ESTRIBO COM {bt(res['diam_estribo'])} cm DE DIÂMETRO EXTERNO, PARA CABER NO TUBO DE PERFURAÇÃO.")
    if af:
        notas.append(f"AFUNILAMENTO DA ARMAÇÃO NOS {br(af['Laf'] / 100)} m INFERIORES: AS BARRAS CONVERGEM ATÉ O ESTRIBO "
                     f"DA PONTA ({{{bt(af['Dp'])} cm EXTERNO); "
                     + ("O ESTRIBO HELICOIDAL ACOMPANHA AS BARRAS (TRONCO DE CONE)." if helic
                        else "ESTRIBOS VARIÁVEIS CONFORME A TABELA."))
    notas += notas_gerais(p)                           # notas gerais por último
    yC -= P(0.8)
    m.texto(xC, yC, "NOTAS:", P(H_SUB))
    yC -= P(0.55)
    for i, n in enumerate(notas, 1):
        for j, lin in enumerate(textwrap.wrap(n, 62)):
            m.texto(xC, yC, (f"{i}. " if j == 0 else "   ") + lin, P(H_TXT))
            yC -= P(0.4)

    # quantitativos lidos pelo resumo estrutural do TQS (categoria "Outros"): volume das N estacas
    if p["quant_resumo"]:
        yC -= P(0.4)
        m.prims.append(dict(t="quant", nv=NV_QUANT, x=xC, y=yC, esc=E, area_est=0.0, area_for=0.0,
                            volume=round(volN + perdN, 2)))              # o que é lançado
        m._cx((xC, yC - P(QUANT_ALT)), (xC + P(QUANT_LARG), yC))
        yC -= P(QUANT_ALT)

    # detalhe da ancoragem no bloco, abaixo das notas
    if det_anc:
        yC = _detalhe_ancoragem(m, p, res, xC, yC - P(1.2))

    # estribo helicoidal desenvolvido (linha em escala real) abaixo de tudo
    if helic:
        # abaixo da estaca, a partir da borda esquerda da elevação, logo abaixo do que já ocupa essa faixa
        # (pedido de 13/10/2026: antes ficava embaixo de tudo, a partir da coluna dos detalhes)
        esp_f = [f for f in m.ferros if f["chave"].startswith("ESP")]
        tit = f"ESTRIBO HELICOIDAL {res['espiral']['marcas']} DESENVOLVIDO (ESC. 1:{E:g})"
        larg = max([f["main"] + len(f["desc"]) * P(H_TXT) + P(0.3) for f in esp_f] + [len(tit) * P(H_SUB)])
        x_dev = x_esq
        y_dev = _y_min_faixa(m, x_dev - P(0.3), x_dev + larg + P(0.3), ignorar=esp_f) - P(1.5) - P(0.9)
        m.texto(x_dev, y_dev + P(0.9), tit, P(H_SUB), NV_CORTE)
        for f_esp in esp_f:                            # uma linha por peça
            curta = f_esp["main"] < len(f_esp["desc"]) * P(H_TXT) + P(0.5)     # texto não cabe sob a linha
            f_esp["ins"].append(dict(x=x_dev, y=y_dev, ang=0.0, esc=1.0, ident=0 if curta else 1, idobra=1, ipatas=1))
            if curta:                                                        # texto à direita da peça
                f_esp["texto"] = dict(x=x_dev + f_esp["main"] + P(0.3), y=y_dev - P(H_TXT) / 2, alin="esq")
            m._cx((x_dev, y_dev - P(0.6)), (x_dev + f_esp["main"] + (len(f_esp["desc"]) * P(H_TXT) + P(0.3) if curta else 0),
                                            y_dev + P(0.6)))
            y_dev -= P(1.0)

    # ---------------------------------------------------------------- título
    xt = m.caixa[0]
    yt = m.caixa[3] + P(1.6)
    if p["obra"]:
        m.texto(xt, yt + P(0.9), p["obra"].upper(), P(H_SUB))
    m.texto(xt, yt, f"ESTACA {p['tipo']}".strip(), P(H_TIT), NV_TITULO)
    m.texto(xt, yt - P(0.5), f"(ESCALA 1:{E:g})", P(H_TXT * 1.25), NV_CONTORNO)
    m.texto(xt + P(4.0), yt - P(0.5), f"ESTACA {TIPOS_ESTACA[p['tipo_estaca']]} {{{D:g} cm - L = {br(L / 100)} m - {p['n_barras']} {{{bt(p['bitola_long'])}"
            f" - ESTRIBO {'HELICOIDAL' if helic else 'CIRCULAR'} {{{bt(p['bitola_estr'])}", P(H_TXT))
    m.texto(xt, yt - P(1.1), f"{N}x", P(H_TXT * 1.25), NV_MULT)
    return m


def resumo_texto(res, tabela=None):
    """Resumo em texto puro para o aplicativo e para a linha de comando."""
    p = res["p"]
    tabela = tabela or tabela_estimada(res)
    N = p["quantidade"]
    out = [f"Estaca {p['tipo']}: {{{p['diametro']:g} cm, L = {br(res['L'] / 100)} m, armação {br(res['Larm'] / 100)} m"
           f" + ancoragem {p['ancoragem']:g} cm".replace("{", "ø")
           + (f" (prolongada {res['h_perd']:g} cm acima do arrasamento, até o início da perfuração)" if res.get("h_perd") else "")
           + (f"\nBlocos com fundo variável: arrasamento de {cota(p['cota_arrasamento'] - res['dv'] / 100)} a "
              f"{cota(p['cota_arrasamento'])} (detalhe pelo bloco mais alto)" if res.get("dv") else ""),
           f"CAA {p['caa']}: " + (f"argamassa fak {p['fck']:g} MPa" if p["tipo_estaca"] == "raiz" else f"concreto C{p['fck']:g}")
           + f" (mínimo da NBR 6122, Tabela 4: {fck_minimo(p['tipo_estaca'], p['caa']):g} MPa; anexo {CONCRETO_6122[p['tipo_estaca']]['anexo']})",
           f"lb (NBR 6118) = {res['lb']:.0f} cm   transpasse = {res['l0']:g} cm   espaçamento livre = {br(res['esp_livre'], 1)} cm",
           "", f"{'POS':>4} {'AÇO':6} {'BIT':>5} {'QUANT':>6} {'UNIT cm':>8} {'TOTAL m':>8}  OBS"]
    for t in sorted(tabela, key=lambda t: t["mark"]):
        out.append(f"{'N' + str(t['mark']):>4} {t['aco']:6} {bt(t['bitola']):>5} {t['quant']:>6} {t['comp']:>8.0f} "
                   f"{br(t['quant'] * t['comp'] / 100):>8}  {t['obs']}")
    out.append("")
    kg1 = 0.0
    for (aco, b), m in resumo_aco(tabela).items():
        kg = m * massa_linear(b)
        kg1 += kg
        out.append(f"  {aco} ø{bt(b):>5}: {br(m):>8} m  {br(kg, 1):>8} kg")
    out.append(f"  Aço por estaca: {br(kg1, 1)} kg   x{N} = {br(kg1 * N, 1)} kg")
    out.append(f"  {'Argamassa' if p['tipo_estaca'] == 'raiz' else 'Concreto'}: {br(res['volume'])} m3 por estaca   x{N} = {br(res['volume_N'])} m3"
               + (" (pelas cotas dos blocos)" if res.get("blocos_cota") else "")
               + f"   taxa {kg1 / res['volume']:.0f} kg/m3")
    if res.get("volume_perdido"):
        out.append(f"  Perdido no arrasamento: {br(res['volume_perdido'], 3)} m3 por estaca   x{N} = "
                   f"{br(res['volume_perdido_N'], 3)} m3 (total lançado {br(res['volume_N'] + res['volume_perdido_N'])} m3)")
    if res.get("blocos"):
        out.append("  Blocos: " + ", ".join(f"{b['bloco']} ({b['estacas']}" + (f", fundo {cota(b['fundo'])}" if b["fundo"] is not None else "")
                                         + ")" for b in res["blocos"]) + f" = {N} estacas")
    if res.get("roletes"):
        rol = res["roletes"]
        out.append(f"  Roletes espaçadores ø{rol['mm']:g} mm: {rol['n']} por seção x {rol['secoes']} seções = {rol['total']} "
                   f"por estaca   x{N} = {rol['total'] * N}")
    if p["quant_resumo"]:
        out.append(f"  Resumo estrutural do TQS (Outros): volume de concreto "
                   f"{br(res['volume_N'] + res['volume_perdido_N'])} m3"
                   f" ({N} estaca{'s' if N > 1 else ''}), áreas zeradas")
    return "\n".join(out)
