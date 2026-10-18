version: 1.0
purpose: classify each manifesto promise (covariates) and decompose vague promises into checkable indicators with search queries (spec 03 §4.2–§4.5, D-065–D-068). One prompt for every manifesto; the manifesto's text is data.

You classify promises taken from an election manifesto of an Indian state government, and you write checkable indicators and search queries for them.

Use ONLY the text given below: the front matter, each promise and the unit (manifesto item) it comes from. Do not use anything you know about any party, about Tamil Nadu, about what happened after the election, about which schemes already existed, or about which promises later became well known. The only outside knowledge allowed is general knowledge of the Indian Constitution, for `union_dependent` (see its rule).

## Input
- `front_matter`: the manifesto's opening pages (title, preface), in the manifesto's language.
- `units`: manifesto items. Each has `unit` (a label), `section`, `unit_text` (original language; Tamil or English) and `promises`. Each promise has `id`, `text` (one English sentence), `source_text` (the span of the unit it comes from) and `source_lang`.

Return exactly one result for every promise `id`, with the same `id`.

## Covariates

### `sector` (one per promise, by the main beneficiary or policy area; a tie goes to the department that would deliver it)
- `agriculture_fisheries`: farming, irrigation for farmers, crop insurance and loans, animal husbandry, dairy, fisheries, fishers
- `education`: schools, higher education, scholarships, exams, teachers, skills training within education
- `health`: hospitals, medical colleges, insurance, nutrition as health, sanitation as health, drugs
- `social_welfare`: women, children, elderly, persons with disabilities, transgender persons, pensions, food security and PDS
- `caste_minority_welfare`: Adi Dravidar and tribal welfare, backward and most backward classes, minorities, reservation
- `employment_labour`: jobs, recruitment to government posts, wages, unorganised workers, government employees' service conditions
- `industry_it_msme`: industry, investment, MSME, IT, startups, handlooms, textiles, tourism as industry
- `infrastructure_transport_housing`: roads, bridges, rail, metro, buses, ports, airports, housing
- `local_government`: rural development, urban local bodies, panchayats, municipal services, local elections
- `water_environment_energy`: drinking water, rivers, dams, environment, forests, climate, electricity, renewable energy
- `governance_law_state_rights`: administration, police, courts, anti-corruption, e-governance, Union–state relations, state rights, taxation and state finances
- `culture_language_religion`: Tamil language, culture, arts, sports, temples and religious bodies, heritage
- `other`: none of the above (expected to be rare)

### `promise_type` (when several fit, take the FIRST that applies in this order)
1. `advocacy`: the action is to urge, press or fight for something from the Union government, Parliament or another authority outside the state's control.
2. `law_regulation`: enact, amend or repeal a law or rule, or set up a regulatory standard.
3. `transfer_subsidy`: cash, in-kind goods, fee waivers, loans, subsidies or concessions to individuals or households.
4. `infrastructure`: build, upgrade or maintain a physical asset.
5. `institution`: set up a new body (commission, board, university, authority, college, centre).
6. `scheme_expansion`: extend, enlarge, raise or restore an existing programme without changing its kind.
7. `new_scheme`: a new programme not covered above.
8. `administrative`: a procedure, policy, staffing, survey, campaign or other executive measure.

### `specificity`
- `specific`: one checkable action with a clear object or beneficiary group. An amount or target is optional ("Provide a monthly assistance to women heads of family" is specific).
- `vague`: a goal or direction with no checkable action ("Strengthen the fisheries sector", "Make the state a leader in IT").
- Advocacy promises are judged on what is asked for.

### `cost_band` (judged from the text)
- `none`: administrative, regulatory or advocacy action with no material spending;
- `low`: one location, one institution, or a small targeted group;
- `medium`: district-scale or multi-site work, or one scheme for a defined group;
- `high`: a statewide entitlement or transfer, or a statewide programme of works.
A stated amount, when present, guides the band, but the band never invents an amount.

### `union_dependent` (true/false) and `union_basis`
`union_dependent` is true if delivery **as promised** needs an act of the Union government, Parliament or the President. Then `union_basis` is one of:
- `advocacy`: an advocacy promise;
- `union_subject`: a Union List subject (e.g. railways, national highways, central exams, citizenship, defence, airports, ports other than minor ports, central taxes);
- `presidential_assent`: a state law on a Concurrent List subject that departs from a central law (Art. 254(2)), or any change the text says needs central assent or exemption;
- `union_approval`: needs a Union clearance or approval that the text names or that is inherent (e.g. a new railway line, an AIIMS, an environmental clearance stated in the text);
- `union_funds`: the text makes Union funding a condition;
- `gst_council`: a change to a GST rate. Taxes outside GST stay state powers: a promise phrased as VAT, sales tax or a tax on petrol/diesel/alcohol is `none`. The rule follows the wording of the promise.

Otherwise `union_dependent` is false and `union_basis` is `none`. A State List subject, or a Concurrent List subject where the state can act within existing central law, is false. Backward-class lists are a state power (false, unless the text asks for a Union change such as Ninth Schedule protection, which is `union_subject`).
Use general knowledge of the Constitution of India as amended up to the 106th Amendment, about who holds the power. Judge by the promise's wording; never use events or dates after the election.

### `continues_existing` (true/false) and `continues_cue`
- true only when the **text itself** says the promise continues, extends, raises, restores or renames an existing programme or arrangement ("continue", "extend", "increase from", "restore", "will be expanded", or an existing scheme named as existing). `continues_cue` must hold those words, copied **exactly** (same script, spelling and punctuation) from the promise `text` or its `unit_text`, as one contiguous span.
- false otherwise, **including when you happen to know that such a scheme already existed**. Then `continues_cue` is "".
- A `scheme_expansion` promise always has `continues_existing` = true.

### `headline_signal` (0–3), from the text only
One point each, up to 3:
- a statewide or universal entitlement, or a benefit to a very large group;
- wording that marks the promise as special or primary in the manifesto itself ("flagship", "first", "major", "important", "special scheme", or a heading of its own);
- the promise being named or summarised in the front matter.
Never use knowledge of which promises later became well known.

## Consistency
- `promise_type` = `advocacy` ⇒ `union_dependent` = true and `union_basis` = `advocacy`.
- `promise_type` = `scheme_expansion` ⇒ `continues_existing` = true.
- `union_dependent` = false ⇔ `union_basis` = `none`.

## Indicators and search queries
- A `specific` promise is its own indicator: give only `search_queries` (2–4) for it and leave `indicators` empty.
- A `vague` promise gets `indicators`: 2–4 items, each `{text, search_queries}`, and an empty top-level `search_queries`.
- Each indicator is one official, observable step that would show the promise being acted on (an order, a scheme, a law, a body set up, a facility opened, a payment started). Write it as one English sentence of at most 40 words. Use only the promise's own words for names, amounts and places; add no scheme name, number, date or place the promise does not state.
- Search queries: 2–4 per indicator, English keywords, each 2 to 12 words. Generic government vocabulary and synonyms are fine ("government order", "scheme", "sanction", "launched", "assistance"). Write queries in lower case; a capitalised word or any number may appear only if it is in the promise `text`. Never add a scheme name, order number, year or date.

## Example (invented; not from any real manifesto)

Front matter: "Our pledge to the hill country. Five promises come first: a monthly support for every small tea grower, ..."

Units:
[{"unit": "U01", "section": "Hill Farmers", "unit_text": "41. Hill Farmers\nTea growers owning under two acres shall get a monthly support of Rs 1,200. The existing seedling subsidy for pepper growers will be raised from 40 percent to 60 percent.", "promises": [
  {"id": "P01", "text": "Provide a monthly support of Rs 1,200 to tea growers owning under two acres.", "source_text": "Tea growers owning under two acres shall get a monthly support of Rs 1,200.", "source_lang": "en"},
  {"id": "P02", "text": "Raise the existing seedling subsidy for pepper growers from 40 percent to 60 percent.", "source_text": "The existing seedling subsidy for pepper growers will be raised from 40 percent to 60 percent.", "source_lang": "en"}]},
 {"unit": "U02", "section": "Clean Coast", "unit_text": "42. Every seaside town shall be rid of plastic litter.", "promises": [
  {"id": "P03", "text": "Make every seaside town free of plastic litter.", "source_text": "Every seaside town shall be rid of plastic litter.", "source_lang": "en"}]},
 {"unit": "U03", "section": "Railways", "unit_text": "43. We will press the Union Government for an overnight train linking Valparai and Kotagiri.", "promises": [
  {"id": "P04", "text": "Urge the Union Government to run an overnight train linking Valparai and Kotagiri.", "source_text": "We will press the Union Government for an overnight train linking Valparai and Kotagiri.", "source_lang": "en"}]}]

Output:
{"promises": [
 {"promise_id": "P01", "sector": "agriculture_fisheries", "promise_type": "transfer_subsidy", "specificity": "specific", "cost_band": "medium", "union_dependent": false, "union_basis": "none", "continues_existing": false, "continues_cue": "", "headline_signal": 1, "search_queries": ["monthly support small tea growers", "tea growers under two acres assistance", "Rs 1,200 monthly support tea growers"], "indicators": []},
 {"promise_id": "P02", "sector": "agriculture_fisheries", "promise_type": "transfer_subsidy", "specificity": "specific", "cost_band": "medium", "union_dependent": false, "union_basis": "none", "continues_existing": true, "continues_cue": "The existing seedling subsidy for pepper growers will be raised from", "headline_signal": 0, "search_queries": ["pepper growers seedling subsidy enhanced", "seedling subsidy 60 percent pepper", "subsidy pepper seedlings revised"], "indicators": []},
 {"promise_id": "P03", "sector": "water_environment_energy", "promise_type": "administrative", "specificity": "vague", "cost_band": "medium", "union_dependent": false, "union_basis": "none", "continues_existing": false, "continues_cue": "", "headline_signal": 0, "search_queries": [], "indicators": [
   {"text": "The government issues an order to ban or control plastic litter in seaside towns.", "search_queries": ["plastic ban seaside towns order", "plastic litter coastal towns government order"]},
   {"text": "A plastic waste collection drive is started in seaside towns.", "search_queries": ["plastic waste collection coastal towns", "beach plastic clean up drive launched"]},
   {"text": "Facilities to collect or recycle plastic waste are set up in seaside towns.", "search_queries": ["plastic recycling unit coastal town", "plastic waste recovery facility sanctioned"]}]},
 {"promise_id": "P04", "sector": "infrastructure_transport_housing", "promise_type": "advocacy", "specificity": "specific", "cost_band": "none", "union_dependent": true, "union_basis": "advocacy", "continues_existing": false, "continues_cue": "", "headline_signal": 0, "search_queries": ["overnight train Valparai Kotagiri", "new train request railway ministry", "train service Valparai Kotagiri request"], "indicators": []}]}

Why: P02 is a subsidy to growers, so `transfer_subsidy` comes before `scheme_expansion` in the order, and its text says the existing subsidy is raised, so `continues_existing` is true with the words copied exactly. P03 states a goal with no checkable action, so it is vague and decomposed. P01 is named in the front matter (one point).

## Front matter
{{front_matter}}

## Units
{{units}}

Return JSON: {"promises": [{"promise_id": …, "sector": …, "promise_type": …, "specificity": …, "cost_band": …, "union_dependent": …, "union_basis": …, "continues_existing": …, "continues_cue": …, "headline_signal": …, "search_queries": […], "indicators": [{"text": …, "search_queries": […]}, …]}, …]} with one entry per promise `id`.
