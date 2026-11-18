# -*- coding: utf-8 -*-
"""
Dimensionamento de tubulões curtos (rígidos, sem base alargada) sob força horizontal e momento. Sem TQS.

Modelo (ver PLANO_TubulõesCurtos.md e AVALIACAO_referencias.md):
- corpo rígido com 5 graus de liberdade: deslocamentos horizontais do topo (ux, uy), inclinações (tx, ty: o fuste
  na profundidade z se desloca ux - tx·z) e recalque (w); a base em z = L com recalque w + tx·x + ty·y;
- reação lateral por fatias: q = nh·z_s·u por metro (R01, Fórm. 6.9.2), limitada a p_u(z) (Brinch Hansen, Broms
  ou Rankine, tubulao_solo), na direção do deslocamento; abaixo do ponto de rotação a reação troca de lado;
- base: grade polar de pontos com kv, sem tração e limitada a q_ult; atrito na base opcional (padrão: só na
  ruptura, μ = tan(2φ'/3); em argila não drenada, desprezado);
- Newton-Raphson com rigidez tangente; ruptura por "pushover" (λ sobre as ações horizontais e os momentos de cada
  combinação de serviço, força normal fixa); conferência por equilíbrio limite no plano do tombamento.
Sem plastificação e com a base toda comprimida (ou admitindo tração), o modelo é o de R01 (6.10) e R02: os
exemplos dessas referências são reproduzidos em tubulao_testes.py.

Cargas características por ação, no topo do tubulão (kN, kN·m; z para cima; Mx em torno de x, My em torno de y;
Hx com My > 0 tombam no mesmo sentido). Combinações pela NBR 6118:2026 (Tabelas 11.1 e 11.2).

Critérios da NBR 6122:2022 (R08; o 8.2.3 aplica ao tubulão as regras da fundação rasa, 7.2 a 7.6):
- classificação pela profundidade da base (3.27 e 3.28): rasa abaixo de 2·D, profunda a partir de 8·D e 3 m;
- σadm com q_ult = 3·σadm (Tabela 1); majorada em até 15 % só quando o vento é a ação variável principal (6.3.2;
  30 % nas obras da lista do item), com FS ≥ 1,6;
- área comprimida da base ≥ 2/3 nas combinações características (7.6.2) e empuxo passivo reduzido por 2,0 (7.6.3);
- tombamento em valores de cálculo (6.2.1.1.2): resistências do solo ÷ 1,4 (p_u, q_ult e atrito), peso favorável
  ÷ 1,2, ações × 1,4: λd ≥ 1,4 no modelo minorado (ou, opcionalmente, FS global ≥ fs_tombamento);
- concreto (8.6.3, 8.6.4.1, Tabela 4): γc e classe mínima pela camisa e pela CAA (tubulao_concreto.parametros_6122),
  compressão simples ≤ 5 MPa sem armadura, armadura mínima de 0,4 % em 3,0 m e barras 2 mm mais finas (8.6.2).

Uso: python tubulao_core.py <parametros.json>  (grava <nome>_resultado.json e <nome>_resumo.txt em saidas\\)
"""
import os, sys, json, math, copy, itertools, time
import dependencias                       # cópia portátil: sem o numpy, diz o que falta e sai
dependencias.exigir_calculo()
import numpy as np
import tubulao_sondagem as ts
import tubulao_solo as so
import tubulao_concreto as tc

AQUI = os.path.dirname(os.path.abspath(__file__))
SAIDAS = os.path.join(AQUI, "saidas")
VERSAO = "1.0"
GAMA_W = so.GAMA_W

# Catálogo de anéis pré-moldados (R05, p. 42: DN interno, altura 0,50 m, espessuras do fabricante; editável)
CATALOGO_ANEIS = [
    dict(DN=0.60, h=0.50, e=0.06), dict(DN=0.80, h=0.50, e=0.08), dict(DN=1.00, h=0.50, e=0.09),
    dict(DN=1.20, h=0.50, e=0.09), dict(DN=1.50, h=0.50, e=0.08), dict(DN=1.80, h=0.50, e=0.10),
    dict(DN=2.00, h=0.50, e=0.10),
]
PSI = {  # NBR 6118:2026, Tabela 11.2: (ψ0, ψ1, ψ2)
    "edificacao": (0.5, 0.4, 0.3), "edificacao_predominancia": (0.7, 0.6, 0.4), "biblioteca_garagem": (0.8, 0.7, 0.6),
    "vento": (0.6, 0.3, 0.0), "temperatura": (0.6, 0.5, 0.3), "equipamento": (0.8, 0.7, 0.6),
}
GAMA_F = dict(permanente=(1.4, 1.0), variavel=1.4, temperatura=1.2)   # Tabela 11.1, combinações normais

PADROES = dict(
    nome="T1", quantidade=1, descricao="",
    geometria=dict(D=None, L=2.0, cota_topo=0.0, cota_terreno=None, desprezar_topo=0.0),
    camisa=dict(usar=True, DN=None, espessura=None, altura=0.50, estrutural=False),
    folga=dict(largura=0.05, preenchimento="autoadensavel", folga_min_compactacao=0.30),
    lastro=dict(espessura=0.05, material="concreto magro"),
    materiais=dict(fck=30.0, fyk=500.0, cobrimento=0.05, caa="II", gama_c=25.0, agregado="granito"),
    apoio=dict(tipo="nenhum", secao="retangular", a=0.40, b=0.40, d=0.40, h_aplicacao=0.0, embutimento=0.0,
               area_secao=0.0, ex=0.0, ey=0.0),
    acoes=[],
    sondagem=dict(arquivo=None, sondagens=None, furos=None, janela=0.50, submodo="2.2_conservador",
                  perfis=["media", "envoltoria"], delta=0.0, na=None, na_criterio="mais_alto"),
    solo=dict(metodo_pu="brinch_hansen", metodo_phi="teixeira", edicoes=[], sigma_adm=None, fs_base=3.0,
              atrito_base_servico=False, atrito_base_ruptura=True),
    criterios=dict(tombamento="calculo", gama_m_solo=1.4, gama_m_peso=1.2, gama_f_tombamento=1.4, fs_tombamento=2.0,
                   fs_passivo=2.0, fator_sigma_vento=1.15, vento_obra_lista=False, area_comprimida_min=2 / 3,
                   area_comprimida_qp=1.0, rotacao_lim=1 / 200, rotacao_lim_poste=0.01, desloc_aplicacao_lim=None, recalque_lim=0.025,
                   z_rigido=2.0, z_longo=4.0, as_min_fuste=0.004, comp_min_armadura=3.0, sacrificio_barras=2.0,
                   concreto_simples=True, theta_ruptura=0.10, fs_criterio="min",
                   fretagem_arranjo="auto", fretagem_a_d_limite=0.5, grelha_espac_camadas=0.20, grelha_espac_barras=0.15,
                   grelha_min_barras=3, aneis_construtivos_s=0.20, montagem_bitola=10.0, montagem_espac_max=0.50,
                   montagem_min=6),
    dimensionamento=dict(automatico=False, D_lista=None, L_min=1.0, L_max=6.0, L_passo=None),
    analise=dict(n_fatias=60, n_aneis_base=14, n_setores_base=40),
    saidas=dict(pasta=None, escala=25, pdf=True, dxf=True, dxf_plotagem=True, memoria=True, memoria_pdf=True,
                tres_d=True, quant_resumo=True, sondagens_desenho=True),
)


def _br(v, c=None):
    """Número com vírgula decimal (textos das verificações e avisos)."""
    return (f"{v:g}" if c is None else f"{v:.{c}f}").replace(".", ",")


def _mesclar(base, novo):
    out = copy.deepcopy(base)
    for k, v in (novo or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _mesclar(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def normalizar(par, pasta_base=None):
    """Parâmetros com os padrões e a geometria derivada. ValueError com a lista de erros."""
    p = _mesclar(PADROES, par)
    erros = []
    g, cm, mt = p["geometria"], p["camisa"], p["materiais"]
    if g["cota_terreno"] is None:
        g["cota_terreno"] = g["cota_topo"]
    if cm["usar"]:
        if cm["DN"] is None:
            erros.append("Camisa de anéis: informe o DN (diâmetro interno).")
        elif cm["espessura"] is None:
            cat = [c for c in CATALOGO_ANEIS if abs(c["DN"] - cm["DN"]) < 1e-6]
            if cat:
                cm["espessura"] = cat[0]["e"]
            else:
                erros.append(f"Anel DN {cm['DN']:g}: fora do catálogo, informe a espessura.")
        if cm["DN"] is not None and cm["espessura"] is not None:
            g["D"] = cm["DN"] + 2 * cm["espessura"]
    if not g["D"] or g["D"] <= 0:
        erros.append("Informe o diâmetro do tubulão (ou o anel da camisa).")
    if not g["L"] or g["L"] <= 0:
        erros.append("Informe o comprimento L do tubulão.")
    if g["cota_terreno"] > g["cota_topo"] + 1e-9 and not erros:
        erros.append("Terreno acima do topo do tubulão: o topo fica enterrado (informe a cota do topo no terreno).")
    if p["folga"]["preenchimento"] not in ("autoadensavel", "solo_cimento_compactado", "nenhuma"):
        erros.append("Preenchimento da folga: autoadensavel, solo_cimento_compactado ou nenhuma.")
    if p["solo"]["metodo_pu"] not in so.METODOS_PU:
        erros.append(f"Método de ruptura lateral: {', '.join(so.METODOS_PU)}.")
    if not p["acoes"]:
        erros.append("Informe ao menos uma ação (carga característica).")
    for a in p["acoes"]:
        a.setdefault("nome", "Ação")
        a.setdefault("tipo", "permanente")
        for k in ("N", "Hx", "Hy", "Mx", "My"):
            a[k] = float(a.get(k) or 0.0)
        if a["tipo"] not in ("permanente", "variavel", "excepcional"):
            erros.append(f"Ação {a['nome']}: tipo permanente, variavel ou excepcional.")
        a.setdefault("categoria", "vento" if a["tipo"] == "variavel" else "")
        if a["tipo"] == "variavel" and a["categoria"] not in PSI:
            erros.append(f"Ação {a['nome']}: categoria {a['categoria']!r} (use {', '.join(PSI)}).")
        a.setdefault("grupo", a["nome"])
    cr = p["criterios"]
    if cr["fretagem_arranjo"] not in ("auto", "aneis", "grelha"):
        erros.append("Arranjo da fretagem: auto, aneis ou grelha.")
    if cr["tombamento"] not in ("calculo", "global"):
        erros.append("Tombamento: calculo (NBR 6122 6.2.1.1.2) ou global (FS mínimo informado).")
    lim_vento = 1.30 if cr["vento_obra_lista"] else 1.15
    if cr["fator_sigma_vento"] > lim_vento + 1e-9:
        erros.append(f"Majoração de σadm com vento {_br(cr['fator_sigma_vento'])}: a NBR 6122 (6.3.2) permite até "
                     f"{_br(lim_vento)}" + ("" if cr["vento_obra_lista"] else " (1,30 só nas obras da lista do item)") + ".")
    s = p["sondagem"]
    if s["arquivo"] and not os.path.isabs(s["arquivo"]) and pasta_base:
        s["arquivo"] = os.path.normpath(os.path.join(pasta_base, s["arquivo"]))
    if not s["arquivo"] and not s["sondagens"]:
        erros.append("Informe a sondagem (arquivo do GEOSPT ou furos digitados).")
    if erros:
        raise ValueError("\n".join(erros))
    # geometria derivada
    D, L = g["D"], g["L"]
    g["cota_base"] = g["cota_topo"] - L
    g["D_estrutura"] = cm["DN"] if (cm["usar"] and not cm["estrutural"]) else D
    g["D_escavacao"] = D + 2 * (p["folga"]["largura"] if cm["usar"] else 0.0)
    g["contra_solo"] = not cm["usar"]
    p["_concreto"] = tc.parametros_6122(mt["caa"], cm["usar"])
    return p


def classificar(p):
    """Classificação da NBR 6122:2022 pela profundidade da base abaixo do terreno (3.27 e 3.28)."""
    g = p["geometria"]
    D, prof = g["D"], g["cota_terreno"] - g["cota_base"]
    b = lambda v: f"{v:.2f}".replace(".", ",")
    if prof < 2 * D:
        tipo, txt = "rasa", (f"base a {b(prof)} m de profundidade, menos que 2·D = {b(2 * D)} m: fundação rasa (R08, 3.28). "
                             "O tubulão é verificado como fundação rasa, o que o 8.2.3 já manda fazer na base.")
    elif prof >= 8 * D and prof >= 3.0:
        tipo, txt = "profunda", f"base a {b(prof)} m de profundidade (≥ 8·D e ≥ 3 m): fundação profunda (R08, 3.27)."
    else:
        tipo, txt = "intermediaria", (f"base a {b(prof)} m de profundidade, entre 2·D = {b(2 * D)} m e 8·D = {b(8 * D)} m: "
                                      "a denominação de fundação profunda deve ser justificada (R08, 3.27).")
    return dict(tipo=tipo, profundidade=prof, D=D, texto=txt)


# --------------------------------------------------------------------------------------------- combinações
def combinacoes(acoes):
    """Combinações características (serviço, geotecnia), quase permanentes (recalque) e últimas normais (estrutura).
    Ações do mesmo 'grupo' são alternativas exclusivas (ex.: vento em várias direções). Devolve dict de listas
    [{nome, tipo, F: (N, Hx, Hy, Mx, My), parcelas: [(fator, nome)], vento}]."""
    perm = [a for a in acoes if a["tipo"] == "permanente"]
    var = [a for a in acoes if a["tipo"] == "variavel"]
    grupos = {}
    for a in var:
        grupos.setdefault(a["grupo"], []).append(a)
    def soma(parcelas):
        F = [0.0] * 5
        for f, a in parcelas:
            for i, k in enumerate(("N", "Hx", "Hy", "Mx", "My")):
                F[i] += f * a[k]
        return F
    gnomes = list(grupos)
    escolhas = list(itertools.product(*[[None] + grupos[g] for g in gnomes])) if gnomes else [()]
    serv, qp, elu = [], [], []
    vistos = set()
    for esc in escolhas:
        ativos = [a for a in esc if a is not None]
        cands = [None] if not ativos else ativos
        for princ in cands:
            # característica: G + Q1 + Σψ0·Qj
            parc = [(1.0, a) for a in perm]
            for a in ativos:
                parc.append((1.0 if a is princ else PSI[a["categoria"]][0], a))
            chave = tuple(sorted((round(f, 3), a["nome"]) for f, a in parc))
            if chave in vistos:
                continue
            vistos.add(chave)
            nome = " + ".join(("" if f == 1 else f"{f:g}·") + a["nome"] for f, a in parc)
            vento = any(a["categoria"] == "vento" for _, a in parc if a["tipo"] == "variavel" and _ > 0)
            serv.append(dict(nome=nome, tipo="caracteristica", F=soma(parc), parcelas=[(f, a["nome"]) for f, a in parc],
                             vento=vento, principal=princ["nome"] if princ else None,
                             vento_principal=bool(princ is not None and princ["categoria"] == "vento"),
                             N_perm=sum(f * a["N"] for f, a in parc if a["tipo"] == "permanente"),
                             N_var=sum(f * a["N"] for f, a in parc if a["tipo"] != "permanente")))
            # últimas normais, com as permanentes desfavoráveis e favoráveis
            for gp in GAMA_F["permanente"]:
                pe = [(gp, a) for a in perm]
                for a in ativos:
                    gq = GAMA_F["temperatura"] if a["categoria"] == "temperatura" else GAMA_F["variavel"]
                    pe.append((gq * (1.0 if a is princ else PSI[a["categoria"]][0]), a))
                nome_e = " + ".join(f"{f:.2f}·{a['nome']}" for f, a in pe)
                elu.append(dict(nome=nome_e, tipo="ultima", F=soma(pe), parcelas=[(f, a["nome"]) for f, a in pe],
                                vento=vento, gama_g=gp))
    # quase permanente: G + Σψ2·Qj (uma por escolha de alternativas)
    vistos = set()
    for esc in escolhas:
        parc = [(1.0, a) for a in perm] + [(PSI[a["categoria"]][2], a) for a in esc if a is not None]
        parc = [(f, a) for f, a in parc if f > 0]
        chave = tuple(sorted((round(f, 3), a["nome"]) for f, a in parc))
        if chave in vistos or not parc:
            continue
        vistos.add(chave)
        qp.append(dict(nome=" + ".join(("" if f == 1 else f"{f:g}·") + a["nome"] for f, a in parc),
                       tipo="quase_permanente", F=soma(parc), parcelas=[(f, a["nome"]) for f, a in parc], vento=False))
    return dict(servico=serv, quase_permanente=qp, ultima=elu)


def vetor_carga(F):
    """(N, Hx, Hy, Mx, My) -> vetor generalizado [Hx, Hy, My, -Mx, N] (ver o cabeçalho)."""
    N, Hx, Hy, Mx, My = F
    return np.array([Hx, Hy, My, -Mx, N], dtype=float)


# --------------------------------------------------------------------------------------------- solo do tubulão
def preparar_solo(p, pasta_base=None):
    """Sondagens, perfis de cálculo (média e/ou envoltória ou furo) e camadas com os parâmetros."""
    s = p["sondagem"]
    if s["sondagens"]:
        sond, info = ts.normalizar_sondagens(s["sondagens"]), dict(esquema="digitado")
    else:
        sond, info = ts.ler_geospt(s["arquivo"])
    if s["delta"]:
        for f in sond.values():
            f["cotaTopo_m"] += s["delta"]
    nomes = s["furos"] or list(sond)
    pf = ts.perfis(sond, nomes, s["janela"], s["submodo"] if s["submodo"] != "2.3_dois_paralelos" else "2.2_conservador")
    na = s["na"] if s["na"] is not None else ts.na_cota(sond, nomes, s["na_criterio"])
    escolhas = []
    for nome in s["perfis"]:
        if nome == "media":
            escolhas.append(("media", f"sondagem média ({s['submodo']})", pf["media"]["camadas"]))
        elif nome == "envoltoria":
            escolhas.append(("envoltoria", "envoltória mínima", pf["envoltoria"]))
        elif nome.startswith("furo:"):
            fn = nome[5:]
            escolhas.append((nome, f"furo {fn}", ts.perfil_furo(sond, fn)))
    if not escolhas:
        raise ValueError("Escolha o perfil de cálculo (média, envoltória ou furo).")
    g = p["geometria"]
    perfis = []
    for chave, rot, cams in escolhas:
        c = so.camadas_calculo(cams, g["cota_terreno"], p["solo"]["metodo_phi"], p["solo"]["edicoes"], rot)
        perfis.append(dict(chave=chave, rotulo=rot, camadas=c, origem=cams))
    fim = min(f["cotaTopo_m"] - f["profundidadeFinal_m"] for f in (sond[n] for n in nomes))
    return dict(sondagens=sond, info=info, nomes=nomes, perfis_geospt=pf, na=na, perfis=perfis, cota_fim=fim)


# --------------------------------------------------------------------------------------------- base circular
_E_LIM = {}


def e_lim_circulo(frac):
    """Excentricidade limite da resultante (fração do raio) para que a base circular, com pressão linear e sem
    tração, tenha a fração 'frac' da área comprimida. frac = 1: núcleo central, e = R/4 (= D/8)."""
    if frac >= 1 - 1e-9:
        return 0.25
    k = round(frac, 4)
    if k in _E_LIM:
        return _E_LIM[k]
    xi = np.linspace(-1, 1, 4001)
    larg = 2 * np.sqrt(np.clip(1 - xi * xi, 0, None))
    def area(c):
        m = xi >= c
        return np.trapezoid(larg[m], xi[m]) / math.pi if m.sum() > 1 else 0.0
    lo, hi = -1.0, 1.0                                   # linha neutra em xi = c (comprimido para xi > c)
    for _ in range(60):
        c = (lo + hi) / 2
        if area(c) > frac:
            lo = c
        else:
            hi = c
    m = xi >= c
    p = (xi[m] - c) * larg[m]
    e = np.trapezoid(p * xi[m], xi[m]) / np.trapezoid(p, xi[m])
    _E_LIM[k] = float(e)
    return _E_LIM[k]


# --------------------------------------------------------------------------------------------- modelo
class Modelo:
    """Tubulão rígido em molas elastoplásticas (fatias laterais e grade da base)."""

    def __init__(self, p, perfil, na, sigma_adm, n_fatias=None, n_aneis=None, n_setores=None):
        g, mt = p["geometria"], p["materiais"]
        an = p["analise"]
        self.p, self.na, self.cams = p, na, perfil["camadas"]
        D, L = g["D"], g["L"]
        self.D, self.L = D, L
        self.cota_topo, self.cota_terreno = g["cota_topo"], g["cota_terreno"]
        metodo = p["solo"]["metodo_pu"]
        # fatias laterais (só abaixo do terreno e do trecho desprezado)
        z_ini = (g["cota_topo"] - g["cota_terreno"]) + g["desprezar_topo"]
        n = n_fatias or an["n_fatias"]
        self.z_ini = z_ini
        if z_ini >= L:
            raise ValueError("Não há solo em contato com o fuste (topo do solo abaixo da base).")
        bordas = np.linspace(z_ini, L, n + 1)
        self.z = (bordas[:-1] + bordas[1:]) / 2
        self.dz = np.diff(bordas)
        self.zs = self.z - (g["cota_topo"] - g["cota_terreno"])           # profundidade abaixo do terreno
        cotas = g["cota_topo"] - self.z
        self.cota_fatias = cotas
        self.cam_fatia = [so.camada_em(self.cams, c) for c in cotas]
        self.sv = np.array([so.sigma_v(self.cams, g["cota_terreno"], na, c) for c in cotas])
        sub = np.array([na is not None and c < na for c in cotas])
        self.nh = np.array([cm["nh_sub"] if s else cm["nh"] for cm, s in zip(self.cam_fatia, sub)])
        self.k = self.nh * self.zs * self.dz                                 # kN/m por fatia
        self.pu = np.array([so.p_ultimo(metodo, cm, sv, zs, D) for cm, sv, zs in zip(self.cam_fatia, self.sv, self.zs)])
        self.P = self.pu * self.dz                                           # kN por fatia
        # base: grade polar de áreas iguais
        nr, nt = n_aneis or an["n_aneis_base"], n_setores or an["n_setores_base"]
        Dbase = g.get("D_base") or D                     # base alargada só para os testes com R02 (o app não alarga)
        R = Dbase / 2
        rr = R * np.sqrt((np.arange(nr) + 0.5) / nr)
        tt = (np.arange(nt) + 0.5) / nt * 2 * math.pi
        RR, TT = np.meshgrid(rr, tt)
        self.bx, self.by = (RR * np.cos(TT)).ravel(), (RR * np.sin(TT)).ravel()
        self.ba = np.full(self.bx.size, math.pi * R * R / self.bx.size)
        self.Ab = math.pi * R * R
        self.Ib = math.pi * Dbase ** 4 / 64
        self.Dbase = Dbase
        cota_b = g["cota_base"]
        self.cam_base = so.camada_em(self.cams, cota_b - 0.01)
        sub_b = na is not None and cota_b < na
        self.kv = self.cam_base["kv_sub"] if sub_b else self.cam_base["kv"]
        self.sigma_adm = sigma_adm
        self.q_ult = p["solo"]["fs_base"] * sigma_adm
        cb = self.cam_base
        if cb["comportamento"] == "drenado":
            self.mu = math.tan(math.radians(2 * cb["phi"] / 3))
            self.atrito_nota = f"μ = tan(2φ'/3), φ' = {cb['phi']:.1f}° da camada da base"
        else:
            self.mu = 0.0
            self.atrito_nota = "base em argila não drenada: atrito desprezado"
        self.kt = self.kv * self.Ab                                          # rigidez do atrito (só mobiliza o limite)
        # pesos
        Dc = g["D_estrutura"]
        gc = mt["gama_c"]
        self.peso_enchimento, self.peso_camisa = self._peso(Dc, 0.0, gc), self._peso(D, Dc, gc) if D > Dc else 0.0
        self.W = self.peso_enchimento + self.peso_camisa
        self.Bf = None

    def _peso(self, D1, D0, gc):
        """Peso efetivo (empuxo abaixo do NA) do anel D0..D1 ao longo de L."""
        A = math.pi * (D1 ** 2 - D0 ** 2) / 4
        topo, base = self.cota_topo, self.cota_topo - self.L
        if self.na is None or self.na <= base:
            return A * self.L * gc
        acima = max(0.0, topo - max(self.na, base))
        return A * (acima * gc + (self.L - acima) * (gc - GAMA_W))

    # ---------------------------------------------------------------- forças e rigidez
    def forcas(self, U, caps=True, tracao=False, atrito=False, kv_lin=False):
        ux, uy, tx, ty, w = U
        z = self.z
        dx, dy = ux - tx * z, uy - ty * z
        r = np.hypot(dx, dy)
        fe = self.k * r
        plast = caps & (fe > self.P) if caps else np.zeros_like(r, dtype=bool)
        ex = np.divide(dx, r, out=np.zeros_like(r), where=r > 0)
        ey = np.divide(dy, r, out=np.zeros_like(r), where=r > 0)
        mag = np.where(plast, self.P, fe)
        fx, fy = -mag * ex, -mag * ey                                        # reação do solo sobre o fuste
        # rigidez tangente das fatias (2x2 por fatia)
        kel = np.where(plast, 0.0, self.k)
        kpl = np.where(plast, np.divide(self.P, r, out=np.zeros_like(r), where=r > 0), 0.0)
        kxx = kel + kpl * (1 - ex * ex)
        kyy = kel + kpl * (1 - ey * ey)
        kxy = -kpl * ex * ey
        F = np.zeros(5)
        K = np.zeros((5, 5))
        F[0] += fx.sum(); F[1] += fy.sum()
        F[2] += (-z * fx).sum(); F[3] += (-z * fy).sum()
        # B = [[1,0,-z,0,0],[0,1,0,-z,0]] ; K += Bᵀ k B
        K[0, 0] += kxx.sum(); K[1, 1] += kyy.sum(); K[0, 1] += kxy.sum(); K[1, 0] += kxy.sum()
        K[0, 2] += (-z * kxx).sum(); K[2, 0] = K[0, 2]
        K[1, 3] += (-z * kyy).sum(); K[3, 1] = K[1, 3]
        K[0, 3] += (-z * kxy).sum(); K[3, 0] = K[0, 3]
        K[1, 2] += (-z * kxy).sum(); K[2, 1] = K[1, 2]
        K[2, 2] += (z * z * kxx).sum(); K[3, 3] += (z * z * kyy).sum()
        K[2, 3] += (z * z * kxy).sum(); K[3, 2] = K[2, 3]
        # base
        wb = w + tx * self.bx + ty * self.by
        pb = self.kv * wb
        if not tracao:
            pb = np.maximum(pb, 0.0)
        ativo = (pb > 0) if not tracao else np.ones_like(pb, dtype=bool)
        if caps and not tracao:
            sat = pb > self.q_ult
            pb = np.minimum(pb, self.q_ult)
            ativo = ativo & ~sat
        fb = pb * self.ba                                                    # força para cima em cada ponto
        F[2] += -(self.bx * fb).sum(); F[3] += -(self.by * fb).sum(); F[4] += -fb.sum()
        kb = np.where(ativo, self.kv * self.ba, 0.0)
        bx, by = self.bx, self.by
        K[2, 2] += (kb * bx * bx).sum(); K[3, 3] += (kb * by * by).sum(); K[4, 4] += kb.sum()
        K[2, 3] += (kb * bx * by).sum(); K[3, 2] = K[2, 3]
        K[2, 4] += (kb * bx).sum(); K[4, 2] = K[2, 4]
        K[3, 4] += (kb * by).sum(); K[4, 3] = K[3, 4]
        info = dict(fx=fx, fy=fy, plast=plast, pb=pb, r=r)
        if atrito:
            N_b = fb.sum()
            ubx, uby = ux - tx * self.L, uy - ty * self.L
            rb = math.hypot(ubx, uby)
            cap = self.mu * max(N_b, 0.0)
            fe_b = self.kt * rb
            if rb > 0:
                ebx, eby = ubx / rb, uby / rb
            else:
                ebx = eby = 0.0
            if fe_b <= cap:
                ft, kxx_b, kyy_b, kxy_b = fe_b, self.kt, self.kt, 0.0
            else:
                ft = cap
                kk = cap / rb if rb > 0 else 0.0
                kxx_b, kyy_b, kxy_b = kk * (1 - ebx * ebx), kk * (1 - eby * eby), -kk * ebx * eby
            ftx, fty = -ft * ebx, -ft * eby
            L = self.L
            F[0] += ftx; F[1] += fty; F[2] += -L * ftx; F[3] += -L * fty
            Kb = np.array([[kxx_b, kxy_b], [kxy_b, kyy_b]])
            B = np.array([[1, 0, -L, 0, 0], [0, 1, 0, -L, 0]], dtype=float)
            K += B.T @ Kb @ B
            info.update(atrito=(ftx, fty), atrito_cap=cap)
        return F, K, info

    def resolver(self, Fext, U0=None, caps=True, tracao=False, atrito=False, maxit=80):
        """Equilíbrio Fext + F_solo(U) = 0. Devolve (U, ok, iterações)."""
        Fext = np.asarray(Fext, dtype=float)
        if U0 is None:
            U0 = self.linear(Fext)
        U = np.array(U0, dtype=float)
        escala = np.array([1, 1, self.L, self.L, 1.0]) * max(1.0, np.abs(Fext).max())
        tol = 1e-7
        for it in range(maxit):
            Fs, K, _ = self.forcas(U, caps, tracao, atrito)
            R = Fext + Fs
            if np.all(np.abs(R) / escala < tol):
                return U, True, it
            try:
                dU = np.linalg.solve(K + np.eye(5) * 1e-9 * np.trace(K), R)
            except np.linalg.LinAlgError:
                return U, False, it
            n0 = np.linalg.norm(R / escala)
            passo = 1.0
            for _ in range(12):                                  # busca linear
                Un = U + passo * dU
                Rn = Fext + self.forcas(Un, caps, tracao, atrito)[0]
                if np.linalg.norm(Rn / escala) < n0 or passo < 1e-3:
                    break
                passo /= 2
            U = Un
            if not np.all(np.isfinite(U)) or abs(U[2]) > 1.0 or abs(U[3]) > 1.0:
                return U, False, it
        Fs = self.forcas(U, caps, tracao, atrito)[0]
        return U, bool(np.all(np.abs(Fext + Fs) / escala < 1e-5)), maxit

    def linear(self, Fext):
        """Solução linear com contato total na base (ponto de partida e solução de referência de R01)."""
        K = self.forcas(np.array([0.0, 0, 0, 0, 1e-6]), caps=False, tracao=True)[1]
        return np.linalg.solve(K, np.asarray(Fext, dtype=float))

    def estado(self, U, caps=True, tracao=False, atrito=False):
        Fs, K, inf = self.forcas(U, caps, tracao, atrito)
        ux, uy, tx, ty, w = U
        th = math.hypot(tx, ty)
        q = np.hypot(inf["fx"], inf["fy"]) / self.dz                   # kN/m (módulo)
        # ponto de rotação: profundidade em que o deslocamento na direção da inclinação se anula
        z0 = (ux * tx + uy * ty) / (th * th) if th > 0 else None
        pb = inf["pb"]
        nb = float((pb * self.ba).sum())
        e_base = math.hypot((pb * self.ba * self.bx).sum(), (pb * self.ba * self.by).sum()) / nb if nb > 0 else math.inf
        return dict(e_base=e_base, U=U.tolist(), ux=ux, uy=uy, tx=tx, ty=ty, w=w, theta=th, u_topo=math.hypot(ux, uy), z0=z0,
                    q=q.tolist(), fx=inf["fx"].tolist(), fy=inf["fy"].tolist(), plast=inf["plast"].tolist(),
                    mob=(q / self.pu.clip(min=1e-9)).tolist(), pb=pb.tolist(), p_max=float(pb.max()),
                    p_min=float(pb.min()), area_comp=float((pb > 1e-9).sum() / pb.size),
                    base_sat=float((pb >= self.q_ult - 1e-6).sum() / pb.size) if caps and not tracao else 0.0,
                    N_base=float((pb * self.ba).sum()), atrito=inf.get("atrito"))

    # ---------------------------------------------------------------- esforços no fuste
    def esforcos(self, U, Fext, caps=True, tracao=False, atrito=False, n=41):
        """N, V e M ao longo do fuste (z do topo à base), com as reações das fatias acima de cada seção."""
        _, _, inf = self.forcas(U, caps, tracao, atrito)
        Hx, Hy, Mtx, Mty, N0 = Fext
        Dc = self.p["geometria"]["D_estrutura"]
        gc = self.p["materiais"]["gama_c"]
        A = math.pi * Dc * Dc / 4
        zs = np.linspace(0.0, self.L, n)
        out = []
        for zc in zs:
            m = self.z < zc
            fx, fy, zi = inf["fx"][m], inf["fy"][m], self.z[m]
            # parte da fatia cortada pela seção
            Vx, Vy = Hx + fx.sum(), Hy + fy.sum()
            Mx_ = Mtx + Hx * zc + (fx * (zc - zi)).sum()
            My_ = Mty + Hy * zc + (fy * (zc - zi)).sum()
            cota = self.cota_topo - zc
            if self.na is None or cota >= self.na:
                peso = A * zc * gc
            else:
                acima = max(0.0, self.cota_topo - self.na)
                peso = A * (acima * gc + (zc - acima) * (gc - GAMA_W))
            out.append(dict(z=float(zc), N=float(N0 + peso), V=float(math.hypot(Vx, Vy)), M=float(math.hypot(Mx_, My_)),
                            Vx=float(Vx), Vy=float(Vy), Mtx=float(Mx_), Mty=float(My_)))
        return out

    # ---------------------------------------------------------------- ruptura
    def pushover(self, F, atrito=True, lam_max=20.0, tol=0.01, theta_rup=0.10):
        """Fator λ sobre as ações horizontais e os momentos (força normal fixa) até o colapso numérico ou até a
        rotação convencional de ruptura theta_rup."""
        Fh = np.array(F, dtype=float); Fh[4] = 0.0
        Fv = np.zeros(5); Fv[4] = F[4]
        if np.abs(Fh).max() < 1e-9:
            return dict(lam=math.inf, curva=[], estado=None)
        U, ok, _ = self.resolver(Fv, atrito=atrito)
        curva = [(0.0, 0.0, 0.0)]
        lam, dl = 0.0, 0.25
        ult_ok = (0.0, U)
        while dl > tol / 4 and lam < lam_max:
            ln = min(lam + dl, lam_max)
            Un, ok, _ = self.resolver(Fv + ln * Fh, U0=ult_ok[1], atrito=atrito)
            if ok and math.hypot(Un[2], Un[3]) < theta_rup:
                lam = ln
                ult_ok = (ln, Un)
                curva.append((ln, float(math.hypot(Un[2], Un[3])), float(math.hypot(Un[0], Un[1]))))
                dl *= 1.5 if dl < 1.0 else 1.0
            else:
                dl /= 2
        lam_u = ult_ok[0]
        return dict(lam=lam_u if lam_u < lam_max else math.inf, curva=curva,
                    estado=self.estado(ult_ok[1], atrito=atrito) if lam_u > 0 else None)

    def equilibrio_limite(self, F, atrito=True):
        """Conferência 2D (corpo rígido-plástico) no plano do tombamento: H e M projetados na direção do momento
        de tombamento na base. Devolve λ."""
        Hx, Hy, Mtx, Mty, N = F
        mb = np.array([Mtx + Hx * self.L, Mty + Hy * self.L])
        if np.linalg.norm(mb) < 1e-9:
            return math.inf
        e = mb / np.linalg.norm(mb)
        H, M = Hx * e[0] + Hy * e[1], Mtx * e[0] + Mty * e[1]
        V = N                                            # força normal na base: F já inclui o peso do tubulão
        P, z = self.P, self.z
        # momento resistente da base: resultante V no segmento comprimido com q_ult
        R = self.Dbase / 2
        if V <= 0 or V >= self.q_ult * self.Ab:
            Mb = 0.0
        else:
            def area(c):
                a = math.acos(max(-1.0, min(1.0, c / R)))
                return R * R * (a - math.sin(a) * math.cos(a))
            lo, hi = -R, R
            for _ in range(80):
                mid = (lo + hi) / 2
                if area(mid) > V / self.q_ult:
                    lo = mid
                else:
                    hi = mid
            a = math.acos(lo / R)
            Mb = V * (2 / 3) * R ** 3 * math.sin(a) ** 3 / area(lo)
        T = self.mu * max(V, 0.0) if atrito else 0.0
        # mecanismo cinemático (teorema do limite superior): rotação θ em torno do ponto zr do eixo; o topo anda zr·θ.
        # λ(zr) = [Σ P_i·|zr - z_i| + T·|zr - L| + Mb] / (H·zr + M); o colapso é o menor λ, inclusive com zr abaixo
        # da base (rotação com escorregamento) e no limite zr -> ∞ (translação pura: (ΣP + T)/H).
        zr = np.concatenate([np.linspace(min(self.z_ini, 0.0), self.L, 801)[1:],
                             self.L * (1 + np.logspace(-4, 3, 300))])
        dis = np.abs(zr[:, None] - z[None, :]) @ P + T * np.abs(zr - self.L) + Mb
        den = H * zr + M
        lam = np.where(den > 1e-9, dis / np.where(den > 1e-9, den, 1.0), np.inf)
        cand = [float(lam.min())]
        if H > 1e-9:
            cand.append((P.sum() + T) / H)
        lam_u = min(cand)
        self.le_zr = float(zr[int(np.argmin(lam))]) if lam_u == cand[0] else math.inf
        return lam_u

    def minorado(self, gama_m):
        """Cópia com a resistência do solo dividida por gama_m (R08, 6.2.1.1.2): p_u das fatias, q_ult e atrito da
        base. As rigidezes não mudam."""
        m = copy.copy(self)
        m.P, m.pu = self.P / gama_m, self.pu / gama_m
        m.q_ult, m.mu = self.q_ult / gama_m, self.mu / gama_m
        return m


# --------------------------------------------------------------------------------------------- comparações
def comparar_metodos(p, perfil, na, sigma_adm, F):
    """λ de ruptura (equilíbrio limite) com cada lei de p_u, para a mesma combinação (vetor generalizado F)."""
    out = {}
    for met in so.METODOS_PU:
        q = copy.deepcopy(p)
        q["solo"]["metodo_pu"] = met
        m = Modelo(q, perfil, na, sigma_adm)
        Fw = np.array(F, dtype=float)
        out[met] = dict(nome=so.METODOS_PU[met], lam=m.equilibrio_limite(Fw, atrito=p["solo"]["atrito_base_ruptura"]),
                        lam_sem_base=_lam_sem_base(m, Fw), pu=m.pu.tolist())
    return out


def _lam_sem_base(m, F):
    """λ desprezando a base (momento e atrito), como nas soluções clássicas de estacas curtas."""
    q_ult, mu = m.q_ult, m.mu
    m.q_ult, m.mu = 1e-9, 0.0
    try:
        return m.equilibrio_limite(F, atrito=False)
    finally:
        m.q_ult, m.mu = q_ult, mu


def verificacoes_referencia(m, e_lin, F):
    """Critérios das referências antigas, sobre a solução linear: limite elástico de R01 (Fórm. 6.10.5: inclinação da
    carga lateral na origem m = nh·Δx ≤ γ·a·(kp - ka), com a camada do topo) e o CS de Sherif de R02/R03 (área
    resistente γ·z·(Kp - Ka), que cai a zero no ponto de rotação a partir de 0,75·y0, sobre a área atuante acima de
    y0), com Kp sem redução (como em R02) e com Kp/2 (como em R05, NBR 6122 7.6.3)."""
    ux, tx = e_lin["U"][0], e_lin["U"][2]
    th = math.hypot(e_lin["U"][2], e_lin["U"][3])
    u0 = math.hypot(e_lin["U"][0], e_lin["U"][1])
    if th <= 0:
        return None
    y0 = e_lin["z0"]
    cam0 = m.cam_fatia[0]
    ka, kp = so.ka_kp(cam0["phi"]) if cam0["comportamento"] == "drenado" else (1.0, 1.0)
    g0 = cam0["gama"]
    m_ref = m.nh[0] * u0                                   # dq/dz na superfície (kN/m²)
    lim = g0 * m.D * (kp - ka)
    q = np.array(e_lin["q"])
    acima = m.z < y0
    A1 = float((q[acima] / m.D * m.dz[acima]).sum()) if acima.any() else 0.0
    def a2(fkp):
        tot = 0.0
        for z, dz, sv, cm in zip(m.z, m.dz, m.sv, m.cam_fatia):
            if z >= y0:
                break
            ka_, kp_ = so.ka_kp(cm["phi"]) if cm["comportamento"] == "drenado" else (1.0, 1.0)
            pr = sv * (kp_ / fkp - ka_)
            fat = 1.0 if z <= 0.75 * y0 else max(0.0, (y0 - z) / (0.25 * y0))
            tot += max(pr, 0.0) * fat * dz
        return tot
    return dict(m=m_ref, m_lim=lim, m_ok=m_ref <= lim, y0=y0, A1=A1, A2=a2(1.0), A2_reduzido=a2(2.0),
                cs=a2(1.0) / A1 if A1 > 0 else math.inf, cs_reduzido=a2(2.0) / A1 if A1 > 0 else math.inf,
                kp=kp, ka=ka, gama=g0)


# --------------------------------------------------------------------------------------------- análise completa
def rigidez(p, modelo):
    """Z = L/T, T = (EI/nh)^(1/5) com nh médio ao longo do comprimento enterrado (R01, Fórm. 6.9.3)."""
    mt, g = p["materiais"], p["geometria"]
    E = tc.modulo_ecs(mt["fck"], mt["agregado"])
    I = math.pi * g["D_estrutura"] ** 4 / 64
    nh = float((modelo.nh * modelo.dz).sum() / modelo.dz.sum())
    T = (E * I / nh) ** 0.2
    return dict(E=E, I=I, nh=nh, T=T, Z=g["L"] / T)


def recalque_elastico(p, perfil, na, Nqp, W, D, cota_base, cota_fim):
    """Recalque da base pela teoria da elasticidade: E equivalente ponderado pelo acréscimo de tensão sob o centro
    de uma placa circular (Boussinesq), w = (π/4)·Δq·D·(1 - ν²)/E_eq (placa rígida). Δq = carga/área - σv0."""
    cams = perfil["camadas"]
    A = math.pi * D * D / 4
    sv0 = so.sigma_v(cams, p["geometria"]["cota_terreno"], na, cota_base)
    dq = (Nqp + W) / A - sv0
    if dq <= 0:
        return dict(w=0.0, dq=dq, E_eq=None, nu=None, prof=0.0, nota="sem acréscimo líquido de tensão na base")
    R = D / 2
    prof_max = min(4 * D, max(0.5, cota_base - cota_fim))
    zz = np.linspace(0.005, prof_max, 400)
    dz = zz[1] - zz[0]
    infl = 1 - (zz / np.sqrt(zz * zz + R * R)) ** 3
    Es = np.array([so.camada_em(cams, cota_base - z)["E"] for z in zz])
    nus = np.array([so.camada_em(cams, cota_base - z)["nu"] for z in zz])
    E_eq = (infl * dz).sum() / (infl * dz / Es).sum()
    nu = float((infl * nus).sum() / infl.sum())
    w = math.pi / 4 * dq * D * (1 - nu * nu) / E_eq
    nota = (f"bulbo até {prof_max:.2f} m abaixo da base" + (" (limitado pelo fim da sondagem)" if prof_max < 4 * D else ""))
    return dict(w=w, dq=dq, E_eq=E_eq, nu=nu, prof=prof_max, sv0=sv0, nota=nota)


def _sigma_adm(p, perfil, modelo_D, L):
    s = p["solo"]
    if s["sigma_adm"]:
        return float(s["sigma_adm"]), "valor informado pelo usuário", None
    v, nota, n = so.sigma_adm_alonso(perfil["camadas"], p["geometria"]["cota_base"], modelo_D, L)
    return v, nota, n


def normal_tombamento(c, W, cr):
    """Força normal de cálculo na verificação ao tombamento (R08, 6.2.1.1.2): peso do tubulão e cargas permanentes
    favoráveis ÷ γm = 1,2; variáveis favoráveis desprezadas; parcelas desfavoráveis (tração) × γf = 1,4."""
    perm = W + c.get("N_perm", c["F"][0])
    Nd = perm / cr["gama_m_peso"] if perm >= 0 else perm * cr["gama_f_tombamento"]
    if c.get("N_var", 0.0) < 0:
        Nd += cr["gama_f_tombamento"] * c["N_var"]
    return Nd


def analisar_perfil(p, perfil, na, combs, completo=True, fino=True, ruptura="pushover"):
    """Análise de um perfil de cálculo: serviço, ruptura, recalque e esforços."""
    g = p["geometria"]
    sadm, sadm_nota, n_bulbo = _sigma_adm(p, perfil, g["D"], g["L"])
    an = p["analise"] if fino else dict(n_fatias=24, n_aneis_base=8, n_setores_base=24)
    m = Modelo(p, perfil, na, sadm, an["n_fatias"], an["n_aneis_base"], an["n_setores_base"])
    rg = rigidez(p, m)
    sl = p["solo"]
    res = dict(perfil=perfil["chave"], rotulo=perfil["rotulo"], sigma_adm=sadm, sigma_adm_nota=sadm_nota,
               n_bulbo=n_bulbo, q_ult=m.q_ult, kv=m.kv, mu=m.mu, atrito_nota=m.atrito_nota, W=m.W,
               peso_enchimento=m.peso_enchimento, peso_camisa=m.peso_camisa, rigidez=rg, servico=[], qp=[],
               ultima=[], modelo=m)
    for c in combs["servico"]:
        F = vetor_carga(c["F"]).copy(); F[4] += m.W
        U, ok, it = m.resolver(F, atrito=sl["atrito_base_servico"])
        e = m.estado(U, atrito=sl["atrito_base_servico"])
        e.update(nome=c["nome"], ok=ok, vento=c["vento"], vento_principal=c.get("vento_principal", False), F=c["F"])
        if completo:
            e["esforcos"] = m.esforcos(U, F, atrito=sl["atrito_base_servico"])
            Ul, okl, _ = m.resolver(F, caps=False, tracao=True)
            el = m.estado(Ul, caps=False, tracao=True)
            e["linear"] = dict(U=el["U"], theta=el["theta"], u_topo=el["u_topo"], z0=el["z0"], p_max=el["p_max"],
                               p_min=el["p_min"], q=el["q"], area_comp=el["area_comp"], ok=okl)
            if abs(F[0]) + abs(F[1]) + abs(F[2]) + abs(F[3]) > 1e-9:
                e["referencias"] = verificacoes_referencia(m, el, F) if el["z0"] is not None else None
                e["metodos"] = comparar_metodos(p, perfil, na, sadm, F)
        cr = p["criterios"]
        lam_le = m.equilibrio_limite(F, atrito=sl["atrito_base_ruptura"])
        e["lam_le"] = lam_le
        if ruptura == "le":                                  # varredura do dimensionamento: equilíbrio limite (rápido)
            e["lam"] = lam_le
        else:
            po = m.pushover(F, atrito=sl["atrito_base_ruptura"], theta_rup=cr["theta_ruptura"])
            e["lam_pushover"] = po["lam"]
            e["lam"] = {"min": min(lam_le, po["lam"]), "le": lam_le, "pushover": po["lam"]}[cr["fs_criterio"]]
            if completo:
                e["pushover"] = po
        # tombamento em valores de cálculo (R08, 6.2.1.1.2): solo ÷ γm, peso favorável ÷ 1,2; exige λd ≥ γf
        Fd = F.copy()
        Fd[4] = normal_tombamento(c, m.W, cr)
        md = m.minorado(cr["gama_m_solo"])
        lam_d_le = md.equilibrio_limite(Fd, atrito=sl["atrito_base_ruptura"])
        e.update(N_tombamento=float(Fd[4]), lam_d_le=lam_d_le)
        if ruptura == "le" or cr["tombamento"] != "calculo":
            e["lam_d"] = lam_d_le
        else:
            pod = md.pushover(Fd, atrito=sl["atrito_base_ruptura"], theta_rup=cr["theta_ruptura"])
            e["lam_d_pushover"] = pod["lam"]
            e["lam_d"] = {"min": min(lam_d_le, pod["lam"]), "le": lam_d_le, "pushover": pod["lam"]}[cr["fs_criterio"]]
            if completo:
                e["pushover_d"] = pod
        res["servico"].append(e)
    for c in combs["quase_permanente"]:
        F = vetor_carga(c["F"]).copy(); F[4] += m.W
        U, ok, _ = m.resolver(F, atrito=sl["atrito_base_servico"])
        e = m.estado(U, atrito=sl["atrito_base_servico"])
        e.update(nome=c["nome"], ok=ok, F=c["F"])
        e["recalque_el"] = recalque_elastico(p, perfil, na, c["F"][0], m.W, g["D"], g["cota_base"],
                                             p.get("_cota_fim_sond", g["cota_base"] - 4 * g["D"]))
        res["qp"].append(e)
    if completo:
        for c in combs["ultima"]:
            F = vetor_carga(c["F"]).copy(); F[4] += m.W * c.get("gama_g", 1.4)
            U, ok, _ = m.resolver(F, atrito=sl["atrito_base_servico"])
            e = m.estado(U, atrito=sl["atrito_base_servico"])
            e.update(nome=c["nome"], ok=ok, F=c["F"], gama_g=c.get("gama_g"))
            Fd = vetor_carga(c["F"])
            e["esforcos"] = m.esforcos(U, np.r_[Fd[:4], Fd[4]], atrito=sl["atrito_base_servico"])
            # peso próprio de cálculo no fuste: esforcos() usa o peso característico; majora aqui
            for s in e["esforcos"]:
                s["N"] = Fd[4] + (s["N"] - Fd[4]) * c.get("gama_g", 1.4)
            res["ultima"].append(e)
    return res


# --------------------------------------------------------------------------------------------- verificações
def _chk(lista, grupo, nome, valor, limite, ok, ref, unidade="", detalhe="", combinacao="", perfil=""):
    lista.append(dict(grupo=grupo, nome=nome, valor=valor, limite=limite, ok=bool(ok), ref=ref, unidade=unidade,
                      detalhe=detalhe, combinacao=combinacao, perfil=perfil,
                      aproveitamento=(valor / limite if isinstance(valor, (int, float)) and limite not in (None, 0)
                                      and isinstance(limite, (int, float)) else None)))


def limite_rotacao(p):
    """Rotação de serviço admissível e a sua fonte. Poste: tg α ≤ 0,01 de Sulzberger (R09, p. 7), para não alterar a
    flecha e a tração dos condutores. Pilar e outros: limite do projetista (padrão 1/200), porque depende da estrutura
    apoiada; a NBR 6122 não fixa valores (R08, 6.2.2)."""
    cr = p["criterios"]
    if p["apoio"]["tipo"] == "poste":
        return cr["rotacao_lim_poste"], "R09 (Sulzberger: tg α ≤ 0,01 com poste, p. 7)"
    return cr["rotacao_lim"], "limite do projetista (R08, 6.2.2: a norma não fixa valores)"


def verificar(p, ap_list, estrutura=None):
    cr = p["criterios"]
    chks, alertas = [], []
    g = p["geometria"]
    for ap in ap_list:
        pr = ap["rotulo"]
        rg = ap["rigidez"]
        if rg["Z"] > cr["z_longo"]:
            alertas.append(("erro", f"{pr}: Z = L/T = {rg['Z']:.2f} > {cr['z_longo']:g}: o tubulão não é curto (R01, 6.9.3). "
                                    "O modelo de corpo rígido não vale."))
        elif rg["Z"] > cr["z_rigido"]:
            alertas.append(("aviso", f"{pr}: Z = {rg['Z']:.2f} entre {cr['z_rigido']:g} e {cr['z_longo']:g}: o tubulão não é "
                                     "perfeitamente rígido (R01: L ≤ 2·L0); os resultados são aproximados."))
        _chk(chks, "Rigidez", "Z = L/T (corpo rígido)", rg["Z"], cr["z_rigido"], rg["Z"] <= cr["z_rigido"],
             "R01, 6.9.3 e Ex. 6.10.2.1", perfil=pr)
        for e in ap["servico"]:
            if not e["ok"]:
                alertas.append(("erro", f"{pr}, {e['nome']}: sem equilíbrio em serviço (solo plastificado ou base levantando)."))
            fat = cr["fator_sigma_vento"] if e.get("vento_principal") else 1.0
            lim = fat * ap["sigma_adm"]
            _chk(chks, "Base", "Tensão máxima de borda", e["p_max"], lim, e["p_max"] <= lim + 1e-6,
                 "R08, 8.2.3 e 7.3 (σadm)" + (f"; × {_br(fat)} com o vento como ação principal (6.3.2)" if fat != 1 else ""),
                 "kPa", combinacao=e["nome"], perfil=pr)
            el = e_lim_circulo(cr["area_comprimida_min"]) * g["D"] / 2
            _chk(chks, "Base", f"Excentricidade na base (área comprimida ≥ {cr['area_comprimida_min'] * 100:.0f} %)",
                 e["e_base"], el, e["e_base"] <= el + 1e-9, "R08, 7.6.2 (por 8.2.3.5)", "m", combinacao=e["nome"], perfil=pr,
                 detalhe=f"área comprimida {e['area_comp'] * 100:.0f} %")
            mob = max(e["mob"]) if e["mob"] else 0.0
            _chk(chks, "Empuxo", "Mobilização máxima do empuxo │q│/p_u", mob, 1 / cr["fs_passivo"],
                 mob <= 1 / cr["fs_passivo"] + 1e-9, "R08, 7.6.3 (por 8.2.3.5): passivo reduzido por ≥ 2,0",
                 combinacao=e["nome"], perfil=pr)
            rlim, rref = limite_rotacao(p)
            _chk(chks, "Deslocamentos", "Rotação do tubulão", e["theta"], rlim, e["theta"] <= rlim, rref, "rad",
                 combinacao=e["nome"], perfil=pr)
            ha = p["apoio"]["h_aplicacao"] or 0.0
            u_ap = e["u_topo"] + e["theta"] * ha
            e["u_aplicacao"] = u_ap
            if cr["desloc_aplicacao_lim"]:
                _chk(chks, "Deslocamentos", f"Deslocamento no ponto de aplicação ({_br(ha)} m acima do topo)", u_ap,
                     cr["desloc_aplicacao_lim"], u_ap <= cr["desloc_aplicacao_lim"], "limite informado", "m",
                     combinacao=e["nome"], perfil=pr)
            def _det(le, po):
                t = f"equilíbrio limite {_br(le, 2)}" if le is not None and math.isfinite(le) else "equilíbrio limite —"
                if po is not None:
                    t += f"; pushover até θ = {_br(cr['theta_ruptura'])} rad: " + (_br(po, 2) if math.isfinite(po) else "—")
                return t
            met = so.METODOS_PU[p["solo"]["metodo_pu"]]
            if cr["tombamento"] == "calculo":
                gf = cr["gama_f_tombamento"]
                _chk(chks, "Ruptura", f"Tombamento em valores de cálculo: λd ≥ γf ({met})", e["lam_d"], gf, e["lam_d"] >= gf,
                     f"R08, 6.2.1.1.2 (solo ÷ {_br(cr['gama_m_solo'])}, peso ÷ {_br(cr['gama_m_peso'])}, ações × {_br(gf)})",
                     combinacao=e["nome"], perfil=pr,
                     detalhe=_det(e.get("lam_d_le"), e.get("lam_d_pushover")) + f"; N = {e['N_tombamento']:.0f} kN"
                             + (f"; FS global {_br(e['lam'], 2)}" if math.isfinite(e["lam"]) else ""))
            else:
                _chk(chks, "Ruptura", f"Tombamento: FS global = λ último ({met})", e["lam"], cr["fs_tombamento"],
                     e["lam"] >= cr["fs_tombamento"], "FS global informado (R08, 6.2.1.1.2, em valores característicos)",
                     combinacao=e["nome"], perfil=pr, detalhe=_det(e.get("lam_le"), e.get("lam_pushover")))
        for e in ap["qp"]:
            el = e_lim_circulo(cr["area_comprimida_qp"]) * g["D"] / 2
            _chk(chks, "Base", f"Excentricidade na base, quase permanente (área comprimida ≥ {cr['area_comprimida_qp'] * 100:.0f} %)",
                 e["e_base"], el, e["e_base"] <= el + 1e-9, "critério do app (a NBR 6122 exige 2/3 só nas características)",
                 "m", combinacao=e["nome"], perfil=pr, detalhe=f"área comprimida {e['area_comp'] * 100:.0f} %")
            w = max(e["w"], e["recalque_el"]["w"])
            _chk(chks, "Recalque", "Recalque da base (maior entre Winkler e elástico)", w, cr["recalque_lim"],
                 w <= cr["recalque_lim"], "limite informado (a confirmar)", "m", combinacao=e["nome"], perfil=pr)
    if estrutura:
        for v in estrutura["verificacoes"]:
            chks.append(v)
        alertas.extend(estrutura["alertas"])
    return chks, alertas


# --------------------------------------------------------------------------------------------- estrutura
def _grampos(gr, lista, apoio, **extra):
    """Guarda na grelha os grampos com ganchos de 180° (tc.grampos): cada grampo, os comprimentos distintos (cada um
    vira uma posição no desenho) e o maior (comp, usado nos textos)."""
    comps = sorted({gp["comp"] for gp in lista}, reverse=True)
    gr.update(ganchos=180, apoio_ganchos=apoio, grampos=lista, comps=comps, comp=comps[0], **extra)


def dimensionar_estrutura(p, ap_list):
    """Fuste (concreto simples ou armado) e topo (bloco parcialmente carregado) para todas as combinações últimas."""
    g, mt, cr, apo = p["geometria"], p["materiais"], p["criterios"], p["apoio"]
    Dc = g["D_estrutura"]
    fck, fyk, cob = mt["fck"], mt["fyk"], mt["cobrimento"]
    verif, alertas, envelope = [], [], []
    for ap in ap_list:
        for e in ap["ultima"]:
            for s in e["esforcos"]:
                envelope.append(dict(perfil=ap["rotulo"], comb=e["nome"], **s))
    if not envelope:
        return dict(verificacoes=verif, alertas=alertas, envelope=[], simples=None, armadura=None, bloco=None)
    pc = p["_concreto"]
    gcs, gca = pc["gc_simples"], pc["gc_armado"]
    if fck < pc["fck_min"] - 1e-9:
        alertas.append(("erro", f"Concreto C{fck:g} abaixo do mínimo C{pc['fck_min']:g} para a CAA {mt['caa']} ({pc['ref_classe']})."))
    # compressão simples característica (R08, 8.6.3 e Tabela 4): acima de 5 MPa o fuste tem de ser armado
    A_c = math.pi * Dc * Dc / 4
    serv_N = [(s["N"], e["nome"], ap["rotulo"], s["z"]) for ap in ap_list for e in ap["servico"] for s in e.get("esforcos", [])]
    sig_k = None
    if serv_N:
        Nk, ck, pk, zk = max(serv_N)
        sig_k = Nk / A_c
        _chk(verif, "Estrutura", "Compressão simples característica N/A (sem armar até o limite)", sig_k, pc["sigma_sem_armar"],
             sig_k <= pc["sigma_sem_armar"], "R08, 8.6.3 e Tabela 4", "kPa", combinacao=ck, perfil=pk, detalhe=f"z = {_br(zk, 2)} m")
    # bloco parcialmente carregado
    bloco = None
    if apo["tipo"] == "pilar":
        topo = [s for s in envelope if s["z"] == 0.0]
        # momentos de cálculo no topo de volta à convenção de entrada: Mx = -Mty, My = Mtx (inverso de vetor_carga)
        b_list = []
        for s in topo:
            Mx_d, My_d = -s["Mty"], s["Mtx"]
            b = tc.bloco_parcial(Dc, fck, fyk, dict(secao=apo["secao"], a=apo["a"], b=apo["b"], d=apo["d"]), s["N"], Mx_d, My_d,
                                 apo.get("fck") or fck, gama_c=gca)
            b_list.append((b, s))
        b, s = max(b_list, key=lambda t: t[0]["s_max"] / t[0]["f_lim"] if t[0].get("f_lim") else 0.0)
        _chk(verif, "Topo", "Pressão de contato sob o pilar: σ ≤ fcd·√(Ac1/Ac0) ≤ 3,3·fcd", b["s_max"], b["f_lim"],
             b["s_max"] <= b["f_lim"] + 1e-6, f"R07, 21.2.1 (γc = {_br(gca)} no tubulão)", "kPa", combinacao=s["comb"],
             perfil=s["perfil"],
             detalhe=f"Ac0 = {_br(b['Ac0'], 3)} m², Ac1 = {_br(b['Ac1'], 3)} m²")
        bt, st = max(b_list, key=lambda t: t[0]["Td"])
        as_fret = bt["As_fret"]
        # arranjo: anéis (fendilhamento anelar, R07 Fig. 21.1a) ou grelha nas duas direções sob o pilar + anéis
        # construtivos; no automático, grelha quando o pilar é pequeno em relação ao tubulão (a/D abaixo do limite)
        lado = max(apo["a"], apo["b"]) if apo["secao"] == "retangular" else apo["d"]
        a_D = lado / Dc
        arranjo = cr["fretagem_arranjo"]
        if arranjo == "auto":
            arranjo = "grelha" if a_D < cr["fretagem_a_d_limite"] else "aneis"
        gr = None
        if as_fret <= 0:
            fr = None
        elif arranjo == "aneis":
            fr = tc.fretagem(as_fret, Dc, cob, bt["zona"])
        else:
            z1_, z2_ = bt["zona"]                                 # anéis entre as camadas da grelha (meio espaçamento abaixo)
            fr = tc.fretagem(0.0, Dc, cob, (z1_ + cr["grelha_espac_camadas"] / 2, z2_), s_max=cr["aneis_construtivos_s"])
            if fr:
                fr["construtivo"] = True
            phi_a = fr["bitola"] if fr else 0.0
            tx_max = max(b2["Tx"] for b2, _ in b_list)
            ty_max = max(b2["Ty"] for b2, _ in b_list)
            gr = tc.grelha_fretagem(tx_max, ty_max, Dc / 2 - cob - phi_a / 1000, bt["zona"], fyk,
                                    s_camadas=cr["grelha_espac_camadas"], s_barras=cr["grelha_espac_barras"],
                                    n_min=cr["grelha_min_barras"])
            if gr is None:
                alertas.append(("aviso", "A grelha de fretagem não coube: usados os anéis."))
                fr, arranjo = tc.fretagem(as_fret, Dc, cob, bt["zona"]), "aneis"
        bloco = dict(verif=b, comb=s["comb"], verif_t=bt, comb_t=st["comb"], fretagem=fr, grelha=gr, arranjo=arranjo,
                     arranjo_opcao=cr["fretagem_arranjo"], a_D=a_D,
                     todas=[dict(comb=s2["comb"], N=s2["N"], **{k: v for k, v in b2.items() if k in
                                 ("f_lim", "s_max", "Td", "Tx", "Ty", "As_fret", "Ac0", "Ac1", "ax", "ay")}) for b2, s2 in b_list])
        for bb, _ in b_list:
            for a in bb.get("avisos", []):
                if ("aviso", a) not in alertas:
                    alertas.append(("aviso", a))
        if fr and not fr.get("construtivo"):
            _chk(verif, "Topo", f"Fretagem: {fr['n']} estribos circulares ø{fr['bitola']:g} c/{fr['s'] * 100:.0f}", as_fret,
                 fr["As_ef"], fr["As_ef"] >= as_fret - 1e-12, "R07, 21.2.1 e Seção 22 (bielas e tirantes)", "m²",
                 combinacao=st["comb"], detalhe=f"Td = {_br(bt['Td'], 0)} kN; a/D = {_br(a_D, 2)}")
        if gr:
            for dr, k in (("x", "As_x"), ("y", "As_y")):
                n_ = gr["nx"] if dr == "x" else gr["ny"]
                _chk(verif, "Topo", f"Fretagem em grelha, barras em {dr}: {gr['n_camadas']} camadas × {n_} ø{_br(gr['bitola'])}",
                     gr[k], gr[k + "_ef"], gr[k + "_ef"] >= gr[k] - 1e-12, "R07, 21.2.1 e Seção 22 (bielas e tirantes)", "m²",
                     detalhe=f"T{dr} = {_br(gr[k] * fyk / tc.GAMA_S * 1000, 0)} kN; a/D = {_br(a_D, 2)}; "
                             f"camadas c/{gr['s_camadas'] * 100:.0f} de {_br(gr['z1'], 2)} a {_br(gr['z2'], 2)} m")
            if fr:
                _chk(verif, "Topo", f"Anéis construtivos da grelha: {fr['n']} ø{_br(fr['bitola'])} c/{fr['s'] * 100:.0f}", fr["s"],
                     None, True, "cintamento construtivo (o tirante fica com a grelha)", "m")
    # concreto simples
    pior = max(envelope, key=lambda s: tc.concreto_simples(Dc, fck, s["N"], s["M"], s["V"], g["contra_solo"], gcs)["aproveitamento"])
    cs = tc.concreto_simples(Dc, fck, pior["N"], pior["M"], pior["V"], g["contra_solo"], gcs)
    simples_ok = cs["ok_comp"] and cs["ok_trac"] and cs["ok_cis"] and (sig_k is None or sig_k <= pc["sigma_sem_armar"])
    armadura = None
    ref_gc = "R08, Tabela 4" if gcs > tc.GAMA_C_SIMPLES else "R07, 24.5.2.1"
    if cr["concreto_simples"] and simples_ok:
        _chk(verif, "Estrutura", "Fuste em concreto simples: compressão na fibra", cs["s_max"], cs["sc_rd"], cs["ok_comp"],
             f"R07, 24.5.2 (γc = {_br(gcs)}; {ref_gc})", "kPa",
             combinacao=pior["comb"], perfil=pior["perfil"], detalhe=f"z = {_br(pior['z'], 2)} m")
        _chk(verif, "Estrutura", "Fuste em concreto simples: tração na fibra", max(-cs["s_min"], 0.0), cs["st_rd"], cs["ok_trac"],
             "R07, 24.5.2", "kPa", combinacao=pior["comb"], perfil=pior["perfil"], detalhe=f"z = {_br(pior['z'], 2)} m")
        _chk(verif, "Estrutura", "Fuste em concreto simples: cisalhamento", cs["tau"], cs["tau_rd"], cs["ok_cis"],
             "R07, 24.5.2.3", "kPa", combinacao=pior["comb"], perfil=pior["perfil"], detalhe=f"z = {_br(pior['z'], 2)} m")
    else:
        if cr["concreto_simples"]:
            alertas.append(("aviso", "O fuste não passa como concreto simples (R07, Seção 24; R08, Tabela 4): armadura "
                                     "longitudinal calculada."))
        # trecho que precisa de armadura: seções reprovadas em concreto simples ou acima da compressão simples da Tabela 4
        L_ = g["L"]
        z_rep = [sx["z"] for sx in envelope
                 if tc.concreto_simples(Dc, fck, sx["N"], sx["M"], sx["V"], g["contra_solo"], gcs)["aproveitamento"] > 1 + 1e-9]
        z_rep += [zz for (Nk_, _, _, zz) in serv_N if Nk_ / A_c > pc["sigma_sem_armar"]]
        zs_env = sorted(set(sx["z"] for sx in envelope))
        if cr["concreto_simples"] and z_rep:
            # o trecho reprovado acaba na primeira seção que passa depois da última reprovada (a favor da segurança)
            z_falha = min((zz for zz in zs_env if zz > max(z_rep) + 1e-9), default=L_)
        else:
            z_falha = L_                                     # sem concreto simples: o fuste inteiro
        sol = [(s["N"], s["M"]) for s in envelope if s["z"] <= z_falha + 1e-9]
        as_min = cr["as_min_fuste"] * math.pi * Dc * Dc / 4
        sac = cr["sacrificio_barras"]
        fr = bloco["fretagem"] if bloco else None
        grl = bloco["grelha"] if bloco else None
        # barras por dentro do estribo mais grosso (no cálculo, o construtivo de até 6,3 mm (φl ≤ 25) ou a fretagem)
        # ou do gancho dos grampos da grelha, que ocupa o mesmo espaço
        phi_fr = max(fr["bitola"] if fr else 0.0, grl["bitola"] if grl else 0.0)
        cob_l = cob + max(6.3, phi_fr) / 1000
        armadura = tc.armadura_longitudinal(Dc, fck, fyk, cob_l, sol, as_min, gama_c=gca, sacrificio=sac, par=bool(grl))
        if armadura is None:
            alertas.append(("erro", "Armadura longitudinal: nenhuma combinação de barras atende (aumente o diâmetro)."))
        else:
            # fim das barras: o maior entre o mínimo da Tabela 4 (R08) e o fim do trecho reprovado + lb (R07, 9.4.2.4),
            # arredondado a 5 cm e limitado ao cobrimento da base
            lb = tc.comprimento_ancoragem(fck, armadura["bitola"], gca, fyk)
            z_bar = max(cr["comp_min_armadura"], z_falha + lb)
            z_bar = min(math.ceil(z_bar * 20 - 1e-6) / 20, L_ - cob)
            inteiro = z_bar >= L_ - cob - 1e-6
            estr = tc.estribos_fuste(armadura["bitola"], Dc, cob, z_bar, fr)
            cob_l = cob + max(estr["bitola"] if estr else 0.0, phi_fr) / 1000
            raio = Dc / 2 - cob_l - armadura["bitola"] / 2000
            armadura.update(cobrimento_barras=cob_l, raio=raio, espac=2 * math.pi * raio / armadura["n"], estribo=estr)
            # M_Rd na força normal de cada solicitação; a verificação usa a solicitação de pior relação M_Sd/M_Rd
            rel = []
            pts = tc.diagrama_interacao(Dc, fck, fyk, armadura["n"], armadura["bitola"], cob_l, gca, sac)
            for s in envelope:
                if s["z"] > z_falha + 1e-9:
                    continue
                mr = tc.m_do_diagrama(pts, s["N"]) or 0.0
                rel.append((abs(s["M"]) / mr if mr > 0 else 99.0, s["M"], mr, s))
            r_max, m_sd, m_rd, s_pior = max(rel, key=lambda t: t[0])
            comp = z_bar - cob
            armadura.update(gama_c=gca, sacrificio=sac, M_Rd=m_rd, M_Sd=m_sd, comprimento=comp, z_falha=z_falha, lb=lb,
                            z_fim=z_bar, inteiro=inteiro)
            _chk(verif, "Estrutura", f"Fuste armado {armadura['n']} ø{armadura['bitola']:g}: M_Sd ≤ M_Rd", abs(m_sd), m_rd,
                 abs(m_sd) <= m_rd + 1e-6,
                 f"R07, 17.2 e 8.2.10.1; R08, 8.6.3 (γc = {_br(gca)}) e 8.6.2 (barras {_br(sac)} mm mais finas)", "kN.m",
                 combinacao=s_pior["comb"], perfil=s_pior["perfil"],
                 detalhe=f"z = {_br(s_pior['z'], 2)} m; As = {_br(armadura['As'] * 1e4, 1)} cm²; mínimo {_br(as_min * 1e4, 1)} cm² "
                         f"({_br(cr['as_min_fuste'] * 100)} %, R08, Tabela 4)")
            _chk(verif, "Estrutura", f"Comprimento das barras ({'todo o fuste' if inteiro else 'trecho necessário'})", comp,
                 None, True, f"R08, Tabela 4 (mínimo {_br(cr['comp_min_armadura'])} m); R07, 9.4.2.4 (lb)", "m",
                 detalhe=(f"concreto simples reprovado até z = {_br(z_falha, 2)} m; lb = {_br(lb, 2)} m; barras do topo até "
                          f"z = {_br(z_bar, 2)} m"))
            if not inteiro:
                abaixo = [sx for sx in envelope if sx["z"] > z_falha + 1e-9]
                if abaixo:
                    cmax, smax_ = max(((tc.concreto_simples(Dc, fck, sx["N"], sx["M"], sx["V"], g["contra_solo"], gcs), sx)
                                       for sx in abaixo), key=lambda t: t[0]["aproveitamento"])
                    _chk(verif, "Estrutura", "Fuste abaixo do trecho armado em concreto simples (aproveitamento)",
                         cmax["aproveitamento"], 1.0, cmax["aproveitamento"] <= 1 + 1e-9, "R07, Seção 24", "",
                         combinacao=smax_["comb"], perfil=smax_["perfil"], detalhe=f"z = {_br(smax_['z'], 2)} m")
            if g["L"] < cr["comp_min_armadura"]:
                alertas.append(("aviso", f"Armadura em todo o tubulão ({_br(comp, 2)} m): a Tabela 4 (R08) pede {_br(cr['comp_min_armadura'])} m "
                                         "incluindo a ligação com o bloco, que fica fora do escopo."))
            if estr:
                _chk(verif, "Estrutura", f"Estribos do fuste armado: {estr['n']} ø{_br(estr['bitola'])} c/{estr['s'] * 100:.0f}",
                     estr["s"], None, estr["s"] <= estr["s_max"] + 1e-9,
                     "R07, 18.4.3 (φt ≥ 5 mm e φl/4; s ≤ 20 cm, D e 12·φl)", "m",
                     detalhe=f"s máx. {_br(estr['s_max'] * 100, 1)} cm; de {_br(estr['z1'], 2)} a {_br(estr['z2'], 2)} m abaixo do topo"
                             + ("; acima, a fretagem" if fr else ""))
            # cisalhamento: o concreto sozinho (24.5.2.3), a favor da segurança; os estribos são só os construtivos
            c_cis, s_cis = max(((tc.concreto_simples(Dc, fck, sx["N"], sx["M"], sx["V"], g["contra_solo"], gcs), sx)
                                for sx in envelope), key=lambda t: t[0]["tau"] / t[0]["tau_rd"])
            _chk(verif, "Estrutura", "Cisalhamento resistido pelo concreto (estribos só construtivos)", c_cis["tau"],
                 c_cis["tau_rd"], c_cis["ok_cis"], "R07, 24.5.2.3 (concreto simples, a favor da segurança)", "kPa",
                 combinacao=s_cis["comb"], perfil=s_cis["perfil"], detalhe=f"z = {_br(s_cis['z'], 2)} m")
            if not c_cis["ok_cis"]:
                alertas.append(("aviso", "Cortante acima da resistência do concreto: dimensione os estribos à força cortante "
                                         "(R07, 17.4); o app só calcula os estribos construtivos."))
    # barras de montagem da gaiola da fretagem quando o fuste não é armado (com armadura, ela segura os estribos)
    mont = None
    if bloco and (bloco["fretagem"] or bloco["grelha"]) and not armadura:
        fr_, gr_ = bloco["fretagem"], bloco["grelha"]
        z_fim = max(fr_["z2"] if fr_ else 0.0, gr_["z2"] if gr_ else 0.0) + 0.10
        offs = (lambda n_: [(k - (n_ - 1) / 2) * gr_["s_barras"] for k in range(n_)]) if gr_ else None
        # encostadas nos anéis; com grampos mais grossos que os anéis, por dentro dos ganchos (que ficam no cobrimento
        # dos anéis, entre as camadas deles)
        phi_e = max(fr_["bitola"] if fr_ else 0.0, gr_["bitola"] if gr_ else 0.0)
        mont = tc.montagem(Dc, cob, min(z_fim, g["L"] - cob), phi_e, cr["montagem_bitola"],
                           cr["montagem_espac_max"], cr["montagem_min"], offs and offs(gr_["nx"]), offs and offs(gr_["ny"]))
        if gr_:                                                   # grampos: ganchos de 180° abraçando a montagem
            _grampos(gr_, tc.grampos(gr_, mont["raio"], mont["bitola"]), "montagem")
        _chk(verif, "Topo", f"Barras de montagem: {mont['n']} ø{_br(mont['bitola'])}", mont["comp"], None, True,
             "construtivas (porta-estribos da fretagem)", "m",
             detalhe=(f"{mont['n_pontas']} nas pontas da grelha, junto aos estribos; " if mont["n_pontas"] else "")
                     + f"vão máximo {_br(mont['espac'] * 100, 0)} cm; do topo até z = {_br(mont['z_fim'], 2)} m")
    if bloco and bloco["grelha"] and armadura:                   # grampos com os ganchos nas barras longitudinais
        gr_ = bloco["grelha"]
        _grampos(gr_, tc.grampos(gr_, armadura["raio"], armadura["bitola"], n_barras=armadura["n"]), "longitudinais",
                 r_int=armadura["raio"])
    return dict(verificacoes=verif, alertas=alertas, envelope=envelope, montagem=mont, simples=dict(cs, comb=pior["comb"], z=pior["z"],
                perfil=pior["perfil"], ok=simples_ok, sigma_k=sig_k), armadura=armadura, bloco=bloco, concreto_6122=pc)


# --------------------------------------------------------------------------------------------- quantitativos
def quantitativos(p, ap):
    g, cm, fo, la, apo = p["geometria"], p["camisa"], p["folga"], p["lastro"], p["apoio"]
    D, L, De = g["D"], g["L"], g["D_escavacao"]
    Dc = g["D_estrutura"]
    q = {}
    v_poste = apo["area_secao"] * min(apo["embutimento"], L) if apo["tipo"] == "poste" else 0.0
    q["concreto_enchimento"] = math.pi * Dc * Dc / 4 * L - v_poste
    if cm["usar"]:
        n = math.ceil(L / cm["altura"] - 1e-6)
        q["aneis"] = n
        q["aneis_desc"] = f"anel DN {cm['DN']:.2f} m × {cm['altura']:.2f} m, parede {cm['espessura'] * 100:.0f} cm"
        q["volume_aneis"] = math.pi * (D * D - Dc * Dc) / 4 * n * cm["altura"]
        if abs(n * cm["altura"] - L) > 1e-6:
            q["aviso_aneis"] = f"L = {L:g} m não é múltiplo da altura do anel ({cm['altura']:g} m): o último anel sobra."
    q["escavacao"] = math.pi * De * De / 4 * (L + la["espessura"])
    q["folga"] = math.pi * (De * De - D * D) / 4 * L if cm["usar"] else 0.0
    q["lastro"] = math.pi * De * De / 4 * la["espessura"]
    q["peso_total"] = ap["W"] if ap else None
    return q


# --------------------------------------------------------------------------------------------- dimensionamento
def candidatos(p):
    dm, cm = p["dimensionamento"], p["camisa"]
    if cm["usar"]:
        cat = [c for c in CATALOGO_ANEIS if dm["D_lista"] is None or any(abs(c["DN"] - d) < 1e-6 for d in dm["D_lista"])]
        passo = dm["L_passo"] or cm["altura"]
        Ds = [(c["DN"], c["e"], c["DN"] + 2 * c["e"]) for c in cat]
    else:
        lista = dm["D_lista"] or [round(0.60 + 0.10 * i, 2) for i in range(15)]
        passo = dm["L_passo"] or 0.25
        Ds = [(None, None, d) for d in lista]
    Ls = []
    L = dm["L_min"]
    while L <= dm["L_max"] + 1e-9:
        Ls.append(round(L, 3))
        L += passo
    return Ds, Ls


def dimensionar(p, solo, combs, progresso=None):
    """Varredura D × L com o modelo grosso; devolve o mapa e a menor solução que passa (volume de concreto)."""
    Ds, Ls = candidatos(p)
    mapa = []
    for DN, e, D in Ds:
        for L in Ls:
            q = copy.deepcopy(p)
            q["geometria"]["L"] = L
            q["geometria"]["cota_base"] = q["geometria"]["cota_topo"] - L
            if DN is not None:
                q["camisa"]["DN"], q["camisa"]["espessura"] = DN, e
                q["geometria"]["D_estrutura"] = DN if not q["camisa"]["estrutural"] else D
                q["geometria"]["D_escavacao"] = D + 2 * q["folga"]["largura"]
            q["geometria"]["D"] = D
            if DN is None:
                q["geometria"]["D_estrutura"] = D
                q["geometria"]["D_escavacao"] = D
            try:
                aps = [analisar_perfil(q, pf, solo["na"], combs, completo=False, fino=False, ruptura="le")
                       for pf in solo["perfis"]]
                chks, al = verificar(q, aps)
                apr = [c for c in chks if c["aproveitamento"] is not None]
                gov = None
                pior = 0.0
                for c in apr:
                    a = c["aproveitamento"]
                    if c["nome"].startswith("Tombamento"):
                        a = (c["limite"] / c["valor"]) if c["valor"] else math.inf
                    a = min(a, 99.0)
                    if a > pior:
                        pior, gov = a, c["nome"]
                ok = all(c["ok"] for c in chks) and not any(n == "erro" for n, _ in al)
            except (ValueError, np.linalg.LinAlgError) as ex:
                ok, pior, gov = False, math.inf, str(ex)
            vol = math.pi * D * D / 4 * L
            mapa.append(dict(DN=DN, D=D, L=L, ok=ok, aproveitamento=pior, governante=gov, volume=vol))
            if progresso:
                progresso(len(mapa), len(Ds) * len(Ls))
    ok = [m for m in mapa if m["ok"]]
    escolha = min(ok, key=lambda m: (m["volume"], m["D"])) if ok else None
    return dict(mapa=mapa, escolha=escolha, Ds=[d for _, _, d in Ds], Ls=Ls)


# --------------------------------------------------------------------------------------------- entrada principal
def calcular(par, pasta_base=None, progresso=None):
    t0 = time.time()
    p = normalizar(par, pasta_base)
    solo = preparar_solo(p, pasta_base)
    p["_cota_fim_sond"] = solo["cota_fim"]
    combs = combinacoes(p["acoes"])
    dim = None
    if p["dimensionamento"]["automatico"]:
        dim = dimensionar(p, solo, combs, progresso)
        dim["otima"] = dim["escolha"]
        eu = p["dimensionamento"].get("escolha_usuario")
        if eu:                                           # solução escolhida pelo usuário no mapa (passe ou não)
            cel = next((m for m in dim["mapa"] if abs(m["D"] - eu["D"]) < 1e-6 and abs(m["L"] - eu["L"]) < 1e-6), None)
            if cel:
                dim["escolha"], dim["usuario"] = cel, True
            else:
                dim["aviso_usuario"] = (f"A solução escolhida (D = {_br(eu['D'], 2)} m, L = {_br(eu['L'], 2)} m) não está na "
                                        "varredura atual: foi usada a ótima.")
        if dim["escolha"]:
            esc = dim["escolha"]
            p["geometria"]["L"] = esc["L"]
            p["geometria"]["cota_base"] = p["geometria"]["cota_topo"] - esc["L"]
            if esc["DN"] is not None:
                cat = [c for c in CATALOGO_ANEIS if abs(c["DN"] - esc["DN"]) < 1e-6][0]
                p["camisa"]["DN"], p["camisa"]["espessura"] = cat["DN"], cat["e"]
            else:
                p["geometria"]["D"] = esc["D"]
            p = normalizar({k: v for k, v in p.items() if not k.startswith("_")}, pasta_base)
            p["_cota_fim_sond"] = solo["cota_fim"]
    aps = [analisar_perfil(p, pf, solo["na"], combs) for pf in solo["perfis"]]
    est = dimensionar_estrutura(p, aps)
    chks, alertas = verificar(p, aps, est)
    if dim and dim["escolha"] and not dim.get("usuario"):
        # a varredura usa o equilíbrio limite; a análise completa (com o pushover) pode reprovar: sobe de tamanho
        fila = sorted([m for m in dim["mapa"] if m["ok"]], key=lambda m: (m["volume"], m["D"]))
        dim["tentativas"] = []
        k = 0
        while not (all(c["ok"] for c in chks) and not any(n == "erro" for n, _ in alertas)) and k + 1 < len(fila):
            dim["tentativas"].append(dict(D=fila[k]["D"], L=fila[k]["L"], motivo="reprovada na análise completa"))
            k += 1
            esc = fila[k]
            p["geometria"]["L"] = esc["L"]
            if esc["DN"] is not None:
                cat = [c for c in CATALOGO_ANEIS if abs(c["DN"] - esc["DN"]) < 1e-6][0]
                p["camisa"]["DN"], p["camisa"]["espessura"] = cat["DN"], cat["e"]
            else:
                p["geometria"]["D"] = esc["D"]
            p = normalizar({kk: v for kk, v in p.items() if not kk.startswith("_")}, pasta_base)
            p["_cota_fim_sond"] = solo["cota_fim"]
            dim["escolha"] = dim["otima"] = esc
            aps = [analisar_perfil(p, pf, solo["na"], combs) for pf in solo["perfis"]]
            est = dimensionar_estrutura(p, aps)
            chks, alertas = verificar(p, aps, est)
    g = p["geometria"]
    if g["cota_base"] - 1.5 * g["D"] < solo["cota_fim"]:
        alertas.append(("aviso", f"A sondagem termina na cota {solo['cota_fim']:.2f}, acima do bulbo da base "
                                 f"({g['cota_base'] - 1.5 * g['D']:.2f})."))
    if p["folga"]["preenchimento"] == "solo_cimento_compactado" and p["folga"]["largura"] < p["folga"]["folga_min_compactacao"]:
        alertas.append(("aviso", f"Folga de {p['folga']['largura'] * 100:.0f} cm: o aterro de solo-cimento compactado exige no "
                                 f"mínimo {p['folga']['folga_min_compactacao'] * 100:.0f} cm para o compactador."))
    if dim and dim.get("aviso_usuario"):
        alertas.append(("aviso", dim["aviso_usuario"]))
    if dim and dim.get("usuario"):
        o = dim.get("otima")
        alertas.append(("info", f"Solução escolhida pelo usuário no mapa D x L: D = {_br(dim['escolha']['D'], 2)} m, L = "
                                f"{_br(dim['escolha']['L'], 2)} m" + (f" (a ótima é D = {_br(o['D'], 2)} m, L = {_br(o['L'], 2)} m)." if o else ".")))
    cl = classificar(p)
    alertas.insert(0, ("aviso" if cl["tipo"] == "intermediaria" else "info", "Classificação: " + cl["texto"]))
    cr, sl = p["criterios"], p["solo"]
    if sl["fs_base"] < 3.0 - 1e-9:
        alertas.append(("aviso", f"q_ult = {_br(sl['fs_base'])}·σadm: a Tabela 1 da NBR 6122 (R08, por 8.2.3.2) pede FS = 3,0 na base, "
                                 "ou 2,0 com duas ou mais provas de carga na fase de projeto."))
    if cr["fator_sigma_vento"] > 1 and sl["fs_base"] / cr["fator_sigma_vento"] < 1.6 - 1e-9:
        alertas.append(("erro", f"σadm × {_br(cr['fator_sigma_vento'])} com vento deixa FS = {_br(sl['fs_base'] / cr['fator_sigma_vento'], 2)} "
                                "na base, abaixo de 1,6 (R08, 6.3.2)."))
    if cl["tipo"] == "rasa":
        if p["lastro"]["espessura"] < 0.05 - 1e-9:
            alertas.append(("aviso", "Lastro com menos de 5 cm (R08, 7.7.3)."))
        if g["D"] < 0.60 - 1e-9:
            alertas.append(("aviso", "Diâmetro menor que 60 cm (R08, 7.7.1)."))
    if g["cota_topo"] > g["cota_terreno"] + 1e-6:
        alertas.append(("aviso", f"Topo do tubulão {_br(g['cota_topo'] - g['cota_terreno'], 2)} m acima do terreno: a NBR 6122 (R08, 8.6.1) "
                                 "pede a verificação dos efeitos de 2ª ordem; no tubulão rígido e curto eles são pequenos."))
    if p["apoio"]["tipo"] == "poste" and p["apoio"]["embutimento"] > g["L"] + 1e-6:
        alertas.append(("erro", "O embutimento do poste é maior que o comprimento do tubulão."))
    if p["apoio"]["tipo"] == "pilar":
        lado = math.hypot(p["apoio"]["a"], p["apoio"]["b"]) if p["apoio"]["secao"] == "retangular" else p["apoio"]["d"]
        if lado > g["D_estrutura"]:
            alertas.append(("erro", "O pilar não cabe na seção do tubulão (diagonal maior que o diâmetro)."))
    vistos, unicos = set(), []
    for a in alertas:
        if a not in vistos:
            vistos.add(a)
            unicos.append(a)
    alertas = unicos
    quant = quantitativos(p, aps[0])
    gov = governante(chks)
    res = dict(versao=VERSAO, p={k: v for k, v in p.items() if not k.startswith("_")}, solo=solo, combinacoes=combs,
               classificacao=cl, concreto_6122=p["_concreto"],
               analises=aps, estrutura=est, verificacoes=chks, alertas=alertas, quantitativos=quant,
               dimensionamento=dim, governante=gov, ok=all(c["ok"] for c in chks) and not any(n == "erro" for n, _ in alertas),
               tempo=time.time() - t0)
    return res


def governante(chks):
    melhor = None
    for c in chks:
        a = c["aproveitamento"]
        if a is None:
            continue
        if c["nome"].startswith("Tombamento"):
            a = (c["limite"] / c["valor"]) if c["valor"] else math.inf
        if melhor is None or a > melhor[0]:
            melhor = (a, c)
    return dict(melhor[1], aproveitamento=melhor[0]) if melhor else None


# --------------------------------------------------------------------------------------------- saída
def _limpo(o):
    """Resultado serializável (sem o objeto Modelo e sem arrays)."""
    if isinstance(o, Modelo):
        return None
    if isinstance(o, dict):
        return {k: _limpo(v) for k, v in o.items() if k != "modelo"}
    if isinstance(o, (list, tuple)):
        return [_limpo(v) for v in o]
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.floating, np.integer, np.bool_)):
        return _limpo(o.item())
    if isinstance(o, float) and (math.isinf(o) or math.isnan(o)):
        return None if math.isnan(o) else ("inf" if o > 0 else "-inf")
    return o


def resultado_json(res):
    return _limpo(res)


def kpa(v):
    return f"{v:.1f} kPa ({v / 98.0665:.2f} kgf/cm²)"


def resumo_texto(res):
    p = res["p"]
    g = p["geometria"]
    L = []
    L.append(f"TUBULÃO {p['nome']} ({p['quantidade']}x) — D = {g['D']:.2f} m, L = {g['L']:.2f} m, base na cota {g['cota_base']:.2f}")
    if p["camisa"]["usar"]:
        L.append(f"  camisa: anéis DN {p['camisa']['DN']:.2f} m, parede {p['camisa']['espessura'] * 100:.0f} cm; folga "
                 f"{p['folga']['largura'] * 100:.0f} cm ({p['folga']['preenchimento']})")
    na = res["solo"]["na"]
    L.append(f"  ruptura lateral: {so.METODOS_PU[p['solo']['metodo_pu']]}; NA na cota {('%.2f' % na) if na is not None else '—'}")
    for ap in res["analises"]:
        rg = ap["rigidez"]
        L.append(f"  [{ap['rotulo']}] σadm = {kpa(ap['sigma_adm'])}; Z = {rg['Z']:.2f}; peso {ap['W']:.1f} kN")
        for e in ap["servico"]:
            L.append(f"    {e['nome'][:70]:70s} θ={e['theta'] * 1000:.2f}‰ u={e['u_topo'] * 1000:.1f} mm "
                     f"pmax={e['p_max']:.0f} kPa comp={e['area_comp'] * 100:.0f}% mob={max(e['mob']):.2f} "
                     f"FS={('%.2f' % e['lam']) if math.isfinite(e['lam']) else '—'} "
                     f"λd={('%.2f' % e['lam_d']) if math.isfinite(e['lam_d']) else '—'}")
    est = res["estrutura"]
    if est.get("simples"):
        s = est["simples"]
        L.append(f"  fuste: concreto simples {'OK' if s['ok'] else 'NÃO PASSA'} (aproveitamento {s['aproveitamento']:.2f})")
    if est.get("armadura"):
        a = est["armadura"]
        L.append(f"  armadura longitudinal: {a['n']} ø{a['bitola']:g} (As = {a['As'] * 1e4:.1f} cm²)"
                 + (f"; estribos {a['estribo']['n']} ø{a['estribo']['bitola']:g} c/{a['estribo']['s'] * 100:.0f}" if a.get("estribo") else ""))
    if est.get("bloco"):
        b = est["bloco"]
        fr = b["fretagem"]
        L.append(f"  topo (bloco parcialmente carregado): σmáx = {b['verif']['s_max']:.0f} kPa ≤ {b['verif']['f_lim']:.0f} kPa; "
                 f"Td = {b['verif_t']['Td']:.0f} kN" + (f"; fretagem {fr['n']} ø{fr['bitola']:g} c/{fr['s'] * 100:.0f}" if fr else ""))
    gv = res["governante"]
    if gv:
        L.append(f"  governa: {gv['nome']} ({gv['perfil']}, {gv['combinacao'][:40]}) — aproveitamento {gv['aproveitamento']:.2f}")
    falhas = [c for c in res["verificacoes"] if not c["ok"]]
    L.append(f"  verificações: {len(res['verificacoes']) - len(falhas)} ok, {len(falhas)} não atendidas")
    for c in falhas[:12]:
        L.append(f"    NÃO ATENDE: {c['grupo']} — {c['nome']} = {c['valor']:.4g} (limite {c['limite']}) [{c['perfil']}; {c['combinacao'][:40]}]")
    for n, msg in res["alertas"]:
        L.append(f"  [{n}] {msg}")
    q = res["quantitativos"]
    L.append(f"  quantitativos por unidade: enchimento {q['concreto_enchimento']:.2f} m3; escavação {q['escavacao']:.2f} m3; "
             f"folga {q['folga']:.2f} m3; lastro {q['lastro']:.2f} m3" + (f"; {q['aneis']} anéis" if 'aneis' in q else ""))
    if res["dimensionamento"]:
        d = res["dimensionamento"]
        L.append(f"  dimensionamento automático: {sum(m['ok'] for m in d['mapa'])} de {len(d['mapa'])} soluções passam; "
                 f"escolhida {('D = %.2f m, L = %.2f m' % (d['escolha']['D'], d['escolha']['L'])) if d['escolha'] else 'nenhuma'}")
    L.append(f"  ({res['tempo']:.1f} s)")
    return "\n".join(L)


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Dimensionamento de tubulão curto (sem TQS)")
    ap.add_argument("json")
    ap.add_argument("--saida")
    a = ap.parse_args()
    sys.stdout.reconfigure(errors="replace")
    par = json.load(open(a.json, encoding="utf-8"))
    res = calcular(par, os.path.dirname(os.path.abspath(a.json)))
    pasta = a.saida or SAIDAS
    os.makedirs(pasta, exist_ok=True)
    base = os.path.join(pasta, res["p"]["nome"])
    json.dump(resultado_json(res), open(base + "_resultado.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    txt = resumo_texto(res)
    open(base + "_resumo.txt", "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
