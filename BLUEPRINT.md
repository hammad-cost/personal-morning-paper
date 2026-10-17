# The Personal Morning Paper: Golden Blueprint

Oct 17, 2026

## Product summary

The Personal Morning Paper turns scattered news into one calm, finite daily newspaper per reader, made fresh every day, read on the web or downloaded as a PDF, and getting better with every click and skip. It stands out through two CopilotKit experiences: a conversational onboarding interviewer that builds the reader's profile live on screen, and an AI Editor Desk that edits the paper by chat.

**One-line pitch:** Instagram gave social media one feed. We give news one finite paper that knows you, and you finish it able to name three things you learned.

| # | Hackathon requirement | How we meet it |
| --- | --- | --- |
| 1 | Onboarding that captures interests with great UX | CopilotKit interviewer: the reader chats, and topic pills, weights and the masthead fill in live beside the chat. A 30-second manual form is the fallback |
| 2 | Daily PDF, newspaper layout, as personalized as possible | ReportLab broadsheet: masthead, edition number, 3 Takeaways box, 3 columns, linked headlines. Lead story and section order follow the reader's weights; skipped stories are left out |
| 3 | Full web reading experience, same edition as PDF, previous papers | Broadsheet webpage with Read Original, Skip with undo, "Why this story?", and a Past Editions drawer where every edition reopens and downloads |
| 4 | Learns over time and improves future papers | Clicks, skips, recall answers and Copilot requests change topic weights; weights decide what appears and where. The Brain panel shows the change, and "Print next edition" proves it |
| 5 | Room to explore | 3 Things You Learned box, "Can you name 3 things?" recall check, Connect the Dots, Mind Vitamin, AI Editor Desk |
| Rule | Repo from the start, commits monitored | Repo created and pushed in Step 0; one or more commits per step |
| Submit | Public repo, Loom of 5 min or less, architecture diagram | Step 11 |

**Fixes over the first blueprint.**

- A new edition is generated automatically the first time the app is opened each day
- Layout is personalized, not only content: the top-scoring story leads and sections follow weight order
- A defined ranking formula connects learning to the next paper
- "Print next edition" makes the archive and learning demo possible on day one
- The AI only summarizes fetched article text; every takeaway links to its source
- CopilotKit moves to the very start (onboarding) as the headline feature

## User experience

The app has two states: a first visit that ends in Edition No. 1, and every later visit, which opens straight to today's paper.

**Visit 1: onboarding (about 60 seconds)**

1. A full-page welcome in newspaper style: "Every great paper starts with its reader." Two choices: **Talk to the Editor** (CopilotKit) or **Quick setup** (form).
2. Talk to the Editor: a split screen. The chat is on the left; a live **Reader Profile card** is on the right showing masthead name, topic pills with weights, and a short bio.
3. The Editor asks at most 4 short questions: name, what you do, what you can't stop reading about, what you never want to see. Each answer fills the profile card instantly through Copilot actions.
4. The reader can edit pills directly on the card (add, remove, change weight). The chat sees those edits.
5. "Print my first edition" opens the **Printing Press** loading screen with real steps: Gathering articles → Choosing your stories → Writing your summaries → Setting the type.
6. Edition No. 1 appears.

**Visit 2 and later: daily reading**

1. The app opens. If today's edition exists, it loads instantly; if not, the Printing Press runs once and creates it.
2. Masthead: paper name, volume, edition number, date, reading time ("Today's paper: 8 min"), Download PDF, Past Editions, Brain, Editor Desk.
3. **3 Things You Learned Today** box at the top, each item linked to its source story.
4. Broadsheet: the lead story across 2 columns, then sections ordered by the reader's weights.
5. Each card: section tag, source, headline, 2–3 sentence summary, "Why it matters to you", Read Original ↗, Skip ✕, and "Why this story?".
6. Skip fades the card out and shows "Skipped · Undo" for 5 seconds.
7. Side column: Connect the Dots editor's note and Morning Mind Vitamin.
8. The end of the paper: "You're all caught up." Then the **Can you name 3 things?** recall check: 3 quick questions with instant feedback and a score.
9. AI Editor Desk (sidebar) is available at any time to change the paper by chat.
10. "Print next edition" creates a new edition using the updated weights, so improvement is visible.

## CopilotKit features

CopilotKit powers two experiences, and both work the same way: the AI reads the app's state and calls **frontend actions** that update React state and call our FastAPI endpoints.

**Setup choice (decide in Step 2, do not switch later).**

- **Option A, fastest:** Copilot Cloud public API key in `<CopilotKit publicApiKey=...>`. No runtime server.
- **Option B, self-hosted:** a tiny Node `runtime/` server using `@copilotkit/runtime` with an OpenAI or Gemini adapter, on port 4000. The frontend points `runtimeUrl` at it.
- Either way, FastAPI stays a plain REST backend. We do not use the CopilotKit Python SDK.
- CopilotKit's API changes between versions. Claude Code must check the installed version's docs before writing hook code (for example `useCopilotAction` vs newer tool hooks).

**1. Onboarding interviewer ("Talk to the Editor")**

| Piece | Name | What it does |
| --- | --- | --- |
| Readable | `readerProfileDraft` | The live profile card state: name, paper title, bio, topics with weights |
| Action | `setReaderName` | Sets the name and masthead, e.g. "THE AYESHA CHRONICLE" |
| Action | `addTopics` | Adds topic pills with starting weights (core interest 10, casual 5) |
| Action | `blockTopics` | Adds topics the reader never wants, weight −10 |
| Action | `setBio` | Saves a one-line plain-English bio |
| Action | `finishOnboarding` | Calls `POST /api/onboard`, then starts the Printing Press |
| Generative UI | Topic pill render | Shows newly added pills inside the chat as they are created |

System instructions: be a warm newspaper editor; ask one short question at a time; at most 4 questions; call actions as soon as you learn something; never invent interests.

**2. AI Editor Desk (sidebar on the paper)**

| Piece | Name | What it does |
| --- | --- | --- |
| Readable | `currentEdition` | Headlines, summaries, sections and skipped status of the open edition |
| Readable | `topicWeights` | The reader's current weights |
| Action | `adjustInterest` | Changes a topic weight (±5) and logs a COPILOT signal |
| Action | `swapStory` | Replaces one story with a fresh one on a requested topic via `POST /api/edition/{id}/swap` |
| Action | `explainStory` | Answers in chat using the story's summary and source; no new facts |
| Action | `printNextEdition` | Generates a new edition with the updated weights |
| Action | `quizMe` | Opens the recall check |

Demo lines: "Less politics, more quantum computing." · "Swap the lead story for something on climate tech." · "Why does story 3 matter to me?"

## Architecture

```text
┌──────────────────────────────┐                 ┌──────────────────────────────┐
│ REACT + VITE FRONTEND        │                 │ FASTAPI BACKEND              │
│                              │                 │                              │
│ Onboarding                   │                 │ Gatherer                     │
│  Talk to the Editor / Quick  │   REST /api     │  Google News RSS + fallbacks │
│                              │◄───────────────►│ Ranker                       │
│ Broadsheet page              │                 │  Score, explore, lead, order │
│  Masthead, 3 Things, cards,  │                 │ AI editor                    │
│  caught up + recall check    │                 │  One LLM call, strict JSON   │
│                              │                 │ Learning engine              │
│ Drawers and Editor Desk      │                 │  Clicks, skips, quiz, Copilot│
│  Brain, Past Editions,       │                 │ PDF press                    │
│  AI Editor Desk              │                 │  ReportLab 3-column          │
└──────────────┬───────────────┘                 │ Store                        │
               │                                 │  store.json                  │
               ▼                                 └──────┬───────────────▲───────┘
┌──────────────────────────────┐                        │               │ fetch
│ COPILOTKIT                   │                        ▼               │
│ Cloud key or Node runtime    │──────────────►┌──────────────┐  ┌──────┴───────┐
│ Reads state, calls actions   │               │ LLM API      │  │ Web news     │
└──────────────────────────────┘               │ Gemini/OpenAI│  │ RSS feeds    │
                                               └──────────────┘  └──────────────┘
```

The browser talks to FastAPI over REST for everything except chat. CopilotKit handles chat and calls frontend actions, which in turn call the same REST endpoints, so the backend has one source of truth. The backend calls the LLM once per edition and once per story swap. Export a clean version of this diagram as `architecture-diagram.png` for the submission.

## Data model and API

All state lives in `backend/data/store.json` for one reader, read and written through a small `store.py` module with a file lock, so the rest of the code never touches the file directly.

```json
{
  "user": {
    "onboarded": true,
    "name": "Ayesha",
    "paper_title": "THE AYESHA CHRONICLE",
    "bio": "CS student into AI agents and cybersecurity",
    "topic_weights": {"AI Agents": 12, "Cybersecurity": 10, "Celebrity Gossip": -10},
    "source_weights": {"TechCrunch": 2},
    "created_at": "2026-10-17T11:40:00Z"
  },
  "editions": [
    {
      "id": "ed-2026-10-17-1",
      "edition_number": 1,
      "date": "2026-10-17",
      "reading_minutes": 8,
      "three_takeaways": [{"text": "...", "article_id": "a1"}],
      "connect_the_dots": {"text": "...", "article_ids": ["a1", "a4"]},
      "mind_vitamin": {"title": "...", "content": "..."},
      "recall_quiz": [{"question": "...", "options": ["..."], "answer_index": 0, "article_id": "a1"}],
      "sections": ["AI Agents", "Cybersecurity"],
      "articles": [
        {
          "id": "a1", "topic": "AI Agents", "headline": "...", "summary": "...",
          "why_it_matters": "...", "source_name": "TechCrunch", "url": "https://...",
          "published_at": "...", "score": 14.2, "is_lead": true,
          "skipped": false, "clicked": false
        }
      ]
    }
  ],
  "signals": [
    {"ts": "...", "edition_id": "...", "article_id": "a1", "topic": "AI Agents", "action": "CLICK", "delta": 2}
  ]
}
```

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Health check |
| GET | `/api/state` | `onboarded`, profile, and today's edition id if it exists |
| POST | `/api/onboard` | Save profile, set `onboarded = true` |
| POST | `/api/reset` | Dev only: clear the store for a fresh demo |
| GET | `/api/edition/today` | Return today's edition, generating it if missing |
| POST | `/api/edition/next` | Generate a new edition now (demo of learning and archive) |
| GET | `/api/editions` | List editions: id, number, date, lead headline |
| GET | `/api/edition/{id}` | One full edition |
| GET | `/api/edition/{id}/pdf` | Download the PDF, skipped stories excluded |
| POST | `/api/edition/{id}/swap` | Replace one article with a new one on a topic |
| POST | `/api/signal` | Record CLICK, SKIP, UNSKIP, QUIZ_RIGHT, QUIZ_WRONG or COPILOT and update weights |
| GET | `/api/brain` | Topic weights plus the last 10 signals |
| GET | `/api/generation/status` | Printing Press step for the loading screen |

## AI editor, ranking and learning

An edition is built in four steps: gather, rank, write, save. Only the write step uses the AI, in **one call per edition**.

**1. Gather (`gatherer.py`)**

- For each topic with weight above 0, query Google News RSS: `https://news.google.com/rss/search?q=<topic>&hl=en-US&gl=US&ceid=US:en`
- Add 3–5 fixed fallback feeds (BBC, Reuters-style tech and world feeds) in case Google News fails
- Keep articles from the last 48 hours; remove duplicates by URL and by similar headline
- Fetch up to 600 characters of text per article from the RSS description; do not scrape full pages (too slow)
- Cache raw results for 30 minutes in memory

**2. Rank (`ranker.py`, pure Python, fully unit-tested)**

```text
score = topic_weight
      + recency_bonus      (3 if under 12 hours, 1.5 if under 24, else 0)
      + source_weight      (from clicks on that source)
      - seen_penalty       (10 if the URL appeared in an earlier edition)
```

- Pick 10 articles: the top 9 by score, plus 1 **explore slot** from a low or new topic, labelled "Something new"
- At most 3 articles per topic, so one interest never fills the paper
- Topics with negative weight are never fetched
- The highest score becomes the lead story; sections are ordered by topic weight

**3. Write (`ai_editor.py`, one AI call)**

Input: reader bio, topic weights, and the 10 chosen articles (id, headline, source, text). Output: strict JSON, validated with Pydantic.

```json
{
  "articles": [{"id": "a1", "headline": "...", "summary": "2-3 sentences", "why_it_matters": "1 sentence for this reader"}],
  "three_takeaways": [{"text": "...", "article_id": "a1"}],
  "connect_the_dots": {"text": "...", "article_ids": ["a1", "a4"]},
  "mind_vitamin": {"title": "...", "content": "..."},
  "recall_quiz": [{"question": "...", "options": ["...", "...", "..."], "answer_index": 0, "article_id": "a1"}]
}
```

Prompt rules: use only facts in the given text; never invent numbers; keep the original headline meaning; each takeaway and quiz question must cite an article id; write in calm newspaper style. If the JSON fails validation, retry once, then fall back to RSS headlines and descriptions with no AI text.

**4. Learning signals (`learning.py`)**

| Signal | Topic delta | Other effect |
| --- | --- | --- |
| Read Original click | +2 | Source weight +1 |
| Skip | −3 | Story hidden on web and left out of the PDF |
| Undo skip | +3 | Reverses the skip |
| Recall question right | +1 | Shows the reader engaged with that topic |
| Copilot "more / less" | ±5 | Logged with the reader's words |
| Onboarding | 10 core, 5 casual, −10 blocked | Initial weights |

Weights are clamped between −15 and 25. The Brain panel shows each topic's weight as a bar and the last 10 signals in plain words, for example "Skipped a Crypto story · Crypto −3".

## Design system

The look is a classic broadsheet with modern product precision: warm paper, black ink, serif headlines, strict column rules, and one red accent.

| Token | Value | Use |
| --- | --- | --- |
| `--bg-paper` | #FAF7F2 | Page background |
| `--bg-card` | #FFFDF9 | Cards, drawers, chat |
| `--ink` | #1A1917 | Text and heavy rules |
| `--ink-muted` | #5C5852 | Dates, sources, metadata |
| `--rule` | #D6D1C7 | 1px column rules |
| `--accent` | #B93829 | Badges, Skip, the one highlight per view |
| Headline font | Playfair Display | Masthead and headlines |
| Body font | Inter, line height 1.6 | Summaries and UI |
| Meta font | JetBrains Mono | Dates, sources, weights, edition numbers |

**Layout rules**

- Masthead: double rule above and below, centered paper title, a meta row of volume, edition, date and reading time
- Grid: 12 columns on desktop; lead story spans 8, side column 4; collapses to 1 column on phones
- Cards have no shadows or rounded corners; separate them with rules, like print
- Motion: skip fades and collapses in 250 ms; drawers slide in 200 ms; nothing else animates
- Every button has a visible focus state and works by keyboard

**PDF** uses the same structure in ReportLab: Times-Bold masthead, a boxed 3 Takeaways strip, 3 columns with vertical rules, and headlines as live links.

## Working rules for Claude Code

Every step follows the same loop: build backend and frontend, run tests, check in the browser, commit and push. A step is not done until all four pass.

**Stack**

- Backend: Python 3.11+, FastAPI, Uvicorn, Pydantic, feedparser, httpx, ReportLab, google-genai or openai, python-dotenv. Tests: pytest, pytest-asyncio, FastAPI TestClient
- Frontend: React + Vite, Tailwind CSS, lucide-react, CopilotKit. Tests: Vitest, React Testing Library, jsdom
- Optional: Playwright for one end-to-end smoke test in Step 10

**The loop for every step**

1. Backend: write the code and its pytest tests in the same step. Mock all network and AI calls in tests.
2. Frontend: write the component and its Vitest test. Mock `fetch` and CopilotKit.
3. Run `pytest -q` in `backend/` and `npm test -- --run` in `frontend/`. Both must be green.
4. Run both servers and do the step's browser check yourself (you, the human, watch it).
5. Commit with the step's message and push to GitHub.

**Rules**

- Never commit `.env`, `venv/`, `node_modules/`, or `backend/data/store.json`; commit `store.example.json` instead
- Keep all AI access in `ai_editor.py` and all file access in `store.py`
- Frontend calls the backend only through `src/api.js`
- Vite proxies `/api` to `http://localhost:8000`, so there are no CORS problems
- If a step runs over its time by 10 minutes, stop, commit what works, and move on
- Never break a passing test to make a new one pass

**Paste this into `CLAUDE.md` at the repo root**

```markdown
# The Personal Morning Paper
Read BLUEPRINT.md before every step. Build only the current step.
For each step: backend code + pytest tests, frontend code + Vitest tests,
run `cd backend && pytest -q` and `cd frontend && npm test -- --run`,
fix until green, then tell me exactly what to check in the browser.
Do not commit until I confirm the browser check.
Mock all network and AI calls in tests. Never commit .env or store.json.
CopilotKit APIs change between versions: check the installed version's
docs before writing CopilotKit code.
```

## Step-by-step build guide

Twelve steps fit in 5 hours, with the riskiest feature (CopilotKit onboarding) early while there is time to recover. Tell Claude Code: **"Do Step N from BLUEPRINT.md."**

| Step | Time | Build | Commit message |
| --- | --- | --- | --- |
| 0 | 0:00–0:15 | Repo, scaffolds, test runners | `chore(step-0): scaffold monorepo with tests` |
| 1 | 0:15–0:35 | Store, state API, app router, design tokens | `feat(step-1): state store and visit router` |
| 2 | 0:35–1:20 | CopilotKit onboarding interviewer + quick form | `feat(step-2): copilot onboarding interviewer` |
| 3 | 1:20–1:50 | News gatherer and ranker | `feat(step-3): news gatherer and ranker` |
| 4 | 1:50–2:25 | AI editor, daily edition, Printing Press | `feat(step-4): ai editor and daily edition` |
| 5 | 2:25–3:00 | Broadsheet webpage | `feat(step-5): broadsheet reading page` |
| 6 | 3:00–3:25 | Learning engine and Brain panel | `feat(step-6): learning engine and brain panel` |
| 7 | 3:25–3:50 | AI Editor Desk | `feat(step-7): copilot editor desk` |
| 8 | 3:50–4:05 | Archive and Print next edition | `feat(step-8): past editions archive` |
| 9 | 4:05–4:30 | PDF generator | `feat(step-9): broadsheet pdf` |
| 10 | 4:30–4:45 | Recall check, explore boxes, full-flow test | `feat(step-10): recall check and polish` |
| 11 | 4:45–5:00 | README, diagram, Loom, submit | `docs(step-11): readme and architecture` |

### Step 0: Setup (0:00–0:15)

- Create a **public** GitHub repo `personal-morning-paper`, clone it, add `BLUEPRINT.md`, `CLAUDE.md`, `.gitignore`
- Backend: `backend/` with venv, `app/main.py` (FastAPI with `/api/health`), `requirements.txt`, `tests/test_health.py`, `.env.example`
- Frontend: `npm create vite@latest frontend -- --template react`, add Tailwind, lucide-react, Vitest, React Testing Library, jsdom; Vite proxy `/api` → 8000; one smoke test that App renders
- **Tests:** `pytest -q` passes 1 test; `npm test -- --run` passes 1 test
- **Browser:** `localhost:8000/api/health` shows `{"ok": true}`; `localhost:5173` shows the app
- Commit and push. Check the commit appears on GitHub.

### Step 1: State core and router (0:15–0:35)

- Backend: `store.py` (load, save, lock, defaults), `/api/state`, `/api/onboard`, `/api/reset`, Pydantic models for profile
- Frontend: `api.js`, `App.jsx` reads `/api/state` and shows Onboarding or Paper; design tokens and fonts in `index.css`; a placeholder Masthead
- **Tests:** store creates defaults when the file is missing; onboard sets `onboarded = true`; App shows onboarding when `onboarded` is false and the paper when true
- **Browser:** open the app, see onboarding; POST a profile in `/docs`; refresh and see the paper placeholder with your masthead; reset brings onboarding back

### Step 2: CopilotKit onboarding (0:35–1:20)

- Choose Option A or B from the CopilotKit section and wire the `<CopilotKit>` provider
- `Onboarding.jsx`: welcome screen with "Talk to the Editor" and "Quick setup"
- `EditorInterview.jsx`: chat on the left, `ReaderProfileCard.jsx` on the right; readable `readerProfileDraft`; actions `setReaderName`, `addTopics`, `blockTopics`, `setBio`, `finishOnboarding`
- `QuickSetup.jsx`: name, topic pills, bio, submit (also the fallback if CopilotKit fails)
- Profile card pills are editable by hand
- **Tests:** profile reducer adds, blocks and removes topics correctly; QuickSetup submits the right payload; profile card renders pills and weights
- **Browser:** chat "I'm Ayesha, I study CS and love AI agents and cybersecurity, no celebrity news." The card fills in live, with "THE AYESHA CHRONICLE" and a blocked pill. Finish, and `store.json` holds the profile

### Step 3: News gatherer and ranker (1:20–1:50)

- Backend: `gatherer.py` (Google News RSS per topic, fallback feeds, 48-hour filter, dedupe, 30-minute cache); `ranker.py` (the score formula, max 3 per topic, explore slot, lead pick, section order); `/api/debug/candidates`
- **Tests:** dedupe removes same URL and near-same headline; blocked topics are never queried; the ranker picks the top score as lead, caps 3 per topic, includes 1 explore article; parsing works on a saved sample RSS file
- **Browser:** open `/api/debug/candidates` and see real, current articles for your topics with scores

### Step 4: AI editor and daily edition (1:50–2:25)

- Backend: `ai_editor.py` (one call, strict JSON, Pydantic validation, one retry, no-AI fallback); `editions.py` builds gather → rank → write → save; `/api/edition/today`, `/api/generation/status`; reading time from word count
- Frontend: `PrintingPress.jsx` loading screen polling the status; after onboarding, it shows until the edition is ready
- **Tests:** a valid AI response parses; invalid JSON triggers retry then fallback; every takeaway references a real article id; calling `today` twice the same day does not create a second edition
- **Browser:** finish onboarding, watch the Printing Press steps, and the edition JSON appears in `store.json` with summaries and 3 takeaways

### Step 5: Broadsheet webpage (2:25–3:00)

- Frontend: `Masthead.jsx` (title, volume, edition, date, reading time, buttons), `ThreeTakeaways.jsx` (each links to its story), `BroadsheetGrid.jsx` (lead spans 8 columns, sections in weight order), `StoryCard.jsx` (tag, source, headline, summary, why it matters, Read Original, Skip, Why this story?), `SideColumn.jsx`, `CaughtUp.jsx`
- **Tests:** the lead card renders first; sections follow the given order; Read Original has `target="_blank"` and the right URL; takeaway click scrolls to its story
- **Browser:** the page looks like a newspaper; resize to phone width and it becomes one column; Read Original opens the publisher

### Step 6: Learning engine and Brain panel (3:00–3:25)

- Backend: `learning.py` with the signal table, clamping, `/api/signal`, `/api/brain`
- Frontend: Skip fades the card and shows "Skipped · Undo" for 5 seconds; Read Original sends CLICK; `BrainPanel.jsx` drawer with weight bars and the last 10 signals; "Why this story?" shows topic and weight
- **Tests:** skip −3, click +2 and source +1, undo +3, clamping at −15 and 25; skip marks `skipped = true` in the edition; card disappears and undo restores it
- **Browser:** skip a story, open the Brain, see that topic drop by 3; undo and see it return

### Step 7: AI Editor Desk (3:25–3:50)

- Backend: `/api/edition/{id}/swap` (fetch and rank one replacement on a topic, write its summary with the AI)
- Frontend: `EditorDesk.jsx` CopilotKit sidebar; readables `currentEdition`, `topicWeights`; actions `adjustInterest`, `swapStory`, `explainStory`, `printNextEdition`, `quizMe`
- **Tests:** swap replaces exactly one article and keeps the rest; adjustInterest sends a COPILOT signal with the right delta
- **Browser:** say "less politics, more quantum computing" and see weights change in the Brain; say "swap the lead story for climate tech" and see the lead change live

### Step 8: Archive and next edition (3:50–4:05)

- Backend: `/api/editions`, `/api/edition/{id}`, `/api/edition/next`
- Frontend: `ArchiveDrawer.jsx` lists editions newest first; selecting one loads it and updates the masthead; a "Print next edition" button
- **Tests:** next edition increments the number and avoids URLs already used; the list is newest first
- **Browser:** skip two stories of one topic, print the next edition, see that topic shrink; open the archive and reopen Edition 1

### Step 9: PDF (4:05–4:30)

- Backend: `pdf.py` with ReportLab `BaseDocTemplate`, 3 frames, masthead, takeaways box, column rules, linked headlines, skipped stories excluded; `/api/edition/{id}/pdf`
- Frontend: Download PDF in the masthead and in each archive entry
- **Tests:** the response is `application/pdf` and starts with `%PDF`; a skipped headline is not in the PDF text; the edition number appears
- **Browser:** download today's PDF, check columns, takeaways box and that a headline link opens the article

### Step 10: Recall check and polish (4:30–4:45)

- Frontend: `RecallCheck.jsx` after "You're all caught up": 3 questions, instant feedback, score, sends QUIZ signals; Connect the Dots and Mind Vitamin boxes in the side column
- Run the whole flow from `/api/reset`: onboarding → edition → read, skip, quiz → next edition → archive → PDF
- Optional: one Playwright smoke test of that flow
- **Browser:** the full flow with no console errors

### Step 11: Submission (4:45–5:00)

- README: what it is, features mapped to the 5 requirements, setup, `.env` keys, how to run tests, screenshots
- Export the architecture diagram to `architecture-diagram.png` in the repo root
- Record the Loom, make the repo public, submit all three links

## Demo, Loom and submission

Record the Loom only after a full rehearsal, with today's edition already generated, so nothing waits on the network while you film.

**Demo safety**

- Keep `sample_edition.json`; if the AI or feeds fail, `/api/edition/today` falls back to it
- Generate Edition 1, use it (skip, click), then generate Edition 2 before recording
- Keep API keys in `.env` only; check `git log` shows no secrets before making the repo public
- If CopilotKit misbehaves live, Quick setup and the normal buttons still do everything

**Loom script (5 minutes or less)**

| Time | Show |
| --- | --- |
| 0:00–0:30 | The problem: 10 news tabs open. "After all this, can you name 3 things you learned?" |
| 0:30–1:30 | Talk to the Editor: chat, and the profile card fills in live. Print my first edition, Printing Press |
| 1:30–2:30 | The paper: 3 Things box, lead story, "Why this story?", Read Original, Skip with undo |
| 2:30–3:15 | Brain panel shows the weight drop; Editor Desk: "less politics, more quantum", swap the lead live |
| 3:15–3:45 | Print next edition: the skipped topic shrank. Archive: reopen Edition 1 |
| 3:45–4:20 | Download PDF: columns, takeaways box, working links |
| 4:20–4:50 | Caught up → recall check, Connect the Dots, Mind Vitamin |
| 4:50–5:00 | Architecture diagram, close |

**Submission checklist**

- [ ] Repo created and pushed in the first 15 minutes
- [ ] At least one commit per step, pushed
- [ ] All pytest and Vitest tests green
- [ ] Full flow tested from a reset
- [ ] README with setup and feature list
- [ ] `architecture-diagram.png` in the repo root
- [ ] Loom recorded, 5 minutes or less
- [ ] Repo set to public
- [ ] Repo link, Loom link and diagram submitted