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

import base64
import csv
import io
import json
import mimetypes
import os
import sys
import requests

# ─── SETTINGS ────────────────────────────────────────────────────────────────

SHEET_URL = "https://docs.google.com/spreadsheets/d/1njbBYMUmdq0tc_hgz7kTrzzEVsl-aTpDo7ZY8tpEx8A/edit?gid=1437642413#gid=1437642413"

# Column headers (case-insensitive, partial match)
CANDIDATE_COL = "candidate"
WARD_COL      = "ward"
HEADLINE_COL  = "headline"
LINK_COL      = "url"

OUTPUT_FILE  = "index.html"

# Set to a local CSV filename to use that instead of fetching from Google Sheets
LOCAL_CSV    = "cleanlist.csv"

# Set to an image URL to show it on every poster; leave blank for the placeholder box
IMAGE_URL    = "reformImage.png"

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

def fetch_characters(url, candidate_col, ward_col, headline_col, link_col):
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
            cleaned = h.strip().lstrip('\ufeff')
            if keyword.lower() in cleaned.lower():
                return h
        return None

    cc = find_col(candidate_col)
    wc = find_col(ward_col)
    hc = find_col(headline_col)
    lc = find_col(link_col)

    missing = [k for k, v in [(candidate_col, cc), (ward_col, wc), (headline_col, hc), (link_col, lc)] if v is None]
    if missing:
        sys.exit(f"\nCouldn't find columns matching: {missing}\nEdit the column settings at the top of this script.")

    characters = []
    for row in reader:
        candidate = (row.get(cc) or "").strip()
        ward      = (row.get(wc) or "").strip()
        headline  = (row.get(hc) or "").strip()
        link      = (row.get(lc) or "").strip()
        if candidate:
            characters.append({"candidate": candidate, "ward": ward, "headline": headline, "link": link})

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
  <title>Campaign Leaflet Generator</title>
  <link href="https://fonts.googleapis.com/css2?family=Saira+Extra+Condensed:wght@900&family=Special+Elite&display=swap" rel="stylesheet">
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }

    body {
      font-family: system-ui, sans-serif;
      background: #1a1a1a;
      color: #eee;
      min-height: 100vh;
    }

    /* ── Search screen ── */
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

    /* ── Poster screen ── */
    #poster-screen {
      display: none;
      flex-direction: column;
      align-items: center;
      padding: 2rem 1rem;
      min-height: 100vh;
      background: #444;
    }

    .poster {
      width: 960px;
      height: 1190px;
      max-width: 100%;
      background: #000;
      display: flex;
      flex-direction: column;
      padding: 55px 55px 38px;
      position: relative;
      overflow: hidden;
    }

    .top-text {
      font-family: 'Saira Extra Condensed', sans-serif;
      font-size: 130px;
      font-weight: 900;
      color: #fff;
      line-height: 0.92;
      letter-spacing: -1px;
      text-align: center;
      flex-shrink: 0;
    }

    .top-row {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 22px;
      line-height: 0.92;
    }

    .inline-image-placeholder {
      width: 118px;
      height: 118px;
      border: 3px dashed rgba(255,255,255,0.4);
      border-radius: 5px;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      position: relative;
      top: -4px;
    }

    .inline-image-placeholder span {
      font-family: 'Special Elite', monospace;
      font-size: 11px;
      color: rgba(255,255,255,0.4);
      text-align: center;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      line-height: 1.4;
    }

    .spacer { flex: 1; }

    .headline-wrap {
      display: flex;
      justify-content: center;
      flex-shrink: 0;
    }

    .headline-box {
      background: #fff;
      border: 5px solid #cc2200;
      padding: 8px 30px;
      display: inline-block;
    }

    .headline-box span {
      font-family: 'Saira Extra Condensed', sans-serif;
      font-size: 116px;
      font-weight: 900;
      color: #cc2200;
      letter-spacing: -1px;
      line-height: 1;
      text-transform: uppercase;
      text-align: center;
      display: block;
    }

    .bottom-text {
      font-family: 'Saira Extra Condensed', sans-serif;
      font-size: 126px;
      font-weight: 900;
      color: #fff;
      line-height: 0.92;
      letter-spacing: -1px;
      text-align: center;
      flex-shrink: 0;
    }

    .bottom-text .red { color: #cc2200; }

    .source {
      font-family: 'Special Elite', monospace;
      font-size: 22px;
      color: #555;
      letter-spacing: 0.5px;
      flex-shrink: 0;
      margin-top: auto;
      padding-top: 18px;
      text-align: left;
      word-break: break-all;
    }

    .poster-buttons {
      display: flex; gap: 1rem;
      margin-top: 1.5rem; flex-wrap: wrap; justify-content: center;
    }
    button {
      padding: 0.6rem 1.25rem; border-radius: 7px;
      border: 1px solid #666; background: #333;
      color: #eee; font-size: 0.9rem; cursor: pointer;
      transition: background 0.1s;
    }
    button:hover { background: #444; }

    @media print {
      body, #poster-screen { background: #444; }
      .poster-buttons { display: none; }
      #search-screen { display: none !important; }
      #poster-screen { display: flex !important; }
    }
  </style>
</head>
<body>

<div id="search-screen">
  <h1>Campaign Leaflet Generator</h1>
  <p class="subtitle">Search for a candidate to generate their leaflet.</p>
  <div class="badge" id="count-badge"></div>
  <input id="search-input" type="text" placeholder="Type a candidate name..." autocomplete="off" />
  <div id="results"></div>
</div>

<div id="poster-screen">
  <div class="poster">
    <div class="top-text">
      <div class="top-row">
        Your
        %%IMAGE_HTML%%
      </div>
      candidate for<br>
      <span id="poster-name"></span>
    </div>
    <div class="spacer"></div>
    <div class="headline-wrap">
      <div class="headline-box">
        <span id="poster-headline"></span>
      </div>
    </div>
    <div class="spacer"></div>
    <div class="bottom-text">
      Will you still <span class="red">vote</span> for them?
    </div>
    <div class="source">source: <span id="poster-link"></span></div>
  </div>
  <div class="poster-buttons">
    <button onclick="showSearch()">&#8592; Search again</button>
    <button onclick="window.print()">Print leaflet</button>
  </div>
</div>

<script>
var CHARACTERS = %%CHARACTERS_JSON%%;

var searchEl  = document.getElementById('search-input');
var resultsEl = document.getElementById('results');
var searchScr = document.getElementById('search-screen');
var posterScr = document.getElementById('poster-screen');

document.getElementById('count-badge').textContent = CHARACTERS.length + ' candidates loaded';

searchEl.addEventListener('input', function() {
  var q = searchEl.value.trim().toLowerCase();
  resultsEl.innerHTML = '';

  if (!q) {
    resultsEl.innerHTML = '<p id="hint">Start typing to search. Partial matches work.</p>';
    return;
  }

  var matches = CHARACTERS.filter(function(c) {
    return c.candidate.toLowerCase().indexOf(q) !== -1 ||
           c.ward.toLowerCase().indexOf(q) !== -1;
  });

  if (matches.length === 0) {
    resultsEl.innerHTML = '<p id="no-results">No results for "' + escHtml(searchEl.value) + '"</p>';
    return;
  }

  matches.slice(0, 10).forEach(function(c) {
    var div = document.createElement('div');
    div.className = 'result-card';
    div.innerHTML = '<div class="result-name">' + escHtml(c.candidate) + ' &mdash; ' + escHtml(c.ward) + '</div>' +
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

function fitHeadline() {
  var span = document.getElementById('poster-headline');
  var box  = span.parentElement;
  var size = 116;
  span.style.fontSize = size + 'px';
  while (span.scrollWidth > box.clientWidth && size > 24) {
    size -= 2;
    span.style.fontSize = size + 'px';
  }
}

function showPoster(c) {
  document.getElementById('poster-name').textContent     = c.ward;
  document.getElementById('poster-headline').textContent = c.headline;
  document.getElementById('poster-link').textContent     = c.link;
  searchScr.style.display = 'none';
  posterScr.style.display = 'flex';
  window.scrollTo(0, 0);
  fitHeadline();
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

def resolve_image(image_url):
    if not image_url:
        return None
    if not image_url.startswith("http"):
        mime = mimetypes.guess_type(image_url)[0] or "image/png"
        with open(image_url, "rb") as f:
            data = base64.b64encode(f.read()).decode()
        return f"data:{mime};base64,{data}"
    return image_url

def load_local_csv(path, candidate_col, ward_col, headline_col, link_col):
    print(f"Loading local CSV: {path}")
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []

        def find_col(keyword):
            for h in headers:
                if keyword.lower() in h.strip().lower():
                    return h
            return None

        cc = find_col(candidate_col)
        wc = find_col(ward_col)
        hc = find_col(headline_col)
        lc = find_col(link_col) or find_col("link") or find_col("url")

        missing = [k for k, v in [(candidate_col, cc), (ward_col, wc), (headline_col, hc), (link_col, lc)] if v is None]
        if missing:
            sys.exit(f"\nCouldn't find columns matching: {missing} in {path}")

        characters = []
        for row in reader:
            candidate = (row.get(cc) or "").strip()
            ward      = (row.get(wc) or "").strip()
            headline  = (row.get(hc) or "").strip()
            link      = (row.get(lc) or "").strip()
            if candidate:
                characters.append({"candidate": candidate, "ward": ward, "headline": headline, "link": link})
    print(f"Loaded {len(characters)} characters.")
    return characters

def generate(url, candidate_col, ward_col, headline_col, link_col, output_file, image_url="", local_csv=""):
    if local_csv:
        characters = load_local_csv(local_csv, candidate_col, ward_col, headline_col, link_col)
    else:
        characters = fetch_characters(url, candidate_col, ward_col, headline_col, link_col)
    characters_json = json.dumps(characters, ensure_ascii=False, indent=2)
    src = resolve_image(image_url)
    if src:
        image_html = f'<img src="{src}" style="height:80px;width:500px;border-radius:5px;display:block;" />'
    else:
        image_html = '<div class="inline-image-placeholder"><span>Image<br>here</span></div>'
    html = HTML_TEMPLATE.replace("%%CHARACTERS_JSON%%", characters_json)
    html = html.replace("%%IMAGE_HTML%%", image_html)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Done! Open {output_file} in your browser.")

if __name__ == "__main__":
    generate(SHEET_URL, CANDIDATE_COL, WARD_COL, HEADLINE_COL, LINK_COL, OUTPUT_FILE, IMAGE_URL, LOCAL_CSV)