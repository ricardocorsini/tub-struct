# -*- coding: utf-8 -*-
"""
Verificações de concreto do fuste e do topo do tubulão pela ABNT NBR 6118:2026 (R07). Unidades: kN, m, kPa.

- Concreto simples (Seção 24): o fuste dentro do solo, ou dentro dos anéis, tem o confinamento lateral que 24.2
  exige ("caso de estacas ou tubos"). γc = 1,68 (24.5.2.1); σcRd = 0,85·fcd e σctRd = 0,85·fctd nas fibras
  extremas (24.5.2.2); fctd = fctk,inf/γc com fctk,inf = 0,7·0,3·fck^(2/3) (8.2.5); cisalhamento
  τwRd = 0,30·fctd·(1 + 3·σcmd/fck), fator ≤ 2 (24.5.2.3); concreto lançado contra o solo: altura 5 cm menor
  (24.5.3). Tensões elásticas na seção bruta; cisalhamento máximo da seção circular 4·V/(3·A).
- Concreto armado: seção circular com barras no contorno, diagrama parábola-retângulo de 8.2.10.1
  (σc = 0,85·ηc·fcd·[1 - (1 - εc/εc2)^n], ηc = 1 até C40), εc2 = 2 ‰ e εcu = 3,5 ‰ até C50, aço com patamar
  (fyd, εyd) e alongamento limite de 10 ‰; momento resistente pela compatibilidade de deformações.
- Bloco parcialmente carregado (21.2.1): FRd = Ac0·fcd·√(Ac1/Ac0) ≤ 3,3·fcd·Ac0, com Ac1 homotética a Ac0 e
  inscrita na seção do tubulão; carga excêntrica com a área reduzida (a - 2e)·(b - 2e), porque a norma manda
  reduzir o valor quando a carga não é uniforme. Tirante de fendilhamento por bielas e tirantes (Seção 22):
  T = 0,25·Nd·(1 - a/b) em cada direção (o par de bielas abre de a/4 para b/4 com braço b/2), resistido por
  estribos circulares de fretagem entre 0,1·b e b abaixo do topo.
- NBR 6122:2022 (R08), 8.6.3, 8.6.4.1 e Tabela 4: o γc do tubulão depende da camisa (parametros_6122). Sem camisa
  (concreto lançado contra o solo), γc = 2,2 (CAA I e II, C25) ou 3,6 (III e IV, C40), também no concreto simples
  e no topo; com camisa de concreto (os anéis), γc = 1,4 na seção armada e 1,68 no concreto simples (NBR 6118). O
  pilar continua com γc = 1,4. Com flexão, a armadura é calculada com as barras 2 mm mais finas (8.6.2).
"""
import math
import numpy as np

GAMA_C, GAMA_S, GAMA_C_SIMPLES = 1.4, 1.15, 1.68
ES = 210e6                      # kPa
BITOLAS = [6.3, 8.0, 10.0, 12.5, 16.0, 20.0, 25.0, 32.0]


def fctm(fck):
    return 0.3 * fck ** (2 / 3) if fck <= 50 else 2.12 * math.log(1 + 0.1 * (fck + 8))


def modulo_ecs(fck, agregado="granito"):
    """Ecs (kPa), NBR 6118:2026 8.2.8."""
    ae = {"basalto": 1.2, "diabasio": 1.2, "granito": 1.0, "gnaisse": 1.0, "calcario": 0.9, "arenito": 0.7}.get(agregado, 1.0)
    eci = ae * 5600 * math.sqrt(fck)
    return min(0.8 + 0.2 * fck / 80, 1.0) * eci * 1000.0


def area_barra(b_mm):
    return math.pi * (b_mm / 1000) ** 2 / 4


# ------------------------------------------------------------------------------------- concreto simples
def parametros_6122(caa, encamisado):
    """γc, classe mínima e tensão de compressão simples abaixo da qual não é preciso armar (R08, Tabela 4, linha
    "Tubulões não encamisados", e 8.6.4.1 para a camisa de concreto). caa: "I" a "IV"."""
    c = str(caa).strip().upper()
    agress = c in ("III", "IV")
    if encamisado:
        # concreto lançado dentro dos anéis: classe e a/c do concreto armado da NBR 6118 (R07, Tabela 7.1)
        fck_min, ac = {"I": (20.0, 0.65), "II": (25.0, 0.60), "III": (30.0, 0.55), "IV": (40.0, 0.45)}.get(c, (25.0, 0.60))
        return dict(gc_armado=GAMA_C, gc_simples=GAMA_C_SIMPLES, fck_min=fck_min, sigma_sem_armar=5000.0, ac_max=ac,
                    cimento_min=None, ref_classe="R07, Tabela 7.1",
                    nota=f"tubulão com camisa de concreto (anéis): γc = 1,4 na seção armada (R08, 8.6.4.1) e 1,68 no concreto "
                         f"simples (R07, 24.5.2.1); C{fck_min:g} e a/c ≤ {f'{ac:.2f}'.replace('.', ',')} para a CAA {c} (R07, Tabela 7.1); compressão "
                         "simples sem armar até 5 MPa, como na Tabela 4 (R08), a favor da segurança")
    fck_min = 40.0 if agress else 25.0
    gc = 3.6 if agress else 2.2
    return dict(gc_armado=gc, gc_simples=max(gc, GAMA_C_SIMPLES), fck_min=fck_min, sigma_sem_armar=5000.0,
                ac_max=0.45 if agress else 0.60, cimento_min=360 if agress else 280, ref_classe="R08, Tabela 4",
                nota=f"tubulão não encamisado, CAA {c}: C{fck_min:g} no mínimo e γc = {f'{gc:g}'.replace('.', ',')} (R08, Tabela 4); traço do Anexo B (B.9)")


def traco_anexo_b(fck, caa):
    """Recomendações do concreto de tubulão a céu aberto (R08, B.9): a linha do C40 vale a partir de 40 MPa e nas CAA
    III e IV; abaixo disso, a do C25."""
    c40 = fck >= 40 or str(caa).strip().upper() in ("III", "IV")
    return dict(classe="C40" if c40 else "C25", abatimento="100 A 160 mm (S100)", agregado="9,5 A 25 mm", exsudacao="< 4 %",
                cimento=360 if c40 else 280, ac=0.45 if c40 else 0.60)


def concreto_simples(D, fck, N, M, V, contra_solo, gama_c=GAMA_C_SIMPLES):
    """Verificação de uma seção circular de concreto simples. N > 0 compressão (kN), M (kN.m), V (kN), de cálculo."""
    h = D - (0.05 if contra_solo else 0.0)
    A, W = math.pi * h * h / 4, math.pi * h ** 3 / 32
    fcd = fck / gama_c * 1000
    fctd = 0.7 * fctm(fck) / gama_c * 1000
    sc_rd, st_rd = 0.85 * fcd, 0.85 * fctd
    s_max = N / A + abs(M) / W
    s_min = N / A - abs(M) / W                    # negativo = tração
    scmd = max(N / A, 0.0)
    fat = min(1 + 3 * scmd / (fck * 1000), 2.0)
    tau_rd = 0.30 * fctd * fat
    tau = 4 * abs(V) / (3 * A)
    return dict(h=h, A=A, W=W, gama_c=gama_c, fcd=fcd, fctd=fctd, sc_rd=sc_rd, st_rd=st_rd, s_max=s_max, s_min=s_min,
                tau=tau, tau_rd=tau_rd, fator_n=fat,
                ok_comp=s_max <= sc_rd, ok_trac=-s_min <= st_rd if s_min < 0 else True, ok_cis=tau <= tau_rd,
                aproveitamento=max(s_max / sc_rd, (-s_min / st_rd) if s_min < 0 else 0.0, tau / tau_rd))


# ------------------------------------------------------------------------------------- seção armada
def _sigma_c(ec, fck, gama_c=GAMA_C):
    if ec <= 0:
        return 0.0
    eta = 1.0 if fck <= 40 else (40 / fck) ** (1 / 3)
    fcd = fck / gama_c * 1000
    n = 2.0 if fck <= 50 else 1.4 + 23.4 * ((90 - fck) / 100) ** 4
    ec2 = 0.002 if fck <= 50 else 0.002 + 0.000085 * (fck - 50) ** 0.53
    return 0.85 * eta * fcd * (1 - (1 - min(ec, ec2) / ec2) ** n)


def _limites(fck):
    if fck <= 50:
        return 0.002, 0.0035
    return 0.002 + 0.000085 * (fck - 50) ** 0.53, 0.0026 + 0.035 * ((90 - fck) / 100) ** 4


def esforcos_resistentes(D, fck, fyk, nbar, bitola, cobr, e_top, e_bot, nfaixas=80, gama_c=GAMA_C, sacrificio=0.0):
    """(N_R, M_R) da seção circular para o estado de deformação linear (e_top na fibra de cima, e_bot na de baixo;
    encurtamento positivo). M positivo com compressão em cima. sacrificio: redução do diâmetro das barras (mm) na
    área resistente (R08, 8.6.2)."""
    R = D / 2
    rs = R - cobr - bitola / 2000
    fyd = fyk / GAMA_S * 1000
    eps = lambda y: e_top + (e_bot - e_top) * y / D          # y medido da fibra de cima
    N = M = 0.0
    dy = D / nfaixas
    for i in range(nfaixas):                                  # faixas horizontais do círculo
        yc = (i + 0.5) * dy
        larg = 2 * math.sqrt(max(R * R - (R - yc) ** 2, 0.0))
        s = _sigma_c(eps(yc), fck, gama_c) * larg * dy
        N += s
        M += s * (R - yc)
    ab = area_barra(bitola - sacrificio)
    for k in range(nbar):
        yb = R - rs * math.cos(2 * math.pi * k / nbar)
        es = eps(yb)
        f = (max(-fyd, min(fyd, es * ES)) - _sigma_c(es, fck, gama_c)) * ab   # desconta o concreto deslocado pela barra
        N += f
        M += f * (R - yb)
    return N, M


def estados_ultimos(D, fck, cobr, bitola, n=60):
    """Estados de deformação na fronteira dos domínios do ELU, da tração uniforme à compressão uniforme: pivô A
    (aço a 10 ‰ na barra mais baixa), pivô B (εcu na fibra de cima) e pivô C (εc2 a (εcu - εc2)/εcu·h do topo)."""
    ec2, ecu = _limites(fck)
    d = D / 2 + (D / 2 - cobr - bitola / 2000)
    est = []
    for i in range(n + 1):                                    # pivô A
        et = -0.010 + (ecu + 0.010) * i / n
        est.append((et, et + (-0.010 - et) * D / d))
    x23 = ecu / (ecu + 0.010) * d
    for i in range(1, n + 1):                                 # pivô B
        x = x23 + (D - x23) * i / n
        est.append((ecu, ecu * (1 - D / x)))
    yc = (ecu - ec2) / ecu * D
    for i in range(1, n + 1):                                 # pivô C
        eb = ec2 * i / n
        sl = (eb - ec2) / (D - yc)
        est.append((ec2 - sl * yc, eb))
    return est


def diagrama_interacao(D, fck, fyk, nbar, bitola, cobr, gama_c=GAMA_C, sacrificio=0.0):
    """Pontos (N_R, M_R) da fronteira do ELU, da tração à compressão uniforme (ver estados_ultimos)."""
    return [esforcos_resistentes(D, fck, fyk, nbar, bitola, cobr, et, eb, gama_c=gama_c, sacrificio=sacrificio)
            for et, eb in estados_ultimos(D, fck, cobr, bitola)]


def m_do_diagrama(pts, Nd):
    """M_Rd do diagrama para a força normal Nd (interpolação linear). None se Nd fora do intervalo resistente."""
    for (n1, m1), (n2, m2) in zip(pts, pts[1:]):
        if (n1 - Nd) * (n2 - Nd) <= 0 and n1 != n2:
            t = (Nd - n1) / (n2 - n1)
            return m1 + t * (m2 - m1)
    return None


def momento_resistente(D, fck, fyk, nbar, bitola, cobr, Nd, gama_c=GAMA_C, sacrificio=0.0):
    """M_Rd (kN.m) para a força normal de cálculo Nd (compressão > 0). None se Nd fora do intervalo resistente."""
    pts = diagrama_interacao(D, fck, fyk, nbar, bitola, cobr, gama_c, sacrificio)
    for (n1, m1), (n2, m2) in zip(pts, pts[1:]):
        if (n1 - Nd) * (n2 - Nd) <= 0 and n1 != n2:
            t = (Nd - n1) / (n2 - n1)
            return m1 + t * (m2 - m1)
    return None


def armadura_longitudinal(D, fck, fyk, cobr, solicitacoes, as_min, bitolas=(10.0, 12.5, 16.0, 20.0, 25.0),
                          espac_max=0.20, espac_min=0.08, gama_c=GAMA_C, sacrificio=0.0, par=False):
    """Menor armadura (n barras de mesma bitola no contorno) que atende todas as solicitações [(Nd, Md)] e a
    área mínima. par: só número par de barras (os grampos da grelha abraçam pares simétricos). Devolve dict ou None."""
    rs = D / 2 - cobr
    melhor = None
    sol = sorted(solicitacoes, key=lambda t: -abs(t[1]))      # maiores momentos primeiro: reprova mais cedo
    for b in bitolas:
        nmin = max(6, math.ceil(2 * math.pi * rs / espac_max), math.ceil(as_min / area_barra(b) - 1e-9))
        for n in range(nmin + (nmin % 2 if par else 0), 200, 2 if par else 1):
            if 2 * math.pi * rs / n < espac_min:
                break
            pts = diagrama_interacao(D, fck, fyk, n, b, cobr, gama_c, sacrificio)
            ok = True
            for Nd, Md in sol:
                mr = m_do_diagrama(pts, Nd)
                if mr is None or mr < abs(Md):
                    ok = False
                    break
            if ok:
                a = n * area_barra(b)
                if melhor is None or a < melhor["As"] - 1e-12:
                    melhor = dict(n=n, bitola=b, As=a, espac=2 * math.pi * rs / n)
                break
    return melhor


# ------------------------------------------------------------------------------------- bloco parcialmente carregado
def bloco_parcial(D, fck, fyk, pilar, Nd, Mxd=0.0, Myd=0.0, fck_pilar=None, gama_c=GAMA_C):
    """Topo do tubulão sob pilar apoiado direto (R07, 21.2.1 e Seção 22). Em cada direção do pilar (a em x, b em y):
    - excentricidade e = M/N no núcleo central (e ≤ a/6): compressão em toda a seção, C = Nd, largura comprimida
      a_c = a e pressão de pico Nd/(a·b)·(1 + 6e/a);
    - fora do núcleo, a armadura do pilar absorve a tração (ancoragem fora do escopo) e o binário tem braço
      z = 0,8·a: C = Nd/2 + M/z, com o bloco comprimido do pilar em 0,85·fcd do pilar: a_c = C/(0,85·fcd,p·b) ≤ a e
      pressão C/(a_c·b).
    A pressão (o maior valor das duas direções) é comparada com fcd·√(Ac1/Ac0) ≤ 3,3·fcd, Ac0 = seção do pilar e Ac1
    homotética inscrita no círculo do tubulão. Tirante de fendilhamento: T = 0,25·C·(1 - a_c/D) em cada direção
    (o par de bielas abre de a_c/4 para D/4 com braço D/2). Pilar circular: quadrado de mesma área. gama_c: o do
    concreto do tubulão (parametros_6122); o pilar fica com 1,4."""
    fcd = fck / gama_c * 1000
    fcd_p = (fck_pilar or fck) / GAMA_C * 1000
    fyd = fyk / GAMA_S * 1000
    out = dict(avisos=[])
    if pilar.get("secao") == "circular":
        a = b = pilar["d"] * math.sqrt(math.pi) / 2
        ac0, ac1 = math.pi * pilar["d"] ** 2 / 4, math.pi * D * D / 4
    else:
        a, b = pilar["a"], pilar["b"]
        if max(a, b) / min(a, b) > 2:
            out["avisos"].append(f"Pilar {a * 100:.0f} x {b * 100:.0f}: lados na proporção maior que 2; a NBR 6118 "
                                 "(21.2.1) limita Ac0 a essa proporção.")
        ac0 = a * b
        k = D / math.hypot(a, b)                       # retângulo homotético inscrito no círculo
        ac1 = k * k * ac0
    f_lim = min(fcd * math.sqrt(ac1 / ac0), 3.3 * fcd)
    if Nd <= 0:
        out.update(ok=True, Ac0=ac0, Ac1=ac1, f_lim=f_lim, FRd=f_lim * ac0, s_max=0.0, Td=0.0, Tx=0.0, Ty=0.0,
                   As_fret=0.0, ax=a, ay=b, Cx=0.0, Cy=0.0, zona=(0.1 * D, D))
        if Nd < 0:
            out["avisos"].append("Pilar tracionado no topo do tubulão: a ancoragem do pilar (fora do escopo) resiste à tração.")
        return out
    def direcao(dim, outra, M):
        e = abs(M) / Nd
        if e <= dim / 6:
            return Nd, dim, Nd / (dim * outra) * (1 + 6 * e / dim), "núcleo central"
        C = Nd / 2 + abs(M) / (0.8 * dim)
        ac = min(dim, C / (0.85 * fcd_p * outra))
        return C, ac, C / (ac * outra), "fora do núcleo: binário com a armadura do pilar"
    Cx, ax, sx, mx = direcao(a, b, Myd)
    Cy, ay, sy, my = direcao(b, a, Mxd)
    s_ref = max(sx, sy)
    tx = 0.25 * Cx * max(0.0, 1 - ax / D)
    ty = 0.25 * Cy * max(0.0, 1 - ay / D)
    td = max(tx, ty)
    out.update(ok=s_ref <= f_lim, fcd=fcd, Ac0=ac0, Ac1=ac1, f_lim=f_lim, FRd=f_lim * ac0, s_max=s_ref, Cx=Cx, Cy=Cy,
               ax=ax, ay=ay, modo_x=mx, modo_y=my, Tx=tx, Ty=ty, Td=td, As_fret=td / fyd, zona=(0.1 * D, D))
    return out


def comprimento_ancoragem(fck, bitola_mm, gama_c=GAMA_C, fyk=500.0):
    """lb básico (m), R07 9.4.2.4: lb = (φ/4)·(fyd/fbd) ≥ 25·φ, com fbd = η1·η2·η3·fctd (9.3.2.1): barra nervurada
    (η1 = 2,25), vertical e portanto em boa aderência (η2 = 1, 9.3.1), η3 = 1 até ø32; fctd = 0,7·fctm/γc com o γc do
    concreto do tubulão (R08, 8.6.3), a favor da segurança."""
    fctd = 0.7 * fctm(fck) / gama_c
    eta3 = 1.0 if bitola_mm < 32 else (132 - bitola_mm) / 100
    fbd = 2.25 * 1.0 * eta3 * fctd
    phi = bitola_mm / 1000
    return max(phi / 4 * (fyk / GAMA_S) / fbd, 25 * phi)


def estribos_fuste(phi_l, D, cobr, z_fim, fret=None, bitolas=(5.0, 6.3, 8.0, 10.0)):
    """Estribos construtivos do fuste armado, como os de pilar (R07, 18.4.3): φt ≥ 5 mm e ≥ φl/4; espaçamento ≤ 200 mm,
    ≤ menor dimensão da seção e ≤ 12·φl (CA-50), em cm inteiros. Vão do fim da fretagem (que faz o papel deles no topo)
    ou do cobrimento do topo até z_fim, o fim das barras longitudinais. Devolve None se não houver trecho."""
    bt = next(b for b in bitolas if b >= max(5.0, phi_l / 4) - 1e-9)
    s_max = min(0.20, D, 12 * phi_l / 1000)
    s = math.floor(s_max * 100 + 1e-9) / 100
    z1 = fret["z2"] + s if fret else cobr
    z2 = z_fim
    if z2 < z1 - 1e-9:
        return None
    n = int(math.floor((z2 - z1) / s + 1e-9)) + 1
    return dict(bitola=bt, s=s, s_max=s_max, z1=z1, z2=z1 + (n - 1) * s, n=n, raio=D / 2 - cobr - bt / 2000)


def grelha_fretagem(Tx, Ty, r_int, zona, fyk=500.0, bitolas=(8.0, 10.0, 12.5, 16.0), s_camadas=0.20, s_barras=0.15,
                    n_min=3):
    """Fretagem em grelha (pilar pequeno em relação ao tubulão: a tração de fendilhamento se concentra perto do eixo,
    sob o pilar): camadas de barras retas nas duas direções, centradas sob o pilar, a cada s_camadas no trecho de
    fendilhamento (zona = (z1, z2) abaixo do topo). Em cada direção, n_camadas·n_barras·A ≥ T/fyd, com as barras a
    s_barras em planta e no mínimo n_min por camada. Todas as barras com o comprimento da corda da barra mais afastada
    do eixo, dentro do raio r_int (por dentro dos anéis ou da armadura longitudinal). Devolve None se nada couber."""
    z1, z2 = zona
    fyd = fyk / GAMA_S * 1000
    nc = int(math.floor((z2 - z1) / s_camadas + 1e-9)) + 1
    for b in bitolas:
        a = area_barra(b)
        nx = max(n_min, math.ceil(Tx / fyd / (nc * a) - 1e-9))
        ny = max(n_min, math.ceil(Ty / fyd / (nc * a) - 1e-9))
        y_max = (max(nx, ny) - 1) / 2 * s_barras
        if y_max < 0.6 * r_int:
            comp = math.floor(2 * math.sqrt(r_int * r_int - y_max * y_max) * 100 - 1e-6) / 100
            return dict(bitola=b, n_camadas=nc, nx=nx, ny=ny, s_barras=s_barras, s_camadas=s_camadas, z1=z1,
                        z2=z1 + (nc - 1) * s_camadas, comp=comp, As_x=Tx / fyd, As_y=Ty / fyd,
                        As_x_ef=nc * nx * a, As_y_ef=nc * ny * a, r_int=r_int)
    return None


def grampos(gr, r, phi_v, n_barras=None):
    """Grampos da grelha de fretagem com os ganchos de 180° abraçando as barras verticais. O TQS mede o grampo de face
    externa a face externa dos ganchos e desenha o gancho com raio externo de 3,5·φ (pino de 5·φ, R07 Tabela 9.1),
    voltado para +90° do sentido da barra. A barra vertical fica dentro do gancho, encostada na face interna do
    fundo (onde o grampo tracionado se apoia): face externa do gancho = eixo da barra + φv/2 + φg. Assim o gancho
    ocupa o mesmo espaço do estribo e não invade o cobrimento quando φg ≤ φ do estribo.
    - Sem n_barras (barras de montagem): barras no círculo de raio r, nos afastamentos da grelha (a montagem vai
      nesses pontos).
    - Com n_barras (armadura longitudinal: barras a 2·π·j/n a partir do ângulo 0, raio r, n par): em cada
      afastamento, a barra mais próxima; a outra ponta abraça a simétrica (π − θ nas barras em x, −θ nas em y).
    Devolve [dict(dir, bx, by, comp)]: (bx, by) = barra da ponta positiva (bx > 0 nos grampos em x, by > 0 nos em
    y), em m; comp = comprimento de face externa a face externa, arredondado ao cm para baixo."""
    pg, pv = gr["bitola"] / 1000, phi_v / 1000
    sb = gr["s_barras"]
    out = []
    usados = set()
    for dr, n_ in (("X", gr["nx"]), ("Y", gr["ny"])):
        offs = sorted(((k - (n_ - 1) / 2) * sb for k in range(n_)), key=abs)
        for o in offs:
            if n_barras:
                n = n_barras
                cand = []
                for j in range(n):
                    t = 2 * math.pi * j / n
                    c, s_ = r * math.cos(t), r * math.sin(t)
                    if dr == "X" and c > 1e-9:
                        cand.append((abs(s_ - o), j, c, s_))
                    elif dr == "Y" and s_ > 1e-9:
                        cand.append((abs(c - o), j, c, s_))
                _, j, bx, by = min((cd for cd in cand if (dr, cd[1]) not in usados), default=min(cand))
                usados.add((dr, j))
            elif dr == "X":
                bx, by = math.sqrt(max(r * r - o * o, 0.0)), o
            else:
                bx, by = o, math.sqrt(max(r * r - o * o, 0.0))
            meio = bx if dr == "X" else by
            out.append(dict(dir=dr, bx=bx, by=by, comp=math.floor(2 * (meio + pv / 2 + pg) * 100 + 1e-6) / 100))
    return out


def montagem(D, cobr, z_fim, phi_estribo, bitola=10.0, espac_max=0.50, n_min=6, offs_x=None, offs_y=None):
    """Barras verticais de montagem (porta-estribos) para a gaiola da fretagem quando o fuste não é armado: só
    construtivas, encostadas por dentro dos estribos, do cobrimento do topo até z_fim. Sem grelha, igualmente
    espaçadas. Com grelha (offs_x, offs_y = afastamentos das barras da grelha em relação ao eixo), uma barra em cada
    ponta das barras da grelha, para os ganchos as abraçarem, mais barras nos vãos para o espaçamento não passar de
    espac_max. Devolve as posições (x, y) em relação ao centro."""
    r = D / 2 - cobr - phi_estribo / 1000 - bitola / 2000
    angs, n_pontas = [], 0
    if offs_x or offs_y:
        for o in offs_x or []:                      # barras em x: pontas em (±√(r² − o²), o)
            a = math.asin(max(-1.0, min(1.0, o / r)))
            angs += [a, math.pi - a]
        for o in offs_y or []:                      # barras em y: pontas em (o, ±√(r² − o²))
            a = math.asin(max(-1.0, min(1.0, o / r)))
            angs += [math.pi / 2 - a, -math.pi / 2 + a]
        angs = sorted({round(a % (2 * math.pi), 6) for a in angs})
        n_pontas = len(angs)
        novos = []
        for k, a in enumerate(angs):                # vãos entre as pontas: barras extras igualmente espaçadas
            b = angs[(k + 1) % len(angs)] + (2 * math.pi if k + 1 == len(angs) else 0.0)
            nv = math.ceil(r * (b - a) / espac_max - 1e-9) - 1
            novos += [a + (b - a) * j / (nv + 1) for j in range(1, nv + 1)]
        angs = sorted(a % (2 * math.pi) for a in angs + novos)
    if len(angs) < n_min:
        n = max(n_min, math.ceil(2 * math.pi * r / espac_max - 1e-9))
        angs, n_pontas = [2 * math.pi * k / n for k in range(n)], 0
    vaos = [r * ((angs[(k + 1) % len(angs)] - a) % (2 * math.pi) or 2 * math.pi) for k, a in enumerate(angs)]
    return dict(bitola=bitola, n=len(angs), raio=r, pos=[(r * math.cos(a), r * math.sin(a)) for a in angs], n_pontas=n_pontas,
                espac=max(vaos), z_fim=z_fim, comp=z_fim - cobr)


def fretagem(As, D, cobr, zona, bitolas=(8.0, 10.0, 12.5, 16.0), s_min=0.05, s_max=0.15):
    """Estribos circulares de fretagem: cada estribo cruza um plano diametral duas vezes (2·A por estribo).
    Escolhe a menor bitola com espaçamento entre s_min e s_max na zona (z1, z2) abaixo do topo."""
    z1, z2 = zona
    comp = z2 - z1
    for b in bitolas:
        n = max(2, math.ceil(As / (2 * area_barra(b)) - 1e-9))
        s = min(comp / max(n - 1, 1), s_max)
        s = math.floor(s * 100 + 1e-9) / 100                 # espaçamento em centímetros inteiros
        if s >= s_min:
            n = int(math.floor(comp / s + 1e-9)) + 1          # estribos que cabem na zona com esse espaçamento
            return dict(bitola=b, n=n, s=s, z1=z1, z2=z1 + (n - 1) * s, As_ef=2 * n * area_barra(b),
                        raio=D / 2 - cobr - b / 2000)
    return None
