#!/usr/bin/env python3
"""
Import publications from ORCID into the Academic Pages _publications folder.

- Uses the official ORCID public API (pub.orcid.org) to list all works with a DOI.
- Fetches metadata for each DOI from CrossRef.
- Rebuilds _publications from scratch on every run (old files are removed only
  after ORCID has been read successfully), so the folder always mirrors ORCID.

Requires: requests  (pip install requests)
"""

import json
import os
import re
import sys
import time
from urllib.parse import quote

import requests

# Configuration
ORCID_ID = "0000-0002-7699-8191"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_publications")
CONTACT = "martina.kutmon@maastrichtuniversity.nl"  # sent to CrossRef as polite-pool contact
HEADERS = {"User-Agent": f"mkutmon.github.io publication import (mailto:{CONTACT})"}


def yaml_str(value):
    """Return a YAML-safe double-quoted string (JSON strings are valid YAML)."""
    return json.dumps(value or "", ensure_ascii=False)


def fetch_orcid_dois(orcid_id):
    """Return a list of unique DOIs (lower-case) from the ORCID record."""
    url = f"https://pub.orcid.org/v3.0/{orcid_id}/works"
    r = requests.get(url, headers={**HEADERS, "Accept": "application/json"}, timeout=60)
    r.raise_for_status()
    dois = []
    for group in r.json().get("group", []):
        doi = None
        for ext in group.get("external-ids", {}).get("external-id", []):
            if ext.get("external-id-type") == "doi":
                doi = ext.get("external-id-value") or ext.get("external-id-normalized", {}).get("value")
                if ext.get("external-id-relationship") == "self":
                    break
        if doi:
            doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi.strip(), flags=re.I).lower()
            if doi not in dois:
                dois.append(doi)
    return dois


def fetch_crossref(doi):
    r = requests.get(f"https://api.crossref.org/works/{quote(doi)}", headers=HEADERS, timeout=60)
    r.raise_for_status()
    return r.json()["message"]


def clean(text):
    """Strip HTML/JATS tags and collapse whitespace."""
    text = re.sub(r"<[^>]+>", "", text or "")
    return re.sub(r"\s+", " ", text).strip()


def get_year(msg):
    for key in ("published-print", "published-online", "issued", "posted", "created"):
        parts = msg.get(key, {}).get("date-parts", [[None]])
        if parts and parts[0] and parts[0][0]:
            return int(parts[0][0])
    return None


def get_venue(msg):
    venue = (msg.get("container-title") or [""])[0]
    if not venue and msg.get("type") == "posted-content":
        inst = msg.get("institution") or []
        venue = inst[0].get("name", "") if inst else ""
        venue = venue or msg.get("publisher", "") or "Preprint"
    return clean(venue)


def format_authors(authors):
    names = []
    for a in authors:
        family = clean(a.get("family", ""))
        given = clean(a.get("given", ""))
        if not family:
            name = clean(a.get("name", ""))  # consortium / group authors
            if name:
                names.append(name)
            continue
        initials = " ".join(p[0] + "." for p in re.split(r"[\s-]+", given) if p)
        names.append(f"{initials} {family}".strip())
    return ", ".join(names)


def write_publication(msg, doi):
    title = clean((msg.get("title") or ["Untitled"])[0])
    year = get_year(msg) or 1900
    venue = get_venue(msg)
    authors = format_authors(msg.get("author", []))
    category = "preprints" if msg.get("type") == "posted-content" else "manuscripts"
    slug = re.sub(r"[^a-z0-9]+", "-", doi.lower()).strip("-")[:60]
    filename = f"{year}-{slug}.md"
    paperurl = f"https://doi.org/{doi}"
    citation = f'{authors}. ({year}). "{title}." <i>{venue}</i>.'

    content = "\n".join([
        "---",
        f"title: {yaml_str(title)}",
        "collection: publications",
        f"category: {category}",
        f"permalink: /publication/{filename[:-3]}",
        "excerpt: ''",
        f"date: {year}-01-01",
        f"venue: {yaml_str(venue)}",
        f"paperurl: {yaml_str(paperurl)}",
        f"citation: {yaml_str(citation)}",
        "---",
        "",
        f'{authors}. ({year}). "{title}." *{venue}*.',
        "",
        f"[Paper]({paperurl})",
        "",
    ])
    with open(os.path.join(OUTPUT_DIR, filename), "w", encoding="utf-8") as f:
        f.write(content)
    return filename


def main():
    print(f"Fetching works for ORCID {ORCID_ID}")
    try:
        dois = fetch_orcid_dois(ORCID_ID)
    except requests.RequestException as e:
        print(f"ERROR: could not read ORCID ({e}); leaving existing publications untouched.")
        sys.exit(1)
    if not dois:
        print("ERROR: ORCID returned no DOIs; leaving existing publications untouched.")
        sys.exit(1)
    print(f"Found {len(dois)} works with a DOI")

    records = []
    for i, doi in enumerate(dois, 1):
        try:
            records.append((doi, fetch_crossref(doi)))
            print(f"[{i}/{len(dois)}] OK   {doi}")
        except requests.RequestException as e:
            print(f"[{i}/{len(dois)}] SKIP {doi} ({e})")
        time.sleep(0.5)

    if not records:
        print("ERROR: no CrossRef records retrieved; leaving existing publications untouched.")
        sys.exit(1)

    # Rebuild the folder from scratch only now that we have data.
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for name in os.listdir(OUTPUT_DIR):
        if name.endswith(".md"):
            os.remove(os.path.join(OUTPUT_DIR, name))

    written = set()
    for doi, msg in records:
        written.add(write_publication(msg, doi))
    print(f"Done: wrote {len(written)} publications to {os.path.abspath(OUTPUT_DIR)}")


if __name__ == "__main__":
    main()
