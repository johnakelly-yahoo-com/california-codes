#!/usr/bin/env python3
"""
Build a daily changelog comparing old and new versions of each California code file.
Parses section-level diffs and writes a readable markdown log.
"""

import os
import re
import subprocess
import sys
from datetime import datetime, timezone


CODES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "codes")
LOGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
SECTION_SEP = re.compile(r'^-{10,}$', re.MULTILINE)


def parse_sections(text):
    """Split a code file into {section_number: section_text} pairs."""
    sections = {}
    chunks = SECTION_SEP.split(text)
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        lines = chunk.split('\n', 1)
        first_line = lines[0].strip()
        if re.match(r'^[\d.]+[a-z]*\.?', first_line) and len(first_line) < 30:
            sections[first_line] = chunk
    return sections


def get_old_file(filepath):
    """Get the HEAD version of a file from git."""
    try:
        result = subprocess.run(
            ['git', 'show', f'HEAD:{filepath}'],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            return result.stdout
    except Exception:
        pass
    return None


def get_changed_code_files():
    """Return list of code files that differ from HEAD."""
    result = subprocess.run(
        ['git', 'diff', '--name-only', 'HEAD', '--', 'codes/'],
        capture_output=True, text=True
    )
    files = [f.strip() for f in result.stdout.strip().split('\n') if f.strip()]
    return sorted(files)


def build_log():
    today = datetime.now(timezone.utc)
    pretty_date = today.strftime('%B %d, %Y')
    date_stamp = today.strftime('%Y-%m-%d')

    os.makedirs(LOGS_DIR, exist_ok=True)
    changed_files = get_changed_code_files()

    log_lines = []
    log_lines.append(f"## {pretty_date}\n")

    if not changed_files:
        log_lines.append("No changes. All 30 codes match the previous run.\n")
    else:
        log_lines.append(f"{len(changed_files)} code(s) updated:\n")

        for filepath in changed_files:
            code_name = os.path.basename(filepath).replace('CA Code - ', '').replace('.txt', '')
            log_lines.append(f"### {code_name}\n")

            old_text = get_old_file(filepath)
            new_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filepath)
            with open(new_path, 'r', encoding='utf-8') as f:
                new_text = f.read()

            if old_text is None:
                log_lines.append("*New code file — no prior version.*\n")
                continue

            old_sections = parse_sections(old_text)
            new_sections = parse_sections(new_text)

            all_keys = sorted(set(old_sections) | set(new_sections),
                              key=lambda k: [float(x) if x.replace('.','',1).isdigit() else 0
                                             for x in re.split(r'[^0-9.]+', k) if x])

            modified = []
            added = []
            removed = []

            for key in all_keys:
                in_old = key in old_sections
                in_new = key in new_sections
                if in_old and in_new:
                    if old_sections[key] != new_sections[key]:
                        modified.append(key)
                elif in_new and not in_old:
                    added.append(key)
                elif in_old and not in_new:
                    removed.append(key)

            if not modified and not added and not removed:
                log_lines.append("Metadata or structural changes only (no section text changes).\n")
                continue

            if modified:
                log_lines.append(f"**Modified ({len(modified)} sections):**\n")
                for key in modified:
                    log_lines.append(f"<details>\n<summary>Section {key}</summary>\n")
                    log_lines.append("**Prior version:**\n")
                    log_lines.append(f"```\n{old_sections[key]}\n```\n")
                    log_lines.append("**New version:**\n")
                    log_lines.append(f"```\n{new_sections[key]}\n```\n")
                    log_lines.append("</details>\n")

            if added:
                log_lines.append(f"**Added ({len(added)} sections):**\n")
                for key in added:
                    log_lines.append(f"<details>\n<summary>Section {key}</summary>\n")
                    log_lines.append(f"```\n{new_sections[key]}\n```\n")
                    log_lines.append("</details>\n")

            if removed:
                log_lines.append(f"**Removed ({len(removed)} sections):**\n")
                for key in removed:
                    log_lines.append(f"<details>\n<summary>Section {key}</summary>\n")
                    log_lines.append("*Prior version (now removed):*\n")
                    log_lines.append(f"```\n{old_sections[key]}\n```\n")
                    log_lines.append("</details>\n")

    log_path = os.path.join(LOGS_DIR, f"{date_stamp}.md")
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write('\n'.join(log_lines))

    total = len([k for f in changed_files for k in ['_']])  # just the file count
    section_count = sum(1 for f in changed_files for _ in [1])
    print(f"Log written to {log_path}")
    print(f"  {len(changed_files)} code(s) changed")


if __name__ == '__main__':
    build_log()
