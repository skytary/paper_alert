"""연구 관심사 프로필 파일(research_profile.md)을 읽는다.

파일 전체가 평가 프롬프트에 들어가고, "## Categories" 절의 목록이 카테고리가 된다.
카테고리 줄 형식: - `이름`: 설명   (백틱이 없으면 " | " 앞을 이름으로 봄)
"""
import os
import re

import database

APP_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = 'research_profile.template.md'

_CAT_HEADING = re.compile(r'^#{1,6}\s*categories\b', re.IGNORECASE)
_ANY_HEADING = re.compile(r'^#{1,6}\s')
_ITEM = re.compile(r'^\s*[-*]\s+(.*)$')
_COMMENT = re.compile(r'<!--.*?-->', re.DOTALL)


class ProfileError(Exception):
    pass


def path(settings: dict | None = None) -> str:
    settings = settings or database.get_settings()
    p = settings['research_profile_file']
    return p if os.path.isabs(p) else os.path.join(APP_DIR, p)


def parse_categories(text: str) -> list[tuple[str, str]]:
    """'## Categories' 절의 (이름, 설명) 목록."""
    cats, inside = [], False
    for line in _COMMENT.sub('', text).splitlines():
        if _CAT_HEADING.match(line):
            inside = True
            continue
        if inside and _ANY_HEADING.match(line):
            break
        m = _ITEM.match(line) if inside else None
        if not m:
            continue
        item = m.group(1).strip()
        bt = re.match(r'`([^`]+)`\s*:?\s*(.*)$', item)
        if bt:
            name, desc = bt.group(1).strip(), bt.group(2).strip()
        elif ' | ' in item:
            name, desc = (x.strip() for x in item.split(' | ', 1))
        else:
            name, desc = item, ''
        if name and name not in [c[0] for c in cats]:
            cats.append((name, desc))
    return cats


def load(settings: dict | None = None) -> dict:
    """{'text', 'categories', 'path'}. 파일이 없거나 카테고리가 없으면 ProfileError."""
    p = path(settings)
    if not os.path.exists(p):
        raise ProfileError(
            f'Research profile not found: {p}. Copy {TEMPLATE} to research_profile.md, fill it in, '
            f'and check the path in Settings.')
    with open(p, encoding='utf-8') as f:
        text = f.read()
    cats = parse_categories(text)
    if not cats:
        raise ProfileError(f'No categories found in {p}. Add a "## Categories" section '
                           f'(see {TEMPLATE}).')
    if '[' in text and re.search(r'\[(your|a specific|another|course name)', text, re.IGNORECASE):
        raise ProfileError(f'{p} still contains [placeholders] from the template. Fill them in first.')
    return {'text': _COMMENT.sub('', text).strip(), 'categories': cats, 'path': p}


def sync_categories(settings: dict | None = None):
    """프로필의 카테고리를 앱의 카테고리 목록에 추가 (이미 있는 것은 그대로, 지우지 않음)."""
    for name, _ in load(settings)['categories']:
        database.add_category(name)


def status(settings: dict | None = None) -> dict:
    try:
        prof = load(settings)
        return {'ok': True, 'path': prof['path'], 'categories': [c[0] for c in prof['categories']],
                'chars': len(prof['text'])}
    except ProfileError as e:
        return {'ok': False, 'error': str(e)}
