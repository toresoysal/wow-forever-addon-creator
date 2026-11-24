#!/usr/bin/env python3
"""Scaffold a WoW addon from assets/template.

usage: python new_addon.py <AddonName> --interface <N> [--out <dir>] [--author A] [--notes N]

The interface number must come from the target client:  /run print(select(4, GetBuildInfo()))
"""
import argparse
import re
import shutil
import sys
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "template"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("name", help="addon folder/TOC name, letters, digits and _ only")
    ap.add_argument("--interface", required=True, help="interface number(s) measured in the client, e.g. 16001 or '120007, 16001'")
    ap.add_argument("--out", default=".", help="parent directory for the new addon folder")
    ap.add_argument("--author", default="Unknown")
    ap.add_argument("--notes", default="")
    a = ap.parse_args()

    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{1,40}", a.name):
        print("name must start with a letter and contain only letters, digits and _", file=sys.stderr)
        return 1
    if not re.fullmatch(r"\d{4,6}(\s*,\s*\d{4,6})*", a.interface.strip()):
        print("interface must be one or more numbers, e.g. 16001", file=sys.stderr)
        return 1

    dest = Path(a.out).resolve() / a.name
    if dest.exists():
        print(f"refusing to overwrite existing {dest}", file=sys.stderr)
        return 1

    subs = {
        "__UPPER__": a.name.upper(),
        "__NAME__": a.name,
        "__INTERFACE__": a.interface.strip(),
        "__AUTHOR__": a.author,
        "__NOTES__": a.notes or f"{a.name} addon",
    }

    dest.mkdir(parents=True)
    for src in sorted(TEMPLATE.iterdir()):
        target_name = src.name
        for k, v in subs.items():
            target_name = target_name.replace(k, v)
        text = src.read_text(encoding="utf-8")
        for k, v in subs.items():
            text = text.replace(k, v)
        (dest / target_name).write_text(text, encoding="utf-8", newline="\n")
    (dest / "Media").mkdir()

    tokens = list(subs)
    left = [p.name for p in dest.iterdir() if p.is_file() and any(t in p.read_text(encoding="utf-8") for t in tokens)]
    if left:
        print("placeholder left in: " + ", ".join(left), file=sys.stderr)
        shutil.rmtree(dest)
        return 1
    print(f"created {dest}")
    print(f"next: python {Path(__file__).with_name('check_addon.py')} \"{dest}\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
