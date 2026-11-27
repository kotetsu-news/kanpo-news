import datetime
import os
import re
from google import genai
from google.genai import types
from google.genai.errors import APIError
import pypdf
from PIL import Image
import streamlit as st

# ==========================================
# 設定エリア（モデル名などはここで一括管理）
# ==========================================
MODEL_NAME = "gemini-3.8-flash"

# 1. Gemini APIの設定
API_KEY = None
try:
    API_KEY = st.secrets.get("GEMINI_API_KEY")
except Exception:
    pass

if not API_KEY:
    API_KEY = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=API_KEY) if API_KEY else None


# 2. 官報を解析してグループ分け・X投稿案・官報News用JSONを一括作成する関数
def generate_x_posts_batch(
    combined_text, image_list, target_keyword, header_tag, issue_label, target_date_str
):
    if not client:
        return "⚠️ APIキーが設定されていません。環境変数または secrets.toml を確認してください。"

    target_instruction = (
        f"特に【 {target_keyword} 】に関する部分に絞って"
        if target_keyword
        else "全体の中から社会・ビジネスに影響する主要なものを抽出して"
    )

    prompt = f"""
あなたは「難解な官報や国の動きを、一般人やビジネスパーソン向けに分かりやすく届ける『官報速報』およびアーカイブサイト『官報News』の編集長」です。

提供された官報の情報（目次テキスト、複数PDFの抽出テキスト、または複数画像）をすべて照合し、{target_instruction}以下の2つを同時に作成してください。
※目次テキストとPDF本文の両方が入力されている場合は、目次で「正確な法令名・号数（括弧内の漢数字など）・全体件数」を確定させ、PDF本文から「施行期日や具体的な改正内容・影響」を補完して最も正確な要約を作成してください。

1. **X（旧Twitter）投稿用の要約セット**
2. **ホームページ「官報News」（kanpo_data.json）追記用のJSONデータ**

【⚠️超重要：法律・政令・省令番号の絶対厳守ルール】
- 記載されている実際の番号（例：法律第86号、政令第358号、農林水産省令第75号、防衛省令第27・28号 など）を**一文字たりとも変えず、推測や捏造をせず、正確にそのまま**記載してください。
- 目次に漢数字（例：（三五八）、（七五））で書かれている場合は、正しい算用数字（例：第358号、第75号）に変換してください。
- 架空の番号を出力することは絶対に禁止です。

【必須制約ルール】
1. **個人情報の厳重除外**: 個人の破産、帰化、叙勲、特定の個人名が含まれる情報は絶対に除外してください。
2. **対象情報**: 法律・政令・省令の改正、閣議決定、国の重要施策など「社会やビジネスに影響する事項」に絞ってください。
3. **本数に応じたグループ化（まとめ投稿）ルール（超重要）**:
   - **掲載法令が1〜2本の日**：1本ずつ個別に投稿案・記事を作成する。
   - **掲載法令が3本以上ある日**：連投を防ぐため、テーマ・省庁・関連法ごとに分類し、**全体で最大4〜5投稿（記事）程度にグループ化（集約）**してください。
     - 同系統の法令（例：種苗振興関連4本、電気事業法関連2本など）は1つのグループにまとめる。
     - 国民生活への影響が特に大きいものや独立した重要法案は1本単独で立ててよい。
4. **X本投稿のフォーマット・文字数制限（絶対厳守）**:
   - 1投稿あたり**必ず全角140文字以内**（絵文字・ハッシュタグ含む）。
   - 行頭のタグは必ず **{header_tag}** から始め、内容に合う絵文字を1つ添えること。
   - 「結局何が変わるのか・何の分野か」を簡潔に書き、末尾に「詳細はリプ欄へ👇」と厳選ハッシュタグ（2〜3個）を付けること。
5. **Xリプライ用案内テキストの文字数・表記ルール（絶対厳守）**:
   - リプライ用テキストも**必ず全角140文字以内**（URL `https://kanpo.go.jp/` を含めて140文字以内）に収めること。
   - **1〜2本の投稿の場合**：法令の正式名称と番号を記載する。
   - **3本以上まとめた投稿の場合**：文字数オーバーを防ぐため正式名称のフル表記は避け、**「・法令番号（短縮した簡潔な件名）」の箇条書き形式**にして、確実に140文字以内に収めること。
6. **ホームページ「官報News」用JSONデータの作成ルール（超重要）**:
   - X投稿で作成した各グループと**1対1で対応する記事オブジェクト**を作成する。
   - `"date"` は必ず `"{target_date_str}"` とする。
   - `"issue_type"` は必ず `"{issue_label}"` とする。
   - `"category"` は必ず次の4つのうち最も適切な1つだけを選ぶ（表記ゆれ厳禁）：
     - `"経済・産業・中小企業"`
     - `"都市・建築・環境"`
     - `"くらし・医療・労務"`
     - `"行政・防衛・その他"`
   - `"title"` は一般人にも内容がすぐ伝わるニュース見出し（30〜45文字程度）。
   - `"summary"` は**140字制限を気にせず、Xでは書ききれなかった改正の背景・誰にどんな影響があるか・実務上の注目点を200〜300文字程度で分かりやすく丁寧な日本語で解説**すること（目次情報のみの場合は推測で断定せず、法令名から読み取れる制度の目的や影響範囲を正確に記述すること）。
   - `"laws"` はそのグループに含まれるすべての法令の**「法令番号（正式名称）」**を配列（リスト）で漏らさず記載する。
   - 出力するJSONは、既存の `kanpo_data.json` の先頭（`[` の直後）にそのまま貼り付けて追記できるよう、**外側の `[` `]` を付けず、各 `{ ... }` ブロックの末尾すべてにカンマ `,` を付けた形式**にすること。

【出力形式の指定】
はじめに「📊 本日のまとめ構成（全◯投稿）」としてグループ分けの概要を2〜3行で示し、続けて各X投稿を以下の形式で出力してください。

----
### ① 【テーマ名】（◯本まとめ / 単独）
■ 本投稿（140字以内）
（ここに投稿文）

▼ リプライ用案内テキスト（140字以内）
🔗 本日の号外（または官報）一覧（◯◯関連）
・法令番号（短縮件名）
https://kanpo.go.jp/
----

すべてのX投稿案を出力したあと、最後に必ず以下の区切りタグを使って「官報News」追記用のJSONブロックを出力してください。

===JSON_START===
  {{
    "date": "{target_date_str}",
    "issue_type": "{issue_label}",
    "category": "4つのカテゴリのいずれか",
    "title": "ニュース見出し",
    "summary": "140字制限を超えたわかりやすい詳細解説（200〜300文字程度）",
    "laws": [
      "法令番号（正式名称）"
    ]
  }},
===JSON_END===
"""

    # 送信データの組み立て（テキスト＋画像の併用に対応）
    contents = []
    if image_list:
        contents.extend(image_list)

    full_prompt = prompt
    if combined_text.strip():
        full_prompt = f"【入力された官報テキスト（目次・PDF抽出文）】\n{combined_text}\n\n{prompt}"
    contents.append(full_prompt)

    try:
        # 高速化のため思考時間（thinking_budget）を最小限にして呼び出し
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=contents,
                config=types.GenerateContentConfig(
                    thinking_config=types.ThinkingConfig(thinking_budget=0)
                ),
            )
        except Exception:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=contents,
            )
        return response.text

    except APIError as e:
        if "503" in str(e) or "UNAVAILABLE" in str(e):
            return "⏳ 現在Geminiサーバーが非常に混雑しています（エラー 503）。\n1〜2分ほど待ってから、もう一度ボタンを押してみてください！"
        else:
            return f"⚠️ APIエラーが発生しました: {e}"
    except Exception as e:
        return f"⚠️ 予期せぬエラーが発生しました: {e}"


# --- 3. Streamlit UI画面 ---
st.set_page_config(page_title="官報速報 X投稿＆官報News作成アプリ", page_icon="📜", layout="centered")

st.title("📜 官報速報 X投稿＆官報News作成アプリ")
st.caption("目次テキストと複数のPDF・画像を同時に読み込み、X投稿セットと「官報News」追記用JSONを一括作成します")

# 日付と官報の種類の選択（横並び）
col_type, col_date = st.columns([2, 1])
with col_type:
    issue_type = st.radio(
        "📌 官報の種類を選択",
        ["通常号（【官報速報】）", "号外（【号外速報】）"],
        horizontal=True,
    )
with col_date:
    jst = datetime.timezone(datetime.timedelta(hours=9))
    today_jst = datetime.datetime.now(jst).date()
    selected_date = st.date_input("📅 発行日（官報News用）", value=today_jst)

header_tag = "【号外速報】" if "号外" in issue_type else "【官報速報】"
issue_label = "号外" if "号外" in issue_type else "本紙"
target_date_str = selected_date.strftime("%Y-%m-%d")

# 特定の省令キーワード絞り込み（任意）
target_keyword = st.text_input(
    "🎯 特定の分野・番号だけに絞る場合（空欄なら全体を自動でグループ分けします）",
    placeholder="例：防衛省、第一号、など（通常は空欄でOK）",
)

st.divider()

# ① 目次・本文テキスト入力（単独でもPDFと併用でもOK）
st.subheader("① 目次・本文テキストを貼り付け（任意・PDFとの併用で精度アップ）")
user_input = st.text_area(
    "Web版官報の目次やテキストを貼り付けてください（下のPDFアップロードと両方同時に使えます）",
    placeholder="例：\n政令\n重要品種の育成及びその種苗の生産の振興に関する法律の施行期日を定める政令（三五九） 3\n...",
    height=150,
)

# ② PDF・複数画像アップロード（全PDFの全ページ読み込み対応）
st.subheader("② 官報ページ（複数PDF / 複数画像）をアップロード（任意）")
uploaded_files = st.file_uploader(
    "官報のPDF（複数ファイルOK・全ページ自動結合）または画像（PNG/JPG・複数枚OK）を選択してください",
    type=["pdf", "png", "jpg", "jpeg"],
    accept_multiple_files=True,
)

pdf_extracted_text = ""
image_list = []

if uploaded_files:
    pdf_files = [f for f in uploaded_files if f.name.lower().endswith(".pdf")]
    img_files = [f for f in uploaded_files if not f.name.lower().endswith(".pdf")]

    if pdf_files:
        try:
            total_pages = 0
            all_pdf_texts = []
            for pdf_file in pdf_files:
                reader = pypdf.PdfReader(pdf_file)
                file_pages = len(reader.pages)
                total_pages += file_pages
                file_text_parts = []
                for idx, page in enumerate(reader.pages):
                    text = page.extract_text()
                    if text:
                        file_text_parts.append(f"[{pdf_file.name} - {idx+1}ページ目]\n{text}")
                if file_text_parts:
                    all_pdf_texts.append("\n".join(file_text_parts))

            pdf_extracted_text = "\n\n".join(all_pdf_texts)
            if pdf_extracted_text.strip():
                st.success(
                    f"PDFの読み込みに成功しました！（全 {len(pdf_files)} ファイル / 合計 {total_pages} ページ）"
                )
            else:
                st.warning("⚠️ PDFから文字を抽出できませんでした。画像（PNG/JPG）としてアップロードしてみてください。")
        except Exception as e:
            st.error(f"PDFの読み込み中にエラーが発生しました: {e}")

    if img_files:
        try:
            cols = st.columns(min(len(img_files), 3))
            for idx, img_file in enumerate(img_files):
                img = Image.open(img_file)
                # 高速化のため白黒（グレースケール）変換 ＋ 長辺1200pxに軽量化
                img = img.convert("L")
                img.thumbnail((1200, 1200))
                image_list.append(img)
                with cols[idx % 3]:
                    st.image(img, caption=f"{idx+1}枚目（軽量化済）", use_container_width=True)

            st.success(f"画像 {len(image_list)} 枚の軽量読み込みに成功しました！")
        except Exception as e:
            st.error(f"画像の読み込み中にエラーが発生しました: {e}")

if st.button("✨ X投稿セット＆官報News用データを一括生成する", type="primary", use_container_width=True):
    # 目次テキストとPDF抽出テキストを結合
    combined_parts = []
    if user_input.strip():
        combined_parts.append(f"=== 【貼り付けられた目次・テキスト】 ===\n{user_input.strip()}")
    if pdf_extracted_text.strip():
        combined_parts.append(f"=== 【アップロードされたPDF本文】 ===\n{pdf_extracted_text.strip()}")

    combined_text = "\n\n".join(combined_parts)

    if not combined_text and not image_list:
        st.warning("⚠️ 目次テキストを入力するか、官報ファイル（PDF/画像）をアップロードしてください。")
    else:
        with st.spinner("目次とPDF・画像を照合して、X投稿グループと官報News用記事を作成中..."):
            raw_output = generate_x_posts_batch(
                combined_text,
                image_list,
                target_keyword,
                header_tag,
                issue_label,
                target_date_str,
            )

            if raw_output.startswith("⏳") or raw_output.startswith("⚠️"):
                st.warning(raw_output)
            else:
                # X投稿部分とJSON部分を分離する
                x_part = raw_output
                json_part = ""
                match = re.search(
                    r"===JSON_START===\s*(.*?)\s*===JSON_END===",
                    raw_output,
                    re.DOTALL,
                )
                if match:
                    x_part = raw_output[: match.start()].strip()
                    json_part = match.group(1).strip()

                st.success("生成が完了しました！X投稿と「官報News」への反映にご活用ください。")

                # 1. X投稿セット表示
                st.subheader("📝 本日のX投稿セット（グループ分け済）")
                st.text_area(
                    "コピペ用出力結果（確認・微調整しながらお使いください）",
                    value=x_part,
                    height=400,
                )

                # 2. 官報News追記用JSON表示
                if json_part:
                    st.divider()
                    st.subheader("🌐 「官報News」追記用データ（kanpo_data.json用）")
                    st.caption(
                        "GitHubの `kanpo-news` 内にある `kanpo_data.json` を開き、"
                        "一番上の `[` のすぐ下の行にそのまま貼り付けて保存（Commit changes）してください。"
                    )
                    st.code(json_part, language="json")