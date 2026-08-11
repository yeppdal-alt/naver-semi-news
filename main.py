"""
반도체 섹터 뉴스 감성 분석 대시보드 (Streamlit Cloud 배포용)

- 데이터 소스: 네이버 뉴스 검색 API
  API 가이드: https://guide.ncloud-docs.com/docs/home 참고
- 인증: Streamlit secrets의 NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 사용
  (하드코딩 금지. .streamlit/secrets.toml 또는 Streamlit Cloud > Settings > Secrets 에 등록)
"""

import re
import html
from datetime import datetime, timedelta

import requests
import pandas as pd
import streamlit as st

# ----------------------------------------------------------------------------
# 설정
# ----------------------------------------------------------------------------

NAVER_NEWS_URL = "https://openapi.naver.com/v1/search/news.json"

KEYWORDS = ["반도체", "삼성전자 반도체", "SK하이닉스", "HBM", "파운드리", "메모리 반도체"]

POS_WORDS = [
    "급등", "사상 최대", "역대 최대", "호황", "수주", "공급계약", "목표주가 상향",
    "상향", "증설", "투자 확대", "신기록", "흑자전환", "실적 서프라이즈", "훈풍", "강세",
]
NEG_WORDS = [
    "급락", "부진", "적자", "감산", "구조조정", "목표주가 하향", "하향", "규제",
    "재고 증가", "가격 하락", "위축", "우려", "쇼크", "약세", "감원",
]

st.set_page_config(page_title="반도체 뉴스 감성 대시보드", layout="wide")


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


def classify(text: str):
    pos_hit = any(w in text for w in POS_WORDS)
    neg_hit = any(w in text for w in NEG_WORDS)
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
    return {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }


@st.cache_data(ttl=300, show_spinner=False)
def fetch_news_for_keyword(keyword: str, display: int = 10):
    headers = get_naver_headers()
    params = {"query": keyword, "display": display, "sort": "date"}
    resp = requests.get(NAVER_NEWS_URL, headers=headers, params=params, timeout=10)
    resp.raise_for_status()
    items = resp.json().get("items", [])
    for it in items:
        it["_keyword"] = keyword
    return items


@st.cache_data(ttl=300, show_spinner=False)
def collect_all_news(keywords: tuple, max_age_days: int = 3):
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
        key = normalize_key(title)

        if key in seen:
            seen[key]["keywords"].add(it["_keyword"])
            continue

        sentiment, reason = classify(title + " " + desc)
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

def main():
    st.title("반도체 섹터 뉴스 감성 대시보드")
    st.caption(
        "데이터 출처: 네이버 뉴스 검색 API · "
        "API 가이드: https://guide.ncloud-docs.com/docs/home"
    )

    with st.sidebar:
        st.header("필터")
        selected_keywords = st.multiselect(
            "검색 키워드", options=KEYWORDS, default=KEYWORDS
        )
        if st.button("새로고침 (최신 기사 재조회)"):
            fetch_news_for_keyword.clear()
            collect_all_news.clear()
            st.rerun()

    if not selected_keywords:
        st.info("사이드바에서 키워드를 하나 이상 선택해주세요.")
        return

    with st.spinner("네이버 뉴스 검색 중..."):
        articles = collect_all_news(tuple(selected_keywords))

    if not articles:
        st.warning("최근 3일 이내 수집된 기사가 없습니다.")
        return

    counts = {"긍정": 0, "부정": 0, "중립": 0}
    for a in articles:
        counts[a["sentiment"]] += 1

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
    st.info(tone)

    st.subheader("최근 조회 시점 기준 감성 비율")
    ratio_df = pd.DataFrame(
        {"건수": [counts["긍정"], counts["부정"], counts["중립"]]},
        index=["긍정", "부정", "중립"],
    )
    st.bar_chart(ratio_df)

    st.subheader("기사 목록")
    tab_pos, tab_neg, tab_neu = st.tabs(
        [f"긍정 ({counts['긍정']})", f"부정 ({counts['부정']})", f"중립 ({counts['중립']})"]
    )

    def render_articles(container, sentiment):
        items = [a for a in articles if a["sentiment"] == sentiment]
        if not items:
            container.write("해당하는 기사가 없습니다.")
            return
        for a in items:
            with container.container(border=True):
                st.markdown(f"**[{a['title']}]({a['link']})**")
                time_str = a["pub_date"].strftime("%m/%d %H:%M") if a["pub_date"] else a["pub_date_raw"]
                st.caption(f"{time_str} · {', '.join(sorted(a['keywords']))}")
                st.write(a["description"])
                st.caption(f"분류 근거: {a['reason']}")

    render_articles(tab_pos, "긍정")
    render_articles(tab_neg, "부정")
    render_articles(tab_neu, "중립")

    st.caption(
        "※ 감성 분류는 키워드 기반 자동 분류입니다. 정교한 분류가 필요하면 "
        "LLM API(Claude 등)를 연동해 classify() 함수를 교체하세요."
    )


if __name__ == "__main__":
    main()
