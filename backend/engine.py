"""Validated, file-system independent boundary around the supplied calculation engine."""
from __future__ import annotations

import copy
import html
import json
import math
import sys
from pathlib import Path

LEGACY = Path(__file__).resolve().parent / "legacy"
sys.path.insert(0, str(LEGACY))
import tubulao_core as core
import tubulao_sondagem as sondagem
import tubulao_memoria as memoria
import tubulao_3d as vista3d

# Data files retain their legacy directory in the frozen sidecar.
vista3d.MODELO_HTML = str(LEGACY / "tubulao_3d.html")
vista3d.VENDOR = str(LEGACY / "vendor" / "three-0.169.0")

VERSION = "0.1.0"
EXAMPLES = {
    "poste": "T1_poste_DT600.json",
    "pilar": "T2_pilar_dimensionamento.json",
    "armado": "T3_fuste_armado.json",
}


def finite_tree(value, path="entrada", depth=0):
    if depth > 24:
        raise ValueError("Arquivo com estrutura excessivamente aninhada.")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{path}: use um número finito.")
    if isinstance(value, dict):
        for key, item in value.items():
            finite_tree(item, f"{path}.{key}", depth + 1)
    elif isinstance(value, list):
        if len(value) > 5000:
            raise ValueError(f"{path}: lista muito extensa.")
        for item in value:
            finite_tree(item, path, depth + 1)


def number(value, label, low, high, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label}: informe um número finito.")
    if not low <= value <= high or (integer and int(value) != value):
        raise ValueError(f"{label}: informe {'um inteiro ' if integer else ''}entre {low:g} e {high:g}.")


def bounded_fields(p, section, fields):
    for key, limits in fields.items():
        number(p[section][key], f"{section}.{key}", *limits)


def prepare(parameters):
    if not isinstance(parameters, dict):
        raise ValueError("Os parâmetros devem ser um objeto JSON.")
    finite_tree(parameters)
    for section in core.PADROES:
        if isinstance(core.PADROES[section], dict) and section in parameters:
            if not isinstance(parameters[section], dict):
                raise ValueError(f"{section}: objeto inválido.")
    p = core._mesclar(core.PADROES, parameters)
    p.pop("_concreto", None)
    if not isinstance(p["nome"], str) or not p["nome"].strip() or len(p["nome"]) > 120:
        raise ValueError("Informe um nome de até 120 caracteres para o tubulão.")
    if not isinstance(p["descricao"], str) or len(p["descricao"]) > 4000:
        raise ValueError("Descrição inválida (máximo de 4000 caracteres).")
    number(p["quantidade"], "Quantidade", 1, 10000, True)
    bounded_fields(p, "geometria", {"L": (.2, 30), "cota_topo": (-10000, 10000), "desprezar_topo": (0, 30)})
    if p["geometria"]["cota_terreno"] is not None:
        number(p["geometria"]["cota_terreno"], "Cota do terreno", -10000, 10000)
    if p["geometria"].get("D_base") is not None:
        raise ValueError("Esta versão trabalha com seção constante, sem base alargada.")
    cm = p["camisa"]
    for section, keys in {"camisa": ("usar", "estrutural"), "dimensionamento": ("automatico",),
                          "solo": ("atrito_base_servico", "atrito_base_ruptura"),
                          "criterios": ("concreto_simples", "vento_obra_lista")}.items():
        for key in keys:
            if not isinstance(p[section][key], bool):
                raise ValueError(f"{section}.{key}: use verdadeiro ou falso.")
    if cm["usar"]:
        number(cm["DN"], "DN da camisa", .3, 10)
        if cm["espessura"] is not None:
            number(cm["espessura"], "Espessura da camisa", .01, 1)
    else:
        number(p["geometria"]["D"], "Diâmetro", .3, 10)
    number(cm["altura"], "Altura do anel", .1, 3)
    bounded_fields(p, "materiais", {"fck": (20, 90), "fyk": (250, 600), "cobrimento": (.02, .2), "gama_c": (15, 30)})
    if p["materiais"]["caa"] not in ("I", "II", "III", "IV"):
        raise ValueError("Classe de agressividade: I, II, III ou IV.")
    bounded_fields(p, "folga", {"largura": (0, 2), "folga_min_compactacao": (.01, 2)})
    number(p["lastro"]["espessura"], "Espessura do lastro", 0, 1)
    bounded_fields(p, "apoio", {"a": (.05, 10), "b": (.05, 10), "d": (.05, 10), "h_aplicacao": (0, 100),
                                "embutimento": (0, 30), "area_secao": (0, 50), "ex": (-10, 10), "ey": (-10, 10)})
    if p["apoio"]["tipo"] not in ("nenhum", "pilar", "poste") or p["apoio"]["secao"] not in ("retangular", "circular"):
        raise ValueError("Tipo ou seção do apoio inválidos.")
    if not isinstance(p["acoes"], list) or not 1 <= len(p["acoes"]) <= 12:
        raise ValueError("Informe de 1 a 12 ações características.")
    names = set()
    for action in p["acoes"]:
        if not isinstance(action, dict):
            raise ValueError("Ação inválida.")
        name = action.get("nome", "")
        if not isinstance(name, str) or not name.strip() or len(name) > 120 or name in names:
            raise ValueError("As ações precisam ter nomes únicos, com até 120 caracteres.")
        names.add(name)
        if action.get("tipo") not in ("permanente", "variavel"):
            raise ValueError("Esta versão admite ações permanentes e variáveis; excepcionais não são combinadas pelo núcleo.")
        for key in ("N", "Hx", "Hy", "Mx", "My"):
            number(action.get(key, 0), f"{name}: {key}", -1e7, 1e7)
        if not isinstance(action.get("grupo", name), str):
            raise ValueError("Grupo de ação inválido.")
    s = p["sondagem"]
    if not s["sondagens"]:
        raise ValueError("Importe ou cadastre os furos SPT. Arquivos antigos com caminhos externos exigem a importação da sondagem.")
    s["arquivo"] = None  # The app never reads arbitrary paths supplied by a project.
    s["sondagens"] = import_sondagem(s["sondagens"])
    if s["submodo"] not in ("2.1_predominante", "2.2_conservador"):
        raise ValueError("Use o perfil predominante (2.1) ou conservador (2.2). O modo 2.3 ainda não está implementado pelo núcleo.")
    number(s["janela"], "Janela SPT", .05, 2)
    number(s["delta"], "Ajuste das cotas SPT", -1000, 1000)
    if s["na"] is not None:
        number(s["na"], "Cota do nível d'água", -10000, 10000)
    if s["na_criterio"] not in ("mais_alto", "media"):
        raise ValueError("Critério de nível d'água inválido.")
    if s["furos"] is not None and (not isinstance(s["furos"], list) or not s["furos"] or any(n not in s["sondagens"] for n in s["furos"])):
        raise ValueError("Seleção de furos inválida.")
    selected = s["furos"] or list(s["sondagens"])
    if not isinstance(s["perfis"], list) or not s["perfis"] or any(n not in ["media", "envoltoria"] + [f"furo:{f}" for f in selected] for n in s["perfis"]):
        raise ValueError("Escolha perfis de cálculo válidos.")
    bounded_fields(p, "solo", {"fs_base": (1, 10)})
    if p["solo"]["sigma_adm"] is not None:
        number(p["solo"]["sigma_adm"], "Tensão admissível", 1, 100000)
    if p["solo"]["metodo_phi"] not in ("teixeira", "godoy"):
        raise ValueError("Correlação do ângulo de atrito inválida.")
    if not isinstance(p["solo"]["edicoes"], list):
        raise ValueError("Edições de solo inválidas.")
    for edit in p["solo"]["edicoes"]:
        if not isinstance(edit, dict):
            raise ValueError("Edição de camada inválida.")
        number(edit.get("cota_m"), "Cota da camada editada", -10000, 10000)
        for field, bounds in {"gama": (1, 40), "gama_sat": (1, 40), "phi": (0, 50), "c": (0, 10000),
                              "su": (0, 10000), "nh": (.01, 1e9), "nh_sub": (.01, 1e9),
                              "kv": (.01, 1e9), "kv_sub": (.01, 1e9), "E": (.01, 1e9), "nu": (0, .49)}.items():
            if edit.get(field) is not None and edit[field] != "":
                number(edit[field], f"Camada: {field}", *bounds)
        if edit.get("comportamento") not in (None, "", "drenado", "nao_drenado"):
            raise ValueError("Comportamento do solo inválido.")
    bounded_fields(p, "criterios", {
        "gama_m_solo": (1, 5), "gama_m_peso": (1, 5), "gama_f_tombamento": (1, 5),
        "fs_tombamento": (1, 10), "fs_passivo": (1, 10), "fator_sigma_vento": (1, 1.3),
        "area_comprimida_min": (.01, 1), "area_comprimida_qp": (.01, 1),
        "rotacao_lim": (.00001, .1), "rotacao_lim_poste": (.00001, .1), "recalque_lim": (.0001, 1),
        "z_rigido": (.1, 10), "z_longo": (.1, 20), "as_min_fuste": (.0001, .08),
        "comp_min_armadura": (.1, 30), "sacrificio_barras": (0, 5), "theta_ruptura": (.001, .3),
        "fretagem_a_d_limite": (.01, 1), "grelha_espac_camadas": (.02, 1), "grelha_espac_barras": (.02, 1),
        "grelha_min_barras": (2, 100, True), "aneis_construtivos_s": (.02, 1), "montagem_bitola": (5, 32),
        "montagem_espac_max": (.02, 2), "montagem_min": (3, 100, True),
    })
    if p["criterios"]["desloc_aplicacao_lim"] is not None:
        number(p["criterios"]["desloc_aplicacao_lim"], "Deslocamento limite", .0001, 5)
    bounded_fields(p, "analise", {"n_fatias": (10, 200, True), "n_aneis_base": (4, 40, True), "n_setores_base": (8, 96, True)})
    dm = p["dimensionamento"]
    bounded_fields(p, "dimensionamento", {"L_min": (.2, 30), "L_max": (.2, 30)})
    if dm["L_passo"] is not None:
        number(dm["L_passo"], "Passo de comprimento", .05, 10)
    if dm["L_min"] > dm["L_max"]:
        raise ValueError("O comprimento mínimo supera o máximo.")
    if dm["D_lista"] is not None:
        if not isinstance(dm["D_lista"], list) or not 1 <= len(dm["D_lista"]) <= 30:
            raise ValueError("Lista de diâmetros inválida.")
        for d in dm["D_lista"]:
            number(d, "Diâmetro candidato", .3, 10)
    if dm.get("escolha_usuario") is not None:
        choice = dm["escolha_usuario"]
        if not isinstance(choice, dict):
            raise ValueError("Escolha de geometria inválida.")
        number(choice.get("D"), "Diâmetro escolhido", .3, 10)
        number(choice.get("L"), "Comprimento escolhido", .2, 30)
    normalized = core.normalizar(p)
    if normalized["materiais"]["cobrimento"] * 2 >= normalized["geometria"]["D_estrutura"]:
        raise ValueError("O cobrimento não cabe na seção.")
    groups = {}
    for a in normalized["acoes"]:
        if a["tipo"] == "variavel":
            groups[a["grupo"]] = groups.get(a["grupo"], 0) + 1
    if math.prod(n + 1 for n in groups.values()) > 128:
        raise ValueError("Muitas combinações. Reduza as ações independentes ou agrupe alternativas exclusivas.")
    if dm["automatico"]:
        ds, lengths = core.candidatos(normalized)
        if not ds or len(ds) * len(lengths) > 500:
            raise ValueError("A varredura deve conter entre 1 e 500 candidatos. Confira os diâmetros e o passo.")
    return normalized


def import_sondagem(data):
    if not isinstance(data, (dict, list)):
        raise ValueError("Arquivo de sondagem inválido.")
    finite_tree(data)
    if isinstance(data, dict):
        schema = data.get("_schema", data.get("schema"))
        version = str(data.get("_schemaVersao", data.get("versao", "")))
        if schema and ((schema == "geospt-obra" and not version.startswith("2.")) or
                       (schema == "geospt-detalhamento-estacas" and not version.startswith("1.")) or
                       schema not in ("geospt-obra", "geospt-detalhamento-estacas")):
            raise ValueError("Use GEOSPT obra 2.x ou detalhamento 1.x.")
    result = sondagem.normalizar_sondagens(data)
    if not 1 <= len(result) <= 50:
        raise ValueError("Cadastre de 1 a 50 furos.")
    for name, hole in result.items():
        if not name.strip() or len(name) > 120:
            raise ValueError("Nome do furo inválido.")
        if not 1 <= len(hole["leituras"]) <= 300:
            raise ValueError(f"{name}: informe de 1 a 300 leituras SPT.")
        number(hole["cotaTopo_m"], f"{name}: cota da boca", -10000, 10000)
        number(hole["profundidadeFinal_m"], f"{name}: profundidade final", .1, 300)
        for reading in hole["leituras"]:
            number(reading["profundidade_m"], f"{name}: profundidade", .1, 300)
            number(reading["nspt_real"], f"{name}: NSPT", 0, 1000, True)
            # Derived data must not override the measured NSPT during import/edit.
            reading["nspt_calculo"] = min(reading["nspt_real"], 50)
            if reading["familia"] not in sondagem.FAMILIAS:
                raise ValueError(f"{name}: informe a família geotécnica do solo '{reading['solo']}'.")
        if hole["profundidadeFinal_m"] < hole["leituras"][-1]["profundidade_m"]:
            raise ValueError(f"{name}: profundidade final anterior à última leitura.")
        for key in ("naInicial_m", "naFinal_m"):
            if hole[key] is not None:
                number(hole[key], f"{name}: nível d'água", 0, 300)
    return result


def example(name):
    if name not in EXAMPLES:
        raise ValueError("Exemplo não encontrado.")
    p = json.loads((LEGACY / "exemplos" / EXAMPLES[name]).read_text(encoding="utf-8"))
    p["sondagem"]["sondagens"], _ = sondagem.ler_geospt(str(LEGACY / "exemplos" / p["sondagem"]["arquivo"]))
    p["sondagem"]["arquivo"] = None
    return {k: v for k, v in prepare(p).items() if not k.startswith("_")}


def calculate(parameters):
    p = prepare(parameters)
    res = core.calcular(p)
    report = memoria.montar_html(res)
    note = ('<aside style="padding:12px;border:1px solid #3448d1;margin:12px 0">'
            '<b>TubStruct 0.1.0 · OpenStruct</b> — Tubulão rígido, circular e sem base alargada. '
            'Critérios e referências herdados da base fornecida. Consulte as hipóteses, '
            'advertências e verificações desta memória; resultados se referem aos dados abaixo.</aside>')
    report = report.replace("<body>", "<body>" + note, 1)
    scene = vista3d.dados_3d(res)
    drawings = {
        "elevacao": memoria.fig_elevacao(res, res["solo"]["perfis"][0]),
        "sondagens": memoria.fig_nspt(res),
        "esforcos": memoria.fig_esforcos(res),
    }
    return dict(result=core.resultado_json(res), scene=core._limpo(scene), report=report,
                drawings=drawings, summary=core.resumo_texto(res), version=VERSION)


def handle(request):
    if not isinstance(request, dict):
        raise ValueError("Requisição inválida.")
    action = request.get("action")
    if action == "health":
        return dict(version=VERSION, kernel=core.VERSAO)
    if action == "calculate":
        return calculate(request.get("parameters"))
    if action == "normalize":
        return {k: v for k, v in prepare(request.get("parameters")).items() if not k.startswith("_")}
    if action == "sondagem":
        return import_sondagem(request.get("data"))
    if action == "example":
        return example(request.get("name"))
    if action == "export3d":
        # Always regenerate from the current inputs, never from imported result objects.
        res = core.calcular(prepare(request.get("parameters")))
        return vista3d.html_3d(vista3d.dados_3d(res))
    raise ValueError("Operação não reconhecida.")
