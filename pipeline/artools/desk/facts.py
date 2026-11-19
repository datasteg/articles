"""Facts: every number a note may print, computed here from the run's tables.

A model never types a number. The analyst asks for a fact as a small expression over the tables
(`cell('panel','KOR','vulnerability')`, `count('panel','flow_pct < 0 and exports_yoy_pct > 0')`,
`spearman('panel','vulnerability','top_dest_share_pct')`); this module evaluates it, records the unrounded value, the
unit, the period and the tables it read, and writes analysis/analysis.json in the pipeline's fact format. The draft
then refers to the fact as {{F7}}, and `artools check numbers` refuses any digit that is not a token.

The expression language is Python's expression syntax cut down to arithmetic, comparisons and the functions below.
Nothing else evaluates: no attribute access, no subscripts on anything but function results, no names but the
functions.
"""
from __future__ import annotations

import ast
import math
import re
import statistics
from pathlib import Path

from ..paths import read_json, write_json
from .tables import dataset_id


class FactError(ValueError):
    pass


# ------------------------------------------------------------------ row conditions

_COND_NODES = (ast.Expression, ast.BoolOp, ast.And, ast.Or, ast.UnaryOp, ast.Not, ast.USub, ast.Compare, ast.Eq, ast.NotEq,
               ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn, ast.Name, ast.Load, ast.Constant, ast.BinOp, ast.Add,
               ast.Sub, ast.Mult, ast.Div, ast.Tuple, ast.List)


def _cond(expr: str | None):
    """A row filter such as "flow_pct < 0 and region == 'Asia'": names are the row's columns."""
    if not expr:
        return lambda row: True
    try:
        tree = ast.parse(str(expr), mode="eval")
    except SyntaxError as e:
        raise FactError(f"condition {expr!r}: not an expression ({e.msg}); write it like \"flow_pct < 0 and region == 'Asia'\"") from e
    for n in ast.walk(tree):
        if not isinstance(n, _COND_NODES):
            raise FactError(f"condition {expr!r}: {type(n).__name__} is not allowed")
    code = compile(tree, "<cond>", "eval")

    def test(row):
        try:
            return bool(eval(code, {"__builtins__": {}}, {k: v for k, v in row.items()}))   # noqa: S307 (whitelisted AST)
        except TypeError:
            return False            # a comparison with a missing value: the row does not qualify
        except NameError as e:
            raise FactError(f"condition {expr!r}: {e}") from e
    return test


class Calc:
    """The functions an expression may call, bound to the run's tables; `used` collects the tables read."""

    def __init__(self, tables: dict[str, dict]):
        self.tables = tables
        self.used: list[str] = []

    def _t(self, name: str) -> dict:
        if name not in self.tables:
            raise FactError(f"no table {name!r}; tables: {sorted(self.tables)}")
        if name not in self.used:
            self.used.append(name)
        return self.tables[name]

    def _row(self, t: dict, key: str) -> dict:
        for r in t["rows"]:
            if r["_key"] == key:
                return r
        near = [r["_key"] for r in t["rows"] if str(key).lower() in r["_key"].lower()][:5]
        raise FactError(f"table {t['name']}: no row {key!r}" + (f"; did you mean {near}" if near else ""))

    def _vals(self, table: str, col: str, where: str | None = None) -> list[tuple[str, float]]:
        t = self._t(table)
        if not any(c["id"] == col for c in t["columns"]):
            raise FactError(f"table {table}: no column {col!r}")
        test = _cond(where)
        return [(r["_key"], r[col]) for r in t["rows"]
                if isinstance(r.get(col), (int, float)) and not isinstance(r.get(col), bool) and test(r)]

    # --- single values
    def cell(self, table, row, col):
        t = self._t(table)
        v = self._row(t, row).get(col, KeyError)
        if v is KeyError:
            raise FactError(f"table {table}: no column {col!r}")
        if v is None:
            raise FactError(f"table {table}: {row}.{col} is empty")
        return v

    def rank(self, table, col, row, order="desc", where=None):
        vals = self._vals(table, col, where)
        me = dict(vals).get(row)
        if me is None:
            raise FactError(f"table {table}: {row} has no {col}")
        return 1 + sum(1 for _, v in vals if (v > me if order == "desc" else v < me))

    # --- over rows
    def count(self, table, where=None):
        test = _cond(where)
        return sum(1 for r in self._t(table)["rows"] if test(r))

    def n(self, table, col, where=None):
        return len(self._vals(table, col, where))

    def total(self, table, col, where=None):
        return sum(v for _, v in self._vals(table, col, where))

    def mean(self, table, col, where=None):
        return self._stat(statistics.fmean, table, col, where)

    def median(self, table, col, where=None):
        return self._stat(statistics.median, table, col, where)

    def lowest(self, table, col, where=None):
        return self._stat(min, table, col, where)

    def highest(self, table, col, where=None):
        return self._stat(max, table, col, where)

    def quantile(self, table, col, q, where=None):
        vals = sorted(v for _, v in self._vals(table, col, where))
        if not vals:
            raise FactError(f"table {table}: no values of {col}")
        pos = (len(vals) - 1) * q
        lo, hi = math.floor(pos), math.ceil(pos)
        return vals[lo] + (vals[hi] - vals[lo]) * (pos - lo)

    def _stat(self, fn, table, col, where):
        vals = [v for _, v in self._vals(table, col, where)]
        if not vals:
            raise FactError(f"table {table}: no values of {col}" + (f" where {where}" if where else ""))
        return fn(vals)

    def share(self, table, where, of=None):
        """% of rows meeting `where` among rows meeting `of` (all rows by default)."""
        base = self.count(table, of)
        if not base:
            raise FactError("share of an empty set")
        both = f"({where}) and ({of})" if of else where
        return 100.0 * self.count(table, both) / base

    # --- two columns
    def spearman(self, table, x, y, where=None):
        return self._corr(table, x, y, where, ranked=True)

    def pearson(self, table, x, y, where=None):
        return self._corr(table, x, y, where, ranked=False)

    def _corr(self, table, x, y, where, ranked):
        a, b = dict(self._vals(table, x, where)), dict(self._vals(table, y, where))
        keys = [k for k in a if k in b]
        if len(keys) < 8:
            raise FactError(f"correlation of {x} and {y}: only {len(keys)} rows have both")
        xs, ys = [a[k] for k in keys], [b[k] for k in keys]
        if ranked:
            xs, ys = _ranks(xs), _ranks(ys)
        return statistics.correlation(xs, ys)

    # --- text results (names are not numbers: a draft may also type them)
    def where_max(self, table, col, where=None, label="name"):
        return self._label(table, max(self._vals(table, col, where), key=lambda kv: kv[1])[0], label)

    def where_min(self, table, col, where=None, label="name"):
        return self._label(table, min(self._vals(table, col, where), key=lambda kv: kv[1])[0], label)

    def _label(self, table, key, label):
        r = self._row(self._t(table), key)
        return r.get(label) or key

    def functions(self) -> dict:
        names = ("cell", "rank", "count", "n", "total", "mean", "median", "lowest", "highest", "quantile", "share",
                 "spearman", "pearson", "where_max", "where_min")
        return {k: getattr(self, k) for k in names} | {"abs": abs, "round": round, "min": min, "max": max}


def _ranks(xs: list[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    out = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            out[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return out


_EXPR_NODES = (ast.Expression, ast.Call, ast.Name, ast.Load, ast.Constant, ast.BinOp, ast.UnaryOp, ast.Add, ast.Sub, ast.Mult,
               ast.Div, ast.Pow, ast.USub, ast.UAdd, ast.keyword)


def _desc(t: dict, row: str | None, col: str) -> tuple[str, str] | None:
    """The period a value is measured over, as (kind, value): Q a quarter end, WQ the goods window joined at a quarter
    (rule C2: ending in its last month, or up to six months earlier), WN another goods window, Y a year."""
    c = next((x for x in t.get("columns") or [] if x.get("id") == col), None)
    if c is None or c.get("unit") in (None, "text"):
        return None
    tp = t.get("period") or {}
    if t.get("name") == "panel" or c.get("period"):
        key = c.get("period") or "funding_quarter"
        r = next((x for x in t.get("rows") or [] if x.get("_key") == row), {}) if row else {}
        if key == "funding_quarter":
            return ("Q", str(tp.get("funding_quarter")))
        if key == "stress_quarter":
            return ("Q", str(tp.get("stress_quarter") or tp.get("funding_quarter")))
        if key == "lenders_quarter":
            return ("Q", str(r.get("lenders_quarter") or tp.get("funding_quarter")))
        if key == "goods_window":
            return ("WQ", str(tp.get("funding_quarter")))
        if key in ("goods_window_newest", "products_window"):
            return ("WN", str(r.get("goods_window_newest_to") or r.get("products_window_to") or key))
        return ("Y", str(r.get("chokepoint_year") or key))
    if tp.get("shown") and str(tp.get("freq") or "Q") == "Q":
        return ("Q", str(tp["shown"]))
    w = tp.get("goods_window") if isinstance(tp.get("goods_window"), dict) else None
    if w or tp.get("window_to"):
        return ("WN", str((w or {}).get("to") or tp.get("window_to")))
    return None


def _periods_agree(tree, tables: dict[str, dict]) -> str | None:
    """Rule C2 (check K9): an expression that multiplies or divides two different measures must
    read them over periods that belong together: the same quarter, or a quarter-end stock with the goods window joined
    at that quarter. One measure at two periods (a change over time) is fine. Returns the problem, or None."""
    if not any(isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Mult, ast.Div)) for n in ast.walk(tree)):
        return None
    refs = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and n.args and isinstance(n.args[0], ast.Constant) and n.args[0].value in tables:
            t = tables[n.args[0].value]
            strs = [a.value for a in n.args[1:] if isinstance(a, ast.Constant) and isinstance(a.value, str)]
            colids = {c.get("id") for c in t.get("columns") or []}
            cols = [x for x in strs if x in colids]
            rows = [x for x in strs if x not in colids]
            for col in cols:
                d = _desc(t, rows[0] if rows and isinstance(n.func, ast.Name) and n.func.id == "cell" else None, col)
                if d:
                    refs.append((col, d, n.args[0].value))
    for i, (ca, da, ta) in enumerate(refs):
        for cb, db, tb in refs[i + 1:]:
            if ca == cb or da == db or {da[0], db[0]} == {"Q", "WQ"} and da[1] == db[1]:
                continue
            return (f"it combines {ta}.{ca} ({da[0]} {da[1]}) with {tb}.{cb} ({db[0]} {db[1]}): two measures over periods "
                    "that do not belong together (rule C2: a quarter-end stock goes with the goods window joined at that "
                    "quarter). Use the columns of the window joined at the quarter, or compare one measure with itself.")
    return None


def evaluate(expr: str, tables: dict[str, dict]) -> tuple[object, list[str]]:
    """(value, tables read). Raises FactError with a message a model can act on."""
    try:
        tree = ast.parse(expr.strip(), mode="eval")
    except SyntaxError as e:
        raise FactError(f"{expr!r}: not an expression ({e.msg})") from e
    why = _periods_agree(tree, tables)
    if why:
        raise FactError(f"{expr!r}: {why}")
    calc = Calc(tables)
    fns = calc.functions()
    for node in ast.walk(tree):
        if not isinstance(node, _EXPR_NODES):
            raise FactError(f"{expr!r}: {type(node).__name__} is not allowed; use the listed functions and arithmetic")
        if isinstance(node, ast.Call) and not (isinstance(node.func, ast.Name) and node.func.id in fns):
            raise FactError(f"{expr!r}: only these functions exist: {sorted(fns)}")
        if isinstance(node, ast.Name) and node.id not in fns:
            raise FactError(f"{expr!r}: unknown name {node.id!r}; table and column names are strings in quotes")
    try:
        v = eval(compile(tree, "<fact>", "eval"), {"__builtins__": {}}, fns)   # noqa: S307 (whitelisted AST)
    except FactError:
        raise
    except ZeroDivisionError as e:
        raise FactError(f"{expr!r}: division by zero") from e
    except Exception as e:
        raise FactError(f"{expr!r}: {type(e).__name__}: {e}") from e
    if isinstance(v, bool) or not isinstance(v, (int, float, str)):
        raise FactError(f"{expr!r}: gives {type(v).__name__}, not a number or a name")
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        raise FactError(f"{expr!r}: not a finite number")
    return v, calc.used


# ------------------------------------------------------------------ analysis.json

UNITS = {"%", "% of GDP", "% per year", "pp", "USD bn", "USD tn", "count", "countries", "months", "years", "times", "index",
         "score", "ratio", "rank", "text", "quarter", "month", "date", "year"}
DISPLAY = {"USD bn": {"en": "USD {v} bn"}, "USD tn": {"en": "USD {v} tn"}, "score": {"en": "{v}", "ko": "{v}"},
           "ratio": {"en": "{v}", "ko": "{v}"}, "rank": {"en": "{v}", "ko": "{v}"}, "index": {"en": "{v}", "ko": "{v}"}}


def _decimals(v, unit: str, asked) -> int:
    if isinstance(asked, int) and 0 <= asked <= 4:
        return asked
    if unit in ("count", "countries", "rank", "months", "years") and float(v).is_integer():
        return 0
    a = abs(v)
    return 0 if a >= 100 else 1 if a >= 10 else 2 if a < 1 and unit in ("ratio", "index") else 1


def _period(spec: dict, used: list[str], tables: dict, expr: str = "") -> str | None:
    if spec.get("period"):
        return str(spec["period"])
    # a panel column has its own period (rule C2): the goods window joined at the quarter, the lenders' quarter …
    import re
    if "panel" in used and "panel" in tables:
        t = tables["panel"]
        for c in t.get("columns") or []:
            if c.get("period") and re.search(rf"'{re.escape(c['id'])}'", expr):
                row = (re.search(r"cell\('panel',\s*'([^']+)'", expr) or [None, None])[1]
                r = next((x for x in t["rows"] if x.get("_key") == row), {}) if row else {}
                tp = t.get("period") or {}
                key = c["period"]
                if key == "goods_window" and r.get("goods_window_to"):
                    return f"{r.get('goods_window_from')}/{r['goods_window_to']}" + (" (partial)" if r.get("goods_window_partial") else "")
                if key in ("goods_window_newest", "products_window") and (r.get("goods_window_newest_to") or r.get("products_window_to")):
                    return f"12 months to {r.get('goods_window_newest_to') or r.get('products_window_to')}"
                if key == "lenders_quarter" and r.get("lenders_quarter"):
                    return str(r["lenders_quarter"])
                if key == "chokepoint_year" and r.get("chokepoint_year"):
                    return str(r["chokepoint_year"])
                if key == "stress_quarter":
                    return str(tp.get("stress_quarter") or tp.get("funding_quarter"))
                break
    for name in used:
        p = tables[name].get("period") or {}
        w = p.get("goods_window") if isinstance(p.get("goods_window"), dict) else None
        got = p.get("shown") or p.get("funding_quarter") or (w and f"{w.get('from')}/{w.get('to')}")
        if got:
            return str(got)
    return None


def compute(specs: list[dict], tables: dict[str, dict], start: int = 1, existing: list[dict] | None = None) -> tuple[list[dict], list[dict]]:
    """Evaluate fact requests [{label, expr, unit, decimals?, period?, note?}] → (facts, problems). A request that
    fails is reported with why, never guessed. Ids continue from `start`; a request that repeats an existing
    expression returns the existing fact."""
    facts, problems = [], []
    seen = {f["formula"]: f for f in existing or []}
    n = start
    for spec in specs:
        expr = str(spec.get("expr") or "").strip()
        label = str(spec.get("label") or "").strip()
        unit = str(spec.get("unit") or "").strip() or "count"
        if not expr or not label:
            problems.append({"request": spec, "problem": "label and expr are both needed"})
            continue
        key = str(spec.get("key") or "").strip()
        if key and not re.fullmatch(r"[a-z][a-z0-9_]{0,30}", key):
            problems.append({"request": {"label": label, "expr": expr}, "problem": f"key {key!r}: lower-case letters, digits and _ only"})
            key = ""
        if expr in seen:
            if key and not seen[expr].get("key"):
                seen[expr]["key"] = key          # a claim may name the existing fact by the key asked for now
            continue
        try:
            v, used = evaluate(expr, tables)
        except FactError as e:
            problems.append({"request": {"label": label, "expr": expr}, "problem": str(e)})
            continue
        if isinstance(v, str):
            unit = "text"
        elif unit == "text":
            unit = "count"
        if unit not in UNITS:
            problems.append({"request": {"label": label, "expr": expr}, "problem": f"unit {unit!r} is not one of {sorted(UNITS)}"})
            continue
        f = {"id": f"F{n}", "label": label, "value": v, "unit": unit, "formula": expr,
             "inputs": _inputs(expr, used), "tables": used, "publishable": True,
             "period": _period(spec, used, tables, expr)}
        if not isinstance(v, str):
            f["display"] = {"decimals": _decimals(v, unit, spec.get("decimals")), **DISPLAY.get(unit, {})}
        if spec.get("note"):
            f["note"] = str(spec["note"])
        if key and not any(x.get("key") == key for x in list(seen.values())):
            f["key"] = key                       # the name a claim uses for this fact before it has an id (claims.resolve)
        facts.append(f)
        seen[expr] = f
        n += 1
    return facts, problems


def _inputs(expr: str, used: list[str]) -> list[str]:
    """The datasets a fact is cited to. A fact read from the panel is cited to the views its columns came from (the
    board, the country sheets …), not to the whole join, so a note's sources list only what it used."""
    import re
    from .panel import views_of
    out = []
    for t in used:
        ids = [dataset_id(v) for v in views_of(re.findall(r"[a-z][a-z0-9_]{2,}", expr))] if t == "panel" else [dataset_id(t)]
        out += [i for i in (ids or [dataset_id(t)]) if i not in out]
    return out


def save(run: Path, facts: list[dict]) -> None:
    write_json(run / "analysis" / "analysis.json", {"facts": facts, "method": "desk: expressions over API tables (artools/desk/facts.py)"})


def load(run: Path) -> list[dict]:
    return (read_json(run / "analysis" / "analysis.json", {}) or {}).get("facts", [])


def sheet(facts: list[dict], lang: str = "en") -> str:
    """The fact sheet a writer or reviewer reads: token, rendered value, what it is, period, where from."""
    from ..content import render_fact
    lines = []
    for f in facts:
        shown = render_fact(f, lang)
        lines.append(f"{{{{{f['id']}}}}} = {shown} — {f['label']}"
                     + (f" · period {f['period']}" if f.get("period") else "")
                     + f" · from {', '.join(f.get('tables') or [])} · cite [[{']] [['.join(f['inputs'])}]]"
                     + (f" · note: {f['note']}" if f.get("note") else ""))
    return "\n".join(lines)
