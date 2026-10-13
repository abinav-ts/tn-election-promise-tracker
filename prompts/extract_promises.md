version: 1.3
purpose: split manifesto units into pieces and render each promise in English (spec 02 §4.5, D-038). One prompt for every party; party and language are data.

You read items from an election manifesto and identify the commitments in them.

Data for this call:
- Party: {{party}}
- Manifesto language: {{language}}

Use ONLY the text of the units below. Do not add anything from your own knowledge of this party, of Tamil Nadu, or of what happened after the election: no scheme names, dates, amounts, places or numbers that are not in the unit.

## Task
For every unit, split its text into pieces. Each piece has a `kind`:
- `promise`: a commitment about the future: something that will be done, given, built, changed, passed or stopped. Commitments to urge, press, fight for or demand something from the Union (Central) government count as promises.
- `achievement`: a claim about what has already been done (past record).
- `criticism`: a statement about opponents or previous governments.
- `values`: a statement of belief or intent with no concrete action.
- `other`: headings, preamble, explanation, justification.

Every unit must return at least one piece.

## Splitting rules
- S1. One promise = one action toward one object or beneficiary group that could be delivered and checked on its own.
- S2. Split when a unit holds distinct actions, distinct beneficiary groups with distinct benefits, or distinct amounts or targets.
- S3. Do not split: a means from its goal ("a committee will be formed to draft a policy" is one promise); conditions or eligibility; a list of places or items under one action (one promise).
- S5. A sentence that says what a promised action, body or scheme will do, cover or achieve (its scope, powers, purpose or target, e.g. "The new board will settle disputes between tenants and owners", "This will meet the target set by the planning council in 2009") is part of that commitment: include its content in the promise's text and extend `source_text` to cover it; make it a separate promise only if it is a distinct, independently checkable action. Never classify a sentence about the future ("will", "shall", Tamil "-ப்படும்") as `other` unless it is pure background with no action.
- Pure explanation and justification of the past or present (why something is needed) is `other`; leave it out of the promise.
- S4. Promises split from one unit may share the same `source_text`.

## For each piece
- `source_text`: the shortest contiguous span copied EXACTLY from the unit text (same script, same spelling, same punctuation; do not translate, correct or join separate parts) that contains the piece.
- `text`:
  - for a `promise`: ONE English sentence starting with a base verb ("Provide …", "Establish …", "Urge the Union government to …"). It must be understandable on its own: if the commitment points to something described elsewhere in the unit ("this scheme", "these centres", "it"), name that thing in the text using the unit's own words, and extend `source_text` so it also covers those words. Keep the unit's own amounts, units, names and places. Write numbers exactly as they appear in the source (digits stay digits; do not turn words into digits or digits into words; do not convert units). Transliterate Tamil names into English letters. Add nothing that is not in the source.
  - for other kinds: a short English gloss (may be empty).

For each unit also give `section_en`: an English rendering of the unit's `section` (null if the unit has no section).

## Examples (invented; not from any real manifesto)

Unit: {"unit_id": "EX-U0001", "section": "Coastal Villages", "text": "Coastal Villages\n18. A cold storage unit will be built in every fishing harbour, and women who sell dried fish will receive Rs 2,500 a month during the lean season. These harbours were neglected for ten years by the last regime."}
Output: {"unit_id": "EX-U0001", "section_en": "Coastal Villages", "pieces": [
 {"kind": "other", "text": "Heading", "source_text": "Coastal Villages"},
 {"kind": "promise", "text": "Build a cold storage unit in every fishing harbour.", "source_text": "A cold storage unit will be built in every fishing harbour"},
 {"kind": "promise", "text": "Provide Rs 2,500 a month during the lean season to women who sell dried fish.", "source_text": "women who sell dried fish will receive Rs 2,500 a month during the lean season"},
 {"kind": "criticism", "text": "The last regime neglected the harbours for ten years.", "source_text": "These harbours were neglected for ten years by the last regime."}]}

Unit: {"unit_id": "EX-U0002", "section": null, "text": "19. We shall press the Union Government to sanction new rail lines on the Arcot - Vellore, Hosur - Dharmapuri and Karur - Salem routes."}
Output: {"unit_id": "EX-U0002", "section_en": null, "pieces": [
 {"kind": "promise", "text": "Urge the Union Government to sanction new rail lines on the Arcot - Vellore, Hosur - Dharmapuri and Karur - Salem routes.", "source_text": "We shall press the Union Government to sanction new rail lines on the Arcot - Vellore, Hosur - Dharmapuri and Karur - Salem routes."}]}

Unit: {"unit_id": "EX-U0003", "section": "3. நூலக வசதி :", "text": "3. நூலக வசதி :\n• அனைத்து ஊராட்சிகளிலும் நவீன நூலகங்கள் அமைக்கப்படும். கடந்த ஐந்து ஆண்டுகளில் 120 நூலகங்கள் திறக்கப்பட்டுள்ளன."}
Output: {"unit_id": "EX-U0003", "section_en": "3. Library facilities", "pieces": [
 {"kind": "other", "text": "Heading", "source_text": "3. நூலக வசதி :"},
 {"kind": "promise", "text": "Establish modern libraries in all village panchayats.", "source_text": "அனைத்து ஊராட்சிகளிலும் நவீன நூலகங்கள் அமைக்கப்படும்"},
 {"kind": "achievement", "text": "120 libraries were opened in the last five years.", "source_text": "கடந்த ஐந்து ஆண்டுகளில் 120 நூலகங்கள் திறக்கப்பட்டுள்ளன."}]}

Unit: {"unit_id": "EX-U0005", "section": null, "text": "• The village bakery scheme started in 2014 now runs in 300 villages. It will be extended to every district."}
Output: {"unit_id": "EX-U0005", "section_en": null, "pieces": [
 {"kind": "achievement", "text": "The village bakery scheme runs in 300 villages.", "source_text": "The village bakery scheme started in 2014 now runs in 300 villages."},
 {"kind": "promise", "text": "Extend the village bakery scheme to every district.", "source_text": "The village bakery scheme started in 2014 now runs in 300 villages. It will be extended to every district."}]}

Unit: {"unit_id": "EX-U0004", "section": "Clean Towns", "text": "20. An expert task force will be formed to prepare a plan to make every town in the state free of flooding by the end of the term."}
Output: {"unit_id": "EX-U0004", "section_en": "Clean Towns", "pieces": [
 {"kind": "promise", "text": "Form an expert task force to prepare a plan to make every town in the state free of flooding by the end of the term.", "source_text": "An expert task force will be formed to prepare a plan to make every town in the state free of flooding by the end of the term."}]}

## Units
{{units}}

Return JSON: {"units": [{"unit_id": …, "section_en": …, "pieces": [{"kind": …, "text": …, "source_text": …}, …]}, …]} with one entry per unit, in the same order.
