"""
멀티 섹션 뉴스 브리핑 대시보드 (Streamlit Cloud 배포용)
반도체 / 금리 / 이란 전쟁 세 섹션을 동일한 포맷으로 보여준다.

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

TOP_N = 5  # 논조별 표시 기사 수
FETCH_DISPLAY = 30  # 키워드당 조회 건수 (제목 필터링 후에도 top5를 채우기 위해 넉넉히 확보)
DESC_TRUNCATE_RATIO = 0.5  # 기사 요약 길이 축소 비율
DESC_MIN_LEN = 35  # 축소 시 최소 보장 길이

# 모던 SaaS 톤앤매너 (인디고 · 화이트 카드 · 라이트 라벤더 배경)
INDIGO = "#4f46e5"
POS_COLOR = "#0e9f6e"
NEG_COLOR = "#e02424"
NEU_COLOR = "#6b7280"
SENTIMENT_COLORS = {"긍정": POS_COLOR, "부정": NEG_COLOR, "중립": NEU_COLOR}
SENTIMENT_BG = {"긍정": "#e7f7f0", "부정": "#fdeced", "중립": "#f1f2f6"}

# ----------------------------------------------------------------------------
# 섹션(토픽) 정의 — 각 섹션은 같은 포맷으로 렌더링됨
# ----------------------------------------------------------------------------

SEMI_KEYWORDS = ["반도체", "삼성전자 반도체", "SK하이닉스", "HBM", "파운드리", "메모리 반도체"]
# 제목 필터용 토큰 — 검색어와 달리 실제 기사 제목에 그대로 등장하는 짧은 단어를 쓴다.
SEMI_TITLE_TOKENS = ["반도체", "하이닉스", "HBM", "파운드리", "메모리", "삼성전자"]
SEMI_POS = [
    "급등", "사상 최대", "역대 최대", "호황", "수주", "공급계약", "목표주가 상향",
    "상향", "증설", "투자 확대", "신기록", "흑자전환", "실적 서프라이즈", "훈풍", "강세",
]
SEMI_NEG = [
    "급락", "부진", "적자", "감산", "구조조정", "목표주가 하향", "하향", "규제",
    "재고 증가", "가격 하락", "위축", "우려", "쇼크", "약세", "감원",
]

RATE_KEYWORDS = ["기준금리", "한국은행 금리", "미국 기준금리", "연준 금리", "금리 인하", "국고채 금리"]
RATE_TITLE_TOKENS = ["금리", "연준", "한국은행", "한은", "국고채", "물가", "CPI", "인플레"]
RATE_POS = [
    "금리 인하", "인하 기대", "비둘기파", "완화적", "인하 단행", "피벗",
    "긴축 완화", "금리 동결", "물가 안정",
]
RATE_NEG = [
    "금리 인상", "매파", "긴축", "물가 상승", "인플레이션 우려", "국채금리 급등",
    "긴축 기조", "고금리 장기화", "금리 쇼크",
]

IRAN_KEYWORDS = [
    "이란", "호르무즈 해협", "미국 이란 협상", "이란 해상봉쇄",
    "하메네이", "후티 반군", "이란 유가",
]
IRAN_TITLE_TOKENS = [
    "이란", "호르무즈", "하메네이", "후티", "중동", "홍해", "테헤란", "페제시키안",
]
# 국가명 '이란'이 스포츠 기사에서 자주 등장해 이를 걸러낸다.
IRAN_EXCLUDE = [
    "아시안컵", "대표팀", "축구", "농구", "월드컵", "올림픽", "K리그", "감독 선임", "예선",
]
IRAN_POS = [
    "휴전", "협상 타결", "합의 근접", "갈등 완화", "긴장 완화", "종전", "평화협정",
    "확전 자제", "휴전 합의", "협상 진전", "재개방", "봉쇄 해제",
]
IRAN_NEG = [
    "공습", "확전", "미사일 공격", "사상자", "전면전", "보복", "긴장 고조",
    "무력 충돌", "폭격", "군사 개입", "긴급 사태", "피격", "봉쇄", "협상 교착", "유가 급등",
]

TOPICS = [
    {
        "id": "semiconductor",
        "badge": "산업",
        "title": "반도체",
        "subtitle": "메모리 · 파운드리 · HBM 관련 최신 보도",
        "keywords": SEMI_KEYWORDS,
        "title_tokens": SEMI_TITLE_TOKENS,
        "exclude_words": [],
        "pos_words": SEMI_POS,
        "neg_words": SEMI_NEG,
    },
    {
        "id": "rates",
        "badge": "거시경제",
        "title": "금리",
        "subtitle": "기준금리 · 연준 · 국고채 동향",
        "keywords": RATE_KEYWORDS,
        "title_tokens": RATE_TITLE_TOKENS,
        "exclude_words": [],
        "pos_words": RATE_POS,
        "neg_words": RATE_NEG,
    },
    {
        "id": "iran_war",
        "badge": "국제정세",
        "title": "이란 전쟁",
        "subtitle": "미·이란 협상 · 호르무즈 해협 · 유가 리스크",
        "keywords": IRAN_KEYWORDS,
        "title_tokens": IRAN_TITLE_TOKENS,
        "exclude_words": IRAN_EXCLUDE,
        "pos_words": IRAN_POS,
        "neg_words": IRAN_NEG,
    },
]

st.set_page_config(page_title="뉴스 브리핑 대시보드", layout="wide")

APP_CSS = """
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css');

.stApp { background-color: #f7f8fc; }
section[data-testid="stSidebar"], div[data-testid="stSidebarCollapsedControl"] { display: none !important; }
.block-container {
    padding-top: 3.2rem !important;
    padding-bottom: 3rem;
    max-width: 1280px;
    font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}
.block-container * { font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }

/* 페이지 헤더 */
.hd-wrap { margin-bottom: 26px; }
.hd-eyebrow {
    display: inline-block; background: #eef2ff; color: #4f46e5;
    font-size: 12px; font-weight: 600; padding: 5px 12px; border-radius: 999px;
    margin-bottom: 12px;
}
.hd-title { font-size: 30px; font-weight: 700; color: #101322; margin: 0 0 6px 0; letter-spacing: -0.02em; }
.hd-sub { font-size: 14px; color: #6b7280; margin: 0; }

/* 섹션 헤더 */
.sec-head {
    display: flex; align-items: center; gap: 10px;
    margin: 0 0 14px 0; padding-bottom: 12px; border-bottom: 1px solid #e8eaf1;
}
.sec-badge {
    background: #eef2ff; color: #4f46e5; font-size: 11px; font-weight: 600;
    padding: 4px 10px; border-radius: 6px;
}
.sec-title { font-size: 20px; font-weight: 700; color: #101322; letter-spacing: -0.01em; }
.sec-sub { font-size: 13px; color: #9096a5; margin-left: 2px; }

/* 섹션 내 키워드 컨트롤 */
div[data-testid="stMultiSelect"] { margin-bottom: 10px; }
div[data-testid="stMultiSelect"] div[data-baseweb="select"] > div {
    background: #ffffff; border: 1px solid #e8eaf1; border-radius: 10px; min-height: 38px;
}
div[data-testid="stMultiSelect"] span[data-baseweb="tag"] {
    background: #eef2ff !important; color: #4f46e5 !important;
    border-radius: 6px; font-size: 11.5px; font-weight: 500;
}
div[data-testid="stMultiSelect"] span[data-baseweb="tag"] svg { fill: #4f46e5; }

/* 요약 지표 (한 줄 pill) */
.kpi-row { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
.kpi {
    display: flex; align-items: baseline; gap: 7px;
    background: #ffffff; border: 1px solid #e8eaf1; border-radius: 10px;
    padding: 8px 14px;
}
.kpi-label { font-size: 12px; color: #6b7280; font-weight: 500; }
.kpi-value { font-size: 17px; font-weight: 700; color: #101322; }
.kpi-dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; }

.tone-bar {
    background: #ffffff; border: 1px solid #e8eaf1; border-left: 3px solid #4f46e5;
    border-radius: 8px; padding: 10px 14px; font-size: 13.5px; color: #3b4051;
    margin-bottom: 14px;
}

/* 기사 카드 열 */
.col-head {
    display: flex; align-items: center; justify-content: space-between;
    padding: 7px 12px; border-radius: 8px; margin-bottom: 8px;
}
.col-head-name { font-size: 12.5px; font-weight: 700; }
.col-head-count { font-size: 11.5px; font-weight: 600; opacity: .75; }

.card-list { background: #ffffff; border: 1px solid #e8eaf1; border-radius: 12px; padding: 2px 14px; }
.news-item { padding: 11px 0; border-bottom: 1px solid #f0f1f5; }
.news-item:last-child { border-bottom: none; }
.news-title {
    font-size: 13.5px; font-weight: 600; color: #101322; text-decoration: none;
    line-height: 1.42; display: block;
}
.news-title:hover { color: #4f46e5; }
.news-meta { font-size: 11px; color: #9096a5; margin: 5px 0 4px 0; }
.news-desc {
    font-size: 12px; color: #6b7280; line-height: 1.5; margin: 0;
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.empty-note { font-size: 12.5px; color: #9096a5; padding: 14px 2px; }
.sec-gap { height: 34px; }

/* AI 브리핑 바로가기 버튼: 새로고침 버튼과 같은 모양 + 인디고 색으로 구분 */
div[data-testid="stPageLink"] {
    margin-bottom: 8px;
}
div[data-testid="stPageLink"] a {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    background: #4f46e5 !important;
    color: #ffffff !important;
    border: 1px solid #4f46e5 !important;
    border-radius: 8px !important;
    padding: 0.5rem 1rem !important;
    min-height: 2.5rem;
    text-decoration: none !important;
    transition: background 0.15s ease, box-shadow 0.15s ease;
}
div[data-testid="stPageLink"] a:hover {
    background: #4338ca !important;
    border-color: #4338ca !important;
    box-shadow: 0 4px 12px rgba(79, 70, 229, 0.3);
}
div[data-testid="stPageLink"] a * {
    color: #ffffff !important;
    font-weight: 600 !important;
    font-size: 14px !important;
}
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
def collect_all_news(
    keywords: tuple,
    title_tokens: tuple,
    exclude_words: tuple,
    pos_words: tuple,
    neg_words: tuple,
    max_age_days: int = 3,
):
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

        # 토픽 토큰이 제목에 실제로 포함된 기사만 채택 (요약문만 일치하는 기사는 제외).
        # 검색어는 다어절이라 제목에 그대로 안 나오는 경우가 많아 별도 토큰으로 판정한다.
        tokens = title_tokens or (it["_keyword"],)
        if not any(tok in title for tok in tokens):
            continue

        # 동명이의 노이즈 제외 (예: 국가명 '이란'이 등장하는 스포츠 기사)
        if any(bad in title for bad in exclude_words):
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

def render_section_head(topic: dict):
    st.markdown(
        '<div class="sec-head">'
        f'<span class="sec-badge">{html.escape(topic["badge"])}</span>'
        f'<span class="sec-title">{html.escape(topic["title"])}</span>'
        f'<span class="sec-sub">{html.escape(topic["subtitle"])}</span>'
        '</div>',
        unsafe_allow_html=True,
    )


def render_kpis(counts: dict, total: int):
    pills = [
        ("전체 기사", total, "#4f46e5"),
        ("긍정", counts["긍정"], POS_COLOR),
        ("부정", counts["부정"], NEG_COLOR),
        ("중립", counts["중립"], NEU_COLOR),
    ]
    items = "".join(
        '<div class="kpi">'
        f'<span class="kpi-dot" style="background:{color}"></span>'
        f'<span class="kpi-label">{html.escape(label)}</span>'
        f'<span class="kpi-value">{value}</span>'
        '</div>'
        for label, value, color in pills
    )
    st.markdown(f'<div class="kpi-row">{items}</div>', unsafe_allow_html=True)


def render_ratio_bar(counts: dict, chart_key: str):
    labels = ["긍정", "부정", "중립"]
    total = max(sum(counts[l] for l in labels), 1)
    fig = go.Figure()
    for l in labels:
        pct = counts[l] / total * 100
        fig.add_trace(
            go.Bar(
                y=["s"],
                x=[counts[l]],
                orientation="h",
                name=l,
                marker=dict(color=SENTIMENT_COLORS[l], line=dict(width=0)),
                text=f"{l} {pct:.0f}%" if pct >= 8 else "",
                textposition="inside",
                insidetextanchor="middle",
                textfont=dict(color="#ffffff", size=11.5),
                hovertemplate=f"{l}: %{{x}}건<extra></extra>",
            )
        )
    fig.update_layout(
        barmode="stack",
        height=44,
        margin=dict(l=0, r=0, t=0, b=0),
        showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        bargap=0,
    )
    st.plotly_chart(fig, use_container_width=True, key=chart_key, config={"displayModeBar": False})


def render_news_column(container, sentiment: str, items: list):
    color = SENTIMENT_COLORS[sentiment]
    bg = SENTIMENT_BG[sentiment]
    container.markdown(
        f'<div class="col-head" style="background:{bg}">'
        f'<span class="col-head-name" style="color:{color}">{sentiment}</span>'
        f'<span class="col-head-count" style="color:{color}">{len(items)}건</span>'
        '</div>',
        unsafe_allow_html=True,
    )
    if not items:
        container.markdown('<div class="empty-note">해당 기사가 없습니다.</div>', unsafe_allow_html=True)
        return

    rows = []
    for a in items:
        time_str = a["pub_date"].strftime("%m/%d %H:%M") if a["pub_date"] else a["pub_date_raw"]
        meta = f"{time_str} · {', '.join(sorted(a['keywords']))}"
        rows.append(
            '<div class="news-item">'
            f'<a class="news-title" href="{html.escape(a["link"] or "", quote=True)}" target="_blank" rel="noopener">{html.escape(a["title"])}</a>'
            f'<div class="news-meta">{html.escape(meta)}</div>'
            f'<p class="news-desc">{html.escape(shorten(a["description"]))}</p>'
            '</div>'
        )
    container.markdown(f'<div class="card-list">{"".join(rows)}</div>', unsafe_allow_html=True)


def render_topic(topic: dict, chart_key: str):
    render_section_head(topic)

    # 키워드 선택은 각 섹션 소제목 바로 아래에 배치한다.
    active_keywords = st.multiselect(
        "검색 키워드",
        options=topic["keywords"],
        default=topic["keywords"],
        key=f"kw-{topic['id']}",
        label_visibility="collapsed",
    )

    if not active_keywords:
        st.info("키워드를 하나 이상 선택해주세요.")
        return

    with st.spinner(f"{topic['title']} 뉴스 불러오는 중..."):
        articles = collect_all_news(
            tuple(active_keywords),
            tuple(topic.get("title_tokens", [])),
            tuple(topic.get("exclude_words", [])),
            tuple(topic["pos_words"]),
            tuple(topic["neg_words"]),
        )

    if not articles:
        st.warning("최근 3일 이내 수집된 기사가 없습니다.")
        return

    counts = {"긍정": 0, "부정": 0, "중립": 0}
    for a in articles:
        counts[a["sentiment"]] += 1

    render_kpis(counts, len(articles))

    if counts["긍정"] > counts["부정"]:
        tone = "긍정 보도가 우세합니다. 업황·정책에 우호적인 기사 비중이 높습니다."
    elif counts["부정"] > counts["긍정"]:
        tone = "부정 보도가 우세합니다. 리스크 요인을 다룬 기사 비중이 높습니다."
    else:
        tone = "긍정과 부정이 비슷합니다. 방향성이 뚜렷하지 않은 국면입니다."
    st.markdown(f'<div class="tone-bar">{html.escape(tone)}</div>', unsafe_allow_html=True)

    render_ratio_bar(counts, chart_key)

    def top_articles(sentiment):
        return [a for a in articles if a["sentiment"] == sentiment][:TOP_N]

    col_pos, col_neg, col_neu = st.columns(3, gap="small")
    render_news_column(col_pos, "긍정", top_articles("긍정"))
    render_news_column(col_neg, "부정", top_articles("부정"))
    render_news_column(col_neu, "중립", top_articles("중립"))


def main():
    st.markdown(APP_CSS, unsafe_allow_html=True)

    now = datetime.now().strftime("%Y년 %m월 %d일 %H:%M")
    head_left, head_right = st.columns([5, 1], vertical_alignment="bottom")
    with head_left:
        st.markdown(
            '<div class="hd-wrap">'
            '<span class="hd-eyebrow">실시간 뉴스 모니터링</span>'
            '<h1 class="hd-title">주요 이슈 뉴스 브리핑</h1>'
            f'<p class="hd-sub">반도체 · 금리 · 이란 전쟁 · 최근 3일 기사 · {now} 기준 · 네이버 뉴스 검색 API</p>'
            '</div>',
            unsafe_allow_html=True,
        )
    with head_right:
        st.page_link("pages/01_AInews.py", label="🤖 AI 브리핑", use_container_width=True)
        st.page_link("pages/02_ThemeSector.py", label="🧭 테마 트렌드", use_container_width=True)
        if st.button("새로고침", use_container_width=True):
            fetch_news_for_keyword.clear()
            collect_all_news.clear()
            st.rerun()

    for i, topic in enumerate(TOPICS):
        render_topic(topic, chart_key=f"chart-{topic['id']}")
        if i < len(TOPICS) - 1:
            st.markdown('<div class="sec-gap"></div>', unsafe_allow_html=True)

    st.caption(
        "논조 분류는 키워드 규칙 기반입니다. "
        "정교한 분류가 필요하면 classify() 함수를 LLM 호출로 교체하세요."
    )


if __name__ == "__main__":
    main()
