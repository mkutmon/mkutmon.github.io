#!/usr/bin/env python3
"""
Import publications from ORCID to Academic Pages format.
Requires: requests, python-dateutil
Install with: pip install requests python-dateutil
"""

import requests
import json
import os
import re
from datetime import datetime
from urllib.parse import quote
import time

# Configuration
ORCID_ID = "0000-0002-7699-8191"  # Replace with your ORCID ID
YOUR_NAME = "Martina Summer-Kutmon"  # Name to bold in publications
OUTPUT_DIR = "_publications"  # Academic Pages publications directory

def fetch_orcid_works(orcid_id):
    """Fetch works from ORCID public API."""
    url = f"https://orcid.org/{orcid_id}/worksPage.json"
    params = {
        'offset': 0,
        'sort': 'date',
        'sortAsc': 'false'
    }
    headers = {
        'Accept': 'application/json',
        'Referer': f'https://orcid.org/{orcid_id}'
    }
    
    response = requests.get(url, params=params, headers=headers)
    response.raise_for_status()
    return response.json()

def get_doi_from_group(group):
    """Extract DOI from ORCID work group."""
    external_ids = group.get('externalIdentifiers', [])
    for ext_id in external_ids:
        if (ext_id.get('externalIdentifierType', {}).get('value') == 'doi' and
            ext_id.get('relationship', {}).get('value') == 'self'):
            return ext_id.get('externalIdentifierId', {}).get('value')
    return None

def fetch_crossref_data(doi):
    """Fetch publication data from CrossRef API."""
    url = f"https://api.crossref.org/v1/works/{quote(doi)}"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()['message']

def format_authors(authors, your_name):
    """Format author list, bolding your name."""
    formatted_authors = []
    for author in authors:
        given = author.get('given', '')
        family = author.get('family', '')
        
        # Abbreviate given names
        given_abbrev = ' '.join([name[0] + '.' for name in given.split() if name])
        full_name = f"{given_abbrev} {family}".strip()
        
        # Bold your name
        if your_name.lower() in full_name.lower():
            full_name = f"**{full_name}**"
            
        formatted_authors.append(full_name)
    
    return ', '.join(formatted_authors)

def create_publication_file(pub_data, output_dir, index):
    """Create Academic Pages publication markdown file."""
    title = pub_data.get('title', ['Untitled'])[0] if pub_data.get('title') else 'Untitled'
    authors = pub_data.get('author', [])
    journal = pub_data.get('container-title', [''])[0] if pub_data.get('container-title') else ''
    doi = pub_data.get('DOI', '')
    
    # Extract year from published date
    published = pub_data.get('published-print') or pub_data.get('published-online')
    year = published['date-parts'][0][0] if published and published.get('date-parts') else datetime.now().year
    
    # Create filename from title
    filename = re.sub(r'[^\w\s-]', '', doi).strip()
    filename = re.sub(r'[-\s]+', '-', filename).lower()
    filename = f"{year}-{filename[:50]}.md"  # Limit length
    
    # Format authors
    author_string = format_authors(authors, YOUR_NAME)
    
    # Create markdown content
    content = f"""---
title: "{title}"
collection: publications
category: manuscripts
permalink: /publication/{filename[:-3]}
excerpt: ''
date: {year}-01-01
venue: '{journal}'
slidesurl: ''
paperurl: 'https://doi.org/{doi}'
citation: '{author_string}. ({year}). &quot;{title}.&quot; <i>{journal}</i>.'
---

{author_string}. ({year}). "{title}." *{journal}*.

[Download paper](https://doi.org/{doi})
"""

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Write file
    filepath = os.path.join(output_dir, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Created: {filepath}")

def main():
    print(f"Fetching publications for ORCID ID: {ORCID_ID}")
    
    # Fetch works from ORCID
    try:
        works_data = fetch_orcid_works(ORCID_ID)
    except requests.RequestException as e:
        print(f"Error fetching ORCID data: {e}")
        return
    
    groups = works_data.get('groups', [])
    
    if not groups:
        print("No publications found in ORCID record")
        return
        
    print(f"Found {len(groups)} publication groups")
    
    successful_imports = 0
    
    for i, group in enumerate(groups):
        doi = get_doi_from_group(group)
        if not doi:
            print(f"Skipping group {i+1}: No DOI found")
            continue
        
        print(f"Processing {i+1}/{len(groups)}: {doi}")
        
        try:
            # Fetch detailed data from CrossRef
            pub_data = fetch_crossref_data(doi)
            
            # Create publication file
            create_publication_file(pub_data, OUTPUT_DIR, i+1)
            successful_imports += 1
            
            # Be nice to APIs - rate limiting
            time.sleep(1)  # Increased to 1 second
            
        except requests.RequestException as e:
            print(f"Error fetching CrossRef data for {doi}: {e}")
            continue
        except Exception as e:
            print(f"Error processing {doi}: {e}")
            continue
    
    print(f"\nImport complete!")
    print(f"Successfully imported: {successful_imports}/{len(groups)} publications")
    print(f"Check the {OUTPUT_DIR} directory for new files.")

if __name__ == "__main__":
    # Update configuration
    if ORCID_ID == "0000-0000-0000-0000":
        print("Please update ORCID_ID and YOUR_NAME in the script configuration!")
        exit(1)
    
    main()
