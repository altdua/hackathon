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

## Other decoys

- Aisha Rahman 22/07/1990, 4 Varley Street M40 7QW
- Peter Okonkwo 30/09/1968, 16 Bengal Street M4 6LN (ASB *complainant*, same street)
- Susan Price 19/12/1955, Flat 3 Salisbury House M22 5RF
