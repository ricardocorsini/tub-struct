# -*- coding: utf-8 -*-
# Cópia portátil dos tubulões (14/11/2026): copiado de _apps\EstacaEscavada\estaca_sondagem.py, sem alterações no código.
"""
Sondagens SPT ao lado da estaca: perfis, tabela digitada, desenho das colunas e leitura da exportação
do GEOSPT (esquema geospt-detalhamento-estacas 1.0.0 e 1.1.0; ver PROMPT_GEOSPT_exportacao.md).

Cor do solo (1.1.0): texto do laudo, só informativo (a obra confere em campo se o solo escavado é o da
sondagem). Vai no rótulo da camada, como veio; nunca entra em cálculo.

O app não calcula geotecnia. Furos, sondagem média e envoltória chegam prontos (digitados na janela de
sondagens ou exportados pelo GEOSPT) e aqui só são desenhados, alinhados por cota com a estaca.

Convenção do GEOSPT, seguida no desenho: o NSPT de uma leitura vale para a camada da sua cota até 1 m
abaixo ("NSPT da cota = camada [cota, cota-1]"). Profundidades a partir da boca do furo, positivas para
baixo. Perfil de média e de envoltória: "cota_boca" é o topo do perfil (1 m acima da 1ª cota).
"""
import json, re

# Níveis da tabela de plotagem do escritório, só penas de 0,10 a 0,20 mm, um por cor (pedido de 09/10/2026)
NV_SOND = 208          # faixa de solos e divisas das camadas: marrom (15), 0,15
NV_SOND_GRAF = 239     # curva e pontos do NSPT, nível d'água: ciano (27), 0,15
NV_SOND_GRADE = 252    # eixo e grade do gráfico: cinza-claro (8), 0,10
NV_SOND_TXT = 216      # textos: preto (3), 0,20
NV_SOND_LIG = 210      # pontilhado das mudanças de camada até a estaca: verde (25), 0,10, pontilhado
NV_SOND_COTA = 221     # cota do pontilhado: vermelho (13), 0,20, como as cotas do desenho
# hachura por família: laranja (16) 0,15 | salmão (17) 0,15 | cinza (24) 0,10; linhas sempre contínuas (estilo 0)
NV_HACHURA = {"Granular": 206, "Intermediário": 250, "Coesivo": 214}
TIPOS = {"furo": "furo", "media": "sondagem média", "envoltoria": "envoltória inferior"}
NSPT_MAX = 50                                             # escala do gráfico (limite de cálculo do GEOSPT)
# Tabela 1.1 do GEOSPT (15 tipos de solo e a família de cada um)
SOLOS = {
    "Areia": "Granular", "Areia Siltosa": "Granular", "Areia Silto-Argilosa": "Granular",
    "Areia Argilo-Siltosa": "Granular", "Areia Argilosa": "Granular",
    "Silte Arenoso": "Intermediário", "Silte Areno-Argiloso": "Intermediário", "Silte": "Intermediário",
    "Silte Argilo-Arenoso": "Intermediário", "Silte Argiloso": "Intermediário",
    "Argila Arenosa": "Coesivo", "Argila Areno-Siltosa": "Coesivo", "Argila Silto-Arenosa": "Coesivo",
    "Argila Siltosa": "Coesivo", "Argila": "Coesivo",
}
FAMILIAS = ("Granular", "Intermediário", "Coesivo", "Outro")
CRITERIOS = {"impenetravel": "impenetrável", "solicitacao_contratante": "solicitação do contratante"}
# Coluna (cm de plotagem): números | gráfico 0-50 | faixa de solos | nomes das camadas
COL_NUM, COL_G0, COL_G1, COL_B0, COL_B1, COL_TXT, COL_LARG = 0.75, 0.9, 3.3, 3.55, 4.35, 4.45, 9.0
H_COL = 0.15
MAX_NOME = 27                                             # caracteres do nome da camada (cabe na coluna)
SUBMODOS = {"2.1_predominante": "2.1 PREDOMINANTE", "2.2_conservador": "2.2 CONSERVADOR", "2.3_dois_paralelos": "2.3 PARALELOS"}


def _num(v):
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", ".")
    return float(s) if s else None


def _texto(v):
    """Texto livre (cor do laudo): espaços extras removidos; None ou vazio viram ""."""
    return " ".join(str(v).split()) if v is not None else ""


def familia_do_solo(solo):
    """Família do GEOSPT pelo nome do solo; nomes fora da tabela pela 1ª palavra (Areia, Silte, Argila)."""
    if solo in SOLOS:
        return SOLOS[solo]
    s = solo.strip().lower()
    for pref, fam in (("areia", "Granular"), ("silte", "Intermediário"), ("argila", "Coesivo")):
        if s.startswith(pref):
            return fam
    return "Outro" if s else ""


def normalizar_perfil(d):
    """Perfil com campos e tipos garantidos. ValueError com o nome do perfil."""
    nome = str(d.get("nome") or "").strip() or "SP"
    tipo = d.get("tipo") if d.get("tipo") in TIPOS else "furo"
    cb = _num(d.get("cota_boca"))
    if cb is None:
        raise ValueError(f"Sondagem {nome}: informe a cota da boca (ou do topo do perfil).")
    leituras = []
    for l in d.get("leituras") or []:
        prof, nspt = _num(l.get("prof")), _num(l.get("nspt"))
        if prof is None or nspt is None or prof <= 0 or nspt < 0:
            raise ValueError(f"Sondagem {nome}: leitura inválida ({l.get('prof')}; {l.get('nspt')}).")
        solo = str(l.get("solo") or "").strip()
        fam = str(l.get("familia") or "").strip() or familia_do_solo(solo)
        leituras.append(dict(prof=prof, nspt=int(round(nspt)), imp=bool(l.get("imp")), solo=solo, familia=fam,
                             het=bool(l.get("het")), det=str(l.get("det") or "").strip(),
                             cor=_texto(l.get("cor")), cor_det=_texto(l.get("cor_det"))))
    leituras.sort(key=lambda l: l["prof"])
    for a, b in zip(leituras, leituras[1:]):
        if abs(a["prof"] - b["prof"]) < 1e-6:
            raise ValueError(f"Sondagem {nome}: profundidade {a['prof']:g} m repetida.")
    return dict(nome=nome, tipo=tipo, cota_boca=cb, prof_final=_num(d.get("prof_final")),
                na_ini=_num(d.get("na_ini")), na_fim=_num(d.get("na_fim")), criterio=str(d.get("criterio") or ""),
                desenhar=bool(d.get("desenhar", True)), obs=str(d.get("obs") or ""), leituras=leituras)


def ler_tabela(texto):
    """Uma leitura por linha: 'profundidade; NSPT; solo; família; cor; het'. NSPT com '>' ou '>=' antes (">=50")
    marca impenetrável. Família vazia: pela tabela de solos do GEOSPT. Cor (opcional): texto do laudo; 'het' e
    'imp' depois da família são marcas. Devolve (leituras, erros)."""
    leituras, erros = [], []
    for n, lin in enumerate(texto.splitlines(), 1):
        if not lin.strip() or lin.strip().startswith("#"):
            continue
        c = [x.strip() for x in re.split(r"[;\t]", lin)]
        try:
            prof = _num(c[0])
            ns = c[1] if len(c) > 1 else ""
            imp = bool(re.match(r"^(>=|≥|>)", ns))
            nspt = _num(re.sub(r"^(>=|≥|>)", "", ns))
            if prof is None or nspt is None:
                raise ValueError
        except (ValueError, IndexError):
            erros.append(f"linha {n}: use 'profundidade; NSPT; solo' ({lin.strip()})")
            continue
        resto = [x.lower() for x in c[4:]]
        cor = next((x for x in c[4:] if x and x.lower() not in ("het", "imp")), "")
        fam = c[3] if len(c) > 3 else ""
        if fam.lower() in ("het", "imp"):
            resto.append(fam.lower())
            fam = ""
        if fam and fam not in FAMILIAS:
            erros.append(f"linha {n}: família '{fam}' (use {', '.join(FAMILIAS)})")
            fam = ""
        leituras.append(dict(prof=prof, nspt=nspt, imp=imp or "imp" in resto, solo=c[2] if len(c) > 2 else "",
                             familia=fam, het="het" in resto, cor=cor))
    return leituras, erros


def tabela_texto(leituras):
    def f(v):
        return f"{v:g}".replace(".", ",")
    out = []
    for l in leituras:
        s = f"{f(l['prof'])}; {'>=' if l['imp'] else ''}{l['nspt']}; {l['solo']}; {l['familia']}"
        out.append(s + (f"; {l['cor']}" if l.get("cor") else "") + ("; het" if l.get("het") else ""))
    return "\n".join(out)


def cota_topo(pf):
    """Topo do perfil: a boca, num furo; a 1ª cota, na média e na envoltória (não há trecho sem SPT)."""
    if pf["tipo"] == "furo" or not pf["leituras"]:
        return pf["cota_boca"]
    return pf["cota_boca"] - pf["leituras"][0]["prof"]


def cota_fim(pf):
    """Cota do fim do perfil: a do limite da sondagem, num furo com profundidade final além da última leitura;
    senão, 1 m abaixo da última leitura (camada da leitura, convenção do GEOSPT)."""
    if not pf["leituras"]:
        return pf["cota_boca"]
    ult = pf["leituras"][-1]["prof"]
    if pf["tipo"] == "furo" and pf["prof_final"] and pf["prof_final"] > ult + 0.01:
        return pf["cota_boca"] - pf["prof_final"]
    return pf["cota_boca"] - ult - 1.0


def intervalos(pf):
    """(topo, base) em cota da camada de cada leitura: da sua cota até a cota da leitura seguinte (1 m nos furos
    com leitura a cada metro) e, na última, até o fim do perfil."""
    boca, fim, L = pf["cota_boca"], cota_fim(pf), pf["leituras"]
    return [(boca - l["prof"], boca - L[i + 1]["prof"] if i + 1 < len(L) else fim) for i, l in enumerate(L)]


def rotulo(pf, l):
    """(solo, cor) que o desenho escreve na camada da leitura. Cota heterogênea da média: os solos e as cores
    por família ("* C: ... | G: ...", corDetalhe do GEOSPT, para não esconder a variação entre furos);
    envoltória: o furo de origem entre parênteses e a cor da mesma leitura; furo e média: solo e cor."""
    if l["het"]:
        return f"* {l['det'] or l['solo']}", l["cor_det"] or l["cor"]
    solo = l["solo"]
    if pf["tipo"] == "envoltoria" and l["det"]:
        solo += f" ({l['det']})"
    return solo, l["cor"]


def camadas(pf):
    """Camadas da faixa de solos: [{topo, base (cotas), solo, familia, het, det, rot, cor}], com as leituras
    vizinhas de mesmo rótulo (solo e cor) juntas; o trecho entre a boca e a 1ª leitura sai como 'sem SPT'
    (solo vazio)."""
    if not pf["leituras"]:
        return []
    out, ints = [], intervalos(pf)
    if pf["tipo"] == "furo" and pf["cota_boca"] - ints[0][0] > 0.01:
        out.append(dict(topo=pf["cota_boca"], base=ints[0][0], solo="", familia="", het=False, det="", rot="", cor=""))
    for l, (topo, base) in zip(pf["leituras"], ints):
        if base >= topo - 1e-6:
            continue
        rot, cor = rotulo(pf, l)
        ch = (rot, cor, l["familia"], l["het"])
        if out and out[-1]["solo"] and abs(out[-1]["base"] - topo) < 1e-6 and \
                (out[-1]["rot"], out[-1]["cor"], out[-1]["familia"], out[-1]["het"]) == ch:
            out[-1]["base"] = base
        else:
            out.append(dict(topo=topo, base=base, solo=l["solo"], familia=l["familia"], het=l["het"], det=l["det"],
                            rot=rot, cor=cor))
    return out


# --------------------------------------------------------------------------- desenho
def _hachura(m, x0, y0, x1, y1, familia, P):
    """Padrão da família dentro do retângulo: diagonais (coesivo), pontos (granular), traços (intermediário),
    cada família na sua cor (nível)."""
    passo, nv = P(0.2), NV_HACHURA.get(familia, NV_SOND)
    if familia == "Coesivo":
        w, h = x1 - x0, y1 - y0
        t = -h + passo / 2
        while t < w:
            v0, v1 = max(0.0, -t), min(h, w - t)
            if v1 - v0 > 1e-6:
                m.linha(x0 + t + v0, y0 + v0, x0 + t + v1, y0 + v1, nv, estilo=0)
            t += passo
    elif familia == "Granular":
        j, y = 0, y0 + passo / 2
        while y < y1:
            x = x0 + (passo / 2 if j % 2 else passo)
            while x < x1 - P(0.03):
                m.linha(x, y, x + P(0.03), y, nv, estilo=0)
                x += passo
            y += passo
            j += 1
    elif familia == "Intermediário":
        y = y0 + passo / 2
        while y < y1:
            x = x0 + P(0.06)
            while x < x1 - P(0.06):
                m.linha(x, y, min(x + P(0.14), x1 - P(0.06)), y, nv, estilo=0)
                x += P(0.24)
            y += passo


def _coluna(m, pf, xc, yv, y_tit, P):
    from estaca_core import br, cota
    h = P(H_COL)
    xn, gx0, gx1, bx0, bx1, xt = (xc + P(v) for v in (COL_NUM, COL_G0, COL_G1, COL_B0, COL_B1, COL_TXT))
    gx = lambda n: gx0 + (gx1 - gx0) * min(n, NSPT_MAX) / NSPT_MAX
    boca, fim = pf["cota_boca"], cota_fim(pf)
    ytop, ybot = yv(cota_topo(pf)), yv(fim)
    sm = SUBMODOS.get(pf["obs"], pf["obs"].replace("_", " ").upper())
    sub = {"furo": f"BOCA {cota(boca)}", "media": "SONDAGEM MÉDIA" + (f" ({sm})" if sm else ""),
           "envoltoria": "ENVOLTÓRIA INFERIOR"}[pf["tipo"]]
    m.texto(xc, y_tit, pf["nome"].upper(), P(0.25), NV_SOND_TXT)
    m.texto(xc, y_tit - P(0.4), sub, P(0.18), NV_SOND_TXT)
    # gráfico: eixo, grade de 10 em 10 e escala
    m.linha(gx0, ytop, gx0, ybot, NV_SOND_GRADE, estilo=0)
    for n in range(0, NSPT_MAX + 1, 10):
        if n:
            m.linha(gx(n), ytop, gx(n), ybot, NV_SOND_GRADE, estilo=2)
        m.texto(gx(n), ytop + P(0.1), str(n), P(0.12), NV_SOND_TXT, alin="centro")
    m.texto(xn, ytop + P(0.1), "NSPT", P(0.12), NV_SOND_TXT, alin="dir")
    # faixa de solos
    m.poli([(bx0, ytop), (bx1, ytop), (bx1, ybot), (bx0, ybot), (bx0, ytop)], NV_SOND, estilo=0)
    for cam in camadas(pf):
        y1, y0 = yv(cam["topo"]), yv(cam["base"])
        m.linha(bx0, y0, bx1, y0, NV_SOND, estilo=0)
        if not cam["solo"]:
            if y1 - y0 >= 1.2 * h:
                m.texto(xt, (y0 + y1) / 2 - h / 2, "(SEM SPT)", P(0.12), NV_SOND_TXT)
            continue
        _hachura(m, bx0, y0, bx1, y1, cam["familia"], P)
        if y1 - y0 >= 1.2 * h:
            nome, cor = cam["rot"].upper(), cam["cor"].upper()
            corta = lambda s: s if len(s) <= MAX_NOME else s[:MAX_NOME - 3].rstrip(" |,") + "..."
            ym = (y0 + y1) / 2
            if cor and y1 - y0 >= 2.6 * h:          # solo e, embaixo, a cor do laudo
                m.texto(xt, ym + 0.15 * h, corta(nome), h, NV_SOND_TXT)
                m.texto(xt, ym - 1.25 * h, corta(cor), h, NV_SOND_TXT)
            else:
                m.texto(xt, ym - h / 2, corta(f"{nome}, {cor}" if cor else nome), h, NV_SOND_TXT)
    # NSPT de cada leitura (número e gráfico, no meio da camada da leitura)
    pts = []
    for l, (topo, base) in zip(pf["leituras"], intervalos(pf)):
        ym = yv((topo + base) / 2)
        txt = (">=" if l["imp"] else "") + str(l["nspt"]) + ("*" if l["het"] else "")
        m.texto(xn, ym - h / 2, txt, h, NV_SOND_TXT, alin="dir")
        pts.append((gx(l["nspt"]), ym))
        m.circulo(gx(l["nspt"]), ym, P(0.035), NV_SOND_GRAF, estilo=0)
    if len(pts) > 1:
        m.poli(pts, NV_SOND_GRAF, estilo=0)
    # nível d'água (inicial e final)
    nas = [(pf["na_ini"], "NA")]
    if pf["na_fim"] is not None and (pf["na_ini"] is None or abs(pf["na_fim"] - pf["na_ini"]) > 0.05):
        nas.append((pf["na_fim"], "NA FINAL"))
    for prof, rot in nas:
        if prof is None:
            continue
        y, a = yv(boca - prof), P(0.1)
        m.linha(bx0 - P(0.25), y, bx0 + P(0.25), y, NV_SOND_GRAF, estilo=0)
        m.poli([(bx0, y), (bx0 - a, y + 1.6 * a), (bx0 + a, y + 1.6 * a), (bx0, y)], NV_SOND_GRAF, estilo=0)
        m.texto(bx0 - P(0.3), y + P(0.05), f"{rot} {br(prof)}", P(0.12), NV_SOND_GRAF, alin="dir")
    # fim do perfil e nota das cotas heterogêneas
    yb = ybot - P(0.35)
    if pf["tipo"] == "furo":
        txt = "IMPENETRÁVEL" if pf["criterio"] == "impenetravel" else "LIMITE DA SONDAGEM"
        m.texto(bx0, yb, f"{txt} {cota(fim)}", P(0.15), NV_SOND_TXT)
        yb -= P(0.3)
    if any(l["het"] for l in pf["leituras"]):
        m.texto(xc, yb, "* COTA HETEROGÊNEA (FAMÍLIAS DIFERENTES ENTRE FUROS)", P(0.12), NV_SOND_TXT)


def desenhar_colunas(m, perfis, cota_arr, x_dir, face=None):
    """Colunas dos perfis à esquerda da estaca, da direita para a esquerda a partir de x_dir (o 1º perfil
    fica junto da estaca), na escala da elevação e alinhadas por cota (y = 0 na cota de arrasamento).
    face(y): x da face da estaca (ou do bloco) na altura y. Com ela, cada mudança de camada do 1º perfil
    (boca, trocas de solo e fim) vai em pontilhado da faixa de solos até a estaca, com a cota escrita junto
    da coluna. Devolve a largura ocupada (cm do desenho)."""
    from estaca_core import cota
    P = m.P
    yv = lambda c: (c - cota_arr) * 100.0
    y_tit = yv(max(cota_topo(pf) for pf in perfis)) + P(1.2)
    for i, pf in enumerate(perfis):
        _coluna(m, pf, x_dir - (i + 1) * P(COL_LARG), yv, y_tit, P)
    if face and perfis:
        x_faixa = x_dir - P(COL_LARG) + P(COL_B1)
        cotas = sorted({round(c, 3) for cam in camadas(perfis[0]) for c in (cam["topo"], cam["base"])}, reverse=True)
        for c in cotas:
            y = yv(c)
            m.linha(x_faixa, y, face(y) - m.P(0.15), y, NV_SOND_LIG, estilo=2)   # folga até a face (como as cotas)
            m.texto(x_dir + P(0.1), y + P(0.05), cota(c), P(H_COL), NV_SOND_COTA)
    return len(perfis) * P(COL_LARG)


# --------------------------------------------------------------------------- exportação do GEOSPT
ESQUEMA = "geospt-detalhamento-estacas"


def ler_exportacao(caminho):
    """Lê o JSON 'Exportar para detalhamento de estacas' do GEOSPT. ValueError se não for esse arquivo."""
    with open(caminho, encoding="utf-8") as fp:
        d = json.load(fp)
    if not isinstance(d, dict) or d.get("_schema") != ESQUEMA:
        esq = d.get("_schema") if isinstance(d, dict) else None
        raise ValueError(f"O arquivo não é a exportação do GEOSPT para detalhamento de estacas "
                         f"(_schema '{esq}', esperado '{ESQUEMA}'). No GEOSPT, use Aba 7 > "
                         f"'Exportar para detalhamento de estacas (JSON)'.")
    if str(d.get("_schemaVersao", "")).split(".")[0] != "1":
        raise ValueError(f"Versão {d.get('_schemaVersao')} da exportação do GEOSPT não suportada: este app lê as "
                         f"versões 1.x (1.0.0 e 1.1.0, com a cor do solo). Atualize o app de estacas.")
    if not d.get("estacas"):
        raise ValueError("A exportação do GEOSPT não tem estacas cadastradas.")
    return d


def listar_estacas(d):
    """Resumo de cada estaca da exportação, para a escolha na importação."""
    out = []
    for e in d["estacas"]:
        dist = next((s["distancia_m"] for s in e.get("sondagensPorDistancia") or [] if s["nome"] == e.get("sondagemMaisProxima")), None)
        out.append(dict(nome=e["nome"], tipo=e.get("tipoEstaca"), dimensao_cm=round(e["dimensao_m"] * 100, 1) if e.get("dimensao_m") else None,
                        cota_arr=e.get("cotaArrasamento_m"), mais_proxima=e.get("sondagemMaisProxima"), distancia=dist,
                        dominio=e.get("dominioNome"), furos=e.get("furosConsiderados") or [],
                        ponta=e.get("cotaPontaSugerida_m") or {}, avisos=e.get("avisos") or []))
    return out


def _perfil_furo(s, delta):
    return normalizar_perfil(dict(
        nome=s["nome"], tipo="furo", cota_boca=s["cotaBoca_m"] + delta, prof_final=s.get("profundidadeFinal_m"),
        na_ini=s.get("naInicial_m"), na_fim=s.get("naFinal_m"), criterio=s.get("criterioParalisacao") or "",
        leituras=[dict(prof=l["profundidade_m"], nspt=l["nspt_real"], imp=l.get("impenetravel", False),
                       solo=l.get("solo") or "", familia=l.get("familia") or "", cor=l.get("cor"))   # cor: 1.1.0
                  for l in s.get("leituras") or []]))


def _perfil_cotas(nome, tipo, cams, delta, obs="", det=None):
    topo = max(c["cota_m"] for c in cams) + 1.0
    return normalizar_perfil(dict(
        nome=nome, tipo=tipo, cota_boca=topo + delta, obs=obs,
        leituras=[dict(prof=round(topo - c["cota_m"], 3), nspt=c["nspt"], imp=c.get("impenetravel", False),
                       solo=c.get("solo") or "", familia=c.get("familia") or "", het=bool(c.get("heterogeneo")),
                       det=(det(c) if det else c.get("soloDetalhe")) or "",
                       cor=c.get("cor"), cor_det=c.get("corDetalhe")) for c in cams]))         # cor: 1.1.0


def importar_estaca(d, nome, delta=0.0, furos=None, media=True, envoltoria=True):
    """Perfis e dados de uma estaca da exportação. furos=None: só o mais próximo. delta: somado a todas as
    cotas (referencial do projeto = referencial do GEOSPT + delta)."""
    e = next(x for x in d["estacas"] if x["nome"] == nome)
    if furos is None:
        furos = [e["sondagemMaisProxima"]] if e.get("sondagemMaisProxima") else []
    sond = {s["nome"]: s for s in d.get("sondagens") or []}
    perfis = [_perfil_furo(sond[n], delta) for n in furos if n in sond]
    pr = e.get("perfis") or {}
    md = pr.get("media") or {}
    if media and md.get("camadas"):
        perfis.append(_perfil_cotas("Média", "media", md["camadas"], delta, obs=md.get("submodo") or ""))
    if envoltoria and pr.get("envoltoria"):
        perfis.append(_perfil_cotas("Envoltória", "envoltoria", pr["envoltoria"], delta, det=lambda c: c.get("furo")))
    arr = e.get("cotaArrasamento_m")
    te = str(e.get("tipoEstaca") or "").lower()
    tipo_estaca = "raiz" if "raiz" in te else ("hélice contínua" if "helice" in te or "hélice" in te
                                                else ("escavada" if "escavada" in te else None))
    estaca = dict(tipo=e["nome"], tipo_estaca=tipo_estaca, diametro=round(e["dimensao_m"] * 100, 1) if e.get("dimensao_m") else None,
                  cota_arrasamento=arr + delta if arr is not None else None,
                  ponta={k: v + delta for k, v in (e.get("cotaPontaSugerida_m") or {}).items() if v is not None})
    avisos = list(e.get("avisos") or []) + list(d.get("avisos") or [])
    if not e.get("sondagemMaisProxima"):
        avisos.append(f"Estaca {nome}: o GEOSPT não indicou a sondagem mais próxima (faltam coordenadas).")
    return dict(estaca=estaca, perfis=perfis, avisos=avisos)
