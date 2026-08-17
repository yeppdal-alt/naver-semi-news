import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from zoneinfo import ZoneInfo

# ----------------------------------------------------
# 기본 설정
# ----------------------------------------------------
st.set_page_config(
    page_title="섹터 트렌드 분석",
    page_icon="🧭",
    layout="wide",
)

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
.sec-gap { height: 34px; }

/* 랭킹 차트 옆 인사이트 박스 - 높이는 Python에서 차트와 동일하게 인라인으로 지정 */
.insight-box {
    background: #ffffff; border: 1px solid #e8eaf1; border-left: 3px solid #4f46e5;
    border-radius: 8px; padding: 14px 16px; box-sizing: border-box; overflow-y: auto;
}
.insight-box-title {
    font-size: 12.5px; font-weight: 700; color: #101322; margin-bottom: 8px;
}
.insight-box ul { margin: 0; padding-left: 18px; }
.insight-box li { font-size: 13px; color: #3b4051; line-height: 1.7; }

/* 종목 상세 expander를 카드처럼 */
div[data-testid="stExpander"] {
    background: #ffffff; border: 1px solid #e8eaf1 !important; border-radius: 12px;
}

/* 새로고침 버튼: 강조하지 않고 텍스트 링크처럼 보이게 */
div[data-testid="stButton"] button {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    color: #6b7280 !important;
    font-weight: 500 !important;
    font-size: 13px !important;
    padding: 0.4rem 0.6rem !important;
}
div[data-testid="stButton"] button:hover {
    color: #4f46e5 !important;
    text-decoration: underline;
}

/* AI 브리핑 / 반도체 브리핑 바로가기 버튼: 인디고 색 박스 버튼 */
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
st.markdown(APP_CSS, unsafe_allow_html=True)


def now_kst_et_str() -> str:
    """현재 시각을 한국시간(KST)과 미국 동부시간(ET) 한 줄로 반환."""
    now_utc = datetime.now(ZoneInfo("UTC"))
    kst = now_utc.astimezone(ZoneInfo("Asia/Seoul"))
    et = now_utc.astimezone(ZoneInfo("America/New_York"))
    return (
        f"KST {kst.strftime('%Y-%m-%d %H:%M')} · "
        f"ET {et.strftime('%Y-%m-%d %H:%M %Z')}"
    )


# ----------------------------------------------------
# 테마별 대표 종목 (테마당 5개, 전부 미국 상장·USD 표시)
# ----------------------------------------------------
THEMES = {
    "AI 반도체": ["NVDA", "AMD", "AVGO", "TSM", "ASML"],
    "양자컴퓨팅": ["IONQ", "RGTI", "QBTS", "QUBT", "IBM"],
    "원자력/SMR": ["CEG", "VST", "OKLO", "SMR", "CCJ"],
    "비만치료제(GLP-1)": ["LLY", "NVO", "VKTX", "AMGN", "PFE"],
    "방위산업/우주": ["LMT", "RTX", "NOC", "PLTR", "RKLB"],
    "로보틱스/자동화": ["ISRG", "ROK", "SYM", "TER", "PATH"],
    "사이버보안": ["CRWD", "PANW", "ZS", "FTNT", "S"],
    "클라우드/SaaS": ["MSFT", "CRM", "NOW", "SNOW", "DDOG"],
    "전기차/배터리": ["TSLA", "RIVN", "LI", "ALB", "XPEV"],
    "비트코인/블록체인": ["COIN", "MSTR", "MARA", "RIOT", "HOOD"],
    "중국 기술주": ["BABA", "PDD", "JD", "BIDU", "NIO"],
    "그린수소/재생에너지": ["ENPH", "FSLR", "PLUG", "BE", "NEE"],
    "AI 전력망/인프라": ["GEV", "ETN", "VRT", "NRG", "PWR"],
    "반도체 장비/EDA": ["AMAT", "LRCX", "KLAC", "SNPS", "CDNS"],
    "구리/핵심광물": ["FCX", "SCCO", "TECK", "MP", "RIO"],
    "핀테크/디지털결제": ["V", "MA", "PYPL", "SOFI", "AXP"],
    "데이터센터 리츠": ["DLR", "EQIX", "IRM", "AMT", "SBAC"],
    "금/귀금속": ["GLD", "NEM", "GOLD", "AEM", "FNV"],
}

ALL_TICKERS = sorted({t for tickers in THEMES.values() for t in tickers})

# ----------------------------------------------------
# 데이터 로딩 (캐시) - 전체 종목 일괄 다운로드
# ----------------------------------------------------
@st.cache_data(ttl=1800, show_spinner=False)
def load_all_history(tickers: list, period: str = "6mo") -> pd.DataFrame:
    data = yf.download(
        tickers=tickers, period=period, interval="1d",
        group_by="ticker", auto_adjust=True, threads=True, progress=False,
    )
    return data


def get_close_series(data: pd.DataFrame, ticker: str) -> pd.Series:
    try:
        if isinstance(data.columns, pd.MultiIndex):
            s = data[ticker]["Close"]
        else:
            s = data["Close"]
        return s.dropna()
    except Exception:
        return pd.Series(dtype=float)


def compute_returns(close: pd.Series):
    """(현재가, 1개월수익률, 3개월수익률, 6개월수익률) 튜플 반환. 거래일수 21/63/126일 기준."""
    if close.empty:
        return None, None, None, None
    last = close.iloc[-1]

    def ret(n_days):
        if len(close) > n_days:
            base = close.iloc[-(n_days + 1)]
        else:
            base = close.iloc[0]
        return (last / base - 1) if base else None

    return last, ret(21), ret(63), ret(126)


def fmt_pct(x):
    return f"{x * 100:+.2f}%" if isinstance(x, (int, float)) else "N/A"


def fmt_num(x, decimals=2):
    return f"{x:,.{decimals}f}" if isinstance(x, (int, float)) else "N/A"


def build_ranking_insights(stats: pd.DataFrame) -> list[str]:
    """전체 테마 랭킹 차트를 바탕으로 규칙 기반 인사이트 10줄 생성 (LLM 미사용)."""
    if stats.empty:
        return ["표시할 테마가 없습니다."]

    top = stats.iloc[0]
    bottom = stats.iloc[-1]
    pos_n = int((stats["1개월"] > 0).sum())
    neg_n = int((stats["1개월"] < 0).sum())
    avg_1m = stats["1개월"].mean()
    spread = top["1개월"] - bottom["1개월"]

    accel = stats.copy()
    accel["accel"] = accel["1개월"] - accel["6개월"] / 6
    accel_top = accel.sort_values("accel", ascending=False).iloc[0]

    # 한때(6개월) 강세였지만 최근(1개월) 식고 있는 테마
    cooling_pool = accel[accel["6개월"] > 0].sort_values("accel", ascending=True)
    cooling = cooling_pool.iloc[0] if not cooling_pool.empty else accel.sort_values("accel", ascending=True).iloc[0]

    long_term_top = stats.sort_values("6개월", ascending=False).iloc[0]
    mid_term_top = stats.sort_values("3개월", ascending=False).iloc[0]

    # 6개월간 부진했지만 최근 1개월 반등 중인 테마 (없으면 낙폭이 가장 덜한 테마로 대체)
    laggards = stats[stats["6개월"] < 0].sort_values("1개월", ascending=False)
    if not laggards.empty:
        cand = laggards.iloc[0]
        if cand["1개월"] > 0:
            turnaround_line = (
                f"🔄 <b>{cand['테마']}</b>는 6개월간 부진했지만 최근 1개월 {fmt_pct(cand['1개월'])}로 반등하고 있습니다."
            )
        else:
            turnaround_line = (
                f"🔄 6개월 하락 테마 중에서는 <b>{cand['테마']}</b>의 낙폭이 가장 덜합니다(1개월 {fmt_pct(cand['1개월'])})."
            )
    else:
        turnaround_line = "🔄 6개월 기준 하락 중인 테마가 없어, 전 테마가 중장기 상승 흐름입니다."

    return [
        f"🏆 <b>{top['테마']}</b>가 1개월 {fmt_pct(top['1개월'])}로 가장 강한 모멘텀을 보이고 있습니다.",
        f"🥶 <b>{bottom['테마']}</b>는 1개월 {fmt_pct(bottom['1개월'])}로 가장 부진합니다.",
        f"📊 전체 {len(stats)}개 테마 중 {pos_n}개 상승, {neg_n}개 하락 중입니다.",
        f"📐 테마 평균 1개월 수익률은 {fmt_pct(avg_1m)}입니다.",
        f"↔️ 최고-최저 테마 간 1개월 수익률 격차는 {spread*100:.1f}%p입니다.",
        f"🚀 <b>{accel_top['테마']}</b>는 6개월 평균 페이스 대비 최근 1개월 모멘텀이 가장 가파르게 붙었습니다.",
        f"🐌 <b>{cooling['테마']}</b>는 6개월 추세 대비 최근 1개월 모멘텀이 가장 식고 있습니다.",
        f"🎯 6개월 기준으로는 <b>{long_term_top['테마']}</b>가 {fmt_pct(long_term_top['6개월'])}로 가장 견조한 흐름을 이어가고 있습니다.",
        f"🧭 3개월 기준으로는 <b>{mid_term_top['테마']}</b>가 {fmt_pct(mid_term_top['3개월'])}로 가장 우수합니다.",
        turnaround_line,
    ]


# ----------------------------------------------------
# 사이드바
# ----------------------------------------------------
st.sidebar.header("⚙️ 분석 옵션")

selected_theme_names = st.sidebar.multiselect(
    "분석할 테마 (기본: 전체)",
    options=list(THEMES.keys()),
    default=list(THEMES.keys()),
)

top_n = st.sidebar.slider("카테고리별 표시 테마 수", min_value=2, max_value=6, value=4)

st.sidebar.caption("데이터 출처: Yahoo Finance (yfinance) · 종목당 1개월(21거래일)/3개월(63거래일)/6개월(126거래일) 수익률 기준")

# ----------------------------------------------------
# 메인 화면
# ----------------------------------------------------
head_left, head_right = st.columns([3.3, 2.4], vertical_alignment="bottom")
with head_left:
    st.markdown(
        '<div class="hd-wrap">'
        '<span class="hd-eyebrow">투자 테마 모멘텀 분석</span>'
        '<h1 class="hd-title">🧭 섹터 트렌드 분석</h1>'
        f'<p class="hd-sub">주요 투자 테마의 실시간 가격 모멘텀을 계산해 상승·하락·잠재 성장 테마로 자동 분류 '
        f'· {now_kst_et_str()} 기준 · Yahoo Finance</p>'
        '</div>',
        unsafe_allow_html=True,
    )
with head_right:
    btn_col1, btn_col2, refresh_col = st.columns([1, 1, 0.7], gap="small")
    with btn_col1:
        st.page_link("main.py", label="🖥️ 반도체 브리핑", use_container_width=True)
    with btn_col2:
        st.page_link("pages/01_AInews.py", label="🤖 AI 브리핑", use_container_width=True)
    with refresh_col:
        if st.button("새로고침", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

st.markdown(
    '<div class="tone-bar">ℹ️ <b>분류 방식</b>: 테마는 사전에 큐레이션된 12개 대표 섹터이며, '
    "'주목받는/하락/잠재 성장' 라벨은 고정된 것이 아니라 각 테마 구성 종목 5개의 <b>실시간 가격 수익률 평균</b>으로 "
    "매번 새로 계산됩니다. 🔥 상승 테마 = 최근 1개월 수익률 상위, 📉 하락 테마 = 최근 1개월 수익률 하위, "
    "🌱 잠재 성장 테마 = 6개월 추세는 견조하지만 아직 단기 급등(상승 테마 상위권)에는 포함되지 않은 테마입니다.</div>",
    unsafe_allow_html=True,
)

if not selected_theme_names:
    st.warning("왼쪽 사이드바에서 테마를 하나 이상 선택해 주세요.")
    st.stop()

active_themes = {name: THEMES[name] for name in selected_theme_names}
active_tickers = sorted({t for tickers in active_themes.values() for t in tickers})

with st.spinner("전체 종목 가격 데이터 불러오는 중... (테마 수에 따라 다소 시간이 걸릴 수 있습니다)"):
    raw_data = load_all_history(active_tickers, period="6mo")

# ---- 종목별 수익률 테이블 생성 ----
rows = []
last_dates = []
for theme_name, tickers in active_themes.items():
    for ticker in tickers:
        close = get_close_series(raw_data, ticker)
        if not close.empty:
            last_dates.append(close.index.max())
        last, r1m, r3m, r6m = compute_returns(close)
        rows.append({
            "테마": theme_name, "티커": ticker,
            "현재가": last, "1개월": r1m, "3개월": r3m, "6개월": r6m,
        })

df_all = pd.DataFrame(rows)

if last_dates:
    latest_date = pd.to_datetime(max(last_dates)).strftime("%Y-%m-%d")
    st.caption(f"📅 데이터 기준일(최근 거래일): **{latest_date}**")

# ---- 테마별 평균 수익률 집계 ----
theme_stats = df_all.groupby("테마")[["1개월", "3개월", "6개월"]].mean().reset_index()
theme_stats = theme_stats.sort_values("1개월", ascending=False).reset_index(drop=True)

# ---- 전체 테마 랭킹 개요 차트 ----
st.markdown(
    '<div class="sec-head">'
    '<span class="sec-badge">랭킹</span>'
    '<span class="sec-title">전체 테마 모멘텀 랭킹</span>'
    '<span class="sec-sub">1개월 평균 수익률 기준</span>'
    '</div>',
    unsafe_allow_html=True,
)
rank_col, insight_col = st.columns([2.2, 1], gap="medium")

# 막대를 얇게 해서 차트 높이를 인사이트 10줄 분량에 맞추고, 정확히 같은 픽셀 높이로 맞춘다.
# (Streamlit의 컬럼 내부 래퍼가 여러 겹이라 CSS height:100%만으로는 안정적으로 안 맞음)
panel_height = max(90 + 24 * len(theme_stats), 320)

with rank_col:
    colors = ["rgba(220,20,60,0.8)" if v < 0 else "rgba(34,139,34,0.8)" for v in theme_stats["1개월"]]
    fig_overview = go.Figure(go.Bar(
        x=theme_stats["1개월"] * 100, y=theme_stats["테마"],
        orientation="h", marker_color=colors,
        text=[f"{v*100:+.1f}%" for v in theme_stats["1개월"]], textposition="outside",
    ))
    fig_overview.update_layout(
        height=panel_height, xaxis_title="1개월 평균 수익률 (%)",
        margin=dict(l=10, r=40, t=20, b=20), yaxis=dict(autorange="reversed"),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        bargap=0.35,
    )
    st.plotly_chart(fig_overview, use_container_width=True)

with insight_col:
    insight_items = "".join(f"<li>{line}</li>" for line in build_ranking_insights(theme_stats))
    st.markdown(
        f'<div class="insight-box" style="height:{panel_height}px;">'
        '<div class="insight-box-title">📌 랭킹 인사이트</div>'
        f'<ul>{insight_items}</ul>'
        '</div>',
        unsafe_allow_html=True,
    )

st.markdown('<div class="sec-gap"></div>', unsafe_allow_html=True)

# ---- 카테고리 분류 ----
rising_themes = theme_stats.head(top_n)["테마"].tolist()

falling_themes = theme_stats.sort_values("1개월", ascending=True).head(top_n)["테마"].tolist()
falling_themes = [t for t in falling_themes if t not in rising_themes]

growth_candidates = theme_stats[
    (~theme_stats["테마"].isin(rising_themes)) &
    (~theme_stats["테마"].isin(falling_themes)) &
    (theme_stats["6개월"] > 0)
].sort_values("6개월", ascending=False)
growth_themes = growth_candidates.head(top_n)["테마"].tolist()


def render_theme_section(badge: str, title: str, subtitle: str, theme_list: list, empty_msg: str):
    st.markdown(
        '<div class="sec-head">'
        f'<span class="sec-badge">{badge}</span>'
        f'<span class="sec-title">{title}</span>'
        f'<span class="sec-sub">{subtitle}</span>'
        '</div>',
        unsafe_allow_html=True,
    )
    if not theme_list:
        st.markdown(f'<div class="tone-bar">{empty_msg}</div>', unsafe_allow_html=True)
        return
    for theme_name in theme_list:
        stat_row = theme_stats[theme_stats["테마"] == theme_name].iloc[0]
        with st.expander(
            f"{theme_name}  ·  1개월 {fmt_pct(stat_row['1개월'])}  "
            f"·  3개월 {fmt_pct(stat_row['3개월'])}  ·  6개월 {fmt_pct(stat_row['6개월'])}",
            expanded=True,
        ):
            theme_df = df_all[df_all["테마"] == theme_name].sort_values("1개월", ascending=False).reset_index(drop=True)
            theme_df.insert(0, "순위", range(1, len(theme_df) + 1))

            col_chart, col_table = st.columns([1, 1])
            with col_chart:
                bar_colors = ["rgba(220,20,60,0.75)" if v < 0 else "rgba(65,105,225,0.75)"
                              for v in theme_df["1개월"]]
                fig = go.Figure(go.Bar(
                    x=theme_df["티커"], y=theme_df["1개월"] * 100,
                    marker_color=bar_colors,
                    text=[f"{v*100:+.1f}%" if pd.notna(v) else "N/A" for v in theme_df["1개월"]],
                    textposition="outside",
                ))
                fig.update_layout(
                    title="종목별 1개월 수익률 (%)", height=320,
                    margin=dict(l=10, r=10, t=40, b=10),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig, use_container_width=True)

            with col_table:
                display_df = theme_df.copy()
                display_df["현재가"] = display_df["현재가"].apply(lambda x: fmt_num(x))
                display_df["1개월"] = display_df["1개월"].apply(fmt_pct)
                display_df["3개월"] = display_df["3개월"].apply(fmt_pct)
                display_df["6개월"] = display_df["6개월"].apply(fmt_pct)
                st.dataframe(
                    display_df[["순위", "티커", "현재가", "1개월", "3개월", "6개월"]],
                    use_container_width=True, hide_index=True, height=250,
                )


render_theme_section(
    "상승",
    "🔥 최근 주목받는 테마",
    "Top 종목 5개씩 · 1개월 수익률 상위",
    rising_themes,
    "조건을 만족하는 상승 테마가 없습니다.",
)

st.markdown('<div class="sec-gap"></div>', unsafe_allow_html=True)

render_theme_section(
    "하락",
    "📉 하락 테마",
    "Top 종목 5개씩 · 1개월 수익률 하위",
    falling_themes,
    "조건을 만족하는 하락 테마가 없습니다.",
)

st.markdown('<div class="sec-gap"></div>', unsafe_allow_html=True)

render_theme_section(
    "잠재성장",
    "🌱 잠재 성장 테마",
    "Top 종목 5개씩 · 6개월 추세 견조, 단기 급등 제외",
    growth_themes,
    "현재 조건(6개월 수익률 플러스이면서 단기 급등에 포함되지 않은 테마)을 만족하는 테마가 없습니다. "
    "사이드바에서 '카테고리별 표시 테마 수'를 조정해보세요.",
)

st.markdown('<div class="sec-gap"></div>', unsafe_allow_html=True)
st.caption(
    "※ 상단의 새로고침 시각은 페이지가 로드된 시각입니다. 가격 데이터는 30분 캐시(TTL)로 관리되어 실제 시세와 "
    "차이가 날 수 있습니다. 즉시 최신화하려면 상단 '새로고침' 버튼을 눌러주세요. 테마 분류와 종목 구성은 "
    "투자 참고용 큐레이션이며, 투자 판단의 책임은 본인에게 있습니다."
)
