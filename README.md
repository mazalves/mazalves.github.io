# Site pessoal — Marco Antonio Zanata Alves

Site acadêmico bilíngue (PT/EN) em [Hugo](https://gohugo.io), sem tema externo, publicado no GitHub Pages.

## Estrutura de diretórios

```
sitepessoal/
├── hugo.yaml                    Configuração: idiomas PT/EN, menu, links (ORCID, Lattes, DBLP). Ajuste baseURL e params aqui.
├── README.md                    Este guia.
├── .gitignore                   Ignora public/, resources/ e listagens do SIGA (dados de alunos).
├── .github/workflows/
│   └── deploy.yml               GitHub Actions: valida o .bib, confere o JSON, roda o Hugo e publica no Pages.
│
├── bib/
│   ├── publicacoes.bib          ★ FONTE ÚNICA das publicações. Chave = nome do PDF (ANO-SIGLA-Sobrenome).
│   └── pendentes.bib            (criado pelo importador) rascunhos a revisar e mover para publicacoes.bib.
│
├── data/                        Dados lidos pelos templates (site.Data.*)
│   ├── publicacoes.json         GERADO por bib2json.py — não edite.
│   ├── nuvem.json               GERADO por bib2json.py — termos da nuvem de palavras (página Pesquisa).
│   ├── ensino.json              GERADO por siga_para_json.py — disciplinas por curso (sem dados de alunos).
│   ├── videos.json              Vídeos avulsos e playlists (os do .bib entram sozinhos).
│   ├── projetos.json            Projetos de pesquisa (edite à mão; origem: Lattes e proposta PQ).
│   ├── pessoas.json             Orientandos atuais (edite à mão; origem: Lattes).
│   └── noticias.json            Notícias da página inicial (edite à mão).
│
├── content/                     Páginas em Markdown, um arquivo por idioma (nome.pt.md / nome.en.md)
│   ├── _index.*.md              Página inicial (trajetória, contatos).
│   ├── research/_index.*.md     Linhas de pesquisa e grupo HiPES.
│   ├── projects.*.md            Projetos de pesquisa (lista vem de data/projetos.json).
│   ├── publications/_index.*.md Texto de abertura da lista de publicações (a lista vem do JSON).
│   ├── teaching/_index.*.md     Ensino: tabelas por curso (shortcode ensino) + material.
│   ├── courses/*.md             Páginas de material de cada disciplina.
│   ├── people.*.md              Orientandos atuais + egressos (gerados do .bib e de pessoas.json).
│   ├── students.*.md            Convite a novos alunos.
│   ├── undergraduate-research.*.md  Iniciação científica.
│   └── videos.*.md              Vídeos (página montada por layouts/_default/videos.html).
│
├── layouts/                     Templates Hugo
│   ├── _default/baseof.html     Esqueleto (cabeçalho, menu, rodapé, idioma).
│   ├── _default/{list,single}.html  Páginas genéricas.
│   ├── _default/videos.html     Aba Vídeos: seções, busca e miniaturas que carregam o player ao clicar.
│   ├── index.html               Home: retrato, notícias e publicações recentes.
│   ├── publications/list.html   Lista de publicações: filtros, busca, selo de prêmio, botão BibTeX.
│   └── shortcodes/
│       ├── ensino.html          {{< ensino nivel="graduacao" curso="BCC" >}} → tabela de data/ensino.json
│       ├── pessoas.html         {{< pessoas grupo="doutorado" >}} → lista de data/pessoas.json
│       ├── egressos.html        {{< egressos >}} → teses/dissertações orientadas (do .bib), com filtro de nível e ano
│       ├── nuvem.html           {{< nuvem >}} → nuvem de palavras dos títulos (clique filtra Publicações)
│       ├── projetos.html        {{< projetos >}} → lista de data/projetos.json
│       ├── email.html           {{< email >}} → e-mail montado por JavaScript (anti-spam)
│       └── youtube.html         {{< youtube id="…" >}}
│
├── assets/
│   ├── css/main.css             Estilos (processados e minificados pelo Hugo).
│   └── js/publicacoes.js, videos.js   Filtro/busca/BibTeX; vídeos.
│
├── static/                      Copiado como está para o site
│   ├── pdf/                     PDFs nomeados pela chave: <chave>.pdf, _slides, _preprint, _poster, _en, _pt…
│   ├── img/  docs/              Imagens e documentos avulsos.
│
└── scripts/                     Ferramentas de manutenção (Python 3, só biblioteca padrão)
    ├── bib2json.py              .bib → data/publicacoes.json, com validação (--check só valida).
    ├── importar_pdfs.py         Pasta de PDFs soltos → renomeia/anexa, extrai título e gera rascunhos .bib.
    ├── baixar_acervo.py         Baixa teses do Acervo Digital da UFPR para as entradas sem PDF.
    ├── youtube_para_json.py     Canal/playlist do YouTube → data/videos.json (títulos e vídeos novos).
    ├── siga_para_json.py        Listagens do SIGA (HTML) → data/ensino.json.
    └── limpar_originais.py      Remove da sua pasta de PDFs originais os que já estão idênticos no site.
```

## Rodar localmente

Precisa de Hugo **extended** (≥ 0.141) e Python 3.8+ (sem pacotes extras).

```bash
python3 scripts/bib2json.py   # regenera data/publicacoes.json
hugo server                   # http://localhost:1313
```

## Publicações

### Convenção de nomes

A **chave BibTeX é o nome do arquivo**: `ANO-SIGLA-Sobrenome` (sobrenome do 1º autor).

| Item | Arquivo |
|---|---|
| Artigo | `static/pdf/2019-ARC-Lima.pdf` |
| Slides | `static/pdf/2019-ARC-Lima_slides.pdf` |
| Outras versões | `static/pdf/2019-ARC-Lima_preprint.pdf`, `_en`, `_pt`, `_poster`… (o sufixo vira o rótulo do link) |

- Sigla em maiúsculas (ARC, SBAC-PAD, PACMMOD). Para teses/dissertações use a instituição: `2022-UFPR-Carmin`.
- Dois trabalhos com a mesma chave? Acrescente `a`, `b`: `2022-ERADRS-Santosa`, `2022-ERADRS-Santosb`.
- **Não precisa declarar o PDF no `.bib`**: se o arquivo existe com o nome da chave, o link aparece sozinho.

### Adicionar uma publicação

1. Pegue o BibTeX (DBLP: botão “export record as BibTeX”; ou `curl -LH "Accept: application/x-bibtex" https://doi.org/<DOI>`).
2. Cole em `bib/publicacoes.bib`, troque a chave para `ANO-SIGLA-Sobrenome` e acrescente `category = {paper}`
   (`paper` · `abstract` · `software` · `thesis`). Opcional: `video = {https://...}`, `pdfurl = {https://...}` (PDF hospedado fora).
3. Copie o PDF para `static/pdf/<chave>.pdf`.
4. `python3 scripts/bib2json.py` — valida (chaves duplicadas, campos faltando, PDFs órfãos) e gera o JSON.

### Muitos PDFs de uma vez (nomes bagunçados)

```bash
python3 scripts/importar_pdfs.py ~/pasta                      # relatório, não copia nada
python3 scripts/importar_pdfs.py ~/pasta --aplicar            # copia os casamentos seguros
python3 scripts/importar_pdfs.py ~/pasta --stubs              # grava bib/pendentes.bib (rascunhos dos NOVOS)
python3 scripts/importar_pdfs.py ~/pasta --stubs --scholar google_citations.bib   # usa o Scholar como 2ª fonte
python3 scripts/importar_pdfs.py ~/pasta --csv relatorio.csv  # relatório em planilha
```

O script não confia no nome do arquivo: lê a 1ª página (título = maior fonte), DOI e metadados e compara
com o `.bib` (DOI idêntico ou título muito parecido). Classifica cada PDF como **CASOU**, **REVISAR**, **NOVO**,
**SLIDES** (viram `_slides`), **JÁ EXISTE** (mesmo MD5), ou **IGNORAR** (certificados etc.). Em teses, lê a capa
(autor, título) e detecta se você é orientador ou coorientador. Fluxo para um PDF novo: `--stubs` → revise
`bib/pendentes.bib` (sigla `XXX` = pendente) → mova para `publicacoes.bib` → rode de novo com `--aplicar`.
Requer `pdftotext`/`pdfinfo` (poppler). Nunca apaga os originais.

### Google Scholar BibTeX serve como fonte?

Como **fonte principal, não**: o export do Scholar não traz DOI, abrevia autores (“MAZ Alves”), mistura
versões duplicadas, perde acentos/LaTeX e tem entradas erradas ou de terceiros. Use **DBLP** (ou o DOI,
via `curl -LH "Accept: application/x-bibtex" https://doi.org/<DOI>`) como fonte principal e o Scholar apenas
para **descobrir** o que falta (`--scholar google_citations.bib` usa o título/ano dele nos rascunhos).

### Teses e dissertações do Acervo Digital

```bash
python3 scripts/baixar_acervo.py --dry-run     # lista o que baixaria
python3 scripts/baixar_acervo.py               # baixa, confere o título na 1ª página e grava <chave>.pdf
python3 scripts/baixar_acervo.py --buscar      # entradas sem handle: sugere candidatos pelo título
python3 scripts/baixar_acervo.py --orientados "Zanata Alves"   # itens do Acervo que faltam no .bib
python3 scripts/baixar_acervo.py --handle 70843                # metadados + rascunho de entrada .bib
```

Pega as entradas `thesis` sem PDF e com `url = {https://hdl.handle.net/1884/N}`. Arquivos cujo título não
bate vão para `static/pdf/_conferir/` (ignorada pelo git) para você decidir. **Atenção:** o script foi escrito
sem acesso ao Acervo; teste com `--dry-run` primeiro. Confirme também a política de divulgação de cada trabalho.

### Campos extras no .bib

`category` (paper · abstract · software · thesis) · `award = {Best Paper}` (selo ★) · `role = {co}` (coorientação) ·
`pdfurl` (PDF externo) · `video` · `dblp`. O botão **BibTeX** de cada item copia o registro sem esses campos.

## Nuvem de palavras

A nuvem na página Pesquisa é gerada pelo `bib2json.py` a partir dos títulos do `.bib` (`data/nuvem.json`): português e
inglês são unificados (memory/memória, performance/desempenho…) e siglas são preservadas. Para ajustar, edite
`CLOUD_CANON` (sinônimos) e `CLOUD_STOP` (palavras ignoradas) em `scripts/bib2json.py` e rode o script de novo.

## Vídeos

A aba Vídeos lê `data/videos.json` (cursos, divulgação, canal) e o campo `video = {https://youtu.be/...}` de cada
publicação (vão para Defesas se `category = {thesis}`, senão Apresentações). Para trazer títulos reais e vídeos
novos do canal, rode no seu computador:

```bash
python3 scripts/youtube_para_json.py --titulos          # preenche títulos dos marcados "titulo_auto"
python3 scripts/youtube_para_json.py --novos --dry-run  # vê o que há de novo no canal @HiPESLab
python3 scripts/youtube_para_json.py --novos            # grava em data/videos.json (seção "novos")
```

Depois mova os vídeos de `"novos"` para a seção certa em `data/videos.json`.

## Ensino a partir do SIGA

```bash
python3 scripts/siga_para_json.py SIGA_BCC.html SIGA_ibm.html SIGAPPGINF.html
```

Salve as listagens de turmas pelo navegador (arquivo → salvar página). O script grava só **disciplina, código,
semestre e ementa** em `data/ensino.json`; nomes e notas de alunos são descartados. **Não** versione os HTML do
SIGA (o `.gitignore` já bloqueia `SIGA*.html`). Códigos antigos → atuais (CI316→CI1316…) ficam em `CODIGO_ATUAL`.

## Publicar no GitHub Pages

1. Crie o repositório (`mazalves.github.io` publica na raiz do domínio — recomendado, pois as páginas usam caminhos como `/img/...`).
2. Em **Settings → Pages → Source**, escolha **GitHub Actions**.
3. `git push` na branch `main`. O workflow `.github/workflows/deploy.yml` valida o `.bib`, confere que o JSON está em dia, roda o Hugo e publica.

Domínio próprio: configure em Settings → Pages e ajuste `baseURL` em `hugo.yaml` (o workflow já injeta a URL correta).

## Notas

- Os PDFs somam ~240 MB; está dentro do limite do GitHub (arquivo < 100 MB, repositório < 1 GB), não precisa de Git LFS.
- Textos de páginas: edite `content/*.pt.md` e `content/*.en.md` (mantenha os dois em sincronia).
