# TubStruct · OpenStruct

**TubStruct 0.1.0** — análise e dimensionamento de tubulões curtos, rígidos, circulares e sem base alargada. Interface no padrão do ArmaduraStruct: ribbon, árvore de projeto, propriedades laterais, área gráfica e resultados rastreáveis.

A interface usa React, TypeScript e Vite, com Tauri 2 no desktop, seguindo a estrutura de ArmaduraStruct e ConsoloStruct. O TubStruct acrescenta a pasta `backend/` para executar o motor Python/NumPy do pacote `TubuloesCurtos_Portatil.zip`.

## Rodar localmente

**Pelo instalador desktop**, baixe o pacote do seu sistema em [Desktop builds](https://github.com/ricardocorsini/tub-struct/actions/workflows/desktop.yml). O aplicativo inclui Python e NumPy. Basta abrir o TubStruct e calcular.

**Pelo código-fonte**, instale Node **22.12+** e Python **3.12 ou 3.13**. No terminal:

```bash
git clone https://github.com/ricardocorsini/tub-struct.git
cd tub-struct
npm ci
npm run setup:engine
npm run dev
```

`setup:engine` cria a `.venv` e instala as dependências na primeira configuração. `npm run dev` usa esse ambiente automaticamente, sobe a interface e a API de cálculo e exibe o endereço [http://127.0.0.1:1420](http://127.0.0.1:1420). Abra a página e clique em **Calcular** para testar o exemplo inicial. Use `Ctrl+C` para encerrar.

Se o terminal apontar que a porta 1420 ou 8765 está em uso, encerre a outra aplicação na porta indicada e execute `npm run dev` novamente. Para escolher o Python que cria a `.venv`, defina `TUBSTRUCT_PYTHON` com o caminho do executável antes de executar `npm run setup:engine`.

## O que funciona

- Projeto com múltiplos tubulões; criar, duplicar, remover, desfazer/refazer e recuperação local.
- Arquivo portátil `.tubstruct.json`, com sondagens incorporadas; importação de parâmetros do aplicativo original.
- Geometria, camisa de anéis, folga, lastro, materiais, apoio de pilar/poste e critérios editáveis.
- Ações características N, Hx, Hy, Mx e My; grupos de ações variáveis mutuamente exclusivas e combinações do núcleo.
- Cadastro de furos e leituras SPT; importação GEOSPT obra 2.x e detalhamento 1.x; perfis médio, envoltória e furos individuais.
- Verificação de geometria fixa e dimensionamento automático D × L, com reavaliação da solução pelo modelo completo.
- Visualização 3D com órbita, zoom, vistas, camadas de solo, camisa, concreto, água e armaduras calculadas. Renderização sob demanda, sem animação contínua em repouso.
- Corte, perfis SPT, diagramas de esforços, tabela de verificações com filtros, observações e memória integral do cálculo.
- Quantitativos por elemento e total; CSV; resultado JSON; memória HTML; 3D HTML independente e offline.
- No navegador, impressão da memória em PDF. No desktop, salve o HTML e abra no navegador para imprimir.
- Proteção contra resultados desatualizados: qualquer mudança nos parâmetros invalida a saída daquele elemento; respostas atrasadas não substituem os resultados dos dados atuais.

O ícone provisório é SVG textual. PNG/ICO dos instaladores são gerados no build; imagens em base64 e binários de build não são versionados.

## Executar serviços separados

Para trabalhar diretamente em cada processo, execute a API no ambiente Python e a interface em outro terminal:

```bash
python -m uvicorn backend.server:app --host 127.0.0.1 --port 8765
npm run dev:ui
```

`npm run build` gera a interface em `dist/`. Para calcular na prévia, mantenha a API ativa e execute `npm run preview`.

## Desktop Linux e Windows

Instale os [pré-requisitos Tauri 2](https://v2.tauri.app/start/prerequisites/) e Rust. Ative a `.venv` antes de compilar ou desenvolver a janela nativa. Use `source .venv/bin/activate` no Linux ou `.venv\Scripts\Activate.ps1` no PowerShell.

```bash
python -m pip install -r backend/requirements-build.txt
npm run desktop:dev
```

O desenvolvimento usa `python3` (Linux) ou `python` (Windows). Para escolher outro interpretador, defina `TUBSTRUCT_PYTHON` com o caminho completo.

Para compilar:

```bash
# Linux
npm run desktop:build -- --bundles deb,appimage
# Windows
npm run desktop:build -- --bundles nsis
```

Os ícones e o executável `tubstruct-engine` são gerados antes do build. A versão empacotada inclui Python e NumPy; não exige Python, TQS, internet ou servidor local para calcular. A comunicação desktop é por IPC/stdin, sem abrir uma porta HTTP.

O workflow **Desktop builds** compila os dois sistemas e disponibiliza os instaladores como artefatos do GitHub Actions. Criar uma release pública e integrar Launcher/site são etapas separadas; esta versão não altera outros repositórios.

## Como usar

1. Ao abrir pela primeira vez, o aplicativo apresenta o exemplo do poste, **sem resultados pré-calculados**. A faixa informa que são dados fictícios.
2. Use **Novo projeto** para começar vazio; preencha a identificação.
3. Cadastre geometria, materiais, apoio, ações e sondagens. Cargas positivas N representam compressão; unidades básicas: m, kN, kN·m, MPa.
4. As ações são referidas ao **topo do tubulão**. Inclua previamente o transporte H × h nos momentos. A altura do apoio é usada no deslocamento do ponto de aplicação e não acrescenta momentos às ações automaticamente.
5. Pressione **Calcular** ou **F9**. Revise todas as verificações e observações, além do aproveitamento governante.
6. No dimensionamento automático, a geometria da visualização passa a ser a solução calculada. Os parâmetros de entrada continuam disponíveis. **Adotar geometria calculada**, na aba D × L, transforma-a em geometria fixa e exige novo cálculo.
7. Exporte as saídas em **Resultados**. **Salvar / Ctrl+S** gera uma cópia portátil do projeto; recuperação local não substitui esse arquivo.

Arquivos antigos que apontam para uma sondagem externa precisam da importação desse arquivo em **Sondagens**. A aplicação não acessa caminhos arbitrários contidos no JSON. As opções completas do contrato, inclusive edições por camada e lista de diâmetros, ficam em **Parâmetros completos**.

## Hipóteses e limites desta adaptação

O modelo original possui cinco graus de liberdade de corpo rígido, molas laterais limitadas por resistência, base polar sem tração, solução de Newton e verificação de ruptura por pushover/equilíbrio limite. Combinações, referências e interpretações normativas são as registradas na base fornecida. **Preservação e regressão do código não equivalem a revisão normativa independente.** Consulte a memória e [a análise da base](docs/BASE_ANALYSIS.md).

- Seção circular constante; sem base alargada na interface de produção.
- Ações permanentes e variáveis. Ações excepcionais são bloqueadas porque não entram nas combinações implementadas no núcleo.
- SPT 2.1 e 2.2; o modo 2.3 é bloqueado porque o núcleo o substitui por 2.2.
- Até 100 elementos por projeto, 12 ações por elemento, 50 furos e 500 candidatos por varredura; tempo máximo de 5 minutos por operação.
- Análise por elemento. Quantitativos do elemento consideram sua repetição; não há combinação de fundações ou memorial consolidado da obra.
- A vista 3D interna apresenta armaduras de modo esquemático; ganchos e detalhes completos devem ser conferidos na memória e na integração original. O apoio é mostrado com altura gráfica reduzida.
- A exportação **DWG/DXF/PDF de desenho com ferros inteligentes** continua na integração TQS original, exclusiva de Windows com instalação licenciada. Não foi implementado um novo exportador DWG independente.

## Integração TQS preservada

Todo o pacote recebido está em `backend/legacy`, inclusive a janela Tk original, três exemplos, testes e dependências opcionais. Os arquivos foram preservados integralmente (normalização de quebras de linha permitida); o manifesto de hashes está em [docs/legacy-manifest.json](docs/legacy-manifest.json).

Para usar a integração original, consulte [backend/legacy/LEIA-ME.md](backend/legacy/LEIA-ME.md). Não há DLL, licença ou wheel proprietário do TQS neste repositório.

## Verificação

```bash
npm run check
npx playwright install chromium
npm run test:e2e
python scripts/test_frozen_engine.py  # após preparar o motor empacotado
```

`npm run check` verifica TypeScript/build, persistência/importação e testes Python (entradas inválidas, isolamento de arquivos, exemplos e referências originais). Os testes de interface usam o motor real, não respostas simuladas. Evidências visuais e traces são anexados ao workflow CI.

| Exemplo original | Geometria esperada                    | Verificações | Resultado relevante           |
| ---------------- | ------------------------------------- | -----------: | ----------------------------- |
| T1 poste         | DN 2,00 m; D externo 2,20 m; L 2,00 m |           46 | Aproveitamento 0,688904823    |
| T2 pilar         | D 2,00 m; L 5,50 m                    |           99 | 2 de 63 candidatos na triagem |
| T3 fuste armado  | D 1,60 m; L 6,00 m                    |          100 | 40 barras Ø16 mm              |

O teste original com arquivos reais da obra de Pinheiro é pulado, pois esses arquivos não vieram no ZIP. Não são criados dados substitutos para esse ensaio.

## Estrutura

```text
src/                 interface, projeto e visualização
backend/engine.py    validação e adaptação do contrato original
backend/worker.py    processo isolado de cálculo
backend/server.py    API de desenvolvimento em loopback
backend/legacy/      base fornecida, preservada
backend/tests/       regressão numérica e validação
src-tauri/           aplicativo desktop e IPC
scripts/             desenvolvimento e empacotamento
tests/               testes TypeScript e interface
docs/                análise, arquitetura e rastreabilidade
```

Contribuições: preserve os testes numéricos e a invalidação de resultados; mudanças em hipóteses de engenharia precisam de referência e teste independente. [Próximas etapas](docs/ROADMAP.md).
