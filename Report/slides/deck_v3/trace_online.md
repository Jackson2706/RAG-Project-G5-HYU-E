# Online traces of AAES (A0) on the demo questions

From the backend traces behind the Execution tab (`trace_S1.json`, `trace_S2_S6.json`, index r5, run 2026-11-16). Labels: applies / conflicts / depends / applies to all / unknown status.

## S1: one question

Question: "Which insurance rules apply to me?"

**Step 1 profile** (rules):

- campus: missing
- degree_level: missing
- year: missing
- student_type: missing
- visa: missing
- topik_level: missing
- english_track: missing
- academic_status: scope_default = admitted_not_enrolled, enrolled, leave_of_absence, completed_coursework, graduating
- korean_standard: missing

**Retrieval**: dense top 10 + BM25 top 10, RRF fused to 18 candidates (18 after enrichment):

| RRF rank | Title | Section | dense | BM25 | RRF | cross-encoder | label | tags | after penalty | reranked rank |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | International Student Insurance | Filing a claim for National Health  | 0.6524 | 9.6286 | 0.031514 | -3.31 | depends | campus=seoul/erica; scope=national | -3.31 | 1 |
| 2 | Guidelines on personal quarantine rules  | Guidelines on personal quarantine r | 0.6465 | 9.7097 | 0.031498 | -9.31 | depends | campus=seoul/erica; scope=national | -9.31 | 11 |
| 3 | International Student Insurance | Warning | 0.6631 |  | 0.016393 | -5.95 | unknown status | campus=seoul/erica; scope=national | -5.95 | 4 |
| 4 | Return to School for 2025 Fall Semeste… | Return to School for 2025 Fall Seme |  | 12.9197 | 0.016393 | -5.31 | depends | campus=erica; scope=campus; academic_status=leave_of_absence | -5.31 | 2 |
| 5 | [학적/비자] 2025-1학기 복학 신청 관련 추가 안내 사항 (보험가입 |  |  | 11.2267 | 0.016129 | -7.15 | unknown status | campus=seoul; scope=campus | -7.15 | 6 |
| 6 | Undergraduate Admission Guideline | Undergraduate Admission Guideline |  | 9.8142 | 0.015873 | -10.5 | conflicts | campus=seoul/erica; scope=national; degree_level=undergraduate; visa=D-2; academic_status=applicant | -14.5 | 18 |
| 7 | International Student Insurance | University Group Insurance Coverage | 0.646 |  | 0.015625 | -9.42 | unknown status | campus=erica; scope=campus | -9.42 | 13 |
| 8 | International Student Insurance | National Health Insurance Coverage  | 0.6421 |  | 0.015385 | -8.64 | depends | campus=seoul/erica; scope=national | -8.64 | 10 |
| 9 | [국제팀] 2023-1학기 서울캠퍼스 학위과정 재학생 표준입학허가서 신청 |  |  | 9.1277 | 0.015152 | -9.32 | unknown status | campus=seoul; scope=campus | -9.32 | 12 |
| 10 | International Student Insurance | Insurance Information | 0.6403 |  | 0.015152 | -8.3 | unknown status | campus=seoul/erica; scope=national | -8.3 | 8 |
| 11 | [국제팀] 2023-2학기 서울캠퍼스 학위과정 재학생 표준입학허가서 신청 |  |  | 9.1277 | 0.014925 | -9.65 | unknown status | campus=seoul; scope=campus | -9.65 | 14 |
| 12 | International Student Insurance | Insurance Information | 0.6403 |  | 0.014925 | -8.3 | unknown status | campus=seoul/erica; scope=national | -8.3 | 9 |
| 13 | International Student Insurance | University Group Insurance Subscrip | 0.6362 |  | 0.014706 | -5.58 | depends | campus=erica; scope=campus; academic_status=leave_of_absence | -5.58 | 3 |
| 14 | Student Dormitories | Overview |  | 9.0019 | 0.014706 | -10.83 | unknown status | campus=erica; scope=campus | -10.83 | 17 |
| 15 | Graduate Admission Guideline | Graduate Admission Guideline |  | 8.5912 | 0.014493 | -10.71 | depends | campus=seoul; scope=campus; degree_level=master/doctoral; academic_status=admitted_not_enrolled | -10.71 | 15 |
| 16 | International Student Insurance | Penalties for Overdue Payment | 0.6336 |  | 0.014493 | -7.7 | unknown status | campus=erica; scope=campus | -7.7 | 7 |
| 17 | Undergraduate Admission Guideline | Undergraduate Admission Guideline |  | 8.5422 | 0.014286 | -10.75 | depends | campus=seoul; scope=campus; degree_level=undergraduate; student_type=degree_seeking; academic_status=admitted_not_enrolled | -10.75 | 16 |
| 18 | International Student Insurance | Subscribing to National Health Insu | 0.6334 |  | 0.014286 | -6.88 | unknown status | campus=seoul/erica; scope=national | -6.88 | 5 |

**Top-3 evidence and coverage** (relevant if query-word coverage ≥ 0.30):

- International Student Insurance (https://global.hanyang.ac.kr/eng/s3/s3_2_2.php): coverage 0.25
- Return to School for 2025 Fall Semeste… (https://global.hanyang.ac.kr/bbs/board.php?bo_table=s4_1_eng&wr_id=67): coverage 0.75
- International Student Insurance (https://global.hanyang.ac.kr/eng/s3/s3_2_1.php): coverage 0.25

**Branches** (information score per detail, over the relevant chunks: d474ac2d-ed5b-539a-8948-225d351174db):

- campus: information 1.0; chunks that apply per value: seoul → 0; erica → 1
- academic_status: information 0.721928; chunks that apply per value: admitted_not_enrolled → 0; enrolled → 0; leave_of_absence → 1; completed_coursework → 0; graduating → 0

**Branch table** (detail → value → passages):

- {'campus': ['seoul', 'erica'], 'academic_status': ['admitted_not_enrolled', 'enrolled', 'leave_of_absence', 'completed_coursework', 'graduating']} → no passage
- {'campus': ['erica'], 'academic_status': ['leave_of_absence']} → ['d474ac2d-ed5b-539a-8948-225d351174db']

**Decision**: CONDITIONAL (reason: few_branches; clarify detail: None)

**Branch note added to the prompt**:

```
The answer depends on the student's campus and academic status. Answer every case below separately, starting each with 'If you'; do not pick one for the student.
- campus Seoul or ERICA; academic status admitted not enrolled, enrolled, leave of absence, completed coursework or graduating: use no evidence: say the student should ask the OIA office
- campus ERICA; academic status leave of absence: use [E1]
```

**Prompt** (347 tokens; system message trimmed):

```
You are HYU Compass, a helpful assistant for new students at Hanyang University.
Answer ONLY with information from the evidence blocks provided with the question.
Rules:
- After every fact, write the label of the evidence it comes from, like [E1] or [E1][E3].
- Use only evidence labels that appear below. Never invent sources, dates or numbers.
- If the evidence does not answer the question, reply with INSUFFICIENT_CONTEXT on the first line, then one sentence explaining what is missing.
- Write clear, short English in Markdown. …
```

**Final reply**:

> If you are at Seoul campus with an admitted but not enrolled status, you should ask the OIA office. [No Evidence Provided]
> If you are at Seoul campus with an enrolled status, you should ask the OIA office. [No Evidence Provided]
> If you are at Seoul campus with a leave of absence status, you should ask the OIA office. [No Evidence Provided]
> If you are at Seoul campus with a completed coursework or graduating status, you should ask the OIA office. [No Evidence Provided]
> If you are at ERICA campus with an admitted but not enrolled status, you should ask the OIA office. [No Evidence Provided]
> If you are at ERICA campus with an enrolled status, you should ask the OIA office. [No Evidence Provided]
> If you are at ERICA campus with a leave of absence status, international students must register for group insurance due to strict laws of the Korean Ministry of Health and Welfare, submit the insurance registration certificate when applying for registration, pay a fee of 25,000 Won, and access www.isamaster.co.kr/hanyang to click "Insurance applications" (Virtual account on Website); inquiries can be made via KAKAO ID ISACHINA or by calling HYU OIA manager at 031-400-0791~0795. [E1]
> If you are at ERICA campus with a completed coursework or graduating status, you should ask the OIA office. [No Evidence Provided]

## S2: the counseling question, no profile

Question: "How do I book the international student counseling program?"

**Step 1 profile** (rules):

- campus: missing
- degree_level: missing
- year: missing
- student_type: missing
- visa: missing
- topik_level: missing
- english_track: missing
- academic_status: scope_default = admitted_not_enrolled, enrolled, leave_of_absence, completed_coursework, graduating
- korean_standard: missing

**Retrieval**: dense top 10 + BM25 top 10, RRF fused to 14 candidates (14 after enrichment):

| RRF rank | Title | Section | dense | BM25 | RRF | cross-encoder | label | tags | after penalty | reranked rank |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | / KIRD Psychological Counseling for Inte | / KIRD Psychological Counseling for | 0.7008 | 16.6924 | 0.031319 | 1.11 | depends | campus=seoul; scope=campus; degree_level=master/doctoral | 1.11 | 7 |
| 2 | Couseling Program | Hello, International students! | 0.6819 | 15.4869 | 0.030415 | 2.15 | unknown status | campus=seoul; scope=campus | 2.15 | 2 |
| 3 | / Application guide for international st | / Application guide for internation | 0.7339 | 10.9069 | 0.030415 | 1.45 | depends | campus=seoul; scope=campus | 1.45 | 5 |
| 4 | 2026 KOICA-Hanyang(ERICA) NEXT Fellowshi | 2026 KOICA-Hanyang(ERICA) NEXT Fell | 0.6945 | 13.924 | 0.030366 | 0.38 | unknown status | campus=seoul; scope=campus | 0.38 | 10 |
| 5 | 2026 KOICA-Hanyang(ERICA) NEXT Fellowshi | 2026 KOICA-Hanyang(ERICA) NEXT Fell | 0.7072 | 11.1023 | 0.03009 | 0.87 | unknown status | campus=seoul; scope=campus | 0.87 | 8 |
| 6 | Psychological Counseling | Stay Connected | 0.6993 | 11.0557 | 0.029199 | 1.84 | unknown status | campus=erica; scope=campus | 1.84 | 4 |
| 7 | / Application guide for international st | / Application guide for internation | 0.7805 |  | 0.016393 | 0.64 | depends | campus=seoul; scope=campus | 0.64 | 9 |
| 8 | Psychological Counseling | Psychological counseling for intern | 0.7281 |  | 0.015873 | 0.08 | depends | campus=erica; scope=campus | 0.08 | 11 |
| 9 | Couseling Program | Hello, International students! | 0.7162 |  | 0.015625 | -0.43 | depends | campus=seoul; scope=campus | -0.43 | 12 |
| 10 | Couseling Program | Hello, International students! |  | 13.2933 | 0.015625 | -1.47 | unknown status | campus=seoul; scope=campus | -1.47 | 14 |
| 11 | / Painting My Hopes for Studying Abroad | / Painting My Hopes for Studying Ab |  | 12.1371 | 0.015385 | 1.18 | depends | campus=seoul; scope=campus; degree_level=undergraduate/master/doctoral | 1.18 | 6 |
| 12 | International students Counseling Month  | International students Counseling M | 0.7049 |  | 0.015152 | 2.97 | depends | campus=seoul; scope=campus; degree_level=master/doctoral | 2.97 | 1 |
| 13 | Christmas Wreath Making Program / | Christmas Wreath Making Program / |  | 11.9762 | 0.015152 | -0.73 | depends | campus=seoul; scope=campus; degree_level=undergraduate/master/doctoral | -0.73 | 13 |
| 14 | Psychological Counseling | 3-Phase Counseling Services |  | 11.2266 | 0.014925 | 2.09 | unknown status | campus=erica; scope=campus | 2.09 | 3 |

**Top-3 evidence and coverage** (relevant if query-word coverage ≥ 0.30):

- International students Counseling Month program (https://oia.hanyang.ac.kr/notice/1796004): coverage 0.4
- Couseling Program (https://oia.hanyang.ac.kr/counseling): coverage 0.4
- Psychological Counseling (https://global.hanyang.ac.kr/eng/s3/s3_5_1.php): coverage 0.8

**Branches** (information score per detail, over the relevant chunks: 10a6d7dc-3bcb-56ce-a901-c3dd2250dc91, c0df53fd-278e-56d6-af25-2e7cf16c687f, 7fc6be78-01b5-5043-9e21-7b189464bbd9):

- campus: information 1.0; chunks that apply per value: seoul → 2; erica → 1
- degree_level: information 0.970951; chunks that apply per value: undergraduate → 2; master → 3; doctoral → 3; language_program → 2; non_degree → 2

**Branch table** (detail → value → passages):

- {'campus': ['seoul'], 'degree_level': ['undergraduate', 'language_program', 'non_degree']} → ['c0df53fd-278e-56d6-af25-2e7cf16c687f']
- {'campus': ['seoul'], 'degree_level': ['master', 'doctoral']} → ['10a6d7dc-3bcb-56ce-a901-c3dd2250dc91', 'c0df53fd-278e-56d6-af25-2e7cf16c687f']
- {'campus': ['erica'], 'degree_level': ['undergraduate', 'master', 'doctoral', 'language_program', 'non_degree']} → ['7fc6be78-01b5-5043-9e21-7b189464bbd9']

**Decision**: CLARIFY (reason: different_procedures; clarify detail: campus)

**Reply source**: fixed template, no LLM call.

**Final reply**:

> The answer depends on your campus. Which applies to you: Seoul or ERICA?

## S6: the same question after "I'm a Seoul campus student."

Question: "How do I book the international student counseling program?" (earlier turns: ["I'm a Seoul campus student."])

**Step 1 profile** (rules):

- campus: remembered = seoul (from "Seoul")
- degree_level: missing
- year: missing
- student_type: missing
- visa: missing
- topik_level: missing
- english_track: missing
- academic_status: scope_default = admitted_not_enrolled, enrolled, leave_of_absence, completed_coursework, graduating
- korean_standard: missing

**Retrieval**: dense top 10 + BM25 top 10, RRF fused to 14 candidates (14 after enrichment):

| RRF rank | Title | Section | dense | BM25 | RRF | cross-encoder | label | tags | after penalty | reranked rank |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | / KIRD Psychological Counseling for Inte | / KIRD Psychological Counseling for | 0.7008 | 16.6924 | 0.031319 | 1.11 | depends | campus=seoul; scope=campus; degree_level=master/doctoral | 1.11 | 5 |
| 2 | Couseling Program | Hello, International students! | 0.6819 | 15.4869 | 0.030415 | 2.15 | unknown status | campus=seoul; scope=campus | 2.15 | 2 |
| 3 | / Application guide for international st | / Application guide for internation | 0.7339 | 10.9069 | 0.030415 | 1.45 | applies to all | campus=seoul; scope=campus | 1.45 | 3 |
| 4 | 2026 KOICA-Hanyang(ERICA) NEXT Fellowshi | 2026 KOICA-Hanyang(ERICA) NEXT Fell | 0.6945 | 13.924 | 0.030366 | 0.38 | unknown status | campus=seoul; scope=campus | 0.38 | 8 |
| 5 | 2026 KOICA-Hanyang(ERICA) NEXT Fellowshi | 2026 KOICA-Hanyang(ERICA) NEXT Fell | 0.7072 | 11.1023 | 0.03009 | 0.87 | unknown status | campus=seoul; scope=campus | 0.87 | 6 |
| 6 | Psychological Counseling | Stay Connected | 0.6993 | 11.0557 | 0.029199 | 1.84 | conflicts | campus=erica; scope=campus | -2.16 | 13 |
| 7 | / Application guide for international st | / Application guide for internation | 0.7805 |  | 0.016393 | 0.64 | applies to all | campus=seoul; scope=campus | 0.64 | 7 |
| 8 | Psychological Counseling | Psychological counseling for intern | 0.7281 |  | 0.015873 | 0.08 | conflicts | campus=erica; scope=campus | -3.92 | 14 |
| 9 | Couseling Program | Hello, International students! | 0.7162 |  | 0.015625 | -0.43 | applies to all | campus=seoul; scope=campus | -0.43 | 9 |
| 10 | Couseling Program | Hello, International students! |  | 13.2933 | 0.015625 | -1.47 | unknown status | campus=seoul; scope=campus | -1.47 | 11 |
| 11 | / Painting My Hopes for Studying Abroad | / Painting My Hopes for Studying Ab |  | 12.1371 | 0.015385 | 1.18 | depends | campus=seoul; scope=campus; degree_level=undergraduate/master/doctoral | 1.18 | 4 |
| 12 | International students Counseling Month  | International students Counseling M | 0.7049 |  | 0.015152 | 2.97 | depends | campus=seoul; scope=campus; degree_level=master/doctoral | 2.97 | 1 |
| 13 | Christmas Wreath Making Program / | Christmas Wreath Making Program / |  | 11.9762 | 0.015152 | -0.73 | depends | campus=seoul; scope=campus; degree_level=undergraduate/master/doctoral | -0.73 | 10 |
| 14 | Psychological Counseling | 3-Phase Counseling Services |  | 11.2266 | 0.014925 | 2.09 | conflicts | campus=erica; scope=campus | -1.91 | 12 |

**Top-3 evidence and coverage** (relevant if query-word coverage ≥ 0.30):

- International students Counseling Month program (https://oia.hanyang.ac.kr/notice/1796004): coverage 0.4
- Couseling Program (https://oia.hanyang.ac.kr/counseling): coverage 0.4
- / Application guide for international student counseling ser (https://oia.hanyang.ac.kr/notice/1796780): coverage 0.2

**Branches** (information score per detail, over the relevant chunks: 10a6d7dc-3bcb-56ce-a901-c3dd2250dc91, c0df53fd-278e-56d6-af25-2e7cf16c687f):

- degree_level: information 0.970951; chunks that apply per value: undergraduate → 1; master → 2; doctoral → 2; language_program → 1; non_degree → 1

**Branch table** (detail → value → passages):

- {'degree_level': ['undergraduate', 'language_program', 'non_degree']} → ['c0df53fd-278e-56d6-af25-2e7cf16c687f']
- {'degree_level': ['master', 'doctoral']} → ['10a6d7dc-3bcb-56ce-a901-c3dd2250dc91', 'c0df53fd-278e-56d6-af25-2e7cf16c687f']

**Decision**: CONDITIONAL (reason: few_branches; clarify detail: None)

**Branch note added to the prompt**:

```
The answer depends on the student's degree level. Answer every case below separately, starting each with 'If you'; do not pick one for the student.
- degree level undergraduate, language program or non degree: use [E2]
- degree level master or doctoral: use [E1][E2]
```

**Prompt** (439 tokens; system message trimmed):

```
You are HYU Compass, a helpful assistant for new students at Hanyang University.
Answer ONLY with information from the evidence blocks provided with the question.
Rules:
- After every fact, write the label of the evidence it comes from, like [E1] or [E1][E3].
- Use only evidence labels that appear below. Never invent sources, dates or numbers.
- If the evidence does not answer the question, reply with INSUFFICIENT_CONTEXT on the first line, then one sentence explaining what is missing.
- Write clear, short English in Markdown. …
```

**Final reply**:

> If you are an undergraduate student in a language program or without a degree, you can visit the Office of International Cooperation (OIA) at Hanyang University for help with psychological and affective problems as well as needs in daily life and study. [E2]
> If you are a graduate student (Master & Ph.D.), you can participate in the International students Counseling Month program which is prepared for international students in January in English, where 10 international students will be present every session with four topics to enrich your hearts. You can apply online via the link provided: https://moaform.com/q/OfIsWX. [E1][E2]
> 
> This may depend on your situation; please confirm with the OIA office.

