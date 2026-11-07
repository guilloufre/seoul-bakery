# 3년 뒤 뜰 베이커리 상권 — 삼청동 한옥 쇼베이킹 플래그십

PE 보유 베이커리 전문점의 신규 출점 전략 제안 (AX Native Academy 조별 과제).

- **제안서**: [`index.html`](index.html) — 한 페이지 제안서 (P 키 = 발표 모드)
- **30초 소개 영상**: [`video/intro.mp4`](video/intro.mp4) · 영상 컴포지션 [`video/intro.html`](video/intro.html)
- **분석**: [`analysis/fetch_and_score.py`](analysis/fetch_and_score.py) → [`analysis/results.json`](analysis/results.json)

## 결론
149개 서울 골목·발달상권을 4축(수요 성장 35 · 고객 적합성 25 · 경쟁 여지 25 · 상권 모멘텀 15)으로 채점한 결과 **종로구 삼청동이 84.8점으로 1위**.
제과 매출 3년 CAGR 5.9%(서울 1.4%), 유동인구 +5.2%, 폐업률 0%, 상권변화지표 '상권확장'.

## 데이터
- 출처: 서울 열린데이터광장 · 서울시 상권분석서비스 (추정매출, 점포, 길단위인구, 상권변화지표, 상권 영역)
- 기간: 2023 2Q vs 2026 2Q (같은 분기, 3년) · 업종: 제과점(CS100005) · 단위: 원/분기, 명/분기, 개

## 재현
```bash
SEOUL_KEY=<서울 열린데이터 인증키> python analysis/fetch_and_score.py
```
원본 응답은 `data/`에 캐시되며(저장소에는 미포함), 같은 기간·조건이면 같은 순위가 나옵니다.
