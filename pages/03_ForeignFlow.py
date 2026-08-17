# main.py
# ─────────────────────────────────────────────────────────────
# 외국인 매수 의지 확인 대시보드 (Streamlit)
#
# 1) 종목 코드를 입력하면 외국인이 실제로 사고 있는지 확인해 줍니다.
#    (네이버 증권의 "외국인·기관 매매동향" 표 + yfinance 주가)
# 2) 삼성전자·SK하이닉스처럼 여러 종목의 외국인 보유율을
#    한 그래프에 겹쳐서 비교할 수 있습니다.
#
# 실행: streamlit run main.py
# ─────────────────────────────────────────────────────────────

import datetime as dt          # 날짜 계산에 사용
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

# 다른 페이지로 가는 바로가기 버튼 (다른 페이지들과 같은 인디고 박스 스타일)
st.markdown(
    """
    <style>
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
    """,
    unsafe_allow_html=True,
)

_nav1, _nav2, _nav3, _nav_rest = st.columns([1, 1, 1, 2.7], gap="small")
with _nav1:
    st.page_link("main.py", label="🖥️ 이슈 브리핑", use_container_width=True)
with _nav2:
    st.page_link("pages/01_AInews.py", label="🤖 AI 브리핑", use_container_width=True)
with _nav3:
    st.page_link("pages/02_ThemeSector.py", label="🧭 섹터 트렌드", use_container_width=True)

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


# ── 4. 화면 맨 위: 제목과 설명 ─────────────────────────────────
st.title("🌏 외국인 수급 대시보드")
st.markdown(
    """
    한국 종목이라면 **외국인이 실제로 사고 있는지**를 보유율과 순매매로 확인해 보세요.
    아래 칸에 종목 코드를 넣으면 지표와 그래프가 바로 나타납니다.

    - 한국 주식: `005930.KS` (삼성전자), `000660.KS` (SK하이닉스)
    - 미국 주식: `AAPL` (애플), `NVDA` (엔비디아)
    """
)

# ── 5. 종목 입력창 ─────────────────────────────────────────────
ticker = st.text_input(
    "종목 코드를 입력해 주세요",
    value="005930.KS",
    help="한국 종목은 코스피 `.KS`, 코스닥 `.KQ`를 뒤에 붙여 주세요.",
).strip()

# 입력이 비어 있으면 안내만 하고 여기서 멈춥니다.
if not ticker:
    st.info("종목 코드를 입력하면 그래프를 그려 드릴게요.")
    st.stop()

# ── 6. 주가 데이터 불러오기 ────────────────────────────────────
with st.spinner("주가를 불러오는 중이에요…"):
    data = load_price(ticker)

# 데이터가 없으면 친절하게 알려 주고 멈춥니다.
if data.empty:
    st.error(
        f"`{ticker}` 종목의 데이터를 찾지 못했어요. "
        "코드를 다시 확인해 주세요. (예: 삼성전자는 `005930.KS`)"
    )
    st.stop()

name = load_name(ticker)

# ── 7. 지표 카드 (현재가 · 1년 등락률 · 기간) ────────────────────
first_price = float(data["종가"].iloc[0])   # 1년 전 가격
last_price = float(data["종가"].iloc[-1])   # 가장 최근 가격
change_pct = (last_price - first_price) / first_price * 100  # 등락률(%)

st.subheader(f"{name}  ·  `{ticker}`")

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
st.divider()
st.header("🌏 외국인, 정말 사고 있을까?")
st.markdown(
    "증권사 리포트의 **말**과 외국인의 **실제 행동**이 같은 방향인지 확인하는 자리예요. "
    "보유율이 오르고 순매수가 쌓이고 있다면, 말과 행동이 맞아떨어지는 셈입니다. "
    "자료는 네이버 증권의 *외국인·기관 매매동향*에서 가져옵니다."
)

if not is_korean(ticker):
    # 외국인 보유율은 국내 증시에만 있는 지표라 해외 종목에는 없습니다.
    st.info(
        "외국인 보유율·순매매 자료는 국내 상장 종목에만 제공돼요. "
        "`005930.KS` 처럼 한국 종목을 입력하면 이 코너가 채워집니다."
    )
else:
    with st.spinner("네이버 증권에서 외국인 매매동향을 읽어오는 중이에요…"):
        fdf = load_foreign_naver(to_krx_code(ticker))

    if fdf.empty:
        st.warning(
            "외국인 수급 데이터를 불러오지 못했어요. "
            "네이버 증권이 잠시 응답하지 않거나 종목 코드가 상장 종목이 아닐 수 있어요. "
            "잠시 뒤 다시 시도해 주세요."
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
            st.success(
                f"📗 **말과 행동이 같은 방향이에요.** 최근 {window}거래일 동안 외국인 보유율이 "
                f"{diff_share:+.2f}%p 오르고, {format_shares(cum_qty)}"
                f"({format_won(cum_won)} 어치)를 순매수했습니다."
            )
        elif diff_share < -0.05 and cum_qty < 0:
            st.error(
                f"📕 **행동은 반대예요.** 최근 {window}거래일 동안 외국인 보유율이 "
                f"{diff_share:+.2f}%p 줄고, {format_shares(abs(cum_qty))}를 순매도했습니다. "
                "매수 추천 리포트와는 결이 다른 흐름이네요."
            )
        else:
            st.info(
                f"📘 **아직은 지켜보는 분위기예요.** 최근 {window}거래일 보유율 변화는 "
                f"{diff_share:+.2f}%p, 누적 순매수는 {format_shares(cum_qty)}로 "
                "뚜렷한 방향이 보이지 않습니다."
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
                line=dict(color="#2A9D8F", width=2.4),
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
            # 산 날은 붉게, 판 날은 파랗게
            colors = ["#E4572E" if v >= 0 else "#3D7EA6" for v in bars["만주"]]

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
st.divider()
st.header("⚖️ 종목별 외국인 보유율 비교")
st.markdown(
    "여러 종목을 한 그래프에 겹쳐 보면, 외국인이 **어느 쪽을 더 사들이는지**가 드러납니다. "
    "같은 반도체라도 종목마다 흐름이 다를 수 있어요."
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
    st.info("위에서 종목을 하나 이상 골라 주세요.")
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
    palette = ["#E4572E", "#2A9D8F", "#7B68A6", "#E9A13B", "#3D7EA6", "#B5495B"]
    fig4 = go.Figure()
    rows = []          # 아래 요약 표에 쓸 값들

    with st.spinner("종목별 외국인 매매동향을 모으는 중이에요…"):
        for i, code in enumerate(codes):
            cdf = load_foreign_naver(code)     # 이미 받아 둔 종목은 캐시에서 바로 나옵니다
            label = PRESETS.get(code, code)

            if cdf.empty:
                st.warning(f"`{label}({code})` 자료를 불러오지 못했어요.")
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
st.divider()
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
