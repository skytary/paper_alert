"""PaperAlert 버전 정보 (About 창에 표시). 새 버전을 내면 HISTORY 맨 앞에 추가한다."""

APP_NAME = 'PaperAlert'
VERSION = '2.1.0'

AUTHOR = {
    'name': 'Seongsoo Choi',
    'affiliation': 'Department of Sociology, Yonsei University',
    'email': 's.choi@yonsei.ac.kr',
    'github': 'https://github.com/skytary/paper_alert',
}

HISTORY = [
    {
        'version': '2.1.0',
        'date': '2026-10-04',
        'changes': [
            'Research interests, scoring rubric, and categories now live in a profile file '
            '(research_profile.md) chosen in Settings, with a template and an example',
            'Categories are read from the profile and enforced in Claude\'s answers',
            'Quick Start guide and GitHub issue templates for new users',
        ],
    },
    {
        'version': '2.0.0',
        'date': '2026-10-04',
        'changes': [
            'English interface; the "Fetch" button; a Settings window',
            'Claude Sonnet 5.5 with structured outputs and prompt caching',
            'DOI and abstract lookup through Crossref and OpenAlex; more specific data and method summaries',
            'Duplicate detection by DOI and title; every article except book reviews is kept and scored',
            'Summary language (Korean or English)',
            'Start date, emails per fetch, and fetch order settings',
            'Batch mode at half price for large backlogs',
            'Send to Zotero with a summary note; automatic sending by score',
            'Detects papers already in Zotero; can fill in missing details',
            'Choose where papers go in Zotero: library root, one collection, by category, or by a criteria file',
            'Desktop shortcut without a terminal window; new owl icon',
        ],
    },
    {
        'version': '1.0.0',
        'date': '2026-04',
        'changes': [
            'First version: collects journal alert emails from Gmail, extracts papers with Claude, '
            'scores them against research interests, and lists them in a desktop window',
        ],
    },
]
