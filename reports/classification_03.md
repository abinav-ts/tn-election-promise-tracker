# Classification & decomposition (stage 03)

Generated 2026-10-20T17:18:53 · prompt `classify_promises` v1.1 · model `gemini-3.5-flash-lite`

## Summary

| term | promises | classified | unresolved | vague share | indicators | headline (signal ≥ 1) | LLM calls | cache hits | retried alone | overrides |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| AIADMK-2016 | 312 of 312 | 308 | 4 | 18.8% | 366 | 25 (36) | 41 | 1 | 26 | 0 |
| DMK-2021 | 667 of 667 | 658 | 9 | 5.6% | 695 | 25 (84) | 59 | 3 | 29 | 0 |
| TVK-2026 | 695 of 695 | 683 | 12 | 10.2% | 758 | 25 (102) | 106 | 3 | 76 | 0 |

**Vague share stop rule (> 50%, D-070):** not exceeded.

**Neutrality:** every term used the same prompt version (classify_promises v1.1), the same rubric, the same checks C1–C6 and the same thresholds (headline cap 25, 2–4 indicators, 2–4 queries of 2–12 words). The template names no party or term; promise and unit IDs are replaced by batch-local aliases. Manifesto text (units, source spans) can name the party: it is data.

## Covariates

### Sector

| value | AIADMK-2016 | DMK-2021 | TVK-2026 |
|---|---:|---:|---:|
| agriculture_fisheries | 56 | 95 | 73 |
| education | 13 | 31 | 49 |
| health | 14 | 31 | 30 |
| social_welfare | 18 | 50 | 44 |
| caste_minority_welfare | 36 | 28 | 31 |
| employment_labour | 20 | 82 | 48 |
| industry_it_msme | 44 | 53 | 165 |
| infrastructure_transport_housing | 25 | 74 | 40 |
| local_government | 8 | 12 | 7 |
| water_environment_energy | 41 | 82 | 55 |
| governance_law_state_rights | 21 | 67 | 92 |
| culture_language_religion | 12 | 53 | 49 |
| other | 0 | 0 | 0 |

### Promise type

| value | AIADMK-2016 | DMK-2021 | TVK-2026 |
|---|---:|---:|---:|
| advocacy | 11 | 55 | 26 |
| law_regulation | 6 | 28 | 22 |
| transfer_subsidy | 59 | 103 | 154 |
| infrastructure | 68 | 143 | 137 |
| institution | 20 | 65 | 68 |
| scheme_expansion | 49 | 47 | 10 |
| new_scheme | 13 | 22 | 38 |
| administrative | 82 | 195 | 228 |

### Specificity

| value | AIADMK-2016 | DMK-2021 | TVK-2026 |
|---|---:|---:|---:|
| specific | 250 | 621 | 613 |
| vague | 58 | 37 | 70 |

### Cost band

| value | AIADMK-2016 | DMK-2021 | TVK-2026 |
|---|---:|---:|---:|
| none | 40 | 105 | 115 |
| low | 31 | 140 | 85 |
| medium | 116 | 226 | 246 |
| high | 121 | 187 | 237 |

### Union basis

| value | AIADMK-2016 | DMK-2021 | TVK-2026 |
|---|---:|---:|---:|
| advocacy | 11 | 55 | 26 |
| union_subject | 1 | 18 | 0 |
| presidential_assent | 0 | 0 | 0 |
| union_approval | 2 | 5 | 2 |
| union_funds | 0 | 0 | 1 |
| gst_council | 0 | 0 | 0 |
| none | 294 | 580 | 654 |

### Continues existing (verbatim cue)

| term | true |
|---|---:|
| AIADMK-2016 | 77 |
| DMK-2021 | 63 |
| TVK-2026 | 16 |

### Indicators per vague promise

| term | 2 | 3 | 4 |
|---|---:|---:|---:|
| AIADMK-2016 | 58 | 0 | 0 |
| DMK-2021 | 37 | 0 | 0 |
| TVK-2026 | 65 | 5 | 0 |

## Headline promises

### AIADMK-2016

| rank | promise | signal | cost | text |
|---:|---|---:|---|---|
| 1 | AIADMK-2016-0160 | 2 | high | Provide a gift coupon worth 500 rupees to all family cardholders to purchase handloom clothes from Co-optex worth 500 rupees for Pongal fest |
| 2 | AIADMK-2016-0223 | 2 | high | Provide cellphones free of cost to all ration cardholders. |
| 3 | AIADMK-2016-0001 | 1 | high | Waive all crop loans, medium-term loans and long-term loans payable by small and marginal farmers to cooperative banks. |
| 4 | AIADMK-2016-0002 | 1 | high | Provide crop loans to the extent of 40,000 crores through cooperative banks during the 5-year period from 2016 to 2021. |
| 5 | AIADMK-2016-0029 | 1 | high | Implement a new special scheme at a cost of 800 crore rupees to cut down and remove old and pest-attacked coconut trees and plant new coconu |
| 6 | AIADMK-2016-0032 | 1 | high | Provide free electricity continuously to farmers. |
| 7 | AIADMK-2016-0035 | 1 | high | Implement an enhanced crop insurance scheme. |
| 8 | AIADMK-2016-0039 | 1 | high | Establish integrated cold storage infrastructure facilities across Tamil Nadu for easily perishable vegetable and fruit varieties for this p |
| 9 | AIADMK-2016-0040 | 1 | high | Provide increased procurement price for paddy. |
| 10 | AIADMK-2016-0094 | 1 | high | Continue the scheme of providing free laptops to students studying in 11th standard and 12th standard. |
| 11 | AIADMK-2016-0107 | 1 | high | Establish separate intensive care units in all government hospitals. |
| 12 | AIADMK-2016-0117 | 1 | high | Provide Vitamin C tablets to boys and girls through Anganwadis and schools. |
| 13 | AIADMK-2016-0123 | 1 | high | Provide 100 units of electricity free of charge to homes according to the current billing method. |
| 14 | AIADMK-2016-0171 | 1 | high | Continue to implement the scheme for providing free dhotis and sarees. |
| 15 | AIADMK-2016-0190 | 1 | high | Build multi-story apartments for families living in huts in metropolitan areas, and transform them into slum-free cities. |
| 16 | AIADMK-2016-0191 | 1 | high | Construct 10 lakh houses through the Chief Minister's Green Houses Scheme, Group Houses Scheme and other schemes. |
| 17 | AIADMK-2016-0210 | 1 | high | Provide all government department services through website and mobile phone. |
| 18 | AIADMK-2016-0211 | 1 | high | Provide all government services through the website. |
| 19 | AIADMK-2016-0216 | 1 | high | Expand and refine the service called Illandhorum Inaiyam to all areas. |
| 20 | AIADMK-2016-0218 | 1 | high | Provide Set-top Boxes free of cost to those who have obtained government cable TV connection. |
| 21 | AIADMK-2016-0224 | 1 | high | Provide breakfast under the nutritious meal scheme for primary school children. |
| 22 | AIADMK-2016-0225 | 1 | high | Provide 1 liter of Aavin milk fortified with Vitamin A, Vitamin D, and iron at a low price of Rs 25 to nurture the welfare of women and chil |
| 23 | AIADMK-2016-0229 | 1 | high | Continue to implement the nutritious meal scheme providing new food varieties. |
| 24 | AIADMK-2016-0231 | 1 | high | Continue to implement the old-age pension scheme. |
| 25 | AIADMK-2016-0234 | 1 | high | Continue to implement the scheme for constructing quality roads in all villages. |
| | *below the cap* | | | |
| 26 | AIADMK-2016-0235 | 1 | high | Ensure that there are no houses without an individual household toilet. |
| 27 | AIADMK-2016-0291 | 1 | high | Take steps to revise wage scales for Tamil Nadu government employees as soon as the recommendations of the 7th Pay Commission for Central Go |
| 28 | AIADMK-2016-0292 | 1 | high | Obtain the report of that committee and take action to continue the old pension scheme itself. |
| 29 | AIADMK-2016-0306 | 1 | high | Provide trainings to 10 lakh persons through industries and take action for them to get jobs in those same companies, with the government it |
| 30 | AIADMK-2016-0310 | 1 | high | Provide 50 percent subsidy to buy two wheelers (Moped/Scooter) so that women can easily go to their workplaces and other works. |

### DMK-2021

| rank | promise | signal | cost | text |
|---:|---|---:|---|---|
| 1 | DMK-2021-0015 | 2 | high | Set up Semmozhi Park in all Municipal Corporations. |
| 2 | DMK-2021-0125 | 2 | high | Set-up a State level Water Management Scheme with a budget of 10,000 crore under the Chief Minister’s Monitorable Target to improve the live |
| 3 | DMK-2021-0242 | 2 | high | Implement a massive scheme to provide 10 lakh jobs each year and 50 lakh jobs for youngsters at the end of 2025-26 from 2021. |
| 4 | DMK-2021-0041 | 1 | high | Protect farmers from market fluctuations by a new model to determine the prices of their produce and guarantee a minimum price. |
| 5 | DMK-2021-0042 | 1 | high | Waive all the farm and jewellery loans of small and medium farmers as promised two years ago by allocating necessary funds. |
| 6 | DMK-2021-0052 | 1 | high | Provide 90% subsidy to farmers to encourage the implementation of drip irrigation for up to 5 acres of land. |
| 7 | DMK-2021-0053 | 1 | high | Amend NREGA to provide 150 days of employment to rural people. |
| 8 | DMK-2021-0055 | 1 | high | Increase daily wage to Rs 300. |
| 9 | DMK-2021-0077 | 1 | high | Add palm jaggery to the list of items for sale for card holders in ration shops. |
| 10 | DMK-2021-0093 | 1 | high | Establish Soil Research Institutes in Regional agricultural offices located in every Ward within Panchayat Unions across the state. |
| 11 | DMK-2021-0095 | 1 | high | Deliver agricultural inputs required for increased production to all villages across the state through farmer-friendly vehicles at support p |
| 12 | DMK-2021-0102 | 1 | high | Increase the support price from 2000 rupees (under present ADMK govt) to 2500 rupees per quintal. |
| 13 | DMK-2021-0103 | 1 | high | Increase the support price for sugarcane to 4000 rupees. |
| 14 | DMK-2021-0124 | 1 | high | Convert all existing ground bridges across the state to high-level bridges to prevent waterlogging of streets caused during floods. |
| 15 | DMK-2021-0155 | 1 | high | Provide 2 lakh new houses for fishermen. |
| 16 | DMK-2021-0156 | 1 | high | Construct 2 lakh new houses to benefit the fishermen community from coastal districts of Tamil Nadu. |
| 17 | DMK-2021-0165 | 1 | high | Increase Monsoon and Fishing ban relief to Rs 8000. |
| 18 | DMK-2021-0175 | 1 | high | Provide Fish Landing site to all fishing villages in the state. |
| 19 | DMK-2021-0178 | 1 | high | Provide fishing harbors and cold storage facilities for all coastal areas in the state to encourage fishing and its related employment econo |
| 20 | DMK-2021-0208 | 1 | high | Repay graduate education loans for students from schools in Tamil Nadu, who are under 30 years of age, who are unable to pay it back within  |
| 21 | DMK-2021-0212 | 1 | high | Install automatic vending machines to provide free of cost sanitary napkins for government and government-aided school and college students. |
| 22 | DMK-2021-0213 | 1 | high | Provide tablet devices to students studying higher secondary schools and colleges with 4G/5G connectivity and 10GB data connection. |
| 23 | DMK-2021-0214 | 1 | high | Equip all educational institutions with wi-fi facilities. |
| 24 | DMK-2021-0215 | 1 | high | Establish new medical colleges in districts where currently there are no medical colleges. |
| 25 | DMK-2021-0216 | 1 | high | Bear the fees of the first generation economically backward students who enrol in engineering, medical and agricultural courses through the  |
| | *below the cap* | | | |
| 26 | DMK-2021-0220 | 1 | high | Provide milk to students in government and government-aided schools in the morning to improve the students’ nutrition. |
| 27 | DMK-2021-0247 | 1 | high | Appoint 3.50 youngsters from Tamil Nadu to the unfilled job vacancies across Tamil Nadu. |
| 28 | DMK-2021-0252 | 1 | high | Set aside 15,000 crores to support the revival of such industries and enable employment opportunities to its employees by providing loans at |
| 29 | DMK-2021-0286 | 1 | high | Enable a user household to save upto 6000 rupees (for <1000 units) annually through this scheme. |
| 30 | DMK-2021-0291 | 1 | high | Take steps to optimise the efficient usage of electricity by replacing the existing traditional power consumption at govt schools, govt coll |

### TVK-2026

| rank | promise | signal | cost | text |
|---:|---|---:|---|---|
| 1 | TVK-2026-0214 | 2 | high | Credit 2500 rupees every month into the bank account of every woman family head until they reach the age of 60. |
| 2 | TVK-2026-0219 | 2 | high | Credit 15 thousand rupees a year in two installments to the bank account of the mother or guardian of students studying from the first stand |
| 3 | TVK-2026-0556 | 2 | high | Provide a 'Makkal Nalan Kaapeedu' card worth Rs. 25 lakh to each family upon the formation of the TVK government. |
| 4 | TVK-2026-0558 | 2 | high | Conduct a free full body check-up once a year for every person in Tamil Nadu. |
| 5 | TVK-2026-0680 | 2 | high | Allocate and spend this fund entirely without any diversion for the equal advancement of women, Scheduled Castes and Scheduled Tribes people |
| 6 | TVK-2026-0087 | 1 | high | Identify poor families in Tamil Nadu and ensure that all government welfare schemes reach them. |
| 7 | TVK-2026-0088 | 1 | high | Create appropriate employment opportunities for them and opportunities to start self-employment, through which their minimum annual income w |
| 8 | TVK-2026-0089 | 1 | high | Provide 200 units of free electricity every month to eligible households. |
| 9 | TVK-2026-0090 | 1 | high | Ensure 100 percent clean drinking water supply to all houses in Tamil Nadu. |
| 10 | TVK-2026-0091 | 1 | high | Build and give 5 lakh new houses so that poor and common people in rural areas can get their own houses. |
| 11 | TVK-2026-0095 | 1 | high | Distribute iron and folic acid-fortified rice, vitamin A and vitamin D-enriched cooking oil, and fortified wheat flour to everyone through r |
| 12 | TVK-2026-0105 | 1 | high | Provide permanent houses and pattas to all Adi Dravidar and Tribal people in Tamil Nadu. |
| 13 | TVK-2026-0119 | 1 | high | Increase the old-age pension to three thousand (Rs 3000) rupees. |
| 14 | TVK-2026-0120 | 1 | high | Arrange to take two and a half lakh senior citizens to pilgrimage destinations of their choice every year. |
| 15 | TVK-2026-0122 | 1 | high | Start 1000 mobile senior citizen clinics across Tamil Nadu for senior citizens. |
| 16 | TVK-2026-0124 | 1 | high | Conduct free physical examinations and provide medicines for chronic diseases by visiting each village panchayat across Tamil Nadu in person |
| 17 | TVK-2026-0125 | 1 | high | Provide ten thousand rupees financial assistance to purchase essential equipment for senior citizens including walking sticks, spectacles, w |
| 18 | TVK-2026-0132 | 1 | high | Increase the monthly pension for differently-abled persons to three thousand (Rs 3000) rupees. |
| 19 | TVK-2026-0133 | 1 | high | Appoint an exclusive teacher for special children in every government school. |
| 20 | TVK-2026-0140 | 1 | high | Provide an annual financial assistance of 30 thousand rupees to each weaver family that owns a loom (power loom/handloom). |
| 21 | TVK-2026-0145 | 1 | high | Provide life insurance worth 10 lakh rupees to all weavers. |
| 22 | TVK-2026-0154 | 1 | high | Establish a Government Employee Welfare Board with an allocation of Rs 5,000 crore to protect the rights and ensure the welfare of governmen |
| 23 | TVK-2026-0176 | 1 | high | Convert all Anganwadi workers into 'Grade - D' government employees and provide them a monthly salary of 18000 rupees on that basis. |
| 24 | TVK-2026-0215 | 1 | high | Deposit the money for purchasing 6 cooking gas cylinders per year directly into the bank account of every family. |
| 25 | TVK-2026-0216 | 1 | high | Implement the Vettri Payanam scheme where women can travel free of charge in all town, city, and inter-district government buses operating a |
| | *below the cap* | | | |
| 26 | TVK-2026-0220 | 1 | high | Provide a monthly financial assistance of 3 thousand rupees to impoverished widows and destitute women. |
| 27 | TVK-2026-0234 | 1 | high | Establish hostels with adequate security and modern facilities for working women and students to stay in important cities across Tamil Nadu. |
| 28 | TVK-2026-0236 | 1 | high | Provide 25 thousand rupees as financial assistance to pregnant women to help them purchase required nutritious foods, undergo monthly medica |
| 29 | TVK-2026-0237 | 1 | high | Establish service and assistance centers for pregnant women named 'Thai Care' across the state. |
| 30 | TVK-2026-0239 | 1 | high | Provide free sanitary napkins for women at ration shops, schools, and colleges. |

## Check failures

| term | by rule | resolution |
|---|---|---|
| AIADMK-2016 | {'C2': 5, 'C5': 1, 'C3': 36, 'C4': 1} | {'retry alone': 29, 'UNRESOLVED': 14} |
| DMK-2021 | {'C3': 52, 'C5': 1} | {'retry alone': 21, 'UNRESOLVED': 32} |
| TVK-2026 | {'C5': 12, 'C3': 71, 'C6': 2, 'C2': 14} | {'retry alone': 68, 'UNRESOLVED': 31} |

