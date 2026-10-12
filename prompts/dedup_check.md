version: 1.0
purpose: decide whether pairs of promises from the same manifesto are the same commitment (spec 02 §4.6, D-038, D-050)

Each pair below holds two promises from the same election manifesto (written in English).

For each pair decide: are they the SAME commitment, meaning the same action, for the same beneficiaries, with the same amount or target? Two promises about the same topic with different actions, beneficiaries, places or amounts are NOT the same. Use only the text of the two promises.

Pairs:
{{pairs}}

Return JSON: {"pairs": [{"pair_id": …, "same": true|false, "reason": "<one short line>"}, …]} with one entry per pair, in the same order.
