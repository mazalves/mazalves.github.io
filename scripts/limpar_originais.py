#!/usr/bin/env python3
"""Limpa a pasta de PDFs ORIGINAIS (a que você importou para o site), sem tocar no site.

Regra: um arquivo da pasta de originais só é candidato a remoção se existir em static/pdf/ um
arquivo com conteúdo BYTE A BYTE idêntico (MD5 + tamanho) e esse arquivo estiver em uso
(linkado em data/publicacoes.json). Tudo o mais permanece: PDFs ainda não importados,
versões diferentes (rascunhos, preprints, versões antigas), arquivos que não são PDF.

Uso:
  python3 scripts/limpar_originais.py PASTA                 # relatório; não altera nada
  python3 scripts/limpar_originais.py PASTA --mover         # move os redundantes p/ PASTA/_redundantes_para_apagar
  python3 scripts/limpar_originais.py PASTA --apagar        # apaga de verdade (pede para digitar APAGAR)
  python3 scripts/limpar_originais.py PASTA --csv rel.csv   # relatório em planilha

Recomendado: rode sem opção, confira, use --mover, olhe a pasta, e só então apague a pasta
_redundantes_para_apagar à mão. Faça backup (ou confirme que o site está no git) antes.
Para o site existir a salvo, o script também confere que o arquivo do site abre como PDF (%PDF).
"""
import argparse, csv, hashlib, json, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE_PDF = ROOT / "static" / "pdf"
JSON = ROOT / "data" / "publicacoes.json"
QUARENTENA = "_redundantes_para_apagar"


def md5(p, bloco=1 << 20):
    h = hashlib.md5()
    with open(p, "rb") as f:
        while chunk := f.read(bloco):
            h.update(chunk)
    return h.hexdigest()


def pdfs_em_uso():
    """Nomes de arquivo em static/pdf referenciados pelo site (links locais do JSON)."""
    dados = json.loads(JSON.read_text(encoding="utf-8"))
    return {Path(l["url"]).name for ano in dados["years"] for it in ano["items"]
            for l in it["links"] if l["url"].startswith("/pdf/")}


def eh_pdf(p):
    with open(p, "rb") as f:
        return f.read(5) == b"%PDF-"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pasta")
    ap.add_argument("--mover", action="store_true")
    ap.add_argument("--apagar", action="store_true")
    ap.add_argument("--csv")
    a = ap.parse_args()
    pasta = Path(a.pasta).expanduser().resolve()
    if not pasta.is_dir():
        sys.exit(f"pasta não encontrada: {pasta}")
    if pasta == SITE_PDF.resolve() or SITE_PDF.resolve() in pasta.parents or ROOT in (pasta, *pasta.parents):
        sys.exit("A pasta de originais não pode estar dentro do projeto do site (evita apagar o site por engano).")
    if not SITE_PDF.is_dir() or not JSON.exists():
        sys.exit("Rode a partir do projeto do site (precisa de static/pdf e data/publicacoes.json).")

    uso = pdfs_em_uso()
    site = {}                                    # (tamanho, md5) -> nome no site
    for p in SITE_PDF.glob("*.pdf"):
        if p.name in uso and eh_pdf(p):
            site[(p.stat().st_size, md5(p))] = p.name

    linhas, manter, redundantes = [], [], []
    for p in sorted(pasta.rglob("*")):
        if not p.is_file() or QUARENTENA in p.parts:
            continue
        rel = p.relative_to(pasta)
        if p.suffix.lower() != ".pdf":
            linhas.append((str(rel), "MANTER", "não é PDF"))
            manter.append(p)
            continue
        chave = (p.stat().st_size, md5(p))
        if chave in site:
            linhas.append((str(rel), "REDUNDANTE", f"idêntico a static/pdf/{site[chave]}"))
            redundantes.append(p)
        else:
            linhas.append((str(rel), "MANTER", "não está no site (ou difere dos arquivos do site)"))
            manter.append(p)

    for rel, st, det in linhas:
        print(f"{st:10} {rel}  —  {det}")
    tam = sum(p.stat().st_size for p in redundantes) / 1e6
    print(f"\n{len(redundantes)} redundantes ({tam:.0f} MB) · {len(manter)} permanecem (inclui itens não importados).")

    if a.csv:
        with open(a.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["arquivo", "decisao", "detalhe"])
            w.writerows(linhas)
        print("relatório:", a.csv)

    if a.mover:
        dest = pasta / QUARENTENA
        for p in redundantes:
            alvo = dest / p.relative_to(pasta)
            alvo.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(p), str(alvo))
        print(f"movidos para {dest}. Confira e apague essa pasta manualmente.")
    elif a.apagar:
        if input(f"Apagar {len(redundantes)} arquivos de {pasta}? Digite APAGAR: ") != "APAGAR":
            sys.exit("cancelado.")
        for p in redundantes:
            p.unlink()
        print("apagados.")
    else:
        print("(relatório apenas — nada foi alterado)")


if __name__ == "__main__":
    main()
