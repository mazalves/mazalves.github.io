#!/usr/bin/env python3
"""Baixa do Acervo Digital da UFPR (https://acervodigital.ufpr.br) os PDFs de teses,
dissertações e monografias que estão em bib/publicacoes.bib mas ainda não têm PDF local.

STATUS: escrito sem acesso à rede do Acervo (o ambiente de desenvolvimento não alcança o site).
Rode primeiro com --dry-run no seu computador e confira a saída. Se o layout do DSpace
mudar, ajuste a função links_pdf().

Uso:
  python3 scripts/baixar_acervo.py --dry-run          # só lista o que faria
  python3 scripts/baixar_acervo.py                    # baixa e valida
  python3 scripts/baixar_acervo.py --only 2022-UFPR-Sokulski
  python3 scripts/baixar_acervo.py --buscar           # sem handle no .bib: busca pelo título e lista candidatos
  python3 scripts/baixar_acervo.py --orientados "Zanata Alves"   # lista itens do Acervo em que você é
                                                      # orientador e que NÃO estão no .bib (acha esquecidos)
  python3 scripts/baixar_acervo.py --handle 70843     # mostra os metadados do item e um rascunho de entrada .bib

Como funciona
  1. Para cada @mastersthesis/@phdthesis sem static/pdf/<chave>.pdf e com url do tipo
     hdl.handle.net/1884/N (ou acervodigital.ufpr.br/handle/1884/N), abre a página do item.
  2. Procura o link do bitstream .pdf (DSpace XMLUI: /bitstream/handle/1884/N/arquivo.pdf).
  3. Baixa, confere se começa com %PDF e se a 1ª página (pdftotext) contém palavras do título
     do .bib. Só então grava como static/pdf/<chave>.pdf. Se não bater, salva em
     static/pdf/_conferir/ e avisa — evita repetir o problema de baixar a versão errada.
  4. Depois rode: python3 scripts/bib2json.py
"""
import argparse, difflib, re, ssl, subprocess, sys, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from bib2json import parse_bib, latex2text   # reaproveita o parser do projeto

BASE = "https://acervodigital.ufpr.br"
UA = {"User-Agent": "Mozilla/5.0 (site pessoal; script de uso pessoal)"}
HANDLE_RE = re.compile(r"(?:handle(?:\.net)?/|handle/)(1884/\d+)")


INSEGURO = False     # --inseguro: não verifica o certificado (só para hosts *.ufpr.br)
AVISO_SSL = """
ERRO de certificado SSL ao abrir o Acervo ({host}).
O servidor da UFPR envia a cadeia de certificados incompleta (navegadores completam, o Python não).
Opções:
  1) rode de novo com --inseguro  (pula a verificação do certificado SOMENTE para hosts *.ufpr.br;
     o script só lê páginas públicas e confere que o arquivo baixado é PDF e tem o título esperado);
  2) ou instale os certificados: no Ubuntu  sudo apt install ca-certificates && sudo update-ca-certificates
"""


def http(url, binary=False):
    req = urllib.request.Request(url, headers=UA)
    host = urllib.parse.urlparse(url).hostname or ""
    ctx = None
    if INSEGURO and host.endswith("ufpr.br"):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    try:
        with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
            data = r.read()
    except urllib.error.URLError as ex:
        if isinstance(ex.reason, ssl.SSLCertVerificationError):
            sys.exit(AVISO_SSL.format(host=host))
        raise
    return data if binary else data.decode("utf-8", "replace")


def links_pdf(html, handle):
    """Links de bitstream PDF da página do item, o primeiro (sequence=1) antes."""
    found = re.findall(r'href="([^"]*bitstream[^"]*\.pdf[^"]*)"', html, flags=re.I)
    out = []
    for h in found:
        u = urllib.parse.urljoin(BASE + "/handle/" + handle, h.replace("&amp;", "&"))
        if u not in out:
            out.append(u)
    return out


def primeira_pagina(pdf_path):
    try:
        return subprocess.run(["pdftotext", "-f", "1", "-l", "2", str(pdf_path), "-"],
                              capture_output=True, text=True, timeout=60).stdout
    except Exception:
        return ""


def confere_titulo(texto, titulo):
    """Fração das palavras (>3 letras) do título presentes nas 2 primeiras páginas."""
    pal = [w for w in re.findall(r"\w+", titulo.lower()) if len(w) > 3]
    if not pal:
        return 1.0
    t = texto.lower()
    return sum(w in t for w in pal) / len(pal)


def buscar(titulo):
    q = urllib.parse.quote(titulo)
    html = http(f"{BASE}/discover?query={q}")
    res = re.findall(r'href="(/handle/1884/\d+)"[^>]*>([^<]{10,200})<', html)
    return [(BASE + h, t.strip(), difflib.SequenceMatcher(None, t.lower(), titulo.lower()).ratio())
            for h, t in dict(res).items()]


def metadados(handle):
    """Campos Dublin Core da página ?show=full (DSpace XMLUI)."""
    html = http(f"{BASE}/xmlui/handle/1884/{handle}?show=full")
    campos = {}
    for k, v in re.findall(r'<td[^>]*label-cell[^>]*>\s*([\w.]+)\s*</td>\s*<td[^>]*>(.*?)</td>', html, flags=re.S):
        campos.setdefault(k, []).append(re.sub(r"<[^>]+>|\s+", " ", v).strip())
    return campos


def rascunho_bib(handle, c):
    def g(*ks):
        for k in ks:
            if c.get(k):
                return c[k][0]
        return ""
    autor = g("dc.contributor.author", "dc.creator")
    if "," in autor:                       # "Sobrenome, Nome" -> "Nome Sobrenome"
        sob, nome = [x.strip() for x in autor.split(",", 1)]
        autor = f"{nome} {sob}".title()
    ano = (g("dc.date.issued", "dc.date.available") or "")[:4]
    sob = autor.split()[-1] if autor else "XXX"
    tipo = g("dc.type").lower()
    nivel = "Especialização" if "especializa" in tipo or "lato" in tipo else (
        "Trabalho de Conclusão de Curso" if "gradua" in tipo or "tcc" in tipo else "")
    ent = "phdthesis" if "doutorado" in tipo else "mastersthesis"
    return (f"@{ent}{{{ano}-UFPR-{sob},\n  author       = {{{autor}}},\n  title        = {{{g('dc.title')}}},\n"
            f"  school       = {{UFPR}},\n" + (f"  type         = {{{nivel}}},\n" if nivel else "") +
            f"  year         = {{{ano}}},\n  url          = {{https://hdl.handle.net/1884/{handle}}},\n  category     = {{thesis}}\n}}")


def orientados(nome, entries):
    """Busca o nome do orientador no Acervo e lista itens cujo handle não está no .bib."""
    conhecidos = {m.group(1) for e in entries for m in [HANDLE_RE.search(e["fields"].get("url", ""))] if m}
    achados, pag = {}, 0
    while pag < 20:
        url = f"{BASE}/xmlui/discover?query={urllib.parse.quote(chr(34) + nome + chr(34))}&rpp=100&page={pag + 1}"
        html = http(url)
        novos = dict(re.findall(r'href="[^"]*/handle/(1884/\d+)"[^>]*>([^<]{8,300})<', html))
        if not novos or all(h in achados for h in novos):
            break
        achados.update(novos)
        pag += 1
        time.sleep(2)
    faltam = {h: t for h, t in achados.items() if h not in conhecidos}
    print(f"{len(achados)} itens encontrados; {len(faltam)} fora do .bib:")
    for h, t in faltam.items():
        print(f"  {h}  {t.strip()}")
    print("\nConfira cada um (a busca por nome pega também citações/coautorias) e rode "
          "--handle N para gerar o rascunho.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only")
    ap.add_argument("--buscar", action="store_true", help="busca por título quando não há handle")
    ap.add_argument("--inseguro", action="store_true", help="não verifica o certificado SSL de *.ufpr.br")
    ap.add_argument("--orientados", metavar="NOME")
    ap.add_argument("--handle", metavar="N")
    ap.add_argument("--min", type=float, default=0.6, help="mínimo de palavras do título na 1ª página")
    a = ap.parse_args()

    global INSEGURO
    INSEGURO = a.inseguro
    entries = parse_bib((ROOT / "bib/publicacoes.bib").read_text(encoding="utf-8"))
    if a.handle:
        print(rascunho_bib(a.handle, metadados(a.handle)))
        return
    if a.orientados:
        orientados(a.orientados, entries)
        return
    pdfdir = ROOT / "static/pdf"
    ok = falha = 0
    for e in entries:
        k, f = e["key"], e["fields"]
        if e["type"] not in ("mastersthesis", "phdthesis"):
            continue
        if a.only and a.only != k:
            continue
        if (pdfdir / f"{k}.pdf").exists():
            continue
        titulo = latex2text(f.get("title", ""))
        m = HANDLE_RE.search(f.get("url", ""))
        if not m:
            print(f"- {k}: sem handle no .bib")
            if a.buscar:
                try:
                    for u, t, s in sorted(buscar(titulo), key=lambda x: -x[2])[:3]:
                        print(f"    candidato {s:.2f}: {t}\n      {u}")
                except Exception as ex:
                    print("    busca falhou:", ex)
            continue
        handle = m.group(1)
        print(f"- {k}: {handle}")
        try:
            pdfs = links_pdf(http(f"{BASE}/handle/{handle}"), handle)
        except Exception as ex:
            print("    não foi possível abrir a página:", ex)
            falha += 1
            continue
        if not pdfs:
            print("    nenhum PDF público no item (acesso restrito ou layout mudou)")
            falha += 1
            continue
        print("    PDF:", pdfs[0])
        if a.dry_run:
            continue
        try:
            data = http(pdfs[0], binary=True)
        except Exception as ex:
            print("    download falhou:", ex)
            falha += 1
            continue
        if not data.startswith(b"%PDF"):
            print("    o arquivo baixado não é PDF")
            falha += 1
            continue
        tmp = pdfdir / "_conferir" / f"{k}.pdf"
        tmp.parent.mkdir(exist_ok=True)
        tmp.write_bytes(data)
        score = confere_titulo(primeira_pagina(tmp), titulo)
        if score >= a.min:
            tmp.rename(pdfdir / f"{k}.pdf")
            print(f"    OK (título confere: {score:.0%})")
            ok += 1
        else:
            print(f"    CONFERIR: título bate só {score:.0%}; ficou em static/pdf/_conferir/{k}.pdf")
            falha += 1
        time.sleep(2)   # gentileza com o servidor
    print(f"\n{ok} baixados, {falha} com pendência. Rode: python3 scripts/bib2json.py")


if __name__ == "__main__":
    main()
