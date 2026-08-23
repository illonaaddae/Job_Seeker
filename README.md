<div align="center">

# JobSeeker

**An autonomous job application engine that reads real job descriptions, scores them against who you actually are, writes something specific, and never sends anything you have not approved.**

Python, no dependencies · React + TypeScript dashboard · SQLite · deploys to Azure for the price of a coffee

</div>

---

## What it does

```
 discover  ──►  score  ──►  draft  ──►  approve  ──►  send  ──►  follow up  ──►  read replies
 real ATS      explainable   letter +    you, a       capped,     twice, in     inbox sync,
 job boards    0 to 100      tailored    human,       paced,      thread, then  auto status
               per signal    CV + email  decide       suppressed  it stops      updates
```

One command runs a stage. The dashboard runs the same stages behind a button, on the same guardrails.

```bash
./run discover      # pull open roles from Greenhouse, Lever, Ashby, Workable, RemoteOK, Arbeitnow
./run score         # rank every role against your profile, with reasons
./run draft         # write the letter, the tailored CV and the email
./run approve --all-drafts
./run send          # dry run by default. Live sending needs the master switch and a typed confirmation
./run serve         # the dashboard
```

## Why it is built this way

**Scoring is explainable, not a black box.** Every job gets a 0 to 100 score assembled from six named signals: title fit, skill overlap, seniority, location, freshness and how much description there is to work with. The breakdown is stored with the job, so the dashboard can say *why* something was skipped rather than showing a mysterious number. A role can also be blocked outright: senior titles, stacks that are not yours, and keywords you never want to see.

**Letters are specific or they do not go out.** Two writers produce the copy. With an `ANTHROPIC_API_KEY`, Claude writes against the actual job description. Without one, a deterministic writer quotes a real line from the posting and cites the project in your profile with the highest overlap. Either way the output goes through the same guard, which enforces two rules absolutely:

- **No em dashes or en dashes.** Anywhere. They are the clearest tell of machine written text.
- **Nothing generic.** A draft is audited for filler phrases, and for whether it names the company, names the role, and cites something concrete. A sentence that would survive a find and replace of the company name is not worth sending.

**Approval is a human step, on purpose.** Drafting and sending are separate stages with a person in between. The engine can find a thousand roles and write a hundred letters, but it cannot email a stranger in your name until you say so.

**It reads what comes back.** Replies are pulled over IMAP, matched to the application that caused them using the threading headers, classified, and used to update the funnel. A reply cancels every scheduled follow up for that thread automatically.

**No dependencies.** The engine runs on the Python standard library alone: its own PDF writer, its own HTTP client, SQLite for state, `http.server` for the API. It installs anywhere Python 3.11+ runs, and the container image is the runtime plus the source.

## Quick start

```bash
git clone <your fork> && cd Job_Seeker

cp .env.example .env                                   # nothing is required to start
cp data/profile.example.json data/profile.me.json       # then edit it
cp data/answers.example.json data/answers.json         # your form answers
./run discover                # real jobs, no API key needed
./run score
./run list --min-score 65
./run show <job id>           # the full breakdown and the description
./run draft --limit 5
./run serve                   # http://127.0.0.1:8787
```

The dashboard in development mode:

```bash
cd dashboard && npm install && npm run dev     # http://localhost:5273
```

Requires Python 3.11 or newer, and Node 20+ only if you want to change the dashboard.

## Your profile is the whole configuration

`data/profile.example.json` is the template. Copy it to `data/profile.<you>.json`, fill it in, and point `PROFILE_PATH` at it. It is the single source of truth: identity, target roles, skills with weights and aliases, experience, projects with keywords, education, certifications, tone, and the phrases you never want written in your name. Change that file and the engine applies as someone else. Nothing about any one person is hardcoded in code.

The same applies to `data/answers.example.json`, which holds the answers to the free text questions application forms keep asking. Both real files are git ignored: a profile carries a phone number and an address, and prepared interview answers are not something to publish.

The parts that do the most work:

| Section | What it drives |
| --- | --- |
| `targeting.roles` | title matching |
| `targeting.seniority_exclude` | blocks roles pitched above your level |
| `targeting.foreign_stacks` | blocks roles built around a language you do not use |
| `targeting.exclude_keywords` | hard rejections, for example clearance requirements |
| `skills.core` / `secondary` | the weighted skill match, with aliases so "react.js" counts as React |
| `projects[].keywords` | which project each letter cites, chosen by overlap with the posting |
| `style_rules` | the phrases and characters the guard strips |

## Where jobs come from

| Source | Key needed | Notes |
| --- | --- | --- |
| Greenhouse, Lever, Ashby, Workable | none | public board APIs, full descriptions |
| RemoteOK, Arbeitnow | none | aggregate feeds, remote heavy |
| `url` | none | paste any job link, the page is parsed and scored |
| `csv` | none | bulk import |
| Exa | `EXA_API_KEY` | finds companies with no public board, for speculative applications |
| Hunter, Prospeo, Apify | optional | resolves a company domain to a person worth writing to |

Board handles live in `data/boards.json`. Add one and the engine checks it answers before saving it:

```bash
./run boards add greenhouse monzo
./run boards list
```

## The guardrails

Nothing is sent until all of these pass, in this order:

1. `SEND_ENABLED=true`, off by default, and the CLI additionally requires you to type `SEND`
2. the application is `approved`, which only a human does
3. the daily cap, 12 by default
4. the per company cooling off window, 45 days by default
5. the suppression list, so anyone who asks to be left alone is never contacted again
6. the send score threshold
7. both attachments exist on disk

Sends are paced 35 to 75 seconds apart. Follow ups run twice, six and fourteen days out, in the original thread, and the second one offers to close the loop and step away. There is no third.

## The dashboard

Five views, dark and light, keyboard reachable, no chart library.

- **Overview** the funnel, sending rhythm, best matches, follow ups due, activity
- **Job matches** everything scored, filterable, with a review drawer showing the score breakdown, matched and missing skills, the draft, and the original posting
- **Applications** approve drafts, track what happened
- **Replies** what came back and how it was classified
- **Profile** what the engine knows and exactly what it will not do

## Running it without you

By default the engine finds and writes; you decide what goes out. Three settings
move that line, and each is off until you move it:

| Setting | Effect |
| --- | --- |
| `AUTO_APPROVE_SCORE=78` | drafts scoring 78 or more are approved without you, so `daily --live` sends them. Still capped, still suppression checked, and any draft the style guard flagged is held back. |
| `AUTO_REPLY=send` | straightforward replies are answered automatically. Anything about salary, notice, scheduling, visas or an offer is queued for you instead, always. |
| `DIGEST_TO=you@example.com` | a plain text summary lands in your inbox: what was sent, what came back, what needs a decision. |

The full loop, which is what the weekday cron runs:

```bash
./run daily            # dry run: discovers, scores, drafts, reads the inbox, simulates every send
./run daily --live     # the same, actually sending, within every guardrail
```

Individually:

```bash
./run respond          # draft answers to people who replied
./run digest           # email yourself the summary
./run auto-approve     # approve high scorers, if you have set a threshold
```

What is never automated, whatever the settings: accepting an offer, agreeing a
salary, or committing to a time. Those are drafted and left for you.

## The password

The dashboard is behind a password, because it can send email in your name.

```bash
./run set-password        # local: writes a scrypt hash into .env
```

Change it later from the dashboard under Profile, which stores it in the
database and signs out every other session. If you are ever locked out on a
deployed instance, `./run set-password --db` inside the container sets a new one,
and `--clear-db` falls back to the deployed secret. Full walkthrough in
`deploy/README.md`.

Only the hash is ever stored. There is no reset by email, by design.

## Deploying to Azure

One container serves both the API and the dashboard, with the database and the PDFs on an Azure Files share so nothing is lost on restart. Scale to zero means you pay for the storage and almost nothing else.

```bash
az login
export API_TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
./deploy/azure.sh
```

Then put a login in front of it. The app can send email as you, so it should never be open to the internet:

```bash
az containerapp auth microsoft update --name jobseeker --resource-group jobseeker-rg \
  --client-id <app-registration-id> --tenant-id <tenant-id> --yes
az containerapp auth update --name jobseeker --resource-group jobseeker-rg \
  --unauthenticated-client-action RedirectToLoginPage
```

`deploy/README.md` has the full walkthrough, including the GitHub Actions workflows for deploys and the weekday cron that discovers, scores and drafts while you sleep. That scheduled run never sends.

## Testing

```bash
python3 -m unittest discover -s tests -t . -v
cd dashboard && npm run type-check
```

The suite covers the style guard, the scoring blockers, the send guardrails, the PDF writer and the source parsers.

## Project layout

```
jobseeker/
  pipeline.py        every stage, in one place
  scoring.py         the explainable match score
  persona.py         your profile, as an object
  db.py              SQLite schema and queries
  sources/           one adapter per job board
  llm/               Claude writer, template writer, shared style enforcement
  documents/         PDF engine, cover letter, tailored CV
  outreach/          SMTP with guardrails, follow up sequencing, IMAP replies
  server/            the JSON API and static host
  util/style.py      the no dash, no filler rules
dashboard/           React + TypeScript + Tailwind
deploy/              Dockerfile and the Azure script
legacy/              the upstream project this grew out of
```

## Credit

Built on the idea behind [AbrahamGyamfi/Job_Seeker](https://github.com/AbrahamGyamfi/Job_Seeker), rewritten end to end.

What carried over as ideas: semantic search for companies that do not post publicly, contact enrichment before a speculative send, and the discipline of pacing sends and capping them per day. What did not: the code. The upstream hardcoded one person's name and positioning through every module, tracked state in CSV files, emailed every company it found with no matching step, and never read anything that came back.

The upstream copy is kept locally for reference and is deliberately not published here, because it contains its author's personal contact details.
