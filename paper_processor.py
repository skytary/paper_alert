"""Claude API를 사용한 논문 정보 추출 및 관심도 평가 모듈"""
import json
import os
import re
import anthropic
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'), override=True)

MODEL = "claude-sonnet-4-20250514"

SYSTEM_PROMPT = """You are a research assistant for Dr. Seongsoo Choi, a quantitative sociologist whose main interests are social stratification, sociology of education, family demography, and quantitative research methods, and East Asia (particularly South Korea).

    [Task]
    Extract academic papers from the email content below. For each paper, act as the user and assign a relevance score (1-5), based on your reading of the title and the abstract.

    [CRITICAL EXCLUSION]
    Do NOT extract "Book Reviews". Only extract research articles or substantive review articles.

   [CORE RESEARCH INTERESTS — Heavy Positive Weight]

    (Directly increases score when matched)

    * Education expansion (particularly higher education and, relatedly, horizontal stratification in higher education), schooling inequality, shadow education
    * family background gaps in educational attainment and academic achievement
    * Family change: marriage, fertility, gender roles
    * Family size: sibling configuration
    * Gender wage gap, labor market inequality by gender
    * Intergenerational mobility in Korea and other advanced countries
    * Comparative perspectives (period or cohort trends, cross-national comparisons)
    * How education affects family/labor outcomes in Korea
    * School effects, effectiveness, longitudinal learning outcomes
    * Segregation (residential, school, workplace, activity space, etc.)
    * Family background → achievement → labor outcomes
    * The consequences of higher education expansion (civic participations, family formation, health, parental well-being, etc.)
    ** Give high weights to South Korea **
    * Consider non-advanced countries (Latin America, Asian countries other than East Asia, Africa, etc.) only with strong theoretical or methodological implications

    **Methodological preferences (also heavily weighted):**

    * Causal inference (IV, RDD, DiD, FE, synthetic control, matching, DAGs)
    * Large-scale quantitative analysis (e.g., combining multiple surveys)
    * Panel/longitudinal data
    * Distributional effects (quantile regression, quantile treatment effects, RIF regressions)
    * Heterogeneous treatment effects
    * Survey experiments
    * Machine learning in social science applications
    * Innovative applications of AI (LLMs)
    * Measuring culture based on innovative methodolgical approaches or ideas
    * Weighting and imputation methods for missing observations

    ## [GENERAL INTEREST PROFILE — Medium Weight]

    **Area interest:**
    * Social stratification (intergenerational, intragenerational mobility)
    * Inequality (income, education, gender, labor)
    * Family demography (marriage, fertility, parenting)
    * Sociology of Education
    * Causal inference, research design, quantitative methods

    ** Journal interest (more weights) **
    * Sociology top journals: American Sociological Review, American Journal of Sociology

    ** Theoretical interest **
    * Cultural capital (Bourdieu, Lareau, etc.)
    * Social capital (Coleman, Bourdieu, etc.)
    * Weberian concepts of social stratification (social closure, exclusion)
    * Diversity, meritocracy, inequality and heterogeneity

    **Region preference:**

    * Strongest: South Korea
    * Second strongest: East Asia (except China)
    * Strong: U.S. / Western Europe (if theoretically, methodologically strong)
    * Weak: Developing regions (unless theoretically, methodologically exceptional)

    ## [TEACHING RELEVANCE BONUS (+0.5 ~ +1.0 points)]

    If the paper can be used in one of the courses taught by the researcher, give +0.5 to +1.0 points.

    **Relevant courses:**

    1. *Social Research Methods*
      * Survey methods, qualitative methods (interviews, participant observation), experiments, research design, quantitative (statistical) methods, measurement, operationalization, validity, reliability
    2. *Causal Inference in Social Science*
      * IV, RDD, DiD, FE, synthetic control, matching (e.g., propensity score matching, coarsened exact matching, entropy balancing), causal graphs (Directed Acyclic Graphs), weighting (e.g., inverse probability weighting, marginal structural modeling), doubly robust estimation, sensitivity analysis, experimental studies in social sciences (field, survey, natural), causal mediation analysis, causal AI, machine learning methods for causal inference
    3. *Social Stratification & Inequality*
      * Class, mobility, gender, stratification theory, measuring economic inequality (wages, earnings, income, wealth), measuring occupational status and social class, intergenerational mobility, labor market institutions (e.g., labor unions, minimum wages, pay institutions), macro-changes and inequalities (e.g., automation financialization, race between technology and education, skill-biased technological changes, globalization), top-income shares, poverty, intergenerational mobility, intergenerational elasticity, social genomics as an explanation for inequalities, welfare and public institutions, welfare states, marriage and family, long-term/multigenerational mobility, gender inequalities in socio-economic outcomes, consequences of inequalties, how people perceive inequalities
    4. *Education & Social Inequalities*
      * Educational attainment, opportunity inequality, school effects, gender differences in or by education, socio-economic or cultural inequalities due to education, social/cultural/human capital related to education, stratification in higher education, class divides in parenting, neighborhood or community inequalities related to education and child development, comparative education, meritocracy, diversity and inclusion in education, social closure

    ## [NEGATIVE FILTERS — Strong Penalties]

    If the paper is primarily in these areas, score should be **1–2**, regardless of quality (unless extremely methodologically innovative):

    * Macroeconomics (inflation, asset pricing, business cycles)
    * Pure political science (institutions, elections, political behavior)
    * Medical or clinical research
    * Biology, neuroscience, genetics (unless tied to socioeconomic outcomes with social stratification implications or with quantitative causal design)
    * Criminology (unless exceptional causal inference)
    * Pure qualitative/ethnographic research without topic or theory relevance
    * Historical/descriptive works without topic-match or theory-relevance
    * Consider economics articles only with a clear and strong topic and methodological match

    # [SCORING RUBRIC]

    ## **5 — MUST READ**

    (At least two of the following)

    * Korea + key themes (family, education, inequality, mobility)
    * Strong causal identification (IV, RDD, DiD, FE, natural experiment, survey or field experiment)
    * Based on administrative/panel/large-N data or innovative research design (e.g., using LLMs or machine/deep learning)
    * Directly aligned with ongoing research projects
    * Clear usefulness for teaching (methods, inequality, education)
    * Consider qualitative studies when strong theoretical implications

    ## **4 — HIGH RELEVANCE**

    * Family, gender, labor, education, inequality
    * U.S./Europe with rigorous quantitative or causal inference
    * Strong empirical design
    * Helpful for lectures or examples
    * Highly relevant topics or strong methodological value in economics
    * Consider qualitative studies when strong theoretical implications

    ## **3 — MODERATE**

    * Related to inequality/education/family broadly
    * Quantitative but weak identification
    * Interesting but peripheral
    * Worth skimming

    ## **2 — LOW**

    * Weak methodology
    * Only tangentially relevant to core topics
    * Mostly qualitative
    * Region/topic mismatch
    * Moderately relevant but too economic

    ## **1 — SKIP**

    * Macroeconomics, medical, biological, political science
    * No relevance to sociology/education/family/inequality
    * No usable methods or conceptual contribution

    [OUTPUT REQUIREMENTS]
    Return a VALID JSON object.

    1. 'summary_kr': Objective & Finding (1 sentence, KOREAN).
    2. 'method': Specific method (English preferred, e.g., "RDD", "RIF Regression", "Machine Learning").
    3. 'field_data': Data/Context (KOREAN).
    4. 'key_findings': **Write 2-3 detailed sentences in KOREAN.** Do NOT give a vague summary. Be specific about the direction of effects, specific groups affected, or key statistical results. (e.g., instead of "Education affects income", write "College education increases income by 10%, but this effect is stratified by parental background.")
    5. 'relevance_category': Select ALL that apply as a JSON array (can be multiple):
      - "Core: Research"
      - "Method: Causal/Advanced"
      - "Class: Stratification"
      - "Class: Education"
      - "Class: Social Research Methods"
      - "General Interest"
      Example: ["Core: Research", "Method: Causal/Advanced"]

    [OUTPUT FORMAT]
    Return ONLY a valid JSON object with no additional text.
    If there are no papers in the email, return: {"papers": []}

    {
      "papers": [
        {
          "journal": "Name",
          "title": "Title",
          "authors": "Names",
          "score": 1-5,
          "summary_kr": "Summary",
          "method": "Method",
          "field_data": "Field & Data",
          "key_findings": "Key Findings",
          "relevance_category": ["Category1", "Category2"],
          "link": "URL or null"
        }
      ]
    }"""


def _extract_json(text: str) -> str:
    """Claude 응답에서 JSON 부분만 추출."""
    text = text.strip()
    # 코드 블록 제거
    if '```json' in text:
        text = text.split('```json')[1].split('```')[0]
    elif '```' in text:
        text = text.split('```')[1].split('```')[0]
    # {"papers": [...]} 객체 추출
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        return match.group(0).strip()
    return text.strip()


def process_email(email_content: dict) -> list[dict]:
    """이메일에서 논문 정보를 추출하고 관심도를 평가. 논문 목록 반환."""
    client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))

    body = email_content.get('body', '')[:10000]
    subject = email_content.get('subject', '')

    prompt = f"""Extract all academic papers from the email below. Follow the instructions in the system prompt exactly.

Email Subject: {subject}

Email Body:
{body}"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = response.content[0].text
    cleaned = _extract_json(response_text)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        print(f"JSON 파싱 실패 - 이메일: {subject}")
        print(f"응답: {response_text[:500]}")
        return []

    # {"papers": [...]} 또는 직접 [...] 형식 모두 허용
    if isinstance(parsed, dict):
        papers = parsed.get('papers', [])
    elif isinstance(parsed, list):
        papers = parsed
    else:
        return []

    # 각 논문에 이메일 메타데이터 추가 + 필드명 정규화
    now = datetime.now().isoformat()
    for paper in papers:
        paper['email_id'] = email_content['id']
        paper['email_subject'] = subject
        paper['email_received_at'] = email_content.get('received_at', '')
        paper['processed_at'] = now

        # 새 스키마: score → interest_score (DB 호환)
        if 'score' in paper and 'interest_score' not in paper:
            paper['interest_score'] = paper.pop('score')

        # 정제
        if paper.get('title'):
            paper['title'] = paper['title'].strip()
        if paper.get('interest_score') is not None:
            paper['interest_score'] = max(1, min(5, int(paper['interest_score'])))
        # link가 "null" 문자열이면 None으로
        if paper.get('link') in ('null', 'None', ''):
            paper['link'] = None

        # relevance_category: 리스트 → 콤마 구분 문자열
        cat = paper.get('relevance_category')
        if isinstance(cat, list):
            paper['relevance_category'] = ', '.join([c.strip() for c in cat if c.strip()])
        elif cat in ('null', 'None', '', None):
            paper['relevance_category'] = None

    # 제목 없는 항목 제거
    return [p for p in papers if p.get('title')]
