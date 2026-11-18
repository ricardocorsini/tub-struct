# -*- coding: utf-8 -*-
"""
Parâmetros do solo por camada a partir do SPT e resistência lateral última p_u(z) do tubulão.

Cada camada de 1 m do perfil de cálculo (furo, sondagem média ou envoltória do GEOSPT; o NSPT da cota c vale para
[c, c - 1]) recebe peso específico, ângulo de atrito ou resistência não drenada, coeficiente de reação lateral,
coeficiente de reação vertical, módulo de deformação e coeficiente de Poisson. Cada número leva a sua fonte, que
vai para a memória; qualquer um pode ser trocado pelo usuário (decisão de 17/10/2026).

Fontes (códigos do Referências\\CADASTRO.md; as marcadas "a cadastrar" são correlações clássicas cujo texto ainda
não está na pasta):
- reação lateral: lei q = nh·z·y por metro de largura total (R01, Fórm. 6.9.2, p. 363) e nh da Tab. 6.9.1 (R01);
- reação vertical na base: kv da Tab. 6.10.3 (R01, p. 382), para bases da ordem de 3 m;
- Poisson: Tabela III de R03 (0,29 arenoso, 0,40 argiloso);
- compacidade e consistência pelo NSPT: faixas da NBR 6484 (a cadastrar);
- peso específico: Godoy (1972) (citado em R05, p. 25; a cadastrar);
- φ': Teixeira (1996), φ = √(20·N) + 15° (padrão) ou Godoy (1983), φ = 28° + 0,4·N (a cadastrar);
- Su: Teixeira e Godoy (1996), Su = 10·N kPa (a cadastrar);
- E: Teixeira e Godoy (1996), E = α·K·N (a cadastrar);
- p_u: Brinch Hansen (1961), Broms (1964) ou Rankine 2D (Kp - Ka), como em R01 (Fórm. 6.10.4) e R02 (a cadastrar
  Brinch Hansen e Broms);
- σadm: Alonso, como reproduzido em R05 (p. 23): N/30 MPa para tubulões e N/50 MPa para sapatas.
Unidades: kN, m, kPa.
"""
import math

G = 9.80665                 # kN por tf
GAMA_W = 10.0               # kN/m3
NSPT_MAX_CORREL = 50

METODOS_PU = {"brinch_hansen": "Brinch Hansen (1961)", "broms": "Broms (1964)", "rankine": "Rankine 2D (Kp - Ka)"}
METODOS_PHI = {"teixeira": "Teixeira (1996): φ = √(20 N) + 15°", "godoy": "Godoy (1983): φ = 28° + 0,4 N"}

# NBR 6484: compacidade (areias e siltes arenosos) e consistência (argilas e siltes argilosos)
FAIXAS_AREIA = [(4, "fofa"), (8, "pouco compacta"), (18, "medianamente compacta"), (40, "compacta"),
                (math.inf, "muito compacta")]
FAIXAS_ARGILA = [(2, "muito mole"), (5, "mole"), (10, "média"), (19, "rija"), (math.inf, "dura")]

# Godoy (1972): peso específico (kN/m3). Areias: (natural, saturado); argilas: um valor
GODOY_AREIA = {"fofa": (18, 19), "pouco compacta": (18, 19), "medianamente compacta": (19, 20), "compacta": (20, 21),
               "muito compacta": (20, 21)}
GODOY_ARGILA = {"muito mole": 13, "mole": 15, "média": 17, "rija": 19, "dura": 21}

# Teixeira e Godoy (1996): E = alfa·K·N; K em MPa por solo, alfa por família
TG_K = {"Areia": 0.90, "Areia Siltosa": 0.70, "Areia Silto-Argilosa": 0.70, "Areia Argilo-Siltosa": 0.55,
        "Areia Argilosa": 0.55, "Silte Arenoso": 0.45, "Silte Areno-Argiloso": 0.45, "Silte": 0.35,
        "Silte Argilo-Arenoso": 0.25, "Silte Argiloso": 0.25, "Argila Arenosa": 0.30, "Argila Areno-Siltosa": 0.30,
        "Argila Silto-Arenosa": 0.20, "Argila Siltosa": 0.20, "Argila": 0.20}
TG_ALFA = {"Granular": 3.0, "Intermediário": 5.0, "Coesivo": 7.0}


def classe(n, comportamento):
    for lim, nome in (FAIXAS_AREIA if comportamento == "drenado" else FAIXAS_ARGILA):
        if n <= lim:
            return nome
    return ""


def comportamento_padrao(familia):
    """Granular e Intermediário: drenado (φ'); Coesivo: não drenado (Su), carga lateral de curta duração."""
    return "nao_drenado" if familia == "Coesivo" else "drenado"


# --------------------------------------------------------------------------- tabelas de R01 (tf/m3 -> kN/m3)
def nh_pfeil(n, comportamento, submerso):
    """R01, Tab. 6.9.1 (kh por metro de largura total, q = kh·z·y). Devolve (valor kN/m3, nota)."""
    if comportamento == "drenado":
        if n < 5:
            v, nota = 100, "areia fofa (N < 5): só há o valor submerso, carga estática (100 tf/m3), usado também acima do NA"
        elif n <= 10:
            v, nota = (150 if submerso else 250), "areia média (N 5-10)"
        elif n <= 25:
            v, nota = (500 if submerso else 700), "areia compacta (N 10-25)"
        else:
            v, nota = (1250 if submerso else 2000), "areia muito compacta (N > 25)"
    else:
        if n < 2:
            v, nota = 50, "argila muito mole (N < 2), carga estática"
        elif n <= 4:
            v, nota = 100, "argila mole (N 2-4)"
        elif n <= 10:
            v, nota = 250, "argila média (N 4-10)"
        else:
            v, nota = 250, "argila acima de N = 10: fora da tabela, usado o valor da argila média (a favor da segurança)"
    return v * G, f"R01, Tab. 6.9.1, p. 363: {nota}; {v} tf/m3"


def kv_pfeil(n, comportamento, submerso):
    """R01, Tab. 6.10.3 (bases da ordem de 3 m). Devolve (valor kN/m3, nota)."""
    if comportamento == "drenado":
        if n < 5:
            v, nota = (200 if submerso else 300), "areia fofa (N < 5)"
        elif n <= 10:
            v, nota = (600 if submerso else 1000), "areia média (N 5-10)"
        elif n <= 25:
            v, nota = (2500 if submerso else 4000), "areia compacta (N 10-25)"
        else:
            v, nota = (2500 if submerso else 4000), "N > 25: fora da tabela, usado o valor da areia compacta"
    else:
        if n < 5:
            v = max(50.0, 250.0 * n / 5)
            nota = f"argila com N < 5: fora da tabela, extrapolado de 250 tf/m3 (N 5-10) na proporção de N"
        elif n <= 10:
            v, nota = 250, "argila pré-adensada média (N 5-10)"
        elif n <= 15:
            v, nota = 500, "argila rija (N 10-15)"
        else:
            v, nota = 1000, "argila dura (N > 15)"
    return v * G, f"R01, Tab. 6.10.3, p. 382 (bases da ordem de 3 m): {nota}; {v:g} tf/m3"


# --------------------------------------------------------------------------- correlações com o SPT
def phi_spt(n, metodo="teixeira"):
    n = min(max(n, 0), NSPT_MAX_CORREL)
    if metodo == "godoy":
        return min(28.0 + 0.4 * n, 45.0), "Godoy (1983): φ = 28° + 0,4·N (a cadastrar)"
    return min(math.sqrt(20.0 * n) + 15.0, 45.0), "Teixeira (1996): φ = √(20·N) + 15° (a cadastrar)"


def su_spt(n):
    return 10.0 * min(n, NSPT_MAX_CORREL), "Teixeira e Godoy (1996): Su = 10·N kPa (a cadastrar)"


def gama_spt(n, comportamento):
    c = classe(n, comportamento)
    if comportamento == "drenado":
        g, gs = GODOY_AREIA[c]
        return g, gs, f"Godoy (1972), areia {c}: {g} (natural) e {gs} kN/m3 (saturado) (a cadastrar; citado em R05, p. 25)"
    g = GODOY_ARGILA[c]
    return g, g, f"Godoy (1972), argila {c}: {g} kN/m3 (a cadastrar; citado em R05, p. 25)"


def e_spt(n, solo, familia):
    k = TG_K.get(solo)
    if k is None:
        k = {"Granular": 0.90, "Intermediário": 0.35, "Coesivo": 0.20}.get(familia, 0.35)
    a = TG_ALFA.get(familia, 5.0)
    return a * k * max(n, 1) * 1000.0, f"Teixeira e Godoy (1996): E = α·K·N = {a:g} × {k:g} MPa × {n:g} (a cadastrar)"


def nu_padrao(comportamento):
    return (0.29, "R03, Tabela III: solo arenoso") if comportamento == "drenado" else (0.40, "R03, Tabela III: solo argiloso")


def ka_kp(phi_graus):
    t = math.tan(math.radians(45.0 - phi_graus / 2))
    return t * t, 1.0 / (t * t)


# --------------------------------------------------------------------------- perfil de cálculo
CAMPOS = ("comportamento", "gama", "gama_sat", "phi", "c", "su", "nh", "nh_sub", "kv", "kv_sub", "E", "nu")


def camadas_calculo(perfil, cota_terreno, metodo_phi="teixeira", edicoes=None, nome_perfil=""):
    """Camadas do perfil de cálculo com os parâmetros. perfil: [{cota_m, nspt, solo, familia, ...}] (camada
    [cota_m, cota_m - 1]). A camada acima da 1ª leitura (até o terreno) recebe os parâmetros da 1ª leitura.
    edicoes: [{cota_m, campo: valor}] (valores do usuário). Devolve a lista de camadas, de cima para baixo."""
    if not perfil:
        raise ValueError(f"Perfil {nome_perfil or ''} vazio.")
    ed = {round(float(e["cota_m"]), 3): e for e in (edicoes or [])}
    cams = []
    ordem = sorted(perfil, key=lambda c: -c["cota_m"])
    for i, c in enumerate(ordem):
        n = float(c["nspt"])
        fam = c.get("familia") or ""
        e = ed.get(round(float(c["cota_m"]), 3), {})
        comp = e.get("comportamento") or comportamento_padrao(fam)
        fontes = {}
        g, gs, fontes["gama"] = gama_spt(n, comp)
        if comp == "drenado":
            phi, fontes["phi"] = phi_spt(n, metodo_phi)
            su, fontes["su"] = 0.0, "-"
        else:
            phi, fontes["phi"] = 0.0, "análise não drenada (φ = 0)"
            su, fontes["su"] = su_spt(n)
        nh, fontes["nh"] = nh_pfeil(n, comp, False)
        nhs, fontes["nh_sub"] = nh_pfeil(n, comp, True)
        kv, fontes["kv"] = kv_pfeil(n, comp, False)
        kvs, fontes["kv_sub"] = kv_pfeil(n, comp, True)
        E, fontes["E"] = e_spt(n, c.get("solo") or "", fam)
        nu, fontes["nu"] = nu_padrao(comp)
        cam = dict(cota_m=float(c["cota_m"]), topo=float(c["cota_m"]), base=float(c["cota_m"]) - 1.0, nspt=n,
                   solo=c.get("solo") or "", familia=fam, heterogeneo=bool(c.get("heterogeneo")), furo=c.get("furo", ""),
                   cor=c.get("cor") or "", comportamento=comp, classe=classe(n, comp), gama=g, gama_sat=gs, phi=phi,
                   c=0.0, su=su, nh=nh, nh_sub=nhs, kv=kv, kv_sub=kvs, E=E, nu=nu, fontes=fontes, editados=[])
        for k in CAMPOS:
            if k in e and e[k] not in (None, "") and k != "comportamento":
                cam[k] = float(e[k])
                cam["fontes"][k] = "valor do usuário"
                cam["editados"].append(k)
        if "comportamento" in e and e["comportamento"]:
            cam["editados"].append("comportamento")
        cams.append(cam)
    if cota_terreno > cams[0]["topo"] + 1e-6:          # trecho entre o terreno e a 1ª leitura
        c0 = dict(cams[0])
        c0.update(topo=cota_terreno, base=cams[0]["topo"], cota_m=cota_terreno, extrapolada=True,
                  fontes=dict(cams[0]["fontes"]))
        cams.insert(0, c0)
    for i in range(len(cams) - 1):                      # lacunas do perfil: a camada de cima desce até a de baixo
        if cams[i]["base"] > cams[i + 1]["topo"] + 1e-6:
            cams[i]["base"] = cams[i + 1]["topo"]
    return cams


def camada_em(cams, cota):
    for c in cams:
        if c["topo"] + 1e-9 >= cota > c["base"] - 1e-9:
            return c
    return cams[-1] if cota <= cams[-1]["base"] else cams[0]


def sigma_v(cams, cota_terreno, na, cota):
    """Tensão vertical efetiva (kPa) na cota, integrando do terreno (γ acima do NA, γsat - γw abaixo)."""
    if cota >= cota_terreno:
        return 0.0
    s = 0.0
    for i, c in enumerate(cams):
        top = min(c["topo"], cota_terreno)
        bot = max(c["base"] if i < len(cams) - 1 else -math.inf, cota)   # a última camada continua para baixo
        if top <= bot:
            continue
        if na is None:
            s += (top - bot) * c["gama"]
            continue
        if top > max(bot, na):                                            # trecho acima do NA
            s += (top - max(bot, na)) * c["gama"]
        if min(top, na) > bot:                                            # trecho abaixo do NA
            s += (min(top, na) - bot) * (c["gama_sat"] - GAMA_W)
    return s


# --------------------------------------------------------------------------- p_u (kN por metro de fuste)
def brinch_hansen_k(phi_graus, z_d):
    """Coeficientes Kq e Kc de Brinch Hansen (1961) na profundidade relativa z/D."""
    p = math.radians(max(phi_graus, 0.0))
    if p < 1e-4:
        kq0 = kqi = 0.0
        kc0, kci = math.pi / 2 + 1.0, (math.pi + 2.0) * 1.58
    else:
        t, cp = math.tan(p), math.cos(p)
        kq0 = math.exp((math.pi / 2 + p) * t) * cp * math.tan(math.pi / 4 + p / 2) - \
            math.exp(-(math.pi / 2 - p) * t) * cp * math.tan(math.pi / 4 - p / 2)
        kc0 = (math.exp((math.pi / 2 + p) * t) * cp * math.tan(math.pi / 4 + p / 2) - 1.0) / t
        nc = (math.exp(math.pi * t) * math.tan(math.pi / 4 + p / 2) ** 2 - 1.0) / t
        kci = nc * (1.58 + 4.09 * t ** 4)
        kqi = kci * (1.0 - math.sin(p)) * t
    aq = 0.0 if kqi <= kq0 else kq0 / (kqi - kq0) * (1.0 - math.sin(p)) * math.sin(p) / math.sin(math.pi / 4 + p / 2)
    ac = kc0 / (kci - kc0) * 2.0 * math.sin(math.pi / 4 + p / 2)
    kq = (kq0 + kqi * aq * z_d) / (1.0 + aq * z_d)
    kc = (kc0 + kci * ac * z_d) / (1.0 + ac * z_d)
    return kq, kc


def p_ultimo(metodo, cam, sv, z_s, D):
    """Resistência lateral última por metro de fuste (kN/m), na profundidade z_s abaixo do terreno."""
    if cam["comportamento"] == "nao_drenado":
        su = cam["su"]
        if metodo == "broms":
            return 9.0 * su * D if z_s > 1.5 * D else 0.0
        if metodo == "rankine":
            return 4.0 * su * D
        _, kc = brinch_hansen_k(0.0, z_s / D)
        return kc * su * D
    phi, c = cam["phi"], cam["c"]
    ka, kp = ka_kp(phi)
    if metodo == "broms":
        return 3.0 * kp * sv * D
    if metodo == "rankine":
        return ((kp - ka) * sv + 2.0 * c * (math.sqrt(kp) + math.sqrt(ka))) * D
    kq, kc = brinch_hansen_k(phi, z_s / D)
    return (kq * sv + kc * c) * D


# --------------------------------------------------------------------------- tensão admissível na base
def sigma_adm_alonso(cams, cota_base, D, L):
    """σadm (kPa) pelo método de Alonso (R05, p. 23): N/30 MPa para tubulão e N/50 MPa para sapata. N = média do
    NSPT das camadas da base até 1,5·D abaixo dela (bulbo; R05 usou a camada da base e as duas de baixo para D = 2 m).
    Tubulão se L ≥ 2·D; senão, a fórmula das sapatas (sem confinamento, como em R05)."""
    fundo = cota_base - 1.5 * D
    ns = [c["nspt"] for c in cams if c["topo"] > fundo + 1e-9 and c["base"] < cota_base - 1e-9 and not c.get("extrapolada")]
    if not ns:
        ns = [camada_em(cams, cota_base - 0.01)["nspt"]]
    n = sum(ns) / len(ns)
    tub = L >= 2.0 * D
    div = 30.0 if tub else 50.0
    return n / div * 1000.0, (f"Alonso (R05, p. 23), {'tubulão' if tub else 'sapata (L < 2D, sem confinamento)'}: "
                              f"σadm = N/{div:g} MPa, N = média de {len(ns)} camada(s) do bulbo (1,5·D abaixo da base) = "
                              f"{n:.1f}"), n
