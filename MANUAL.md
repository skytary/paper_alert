# PaperAlert User Manual

**English** | [한국어](MANUAL.ko.md)

This manual covers version 2.1.0. For installation and first-time setup, see the [Quick Start](QUICKSTART.md). This document explains how to use the app once it is running.

## Contents

1. [Overview](#1-overview)
2. [Collecting papers: Fetch](#2-collecting-papers-fetch)
3. [Browsing papers](#3-browsing-papers)
4. [Sending papers to Zotero](#4-sending-papers-to-zotero)
5. [Settings](#5-settings)
6. [Writing a criteria file](#6-writing-a-criteria-file)
7. [Clearing a backlog with batch mode](#7-clearing-a-backlog-with-batch-mode)
8. [Costs](#8-costs)
9. [Troubleshooting](#9-troubleshooting)
10. [Where your data lives](#10-where-your-data-lives)

---

## 1. Overview

PaperAlert reads the journal alert emails you receive in Gmail (tables of contents, OnlineFirst alerts, Google Scholar alerts, and so on) and turns each listed article into an entry you can sort, filter, and send to Zotero.

1. It finds **unread** emails with the Gmail label `논문_알리미` (you can rename the label; see [Troubleshooting](#9-troubleshooting)).
2. Claude extracts every article listed in each email. **Only book reviews are skipped.**
3. It looks up each article's **DOI and abstract** in Crossref and OpenAlex.
4. Articles already in your PaperAlert library (same DOI or same title) are skipped, so a paper announced first as OnlineFirst and later in an issue's table of contents is saved only once.
5. Claude scores each new article from **1 to 5** against your research interests and writes a summary, the data, the method, and the key findings.
6. Processed emails are marked as read in Gmail.

### Starting the app

Click the owl icon: the `PaperAlert` shortcut in the app folder, the Start menu entry, or the taskbar icon. If the app is already open, its window comes to the front instead of a second copy starting. Closing the window quits the app. The owl icon in the system tray (next to the clock) also offers **Open PaperAlert** and **Quit**.

### Screen layout

- **Top bar**: batch progress, time of the last fetch, **⚙ Settings**, **ⓘ About**, and the **Fetch** button.
- **Summary cards**: total papers (All papers), papers scored 4 or 5 (High interest), and papers you have not read yet (Unread papers). Click the Unread papers card to show only unread papers.
- **Papers by category**: paper counts per category. Click a category to show only its papers.
- **Filter bar** and the list of **paper cards**.

---

## 2. Collecting papers: Fetch

Click **Fetch** to process waiting emails. How many emails, in what order, and in which mode are set in Settings ([Section 5](#5-settings)).

- While it runs, a progress bar and a red **⏹ Stop** button appear. Stop finishes the email currently being processed and then stops. Emails already processed stay processed; the rest are handled next time.
- When it finishes, a summary message and a green **✓ Done** button appear. Click Done to close the message.
- Example message: `Done. 10 emails processed, 22 papers saved (6 already in the library were skipped). 461 emails are still waiting.`
- An email that fails is **not** recorded as processed, so it is retried on the next fetch. Errors are listed on screen.

The first time you click Fetch, or when Gmail access has expired, a Google sign-in page opens in your browser. Choose your account and allow access.

---

## 3. Browsing papers

### Filters and sorting

| Control | What it does |
|---|---|
| Score | All / 3+ / 4+ / 5 only |
| Status | All / Unread / Read |
| Journal, Year, Category | Filter by journal, publication year, or category |
| Sort | By score, fetch date, publication year, or journal name |
| Search | Search titles and authors |

### Paper cards

- **Score badge** (the number at the top right): click it to change the score. The levels are 1 Skip, 2 Low, 3 Moderate, 4 High, 5 Must read.
- **Title**: opens the article page.
- **Category tags**: click **✏ Edit** to change them.
- The **summary** is shown on the card; click **🔍 Key findings** or **💬 Data & method** to expand those. When no abstract could be found, these fields say "No abstract" (or "초록 없음" for Korean summaries) instead of guessing.
- **Open paper** opens the article page. If there is no link, **🔍 Scholar** searches Google Scholar instead.
- **➜ Zotero** sends the paper to Zotero ([Section 4](#4-sending-papers-to-zotero)).
- **○ Unread / ✓ Read** toggles the read status.

### Managing categories

Use **⚙ Manage categories** to add or delete categories. Deleting a category also removes it from the papers that have it. The categories Claude assigns to new papers come from the **Categories** section of your research profile (`research_profile.md`); categories listed there are added to the app automatically. To change them for future papers, edit the profile.

---

## 4. Sending papers to Zotero

Click **➜ Zotero** on a card to create an item in your Zotero library.

- If the paper has a DOI, the item is filled from Crossref's bibliographic record: authors (first and last names), journal, volume, issue, pages, year, ISSN, URL, and abstract.
- The tags `PaperAlert` and `score:N` are added.
- A **PaperAlert note** is attached: score, categories, summary, data, method, key findings, and the subject of the alert email.
- The button then reads **✓ In Zotero**. Click it to select the item in the Zotero desktop app.

### Papers already in Zotero

PaperAlert keeps a list of the DOIs and titles in your Zotero library and checks it before sending. If the paper is already there, **no new item is created** and the button reads **✓ Already in Zotero**. What happens to the existing item is set by **If already in Zotero** in Settings. Existing items are never moved to other collections.

### Choosing the collection

Set **Where to send** in Settings ([Section 5](#where-to-send)).

### Automatic sending

Turn on **Auto-send to Zotero** in Settings to send newly fetched papers at or above a chosen score automatically.

---

## 5. Settings

Click **⚙ Settings** in the top bar. Changes are saved immediately ("Saved." appears at the bottom).

### Fetching

| Setting | Options | Description |
|---|---|---|
| Research profile | A file path | Your research interests, scoring rubric, and categories (default `research_profile.md` in the app folder). Settings shows the categories found in the file, or what is wrong with it. See [Changing your research interests](#changing-your-research-interests). |
| Summary language | Korean / English | Language of the summary, data, and key findings. Applies to papers fetched afterwards. Default: Korean |
| Start date | A date | Only emails received on or after this date are processed. Older emails stay unread in Gmail; click **Clear** to include them again. Useful for setting aside a backlog and starting fresh. |
| Emails per fetch | 10, 25, 50, 100, 200, 500, All | How many emails one click of Fetch processes. Default: 50 |
| Fetch order | Newest first / Oldest first | Which waiting emails to process first |
| Fetch mode | Instant / Batch | Instant processes right away; Batch costs half as much but results arrive later ([Section 7](#7-clearing-a-backlog-with-batch-mode)). |

The bottom of the Settings window shows how many emails are waiting. With a start date set, it shows both the number since that date and the total.

### Zotero

| Setting | Options | Description |
|---|---|---|
| Zotero | On / Off | Off hides all Zotero buttons. |
| Auto-send to Zotero | Off / Score 5 / Score 4 or higher / Score 3 or higher | During Fetch, send new papers at or above this score automatically. Default: Off |
| If already in Zotero | Skip / Fill in missing details | Skip leaves the existing item alone. Fill in adds **only details that are empty** in Zotero (DOI, abstract, volume, issue, pages, date, ISSN, URL, and authors if there are none). Filled fields, tags, notes, attachments, and collections are never changed. |
| Where to send | See below | The collection a new item goes into |
| Zotero library index | Sync now | Status of the list used to detect papers already in Zotero |

<a id="where-to-send"></a>
#### Where to send

| Option | Description |
|---|---|
| Library root | No collection; the item goes to the library root. Default |
| One collection | Every paper goes into the collection chosen under **Collection**. Collections are listed with their full path, such as "02_Research / Education / Korea". |
| By category | In the **Collection for each category** table, choose a collection for each PaperAlert category. A paper with several categories goes into each matching collection. No extra cost. |
| By criteria file (Claude) | Claude reads your criteria file ([Section 6](#6-writing-a-criteria-file)) and picks every collection whose criteria fit. About one cent per paper. |

With By category and By criteria file, also set **If nothing fits**: the collection for papers that match no category or criterion. Leave it empty to use the library root. If you keep an inbox collection for papers to sort by hand later, choose it here.

#### Zotero library index

- It is built automatically the first time you send a paper, or click **Sync now** to build it in advance. The first build takes one to three minutes depending on library size (about two minutes for 10,000 items). After that, only changes are downloaded, which takes a few seconds.
- Before sending a paper, the index is refreshed if it is more than five minutes old.
- Papers sent while the index is first being built are sent without the duplicate check.

---

## 6. Writing a criteria file

The **By criteria file** option uses this file. The default is `zotero_분류기준.md` in the app folder; you can point **Criteria file** in Settings to another file (a path relative to the app folder, or a full path). A ready-to-edit example is in [examples/zotero_criteria.example.md](examples/zotero_criteria.example.md).

PaperAlert reads the file every time it sends a paper, so changes apply as soon as you save. No restart is needed.

### Format

One collection per line, written exactly as it is named in Zotero. Indent subcollections by two spaces under their parent. After the name, write a colon and the criterion: which papers belong there.

```
- 02_Research
  - Shadow education: studies whose main topic is private tutoring, shadow education, or cram schools
  - Low fertility: studies whose main motivation is to explain low fertility
    - Gender equality and fertility: studies of the relationship between gender equality and fertility
  - Statistical software
```

- **A line with a criterion** is a target: Claude puts papers there when the criterion fits.
- **A line without a criterion** (just the name) is not a target. Use this for parent folders that only organize subcollections (like `02_Research` above) and for folders you do not want filled automatically (project, seminar, or software folders). You can also leave such folders out of the file entirely; writing parent folders helps PaperAlert find subcollections by their full path.
- **Collection keys are not needed.** PaperAlert finds each collection in Zotero by its path (the line's name and the names of its parent lines). If several collections share the same name and the path does not tell them apart, or the name itself contains a colon, add the collection key in square brackets after the name, for example `- Korea [H3V6BLZE]: Korean studies of educational inequality`. You can find a collection's key in the address bar when you open it in the Zotero web library.

After saving, open **Settings** and look at the check under **Criteria file**. It shows how many collections have criteria, collections found by name, lines that could not be matched to a Zotero collection (in red), and Zotero collections not yet in the file.

### Tips for writing criteria

- Be specific, for example "studies in which X is the dependent (or independent) variable" or "studies whose main topic or keyword is X".
- A paper can go into several collections. Claude prefers the most specific subcollection and adds a parent only when the paper also fits the parent's own criterion.
- When you create a new collection in Zotero, add a line for it under its parent in this file.

---

## 7. Clearing a backlog with batch mode

When many emails have piled up, switch **Fetch mode** to **Batch** to halve the cost.

1. In Settings, set **Fetch mode → Batch** and **Emails per fetch → All** (or any number).
2. Click **Fetch**. PaperAlert loads the emails, submits them as a batch, and finishes right away.
3. The top bar shows progress, for example `⏳ Batch: 120 emails in progress (step 1: 120, step 2: 0)`.
   - Step 1: extracting the list of articles
   - Step 2: scoring (only emails with new articles)
4. While the app is open it checks for results every minute. Click the progress text to check immediately.
5. When everything is done, the progress text disappears and the paper list refreshes.

- Each step usually finishes within a few minutes to an hour, but can take up to 24 hours. A test with four emails took 13 minutes for both steps.
- **You can close the app.** When you reopen it, it picks up where it left off.
- Emails that fail or expire are not recorded as processed, so they are retried on the next fetch.
- We recommend keeping Instant for everyday use and switching to Batch only for large backlogs.

---

## 8. Costs

Claude API usage is paid from credits in the Anthropic Console. These are rough figures measured in October 2026 with the model `claude-sonnet-5-5`.

| Task | Cost |
|---|---|
| Processing one email (Instant) | About $0.04 (depends on how many articles it lists) |
| Processing one email (Batch) | About $0.02 |
| An email listing only papers already in your library | Only the extraction step is charged (scoring is skipped) |
| Sending to Zotero | Free (about one cent per paper with By criteria file) |
| DOI and abstract lookup (Crossref, OpenAlex) | Free |

**Buy credits in the Anthropic Console (platform.claude.com) under Settings → Billing.** Extra usage on a claude.ai subscription is a separate balance and cannot be used by PaperAlert. Make sure you add credits to the organization that owns the API key in your `.env` file (check the API keys page). Turning off auto-reload prevents unexpected charges.

---

## 9. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `credit balance is too low` after Fetch | Your API credits ran out. Add credits as described in [Section 8](#8-costs). Unprocessed emails are retried on the next fetch. |
| A Google sign-in page opens | Gmail access has expired; allow access again. If your Google Cloud OAuth consent screen is in "Testing", access expires every seven days; publishing it to "In production" avoids this. |
| `Gmail label '논문_알리미' was not found` | The label does not exist in Gmail. Create it and set up a filter that applies it to your alert emails. To use another label name, change `GMAIL_LABEL` in `gmail_client.py`. |
| `No new emails to fetch` but emails are waiting | They are older than the Start date in Settings, or already read. Clear the Start date, or mark the emails as unread in Gmail. |
| Clicking the shortcut does nothing | Run `.venv\Scripts\python.exe create_shortcut.py` on this computer to recreate the shortcuts. Shortcuts contain a computer-specific Python path, so on another computer that shares the folder (e.g., through Dropbox) you need to recreate them. |
| A black terminal window opens with the app | You are using an old shortcut. Recreate it as above. |
| The taskbar shows the old icon | Windows icon cache. Sign out of Windows and sign in again. |
| No Zotero buttons | Zotero is set to Off in Settings. |
| `ZOTERO_API_KEY and ZOTERO_USER_ID must be set` | Add your Zotero API key and user ID to `.env` (see the README). The key needs write access. |
| Clicking ✓ In Zotero does not open Zotero | The Zotero desktop app must be installed. |
| Batch progress stays for a long time | Batches can take up to 24 hours. Click the progress text to check now; hover over it to see the last check time and message. |
| "File not found" in the criteria file check | Check the Criteria file path in Settings and click **Save**. |
| "Not found in Zotero" in the criteria file check | The name or path on that line does not match Zotero. Check the spelling and the parent lines, or add the collection key in square brackets ([Section 6](#6-writing-a-criteria-file)). |

---

## 10. Where your data lives

Everything is in the app folder. These files are listed in `.gitignore` and are never committed to Git.

| File | Contents |
|---|---|
| `papers.db` | Papers, processing records, settings, the Zotero index, batch progress |
| `.env` | Anthropic and Zotero API keys |
| `credentials.json`, `token.json` | Gmail authorization |
| `research_profile.md` | Your research profile |
| `zotero_분류기준.md` | Criteria file (default name) |
| `_backup/` | Database backups |

To back up `papers.db`, quit the app and copy the file. If the app folder is in a synced folder (such as Dropbox) used by several computers, **do not run the app on two computers at the same time**; the database could end up with conflicting copies.

### Changing your research interests

Scores come from your research profile, `research_profile.md` (or the file set in **Settings → Research profile**). Start from `research_profile.template.md`; a complete example is in `examples/research_profile.example.md`. Describe your core topics, preferred methods, regions, journals, courses, negative filters, and scoring rubric in plain language. Only the **Categories** section has a fixed format: one line per category, the name in backticks, then a colon and a short description. Changes apply to papers fetched after you save the file; no restart is needed.
