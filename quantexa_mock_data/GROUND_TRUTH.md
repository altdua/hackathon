# Ground truth for matchers (do not show this file in the demo)

Generated 2026-09-10. All people and identifiers are fictitious. NHS numbers, UPRNs and phones are fabricated. Phones use the Ofcom drama range 07700 900xxx.

## Should merge (one person)

Margaret "Maggie" Hale — canonical key suggestion: `person:hale-margaret-1959-03-12`

| Source | How she appears | Link keys |
|---|---|---|
| Housing CSV | `HALE` / `M` / DOB `12/03/1959` / postcode `M46LN` | tenancy T/88421/MCC, tel 07700900441 |
| GP JSON | `Maggie Hale` + old name `Margaret Hale` / `1959-03-12` / `M4 6LN` | **NHS 9434765919 only exists here** |
| Social care | `Hale / female` / `67y female` / `Mar 1959` / address order `Ancoats, 18 Bengal St, Manchester` | Case ASC/26/10994, UPRN 10093022184 |
| Food bank JSONL | `Maggie` / `Mags` + postcode only | 4 visits 28 Jul–8 Sep 2026 |
| Revenues/energy CSV | `HALE M` / `M4 6LN` and `M46LN` / no DOB | CTAX-M4-882341, HEAT-ON-88421, UPRN 10093022184 |

Signals: 4 weeks rent arrears; missed housing visit 20/08/2026; ASB on *property* (complainant is neighbour Okonkwo at 16 Bengal St); 3 GP DNAs; depression flag; lives alone; open low-level ASC with **no allocated worker**; 4 food-bank visits in 6 weeks; CT + heat debt.

## Household / network edge (do not collapse into Maggie)

Daniel Hale, DOB 04/06/1992. Former MCC tenant T/55218/MCC at 41 Wellington Street, Gorton M18 8WU. Evicted 18/04/2024. **Same mobile** 07700900441. CT account CTAX-M18-441900 still in recovery. Separate person.

## Must not merge

| Person | DOB | Address | Why people will get this wrong |
|---|---|---|---|
| John Michael Smith | 1978-01-15 | 9 Bonsall Street, Hulme M15 6EE | Housing `JOHN SMITH` vs GP `John Michael Smith` — **do merge these two sources** |
| John Smith | 1952-11-03 | 9 Bonsall Court, Hulme M15 6EF | Same name, adjacent address, different DOB — **do not merge with the other John Smith** |

## Should merge — person 2

Callum Brennan — `person:brennan-callum-1997-08-14`

| Source | How he appears | Link keys |
|---|---|---|
| Housing CSV | `BRENNAN` / `C` / DOB `14/08/1997` / postcode `M46BN` | tenancy T/90112/MCC, tel 07700900882, NOSP 15/08/2026, 9 weeks arrears |
| GP JSON | `Callum Brennan` + nickname `Cal` / `1997-08-14` / `M4 6BN` | **NHS 6129843301 only here**; anxiety; 2 DNAs |
| Social care | `Brennan / male` / `29y male` / `Aug 1997` / `Ancoats, 11 Poland St, Manchester` | Case ASC/26/14102, UPRN 10093300118, RAG Red, no worker |
| Food bank JSONL | `Callum` / `Cal` + postcode only | 3 visits 30 Jul–5 Sep 2026, Shelter referral |
| Revenues/energy CSV | `BRENNAN C` / `M4 6BN` and `M46BN` / no DOB | CTAX-M4-990441, HEAT-ON-90112, UPRN 10093300118 |

Signals: introductory tenancy + NOSP (homelessness risk); 9 weeks rent arrears; CT + heat debt; 3 food-bank visits; 2 GP DNAs; open ASC housing-related support with no worker.

## Should merge — person 3

Irene / Irena Nwosu — `person:nwosu-irene-1945-01-02`

| Source | How she appears | Link keys |
|---|---|---|
| Housing CSV | `NWOSU` / `I` / DOB `02/01/1945` / postcode `M45AE` | tenancy T/33008/MCC, landline 01612284401 only |
| GP JSON | **`Irena` Nwosu** + old name `Irene` / `1945-01-02` / `M4 5AE` | **NHS 3087765412 only here**; lives alone; hypertension; 2 DNAs |
| Social care | `Nwosu / female` / `81y female` / `Jan 1945` / `Flat 7 Redhill Street, Ancoats Manchester` | Case ASC/26/12880, UPRN 10093411209, no worker |
| Food bank JSONL | `Irene` / `Renie` + postcode only | 2 visits; Age UK; “neighbour brought her” |
| Revenues/energy CSV | `NWOSU I` / `M4 5AE` / no DOB / no energy debt | CTAX-M4-221008, UPRN 10093411209, balance 0 |

Signals: isolation / possible safeguarding concern (neighbour + housing no-access), not rent. GP spelling `Irena` vs food-bank `Renie` is the hard match. Landline only — no mobile shared with anyone else.

## Other decoys

- Aisha Rahman 22/07/1990, 4 Varley Street M40 7QW
- Peter Okonkwo 30/09/1968, 16 Bengal Street M4 6LN (ASB *complainant*, same street)
- Susan Price 19/12/1955, Flat 3 Salisbury House M22 5RF
