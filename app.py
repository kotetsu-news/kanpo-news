import json
import os
import streamlit as st

# ==========================================
# ページ基本設定
# ==========================================
st.set_page_config(
    page_title="官報News｜わかりやすく残す官報・法令アーカイブ",
    page_icon="📜",
    layout="centered",
)

# カスタムCSS（ニュースサイト風のカードデザイン・バッジ装飾）
st.markdown(
    """
    <style>
    .news-card {
        background-color: #ffffff;
        border: 1px solid #e0e4e8;
        border-left: 5px solid #1e3a8a;
        border-radius: 8px;
        padding: 16px 18px;
        margin-bottom: 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .news-card.gogai {
        border-left-color: #b91c1c;
    }
    .meta-row {
        font-size: 0.82rem;
        color: #555555;
        margin-bottom: 6px;
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        align-items: center;
    }
    .badge-normal {
        background-color: #1e3a8a;
        color: #ffffff;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 0.75rem;
    }
    .badge-gogai {
        background-color: #b91c1c;
        color: #ffffff;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 0.75rem;
    }
    .badge-cat {
        background-color: #f1f5f9;
        color: #334155;
        border: 1px solid #cbd5e1;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.75rem;
    }
    .news-title {
        font-size: 1.08rem;
        font-weight: bold;
        color: #0f172a;
        margin: 6px 0 8px 0;
        line-height: 1.45;
    }
    .news-summary {
        font-size: 0.93rem;
        color: #334155;
        line-height: 1.65;
        margin-bottom: 10px;
    }
    .law-box {
        background-color: #f8fafc;
        border-radius: 6px;
        padding: 10px 12px;
        font-size: 0.83rem;
        color: #475569;
    }
    .law-box ul {
        margin: 4px 0 0 0;
        padding-left: 18px;
    }
    .law-box li {
        margin-bottom: 3px;
    }
    @media (prefers-color-scheme: dark) {
        .news-card {
            background-color: #1e293b;
            border-color: #334155;
        }
        .news-title {
            color: #f8fafc;
        }
        .news-summary {
            color: #cbd5e1;
        }
        .meta-row {
            color: #94a3b8;
        }
        .badge-cat {
            background-color: #334155;
            color: #e2e8f0;
            border-color: #475569;
        }
        .law-box {
            background-color: #0f172a;
            color: #cbd5e1;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ==========================================
# データ読み込み関数
# ==========================================
DATA_FILE = "kanpo_data.json"


def load_articles():
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # 日付の新しい順に並べ替え
        return sorted(data, key=lambda x: x.get("date", ""), reverse=True)
    except Exception as e:
        st.error(f"記事データの読み込みに失敗しました: {e}")
        return []


# ==========================================
# ヘッダー
# ==========================================
st.title("📜 官報News")
st.caption("X（140字）では伝えきれない国の動き・法改正をわかりやすく整理して残すアーカイブサイト")

# メインナビゲーション（タブ）
tab_news, tab_guide, tab_links = st.tabs(
    ["📰 官報アーカイブ（一覧・検索）", "📖 初心者向け 官報用語ガイド", "🔗 公式一次情報リンク集"]
)

# ==========================================
# タブ1：官報アーカイブ（一覧・検索）
# ==========================================
with tab_news:
    articles = load_articles()

    st.info(
        "💡 **このサイトについて**：本家のインターネット版官報は直近90日分のみ無料公開されます。"
        "「官報News」では、社会や暮らしに関わる主要な法律・政令・省令の要点を整理して蓄積しています。"
    )

    # 検索・絞り込みエリア
    col1, col2 = st.columns([2, 1])
    with col1:
        search_word = st.text_input(
            "🔍 キーワード検索",
            placeholder="例：建築基準法、防衛省、給付金、2026-11-24 など",
        )
    with col2:
        categories = [
            "すべて",
            "経済・産業・中小企業",
            "都市・建築・環境",
            "くらし・医療・労務",
            "行政・防衛・その他",
        ]
        selected_cat = st.selectbox("📂 分野で絞り込み", categories)

    # フィルタリング処理
    filtered = []
    for art in articles:
        if selected_cat != "すべて" and art.get("category") != selected_cat:
            continue
        if search_word.strip():
            kw = search_word.strip().lower()
            target_text = (
                art.get("date", "")
                + art.get("title", "")
                + art.get("summary", "")
                + " ".join(art.get("laws", []))
            ).lower()
            if kw not in target_text:
                continue
        filtered.append(art)

    st.write(f"表示件数：**{len(filtered)} 件**（全 {len(articles)} 件中）")

    if not filtered:
        st.warning("条件に一致する記事が見つかりませんでした。検索ワードや分野を変更してみてください。")
    else:
        # 1ページあたりの表示件数（記事が増えても重くならないように15件ずつ表示）
        per_page = 15
        total_pages = max(1, (len(filtered) + per_page - 1) // per_page)
        page = 1
        if total_pages > 1:
            page = st.number_input(
                f"ページ選択（全 {total_pages} ページ）",
                min_value=1,
                max_value=total_pages,
                value=1,
                step=1,
            )

        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page

        for art in filtered[start_idx:end_idx]:
            is_gogai = art.get("issue_type") == "号外"
            card_class = "news-card gogai" if is_gogai else "news-card"
            badge_class = "badge-gogai" if is_gogai else "badge-normal"
            issue_label = art.get("issue_type", "本紙")
            date_str = art.get("date", "")
            cat_str = art.get("category", "その他")
            title_str = art.get("title", "")
            summary_str = art.get("summary", "")
            laws_list = art.get("laws", [])

            laws_html = "".join([f"<li>{law}</li>" for law in laws_list])

            card_html = f"""
            <div class="{card_class}">
                <div class="meta-row">
                    <span>📅 {date_str}</span>
                    <span class="{badge_class}">{issue_label}</span>
                    <span class="badge-cat">{cat_str}</span>
                </div>
                <div class="news-title">{title_str}</div>
                <div class="news-summary">{summary_str}</div>
                <div class="law-box">
                    <strong>📌 該当する法令・番号：</strong>
                    <ul>{laws_html}</ul>
                </div>
            </div>
            """
            st.markdown(card_html, unsafe_allow_html=True)

# ==========================================
# タブ2：初心者向け 官報用語ガイド
# ==========================================
with tab_guide:
    st.subheader("📖 一般人でもわかる「官報・法令」の基本用語")
    st.write("官報を読むときに出てくる独特の言葉や仕組みを、かみ砕いてまとめました。")

    with st.expander("1. 「法律・政令・省令・告示」は何が違う？", expanded=True):
        st.markdown(
            """
            ルールには「誰が決めたか」「どれくらい強い力があるか」の順番があります。
            * **法律（ほうりつ）**：**国会**の議決で作られる一番強いルール。（例：道路交通法、建築基準法）
            * **政令（せいれい）**：法律を実際に動かすために、**内閣（閣議決定）**が決める細かいルール。「施行令」とも呼ばれます。
            * **府令・省令（ふれい・しょうれい）**：各大臣（厚生労働大臣、国土交通大臣など）が自分の担当分野について決めるさらに細かい現場ルール。「施行規則」と呼ばれます。
            * **告示（こくじ）**：国や省庁が国民に公式に知らせる「お知らせ・基準値・指定」など。（例：薬価基準の改定、保安林の指定）
            """
        )

    with st.expander("2. 「本紙」と「号外」の違いは？", expanded=True):
        st.markdown(
            """
            * **本紙（ほんし）**：土日祝・年末年始を除き、原則**毎日（朝8時30分）**発行される通常版です。
            * **号外（ごうがい）**：本紙に載せきれない大量の法令や、予算・条約・白書・大量の公告などがある日に**追加で発行される特別版**です。年度末（3月）や国会閉会後などは、1日に何冊も号外が出ることがあります。
            """
        )

    with st.expander("3. 「公布日」と「施行日」の違いは？", expanded=True):
        st.markdown(
            """
            * **公布日（こうふび）**：官報に載って**「こういうルールが決まりました」と世の中に発表された日**です。当サイトで日々速報しているのは主にこの「公布」のタイミングです。
            * **施行日（しこうび）**：そのルールが**実際に効力を発揮し、スタートする日**です。「公布の日から施行」とすぐ始まるものもあれば、準備期間をおいて「令和○年4月1日から施行」となるものもあります。
            """
        )

    with st.expander("4. 「一部改正（いちぶかいせい）」ってどう読むの？", expanded=False):
        st.markdown(
            """
            日本の法律や省令は、まるごと作り直すのではなく、元の法律の「第○条の『A』を『B』に改める」という**修正パッチ方式（一部改正）**で更新されます。
            そのため官報の本文だけ見るとパズルのように読みにくいですが、改正の背景や「どこが変わるか」の要点をつかむことで世の中の動きが見えてきます。
            """
        )

    with st.expander("5. 官報に載る「公告（こうこく）」とは？", expanded=False):
        st.markdown(
            """
            法令以外に、裁判所や会社・自治体などが公式に知らせる欄です。会社の決算公告、合併・解散のお知らせ、破産手続、入札公告、資格試験の合格発表などが掲載されます。
            （※当サイトでは個人のプライバシー保護のため、個人の破産・帰化・叙勲等の情報は扱っていません）
            """
        )

# ==========================================
# タブ3：公式一次情報リンク集
# ==========================================
with tab_links:
    st.subheader("🔗 官報・法令の公式一次情報リンク集")
    st.write("原文の全文や最新の条文を確認したいときは、以下の国の公式データベースをご利用ください。")

    st.markdown(
        """
        * **[インターネット版官報（国立印刷局）](https://kanpo.go.jp/)**
          毎朝8時30分更新。直近90日分の官報（本紙・号外・政府調達など）のPDFを無料で閲覧できます。
        * **[e-Gov（イーガブ）法令検索](https://laws.e-gov.go.jp/)**
          現行の憲法・法律・政令・省令がすべて反映された最新条文を検索・閲覧できるデジタル庁の公式サイトです。
        * **[e-Gov パブリック・コメント（意見公募手続）](https://public-comment.e-gov.go.jp/)**
          政令や省令が官報に公布される前の「案」の段階で公表され、国民から意見を募集しているページです。これからどんな改正が来るかを先読みできます。
        * **[首相官邸（閣議案件）](https://www.kantei.go.jp/jp/kakugi/)**
          原則毎週火曜・金曜に行われる閣議で決定された法律案・政令・人事などの一覧が公開されています。
        * **[衆議院・参議院 議案情報](https://www.shugiin.go.jp/internet/itdb_gian.nsf/html/gian/menu.htm)**
          現在国会で審議されている法律案の提出理由や新旧対照表を確認できます。
        """
    )

st.divider()
st.caption("※本サイトは官報の公開情報をもとに要点整理・アーカイブ化した個人運営の情報サイトです。正確な原文・法的効力については必ず国立印刷局の『インターネット版官報』をご確認ください。")