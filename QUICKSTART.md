# PaperAlert Quick Start

**English** | [한국어](QUICKSTART.ko.md)

This guide takes you from nothing to your first fetched papers, step by step. Allow **about 45 minutes**. Most of the time goes into the Google Cloud setup (Step 4), which you only do once.

If you get stuck, check [When something goes wrong](#when-something-goes-wrong) at the end, then [open an issue](https://github.com/skytary/paper_alert/issues/new/choose).

## What you need

- A Windows 10 or 11 computer
- A Gmail account that receives journal alert emails
- A credit card to buy Anthropic API credits (US$5 is enough to start; processing one email costs about $0.04)
- Optional: a Zotero account, if you want to send papers to Zotero

## Step 1. Install Python

1. Download Python 3.12 or later from https://www.python.org/downloads/windows/ ("Windows installer (64-bit)").
2. Run the installer. On the first screen, **check "Add python.exe to PATH"**, then click "Install Now".
3. Open PowerShell (Start menu → type "PowerShell") and check:
   ```powershell
   python --version
   ```
   You should see `Python 3.12.x` or later.

## Step 2. Download PaperAlert

Choose one:

- **Without Git**: open https://github.com/skytary/paper_alert, click the green **Code** button → **Download ZIP**, and extract it.
- **With Git**: `git clone https://github.com/skytary/paper_alert.git`

**Put the folder somewhere with a short path**, for example `C:\Users\<you>\Documents\paper_alert`. Windows limits file paths to 260 characters, and a deeply nested folder can make the installation in Step 3 fail. If you use Dropbox or OneDrive, see [Where your data lives](MANUAL.md#10-where-your-data-lives) before putting the folder there.

## Step 3. Install the packages

In PowerShell, go to the folder and run:

```powershell
cd C:\Users\<you>\Documents\paper_alert
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

This takes a few minutes. It is done when you get the prompt back without red error text.

## Step 4. Let PaperAlert read your Gmail (Google Cloud)

Google requires every app that reads Gmail to be registered. You will register your own private copy of PaperAlert in a free Google Cloud project. Use the **same Google account** as the Gmail you want to read.

### 4.1 Create a project

1. Go to https://console.cloud.google.com and sign in. Accept the terms if asked.
2. Click the project selector at the top of the page → **New project**.
3. Name it `PaperAlert` and click **Create**. Make sure the new project is selected at the top.

### 4.2 Turn on the Gmail API

1. Open https://console.cloud.google.com/apis/library/gmail.googleapis.com (or search for "Gmail API" in the top search bar).
2. Click **Enable**.

### 4.3 Set up the consent screen

1. Open the menu (☰) → **Google Auth platform** → **Branding**. Click **Get started** if you see it.
2. **App information**: App name `PaperAlert`, User support email: your Gmail address. Click **Next**.
3. **Audience**: choose **External** (with a personal Gmail account, Internal is not available). Click **Next**.
4. **Contact information**: your Gmail address. Click **Next**.
5. Agree to the Google API Services User Data Policy, then click **Continue** and **Create**.

### 4.4 Add yourself as a test user

1. In **Google Auth platform**, open **Audience**.
2. Under **Test users**, click **Add users**, enter your own Gmail address, and save.

If you skip this step, Google will block the sign-in later with "Access blocked" or `access_denied`.

### 4.5 Create the credentials file

1. In **Google Auth platform**, open **Clients** → **Create client**.
2. Application type: **Desktop app**. Name: `PaperAlert desktop`. Click **Create**.
3. Click **Download JSON** in the dialog (or the download icon next to the new client).
4. Rename the downloaded file to `credentials.json` and move it into the PaperAlert folder.

> Windows may hide file extensions. If you see `credentials.json` but it still does not work, turn on "File name extensions" in File Explorer's **View** menu and make sure the file is not named `credentials.json.json`.

### 4.6 (Optional) Stop the weekly sign-in

While your app is in "Testing" status, Google signs you out of PaperAlert every 7 days, and the sign-in page opens again on the next fetch. To avoid this, go to **Google Auth platform** → **Audience** → **Publish app**. Because your app is not verified by Google, the sign-in page will show "Google hasn't verified this app"; click **Advanced** → **Go to PaperAlert (unsafe)**. This is safe because the app is your own: it runs on your computer and only you use it.

## Step 5. Label your alert emails in Gmail

PaperAlert only reads unread emails with the label `논문_알리미` ("paper alerts" in Korean).

1. In Gmail, create the label: left sidebar → **Labels** → **+** → `논문_알리미`.
2. Create a filter that applies it automatically: click the search options icon in the Gmail search bar, fill in **From** with the alert senders, for example
   `scholaralerts-noreply@google.com OR alerts@sagepub.com OR onlinelibrary@wiley.com`,
   click **Create filter**, check **Apply the label: 논문_알리미**, and also check **Also apply filter to matching conversations** to label emails you already have.
3. Subscribe to the journals you follow (table-of-contents or OnlineFirst alerts on the journal website) and to Google Scholar alerts. Check who sends them and add those addresses to your filter.

To use a different label name, change `GMAIL_LABEL` in `gmail_client.py`.

## Step 6. Get an Anthropic API key

1. Go to https://platform.claude.com and sign up or sign in.
2. **Settings → Billing → Buy credits**: add US$5. We recommend leaving auto-reload off.
   > This is **not** the same as a claude.ai subscription. Credits or "extra usage" on claude.ai cannot be used by PaperAlert.
3. **API keys → Create key**. Copy the key (it starts with `sk-ant-`). It is shown only once.

## Step 7. (Optional) Get a Zotero API key

1. Go to https://www.zotero.org/settings/keys.
2. Note the number after **Your user ID for use in API calls**.
3. Click **Create new private key**. Check **Allow library access** and **Allow write access**, then save. Copy the key.

## Step 8. Put your keys in `.env`

In the PaperAlert folder:

```powershell
copy .env.example .env
notepad .env
```

Fill in `ANTHROPIC_API_KEY`, and if you use Zotero, `ZOTERO_API_KEY` and `ZOTERO_USER_ID`. Save and close. **Never share this file.**

## Step 9. Write your research profile

PaperAlert scores papers against a profile of your research interests.

```powershell
copy research_profile.template.md research_profile.md
notepad research_profile.md
```

Replace every `[bracketed placeholder]` with your own interests, methods, filters, and categories. The more specific, the better the scores. For a complete example, see [examples/research_profile.example.md](examples/research_profile.example.md). You can edit the file any time; changes apply to papers fetched afterwards.

## Step 10. Start PaperAlert

1. Create the shortcuts:
   ```powershell
   .venv\Scripts\python.exe create_shortcut.py
   ```
2. Double-click **PaperAlert** in the folder (or find it in the Start menu). The app window opens.
3. Before your first fetch, click **⚙ Settings** and set **Emails per fetch** to **10**, and **Start date** to a recent date. This keeps your first test small and cheap.
4. Click **Fetch**. A Google sign-in page opens in your browser: choose your account, click through "Google hasn't verified this app" (**Continue**, or **Advanced → Go to PaperAlert**), and allow access.
5. When the fetch finishes, your papers appear. 🎉

Next, read the [User Manual](MANUAL.md) for filters, Zotero, batch mode, and all settings.

## When something goes wrong

| What you see | What to do |
|---|---|
| `python` is not recognized | Python is not on PATH. Reinstall Python with "Add python.exe to PATH" checked, or use `py` instead of `python` in Step 3. |
| Errors mentioning a missing module or file during Step 3 | Your folder path may be too long. Move the folder to a shorter path (Step 2), delete the `.venv` folder, and run Step 3 again. |
| Sign-in page says **Access blocked** or `access_denied` | Add your Gmail address as a test user (Step 4.4). Make sure you sign in with that same account. |
| `redirect_uri_mismatch` | The client is not a Desktop app. Create a new client with type **Desktop app** (Step 4.5) and replace `credentials.json`. |
| `credentials.json` not found | The file is missing from the PaperAlert folder or has the wrong name (Step 4.5). |
| `invalid_grant` | Your sign-in expired. Delete `token.json` from the folder and fetch again. |
| `Gmail label '논문_알리미' was not found` | Create the label in Gmail (Step 5). |
| `No new emails to fetch` | No unread emails with the label after the Start date. Check that your filter applies the label and that the emails are unread. |
| `credit balance is too low` | Buy credits at https://platform.claude.com (Step 6). Check that the key in `.env` belongs to the organization you added credits to. |
| `authentication_error` or `invalid x-api-key` | The Anthropic key in `.env` is wrong or has spaces. Copy it again (Step 6, 8). |
| `Research profile not found` or `still contains [placeholders]` | Create and fill in `research_profile.md` (Step 9). |
| The app window is blank or does not open (Windows 10) | Install the Microsoft Edge WebView2 Runtime from https://developer.microsoft.com/microsoft-edge/webview2/ and try again. |
| A black terminal window opens with the app | Run `create_shortcut.py` again (Step 10) and use the new shortcut. |

Still stuck? [Open an issue](https://github.com/skytary/paper_alert/issues/new/choose) and choose **Setup help**. Include the exact message you see (a screenshot is fine) and, if it exists, the contents of `launch_error.log` in the PaperAlert folder. **Never post the contents of `.env`, `credentials.json`, or `token.json`.**
