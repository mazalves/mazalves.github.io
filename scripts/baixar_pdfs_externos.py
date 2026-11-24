#!/usr/bin/env python3
"""Baixa os PDFs apontados por `pdfurl` no .bib e grava em static/pdf/<chave>.pdf.

Para cada entrada com `pdfurl = {https://...}` que ainda não tem static/pdf/<chave>.pdf:
  1. baixa o arquivo (segue redirecionamentos, com User-Agent de navegador);
  2. confere que é mesmo um PDF (começa com %PDF) e não uma página de erro/login;
  3. grava com o nome certo (a chave BibTeX).
Depois rode `python3 scripts/bib2json.py`: o link passa a apontar para a cópia local e o `pdfurl`
fica só como reserva (o conversor ignora o pdfurl quando existe o arquivo local).

Uso:
  python3 scripts/baixar_pdfs_externos.py --dry-run          # só lista o que baixaria
  python3 scripts/baixar_pdfs_externos.py                    # baixa tudo que falta
  python3 scripts/baixar_pdfs_externos.py --only 2026-JPM-Brito
  python3 scripts/baixar_pdfs_externos.py --forcar           # rebaixa mesmo se já existir (sobrescreve)

Atenção a direitos: baixar e hospedar PDF de editora (IEEE, Elsevier, ACM, Springer) pode violar a
política de autoarquivamento. Use para anais abertos, preprints e trabalhos seus de acesso livre.
Se o site pedir login ou bloquear robôs, o script avisa e você baixa pelo navegador, salvando como
static/pdf/<chave>.pdf.
"""
import argparse, sys, time, urllib.error, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from bib2json import parse_bib          # reaproveita o parser do projeto

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
      "Accept": "application/pdf,*/*"}
LIMITE_MB = 90          # GitHub recusa arquivos > 100 MB


def baixar(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=90) as r:
        dados = r.read(LIMITE_MB * 1024 * 1024 + 1)
        tipo = r.headers.get("Content-Type", "")
    return dados, tipo


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only")
    ap.add_argument("--forcar", action="store_true")
    ap.add_argument("--bib", default=str(ROOT / "bib" / "publicacoes.bib"))
    ap.add_argument("--saida", default=str(ROOT / "static" / "pdf"))
    a = ap.parse_args()

    saida = Path(a.saida)
    saida.mkdir(parents=True, exist_ok=True)
    entradas = parse_bib(Path(a.bib).read_text(encoding="utf-8"))
    alvos = [(e["key"], e["fields"]["pdfurl"]) for e in entradas
             if e["fields"].get("pdfurl") and (not a.only or a.only == e["key"])]
    if not alvos:
        print("nenhuma entrada com pdfurl.")
        return

    ok = pulados = falhas = 0
    for chave, url in alvos:
        destino = saida / f"{chave}.pdf"
        if destino.exists() and not a.forcar:
            print(f"= {chave}: já existe ({destino.stat().st_size / 1e6:.1f} MB)")
            pulados += 1
            continue
        print(f"- {chave}: {url}")
        if a.dry_run:
            continue
        try:
            dados, tipo = baixar(url)
        except (urllib.error.URLError, TimeoutError, OSError) as ex:
            print(f"    FALHOU: {ex}\n    -> baixe pelo navegador e salve como {destino.relative_to(ROOT) if ROOT in destino.parents else destino}")
            falhas += 1
            continue
        if len(dados) > LIMITE_MB * 1024 * 1024:
            print(f"    arquivo maior que {LIMITE_MB} MB; não gravado (limite do GitHub é 100 MB).")
            falhas += 1
            continue
        if not dados.startswith(b"%PDF"):
            print(f"    não é PDF (Content-Type: {tipo or '?'}); provavelmente página de login/erro. Baixe pelo navegador.")
            falhas += 1
            continue
        destino.write_bytes(dados)
        print(f"    OK {len(dados) / 1e6:.2f} MB -> {destino.name}")
        ok += 1
        time.sleep(1.5)          # gentileza com o servidor

    print(f"\n{ok} baixados, {pulados} já existiam, {falhas} com pendência.")
    if ok:
        print("Agora rode: python3 scripts/bib2json.py")


if __name__ == "__main__":
    main()
