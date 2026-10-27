#!/usr/bin/env python3
"""Merge several XMLTV EPGs into one, keeping only channels used by the playlists.

Usage: merge_epg.py [--offline] [--refresh-ids] [--private DIR] [--keep-dummy] [-o merged.xml.gz]
  --refresh-ids regenerate channel_ids.txt from the playlists (they hold credentials, so never commit them)
  --private DIR folder with the git-ignored playlists.txt and playlists/ (default: current folder)
  --offline     read epgs/*.gz and playlists/*.m3u instead of downloading
  --keep-dummy  also keep "dummy-*" channels (placeholder guides whose only title is the channel name)

Without --refresh-ids the playlists are not touched: channel ids come from channel_ids.txt.
"""
import argparse
import gzip
import io
import os
import re
import urllib.request
import xml.etree.ElementTree as ET

# Earlier sources win when the same channel id appears more than once.
EPGS = [
    ("https://github.com/ferteque/Curated-M3U-Repository/raw/refs/heads/main/epg6.xml.gz", "epgs/ganjarelease.gz"),
    ("https://github.com/ferteque/Curated-M3U-Repository/raw/refs/heads/main/epg1.xml.gz", "epgs/ferteque.gz"),
    ("https://github.com/ferteque/Curated-M3U-Repository/raw/refs/heads/main/epg42.xml.gz", "epgs/koalamanx.gz"),
]
# Playlist URLs live in the git-ignored playlists.txt (one per line): the playlists hold credentials.
def playlist_sources(folder):
    with open(os.path.join(folder, "playlists.txt"), encoding="utf8") as f:
        urls = [line.strip() for line in f if line.strip()]
    return [(u, os.path.join(folder, f"playlists/pl{i}.m3u")) for i, u in enumerate(urls, 1)]


IDS_FILE = "channel_ids.txt"


def fetch(url, local, offline):
    if offline:
        return open(local, "rb").read()
    with urllib.request.urlopen(url, timeout=300) as r:
        return r.read()


def gunzip_if_needed(data):
    return gzip.decompress(data) if data[:2] == b"\x1f\x8b" else data


def playlist_ids(offline, folder):
    ids = set()
    for url, local in playlist_sources(folder):
        text = fetch(url, local, offline).decode("utf8", "replace")
        ids.update(m.group(1) for m in re.finditer(r'^#EXTINF[^\n]*?tvg-id="([^"]*)"', text, re.M | re.I))
    return {i for i in ids if i}


def load_wanted(args):
    if args.refresh_ids:
        ids = playlist_ids(args.offline, args.private)
        with open(IDS_FILE, "w", encoding="utf8") as f:
            f.write("\n".join(sorted(ids)) + "\n")
        print(f"wrote {IDS_FILE}: {len(ids)} ids")
    with open(IDS_FILE, encoding="utf8") as f:
        ids = {line.strip() for line in f if line.strip()}
    return {i for i in ids if args.keep_dummy or not i.startswith("dummy")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--refresh-ids", action="store_true")
    ap.add_argument("--private", default=".")
    ap.add_argument("--keep-dummy", action="store_true")
    ap.add_argument("-o", "--output", default="merged.xml.gz")
    args = ap.parse_args()

    wanted = load_wanted(args)
    root = ET.Element("tv", {"generator-info-name": "merge_epg"})
    channels, programmes = [], []
    seen_channels, seen_programmes = set(), set()

    for url, local in EPGS:
        data = gunzip_if_needed(fetch(url, local, args.offline))
        # Only channels this source contributes; ones an earlier source already provided are skipped.
        owned = set()
        for _, el in ET.iterparse(io.BytesIO(data), events=("end",)):
            if el.tag == "channel":
                cid = el.get("id")
                if cid in wanted and cid not in seen_channels:
                    seen_channels.add(cid)
                    owned.add(cid)
                    channels.append(el)
                else:
                    el.clear()
            elif el.tag == "programme":
                key = (el.get("channel"), el.get("start"), el.get("stop"))
                if el.get("channel") in owned and key not in seen_programmes:
                    seen_programmes.add(key)
                    programmes.append(el)
                else:
                    el.clear()
        print(f"{local}: {len(owned)} channels")

    root.extend(channels)
    root.extend(programmes)
    ET.indent(root)
    with gzip.open(args.output, "wb") as f:
        ET.ElementTree(root).write(f, encoding="utf-8", xml_declaration=True)
    print(f"wrote {args.output}: {len(channels)} channels, {len(programmes)} programmes "
          f"({len(wanted - seen_channels)} playlist ids without EPG)")


if __name__ == "__main__":
    main()
