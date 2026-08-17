# pages/03_ForeignFlow.py
# ─────────────────────────────────────────────────────────────
# 외국인 수급 대시보드 (Streamlit 멀티페이지)
#
# 1) 종목 코드를 입력하면 외국인이 실제로 사고 있는지 확인해 줍니다.
#    (네이버 증권의 "외국인·기관 매매동향" 표 + yfinance 주가)
# 2) 삼성전자·SK하이닉스처럼 여러 종목의 외국인 보유율을
#    한 그래프에 겹쳐서 비교할 수 있습니다.
#
# 디자인은 main.py / 01_AInews.py / 02_ThemeSector.py와 같은
# 인디고 · 화이트카드 · 라벤더 배경 톤을 공유합니다.
# ─────────────────────────────────────────────────────────────

import datetime as dt          # 날짜 계산에 사용
import html as _html           # 종목명·코드를 HTML에 넣을 때 escape 용
import io                      # 문자열을 파일처럼 다루기 위해
import time                    # 페이지를 넘길 때 잠깐 쉬어 주기 위해

import pandas as pd            # 표(데이터프레임) 다루기
import plotly.graph_objects as go       # 그래프 그리기
from plotly.subplots import make_subplots   # 축이 두 개인 그래프용
import requests                # 웹 페이지 내용 받아오기
import streamlit as st         # 웹 화면 만들기
import yfinance as yf          # 야후 파이낸스에서 주가 받아오기


# ── 1. 페이지 기본 설정 ────────────────────────────────────────
# 브라우저 탭 제목과 화면 폭을 정합니다. 반드시 다른 st 명령보다 먼저 나와야 합니다.
st.set_page_config(
    page_title="외국인 수급",
    page_icon="🌏",
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
/* 한 줄 판정 박스 - 방향에 따라 왼쪽 선 색만 바뀜 */
.verdict-good { border-left-color: #0e9f6e; }
.verdict-bad  { border-left-color: #e02424; }
.sec-gap { height: 34px; }

/* 지표 카드 */
div[data-testid="stMetric"] {
    background: #ffffff; border: 1px solid #e8eaf1; border-radius: 12px;
    padding: 14px 16px;
}
div[data-testid="stMetricLabel"] p { font-size: 12px !important; color: #6b7280 !important; font-weight: 500 !important; }
div[data-testid="stMetricValue"] { font-size: 22px !important; color: #101322 !important; font-weight: 700 !important; }

/* 원본 데이터 expander를 카드처럼 */
div[data-testid="stExpander"] {
    background: #ffffff; border: 1px solid #e8eaf1 !important; border-radius: 12px;
}

/* 입력 위젯 */
div[data-testid="stTextInput"] input,
div[data-testid="stMultiSelect"] div[data-baseweb="select"] > div {
    background: #ffffff; border: 1px solid #e8eaf1; border-radius: 10px;
}
div[data-testid="stMultiSelect"] span[data-baseweb="tag"] {
    background: #eef2ff !important; color: #4f46e5 !important;
    border-radius: 6px; font-size: 11.5px; font-weight: 500;
}
div[data-testid="stMultiSelect"] span[data-baseweb="tag"] svg { fill: #4f46e5; }

/* 이슈/AI/섹터 바로가기 버튼: 인디고 색 박스 버튼 */
div[data-testid="stPageLink"] { margin-bottom: 8px; }
div[data-testid="stPageLink"] a {
    display: flex; align-items: center; justify-content: center; gap: 6px;
    background: #4f46e5 !important; color: #ffffff !important;
    border: 1px solid #4f46e5 !important; border-radius: 8px !important;
    padding: 0.5rem 1rem !important; min-height: 2.5rem;
    text-decoration: none !important;
    transition: background 0.15s ease, box-shadow 0.15s ease;
}
div[data-testid="stPageLink"] a:hover {
    background: #4338ca !important; border-color: #4338ca !important;
    box-shadow: 0 4px 12px rgba(79, 70, 229, 0.3);
}
div[data-testid="stPageLink"] a * {
    color: #ffffff !important; font-weight: 600 !important; font-size: 14px !important;
}
</style>
"""
st.markdown(APP_CSS, unsafe_allow_html=True)

# 다른 페이지들과 같은 팔레트 (인디고 · 그린 · 레드)
INDIGO, POS_COLOR, NEG_COLOR = "#4f46e5", "#0e9f6e", "#e02424"

# 네이버 증권은 브라우저가 아닌 접속을 막기 때문에,
# "나 브라우저야" 라고 알려 주는 표식(User-Agent)을 붙여서 요청합니다.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/123.0 Safari/537.36"
    ),
    "Referer": "https://finance.naver.com/",
}


# ── 2. 도우미 함수들 ───────────────────────────────────────────
def is_korean(ticker: str) -> bool:
    """코스피(.KS)나 코스닥(.KQ) 종목인지 확인합니다."""
    return ticker.upper().endswith((".KS", ".KQ"))


def to_krx_code(ticker: str) -> str:
    """'005930.KS' 처럼 생긴 코드에서 6자리 숫자만 떼어 냅니다."""
    return ticker.split(".")[0]


def format_price(value: float, ticker: str) -> str:
    """한국 종목이면 '원', 그 외에는 '$'를 붙여 보기 좋게 만듭니다."""
    if is_korean(ticker):
        return f"{value:,.0f}원"
    return f"${value:,.2f}"


def format_won(value: float) -> str:
    """큰 금액을 '조 / 억' 단위로 읽기 쉽게 바꿉니다. (예: +1,234억원)"""
    sign = "+" if value > 0 else ("-" if value < 0 else "")
    v = abs(value)
    if v >= 1_0000_0000_0000:          # 1조 이상
        return f"{sign}{v / 1_0000_0000_0000:,.2f}조원"
    if v >= 1_0000_0000:               # 1억 이상
        return f"{sign}{v / 1_0000_0000:,.0f}억원"
    return f"{sign}{v:,.0f}원"


def format_shares(value: float) -> str:
    """주식 수를 '만 주' 단위로 읽기 쉽게 바꿉니다."""
    sign = "+" if value > 0 else ("-" if value < 0 else "")
    v = abs(value)
    if v >= 1_0000:
        return f"{sign}{v / 1_0000:,.1f}만 주"
    return f"{sign}{v:,.0f}주"


def to_number(series: pd.Series) -> pd.Series:
    """'1,234' '50.12%' '+56' 같은 글자를 숫자로 바꿉니다. 못 바꾸면 비워 둡니다."""
    return pd.to_numeric(
        series.astype(str)
              .str.replace(",", "", regex=False)
              .str.replace("%", "", regex=False)
              .str.replace("+", "", regex=False)
              .str.strip(),
        errors="coerce",
    )


def flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    네이버 표는 열 이름이 2층('외국인' / '보유율')으로 되어 있습니다.
    이를 '외국인 보유율' 처럼 한 줄로 합쳐서 다루기 쉽게 만듭니다.
    """
    if isinstance(df.columns, pd.MultiIndex):
        cols = []
        for tup in df.columns:
            # 같은 말이 두 번 반복되면(예: '날짜'/'날짜') 한 번만 씁니다.
            parts = [str(p) for p in tup if "Unnamed" not in str(p)]
            uniq = list(dict.fromkeys(parts))
            cols.append(" ".join(uniq))
        df = df.copy()
        df.columns = cols
    else:
        df = df.copy()
        df.columns = [str(c) for c in df.columns]
    return df


def pick_column(columns, *keywords):
    """열 이름 목록에서 키워드를 모두 포함하는 첫 번째 열을 찾아 줍니다."""
    for c in columns:
        if all(k in c for k in keywords):
            return c
    return None


# ── 3. 데이터 불러오기 함수 ────────────────────────────────────
# @st.cache_data 는 "같은 입력이면 결과를 기억해 둬라"는 뜻입니다.
# 덕분에 화면을 다시 그릴 때마다 서버에 또 물어보지 않아 빠릅니다. (ttl=1시간)
@st.cache_data(ttl=3600, show_spinner=False)
def load_price(ticker: str) -> pd.DataFrame:
    """종목 코드를 받아 최근 1년치 일별 주가를 돌려줍니다."""
    end = dt.date.today()                       # 오늘
    start = end - dt.timedelta(days=365)        # 1년 전

    df = yf.download(
        ticker,
        start=start,
        end=end + dt.timedelta(days=1),  # 마지막 날도 포함되도록 하루 더
        progress=False,
        auto_adjust=True,                # 액면분할·배당을 반영한 수정주가 사용
    )

    if df is None or df.empty:
        return pd.DataFrame()            # 데이터가 없으면 빈 표를 돌려줌

    # yfinance가 가끔 열 이름을 2층 구조(MultiIndex)로 주는데, 한 층으로 펴 줍니다.
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.reset_index()                # 날짜를 일반 열로 꺼내기
    df = df.rename(columns={"Date": "날짜", "Close": "종가"})
    return df[["날짜", "종가"]].dropna()


@st.cache_data(ttl=3600, show_spinner=False)
def load_name(ticker: str) -> str:
    """종목의 한글/영문 이름을 가져옵니다. 실패하면 코드 그대로 씁니다."""
    try:
        info = yf.Ticker(ticker).info
        return info.get("longName") or info.get("shortName") or ticker
    except Exception:
        return ticker


def parse_naver_table(html: str) -> pd.DataFrame:
    """
    네이버 증권 HTML에서 '외국인·기관 매매동향' 표만 골라 정리합니다.
    한 페이지에 20거래일치가 들어 있습니다.
    """
    try:
        tables = pd.read_html(io.StringIO(html))
    except ValueError:
        return pd.DataFrame()            # 표가 하나도 없는 페이지

    for raw in tables:
        t = flatten_columns(raw)
        cols = list(t.columns)

        col_date = pick_column(cols, "날짜")
        col_rate = pick_column(cols, "보유율")
        if col_date is None or col_rate is None:
            continue                     # 우리가 찾는 표가 아님

        col_close = pick_column(cols, "종가")
        col_hold = pick_column(cols, "보유주수")
        col_net = pick_column(cols, "외국인", "순매매")
        col_inst = pick_column(cols, "기관", "순매매")

        out = pd.DataFrame()
        out["날짜"] = pd.to_datetime(t[col_date], errors="coerce")
        out["외국인 보유율"] = to_number(t[col_rate])
        if col_close:
            out["종가"] = to_number(t[col_close])
        if col_hold:
            out["외국인 보유주수"] = to_number(t[col_hold])
        if col_net:
            out["외국인 순매매량"] = to_number(t[col_net])
        if col_inst:
            out["기관 순매매량"] = to_number(t[col_inst])

        # 표 사이사이의 빈 줄(구분선)을 걷어 냅니다.
        out = out.dropna(subset=["날짜", "외국인 보유율"])
        if not out.empty:
            return out

    return pd.DataFrame()


@st.cache_data(ttl=1800, show_spinner=False)
def load_foreign_naver(code: str, pages: int = 13) -> pd.DataFrame:
    """
    네이버 증권에서 외국인 보유율·순매매량을 가져옵니다.

    한 페이지가 20거래일이라, 13페이지면 약 260거래일(1년치)입니다.
    돌려주는 표의 열: 날짜 / 종가 / 외국인 보유율 / 외국인 보유주수 /
                     외국인 순매매량 / 기관 순매매량
    """
    url = "https://finance.naver.com/item/frgn.naver"
    frames = []

    with requests.Session() as sess:
        sess.headers.update(HEADERS)
        for page in range(1, pages + 1):
            try:
                res = sess.get(url, params={"code": code, "page": page}, timeout=8)
                res.encoding = "euc-kr"          # 네이버 증권은 euc-kr 인코딩입니다
                if res.status_code != 200:
                    break
                part = parse_naver_table(res.text)
            except Exception:
                break                            # 중간에 막히면 모은 데까지만 사용

            if part.empty:
                break                            # 더 이상 데이터가 없는 페이지
            frames.append(part)
            time.sleep(0.15)                     # 서버에 부담 주지 않도록 잠깐 쉬기

    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates(subset=["날짜"])
    return df.sort_values("날짜").reset_index(drop=True)


# ── 4. 화면 맨 위: 제목과 다른 페이지 바로가기 ──────────────────
head_left, head_right = st.columns([2.6, 3.4], vertical_alignment="bottom")
with head_left:
    st.markdown(
        '<div class="hd-wrap">'
        '<span class="hd-eyebrow">외국인 매매동향 추적</span>'
        '<h1 class="hd-title">🌏 외국인 수급</h1>'
        '<p class="hd-sub">외국인이 실제로 사고 있는지 보유율과 순매매로 확인 '
        '· 네이버 증권 외국인·기관 매매동향 · Yahoo Finance</p>'
        '</div>',
        unsafe_allow_html=True,
    )
with head_right:
    nav1, nav2, nav3 = st.columns(3, gap="small")
    with nav1:
        st.page_link("main.py", label="🖥️ 이슈 브리핑", use_container_width=True)
    with nav2:
        st.page_link("pages/01_AInews.py", label="🤖 AI 브리핑", use_container_width=True)
    with nav3:
        st.page_link("pages/02_ThemeSector.py", label="🧭 섹터 트렌드", use_container_width=True)

st.markdown(
    '<div class="tone-bar">ℹ️ 아래 칸에 종목 코드를 넣으면 지표와 그래프가 바로 나타납니다. '
    '한국 주식은 <b>005930.KS</b>(삼성전자) · <b>000660.KS</b>(SK하이닉스)처럼 코스피 <b>.KS</b>, '
    '코스닥 <b>.KQ</b>를 뒤에 붙여 주세요. 미국 주식은 <b>AAPL</b> · <b>NVDA</b>처럼 티커만 넣으면 됩니다 '
    '(외국인 보유율은 국내 종목에만 제공돼요).</div>',
    unsafe_allow_html=True,
)

# ── 5. 종목 입력창 ─────────────────────────────────────────────
ticker = st.text_input(
    "종목 코드를 입력해 주세요",
    value="005930.KS",
    help="한국 종목은 코스피 `.KS`, 코스닥 `.KQ`를 뒤에 붙여 주세요.",
).strip()

# 입력이 비어 있으면 안내만 하고 여기서 멈춥니다.
if not ticker:
    st.markdown(
        '<div class="tone-bar">종목 코드를 입력하면 그래프를 그려 드릴게요.</div>',
        unsafe_allow_html=True,
    )
    st.stop()

# ── 6. 주가 데이터 불러오기 ────────────────────────────────────
with st.spinner("주가를 불러오는 중이에요…"):
    data = load_price(ticker)

# 데이터가 없으면 친절하게 알려 주고 멈춥니다.
if data.empty:
    st.markdown(
        f'<div class="tone-bar verdict-bad">❌ <b>{_html.escape(ticker)}</b> 종목의 데이터를 찾지 못했어요. '
        '코드를 다시 확인해 주세요. (예: 삼성전자는 <b>005930.KS</b>)</div>',
        unsafe_allow_html=True,
    )
    st.stop()

name = load_name(ticker)

# ── 7. 지표 카드 (현재가 · 1년 등락률 · 기간) ────────────────────
first_price = float(data["종가"].iloc[0])   # 1년 전 가격
last_price = float(data["종가"].iloc[-1])   # 가장 최근 가격
change_pct = (last_price - first_price) / first_price * 100  # 등락률(%)

st.markdown(
    '<div class="sec-head">'
    '<span class="sec-badge">종목</span>'
    f'<span class="sec-title">{_html.escape(str(name))}</span>'
    f'<span class="sec-sub">{_html.escape(ticker)}</span>'
    '</div>',
    unsafe_allow_html=True,
)

col1, col2, col3 = st.columns(3)

col1.metric(
    label="현재가 (최근 종가)",
    value=format_price(last_price, ticker),
)
col2.metric(
    label="1년 등락률",
    value=f"{change_pct:+.2f}%",
    delta=f"{change_pct:+.2f}%",   # 오르면 초록, 내리면 빨강으로 표시됩니다
)
col3.metric(
    label="조회 기간",
    value=f"{data['날짜'].iloc[0]:%Y.%m.%d} ~ {data['날짜'].iloc[-1]:%Y.%m.%d}",
)

# 참고: 상단의 주가 단독 그래프는 없앴습니다.
# 주가는 아래 '외국인 보유율'과 겹쳐 그린 그래프에서 함께 보실 수 있어요.


# ═══════════════════════════════════════════════════════════════
# 8. 외국인, 정말 사고 있을까? — 수급 확인 코너 (네이버 증권 자료)
# ═══════════════════════════════════════════════════════════════
st.markdown('<div class="sec-gap"></div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sec-head">'
    '<span class="sec-badge">수급</span>'
    '<span class="sec-title">🌏 외국인, 정말 사고 있을까?</span>'
    '<span class="sec-sub">네이버 증권 외국인·기관 매매동향</span>'
    '</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="tone-bar">증권사 리포트의 <b>말</b>과 외국인의 <b>실제 행동</b>이 같은 방향인지 '
    '확인하는 자리예요. 보유율이 오르고 순매수가 쌓이고 있다면, 말과 행동이 맞아떨어지는 셈입니다.</div>',
    unsafe_allow_html=True,
)

if not is_korean(ticker):
    # 외국인 보유율은 국내 증시에만 있는 지표라 해외 종목에는 없습니다.
    st.markdown(
        '<div class="tone-bar">외국인 보유율·순매매 자료는 국내 상장 종목에만 제공돼요. '
        '<b>005930.KS</b> 처럼 한국 종목을 입력하면 이 코너가 채워집니다.</div>',
        unsafe_allow_html=True,
    )
else:
    with st.spinner("네이버 증권에서 외국인 매매동향을 읽어오는 중이에요…"):
        fdf = load_foreign_naver(to_krx_code(ticker))

    if fdf.empty:
        st.markdown(
            '<div class="tone-bar verdict-bad">외국인 수급 데이터를 불러오지 못했어요. '
            '네이버 증권이 잠시 응답하지 않거나 종목 코드가 상장 종목이 아닐 수 있어요. '
            '잠시 뒤 다시 시도해 주세요.</div>',
            unsafe_allow_html=True,
        )
    else:
        # ── 8-1. 기간 선택 ────────────────────────────────────
        window = st.radio(
            "요약 기간",
            options=[5, 20, 60],
            format_func=lambda d: f"최근 {d}거래일",
            index=1,                # 기본값은 20거래일(약 한 달)
            horizontal=True,
        )
        recent = fdf.tail(window)

        m1, m2, m3, m4 = st.columns(4)

        # (1) 지금 보유율 + 기간 중 변화
        now_share = float(fdf["외국인 보유율"].dropna().iloc[-1])
        past = recent["외국인 보유율"].dropna()
        diff_share = now_share - float(past.iloc[0]) if len(past) else 0.0
        m1.metric(
            "외국인 보유율",
            f"{now_share:.2f}%",
            delta=f"{diff_share:+.2f}%p",
            help="전체 상장주식 중 외국인이 들고 있는 비중이에요.",
        )

        # (2) 기간 누적 순매수 (주식 수 + 금액 어림값)
        if "외국인 순매매량" in fdf.columns and recent["외국인 순매매량"].notna().any():
            cum_qty = float(recent["외국인 순매매량"].fillna(0).sum())

            # 금액은 그날 종가를 곱해 대략 계산합니다. (정확한 체결가는 아니에요)
            if "종가" in recent.columns:
                est = (recent["외국인 순매매량"].fillna(0) * recent["종가"].fillna(0)).sum()
                cum_won = float(est)
            else:
                cum_won = cum_qty * last_price

            m2.metric(
                f"{window}일 누적 순매수",
                format_shares(cum_qty),
                delta=format_won(cum_won) + " 어치",
                help="산 주식에서 판 주식을 뺀 값이에요. 양수면 순매수입니다.",
            )

            # (3) 며칠이나 순매수였는지 — 꾸준함을 보는 지표
            buy_days = int((recent["외국인 순매매량"].fillna(0) > 0).sum())
            total_days = int(recent["외국인 순매매량"].notna().sum())
            m3.metric(
                "순매수한 날",
                f"{buy_days} / {total_days}일",
                help="기간 중 외국인이 순매수로 마감한 날의 수예요.",
            )
        else:
            cum_qty, cum_won, buy_days, total_days = 0.0, 0.0, 0, 0
            m2.metric(f"{window}일 누적 순매수", "—")
            m3.metric("순매수한 날", "—")

        # (4) 현재 보유주수
        if "외국인 보유주수" in fdf.columns and fdf["외국인 보유주수"].notna().any():
            m4.metric(
                "외국인 보유주수",
                format_shares(float(fdf["외국인 보유주수"].dropna().iloc[-1])),
                help="외국인이 지금 들고 있는 주식 수예요.",
            )
        else:
            m4.metric("외국인 보유주수", "—")

        # ── 8-2. 한 줄 판정 ───────────────────────────────────
        # 보유율 방향과 누적 순매수 방향을 함께 보고 메시지를 정합니다.
        if diff_share > 0.05 and cum_qty > 0:
            verdict_class, verdict_text = "verdict-good", (
                f"📗 <b>말과 행동이 같은 방향이에요.</b> 최근 {window}거래일 동안 외국인 보유율이 "
                f"{diff_share:+.2f}%p 오르고, {format_shares(cum_qty)}"
                f"({format_won(cum_won)} 어치)를 순매수했습니다."
            )
        elif diff_share < -0.05 and cum_qty < 0:
            verdict_class, verdict_text = "verdict-bad", (
                f"📕 <b>행동은 반대예요.</b> 최근 {window}거래일 동안 외국인 보유율이 "
                f"{diff_share:+.2f}%p 줄고, {format_shares(abs(cum_qty))}를 순매도했습니다. "
                "매수 추천 리포트와는 결이 다른 흐름이네요."
            )
        else:
            verdict_class, verdict_text = "", (
                f"📘 <b>아직은 지켜보는 분위기예요.</b> 최근 {window}거래일 보유율 변화는 "
                f"{diff_share:+.2f}%p, 누적 순매수는 {format_shares(cum_qty)}로 "
                "뚜렷한 방향이 보이지 않습니다."
            )
        st.markdown(
            f'<div class="tone-bar {verdict_class}">{verdict_text}</div>',
            unsafe_allow_html=True,
        )

        # ── 8-3. 주가와 외국인 보유율 겹쳐 보기 ────────────────
        fig2 = make_subplots(specs=[[{"secondary_y": True}]])  # 왼쪽·오른쪽 축 두 개

        fig2.add_trace(
            go.Scatter(
                x=data["날짜"], y=data["종가"],
                name="주가(종가)",
                line=dict(color="#B0B0B0", width=1.6),
                hovertemplate="%{x|%Y.%m.%d}<br>주가 %{y:,.0f}원<extra></extra>",
            ),
            secondary_y=False,
        )
        fig2.add_trace(
            go.Scatter(
                x=fdf["날짜"], y=fdf["외국인 보유율"],
                name="외국인 보유율",
                line=dict(color=INDIGO, width=2.4),
                hovertemplate="%{x|%Y.%m.%d}<br>보유율 %{y:.2f}%<extra></extra>",
            ),
            secondary_y=True,
        )

        fig2.update_layout(
            title="주가와 외국인 보유율 (같이 움직이는지 보세요)",
            hovermode="x unified",
            height=420,
            margin=dict(l=40, r=40, t=60, b=40),
            legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        fig2.update_yaxes(title_text="주가(원)", secondary_y=False,
                          gridcolor="rgba(128,128,128,0.12)")
        fig2.update_yaxes(title_text="외국인 보유율(%)", secondary_y=True,
                          showgrid=False)
        fig2.update_xaxes(gridcolor="rgba(128,128,128,0.10)")

        st.plotly_chart(fig2, use_container_width=True)

        # ── 8-4. 일별 순매매량 막대그래프 ──────────────────────
        if "외국인 순매매량" in fdf.columns and fdf["외국인 순매매량"].notna().any():
            bars = fdf.dropna(subset=["외국인 순매매량"]).tail(60).copy()
            bars["만주"] = bars["외국인 순매매량"] / 1_0000   # 보기 편하게 만 주 단위로
            # 산 날은 초록, 판 날은 빨강 (다른 페이지의 상승·하락 색과 동일)
            colors = [POS_COLOR if v >= 0 else NEG_COLOR for v in bars["만주"]]

            fig3 = go.Figure(
                go.Bar(
                    x=bars["날짜"], y=bars["만주"],
                    marker_color=colors,
                    hovertemplate="%{x|%Y.%m.%d}<br>순매매 %{y:,.1f}만 주<extra></extra>",
                )
            )
            fig3.update_layout(
                title="외국인 일별 순매매량 (최근 60거래일)",
                xaxis_title="날짜",
                yaxis_title="순매매량(만 주)",
                height=360,
                margin=dict(l=40, r=30, t=60, b=40),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                showlegend=False,
            )
            fig3.update_yaxes(gridcolor="rgba(128,128,128,0.15)", zeroline=True,
                              zerolinecolor="rgba(128,128,128,0.5)")
            fig3.update_xaxes(gridcolor="rgba(128,128,128,0.08)")

            st.plotly_chart(fig3, use_container_width=True)

        # ── 8-5. 외국인 수급 원본 데이터 ───────────────────────
        with st.expander("외국인 수급 원본 데이터 보기"):
            st.dataframe(
                fdf.sort_values("날짜", ascending=False),
                use_container_width=True,
                hide_index=True,
            )


# ═══════════════════════════════════════════════════════════════
# 9. 두 종목 이상 나란히 비교하기 — 누가 더 사들이고 있나
# ═══════════════════════════════════════════════════════════════
st.markdown('<div class="sec-gap"></div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sec-head">'
    '<span class="sec-badge">비교</span>'
    '<span class="sec-title">⚖️ 종목별 외국인 보유율 비교</span>'
    '<span class="sec-sub">여러 종목 겹쳐 보기</span>'
    '</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="tone-bar">여러 종목을 한 그래프에 겹쳐 보면, 외국인이 <b>어느 쪽을 더 사들이는지</b>가 '
    '드러납니다. 같은 반도체라도 종목마다 흐름이 다를 수 있어요.</div>',
    unsafe_allow_html=True,
)

# 자주 보는 종목을 미리 담아 뒀습니다. (코드: 이름)
PRESETS = {
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "042700": "한미반도체",
    "000990": "DB하이텍",
    "403870": "HPSP",
}

# 기본으로 삼성전자와 SK하이닉스를 골라 둡니다.
picked = st.multiselect(
    "비교할 종목",
    options=list(PRESETS.keys()),
    default=["005930", "000660"],
    format_func=lambda c: f"{PRESETS[c]} ({c})",
)

# 목록에 없는 종목은 여기에 직접 적을 수 있어요.
extra_raw = st.text_input(
    "다른 종목도 넣고 싶다면 6자리 코드를 쉼표로 이어 적어 주세요",
    value="",
    placeholder="예: 058470, 240810",
)
extra = [c.strip() for c in extra_raw.split(",") if c.strip().isdigit()]

codes = list(dict.fromkeys(picked + extra))   # 중복 제거, 순서 유지

if not codes:
    st.markdown(
        '<div class="tone-bar">위에서 종목을 하나 이상 골라 주세요.</div>',
        unsafe_allow_html=True,
    )
else:
    # ── 9-1. 보기 방식 고르기 ─────────────────────────────────
    c_left, c_right = st.columns([1, 1])

    cmp_window = c_left.radio(
        "비교 기간",
        options=[20, 60, 120, 250],
        format_func=lambda d: f"최근 {d}거래일",
        index=1,
        horizontal=True,
        key="cmp_window",
    )
    # 종목마다 보유율 수준이 달라서(예: 50% vs 55%) 절대값만 보면 비교가 어렵습니다.
    # '변화량'으로 보면 누가 더 담고 있는지가 선명해져요.
    cmp_mode = c_right.radio(
        "보는 방식",
        options=["시작일 대비 변화(%p)", "절대 보유율(%)"],
        index=0,
        horizontal=True,
        key="cmp_mode",
    )

    # ── 9-2. 종목별로 네이버 자료 받아오기 ────────────────────
    # 01_AInews.py의 그룹 색과 같은 계열 팔레트
    palette = ["#4f46e5", "#0e9f6e", "#d97757", "#7c3aed", "#0ea5e9", "#f59e0b"]
    fig4 = go.Figure()
    rows = []          # 아래 요약 표에 쓸 값들

    with st.spinner("종목별 외국인 매매동향을 모으는 중이에요…"):
        for i, code in enumerate(codes):
            cdf = load_foreign_naver(code)     # 이미 받아 둔 종목은 캐시에서 바로 나옵니다
            label = PRESETS.get(code, code)

            if cdf.empty:
                st.markdown(
                    f'<div class="tone-bar verdict-bad"><b>{_html.escape(str(label))}({_html.escape(code)})</b> '
                    '자료를 불러오지 못했어요.</div>',
                    unsafe_allow_html=True,
                )
                continue

            part = cdf.tail(cmp_window)
            share = part["외국인 보유율"]

            # 보는 방식에 따라 y값을 바꿉니다.
            if cmp_mode.startswith("시작일"):
                y = share - float(share.iloc[0])   # 시작일을 0으로 맞춰 변화만 봅니다
                suffix, ytitle = "%p", "시작일 대비 보유율 변화(%p)"
            else:
                y = share
                suffix, ytitle = "%", "외국인 보유율(%)"

            fig4.add_trace(
                go.Scatter(
                    x=part["날짜"], y=y,
                    name=f"{label} ({code})",
                    mode="lines",
                    line=dict(color=palette[i % len(palette)], width=2.4),
                    hovertemplate="%{x|%Y.%m.%d}<br>%{y:.2f}" + suffix + "<extra></extra>",
                )
            )

            # 요약 표에 넣을 값 계산
            net_col = part["외국인 순매매량"] if "외국인 순매매량" in part.columns else None
            rows.append({
                "종목": f"{label} ({code})",
                "현재 보유율": f"{float(share.iloc[-1]):.2f}%",
                f"{cmp_window}일 변화": f"{float(share.iloc[-1]) - float(share.iloc[0]):+.2f}%p",
                "누적 순매수": format_shares(float(net_col.fillna(0).sum())) if net_col is not None else "—",
                "순매수한 날": (
                    f"{int((net_col.fillna(0) > 0).sum())} / {int(net_col.notna().sum())}일"
                    if net_col is not None else "—"
                ),
            })

    if rows:
        # ── 9-3. 겹쳐 그린 비교 그래프 ────────────────────────
        fig4.update_layout(
            title=f"외국인 보유율 비교 · 최근 {cmp_window}거래일",
            xaxis_title="날짜",
            yaxis_title=ytitle,
            hovermode="x unified",
            height=460,
            margin=dict(l=40, r=30, t=60, b=40),
            legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        fig4.update_yaxes(gridcolor="rgba(128,128,128,0.15)")
        fig4.update_xaxes(gridcolor="rgba(128,128,128,0.10)")

        # '변화' 모드일 때는 0선을 그어 두면 늘었는지 줄었는지 한눈에 보입니다.
        if cmp_mode.startswith("시작일"):
            fig4.add_hline(y=0, line_dash="dot", line_color="rgba(128,128,128,0.6)")

        st.plotly_chart(fig4, use_container_width=True)

        # ── 9-4. 한눈에 보는 요약 표 ──────────────────────────
        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
        )
        st.caption(
            "‘변화’가 플러스이고 ‘누적 순매수’도 플러스인 종목이, "
            "외국인이 실제로 담고 있는 쪽이에요."
        )


# ── 10. 주가 원본 데이터 (접어 두기) ──────────────────────────
st.markdown('<div class="sec-gap"></div>', unsafe_allow_html=True)
with st.expander("주가 원본 데이터 보기"):
    st.dataframe(
        data.sort_values("날짜", ascending=False),  # 최근 날짜가 위로
        use_container_width=True,
        hide_index=True,
    )

# ── 11. 맨 아래 안내 문구 ──────────────────────────────────────
st.caption(
    "데이터 출처: 주가 — Yahoo Finance(yfinance, 수정주가) · "
    "외국인 수급 — 네이버 증권 외국인·기관 매매동향. "
    "순매수 금액은 종가를 곱해 어림한 값이라 실제 체결 금액과 다를 수 있어요. "
    "투자 판단과 그 결과는 본인의 몫입니다."
)
