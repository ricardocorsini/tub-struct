# Arquitetura 0.1.0

React mantém o projeto de entrada e resultados efêmeros. Cada resultado tem a identidade do elemento e o JSON exato dos parâmetros calculados. Alterações invalidam a saída; uma resposta atrasada só é mostrada se corresponder aos dados atuais. O projeto portátil não contém resultados nem caminhos absolutos necessários ao cálculo.

No navegador de desenvolvimento, `POST /api/request` é encaminhado pelo Vite à API FastAPI em `127.0.0.1:8765`. Cada operação executa `backend/worker.py` em um novo processo. A API limita o corpo a 2 MB, duas operações simultâneas, origens locais e 300 segundos; o processo é encerrado ao exceder o prazo. Não é uma API de hospedagem pública.

No desktop, o comando Tauri `engine_request` chama diretamente o executável local empacotado. A mensagem JSON é enviada por stdin, nunca pela linha de comando ou por arquivo temporário com dados de projeto. O resultado retorna por stdout. O processo tem tempo limite e é encerrado se a tarefa for descartada. Em desenvolvimento, o interpretador pode ser selecionado por `TUBSTRUCT_PYTHON`.

O adaptador `engine.py` valida os parâmetros e reaproveita os módulos originais. O núcleo é preservado em `backend/legacy`; seu manifesto detecta alterações acidentais. O processo não importa os módulos de desenho TQS para calcular. PyInstaller inclui Python, NumPy e os recursos locais da visualização 3D.

A memória é renderizada em iframe sem permissão de scripts. As exportações usam arquivos escolhidos pelo usuário no desktop ou download no navegador. Números não finitos são rejeitados na entrada; resultados usam a serialização do núcleo (`inf` como texto quando pertinente).

## Alterações futuras

Mudanças no motor devem vir acompanhadas de casos independentes de referência. A suíte de regressão deve continuar distinguindo reprodução do original de validação de uma nova hipótese. Caso se adote Rust/TypeScript no futuro, mantenha comparação dos resultados por combinação e por perfil, não apenas da geometria escolhida.

Documentação técnica consultada para empacotamento: [Tauri sidecars](https://v2.tauri.app/develop/sidecar/), [diálogos](https://v2.tauri.app/plugin/dialog/), [arquivos](https://v2.tauri.app/plugin/file-system/).
