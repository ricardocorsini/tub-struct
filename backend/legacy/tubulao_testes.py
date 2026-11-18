# -*- coding: utf-8 -*-
"""
Validação do app de tubulões curtos com as referências (códigos do Referências\\CADASTRO.md do original; na cópia
portátil, a lista está no LEIA-ME.md).

  R01 Pfeil, Ex. 6.10.2.2 (p. 385): tubulão sem base alargada, solução linear
  R02 Timerman, exemplo numérico (p. 23-24) e R03 (TubCurto): base alargada, solução linear
  R05 memória, solução 03 (p. 46): a rotina R04 com a "base falsa" (Df 1,9; Db 2,0)
  GEOSPT: média e envoltória do arquivo de Pinheiro iguais às exportadas pelo próprio GEOSPT
  GEOSPT: regras de cota heterogênea e de cor em um caso montado
  Ruptura: pushover e equilíbrio limite concordam no caso alinhado
  Grampos da grelha: ganchos de 180° abraçando as barras, sem invadir o cobrimento

Uso: python tubulao_testes.py
"""
import os, sys, json, math
import dependencias                       # cópia portátil: sem o numpy, diz o que falta e sai
dependencias.exigir_calculo()
import numpy as np
import tubulao_core as tcore
import tubulao_sondagem as ts
import tubulao_solo as so
import tubulao_concreto as tc

AQUI = os.path.dirname(os.path.abspath(__file__))
G = so.G
falhas = []


def confere(nome, valor, esperado, tol_rel=0.01, tol_abs=None):
    ok = abs(valor - esperado) <= (tol_abs if tol_abs is not None else tol_rel * max(abs(esperado), 1e-12))
    print(f"  {'ok ' if ok else 'ERRO'} {nome}: {valor:.6g} (esperado {esperado:.6g})")
    if not ok:
        falhas.append(nome)


def modelo_homogeneo(D, L, nh, kv, Dbase=None, pu=None):
    """Modelo com uma camada (nh por metro de largura total, como R01) e sem peso, para os exemplos das referências."""
    cam = dict(cota_m=0.0, topo=0.0, base=-1e6, nspt=10, solo="Areia", familia="Granular", comportamento="drenado",
               classe="", gama=18.0, gama_sat=20.0, phi=30.0, c=0.0, su=0.0, nh=nh, nh_sub=nh, kv=kv, kv_sub=kv, E=3e4,
               nu=0.3, fontes={}, editados=[])
    p = tcore._mesclar(tcore.PADROES, dict(geometria=dict(D=D, L=L, cota_topo=0.0, cota_terreno=0.0),
                                            camisa=dict(usar=False), analise=dict(n_fatias=400, n_aneis_base=40,
                                                                                 n_setores_base=96)))
    g = p["geometria"]
    g.update(cota_base=-L, D_estrutura=D, D_escavacao=D, contra_solo=True, D_base=Dbase)
    m = tcore.Modelo(p, dict(camadas=[cam]), None, sigma_adm=1e9)
    return m


def teste_pfeil():
    print("R01, Pfeil, Ex. 6.10.2.2 (L = 7 m, a = b = 1,40 m, kh = 100, kn = 500 tf/m3; N0 = 161,3 tf, H0 = 4 tf, M0 = 24 tfm)")
    m = modelo_homogeneo(1.4, 7.0, 100 * G, 500 * G)
    F = np.array([4 * G, 0, 24 * G, 0, 161.3 * G])
    U, ok, _ = m.resolver(F, caps=False, tracao=True)
    e = m.estado(U, caps=False, tracao=True)
    A, W = math.pi * 1.4 ** 2 / 4, math.pi * 1.4 ** 3 / 32
    p1 = 161.3 * G / A + 500 * G * e["theta"] * 0.7
    p2 = 161.3 * G / A - 500 * G * e["theta"] * 0.7
    confere("pressão de borda p1 (tf/m2)", p1 / G, 107.0, tol_abs=0.6)
    confere("pressão de borda p2 (tf/m2)", p2 / G, 103.0, tol_abs=0.6)
    confere("profundidade z0 (m)", e["z0"], 4.94, tol_abs=0.03)
    confere("coeficiente de z na carga lateral (tf/m)", 100 * e["ux"], 3.11, tol_abs=0.01)
    confere("coeficiente de z² na carga lateral (tf/m)", 100 * e["tx"], 0.63, tol_abs=0.01)


def teste_timerman():
    print("R02, Timerman, exemplo numérico (L = 10 m, df = 1,40 m, db = 3,20 m)")
    L, Df = 10.0, 1.4
    Kh, Kn = 3900 * G, 13000 * G
    m = modelo_homogeneo(Df, L, Kh * Df / L, Kn, Dbase=3.2)     # Kh na base: q = (Kh·z/L)·Df·y
    F = np.array([6 * G, 0, 55 * G, 0, 160 * G])
    U, ok, _ = m.resolver(F, caps=False, tracao=True)
    e = m.estado(U, caps=False, tracao=True)
    confere("φ (rad)", e["theta"], 0.0004346, tol_rel=0.002)
    confere("Δx (m)", e["ux"], 0.003117, tol_rel=0.002)
    confere("Δy (m)", e["w"], 0.0015303, tol_rel=0.002)
    confere("yeng (m)", e["z0"], 7.172, tol_rel=0.002)
    Ab = math.pi * 3.2 ** 2 / 4
    confere("tensão máxima de borda (tf/m2)", (160 * G / Ab + Kn * e["theta"] * 1.6) / G, 28.93, tol_rel=0.002)
    confere("tensão mínima de borda (tf/m2)", (160 * G / Ab - Kn * e["theta"] * 1.6) / G, 10.85, tol_rel=0.005)
    acima = [q for q, z in zip(e["q"], m.z) if z < e["z0"]]       # máximo da parábola acima do ponto de rotação
    confere("tensão lateral máxima acima de yeng (tf/m2)", max(acima) / Df / G, 2.1799, tol_rel=0.005)
    confere("tensão lateral na base (tf/m2; R02 dá +4,793 a 10 m)", e["q"][-1] / Df / G, 4.793, tol_rel=0.01)
    es = m.esforcos(U, F, caps=False, tracao=True, n=301)
    s42 = min(es, key=lambda s: abs(s["z"] - 4.2))
    # com o diâmetro do fuste (R03, programa TubCurto: 65.336,84 kgf.m a 4,2 m); R02 sem o diâmetro dá 69,52 tfm
    confere("momento a 4,2 m (tfm), como R03", (s42["M"] - 0.0) / G, 65.337, tol_rel=0.003)


def teste_mc_solucao03():
    print("R05, solução 03 (rotina R04: Df 1,9, Db 2,0, L = 2 m, kh = 725, kn = 2500 tf/m3, cargas da memória)")
    L = 2.0
    m = modelo_homogeneo(1.9, L, 725 * G * 1.9 / L, 2500 * G, Dbase=2.0)
    W = (14667.31 + 749.27) / 1000 * G                              # pesos da rotina (kgf): Wv + Ws da solução 03
    F = np.array([0.8 * G, 0, 8.5 * G, 0, 2.8 * G + W])
    U, ok, _ = m.resolver(F, caps=False, tracao=True)
    e = m.estado(U, caps=False, tracao=True)
    confere("ângulo de rotação (rad)", e["theta"], 0.004215121, tol_rel=0.002)
    confere("deslocamento horizontal (m)", e["ux"], 0.006200924, tol_rel=0.002)
    confere("deslocamento vertical (m)", e["w"], 0.002319407, tol_rel=0.002)
    confere("ponto de tensão nula (m)", e["z0"], 1.471114, tol_rel=0.002)


def teste_geospt():
    print("GEOSPT: média (2.2) e envoltória iguais às exportadas pelo GEOSPT (Pinheiro, estaca E-01, 9 furos)")
    ex = os.path.join(AQUI, "exemplos")                # cópia portátil: os dois arquivos, se postos em exemplos\
    obra = os.path.join(ex, "geospt_predio_sede_das_promotorias_de_justica_de_pinheiro_ma_2026-10-08.json")
    exp = os.path.join(ex, "geospt_detalhamento_predio_sede_das_promotorias_de_justica_de_pinheiro_ma_2026-10-08.json")
    if not (os.path.exists(obra) and os.path.exists(exp)):
        print("  (arquivos de Pinheiro não encontrados: teste pulado; são dados de obra e não vêm na cópia portátil)")
        return
    s, _ = ts.ler_geospt(obra)
    d = json.load(open(exp, encoding="utf-8"))
    est = d["estacas"][0]
    p = ts.perfis(s, est["furosConsiderados"], d["parametros"]["janelaCompatibilizacao_m"], d["parametros"]["submodoPerfilMedio"])
    for nome, meu, deles, campos in (("envoltória", p["envoltoria"], est["perfis"]["envoltoria"], ("nspt", "solo", "familia", "furo", "nFuros")),
                                     ("média", p["media"]["camadas"], est["perfis"]["media"]["camadas"], ("nspt", "solo", "familia", "heterogeneo", "nFuros"))):
        dm = {c["cota_m"]: c for c in deles}
        dif = sum(1 for c in meu for k in campos if c.get(k) != dm.get(c["cota_m"], {}).get(k)) + abs(len(meu) - len(deles))
        confere(f"diferenças na {nome}", dif, 0, tol_abs=0)


def teste_heterogeneo():
    print("GEOSPT: cota heterogênea (empate 1 x 1), ramo conservador, cores e envoltória")
    sond = ts.normalizar_sondagens({
        "A": dict(cotaTopo_m=0.0, leituras=[dict(profundidade_m=1, nspt_real=8, solo="Areia", cor="Vermelha"),
                                            dict(profundidade_m=2, nspt_real=12, solo="Areia Siltosa", cor="vermelha")]),
        "B": dict(cotaTopo_m=0.0, leituras=[dict(profundidade_m=1, nspt_real=5, solo="Argila", cor="cinza"),
                                            dict(profundidade_m=2, nspt_real=60, impenetravel=True, solo="Areia", cor="Amarela")])})
    p = ts.perfis(sond)
    c1 = p["media"]["camadas"][0]
    confere("cota -1 heterogênea, ramo de menor média (Coesivo, 5)", c1["nspt"], 5, tol_abs=0)
    print("    solo:", c1["solo"], "| detalhe:", c1["soloDetalhe"], "| cor:", c1["corDetalhe"])
    ok = c1["solo"] == "Argila" and c1["soloDetalhe"] == "C: Argila | G: Areia" and c1["corDetalhe"] == "C: cinza | G: Vermelha"
    confere("rótulos da cota heterogênea", 1 if ok else 0, 1, tol_abs=0)
    c2 = p["media"]["camadas"][1]
    confere("cota -2: média floor((12 + 50)/2)", c2["nspt"], 31, tol_abs=0)
    print("    cor da média na cota -2:", c2["cor"], "| detalhe:", c2["corDetalhe"])
    e2 = p["envoltoria"][1]
    confere("envoltória na cota -2 (furo A, 12)", e2["nspt"], 12, tol_abs=0)


def teste_ruptura():
    print("Ruptura: pushover x equilíbrio limite (H e M alinhados, p_u Rankine, base com q_ult)")
    m = modelo_homogeneo(1.5, 3.0, 300 * G, 2000 * G)
    m.P = 3.0 * 18.0 * m.zs * 1.5 * m.dz                       # p_u = 3·γ·z·D (Kp = 3), por fatia
    m.pu = m.P / m.dz
    m.q_ult = 600.0
    m.mu = 0.4
    m.W = 50.0                                                  # o vetor F já traz o peso (como em analisar_perfil)
    F = np.array([30.0, 0, 150.0, 0, 400.0 + m.W])
    po = m.pushover(F, atrito=True, tol=0.002)
    le = m.equilibrio_limite(F, atrito=True)
    confere("λ do pushover = λ do equilíbrio limite", po["lam"], le, tol_rel=0.03)
    md = m.minorado(1.4)                                        # NBR 6122 6.2.1.1.2: resistências do solo ÷ 1,4
    po_d = md.pushover(F, atrito=True, tol=0.002)
    le_d = md.equilibrio_limite(F, atrito=True)
    confere("modelo minorado: λ do pushover = λ do equilíbrio limite", po_d["lam"], le_d, tol_rel=0.03)
    confere("modelo minorado: λ menor que o característico", 1 if le_d < le else 0, 1, tol_abs=0)


def teste_grampos():
    print("Grampos da grelha: ganchos de 180° abraçando as barras verticais (medida do TQS: faces externas)")
    D, cob, phg = 2.0, 0.05, 8.0
    gr = dict(bitola=phg, nx=3, ny=3, s_barras=0.15)
    # montagem ø10 encostada nos anéis ø8: face externa do gancho no alinhamento externo do anel (D/2 - cobrimento)
    r = D / 2 - cob - 0.008 - 0.005
    lst = tc.grampos(gr, r, 10.0)
    confere("grampos (3 em x + 3 em y)", len(lst), 6, tol_abs=0)
    confere("comprimento do grampo central (2·(r + φv/2 + φg))", max(q["comp"] for q in lst), 1.90, tol_abs=1e-9)
    confere("face externa do gancho <= D/2 - cobrimento", max(q["comp"] for q in lst) / 2, D / 2 - cob, tol_abs=0.005)
    confere("grampos em x a ±15 cm", sorted(round(q["by"], 3) for q in lst if q["dir"] == "X")[-1], 0.15, tol_abs=1e-9)
    # armadura longitudinal: 40 barras; cada grampo abraça uma barra e a simétrica
    n, rl = 40, 0.734
    barras = {(round(rl * math.cos(2 * math.pi * j / n), 6), round(rl * math.sin(2 * math.pi * j / n), 6)) for j in range(n)}
    lst = tc.grampos(gr, rl, 16.0, n_barras=n)
    ok = all((round(q["bx"], 6), round(q["by"], 6)) in barras and
             ((round(-q["bx"], 6), round(q["by"], 6)) if q["dir"] == "X" else (round(q["bx"], 6), round(-q["by"], 6))) in barras
             for q in lst)
    confere("ganchos nas próprias barras, em pares simétricos", int(ok), 1, tol_abs=0)
    confere("barras distintas por direção", len({(q["dir"], q["bx"], q["by"]) for q in lst}), 6, tol_abs=0)


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    for t in (teste_pfeil, teste_timerman, teste_mc_solucao03, teste_geospt, teste_heterogeneo, teste_ruptura, teste_grampos):
        t()
    print("\n" + ("TODOS OS TESTES PASSARAM" if not falhas else f"FALHARAM {len(falhas)}: " + "; ".join(falhas)))
    sys.exit(1 if falhas else 0)
