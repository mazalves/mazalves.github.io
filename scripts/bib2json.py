#!/usr/bin/env python3
"""Converte bib/publicacoes.bib em data/publicacoes.json (usado pelo Hugo).

Uso:
    python3 scripts/bib2json.py            # valida e gera o JSON
    python3 scripts/bib2json.py --check    # só valida (usado no GitHub Actions)

Sem dependências externas: só a biblioteca padrão do Python 3.8+.

Convenção de nomes (a chave BibTeX é o nome do arquivo):
    chave:   2019-ARC-Lima
    artigo:  static/pdf/2019-ARC-Lima.pdf
    slides:  static/pdf/2019-ARC-Lima_slides.pdf
    outros:  static/pdf/2019-ARC-Lima_<sufixo>.pdf   (ex.: _en, _pt, _poster)
Basta colocar o PDF na pasta com o nome certo: o link aparece sozinho.
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIB = ROOT / "bib" / "publicacoes.bib"
PDF_DIR = ROOT / "static" / "pdf"
OUT = ROOT / "data" / "publicacoes.json"
CLOUD_OUT = ROOT / "data" / "nuvem.json"

CATEGORIES = {"paper", "abstract", "thesis", "software"}
KEY_RE = re.compile(r"^(\d{4})-([A-Za-z0-9]+(?:-[A-Za-z0-9]+)*)-([A-Z][A-Za-z]+?)([a-z]?)$")


# --------------------------------------------------------------------------
# Leitor de BibTeX (suficiente para este projeto)
# --------------------------------------------------------------------------
def _read_braced(text, i):
    """text[i] == '{'. Devolve (conteúdo, posição após o '}')."""
    depth, start = 0, i
    while i < len(text):
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1:i], i + 1
        i += 1
    raise ValueError("chave '{' sem fechamento")


def _read_value(text, i):
    parts = []
    while True:
        while text[i] in " \t\r\n":
            i += 1
        if text[i] == "{":
            v, i = _read_braced(text, i)
        elif text[i] == '"':
            j = i + 1
            while text[j] != '"' or text[j - 1] == "\\":
                j += 1
            v, i = text[i + 1:j], j + 1
        else:
            m = re.compile(r"[^\s,}#]+").match(text, i)
            v, i = m.group(0), m.end()
        parts.append(v)
        while text[i] in " \t\r\n":
            i += 1
        if text[i] == "#":
            i += 1
            continue
        return "".join(parts), i


def parse_bib(text):
    """Devolve lista de dicts: {'type', 'key', 'fields': {...}}."""
    entries, i = [], 0
    head = re.compile(r"@(\w+)\s*[{(]")
    field = re.compile(r"([A-Za-z_][\w\-:]*)\s*=\s*")
    while True:
        m = head.search(text, i)
        if not m:
            break
        etype, i = m.group(1).lower(), m.end()
        if etype in ("comment", "string", "preamble"):
            _, i = _read_braced(text, m.end() - 1)
            continue
        j = text.index(",", i)
        key, i = text[i:j].strip(), j + 1
        fields = {}
        while True:
            while text[i] in " \t\r\n,":
                i += 1
            if text[i] in "})":
                i += 1
                break
            fm = field.match(text, i)
            if not fm:
                raise ValueError(f"campo ilegível perto de: {text[i:i+60]!r} (entrada {key})")
            i = fm.end()
            value, i = _read_value(text, i)
            fields[fm.group(1).lower()] = value
        entries.append({"type": etype, "key": key, "fields": fields})
    return entries


# --------------------------------------------------------------------------
# LaTeX -> texto
# --------------------------------------------------------------------------
_ACC = {"'": "\u0301", "`": "\u0300", "^": "\u0302", '"': "\u0308", "~": "\u0303",
        "=": "\u0304", ".": "\u0307", "c": "\u0327", "v": "\u030c", "u": "\u0306",
        "H": "\u030b", "r": "\u030a"}
_SPECIAL = {"ss": "ß", "o": "ø", "O": "Ø", "l": "ł", "L": "Ł", "ae": "æ", "AE": "Æ",
            "oe": "œ", "OE": "Œ", "aa": "å", "AA": "Å"}


def latex2text(s):
    s = s.replace("\\&", "&").replace("\\_", "_").replace("\\%", "%") \
         .replace("\\#", "#").replace("\\$", "$")

    def accent(m):                    # \'e  \'{e}  {\'{e}}  \'\i
        base = m.group("b1") or m.group("b2") or "i"
        return unicodedata.normalize("NFC", base + _ACC[m.group("a")])
    s = re.sub(r"\\(?P<a>[`'^\"~=.])\s*(?:\{\\i\}|\\i(?![A-Za-z])|\{(?P<b1>[A-Za-z])\}|(?P<b2>[A-Za-z]))",
               accent, s)
    s = re.sub(r"\\(?P<a>[cvuHr])\s*(?:\{(?P<b>[A-Za-z])\}|\s(?P<b2>[A-Za-z]))",
               lambda m: unicodedata.normalize("NFC", (m.group("b") or m.group("b2")) + _ACC[m.group("a")]), s)
    for cmd, ch in _SPECIAL.items():
        s = re.sub(r"\\" + cmd + r"(?![A-Za-z])\s*", ch, s)
    s = s.replace("{", "").replace("}", "")
    s = re.sub(r"\s+", " ", s).strip()
    return unicodedata.normalize("NFC", s)


def split_authors(raw):
    """'A and B and C' (no nível 0 de chaves) -> ['A', 'B', 'C'], na ordem 'Nome Sobrenome'."""
    out, depth, cur = [], 0, []
    tokens = re.split(r"(\{|\}|\s+)", raw)
    for t in tokens:
        if t == "{":
            depth += 1
        elif t == "}":
            depth -= 1
        if depth == 0 and t.strip() == "and" and cur and "".join(cur).endswith(" "):
            out.append("".join(cur).strip())
            cur = []
        else:
            cur.append(t if t.strip() or t == "" else " ")
    out.append("".join(cur).strip())
    names = []
    for a in out:
        a = latex2text(a)
        if "," in a:                    # 'Sobrenome, Nome' -> 'Nome Sobrenome'
            last, first = [p.strip() for p in a.split(",", 1)]
            a = f"{first} {last}"
        names.append(a)
    return [n for n in names if n]


# --------------------------------------------------------------------------
# Construção do JSON
# --------------------------------------------------------------------------
def venue_of(etype, f):
    if etype == "article":
        return latex2text(f.get("journal", ""))
    if etype in ("inproceedings", "incollection", "conference"):
        return latex2text(f.get("booktitle", ""))
    if etype in ("phdthesis", "mastersthesis"):
        return latex2text(f.get("school", ""))
    return latex2text(f.get("booktitle") or f.get("journal") or f.get("publisher") or f.get("howpublished") or "")


def local_files(key):
    """Arquivos static/pdf/<key>.pdf, <key>_slides.pdf, <key>_<sufixo>.pdf."""
    found = []
    if PDF_DIR.is_dir():
        for p in sorted(PDF_DIR.glob(f"{key}*.pdf")):
            stem = p.stem
            if stem == key:
                found.append(("pdf", "PDF", p.name))
            elif stem.startswith(key + "_"):
                suffix = stem[len(key) + 1:]
                label = "Slides" if suffix == "slides" else suffix.replace("_", " ")
                found.append(("slides" if suffix == "slides" else "pdf", label, p.name))
    return found


def build_links(f, key):
    links = []
    for kind, label, name in local_files(key):
        links.append({"label": label if label != "PDF" else "PDF", "url": f"/pdf/{name}", "kind": kind})
    if f.get("pdfurl"):
        links.append({"label": "PDF", "url": f["pdfurl"], "kind": "pdf"})
    if f.get("doi"):
        links.append({"label": "DOI", "url": "https://doi.org/" + latex2text(f["doi"]), "kind": "doi"})
    url = latex2text(f.get("url", ""))
    if url and not (f.get("doi") and "doi.org/" in url):
        links.append({"label": "Link", "url": url, "kind": "link"})
    if f.get("video"):
        links.append({"label": "Vídeo", "url": latex2text(f["video"]), "kind": "video"})
    order = {"pdf": 0, "slides": 1, "video": 2, "doi": 3, "link": 4}
    links.sort(key=lambda l: order[l["kind"]])
    return links


CUSTOM_FIELDS = {"category", "pdfurl", "video", "dblp", "award", "role"}


def bibtex_text(entry):
    """BibTeX limpo (sem campos internos do site) para o botão 'BibTeX' da página."""
    lines = [f"@{entry['type']}{{{entry['key']},"]
    for k, v in entry["fields"].items():
        if k not in CUSTOM_FIELDS:
            lines.append(f"  {k} = {{{v}}},")
    lines.append("}")
    return "\n".join(lines)


def convert(entry):
    f, key = entry["fields"], entry["key"]
    item = {
        "key": key,
        "type": entry["type"],
        "category": f.get("category", "paper"),
        "title": latex2text(f.get("title", "")),
        "authors": split_authors(f.get("author", "")),
        "year": int(f["year"]) if f.get("year", "").isdigit() else f.get("year", ""),
        "venue": venue_of(entry["type"], f),
        "links": build_links(f, key),
    }
    for opt in ("volume", "number", "pages"):
        if f.get(opt):
            item[opt] = latex2text(f[opt])
    if f.get("type"):
        item["kind"] = latex2text(f["type"])
    if f.get("award"):
        item["award"] = latex2text(f["award"])
    if f.get("role") == "co":
        item["role"] = "co"          # coorientação (teses)
    item["bibtex"] = bibtex_text(entry)
    return item


def validate(entries, items):
    errors, warnings = [], []
    seen = set()
    for e, it in zip(entries, items):
        k, f = e["key"], e["fields"]
        if k in seen:
            errors.append(f"chave duplicada: {k}")
        seen.add(k)
        for req in ("author", "title", "year"):
            if not f.get(req):
                errors.append(f"{k}: falta o campo '{req}'")
        m = KEY_RE.match(k)
        if not m:
            warnings.append(f"{k}: chave fora do padrão ANO-SIGLA-Sobrenome")
        elif f.get("year") and m.group(1) != f["year"]:
            warnings.append(f"{k}: ano da chave ({m.group(1)}) difere do campo year ({f['year']})")
        if "-XXX-" in k:
            warnings.append(f"{k}: sigla 'XXX' pendente — renomeie a chave (e o PDF)")
        if it["category"] not in CATEGORIES:
            errors.append(f"{k}: category='{it['category']}' inválida (use {', '.join(sorted(CATEGORIES))})")
    # PDFs sem entrada
    if PDF_DIR.is_dir():
        for p in sorted(PDF_DIR.glob("*.pdf")):
            if not any(p.stem == k or p.stem.startswith(k + "_") for k in seen):
                warnings.append(f"static/pdf/{p.name}: nenhum registro com essa chave (arquivo órfão)")
    return errors, warnings


# ---------------------------------------------------------------- nuvem de palavras
# Termos canônicos bilíngues: variante (minúscula, sem plural) -> (rótulo EN, rótulo PT).
CLOUD_CANON = {
    "memory": ("memory", "memória"), "memories": ("memory", "memória"), "memória": ("memory", "memória"),
    "memórias": ("memory", "memória"),
    "processing": ("processing", "processamento"), "processamento": ("processing", "processamento"),
    "processor": ("processors", "processadores"), "processadore": ("processors", "processadores"),
    "processadores": ("processors", "processadores"),
    "performance": ("performance", "desempenho"), "desempenho": ("performance", "desempenho"),
    "architecture": ("architecture", "arquitetura"), "arquitetura": ("architecture", "arquitetura"),
    "arquiteturas": ("architecture", "arquitetura"),
    "data": ("data", "dados"), "dados": ("data", "dados"),
    "machine": ("machine learning", "aprendizado de máquina"), "learning": ("machine learning", "aprendizado de máquina"),
    "aprendizagem": ("machine learning", "aprendizado de máquina"),
    "máquina": ("machine learning", "aprendizado de máquina"), "aprendizado": ("machine learning", "aprendizado de máquina"),
    "avaliação": ("evaluation", "avaliação"), "evaluating": ("evaluation", "avaliação"),
    "evaluation": ("evaluation", "avaliação"),
    "simulação": ("simulation", "simulação"), "simulation": ("simulation", "simulação"),
    "simulator": ("simulation", "simulação"), "simulador": ("simulation", "simulação"),
    "instrução": ("instructions", "instruções"), "instruções": ("instructions", "instruções"),
    "instruction": ("instructions", "instruções"),
    "energy": ("energy", "energia"), "energia": ("energy", "energia"),
    "efficient": ("efficiency", "eficiência"), "efficiency": ("efficiency", "eficiência"),
    "eficiente": ("efficiency", "eficiência"), "eficiência": ("efficiency", "eficiência"),
    "parallel": ("parallel", "paralelo"), "paralelo": ("parallel", "paralelo"), "paralela": ("parallel", "paralelo"),
    "thread": ("threads", "threads"), "threads": ("threads", "threads"),
    "application": ("applications", "aplicações"), "aplicações": ("applications", "aplicações"),
    "technique": ("techniques", "técnicas"), "técnicas": ("techniques", "técnicas"),
    "database": ("databases", "bancos de dados"), "databas": ("databases", "bancos de dados"),
    "precipitação": ("precipitation", "precipitação"), "precipitation": ("precipitation", "precipitação"),
    "nuvem": ("cloud", "nuvem"), "cloud": ("cloud", "nuvem"),
    "mapping": ("mapping", "mapeamento"), "mapeamento": ("mapping", "mapeamento"),
    "multicore": ("multi-core", "multi-core"), "multi-core": ("multi-core", "multi-core"),
    "multi-cores": ("multi-core", "multi-core"),
    "processing-in-memory": ("PIM", "PIM"), "pim": ("PIM", "PIM"),
    "system": ("systems", "sistemas"), "sistema": ("systems", "sistemas"), "sistemas": ("systems", "sistemas"),
    "analysis": ("analysis", "análise"), "análise": ("analysis", "análise"),
    "optimize": ("optimization", "otimização"), "optimization": ("optimization", "otimização"),
    "otimização": ("optimization", "otimização"),
    "real-time": ("real-time", "tempo real"), "vector": ("vector", "vetorial"), "vetorial": ("vector", "vetorial"),
    "mechanism": ("mechanisms", "mecanismos"), "mecanismo": ("mechanisms", "mecanismos"),
    "access": ("memory access", "acesso à memória"), "acesso": ("memory access", "acesso à memória"),
    "caches": ("cache", "cache"), "cache": ("cache", "cache"),
}
CLOUD_STOP = set("""a an the of for and in on to with by via from under through at as or its into over using use used
based approach toward towards new case study line table fast shared extensions annotated deolhonoscorais design de da do das dos e em para com por uma um uns umas no na nos nas ao aos
através utilizando proposta sobre entre sua seu como que se ou v version versão 1 2 3 vs""".split())
TOKEN_RE = re.compile(r"[A-Za-zÀ-ÿ0-9]+(?:-[A-Za-zÀ-ÿ0-9]+)*")


def build_cloud(items, minimo=3, maximo=50):
    """Conta termos dos títulos (1 voto por título) e devolve a lista já arranjada do centro p/ fora."""
    from collections import Counter
    votos, variantes, acronimos = Counter(), {}, set()
    for it in items:
        vistos = set()
        for tok in TOKEN_RE.findall(it["title"]):
            low = tok.lower()
            if low in CLOUD_STOP or low.isdigit() or len(low) < 2:
                continue
            if len(tok) >= 2 and tok.isupper() and tok.isalpha():
                acronimos.add(low)
            canon = CLOUD_CANON.get(low) or CLOUD_CANON.get(low.rstrip("s"))
            if canon is None:
                chave = low[:-1] if low.endswith("s") and len(low) > 4 and not low.endswith("ss") else low
                canon = (tok if low in acronimos else low, tok if low in acronimos else low)
                chave_c = chave
            else:
                chave_c = canon[0]
            if chave_c in vistos:
                continue
            vistos.add(chave_c)
            votos[chave_c] += 1
            variantes.setdefault(chave_c, canon)
            variantes.setdefault(("q", chave_c), Counter())[low] += 1
    termos = []
    for k, n in votos.items():
        if n < minimo:
            continue
        en, pt = variantes[k]
        if k in acronimos or en.isupper():
            en = pt = en.upper()
        q = "|".join(w for w, _ in variantes[("q", k)].most_common(4))   # variantes (OR) p/ a busca
        termos.append({"en": en, "pt": pt, "n": n, "q": q})
    termos.sort(key=lambda t: (-t["n"], t["en"]))
    termos = termos[:maximo]
    # arranjo centro->fora: maiores no meio, alternando esquerda/direita
    esq, dir_ = [], []
    for i, t in enumerate(termos):
        (esq if i % 2 else dir_).append(t)
    return list(reversed(esq)) + dir_



def main():
    check_only = "--check" in sys.argv
    entries = parse_bib(BIB.read_text(encoding="utf-8"))
    items = [convert(e) for e in entries]
    errors, warnings = validate(entries, items)

    for w in warnings:
        print("aviso:", w)
    for e in errors:
        print("ERRO: ", e)
    if errors:
        sys.exit(1)

    # agrupa por ano (mais recente primeiro), mantendo a ordem do .bib dentro do ano
    by_year = {}
    for it in items:
        by_year.setdefault(it["year"], []).append(it)
    years = [{"year": y, "items": by_year[y]} for y in sorted(by_year, key=lambda v: -int(v))]
    data = {"count": len(items), "years": years}

    n_pdf = sum(1 for it in items if any(l["kind"] == "pdf" for l in it["links"]))
    print(f"{len(items)} registros, {len(years)} anos, {n_pdf} com PDF local.")
    if check_only:
        print("OK (--check: nada foi escrito)")
        return
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("gerado:", OUT.relative_to(ROOT))
    nuvem = build_cloud(items)
    CLOUD_OUT.write_text(json.dumps({"termos": nuvem}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"gerado: {CLOUD_OUT.relative_to(ROOT)} ({len(nuvem)} termos)")


if __name__ == "__main__":
    main()
