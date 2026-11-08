"""対応表を埋め込んだ単一ファイル HTML（一覧・対応づけ・WOLD 検索）を生成する."""
import json
from pathlib import Path

TEMPLATE = Path(__file__).with_name("viewer_template.html")

def compact_index(idx):
    out = []
    for m in idx["meanings"].values():
        out.append({"id": m["id"], "name": m["name"], "field": m["field"], "score": m["score"],
                    "rank": m["rank"], "core": m["core"],
                    "jp": [[f["script"], f["form"], (f["borrowed"][:1] if f["borrowed"] else "")] for f in m["forms"]]})
    return out

def render_html(idx, mapping_rows, name="対応表"):
    keep = ("id", "label", "gloss", "wold", "match", "note", "memo", "digitized", "prior_review", "volume")
    rows = [{k: r.get(k, "") for k in keep if k in r or k in ("id", "label", "wold", "match", "note")} for r in mapping_rows]
    t = TEMPLATE.read_text(encoding="utf-8")
    j = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return (t.replace("/*WOLD*/null", j(compact_index(idx)))
             .replace("/*FIELDMEANS*/null", j(idx["field_means"]))
             .replace("/*DATASET*/null", j({"name": name, "rows": rows})))
