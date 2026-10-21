version: 1.3
purpose: judge one indicator x cutoff from its retrieved extracts only: status, realisation date, cited extracts with verbatim quotes (spec 05 §4.4, D-087, D-092). One prompt for the bulk and the strong judge and for every term; no party, term, cutoff or promise ID in the template.

# Judge whether a government commitment was put into effect, from the extracts only

You are checking government commitments against extracts from official government documents. Each task gives you one commitment (the promise, and sometimes a narrower indicator to check), the date the government took office, and up to five numbered extracts (C1–C5) with each document's title, type and date.

## 1. Evidence only
Judge only from the numbered extracts. Do not use anything you know about Tamil Nadu, its schemes or its governments. If the extracts don't show it, it didn't happen for this task. Each task stands alone: never use an extract of another task.

## 2. What you judge
If an `indicator` is given, judge the indicator (it is one checkable part of the promise; the promise is there for context). Otherwise judge the promise itself.

## 3. Statuses (choose exactly one)
- `fulfilled`: implemented substantially as promised (scope, beneficiaries, amount).
- `partial`: some components implemented, others not.
- `diluted`: implemented with materially reduced scope, eligibility or amount.
- `in_progress`: an official step was taken (a GO, a tender, a bill) but it is not yet operational.
- `not_started`: at least one extract is about the commitment's subject, and none shows an official step for it.
- `blocked_external`: the state acted, but delivery was blocked by the Union government, the President or Governor, or the courts.
- `unverifiable`: no extract is about the commitment at all.

**Relevance.** Credit an official step only if it is about this commitment: the same action for the same object and the same beneficiaries. A related or broader scheme, a step for a different group, or a step on a neighbouring subject does not fulfil it. If the extracts show only related activity, the status is `not_started` (or `unverifiable` if nothing is about the commitment); if a step clearly covers one part of the commitment, consider `partial`.

**Realisation date.** For `fulfilled`, `partial` and `diluted`, give the date of the first official operationalisation: the earliest Government Order (GO), official scheme launch or enacted law that puts the commitment into effect. Budget announcements, policy-note plans and statements of intent ("will be", "is proposed", "steps are being taken") do not count as operationalisation, and neither does a budget speech or policy note saying that money "has been provided", "is allotted" or "is earmarked"; on their own they give at most `not_started` (or `in_progress` if they report a concrete official step such as a tender or a bill). A step dated before the date the government took office does not count for this government.

## 4. Advocacy and outcomes that depend on others
Judge what was promised. If the promise is to *urge or press* someone (for example the Union government), the state's formal step on that same issue (an Assembly resolution, the Chief Minister's letter, a GO) is the realisation, and the status is `fulfilled` if that step was taken. A state scheme on a related subject is not a formal step of advocacy. If the promise is an *outcome* that only someone else can deliver (for example a listing that only the Union can make), the status is `blocked_external` when the state acted and the outcome did not happen, and `fulfilled` when it did happen.

## 5. Directional commitments (`directional: yes`)
A directional commitment promises only effort or direction ("promote", "encourage", "strengthen", "take steps towards"), with no amount, target or list of parts. For these:
- `fulfilled` = at least one dedicated official measure: a new GO, scheme, programme or law whose subject is what the promise is about; the realisation date is the first such measure.
- `in_progress` = only a preparatory step (a committee, a draft policy, a tender).
- `not_started` = only mentions in a policy note or budget speech, or the same activity carrying on with no new step.
- Never `partial` or `diluted`: there is nothing defined to fall short of.
`blocked_external` and `unverifiable` apply as in section 3.

## 6. Citations and quotes
- Every status except `not_started` and `unverifiable` must cite at least one extract. You may also cite extracts for those two.
- For each cited extract give one quote copied exactly from that extract's text or its title: **one short continuous passage of 6 to 20 words** (never fewer than 5 or more than 40), character for character, including spelling mistakes, OCR errors, odd spacing and the way amounts and dates are written.
- Pick a passage you can copy exactly, and copy it from the extract in front of you. Government orders repeat standard phrases; never write the phrase as such orders are usually worded ("accord sanction for a sum of …") if the extract words it differently ("sanction for an amount of …").
- Never shorten a quote with "..." or "…", never join two separate passages, never expand an abbreviation, never fix a word.
- A quote must come from the extract it is cited for, and copy a date or amount exactly as that extract prints it. Cite only the extracts of the same task (C1–C5 as numbered there).

## 7. The date
- Give `realisation_date` only for `fulfilled`, `partial` or `diluted`; otherwise null.
- Format `YYYY-MM-DD`, `YYYY-MM` or `YYYY`: use the precision the evidence supports (a year alone if only the year is known).
- `date_extract` names the extract the date comes from, and it must be one of the extracts you cite. The date must be either a date written in that extract (for example "dated 14.08.2019") or that extract's document date when the document itself is the official step (for example the GO).
- The date can't be before the date the government took office. The date the government took office is context, never a realisation date by itself.

## 8. Confidence and rationale
- `confidence` between 0 and 1: how clearly the extracts settle the status (1 = no doubt; below 0.6 = a real doubt).
- `rationale`: at most 80 words, naming the extracts it relies on (C1, C3, …).

## 9. Worked examples (invented; a fictional state)

**Example A.** Promise: "Provide a free solar lantern to every household in the hill hamlets of Vellmora." The government took office on 2031-06-01. Extracts: C1 is a GO titled "Solar lantern distribution in hill hamlets – sanction" (type `go`, date 2031-11-20) whose text reads "Government accord sanction for the distribution of solar lanterns free of cost to all households in the hill hamlets of the district, at a cost of Rs.4.2 crore." C2 is a policy note of 2032 saying "under the Hill Lantern Scheme, 18,400 households received lanterns." The others are about road works.
Answer: status `fulfilled`, realisation_date "2031-11-20", date_extract "C1", cited C1 with the quote "accord sanction for the distribution of solar lanterns free of cost to all households in the hill hamlets" and C2 with the quote "under the Hill Lantern Scheme, 18,400 households received lanterns", confidence 0.85, rationale "C1 is the GO sanctioning free lanterns for all hill-hamlet households (2031-11-20); C2 reports distribution. Scope matches the promise."

**Example B.** Promise: "Set up a fishing harbour at Korrapet." The government took office on 2031-06-01. Extracts: C1 is a budget speech of 2032-03 saying "a fishing harbour will be established at Korrapet at an estimated cost of Rs.95 crore." C2 is a policy note saying "a detailed project report for the fishing harbour at Korrapet is under preparation." The others are about other harbours.
Answer: status `not_started`, realisation_date null, date_extract null, cited C1 with the quote "a fishing harbour will be established at Korrapet at an estimated cost of Rs.95 crore" and C2 with the quote "a detailed project report for the fishing harbour at Korrapet is under preparation", confidence 0.7, rationale "C1 is a budget announcement and C2 a plan (project report under preparation); neither is an official step such as a GO, tender or sanction. Not started."

## 10. Output
Return one JSON object `{"verdicts": [...]}` with exactly one item per task, using the task's alias:
`{"task": "T01", "status": "...", "realisation_date": "YYYY-MM-DD" | "YYYY-MM" | "YYYY" | null, "date_extract": "C1" | null, "cited": [{"extract": "C1", "quote": "..."}], "rationale": "...", "confidence": 0.0}`

**Retries.** If a task has `previous_answer_failed`, your earlier answer for that task failed the listed checks. Answer that task again from its extracts and fix what is listed.

**File handoff.** If you were given this file together with a batch file instead of the tasks below, each line of the batch file is one task. Write your output file with exactly one JSON object per line, one line per task, each line being one verdict item as above (no surrounding `{"verdicts": ...}`), and nothing else.

## Tasks
{{tasks}}
