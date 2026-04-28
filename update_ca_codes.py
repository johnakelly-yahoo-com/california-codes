#!/usr/bin/env python3
"""
Download and extract all California Codes from the official bulk data.

Source: https://downloads.leginfo.legislature.ca.gov/
Usage:  python3 update_ca_codes.py

This downloads the current session ZIP (~764MB), extracts the law tables
and .lob files, and rebuilds all 30 code text files in the codes/ directory.

The entire process takes about 5-10 minutes depending on internet speed.
"""

import os
import re
import sys
import subprocess
import tempfile
import shutil
from html import unescape
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "codes")


def get_download_url():
    """Determine the correct bulk data URL based on the current legislative session.

    California legislative sessions run in two-year cycles aligned to
    odd-numbered years. The 2025-2026 session file is pubinfo_2025.zip,
    the 2027-2028 session would be pubinfo_2027.zip, etc.
    """
    year = datetime.now().year
    session_year = year if year % 2 == 1 else year - 1
    return f"https://downloads.leginfo.legislature.ca.gov/pubinfo_{session_year}.zip"


def strip_backticks(s):
    if s.startswith('`') and s.endswith('`'):
        return s[1:-1]
    return s


def parse_tsv(filepath, field_names):
    """Parse a tab-delimited file with backtick-enclosed fields."""
    rows = []
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.rstrip('\n').rstrip('\r')
            if not line:
                continue
            parts = line.split('\t')
            row = {}
            for i, name in enumerate(field_names):
                if i < len(parts):
                    row[name] = strip_backticks(parts[i])
                else:
                    row[name] = ''
            rows.append(row)
    return rows


def xml_to_text(xml_content):
    """Convert CAML XML content to readable plain text."""
    if not xml_content:
        return ''

    text = xml_content
    text = re.sub(r'<caml:Content[^>]*>', '', text)
    text = re.sub(r'</caml:Content>', '', text)
    text = re.sub(r'<span\s+class="EnSpace"\s*/?\s*>', ' ', text)
    text = re.sub(r'</p>\s*<p>', '\n\n', text)
    text = re.sub(r'<p>', '', text)
    text = re.sub(r'</p>', '', text)
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'</?i>', '', text)
    text = re.sub(r'</?b>', '', text)
    text = re.sub(r'</?em>', '', text)
    text = re.sub(r'</?strong>', '', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = unescape(text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()
    return text


def read_lob_file(data_dir, lob_filename):
    """Read a .lob file and convert XML to text."""
    filepath = os.path.join(data_dir, lob_filename)
    if not os.path.exists(filepath):
        return ''
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            return xml_to_text(f.read())
    except Exception as e:
        print(f"  Warning: could not read {lob_filename}: {e}")
        return ''


def main():
    download_url = get_download_url()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    tmp_dir = tempfile.mkdtemp(prefix='ca_codes_')
    zip_filename = download_url.rsplit('/', 1)[-1]
    zip_path = os.path.join(tmp_dir, zip_filename)

    try:
        # Step 1: Download
        print(f"Downloading {download_url}...")
        print("  (This is ~764MB and may take a few minutes)")
        subprocess.run(
            ['curl', '-sL', '-o', zip_path, download_url],
            check=True
        )
        size_mb = os.path.getsize(zip_path) / 1048576
        print(f"  Downloaded {size_mb:.0f}MB")

        # Step 2: Extract the .dat files
        print("Extracting data tables...")
        subprocess.run(
            ['unzip', '-o', zip_path,
             'CODES_TBL.dat', 'LAW_SECTION_TBL.dat',
             'LAW_TOC_TBL.dat', 'LAW_TOC_SECTIONS_TBL.dat'],
            cwd=tmp_dir, check=True, capture_output=True
        )

        # Step 3: Extract all .lob files
        print("Extracting law section content files (this takes ~30 seconds)...")
        subprocess.run(
            ['unzip', '-o', zip_path, 'LAW_SECTION_TBL_*.lob'],
            cwd=tmp_dir, check=True, capture_output=True
        )

        lob_count = len([f for f in os.listdir(tmp_dir) if f.startswith('LAW_SECTION_TBL_') and f.endswith('.lob')])
        print(f"  Extracted {lob_count} section content files")

        # Step 4: Parse tables
        print("Reading CODES_TBL.dat...")
        codes = parse_tsv(os.path.join(tmp_dir, 'CODES_TBL.dat'), ['code', 'title'])
        code_names = {}
        for c in codes:
            raw_title = c['title']
            clean = re.sub(r'\s*-\s*[A-Z]+\s*$', '', raw_title)
            clean = clean.lstrip('* ').strip()
            code_names[c['code']] = clean
        print(f"  Found {len(code_names)} codes")

        print("Reading LAW_TOC_TBL.dat...")
        toc_fields = [
            'law_code', 'division', 'title', 'part', 'chapter', 'article',
            'heading', 'active_flg', 'trans_uid', 'trans_update',
            'node_sequence', 'node_level', 'node_position', 'node_treepath',
            'contains_law_sections', 'history_note', 'op_statues', 'op_chapter', 'op_section'
        ]
        toc_rows = parse_tsv(os.path.join(tmp_dir, 'LAW_TOC_TBL.dat'), toc_fields)

        toc_by_code = {}
        for row in toc_rows:
            if row['active_flg'] != 'Y':
                continue
            code = row['law_code']
            if code not in toc_by_code:
                toc_by_code[code] = {}
            toc_by_code[code][row['node_treepath']] = {
                'heading': row['heading'],
                'node_sequence': float(row['node_sequence']) if row['node_sequence'] else 0,
                'node_level': int(float(row['node_level'])) if row['node_level'] else 0,
            }

        print("Reading LAW_SECTION_TBL.dat...")
        section_fields = [
            'id', 'law_code', 'section_num', 'op_statues', 'op_chapter', 'op_section',
            'effective_date', 'law_section_version_id', 'division', 'title', 'part',
            'chapter', 'article', 'history', 'lob_file', 'active_flg', 'trans_uid', 'trans_update'
        ]
        section_rows = parse_tsv(os.path.join(tmp_dir, 'LAW_SECTION_TBL.dat'), section_fields)

        sections_by_code = {}
        latest_update_by_code = {}
        for row in section_rows:
            if row['active_flg'] != 'Y':
                continue
            code = row['law_code']
            if code not in sections_by_code:
                sections_by_code[code] = []
            sections_by_code[code].append(row)
            tu = row.get('trans_update', '')
            if tu and (code not in latest_update_by_code or tu > latest_update_by_code[code]):
                latest_update_by_code[code] = tu

        print("Reading LAW_TOC_SECTIONS_TBL.dat...")
        toc_sec_fields = [
            'id', 'law_code', 'node_treepath', 'section_num', 'section_order',
            'title', 'op_statues', 'op_chapter', 'op_section', 'trans_uid',
            'trans_update', 'law_section_version_id', 'seq_num'
        ]
        toc_sec_rows = parse_tsv(os.path.join(tmp_dir, 'LAW_TOC_SECTIONS_TBL.dat'), toc_sec_fields)

        section_order = {}
        for row in toc_sec_rows:
            code = row['law_code']
            vid = row['law_section_version_id']
            key = (code, vid)
            order_val = float(row['section_order']) if row['section_order'] else 0
            seq_val = float(row['seq_num']) if row['seq_num'] else 0
            treepath = row['node_treepath']
            if key not in section_order or (treepath, order_val, seq_val) < section_order[key]:
                section_order[key] = (treepath, order_val, seq_val)

        # Step 5: Generate files
        separator = "\n\n" + ("=" * 70) + "\n\n"
        thin_sep = "\n" + ("-" * 43) + "\n\n"

        for code in sorted(code_names.keys()):
            code_title = code_names[code]
            filename = f"CA Code - {code_title}.txt"
            filepath = os.path.join(OUTPUT_DIR, filename)

            if code not in sections_by_code:
                print(f"  Skipping {code} ({code_title}) - no sections found")
                continue

            sections = sections_by_code[code]
            print(f"Processing {code} ({code_title}): {len(sections)} sections...")

            def sort_key(sec):
                vid = sec['law_section_version_id']
                key = (code, vid)
                if key in section_order:
                    tp, order, seq = section_order[key]
                    tp_parts = [float(x) for x in tp.split('.') if x]
                    return (tp_parts, order, seq)
                m = re.match(r'(\d+\.?\d*)', sec['section_num'] or '')
                num = float(m.group(1)) if m else 99999
                return ([99999], 0, num)

            sections.sort(key=sort_key)

            last_updated_raw = latest_update_by_code.get(code, '')
            if last_updated_raw:
                try:
                    last_updated = datetime.strptime(last_updated_raw[:10], '%Y-%m-%d').strftime('%B %d, %Y')
                except ValueError:
                    last_updated = last_updated_raw
            else:
                last_updated = 'Unknown'

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"{'=' * 70}\n")
                f.write(f"  {code_title}\n")
                f.write(f"  State of California\n")
                f.write(f"{'=' * 70}\n\n")
                f.write(f"Source: Official California Legislative Information\n")
                f.write(f"        https://downloads.leginfo.legislature.ca.gov/\n")
                f.write(f"Last Updated by State of California: {last_updated}\n")
                f.write(separator)

                written_headings = set()

                for sec in sections:
                    vid = sec['law_section_version_id']
                    key = (code, vid)

                    if key in section_order and code in toc_by_code:
                        treepath = section_order[key][0]
                        parts = treepath.split('.')
                        for depth in range(1, len(parts) + 1):
                            parent_path = '.'.join(parts[:depth])
                            if parent_path and parent_path not in written_headings:
                                if parent_path in toc_by_code[code]:
                                    toc_entry = toc_by_code[code][parent_path]
                                    heading = toc_entry['heading']
                                    level = toc_entry['node_level']
                                    if heading:
                                        if level <= 1:
                                            f.write(separator)
                                            f.write(heading.upper())
                                        elif level == 2:
                                            f.write(f"\n\n{heading}")
                                        else:
                                            f.write(f"\n\n  {heading}")
                                        f.write("\n\n")
                                    written_headings.add(parent_path)

                    section_num = sec['section_num'].strip() if sec['section_num'] else ''
                    lob_file = sec['lob_file'].strip() if sec['lob_file'] else ''
                    history = sec['history'].strip() if sec['history'] else ''

                    content = read_lob_file(tmp_dir, lob_file) if lob_file else ''
                    if not content:
                        continue

                    f.write(f"{section_num}\n\n")
                    f.write(content)
                    if history:
                        f.write(f"\n\n(History: {history})")
                    f.write(thin_sep)

            file_size = os.path.getsize(filepath)
            size_str = f"{file_size / 1048576:.1f}MB" if file_size > 1048576 else f"{file_size / 1024:.0f}KB"
            print(f"  -> {filename} ({size_str})")

        print(f"\nDone! Files written to:\n  {OUTPUT_DIR}")

    finally:
        print(f"\nCleaning up temp files...")
        shutil.rmtree(tmp_dir, ignore_errors=True)
        print("Cleanup complete.")


if __name__ == '__main__':
    main()
