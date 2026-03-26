아래는 실무에서 바로 가져다 쓸 수 있는 형태의 **“LLM + RAG 성능 개선 설계안”**입니다. 핵심은 프롬프트 문구를 늘리는 것이 아니라, **검색된 근거의 적합도·압축도·최신성**을 높여서 LLM이 더 짧은 컨텍스트로 더 정확히 답하게 만드는 것입니다. Microsoft는 운영형 RAG에서 문서 정제, 청킹, 하이브리드 검색, 재정렬, 평가셋을 함께 설계해야 한다고 설명하고 있고, OpenAI도 성능 개선은 프롬프트 감각이 아니라 **eval 기반 반복 최적화**로 접근하라고 권장합니다. ([Microsoft Learn](https://learn.microsoft.com/en-us/azure/developer/ai/advanced-retrieval-augmented-generation?utm_source=chatgpt.com "Build Advanced Retrieval-Augmented Generation Systems"))

## 1. 현재 구조 진단

먼저 현재 파이프라인을 아래 8단계로 쪼개서 진단합니다.
`문서 수집 → 전처리 → 청킹 → 임베딩/인덱싱 → 질의 재작성 → 1차 검색 → 재정렬 → 컨텍스트 구성/응답 생성`
이렇게 나누면 “LLM이 못하는 문제”인지, “검색이 틀린 문제”인지, “근거는 맞는데 프롬프트 조립이 나쁜 문제”인지 분리할 수 있습니다. RAG는 단일 모델 문제가 아니라 검색과 생성이 결합된 체인이라, 각 단계별 측정이 필요합니다. ([Microsoft Learn](https://learn.microsoft.com/en-us/azure/developer/ai/advanced-retrieval-augmented-generation?utm_source=chatgpt.com "Build Advanced Retrieval-Augmented Generation Systems"))

진단 시 가장 먼저 볼 항목은 네 가지입니다.
첫째,  **검색 실패형** : 질문과 맞는 문서가 top-k 안에 안 들어오는 경우.
둘째,  **정렬 실패형** : 맞는 문서는 들어왔지만 순위가 뒤로 밀리는 경우.
셋째,  **조립 실패형** : 좋은 청크를 가져왔는데 불필요한 청크가 섞여 LLM이 흔들리는 경우.
넷째,  **생성 실패형** : 근거는 충분한데도 답변이 틀리거나 장황한 경우.
Azure 문서는 특히 하이브리드 검색과 semantic reranker가 relevance 향상에 핵심이라고 설명합니다. ([Microsoft Learn](https://learn.microsoft.com/en-us/azure/search/search-relevance-overview?utm_source=chatgpt.com "Azure AI Search - Relevance and Ranking Overview"))

실무 진단 질문은 아래처럼 잡으면 됩니다.
“질문이 오면 맞는 문서가 검색되나?”
“검색되면 상위 3~5위에 오나?”
“상위 청크가 서로 중복되거나 산만하지 않나?”
“답변에 실제 근거 인용이 가능한가?”
“최신 문서가 오래된 문서보다 우선되나?”
이 질문에 예/아니오로 답하게 하면 병목이 빨리 드러납니다. 문서 최신성 관리와 버전 추적도 운영형 RAG에서 중요 항목으로 권장됩니다. ([Microsoft Learn](https://learn.microsoft.com/en-us/azure/developer/ai/advanced-retrieval-augmented-generation?utm_source=chatgpt.com "Build Advanced Retrieval-Augmented Generation Systems"))

## 2. 병목 분류

### A. 데이터 병목

문서 원문 품질이 낮거나 표/목차/버전 정보가 깨져 있으면 검색 성능이 바로 떨어집니다. PDF OCR 품질 문제, 중복 문서, 오래된 문서 잔존, 제목/섹션 메타데이터 누락이 대표적입니다. Microsoft는 메타데이터를 별도로 저장하고 텍스트와 함께 활용해 검색 품질을 높이도록 권장합니다. ([Microsoft Learn](https://learn.microsoft.com/en-us/azure/developer/ai/advanced-retrieval-augmented-generation?utm_source=chatgpt.com "Build Advanced Retrieval-Augmented Generation Systems"))

### B. 청킹 병목

청크가 너무 크면 검색은 맞아도 답변이 산만해지고, 너무 작으면 문맥이 끊겨 재정렬과 생성 품질이 떨어집니다. 실무에서 흔한 실패는 “문단과 표가 분리되어 의미가 깨지는 것”, “한 청크에 여러 주제가 섞이는 것”, “FAQ 문서가 질문-답변 단위로 안 잘리는 것”입니다. Microsoft는 작은 단위로 검색한 뒤 주변 문맥을 확장하는 Small2Big 접근을 소개합니다. ([Microsoft Learn](https://learn.microsoft.com/en-us/azure/developer/ai/advanced-retrieval-augmented-generation?utm_source=chatgpt.com "Build Advanced Retrieval-Augmented Generation Systems"))

### C. 검색 병목

벡터 검색만 쓰면 정확 용어 매칭이 약하고, 키워드 검색만 쓰면 의미 유사성이 약합니다. 그래서 운영형 RAG에서는 **hybrid search**가 기본값에 가깝습니다. Azure AI Search는 full-text와 vector query를 병렬로 실행하고 RRF로 합치는 방식을 설명합니다. ([Microsoft Learn](https://learn.microsoft.com/en-us/azure/search/hybrid-search-overview?utm_source=chatgpt.com "Hybrid search using vectors and full text in Azure AI Search"))

### D. 질의 해석 병목

사용자 질문이 길거나 모호하거나 사내 약어가 많으면, retriever는 잘못된 방향으로 찾기 쉽습니다. 이때 query rewriting, subquery decomposition, step-back style 재작성 같은 단계가 유효합니다. Azure의 최신 RAG/agentic retrieval 문서는 복합 질문을 하위 질의로 분해해 병렬 검색하는 접근을 소개합니다. ([Microsoft Learn](https://learn.microsoft.com/en-us/azure/search/retrieval-augmented-generation-overview?utm_source=chatgpt.com "Retrieval Augmented Generation (RAG) in Azure AI Search"))

### E. 재정렬 병목

top-k 안에 맞는 문서가 있어도 순서가 뒤에 있으면 실제 답변에는 못 쓰는 경우가 많습니다. 특히 LLM은 긴 컨텍스트 전체를 균등하게 보지 않기 때문에, 상위 청크 품질이 매우 중요합니다. Azure는 hybrid search 뒤 semantic reranking을 relevance 개선의 핵심 전략으로 제시합니다. ([Microsoft Learn](https://learn.microsoft.com/en-us/azure/search/search-relevance-overview?utm_source=chatgpt.com "Azure AI Search - Relevance and Ranking Overview"))

### F. 컨텍스트 조립 병목

좋은 청크 10개를 무작정 다 넣는 것이 아니라, **중복 제거·충돌 해결·최신 버전 우선·질문별 필요한 부분만 압축**해야 합니다. 불필요한 컨텍스트는 정확도를 떨어뜨리고 latency와 cost도 올립니다. OpenAI는 먼저 평가를 세우고, 그에 맞춰 컨텍스트와 프롬프트를 조정하라고 권장합니다. ([OpenAI 개발자](https://developers.openai.com/api/docs/guides/model-optimization/?utm_source=chatgpt.com "Model optimization | OpenAI API"))

### G. 생성 병목

근거는 맞는데도 답변이 장황하거나 환각이 나는 경우입니다. 이건 프롬프트 규칙, 출력 포맷, 근거 강제, 답변 길이 제한, “근거 부족 시 모른다고 말하기” 정책으로 완화합니다. 다만 이 병목은 검색과 조립이 정리된 뒤 만져야 효과가 큽니다. ([OpenAI 개발자](https://developers.openai.com/api/docs/guides/model-optimization/?utm_source=chatgpt.com "Model optimization | OpenAI API"))

## 3. 개선 아키텍처

권장 구조는 아래와 같습니다.

`[수집/정제] → [구조 보존 파서] → [문서 타입별 청킹] → [메타데이터 강화] → [임베딩 + BM25 동시 인덱스] → [질의 분석/재작성] → [하이브리드 검색] → [semantic reranker] → [중복 제거/압축] → [답변 생성 + 근거 표기] → [평가/모니터링]`

이 구조는 Azure가 제시하는 advanced RAG의 실무형 구성과 거의 맞닿아 있습니다. 하이브리드 검색과 semantic reranker, 문서 메타데이터, 계층형 인덱스, 최신성 관리가 반복적으로 강조됩니다. ([Microsoft Learn](https://learn.microsoft.com/en-us/azure/developer/ai/advanced-retrieval-augmented-generation?utm_source=chatgpt.com "Build Advanced Retrieval-Augmented Generation Systems"))

### 3-1. 수집/정제 계층

문서 수집 시 다음을 반드시 붙입니다.
문서 ID, 문서 유형, 제목, 대주제, 소주제, 작성일, 개정일, 버전, 작성 조직, 제품/프로젝트 태그, 보안 등급, 언어.
이 메타데이터는 retrieval filter와 ranking boost에 직접 사용합니다. 예를 들어 “정책 문서만”, “최근 1년”, “프로젝트 A”, “최신 버전 우선” 같은 조건이 가능해집니다. Microsoft는 metadata를 retrieval과 precision 향상에 적극 활용하도록 권장합니다. ([Microsoft Learn](https://learn.microsoft.com/en-us/azure/developer/ai/advanced-retrieval-augmented-generation?utm_source=chatgpt.com "Build Advanced Retrieval-Augmented Generation Systems"))

### 3-2. 청킹 계층

청킹은 문서 유형별로 다르게 가져가는 것이 좋습니다.
정책/매뉴얼은 섹션-문단 기반,
FAQ는 질문-답변 단위,
코드/API 문서는 함수/클래스/엔드포인트 단위,
회의록은 안건 단위,
표가 많은 문서는 표+주변 설명을 함께 묶는 방식이 좋습니다.
처음 시작점으로는 “문단 중심 + 10~20% overlap + 제목 계층 유지”가 무난합니다. 이후 eval로 조정합니다. ([Microsoft Learn](https://learn.microsoft.com/en-us/azure/developer/ai/advanced-retrieval-augmented-generation?utm_source=chatgpt.com "Build Advanced Retrieval-Augmented Generation Systems"))

### 3-3. 인덱싱 계층

권장 인덱스는 최소 2개입니다.
하나는  **dense vector index** , 다른 하나는 **lexical/BM25 index**입니다.
가능하면 여기에 **summary/title index** 또는 **document-level index**를 추가해 계층형 탐색을 합니다. 즉, 먼저 문서 수준으로 좁히고, 그다음 청크 수준으로 내려갑니다. Microsoft는 hierarchical index와 hybrid index를 모두 advanced RAG 패턴으로 설명합니다. ([Microsoft Learn](https://learn.microsoft.com/en-us/azure/developer/ai/advanced-retrieval-augmented-generation?utm_source=chatgpt.com "Build Advanced Retrieval-Augmented Generation Systems"))

### 3-4. 질의 분석/재작성 계층

질의가 들어오면 바로 검색하지 말고 먼저 분류합니다.
`질문 유형 분류 → 약어 확장 → 엔티티 추출 → 시간 조건 추출 → 질의 재작성 → 필요 시 하위 질의 분해`
예를 들어 “A 시스템에서 오류코드 105 대응 절차”는
`시스템=A`, `오류코드=105`, `의도=운영 절차`로 분해한 뒤 검색 질의를 만듭니다. 복합 질문이면 원인/대응/예외를 분리해 2~3개 서브쿼리로 검색하고 합치는 편이 낫습니다. Azure는 agentic retrieval에서 이런 query planning 접근을 소개합니다. ([Microsoft Learn](https://learn.microsoft.com/en-us/azure/search/search-relevance-overview?utm_source=chatgpt.com "Azure AI Search - Relevance and Ranking Overview"))

### 3-5. 검색/재정렬 계층

1차 검색은 hybrid로 20~50개 정도 후보를 가져오고, 2차에서 semantic reranker로 5~10개 정도로 줄이는 구성이 실무적으로 안정적입니다. Azure의 hybrid search는 full-text와 vector query를 병렬로 수행하고 RRF로 결합하며, 이후 semantic ranker를 얹어 relevance를 높일 수 있습니다. ([Microsoft Learn](https://learn.microsoft.com/en-us/azure/search/hybrid-search-overview?utm_source=chatgpt.com "Hybrid search using vectors and full text in Azure AI Search"))

### 3-6. 컨텍스트 압축 계층

재정렬된 청크를 그대로 다 넣지 말고, 질문 기준으로 필요한 문장만 남겨 압축합니다.
권장 순서는 `중복 제거 → 버전 충돌 해소 → 질문 관련 문장 추출 → 인접 문맥 최소 보존 → 최종 3~6개 근거 청크 구성`입니다.
표·그림·도식이 중요한 문서는 텍스트만 넣지 말고 멀티모달 처리를 검토하는 것이 좋습니다. OpenAI Cookbook은 이미지/표가 중요한 문서에서 페이지 이미지와 metadata를 함께 활용해 RAG 성능을 높이는 예시를 보여줍니다. ([OpenAI 개발자](https://developers.openai.com/cookbook/examples/vector_databases/pinecone/using_vision_modality_for_rag_with_pinecone/?utm_source=chatgpt.com "Optimizing Retrieval-Augmented Generation using GPT-4o ..."))

### 3-7. 생성 계층

생성 프롬프트는 길게 꾸미기보다 규칙형이 좋습니다. 예시는 아래 정도면 충분합니다.

* 제공된 근거 안에서만 답변
* 근거가 부족하면 부족하다고 명시
* 충돌 시 최신 버전과 상위 권위 문서 우선
* 답변은 핵심 먼저, 필요 시 단계별 설명
* 사용한 근거 문서명/섹션 함께 표기

OpenAI의 최적화 가이드는 이런 변경을 반드시 eval과 함께 반복하라고 권장합니다. ([OpenAI 개발자](https://developers.openai.com/api/docs/guides/model-optimization/?utm_source=chatgpt.com "Model optimization | OpenAI API"))

## 4. 평가 지표

평가는  **검색** ,  **재정렬** ,  **생성** , **운영** 네 층으로 나누는 것이 좋습니다. RAG 평가 연구도 retrieval과 generation을 분리해서 보는 것이 중요하다고 정리합니다. ([arXiv](https://arxiv.org/html/2405.07437v2?utm_source=chatgpt.com "Evaluation of Retrieval-Augmented Generation: A Survey"))

### 4-1. 검색 지표

가장 중요한 것은 `Recall@k`입니다.
정답 근거가 top-k에 들어왔는지 먼저 봐야 합니다. 그다음 `MRR`, `NDCG@k`, `Hit Rate@k`를 봅니다. 검색 stage에서 Recall이 낮으면 프롬프트를 아무리 고쳐도 답이 안 좋아집니다. ([arXiv](https://arxiv.org/html/2405.07437v2?utm_source=chatgpt.com "Evaluation of Retrieval-Augmented Generation: A Survey"))

권장 기준 예시는 다음과 같습니다.

* Recall@10: 85% 이상
* Recall@20: 92% 이상
* MRR@10: 0.70 이상
* NDCG@10: 0.80 이상
  이 수치는 도메인 난이도에 따라 다르므로 절대 기준이라기보다 운영 목표 예시로 보는 것이 좋습니다. 평가는 자체 golden set으로 잡아야 합니다. ([Microsoft Learn](https://learn.microsoft.com/en-us/azure/developer/ai/advanced-retrieval-augmented-generation?utm_source=chatgpt.com "Build Advanced Retrieval-Augmented Generation Systems"))

### 4-2. 재정렬 지표

reranker는 “맞는 문서를 얼마나 위로 올렸는가”를 봅니다.
여기서는 `Top-3 Precision`, `MRR uplift`, `NDCG uplift`가 좋습니다.
예를 들어 hybrid만 썼을 때와 hybrid+rereank를 썼을 때의 MRR 상승폭을 보면 재정렬 효과를 바로 볼 수 있습니다. Azure는 semantic reranker를 relevance 향상 수단으로 명시합니다. ([Microsoft Learn](https://learn.microsoft.com/en-us/azure/search/search-relevance-overview?utm_source=chatgpt.com "Azure AI Search - Relevance and Ranking Overview"))

### 4-3. 생성 지표

생성은 최소 네 가지를 봅니다.
`정답 정확도`, `근거 충실성/faithfulness`, `근거 인용 적합성`, `완결성`.
정확도만 보면 운 좋게 맞은 답변과 근거에 충실한 답변을 구분하기 어렵기 때문입니다. RAG 평가 서베이도 relevance, accuracy, faithfulness를 핵심 축으로 다룹니다. ([arXiv](https://arxiv.org/html/2405.07437v2?utm_source=chatgpt.com "Evaluation of Retrieval-Augmented Generation: A Survey"))

실무 기준 예시는 다음과 같습니다.

* Answer accuracy: 85% 이상
* Faithfulness: 90% 이상
* Citation correctness: 95% 이상
* Abstention quality: 근거 부족 시 오답 대신 보류 응답 비율 개선
  특히 “모를 때 모른다고 말하는 비율”은 고신뢰 시스템에서 중요합니다. ([arXiv](https://arxiv.org/html/2405.07437v2?utm_source=chatgpt.com "Evaluation of Retrieval-Augmented Generation: A Survey"))

### 4-4. 운영 지표

운영에서는 `p95 latency`, `토큰 비용`, `검색 성공률`, `인덱스 최신성`, `문서 업데이트 반영 시간`을 봐야 합니다. 최신성 관리와 선택적 재색인은 운영형 RAG에서 중요하다고 Microsoft가 설명합니다. ([Microsoft Learn](https://learn.microsoft.com/en-us/azure/developer/ai/advanced-retrieval-augmented-generation?utm_source=chatgpt.com "Build Advanced Retrieval-Augmented Generation Systems"))

권장 운영 목표 예시는 다음과 같습니다.

* p50 응답 시간: 3초 이내
* p95 응답 시간: 8초 이내
* 질문당 총 토큰 사용량: 기준선 대비 20~40% 절감
* 문서 업데이트 반영 시간: 1시간 이내 또는 업무 SLA에 맞춤
* stale document 사용률: 지속 하락 추세 유지 ([Microsoft Learn](https://learn.microsoft.com/en-us/azure/developer/ai/advanced-retrieval-augmented-generation?utm_source=chatgpt.com "Build Advanced Retrieval-Augmented Generation Systems"))

## 5. 실무 적용용 개선 로드맵

### 1단계: 빠른 개선

가장 먼저 할 일은
`문서 정제`, `메타데이터 추가`, `청킹 재설계`, `hybrid 검색 도입`입니다.
이 네 가지만 해도 체감 성능이 크게 오르는 경우가 많습니다. Azure는 hybrid 검색을 relevance 개선의 핵심 패턴으로 설명합니다. ([Microsoft Learn](https://learn.microsoft.com/en-us/azure/search/hybrid-search-overview?utm_source=chatgpt.com "Hybrid search using vectors and full text in Azure AI Search"))

### 2단계: 정확도 개선

그다음 `query rewriting`, `subquery decomposition`, `semantic reranker`, `context compression`을 붙입니다. 복합 질의나 내부 용어가 많은 환경에서 특히 효과가 큽니다. ([Microsoft Learn](https://learn.microsoft.com/en-us/azure/search/search-relevance-overview?utm_source=chatgpt.com "Azure AI Search - Relevance and Ranking Overview"))

### 3단계: 운영 고도화

마지막으로 `golden dataset`, `A/B eval`, `회귀 테스트`, `최신성 모니터링`, `질문 유형별 라우팅`을 넣습니다. OpenAI는 eval을 중심에 둔 반복 개선을 권장합니다. ([OpenAI 개발자](https://developers.openai.com/api/docs/guides/model-optimization/?utm_source=chatgpt.com "Model optimization | OpenAI API"))

## 6. 추천 기준 아키텍처 한 줄 요약

실무에서 가장 무난한 권장안은 이렇습니다.
**“문서 타입별 청킹 + 메타데이터 강화 + BM25/Vector 하이브리드 검색 + semantic reranker + 컨텍스트 압축 + 근거 강제형 응답 + golden set 회귀 평가”**입니다. 이 조합이 정확도, 비용, latency의 균형이 가장 좋습니다. ([Microsoft Learn](https://learn.microsoft.com/en-us/azure/developer/ai/advanced-retrieval-augmented-generation?utm_source=chatgpt.com "Build Advanced Retrieval-Augmented Generation Systems"))
