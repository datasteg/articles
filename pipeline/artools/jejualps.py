"""Read-only access to the jejualps archive (a Postgres database).

Every connection is opened with default_transaction_read_only=on and a statement timeout, whatever role the URL
names. The URL comes from ARTICLES_DATABASE_URL (articles/.env), else from jejualps' own .env (DATABASE_URL).
"""
from __future__ import annotations

import re
import unicodedata

from .paths import JEJUALPS_ENV, die, env_value

MIN_BODY_CHARS = 3000      # shorter bodies were mostly junk pages (jejualps quality gate)
_conn = None


def conn():
    global _conn
    if _conn:
        return _conn
    import psycopg
    url = env_value("ARTICLES_DATABASE_URL") or env_value("DATABASE_URL", [JEJUALPS_ENV])
    if not url:
        die("no database URL: set ARTICLES_DATABASE_URL in articles/.env")
    try:
        _conn = psycopg.connect(url, connect_timeout=5, autocommit=True,
                                options="-c default_transaction_read_only=on -c statement_timeout=60000")
    except Exception as e:  # never print the URL (it carries the password)
        die(f"cannot connect to the jejualps database: {type(e).__name__}")
    return _conn


def q(sql: str, params=()) -> list[dict]:
    with conn().cursor() as cur:
        cur.execute(sql, params)
        cols = [c.name for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def ping() -> dict:
    r = q("select count(*) n, max(published_date) filter (where published_date <= current_date) newest from documents")[0]
    c = q("select count(*) n from doc_cards")[0]
    return {"ok": True, "documents": r["n"], "newest": r["newest"], "cards": c["n"],
            "read_only": q("show default_transaction_read_only")[0]["default_transaction_read_only"]}


def _filters(date_from: str | None, date_to: str | None, units: list[str] | None) -> tuple[list[str], list]:
    where, params = ["d.published_date is not null", "d.published_date <= current_date",
                     "coalesce(d.text_chars, 0) >= %s"], [MIN_BODY_CHARS]
    if date_from:
        where.append("d.published_date >= %s")
        params.append(date_from)
    if date_to:
        where.append("d.published_date <= %s")
        params.append(date_to)
    if units:
        where.append("s.unit = any(%s)")
        params.append(units)
    return where, params


def search_total(query: str, fields: str, where: list[str], params: list) -> int:
    if fields == "meta":
        return q(f"""select count(*) n from documents d join sources s on s.id = d.source_id
                     where d.meta_tsv @@ to_tsquery('simple', %s) and {' and '.join(where)}""", [query, *params])[0]["n"]
    return q(f"""select count(distinct c.doc_id) n from doc_chunks c join documents d on d.id = c.doc_id
                 join sources s on s.id = d.source_id
                 where c.tsv @@ to_tsquery('simple', %s) and {' and '.join(where)}""", [query, *params])[0]["n"]


def search_lines(query: str, fields: str = "meta", date_from: str | None = None, date_to: str | None = None,
                 units: list[str] | None = None, limit: int = 30, snippet: bool = True, detail: str = "lean") -> dict:
    """What `artools jejualps search` prints: jejualps' search_lines() (same selection and order as search() below),
    one short line per document. `text` is the abstract (300 characters), else "summary: " + a model summary that
    must never be quoted; links, authors and text_sha1 come from cite()."""
    where, params = _filters(date_from, date_to, units)
    rows = q("select search_lines(%s, %s, %s::date, %s::date, %s::text[], %s, %s, %s) l",
             [query, fields, date_from, date_to, units or None, limit, "auto" if snippet else "none", detail])
    lines = [r["l"] for r in rows]
    return {"query": query, "fields": fields, "total": search_total(query, fields, where, params),
            "shown": len(lines), "results": lines}


def cite(doc_ids: list[int]) -> list[dict]:
    """Citation fields for Evidence doc blocks (url, pdf_url, authors_text, text_sha1, kind …), in the order asked."""
    return [r["c"] for r in q("select cite(%s::bigint[]) c", [doc_ids])]


def search(query: str, fields: str = "meta", date_from: str | None = None, date_to: str | None = None,
           units: list[str] | None = None, limit: int = 40, snippet: bool = True) -> dict:
    """Ranked full-text search, full rows. The CLI prints search_lines() instead; this stays as the baseline that
    jejualps' replay scripts (extraction/premise2/eval_*.py) measure against. The index uses the 'simple'
    configuration: no stemming, so write word forms yourself (spread:*, france | french).
    `fields`: meta = title + abstract; body = the text chunks."""
    where, params = _filters(date_from, date_to, units)
    if fields == "meta":
        sql = f"""
          select d.id, d.published_date date, s.unit, d.institution, d.series, d.title, d.doc_url, d.landing_url,
                 d.pdf_url, d.text_chars, (dc.doc_id is not null) carded,
                 ts_rank(d.meta_tsv, to_tsquery('simple', %s)) rank, null::int hits,
                 left(coalesce(d.abstract, ''), 600) abstract
          from documents d join sources s on s.id = d.source_id left join doc_cards dc on dc.doc_id = d.id
          where d.meta_tsv @@ to_tsquery('simple', %s) and {' and '.join(where)}
          order by rank desc, d.published_date desc limit %s"""
        rows = q(sql, [query, query, *params, limit])
    else:
        sql = f"""
          with hit as (
            select c.doc_id, count(*) hits, max(ts_rank(c.tsv, to_tsquery('simple', %s))) rank
            from doc_chunks c where c.tsv @@ to_tsquery('simple', %s) group by c.doc_id)
          select d.id, d.published_date date, s.unit, d.institution, d.series, d.title, d.doc_url, d.landing_url,
                 d.pdf_url, d.text_chars, (dc.doc_id is not null) carded, hit.rank, hit.hits,
                 left(coalesce(d.abstract, ''), 600) abstract
          from hit join documents d on d.id = hit.doc_id join sources s on s.id = d.source_id
          left join doc_cards dc on dc.doc_id = d.id
          where {' and '.join(where)}
          order by hit.rank * ln(1 + hit.hits) desc, d.published_date desc limit %s"""
        rows = q(sql, [query, query, *params, limit])
    total = search_total(query, fields, where, params)
    for r in rows:
        r["ref"] = f"jejualps:{r['id']}"
        r["url"] = r.pop("landing_url") or r["doc_url"]
        r["rank"] = round(float(r["rank"] or 0), 4)
        if not snippet:
            r.pop("abstract")
    return {"query": query, "fields": fields, "total": total, "shown": len(rows), "results": rows}


def doc(doc_id: int) -> dict:
    rows = q("""select d.id, d.published_date date, s.unit, s.institution src_institution, d.institution, d.series,
                       d.title, d.authors, d.speaker, d.speaker_role, d.doc_url, d.landing_url, d.pdf_url, d.jel,
                       d.abstract, d.text_chars, d.text_sha1, d.doc_number, (dc.doc_id is not null) carded,
                       (select count(*) from doc_chunks c where c.doc_id = d.id) chunks
                from documents d join sources s on s.id = d.source_id left join doc_cards dc on dc.doc_id = d.id
                where d.id = %s""", [doc_id])
    if not rows:
        die(f"no document {doc_id}")
    r = rows[0]
    r["ref"] = f"jejualps:{doc_id}"
    r["url"] = r.pop("landing_url") or r["doc_url"]
    return r


def card(doc_id: int) -> dict:
    rows = q("select card_kind, skill_version, card from doc_cards where doc_id = %s", [doc_id])
    if not rows:
        return {"doc": doc_id, "card": None, "note": "no research card for this document; use chunks"}
    r = rows[0]
    c = r["card"].get("card", r["card"])
    return {"doc": doc_id, "kind": r["card_kind"], "version": r["skill_version"], "card": c}


def segments(doc_id: int, kinds: list[str] | None = None, max_chars: int = 30000) -> dict:
    sql = "select seg_id, kind, path, page, text from doc_segments where doc_id = %s"
    params: list = [doc_id]
    if kinds:
        sql += " and kind = any(%s)"
        params.append(kinds)
    sql += " order by char_start nulls last, seg_id"
    rows, used = [], 0
    for r in q(sql, params):
        if used + len(r["text"] or "") > max_chars:
            break
        used += len(r["text"] or "")
        rows.append(r)
    return {"doc": doc_id, "segments": rows, "chars": used}


def chunks(doc_id: int, around: str | None = None, start: int | None = None, count: int = 3,
           max_chars: int = 24000) -> dict:
    """Read a document's text: the chunks matching `around` (websearch syntax, e.g. "spread risk aversion"),
    or `count` chunks from `start` (ord). Chunks are ~4,000 characters and concatenate back to the full text."""
    total = q("select count(*) n from doc_chunks where doc_id = %s", [doc_id])[0]["n"]
    if around:
        rows = q("""select ord, txt, ts_rank(tsv, websearch_to_tsquery('simple', %s)) rank from doc_chunks
                    where doc_id = %s and tsv @@ websearch_to_tsquery('simple', %s)
                    order by rank desc limit %s""", [around, doc_id, around, count])
        if not rows:   # fall back to OR-ing the words
            ors = " | ".join(re.findall(r"\w+", around))
            rows = q("""select ord, txt, ts_rank(tsv, to_tsquery('simple', %s)) rank from doc_chunks
                        where doc_id = %s and tsv @@ to_tsquery('simple', %s) order by rank desc limit %s""",
                     [ors, doc_id, ors, count])
        rows.sort(key=lambda r: r["ord"])
    else:
        s = start or 0
        rows = q("select ord, txt from doc_chunks where doc_id = %s and ord >= %s and ord < %s order by ord",
                 [doc_id, s, s + count])
    used, outrows = 0, []
    for r in rows:
        t = r["txt"]
        if used + len(t) > max_chars:
            t = t[: max(0, max_chars - used)]
        used += len(t)
        outrows.append({"chunk": r["ord"], "text": t})
        if used >= max_chars:
            break
    return {"doc": doc_id, "chunks_total": total, "chunks": outrows}


# ------------------------------------------------------------------ quotes

_LIGATURES = {"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl", "’": "'", "‘": "'", "“": '"', "”": '"',
              "–": "-", "—": "-", "−": "-", "­": "", " ": " "}


def normalise(text: str) -> tuple[str, list[int]]:
    """Whitespace collapsed, PDF line-end hyphenation joined, ligatures and typographic quotes unified.
    Returns the normalised text and, for each of its characters, the index in the original."""
    text = unicodedata.normalize("NFKC", text)
    out, idx = [], []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == "-" and i + 1 < n and text[i + 1] == "\n":          # hyphenated line break: "credit-\nrisk"
            j = i + 1
            while j < n and text[j].isspace():
                j += 1
            i = j
            continue
        ch = _LIGATURES.get(ch, ch)
        if ch == "" :
            i += 1
            continue
        if ch.isspace():
            if out and out[-1] == " ":
                i += 1
                continue
            ch = " "
        for c in ch:
            out.append(c)
            idx.append(i)
        i += 1
    return "".join(out).strip(), idx


def full_text(doc_id: int) -> str:
    return "".join(r["txt"] for r in q("select txt from doc_chunks where doc_id = %s order by ord", [doc_id]))


def verify_quote(doc_id: int, quote: str, text: str | None = None) -> dict:
    text = text if text is not None else full_text(doc_id)
    norm, idx = normalise(text)
    nq, _ = normalise(quote)
    if len(nq) < 20:
        return {"verified": False, "reason": "quote shorter than 20 characters"}
    pos = norm.find(nq)
    interrupted = None
    if pos < 0:
        interrupted = _interrupted_match(norm, nq)
        if interrupted:
            pos = interrupted.pop("pos")
    if pos < 0:
        # case-insensitive match is reported but does not verify: a quote must be verbatim
        ci = norm.lower().find(nq.lower())
        return {"verified": False, "reason": "not found verbatim" + ("; matches ignoring case" if ci >= 0 else ""),
                "doc_chars": len(text)}
    start = idx[pos]
    chunk_rows = q("select ord, char_start from doc_chunks where doc_id = %s order by ord", [doc_id])
    chunk = max((r["ord"] for r in chunk_rows if r["char_start"] <= start), default=0)
    res = {"verified": True, "chunk": chunk, "offset": start, "text_sha1": text_sha1(doc_id)}
    if interrupted:
        res["interrupted"] = interrupted
        res["note"] = ("verbatim except for a page artifact inside it (a footnote or page number from the PDF); "
                       "prefer a sentence that reads cleanly if the paper has one")
    return res


def _interrupted_match(norm: str, nq: str, max_gap: int = 300) -> dict | None:
    """The quote, verbatim, split in two by a PDF page artifact: a footnote or page number dropped into the
    sentence at a page break. Accepted only if the inserted text is short and starts like a footnote."""
    cuts = [i for i, ch in enumerate(nq) if ch == " "]
    for cut in sorted(cuts, key=lambda c: -min(c, len(nq) - c)):   # try balanced splits first
        head, tail = nq[:cut], nq[cut + 1:]
        if len(head) < 15 or len(tail) < 15:
            continue
        p = norm.find(head)
        while p >= 0:
            after = p + len(head)
            t = norm.find(tail, after, after + max_gap + len(tail) + 2)
            if t >= 0:
                gap = norm[after:t].strip()
                if gap and re.match(r"^(\d{1,3}\s|\d{1,3}$|\*|†|page \d)", gap, re.I):
                    return {"pos": p, "skipped": gap[:max_gap]}
            p = norm.find(head, p + 1)
    return None


def text_sha1(doc_id: int) -> str | None:
    r = q("select text_sha1 from documents where id = %s", [doc_id])
    return r[0]["text_sha1"] if r else None
