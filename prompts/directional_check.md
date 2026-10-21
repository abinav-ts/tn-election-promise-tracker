version: 1.0
purpose: mark promises that commit only to effort or direction, from the English promise text only (spec 05 §4.2, D-089). One prompt for every manifesto.

# Mark directional commitments

Each item below is one commitment from an election manifesto, in English. Decide for each whether it is **directional**.

A commitment is **directional** if it commits only to effort or direction ("promote", "encourage", "strengthen", "take steps towards", "give importance to", "work for"), with no amount, target or list of parts.

It is **not directional** if it names something concrete that can be checked: an amount of money, a number of units or people, a target, a list of parts, or a named institution, scheme, building or law to be created or changed. Most commitments ("build a hospital in a named town", "give a monthly payment of a stated amount", "pass a law on a named subject", "set up a named board") are not directional.

Judge only the text given. Do not use anything you know about any party, state or scheme.

## Examples (invented)
- "Encourage the use of organic manure among growers." → directional, cue "Encourage".
- "Take steps towards making every lake in the plains clean." → directional, cue "Take steps towards".
- "Strengthen the fisheries cooperatives by giving each a cold-storage unit." → not directional (a concrete part: a cold-storage unit for each).
- "Promote tourism by setting up a Hill Crafts Museum in the valley town." → not directional (a named institution).

## Output
Return one JSON object `{"promises": [...]}` with exactly one item per commitment, using its id:
`{"id": "P01", "directional": true, "cue": "Encourage"}`
- `cue`: if directional, the effort or direction words copied exactly from the commitment's text (as few words as possible); if not directional, an empty string.

## Commitments
{{promises}}
