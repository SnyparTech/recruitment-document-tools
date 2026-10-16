# Profile Bot AI — User Manual

**Version 2.0 · For recruiters**

---

## 1. What is Profile Bot AI?

Profile Bot AI saves you time on three everyday tasks:

- **Find candidates:** chat about who you're looking for in plain words. The assistant fills in the Naukri Resdex search for you, runs it across every result page, and shows the candidates it found, best matches first.
- **Convert a resume:** turn a messy resume (even a scanned photo) into a clean, structured document.
- **Build a candidate dossier:** combine a candidate's photo, ID proof and resume into one neat Word document.

## 2. Before You Start

You will need:
- Google Chrome
- A Naukri Resdex recruiter account, already logged in
- The Profile Bot website open in one tab and Resdex open in another
- The Profile Bot helper (browser extension) installed in Chrome
- **Your device registered with your `@snypartech.com` email** (first-time setup, one time only — see §3)

## 3. First-Time Setup: Register Your Device

Only devices registered with a verified company email can use the extension. This is a one-time step per computer.

1. Click the Profile Bot extension icon in Chrome.
2. If the dot shows **"Device Not Authorized"**, enter your `@snypartech.com` email and click **Send code**.
3. Check your inbox — a 6-digit code arrives within a minute.
4. Enter the code and click **Activate this device**.
5. Done. This device stays registered — you won't be asked again.

**Note:** each email can only register one device at a time. If you switch laptops, ask your administrator to clear your old device first.

## 4. Finding Candidates

### Step 1 — Start a chat
Open the **Candidates** tab. You'll see a **Chats** panel on the left — click **+ New Chat** to start fresh, or click an existing chat to pick up where you left off. Old chats are never lost unless you delete them.

### Step 2 — Describe the role
Type or paste your requirement the way you'd tell a colleague:

> Find AI/ML engineers in Hyderabad with 2 to 5 years of experience. Python, FastAPI, Machine Learning and NLP are mandatory. Salary should be 8 to 15 LPA. Prefer candidates who can join within 15 days, otherwise currently serving notice period. Active in the last 7 days.

**Tips for good results**
- Mention skills, years of experience, city, salary range and notice period.
- Say which skills are *mandatory* and which are *nice to have*.
- Only include what you truly want — anything left out stays open in Resdex.

**Or upload a job description:** drag a PDF/Word/text file onto the prompt box, or use the upload button. Files up to 10 MB are accepted; scanned picture-only documents can't be read here (use the Resume Converter for those, which has OCR).

### Step 3 — Keep refining with chat
After the first message, just tell the assistant what to change — "remove SQL", "make React optional", "experience 3 to 6 years", "add Pune". It edits the existing plan instead of starting over.

**Choosing a specific AI model (optional):** a dropdown next to the message box lets you pin your message to one specific AI model instead of the automatic default. Useful for comparing how different models handle the same JD — the model that actually answered is shown in small grey text under each reply.

### Step 4 — Review the draft
As you chat, a **Draft keywords** section shows every keyword as a pill. Click a pill to star it (★ = mandatory on Resdex, ☆ = optional). This only affects your local draft — nothing happens in Resdex until you apply it.

### Step 5 — Apply to Resdex
Choose how far it should go, then click the apply button:

| Choice | What happens |
|---|---|
| **Inspection** | Fills in the Resdex form so you can look at it. Does not press Search. |
| **Submit** | Fills in the form, presses Search, and brings the candidates back here. |

New to the tool? Start with **Inspection**, check the form looks right, then switch to **Submit** next time.

### Step 6 — Let it fill Resdex
Switch to your Resdex tab. A small status badge shows progress as fields fill in one by one. You can:
- **Pause** and **Resume** from the badge if you want to step in.
- Use the helper's popup for **Force Re-fill** to start over (normally there's a ~90 second cooldown between fills).

Please leave the mouse and keyboard alone while it works. If you starred/unstarred a keyword after a search already ran, the helper automatically re-applies just that change and re-searches — no need to redo everything.

### Step 7 — Review candidates
Back on the Profile Bot website, candidates appear in **Candidates Found on Resdex**. The helper walks through every result page by itself (up to 200 pages) and collects everyone it finds. Each card shows:
- Name, current role, company and location
- Experience, education and notice period
- Skills (including the full AI-generated summary Resdex shows on hover)
- A **match score** (higher is better) and a **data completeness** figure
- A **View profile** link

The list is sorted best match first.

### Step 8 — Not enough good candidates?
Click **"Not satisfied? Broaden search"** next to the candidate count. This automatically loosens your search one notch — demotes one required keyword to optional, and widens the "active in" window up to 30 days — then re-runs it on Resdex. No need to manually guess what to loosen.

### A note on "active in" learning
If you find yourself widening the "active in" window to the same value (say, 30 days) across several searches, the assistant notices and asks: *"You've widened this 3 times — should I just default to that from now on?"* You decide yes or no — it never changes your default without asking first.

## 5. What Gets Filled in Resdex
| Area | Filled from your description |
|---|---|
| Skills / keywords | Yes, including which are mandatory |
| Experience (from – to) | Yes |
| Current location | Yes |
| Salary range | Yes |
| Notice period | Yes, multiple options. **"Currently serving notice period" is always included.** |
| Education | Yes |
| Verified phone / email / attached resume | Yes, if you ask for them |
| Last active | Yes, if you mention it (otherwise defaults to 15 days, or your confirmed preference) |
| Job title, department, industry, company | Not filled — Resdex suggests these itself from your skills, so filling them would over-narrow results |

## 6. Converting a Resume
1. Open the **Resume Converter** tab.
2. Upload a resume file — PDF, Word, or even a photo/scan of a printed resume (handled automatically with OCR).
3. The assistant extracts the text, structures it with AI, and generates a clean version.
4. Preview the formatted result, the raw LaTeX, or an audit of what was captured.
5. Download as LaTeX or DOCX.

## 7. Building a Candidate Dossier
1. Open the **Dossier** tab.
2. Upload the candidate's **photo**, **ID proof** and **resume**.
3. Click to compile.
4. Download the Word document — it contains the candidate's name and contact line, the photo, the ID proof, and the full resume, each on its own page.

## 8. Good to Know
- Your search details, chat history, and candidate list are kept per-session. Old chats stay in the sidebar until you delete them.
- If a candidate detail is blank, Resdex simply didn't show it on that card.
- Always double-check the filled form before relying on results — take a quick look at the filters Resdex shows as applied.
- JD broadcasting to WhatsApp is handled on the admin/backend side, not from this web app — ask your administrator if you need a JD sent out.

## 9. Troubleshooting
| What you see | What to try |
|---|---|
| "Device Not Authorized" in the popup | Register your device with your work email — see §3 |
| Nothing happens in Resdex | Make sure Resdex is open, you're logged in, and the page is freshly loaded. Then click **Force Re-fill**. |
| Clicking a keyword pill doesn't seem to stick | Reload the page and try again; report it if it keeps happening |
| Some fields are empty | Pause, fill those fields by hand, then Resume. Tell your administrator which ones. |
| "Search not submitted" message | The tool couldn't confirm every field, so it stopped on purpose. Check the form and press Search yourself if it looks right. |
| Candidate list stays empty | Wait a few seconds, confirm the search ran in Resdex, and that you chose **Submit** mode. |
| Document upload rejected | Use PDF, Word, text, or an image; keep it under 10 MB. |
| A chat message says "rule-based (no LLM)" | All AI providers were temporarily unavailable — results still work but may be less refined; try again shortly |

## 10. Getting Help
Contact your administrator with:
- What you typed or uploaded
- What you expected
- What happened instead, and a screenshot if possible

---
*Profile Bot AI · Version 2.0*
