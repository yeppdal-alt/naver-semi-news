"""
AI 뉴스 브리핑 대시보드 (Streamlit 멀티페이지)
클로드 / 챗GPT·제미나이 / 기타(딥시크·업스테이지·퍼플렉시티 등) 3개 그룹으로 나눠
비전공자 학습에 도움이 되는 기사 Top 5와 관련 학습 동영상을 함께 보여준다.

- 뉴스 소스: 네이버 뉴스 검색 API (main.py와 동일한 NAVER API HUB 엔드포인트)
- 동영상 소스: 유튜브 검색결과 페이지 (별도 API 키 불필요)
- 인증: Streamlit secrets의 NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 사용
"""

import re
import html
import json
from datetime import datetime, timedelta, timezone

import requests
import streamlit as st

# ----------------------------------------------------------------------------
# 설정
# ----------------------------------------------------------------------------

NAVER_NEWS_URL = "https://naverapihub.apigw.ntruss.com/search/v1/news"
YOUTUBE_SEARCH_URL = "https://www.youtube.com/results"

TOP_N = 5
FETCH_DISPLAY = 30
MAX_AGE_DAYS = 14  # 학습 콘텐츠는 속보성 뉴스보다 조회 기간을 넉넉히 잡는다
VIDEOS_PER_ARTICLE = 2
DESC_TRUNCATE_RATIO = 0.5
DESC_MIN_LEN = 35

# 비전공자 학습 적합도 판별 키워드 — 많이 맞을수록 입문자에게 도움되는 기사로 간주
AI_LEARNING_WORDS = [
    "초보자", "입문", "비전공자", "가이드", "배우기", "튜토리얼", "따라하기",
    "활용법", "사용법", "강좌", "기초", "처음", "시작하기", "쉽게", "정리", "차이점", "노하우",
]

# AI 에이전트 브랜드별 그룹 — 각 그룹 독립적으로 검색/필터링 후 그룹별 Top 5를 나란히 보여준다.
AI_GROUPS = [
    {
        "id": "claude",
        "label": "클로드",
        "color": "#d97757",
        "bg": "#fdf0ec",
        "keywords": ["클로드 AI", "클로드 코드", "앤스로픽"],
        "title_tokens": ["클로드", "Claude", "앤스로픽", "Anthropic"],
    },
    {
        "id": "gpt_gemini",
        "label": "챗GPT · 제미나이",
        "color": "#10a37f",
        "bg": "#e6f7f1",
        "keywords": ["챗GPT", "오픈AI", "제미나이 AI", "구글 제미나이"],
        "title_tokens": ["챗GPT", "GPT", "ChatGPT", "오픈AI", "OpenAI", "제미나이", "Gemini"],
    },
    {
        "id": "etc",
        "label": "기타 AI 에이전트",
        "color": "#7c3aed",
        "bg": "#f2ecfc",
        "keywords": ["딥시크", "업스테이지 AI", "솔라 LLM", "퍼플렉시티 AI", "AI 에이전트"],
        "title_tokens": [
            "딥시크", "DeepSeek", "업스테이지", "Upstage", "솔라", "Solar",
            "퍼플렉시티", "Perplexity", "에이전트",
        ],
    },
]

st.set_page_config(page_title="AI 뉴스 브리핑", page_icon="🤖", layout="wide")

APP_CSS = """
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css');

.stApp { background-color: #f7f8fc; }
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

.tone-bar {
    background: #ffffff; border: 1px solid #e8eaf1; border-left: 3px solid #4f46e5;
    border-radius: 8px; padding: 10px 14px; font-size: 13.5px; color: #3b4051;
    margin-bottom: 14px;
}

/* 그룹(브랜드)별 컬럼 헤더 */
.col-head {
    display: flex; align-items: center; justify-content: space-between;
    padding: 7px 12px; border-radius: 8px; margin-bottom: 8px;
}
.col-head-name { font-size: 12.5px; font-weight: 700; }
.col-head-count { font-size: 11.5px; font-weight: 600; opacity: .75; }

/* 뉴스 카드 리스트 */
.card-list { background: #ffffff; border: 1px solid #e8eaf1; border-radius: 12px; padding: 2px 14px; }
.news-item { padding: 13px 0; border-bottom: 1px solid #f0f1f5; }
.news-item:last-child { border-bottom: none; }
.news-title {
    font-size: 14px; font-weight: 600; color: #101322; text-decoration: none;
    line-height: 1.45; display: block;
}
.news-title:hover { color: #4f46e5; }
.news-meta { font-size: 11px; color: #9096a5; margin: 6px 0 4px 0; }
.news-desc {
    font-size: 12.5px; color: #6b7280; line-height: 1.5; margin: 0;
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.empty-note { font-size: 12.5px; color: #9096a5; padding: 14px 2px; }
.sec-gap { height: 34px; }

/* AI 학습 기사 전용 뱃지 */
.ai-news-rank {
    display: inline-block; background: #4f46e5; color: #ffffff;
    font-size: 10.5px; font-weight: 700; padding: 2px 9px; border-radius: 999px;
    margin-bottom: 7px; letter-spacing: 0.02em;
}
.ai-news-tags { margin-top: 7px; }
.ai-tag {
    display: inline-block; background: #eef2ff; color: #4f46e5;
    font-size: 10.5px; font-weight: 600; padding: 2px 8px; border-radius: 6px;
    margin: 0 5px 5px 0;
}

/* 관련 학습 동영상 */
.video-head { font-size: 13px; font-weight: 700; color: #101322; margin: 4px 0 10px 2px; }
.video-card {
    display: block; background: #ffffff; border: 1px solid #e8eaf1; border-radius: 12px;
    overflow: hidden; text-decoration: none; margin-bottom: 12px; transition: box-shadow .15s ease;
}
.video-card:hover { box-shadow: 0 4px 14px rgba(79,70,229,0.12); }
.video-thumb { width: 100%; aspect-ratio: 16/9; object-fit: cover; display: block; background: #eef0f5; }
.video-title {
    font-size: 12.5px; font-weight: 600; color: #101322; padding: 9px 12px 3px;
    line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.video-meta { font-size: 11px; color: #9096a5; padding: 0 12px 10px; }

/* 반도체 브리핑 바로가기 버튼: 새로고침 버튼과 같은 모양 + 인디고 색으로 구분 */
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
# 유틸 (main.py와 동일한 로직)
# ----------------------------------------------------------------------------

def strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text or "")
    return html.unescape(text)


def normalize_key(title: str) -> str:
    key = re.sub(r"[^0-9A-Za-z가-힣]", "", strip_html(title))
    return key[:18].lower()


def parse_pubdate(pub_date: str):
    try:
        return datetime.strptime(pub_date, "%a, %d %b %Y %H:%M:%S %z")
    except (ValueError, TypeError):
        return None


def shorten(text: str, ratio: float = DESC_TRUNCATE_RATIO, min_len: int = DESC_MIN_LEN) -> str:
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
            "NAVER_CLIENT_ID / NAVER_CLIENT_SECRET을 등록해주세요."
        )
        st.stop()
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
def collect_ai_learning_news(
    keywords: tuple,
    title_tokens: tuple,
    learning_words: tuple,
    max_age_days: int = MAX_AGE_DAYS,
):
    """AI 에이전트 키워드로 뉴스를 모으고, 비전공자 학습 적합도(learning_score) 순으로 정렬한다."""
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

        if title_tokens and not any(tok in title for tok in title_tokens):
            continue

        key = normalize_key(title)
        if key in seen:
            seen[key]["keywords"].add(it["_keyword"])
            continue

        text = title + " " + desc
        hits = [w for w in learning_words if w in text]
        seen[key] = {
            "title": title,
            "description": desc,
            "link": it.get("link") or it.get("originallink"),
            "pub_date": pub_dt,
            "pub_date_raw": it.get("pubDate", ""),
            "learning_score": len(hits),
            "learning_hits": hits,
            "keywords": {it["_keyword"]},
        }

    fallback_dt = datetime.min.replace(tzinfo=timezone.utc)
    rows = list(seen.values())
    rows.sort(
        key=lambda r: (r["learning_score"], r["pub_date"] or fallback_dt),
        reverse=True,
    )
    return rows


# ----------------------------------------------------------------------------
# 유튜브 관련 학습 동영상 (공식 API 키 불필요 - 검색결과 페이지에서 추출)
# ----------------------------------------------------------------------------

@st.cache_data(ttl=300, show_spinner=False)
def fetch_youtube_videos(query: str, max_results: int = VIDEOS_PER_ARTICLE):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9",
    }
    try:
        resp = requests.get(
            YOUTUBE_SEARCH_URL,
            params={"search_query": query},
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        marker = "var ytInitialData = "
        start = resp.text.find(marker)
        if start == -1:
            return []
        start += len(marker)
        end = resp.text.find(";</script>", start)
        data = json.loads(resp.text[start:end])
        contents = (
            data["contents"]["twoColumnSearchResultsRenderer"]["primaryContents"]
            ["sectionListRenderer"]["contents"][0]["itemSectionRenderer"]["contents"]
        )
    except (requests.RequestException, KeyError, IndexError, ValueError, json.JSONDecodeError):
        return []

    results = []
    for item in contents:
        vr = item.get("videoRenderer")
        if not vr:
            continue
        video_id = vr.get("videoId", "")
        if not video_id:
            continue
        thumbs = vr.get("thumbnail", {}).get("thumbnails", [])
        results.append({
            "title": vr.get("title", {}).get("runs", [{}])[0].get("text", ""),
            "channel": vr.get("ownerText", {}).get("runs", [{}])[0].get("text", ""),
            "duration": vr.get("lengthText", {}).get("simpleText", ""),
            "videoId": video_id,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "thumbnail": thumbs[-1]["url"] if thumbs else "",
        })
        if len(results) >= max_results:
            break
    return results


def collect_related_videos(article_titles: list):
    seen_ids = set()
    videos = []
    for title in article_titles:
        for v in fetch_youtube_videos(title[:40]):
            if v["videoId"] not in seen_ids:
                seen_ids.add(v["videoId"])
                videos.append(v)
    return videos


# ----------------------------------------------------------------------------
# UI
# ----------------------------------------------------------------------------

def render_group_column(container, group: dict, items: list):
    container.markdown(
        f'<div class="col-head" style="background:{group["bg"]}">'
        f'<span class="col-head-name" style="color:{group["color"]}">{html.escape(group["label"])}</span>'
        f'<span class="col-head-count" style="color:{group["color"]}">{len(items)}건</span>'
        '</div>',
        unsafe_allow_html=True,
    )
    if not items:
        container.markdown('<div class="empty-note">해당 기사가 없습니다.</div>', unsafe_allow_html=True)
        return

    rows = []
    for i, a in enumerate(items):
        time_str = a["pub_date"].strftime("%m/%d %H:%M") if a["pub_date"] else a["pub_date_raw"]
        tag_html = "".join(f'<span class="ai-tag">#{html.escape(h)}</span>' for h in a["learning_hits"][:3])
        rows.append(
            '<div class="news-item">'
            f'<span class="ai-news-rank" style="background:{group["color"]}">TOP {i + 1}</span>'
            f'<a class="news-title" href="{html.escape(a["link"] or "", quote=True)}" target="_blank" rel="noopener">{html.escape(a["title"])}</a>'
            f'<div class="news-meta">{html.escape(time_str)}</div>'
            f'<p class="news-desc">{html.escape(shorten(a["description"]))}</p>'
            f'<div class="ai-news-tags">{tag_html}</div>'
            '</div>'
        )
    container.markdown(f'<div class="card-list">{"".join(rows)}</div>', unsafe_allow_html=True)


def render_videos(videos: list):
    if not videos:
        st.markdown('<div class="empty-note">관련 동영상을 찾지 못했습니다.</div>', unsafe_allow_html=True)
        return
    cols = st.columns(3, gap="small")
    for idx, v in enumerate(videos):
        col = cols[idx % 3]
        col.markdown(
            f'<a class="video-card" href="{html.escape(v["url"], quote=True)}" target="_blank" rel="noopener">'
            f'<img class="video-thumb" src="{html.escape(v["thumbnail"], quote=True)}" />'
            f'<div class="video-title">{html.escape(v["title"])}</div>'
            f'<div class="video-meta">📺 {html.escape(v["channel"])} · ⏱️ {html.escape(v["duration"])}</div>'
            '</a>',
            unsafe_allow_html=True,
        )


def main():
    st.markdown(APP_CSS, unsafe_allow_html=True)

    now = datetime.now().strftime("%Y년 %m월 %d일 %H:%M")
    head_left, head_right = st.columns([5, 1], vertical_alignment="bottom")
    with head_left:
        st.markdown(
            '<div class="hd-wrap">'
            '<span class="hd-eyebrow">AI 트렌드 학습 브리핑</span>'
            '<h1 class="hd-title">AI 에이전트 뉴스 브리핑</h1>'
            f'<p class="hd-sub">클로드 · 챗GPT·제미나이 · 기타 AI 에이전트 그룹별 · 비전공자 학습 추천 기사 · {now} 기준 · 네이버 뉴스 검색 API</p>'
            '</div>',
            unsafe_allow_html=True,
        )
    with head_right:
        st.page_link("main.py", label="🖥️ 반도체 브리핑", use_container_width=True)
        if st.button("새로고침", use_container_width=True):
            fetch_news_for_keyword.clear()
            collect_ai_learning_news.clear()
            fetch_youtube_videos.clear()
            st.rerun()

    st.markdown(
        '<div class="sec-head">'
        '<span class="sec-badge">AI 트렌드</span>'
        '<span class="sec-title">AI 에이전트</span>'
        '<span class="sec-sub">클로드 · 챗GPT · 제미나이 · 기타(딥시크·업스테이지·퍼플렉시티 등) 그룹별 최신 보도</span>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="tone-bar">그룹별로 클로드 · 챗GPT · 제미나이 · 기타 AI 에이전트 기사를 모아, '
        '비전공자가 개념을 익히기 좋은 순으로 정렬한 Top 5입니다.</div>',
        unsafe_allow_html=True,
    )

    group_top5 = {}
    with st.spinner("AI 에이전트 뉴스 불러오는 중..."):
        for group in AI_GROUPS:
            articles = collect_ai_learning_news(
                tuple(group["keywords"]), tuple(group["title_tokens"]), tuple(AI_LEARNING_WORDS),
            )
            group_top5[group["id"]] = articles[:TOP_N]

    if not any(group_top5.values()):
        st.warning(f"최근 {MAX_AGE_DAYS}일 이내 수집된 AI 에이전트 관련 기사가 없습니다.")
        return

    cols = st.columns(len(AI_GROUPS), gap="small")
    for col, group in zip(cols, AI_GROUPS):
        render_group_column(col, group, group_top5[group["id"]])

    st.markdown('<div class="sec-gap"></div>', unsafe_allow_html=True)
    st.markdown('<div class="video-head">🎥 관련 학습 동영상 컨텐츠</div>', unsafe_allow_html=True)

    video_source_titles = [a["title"] for group in AI_GROUPS for a in group_top5[group["id"]][:2]]
    with st.spinner("관련 학습 동영상 불러오는 중..."):
        videos = collect_related_videos(video_source_titles)

    render_videos(videos)

    st.caption(
        "학습 적합도는 제목·요약에 포함된 키워드 기반 규칙으로 산정됩니다. "
        "동영상은 유튜브 검색결과에서 자동 수집되며 별도 API 키가 필요하지 않습니다."
    )


if __name__ == "__main__":
    main()
