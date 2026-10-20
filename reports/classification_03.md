# Classification & decomposition (stage 03)

Generated 2026-10-20T22:37:44 · prompt `classify_promises` v1.2 · model `gemini-3.5-flash-lite`

## Summary

| term | promises | classified | unresolved | vague share | indicators | headline (signal ≥ 1) | LLM calls | cache hits | retried alone | overrides |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| AIADMK-2016 | 312 of 312 | 312 | 0 | 22.4% | 385 | 25 (52) | 0 | 38 | 22 | 4 |
| DMK-2021 | 667 of 667 | 667 | 0 | 6.3% | 710 | 25 (106) | 0 | 76 | 43 | 26 |
| TVK-2026 | 695 of 695 | 695 | 0 | 10.2% | 768 | 25 (107) | 0 | 95 | 62 | 13 |

**Vague share stop rule (> 50%, D-070):** not exceeded.

**Neutrality:** every term used the same prompt version (classify_promises v1.2), the same rubric, the same checks C1–C6 and the same thresholds (headline cap 25, 2–4 indicators, 2–4 queries of 2–12 words). The template names no party or term; promise and unit IDs are replaced by batch-local aliases. Manifesto text (units, source spans) can name the party: it is data.

## Covariates

### Sector

| value | AIADMK-2016 | DMK-2021 | TVK-2026 |
|---|---:|---:|---:|
| agriculture_fisheries | 65 | 93 | 78 |
| education | 14 | 34 | 57 |
| health | 15 | 31 | 24 |
| social_welfare | 18 | 53 | 52 |
| caste_minority_welfare | 35 | 29 | 32 |
| employment_labour | 21 | 77 | 49 |
| industry_it_msme | 40 | 62 | 164 |
| infrastructure_transport_housing | 25 | 77 | 37 |
| local_government | 4 | 15 | 10 |
| water_environment_energy | 38 | 80 | 54 |
| governance_law_state_rights | 27 | 60 | 88 |
| culture_language_religion | 10 | 56 | 50 |
| other | 0 | 0 | 0 |

### Promise type

| value | AIADMK-2016 | DMK-2021 | TVK-2026 |
|---|---:|---:|---:|
| advocacy | 11 | 54 | 27 |
| law_regulation | 6 | 32 | 20 |
| transfer_subsidy | 65 | 107 | 159 |
| infrastructure | 62 | 144 | 155 |
| institution | 22 | 72 | 63 |
| scheme_expansion | 52 | 43 | 14 |
| new_scheme | 10 | 25 | 37 |
| administrative | 84 | 190 | 220 |

### Specificity

| value | AIADMK-2016 | DMK-2021 | TVK-2026 |
|---|---:|---:|---:|
| specific | 242 | 625 | 624 |
| vague | 70 | 42 | 71 |

### Cost band

| value | AIADMK-2016 | DMK-2021 | TVK-2026 |
|---|---:|---:|---:|
| none | 32 | 110 | 97 |
| low | 19 | 109 | 86 |
| medium | 136 | 233 | 251 |
| high | 125 | 215 | 261 |

### Union basis

| value | AIADMK-2016 | DMK-2021 | TVK-2026 |
|---|---:|---:|---:|
| advocacy | 11 | 54 | 27 |
| union_subject | 1 | 19 | 0 |
| presidential_assent | 0 | 1 | 0 |
| union_approval | 3 | 8 | 7 |
| union_funds | 0 | 1 | 0 |
| gst_council | 0 | 0 | 0 |
| none | 297 | 584 | 661 |

### Continues existing (verbatim cue)

| term | true |
|---|---:|
| AIADMK-2016 | 83 |
| DMK-2021 | 74 |
| TVK-2026 | 19 |

### Indicators per vague promise

| term | 2 | 3 | 4 |
|---|---:|---:|---:|
| AIADMK-2016 | 67 | 3 | 0 |
| DMK-2021 | 41 | 1 | 0 |
| TVK-2026 | 69 | 2 | 0 |

## Headline promises

### AIADMK-2016

| rank | promise | signal | cost | text |
|---:|---|---:|---|---|
| 1 | AIADMK-2016-0107 | 2 | high | Establish separate intensive care units in all government hospitals. |
| 2 | AIADMK-2016-0108 | 2 | high | Continue the schemes of providing Amma baby care gift box, Amma maternity sanjeevi, and sanitary napkins being provided to protect the welfa |
| 3 | AIADMK-2016-0109 | 2 | high | Expand the Amma full body check-up scheme and Amma women's special full body check-up scheme to all districts. |
| 4 | AIADMK-2016-0111 | 2 | high | Continue to implement the Chief Minister's Comprehensive Health Insurance Scheme. |
| 5 | AIADMK-2016-0114 | 2 | high | Increase and provide the financial assistance provided to pregnant mothers from 12,000 rupees to 18,000 rupees. |
| 6 | AIADMK-2016-0117 | 2 | high | Provide Vitamin C tablets to boys and girls through Anganwadis and schools. |
| 7 | AIADMK-2016-0118 | 2 | high | Continue to provide uninterrupted power supply. |
| 8 | AIADMK-2016-0223 | 2 | high | Provide cellphones free of cost to all ration cardholders. |
| 9 | AIADMK-2016-0001 | 1 | high | Waive all crop loans, medium-term loans and long-term loans payable by small and marginal farmers to cooperative banks. |
| 10 | AIADMK-2016-0002 | 1 | high | Provide crop loans to the extent of 40,000 crores through cooperative banks during the 5-year period from 2016 to 2021. |
| 11 | AIADMK-2016-0029 | 1 | high | Implement a new special scheme at a cost of 800 crore rupees to cut down and remove old and pest-attacked coconut trees and plant new coconu |
| 12 | AIADMK-2016-0032 | 1 | high | Provide free electricity continuously to farmers. |
| 13 | AIADMK-2016-0040 | 1 | high | Provide increased procurement price for paddy. |
| 14 | AIADMK-2016-0081 | 1 | high | Continue these schemes. |
| 15 | AIADMK-2016-0087 | 1 | high | Continue the lifelong beneficial Uzhavar Security Scheme. |
| 16 | AIADMK-2016-0088 | 1 | high | Fully implement the Coastal Disaster Hardship Reduction Scheme to mitigate the damage caused by natural calamities like cyclones, floods and |
| 17 | AIADMK-2016-0090 | 1 | high | Continue the scheme of allotting 3 cents of land to build houses for landless poor families. |
| 18 | AIADMK-2016-0092 | 1 | high | Continue the Amma Scheme and Amma Service Centre being implemented on the basis of government seeking out the people. |
| 19 | AIADMK-2016-0094 | 1 | high | Continue the scheme of providing free laptops to students studying in 11th standard and 12th standard. |
| 20 | AIADMK-2016-0095 | 1 | high | Provide free internet connection facility along with this laptop to students. |
| 21 | AIADMK-2016-0096 | 1 | high | Continue various schemes for school students. |
| 22 | AIADMK-2016-0098 | 1 | high | Implement an internet-based integrated learning scheme in high schools and higher secondary schools. |
| 23 | AIADMK-2016-0100 | 1 | high | Continue the allocation provided to study in private schools for vulnerable and underprivileged sections. |
| 24 | AIADMK-2016-0123 | 1 | high | Provide 100 units of electricity free of charge to homes according to the current billing method. |
| 25 | AIADMK-2016-0160 | 1 | high | Provide a gift coupon worth 500 rupees to all family cardholders to purchase handloom clothes from Co-optex worth 500 rupees for Pongal fest |
| | *below the cap* | | | |
| 26 | AIADMK-2016-0171 | 1 | high | Continue to implement the scheme for providing free dhotis and sarees. |
| 27 | AIADMK-2016-0185 | 1 | high | Continue to implement the projects of constructing new roads, widening roads, constructing bypass roads, railway overbridges, bridges and mi |
| 28 | AIADMK-2016-0190 | 1 | high | Build multi-story apartments for families living in huts in metropolitan areas, and transform them into slum-free cities. |
| 29 | AIADMK-2016-0191 | 1 | high | Construct 10 lakh houses through the Chief Minister's Green Houses Scheme, Group Houses Scheme and other schemes. |
| 30 | AIADMK-2016-0197 | 1 | high | Expand the free bus facility for senior citizens. |

### DMK-2021

| rank | promise | signal | cost | text |
|---:|---|---:|---|---|
| 1 | DMK-2021-0242 | 2 | high | Implement a massive scheme to provide 10 lakh jobs each year and 50 lakh jobs for youngsters at the end of 2025-26 from 2021. |
| 2 | DMK-2021-0414 | 2 | high | Raise assistance provided to all eligible senior citizens to Rs 1500 to Rs 1000 and ensure assured delivery of the assistance through the po |
| 3 | DMK-2021-0424 | 2 | high | Raise financial assistance provided to senior citizen women, widowed women, abandoned women, unmarried women of over 50 years of age, Sri La |
| 4 | DMK-2021-0041 | 1 | high | Protect farmers from market fluctuations by a new model to determine the prices of their produce and guarantee a minimum price. |
| 5 | DMK-2021-0042 | 1 | high | Waive all the farm and jewellery loans of small and medium farmers as promised two years ago by allocating necessary funds. |
| 6 | DMK-2021-0052 | 1 | high | Provide 90% subsidy to farmers to encourage the implementation of drip irrigation for up to 5 acres of land. |
| 7 | DMK-2021-0055 | 1 | high | Increase daily wage to Rs 300. |
| 8 | DMK-2021-0077 | 1 | high | Add palm jaggery to the list of items for sale for card holders in ration shops. |
| 9 | DMK-2021-0092 | 1 | high | Take steps to directly procure coconut oil and distribute it through ration shops. |
| 10 | DMK-2021-0093 | 1 | high | Establish Soil Research Institutes in Regional agricultural offices located in every Ward within Panchayat Unions across the state. |
| 11 | DMK-2021-0095 | 1 | high | Deliver agricultural inputs required for increased production to all villages across the state through farmer-friendly vehicles at support p |
| 12 | DMK-2021-0102 | 1 | high | Increase the support price from 2000 rupees (under present ADMK govt) to 2500 rupees per quintal. |
| 13 | DMK-2021-0103 | 1 | high | Increase the support price for sugarcane to 4000 rupees. |
| 14 | DMK-2021-0109 | 1 | high | Revitalise and expand the ‘Uzhavar Santhai’ scheme to many cities. |
| 15 | DMK-2021-0111 | 1 | high | Provide fully subsidised seed grains to farmers without assessing the variety of seed grains, and its date of validity. |
| 16 | DMK-2021-0118 | 1 | high | Renovate the Kannika Sluice gate and provide water to irrigate about 40000 acres of agri land in Nellai, Thoothukdui and Virudhunagar region |
| 17 | DMK-2021-0124 | 1 | high | Convert all existing ground bridges across the state to high-level bridges to prevent waterlogging of streets caused during floods. |
| 18 | DMK-2021-0125 | 1 | high | Set-up a State level Water Management Scheme with a budget of 10,000 crore under the Chief Minister’s Monitorable Target to improve the live |
| 19 | DMK-2021-0130 | 1 | high | Take steps at 5000 crore budget to deepen the city rivers, design storm-water drainage to facilitate transportation of water into the sea an |
| 20 | DMK-2021-0155 | 1 | high | Provide 2 lakh new houses for fishermen. |
| 21 | DMK-2021-0156 | 1 | high | Construct 2 lakh new houses to benefit the fishermen community from coastal districts of Tamil Nadu. |
| 22 | DMK-2021-0165 | 1 | high | Increase Monsoon and Fishing ban relief to Rs 8000. |
| 23 | DMK-2021-0166 | 1 | high | Increase relief aid given to fishermen for fishing ban days from Rs 5000 to Rs 8000. |
| 24 | DMK-2021-0167 | 1 | high | Increase relief aid given to fishermen for monsoon season from Rs 5000 to Rs 6000. |
| 25 | DMK-2021-0175 | 1 | high | Provide Fish Landing site to all fishing villages in the state. |
| | *below the cap* | | | |
| 26 | DMK-2021-0177 | 1 | high | Erect sea erosion barriers and bait arches (thoondil valaivu) along the coastal areas in the state to prevent sea rage and sea erosion. |
| 27 | DMK-2021-0178 | 1 | high | Provide fishing harbors and cold storage facilities for all coastal areas in the state to encourage fishing and its related employment econo |
| 28 | DMK-2021-0200 | 1 | high | Increase pension, medical assistance, financial assistance for education and accident insurance amounts. |
| 29 | DMK-2021-0208 | 1 | high | Repay graduate education loans for students from schools in Tamil Nadu, who are under 30 years of age, who are unable to pay it back within  |
| 30 | DMK-2021-0212 | 1 | high | Install automatic vending machines to provide free of cost sanitary napkins for government and government-aided school and college students. |

### TVK-2026

| rank | promise | signal | cost | text |
|---:|---|---:|---|---|
| 1 | TVK-2026-0089 | 2 | high | Provide 200 units of free electricity every month to eligible households. |
| 2 | TVK-2026-0216 | 2 | high | Implement the Vettri Payanam scheme where women can travel free of charge in all town, city, and inter-district government buses operating a |
| 3 | TVK-2026-0259 | 2 | high | Appoint 5 lakh youth as permanent employees in every village panchayat and urban local body under the Chief Minister Makkal Sevai Nanbar Thi |
| 4 | TVK-2026-0556 | 2 | high | Provide a 'Makkal Nalan Kaapeedu' card worth Rs. 25 lakh to each family upon the formation of the TVK government. |
| 5 | TVK-2026-0087 | 1 | high | Identify poor families in Tamil Nadu and ensure that all government welfare schemes reach them. |
| 6 | TVK-2026-0088 | 1 | high | Create appropriate employment opportunities for them and opportunities to start self-employment, through which their minimum annual income w |
| 7 | TVK-2026-0090 | 1 | high | Ensure 100 percent clean drinking water supply to all houses in Tamil Nadu. |
| 8 | TVK-2026-0091 | 1 | high | Build and give 5 lakh new houses so that poor and common people in rural areas can get their own houses. |
| 9 | TVK-2026-0095 | 1 | high | Distribute iron and folic acid-fortified rice, vitamin A and vitamin D-enriched cooking oil, and fortified wheat flour to everyone through r |
| 10 | TVK-2026-0105 | 1 | high | Provide permanent houses and pattas to all Adi Dravidar and Tribal people in Tamil Nadu. |
| 11 | TVK-2026-0119 | 1 | high | Increase the old-age pension to three thousand (Rs 3000) rupees. |
| 12 | TVK-2026-0120 | 1 | high | Arrange to take two and a half lakh senior citizens to pilgrimage destinations of their choice every year. |
| 13 | TVK-2026-0122 | 1 | high | Start 1000 mobile senior citizen clinics across Tamil Nadu for senior citizens. |
| 14 | TVK-2026-0124 | 1 | high | Conduct free physical examinations and provide medicines for chronic diseases by visiting each village panchayat across Tamil Nadu in person |
| 15 | TVK-2026-0132 | 1 | high | Increase the monthly pension for differently-abled persons to three thousand (Rs 3000) rupees. |
| 16 | TVK-2026-0133 | 1 | high | Appoint an exclusive teacher for special children in every government school. |
| 17 | TVK-2026-0140 | 1 | high | Provide an annual financial assistance of 30 thousand rupees to each weaver family that owns a loom (power loom/handloom). |
| 18 | TVK-2026-0145 | 1 | high | Provide life insurance worth 10 lakh rupees to all weavers. |
| 19 | TVK-2026-0154 | 1 | high | Establish a Government Employee Welfare Board with an allocation of Rs 5,000 crore to protect the rights and ensure the welfare of governmen |
| 20 | TVK-2026-0173 | 1 | high | Fill all vacant posts in government schools. |
| 21 | TVK-2026-0176 | 1 | high | Convert all Anganwadi workers into 'Grade - D' government employees and provide them a monthly salary of 18000 rupees on that basis. |
| 22 | TVK-2026-0177 | 1 | high | Ensure a monthly salary of 10,000 rupees for Anganwadi assistants and Asha workers who undertake health awareness tasks. |
| 23 | TVK-2026-0195 | 1 | high | Provide life insurance worth 10 lakh rupees and accident insurance worth 10 lakh rupees to all registered gig workers. |
| 24 | TVK-2026-0206 | 1 | high | Provide accident insurance worth 5 lakh rupees to registered construction workers. |
| 25 | TVK-2026-0214 | 1 | high | Credit 2500 rupees every month into the bank account of every woman family head until they reach the age of 60. |
| | *below the cap* | | | |
| 26 | TVK-2026-0215 | 1 | high | Deposit the money for purchasing 6 cooking gas cylinders per year directly into the bank account of every family. |
| 27 | TVK-2026-0218 | 1 | high | Provide every child born in government hospitals in Tamil Nadu with a gold ring and a Thaimaman Seer Pettagam containing essential items inc |
| 28 | TVK-2026-0219 | 1 | high | Credit 15 thousand rupees a year in two installments to the bank account of the mother or guardian of students studying from the first stand |
| 29 | TVK-2026-0221 | 1 | high | Provide interest-free loans up to 5 lakh rupees to women self-help groups. |
| 30 | TVK-2026-0222 | 1 | high | Provide an investment subsidy of 5 lakh rupees in a non-repayable manner to women self-help groups attempting to become micro-entrepreneurs. |

## Check failures

| term | by rule | resolution |
|---|---|---|
| AIADMK-2016 | {'C5': 3, 'C3': 29} | {'retry alone': 29, 'override': 3} |
| DMK-2021 | {'C3': 41, 'C6': 4, 'C5': 9, 'C2': 2} | {'retry alone': 28, 'override': 28} |
| TVK-2026 | {'C3': 46, 'C5': 3, 'C6': 8, 'C2': 19, 'C4': 1} | {'retry alone': 65, 'override': 12} |

