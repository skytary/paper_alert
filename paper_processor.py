"""Claude API를 사용한 논문 정보 추출 및 관심도 평가 모듈"""
import json
import os
import anthropic
from datetime import datetime
from dotenv import load_dotenv

import database
import enrich
import research_profile

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'), override=True)

MODEL = "claude-sonnet-5-5"
EFFORT = "medium"        # 생각 깊이: low / medium / high. 높을수록 정확하지만 비용·시간 증가
MAX_TOKENS = 64000       # 논문이 많은 메일도 응답이 잘리지 않도록 넉넉히 (스트리밍 필요)

# 평가 프롬프트의 공통 부분. 연구자 개인의 관심사·채점 기준·카테고리는 프로필 파일
# (research_profile.md, 설정에서 지정)에서 읽어 {profile} 자리에 넣는다.
SCORING_PROMPT = """You are a research assistant who screens newly published academic papers for one researcher. The researcher's profile below describes their interests, preferred methods, negative filters, teaching, scoring rubric, and categories. Act as this researcher.

[Task]
You will receive a numbered list of papers (title, authors, journal, and the abstract when available), plus the original alert email for context. For EVERY paper in the list, assign a relevance score (1-5) according to the profile and write the summary fields, based on the title and the abstract. Return exactly one result per paper, using its number as 'index'. Never skip a paper: an irrelevant paper gets a low score (usually 1).

--- RESEARCHER PROFILE ---
{profile}
--- END OF RESEARCHER PROFILE ---

[OUTPUT REQUIREMENTS]
For each paper, fill in these fields (the response format is enforced by a JSON schema).
Write 'summary_kr', 'field_data', and 'key_findings' in the OUTPUT LANGUAGE named in the request (the field names stay the same whatever the language).

1. 'index': the paper's number in the list.
2. 'score': integer 1-5 per the profile's scoring rubric and filters.
3. 'summary_kr': Objective & Finding (1 sentence, in the output language).
4. 'method': Specific method as named in the abstract (English preferred, e.g., "RDD", "RIF Regression", "Two-way fixed effects with event study").
5. 'field_data': Data/Context (in the output language). **Name the specific dataset(s) when the abstract names them** (e.g., "NLSY97", "PSID", "Korean Education Longitudinal Study (KELS)", "Danish administrative registers"), together with the country/population and period. Avoid vague labels such as "U.S., longitudinal data" when the abstract gives more detail.
6. 'key_findings': **Write 2-3 detailed sentences in the output language.** Do NOT give a vague summary. Be specific about the direction of effects, specific groups affected, or key statistical results. (e.g., instead of "Education affects income", write "College education increases income by 10%, but this effect is stratified by parental background.")
7. 'relevance_category': Select ALL categories from the profile's Categories section that apply (one or more). Use the category names exactly as written.

[WHEN THE ABSTRACT IS MISSING]
If a paper has no abstract (neither in the list nor in the email), score it from the title, authors, and journal, but do not invent details. Write the NO-ABSTRACT MARKER given in the request for 'method', 'field_data', and 'key_findings', and base 'summary_kr' only on what the title states."""

EXTRACT_PROMPT = """You extract the list of articles from an academic journal alert email (eTOC, OnlineFirst, Google Scholar alerts, etc.).

Rules:
* Do NOT extract book reviews. This is the only content type to skip.
* Extract every other article, however irrelevant it seems. Do not judge relevance.
* Copy 'title', 'authors', and 'journal' as shown in the email. Use null when absent.
* 'link': the URL attached to the article (shown in <angle brackets> after the title, or nearby). Use null if absent.
* 'year': the publication year only if the email states it. Use null otherwise; do not guess.
* If the email contains no articles, return an empty 'papers' list."""


# 요약 언어별 '초록 없음' 표시. 언어 지시는 캐싱되는 시스템 프롬프트가 아니라 요청 쪽에 넣는다.
NO_ABSTRACT_MARKER = {'Korean': '초록 없음', 'English': 'No abstract'}

_NULLABLE_STR = {"type": ["string", "null"]}

# 1단계 응답 형식: 메일에 실린 논문 목록
EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "papers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "authors": _NULLABLE_STR,
                    "journal": _NULLABLE_STR,
                    "year": {"type": ["integer", "null"]},
                    "link": _NULLABLE_STR,
                },
                "required": ["title", "authors", "journal", "year", "link"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["papers"],
    "additionalProperties": False,
}

# 2단계 응답 형식: 논문별 점수와 요약 (index로 목록과 짝지음)
SCORE_SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "score": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
                    "summary_kr": {"type": "string"},
                    "method": {"type": "string"},
                    "field_data": {"type": "string"},
                    "key_findings": {"type": "string"},
                    "relevance_category": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["index", "score", "summary_kr", "method", "field_data",
                             "key_findings", "relevance_category"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["results"],
    "additionalProperties": False,
}

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))
    return _client


def request_params(system: str, user: str, schema: dict, effort: str) -> dict:
    """Messages API 요청 내용. 바로 처리(_call)와 배치 처리(batch_processor)가 같이 씀."""
    return {
        'model': MODEL,
        'max_tokens': MAX_TOKENS,
        # 시스템 프롬프트 캐싱: 두 번째 호출부터 이 부분 비용이 약 1/10
        'system': [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        'messages': [{"role": "user", "content": user}],
        'output_config': {"effort": effort, "format": {"type": "json_schema", "schema": schema}},
    }


def parse_response(message, label: str) -> dict:
    """응답에서 JSON을 꺼냄. 잘리거나(max_tokens) 거절되면 예외."""
    if message.stop_reason == 'max_tokens':
        raise RuntimeError(f'Response cut off at the {MAX_TOKENS}-token limit: {label}')
    if message.stop_reason == 'refusal':
        raise RuntimeError(f'Claude declined to process: {label}')
    text = next((b.text for b in message.content if b.type == 'text'), '')
    return json.loads(text)


def _call(system: str, user: str, schema: dict, effort: str, label: str) -> dict:
    """Claude를 한 번 바로 호출해 스키마에 맞는 JSON을 돌려받음.

    응답이 잘리거나(max_tokens) 거절되면 예외를 일으킨다. 호출하는 쪽은 그 메일을
    처리 완료로 기록하지 않으므로 다음 실행 때 다시 시도된다.
    """
    with _get_client().messages.stream(
        **request_params(system, user, schema, effort),
        # 안전 분류기가 요청을 거절하면 서버가 다른 모델로 자동 재시도 (배치 API에서는 쓸 수 없음)
        extra_headers={"anthropic-beta": "server-side-fallback-2026-07-01"},
        extra_body={"fallbacks": "default"},
    ) as stream:
        response = stream.get_final_message()
    return parse_response(response, label)


# ── 1단계: 논문 목록 뽑기 ─────────────────────────────────────────────────── #

def extract_request(email_content: dict) -> tuple:
    """(system, user, schema, effort)"""
    subject = email_content.get('subject', '')
    user = f"Email Subject: {subject}\n\nEmail Body:\n{email_content.get('body', '')}"
    return EXTRACT_PROMPT, user, EXTRACT_SCHEMA, 'low'


def parse_extract(result: dict) -> list[dict]:
    papers = result['papers']
    for p in papers:
        p['title'] = (p.get('title') or '').strip()
    return [p for p in papers if p['title']]


def extract_papers(email_content: dict) -> list[dict]:
    """1단계: 메일에 실린 논문 목록(제목·저자·학술지·연도·링크)만 뽑음."""
    label = email_content.get('subject', '')[:60]
    return parse_extract(_call(*extract_request(email_content), label))


# ── 보강과 중복 거르기 ───────────────────────────────────────────────────── #

def enrich_and_dedupe(papers: list[dict], skip_existing: bool = True) -> tuple[list[dict], int]:
    """DOI·초록 보강 후 DB에 이미 있는 논문을 거름. (새 논문, 건너뛴 편수)"""
    papers = [enrich.enrich(p) for p in papers]
    if not skip_existing:
        return papers, 0
    keys = database.existing_keys()
    new, skipped = [], 0
    for p in papers:
        if database.is_duplicate(p, keys):
            skipped += 1
            continue
        # 같은 메일 안의 중복도 거름
        keys[0].add((p.get('doi') or '').lower())
        keys[1].add(database.norm_title(p['title']))
        new.append(p)
    return new, skipped


# ── 2단계: 평가 ──────────────────────────────────────────────────────────── #

def score_request(papers: list[dict], email_content: dict, language: str = 'Korean') -> tuple:
    """(system, user, schema, effort). 초록은 보강 단계에서 찾은 것을 붙여 보냄."""
    lines = []
    for i, p in enumerate(papers, 1):
        lines.append(f"[{i}] Title: {p['title']}")
        lines.append(f"    Authors: {p.get('authors') or 'unknown'}")
        lines.append(f"    Journal: {p.get('journal') or 'unknown'}")
        abstract = p.get('abstract') or '(not found in databases; use the email body if it has one)'
        lines.append(f"    Abstract: {abstract}")
    subject = email_content.get('subject', '')
    marker = NO_ABSTRACT_MARKER.get(language, NO_ABSTRACT_MARKER['English'])
    user = (f"OUTPUT LANGUAGE: {language}\nNO-ABSTRACT MARKER: {marker}\n\n"
            + "Papers to score:\n\n" + "\n".join(lines)
            + f"\n\n--- Original alert email (context) ---\nSubject: {subject}\n\n"
            + email_content.get('body', ''))
    profile = research_profile.load()
    names = [c[0] for c in profile['categories']]
    # 카테고리는 프로필에 적힌 이름 중에서만 고르도록 스키마로 강제
    schema = json.loads(json.dumps(SCORE_SCHEMA))
    schema['properties']['results']['items']['properties']['relevance_category']['items'] = {
        'type': 'string', 'enum': names}
    return SCORING_PROMPT.replace('{profile}', profile['text']), user, schema, EFFORT


def merge_scores(papers: list[dict], result: dict, email_content: dict) -> list[dict]:
    """평가 결과를 논문에 붙이고 메일 정보를 더함. 빠진 논문이 있으면 예외."""
    subject = email_content.get('subject', '')
    by_index = {r['index']: r for r in result['results']}
    missing = [i for i in range(1, len(papers) + 1) if i not in by_index]
    if missing:
        raise RuntimeError(f'Scores missing for {len(missing)} papers: {subject[:60]}')

    now = datetime.now().isoformat()
    scored = []
    for i, p in enumerate(papers, 1):
        r = by_index[i]
        cats = [c.strip() for c in r['relevance_category'] if c.strip()]
        scored.append({
            **p,
            'interest_score': r['score'],
            'summary_kr': r['summary_kr'],
            'method': r['method'],
            'field_data': r['field_data'],
            'key_findings': r['key_findings'],
            'relevance_category': ', '.join(cats) or None,
            'email_id': email_content['id'],
            'email_subject': subject,
            'email_received_at': email_content.get('received_at', ''),
            'processed_at': now,
        })
    return scored


def score_papers(papers: list[dict], email_content: dict, language: str = 'Korean') -> list[dict]:
    """2단계: 논문마다 점수·요약을 매김."""
    label = email_content.get('subject', '')[:60]
    result = _call(*score_request(papers, email_content, language), label)
    return merge_scores(papers, result, email_content)


def process_email(email_content: dict, skip_existing: bool = True,
                  language: str | None = None) -> tuple[list[dict], int]:
    """메일 한 통 바로 처리: 목록 뽑기 → DOI·초록 보강 → 이미 있는 논문 건너뛰기 → 평가.

    반환값은 (저장할 논문 목록, 이미 DB에 있어 건너뛴 편수).
    """
    papers, skipped = enrich_and_dedupe(extract_papers(email_content), skip_existing)
    if not papers:
        return [], skipped
    language = language or database.get_settings()['summary_language']
    return score_papers(papers, email_content, language), skipped
