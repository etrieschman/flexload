#!/usr/bin/env python3
"""Render layers.yaml into a self-contained, filterable HTML view.

Usage:  python3 render.py [--out index.html]

Reads schema.yaml for field order and vocabularies, layers.yaml for records.
Validates enum fields against the schema and reports violations rather than
silently rendering them.

LaTeX in `base` and `rate` is typeset with KaTeX, loaded from a CDN. That is
the one external dependency; if it fails to load the page falls back to showing
the raw TeX, so the file is still readable offline.
"""

import argparse
import html
import re
import json
import pathlib
import sys

import yaml

HERE = pathlib.Path(__file__).parent
TODO = "TODO"

# Fields that count toward extraction progress (identity is free, notes optional).
PROGRESS_FIELDS = [
    "base", "base_type", "measurement_window", "billing_window", "determinacy",
    "pool", "rate", "rate_type", "exact_recovery", "true_up",
]
SOURCE_FIELDS = ["document", "section", "effective_date", "quote", "url"]

# Layer names are slugs so they can be keys. These are what a reader should see.
LAYER_LABELS = {
    "energy_congestion": "Energy & Congestion",
    "marginal_losses": "Marginal Losses",
    "scarcity_adder": "Scarcity Adder",
    "ancillary_services": "Ancillary Services",
    "reactive_supply": "Reactive Supply",
    "black_start": "Black Start",
    "uplift": "Uplift",
    "ruc_capacity_short": "Reliability Commitment Shortfall",
    "emergency_response_service": "Emergency Response Service",
    "firm_fuel_supply": "Firm Fuel Supply",
    "capacity_obligation": "Capacity Obligation",
    "transmission_network_service": "Transmission Network Service",
    "interconnection_upgrade_assignment": "Interconnection Upgrade Assignment",
    "regional_project_cost_allocation": "Regional Project Cost Allocation",
    "rmr": "Reliability Must-Run",
    "iso_admin": "System Administration",
    "arr_ftr_allocation": "Congestion Rights Allocation",
    "loss_congestion_surplus_credit": "Loss & Congestion Surplus Credit",
}

VOCAB_LABELS = {
    "metered_energy": "Metered Energy",
    "coincident_peak": "Coincident Peak",
    "non_coincident_peak": "Non-Coincident Peak",
    "contracted_capacity": "Contracted Capacity",
    "deviation": "Deviation",
    "fixed": "Fixed",
    "absent": "Absent",
    "absorbed": "Absorbed",
    "market_clearing": "Market Clearing",
    "average_cost": "Average Cost",
    "posted": "Posted",
    "direct_assignment": "Direct Assignment",
    "yes": "Yes",
    "no": "No",
    "present": "Charged",
    "absent": "No such charge",
    "absorbed": "Charged elsewhere",
    "qse": "Scheduling entity",
    "dsp": "Distribution utility",
    "lse": "Load serving entity",
    "contemporaneous": "Known as it happens",
    "retrospective": "Known only afterwards",
    "historical": "Fixed by an earlier period",
    "n/a": "Not applicable",
    "pjm": "PJM",
    "ercot": "ERCOT",
    "caiso": "CAISO",
    "miso": "MISO",
    "nyiso": "NYISO",
    "isone": "ISO-NE",
    "spp": "SPP",
}

FIELD_HELP = (
    "Fields counts the eight substantive entries: base, base type, window, "
    "pool, rate, rate type, exact recovery and true-up. Sources counts the "
    "five citation entries: document, section, effective date, quote and link."
)


def load():
    """schema.yaml also supplies the on-page glossary."""
    schema = yaml.safe_load((HERE / "schema.yaml").read_text(encoding="utf-8"))
    data = yaml.safe_load((HERE / "layers.yaml").read_text(encoding="utf-8"))
    return schema, data["records"]


def is_todo(v):
    """Only the literal sentinel counts as unextracted. An explicit null means
    the field genuinely does not apply to this layer - which is a finding, not
    a gap, and must not be counted against extraction progress."""
    return isinstance(v, str) and v.strip() == TODO


def validate(schema, records):
    """Enum violations and redirect integrity. The point is to catch vocabulary
    drift during extraction, not to police prose."""
    vocabs = schema["vocabularies"]
    enum_fields = {
        f["name"]: f["vocab"]
        for f in schema["fields"]
        if f.get("type") == "enum"
    }
    problems, seen = [], set()
    ids = {r.get("id") for r in records}
    for r in records:
        rid = r.get("id", "<no id>")
        if rid in seen:
            problems.append((rid, "duplicate id"))
        seen.add(rid)
        # When nothing is charged there is no base and no rate, so their type
        # fields are legitimately null.
        present = r.get("status", "present") == "present"
        for field, vocab_name in enum_fields.items():
            val = r.get(field)
            if is_todo(val):
                continue
            if val is None and (
                field in ("base_type", "rate_type") and not present
            ):
                continue
            vocab = vocabs[vocab_name]
            allowed = list(vocab) if isinstance(vocab, (list, dict)) else []
            if str(val) not in [str(a) for a in allowed]:
                problems.append(
                    (rid, f"{field}={val!r} not in vocabulary '{vocab_name}'")
                )

        # An absorbed layer that points nowhere has quietly vanished from the
        # inventory, which is exactly what `redirect` exists to prevent.
        absorbed = r.get("status") == "absorbed"
        target = r.get("redirect")
        if absorbed and not target:
            problems.append((rid, "marked absorbed but has no redirect"))
        if target and target not in ids:
            problems.append((rid, f"redirect={target!r} matches no record id"))
        if target and not absorbed:
            problems.append((rid, "has a redirect but is not marked absorbed"))

        # Symbols in a formula that nobody defines are the main way these
        # records go stale, so flag formulas with no definitions at all. Units
        # are checked too - `window` does not imply them, so an undeclared unit
        # is genuinely ambiguous.
        for f, d in (("base", "base_definitions"), ("rate", "rate_definitions")):
            val = r.get(f)
            if not val or is_todo(val):
                continue
            entries = r.get(d) or []
            if not entries:
                problems.append((rid, f"{f} is a formula but {d} is empty"))
                continue
            for e in entries:
                if not e.get("unit"):
                    problems.append(
                        (rid, f"{d}: {e.get('symbol', '?')} has no unit")
                    )
                if not str(e.get("symbol") or "").strip():
                    problems.append((rid, f"{d}: an entry has no symbol"))
                if not str(e.get("definition") or "").strip():
                    problems.append(
                        (rid, f"{d}: {e.get('symbol', '?')} has no definition")
                    )
            problems += undefined_symbols(rid, f, val, entries)

        # A base the charge never refers to is a determinant that does no work.
        if r.get("status") == "present" and r.get("rate") not in (None, TODO):
            if not re.search(r"x\^\{?k", r["rate"]):
                problems.append((rid, "rate: the base x^k never appears in the "
                                      "charge, so the declared determinant "
                                      "plays no visible role"))
    return problems


# Structural LaTeX and label-only words: never quantities, never indices.
_TEX_NOISE = {
    "mathrm", "mathcal", "mathbb", "mathbf", "text", "operatorname", "displaystyle",
    "max", "min", "arg", "frac", "sum", "prod", "int", "sqrt",
    "left", "right", "big", "Big", "bigg", "Bigg", "underbrace", "overbrace",
    "overline", "underline", "widehat", "hat", "bar", "tilde", "vec",
    "qquad", "quad", "cdot", "cdots", "ldots", "dots", "times", "div",
    "in", "notin", "subset", "prime", "leq", "geq", "neq", "equiv", "approx",
    "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep",
    "Oct", "Nov", "Dec",
}
# Index letters declared in schema.yaml `notation`.
DECL_INDEX = {"k", "e", "n", "z", "t", "s", "m", "y", "a", "v"}
# Objects `notation` declares globally, so a record need not redefine them.
DECL_GLOBAL = {"x", "Phi", "C", "Z", "AML", "LRS"}
# Letters the economic model reserves for prices, quantities and components.
RESERVED = set("pqbfcgh") | set("PQBFGH")


def split_indices(tex):
    """Return (head, indices). Text inside _{...}/^{...} is index position,
    everything else is head position. Brace-matched, so a nested group such as
    \\sum_{m \\in \\{\\mathrm{Jun}\\}} is consumed whole."""
    head, idx, i, n = [], [], 0, len(tex)
    while i < n:
        if tex[i] in "_^":
            j = i + 1
            if j < n and tex[j] == "{":
                depth, k = 1, j + 1
                while k < n and depth:
                    depth += (tex[k] == "{") - (tex[k] == "}")
                    k += 1
                idx.append(tex[j + 1:k - 1]); i = k; continue
            m = re.match(r"\\[A-Za-z]+|.", tex[j:])
            if m:
                idx.append(m.group(0)); i = j + m.end(); continue
        head.append(tex[i]); i += 1
    h, ix = "".join(head), " ".join(idx)
    if re.search(r"[_^]", ix):
        a, b = split_indices(ix); ix = a + " " + b
    return h, ix


def atoms(text):
    """Symbol atoms: \\mathrm{NAME} tokens, command names, and bare letters."""
    names = set(re.findall(r"\\mathrm\{([A-Za-z]+)\}", text)) - _TEX_NOISE
    s = re.sub(r"\\(?:mathrm|text|mathcal|mathbb|mathbf)\{[^{}]*\}", " ", text)
    cmds = set(re.findall(r"\\([A-Za-z]+)", s)) - _TEX_NOISE
    s = re.sub(r"\\[A-Za-z]+", " ", s)
    return names | cmds | set(re.findall(r"[A-Za-z]", s))


def index_atoms(text):
    """Atoms in index position that are genuinely indices. A \\mathrm{} group in
    a sub/superscript is a mnemonic decoration (C^{k,\\mathrm{sb}}), not an
    index, so it is excluded - otherwise every mnemonic is a false positive."""
    s = re.sub(r"\\(?:mathrm|text|mathcal|mathbb|mathbf)\{[^{}]*\}", " ", text)
    cmds = set(re.findall(r"\\([A-Za-z]+)", s)) - _TEX_NOISE
    s = re.sub(r"\\[A-Za-z]+", " ", s)
    return cmds | set(re.findall(r"[A-Za-z]", s))


def undefined_symbols(rid, field, formula, entries):
    """Every quantity should be defined, every index declared, no reserved
    letter used, and nothing defined that the formula never uses."""
    syms = [str(e.get("symbol") or "") for e in entries]
    def_heads = atoms(split_indices(" ".join(syms))[0])

    own_index = set()
    for sym in syms:
        a, b = split_indices(sym)
        one = atoms(a) | index_atoms(b)
        if len(one) == 1:
            own_index |= one

    h, ix = split_indices(formula)
    f_heads, f_idx = atoms(h), index_atoms(ix)

    p = []
    for a in sorted(f_heads - def_heads - DECL_GLOBAL):
        p.append((rid, f"{field}: `{a}` is used as a quantity but never defined"))
    for a in sorted(f_idx - DECL_INDEX - own_index - def_heads):
        p.append((rid, f"{field}: index `{a}` is neither declared in schema "
                       f"notation nor defined in {field}_definitions"))
    for a in sorted((f_heads | f_idx) & RESERVED):
        p.append((rid, f"{field}: `{a}` is a reserved letter of the economic model"))
    for sym in syms:
        a, b = split_indices(sym)
        for r_ in sorted((atoms(a) | index_atoms(b)) & RESERVED):
            p.append((rid, f"{field}_definitions: symbol `{sym}` uses reserved "
                           f"letter `{r_}`"))
        if atoms(a) and not (atoms(a) & (f_heads | f_idx)):
            p.append((rid, f"{field}_definitions: `{sym}` is defined but never "
                           f"used in {field}"))
    return p


def sources(r):
    """`source` is one entry or a list of them. Always hand back a list."""
    src = r.get("source")
    if isinstance(src, dict):
        return [src]
    return [x for x in (src or []) if isinstance(x, dict)]


def progress(r):
    """A field counts as done only if it is present and not the TODO sentinel.
    Absence must not score as extraction - a skeleton record with no `source`
    key at all would otherwise report full marks."""
    filled = sum(
        1 for f in PROGRESS_FIELDS if f in r and not is_todo(r.get(f))
    )
    srcs = sources(r)
    if not srcs:
        return filled, len(PROGRESS_FIELDS), 0, len(SOURCE_FIELDS)
    # Score the weakest citation, so adding a thin one cannot inflate the count.
    src_filled = min(
        sum(1 for f in SOURCE_FIELDS if s.get(f) and not is_todo(s.get(f)))
        for s in srcs
    )
    return filled, len(PROGRESS_FIELDS), src_filled, len(SOURCE_FIELDS)


def defs(r, key):
    out = []
    for d in (r.get(key) or []):
        out.append({
            "symbol": str(d.get("symbol") or ""),
            "unit": str(d.get("unit") or ""),
            "definition": str(d.get("definition") or "").strip(),
        })
    return out


def norm(r):
    """Flatten a record into the shape the page consumes."""
    filled, total, src_filled, src_total = progress(r)
    return {
        "id": r.get("id", ""),
        "layer": r.get("layer", ""),
        "layer_label": LAYER_LABELS.get(r.get("layer", ""),
                                        r.get("layer", "").replace("_", " ").title()),
        "market": r.get("market", ""),
        "status": r.get("status", "present"),
        "payer": r.get("payer"),
        "base": r.get("base"),
        "base_type": r.get("base_type"),
        "base_defs": defs(r, "base_definitions"),
        "base_note": r.get("base_note"),
        "base_derived": bool(r.get("base_derived")),
        "rate_derived": bool(r.get("rate_derived")),
        "measurement_window": r.get("measurement_window"),
        "billing_window": r.get("billing_window"),
        "determinacy": r.get("determinacy"),
        "pool": r.get("pool"),
        "rate": r.get("rate"),
        "rate_type": r.get("rate_type"),
        "rate_defs": defs(r, "rate_definitions"),
        "exact_recovery": r.get("exact_recovery"),
        "true_up": r.get("true_up"),
        "redirect": r.get("redirect"),
        "sources": [{f: s.get(f) for f in SOURCE_FIELDS} for s in sources(r)],
        "notes": r.get("notes"),
        "_filled": filled,
        "_total": total,
        "_src_filled": src_filled,
        "_src_total": src_total,
    }


CSS = """
:root{
  --page:#FFFFFF; --panel:#FFFFFF; --sunk:#FAFBFC;
  --ink:#12181F; --muted:#697787; --faint:#6B7887;
  --rule:#E4E9EE; --rule-soft:#EFF2F5;
  --accent:#1F5FA8; --accent-soft:#EAF1F9;
  --warn:#9A6212; --warn-soft:#FDF7EC;
  --absent:#8A5A6B; --absent-soft:#F8F1F3;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,Helvetica,Arial,sans-serif;
  --mono:ui-monospace,"SF Mono",SFMono-Regular,Menlo,Consolas,monospace;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--page);color:var(--ink);font-family:var(--sans);
  font-size:13.5px;line-height:1.5;-webkit-font-smoothing:antialiased}
.wrap{max-width:1120px;margin:0 auto;padding:26px 20px 60px}

header{margin-bottom:16px}
h1{font-size:19px;font-weight:640;letter-spacing:-.02em;margin:0 0 5px}
.sub{color:var(--muted);font-size:13px;margin:0;max-width:78ch}

/* summary tiles */
.tiles{display:flex;flex-wrap:wrap;gap:7px;margin:14px 0 0}
.tile{flex:1 1 116px;background:var(--sunk);border:1px solid var(--rule);
  border-radius:6px;padding:7px 10px}
.tile .k{font-size:11px;color:var(--muted);margin-bottom:1px;line-height:1.3}
.tile .v{font-size:17px;font-weight:600;letter-spacing:-.02em;line-height:1.25;
  font-variant-numeric:tabular-nums}
.tile .v.zero{color:var(--faint);font-weight:500}

/* controls */
.bar{position:sticky;top:0;z-index:5;background:var(--page);
  padding:10px 0 8px;margin-top:14px;border-bottom:1px solid var(--rule);
  display:flex;flex-wrap:wrap;gap:6px;align-items:center}
select,input[type=search]{font-family:inherit;font-size:12.5px;padding:5px 8px;
  border:1px solid var(--rule);background:var(--panel);color:var(--ink);
  border-radius:6px}
select{cursor:pointer}
input[type=search]{flex:1 1 210px;min-width:170px}
select:focus,input:focus{outline:2px solid var(--accent);outline-offset:1px;
  border-color:var(--accent)}
tr:focus{outline:2px solid var(--accent);outline-offset:-2px}
.count{margin-left:auto;color:var(--muted);font-size:12.5px;
  font-variant-numeric:tabular-nums}

/* table */
/* fixed layout lets the detail cell shrink, so a wide formula scrolls
   inside .math instead of pushing the whole page sideways on mobile */
table{width:100%;border-collapse:collapse;margin-top:0;table-layout:fixed}
col.c-layer{width:30%} col.c-mkt{width:11%} col.c-base{width:19%}
col.c-rate{width:18%} col.c-prog{width:22%}
td .layer{overflow-wrap:anywhere}
th{font-size:11px;color:var(--muted);text-align:left;font-weight:600;
  padding:7px 10px;border-bottom:1px solid var(--rule);white-space:nowrap}
th .q{display:inline-block;width:13px;height:13px;line-height:13px;
  text-align:center;border:1px solid var(--rule);border-radius:50%;
  font-size:9px;color:var(--muted);margin-left:4px;cursor:help}
td{padding:7px 10px;border-bottom:1px solid var(--rule-soft);
  vertical-align:middle}
tr.row{cursor:pointer}
tr.row:hover td{background:var(--sunk)}
tr.row.open td{background:var(--accent-soft)}
.layer{font-weight:570}

/* chips: a boxed value always means a fixed vocabulary */
.chip{display:inline-block;font-size:12px;line-height:1.45;padding:2px 8px;
  border:1px solid var(--rule);border-radius:999px;white-space:nowrap;
  background:var(--panel);color:var(--ink)}
.chip.set{border-color:#C8D9EC;background:var(--accent-soft);color:var(--accent)}
.chip.todo{border-color:#EBDCC0;background:var(--warn-soft);color:var(--warn)}
.chip.none{border-color:#E7D5DC;background:var(--absent-soft);color:var(--absent)}
.chip.market{font-weight:600;letter-spacing:.02em;font-size:11.5px}
.na{color:var(--faint)}
.todo-txt{color:var(--warn)}

/* completeness */
.prog{display:flex;flex-direction:column;gap:5px;min-width:178px}
.prog .line{display:flex;align-items:center;gap:8px;font-size:11.5px;
  color:var(--muted);font-variant-numeric:tabular-nums}
.prog .lbl{flex:0 0 46px;color:var(--faint)}
.prog .track{flex:0 0 54px;height:5px;border-radius:3px;background:var(--rule);
  overflow:hidden}
/* display:block matters - width has no effect on an inline span */
.prog .fill{display:block;height:100%;background:var(--accent);border-radius:3px}
.prog .fill.none{background:var(--rule)}

/* detail */
tr.detail td{background:var(--sunk);padding:0;
  border-bottom:1px solid var(--rule)}
.det{padding:14px 16px 16px}
.sec{margin-bottom:15px}
.sec:last-child{margin-bottom:0}
.sec h3{font-size:11px;letter-spacing:.06em;text-transform:uppercase;
  color:var(--muted);font-weight:640;margin:0 0 8px;
  padding-bottom:5px;border-bottom:1px solid var(--rule)}
.math{background:var(--panel);border:1px solid var(--rule);border-radius:6px;
  padding:9px 12px;overflow-x:auto;margin-bottom:9px;font-size:.95em}
.derived{font-size:11.5px;color:var(--warn);background:var(--warn-soft);
  border:1px solid #F0E3CB;border-radius:6px;padding:6px 9px;margin:-4px 0 9px}
.math.raw{font-family:var(--mono);font-size:12px;color:var(--muted);
  white-space:pre-wrap}
/* otherwise a formula wider than its box is centred and its left edge is
   scrolled out of view */
.math .katex-display{text-align:left;margin:0}
.grid{display:grid;gap:8px 18px;
  grid-template-columns:repeat(auto-fit,minmax(215px,1fr));margin-bottom:9px}
.f{min-width:0}
.f .k{font-size:11px;color:var(--muted);margin-bottom:1px}
/* .f .v is a descendant selector; <div class="f v"> needs .f.v too */
.f .v,.f.v,.note div{white-space:pre-wrap;word-break:break-word}
.f.wide{grid-column:1/-1}
/* symbol | unit | meaning - three columns so units line up down the page */
.defs{margin:0 0 9px;display:grid;grid-template-columns:auto auto 1fr;
  gap:4px 14px;align-items:baseline;font-size:12.5px}
.defs .sym{white-space:nowrap}
.defs .unit{color:var(--faint);white-space:nowrap;font-variant-numeric:tabular-nums}
.defs .def{color:var(--muted)}
.note{background:var(--warn-soft);border:1px solid #F0E3CB;border-radius:6px;
  padding:9px 11px;margin-bottom:9px}
.note .k{font-size:11px;color:var(--warn);font-weight:600;margin-bottom:2px}
.quote{border-left:3px solid var(--rule);padding:1px 0 1px 11px;
  color:var(--muted);white-space:pre-wrap}
.cites{display:grid;gap:9px}
.cite{border:1px solid var(--rule);border-radius:6px;padding:9px 11px}
.cite .hd{font-size:11px;color:var(--muted);margin-bottom:5px}
.cite .step{display:inline-block;min-width:15px;height:15px;line-height:15px;
  text-align:center;border-radius:50%;background:var(--accent-soft);
  color:var(--accent);font-size:9.5px;font-weight:700;margin-right:6px}
a{color:var(--accent)}
.goto{display:inline-block;background:var(--absent-soft);
  border:1px solid #E7D5DC;color:var(--absent);border-radius:6px;
  padding:8px 11px;cursor:pointer;font-family:inherit;font-size:12.5px;
  text-align:left;line-height:1.45}
.goto b{font-weight:620}

/* overview: the general form, above the records that instantiate it */
.ov{margin:20px 0 4px;padding:18px 20px;border:1px solid var(--rule);
  border-radius:8px;background:var(--sunk)}
.ov h2{font-size:15px;font-weight:640;margin:0 0 5px;letter-spacing:-.01em}
.ov h3{font-size:12px;letter-spacing:.05em;text-transform:uppercase;
  color:var(--muted);font-weight:640;margin:18px 0 8px}
.ov .sub{font-size:12.5px;margin:0 0 10px;max-width:82ch}
.ov .sub2{font-size:11.5px;color:var(--muted);margin-top:2px}
.texd{background:var(--panel);border:1px solid var(--rule);border-radius:6px;
  padding:11px 13px;margin:0 0 10px;overflow-x:auto}
.texd .katex-display{text-align:left;margin:0}
table.ovt{width:100%;border-collapse:collapse;font-size:12px;
  table-layout:auto;background:var(--panel);border:1px solid var(--rule);
  border-radius:6px}
table.ovt th{font-size:10.5px;padding:7px 9px;white-space:normal}
table.ovt td{padding:8px 9px;border-bottom:1px solid var(--rule-soft);
  vertical-align:top}
table.ovt tr:last-child td{border-bottom:none}
table.ovt .den,table.ovt .res{white-space:nowrap}
table.ovt .eg{color:var(--muted);min-width:230px}

.gloss{margin:14px 0 0;border:1px solid var(--rule);border-radius:6px;
  background:var(--sunk)}
.gloss summary{cursor:pointer;padding:8px 12px;font-size:12.5px;
  color:var(--accent);list-style:none}
.gloss summary::-webkit-details-marker{display:none}
.gloss summary::before{content:"▸ ";font-size:10px}
.gloss[open] summary::before{content:"▾ "}
.gloss .body{padding:2px 12px 12px;display:grid;
  grid-template-columns:auto 1fr;gap:6px 14px;align-items:baseline;
  font-size:12.5px}
.gloss .sym{white-space:nowrap}
.gloss .mean{color:var(--muted)}

.problems{border:1px solid #EBDCC0;background:var(--warn-soft);border-radius:6px;
  padding:9px 12px;margin-bottom:12px;font-size:12.5px}
.problems .k{font-size:11px;color:var(--warn);font-weight:640;
  margin-bottom:3px;letter-spacing:.05em;text-transform:uppercase}
.empty{padding:26px;text-align:center;color:var(--muted)}
footer{margin-top:20px;color:var(--faint);font-size:12px;
  border-top:1px solid var(--rule);padding-top:10px}
@media (max-width:720px){
  .wrap{padding:28px 16px 80px}
  th.hide-sm,td.hide-sm{display:none}
}
"""

JS = """
const R = __DATA__, LABELS = __LABELS__;
const $ = s => document.querySelector(s);
const esc = s => (s??'').toString().replace(/[&<>"]/g,
  c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const isTodo = v => v==='TODO';
const isNA = v => v===null || v===undefined;
const label = v => LABELS[v] ?? v;
const NICE = {none:'None'};
let open = null;

function cell(v){
  if (isTodo(v)) return '<span class="todo-txt">Not yet extracted</span>';
  if (isNA(v))   return '<span class="na">Not applicable</span>';
  return esc(NICE[v] ?? v);
}

function chip(v, kind){
  if (isTodo(v)) return '<span class="chip todo">To do</span>';
  if (isNA(v))   return '<span class="chip">Not applicable</span>';
  const none = (v==='absent'||v==='absorbed') ? ' none' : ' set';
  return '<span class="chip'+none+(kind?' '+kind:'')+'">'+esc(label(v))+'</span>';
}

/* Typeset with KaTeX when it loaded, otherwise show the TeX itself. Either way
   the reader can see the formula - that is the point of storing it as one. */
function derivedFlag(on){
  return on ? '<div class="derived">Reconstructed. This formula generalises or '
    + 'reassembles what the source states; it is not quoted algebra.</div>' : '';
}

function mathBlock(tex){
  if (isTodo(tex)) return '<div class="math raw">Not yet extracted</div>';
  if (isNA(tex))   return '';
  if (typeof katex === 'undefined') return '<div class="math raw">'+esc(tex)+'</div>';
  try {
    return '<div class="math">'+katex.renderToString(tex,
      {displayMode:true, throwOnError:false})+'</div>';
  } catch(e){ return '<div class="math raw">'+esc(tex)+'</div>'; }
}

function mathInline(tex){
  if (typeof katex === 'undefined') return '<code>'+esc(tex)+'</code>';
  try { return katex.renderToString(tex, {displayMode:false, throwOnError:false}); }
  catch(e){ return '<code>'+esc(tex)+'</code>'; }
}

function defList(items){
  if (!items || !items.length) return '';
  return '<div class="defs">' + items.map(d =>
    '<div class="sym">'+mathInline(d.symbol)+'</div>'
    + '<div class="unit">'+esc(d.unit||'')+'</div>'
    + '<div class="def">'+esc(d.definition)+'</div>'
  ).join('') + '</div>';
}

function field(k, lbl, r, wide){
  return '<div class="f'+(wide?' wide':'')+'"><div class="k">'+lbl+'</div>'
       + '<div class="v">'+cell(r[k])+'</div></div>';
}

function detail(r){
  const s = r.sources || [];
  let h = '<div class="det">';
  h += '<div class="sec"><div class="grid">'
     + '<div class="f"><div class="k">Status</div><div class="v">'
     + chip(r.status)+'</div></div>'
     + '<div class="f"><div class="k">Billed to</div><div class="v">'
     + chip(r.payer)+'</div></div></div></div>';

  if (r.redirect){
    const t = R.find(x => x.id === r.redirect);
    h += '<div class="sec"><h3>Where this cost is charged instead</h3>'
       + '<button class="goto" data-goto="'+esc(r.redirect)+'">'
       + 'This layer has no charge of its own. It is priced inside '
       + '<b>'+esc(t ? t.layer_label+' ('+label(t.market)+')' : r.redirect)+'</b>.'
       + ' &nbsp;View that record &rarr;</button></div>';
  }

  // An absent or absorbed layer has no base and no charge. Rendering both
  // sections anyway produced a panel of "Not applicable" placeholders.
  const noCharge = r.status !== 'present';

  if (!noCharge) {
    h += '<div class="sec"><h3>Base &mdash; what is measured</h3>'
       + mathBlock(r.base) + derivedFlag(r.base_derived) + defList(r.base_defs)
       + '<div class="grid">'
       + '<div class="f"><div class="k">Base type</div><div class="v">'
       + chip(r.base_type)+'</div></div>'
       + field('measurement_window','Measured over', r)
       + field('billing_window','Billed for', r)
       + '<div class="f"><div class="k">Determinant known</div><div class="v">'
       + chip(r.determinacy)+'</div></div>'
       + '</div>';
    if (!isTodo(r.base_note) && !isNA(r.base_note))
      h += '<div class="note"><div class="k">Worth knowing about this base</div>'
         + '<div>'+esc(r.base_note)+'</div></div>';
    h += '</div>';

    // "Charge", not "Rate" - the field holds the whole charge with the base
    // already in it, not a per-unit rate. Pool leads, because the formula
    // refers to it.
    h += '<div class="sec"><h3>Charge &mdash; what is billed</h3>'
       + field('pool','Pool being recovered', r, true)
       + mathBlock(r.rate) + derivedFlag(r.rate_derived) + defList(r.rate_defs)
       + '<div class="grid">'
       + '<div class="f"><div class="k">Rate type</div><div class="v">'
       + chip(r.rate_type)+'</div></div>'
       + '<div class="f"><div class="k">Recovers the pool exactly</div>'
       + '<div class="v">'+chip(r.exact_recovery)+'</div></div>'
       + field('true_up','True-up', r, true)
       + '</div></div>';
  }

  // Sources, in the order the mechanism runs. A layer assembled from several
  // provisions cites every one of them.
  const many = s.length > 1;
  h += '<div class="sec"><h3>'
     + (many ? 'Sources &mdash; in the order the mechanism runs' : 'Source')
     + '</h3><div class="cites">'
     + (s.length ? s.map(function(c, n){
         return '<div class="cite"><div class="hd">'
           + (many ? '<span class="step">'+(n+1)+'</span>' : '')
           + esc(c.document||'')
           + (c.section ? ' &middot; '+esc(c.section) : '')
           + (c.effective_date ? ' &middot; effective '+esc(c.effective_date) : '')
           + '</div><div class="quote">'+cell(c.quote)+'</div>'
           + (!isTodo(c.url) && !isNA(c.url)
              ? '<div style="margin-top:7px"><a href="'+esc(c.url)
                + '" target="_blank" rel="noopener">Open document &rarr;</a></div>'
              : '')
           + '</div>';
       }).join('')
       : '<div class="cite"><div class="quote">'
         + '<span class="todo-txt">Not yet extracted</span></div></div>')
     + '</div></div>';

  if (!isTodo(r.notes) && !isNA(r.notes))
    h += '<div class="sec"><h3>Notes</h3><div class="f v">'+esc(r.notes)+'</div></div>';

  return h + '</div>';
}

function bar(lbl, n, total){
  const pct = total ? Math.round(100*n/total) : 0;
  return '<div class="line"><span class="lbl">'+lbl+'</span>'
       + '<span class="track"><span class="fill'+(n?'':' none')
       + '" style="width:'+pct+'%"></span></span>'
       + n+' of '+total+'</div>';
}

function progress(r){
  return '<div class="prog">'
    + bar('Fields',  r._filled,     r._total)
    + bar('Sources', r._src_filled, r._src_total)
    + '</div>';
}

function pass(r){
  const q = $('#q').value.trim().toLowerCase();
  for (const k of ['layer','market','base_type','rate_type','determinacy']){
    const v = $('#f_'+k).value;
    if (v && (r[k]||'TODO') !== v) return false;
  }
  const st = $('#f_state').value;
  const done = r._filled===r._total && r._src_filled===r._src_total;
  if (st==='todo' && done) return false;
  if (st==='done' && !done) return false;
  if (q && !JSON.stringify(r).toLowerCase().includes(q)) return false;
  return true;
}

function draw(){
  const rows = R.filter(pass);
  $('#count').textContent = rows.length+' of '+R.length+' records';
  const tb = $('#body');
  tb.innerHTML = rows.map(r =>
    '<tr class="row" tabindex="0" role="button" aria-expanded="'
    + (open===r.id) + '" data-id="'+esc(r.id)+'">'
    + '<td><span class="layer">'+esc(r.layer_label)+'</span></td>'
    + '<td>'+chip(r.market,'market')+'</td>'
    + '<td>'+(r.status==='present' ? chip(r.base_type) : chip(r.status))+'</td>'
    + '<td>'+(r.status==='present' ? chip(r.rate_type)
        : (r.redirect ? '<span class="into">&rarr; '
            + esc((R.find(x=>x.id===r.redirect)||{}).layer_label||r.redirect)
            + '</span>' : '<span class="na">&mdash;</span>'))+'</td>'
    + '<td class="hide-sm">'+progress(r)+'</td></tr>'
  ).join('');
  $('#empty').style.display = rows.length ? 'none' : 'block';
  if (open) {
    const tr = tb.querySelector('[data-id="'+CSS.escape(open)+'"]');
    if (tr) expand(tr, R.find(x=>x.id===open)); else open = null;
  }
}

function expand(tr, r){
  const d = document.createElement('tr');
  d.className = 'detail';
  d.innerHTML = '<td colspan="5">'+detail(r)+'</td>';
  tr.classList.add('open');
  tr.after(d);
}

function toggle(id){
  document.querySelectorAll('tr.detail').forEach(e=>e.remove());
  document.querySelectorAll('tr.row.open').forEach(e=>e.classList.remove('open'));
  if (open === id) { open = null; return; }
  open = id;
  const tr = document.querySelector('tr.row[data-id="'+CSS.escape(id)+'"]');
  if (tr) expand(tr, R.find(x=>x.id===id));
}

document.addEventListener('click', e => {
  const g = e.target.closest('[data-goto]');
  if (g){
    e.stopPropagation();
    const id = g.dataset.goto;
    ['layer','market','base_type','rate_type','determinacy','state']
      .forEach(k => $('#f_'+k).value='');
    $('#q').value='';
    draw();
    toggle(id);
    document.querySelector('tr.row[data-id="'+CSS.escape(id)+'"]')
      ?.scrollIntoView({block:'center', behavior:'smooth'});
    return;
  }
  const tr = e.target.closest('tr.row');
  if (tr) toggle(tr.dataset.id);
});
document.addEventListener('keydown', e => {
  if (e.key!=='Enter' && e.key!==' ') return;
  const tr = e.target.closest && e.target.closest('tr.row');
  if (tr) { e.preventDefault(); toggle(tr.dataset.id); }
});
document.querySelectorAll('.bar select, .bar input').forEach(el =>
  el.addEventListener('input', draw));

// The glossary and the overview are TeX like everything else on the page.
if (typeof katex !== 'undefined'){
  document.querySelectorAll('#gloss-body .sym').forEach(el => {
    try { katex.render(el.textContent, el, {throwOnError:false}); } catch(e){}
  });
  document.querySelectorAll('.texd').forEach(el => {
    try { katex.render(el.textContent.trim(), el,
      {displayMode:true, throwOnError:false}); } catch(e){}
  });
  document.querySelectorAll('.texi').forEach(el => {
    try { katex.render(el.textContent.trim(), el,
      {displayMode:false, throwOnError:false}); } catch(e){}
  });
}
draw();
"""


# Display math for the overview. Kept as data so the page and slide.md stay in
# step - both are generated from these strings.
OVERVIEW_MATH = {
    "layer": r"\Phi^{k}_{e,t} \;=\; \underbrace{\sigma^{k}}_{\text{sign}}\; "
             r"\underbrace{r^{k}_{t}}_{\text{rate}}\; "
             r"\underbrace{x^{k}_{e,\,\mathcal{W}^{k}(t)}\!\left(d_{e}\right)}_{\text{base}}",
    "rate":  r"r^{k}_{t} \;=\; \frac{C^{k}_{t}}{\hat{X}^{k}_{t}} "
             r"\qquad\text{where}\qquad "
             r"\hat{X}^{k}_{t} \;=\; \text{the total base the rate was built on}",
    "resid": r"\sum_{e\in\mathcal{E}}\Phi^{k}_{e,t} \;=\; C^{k}_{t}\,"
             r"\frac{X^{k}_{t}}{\hat{X}^{k}_{t}} \qquad\Longrightarrow\qquad "
             r"R^{k}_{t} \;=\; C^{k}_{t}\left(1-\frac{X^{k}_{t}}{\hat{X}^{k}_{t}}\right)",
    "share": r"\Phi^{k}_{e,t} \;=\; \sigma^{k}\,C^{k}_{t}\,"
             r"\frac{x^{k}_{e,\,\mathcal{W}^{k}(t)}}"
             r"{\sum_{e^{\prime}\in\mathcal{E}}x^{k}_{e^{\prime},\,\mathcal{W}^{k}(t)}}",
}

# Each row: the denominator the rate used, what happens to the residual, a
# worked example. Figures are illustrative - they are not from source text.
OVERVIEW_ROWS = [
    (r"\hat{X}=X", "Realised base",
     "Rate is built from the same period it bills, so shares sum to one.",
     "R = 0",
     "Black start. Pool $50,000 for the hour; ERCOT load 45,000 MWh; yours 90 MWh. "
     "Rate $1.11/MWh, you pay $100. Nothing left over.",
     "reactive supply, black start, firm fuel, RMR"),
    (r"\hat{X}\to X", "Provisional, then revised",
     "Rate is set on an estimate, then recomputed on the realised base and the difference settled.",
     "R \to 0",
     "Ancillary services. Day-ahead you are billed on last week's comparable hour, "
     "say a 0.24% share. Settlement recomputes on the realised 0.20% and refunds the gap.",
     "ancillary services, emergency response, congestion rights"),
    (r"\hat{X}\ \text{frozen}", "Stale denominator",
     "Rate stays in force while the billing base is refreshed, so the two drift apart.",
     "R \neq 0, deferred",
     "Transmission. Rate set when ERCOT peak was 80 GW; billed on this summer's 85 GW. "
     "Collections run 6.25% above the cost of service until the next rate case.",
     "transmission network service"),
    (r"\text{no}\ \hat{X}", "Posted rate",
     "A published per-unit figure. No denominator was ever divided, so nothing ties collections to the pool.",
     "R \neq 0, never reconciled",
     "System administration. $0.55/MWh times whatever load turns out to be, against "
     "whatever ERCOT actually spent. The fee is reset going forward, not backward.",
     "system administration"),
    (r"r \neq C/\hat{X}", "Capped share",
     "The rate is deliberately not the pool over the base, so a remainder is guaranteed.",
     "R > 0 by design, transferred",
     "Reliability commitment shortfall. Your shortfall share implies $1M but the cap holds "
     "you to $400k. The $600k becomes the uplift layer's pool and is spread over all load.",
     "reliability commitment shortfall"),
]


def overview_block():
    """The general form, above the records that instantiate it."""
    rows = "".join(
        f'<tr><td class="den"><span class="texi">{html.escape(den)}</span></td>'
        f'<td><b>{html.escape(name)}</b><div class="sub2">{html.escape(desc)}</div></td>'
        f'<td class="res"><span class="texi">{html.escape(res)}</span></td>'
        f'<td class="eg">{html.escape(eg)}</td></tr>'
        for den, name, desc, res, eg, _ in OVERVIEW_ROWS
    )
    m = OVERVIEW_MATH
    return f"""<section class="ov">
  <h2>How every charge is built</h2>
  <p class="sub">One layer of the bill, for one entity, in one billing period.
     Everything in the table below is an instance of this.</p>
  <div class="texd">{html.escape(m['layer'])}</div>
  <p class="sub"><i>d<sub>e</sub></i> is the entity's demand path &mdash; the only
     thing it controls. <i>t</i> is the period billed;
     <i>W<sup>k</sup>(t)</i> is the window the base is measured over. For most
     layers those coincide; where they do not is where the interesting layers live.</p>

  <h3>The rate is a pool over an estimate of the base</h3>
  <div class="texd">{html.escape(m['rate'])}</div>
  <p class="sub">That single choice &mdash; which denominator the rate was built
     on &mdash; determines everything about recovery. Collections and the
     residual both fall straight out of it:</p>
  <div class="texd">{html.escape(m['resid'])}</div>
  <p class="sub">So there is no separate true-up mechanism. A true-up is just a
     rate whose denominator is revised to the realised base.</p>

  <h3>Five ways the denominator is chosen</h3>
  <table class="ovt"><thead><tr><th>denominator</th><th>form</th>
    <th>residual</th><th>example &mdash; figures illustrative</th></tr></thead>
    <tbody>{rows}</tbody></table>

  <h3>The dominant case</h3>
  <p class="sub">Eleven of the fourteen charged ERCOT layers are this one
     expression, with the residual identically zero.</p>
  <div class="texd">{html.escape(m['share'])}</div>
</section>"""


def build_html(schema, records, problems):
    recs = [norm(r) for r in records]
    vocabs = schema["vocabularies"]

    def lbl(v):
        return VOCAB_LABELS.get(str(v), str(v).replace("_", " ").title())

    base_types = list(vocabs["base_type"])
    rate_types = list(vocabs["rate_type"])
    markets = sorted({r["market"] for r in recs})
    determinacies = list(vocabs["determinacy"])
    layers = sorted({r["layer"] for r in recs},
                    key=lambda s: LAYER_LABELS.get(s, s))

    extracted = sum(1 for r in recs
                    if r["_filled"] == r["_total"] and r["_src_filled"] == r["_src_total"])
    tiles = [
        ("Layers tracked", len(recs)),
        ("Extracted", extracted),
        ("Still to do", len(recs) - extracted),
    ]

    def opts(name, values, label_text, labeller):
        o = "".join(
            f'<option value="{html.escape(str(v))}">{html.escape(labeller(v))}</option>'
            for v in values
        )
        return (f'<select id="f_{name}" aria-label="Filter by {label_text}">'
                f'<option value="">All {label_text}</option>{o}</select>')

    tile_html = "".join(
        f'<div class="tile"><div class="k">{html.escape(k)}</div>'
        f'<div class="v{" zero" if n == 0 else ""}">{n}</div></div>'
        for k, n in tiles
    )

    notation = schema.get("notation") or []
    glossary = ""
    if notation:
        rows = "".join(
            f'<div class="sym">{html.escape(str(n.get("symbol", "")))}</div>'
            f'<div class="mean">{html.escape(str(n.get("meaning", "")).strip())}</div>'
            for n in notation
        )
        glossary = (
            '<details class="gloss"><summary>Notation used in the formulas'
            "</summary>"
            f'<div class="body" id="gloss-body">{rows}</div></details>'
        )

    overview = overview_block()

    prob_block = ""
    if problems:
        items = "<br>".join(f"{html.escape(i)} &mdash; {html.escape(m)}"
                            for i, m in problems)
        prob_block = (f'<div class="problems"><div class="k">Schema violations</div>'
                      f'{items}</div>')

    # json.dumps does not escape "</", which would terminate the script tag
    # early if a quoted provision ever contained one.
    data_json = json.dumps(recs, default=str).replace("</", "<\\/")
    js = (JS.replace("__DATA__", data_json)
            .replace("__LABELS__", json.dumps(VOCAB_LABELS)))

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Wholesale cost-allocation tracker</title>
<link rel="stylesheet"
  href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css"
  integrity="sha384-n8MVd4RsNIU0tAv4ct0nTaAbDJwPJzDEaqSD1odI+WdtXRGWt2kTvGFasHpSy3SV"
  crossorigin="anonymous">
<script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"
  integrity="sha384-XjKyOOlGwcjNTAIQHIpgOno0Hl1YQqzUOEleOLALmuqehneUG+vnGctmUb0ZY0l8"
  crossorigin="anonymous"></script>
<style>{CSS}</style></head><body><div class="wrap">
<header>
  <h1>Wholesale cost-allocation tracker</h1>
  <p class="sub">Tracker of cost-allocation mechanisms for wholesale electricity
     consumption, covering conforming and nonconforming loads. Each record
     separates a charge into three parts: the <strong>pool</strong> of dollars
     being recovered, the <strong>base</strong> that is measured, and the
     <strong>charge</strong> that results. Every entry is taken from source text
     and carries a citation and a quotation.</p>
  {glossary}
</header>
{overview}
<div class="tiles">{tile_html}</div>
{prob_block}
<div class="bar">
  <input type="search" id="q" placeholder="Search every field">
  {opts("layer", layers, "layers", lambda v: LAYER_LABELS.get(v, v))}
  {opts("market", markets, "markets", lbl)}
  {opts("base_type", base_types, "base types", lbl)}
  {opts("rate_type", rate_types, "rate types", lbl)}
  {opts("determinacy", determinacies, "timing", lbl)}
  <select id="f_state" aria-label="Filter by status">
    <option value="">Any status</option>
    <option value="todo">Still incomplete</option>
    <option value="done">Complete</option>
  </select>
  <span class="count" id="count"></span>
</div>
<table>
  <colgroup><col class="c-layer"><col class="c-mkt"><col class="c-base">
    <col class="c-rate"><col class="c-prog"></colgroup>
  <thead><tr>
    <th scope="col">Layer</th><th scope="col">Market</th>
    <th scope="col">Base type</th><th scope="col">Rate type</th>
    <th scope="col" class="hide-sm">Completeness
      <span class="q" title="{html.escape(FIELD_HELP)}">?</span></th>
  </tr></thead>
  <tbody id="body"></tbody>
</table>
<div class="empty" id="empty" style="display:none">
  No records match those filters.</div>
<footer>Generated from layers.yaml and schema.yaml. Re-run render.py after
  editing. The upper bar in each Completeness cell counts substantive fields,
  the lower one counts citation fields.</footer>
</div><script>{js}</script></body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE / "index.html"))
    args = ap.parse_args()

    schema, records = load()
    problems = validate(schema, records)
    pathlib.Path(args.out).write_text(
        build_html(schema, records, problems), encoding="utf-8")

    done = sum(1 for r in records if progress(r)[0] == progress(r)[1])
    print(f"{len(records)} records -> {args.out}")
    print(f"{done} fully extracted, {len(records) - done} with TODOs")
    if problems:
        print(f"{len(problems)} schema violation(s):", file=sys.stderr)
        for i, m in problems:
            print(f"  {i}: {m}", file=sys.stderr)


if __name__ == "__main__":
    main()
