# Profile Bot AI — User Manual

**Version 1.0 · For recruiters**

---

## 1. What is Profile Bot AI?
Profile Bot AI saves you time on two everyday tasks:

- **Find candidates:** describe who you are looking for in plain words. The assistant fills in the Naukri Resdex search for you, runs it, and shows the candidates it found, best matches first.
- **Build a candidate dossier:** combine a candidate's photo, ID proof and resume into one neat Word document.

## 2. Before You Start
You will need:
- Google Chrome
- A Naukri Resdex recruiter account, already logged in
- The Profile Bot website open in one tab and Resdex open in another
- The Profile Bot helper installed in Chrome (your administrator will set this up)

## 3. Finding Candidates

### Step 1 — Describe the role
Open the **Candidates** tab and type or paste your requirement. Write it the way you would tell a colleague:

> Find AI/ML engineers in Hyderabad with 2 to 5 years of experience. Python, FastAPI, Machine Learning and NLP are mandatory. Salary should be 8 to 15 LPA. Prefer candidates who can join within 15 days, otherwise currently serving notice period. Active in the last 7 days.

**Tips for good results**
- Mention skills, years of experience, city, salary range and notice period.
- Say which skills are *mandatory* and which are *nice to have*.
- Only include what you truly want. Anything you leave out is left open in Resdex.

### Step 1b — Or upload a job description
Have a JD as a PDF, Word or text file? Drag it onto the prompt box or use the upload button. The text is read and placed in the box so you can check and edit it before searching. Files up to 10 MB are accepted. Scanned pictures of documents cannot be read.

### Step 2 — Choose how far it should go
| Choice | What happens |
|---|---|
| **Dry-Run** | Shows what it understood. Nothing is done in Resdex. Good for checking. |
| **Visual Form Fill** | Fills in the Resdex form so you can look at it. It does not press Search. |
| **Live Submit Search** | Fills in the form, presses Search, and brings the candidates back here. |

New to the tool? Start with **Dry-Run**, then **Visual Form Fill**, then **Live Submit Search**.

### Step 3 — Run it
Click the run button. You will see a summary of what was understood (skills, experience, location, salary, notice period and so on). If something cannot be used, you will see a clear message instead of a silent failure.

### Step 4 — Let it fill Resdex
Switch to your Resdex tab. A small status badge shows progress as fields are filled one by one. You can:
- **Pause** and **Resume** from the badge if you want to step in.
- Use the helper's toolbar button for **Auto-Fill**, or **Force Re-fill** to start over (normally the tool waits about 90 seconds between fills).

Please leave the mouse and keyboard alone while it works.

### Step 5 — Review candidates
Back on the Profile Bot website, candidates appear in the **Candidates Found on Resdex** list. Each card shows:
- Name, current role, company and location
- Experience, education and notice period
- Skills
- A **match score** (higher is better) and a **data completeness** figure
- Green ticks for requirements met, red crosses for requirements missed, and question marks where Resdex did not show that information
- A **View profile** link

The list is sorted from best to weakest match.

## 4. What Gets Filled in Resdex
| Area | Filled from your description |
|---|---|
| Skills / keywords | Yes, including mandatory ones |
| Experience (from – to) | Yes |
| Current location | Yes |
| Salary range | Yes |
| Notice period | Yes. You can pick several options. **"Currently serving notice period" is always included.** |
| Education | Yes |
| Verified phone / email / attached resume | Yes, if you ask for them |
| Last active | Yes, if you mention it |
| Job title, department, industry and company | Not filled — Resdex suggests these itself from your skills |

## 5. Building a Candidate Dossier
1. Open the **Dossier** tab.
2. Upload the candidate's **photo**, **ID proof** and **resume**.
3. Click to compile.
4. Download the Word document. It contains the candidate's name and contact line, the photo, the ID proof, and the full resume, each on its own page.

## 6. Good to Know
- After a live search, the helper moves through the result pages by itself (up to 10 pages) and collects every candidate it finds.
- If a candidate detail is blank, Resdex may not have shown it on the card.
- Your search details and candidate list are kept only for your current session. They are cleared when the system restarts, and you can clear the list yourself.
- Always double-check the filled form before relying on the results. Take a quick look at the filters Resdex shows as applied.

## 7. Troubleshooting
| What you see | What to try |
|---|---|
| Nothing happens in Resdex | Make sure Resdex is open, you are logged in, and the page is freshly loaded. Then click **Force Re-fill**. |
| Some fields are empty | Pause, fill those fields by hand, then Resume. Tell your administrator which ones. |
| "Search not submitted" message | The tool could not confirm every field, so it stopped on purpose. Check the form and press Search yourself if it looks right. |
| Candidate list stays empty | Wait a few seconds, confirm the search ran in Resdex, and that you chose **Live Submit Search**. |
| Details missing on candidate cards | Report it to your administrator; a small adjustment may be needed. |
| Document upload rejected | Use PDF, Word or text; keep it under 10 MB; avoid scanned images. |

## 8. Getting Help
Contact your administrator with:
- What you typed or uploaded
- What you expected
- What happened instead, and a screenshot if possible

---
*Profile Bot AI · Version 1.0*
