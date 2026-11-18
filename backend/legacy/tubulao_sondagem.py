# -*- coding: utf-8 -*-
"""
Sondagens SPT no mesmo sistema do GEOSPT (github.com/itanervale/GEOSPT-APP, motor geospt-engine.js 2.0.7):
cadastro dos furos, compatibilização por cota absoluta, sondagem média (submodos 2.1, 2.2 e 2.3) e envoltória
inferior (mínima). Lê e grava o arquivo da obra do GEOSPT ("geospt-obra" 2.x) e lê a exportação
"geospt-detalhamento-estacas" (1.x), da qual usa só os furos (média e envoltória são recalculadas aqui).

Regras do motor, seguidas à risca (17/10/2026, leitura do código-fonte):
- cota da leitura = cota da boca - profundidade; grade de cotas inteiras de round(maior cota lida) (round do JS:
  meio para cima) até floor(menor cota lida), passo -1;
- em cada cota, cada furo entra com a leitura mais próxima dentro de +-janela (0,50 m, limite inclusivo; empate:
  a primeira na ordem do furo); furo sem leitura na janela não conta em nFuros;
- família predominante pela contagem de furos; empate entre as duas mais frequentes = cota heterogênea;
- média = floor da média do nspt_calculo (= min(nspt_real, 50)) dos furos da família predominante; em cota
  heterogênea, uma média por família; o nspt_real e a marca de impenetrável não entram;
- solo da cota = moda dos solos da família predominante (empate: o primeiro a chegar ao máximo, na ordem dos
  furos); heterogênea: "C: <moda coesiva> | G: <moda granular>", com "—" na família sem furo;
- envoltória = menor nspt_calculo (empate: o primeiro furo); solo, família, impenetrável e cor do mesmo furo;
- 2.1: cota heterogênea bloqueada (sem camada); 2.2: a família de menor média (empate: Coesivo, Granular,
  Intermediário), com solo canônico Argila, Areia ou Silte; 2.3: três perfis paralelos, um por família;
- cor (src/domain/cores.js): só informativa; agrupada sem maiúsculas, acentos e espaços extras; média = moda das
  cores dos furos da família predominante ("cor (n) | cor (n)" no detalhe quando há mais de uma); heterogênea:
  "C: ... | G: ... | I: ...".
Convenção de camadas: o NSPT da cota c vale para a camada [c, c - 1].
"""
import json, math, unicodedata, datetime

JANELA_PADRAO = 0.50
NSPT_LIMITE = 50
SUBMODOS = ("2.1_predominante", "2.2_conservador", "2.3_dois_paralelos")
FAMILIAS = ("Coesivo", "Granular", "Intermediário")
SIGLA = {"Coesivo": "C", "Granular": "G", "Intermediário": "I"}
CANONICO = {"Coesivo": "Argila", "Granular": "Areia", "Intermediário": "Silte"}
# Tabela 1.1 do GEOSPT: os 15 tipos de solo (código e família)
SOLOS = {
    "Areia": (11, "Granular"), "Areia Siltosa": (12, "Granular"), "Areia Silto-Argilosa": (121, "Granular"),
    "Areia Argilo-Siltosa": (131, "Granular"), "Areia Argilosa": (13, "Granular"),
    "Silte Arenoso": (211, "Intermediário"), "Silte Areno-Argiloso": (212, "Intermediário"), "Silte": (2, "Intermediário"),
    "Silte Argilo-Arenoso": (232, "Intermediário"), "Silte Argiloso": (23, "Intermediário"),
    "Argila Arenosa": (31, "Coesivo"), "Argila Areno-Siltosa": (312, "Coesivo"), "Argila Silto-Arenosa": (321, "Coesivo"),
    "Argila Siltosa": (32, "Coesivo"), "Argila": (3, "Coesivo"),
}
CRITERIOS = {"impenetravel": "impenetrável", "solicitacao_contratante": "solicitação do contratante",
             "outro": "outro"}


def js_round(x):
    """Math.round do JavaScript (meio para cima, também nos negativos)."""
    return math.floor(x + 0.5)


def familia_do_solo(solo):
    """Família pela tabela do GEOSPT; nome fora da tabela pela 1ª palavra (Areia, Silte, Argila)."""
    if solo in SOLOS:
        return SOLOS[solo][1]
    s = (solo or "").strip().lower()
    for pref, fam in (("areia", "Granular"), ("silte", "Intermediário"), ("argila", "Coesivo")):
        if s.startswith(pref):
            return fam
    return ""


def _num(v):
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", ".")
    return float(s) if s else None


def limpar_cor(cor):
    if cor is None:
        return None
    t = " ".join(str(cor).split())
    return t or None


def chave_cor(cor):
    t = limpar_cor(cor)
    if t is None:
        return None
    t = unicodedata.normalize("NFD", t)
    return "".join(ch for ch in t if unicodedata.category(ch) != "Mn").lower()


def resumir_cores(cores):
    """Moda das cores (empate: a primeira a chegar) e o detalhe "cor (n) | cor (n)"."""
    grupos = {}
    for c in cores:
        k = chave_cor(c)
        if k is None:
            continue
        if k not in grupos:
            grupos[k] = dict(cor=limpar_cor(c), n=0, ordem=len(grupos))
        grupos[k]["n"] += 1
    if not grupos:
        return dict(cor=None, detalhe=None)
    g = sorted(grupos.values(), key=lambda x: (-x["n"], x["ordem"]))
    det = g[0]["cor"] if len(g) == 1 else " | ".join(f"{x['cor']} ({x['n']})" for x in g)
    return dict(cor=g[0]["cor"], detalhe=det)


def _moda(valores):
    """Moda dos valores não nulos; empate: o primeiro a atingir a contagem máxima, na ordem."""
    cont, melhor, nmax = {}, None, 0
    for v in valores:
        if v is None or v == "":
            continue
        cont[v] = cont.get(v, 0) + 1
        if cont[v] > nmax:
            melhor, nmax = v, cont[v]
    return melhor


# --------------------------------------------------------------------------------------------- cadastro
def normalizar_leitura(l, nome, i):
    prof = _num(l.get("profundidade_m", l.get("prof")))
    nr = _num(l.get("nspt_real", l.get("nspt")))
    if prof is None or nr is None or prof <= 0 or nr < 0:
        raise ValueError(f"Sondagem {nome}, leitura {i + 1}: profundidade e NSPT válidos são obrigatórios.")
    imp = bool(l.get("impenetravel", l.get("imp", False)))
    if nr > NSPT_LIMITE and not imp:
        raise ValueError(f"Sondagem {nome}, {prof:g} m: NSPT {nr:g} acima de {NSPT_LIMITE} exige a marca de impenetrável "
                         "(regra do GEOSPT).")
    nc = _num(l.get("nspt_calculo"))
    nc = min(nr, NSPT_LIMITE) if nc is None else nc
    solo = str(l.get("solo") or "").strip()
    fam = str(l.get("familia") or "").strip() or familia_do_solo(solo)
    return dict(profundidade_m=prof, nspt_real=int(round(nr)), nspt_calculo=int(round(nc)), impenetravel=imp,
                solo=solo, familia=fam, cor=limpar_cor(l.get("cor")))


def normalizar_furo(nome, f):
    cota = _num(f.get("cotaTopo_m", f.get("cotaBoca_m", f.get("cota_boca"))))
    if cota is None:
        raise ValueError(f"Sondagem {nome}: informe a cota da boca do furo.")
    ls = [normalizar_leitura(l, nome, i) for i, l in enumerate(f.get("leituras") or [])]
    ls.sort(key=lambda l: l["profundidade_m"])
    for a, b in zip(ls, ls[1:]):
        if abs(a["profundidade_m"] - b["profundidade_m"]) < 1e-6:
            raise ValueError(f"Sondagem {nome}: profundidade {a['profundidade_m']:g} m repetida.")
    co = f.get("coordenadas") or {}
    pf = _num(f.get("profundidadeFinal_m"))
    return dict(cotaTopo_m=cota, profundidadeFinal_m=pf if pf is not None else (ls[-1]["profundidade_m"] if ls else 0.0),
                criterioParalisacao=f.get("criterioParalisacao") or "", naInicial_m=_num(f.get("naInicial_m")),
                naFinal_m=_num(f.get("naFinal_m")), dominioGeotecnico=f.get("dominioGeotecnico"),
                coordenadas=dict(x=_num(co.get("x")) or 0.0, y=_num(co.get("y")) or 0.0), leituras=ls)


def normalizar_sondagens(d):
    """Aceita {nome: furo} (geospt-obra), [{nome, ...}] (exportação de detalhamento) ou o JSON inteiro."""
    if isinstance(d, dict) and "obra" in d:
        d = d["obra"].get("sondagens", {})
    elif isinstance(d, dict) and "sondagens" in d:
        d = d["sondagens"]
    if isinstance(d, list):
        d = {s["nome"]: s for s in d}
    return {str(n): normalizar_furo(str(n), f) for n, f in (d or {}).items()}


def ler_geospt(caminho):
    """Furos de um arquivo do GEOSPT (obra 2.x ou exportação de detalhamento 1.x). Devolve (sondagens, info)."""
    d = json.load(open(caminho, encoding="utf-8"))
    esq = d.get("_schema") or d.get("schema") or ""
    ver = str(d.get("_schemaVersao") or d.get("versao") or "")
    if esq == "geospt-obra":
        if not ver.startswith("2."):
            raise ValueError(f"Arquivo do GEOSPT versão {ver}: o app lê a 2.x.")
        ident = d["obra"].get("identificacao", {})
        return normalizar_sondagens(d["obra"]["sondagens"]), dict(esquema=esq, versao=ver, obra=ident.get("nome", ""),
                                                                   local=ident.get("localizacao", ""))
    if esq == "geospt-detalhamento-estacas":
        if ver.startswith("2."):
            raise ValueError(f"Exportação do GEOSPT versão {ver}: o app lê a 1.x.")
        ob = d.get("obra", {})
        return normalizar_sondagens(d["sondagens"]), dict(esquema=esq, versao=ver, obra=ob.get("nome", ""),
                                                           local=ob.get("localizacao", ""))
    raise ValueError(f"{caminho}: não é um arquivo do GEOSPT (esquema '{esq}').")


def gravar_geospt_obra(sondagens, caminho, nome_obra="", local=""):
    """Grava os furos no formato da obra do GEOSPT (2.0.7), para abrir no GEOSPT."""
    agora = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    d = {"_schema": "geospt-obra", "_schemaVersao": "2.0.7", "_engineVersao": "2.0.7", "_exportadoEm": agora,
         "obra": {"identificacao": {"nome": nome_obra, "localizacao": local,
                                    "dataCadastro": datetime.date.today().isoformat(), "sistemaCoordenadas": "xy_local",
                                    "responsavelTecnico": "", "observacoes": "Gravado pelo app de tubulões curtos."},
                  "sondagens": {n: {k: v for k, v in f.items()} for n, f in sondagens.items()}}}
    with open(caminho, "w", encoding="utf-8") as fp:
        json.dump(d, fp, ensure_ascii=False, indent=2)
    return caminho


# ---------------------------------------------------------------------------------- compatibilização
def compatibilizar(sondagens, nomes=None, janela=JANELA_PADRAO):
    """Uma linha por cota inteira, como engine.compatibilizar do GEOSPT."""
    nomes = [n for n in (nomes or list(sondagens)) if n in sondagens]
    if not nomes:
        raise ValueError("Nenhuma sondagem selecionada.")
    cotas = {n: [(sondagens[n]["cotaTopo_m"] - l["profundidade_m"], l) for l in sondagens[n]["leituras"]] for n in nomes}
    todas = [c for n in nomes for c, _ in cotas[n]]
    if not todas:
        raise ValueError("As sondagens selecionadas não têm leituras.")
    topo, base = js_round(max(todas)), math.floor(min(todas))
    linhas, heterogeneas, subamostradas, contagem_critico = [], [], [], {n: 0 for n in nomes}
    for cota in range(topo, base - 1, -1):
        esc = {}
        for n in nomes:
            cand = [(abs(c - cota), c, l) for c, l in cotas[n] if abs(c - cota) <= janela + 1e-9]
            if cand:
                cand.sort(key=lambda t: t[0])                  # estável: empate fica com a 1ª da ordem do furo
                esc[n] = (cand[0][1], cand[0][2])
        if not esc:
            continue
        cont = {}
        for n in esc:
            fam = esc[n][1]["familia"]
            if fam:
                cont[fam] = cont.get(fam, 0) + 1
        ordem = sorted(cont.items(), key=lambda kv: -kv[1])
        het = len(ordem) >= 2 and ordem[0][1] == ordem[1][1]
        fam_pred = None if not ordem else ("HETEROGENEO" if het else ordem[0][0])
        baldes = {f: [] for f in FAMILIAS}
        for n in esc:
            f = esc[n][1]["familia"]
            if f in baldes:
                baldes[f].append(esc[n][1]["nspt_calculo"])
        med = {f: (math.floor(sum(v) / len(v)) if v else None) for f, v in baldes.items()}
        if het:
            media = dict(familiaPredominante=None, coesivo=med["Coesivo"], granular=med["Granular"],
                         intermediario=med["Intermediário"])
            mc = _moda(esc[n][1]["solo"] for n in esc if esc[n][1]["familia"] == "Coesivo")
            mg = _moda(esc[n][1]["solo"] for n in esc if esc[n][1]["familia"] == "Granular")
            solo_pred = f"C: {mc or '—'} | G: {mg or '—'}"
            heterogeneas.append(cota)
        else:
            media = dict(familiaPredominante=med.get(fam_pred) if fam_pred else None, coesivo=None, granular=None,
                         intermediario=None)
            solo_pred = _moda(esc[n][1]["solo"] for n in esc if esc[n][1]["familia"] == fam_pred) or "—"
        env_n, env_furo = math.inf, None
        for n in nomes:
            if n in esc and esc[n][1]["nspt_calculo"] < env_n:
                env_n, env_furo = esc[n][1]["nspt_calculo"], n
        le = esc[env_furo][1]
        contagem_critico[env_furo] += 1
        envolt = dict(nspt=env_n, nspt_real=le["nspt_real"], impenetravel=le["impenetravel"], furo=env_furo,
                      solo=le["solo"], familia=le["familia"], cor=le["cor"])
        # cores (src/domain/cores.js)
        por_fam = {f: resumir_cores([esc[n][1]["cor"] for n in esc if esc[n][1]["familia"] == f]) for f in FAMILIAS}
        if het:
            partes = [f"{SIGLA[f]}: {por_fam[f]['cor'] or '—'}" for f in FAMILIAS if baldes[f]]
            cor_pred, cor_det = None, (" | ".join(partes) if any(por_fam[f]["cor"] for f in FAMILIAS if baldes[f]) else None)
        elif fam_pred in por_fam:
            cor_pred, cor_det = por_fam[fam_pred]["cor"], por_fam[fam_pred]["detalhe"]
        else:
            cor_pred = cor_det = None
        if len(esc) < len(nomes) / 2:
            subamostradas.append(cota)
        linhas.append(dict(
            cotaRef_m=cota, profRef_m=topo - cota + 1, nFuros=len(esc),
            nsptPorSondagem={n: (esc[n][1]["nspt_calculo"] if n in esc else None) for n in nomes},
            nsptRealPorSondagem={n: (esc[n][1]["nspt_real"] if n in esc else None) for n in nomes},
            impenetravelPorSondagem={n: (esc[n][1]["impenetravel"] if n in esc else None) for n in nomes},
            soloPorSondagem={n: (esc[n][1]["solo"] if n in esc else None) for n in nomes},
            familiaPorSondagem={n: (esc[n][1]["familia"] if n in esc else None) for n in nomes},
            corPorSondagem={n: (esc[n][1]["cor"] if n in esc else None) for n in nomes},
            cotaLeituraPorSondagem={n: (esc[n][0] if n in esc else None) for n in nomes},
            familiaPred=fam_pred, soloPred=solo_pred, heterogeneo=het, envoltoria=envolt, media=media,
            corPred=cor_pred, corDetalhe=cor_det))
    furo_critico = max(contagem_critico, key=lambda n: contagem_critico[n]) if linhas else None
    return dict(linhas=linhas, metadata=dict(nomesSondagens=nomes, janela_m=janela, cotaTopoGrade=topo, cotaBaseGrade=base,
                                             cotasHeterogeneas_m=heterogeneas, cotasSubamostradas_m=subamostradas,
                                             furoCritico=furo_critico, contagemFuroCritico=contagem_critico))


def perfil_medio(comp, submodo="2.2_conservador"):
    """Sondagem média como engine.montarPerfilMedio. 2.1/2.2: {camadas, avisos, bloqueadas}; 2.3: {coesivo,
    granular, intermediario, avisos}."""
    if submodo not in SUBMODOS:
        raise ValueError(f"Submodo inválido: {submodo}")
    if not comp["linhas"]:
        raise ValueError("Compatibilização vazia.")
    avisos, bloqueadas = [], []
    if submodo == "2.3_dois_paralelos":
        perf = {f: [] for f in FAMILIAS}
        for c in comp["linhas"]:
            m = c["media"]
            ef = {"Coesivo": m["coesivo"], "Granular": m["granular"], "Intermediário": m["intermediario"]}
            if not c["heterogeneo"] and m["familiaPredominante"] is not None and c["familiaPred"] in ef:
                ef[c["familiaPred"]] = m["familiaPredominante"]
            for f in FAMILIAS:
                if ef[f] is None:
                    avisos.append(dict(cota_m=c["cotaRef_m"], tipo="camada_sem_dado", familia=f))
                    continue
                perf[f].append(dict(cota_m=c["cotaRef_m"], nspt=math.floor(ef[f]), nspt_real=ef[f], impenetravel=False,
                                    solo=CANONICO[f] if c["heterogeneo"] else c["soloPred"], familia=f,
                                    heterogeneo=c["heterogeneo"], soloDetalhe=c["soloPred"], nFuros=c["nFuros"],
                                    origem=f"media_familia_{ {'Coesivo': 'coesiva', 'Granular': 'granular', 'Intermediário': 'intermediaria'}[f]}",
                                    cor=c["corPred"], corDetalhe=c["corDetalhe"]))
        return dict(submodo=submodo, coesivo=perf["Coesivo"], granular=perf["Granular"],
                    intermediario=perf["Intermediário"], avisos=avisos)
    camadas = []
    for c in comp["linhas"]:
        m = c["media"]
        if not c["heterogeneo"]:
            if m["familiaPredominante"] is None:
                continue
            camadas.append(dict(cota_m=c["cotaRef_m"], nspt=math.floor(m["familiaPredominante"]),
                                nspt_real=m["familiaPredominante"], impenetravel=False, solo=c["soloPred"],
                                familia=c["familiaPred"], heterogeneo=False, soloDetalhe=c["soloPred"],
                                nFuros=c["nFuros"], origem="media_compatibilizada", cor=c["corPred"],
                                corDetalhe=c["corDetalhe"]))
            continue
        if submodo == "2.1_predominante":
            bloqueadas.append(c["cotaRef_m"])
            continue
        cand = [(v, i, f) for i, (f, v) in enumerate((("Coesivo", m["coesivo"]), ("Granular", m["granular"]),
                                                       ("Intermediário", m["intermediario"]))) if v is not None]
        if not cand:
            continue
        cand.sort()
        v, _, f = cand[0]
        camadas.append(dict(cota_m=c["cotaRef_m"], nspt=math.floor(v), nspt_real=v, impenetravel=False, solo=CANONICO[f],
                            familia=f, heterogeneo=True, soloDetalhe=c["soloPred"], nFuros=c["nFuros"],
                            origem="media_conservador_heterogeneo", cor=None, corDetalhe=c["corDetalhe"],
                            rotulo=f"{CANONICO[f]} (ramo conservador heterogêneo)"))
        avisos.append(dict(cota_m=c["cotaRef_m"], tipo="heterogenea_ramo_escolhido", ramoEscolhido=f,
                           nspt_coesivo=m["coesivo"], nspt_granular=m["granular"], nspt_intermediario=m["intermediario"]))
    return dict(submodo=submodo, camadas=camadas, avisos=avisos, bloqueadas=bloqueadas)


def perfil_envoltoria(comp):
    out = []
    for c in comp["linhas"]:
        e = c["envoltoria"]
        if e["furo"] is None:
            continue
        out.append(dict(cota_m=c["cotaRef_m"], nspt=e["nspt"], nspt_real=e["nspt_real"], impenetravel=e["impenetravel"],
                        solo=e["solo"], familia=e["familia"], furo=e["furo"], nFuros=c["nFuros"], cor=e["cor"]))
    return out


def na_cota(sondagens, nomes=None, criterio="mais_alto"):
    """Cota do NA dos furos (NA final, ou o inicial na falta dele): o mais alto (padrão, a favor da segurança na
    tensão efetiva) ou a média. None se nenhum furo tem NA."""
    vals = []
    for n in (nomes or list(sondagens)):
        f = sondagens.get(n)
        if not f:
            continue
        na = f["naFinal_m"] if f["naFinal_m"] is not None else f["naInicial_m"]
        if na is not None:
            vals.append(f["cotaTopo_m"] - na)
    if not vals:
        return None
    return max(vals) if criterio == "mais_alto" else sum(vals) / len(vals)


def perfil_furo(sondagens, nome):
    """Leituras de um furo no formato das camadas (cota, NSPT, solo, família)."""
    f = sondagens[nome]
    return [dict(cota_m=f["cotaTopo_m"] - l["profundidade_m"], nspt=l["nspt_calculo"], nspt_real=l["nspt_real"],
                 impenetravel=l["impenetravel"], solo=l["solo"], familia=l["familia"], cor=l["cor"], furo=nome)
            for l in f["leituras"]]


def perfis(sondagens, nomes=None, janela=JANELA_PADRAO, submodo="2.2_conservador"):
    """Compatibilização, média (submodo) e envoltória dos furos escolhidos."""
    comp = compatibilizar(sondagens, nomes, janela)
    med = perfil_medio(comp, submodo) if submodo != "2.3_dois_paralelos" else perfil_medio(comp, "2.2_conservador")
    return dict(compatibilizacao=comp, media=med, envoltoria=perfil_envoltoria(comp),
                media_23=perfil_medio(comp, "2.3_dois_paralelos"))


def para_desenho(nome, tipo, camadas, cota_boca=None, sond=None):
    """Perfil no formato do estaca_sondagem (desenho das colunas no DWG): furo com as leituras, ou média e
    envoltória com 'cota_boca' 1 m acima da 1ª cota."""
    if tipo == "furo":
        f = sond[nome]
        return dict(nome=nome, tipo="furo", cota_boca=f["cotaTopo_m"], prof_final=f["profundidadeFinal_m"],
                    na_ini=f["naInicial_m"], na_fim=f["naFinal_m"], criterio=f["criterioParalisacao"],
                    leituras=[dict(prof=l["profundidade_m"], nspt=l["nspt_calculo"], imp=l["impenetravel"], solo=l["solo"],
                                   familia=l["familia"], cor=l["cor"] or "") for l in f["leituras"]])
    if not camadas:
        return None
    topo = camadas[0]["cota_m"] + 1.0 if cota_boca is None else cota_boca
    return dict(nome=nome, tipo=tipo, cota_boca=topo,
                leituras=[dict(prof=round(topo - c["cota_m"], 6), nspt=c["nspt"], imp=bool(c.get("impenetravel")),
                               solo=c["solo"], familia=c["familia"], het=bool(c.get("heterogeneo")),
                               det=(c.get("soloDetalhe") if c.get("heterogeneo") else c.get("furo", "")) or "",
                               cor=c.get("cor") or "", cor_det=c.get("corDetalhe") or "") for c in camadas])


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(errors="replace")
    s, info = ler_geospt(sys.argv[1])
    p = perfis(s, janela=float(sys.argv[2]) if len(sys.argv) > 2 else JANELA_PADRAO)
    print(info, len(s), "furos")
    print("cota  média(2.2)            envoltória")
    env = {e["cota_m"]: e for e in p["envoltoria"]}
    for c in p["media"]["camadas"]:
        e = env.get(c["cota_m"], {})
        print(f"{c['cota_m']:5.0f} {c['nspt']:3d} {c['solo'][:18]:18s} {e.get('nspt', ''):>3} {e.get('solo', '')[:18]:18s} {e.get('furo', '')}")
