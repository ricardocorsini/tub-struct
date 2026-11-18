# -*- coding: utf-8 -*-
"""
Conferência das dependências do app de tubulões curtos (cópia portátil).

Diz o que falta, sem traceback, antes de o app gravar qualquer arquivo. Não instala nada e não grava nada.
Feito sobre o dependencias.py da cópia portátil das estacas (_apps\\EstacaEscavada_Portatil), com a mesma interface
(o estaca_dwg.py desta pasta o usa).

Uso:  python dependencias.py      (relatório completo; código de saída 1 se faltar algo essencial)

O que é conferido:
  * Python: o app foi testado no 3.13;
  * numpy (o cálculo), tkinter (a janela), matplotlib e Pillow (gráficos e ícones da janela): pacotes do
    requirements.txt, menos o tkinter, que vem com o Python;
  * pacote Python do TQS: "TQSPythonInterface" (TQS V25) ou "tqs" (TQS V26). Não vem do PyPI: é instalado pelo
    EXEC\\X64\\TQSPYINST.EXE da própria instalação do TQS, no Python que ele acha pelo registro do Windows;
  * instalação do TQS: as pastas do registro (HKLM\\SOFTWARE\\TQS) e as DLLs que o desenho usa;
  * arquivos de suporte do TQS que o desenho usa (sem eles o DWG sai, com aviso);
  * Edge: o PDF da memória e a janela do 3D (sem ele, a memória sai só em HTML e o 3D abre no navegador padrão).
"""
import importlib.metadata as _md
import importlib.util as _iu
import os
import sys

PYTHON_TESTADO = (3, 13)
DLLS_DESENHO = ("MDWG.DLL", "IPOFER.DLL")
COMO_INSTALAR_PACOTES = "py -3.13 -m pip install -r requirements.txt  (na pasta do app)"
COMO_INSTALAR_TQS = ("rode o EXEC\\X64\\TQSPYINST.EXE da instalação do TQS (com o TQS fechado); ele instala o pacote do "
                     "TQS no Python 3.13")


def _versao(dist):
    try:
        return _md.version(dist)
    except _md.PackageNotFoundError:
        return None


def _tem(modulo):
    try:
        return _iu.find_spec(modulo) is not None
    except (ImportError, ValueError):
        return False


def _pacote(itens, modulo, dist, para):
    v = _versao(dist)
    itens.append(("ok", dist, v) if v and _tem(modulo) else
                 ("falta", dist, f"não instalado ({para}): {COMO_INSTALAR_PACOTES}"))


def pacote_tqs():
    """Distribuições do pacote do TQS registradas no pip: [(nome, versão, versão do TQS)]."""
    out = []
    for dist, ver_tqs in (("TQSPythonInterface", "V25"), ("tqs", "V26")):
        v = _versao(dist)
        if v:
            out.append((dist, v, ver_tqs))
    return out


def metodo_quantidade_fixa():
    """Nome do método do ferro inteligente que fixa a quantidade da última faixa: RebarDistrQuantity no pacote da V25
    (TQSPythonInterface 2.1.x) e RebarDistrAutoSum no da V26 (tqs 3.0.x; mesma rotina da DLL). None se não houver."""
    from TQS import TQSDwg
    for nome in ("RebarDistrQuantity", "RebarDistrAutoSum"):
        if hasattr(TQSDwg.SmartRebar, nome):
            return nome
    return None


def conferir(janela=False, tqs=True, png=False):
    """Lista de (nível, item, mensagem); nível: "ok", "falta" (impede o uso) ou "aviso" (o app funciona, com limitação).
    O numpy é sempre conferido (o cálculo depende dele). janela: tkinter, matplotlib e Pillow; tqs: gravar o DWG;
    png: matplotlib (mantido pela interface do estaca_dwg)."""
    itens = []
    v = sys.version_info[:2]
    itens.append(("ok" if v == PYTHON_TESTADO else "aviso", "Python",
                  f"{sys.version.split()[0]} ({sys.executable})" + ("" if v == PYTHON_TESTADO else
                                                                   f": o app foi testado no Python {PYTHON_TESTADO[0]}.{PYTHON_TESTADO[1]}")))
    _pacote(itens, "numpy", "numpy", "o cálculo")
    if janela:
        itens.append(("ok", "tkinter", "instalado") if _tem("tkinter") else
                     ("falta", "tkinter", "o Python foi instalado sem o tcl/tk: reinstale o Python 3.13 marcando "
                                          "\"tcl/tk and IDLE\""))
    if janela or png:
        _pacote(itens, "matplotlib", "matplotlib", "os gráficos da janela")
    if janela:
        _pacote(itens, "PIL", "pillow", "os ícones da janela")
    if tqs:
        itens += _conferir_tqs()
    return itens


def _conferir_tqs():
    itens = []
    dist = pacote_tqs()
    if not _tem("TQS"):
        return [("falta", "pacote do TQS", f"não instalado neste Python: {COMO_INSTALAR_TQS}")]
    desc = ", ".join(f"{n} {v} ({t})" for n, v, t in dist) or "versão não registrada no pip"
    try:
        from TQS import TQSDwg, TQSUtil              # só o Python: as DLLs do TQS carregam ao abrir um desenho
    except Exception as e:                           # pacote quebrado ou de outra versão do Python
        return [("falta", "pacote do TQS", f"{desc}, mas não carregou ({type(e).__name__}: {e}). "
                                           + COMO_INSTALAR_TQS[0].upper() + COMO_INSTALAR_TQS[1:])]
    itens.append(("ok", "pacote do TQS", desc))
    if len(dist) > 1:
        itens.append(("aviso", "pacote do TQS", "há dois pacotes do TQS registrados no pip (V25 e V26), que gravam a "
                                                "mesma pasta TQS: vale o último instalado. Confira se é o da versão do "
                                                "TQS em uso; para trocar, rode o TQSPYINST.EXE dela."))
    nome = metodo_quantidade_fixa()
    itens.append(("ok", "ferros inteligentes", f"quantidade fixa por faixa: {nome}") if nome else
                 ("falta", "ferros inteligentes", "o pacote do TQS não tem RebarDistrQuantity nem RebarDistrAutoSum, que "
                                                  "fixam a quantidade da fretagem e dos estribos do fuste. "
                                                  + COMO_INSTALAR_TQS[0].upper() + COMO_INSTALAR_TQS[1:]))
    try:
        programas, suporte = TQSUtil.ProgramsFolder(), TQSUtil.SupportFolder()
    except OSError:
        itens.append(("falta", "TQS", "não achei a instalação do TQS no registro do Windows (HKLM\\SOFTWARE\\TQS): "
                                      "instale e licencie o TQS neste computador"))
        return itens
    faltam = [d for d in DLLS_DESENHO if not os.path.exists(os.path.join(programas, d))]
    if faltam or not os.path.isdir(suporte):
        itens.append(("falta", "TQS", f"instalação incompleta: programas em {programas}, suporte em {suporte}"
                                      + (f"; faltam {', '.join(faltam)}" if faltam else "; pasta de suporte não existe")))
        return itens
    itens.append(("ok", "TQS", f"programas em {programas}; suporte em {suporte}"))
    for rel, efeito in ((("NGE", "MASCARAS2", "MASQUANT.DWG"), "sem o bloco $QUANT (volume no resumo estrutural)"),
                        (("PILAR", "FERCOR", "FERMOR1.DWG"), "barras em corte desenhadas como círculos"),
                        (("NGE", "PENAS", "PLOTPENA.PEN"), "DXF com as cores do desenho, não as da plotagem")):
        arq = os.path.join(suporte, *rel)
        if not os.path.exists(arq):
            itens.append(("aviso", rel[-1], f"não encontrado em {os.path.dirname(arq)}: {efeito}"))
    return itens


def edge():
    """Edge, que grava o PDF da memória (sem janela) e abre o 3D numa janela própria. None se não houver."""
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles")):
        if base and os.path.exists(os.path.join(base, "Microsoft", "Edge", "Application", "msedge.exe")):
            return os.path.join(base, "Microsoft", "Edge", "Application", "msedge.exe")
    return None


def faltas(itens):
    return [i for i in itens if i[0] == "falta"]


def texto(itens, titulo="Dependências do app de tubulões curtos"):
    rot = {"ok": "OK   ", "falta": "FALTA", "aviso": "AVISO"}
    linhas = [titulo, ""] + [f"  {rot[n]}  {item}: {msg}" for n, item, msg in itens]
    if faltas(itens):
        linhas += ["", "Falta o que está marcado FALTA. Veja o LEIA-ME.md."]
    return "\n".join(linhas)


def mensagem_faltas(itens, acao):
    """Texto curto para a janela ou o console: o que falta para a ação pedida."""
    return f"Não dá para {acao} neste computador:\n\n" + "\n".join(f"- {item}: {msg}" for _, item, msg in faltas(itens)) \
        + "\n\nVeja o LEIA-ME.md, na pasta do app."


def exigir_calculo():
    """Nos programas de lote: sem o numpy, diz o que falta e encerra (código 1), sem traceback."""
    itens = conferir(tqs=False)
    if faltas(itens):
        print(mensagem_faltas(itens, "calcular o tubulão"))
        sys.exit(1)


def main():
    itens = conferir(janela=True, tqs=True)
    nav = edge()
    itens.append(("ok", "Edge", nav) if nav else
                 ("aviso", "Edge", "não encontrado: a memória sai só em HTML (imprima pelo navegador) e o 3D abre no "
                                   "navegador padrão"))
    print(texto(itens))
    return 1 if faltas(itens) else 0


if __name__ == "__main__":
    sys.exit(main())
