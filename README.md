# iptv-epg

Merges several XMLTV EPGs into one guide limited to the channels listed in `channel_ids.txt`.
A scheduled GitHub Action rebuilds it and uploads it to the `latest` release.

Refresh the channel list locally (needs the playlists, which hold credentials and are never committed;
`--private` points at the folder holding `playlists.txt` and `playlists/`):

    python3 merge_epg.py --refresh-ids --private DIR
