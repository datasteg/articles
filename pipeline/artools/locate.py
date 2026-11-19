"""How a reader finds a cited series on the provider's own site: one short paragraph per data source, in each
language, built from the Dataset records (table path, item names, series keys). The references show it under the
"Data source" link, because most providers' links open a home page or a whole dataset, not the series.
A record may carry its own `locate` ({"en": …, "ko": …}), written by the fetch skill; it wins."""
from __future__ import annotations

import re

CYCLE = {"A": ("annual", "연간(A)"), "Q": ("quarterly", "분기(Q)"), "M": ("monthly", "월(M)"), "D": ("daily", "일(D)")}


def _checks(rec: dict) -> list[dict]:
    return (rec.get("validation") or {}).get("checks", []) or []


def _ecos(recs: list[dict]) -> dict:
    table = path = None
    items: dict[str, list[str]] = {}
    cycles = []
    for r in recs:
        for c in _checks(r):
            d = str(c.get("detail") or "")
            if c.get("check") == "table" and not table:
                m = re.match(r"^(\w+):\s*(.+?)\s*(?:\(searchable:.*\))?$", d)
                if m:
                    table, path = m.group(1), m.group(2)
            m = re.match(r"^item \d+$", c.get("check") or "") and re.match(r"^(.+?):\s*(\S+)\s+(.+?),\s*\d{4,}", d)
            name_ = re.sub(r"\s*\(under .*\)$", "", m.group(3)) if m else None   # the log notes the parent item in English
            if m and name_ not in items.setdefault(m.group(1), []):
                items[m.group(1)].append(name_)
        parts = str(r.get("key", "")).split("/")
        table = table or parts[0]
        if len(parts) > 1 and parts[1] not in cycles:
            cycles.append(parts[1])
    name = (path or "").split(" > ")[-1] if path else None
    name = re.sub(r"^[\d.]+\s*", "", name) if name else None
    cyc_en = " or ".join(CYCLE.get(c, (c, c))[0] for c in cycles) or "the cycle you want"
    cyc_ko = " 또는 ".join(CYCLE.get(c, (c, c))[1] for c in cycles) or "원하는 주기"
    sel = "; ".join(f"{g}: {', '.join(v)}" for g, v in items.items())
    where_en = (f"type the table name “{name}” or its code {table} in the search box, or follow the statistics list "
                f"{path}") if path else f"search for the table code {table}"
    where_ko = (f"검색창에 통계표 이름 ‘{name}’ 또는 코드 {table}를 입력하거나, 통계 목록에서 {path} 순서로 찾아 들어간다"
                ) if path else f"통계표 코드 {table}를 검색한다"
    en = (f"On ECOS (ecos.bok.or.kr), open 통계검색 (Statistics search) and {where_en}. "
          + (f"In the table, select {sel}. " if sel else "")
          + f"Set the cycle (주기) to {cyc_en}, choose the period, and click 조회 (Search).")
    ko = (f"한국은행 경제통계시스템(ECOS, ecos.bok.or.kr)에서 ‘통계검색’을 열고 {where_ko}. "
          + (f"통계표에서 항목을 다음과 같이 고른다: {sel}. " if sel else "")
          + f"주기를 {cyc_ko}로 정하고 기간을 고른 뒤 ‘조회’를 누른다.")
    return {"en": en, "ko": ko}


def _fred(recs: list[dict]) -> dict:
    ids = list(dict.fromkeys(str(r["key"]) for r in recs))
    if len(ids) == 1:
        return {"en": f"The link opens the FRED series {ids[0]} directly. Use “Edit Graph” to change the dates or "
                      f"units, and “Download” for the data.",
                "ko": f"링크를 누르면 FRED의 {ids[0]} 시리즈가 바로 열린다. ‘Edit Graph’로 기간과 단위를 바꾸고, "
                      f"‘Download’로 자료를 내려받을 수 있다."}
    rest = ", ".join(ids[1:])
    return {"en": f"The link opens the FRED series {ids[0]}. The others ({rest}) open the same way at "
                  f"fred.stlouisfed.org/series/ followed by the ID, or type the ID in FRED's search box.",
            "ko": f"링크는 FRED의 {ids[0]} 시리즈를 연다. 나머지({rest})는 fred.stlouisfed.org/series/ 뒤에 "
                  f"ID를 붙이거나 FRED 검색창에 ID를 입력하면 열린다."}


def _ecb(recs: list[dict]) -> dict:
    keys = list(dict.fromkeys(str(r["key"]) for r in recs))
    ds = keys[0].split(".")[0]
    if len(keys) == 1:
        return {"en": f"The link opens the series {keys[0]} directly in the ECB Data Portal (dataset {ds}), with a "
                      f"chart, the data table and a download button.",
                "ko": f"링크를 누르면 ECB 데이터 포털의 {keys[0]} 시리즈(데이터셋 {ds})가 차트, 자료표, 내려받기 버튼과 "
                      f"함께 바로 열린다."}
    rest = ", ".join(keys[1:])
    return {"en": f"The link opens {keys[0]} in the ECB Data Portal. The other series ({rest}) are in the same "
                  f"dataset {ds}: replace the series key at the end of the link, or type the key in the portal's "
                  f"search box.",
            "ko": f"링크는 ECB 데이터 포털의 {keys[0]}를 연다. 나머지 시리즈({rest})도 같은 데이터셋 {ds}에 있다. "
                  f"링크 끝의 시리즈 키를 바꾸거나 포털 검색창에 키를 입력하면 된다."}


def _eurostat(recs: list[dict]) -> dict:
    code, dims = None, {}
    for r in recs:
        for k in (r["key"] if isinstance(r["key"], list) else [r["key"]]):
            c, _, q = str(k).partition("?")
            code = code or c
            for kv in q.split("&"):
                if "=" in kv:
                    d, v = kv.split("=", 1)
                    if v not in dims.setdefault(d, []):
                        dims[d].append(v)
    sel = "; ".join(f"{d} = {', '.join(v)}" for d, v in dims.items())
    defs = {(r.get("definition") or "").strip().rstrip(".") for r in recs}
    label = "; ".join(dict.fromkeys(x.strip() for x in defs.pop().split(";"))) if len(defs) == 1 else ""
    en = (f"The link opens dataset {code} in Eurostat's Data Browser. Use the filters above the table "
          f"(“Customise your dataset”) to select" + (f" {label}" if label else " the series")
          + (f"; in codes: {sel}" if sel else "") + ".")
    ko = (f"링크는 Eurostat 데이터 브라우저의 데이터셋 {code}를 연다. 표 위의 필터(‘Customise your dataset’)에서 "
          + (f"다음을 고른다: {label}" if label else "해당 시리즈를 고른다")
          + (f". 코드로는 {sel}이다." if sel else "."))
    return {"en": en, "ko": ko}


def _generic(recs: list[dict]) -> dict:
    r = recs[0]
    keys = ", ".join(dict.fromkeys(str(x["key"]) for x in recs))
    name = r.get("title") or r.get("indicator")
    return {"en": f"The link opens {r.get('provider')}. Search there for “{name}” (series {keys}).",
            "ko": f"링크는 {r.get('provider')}를 연다. 그곳에서 ‘{name}’(시리즈 {keys})를 검색한다."}


def locate(recs: list[dict]) -> dict:
    """{"en": …, "ko": …} for the Dataset records grouped into one source."""
    own = next((r["locate"] for r in recs if isinstance(r.get("locate"), dict) and r["locate"].get("en")), None)
    if own:
        return own
    prov = str(recs[0].get("provider") or "")
    if "ECOS" in prov:
        return _ecos(recs)
    if prov.startswith("FRED"):
        return _fred(recs)
    if prov.startswith("ECB"):
        return _ecb(recs)
    if prov.startswith("Eurostat"):
        return _eurostat(recs)
    return _generic(recs)
