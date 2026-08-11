# 반도체 뉴스 감성 대시보드 (Streamlit)

네이버 뉴스 검색 API로 반도체 섹터 뉴스를 수집해 긍정/부정/중립으로 자동 분류하는 Streamlit 앱입니다.

## 파일 구성

- `main.py` — Streamlit 앱 본체
- `requirements.txt` — 의존 패키지
- `secrets.toml.example` — secrets 설정 예시 (실제 키는 여기 넣지 말 것)

## 1. 네이버 API 키 발급

네이버 오픈 API(Client ID / Client Secret) 발급 및 사용법은 공식 가이드를 참고하세요.
https://guide.ncloud-docs.com/docs/home

발급 후 아래 두 값을 확보합니다.

- `NAVER_CLIENT_ID`
- `NAVER_CLIENT_SECRET`

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

- 검색 키워드: 반도체, 삼성전자 반도체, SK하이닉스, HBM, 파운드리, 메모리 반도체
- 최근 3일 이내 기사만 수집, 제목 유사도로 중복 제거
- 키워드 기반 규칙으로 긍정/부정/중립 자동 분류 (`main.py`의 `classify()` 함수)
- 사이드바에서 키워드 필터, "새로고침" 버튼으로 캐시 초기화 후 즉시 재조회 (기본 캐시 TTL 5분)

## 참고

- 감성 분류는 키워드 매칭 기반의 간단한 규칙입니다. 더 정교한 분류가 필요하면
  `classify()` 함수를 LLM API 호출로 교체하세요.
- 네이버 오픈 API는 일일/초당 호출 한도가 있으니 과도한 새로고침은 주의하세요.
  자세한 한도는 https://guide.ncloud-docs.com/docs/home 참고.
