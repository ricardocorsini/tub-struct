# Análise da base fornecida

Data da adaptação: 18/11/2026. Origem: `TubuloesCurtos_Portatil.zip`, cópia portátil de 14/11/2026. O manifesto registra o SHA-256 do ZIP e de cada arquivo (normalizando apenas CRLF/LF).

## Componentes identificados

| Componente                      | Função                                                                | Decisão da primeira versão                                        |
| ------------------------------- | --------------------------------------------------------------------- | ----------------------------------------------------------------- |
| `tubulao_core.py`               | Corpo rígido, combinações, base sem tração, verificações, busca D × L | Preservar e chamar em processo separado                           |
| `tubulao_solo.py`               | Correlações SPT e resistência lateral                                 | Preservar; permitir edições de camada com validação               |
| `tubulao_sondagem.py`           | Importação GEOSPT, compatibilização, média e envoltória               | Preservar; incorporar furos no projeto portátil                   |
| `tubulao_concreto.py`           | Concreto simples, interação N–M, armadura e fretagem                  | Preservar                                                         |
| `tubulao_memoria.py`            | Memória integral e figuras SVG                                        | Reutilizar HTML e figuras; adicionar identificação TubStruct      |
| `tubulao_3d.*`                  | Modelo interativo e exportação offline                                | Reutilizar dados e exportação; criar vista integrada com Three.js |
| `tubulao_dwg.py`, `estaca_*.py` | Desenho e ferros inteligentes TQS                                     | Preservar como integração opcional                                |
| `tubulao_app.pyw`, `cad_*.py`   | Interface Tk                                                          | Preservar histórico; substituir fluxo principal por React/Tauri   |

## Pontos relevantes encontrados

1. **Base numericamente rica.** Não é um formulário simples: contempla contato unilateral, plastificação de solo, várias combinações e dimensionamento estrutural. Uma tradução imediata para TypeScript ampliaria o risco de divergência; por isso o núcleo não foi reescrito.
2. **Referências fornecidas parcialmente.** O ZIP cita normas, Pfeil, Timerman e documentos de projeto, mas não traz a pasta de referências. A adaptação verifica regressão dos exemplos implementados, sem alegar auditoria independente das normas ou das correlações empíricas.
3. **Ações excepcionais aceitas pelo normalizador e ignoradas pelo combinador.** O adaptador bloqueia esse tipo até existir implementação verificável.
4. **Perfil SPT 2.3.** `preparar_solo` substitui o submodo 2.3 pelo conservador 2.2. O adaptador impede sua seleção para não rotular um resultado diferente da análise realizada.
5. **Entradas sem limites completos.** Passo de comprimento não positivo pode impedir o término de `candidatos`; discretizações e quantidades excessivas podem consumir recursos. O adaptador verifica finitude, tipos, intervalos, combinações e tamanho da varredura antes do núcleo.
6. **Arquivo de sondagem vinculado.** O aplicativo original depende de caminhos de arquivo. O novo formato incorpora os dados; importações antigas exigem selecionar a sondagem, sem leitura automática de caminhos externos.
7. **NSPT derivado persistido.** A normalização original aceita `nspt_calculo` fornecido no arquivo. Ao importar ou editar, o adaptador o recalcula a partir de `nspt_real`, evitando usar o valor derivado antigo após mudar uma leitura.
8. **Dimensionamento em duas etapas.** A triagem usa modelo reduzido/equilíbrio limite; a solução escolhida é reavaliada com análise completa e pode aumentar de tamanho. A interface distingue mapa de triagem e verificações finais.
9. **Resultados dependem do estado dos dados.** O cache da interface é associado ao JSON dos parâmetros e ao identificador do elemento. Resultados importados não são confiados nem restaurados como atuais; após reabrir, calcula-se novamente.
10. **Dependências proprietárias isoláveis.** O cálculo e a memória não precisam do TQS. Os módulos de desenho continuam disponíveis sem impor essa dependência à aplicação principal.

## Validação inicial

Os valores de referência em `backend/tests/reference-results.json` foram extraídos executando a cópia original, antes de conectar a interface. Comparam geometria final, situação global, quantidade de verificações, aproveitamento governante e armadura dos três exemplos.

A suíte original cobre Pfeil, Timerman/TubCurto, o caso R05, compatibilização de solo, equilíbrio limite/pushover e grampos. O ensaio de comparação com arquivos reais do GEOSPT permanece explicitamente pulado por ausência dos arquivos no anexo.

## Convenções da interface

N positivo: compressão. Cargas e momentos no topo do tubulão; eixo z de engenharia para cima. Hx e My positivos produzem tombamento compatível; Hy e Mx de sinal negativo também. A altura de aplicação não transporta automaticamente as ações. O motor mantém as convenções e verificações do anexo.

O modelo gráfico usa o eixo vertical do Three.js internamente; o sistema de engenharia é indicado na legenda. Comprimentos, ganchos e zonas de armadura devem ser conferidos na memória. A vista integrada não é um desenho executivo.
