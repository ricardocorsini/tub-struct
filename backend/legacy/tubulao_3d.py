# -*- coding: utf-8 -*-
"""
Tubulão curto: visualização 3D interativa (página HTML com three.js, modelo em tubulao_3d.html).

Mostra as camadas do solo (cortadas para ver o fuste), o NA, a escavação com a folga, os anéis pré-moldados e o
concreto de enchimento, o pilar ou o poste, as armaduras (fretagem e barras longitudinais), o diagrama da reação
lateral no plano de rotação com a envoltória p_u, as pressões na base em cor e a deformada exagerada em torno do
ponto de rotação. Na página: escolha do perfil de cálculo e da combinação, exagero da deformada, camadas
liga/desliga, vistas prontas e dica com os valores sob o mouse.

O three.js 0.169.0 (MIT) vem embutido da pasta vendor\\three-0.169.0 desta pasta (cópia portátil; no original, a
do app de estacas) e a página abre sem internet; sem essa pasta, carrega de cdn.jsdelivr.net.

Uso: python tubulao_3d.py <parametros.json> [--saida PASTA] [--abrir]
"""
import os, sys, json, html, math, argparse, subprocess, webbrowser
from pathlib import Path
import dependencias                       # cópia portátil: sem o numpy, diz o que falta e sai
dependencias.exigir_calculo()
import numpy as np
import tubulao_core as tcore

AQUI = os.path.dirname(os.path.abspath(__file__))
MODELO_HTML = os.path.join(AQUI, "tubulao_3d.html")
VENDOR = os.path.join(AQUI, "vendor", "three-0.169.0")
THREE_LOCAL = (("three-src", "three.module.min.js"), ("three-orbit", "OrbitControls.js"), ("three-css2d", "CSS2DRenderer.js"))
MARCA, MARCA_THREE = "/*__DADOS__*/null", "<!--__THREE_LOCAL__-->"


def _r(v, c=4):
    return None if v is None else round(float(v), c)


def dados_3d(res):
    p = res["p"]
    g, cm, apo = p["geometria"], p["camisa"], p["apoio"]
    est = res["estrutura"]
    perfis = []
    for ap in res["analises"]:
        m = ap["modelo"]
        nr, nt = p["analise"]["n_aneis_base"], p["analise"]["n_setores_base"]
        combs = []
        for e in ap["servico"]:
            th = e["theta"]
            ang = math.atan2(e["ty"], e["tx"]) if th > 0 else 0.0
            ex, ey = (e["tx"] / th, e["ty"] / th) if th > 0 else (1.0, 0.0)
            q = [(fx * ex + fy * ey) / dz for fx, fy, dz in zip(e["fx"], e["fy"], m.dz)]
            combs.append(dict(nome=e["nome"], theta=_r(th, 6), ang=_r(ang), u=_r(e["u_topo"], 5), ux=_r(e["ux"], 5), uy=_r(e["uy"], 5),
                              z0=_r(e["z0"]) if e["z0"] is not None and th > 0 else None, w=_r(e["w"], 5), q=[_r(v, 2) for v in q],
                              pb=[_r(v, 1) for v in e["pb"]], p_max=_r(e["p_max"], 1), area=_r(e["area_comp"], 3),
                              lam=_r(e["lam"], 2) if math.isfinite(e["lam"]) else None, mob=_r(max(e["mob"]), 3)))
        perfis.append(dict(rotulo=ap["rotulo"], z=[_r(v) for v in m.z], pu=[_r(v, 2) for v in m.pu], nr=nr, nt=nt, R=_r(m.Dbase / 2),
                           sigma_adm=_r(ap["sigma_adm"], 1), combs=combs,
                           camadas=[dict(topo=_r(c["topo"], 3), base=_r(c["base"], 3), familia=c["familia"], solo=c["solo"],
                                         nspt=c["nspt"], cor=c.get("cor", "")) for c in ap_camadas(res, ap)]))
    fr = est.get("bloco", {}) and est["bloco"].get("fretagem") if est.get("bloco") else None
    arm = est.get("armadura")
    return dict(nome=p["nome"], descricao=p["descricao"], D=g["D"], Dc=g["D_estrutura"], De=g["D_escavacao"], L=g["L"],
                topo=g["cota_topo"], terreno=g["cota_terreno"], base=g["cota_base"], na=res["solo"]["na"],
                lastro=p["lastro"]["espessura"], camisa=dict(usar=cm["usar"], h=cm["altura"], e=cm["espessura"], DN=cm["DN"]),
                folga=p["folga"]["preenchimento"], apoio=dict(tipo=apo["tipo"], secao=apo["secao"], a=apo["a"], b=apo["b"], d=apo["d"],
                                                              emb=apo["embutimento"], h=apo["h_aplicacao"]),
                fretagem=fr and dict(n=fr["n"], z1=fr["z1"], z2=fr["z2"], raio=fr["raio"], bitola=fr["bitola"]),
                armadura=arm and dict(n=arm["n"], bitola=arm["bitola"], z_fim=arm.get("z_fim"),
                                      raio=arm.get("raio", g["D_estrutura"] / 2 - p["materiais"]["cobrimento"])),
                estribos=arm and arm.get("estribo") and {k: arm["estribo"][k] for k in ("n", "z1", "z2", "raio", "bitola", "s")},
                grelha=(est.get("bloco") or {}).get("grelha") and {k: est["bloco"]["grelha"][k] for k in
                                                                ("n_camadas", "nx", "ny", "s_barras", "s_camadas", "z1", "comp", "bitola",
                                                                 "grampos")},
                montagem=est.get("montagem") and {k: est["montagem"][k] for k in ("n", "raio", "z_fim", "bitola", "pos")},
                cobrimento=p["materiais"]["cobrimento"], fs_passivo=p["criterios"]["fs_passivo"], perfis=perfis)


def ap_camadas(res, ap):
    for pf in res["solo"]["perfis"]:
        if pf["rotulo"] == ap["rotulo"]:
            return pf["camadas"]
    return res["solo"]["perfis"][0]["camadas"]


def _three_local():
    blocos = []
    for ident, arq in THREE_LOCAL:
        caminho = os.path.join(VENDOR, arq)
        if not os.path.exists(caminho):
            return ""
        js = open(caminho, encoding="utf-8").read()
        if "</script" in js.lower() or "<!--" in js:
            return ""
        blocos.append(f'<script type="text/plain" id="{ident}">\n{js}\n</script>')
    return "\n".join(blocos)


def html_3d(dados):
    modelo = open(MODELO_HTML, encoding="utf-8").read()
    js = json.dumps(dados, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/").replace("<!--", "<\\u0021--")
    return modelo.replace(MARCA, js).replace("__TITULO__", html.escape(f"Tubulão {dados['nome']} - 3D")).replace(MARCA_THREE, _three_local())


def gravar(res, pasta):
    os.makedirs(pasta, exist_ok=True)
    caminho = os.path.join(pasta, f"{res['p']['nome']}-3D.html")
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(html_3d(dados_3d(res)))
    return caminho


def abrir(caminho):
    uri = Path(caminho).resolve().as_uri()
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"), os.environ.get("LOCALAPPDATA")):
        exe = base and os.path.join(base, "Microsoft", "Edge", "Application", "msedge.exe")
        if exe and os.path.exists(exe):
            try:
                subprocess.Popen([exe, f"--app={uri}", "--window-size=1500,920"])
                return
            except OSError:
                pass
    webbrowser.open(uri)


def main():
    ap = argparse.ArgumentParser(description="Visualização 3D do tubulão curto (HTML)")
    ap.add_argument("json")
    ap.add_argument("--saida")
    ap.add_argument("--abrir", action="store_true")
    a = ap.parse_args()
    sys.stdout.reconfigure(errors="replace")
    par = json.load(open(a.json, encoding="utf-8"))
    res = tcore.calcular(par, os.path.dirname(os.path.abspath(a.json)))
    c = gravar(res, a.saida or os.path.join(tcore.SAIDAS, res["p"]["nome"]))
    print("3D   ", c)
    if a.abrir:
        abrir(c)


if __name__ == "__main__":
    main()
