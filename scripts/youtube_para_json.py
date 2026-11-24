#!/usr/bin/env python3
"""Atualiza data/videos.json a partir do YouTube (canal do HiPES). Sem pacotes extras e sem chave de API.

STATUS: escrito sem acesso ao YouTube (o ambiente de desenvolvimento não alcança o site);
rode no seu computador e confira o resultado. O formato do feed Atom é estável, mas teste.

Uso:
  python3 scripts/youtube_para_json.py --titulos
        Preenche o título real (via oEmbed) dos vídeos marcados "titulo_auto": true e, para
        playlists sem "id", pega o 1º vídeo (usado só na miniatura).
  python3 scripts/youtube_para_json.py --novos [--canal @HiPESLab]
        Lê o feed do canal (os ~15 vídeos mais recentes) e acrescenta, na seção "novos",
        os que ainda não estão em data/videos.json nem no campo video= do .bib.
  python3 scripts/youtube_para_json.py --playlist PLxxxxxxxx
        Idem, para uma playlist específica (útil para trazer playlists inteiras).
  Acrescente --dry-run para só mostrar o que seria feito.

Depois de rodar: abra data/videos.json, mova cada vídeo de "novos" para a seção certa
("secao") e, se quiser, ajuste título e descrição. Os vídeos do campo video= do .bib já
aparecem sozinhos em Defesas/Apresentações.
"""
import argparse, json, re, sys, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VIDEOS = ROOT / "data" / "videos.json"
BIB = ROOT / "bib" / "publicacoes.bib"
UA = {"User-Agent": "Mozilla/5.0 (site pessoal; uso pessoal)"}
NS = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015",
      "m": "http://search.yahoo.com/mrss/"}
ID_RE = re.compile(r"(?:youtu\.be/|[?&]v=)([A-Za-z0-9_-]{11})")


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def canal_id(handle):
    handle = handle if handle.startswith("@") else "@" + handle
    html = get(f"https://www.youtube.com/{handle}")
    m = re.search(r'"channelId":"(UC[\w-]{22})"', html) or re.search(r'channel/(UC[\w-]{22})', html)
    if not m:
        sys.exit("não consegui descobrir o channel_id; use --playlist ou informe o feed manualmente")
    return m.group(1)


def feed(url):
    root = ET.fromstring(get(url))
    for e in root.findall("a:entry", NS):
        yield {"id": e.findtext("yt:videoId", namespaces=NS),
               "titulo": (e.findtext("a:title", namespaces=NS) or "").strip(),
               "ano": int((e.findtext("a:published", namespaces=NS) or "0")[:4])}


def conhecidos(dados):
    ids = {v["id"] for v in dados["videos"]}
    if BIB.exists():
        ids |= set(ID_RE.findall(BIB.read_text(encoding="utf-8")))
    return ids


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--titulos", action="store_true")
    ap.add_argument("--novos", action="store_true")
    ap.add_argument("--playlist")
    ap.add_argument("--canal")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if not (a.titulos or a.novos or a.playlist):
        sys.exit(__doc__)
    dados = json.loads(VIDEOS.read_text(encoding="utf-8"))

    if a.titulos:
        for v in dados["videos"]:
            if not v.get("titulo_auto"):
                continue
            try:
                j = json.loads(get("https://www.youtube.com/oembed?format=json&url=" +
                                   urllib.parse.quote(f"https://www.youtube.com/watch?v={v['id']}")))
            except Exception as ex:
                print(f"- {v['id']}: falhou ({ex})")
                continue
            print(f"- {v['id']}: {j['title']}")
            if not a.dry_run:
                v["titulo"] = v["titulo_en"] = j["title"]
                v.pop("titulo_auto")

    if a.titulos:                                   # playlists sem id: usa o 1º vídeo da playlist (p/ miniatura)
        for v in dados["videos"]:
            if not v.get("id") and v.get("playlist"):
                try:
                    primeiro = next(iter(feed(f"https://www.youtube.com/feeds/videos.xml?playlist_id={v['playlist']}")), None)
                except Exception as ex:
                    print(f"- playlist {v['playlist']}: falhou ({ex})")
                    continue
                if primeiro:
                    print(f"- playlist {v['playlist']}: miniatura do vídeo {primeiro['id']}")
                    if not a.dry_run:
                        v["id"] = primeiro["id"]

    novos = []
    if a.novos or a.playlist:
        if a.playlist:
            url = f"https://www.youtube.com/feeds/videos.xml?playlist_id={a.playlist}"
        else:
            url = "https://www.youtube.com/feeds/videos.xml?channel_id=" + canal_id(a.canal or dados.get("canal", "@HiPESLab").rsplit("/", 1)[-1])
        ja = conhecidos(dados)
        for v in feed(url):
            if v["id"] and v["id"] not in ja:
                novos.append(v)
                print(f"+ {v['ano']}  {v['id']}  {v['titulo']}")
        if not novos:
            print("nenhum vídeo novo.")
        elif not a.dry_run:
            for v in novos:
                dados["videos"].append({"id": v["id"], "secao": "novos", "titulo": v["titulo"],
                                        "titulo_en": v["titulo"], "ano": v["ano"]})

    if not a.dry_run:
        VIDEOS.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
        print("data/videos.json atualizado.")


if __name__ == "__main__":
    main()
