# 뉴스 브리핑 대시보드 (Streamlit)

네이버 뉴스 검색 API로 반도체 섹터 뉴스를 수집해 긍정/부정/중립으로 자동 분류하는 Streamlit 앱입니다.

## 파일 구성

- `main.py` — Streamlit 앱 본체
- `requirements.txt` — 의존 패키지
- `secrets.toml.example` — secrets 설정 예시 (실제 키는 여기 넣지 말 것)

## 1. 네이버 API 키 발급

NAVER Cloud Platform 콘솔(VPC) > AI·NAVER API > Application 에서 애플리케이션을 등록하고
"NAVER 검색 > 뉴스" API를 추가한 뒤 인증 정보를 발급받으세요. 가이드:
https://guide.ncloud-docs.com/docs/home

발급 후 아래 두 값을 확보합니다.

- `NAVER_CLIENT_ID` (콘솔의 Client ID, 헤더명 `X-NCP-APIGW-API-KEY-ID`)
- `NAVER_CLIENT_SECRET` (콘솔의 Client Secret, 헤더명 `X-NCP-APIGW-API-KEY`)

> NAVER Cloud Platform 콘솔에서 발급한 키는 개발자센터(developers.naver.com)의 예전
> Open API 키와 인증 방식이 다릅니다. `main.py`는 NAVER API HUB 뉴스 검색 API 기준
> (`https://naverapihub.apigw.ntruss.com/search/v1/news`,
> `X-NCP-APIGW-API-KEY-ID`/`X-NCP-APIGW-API-KEY` 헤더)으로 작성되어 있습니다.
> API 상세 명세: https://api.ncloud-docs.com/docs/naver-api-hub-search-news

## 2. 로컬 실행

```bash
pip install -r requirements.txt
mkdir -p .streamlit
cp secrets.toml.example .streamlit/secrets.toml
# .streamlit/secrets.toml 을 열어 실제 키 값 입력
streamlit run main.py
```

## 3. Streamlit Community Cloud 배포

1. 이 폴더(`main.py`, `requirements.txt` 포함)를 GitHub 저장소에 푸시합니다.
   `secrets.toml`은 `.gitignore`에 추가해 절대 커밋하지 않습니다.
2. https://share.streamlit.io 에서 New app → 저장소/브랜치/`main.py` 선택 후 Deploy.
3. 앱 생성 후 **Settings → Secrets** 에 들어가 아래 내용을 붙여넣습니다.

   ```toml
   NAVER_CLIENT_ID = "발급받은_클라이언트_ID"
   NAVER_CLIENT_SECRET = "발급받은_클라이언트_시크릿"
   ```

4. 저장하면 앱이 자동 재시작되며, 이후 접속할 때마다 네이버 뉴스 API를 다시 호출해 최신 기사로 갱신됩니다.

## 동작 방식

- 3개 섹션(반도체 · 금리 · 이란 전쟁)을 동일한 포맷으로 표시
- 섹션마다 검색 키워드를 각각 조회 (키워드당 30건)
- 최근 3일 이내 기사만 수집, 제목 유사도로 중복 제거
- **검색어와 제목 필터를 분리**: 검색은 다어절 키워드로 넓게 하고, 채택은 `title_tokens`의
  짧은 토큰이 제목에 있는지로 판정 (다어절 검색어는 기사 제목에 그대로 등장하지 않기 때문)
- `exclude_words`로 동명이의 노이즈 제외 (예: 국가명 '이란'이 나오는 스포츠 기사)
- 키워드 기반 규칙으로 긍정/부정/중립 자동 분류 (`main.py`의 `classify()` 함수)
- 긍정/부정/중립 비율은 Plotly 가로 스택 바 한 줄로 표시
- 논조별 최신 top 5 기사를 3열로 배치해 한 화면에서 바로 비교
- 사이드바에서 키워드 필터, "최신 기사 다시 불러오기"로 캐시 초기화 후 즉시 재조회 (캐시 TTL 5분)

## 참고

- 논조 분류는 키워드 매칭 기반의 간단한 규칙입니다. 더 정교한 분류가 필요하면
  `classify()` 함수를 LLM API 호출로 교체하세요.
- 네이버 오픈 API는 일일/초당 호출 한도가 있으니 과도한 새로고침은 주의하세요.
  자세한 한도는 https://guide.ncloud-docs.com/docs/home 참고.
