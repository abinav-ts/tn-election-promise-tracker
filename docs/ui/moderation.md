# Comments and corrections: how they work and how to moderate them

The site is static (GitHub Pages): it cannot store or filter anything on a server. So:

1. **Corrections** (per promise): the "Suggest a correction" link opens a pre-filled GitHub issue from `.github/ISSUE_TEMPLATE/correction.yml` (label `community-correction`). Reviewed by hand; never changes a verdict automatically.
2. **General comments** (explorer, "Comments"): the form checks the text in the browser (length 20–600, no links, no abusive words from the short `ABUSE` list in `promises.html`, not all capitals, no long repeated runs, consent box ticked), then opens a pre-filled public GitHub issue from `comment.yml` (label `community-comment`). **Nothing is shown on the site until the maintainer approves it.**
3. **Approving a comment:** read the issue; if it is on topic and civil, add a record to `site/public/community/comments.json`, for example `{"id": 12, "name": "Asha", "date": "2026-10-27", "text": "…"}` (the issue number as `id`, the name field or "Anonymous", no GitHub username), commit and deploy. Close the issue with the label `comment-approved`; close rejected ones with `comment-rejected` and no reply that repeats the text.
4. **Before showing**, the page checks every approved comment against the same word list again and hides any that match (a second guard against a slip).

Limits to state plainly: the word list is a courtesy check and will miss things; the real filter is the person reading each comment. GitHub issues are public and show the submitter's GitHub name; the site never shows it. Comments are never inputs to prompts, thresholds, fits or the gold set (whitepaper §12).

A real backend (with rate limits and an automated classifier) is possible later but would end the "static site, no backend" constraint in spec 08.
