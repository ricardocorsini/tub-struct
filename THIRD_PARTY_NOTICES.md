# Origem e componentes de terceiros

## Base de cálculo recebida

O diretório `backend/legacy` preserva os arquivos do pacote `TubuloesCurtos_Portatil.zip` fornecido para adaptação e publicação neste repositório. O histórico, as referências técnicas e os avisos do pacote estão no seu `LEIA-ME.md`. A cópia portátil não contém uma licença geral explícita nem uma identificação autoral suficiente para atribuir autoria individual adicional; este repositório não inventa essa atribuição. O manifesto `docs/legacy-manifest.json` identifica exatamente a origem.

O TQS e seus produtos são componentes externos proprietários; não estão incluídos no TubStruct. Os adaptadores opcionais dependem da instalação licenciada do usuário.

## Bibliotecas

- React / React DOM — Meta e contribuidores, MIT.
- Three.js — autores e contribuidores, MIT. A versão 0.169.0 original inclui sua licença em `backend/legacy/vendor/three-0.169.0/LICENSE`; a interface usa a versão declarada em `package.json`.
- Lucide — contribuidores, ISC.
- Vite / TypeScript — autores e contribuidores, MIT / Apache-2.0.
- Tauri — contribuidores, MIT ou Apache-2.0; plugins conforme seus pacotes.
- Python — Python Software Foundation License.
- NumPy — NumPy Developers, BSD-3-Clause.
- FastAPI / Uvicorn — autores e contribuidores, MIT / BSD-3-Clause; somente no servidor de desenvolvimento.
- PyInstaller — GPL com exceção de distribuição do bootloader; usado no empacotamento do motor.

As licenças completas das dependências instaladas acompanham seus pacotes e devem ser preservadas na distribuição. A interface utiliza a organização visual do ArmaduraStruct como referência, sem incorporar seus módulos de CAD.
