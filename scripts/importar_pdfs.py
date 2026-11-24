#!/usr/bin/env python3
"""Importa PDFs soltos (com nomes bagunçados) para static/pdf/ com o nome padrão.

Uso:
    python3 scripts/importar_pdfs.py PASTA                 # relatório (não copia nada)
    python3 scripts/importar_pdfs.py PASTA --aplicar       # copia os casamentos seguros
    python3 scripts/importar_pdfs.py PASTA --stubs         # grava bib/pendentes.bib com rascunhos
    python3 scripts/importar_pdfs.py PASTA --scholar google_citations.bib   # 2ª fonte p/ rascunhos

Precisa de `pdftotext` e `pdfinfo` (poppler: `apt install poppler-utils` / `brew install poppler`).
Só biblioteca padrão do Python. Percorre subpastas. NUNCA apaga nem move os originais.

Como decide (para cada PDF):
  1. Extrai DOI, título dos metadados, e os títulos "candidatos" da 1ª página
     (grupos de linhas com a maior fonte, que costuma ser o título).
  2. Compara com os registros de bib/publicacoes.bib: DOI idêntico = certeza; senão
     similaridade de título (ignora acentos/caixa/pontuação).
  3. Classifica: CASOU (>=0.88), REVISAR (0.70-0.88), NOVO (não está no .bib),
     SLIDES (vira <chave>_slides.pdf), JÁ EXISTE (mesmo conteúdo já em static/pdf),
     IGNORAR (certificado, imagem, etc.).
Os NOVOS saem como rascunho em bib/pendentes.bib (com --stubs): revise, mova para
publicacoes.bib e rode este script de novo — aí o PDF é anexado sozinho.
"""
import argparse
import csv
import difflib
import hashlib
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bib2json as B  # noqa: E402

PENDENTES = B.ROOT / "bib" / "pendentes.bib"
DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>\]\)]+)", re.I)
BAD_TITLES = re.compile(r"^(microsoft word|untitled|document\d*|paper|manuscript|slide|presentation|powerpoint|"
                        r"noname|sem t[ií]tulo|main|article|arquivo)\b|\.(docx?|tex|pdf|pptx?)$", re.I)
CERT_RE = re.compile(r"certificamos|certificado de|certificate of|certif[ií]cate|menção honrosa|best paper award", re.I)
CERT_NAME_RE = re.compile(r"certific", re.I)
WEBPRINT_RE = re.compile(r"Institutional Sign In|IEEE Xplore\s+IEEE SA|Skip to main content|ResearchGate|Google Scholar", re.I)
INSTIT_RE = re.compile(r"universidade|setor de|departamento|programa de|curso de|instituto|centro de|faculdade|escola|especializa|p[oó]s-gradua", re.I)
CITY_RE = re.compile(r"^(curitiba|cidade|pr|brasil)\b|\b(19|20)\d\d\s*$", re.I)
THESIS_RE = re.compile(r"(trabalho de conclus[aã]o|monografia|disserta[cç][aã]o|tese de|qualifica[cç][aã]o)", re.I)


# ----------------------------------------------------------------------------- utilidades
def norm(s):
    s = unicodedata.normalize("NFKD", B.latex2text(s).lower())
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in s if not unicodedata.combining(c)))


def run(cmd, timeout=60):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, errors="replace").stdout
    except FileNotFoundError:
        sys.exit(f"'{cmd[0]}' não encontrado. Instale poppler: sudo apt install poppler-utils (ou brew install poppler)")
    except subprocess.TimeoutExpired:
        return ""


def md5(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sim(a, b):
    """Similaridade 0-1 entre dois textos já normalizados."""
    if not a or not b:
        return 0.0
    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    if len(short) >= 15 and short in long_ and len(short) >= 0.6 * len(long_):
        return 0.97
    return difflib.SequenceMatcher(None, a, b).ratio()


# ----------------------------------------------------------------------------- extração
def page1_lines(pdf):
    """[(texto, ymin, altura)] da 1ª página, via pdftotext -bbox-layout."""
    xml = run(["pdftotext", "-bbox-layout", "-f", "1", "-l", "1", str(pdf), "-"])
    m = re.search(r'<page width="([\d.]+)" height="([\d.]+)"', xml)
    pw, ph = (float(m.group(1)), float(m.group(2))) if m else (1, 1)
    lines = []
    for lm in re.finditer(r'<line xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</line>', xml, re.S):
        ymin, ymax = float(lm.group(2)), float(lm.group(4))
        words = re.findall(r">([^<]+)</word>", lm.group(5))
        txt = re.sub(r"\s+", " ", " ".join(words)).strip()
        txt = txt.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'")
        if txt:
            lines.append((txt, ymin, ymax - ymin))
    return lines, pw, ph


def title_candidates(lines, ph):
    """Grupos contíguos de linhas com fonte parecida; devolve os 3 de maior fonte + o 1º longo."""
    top = [l for l in lines if l[1] < 0.7 * ph and 3 <= len(l[0]) <= 220 and not re.fullmatch(r"[\d\W]+", l[0])]
    groups, cur = [], []
    for l in top:
        if cur and abs(l[2] - cur[-1][2]) / max(cur[-1][2], 1) < 0.12 and l[1] - (cur[-1][1] + cur[-1][2]) < 1.6 * l[2]:
            cur.append(l)
        else:
            if cur:
                groups.append(cur)
            cur = [l]
    if cur:
        groups.append(cur)
    scored = []
    for g in groups:
        txt = " ".join(x[0] for x in g)
        if len(txt) >= 12 and len(txt.split()) >= 2:
            scored.append((sum(x[2] for x in g) / len(g), txt))
    scored.sort(key=lambda t: -t[0])
    cands = [t for _, t in scored[:3]]
    for g in groups:                       # 1o grupo (ordem de leitura) com >= 4 palavras
        t = " ".join(x[0] for x in g)
        if len(t.split()) >= 4:
            cands.append(t)
            break
    return cands


def thesis_cover(lines, ph, text, name):
    """Capas padrão UFPR: instituição / AUTOR / TÍTULO / CIDADE / ANO. Devolve dict ou None."""
    head = text[:2500]
    if not (THESIS_RE.search(head) or re.search(r"tcc|monografia|disserta|tese|defesa", name, re.I)):
        return None
    body = [l for l in lines if l[1] < 0.97 * ph]
    if not any(re.search(r"universidade", l[0], re.I) for l in body):
        return None
    rest = [l for l in body if not INSTIT_RE.search(l[0])]
    if len(rest) < 2:
        return None
    author = rest[0][0]
    if not (2 <= len(author.split()) <= 7 and not re.search(r"\d", author)):
        return None
    title, year = [], ""
    STOP = re.compile(r"^(\(|disserta[cç][aã]o|monografia|trabalho de|tese|orientador|coorientador|apresentad|projeto)", re.I)
    for l in rest[1:]:
        if STOP.search(l[0]) and title:
            break
        if CITY_RE.search(l[0]):
            m = re.search(r"((?:19|20)\d\d)\s*$", l[0])
            year = year or (m.group(1) if m else "")
            if title and year:
                break
            continue
        title.append(l[0])
    if not title:
        return None
    low = head.lower()
    if "especializa" in low or "data science" in low:
        kind = ("mastersthesis", "Especialização")
    elif re.search(r"\btese\b", low) and "doutor" in low:
        kind = ("phdthesis", "")
    elif "disserta" in low and "conclus" not in low:
        kind = ("mastersthesis", "")
    else:
        kind = ("mastersthesis", "Trabalho de Conclusão de Curso")
    return {"author": author, "title": " ".join(title), "year": year, "etype": kind[0], "kind": kind[1], "advisor": None}


def advisor_roles(front):
    """Papéis em que o nome do professor aparece no texto: orientador, coorientador, banca..."""
    roles = set()
    for m in re.finditer(r"zanata|marco\s+ant[oô]nio\s+z|marco\s+a\.\s*z", front, re.I):
        ctx = front[max(0, m.start() - 90):m.start()].lower().replace("\n", " ")
        if re.search(r"co-?orientador", ctx):
            roles.add("coorientador")
        elif re.search(r"orientador|supervisor|advisor", ctx):
            roles.add("orientador")
        elif re.search(r"banca|examinador|membro|avaliador|aprovad", ctx):
            roles.add("banca")
        else:
            roles.add("citado")
    return sorted(roles)


def extract(pdf):
    info = run(["pdfinfo", str(pdf)])
    meta_title = (re.search(r"^Title:\s*(.+)$", info, re.M) or [None, ""])[1].strip()
    pages = int((re.search(r"^Pages:\s*(\d+)", info, re.M) or [0, 0])[1])
    size = re.search(r"Page size:\s*([\d.]+) x ([\d.]+)", info)
    landscape = bool(size and float(size.group(1)) > float(size.group(2)) * 1.15)
    text = run(["pdftotext", "-f", "1", "-l", "2", "-layout", str(pdf), "-"])
    lines, pw, ph = page1_lines(pdf)
    cands = title_candidates(lines, ph)
    cover = thesis_cover(lines, ph, text, pdf.stem)
    if cover:
        cands.insert(0, cover["title"])
        front = run(["pdftotext", "-f", "1", "-l", "5", str(pdf), "-"])
        cover["advisor"] = advisor_roles(front)
    dois = [d.rstrip(".,;)") for d in DOI_RE.findall(text + " " + info)]
    allwords = len(text.split())
    return {
        "cover": cover, "path": pdf, "pages": pages, "landscape": landscape, "text": text, "cands": cands,
        "doi": dois[0].lower() if dois else "", "meta_title": meta_title,
        "words_p1": len(" ".join(l[0] for l in lines).split()), "words": allwords,
        "norm_text": norm(text[:6000]),
    }


def is_slides(x):
    name = x["path"].stem.lower()
    if re.search(r"slide|apresenta|\bppt", name):
        return True
    if re.search(r"defesa", name) and x["landscape"]:
        return True
    return x["landscape"] and x["words_p1"] < 120


# ----------------------------------------------------------------------------- casamento
def best_match(x, records):
    """records: [{'key','title','doi','src'}]. Devolve (score, registro, motivo)."""
    best = (0.0, None, "")
    nt_cands = [norm(c) for c in x["cands"]]
    for r in records:
        if x["doi"] and r["doi"] and x["doi"] == r["doi"]:
            return 1.0, r, "DOI"
        nt = r["ntitle"]
        s = max([sim(c, nt) for c in nt_cands] or [0.0])
        if len(nt) >= 25 and nt in x["norm_text"][:3500]:
            s = max(s, 0.92)
        if s > best[0]:
            best = (s, r, "título")
    return best


def load_records(bibpath, src):
    out = []
    if not Path(bibpath).exists():
        return out
    for e in B.parse_bib(Path(bibpath).read_text(encoding="utf-8")):
        f = e["fields"]
        t = B.latex2text(f.get("title", ""))
        out.append({"key": e["key"], "title": t, "ntitle": norm(t), "doi": B.latex2text(f.get("doi", "")).lower(),
                    "src": src, "fields": f, "type": e["type"]})
    return out


# ----------------------------------------------------------------------------- rascunho BibTeX
KNOWN = [(r"computer on the beach", "COTB"), (r"meeting abstracts|american meteorological", "AMS"),
         (r"escola regional de alto desempenho", "ERADRS"), (r"alto desempenho", "WSCAD"),
         (r"knowledge discovery", "KDMILE"), (r"ciberseguran|seguran[cç]a da informa", "SBSEG"),
         (r"banco de dados", "SBBD"), (r"engenharia de software", "SBES")]
ALIASES = {"SSCAD": "WSCAD"}


def guess_sigla(venue):
    for pat, sg in KNOWN:
        if re.search(pat, venue, re.I):
            return sg
    m = re.search(r"\(([A-Z][A-Za-z\-]{2,12})\)", venue) or re.search(r"\b([A-Z]{3,10}(?:-[A-Z]{2,5})?)\b", venue)
    return ALIASES.get(m.group(1).upper(), m.group(1).upper()) if m else "XXX"


def surname_of(author):
    a = B.latex2text(author)
    last = a.split(",")[0] if "," in a else a.split()[-1]
    return re.sub(r"[^A-Za-z]", "", "".join(c for c in unicodedata.normalize("NFKD", last) if not unicodedata.combining(c))).capitalize() or "Autor"


def sentence_case(t):
    t = re.sub(r"\s+", " ", t).strip()
    return t[:1] + t[1:].lower() if t.isupper() else t


def person_case(n):
    if not n.isupper():
        return n
    small = {"de", "da", "do", "das", "dos", "e"}
    return " ".join(w.lower() if (w.lower() in small and i) else w.capitalize() for i, w in enumerate(n.split()))


def make_stub(x, rec, existing_keys, extra_pdfs=()):
    """Rascunho BibTeX. Prioridade: capa de tese/TCC > registro do Scholar > só o que o PDF revela."""
    cover, f = x.get("cover"), (dict(rec["fields"]) if rec else {})
    notes = []
    if cover:
        etype, authors = cover["etype"], person_case(cover["author"])
        title, year, venue, sigla = sentence_case(cover["title"]), cover["year"], "", "UFPR"
        notes.append("capa lida automaticamente: confira autor e título (maiúsculas)")
        roles = cover.get("advisor") or []
        notes.append("seu nome nas 5 primeiras páginas como: " + (", ".join(roles) if roles else "NÃO aparece (provavelmente não é sua orientação)"))
    elif rec:
        etype, authors = rec["type"], f.get("author", "FIXME")
        if etype == "article" and re.search(r"anais|proceedings|symposium|simp[óo]sio|conference|workshop|meeting|escola", (f.get("journal") or ""), re.I):
            etype = "inproceedings"
        title = B.latex2text(f.get("title", ""))
        year = f.get("year", "")
        venue = B.latex2text(f.get("booktitle") or f.get("journal") or "")
        sigla = guess_sigla(venue)
        notes.append("dados do Google Scholar (autores abreviados, sem DOI): confira em DBLP/DOI")
    else:
        etype, authors, venue, sigla = "inproceedings", "FIXME", "", "XXX"
        title = sentence_case(x["cands"][0]) if x["cands"] else x["path"].stem
        year = ""
        notes.append("nada identificado além do título provável")
    if not year:
        m = re.search(r"\b(20[0-2]\d|199\d)\b", x["path"].stem) or re.search(r"\b(20[0-2]\d)\b", x["text"][:3000])
        year = m.group(1) if m else ""
    first = surname_of(authors.split(" and ")[0]) if authors != "FIXME" else "Autor"
    base = f"{year or 'ANO'}-{sigla}-{first}"
    key, n = base, 0
    while key.lower() in existing_keys:
        n += 1
        key = base + "abcdefgh"[n - 1]
    existing_keys.add(key.lower())
    lines = [f"% pdf-origem: {x['path']}"]
    lines += [f"% também: {e}" for e in extra_pdfs]
    lines += [f"% AVISO: {m}" for m in notes]
    lines += [f"@{etype}{{{key},", f"  author       = {{{authors}}},", f"  title        = {{{title}}},"]
    if venue:
        lines.append(f"  {'journal   ' if etype == 'article' else 'booktitle '}  = {{{venue}}},")
    if cover:
        lines.append("  school       = {UFPR},")
        if cover["kind"]:
            lines.append(f"  type         = {{{cover['kind']}}},")
    if f.get("pages"):
        lines.append(f"  pages        = {{{f['pages']}}},")
    lines.append(f"  year         = {{{year or 'FIXME'}}},")
    if x["doi"]:
        lines.append(f"  doi          = {{{x['doi']}}},")
    lines.append("  category     = {" + ("thesis" if cover else "paper") + "},")
    lines[-1] = lines[-1].rstrip(",")
    lines.append("}")
    return key, "\n".join(lines)


# ----------------------------------------------------------------------------- principal
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pasta")
    ap.add_argument("--aplicar", action="store_true", help="copia os PDFs com casamento seguro para static/pdf/")
    ap.add_argument("--stubs", action="store_true", help="grava rascunhos BibTeX dos PDFs novos em bib/pendentes.bib")
    ap.add_argument("--scholar", help="export BibTeX do Google Scholar, usado como 2ª fonte para os rascunhos")
    ap.add_argument("--csv", default="relatorio-importacao.csv", help="relatório CSV (padrão: ./relatorio-importacao.csv)")
    ap.add_argument("--minimo", type=float, default=0.88, help="similaridade mínima p/ casar (padrão 0.88)")
    args = ap.parse_args()

    pasta = Path(args.pasta).expanduser()
    if not pasta.is_dir():
        sys.exit(f"pasta não encontrada: {pasta}")
    mine = load_records(B.BIB, "bib")
    scholar = load_records(args.scholar, "scholar") if args.scholar else []
    known = {r["key"].lower() for r in mine}
    existing = {md5(p): p.name for p in B.PDF_DIR.glob("*.pdf")} if B.PDF_DIR.is_dir() else {}

    pdfs = sorted(p for p in pasta.rglob("*") if p.suffix.lower() == ".pdf")
    others = sorted(p for p in pasta.rglob("*") if p.is_file() and p.suffix.lower() != ".pdf")
    print(f"{len(pdfs)} PDFs em {pasta} (+{len(others)} arquivos não-PDF ignorados)\n")

    rows, plan, seen_md5 = [], {}, {}
    for p in pdfs:
        rel = p.relative_to(pasta)
        h = md5(p)
        if h in existing:
            rows.append((rel, "JÁ EXISTE", "", f"idêntico a static/pdf/{existing[h]}", ""))
            continue
        if h in seen_md5:
            rows.append((rel, "DUPLICADO", "", f"mesmo conteúdo que {seen_md5[h]}", ""))
            continue
        seen_md5[h] = rel
        x = extract(p)
        if x["pages"] <= 2 and (CERT_NAME_RE.search(p.name) or CERT_RE.search(x["text"][:900])):
            rows.append((rel, "IGNORAR", "", "certificado/prêmio (use o dado para o campo award= do .bib)", ""))
            continue
        if WEBPRINT_RE.search(x["text"][:1500]) and x["pages"] <= 4:
            rows.append((rel, "IGNORAR", "", "impressão de página web, não é o artigo", ""))
            continue
        if x["pages"] >= 150 and not x["cover"]:
            rows.append((rel, "IGNORAR", "", f"{x['pages']} páginas: parece anais/livro inteiro", ""))
            continue
        if re.search(r"qualifica", p.stem, re.I) and x["cover"]:
            rows.append((rel, "IGNORAR", "", "exame de qualificação (não é trabalho final)", ""))
            continue
        score, rec, why = best_match(x, mine)
        slides = is_slides(x)
        if rec and score >= args.minimo:
            suf = "_slides" if slides else ("_preprint" if re.search(r"preprint", p.stem, re.I) else "")
            dest = f"{rec['key']}{suf}.pdf"
            rows.append((rel, "CASOU" + (" (slides)" if slides else ""), f"{score:.2f}", f"{rec['key']} · {rec['title'][:60]} [{why}]", dest))
            plan.setdefault(dest, []).append((score, x, rel))
        elif rec and score >= 0.70:
            rows.append((rel, "REVISAR", f"{score:.2f}", f"talvez {rec['key']} · {rec['title'][:60]}", ""))
            rows[-1] = rows[-1] + (x,)
        else:
            srec, sscore, _ = None, 0.0, ""
            if scholar:
                sscore, srec, _ = best_match(x, scholar)
            tag = "NOVO"
            info = (x["cands"][0][:70] if x["cands"] else "(título não detectado)")
            if srec and sscore >= args.minimo:
                info = f"{srec['title'][:70]} [achado no Scholar]"
            else:
                srec = None
            rows.append((rel, tag + (" (slides)" if slides else ""), "", info, "", x, srec))

    # conflitos: vários PDFs para o mesmo destino
    applied = []
    for dest, lst in plan.items():
        lst.sort(key=lambda t: (-t[0], -t[1]["pages"]))
        applied.append((dest, lst[0][1]["path"]))
        for _, x, rel in lst[1:]:
            for i, r in enumerate(rows):
                if r[0] == rel:
                    rows[i] = (rel, "CONFLITO", r[2], f"outro PDF já casou com {dest} (renomeie à mão, ex.: _preprint)", "")

    order = {"CASOU": 0, "CASOU (slides)": 1, "REVISAR": 2, "CONFLITO": 3}
    w = max(len(str(r[0])) for r in rows) if rows else 10
    for r in sorted(rows, key=lambda r: (order.get(r[1], 5), str(r[0]))):
        print(f"{r[1]:15} {str(r[0])[:58]:58} {r[2]:>5}  {r[3]}" + (f"\n{'':15} -> static/pdf/{r[4]}" if r[4] else ""))

    cnt = {}
    for r in rows:
        k = r[1].split(" ")[0]
        cnt[k] = cnt.get(k, 0) + 1
    print("\nResumo:", ", ".join(f"{k}={v}" for k, v in sorted(cnt.items())))

    with open(args.csv, "w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(["arquivo", "status", "score", "detalhe", "destino"])
        for r in rows:
            wr.writerow([str(r[0]), r[1], r[2], r[3], r[4]])
    print(f"Relatório CSV: {args.csv}")

    if args.aplicar:
        B.PDF_DIR.mkdir(parents=True, exist_ok=True)
        for dest, src in applied:
            shutil.copy2(src, B.PDF_DIR / dest)
        print(f"{len(applied)} arquivo(s) copiado(s) para static/pdf/. Rode: python3 scripts/bib2json.py")
    elif applied:
        print("(simulação) use --aplicar para copiar.")

    if args.stubs:
        keys, blocks, groups = set(known), [], {}
        for r in rows:
            if r[1] == "NOVO (slides)":
                print(f"  (slides sem registro, sem rascunho) {r[0]} -> crie o registro do trabalho e salve como <chave>_slides.pdf")
            elif r[1].startswith("NOVO"):
                x, srec = r[5], r[6]
                gid = srec["key"] if srec else (norm(x["cands"][0])[:50] if x["cands"] else str(x["path"]))
                groups.setdefault(gid, []).append((r, x, srec))
        for items in groups.values():
            (r, x, srec), extra = items[0], [str(i[1]["path"]) for i in items[1:]]
            blocks.append(make_stub(x, srec, keys, extra)[1])
        if blocks:
            head = ("% Rascunhos gerados por importar_pdfs.py. REVISE autores/venue/sigla, ajuste a chave\n"
                    "% (ANO-SIGLA-Sobrenome), mova para publicacoes.bib e rode importar_pdfs.py de novo.\n\n")
            PENDENTES.write_text(head + "\n\n".join(blocks) + "\n", encoding="utf-8")
            print(f"{len(blocks)} rascunho(s) em {PENDENTES.relative_to(B.ROOT)}")


if __name__ == "__main__":
    main()
