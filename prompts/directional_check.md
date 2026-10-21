version: 1.1
purpose: mark promises that commit only to effort or direction, from the English promise text only (spec 05 §4.2, D-089). One prompt for every manifesto.

# Mark directional commitments

Each item below is one commitment from an election manifesto, in English. Decide for each whether it is **directional**.

A commitment is **directional** only if it commits to effort or direction towards a broad aim ("promote", "encourage", "strengthen", "improve", "take steps towards", "give importance to", "work for"), with no amount, target or list of parts, so that there is no defined deliverable to check.

It is **not directional** if it names something concrete that can be checked, even without a number:
- an amount of money, a number of units or people, or a target ("achieve self-sufficiency in X" is a target);
- a list of parts;
- a specific action on a named or clearly identified object: build, set up, provide, give, abolish, remove, declare, amend, transfer, waive, start, revive, expand a named scheme ("Remove subject X from list Y", "Build cold stores in fishing harbours", "Revive the named institute");
- a named institution, scheme, building or law to be created or changed.

**Urging or pressing someone else** (the Union government, a court, an authority) to do a specific thing is **not directional**: the thing urged is the concrete part. Mark it directional only if what is urged is itself only an effort or direction.

Most commitments are not directional. When in doubt, answer not directional.

Judge only the text given. Do not use anything you know about any party, state or scheme.

## Examples (invented)
- "Encourage the use of organic manure among growers." → directional, cue "Encourage".
- "Take steps towards making the plains greener." → directional, cue "Take steps towards".
- "Strengthen the fisheries cooperatives by giving each a cold-storage unit." → not directional (a concrete part: a cold-storage unit for each).
- "Promote tourism by setting up a Hill Crafts Museum in the valley town." → not directional (a named institution).
- "Press the federal ministry to open a coastal guard station at Korrapet." → not directional (a specific thing urged).
- "Achieve full coverage of piped water in hill hamlets." → not directional (a target).
- "Expand the lantern scheme further." → not directional (a named scheme to be expanded).

## Output
Return one JSON object `{"promises": [...]}` with exactly one item per commitment, using its id:
`{"id": "P01", "directional": true, "cue": "Encourage"}`
- `cue`: if directional, the effort or direction words copied exactly from the commitment's text (as few words as possible); if not directional, an empty string.

## Commitments
{{promises}}
