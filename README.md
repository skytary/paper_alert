# PaperAlert

**English** | [한국어](README.ko.md)

A Windows desktop app that collects new-article alerts from academic journals in your Gmail (tables of contents, OnlineFirst alerts, Google Scholar alerts, and so on), organizes them on one screen, and sends the papers you want to Zotero.

For day-to-day use, see the [User Manual](MANUAL.md).

## What it does

1. Reads unread Gmail messages with the label `논문_알리미` ("paper alerts"; the label name is configurable).
2. Uses the Claude API to extract every article listed in each email (book reviews are skipped).
3. Looks up each article's DOI and abstract in Crossref and OpenAlex, and skips articles already saved (same DOI or title).
4. Scores each new article from 1 to 5 against your research interests and writes a summary, the data, the method, and the key findings, in Korean or English.
5. Saves the results in a local SQLite database (`papers.db`) that you can filter and sort by score, journal, year, and category.
6. Sends papers to Zotero with full bibliographic data and a summary note, without duplicating items already in your library. The target collection can be fixed, mapped from categories, or chosen by Claude from a criteria file you write.
7. Offers a batch mode (Message Batches API) that halves the cost when many emails have piled up.

## Requirements

- Windows, Python 3.10 or later
- An Anthropic API key with credits (https://platform.claude.com)
- An OAuth client file (`credentials.json`, desktop app type) from a Google Cloud project with the Gmail API enabled
- A Zotero API key with write access and your Zotero user ID (https://www.zotero.org/settings/keys). Not needed if you do not use the Zotero features.

## Installation

```powershell
git clone https://github.com/skytary/paper_alert.git
cd paper_alert
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env    # open .env and fill in your API keys
```

Then:

1. Put the OAuth client file downloaded from the Google Cloud Console in this folder as `credentials.json`.
2. Create the Gmail label `논문_알리미` and a filter that applies it to your journal alert emails. To use a different label name, change `GMAIL_LABEL` in `gmail_client.py`.
3. **Edit `SYSTEM_PROMPT` in `paper_processor.py` to describe your own research interests.** The included prompt scores papers against the author's interests (social stratification, sociology of education, family demography) and course list. If you rename the categories, also update `DEFAULT_CATEGORIES` in `database.py`.

## Running

- Create shortcuts: `.venv\Scripts\python.exe create_shortcut.py`. This creates shortcuts in the app folder (`PaperAlert.lnk`) and the Start menu, and updates a pinned taskbar shortcut if there is one. To pin the app to the taskbar, start it, right-click its taskbar icon, and choose "Pin to taskbar". Use the shortcuts from then on.
  - The shortcuts run the base Python's `pythonw.exe` rather than the venv's `Scripts\pythonw.exe`, because a venv created by uv contains a console version of `pythonw.exe` that opens a terminal window. `launch.pyw` loads the venv's packages itself.
  - The shortcuts and the app window share the app ID `PaperAlert.App.1`, so they appear as one taskbar icon. Clicking a shortcut while the app is open brings the existing window to the front.
- Run in a browser: `.venv\Scripts\python.exe app.py`, then open http://127.0.0.1:5000

The first time you click **Fetch**, a Google sign-in page opens in your browser; after you allow access, `token.json` is created. The same page appears again if access expires.

Use **⚙ Settings** to choose the summary language, start date, number and order of emails per fetch, batch mode, and the Zotero options. See the [User Manual](MANUAL.md) for details.

## Files

| File | Role |
|---|---|
| `app.py` | Flask web app and background email processing |
| `gmail_client.py` | Gmail API authorization and email reading |
| `paper_processor.py` | Article extraction and scoring with the Claude API (includes the research-interest prompt) |
| `enrich.py` | DOI and abstract lookup via Crossref and OpenAlex |
| `batch_processor.py` | Batch processing (Message Batches API, half price) |
| `database.py` | SQLite storage, queries, and settings |
| `zotero_client.py` | Adding items through the Zotero Web API; filling in missing details |
| `zotero_index.py` | Local index of DOIs and titles in your Zotero library (duplicate detection) |
| `zotero_targets.py` | Choosing the Zotero collection (root / one collection / by category / by criteria file) |
| `version.py` | Version and author information (About window) |
| `templates/index.html` | The user interface (single page) |
| `static/owl.png` | Image for the About window |
| `launch.pyw` | Launcher that opens the app in a pywebview window with a tray icon |
| `create_shortcut.py` | Creates the app-folder, Start-menu, and taskbar shortcuts |

## Notes

- `.env`, `credentials.json`, `token.json`, and `papers.db` contain private keys and data and are excluded by `.gitignore`. Do not commit them.
- The server listens on `127.0.0.1:5000`, so only this computer can reach it. To allow other devices on your network, change `host` to `'0.0.0.0'` in `app.py` and `launch.pyw` (there is no authentication, so this is not recommended on public Wi-Fi).
- The Claude model (`MODEL`, default `claude-sonnet-5-5`) and reasoning effort (`EFFORT`, default `medium`) are set in `paper_processor.py`. Responses are constrained by JSON schemas (`EXTRACT_SCHEMA`, `SCORE_SCHEMA`), and the research-interest prompt is cached.

Built with Claude Code (first version March–April 2026; version 2.0 in October 2026).

## Author

Seongsoo Choi, Department of Sociology, Yonsei University (s.choi@yonsei.ac.kr)

## License

MIT License. See [LICENSE](LICENSE) for details.
