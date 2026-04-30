"""
Wanted Poster Generator
-----------------------
Fetches character data from a public Google Sheet and produces a
self-contained HTML file with a search interface and printable wanted posters.

Usage:
    python generate_posters.py

Requirements:
    pip install requests

Configuration:
    Edit the SETTINGS block below before running.
"""

import csv
import io
import json
import sys
import requests

# ─── SETTINGS ────────────────────────────────────────────────────────────────

SHEET_URL = "https://docs.google.com/spreadsheets/d/1njbBYMUmdq0tc_hgz7kTrzzEVsl-aTpDo7ZY8tpEx8A/edit?gid=1437642413#gid=1437642413"

# Column headers (case-insensitive, partial match)
NAME_COL     = "candidate"
HEADLINE_COL = "headline"
LINK_COL     = "url"

OUTPUT_FILE  = "posters.html"

# ─── FETCH & PARSE ───────────────────────────────────────────────────────────

def to_csv_url(url):
    import re
    m = re.search(r'/spreadsheets/d/([^/]+)', url)
    if not m:
        return url
    sheet_id = m.group(1)
    gid_m = re.search(r'[#&?]gid=(\d+)', url)
    gid = gid_m.group(1) if gid_m else '0'
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"

def fetch_characters(url, name_col, headline_col, link_col):
    csv_url = to_csv_url(url)
    print(f"Fetching sheet as CSV: {csv_url}")
    try:
        r = requests.get(csv_url, timeout=15)
        r.raise_for_status()
    except requests.RequestException as e:
        sys.exit(f"Error fetching sheet: {e}\nMake sure the sheet is set to 'Anyone with the link can view'.")

    reader = csv.DictReader(io.StringIO(r.text))
    headers = reader.fieldnames or []
    print("Columns found:", [repr(h) for h in headers])


    def find_col(keyword):
      for h in headers:
          cleaned = h.strip().lstrip('\ufeff')  # strip whitespace and BOM
          if keyword.lower() in cleaned.lower():
              return h
      return None

    nc = find_col(name_col)
    hc = find_col(headline_col)
    lc = find_col(link_col)

    missing = [k for k, v in [(name_col, nc), (headline_col, hc), (link_col, lc)] if v is None]
    if missing:
        sys.exit(f"\nCouldn't find columns matching: {missing}\nEdit the NAME_COL / HEADLINE_COL / LINK_COL settings at the top of this script.")

    characters = []
    for row in reader:
        name     = (row.get(nc) or "").strip()
        headline = (row.get(hc) or "").strip()
        link     = (row.get(lc) or "").strip()
        if name:
            characters.append({"name": name, "headline": headline, "link": link})

    print(f"Loaded {len(characters)} characters.")
    return characters

# ─── HTML TEMPLATE ───────────────────────────────────────────────────────────
# Uses %%CHARACTERS_JSON%% as the placeholder — replaced with str.replace(),
# not .format(), so all JavaScript curly braces are left completely untouched.

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Wanted Poster Generator</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Rye&family=Special+Elite&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: system-ui, sans-serif;
      background: #1a1a1a;
      color: #eee;
      min-height: 100vh;
    }

    #search-screen {
      max-width: 560px;
      margin: 0 auto;
      padding: 3rem 1.5rem;
    }
    h1 { font-size: 2rem; font-weight: 600; margin-bottom: 0.4rem; letter-spacing: -0.5px; }
    .subtitle { color: #888; font-size: 0.9rem; margin-bottom: 2rem; }
    .badge {
      display: inline-block;
      background: #2a3a2a; color: #6b9;
      font-size: 0.75rem; padding: 3px 10px;
      border-radius: 999px; margin-bottom: 1.5rem;
    }
    #search-input {
      width: 100%; padding: 0.75rem 1rem;
      font-size: 1rem; border: 1px solid #333;
      border-radius: 8px; background: #252525;
      color: #eee; outline: none; margin-bottom: 1rem;
      transition: border-color 0.15s;
    }
    #search-input:focus { border-color: #666; }
    #search-input::placeholder { color: #555; }

    .result-card {
      padding: 0.75rem 1rem;
      border: 1px solid #2a2a2a; border-radius: 8px;
      margin-bottom: 0.5rem; cursor: pointer;
      background: #1e1e1e; transition: background 0.1s, border-color 0.1s;
    }
    .result-card:hover { background: #252525; border-color: #3a3a3a; }
    .result-name { font-weight: 500; font-size: 0.95rem; }
    .result-headline {
      font-size: 0.8rem; color: #888; margin-top: 2px;
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    #no-results { color: #666; font-size: 0.9rem; padding: 0.5rem 0; }
    #overflow-note { color: #666; font-size: 0.8rem; margin-top: 0.5rem; }
    #hint { color: #555; font-size: 0.8rem; margin-top: 0.5rem; }

    #poster-screen {
      display: none;
      flex-direction: column;
      align-items: center;
      padding: 2rem 1rem;
      min-height: 100vh;
    }

    .poster {
      width: 480px; max-width: 100%;
      background: radial-gradient(ellipse at center, #f7e9b0 0%, #ecd882 55%, #d9c055 100%);
      border: 7px double #4a2d0a;
      padding: 2.5rem 3rem 2.25rem;
      text-align: center; position: relative;
      box-shadow: 0 16px 64px rgba(0,0,0,0.6);
    }
    .poster::before {
      content: '';
      position: absolute; inset: 8px;
      border: 1.5px solid rgba(74,45,10,0.35);
      pointer-events: none;
    }
    .corner { position: absolute; width: 22px; height: 22px; border: 2.5px solid #4a2d0a; }
    .corner.tl { top:4px; left:4px;  border-right:none; border-bottom:none; }
    .corner.tr { top:4px; right:4px; border-left:none;  border-bottom:none; }
    .corner.bl { bottom:4px; left:4px;  border-right:none; border-top:none; }
    .corner.br { bottom:4px; right:4px; border-left:none;  border-top:none; }

    .poster-wanted {
      font-family: 'Rye', Georgia, serif;
      font-size: 72px; color: #1a0d00;
      letter-spacing: 8px; line-height: 1;
      text-shadow: 2px 3px 6px rgba(0,0,0,0.2);
      margin-bottom: 0.25rem;
    }
    .divider { display: flex; align-items: center; margin: 0.6rem 0; }
    .divider-line { flex: 1; height: 2px; background: #4a2d0a; }
    .divider-star { color: #4a2d0a; font-size: 14px; margin: 0 10px; }
    .divider-thin { height: 1px; background: rgba(74,45,10,0.4); margin: 0.6rem 0; }

    .poster-for {
      font-family: 'Special Elite', Georgia, serif;
      font-size: 12px; letter-spacing: 5px;
      color: #4a2d0a; margin: 0.4rem 0;
    }
    .poster-headline {
      font-family: 'Special Elite', Georgia, serif;
      font-size: 15px; font-style: italic;
      line-height: 1.55; color: #1a0d00;
      background: rgba(74,45,10,0.07);
      border: 1px solid rgba(74,45,10,0.3);
      padding: 0.75rem 1rem; margin: 0.5rem 0 1rem;
    }
    .poster-name {
      font-family: 'Rye', Georgia, serif;
      font-size: 34px; color: #1a0d00;
      letter-spacing: 3px; line-height: 1.25;
      margin: 0.75rem 0 0.5rem; word-break: break-word;
      text-shadow: 1px 2px 4px rgba(0,0,0,0.18);
    }
    .poster-link {
      font-family: 'Special Elite', Georgia, serif;
      font-size: 10px; color: #5a3a1a;
      word-break: break-all; letter-spacing: 0.3px;
      margin-top: 0.75rem; opacity: 0.85; line-height: 1.5;
    }

    .poster-buttons {
      display: flex; gap: 1rem;
      margin-top: 1.5rem; flex-wrap: wrap; justify-content: center;
    }
    button {
      padding: 0.6rem 1.25rem; border-radius: 7px;
      border: 1px solid #444; background: #252525;
      color: #eee; font-size: 0.9rem; cursor: pointer;
      transition: background 0.1s;
    }
    button:hover { background: #333; }

    @media print {
      body { background: white; }
      .poster-buttons { display: none; }
      #search-screen { display: none !important; }
      #poster-screen { display: flex !important; }
    }
  </style>
</head>
<body>

<div id="search-screen">
  <h1>Wanted Posters</h1>
  <p class="subtitle">Search for a character to generate their poster.</p>
  <div class="badge" id="count-badge"></div>
  <input id="search-input" type="text" placeholder="Type a character name..." autocomplete="off" />
  <div id="results"></div>
</div>

<div id="poster-screen">
  <div class="poster">
    <div class="corner tl"></div>
    <div class="corner tr"></div>
    <div class="corner bl"></div>
    <div class="corner br"></div>
    <div class="poster-wanted">WANTED</div>
    <div class="divider">
      <div class="divider-line"></div>
      <span class="divider-star">&#10022;</span>
      <div class="divider-line"></div>
    </div>
    <div class="poster-for">WANTED FOR</div>
    <div class="poster-headline" id="poster-headline"></div>
    <div class="divider-thin"></div>
    <div class="poster-name" id="poster-name"></div>
    <div class="divider">
      <div class="divider-line"></div>
      <span class="divider-star">&#10022;</span>
      <div class="divider-line"></div>
    </div>
    <div class="poster-link" id="poster-link"></div>
  </div>
  <div class="poster-buttons">
    <button onclick="showSearch()">&#8592; Search again</button>
    <button onclick="window.print()">Print poster</button>
  </div>
</div>

<script>
var CHARACTERS = %%CHARACTERS_JSON%%;

var searchEl  = document.getElementById('search-input');
var resultsEl = document.getElementById('results');
var searchScr = document.getElementById('search-screen');
var posterScr = document.getElementById('poster-screen');

document.getElementById('count-badge').textContent = CHARACTERS.length + ' characters loaded';

searchEl.addEventListener('input', function() {
  var q = searchEl.value.trim().toLowerCase();
  resultsEl.innerHTML = '';

  if (!q) {
    resultsEl.innerHTML = '<p id="hint">Start typing to search. Partial matches work.</p>';
    return;
  }

  var matches = CHARACTERS.filter(function(c) {
    return c.name.toLowerCase().indexOf(q) !== -1;
  });

  if (matches.length === 0) {
    resultsEl.innerHTML = '<p id="no-results">No results for "' + escHtml(searchEl.value) + '"</p>';
    return;
  }

  matches.slice(0, 10).forEach(function(c) {
    var div = document.createElement('div');
    div.className = 'result-card';
    div.innerHTML = '<div class="result-name">'     + escHtml(c.name)     + '</div>' +
                    '<div class="result-headline">' + escHtml(c.headline) + '</div>';
    div.onclick = (function(char) {
      return function() { showPoster(char); };
    })(c);
    resultsEl.appendChild(div);
  });

  if (matches.length > 10) {
    var note = document.createElement('p');
    note.id = 'overflow-note';
    note.textContent = '...and ' + (matches.length - 10) + ' more. Keep typing to narrow down.';
    resultsEl.appendChild(note);
  }
});

function showPoster(c) {
  document.getElementById('poster-name').textContent     = c.name;
  document.getElementById('poster-headline').textContent = c.headline;
  document.getElementById('poster-link').textContent     = c.link;
  searchScr.style.display = 'none';
  posterScr.style.display = 'flex';
  window.scrollTo(0, 0);
}

function showSearch() {
  posterScr.style.display = 'none';
  searchScr.style.display = 'block';
  searchEl.focus();
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

resultsEl.innerHTML = '<p id="hint">Start typing to search. Partial matches work.</p>';
</script>
</body>
</html>"""

# ─── GENERATE ────────────────────────────────────────────────────────────────

def generate(url, name_col, headline_col, link_col, output_file):
    characters = fetch_characters(url, name_col, headline_col, link_col)
    characters_json = json.dumps(characters, ensure_ascii=False, indent=2)
    html = HTML_TEMPLATE.replace("%%CHARACTERS_JSON%%", characters_json)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Done! Open {output_file} in your browser.")

if __name__ == "__main__":
    generate(SHEET_URL, NAME_COL, HEADLINE_COL, LINK_COL, OUTPUT_FILE)