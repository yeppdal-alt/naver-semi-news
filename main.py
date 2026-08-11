"""
멀티 섹션 뉴스 감성 분석 대시보드 (Streamlit Cloud 배포용)
반도체 / 금리 / 이란 전쟁 세 섹션을 동일한 신문형 포맷으로 보여준다.

- 데이터 소스: 네이버 뉴스 검색 API
  API 가이드: https://guide.ncloud-docs.com/docs/home 참고
- 인증: Streamlit secrets의 NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 사용
  (하드코딩 금지. .streamlit/secrets.toml 또는 Streamlit Cloud > Settings > Secrets 에 등록)
"""

import re
import html
from datetime import datetime, timedelta

import requests
import plotly.graph_objects as go
import streamlit as st

# ----------------------------------------------------------------------------
# 설정
# ----------------------------------------------------------------------------

NAVER_NEWS_URL = "https://naverapihub.apigw.ntruss.com/search/v1/news"

TOP_N = 5  # 감성별 표시 기사 수
FETCH_DISPLAY = 30  # 키워드당 조회 건수 (제목 필터링 후에도 top5를 채우기 위해 넉넉히 확보)
DESC_TRUNCATE_RATIO = 0.5  # 기사 요약 길이 축소 비율
DESC_MIN_LEN = 35  # 축소 시 최소 보장 길이

# 신문 편집 톤앤매너 (딥그린 + 세리프 + 오프화이트)
GREEN = "#1b4332"
NEG_RED = "#7a2a1f"
NEUTRAL_GRAY = "#5c5c58"
SENTIMENT_COLORS = {"긍정": GREEN, "부정": NEG_RED, "중립": NEUTRAL_GRAY}

# ----------------------------------------------------------------------------
# 섹션(토픽) 정의 — 각 섹션은 같은 포맷으로 렌더링됨
# ----------------------------------------------------------------------------

SEMI_KEYWORDS = ["반도체", "삼성전자 반도체", "SK하이닉스", "HBM", "파운드리", "메모리 반도체"]
SEMI_POS = [
    "급등", "사상 최대", "역대 최대", "호황", "수주", "공급계약", "목표주가 상향",
    "상향", "증설", "투자 확대", "신기록", "흑자전환", "실적 서프라이즈", "훈풍", "강세",
]
SEMI_NEG = [
    "급락", "부진", "적자", "감산", "구조조정", "목표주가 하향", "하향", "규제",
    "재고 증가", "가격 하락", "위축", "우려", "쇼크", "약세", "감원",
]

RATE_KEYWORDS = ["기준금리", "한국은행 금리", "미국 기준금리", "연준 금리", "금리 인하", "국고채 금리"]
RATE_POS = [
    "금리 인하", "인하 기대", "비둘기파", "완화적", "인하 단행", "피벗",
    "긴축 완화", "금리 동결", "물가 안정",
]
RATE_NEG = [
    "금리 인상", "매파", "긴축", "물가 상승", "인플레이션 우려", "국채금리 급등",
    "긴축 기조", "고금리 장기화", "금리 쇼크",
]

IRAN_KEYWORDS = ["이란 전쟁", "이란 이스라엘", "중동 분쟁", "이란 공습", "호르무즈 해협", "이란 미사일"]
IRAN_POS = [
    "휴전", "협상 타결", "갈등 완화", "긴장 완화", "종전", "평화협정", "확전 자제", "휴전 합의",
]
IRAN_NEG = [
    "공습", "확전", "미사일 공격", "사상자", "전면전", "보복", "긴장 고조",
    "무력 충돌", "폭격", "군사 개입", "긴급 사태",
]

TOPICS = [
    {
        "id": "semiconductor",
        "kicker": "Semiconductor Sector · Live Sentiment Wire",
        "title": "반도체 뉴스 감성 대시보드",
        "keywords": SEMI_KEYWORDS,
        "pos_words": SEMI_POS,
        "neg_words": SEMI_NEG,
        "filterable": True,
    },
    {
        "id": "rates",
        "kicker": "Interest Rates · Live Sentiment Wire",
        "title": "금리 뉴스 감성 섹션",
        "keywords": RATE_KEYWORDS,
        "pos_words": RATE_POS,
        "neg_words": RATE_NEG,
        "filterable": False,
    },
    {
        "id": "iran_war",
        "kicker": "Iran Conflict · Live Sentiment Wire",
        "title": "이란 전쟁 뉴스 감성 섹션",
        "keywords": IRAN_KEYWORDS,
        "pos_words": IRAN_POS,
        "neg_words": IRAN_NEG,
        "filterable": False,
    },
]

st.set_page_config(page_title="뉴스 감성 대시보드", layout="wide")

NEWSPAPER_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+KR:wght@400;700&display=swap');

.stApp { background-color: #faf9f5; }
.block-container { padding-top: 3.5rem !important; max-width: 1200px; }

.np-kicker {
    font-size: 11px; letter-spacing: .08em; text-transform: uppercase;
    color: #5c5c58; margin: 0.4rem 0 6px 0; line-height: 1.6;
}
.np-title {
    font-family: 'Noto Serif KR', Georgia, serif;
    font-size: 38px; font-weight: 700; margin: 0 0 12px 0; color: #1a1a1a;
    line-height: 1.3;
}
.np-rule { border-top: 3px solid #1a1a1a; border-bottom: 1px solid #1a1a1a; height: 4px; margin-bottom: 22px; }
.np-section-label {
    display: inline-block; background: #1b4332; color: #fff;
    font-size: 11px; font-weight: 600; letter-spacing: .1em; text-transform: uppercase;
    padding: 4px 12px; margin: 10px 0 14px 0;
}
.np-heading {
    font-family: 'Noto Serif KR', Georgia, serif; font-size: 22px; font-weight: 700;
    margin: 6px 0 4px 0; padding-bottom: 6px; border-bottom: 3px solid #1a1a1a;
}
.np-quote {
    font-family: 'Noto Serif KR', Georgia, serif; font-style: italic; font-size: 17px;
    line-height: 1.6; border-left: 4px solid #1b4332; background: #ffffff;
    padding: 14px 20px; margin: 4px 0 10px 0;
}
.np-divider { border-top: 6px double #1a1a1a; margin: 44px 0 30px 0; }
[data-testid="stMetric"] {
    background: #ffffff; border-top: 2px solid #1a1a1a; border-radius: 0;
    padding: 10px 4px 6px 12px;
}
[data-testid="stMetricLabel"] p { text-transform: uppercase; letter-spacing: .06em; font-size: 11px !important; color: #5c5c58 !important; }
[data-testid="stMetricValue"] { font-family: 'Noto Serif KR', Georgia, serif; }

.np-col-header {
    display: inline-block; font-size: 12px; font-weight: 600; letter-spacing: .1em;
    text-transform: uppercase; color: #fff; padding: 4px 12px; margin-bottom: 14px;
}
.np-article { border-bottom: 1px solid #d8d6cd; padding: 13px 0; }
.np-article-title {
    font-family: 'Noto Serif KR', Georgia, serif; font-size: 16px; font-weight: 700;
    color: #1a1a1a; text-decoration: none; line-height: 1.35; display: block;
}
.np-article-title:hover { color: #1b4332; text-decoration: underline; }
.np-meta { font-size: 11px; letter-spacing: .03em; text-transform: uppercase; color: #5c5c58; margin: 6px 0 8px 0; }
.np-desc { font-family: 'Noto Serif KR', Georgia, serif; font-size: 14px; color: #3a3a37; line-height: 1.55; margin-bottom: 4px; }
.np-reason { font-size: 12px; color: #5c5c58; font-style: italic; }
</style>
"""


# ----------------------------------------------------------------------------
# 유틸
# ----------------------------------------------------------------------------

def strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text or "")
    return html.unescape(text)


def normalize_key(title: str) -> str:
    key = re.sub(r"[^0-9A-Za-z가-힣]", "", strip_html(title))
    return key[:18].lower()


def parse_pubdate(pub_date: str):
    try:
        # 예: 'Tue, 11 Aug 2026 21:42:00 +0900'
        return datetime.strptime(pub_date, "%a, %d %b %Y %H:%M:%S %z")
    except (ValueError, TypeError):
        return None


def shorten(text: str, ratio: float = DESC_TRUNCATE_RATIO, min_len: int = DESC_MIN_LEN) -> str:
    """기사 요약을 원래 길이의 절반 수준으로 축소한다."""
    text = (text or "").strip()
    if not text:
        return text
    target = max(min_len, int(len(text) * ratio))
    if len(text) <= target:
        return text
    cut = text[:target]
    last_space = cut.rfind(" ")
    if last_space > target * 0.6:
        cut = cut[:last_space]
    return cut.rstrip(" .,·") + "…"


def classify(text: str, pos_words, neg_words):
    pos_hit = any(w in text for w in pos_words)
    neg_hit = any(w in text for w in neg_words)
    if pos_hit and not neg_hit:
        return "긍정", "긍정 키워드 감지"
    if neg_hit and not pos_hit:
        return "부정", "부정 키워드 감지"
    return "중립", "뚜렷한 신호 없음"


# ----------------------------------------------------------------------------
# 네이버 뉴스 API 호출
# ----------------------------------------------------------------------------

def get_naver_headers():
    try:
        client_id = st.secrets["NAVER_CLIENT_ID"]
        client_secret = st.secrets["NAVER_CLIENT_SECRET"]
    except (KeyError, FileNotFoundError):
        st.error(
            "네이버 API 인증 정보가 없습니다. Streamlit secrets에 "
            "NAVER_CLIENT_ID / NAVER_CLIENT_SECRET을 등록해주세요. "
            "발급 방법은 https://guide.ncloud-docs.com/docs/home 를 참고하세요."
        )
        st.stop()
    # NAVER Cloud Platform 콘솔(VPC)에서 발급받은 애플리케이션은
    # X-Naver-Client-Id / X-Naver-Client-Secret 이 아니라 아래 두 헤더를 사용합니다.
    return {
        "X-NCP-APIGW-API-KEY-ID": client_id,
        "X-NCP-APIGW-API-KEY": client_secret,
    }


@st.cache_data(ttl=300, show_spinner=False)
def fetch_news_for_keyword(keyword: str, display: int = FETCH_DISPLAY):
    headers = get_naver_headers()
    params = {"query": keyword, "display": display, "sort": "date"}
    resp = requests.get(NAVER_NEWS_URL, headers=headers, params=params, timeout=10)
    resp.raise_for_status()
    items = resp.json().get("items", [])
    for it in items:
        it["_keyword"] = keyword
    return items


@st.cache_data(ttl=300, show_spinner=False)
def collect_all_news(keywords: tuple, pos_words: tuple, neg_words: tuple, max_age_days: int = 3):
    all_items = []
    for kw in keywords:
        try:
            all_items.extend(fetch_news_for_keyword(kw))
        except requests.RequestException as e:
            st.warning(f"'{kw}' 검색 중 오류: {e}")

    seen = {}
    cutoff = datetime.now().astimezone() - timedelta(days=max_age_days)

    for it in all_items:
        pub_dt = parse_pubdate(it.get("pubDate", ""))
        if pub_dt and pub_dt < cutoff:
            continue

        title = strip_html(it.get("title", ""))
        desc = strip_html(it.get("description", ""))

        # 검색 키워드가 제목에 실제로 포함된 기사만 채택 (본문/요약만 일치하는 기사는 제외)
        if it["_keyword"] not in title:
            continue

        key = normalize_key(title)

        if key in seen:
            seen[key]["keywords"].add(it["_keyword"])
            continue

        sentiment, reason = classify(title + " " + desc, pos_words, neg_words)
        seen[key] = {
            "title": title,
            "description": desc,
            "link": it.get("link") or it.get("originallink"),
            "pub_date": pub_dt,
            "pub_date_raw": it.get("pubDate", ""),
            "sentiment": sentiment,
            "reason": reason,
            "keywords": {it["_keyword"]},
        }

    rows = list(seen.values())
    rows.sort(key=lambda r: r["pub_date"] or datetime.min.replace(tzinfo=None), reverse=True)
    return rows


# ----------------------------------------------------------------------------
# UI
# ----------------------------------------------------------------------------

def section_label(text: str):
    st.markdown(f'<div class="np-section-label">{html.escape(text)}</div>', unsafe_allow_html=True)


def render_masthead(kicker: str, title: str):
    st.markdown(
        f'<div class="np-kicker">{html.escape(kicker)}</div>'
        f'<div class="np-title">{html.escape(title)}</div>'
        '<div class="np-rule"></div>',
        unsafe_allow_html=True,
    )


def render_topic(topic: dict, active_keywords: list, chart_key: str):
    render_masthead(topic["kicker"], topic["title"])

    if not active_keywords:
        st.info("키워드를 하나 이상 선택해주세요.")
        return

    with st.spinner(f"{topic['title']} 검색 중..."):
        articles = collect_all_news(
            tuple(active_keywords), tuple(topic["pos_words"]), tuple(topic["neg_words"])
        )

    if not articles:
        st.warning("최근 3일 이내 수집된 기사가 없습니다.")
        return

    counts = {"긍정": 0, "부정": 0, "중립": 0}
    for a in articles:
        counts[a["sentiment"]] += 1

    section_label("Top News")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("긍정 기사", counts["긍정"])
    col2.metric("부정 기사", counts["부정"])
    col3.metric("중립 기사", counts["중립"])
    col4.metric("전체 수집 건수", len(articles))

    if counts["긍정"] > counts["부정"]:
        tone = "긍정 기사가 부정 기사보다 많아 전반적으로 우호적인 뉴스 흐름입니다."
    elif counts["부정"] > counts["긍정"]:
        tone = "부정 기사가 우세해 주의가 필요한 뉴스 흐름입니다."
    else:
        tone = "긍정과 부정 기사가 비슷한 수준으로, 방향성이 뚜렷하지 않습니다."
    st.markdown(f'<div class="np-quote">{html.escape(tone)}</div>', unsafe_allow_html=True)

    section_label("Sentiment Trend")
    labels = ["긍정", "부정", "중립"]
    total = max(sum(counts[l] for l in labels), 1)
    fig = go.Figure()
    for l in labels:
        pct = counts[l] / total * 100
        fig.add_trace(
            go.Bar(
                y=["sentiment"],
                x=[counts[l]],
                orientation="h",
                name=l,
                marker_color=SENTIMENT_COLORS[l],
                text=f"{l} {counts[l]} ({pct:.0f}%)" if counts[l] > 0 else "",
                textposition="inside",
                insidetextanchor="middle",
                textfont=dict(color="#ffffff", size=12),
                hovertemplate=f"{l}: %{{x}}건<extra></extra>",
            )
        )
    fig.update_layout(
        barmode="stack",
        height=64,
        margin=dict(l=0, r=0, t=4, b=4),
        showlegend=False,
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        font=dict(family="Georgia, 'Noto Serif KR', serif", color="#1a1a1a"),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
    )
    st.plotly_chart(fig, use_container_width=True, key=chart_key)

    st.markdown(f'<h2 class="np-heading">Latest News · Top {TOP_N}</h2>', unsafe_allow_html=True)

    def top_articles(sentiment):
        return [a for a in articles if a["sentiment"] == sentiment][:TOP_N]

    col_pos, col_neg, col_neu = st.columns(3)

    def render_column(container, sentiment, color):
        items = top_articles(sentiment)
        container.markdown(
            f'<span class="np-col-header" style="background:{color}">{sentiment} ({len(items)})</span>',
            unsafe_allow_html=True,
        )
        if not items:
            container.write("해당하는 기사가 없습니다.")
            return
        cards = []
        for a in items:
            time_str = a["pub_date"].strftime("%m/%d %H:%M") if a["pub_date"] else a["pub_date_raw"]
            meta = f"{time_str} · {', '.join(sorted(a['keywords']))}"
            cards.append(
                '<div class="np-article">'
                f'<a class="np-article-title" href="{html.escape(a["link"] or "", quote=True)}" target="_blank" rel="noopener">{html.escape(a["title"])}</a>'
                f'<div class="np-meta">{html.escape(meta)}</div>'
                f'<div class="np-desc">{html.escape(shorten(a["description"]))}</div>'
                f'<div class="np-reason">{html.escape(a["reason"] or "")}</div>'
                '</div>'
            )
        container.markdown("".join(cards), unsafe_allow_html=True)

    render_column(col_pos, "긍정", SENTIMENT_COLORS["긍정"])
    render_column(col_neg, "부정", SENTIMENT_COLORS["부정"])
    render_column(col_neu, "중립", SENTIMENT_COLORS["중립"])

    st.caption(
        "※ 감성 분류는 키워드 기반 자동 분류입니다. 정교한 분류가 필요하면 "
        "LLM API(Claude 등)를 연동해 classify() 함수를 교체하세요."
    )


def main():
    st.markdown(NEWSPAPER_CSS, unsafe_allow_html=True)
    st.caption(
        "데이터 출처: 네이버 뉴스 검색 API · "
        "API 가이드: https://guide.ncloud-docs.com/docs/home"
    )

    with st.sidebar:
        st.header("필터")
        selected_semi_keywords = st.multiselect(
            "반도체 키워드", options=SEMI_KEYWORDS, default=SEMI_KEYWORDS
        )
        st.caption("금리 · 이란 전쟁 섹션은 고정 키워드 세트로 조회됩니다.")
        if st.button("새로고침 (전체 재조회)"):
            fetch_news_for_keyword.clear()
            collect_all_news.clear()
            st.rerun()

    for i, topic in enumerate(TOPICS):
        keywords = selected_semi_keywords if topic["filterable"] else topic["keywords"]
        render_topic(topic, keywords, chart_key=f"chart-{topic['id']}")
        if i < len(TOPICS) - 1:
            st.markdown('<div class="np-divider"></div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
