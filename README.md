# WOLD-based Borrowability Predictor

調査項目のリスト（方言地図の項目、辞典の見出し語、語彙調査票など）を [World Loanword Database (WOLD)](https://wold.clld.org) の意味項目に対応づけ、借用されやすさ（Borrowed_score）の低い順に並べるツールです。系統解析に使う語彙項目を、借用されにくいものから選ぶ作業を想定しています。

*English summary:* Maps an arbitrary list of survey items (e.g. dialect-atlas maps or dictionary headwords) onto WOLD meanings and ranks them by WOLD's borrowed score, to help select borrowing-resistant items for phylogenetic analysis. Python 3.8+, standard library only. Candidate suggestion uses the Japanese forms in WOLD plus English glosses; any WOLD language can be used with `--lang`.

## 必要なもの

- Python 3.8 以上（標準ライブラリのみ。追加インストールは不要）
- WOLD の CLDF データ（このリポジトリには含めていません。下記から取得してください）
  - <https://github.com/lexibank/wold/releases> の zip（例：`wold-v4.2.zip`）。zip のままでも、展開したフォルダでも使えます。

## 使い方

作業は 3 段階です。

### 1. 索引を作る（初回のみ）

```sh
python wold_borrowability.py index wold-v4.2.zip -o wold_index.json
```

WOLD の 1814 意味項目（中核 1460 項目）のスコア、意味分野、分野平均、日本語の語形と借用判定をまとめた `wold_index.json` ができます。日本語以外の語形を照合に使う場合は `--lang` に WOLD の Language_ID を指定します（例：`--lang Mandarin`）。

### 2. 項目リストに候補を付ける

項目リストはタブ区切り（TSV, UTF-8）で、列は `id`・`label`（項目名）・任意で `gloss`（英語訳。`;` 区切りで複数可）です。

```sh
python wold_borrowability.py suggest examples/items.tsv -o mapping.tsv
```

`mapping.tsv` に `wold`（自動で選んだ主候補）、`match`（`要確認`）、`candidates`（上位候補）が付きます。候補は次の手がかりから点数をつけて選びます。

- WOLD の日本語語形（漢字表記）との一致、送り仮名を除いた語幹の一致
- かな書きの項目名をローマ字にして WOLD の語形と一致するか
- 英語訳と WOLD の意味項目名（Concepticon の訳語を含む）との一致

**自動候補はあくまで出発点です。** `wold` 列と `match` 列を必ず人が確認・修正してください（下の「対応表の書き方」）。

### 3. スコア順の一覧を作る

```sh
python wold_borrowability.py rank mapping.tsv -o ranked.tsv --html ranked.html --name "調査項目"
```

- `ranked.tsv`：スコアの低い順に並べた一覧（主対応、分野、スコア、順位、日本語語形、判定）
- `ranked.html`：ブラウザで開く単一ファイルのページ（後述）
- `--threshold 0.15`：これを超えるスコアを「除外」と判定します（既定 0.15）

### WOLD の語を調べる

```sh
python wold_borrowability.py lookup 蛙
python wold_borrowability.py lookup "to sit"
```

## 対応表の書き方

| 列 | 内容 |
|---|---|
| `id` | 項目の識別子（地図番号など） |
| `label` | 項目名 |
| `gloss` | 任意。英語訳 |
| `wold` | WOLD 意味項目 ID をセミコロン区切りで。**先頭が主対応**（例 `15-57;15-56`）。対応する意味がない場合は `FIELD:The body` のように意味分野の平均で代理させられます。空欄なら「対応なし」 |
| `match` | `直接` / `近義` / `代理` / `なし` |
| `note`, `memo` | 自由記述 |

これ以外の列はそのまま出力に引き継がれます。記入例は [`examples/mapping.tsv`](examples/mapping.tsv) を見てください。

## スコアの定義

- **score（主対応）**：`wold` 列先頭の意味項目の Borrowed_score。WOLD の 41 言語で、その意味を表す語が借用語である度合いの平均です（0＝どの言語でも借用なし、1＝すべて借用）。
- **max_score**：`wold` 列に挙げた候補のうちの最大値。保守的に判定したいときに使います。
- **rank**：中核 1460 項目の中で、借用されにくい順に数えた順位（1 が最も借用されにくい）。同点は同順位です。
- **分野平均**：中核 1460 項目だけで計算した意味分野ごとの平均。
- ID に `999` を含む項目（例 `3-99929 the mole`）は一部の言語にだけある追加項目で、標本が少なくスコアが 0 や 1 に偏るため、順位と候補の自動選択から外しています。指定すれば対応には使えます。

## HTML ページでできること

`--html` で作ったページは、データを埋め込んだ単一ファイルなので、オフラインでも開けます。

- **一覧**：スコア順の表と、全項目の分布図。閾値と並べ替えの基準（主対応 / 最大値）を画面で変えられます。対応種別ごとの絞り込み、検索もできます。
- **対応づけ**：項目リストを貼り付けるか TSV を読み込むと、候補を付けて表示します。候補をクリックすると主対応が入れ替わり、Shift を押しながらだと副対応に追加されます。修正した対応表とスコア順一覧は TSV でコピーできます。変更はそのブラウザにだけ保存されます。
- **WOLD 意味項目**：全意味項目をスコア順に表示し、意味分野や語で検索できます。ID のコピーもできます。

## 注意

- WOLD の Borrowed_score は 41 言語の平均値で、特定の言語や地域での借用されやすさを直接示すものではありません。
- 方言調査の項目は WOLD の意味項目と一対一に対応しないことが多く、近義の項目や分野平均で代理させる判断が結果を大きく左右します。代理の根拠は `note` 列に残しておくことをおすすめします。
- 自動候補は漢字表記が WOLD の日本語語形と一致する項目ではよく当たりますが、かな書きの形容詞や、文脈語を含む項目名（例「〈幼児を〉負う」）では外れやすくなります。

## データの出典とライセンス

このリポジトリには WOLD のデータを含めていません。ツールが作る `wold_index.json` と HTML ページには WOLD のデータが含まれます。WOLD の CLDF データは [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) で公開されているので、これらを公開・配布する場合は次の出典を明記してください。

- Haspelmath, Martin & Uri Tadmor (eds.) 2009. *World Loanword Database.* Leipzig: Max Planck Institute for Evolutionary Anthropology. <https://wold.clld.org>
- lexibank/wold（CLDF 版）：使用したリリースの DOI。<https://github.com/lexibank/wold>
