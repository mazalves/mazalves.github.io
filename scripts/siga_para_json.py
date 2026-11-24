#!/usr/bin/env python3
"""Converte as listagens do SIGA (HTML salvo do navegador) em data/ensino.json.

Uso:  python3 scripts/siga_para_json.py SIGA_BCC.html SIGA_ibm.html SIGAPPGINF.html

PRIVACIDADE: os HTML do SIGA contêm nomes e notas de alunos. Este script lê SÓ
disciplina, código, semestre, carga horária e ementa — nenhum dado de aluno é
gravado. Não coloque os HTML originais no repositório (veja .gitignore).
O nível (graduação/pós) é deduzido do nome do arquivo: 'PPG' ou 'pos' => pós.
"""
import collections, html, json, re, sys
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "ensino.json"

# Códigos antigos -> código atual (currículos novos renumeraram as disciplinas).
# Edite aqui se aparecer uma disciplina duplicada na página Ensino.
CODIGO_ATUAL = {"CI316": "CI1316", "CI212": "CI1212", "CI068": "CI1068", "CI210": "CI1210",
                "CI086": "CI1086", "CI243": "CI1243", "CI702": "INFO7005", "CI825": "INFO7022",
                "CI826": "INFO7030", "CI744": "INFO7032", "CI745": "INFO7033", "CI728": "INFO7044"}
MINUSCULAS = {"De", "Da", "Do", "Das", "Dos", "E", "Em", "Ii", "I"}


def bonito(nome):
    return " ".join(w.upper() if w in ("Ii",) else (w.lower() if w in MINUSCULAS - {"I"} and i else w)
                    for i, w in enumerate(nome.title().split()))


def linhas(path):
    s = Path(path).read_bytes().decode("utf-8", "replace")
    if "�" in s:                       # arquivos do SIGA costumam vir em latin-1
        s = Path(path).read_bytes().decode("latin-1")
    s = re.sub(r"<script.*?</script>|<style.*?</style>", "", s, flags=re.S)
    s = re.sub(r"</(tr|p|div|h\d|li|td|th)>", "\n", s)
    s = html.unescape(re.sub(r"<[^>]+>", "", s))
    return [re.sub(r"\s+", " ", l).strip() for l in s.split("\n") if l.strip()]


def graduacao(path, curso):
    sem, rows = None, []
    for l in linhas(path):
        m = re.match(r"(\d{4}) - (\d)° Semestre", l)
        if m:
            sem = (int(m[1]), int(m[2]))
            continue
        m = re.match(r"(.+?) - ([A-Z0-9]+) - (CI\d+) - .*?Início: (\S+) - Fim: (\S+)", l)
        if m and sem:
            rows.append({"ano": sem[0], "sem": sem[1], "codigo": m[3], "nome": bonito(m[1]),
                         "turma": m[2], "curso": curso, "nivel": "graduacao"})
    return rows


def pos(path, curso):
    L, rows, i = linhas(path), [], 0
    while i < len(L) - 6:
        # ano, código, nome, código, 'N° Semestre', carga, nível
        if (re.fullmatch(r"\d{4}", L[i]) and re.fullmatch(r"[A-Z]+\d+", L[i + 1])
                and L[i + 3] == L[i + 1] and re.fullmatch(r"\d° Semestre", L[i + 4])):
            r = {"ano": int(L[i]), "sem": int(L[i + 4][0]), "codigo": L[i + 1],
                 "nome": bonito(L[i + 2]), "ch": L[i + 5], "curso": curso, "nivel": "pos"}
            j = i + 7
            while j < len(L) and not re.fullmatch(r"\d{4}", L[j]) and j < i + 40:
                if L[j] == "Ementa" and j + 1 < len(L):
                    r["ementa"] = L[j + 1]
                    break
                j += 1
            rows.append(r)
            i += 5
        else:
            i += 1
    return rows


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    rows = []
    for f in sys.argv[1:]:
        n = Path(f).name.lower()
        if "ppg" in n or "pos" in n:
            rows += pos(f, "PPGINF")
        else:
            rows += graduacao(f, "IBM" if "ibm" in n else "BCC")
    disc = collections.OrderedDict()
    for r in rows:
        r["codigo_antigo"] = r["codigo"]
        r["codigo"] = CODIGO_ATUAL.get(r["codigo"], r["codigo"])
    for r in sorted(rows, key=lambda r: (r["nivel"], r["curso"], r["codigo"], -r["ano"], -r["sem"])):
        d = disc.setdefault((r["nivel"], r["curso"], r["codigo"]), {
            "nivel": r["nivel"], "curso": r["curso"], "codigo": r["codigo"], "nome": r["nome"],
            "periodos": set(), "ementa": r.get("ementa", "")})
        d["periodos"].add(f"{r['ano']}/{r['sem']}")
        if r.get("ementa") and not d["ementa"]:
            d["ementa"] = r["ementa"]
    out = []
    for d in disc.values():
        d["periodos"] = sorted(d["periodos"], reverse=True)
        d["ultimo"] = d["periodos"][0]
        out.append(d)
    out.sort(key=lambda d: (d["nivel"], d["curso"], d["nome"]))
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"disciplinas": out}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(rows)} turmas -> {len(out)} disciplinas em {OUT}")


if __name__ == "__main__":
    main()
