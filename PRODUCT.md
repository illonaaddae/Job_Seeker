# PRODUCT.md

Durable product context for JobSeeker. Design decisions live in `DESIGN.md`;
this file is what the product *is*, and it should outlast any visual system.

> **Provenance.** Written on 2026-09-03 from the repository itself — README,
> `jobseeker/` source, the pipeline stages, the guardrails in `.env`, and the
> shipped dashboard — rather than from an interview. Lines marked **[assumed]**
> are inference and should be corrected by the owner. Everything else is
> verifiable in the code.

## What it is

An autonomous job application engine. It reads real job descriptions from ATS
boards, scores them against who the owner actually is, writes something specific
to each one, and never sends anything the owner has not approved.

It is a **personal tool for one person**, not a product with customers. That
single fact drives most of the design: there is no multi-tenancy, no onboarding
funnel, no billing, and the dashboard can assume its reader already knows what
the engine does.

## The unique mechanism

Explainable scoring plus a hard human gate.

Every role gets 0–100 assembled from six **named** signals — title fit, skill
overlap, seniority, location, freshness, and how much description there is to
work with. The breakdown is stored with the job, so the product can always say
*why* something was skipped instead of showing a mysterious number. Roles can
also be blocked outright by senior titles, wrong stacks, or excluded keywords.

Drafting and sending are separate stages with a person in between. The engine
can find a thousand roles and write a hundred letters; it cannot email a
stranger in the owner's name until the owner says so.

## Who uses it, and the real scene

One person — the repo owner — several times a day, mostly on a laptop, often in
the evening. **[assumed: the evening/laptop bias, from the dark-first theme
preference and the 06:00 Accra automation window.]**

They arrive with one of three questions, in this order:

1. What is waiting for me right now?
2. Which of these roles is worth my afternoon?
3. Is this letter good enough to send in my name?

The dashboard exists to answer those three and little else. Anything that does
not serve one of them is decoration.

## The pipeline

```
discover → score → draft → approve → send → follow up → read replies
```

- **discover** — pulls open roles from Greenhouse, Lever, Ashby, Workable,
  RemoteOK and Arbeitnow. Needs no API key.
- **score** — ranks every role against the profile, with stored reasons.
- **draft** — writes the letter, a CV reordered for the posting, and the email
  that carries them.
- **approve** — a human decision. Never automated, by design.
- **send** — capped and paced, suppressed per company by a cooldown.
- **follow up** — twice, in the original thread, then it stops.
- **read replies** — IMAP sync, matched back to the causing application by
  threading headers, classified, and used to update the funnel. A reply cancels
  every scheduled follow-up for that thread.

## Non-negotiable constraints

These are commitments, not preferences. Breaking one is a bug.

- **Approval is always human.** The API refuses a live send when the master
  switch is off, whatever the dashboard asks for.
- **No em dashes or en dashes in generated copy.** Anywhere. They are the
  clearest tell of machine-written text, and the style guard enforces it
  absolutely.
- **Nothing generic ships.** A draft is audited for filler, and for whether it
  names the company, names the role, and cites something concrete. A sentence
  that would survive a find-and-replace of the company name is not worth
  sending.
- **No runtime dependencies.** The engine runs on the Python standard library
  alone: its own PDF writer, its own HTTP client, SQLite for state,
  `http.server` for the API. Python 3.11+.
- **Portal applications are never auto-submitted.** Every major ATS forbids it.
  The product removes the tedium instead, via a copy-ready apply pack.
- **Secrets stay in `.env` and the database.** Only a scrypt hash of the
  dashboard password is stored, never the password.

## Guardrails (current values)

Live sending is **off**; every send is a dry run until the master switch is
flipped and a confirmation is typed.

| Guardrail | Value |
|---|---|
| Live sending | disabled (`SEND_ENABLED=false`) |
| Daily send cap | 12 applications |
| Per-company cooldown | 45 days |
| Draft threshold | score 55 |
| Send threshold | score 62 |
| Follow-up schedule | day 6, then day 14 |
| Writer | `auto` → Claude when a key is present, else the template writer |

## What success looks like

The owner opens the dashboard, sees what needs them, decides on a handful of
applications, and closes it. Time-to-decision is the metric that matters, not
volume. A morning where the engine found 300 roles and the owner approved three
good letters is a success; one where they scrolled a lot is not.

## What would make a polished result feel wrong

- Anything that hides or softens the send state. Dry-run versus live must never
  be ambiguous.
- A dashboard that looks like a SaaS analytics product. This is a workshop tool
  for one person, and vanity metrics are noise.
- Automation that quietly does half its job. When a capability is missing, the
  product says which piece and what it would unlock.
- Cheerful copy. The product's voice is plain and specific. **[assumed: from the
  existing copy, which consistently states mechanism over benefit.]**

## Deployment

Runs locally with `./run serve`, which serves the JSON API and the built
dashboard from `dashboard/dist` on one port. Deploys to Azure as a container
(the runtime plus the source).

A GitHub Actions workflow (`.github/workflows/daily.yml`) runs weekdays at 06:00
UTC against a **deployed** instance, executing discover, score, draft, replies,
respond, followup and digest. It deliberately does **not** run `send`. It is
gated on the `JOBSEEKER_URL` repository variable and skips entirely when that is
unset, which is the current state — so no automation is live today.
