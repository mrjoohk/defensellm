# 260325_1300 — PDF OCR 기능 추가 분석

작성일: 2026-03-25

---

## 1. 요청 내용

PDF 문서를 ingest할 때 글자 이미지(스캔 PDF)를 텍스트로 변환하는 OCR 기능 추가.
제안된 두 가지 방법 비교·검토:
- Node.js: `@opendataloader/pdf` (npm)
- Python: `opendataloader_pdf` (pip)

---

## 2. 라이브러리 검토 결과

### 2.1 @opendataloader/pdf (npm)

| 항목 | 내용 |
|------|------|
| 상태 | npm 실제 존재 (v2.0.2) |
| 언어 | TypeScript / Node.js |
| 특징 | Python 버전과 동일한 Java JAR 래핑 |
| 결론 | **채택 불가** — 이 프로젝트는 순수 Python 스택 |

### 2.2 opendataloader_pdf (Python)

| 항목 | 내용 |
|------|------|
| 상태 | PyPI 실제 존재 (v2.0.2, 최근 업데이트) |
| 언어 | Python |
| 엔진 | Java 내장 JAR (`opendataloader-pdf-cli.jar`) |
| 오프라인 | ✅ Java JAR 번들 포함, 네트워크 불필요 |
| 출력 포맷 | text / json / markdown (선택) |
| 페이지 마커 | `--text-page-separator` 옵션으로 `[PAGE N]` 삽입 가능 |
| Java 요건 | Java 11+ 필수 |
| 환경 확인 | OpenJDK 11.0.30 설치 확인 ✅ |

### 2.3 pytesseract + pdf2image (폴백)

| 항목 | 내용 |
|------|------|
| 상태 | 이미 시스템 설치됨 (pytesseract 0.3.13, pdf2image 1.17.0) |
| 역할 | 이미지 기반 PDF의 OCR 폴백 |
| 언어 팩 | eng (기본), kor 팩은 별도 설치 필요 |
| 오프라인 | ✅ Tesseract binary 설치 후 완전 오프라인 동작 |

---

## 3. 판단 근거

**Python `opendataloader_pdf` 채택 이유:**
1. **Python 프로젝트 일관성** — Node.js 런타임 추가 불필요
2. **오프라인 동작** — JAR 번들, 외부 API 호출 없음 (프로젝트 핵심 요건)
3. **RAG 최적화** — `[PAGE N]` 마커로 기존 `chunker.py` 페이지 파싱 직접 호환
4. **Java 이미 설치** — OpenJDK 11.0.30 확인, 추가 부담 없음
5. **고품질 추출** — 텍스트 레이어 PDF에서 구조화된 출력

**pytesseract 폴백 유지 이유:**
1. 이미 시스템에 설치됨
2. opendataloader_pdf 실패 또는 텍스트 희소 감지 시 자동 전환
3. `--ocr-lang kor+eng` 등 언어 지정 가능

---

## 4. 구현 내용

### 신규 파일

| 파일 | 내용 |
|------|------|
| `src/defense_llm/rag/pdf_parser.py` | UF-025 구현. `extract_text_from_pdf()`, `is_image_based_pdf()` |
| `tests/unit/test_pdf_parser.py` | 18개 단위 테스트 (18/18 통과) |
| `260325_1300_pdf_ocr_analysis.md` | 이 분석 파일 |

### 수정 파일

| 파일 | 변경 내용 |
|------|-----------|
| `src/defense_llm/cli.py` | `index` 명령에 .pdf 자동 감지, `--ocr`, `--ocr-lang` 추가 |
| `requirements.txt` | opendataloader-pdf, pytesseract, pdf2image, Pillow 추가 |
| `project_summary.md` | Phase 8 추가, 모듈 구성 업데이트, PDF OCR 상세 섹션 |
| `docs/CLI_MANUAL_KO.md` | 4.2절 전면 개정, 2.2절 선행 요건, FAQ 추가 (v0.1.1) |
| `0.FilesUpdate.xlsx` | 신규 생성 + 위 파일들 기록 |

### 자동 감지 로직

```
추출된 텍스트 평균 chars/page < 50
  → 이미지 기반 PDF로 판단 → OCR 자동 적용
```

---

## 5. 미결 사항

| 항목 | 내용 |
|------|------|
| 한국어 OCR | Tesseract `kor` 팩 시스템 설치 필요 (`apt install tesseract-ocr-kor`) |
| Windows Poppler | pdf2image 사용 시 Poppler 별도 설치 필요 |
| OCR 정확도 | Tesseract는 고해상도(300dpi+) 이미지에서 정확도 최적화 |
| 암호화 PDF | opendataloader_pdf는 `password` 파라미터 지원, CLI 옵션 미노출 |
