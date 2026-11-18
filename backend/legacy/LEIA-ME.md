# Dimensionamento de tubulões curtos (cópia portátil)

Aplicativo de dimensionamento de tubulões curtos: rígidos, sem base alargada, sob força horizontal e momento, pela NBR 6122:2022 e pela NBR 6118:2026. Ele tem janela no estilo do TQS, memória de cálculo em HTML e PDF, visualização 3D e desenho em DWG do TQS, com ferros inteligentes. Esta pasta é independente: basta copiá-la para outro computador.

Foi copiada em 14/11/2026 do app `_apps\TubulõesCurtos`, com o mesmo cálculo, a mesma janela e o mesmo desenho. As diferenças:

- **Módulos de outras pastas trazidos para esta.** O original importava o ribbon e os ícones do app de telas soldadas (que vêm do `_apps\_comum`), o desenho do app de estacas e o three.js da pasta das estacas. Aqui ficam `cad_ribbon.py`, `cad_icones.py`, os módulos `estaca_*.py` e `vendor\three-0.169.0\`, copiados sem mudar o código. Os dois ícones das telas que a janela usa (vistas Base e Esforços) foram para o `tubulao_app.pyw`.
- **Conferência das dependências** (`dependencias.py`). A conferência roda na abertura da janela, no "DWG, PDF e DXF" e nos programas de lote, e diz o que falta sem traceback, antes de gravar qualquer arquivo.
- **TQS V25 e V26:** o `estaca_dwg.py` é o da cópia portátil das estacas (abaixo).
- **Exemplos com sondagens fictícias.** As sondagens dos exemplos do original são de uma obra e ficaram fora. No lugar delas, os exemplos usam dois furos fictícios, SP-A e SP-B (`exemplos\sondagens_exemplo_SP-A_SP-B.json`), e os resultados mudam (tabela abaixo). O T1 se chama `T1_poste_DT600.json`.
- **Sem a pasta `Referências`** (normas, livros e documentos de projeto), o plano e a avaliação das referências. A lista das referências citadas pelo app está no fim deste arquivo.

## Pré-requisitos

1. **Python 3.13**, de 64 bits, do python.org. Na instalação, marque "tcl/tk and IDLE" e o lançador "py" (são os padrões).
2. **Pacotes de terceiros**, nesta pasta e com internet:

   ```
   py -3.13 -m pip install -r requirements.txt
   ```

   São o numpy (o cálculo), o matplotlib (os gráficos da janela) e o Pillow (os ícones).
3. **Para gravar o DWG:** o TQS instalado e licenciado (V25 ou V26) e o pacote Python do TQS no Python 3.13. Com o TQS fechado, rode o `EXEC\X64\TQSPYINST.EXE` da instalação do TQS (por exemplo, `C:\TQSW\EXEC\X64\TQSPYINST.EXE`). Ele instala o pacote da versão em uso: `TQSPythonInterface` na V25 e `tqs` na V26.
   - O pacote não vem do PyPI, e a pasta não traz o wheel nem as DLLs do TQS: cada computador usa os da própria instalação.
   - O instalador põe o pacote no Python que acha pelo registro do Windows. Se houver mais de um Python, confira o resultado com o `Conferir instalacao.bat`.
4. **Microsoft Edge**, para o PDF da memória e a janela do 3D. Sem ele, a memória sai só em HTML (imprima pelo navegador) e o 3D abre no navegador padrão.

Sem o TQS, o cálculo, a memória, o 3D e a prévia do desenho funcionam; só o DWG, o PDF e o DXF do desenho não saem.

Para conferir tudo, use o **`Conferir instalacao.bat`**. Ele mostra, sem instalar nem gravar nada:

- o Python;
- o numpy, o tkinter, o matplotlib e o Pillow;
- o pacote e a instalação do TQS;
- os arquivos de suporte do TQS que o desenho usa;
- o Edge.

## Como abrir

- **Janela:** `Dimensionar Tubulao.bat`. Ele acha o Python 3.13 sozinho (pelo `py -3.13`, pelas pastas usuais de instalação ou pelo `python` do PATH) e avisa se não achar.
  - Sem os pacotes do `requirements.txt`, a janela não abre e diz o que falta.
  - Sem o TQS, ela abre com um aviso. O "DWG, PDF e DXF" diz o que falta e não grava nada, e o "Gerar tudo" grava a memória e o 3D e avisa que o desenho não saiu.
- **Lote** (cada programa calcula o tubulão a partir do arquivo de parâmetros, o mesmo que a janela salva):

  | Comando | Grava |
  |---|---|
  | `py -3.13 tubulao_core.py exemplos\T1_poste_DT600.json [--saida PASTA]` | `<nome>_resultado.json` e `<nome>_resumo.txt` |
  | `py -3.13 tubulao_memoria.py <parâmetros.json> [--saida PASTA] [--sem-pdf]` | memória em HTML e PDF |
  | `py -3.13 tubulao_3d.py <parâmetros.json> [--saida PASTA] [--abrir]` | página 3D |
  | `py -3.13 tubulao_dwg.py <parâmetros.json> [--saida PASTA]` | DWG, PDF e DXF (precisa do TQS) |
  | `py -3.13 tubulao_testes.py` | nada: confere o núcleo com os exemplos das referências |

  Sem um pacote ou sem o TQS, cada programa diz o que falta antes de gravar qualquer arquivo.
- **3D:** a página leva o three.js embutido e abre sem internet.

## Onde ficam as saídas

Por padrão, em `saidas\<nome do tubulão>\`, dentro desta pasta. Na janela, a pasta muda em "Saídas > Opções de saída". Para cada tubulão o app grava:

- `<nome>_memoria.html` e `<nome>_memoria.pdf`;
- `<nome>-3D.html`;
- `<nome>.DWG`, o desenho do TQS, com os ferros inteligentes e o bloco `$QUANT`;
- `<nome>-R00.PDF`, com o carimbo do licenciado do TQS deste computador;
- `<nome>.DXF`, com as cores da plotagem, se pedido.

O `tubulao_core.py` do lote grava o resultado e o resumo direto em `saidas\`. Erros da janela vão para `saidas\erros_janela.log`.

Deixe a pasta do app num lugar com permissão de escrita, não em "Arquivos de Programas".

## TQS V25 e V26

No pacote da V26 (`tqs` 3.0.x), o método que fixa a quantidade de ferros de uma faixa trocou de nome: `RebarDistrQuantity` na V25, `RebarDistrAutoSum` na V26. Os parâmetros e a rotina da DLL são os mesmos. O desenho do tubulão usa esse método na fretagem e nos estribos do fuste, e o app usa o que existir.

O TQS também põe a revisão no meio dos nomes longos do PDF: depois do 15º caractere na V25 (`T1-POSTE-DT600--R0012.PDF`) e do 23º na V26. O app acha o PDF que o TQS acabou de gravar e leva a revisão para o fim do nome (`T1-POSTE-DT600-12-R00.PDF`). Se o PDF anterior estiver aberto em outro programa, o TQS não o substitui, e o app avisa.

Testado em 14/11/2026, num computador com a V25 ativa e o pacote da V25 (`TQSPythonInterface` 2.1.7): os três exemplos e os mesmos tubulões com as sondagens da obra do original. Numa instalação da V26 completa (pacote e DLLs da V26), esta cópia ainda não foi testada. Se der erro, rode o `Conferir instalacao.bat` e anote a mensagem.

## Exemplos (`exemplos\`)

Os três usam as sondagens fictícias SP-A e SP-B (`sondagens_exemplo_SP-A_SP-B.json`, no formato da obra do GEOSPT).

| Arquivo | Caso | Resultado com as sondagens fictícias |
|---|---|---|
| `T1_poste_DT600.json` | Fundação de poste duplo T 600/12 m em anéis pré-moldados, cargas características | Anéis DN 2,00 m e L = 2,00 m. As 46 verificações passam; governa o deslocamento no ponto de aplicação (0,69). |
| `T2_pilar_dimensionamento.json` | Pilar 40 × 60 apoiado direto no tubulão, sem camisa, com dimensionamento automático de D e L | D = 2,00 m e L = 5,50 m (2 de 63 soluções passam). Fretagem em grelha: N2 20 ø8 C=204 e N3 40 ø8 C=201, com 9 anéis ø8 e 20 ø10 de montagem. Governa a tensão de borda da base (1,00). |
| `T3_fuste_armado.json` | Pilar 50 × 50 com momento alto, sem camisa, com dimensionamento automático: o fuste é armado | D = 1,60 m e L = 6,00 m. O fuste não passa em concreto simples e leva 40 ø16 C=515 e 19 estribos ø5. Governa a tensão de borda da base (0,96). |

Os comprimentos são os do TQS. Com as sondagens da obra do original, D, L e os ferros dos três exemplos são os mesmos; mudam a tensão admissível e os aproveitamentos.

A janela importa e exporta sondagens no formato do GEOSPT ("Furos e leituras": obra 2.x e exportação de detalhamento 1.x).

## Validação (`tubulao_testes.py`)

O núcleo reproduz, nas hipóteses de cada referência:

- o exemplo 6.10.2.2 de R01 (pressões de borda, profundidade do ponto de rotação, reação lateral);
- o exemplo numérico de R02 e o momento de R03;
- a solução 03 de R05 (rotação, deslocamentos e ponto de tensão nula).

Também confere a compatibilização das sondagens (cota heterogênea, cor e envoltória num caso montado), a concordância entre o pushover e o equilíbrio limite e os grampos da grelha de fretagem.

O teste que compara a média e a envoltória com as exportadas pelo GEOSPT usa os arquivos de uma obra e fica pulado nesta cópia. Para rodá-lo, ponha em `exemplos\` os dois arquivos do GEOSPT que o teste procura.

## Referências citadas pelo app

Os códigos aparecem na memória, nas mensagens e nos comentários do código.

| Cód. | Referência |
|---|---|
| R01 | PFEIL, W. *Pontes em Concreto Armado*, cap. 6 (tubulões; 6.10, tubulão curto). |
| R02 | TIMERMAN, J. Cálculo de tubulões curtos. *Revista Estrutura*, n. 90, p. 8–27, mar. 1980. |
| R03 | MARTINS, C. V. A. *Formulário para cálculo de tubulões curtos*, 1997 (programa TubCurto). |
| R04 | Rotina Python de cálculo de tubulões curtos que transcreve R03 (2022). |
| R05 | Memória de cálculo de fundações de poste duplo T, caso de validação (2022). |
| R06 | Desenho dessas fundações (2022). |
| R07 | ABNT NBR 6118:2026, *Projeto de estruturas de concreto*. |
| R08 | ABNT NBR 6122:2022, *Projeto e execução de fundações*. |
| R09 | SCHENBERGER, L.; TOLLER, M. *Cálculo de fundaciones* (método de Sulzberger). UTN, 2022: limite de rotação da fundação de poste, tg α ≤ 0,01. |

R04 a R06 são documentos de projeto e não vêm nesta pasta. Correlações com o SPT: Godoy (1972, 1983), Teixeira (1996), Teixeira e Godoy (1996) e o método de Alonso para a tensão admissível; resistência lateral: Brinch Hansen (1961) e Broms (1964).

## Arquivos

| Arquivo | Conteúdo |
|---|---|
| `Dimensionar Tubulao.bat`, `Conferir instalacao.bat`, `_achar_python.bat` | Atalhos |
| `tubulao_app.pyw` | Janela |
| `tubulao_core.py` | Núcleo: modelo de corpo rígido, combinações, verificações e dimensionamento |
| `tubulao_solo.py`, `tubulao_sondagem.py` | Parâmetros do solo e sondagens (compatibilização do GEOSPT) |
| `tubulao_concreto.py` | Concreto e armaduras (NBR 6118 e NBR 6122) |
| `tubulao_memoria.py` | Memória de cálculo em HTML e PDF |
| `tubulao_3d.py`, `tubulao_3d.html` | 3D |
| `tubulao_dwg.py` | Desenho em DWG do TQS |
| `tubulao_testes.py` | Validação |
| `estaca_core.py`, `estaca_dwg.py`, `estaca_previa.py`, `estaca_sondagem.py` | Desenho reaproveitado do app de estacas |
| `cad_ribbon.py`, `cad_icones.py` | Ribbon e ícones das janelas no estilo do TQS |
| `dependencias.py` | Conferência |
| `vendor\three-0.169.0\` | three.js, licença MIT |
| `requirements.txt` | Pacotes de terceiros |
