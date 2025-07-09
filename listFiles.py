#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path
from collections import defaultdict

# — Customize these if needed —
GITHUB_PREFIX = "https://github.com/peoczr2/VoiceAgent/blob/main/"
OUTPUT_FILE   = "FILE_LIST.md"
TITLE         = "# Project File Index\n\n"

def get_all_files_not_ignored():
    """
    Runs:
      git ls-files --cached --others --exclude-standard
    to get both tracked and untracked files, minus anything in .gitignore.
    """
    try:
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
    except subprocess.CalledProcessError as e:
        print("Error running git:", e.stderr, file=sys.stderr)
        sys.exit(1)

    return [line for line in result.stdout.splitlines() if line.strip()]

def group_by_folder(file_paths):
    """
    Returns a dict mapping folder paths (as strings) to lists of file paths.
    The repo root is represented by the empty string "".
    """
    groups = defaultdict(list)
    for relpath in file_paths:
        folder = str(Path(relpath).parent)
        # Normalize root folder to empty string
        if folder == ".":
            folder = ""
        groups[folder].append(relpath)
    return groups

def write_markdown(groups, out_path: Path):
    """
    Writes the grouped file list to Markdown, using headers for each folder.
    """
    with out_path.open("w", encoding="utf-8") as md:
        md.write(TITLE)
        for folder in sorted(groups):
            header = folder or "./"
            md.write(f"## `{header}`\n\n")
            for relpath in sorted(groups[folder]):
                url = f"{GITHUB_PREFIX}{relpath}"
                md.write(f"- [{relpath}]({url})\n")
            md.write("\n")

if __name__ == "__main__":
    files = get_all_files_not_ignored()
    if not files:
        print("No files found (or none outside .gitignore).")
        sys.exit(0)

    groups = group_by_folder(files)
    out = Path(OUTPUT_FILE)
    write_markdown(groups, out)
    print(f"✅ Generated {out!s} with {len(files)} entries across {len(groups)} folders.")
