#!/usr/bin/env python3
"""Static red-flag scan for WoW addon Lua. Hits are LEADS for a reviewer, not verdicts.

usage: python review_scan.py <addon-folder> [--json] [--modern | --classic]

--modern (default): the target is a modern Mainline-family client (Retail 12.x, WoW Forever),
so combat-log registration and removed globals are flagged as blockers.
--classic: those two rules drop to "check" (older clients still have some of these APIs).
Exit code is always 0 unless the folder is missing; read the findings.
"""
import argparse
import json
import re
import sys
from pathlib import Path

BLIZZ_FRAME = r"(?:ActionButton\d*|MultiBar\w*Button\d*|PetActionButton\d*|StanceButton\d*|PlayerFrame|TargetFrame|FocusFrame|PartyMemberFrame\d*|MainMenuBar\w*|MainActionBar\w*|PlayerCastingBarFrame|CastingBarFrame|Minimap\w*|ContainerFrame\d*|GameTooltip|ChatFrame\d+)"
REMOVED = ("GetAddOnMetadata", "GetSpellInfo", "GetSpellCooldown", "UnitAura", "UnitBuff", "UnitDebuff",
           "GetItemCount", "GetItemInfo", "GetCoinTextureString", "InterfaceOptions_AddCategory",
           "CombatLogGetCurrentEventInfo", "GetSpellTexture")
PROTECTED_CALLS = ("SetAttribute", "SetOverrideBinding", "SetOverrideBindingClick", "ClearOverrideBindings",
                   "RegisterStateDriver", "UnregisterStateDriver", "SecureHandlerSetFrameRef")
SECRET_SOURCES = r"(?:UnitHealth|UnitHealthMax|UnitPower|UnitPowerMax|UnitGetTotalAbsorbs|UnitGetIncomingHeals)"

RULES = []


def rule(rid, severity, pattern, message, flags=0):
    RULES.append((rid, severity, re.compile(pattern, flags), message))


rule("cleu", "blocker", r"RegisterEvent\(\s*[\"']COMBAT_LOG_EVENT(?:_UNFILTERED)?[\"']",
     "registers the combat log; modern clients block or starve this (use UNIT_COMBAT / UNIT_SPELLCAST_*)")
rule("blizzard-field", "blocker", BLIZZ_FRAME + r"\s*\.\s*(?!Show\b|Hide\b)(\w+)\s*=(?!=)",
     "writes a field onto a Blizzard frame; keep state in your own table keyed by the frame (taint)")
rule("blizzard-field-dyn", "blocker", r"_G\[\s*[\"'](?:ActionButton|MultiBar\w*Button|PetActionButton)[\"']\s*\.\.[^\]]*\]\s*\.\s*(\w+)\s*=(?!=)",
     "writes a field onto a Blizzard button found through _G; use a side table (taint)")
rule("or-true", "major", r"\b([\w\.\[\]\"']+)\s*=\s*\1\s+or\s+true\b",
     "`x = x or true` turns a saved false back into true; nil-check the default instead")
rule("lua52", "blocker", r"(?:^|\s)goto\s+\w+|::\w+::|\w\s*//\s*\w|<const>|<close>|\butf8\.|\btable\.unpack\b|\bstring\.pack\b",
     "Lua 5.2+ syntax or library; the client runs Lua 5.1")
rule("secret-concat", "major", r"\.\.\s*" + SECRET_SOURCES + r"\s*\(|" + SECRET_SOURCES + r"\s*\([^)]*\)\s*\.\.",
     "concatenates a value that can be secret in combat; use SetFormattedText + BreakUpLargeNumbers")
rule("secret-compare", "major", SECRET_SOURCES + r"\s*\([^)]*\)\s*(?:[<>]=?|==|~=)\s*[\w\d]",
     "compares a value that can be secret in combat; guard with issecretvalue or use a curve")
rule("secret-arith", "major", SECRET_SOURCES + r"\s*\([^)]*\)\s*[\+\-\*/%^]|[\+\-\*/%^]\s*" + SECRET_SOURCES + r"\s*\(",
     "arithmetic on a value that can be secret in combat; use UnitHealthPercent with a curve or guard with issecretvalue")
rule("protected-in-combat-event", "check", r"PLAYER_REGEN_DISABLED",
     "work triggered by entering combat: anything protected here (SetAttribute, secure Show/SetPoint, bindings) is refused; check what this handler does")
rule("and-or-false", "check", r"\band\s+[\w\.]+\s+or\s+nil\b",
     "`x and r or nil` returns nil when r is false; use an explicit if for boolean results")
rule("global-function", "minor", r"^function\s+([A-Z]\w*)\s*\(",
     "defines a global function; prefer `local function` or the addon namespace")
rule("replace-function", "major", r"^\s*([A-Z]\w*(?:[\.:]\w+)?)\s*=\s*function\b",
     "assigns a function to a global or field; if it is Blizzard's, use hooksecurefunc instead (replacing taints)")


def scan_file(path: Path, rel: str, modern: bool):
    findings = []
    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    in_block = False
    for i, raw in enumerate(lines, 1):
        line = raw
        if in_block:
            if "]]" in line:
                in_block = False
                line = line.split("]]", 1)[1]
            else:
                continue
        if "--[[" in line and "]]" not in line.split("--[[", 1)[1]:
            in_block = True
            line = line.split("--[[", 1)[0]
        code = re.sub(r"--.*$", "", line)
        if not code.strip():
            continue
        for rid, sev, rx, msg in RULES:
            if rx.search(code):
                if rid in ("secret-compare", "secret-concat", "secret-arith") and "issecretvalue" in code:
                    continue
                if rid == "protected-in-combat-event" and not re.search(r"RegisterEvent|==\s*[\"']PLAYER_REGEN_DISABLED", code):
                    continue
                if rid in ("global-function", "replace-function"):
                    name = rx.search(code).group(1)
                    base = re.split(r"[\.:]", name)[0]
                    if re.fullmatch(r"[A-Z0-9_]+", name) or base == "SlashCmdList":
                        continue   # event-handler table keys and slash handlers are expected
                    if re.search(r"^\s*local\s+(?:[\w,\s]*\b)?" + re.escape(base) + r"\b", "\n".join(lines[:i - 1]), re.M):
                        continue   # forward-declared local, not a global
                if rid == "cleu" and not modern:
                    sev = "check"
                findings.append({"file": rel, "line": i, "rule": rid, "severity": sev, "message": msg, "code": raw.strip()[:160]})
        for name in REMOVED:
            if re.search(r"(?<![\w\.:])" + name + r"\s*\(", code):
                findings.append({"file": rel, "line": i, "rule": "removed-global",
                                 "severity": "blocker" if modern else "check",
                                 "message": f"{name} is removed or moved to a C_ namespace on modern clients; verify in the target client's source",
                                 "code": raw.strip()[:160]})
        for name in PROTECTED_CALLS:
            if re.search(r"[:\.]?\b" + name + r"\s*\(", code):
                window = "\n".join(lines[max(0, i - 25):i])
                if not re.search(r"InCombatLockdown|AfterCombat|PLAYER_REGEN_ENABLED|combatQueue", window):
                    findings.append({"file": rel, "line": i, "rule": "protected-unguarded", "severity": "major",
                                     "message": f"{name} with no combat guard in the previous 25 lines; protected in combat",
                                     "code": raw.strip()[:160]})
        if "SetScript" in code and "OnUpdate" in code and not re.search(r"OnUpdate[\"']\s*,\s*nil", code):
            window = "\n".join(lines[i - 1:i + 6])
            if not re.search(r"elapsed|throttle|acc|since|GetTime|\bdt\b|\bel\b", window, re.I):
                findings.append({"file": rel, "line": i, "rule": "onupdate-unthrottled", "severity": "minor",
                                 "message": "OnUpdate without an obvious throttle; throttle or hide the frame when idle",
                                 "code": raw.strip()[:160]})
    return findings


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder")
    ap.add_argument("--json", action="store_true")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--modern", action="store_true", default=True)
    g.add_argument("--classic", action="store_true")
    a = ap.parse_args()
    folder = Path(a.folder).resolve()
    if not folder.is_dir():
        print(f"not a folder: {folder}", file=sys.stderr)
        return 1
    modern = not a.classic
    files = sorted(p for p in folder.rglob("*.lua") if not any(part.lower() in ("libs", "lib", ".release") for part in p.parts))
    findings = []
    for p in files:
        findings += scan_file(p, p.relative_to(folder).as_posix(), modern)
    order = {"blocker": 0, "major": 1, "check": 2, "minor": 3}
    findings.sort(key=lambda f: (order[f["severity"]], f["file"], f["line"]))
    if a.json:
        print(json.dumps(findings, indent=2, ensure_ascii=False))
        return 0
    print(f"review_scan: {folder}  ({len(files)} Lua files, {len(findings)} leads, target={'modern' if modern else 'classic'})")
    for f in findings:
        print(f"  [{f['severity']:7}] {f['file']}:{f['line']}  {f['rule']}: {f['message']}")
        print(f"             {f['code']}")
    print("  leads only: confirm each by reading the code; false positives are expected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
