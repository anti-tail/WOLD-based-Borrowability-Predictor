#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
wold_borrowability.py — 任意の調査項目リストを WOLD (World Loanword Database) の
意味項目に対応づけ，借用可能性スコア（Borrowed_score）の低い順に並べる汎用ツール．

使い方（3段階）
  1) index   : WOLD の CLDF データ（zip でもフォルダでも可）から索引 JSON を作る
       python wold_borrowability.py index wold-v4.2.zip -o wold_index.json
  2) suggest : 項目リスト（TSV: id, label[, gloss]）に WOLD 候補を自動で付ける
       python wold_borrowability.py suggest items.tsv -i wold_index.json -o mapping.tsv
     → mapping.tsv の wold 列を人手で確認・修正する（ここが本作業）
  3) rank    : 確定した対応表から，スコア順の一覧（TSV と HTML）を作る
       python wold_borrowability.py rank mapping.tsv -i wold_index.json -o ranked.tsv --html ranked.html

対応表（mapping.tsv）の書式
  id      項目の識別子（地図番号など）
  label   項目名（日本語）
  gloss   （任意）英語の訳語。suggest の照合に使う
  wold    WOLD 意味項目 ID をセミコロン区切りで。先頭が主対応。
          意味分野の平均で代理させるときは FIELD:The body のように書く
  match   直接 / 近義 / 代理 / なし のいずれか
  note    自由記述
  他の列はそのまま出力に引き継がれる

スコアの定義
  primary : 先頭 ID のスコア（並べ替えの既定値）
  max     : 候補中の最大値（保守的な判定用）
  rank    : WOLD 中核 1460 項目中の「借用されにくさ」順位（1 が最も借用されにくい）
"""
import argparse, csv, io, json, re, sys, unicodedata, zipfile
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------- index
def _open_cldf(src):
    """zip でもフォルダでも cldf/parameters.csv と cldf/forms.csv を開く."""
    src = Path(src)
    if src.suffix == ".zip":
        z = zipfile.ZipFile(src)
        names = z.namelist()
        def op(fname):
            n = next(x for x in names if x.endswith("cldf/" + fname))
            return io.TextIOWrapper(z.open(n), encoding="utf-8")
        return op
    base = src if (src / "parameters.csv").exists() else src / "cldf"
    return lambda fname: open(base / fname, encoding="utf-8")

def build_index(src, lang="Japanese"):
    op = _open_cldf(src)
    params = list(csv.DictReader(op("parameters.csv")))
    core = [p for p in params if "999" not in p["ID"] and p["Borrowed_score"]]
    # 借用されにくさ順位（スコア昇順，同点は同順位）
    scores = sorted(float(p["Borrowed_score"]) for p in core)
    def rank_of(s):
        import bisect
        return bisect.bisect_left(scores, s) + 1
    fields = defaultdict(list)
    for p in core:
        fields[p["Semantic_field"]].append(float(p["Borrowed_score"]))
    meanings = {}
    for p in params:
        if not p["Borrowed_score"]:
            continue
        s = float(p["Borrowed_score"])
        is_core = "999" not in p["ID"]
        meanings[p["ID"]] = {
            "id": p["ID"], "name": p["Name"], "concepticon": p.get("Concepticon_Gloss", ""),
            "field": p["Semantic_field"], "category": p.get("Semantic_category", ""),
            "score": round(s, 4), "core": is_core,
            "rank": rank_of(s) if is_core else None,
            "age": float(p["Age_score"]) if p.get("Age_score") else None,
            "simplicity": float(p["Simplicity_score"]) if p.get("Simplicity_score") else None,
            "forms": [],  # 指定言語の語形
        }
    # 指定言語の語形（照合キー兼・参考情報）
    if lang:
        for f in csv.DictReader(op("forms.csv")):
            if f["Language_ID"] != lang or f["Parameter_ID"] not in meanings:
                continue
            meanings[f["Parameter_ID"]]["forms"].append({
                "form": f["Form"], "script": (f.get("original_script") or "").strip(),
                "borrowed": (f.get("Borrowed") or "").strip(),
                "source": (f.get("borrowed_base") or f.get("loan_history") or "").strip()[:80],
            })
    return {
        "source": str(src), "language": lang, "n_core": len(core),
        "field_means": {k: round(sum(v) / len(v), 4) for k, v in fields.items()},
        "meanings": meanings,
    }

# ---------------------------------------------------------------- kana → romaji
_K = dict(zip(
    "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわゐゑをんがぎぐげござじずぜぞだぢづでどばびぶべぼぱぴぷぺぽぁぃぅぇぉゃゅょっー",
    "a i u e o ka ki ku ke ko sa shi su se so ta chi tsu te to na ni nu ne no ha hi fu he ho ma mi mu me mo ya yu yo ra ri ru re ro wa i e o n ga gi gu ge go za ji zu ze zo da ji zu de do ba bi bu be bo pa pi pu pe po a i u e o ya yu yo Q -".split()))

def kana2romaji(s):
    s = "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)
    out = []
    for c in s:
        r = _K.get(c)
        if r is None:
            out.append(c); continue
        if c in "ゃゅょ" and out and out[-1].endswith("i") and len(out[-1]) > 1:
            base = out.pop()[:-1]
            if base in ("sh", "ch", "j"):
                r = base + r[1:]
            else:
                r = base + r
        out.append(r)
    t = "".join(out)
    t = re.sub(r"Q([a-z])", r"\1\1", t).replace("Q", "")
    t = re.sub(r"n(?=[bmp])", "n", t)
    return t

def norm_roman(s):
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("ou", "o").replace("oo", "o").replace("uu", "u").replace("-", "")
    return re.sub(r"[^a-z]", "", s)

def clean_label(label):
    """〈…〉や（…）や「前部分」などを外し，検索語の候補を返す."""
    t = re.sub(r"〈[^〉]*〉|\([^)]*\)|（[^）]*）|［[^］]*］|\[[^\]]*\]", " ", label)
    t = re.sub(r"(前部分|後部分|その\d+|一般的な名称|特殊な名称|の詳細図)", " ", t)
    parts = [(p, 1.0) for p in re.split(r"[\s・／/,，、]+", t) if p]
    inner = re.findall(r"〈([^〉]*)〉|（([^）]*)）|\(([^)]*)\)", label)
    for g in inner:
        for x in g:
            for p in re.split(r"[\s・／/,，、をがにのでは]+", x):
                if p: parts.append((p, 0.4 if parts else 1.0))   # 括弧内（文脈語）は弱く効かせる
    return parts

# ---------------------------------------------------------------- suggest
def suggest(index, label, gloss="", k=5):
    """ラベル（漢字・かな）と英語訳語から WOLD 候補を点数づけして返す."""
    M = index["meanings"]
    cands = defaultdict(float)
    keys = clean_label(label)
    for key, wt in keys:
        pure_kana = bool(re.fullmatch(r"[ぁ-ゖァ-ヶー]+", key))
        kr = norm_roman(kana2romaji(key)) if pure_kana else ""
        has_kanji = bool(re.search(r"[一-龯々]", key))
        stem = re.sub(r"[ぁ-ゖ]+$", "", key) if has_kanji else ""   # 送り仮名を外した語幹
        for mid, m in M.items():
            if not m["core"]:
                continue
            for f in m["forms"]:
                toks = [t.strip() for t in re.split(r"[,、，/・;；\s]+", re.sub(r"\(.*?\)|（.*?）", "", f["script"])) if t.strip()]
                if key in toks:
                    cands[mid] += 10 * wt
                elif stem and len(stem) >= 1 and any(re.sub(r"[ぁ-ゖ]+$", "", t) == stem for t in toks):
                    cands[mid] += 7 * wt
                elif has_kanji and len(key) >= 2 and any(key in t for t in toks):
                    cands[mid] += 3 * wt
                if kr and len(kr) >= 2 and norm_roman(f["form"]) == kr:
                    cands[mid] += 8 * wt
    if gloss:
        for g in re.split(r"[;,/]", gloss):
            g = g.strip().lower()
            if not g: continue
            for mid, m in M.items():
                if not m["core"]: continue
                nm = re.sub(r"^(the|to) ", "", m["name"].lower())
                nm = re.sub(r"\(\d\)", "", nm).strip()
                gg = re.sub(r"^(the|to) ", "", g)
                if nm == gg or gg in [x.strip() for x in re.split(r" or |/", nm)]:
                    cands[mid] += 9
                elif re.search(r"\b" + re.escape(gg) + r"\b", nm):
                    cands[mid] += 3
                elif m["concepticon"] and gg.upper() == m["concepticon"]:
                    cands[mid] += 9
    best = sorted(cands.items(), key=lambda x: (-x[1], M[x[0]]["score"]))[:k]
    return [(mid, sc) for mid, sc in best]

# ---------------------------------------------------------------- resolve / rank
def resolve(index, spec):
    """'4-2;4-14' や 'FIELD:The body' を [(id, name, score, rank)] に."""
    out = []
    for tok in [t.strip() for t in re.split(r"[;；]", spec or "") if t.strip()]:
        if tok.upper().startswith("FIELD:"):
            fld = tok.split(":", 1)[1].strip()
            fm = index["field_means"].get(fld)
            if fm is None:
                raise SystemExit(f"未知の意味分野: {fld}")
            out.append({"id": tok, "name": f"[{fld} 分野平均]", "score": fm, "rank": None, "field": fld, "forms": []})
        else:
            m = index["meanings"].get(tok)
            if m is None:
                raise SystemExit(f"WOLD に無い ID: {tok}")
            out.append(m)
    return out

def jp_forms(m):
    return " / ".join(
        f"{f['script'] or f['form']}〈{f['form']}〉{'' if f['borrowed'].startswith('5') else '[' + f['borrowed'][:1] + ']'}"
        for f in m.get("forms", [])[:4])

def rank_rows(index, rows, threshold=0.15):
    out = []
    for r in rows:
        ms = resolve(index, r.get("wold", ""))
        o = dict(r)
        if ms:
            p = ms[0]
            o.update({
                "primary_id": p["id"], "primary_meaning": p["name"], "field": p.get("field", ""),
                "score": f"{p['score']:.3f}", "rank": p["rank"] or "",
                "max_score": f"{max(m['score'] for m in ms):.3f}",
                "all_candidates": " | ".join(f"{m['name']} {m['score']:.3f}" for m in ms),
                "wold_japanese": jp_forms(p),
                "judgement": "除外" if p["score"] > threshold else "採用",
            })
        else:
            o.update({"primary_id": "", "primary_meaning": "", "field": "", "score": "", "rank": "",
                      "max_score": "", "all_candidates": "", "wold_japanese": "", "judgement": "対応なし"})
        out.append(o)
    out.sort(key=lambda o: (o["score"] == "", float(o["score"] or 9), str(o.get("id"))))
    for i, o in enumerate(out, 1):
        o["order"] = i
    return out

# ---------------------------------------------------------------- io helpers
def read_tsv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))

def write_tsv(path, rows, cols=None):
    cols = cols or list(dict.fromkeys(k for r in rows for k in r))
    f = open(path, "w", encoding="utf-8", newline="") if path != "-" else sys.stdout
    w = csv.DictWriter(f, fieldnames=cols, delimiter="\t", extrasaction="ignore", lineterminator="\n")
    w.writeheader(); w.writerows(rows)

def load_index(path):
    return json.load(open(path, encoding="utf-8"))

# ---------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    a = sp.add_parser("index", help="WOLD CLDF から索引 JSON を作る")
    a.add_argument("wold"); a.add_argument("-o", "--out", default="wold_index.json")
    a.add_argument("--lang", default="Japanese", help="参照語形を取り込む言語 (WOLD の Language_ID)")
    b = sp.add_parser("suggest", help="項目リストに候補を付ける")
    b.add_argument("items"); b.add_argument("-i", "--index", default="wold_index.json")
    b.add_argument("-o", "--out", default="-"); b.add_argument("-k", type=int, default=5)
    c = sp.add_parser("rank", help="対応表からスコア順一覧を作る")
    c.add_argument("mapping"); c.add_argument("-i", "--index", default="wold_index.json")
    c.add_argument("-o", "--out", default="-"); c.add_argument("--threshold", type=float, default=0.15)
    c.add_argument("--html", help="一覧・対応づけ用 HTML の出力先（任意）")
    c.add_argument("--name", default="対応表", help="HTML に表示するデータセット名")
    d = sp.add_parser("lookup", help="WOLD 意味項目を語で検索")
    d.add_argument("query"); d.add_argument("-i", "--index", default="wold_index.json")
    args = ap.parse_args(argv)

    if args.cmd == "index":
        idx = build_index(args.wold, args.lang)
        json.dump(idx, open(args.out, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"{len(idx['meanings'])} meanings (core {idx['n_core']}) → {args.out}", file=sys.stderr)
    elif args.cmd == "suggest":
        idx = load_index(args.index); M = idx["meanings"]; rows = read_tsv(args.items)
        for r in rows:
            label = r.get("label") or r.get("項目") or ""
            sug = suggest(idx, label, r.get("gloss", ""), args.k)
            r.setdefault("wold", sug[0][0] if sug else "")
            r.setdefault("match", "要確認")
            r["candidates"] = " | ".join(f"{mid} {M[mid]['name']} ({M[mid]['score']:.3f})" for mid, _ in sug)
        write_tsv(args.out, rows)
    elif args.cmd == "rank":
        idx = load_index(args.index)
        out = rank_rows(idx, read_tsv(args.mapping), args.threshold)
        write_tsv(args.out, out)
        if args.html:
            sys.path.insert(0, str(Path(__file__).parent))
            from wold_viewer import render_html
            Path(args.html).write_text(render_html(idx, read_tsv(args.mapping), args.name), encoding="utf-8")
    elif args.cmd == "lookup":
        idx = load_index(args.index)
        for mid, sc in suggest(idx, args.query, args.query, 10):
            m = idx["meanings"][mid]
            print(f"{mid}\t{m['name']}\t{m['score']:.3f}\t#{m['rank']}\t{jp_forms(m)}")

if __name__ == "__main__":
    main()
