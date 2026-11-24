#!/usr/bin/env python3
"""Offline gates for a WoW addon folder.

usage:
  python check_addon.py <addon-folder> [--ui-source <wow-ui-source/Interface>] [--luacheck <exe>]
                        [--allow-global NAME ...] [--stub-extra file.lua ...] [--json]
  python check_addon.py --negative <addon-folder> [same options]   # prove every gate can turn red

Gates
  toc       listed files exist, ## Interface present and numeric, TOC name matches folder
  luacheck  luacheck with the addon's .luacheckrc (NOT RUN if luacheck is missing)
  compile   Lua 5.1 syntax (catches goto, //, <const>)                      needs lupa
  api       every :Method(, registered event, template and bare global call exists in the
            client's Blizzard UI source (NOT RUN without --ui-source)
  smoke     loads every TOC file on assets/stub.lua, fires login, target, combat
            enter/leave and slash commands; fails on Lua errors              needs lupa
  globals   new globals other than SavedVariables, SLASH_*, named frames, .luacheckrc globals
  secret    comparing/arithmetic/concatenating values the stub returns as secret in combat
  taint     fields written onto Blizzard-owned frames; SetAttribute/Show/Hide/SetScale on
            secure frames while in combat

Statuses: PASS, FAIL, CHECK (a call the stub does not know: either a real missing API or a
stand-in to add with --stub-extra), NOT RUN (tool or input missing; never counted as a pass).
Exit: 0 all run gates PASS · 1 a FAIL · 2 CHECK only · 3 nothing provable (all Lua gates NOT RUN).

The stub is not the game client. PASS means the addon's own logic runs offline,
never that an API exists or behaves this way in game.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

STUB = Path(__file__).resolve().parent.parent / "assets" / "stub.lua"
PASS, FAIL, NOTRUN, CHECK = "PASS", "FAIL", "NOT RUN", "CHECK"
GATES = ("toc", "luacheck", "compile", "api", "smoke", "globals", "secret", "taint")

try:
    if os.environ.get("WOW_FORGE_LUPA_PATH"):
        sys.path.insert(0, os.environ["WOW_FORGE_LUPA_PATH"])
    from lupa.lua51 import LuaRuntime, LuaError  # type: ignore
    HAVE_LUPA = True
except Exception:  # noqa: BLE001
    HAVE_LUPA = False

STUB_EXTRA = []


# --------------------------------------------------------------------------------------
# TOC
# --------------------------------------------------------------------------------------
def find_toc(folder: Path):
    tocs = sorted(folder.glob("*.toc"))
    main = folder / f"{folder.name}.toc"
    if main in tocs:
        return main, tocs
    return (tocs[0] if tocs else None), tocs


def parse_toc(toc: Path):
    fields, files = {}, []
    for raw in toc.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("##"):
            m = re.match(r"##\s*([^:]+):\s*(.*)", line)
            if m:
                fields[m.group(1).strip()] = m.group(2).strip()
            continue
        if line.startswith("#"):
            continue
        line = re.sub(r"\s*\[[^\]]*\]\s*", "", line)
        files.append(line.replace("\\", "/"))
    return fields, files


def saved_variables(fields):
    out = []
    for key in ("SavedVariables", "SavedVariablesPerCharacter"):
        out += [s.strip() for s in fields.get(key, "").split(",") if s.strip()]
    return out


def gate_toc(folder: Path, toc, tocs):
    if toc is None:
        return FAIL, ["no .toc file in folder"]
    problems = []
    if toc.stem != folder.name and not toc.stem.startswith(folder.name + "_"):
        problems.append(f"TOC name {toc.name} does not match folder {folder.name} (the client ignores it)")
    for t in tocs:
        fields, files = parse_toc(t)
        if "Interface" not in fields:
            problems.append(f"{t.name}: no ## Interface line")
        elif not re.fullmatch(r"\d{4,6}(\s*,\s*\d{4,6})*", fields["Interface"]):
            problems.append(f"{t.name}: Interface '{fields['Interface']}' is not numeric")
        for f in files:
            if not (folder / f).is_file():
                problems.append(f"{t.name}: listed file missing: {f}")
        if not files:
            problems.append(f"{t.name}: lists no files")
    return (FAIL if problems else PASS), problems


# --------------------------------------------------------------------------------------
# luacheck
# --------------------------------------------------------------------------------------
def gate_luacheck(folder: Path, exe):
    exe = exe or shutil.which("luacheck")
    if not exe:
        return NOTRUN, ["luacheck not found (install it or pass --luacheck <exe>)"]
    cmd = [exe, str(folder), "--no-cache", "--codes"]
    cfg = folder / ".luacheckrc"
    cmd += ["--config", str(cfg)] if cfg.is_file() else ["--std", "lua51"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    except Exception as e:  # noqa: BLE001
        return NOTRUN, [f"luacheck could not run: {e}"]
    if r.returncode == 0:
        return PASS, []
    out = (r.stdout + r.stderr).strip().splitlines()
    hits = [l.strip() for l in out if re.search(r":\d+:\d+:", l)]
    return FAIL, hits[:40] or out[-10:]


def luacheck_globals(folder: Path):
    cfg = folder / ".luacheckrc"
    if not cfg.is_file():
        return []
    m = re.search(r"(?<![\w])globals\s*=\s*\{([^}]*)\}", cfg.read_text(encoding="utf-8", errors="replace"))
    return re.findall(r'"([^"]+)"', m.group(1)) if m else []


# --------------------------------------------------------------------------------------
# API gate against the client's Blizzard UI source
# --------------------------------------------------------------------------------------
_API_CACHE = {}


def known_names(ui_source: Path):
    key = str(ui_source)
    if key in _API_CACHE:
        return _API_CACHE[key]
    names, events, templates, deprecated = set(), set(), set(), set()
    for p in ui_source.rglob("*.lua"):
        t = p.read_text(encoding="utf-8", errors="replace")
        if "deprecat" in str(p).lower():
            # Compatibility shims: may not be loaded in game (measured on Forever:
            # CombatLogGetCurrentEventInfo is defined here and was nil in the client).
            deprecated.update(re.findall(r"^\s*([A-Za-z_]\w*)\s*=", t, re.M))
            deprecated.update(re.findall(r"\bfunction\s+([A-Za-z_]\w*)\s*\(", t))
            continue
        names.update(re.findall(r'\bName = "(\w+)"', t))
        events.update(re.findall(r'\bLiteralName = "(\w+)"', t))
        names.update(re.findall(r"\bfunction\s+(?:[\w\.]+[\.:])?(\w+)\s*\(", t))
        names.update(re.findall(r"[:\.](\w+)\s*\(", t))          # call sites: C-side widget methods
        names.update(re.findall(r"\b([A-Z]\w+)\s*\(", t))         # bare global calls
        names.update(re.findall(r"^\s*([A-Z]\w+)\s*=", t, re.M))  # global tables/constants
        events.update(re.findall(r'RegisterEvent\(\s*"(\w+)"', t))
    for p in ui_source.rglob("*.xml"):
        t = p.read_text(encoding="utf-8", errors="replace")
        templates.update(re.findall(r'\bname="(\w+)"', t))
        names.update(re.findall(r"[:\.](\w+)\s*\(", t))
    _API_CACHE[key] = (names, events, templates, deprecated)
    return _API_CACHE[key]


LUA_BUILTINS = set("""assert error ipairs next pairs pcall print rawequal rawget rawset select setmetatable
getmetatable tonumber tostring type unpack xpcall loadstring require""".split())


def gate_api(folder: Path, files, ui_source):
    if not ui_source:
        return NOTRUN, ["pass --ui-source <path to the client's wow-ui-source Interface folder> to check API names"]
    src = Path(ui_source)
    if not src.is_dir():
        return NOTRUN, [f"--ui-source is not a folder: {src}"]
    names, events, templates, deprecated = known_names(src)
    if len(names) < 1000:
        return NOTRUN, [f"--ui-source looks incomplete ({len(names)} names found)"]
    code = "\n".join((folder / f).read_text(encoding="utf-8-sig", errors="replace")
                     for f in files if f.lower().endswith(".lua") and (folder / f).is_file())
    xml = "\n".join((folder / f).read_text(encoding="utf-8-sig", errors="replace")
                    for f in files if f.lower().endswith(".xml") and (folder / f).is_file())
    code_nc = re.sub(r"--\[\[.*?\]\]|--[^\n]*", "", code, flags=re.S)
    code_nc = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', '""', code_nc)    # strings out for call scan
    own = set(re.findall(r"\bfunction\s+(?:[\w\.]+[\.:])?(\w+)\s*\(", code))
    own |= set(re.findall(r"[\.:](\w+)\s*=\s*function", code))
    own |= set(re.findall(r"\blocal\s+(?:function\s+)?(\w+)", code))
    own |= set(re.findall(r"[\.\[\"'](\w+)[\"'\]]?\s*=", code))
    own |= set(re.findall(r'\b(?:name|parentKey|parentArray)="(\w+)"', xml))
    unknown = []
    for m in sorted(set(re.findall(r":([A-Z]\w*)\s*\(", code_nc))):
        if m not in names and m not in own:
            unknown.append(f"method :{m}()")
    for g in sorted(set(re.findall(r"(?<![\w\.:])([A-Z]\w*)\s*\(", code_nc))):
        if g in own or g in LUA_BUILTINS:
            continue
        if g not in names and g in deprecated:
            unknown.append(f"global {g}() exists only in a Blizzard deprecation shim (may be absent in game; use the replacement)")
        elif g not in names:
            unknown.append(f"global {g}()")
    for e in sorted(set(re.findall(r'Register(?:Unit)?Event\(\s*"(\w+)"', code))):
        if e not in events:
            unknown.append(f"event {e}")
    for t in sorted(set(re.findall(r'CreateFrame\([^)]*?"(\w*Template\w*)"', code))):
        for part in t.split(","):
            if part.strip() and part.strip() not in templates and part.strip() not in own:
                unknown.append(f"template {part.strip()}")
    if unknown:
        return FAIL, [u + " - not in the client's UI source" if "shim" not in u else u for u in unknown[:40]]
    return PASS, []


# --------------------------------------------------------------------------------------
# Lua runtime gates
# --------------------------------------------------------------------------------------
def lua_files(folder: Path, files):
    return [f for f in files if f.lower().endswith(".lua") and (folder / f).is_file()]


def gate_compile(folder: Path, files):
    if not HAVE_LUPA:
        return NOTRUN, ["lupa not installed (pip install lupa)"]
    lua = LuaRuntime(unpack_returned_tuples=True)
    check = lua.eval("function(src, name) local f, err = loadstring(src, name) return err end")
    problems = []
    for f in lua_files(folder, files):
        err = check((folder / f).read_text(encoding="utf-8-sig", errors="replace"), "@" + f)
        if err:
            problems.append(str(err))
    return (FAIL if problems else PASS), problems


SMOKE = r"""
local harness, addonName, sources, names, toc, svNames = ...
harness.toc = toc
local ns = {}
local before = {}
for k in pairs(_G) do before[k] = true end
for i = 1, #sources do
    local chunk, err = loadstring(sources[i], "@" .. names[i])
    if not chunk then
        harness.errors[#harness.errors + 1] = err
    else
        local ok, e = pcall(chunk, addonName, ns)
        if not ok then harness.errors[#harness.errors + 1] = e end
    end
end
local function step(ev, ...) harness.fire(ev, ...); harness.flush() end
step("ADDON_LOADED", addonName)
step("SPELLS_CHANGED")
step("PLAYER_LOGIN")
step("SETTINGS_LOADED")
step("PLAYER_ENTERING_WORLD", true, false)
step("PLAYER_TARGET_CHANGED")
step("UNIT_HEALTH", "target")
harness.update(0.5)
harness.combat = true
step("PLAYER_REGEN_DISABLED")
step("PLAYER_TARGET_CHANGED")
step("UNIT_HEALTH", "player"); step("UNIT_MAXHEALTH", "player")
step("UNIT_HEALTH", "target"); step("UNIT_MAXHEALTH", "target")
step("UNIT_POWER_UPDATE", "player", "MANA"); step("UNIT_POWER_FREQUENT", "player", "MANA")
step("UNIT_AURA", "player"); step("UNIT_AURA", "target")
step("SPELL_UPDATE_COOLDOWN"); step("ACTIONBAR_UPDATE_COOLDOWN"); step("UNIT_SPELLCAST_START", "player")
step("UNIT_COMBAT", "player", "WOUND", "", harness.SECRET, 1)
harness.update(0.5)
harness.combat = false
step("PLAYER_REGEN_ENABLED")
local slashKeys = {}
for k in pairs(SlashCmdList) do slashKeys[#slashKeys + 1] = k end
table.sort(slashKeys)
for _, k in ipairs(slashKeys) do harness.slash(k, ""); harness.slash(k, "help") end
harness.flush()
local after, allowed = {}, {}
for i = 1, #svNames do allowed[svNames[i]] = true end
for k in pairs(_G) do
    if not before[k] and type(k) == "string" and not allowed[k]
        and not harness.named[k] and not k:match("^SLASH_") and not k:match("^BINDING_")
        and not (harness.autoNamespaces and harness.autoNamespaces[k]) then
        after[#after + 1] = k
    end
end
table.sort(after)
return harness.errors, after, harness.blizzWrites, harness.protectedInCombat
"""


def lua_list(t):
    return [str(t[i]) for i in range(1, len(t) + 1)]


def run_smoke(folder: Path, toc_fields, files, allow):
    lua = LuaRuntime(unpack_returned_tuples=True)
    harness = lua.execute(STUB.read_text(encoding="utf-8"))
    for extra in STUB_EXTRA:
        lua.execute(Path(extra).read_text(encoding="utf-8"), harness)
    names = lua_files(folder, files)
    sources = [(folder / f).read_text(encoding="utf-8-sig", errors="replace") for f in names]
    sv = saved_variables(toc_fields) + list(allow) + luacheck_globals(folder)
    smoke = lua.execute("return function(...) " + SMOKE + " end")
    errors, leaked, writes, prot = smoke(harness, folder.name, lua.table_from(sources), lua.table_from(names),
                                         lua.table_from(dict(toc_fields)), lua.table_from(sv))
    return lua_list(errors), lua_list(leaked), lua_list(writes), lua_list(prot)


GAP = re.compile(r"attempt to call (?:global|field|method) '(\w+)' \(a nil value\)|hooksecurefunc: (\w+) is not a function")


def stub_gap(msg: str):
    m = GAP.search(msg)
    if not m:
        return None
    name = m.group(1) or m.group(2)
    return name if name[:1].isupper() or name.startswith("C_") else None


def is_secret_error(msg: str) -> bool:
    return "secret value" in msg or bool(re.search(r"attempt to (compare|perform arithmetic on|concatenate) .*table", msg))


def gate_runtime(folder: Path, toc_fields, files, allow):
    if not HAVE_LUPA:
        r = (NOTRUN, ["lupa not installed (pip install lupa)"])
        return r, r, r, r
    try:
        errs, leaks, writes, prot = run_smoke(folder, toc_fields, files, allow)
    except LuaError as e:
        skip = (NOTRUN, ["smoke did not finish"])
        return (FAIL, [f"harness crashed: {e}"]), skip, skip, skip
    secret = [e for e in errs if is_secret_error(e)]
    gaps = sorted({stub_gap(e) for e in errs if stub_gap(e)})
    other = [e for e in errs if not is_secret_error(e) and not stub_gap(e)]
    if other:
        smoke = FAIL, other[:20] + ([f"(also not in stub: {', '.join(gaps)})"] if gaps else [])
    elif gaps:
        smoke = CHECK, [f"not in stub: {g} - if {g} is missing in the target client this is a real bug; "
                        f"otherwise add a stand-in with --stub-extra" for g in gaps]
    else:
        smoke = PASS, []
    sv = set(saved_variables(toc_fields))
    glob_notes = []
    for g in leaks:
        hint = " (looks like SavedVariables: declare it in the TOC)" if g.endswith("DB") and g not in sv else ""
        glob_notes.append(f"new global: {g}{hint}")
    glob = (FAIL if leaks else PASS), glob_notes[:40]
    sec = (FAIL if secret else PASS), secret[:20]
    taint_notes = [f"field written on Blizzard frame: {w}" for w in sorted(set(writes))]
    taint_notes += sorted(set(prot))
    taint = (FAIL if taint_notes else PASS), taint_notes[:30]
    return smoke, glob, sec, taint


def run_all(folder: Path, opts):
    toc, tocs = find_toc(folder)
    results = {"toc": gate_toc(folder, toc, tocs)}
    fields, files = parse_toc(toc) if toc else ({}, [])
    results["luacheck"] = gate_luacheck(folder, opts.get("luacheck"))
    results["compile"] = gate_compile(folder, files)
    results["api"] = gate_api(folder, files, opts.get("ui_source"))
    if results["compile"][0] == FAIL:
        skip = (NOTRUN, ["skipped: compile failed"])
        for g in ("smoke", "globals", "secret", "taint"):
            results[g] = skip
    else:
        (results["smoke"], results["globals"], results["secret"],
         results["taint"]) = gate_runtime(folder, fields, files, opts.get("allow", ()))
    return results


def print_results(folder, results):
    print(f"wow-forever-addon-creator check: {folder}")
    for name in GATES:
        status, notes = results[name]
        print(f"  {status:8} {name}")
        for n in notes:
            print(f"           - {n}")
    print("  note: offline PASS proves the addon's own logic runs on a stub, not that it works in game.")


def exit_code(results):
    statuses = [s for s, _ in results.values()]
    if FAIL in statuses:
        return 1
    if CHECK in statuses:
        return 2
    if all(results[k][0] == NOTRUN for k in ("compile", "smoke", "globals", "secret", "taint")):
        return 3
    return 0


# --------------------------------------------------------------------------------------
# Negative arms: break a temp copy, the named gate must turn red.
# --------------------------------------------------------------------------------------
def arms(folder: Path):
    toc, _ = find_toc(folder)
    fields, files = parse_toc(toc)
    luas = lua_files(folder, files)
    if not luas:
        return None
    first, last = luas[0], luas[-1]
    login = ('\nlocal forgeNeg = CreateFrame("Frame")\nforgeNeg:RegisterEvent("PLAYER_LOGIN")\n'
             'forgeNeg:SetScript("OnEvent", function() {body} end)\n')
    return [
        ("compile", "goto (Lua 5.2 syntax)", first, "\ngoto skip\n::skip::\n"),
        ("luacheck", "unused local variable", last, "\nlocal forgeUnusedLocal = 1\n"),
        ("api", "invented widget method", last, "\nlocal function forgeApiArm() UIParent:ForgeNoSuchMethod() end\n"),
        ("globals", "stray global", last, "\nForgeNegativeLeak = 1\n"),
        ("smoke", "error in login handler", last, login.format(body='error("negative arm: boom")')),
        ("secret", "compare a secret health value", last,
         '\nlocal forgeSec = CreateFrame("Frame")\nforgeSec:RegisterEvent("PLAYER_REGEN_DISABLED")\n'
         'forgeSec:SetScript("OnEvent", function() if UnitHealth("player") < 1 then return end end)\n'),
        ("taint", "field on a Blizzard button through a local", last,
         login.format(body='local b = _G["ActionButton" .. 1]; b.forgeFlag = true')),
        ("toc", "missing listed file", toc.name, "\nForgeMissingFile.lua\n"),
    ]


def negative(folder: Path, opts):
    base = run_all(folder, opts)
    print_results(folder, base)
    if exit_code(base) == 1:
        print("negative: base run has a FAIL; fix it first (a red base proves nothing about the arms).")
        return 1
    if exit_code(base) == 3:
        print("negative: cannot run the arms, the Lua gates are NOT RUN (install lupa).")
        return 3
    plan = arms(folder)
    if plan is None:
        print("negative: the TOC lists no Lua files, nothing to break.")
        return 3
    escaped, unproven = [], []
    for gate, label, target, append in plan:
        if base[gate][0] == NOTRUN:
            print(f"  NOT RUN  {gate:8} <- {label} (gate not runnable here, arm unproven)")
            unproven.append(label)
            continue
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / folder.name
            shutil.copytree(folder, copy)
            p = copy / target
            p.write_text(p.read_text(encoding="utf-8-sig", errors="replace") + append, encoding="utf-8", newline="\n")
            res = run_all(copy, opts)
        status = res[gate][0]
        if status == FAIL:
            print(f"  red      {gate:8} <- {label}")
        elif status == NOTRUN:
            print(f"  NOT RUN  {gate:8} <- {label} (arm unproven)")
            unproven.append(label)
        else:
            print(f"  NEGATIVE ESCAPED {gate} <- {label}")
            escaped.append(label)
    total = len(plan)
    print(f"negative: {total - len(escaped) - len(unproven)}/{total} red, {len(unproven)} unproven, {len(escaped)} escaped")
    if escaped:
        return 1
    return 3 if unproven else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder")
    ap.add_argument("--negative", action="store_true")
    ap.add_argument("--luacheck")
    ap.add_argument("--ui-source", help="the client's Blizzard UI source Interface folder (e.g. wow-ui-source on the matching branch)")
    ap.add_argument("--allow-global", action="append", default=[])
    ap.add_argument("--stub-extra", action="append", default=[], help="extra Lua stand-ins run after the stub (receives harness as ...)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    STUB_EXTRA.extend(a.stub_extra)
    folder = Path(a.folder).resolve()
    if not folder.is_dir():
        print(f"not a folder: {folder}", file=sys.stderr)
        return 1
    opts = {"luacheck": a.luacheck, "ui_source": a.ui_source, "allow": a.allow_global}
    if a.negative:
        return negative(folder, opts)
    results = run_all(folder, opts)
    if a.json:
        print(json.dumps({k: {"status": s, "notes": n} for k, (s, n) in results.items()}, indent=2))
    else:
        print_results(folder, results)
    return exit_code(results)


if __name__ == "__main__":
    sys.exit(main())
