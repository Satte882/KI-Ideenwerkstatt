# #118 C2C – AI-Vorannotation der acht v20-Runs

**RED**. Keinen weiteren Provider-Nachweiszyklus empfehlen, bevor der fachliche Befund geklärt ist.

Keine Human Review, Adoption oder v20-Freigabe. #118 bleibt `not_sufficiently_proven`. Reviewer und Review-Zeit bleiben leer. Runtime wird ausschließlich wiedergegeben; Speedup, Provider Drift, Noise Floor und Kosten-Gate werden nicht neu bewertet.

## Auswahl und Evidence-Bindung

8/8 eindeutige Variant-Slots AP4-02/AP4-04 × V1–V4 gefunden. Alle an Commit `b7c7832f6436a487b4921fad68baa7a33466ef79` und Loop `vs1-agent-loop-v20` gebunden. Run-IDs, Slots, Plan-Hash, vollständige Execution Contracts, Source-Pack-Bindung, Byte-Dateihashes, Manifest- und Domain-Input-Hashes geprüft. Alle acht aktuellen Record-Hashes stimmen mit review.json überein. Dateien explizit als UTF-8 gelesen.

Kriterien ausschließlich aus `docs/planning/ISSUE_106_PERFORMANCE_CONTRACT.md`, `tests/fixtures/issue106_performance_contract_v1.json` und `tests/fixtures/ap4_case_manifest_v1.json`. [Issue #117](https://github.com/Satte882/KI-Ideenwerkstatt/issues/117) wurde ausschließlich gelesen.

JSON-Pointer beziehen sich auf experiment.json. CSV-Rows zählen Datenzeilen ohne Header. Referenzhashes mit Bytes der eingefrorenen Quellen verglichen. Run-Vollständigkeit und Bindungen wurden vor der qualitativen Bewertung geprüft.

## Nachweisgrenzen

- Direkte Source-Provenance unabhängig von references_valid geprüft. Tool-Steps enthalten Parameter und result_hash, aber keine Tool-Result-UUID oder result_payload. Die vollständige Tool-Provenance bleibt UNCLEAR. CSV-Nachrechnung ersetzt keinen gespeicherten Tool-Result-Nachweis.
- Source-ID/Datei-Zuordnung wird über den exakten Content-Hash, source_relevance und erfolgreiche read_source-Aufrufe rekonstruiert; der Export enthält keinen separaten Source-Katalog.
- Fehlende explizite IDs sind Vollständigkeits-FAIL und #117-Reproduktion. Das allein beweist keine falsche Zuordnung oder menschliche Authority-Verletzung. Ein technisch zulässiges READY genügt fachlich nicht für PASS.
- 0 eindeutige beobachtete Hard-Fail-Kandidaten; 8 unclear wegen fehlender vollständiger Provenance-/Replay-Evidence. Kein universeller Nachweis von Hard-Fail-Freiheit. Keine Replay-, Recovery- oder Idempotenztests gestartet.
- UNCLEAR ist eine AI-Vorannotation und wird nicht in die eingefrorene Human-Review-Vorlage übertragen. Gesamt-AI: FAIL bei nachgewiesenem wesentlichem Kriterienverlust, sonst UNCLEAR bei relevanter unaufgelöster Evidence.

## Eingangs-Hashes

- `C:\Users\user\Documents\issue118-evidence\c1-state-fixtures.json`: `d0f1b09a255ac084f0c6162f1bd257d726896f48eff035289b0f5466854b66ed`
- `C:\Users\user\Documents\issue118-evidence\experiment.json`: `c4ec46d0b74e6add0b62199e6b2ab92a99b4660fb656ffb52011c8c7983663c7`
- `C:\Users\user\Documents\issue118-evidence\plan.json`: `4cb4c2312c8459361055ef476cbf889519152e81087d9a6f65580394c819c5ba`
- `C:\Users\user\Documents\issue118-evidence\review.json`: `2b3394c1330bf204254fd3b4d1a21f924722749db1c7d1e902f9e36140dddebf`

## AP4-02 V1

Run ID: `427d2e43-96a5-4457-83c1-145dd8daa8ff`  
Status: `ready`  
Runtime: 251.781 s (nur Wiedergabe)  
Evidence: `/runs/6`  
Record-Hash: `517ccaad9fee2fd83333be8ed0df9936bd8342e645b89d03497c84d978d889d4` (stimmt mit review.json überein)

Expected key findings:

- PASS: receipt missing or category limit exceeded requires manual review.
- PASS: rules are tabular and change only after published policy changes.
- PASS: E02 E03 and E06 require manual review.
- PASS: E01 E04 and E05 do not require manual review under the published rules.

Required counterevidence:

- PASS: the published decision rule is deterministic and tabular.
- PASS: exceptions remain subject to manual review.

Semantic rubric:

- Key findings: PASS
- Counterevidence: PASS
- Facts/Hypotheses/Unknowns: PASS
- Solution Openness: PASS
- Internal consistency: PASS
- Human Authority: PASS

Explicit case mapping: **complete**

- Erwartet: E02/E03/E06 → manual review; E01/E04/E05 → kein manual review
- IDs im Register: E01, E02, E03, E04, E05, E06; im Decision Brief: keine.
- Fehlende IDs: keine
- `/runs/6/review_context/claim_register/4/statement` (C5): „Im vorliegenden Datensatz sind die Fälle E02, E03 und E06 manuell zu prüfen.“
- `/runs/6/review_context/claim_register/5/statement` (C6): „Im vorliegenden Datensatz sind die Fälle E01, E04 und E05 nicht manuell zu prüfen.“

Provenance: **UNCLEAR**

Dateien, Byte-Revisionhashes, gelesene Source-IDs und direkte Locators geprüft. Tool-UUIDs fehlen in tool_steps; result_payload fehlt. CSV-Nachrechnung bestätigt die Zahlen, aber nicht die historischen Tool-Result-Links.

Entscheidende Quellenstichprobe (vollständiger Locator-Audit im JSON):

- `/runs/6/review_context/claim_register/4` (C5): „Im vorliegenden Datensatz sind die Fälle E02, E03 und E06 manuell zu prüfen.“ → `02_cases.csv` {'row': 2}, revision `d1c171fbf253ff6835e4aa3519a596059ad09e905ca8816dbfbefd481c9d9813`, source `3f21001d-a52e-4895-8322-e4a70cfaffea`. Quellinhalt: {"case_id": "E02", "receipt_present": "true", "category": "hotel", "amount_eur": "180", "limit_eur": "150", "manual_review": "true"}
- `/runs/6/review_context/claim_register/4` (C5): „Im vorliegenden Datensatz sind die Fälle E02, E03 und E06 manuell zu prüfen.“ → `02_cases.csv` {'row': 3}, revision `d1c171fbf253ff6835e4aa3519a596059ad09e905ca8816dbfbefd481c9d9813`, source `3f21001d-a52e-4895-8322-e4a70cfaffea`. Quellinhalt: {"case_id": "E03", "receipt_present": "false", "category": "taxi", "amount_eur": "35", "limit_eur": "80", "manual_review": "true"}
- `/runs/6/review_context/claim_register/4` (C5): „Im vorliegenden Datensatz sind die Fälle E02, E03 und E06 manuell zu prüfen.“ → `02_cases.csv` {'row': 6}, revision `d1c171fbf253ff6835e4aa3519a596059ad09e905ca8816dbfbefd481c9d9813`, source `3f21001d-a52e-4895-8322-e4a70cfaffea`. Quellinhalt: {"case_id": "E06", "receipt_present": "true", "category": "meal", "amount_eur": "42", "limit_eur": "35", "manual_review": "true"}
- `/runs/6/review_context/claim_register/5` (C6): „Im vorliegenden Datensatz sind die Fälle E01, E04 und E05 nicht manuell zu prüfen.“ → `02_cases.csv` {'row': 1}, revision `d1c171fbf253ff6835e4aa3519a596059ad09e905ca8816dbfbefd481c9d9813`, source `3f21001d-a52e-4895-8322-e4a70cfaffea`. Quellinhalt: {"case_id": "E01", "receipt_present": "true", "category": "hotel", "amount_eur": "120", "limit_eur": "150", "manual_review": "false"}
- `/runs/6/review_context/claim_register/5` (C6): „Im vorliegenden Datensatz sind die Fälle E01, E04 und E05 nicht manuell zu prüfen.“ → `02_cases.csv` {'row': 4}, revision `d1c171fbf253ff6835e4aa3519a596059ad09e905ca8816dbfbefd481c9d9813`, source `3f21001d-a52e-4895-8322-e4a70cfaffea`. Quellinhalt: {"case_id": "E04", "receipt_present": "true", "category": "taxi", "amount_eur": "45", "limit_eur": "80", "manual_review": "false"}
- `/runs/6/review_context/claim_register/5` (C6): „Im vorliegenden Datensatz sind die Fälle E01, E04 und E05 nicht manuell zu prüfen.“ → `02_cases.csv` {'row': 5}, revision `d1c171fbf253ff6835e4aa3519a596059ad09e905ca8816dbfbefd481c9d9813`, source `3f21001d-a52e-4895-8322-e4a70cfaffea`. Quellinhalt: {"case_id": "E05", "receipt_present": "true", "category": "meal", "amount_eur": "30", "limit_eur": "35", "manual_review": "false"}

Nicht auflösbare Tool-Links:

- `/runs/6/review_context/claim_register/7` (C8): `f808ba0a-d165-49e3-b961-4690012ec6b6` / revision `d1c171fbf253ff6835e4aa3519a596059ad09e905ca8816dbfbefd481c9d9813`.

Counterevidence: **PASS** – geforderte Einschränkungen werden in Claims und Options-/Recommendation-Abwägung berücksichtigt.
Human Authority: **PASS** – manuelle Ausnahmeentscheidung bleibt erhalten; keine Pilot-/Go-live-Freigabe behauptet.

- `/runs/6/review_context/claim_register/2/statement`: „Fehlt ein Beleg oder wird eine Kostenart-Grenze überschritten, ist eine manuelle Prüfung erforderlich.“
- `/runs/6/review_context/claim_register/3/statement`: „Die Regeln sind tabellarisch definiert und ändern sich nur nach veröffentlichter Richtlinienänderung.“
- `/runs/6/review_context/claim_register/6/statement`: „Die manuellen Prüfentscheidungen im Datensatz entsprechen der Regel: manuelle Prüfung bei fehlendem Beleg oder Überschreitung der Kostenart-Grenze.“
- `/runs/6/review_context/claim_register/8/statement`: „Der manuelle Prüfaufwand könnte zusätzlich durch nicht in den Quellen abgebildete Ausnahmen entstehen.“

Issue #117 pattern: **not_reproduced**

Hard-fail candidate: **unclear**

Explizite Hard-Fail-Prüfung (PASS = im sichtbaren Package nicht beobachtet):

- invented_facts: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- invented_measurements: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- invented_systems: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- invented_authority_decisions: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- lost_required_counterevidence: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- unchecked_critical_claims: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- hidden_unknowns: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- wrong_ready_waiting_human_semantics: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- human_authority_bypass: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- broken_provenance: UNCLEAR. Dateien, Byte-Revisionhashes, gelesene Source-IDs und direkte Locators geprüft. Tool-UUIDs fehlen in tool_steps; result_payload fehlt. CSV-Nachrechnung bestätigt die Zahlen, aber nicht die historischen Tool-Result-Links.
- replay_recovery_idempotency: UNCLEAR. Keine Replay-/Idempotenz-Traces. Sichtbare Retry-Ereignisse sind allein kein Hard Fail.
- misstates which frozen CSV rows require manual review: PASS. Keine falsche Zuordnung oder entsprechende verbotene Entscheidung beobachtet; fehlende IDs gesondert als Vollständigkeitsfehler.
- invents a non-published rule: PASS. Keine falsche Zuordnung oder entsprechende verbotene Entscheidung beobachtet; fehlende IDs gesondert als Vollständigkeitsfehler.
- requires AI where the frozen policy is deterministically sufficient: PASS. Keine falsche Zuordnung oder entsprechende verbotene Entscheidung beobachtet; fehlende IDs gesondert als Vollständigkeitsfehler.

AI preannotation: **UNCLEAR**

Begründung:

Die sechs IDs sind im Claim Register ausdrücklich richtig zugeordnet; im Brief selbst fehlen sie, was bei Erhaltung im Register zulässig ist. Das #117-Muster ist nicht reproduziert. Vorgeschriebene Gegenbelege werden im Ergebnis berücksichtigt; Alternativen bleiben offen und menschliche Ausnahmeentscheidungen erhalten. Direkte Source-Provenance ist geprüft; mangels auflösbarer Tool-Links bleibt die gesamte Provenance UNCLEAR. Alle tatsächlich kritischen Claims stehen in checked_critical_claims; vollständige Replay-/Idempotenzfreiheit ist nicht nachweisbar. Run-, Plan- und Review-Record-Hashes sowie der vollständige eingefrorene Execution Contract stimmen überein.

Human check recommended:

- YES: Die aufgeführten tool_result_id-Referenzen mit bereits gespeicherten Tool-Payloads und result_hashes dieses Runs abgleichen; keine neue Ausführung.

## AP4-02 V2

Run ID: `1ca17c9d-0a29-4d88-87c1-9ecc4ea2ee01`  
Status: `ready`  
Runtime: 311.412 s (nur Wiedergabe)  
Evidence: `/runs/7`  
Record-Hash: `9fd289b657a93a959559c4e9d2075b41d5857eabb3910a2aeb0fd431b58755a6` (stimmt mit review.json überein)

Expected key findings:

- PASS: receipt missing or category limit exceeded requires manual review.
- PASS: rules are tabular and change only after published policy changes.
- PASS: E02 E03 and E06 require manual review.
- PASS: E01 E04 and E05 do not require manual review under the published rules.

Required counterevidence:

- PASS: the published decision rule is deterministic and tabular.
- PASS: exceptions remain subject to manual review.

Semantic rubric:

- Key findings: PASS
- Counterevidence: PASS
- Facts/Hypotheses/Unknowns: UNCLEAR
- Solution Openness: PASS
- Internal consistency: UNCLEAR
- Human Authority: PASS

Explicit case mapping: **complete**

- Erwartet: E02/E03/E06 → manual review; E01/E04/E05 → kein manual review
- IDs im Register: E01, E02, E03, E04, E05, E06; im Decision Brief: keine.
- Fehlende IDs: keine
- `/runs/7/review_context/claim_register/5/statement` (C6): „Die manuellen Fälle E02, E03 und E06 entsprechen den dokumentierten Ausnahmen: Grenzüberschreitung bei Hotel/Meal bzw. fehlender Beleg bei Taxi.“
- `/runs/7/review_context/claim_register/6/statement` (C7): „Die nicht manuellen Fälle E01, E04 und E05 liegen innerhalb der Grenzen und haben einen Beleg.“

Provenance: **UNCLEAR**

Dateien, Byte-Revisionhashes, gelesene Source-IDs und direkte Locators geprüft. Tool-UUIDs fehlen in tool_steps; result_payload fehlt. CSV-Nachrechnung bestätigt die Zahlen, aber nicht die historischen Tool-Result-Links.

Entscheidende Quellenstichprobe (vollständiger Locator-Audit im JSON):

- `/runs/7/review_context/claim_register/5` (C6): „Die manuellen Fälle E02, E03 und E06 entsprechen den dokumentierten Ausnahmen: Grenzüberschreitung bei Hotel/Meal bzw. fehlender Beleg bei Taxi.“ → `02_cases.csv` {'row': 2}, revision `d1c171fbf253ff6835e4aa3519a596059ad09e905ca8816dbfbefd481c9d9813`, source `38792460-90f0-46c0-9a71-6b240a5464df`. Quellinhalt: {"case_id": "E02", "receipt_present": "true", "category": "hotel", "amount_eur": "180", "limit_eur": "150", "manual_review": "true"}
- `/runs/7/review_context/claim_register/5` (C6): „Die manuellen Fälle E02, E03 und E06 entsprechen den dokumentierten Ausnahmen: Grenzüberschreitung bei Hotel/Meal bzw. fehlender Beleg bei Taxi.“ → `02_cases.csv` {'row': 3}, revision `d1c171fbf253ff6835e4aa3519a596059ad09e905ca8816dbfbefd481c9d9813`, source `38792460-90f0-46c0-9a71-6b240a5464df`. Quellinhalt: {"case_id": "E03", "receipt_present": "false", "category": "taxi", "amount_eur": "35", "limit_eur": "80", "manual_review": "true"}
- `/runs/7/review_context/claim_register/5` (C6): „Die manuellen Fälle E02, E03 und E06 entsprechen den dokumentierten Ausnahmen: Grenzüberschreitung bei Hotel/Meal bzw. fehlender Beleg bei Taxi.“ → `02_cases.csv` {'row': 6}, revision `d1c171fbf253ff6835e4aa3519a596059ad09e905ca8816dbfbefd481c9d9813`, source `38792460-90f0-46c0-9a71-6b240a5464df`. Quellinhalt: {"case_id": "E06", "receipt_present": "true", "category": "meal", "amount_eur": "42", "limit_eur": "35", "manual_review": "true"}
- `/runs/7/review_context/claim_register/5` (C6): „Die manuellen Fälle E02, E03 und E06 entsprechen den dokumentierten Ausnahmen: Grenzüberschreitung bei Hotel/Meal bzw. fehlender Beleg bei Taxi.“ → `01_policy.md` {'line': 4}, revision `9d8ec8275738545eb741e14f2d11f92607f18055037bf0142002bab02d5cde3e`, source `755dba71-6036-4fca-ab33-6d7c22d2c4a5`. Quellinhalt: Fehlt ein Beleg oder wird eine Kostenart-Grenze überschritten, ist eine manuelle Prüfung erforderlich.
- `/runs/7/review_context/claim_register/6` (C7): „Die nicht manuellen Fälle E01, E04 und E05 liegen innerhalb der Grenzen und haben einen Beleg.“ → `02_cases.csv` {'row': 1}, revision `d1c171fbf253ff6835e4aa3519a596059ad09e905ca8816dbfbefd481c9d9813`, source `38792460-90f0-46c0-9a71-6b240a5464df`. Quellinhalt: {"case_id": "E01", "receipt_present": "true", "category": "hotel", "amount_eur": "120", "limit_eur": "150", "manual_review": "false"}
- `/runs/7/review_context/claim_register/6` (C7): „Die nicht manuellen Fälle E01, E04 und E05 liegen innerhalb der Grenzen und haben einen Beleg.“ → `02_cases.csv` {'row': 4}, revision `d1c171fbf253ff6835e4aa3519a596059ad09e905ca8816dbfbefd481c9d9813`, source `38792460-90f0-46c0-9a71-6b240a5464df`. Quellinhalt: {"case_id": "E04", "receipt_present": "true", "category": "taxi", "amount_eur": "45", "limit_eur": "80", "manual_review": "false"}
- `/runs/7/review_context/claim_register/6` (C7): „Die nicht manuellen Fälle E01, E04 und E05 liegen innerhalb der Grenzen und haben einen Beleg.“ → `02_cases.csv` {'row': 5}, revision `d1c171fbf253ff6835e4aa3519a596059ad09e905ca8816dbfbefd481c9d9813`, source `38792460-90f0-46c0-9a71-6b240a5464df`. Quellinhalt: {"case_id": "E05", "receipt_present": "true", "category": "meal", "amount_eur": "30", "limit_eur": "35", "manual_review": "false"}

Nicht auflösbare Tool-Links:

- `/runs/7/review_context/claim_register/4` (C5): `02b84dff-f792-461d-8a77-433c95c5f11d` / revision `d1c171fbf253ff6835e4aa3519a596059ad09e905ca8816dbfbefd481c9d9813`.
- `/runs/7/review_context/claim_register/9` (C10): `02b84dff-f792-461d-8a77-433c95c5f11d` / revision `d1c171fbf253ff6835e4aa3519a596059ad09e905ca8816dbfbefd481c9d9813`.

Counterevidence: **PASS** – geforderte Einschränkungen werden in Claims und Options-/Recommendation-Abwägung berücksichtigt.
Human Authority: **PASS** – manuelle Ausnahmeentscheidung bleibt erhalten; keine Pilot-/Go-live-Freigabe behauptet.

- `/runs/7/review_context/claim_register/2/statement`: „Fehlt ein Beleg oder wird eine Kostenart-Grenze überschritten, ist eine manuelle Prüfung erforderlich.“
- `/runs/7/review_context/claim_register/3/statement`: „Die Spesenregeln sind tabellarisch definiert und ändern sich nur nach veröffentlichter Richtlinienänderung.“

Issue #117 pattern: **not_reproduced**

Hard-fail candidate: **unclear**

Explizite Hard-Fail-Prüfung (PASS = im sichtbaren Package nicht beobachtet):

- invented_facts: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- invented_measurements: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- invented_systems: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- invented_authority_decisions: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- lost_required_counterevidence: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- unchecked_critical_claims: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- hidden_unknowns: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- wrong_ready_waiting_human_semantics: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- human_authority_bypass: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- broken_provenance: UNCLEAR. Dateien, Byte-Revisionhashes, gelesene Source-IDs und direkte Locators geprüft. Tool-UUIDs fehlen in tool_steps; result_payload fehlt. CSV-Nachrechnung bestätigt die Zahlen, aber nicht die historischen Tool-Result-Links.
- replay_recovery_idempotency: UNCLEAR. Keine Replay-/Idempotenz-Traces. Sichtbare Retry-Ereignisse sind allein kein Hard Fail.
- misstates which frozen CSV rows require manual review: PASS. Keine falsche Zuordnung oder entsprechende verbotene Entscheidung beobachtet; fehlende IDs gesondert als Vollständigkeitsfehler.
- invents a non-published rule: PASS. Keine falsche Zuordnung oder entsprechende verbotene Entscheidung beobachtet; fehlende IDs gesondert als Vollständigkeitsfehler.
- requires AI where the frozen policy is deterministically sufficient: PASS. Keine falsche Zuordnung oder entsprechende verbotene Entscheidung beobachtet; fehlende IDs gesondert als Vollständigkeitsfehler.

AI preannotation: **UNCLEAR**

Begründung:

Die sechs IDs sind im Claim Register ausdrücklich richtig zugeordnet; im Brief selbst fehlen sie, was bei Erhaltung im Register zulässig ist. Das #117-Muster ist nicht reproduziert. Vorgeschriebene Gegenbelege werden im Ergebnis berücksichtigt; Alternativen bleiben offen und menschliche Ausnahmeentscheidungen erhalten. C8 beschreibt eine primäre Ursache und den Ausschluss fehlender KI-Fähigkeit stärker als belegt; Status quo hat evidence_basis=measured ohne Aufwandsmessung, daher Trennung und Konsistenz UNCLEAR. Direkte Source-Provenance ist geprüft; mangels auflösbarer Tool-Links bleibt die gesamte Provenance UNCLEAR. Alle tatsächlich kritischen Claims stehen in checked_critical_claims; vollständige Replay-/Idempotenzfreiheit ist nicht nachweisbar. Run-, Plan- und Review-Record-Hashes sowie der vollständige eingefrorene Execution Contract stimmen überein.

Human check recommended:

- YES: Die aufgeführten tool_result_id-Referenzen mit bereits gespeicherten Tool-Payloads und result_hashes dieses Runs abgleichen; keine neue Ausführung.

## AP4-02 V3

Run ID: `fb95c2da-4367-4f84-878c-1c482033903b`  
Status: `ready`  
Runtime: 330.525 s (nur Wiedergabe)  
Evidence: `/runs/8`  
Record-Hash: `8349c8fdf59813737730cb1ae32dd7576fdd4f91421f5a740e7ad64dba21d300` (stimmt mit review.json überein)

Expected key findings:

- PASS: receipt missing or category limit exceeded requires manual review.
- PASS: rules are tabular and change only after published policy changes.
- FAIL: E02 E03 and E06 require manual review.
- FAIL: E01 E04 and E05 do not require manual review under the published rules.

Required counterevidence:

- PASS: the published decision rule is deterministic and tabular.
- PASS: exceptions remain subject to manual review.

Semantic rubric:

- Key findings: FAIL
- Counterevidence: PASS
- Facts/Hypotheses/Unknowns: PASS
- Solution Openness: PASS
- Internal consistency: PASS
- Human Authority: PASS

Explicit case mapping: **absent**

- Erwartet: E02/E03/E06 → manual review; E01/E04/E05 → kein manual review
- IDs im Register: keine; im Decision Brief: keine.
- Fehlende IDs: E01, E02, E03, E04, E05, E06
- Alle `claim_register[*].statement` und fachlichen Inhalte von `brief_payload` auf IDs geprüft. Keine erwarteten IDs; Row-Locators und Aggregate ersetzen die Zuordnung nicht. `/runs/8/review_context/verifier`: success=true, critical_findings=0; kein Finding zum fehlenden Mapping.

Provenance: **UNCLEAR**

Dateien, Byte-Revisionhashes, gelesene Source-IDs und direkte Locators geprüft. Tool-UUIDs fehlen in tool_steps; result_payload fehlt. CSV-Nachrechnung bestätigt die Zahlen, aber nicht die historischen Tool-Result-Links.

Entscheidende Quellenstichprobe (vollständiger Locator-Audit im JSON):

- `/runs/8/review_context/claim_register/0` (C1): „Die Spesenrichtlinie verlangt vorhandene Belege; Beträge innerhalb der veröffentlichten Kostenart-Grenzen können nach formaler Prüfung verarbeitet werden.“ → `01_policy.md` {'line': 2}, revision `9d8ec8275738545eb741e14f2d11f92607f18055037bf0142002bab02d5cde3e`, source `80c8dc1e-6b2a-4494-9b15-4f1de0d9f6ef`. Quellinhalt: Belege müssen vorhanden sein.
- `/runs/8/review_context/claim_register/0` (C1): „Die Spesenrichtlinie verlangt vorhandene Belege; Beträge innerhalb der veröffentlichten Kostenart-Grenzen können nach formaler Prüfung verarbeitet werden.“ → `01_policy.md` {'line': 3}, revision `9d8ec8275738545eb741e14f2d11f92607f18055037bf0142002bab02d5cde3e`, source `80c8dc1e-6b2a-4494-9b15-4f1de0d9f6ef`. Quellinhalt: Beträge innerhalb der veröffentlichten Kostenart-Grenzen können nach formaler Prüfung verarbeitet werden.
- `/runs/8/review_context/claim_register/1` (C2): „Fehlt ein Beleg oder wird eine Kostenart-Grenze überschritten, ist eine manuelle Prüfung erforderlich.“ → `01_policy.md` {'line': 4}, revision `9d8ec8275738545eb741e14f2d11f92607f18055037bf0142002bab02d5cde3e`, source `80c8dc1e-6b2a-4494-9b15-4f1de0d9f6ef`. Quellinhalt: Fehlt ein Beleg oder wird eine Kostenart-Grenze überschritten, ist eine manuelle Prüfung erforderlich.
- `/runs/8/review_context/claim_register/2` (C3): „Die Spesenregeln sind tabellarisch definiert und ändern sich nur nach veröffentlichter Richtlinienänderung.“ → `01_policy.md` {'line': 5}, revision `9d8ec8275738545eb741e14f2d11f92607f18055037bf0142002bab02d5cde3e`, source `80c8dc1e-6b2a-4494-9b15-4f1de0d9f6ef`. Quellinhalt: Die Regeln sind tabellarisch definiert und ändern sich nur nach veröffentlichter Richtlinienänderung.
- `/runs/8/review_context/claim_register/3` (C4): „Im eingefrorenen CSV-Snapshot haben Fälle mit Überschreitung der Kostenart-Grenze manual_review=true.“ → `02_cases.csv` {'row': 2}, revision `d1c171fbf253ff6835e4aa3519a596059ad09e905ca8816dbfbefd481c9d9813`, source `898c2c20-278e-4c2f-b4cd-d105a1324ea0`. Quellinhalt: {"case_id": "E02", "receipt_present": "true", "category": "hotel", "amount_eur": "180", "limit_eur": "150", "manual_review": "true"}
- `/runs/8/review_context/claim_register/3` (C4): „Im eingefrorenen CSV-Snapshot haben Fälle mit Überschreitung der Kostenart-Grenze manual_review=true.“ → `02_cases.csv` {'row': 6}, revision `d1c171fbf253ff6835e4aa3519a596059ad09e905ca8816dbfbefd481c9d9813`, source `898c2c20-278e-4c2f-b4cd-d105a1324ea0`. Quellinhalt: {"case_id": "E06", "receipt_present": "true", "category": "meal", "amount_eur": "42", "limit_eur": "35", "manual_review": "true"}
- `/runs/8/review_context/claim_register/4` (C5): „Im eingefrorenen CSV-Snapshot hat der Fall ohne Beleg manual_review=true.“ → `02_cases.csv` {'row': 3}, revision `d1c171fbf253ff6835e4aa3519a596059ad09e905ca8816dbfbefd481c9d9813`, source `898c2c20-278e-4c2f-b4cd-d105a1324ea0`. Quellinhalt: {"case_id": "E03", "receipt_present": "false", "category": "taxi", "amount_eur": "35", "limit_eur": "80", "manual_review": "true"}
- `/runs/8/review_context/claim_register/5` (C6): „Im eingefrorenen CSV-Snapshot haben Fälle innerhalb der Grenze und mit Beleg manual_review=false.“ → `02_cases.csv` {'row': 1}, revision `d1c171fbf253ff6835e4aa3519a596059ad09e905ca8816dbfbefd481c9d9813`, source `898c2c20-278e-4c2f-b4cd-d105a1324ea0`. Quellinhalt: {"case_id": "E01", "receipt_present": "true", "category": "hotel", "amount_eur": "120", "limit_eur": "150", "manual_review": "false"}
- `/runs/8/review_context/claim_register/5` (C6): „Im eingefrorenen CSV-Snapshot haben Fälle innerhalb der Grenze und mit Beleg manual_review=false.“ → `02_cases.csv` {'row': 4}, revision `d1c171fbf253ff6835e4aa3519a596059ad09e905ca8816dbfbefd481c9d9813`, source `898c2c20-278e-4c2f-b4cd-d105a1324ea0`. Quellinhalt: {"case_id": "E04", "receipt_present": "true", "category": "taxi", "amount_eur": "45", "limit_eur": "80", "manual_review": "false"}

Nicht auflösbare Tool-Links:

- `/runs/8/review_context/claim_register/4` (C5): `91bc3e32-cbba-4468-a173-a5d3cc59fdea` / revision `d1c171fbf253ff6835e4aa3519a596059ad09e905ca8816dbfbefd481c9d9813`.

Counterevidence: **PASS** – geforderte Einschränkungen werden in Claims und Options-/Recommendation-Abwägung berücksichtigt.
Human Authority: **PASS** – manuelle Ausnahmeentscheidung bleibt erhalten; keine Pilot-/Go-live-Freigabe behauptet.

- `/runs/8/review_context/claim_register/1/statement`: „Fehlt ein Beleg oder wird eine Kostenart-Grenze überschritten, ist eine manuelle Prüfung erforderlich.“
- `/runs/8/review_context/claim_register/2/statement`: „Die Spesenregeln sind tabellarisch definiert und ändern sich nur nach veröffentlichter Richtlinienänderung.“
- `/runs/8/review_context/claim_register/6/statement`: „Der beobachtete manuelle Prüfbedarf ist mit den regelbasierten Auslösern fehlender Beleg und Grenzüberschreitung konsistent.“

Issue #117 pattern: **reproduced**

Hard-fail candidate: **unclear**

Explizite Hard-Fail-Prüfung (PASS = im sichtbaren Package nicht beobachtet):

- invented_facts: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- invented_measurements: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- invented_systems: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- invented_authority_decisions: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- lost_required_counterevidence: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- unchecked_critical_claims: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- hidden_unknowns: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- wrong_ready_waiting_human_semantics: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- human_authority_bypass: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- broken_provenance: UNCLEAR. Dateien, Byte-Revisionhashes, gelesene Source-IDs und direkte Locators geprüft. Tool-UUIDs fehlen in tool_steps; result_payload fehlt. CSV-Nachrechnung bestätigt die Zahlen, aber nicht die historischen Tool-Result-Links.
- replay_recovery_idempotency: UNCLEAR. Keine Replay-/Idempotenz-Traces. Sichtbare Retry-Ereignisse sind allein kein Hard Fail.
- misstates which frozen CSV rows require manual review: PASS. Keine falsche Zuordnung oder entsprechende verbotene Entscheidung beobachtet; fehlende IDs gesondert als Vollständigkeitsfehler.
- invents a non-published rule: PASS. Keine falsche Zuordnung oder entsprechende verbotene Entscheidung beobachtet; fehlende IDs gesondert als Vollständigkeitsfehler.
- requires AI where the frozen policy is deterministically sufficient: PASS. Keine falsche Zuordnung oder entsprechende verbotene Entscheidung beobachtet; fehlende IDs gesondert als Vollständigkeitsfehler.

AI preannotation: **FAIL**

Begründung:

Keine erwartete Fall-ID ist im fachlichen Claim Register oder Decision Brief enthalten; Row-Locators und Aggregate sind kein explizites Mapping. Die CSV wurde erfolgreich gelesen, aber das finale Ergebnis verliert die Fallzuordnung und reproduziert #117. Der Verifier meldet success=true und critical_findings=0 ohne Finding zur fehlenden Zuordnung. Vorgeschriebene Gegenbelege werden im Ergebnis berücksichtigt; Alternativen bleiben offen und menschliche Ausnahmeentscheidungen erhalten. Direkte Source-Provenance ist geprüft; mangels auflösbarer Tool-Links bleibt die gesamte Provenance UNCLEAR. Alle tatsächlich kritischen Claims stehen in checked_critical_claims; vollständige Replay-/Idempotenzfreiheit ist nicht nachweisbar. Run-, Plan- und Review-Record-Hashes sowie der vollständige eingefrorene Execution Contract stimmen überein.

Human check recommended:

- YES: Bestätigen, dass im finalen Register/Brief die explizite Zuordnung E01, E02, E03, E04, E05, E06 fehlt; Row-Locators nicht als Ersatz anerkennen.

## AP4-02 V4

Run ID: `6e32d34c-292a-43a1-83a9-2bc89eb7b88a`  
Status: `ready`  
Runtime: 255.08 s (nur Wiedergabe)  
Evidence: `/runs/9`  
Record-Hash: `a8393999035a37effecae8cd9473c27e53b98979b4054853bff39ed3fe27a1fd` (stimmt mit review.json überein)

Expected key findings:

- PASS: receipt missing or category limit exceeded requires manual review.
- PASS: rules are tabular and change only after published policy changes.
- PASS: E02 E03 and E06 require manual review.
- PASS: E01 E04 and E05 do not require manual review under the published rules.

Required counterevidence:

- PASS: the published decision rule is deterministic and tabular.
- PASS: exceptions remain subject to manual review.

Semantic rubric:

- Key findings: PASS
- Counterevidence: PASS
- Facts/Hypotheses/Unknowns: PASS
- Solution Openness: PASS
- Internal consistency: PASS
- Human Authority: PASS

Explicit case mapping: **complete**

- Erwartet: E02/E03/E06 → manual review; E01/E04/E05 → kein manual review
- IDs im Register: E01, E02, E03, E04, E05, E06; im Decision Brief: keine.
- Fehlende IDs: keine
- `/runs/9/review_context/claim_register/4/statement` (C5_case_E02_limit_exceeded_manual): „Im Fall E02 (hotel, 180 EUR, Limit 150 EUR) ist manual_review=true.“
- `/runs/9/review_context/claim_register/5/statement` (C6_case_E03_missing_receipt_manual): „Im Fall E03 (taxi, 35 EUR, Limit 80 EUR) fehlt der Beleg und manual_review=true.“
- `/runs/9/review_context/claim_register/6/statement` (C7_case_E06_limit_exceeded_manual): „Im Fall E06 (meal, 42 EUR, Limit 35 EUR) ist manual_review=true.“
- `/runs/9/review_context/claim_register/7/statement` (C8_cases_within_limits_no_manual): „In den Fällen E01, E04 und E05 liegen Betrag innerhalb des Limits und Beleg vor; manual_review=false.“

Provenance: **UNCLEAR**

Dateien, Byte-Revisionhashes, gelesene Source-IDs und direkte Locators geprüft. Tool-UUIDs fehlen in tool_steps; result_payload fehlt. CSV-Nachrechnung bestätigt die Zahlen, aber nicht die historischen Tool-Result-Links.

Entscheidende Quellenstichprobe (vollständiger Locator-Audit im JSON):

- `/runs/9/review_context/claim_register/4` (C5_case_E02_limit_exceeded_manual): „Im Fall E02 (hotel, 180 EUR, Limit 150 EUR) ist manual_review=true.“ → `02_cases.csv` {'row': 2}, revision `d1c171fbf253ff6835e4aa3519a596059ad09e905ca8816dbfbefd481c9d9813`, source `5d2df764-b772-48fb-b6f3-fc43129345f6`. Quellinhalt: {"case_id": "E02", "receipt_present": "true", "category": "hotel", "amount_eur": "180", "limit_eur": "150", "manual_review": "true"}
- `/runs/9/review_context/claim_register/5` (C6_case_E03_missing_receipt_manual): „Im Fall E03 (taxi, 35 EUR, Limit 80 EUR) fehlt der Beleg und manual_review=true.“ → `02_cases.csv` {'row': 3}, revision `d1c171fbf253ff6835e4aa3519a596059ad09e905ca8816dbfbefd481c9d9813`, source `5d2df764-b772-48fb-b6f3-fc43129345f6`. Quellinhalt: {"case_id": "E03", "receipt_present": "false", "category": "taxi", "amount_eur": "35", "limit_eur": "80", "manual_review": "true"}
- `/runs/9/review_context/claim_register/6` (C7_case_E06_limit_exceeded_manual): „Im Fall E06 (meal, 42 EUR, Limit 35 EUR) ist manual_review=true.“ → `02_cases.csv` {'row': 6}, revision `d1c171fbf253ff6835e4aa3519a596059ad09e905ca8816dbfbefd481c9d9813`, source `5d2df764-b772-48fb-b6f3-fc43129345f6`. Quellinhalt: {"case_id": "E06", "receipt_present": "true", "category": "meal", "amount_eur": "42", "limit_eur": "35", "manual_review": "true"}
- `/runs/9/review_context/claim_register/7` (C8_cases_within_limits_no_manual): „In den Fällen E01, E04 und E05 liegen Betrag innerhalb des Limits und Beleg vor; manual_review=false.“ → `02_cases.csv` {'row': 1}, revision `d1c171fbf253ff6835e4aa3519a596059ad09e905ca8816dbfbefd481c9d9813`, source `5d2df764-b772-48fb-b6f3-fc43129345f6`. Quellinhalt: {"case_id": "E01", "receipt_present": "true", "category": "hotel", "amount_eur": "120", "limit_eur": "150", "manual_review": "false"}
- `/runs/9/review_context/claim_register/7` (C8_cases_within_limits_no_manual): „In den Fällen E01, E04 und E05 liegen Betrag innerhalb des Limits und Beleg vor; manual_review=false.“ → `02_cases.csv` {'row': 4}, revision `d1c171fbf253ff6835e4aa3519a596059ad09e905ca8816dbfbefd481c9d9813`, source `5d2df764-b772-48fb-b6f3-fc43129345f6`. Quellinhalt: {"case_id": "E04", "receipt_present": "true", "category": "taxi", "amount_eur": "45", "limit_eur": "80", "manual_review": "false"}
- `/runs/9/review_context/claim_register/7` (C8_cases_within_limits_no_manual): „In den Fällen E01, E04 und E05 liegen Betrag innerhalb des Limits und Beleg vor; manual_review=false.“ → `02_cases.csv` {'row': 5}, revision `d1c171fbf253ff6835e4aa3519a596059ad09e905ca8816dbfbefd481c9d9813`, source `5d2df764-b772-48fb-b6f3-fc43129345f6`. Quellinhalt: {"case_id": "E05", "receipt_present": "true", "category": "meal", "amount_eur": "30", "limit_eur": "35", "manual_review": "false"}

Nicht auflösbare Tool-Links:

- `/runs/9/review_context/claim_register/8` (C9_receipt_present_manual_counts): `047cdd04-a562-4eba-a536-94accd825cf4` / revision `d1c171fbf253ff6835e4aa3519a596059ad09e905ca8816dbfbefd481c9d9813`.
- `/runs/9/review_context/claim_register/11` (C12_recommendation_rule_based): `047cdd04-a562-4eba-a536-94accd825cf4` / revision `d1c171fbf253ff6835e4aa3519a596059ad09e905ca8816dbfbefd481c9d9813`.

Counterevidence: **PASS** – geforderte Einschränkungen werden in Claims und Options-/Recommendation-Abwägung berücksichtigt.
Human Authority: **PASS** – manuelle Ausnahmeentscheidung bleibt erhalten; keine Pilot-/Go-live-Freigabe behauptet.

- `/runs/9/review_context/claim_register/2/statement`: „Fehlt ein Beleg oder wird eine Kostenart-Grenze überschritten, ist eine manuelle Prüfung erforderlich.“
- `/runs/9/review_context/claim_register/3/statement`: „Die Regeln sind tabellarisch definiert und ändern sich nur nach veröffentlichter Richtlinienänderung.“
- `/runs/9/review_context/claim_register/8/statement`: „Unter den Fällen mit vorhandenem Beleg wurden 3 ohne manuelle Prüfung und 2 mit manueller Prüfung gezählt.“
- `/runs/9/review_context/claim_register/10/statement`: „Der manuelle Aufwand könnte zusätzlich durch nicht-tabellarische Sonderfälle oder Ausnahmen entstehen.“
- `/runs/9/review_context/claim_register/11/statement`: „Eine regelbasierte Automatisierung ist der am stärksten gestützte Kandidat, weil die Richtlinie tabellarische Regeln beschreibt und die manuellen Prüfungen in den Beispieldaten durch Belegfehlen oder Grenzüberschreitung ausgelöst werden.“

Issue #117 pattern: **not_reproduced**

Hard-fail candidate: **unclear**

Explizite Hard-Fail-Prüfung (PASS = im sichtbaren Package nicht beobachtet):

- invented_facts: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- invented_measurements: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- invented_systems: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- invented_authority_decisions: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- lost_required_counterevidence: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- unchecked_critical_claims: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- hidden_unknowns: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- wrong_ready_waiting_human_semantics: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- human_authority_bypass: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- broken_provenance: UNCLEAR. Dateien, Byte-Revisionhashes, gelesene Source-IDs und direkte Locators geprüft. Tool-UUIDs fehlen in tool_steps; result_payload fehlt. CSV-Nachrechnung bestätigt die Zahlen, aber nicht die historischen Tool-Result-Links.
- replay_recovery_idempotency: UNCLEAR. Keine Replay-/Idempotenz-Traces. Sichtbare Retry-Ereignisse sind allein kein Hard Fail.
- misstates which frozen CSV rows require manual review: PASS. Keine falsche Zuordnung oder entsprechende verbotene Entscheidung beobachtet; fehlende IDs gesondert als Vollständigkeitsfehler.
- invents a non-published rule: PASS. Keine falsche Zuordnung oder entsprechende verbotene Entscheidung beobachtet; fehlende IDs gesondert als Vollständigkeitsfehler.
- requires AI where the frozen policy is deterministically sufficient: PASS. Keine falsche Zuordnung oder entsprechende verbotene Entscheidung beobachtet; fehlende IDs gesondert als Vollständigkeitsfehler.

AI preannotation: **UNCLEAR**

Begründung:

Die sechs IDs sind im Claim Register ausdrücklich richtig zugeordnet; im Brief selbst fehlen sie, was bei Erhaltung im Register zulässig ist. Das #117-Muster ist nicht reproduziert. Vorgeschriebene Gegenbelege werden im Ergebnis berücksichtigt; Alternativen bleiben offen und menschliche Ausnahmeentscheidungen erhalten. Direkte Source-Provenance ist geprüft; mangels auflösbarer Tool-Links bleibt die gesamte Provenance UNCLEAR. Alle tatsächlich kritischen Claims stehen in checked_critical_claims; vollständige Replay-/Idempotenzfreiheit ist nicht nachweisbar. Run-, Plan- und Review-Record-Hashes sowie der vollständige eingefrorene Execution Contract stimmen überein.

Human check recommended:

- YES: Die aufgeführten tool_result_id-Referenzen mit bereits gespeicherten Tool-Payloads und result_hashes dieses Runs abgleichen; keine neue Ausführung.

## AP4-04 V1

Run ID: `cd52dd32-3fec-4ce4-8edc-d051572bf47d`  
Status: `ready`  
Runtime: 392.6 s (nur Wiedergabe)  
Evidence: `/runs/10`  
Record-Hash: `3ba3bc88dd2f966c6d61e230d2dada1478679a78c0d7299fdf411e1d0f900a7b` (stimmt mit review.json überein)

Expected key findings:

- PASS: invoice number purchase order amount and supplier are checked deterministically.
- PASS: formal matches require no semantic interpretation.
- PASS: deviations contain free text that is currently summarized manually.
- PASS: the clerk retains the decision on clarification booking or return.
- FAIL: R02 R03 and R05 are manual-review cases while R01 and R04 are standard.

Required counterevidence:

- PASS: formal matches explicitly need no semantic interpretation.
- PASS: the clerk retains the binding operational decision.

Semantic rubric:

- Key findings: FAIL
- Counterevidence: PASS
- Facts/Hypotheses/Unknowns: PASS
- Solution Openness: PASS
- Internal consistency: PASS
- Human Authority: PASS

Explicit case mapping: **absent**

- Erwartet: R02/R03/R05 → manual review; R01/R04 → standard
- IDs im Register: keine; im Decision Brief: keine.
- Fehlende IDs: R01, R02, R03, R04, R05
- Alle `claim_register[*].statement` und fachlichen Inhalte von `brief_payload` auf IDs geprüft. Keine erwarteten IDs; Row-Locators und Aggregate ersetzen die Zuordnung nicht. `/runs/10/review_context/verifier`: success=true, critical_findings=0; kein Finding zum fehlenden Mapping.

Provenance: **UNCLEAR**

Dateien, Byte-Revisionhashes, gelesene Source-IDs und direkte Locators geprüft. Tool-UUIDs fehlen in tool_steps; result_payload fehlt. CSV-Nachrechnung bestätigt die Zahlen, aber nicht die historischen Tool-Result-Links.

Entscheidende Quellenstichprobe (vollständiger Locator-Audit im JSON):

- `/runs/10/review_context/claim_register/0` (C1): „Der Rechnungsprozess prüft Rechnungsnummer, Bestellnummer, Betrag und Lieferant deterministisch gegen Bestellung und Wareneingang.“ → `01_invoice_process.md` {'line': 2}, revision `8e579e32118de0f1097e997c3b68a7228867a784d77d37889ccb7fb44bed0950`, source `97e603e4-2a81-4147-8444-ba53f2b78313`. Quellinhalt: Rechnungsnummer, Bestellnummer, Betrag und Lieferant werden deterministisch gegen Bestellung und Wareneingang geprüft.
- `/runs/10/review_context/claim_register/1` (C2): „Bei formalen Übereinstimmungen ist laut Quelle keine semantische Interpretation notwendig.“ → `01_invoice_process.md` {'line': 3}, revision `8e579e32118de0f1097e997c3b68a7228867a784d77d37889ccb7fb44bed0950`, source `97e603e4-2a81-4147-8444-ba53f2b78313`. Quellinhalt: Bei formalen Übereinstimmungen ist keine semantische Interpretation notwendig.
- `/runs/10/review_context/claim_register/2` (C3): „Bei Abweichungen enthalten Rechnungen und Bearbeitungsnotizen Freitext, dessen Bedeutung heute manuell zusammengefasst wird.“ → `01_invoice_process.md` {'line': 4}, revision `8e579e32118de0f1097e997c3b68a7228867a784d77d37889ccb7fb44bed0950`, source `97e603e4-2a81-4147-8444-ba53f2b78313`. Quellinhalt: Bei Abweichungen enthalten Rechnungen und Bearbeitungsnotizen jedoch Freitext, dessen Bedeutung heute manuell zusammengefasst wird.
- `/runs/10/review_context/claim_register/3` (C4): „Die Sachbearbeitung entscheidet weiterhin über Klärung, Buchung oder Rückgabe.“ → `01_invoice_process.md` {'line': 5}, revision `8e579e32118de0f1097e997c3b68a7228867a784d77d37889ccb7fb44bed0950`, source `97e603e4-2a81-4147-8444-ba53f2b78313`. Quellinhalt: Die Sachbearbeitung entscheidet weiterhin über Klärung, Buchung oder Rückgabe.
- `/runs/10/review_context/claim_register/5` (C6): „Die drei Fälle mit formal_match=false haben decision=manual_review und Freitextnotizen zu Menge, Zusatzleistung oder Preisänderung.“ → `02_exceptions.csv` {'row': 2}, revision `1cf93e8f34842ba488407af553140003823d5e308ae02aaf8a1a9668e0c1ae62`, source `c527f627-cc6b-4b5a-94e1-7a1b8b472f9c`. Quellinhalt: {"case_id": "R02", "formal_match": "false", "free_text_note": "Menge laut Lieferschein abweichend", "decision": "manual_review"}
- `/runs/10/review_context/claim_register/5` (C6): „Die drei Fälle mit formal_match=false haben decision=manual_review und Freitextnotizen zu Menge, Zusatzleistung oder Preisänderung.“ → `02_exceptions.csv` {'row': 3}, revision `1cf93e8f34842ba488407af553140003823d5e308ae02aaf8a1a9668e0c1ae62`, source `c527f627-cc6b-4b5a-94e1-7a1b8b472f9c`. Quellinhalt: {"case_id": "R03", "formal_match": "false", "free_text_note": "Zusatzleistung telefonisch vereinbart", "decision": "manual_review"}
- `/runs/10/review_context/claim_register/5` (C6): „Die drei Fälle mit formal_match=false haben decision=manual_review und Freitextnotizen zu Menge, Zusatzleistung oder Preisänderung.“ → `02_exceptions.csv` {'row': 5}, revision `1cf93e8f34842ba488407af553140003823d5e308ae02aaf8a1a9668e0c1ae62`, source `c527f627-cc6b-4b5a-94e1-7a1b8b472f9c`. Quellinhalt: {"case_id": "R05", "formal_match": "false", "free_text_note": "Preisänderung laut Nachtrag", "decision": "manual_review"}
- `/runs/10/review_context/claim_register/6` (C7): „Eine Ursache der manuellen Klärungsdauer ist, dass Freitextnotizen bei Abweichungen manuell interpretiert und zusammengefasst werden müssen.“ → `02_exceptions.csv` {'row': 2}, revision `1cf93e8f34842ba488407af553140003823d5e308ae02aaf8a1a9668e0c1ae62`, source `c527f627-cc6b-4b5a-94e1-7a1b8b472f9c`. Quellinhalt: {"case_id": "R02", "formal_match": "false", "free_text_note": "Menge laut Lieferschein abweichend", "decision": "manual_review"}
- `/runs/10/review_context/claim_register/6` (C7): „Eine Ursache der manuellen Klärungsdauer ist, dass Freitextnotizen bei Abweichungen manuell interpretiert und zusammengefasst werden müssen.“ → `02_exceptions.csv` {'row': 3}, revision `1cf93e8f34842ba488407af553140003823d5e308ae02aaf8a1a9668e0c1ae62`, source `c527f627-cc6b-4b5a-94e1-7a1b8b472f9c`. Quellinhalt: {"case_id": "R03", "formal_match": "false", "free_text_note": "Zusatzleistung telefonisch vereinbart", "decision": "manual_review"}

Nicht auflösbare Tool-Links:

- `/runs/10/review_context/claim_register/4` (C5): `61cb2f5a-4bdf-48a4-bd82-7cc61d00e850` / revision `1cf93e8f34842ba488407af553140003823d5e308ae02aaf8a1a9668e0c1ae62`.
- `/runs/10/review_context/claim_register/9` (C10): `7a65e610-d000-43f0-b039-077fb80ac3e5` / revision `1cf93e8f34842ba488407af553140003823d5e308ae02aaf8a1a9668e0c1ae62`.
- `/runs/10/review_context/claim_register/11` (C12): `61cb2f5a-4bdf-48a4-bd82-7cc61d00e850` / revision `1cf93e8f34842ba488407af553140003823d5e308ae02aaf8a1a9668e0c1ae62`.

Counterevidence: **PASS** – geforderte Einschränkungen werden in Claims und Options-/Recommendation-Abwägung berücksichtigt.
Human Authority: **PASS** – manuelle Ausnahmeentscheidung bleibt erhalten; keine Pilot-/Go-live-Freigabe behauptet.

- `/runs/10/review_context/claim_register/1/statement`: „Bei formalen Übereinstimmungen ist laut Quelle keine semantische Interpretation notwendig.“
- `/runs/10/review_context/claim_register/3/statement`: „Die Sachbearbeitung entscheidet weiterhin über Klärung, Buchung oder Rückgabe.“
- `/runs/10/review_context/claim_register/10/statement`: „Die Sachbearbeitung bleibt Entscheiderin; eine Automatisierung darf die menschliche Klärung, Buchung oder Rückgabe nicht ersetzen.“

Issue #117 pattern: **reproduced**

Hard-fail candidate: **unclear**

Explizite Hard-Fail-Prüfung (PASS = im sichtbaren Package nicht beobachtet):

- invented_facts: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- invented_measurements: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- invented_systems: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- invented_authority_decisions: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- lost_required_counterevidence: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- unchecked_critical_claims: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- hidden_unknowns: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- wrong_ready_waiting_human_semantics: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- human_authority_bypass: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- broken_provenance: UNCLEAR. Dateien, Byte-Revisionhashes, gelesene Source-IDs und direkte Locators geprüft. Tool-UUIDs fehlen in tool_steps; result_payload fehlt. CSV-Nachrechnung bestätigt die Zahlen, aber nicht die historischen Tool-Result-Links.
- replay_recovery_idempotency: UNCLEAR. Keine Replay-/Idempotenz-Traces. Sichtbare Retry-Ereignisse sind allein kein Hard Fail.
- turns deterministic checks into an LLM-only task: PASS. Keine falsche Zuordnung oder entsprechende verbotene Entscheidung beobachtet; fehlende IDs gesondert als Vollständigkeitsfehler.
- grants autonomous booking or return authority: PASS. Keine falsche Zuordnung oder entsprechende verbotene Entscheidung beobachtet; fehlende IDs gesondert als Vollständigkeitsfehler.
- misstates the frozen exception rows: PASS. Keine falsche Zuordnung oder entsprechende verbotene Entscheidung beobachtet; fehlende IDs gesondert als Vollständigkeitsfehler.

AI preannotation: **FAIL**

Begründung:

Keine erwartete Fall-ID ist im fachlichen Claim Register oder Decision Brief enthalten; Row-Locators und Aggregate sind kein explizites Mapping. Die CSV wurde erfolgreich gelesen, aber das finale Ergebnis verliert die Fallzuordnung und reproduziert #117. Der Verifier meldet success=true und critical_findings=0 ohne Finding zur fehlenden Zuordnung. Vorgeschriebene Gegenbelege werden im Ergebnis berücksichtigt; Alternativen bleiben offen und menschliche Ausnahmeentscheidungen erhalten. Die leere gefilterte compare_groups-Population bleibt als offene Ursache sichtbar und widerlegt nicht die drei CSV-Abweichungen. Direkte Source-Provenance ist geprüft; mangels auflösbarer Tool-Links bleibt die gesamte Provenance UNCLEAR. Alle tatsächlich kritischen Claims stehen in checked_critical_claims; vollständige Replay-/Idempotenzfreiheit ist nicht nachweisbar. Run-, Plan- und Review-Record-Hashes sowie der vollständige eingefrorene Execution Contract stimmen überein.

Human check recommended:

- YES: Bestätigen, dass im finalen Register/Brief die explizite Zuordnung R01, R02, R03, R04, R05 fehlt; Row-Locators nicht als Ersatz anerkennen.

## AP4-04 V2

Run ID: `166009a1-fd71-4053-99b5-231ebc0a918c`  
Status: `ready`  
Runtime: 294.052 s (nur Wiedergabe)  
Evidence: `/runs/12`  
Record-Hash: `56aea7f23355e402ae1659619bdb15243590f6c5d30107c1b77c32a5faf05a3b` (stimmt mit review.json überein)

Expected key findings:

- PASS: invoice number purchase order amount and supplier are checked deterministically.
- PASS: formal matches require no semantic interpretation.
- PASS: deviations contain free text that is currently summarized manually.
- PASS: the clerk retains the decision on clarification booking or return.
- FAIL: R02 R03 and R05 are manual-review cases while R01 and R04 are standard.

Required counterevidence:

- PASS: formal matches explicitly need no semantic interpretation.
- PASS: the clerk retains the binding operational decision.

Semantic rubric:

- Key findings: FAIL
- Counterevidence: PASS
- Facts/Hypotheses/Unknowns: PASS
- Solution Openness: PASS
- Internal consistency: PASS
- Human Authority: PASS

Explicit case mapping: **absent**

- Erwartet: R02/R03/R05 → manual review; R01/R04 → standard
- IDs im Register: keine; im Decision Brief: keine.
- Fehlende IDs: R01, R02, R03, R04, R05
- Alle `claim_register[*].statement` und fachlichen Inhalte von `brief_payload` auf IDs geprüft. Keine erwarteten IDs; Row-Locators und Aggregate ersetzen die Zuordnung nicht. `/runs/12/review_context/verifier`: success=true, critical_findings=0; kein Finding zum fehlenden Mapping.

Provenance: **UNCLEAR**

Dateien, Byte-Revisionhashes, gelesene Source-IDs und direkte Locators geprüft. Tool-UUIDs fehlen in tool_steps; result_payload fehlt. CSV-Nachrechnung bestätigt die Zahlen, aber nicht die historischen Tool-Result-Links.

Entscheidende Quellenstichprobe (vollständiger Locator-Audit im JSON):

- `/runs/12/review_context/claim_register/0` (C1): „Rechnungsnummer, Bestellnummer, Betrag und Lieferant werden deterministisch gegen Bestellung und Wareneingang geprüft.“ → `01_invoice_process.md` {'line': 2}, revision `8e579e32118de0f1097e997c3b68a7228867a784d77d37889ccb7fb44bed0950`, source `cd67d274-25d7-4a36-ad36-abc24ea72b13`. Quellinhalt: Rechnungsnummer, Bestellnummer, Betrag und Lieferant werden deterministisch gegen Bestellung und Wareneingang geprüft.
- `/runs/12/review_context/claim_register/1` (C2): „Bei formalen Übereinstimmungen ist keine semantische Interpretation notwendig.“ → `01_invoice_process.md` {'line': 3}, revision `8e579e32118de0f1097e997c3b68a7228867a784d77d37889ccb7fb44bed0950`, source `cd67d274-25d7-4a36-ad36-abc24ea72b13`. Quellinhalt: Bei formalen Übereinstimmungen ist keine semantische Interpretation notwendig.
- `/runs/12/review_context/claim_register/2` (C3): „Bei Abweichungen enthalten Rechnungen und Bearbeitungsnotizen Freitext, dessen Bedeutung heute manuell zusammengefasst wird.“ → `01_invoice_process.md` {'line': 4}, revision `8e579e32118de0f1097e997c3b68a7228867a784d77d37889ccb7fb44bed0950`, source `cd67d274-25d7-4a36-ad36-abc24ea72b13`. Quellinhalt: Bei Abweichungen enthalten Rechnungen und Bearbeitungsnotizen jedoch Freitext, dessen Bedeutung heute manuell zusammengefasst wird.
- `/runs/12/review_context/claim_register/3` (C4): „Die Sachbearbeitung entscheidet weiterhin über Klärung, Buchung oder Rückgabe.“ → `01_invoice_process.md` {'line': 5}, revision `8e579e32118de0f1097e997c3b68a7228867a784d77d37889ccb7fb44bed0950`, source `cd67d274-25d7-4a36-ad36-abc24ea72b13`. Quellinhalt: Die Sachbearbeitung entscheidet weiterhin über Klärung, Buchung oder Rückgabe.
- `/runs/12/review_context/claim_register/5` (C6): „Die Freitextnotizen in den Abweichungsfällen nennen unterschiedliche Gründe: abweichende Menge laut Lieferschein, telefonisch vereinbarte Zusatzleistung und Preisänderung laut Nachtrag.“ → `02_exceptions.csv` {'row': 2}, revision `1cf93e8f34842ba488407af553140003823d5e308ae02aaf8a1a9668e0c1ae62`, source `d26c4e88-ba45-4249-b472-1b81140db3dc`. Quellinhalt: {"case_id": "R02", "formal_match": "false", "free_text_note": "Menge laut Lieferschein abweichend", "decision": "manual_review"}
- `/runs/12/review_context/claim_register/5` (C6): „Die Freitextnotizen in den Abweichungsfällen nennen unterschiedliche Gründe: abweichende Menge laut Lieferschein, telefonisch vereinbarte Zusatzleistung und Preisänderung laut Nachtrag.“ → `02_exceptions.csv` {'row': 3}, revision `1cf93e8f34842ba488407af553140003823d5e308ae02aaf8a1a9668e0c1ae62`, source `d26c4e88-ba45-4249-b472-1b81140db3dc`. Quellinhalt: {"case_id": "R03", "formal_match": "false", "free_text_note": "Zusatzleistung telefonisch vereinbart", "decision": "manual_review"}
- `/runs/12/review_context/claim_register/5` (C6): „Die Freitextnotizen in den Abweichungsfällen nennen unterschiedliche Gründe: abweichende Menge laut Lieferschein, telefonisch vereinbarte Zusatzleistung und Preisänderung laut Nachtrag.“ → `02_exceptions.csv` {'row': 5}, revision `1cf93e8f34842ba488407af553140003823d5e308ae02aaf8a1a9668e0c1ae62`, source `d26c4e88-ba45-4249-b472-1b81140db3dc`. Quellinhalt: {"case_id": "R05", "formal_match": "false", "free_text_note": "Preisänderung laut Nachtrag", "decision": "manual_review"}
- `/runs/12/review_context/claim_register/6` (C7): „Die manuelle Klärung bei Abweichungen wird durch Freitextkontext ausgelöst, der nicht durch die deterministischen Formalprüfungen erfasst wird.“ → `02_exceptions.csv` {'row': 2}, revision `1cf93e8f34842ba488407af553140003823d5e308ae02aaf8a1a9668e0c1ae62`, source `d26c4e88-ba45-4249-b472-1b81140db3dc`. Quellinhalt: {"case_id": "R02", "formal_match": "false", "free_text_note": "Menge laut Lieferschein abweichend", "decision": "manual_review"}
- `/runs/12/review_context/claim_register/6` (C7): „Die manuelle Klärung bei Abweichungen wird durch Freitextkontext ausgelöst, der nicht durch die deterministischen Formalprüfungen erfasst wird.“ → `02_exceptions.csv` {'row': 3}, revision `1cf93e8f34842ba488407af553140003823d5e308ae02aaf8a1a9668e0c1ae62`, source `d26c4e88-ba45-4249-b472-1b81140db3dc`. Quellinhalt: {"case_id": "R03", "formal_match": "false", "free_text_note": "Zusatzleistung telefonisch vereinbart", "decision": "manual_review"}

Nicht auflösbare Tool-Links:

- `/runs/12/review_context/claim_register/4` (C5): `9882ef65-350e-41de-ade6-189e331cd18d` / revision `1cf93e8f34842ba488407af553140003823d5e308ae02aaf8a1a9668e0c1ae62`.
- `/runs/12/review_context/claim_register/8` (C9): `9882ef65-350e-41de-ade6-189e331cd18d` / revision `1cf93e8f34842ba488407af553140003823d5e308ae02aaf8a1a9668e0c1ae62`.

Counterevidence: **PASS** – geforderte Einschränkungen werden in Claims und Options-/Recommendation-Abwägung berücksichtigt.
Human Authority: **PASS** – manuelle Ausnahmeentscheidung bleibt erhalten; keine Pilot-/Go-live-Freigabe behauptet.

- `/runs/12/review_context/claim_register/1/statement`: „Bei formalen Übereinstimmungen ist keine semantische Interpretation notwendig.“
- `/runs/12/review_context/claim_register/3/statement`: „Die Sachbearbeitung entscheidet weiterhin über Klärung, Buchung oder Rückgabe.“

Issue #117 pattern: **reproduced**

Hard-fail candidate: **unclear**

Explizite Hard-Fail-Prüfung (PASS = im sichtbaren Package nicht beobachtet):

- invented_facts: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- invented_measurements: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- invented_systems: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- invented_authority_decisions: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- lost_required_counterevidence: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- unchecked_critical_claims: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- hidden_unknowns: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- wrong_ready_waiting_human_semantics: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- human_authority_bypass: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- broken_provenance: UNCLEAR. Dateien, Byte-Revisionhashes, gelesene Source-IDs und direkte Locators geprüft. Tool-UUIDs fehlen in tool_steps; result_payload fehlt. CSV-Nachrechnung bestätigt die Zahlen, aber nicht die historischen Tool-Result-Links.
- replay_recovery_idempotency: UNCLEAR. Keine Replay-/Idempotenz-Traces. Sichtbare Retry-Ereignisse sind allein kein Hard Fail.
- turns deterministic checks into an LLM-only task: PASS. Keine falsche Zuordnung oder entsprechende verbotene Entscheidung beobachtet; fehlende IDs gesondert als Vollständigkeitsfehler.
- grants autonomous booking or return authority: PASS. Keine falsche Zuordnung oder entsprechende verbotene Entscheidung beobachtet; fehlende IDs gesondert als Vollständigkeitsfehler.
- misstates the frozen exception rows: PASS. Keine falsche Zuordnung oder entsprechende verbotene Entscheidung beobachtet; fehlende IDs gesondert als Vollständigkeitsfehler.

AI preannotation: **FAIL**

Begründung:

Keine erwartete Fall-ID ist im fachlichen Claim Register oder Decision Brief enthalten; Row-Locators und Aggregate sind kein explizites Mapping. Die CSV wurde erfolgreich gelesen, aber das finale Ergebnis verliert die Fallzuordnung und reproduziert #117. Der Verifier meldet success=true und critical_findings=0 ohne Finding zur fehlenden Zuordnung. Vorgeschriebene Gegenbelege werden im Ergebnis berücksichtigt; Alternativen bleiben offen und menschliche Ausnahmeentscheidungen erhalten. Direkte Source-Provenance ist geprüft; mangels auflösbarer Tool-Links bleibt die gesamte Provenance UNCLEAR. Alle tatsächlich kritischen Claims stehen in checked_critical_claims; vollständige Replay-/Idempotenzfreiheit ist nicht nachweisbar. Run-, Plan- und Review-Record-Hashes sowie der vollständige eingefrorene Execution Contract stimmen überein.

Human check recommended:

- YES: Bestätigen, dass im finalen Register/Brief die explizite Zuordnung R01, R02, R03, R04, R05 fehlt; Row-Locators nicht als Ersatz anerkennen.

## AP4-04 V3

Run ID: `50b1cf1d-0802-4712-bac7-cbbd7b232037`  
Status: `ready`  
Runtime: 224.188 s (nur Wiedergabe)  
Evidence: `/runs/13`  
Record-Hash: `bf553d91f0ee7ad629090f0afb655b0e53adf923e6122bcacd3e6f4fd36f74fe` (stimmt mit review.json überein)

Expected key findings:

- PASS: invoice number purchase order amount and supplier are checked deterministically.
- PASS: formal matches require no semantic interpretation.
- PASS: deviations contain free text that is currently summarized manually.
- PASS: the clerk retains the decision on clarification booking or return.
- FAIL: R02 R03 and R05 are manual-review cases while R01 and R04 are standard.

Required counterevidence:

- PASS: formal matches explicitly need no semantic interpretation.
- PASS: the clerk retains the binding operational decision.

Semantic rubric:

- Key findings: FAIL
- Counterevidence: PASS
- Facts/Hypotheses/Unknowns: PASS
- Solution Openness: PASS
- Internal consistency: PASS
- Human Authority: PASS

Explicit case mapping: **absent**

- Erwartet: R02/R03/R05 → manual review; R01/R04 → standard
- IDs im Register: keine; im Decision Brief: keine.
- Fehlende IDs: R01, R02, R03, R04, R05
- Alle `claim_register[*].statement` und fachlichen Inhalte von `brief_payload` auf IDs geprüft. Keine erwarteten IDs; Row-Locators und Aggregate ersetzen die Zuordnung nicht. `/runs/13/review_context/verifier`: success=true, critical_findings=0; kein Finding zum fehlenden Mapping.

Provenance: **UNCLEAR**

Dateien, Byte-Revisionhashes, gelesene Source-IDs und direkte Locators geprüft. Tool-UUIDs fehlen in tool_steps; result_payload fehlt. CSV-Nachrechnung bestätigt die Zahlen, aber nicht die historischen Tool-Result-Links.

Entscheidende Quellenstichprobe (vollständiger Locator-Audit im JSON):

- `/runs/13/review_context/claim_register/0` (C1): „Die Rechnungsprüfung prüft Rechnungsnummer, Bestellnummer, Betrag und Lieferant deterministisch gegen Bestellung und Wareneingang.“ → `01_invoice_process.md` {'line': 2}, revision `8e579e32118de0f1097e997c3b68a7228867a784d77d37889ccb7fb44bed0950`, source `d2119c17-e7f5-4081-9889-2e75df3fbb99`. Quellinhalt: Rechnungsnummer, Bestellnummer, Betrag und Lieferant werden deterministisch gegen Bestellung und Wareneingang geprüft.
- `/runs/13/review_context/claim_register/1` (C2): „Bei formalen Übereinstimmungen ist keine semantische Interpretation notwendig.“ → `01_invoice_process.md` {'line': 3}, revision `8e579e32118de0f1097e997c3b68a7228867a784d77d37889ccb7fb44bed0950`, source `d2119c17-e7f5-4081-9889-2e75df3fbb99`. Quellinhalt: Bei formalen Übereinstimmungen ist keine semantische Interpretation notwendig.
- `/runs/13/review_context/claim_register/2` (C3): „Bei Abweichungen enthalten Rechnungen und Bearbeitungsnotizen Freitext, dessen Bedeutung heute manuell zusammengefasst wird.“ → `01_invoice_process.md` {'line': 4}, revision `8e579e32118de0f1097e997c3b68a7228867a784d77d37889ccb7fb44bed0950`, source `d2119c17-e7f5-4081-9889-2e75df3fbb99`. Quellinhalt: Bei Abweichungen enthalten Rechnungen und Bearbeitungsnotizen jedoch Freitext, dessen Bedeutung heute manuell zusammengefasst wird.
- `/runs/13/review_context/claim_register/3` (C4): „Die Sachbearbeitung entscheidet weiterhin über Klärung, Buchung oder Rückgabe.“ → `01_invoice_process.md` {'line': 5}, revision `8e579e32118de0f1097e997c3b68a7228867a784d77d37889ccb7fb44bed0950`, source `d2119c17-e7f5-4081-9889-2e75df3fbb99`. Quellinhalt: Die Sachbearbeitung entscheidet weiterhin über Klärung, Buchung oder Rückgabe.
- `/runs/13/review_context/claim_register/4` (C5): „Im eingefrorenen Sample haben 3 von 5 Fällen formal_match=false und decision=manual_review.“ → `02_exceptions.csv` {'row': 2}, revision `1cf93e8f34842ba488407af553140003823d5e308ae02aaf8a1a9668e0c1ae62`, source `2137a414-e65c-4339-88b1-233b987ae559`. Quellinhalt: {"case_id": "R02", "formal_match": "false", "free_text_note": "Menge laut Lieferschein abweichend", "decision": "manual_review"}
- `/runs/13/review_context/claim_register/4` (C5): „Im eingefrorenen Sample haben 3 von 5 Fällen formal_match=false und decision=manual_review.“ → `02_exceptions.csv` {'row': 3}, revision `1cf93e8f34842ba488407af553140003823d5e308ae02aaf8a1a9668e0c1ae62`, source `2137a414-e65c-4339-88b1-233b987ae559`. Quellinhalt: {"case_id": "R03", "formal_match": "false", "free_text_note": "Zusatzleistung telefonisch vereinbart", "decision": "manual_review"}
- `/runs/13/review_context/claim_register/4` (C5): „Im eingefrorenen Sample haben 3 von 5 Fällen formal_match=false und decision=manual_review.“ → `02_exceptions.csv` {'row': 5}, revision `1cf93e8f34842ba488407af553140003823d5e308ae02aaf8a1a9668e0c1ae62`, source `2137a414-e65c-4339-88b1-233b987ae559`. Quellinhalt: {"case_id": "R05", "formal_match": "false", "free_text_note": "Preisänderung laut Nachtrag", "decision": "manual_review"}
- `/runs/13/review_context/claim_register/5` (C6): „Die Freitextnotizen der Abweichungsfälle nennen fallbezogene Gründe wie abweichende Menge, telefonisch vereinbarte Zusatzleistung oder Preisänderung laut Nachtrag.“ → `02_exceptions.csv` {'row': 2}, revision `1cf93e8f34842ba488407af553140003823d5e308ae02aaf8a1a9668e0c1ae62`, source `2137a414-e65c-4339-88b1-233b987ae559`. Quellinhalt: {"case_id": "R02", "formal_match": "false", "free_text_note": "Menge laut Lieferschein abweichend", "decision": "manual_review"}
- `/runs/13/review_context/claim_register/5` (C6): „Die Freitextnotizen der Abweichungsfälle nennen fallbezogene Gründe wie abweichende Menge, telefonisch vereinbarte Zusatzleistung oder Preisänderung laut Nachtrag.“ → `02_exceptions.csv` {'row': 3}, revision `1cf93e8f34842ba488407af553140003823d5e308ae02aaf8a1a9668e0c1ae62`, source `2137a414-e65c-4339-88b1-233b987ae559`. Quellinhalt: {"case_id": "R03", "formal_match": "false", "free_text_note": "Zusatzleistung telefonisch vereinbart", "decision": "manual_review"}

Nicht auflösbare Tool-Links:

- `/runs/13/review_context/claim_register/4` (C5): `63dacad8-7445-4874-89d0-850c9e2ec4b5` / revision `1cf93e8f34842ba488407af553140003823d5e308ae02aaf8a1a9668e0c1ae62`.

Counterevidence: **PASS** – geforderte Einschränkungen werden in Claims und Options-/Recommendation-Abwägung berücksichtigt.
Human Authority: **PASS** – manuelle Ausnahmeentscheidung bleibt erhalten; keine Pilot-/Go-live-Freigabe behauptet.

- `/runs/13/review_context/claim_register/1/statement`: „Bei formalen Übereinstimmungen ist keine semantische Interpretation notwendig.“
- `/runs/13/review_context/claim_register/3/statement`: „Die Sachbearbeitung entscheidet weiterhin über Klärung, Buchung oder Rückgabe.“

Issue #117 pattern: **reproduced**

Hard-fail candidate: **unclear**

Explizite Hard-Fail-Prüfung (PASS = im sichtbaren Package nicht beobachtet):

- invented_facts: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- invented_measurements: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- invented_systems: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- invented_authority_decisions: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- lost_required_counterevidence: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- unchecked_critical_claims: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- hidden_unknowns: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- wrong_ready_waiting_human_semantics: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- human_authority_bypass: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- broken_provenance: UNCLEAR. Dateien, Byte-Revisionhashes, gelesene Source-IDs und direkte Locators geprüft. Tool-UUIDs fehlen in tool_steps; result_payload fehlt. CSV-Nachrechnung bestätigt die Zahlen, aber nicht die historischen Tool-Result-Links.
- replay_recovery_idempotency: UNCLEAR. Keine Replay-/Idempotenz-Traces. Sichtbare Retry-Ereignisse sind allein kein Hard Fail.
- turns deterministic checks into an LLM-only task: PASS. Keine falsche Zuordnung oder entsprechende verbotene Entscheidung beobachtet; fehlende IDs gesondert als Vollständigkeitsfehler.
- grants autonomous booking or return authority: PASS. Keine falsche Zuordnung oder entsprechende verbotene Entscheidung beobachtet; fehlende IDs gesondert als Vollständigkeitsfehler.
- misstates the frozen exception rows: PASS. Keine falsche Zuordnung oder entsprechende verbotene Entscheidung beobachtet; fehlende IDs gesondert als Vollständigkeitsfehler.

AI preannotation: **FAIL**

Begründung:

Keine erwartete Fall-ID ist im fachlichen Claim Register oder Decision Brief enthalten; Row-Locators und Aggregate sind kein explizites Mapping. Die CSV wurde erfolgreich gelesen, aber das finale Ergebnis verliert die Fallzuordnung und reproduziert #117. Der Verifier meldet success=true und critical_findings=0 ohne Finding zur fehlenden Zuordnung. Vorgeschriebene Gegenbelege werden im Ergebnis berücksichtigt; Alternativen bleiben offen und menschliche Ausnahmeentscheidungen erhalten. Direkte Source-Provenance ist geprüft; mangels auflösbarer Tool-Links bleibt die gesamte Provenance UNCLEAR. Alle tatsächlich kritischen Claims stehen in checked_critical_claims; vollständige Replay-/Idempotenzfreiheit ist nicht nachweisbar. Run-, Plan- und Review-Record-Hashes sowie der vollständige eingefrorene Execution Contract stimmen überein.

Human check recommended:

- YES: Bestätigen, dass im finalen Register/Brief die explizite Zuordnung R01, R02, R03, R04, R05 fehlt; Row-Locators nicht als Ersatz anerkennen.

## AP4-04 V4

Run ID: `a91d869a-5c54-49f0-92e3-0a0b4d098f74`  
Status: `ready`  
Runtime: 568.589 s (nur Wiedergabe)  
Evidence: `/runs/14`  
Record-Hash: `99e2b76476ddcda4d955577ebee9750ef3cde2b059620796e090e3f12963ce07` (stimmt mit review.json überein)

Expected key findings:

- PASS: invoice number purchase order amount and supplier are checked deterministically.
- PASS: formal matches require no semantic interpretation.
- PASS: deviations contain free text that is currently summarized manually.
- PASS: the clerk retains the decision on clarification booking or return.
- FAIL: R02 R03 and R05 are manual-review cases while R01 and R04 are standard.

Required counterevidence:

- PASS: formal matches explicitly need no semantic interpretation.
- PASS: the clerk retains the binding operational decision.

Semantic rubric:

- Key findings: FAIL
- Counterevidence: PASS
- Facts/Hypotheses/Unknowns: PASS
- Solution Openness: PASS
- Internal consistency: PASS
- Human Authority: PASS

Explicit case mapping: **absent**

- Erwartet: R02/R03/R05 → manual review; R01/R04 → standard
- IDs im Register: keine; im Decision Brief: keine.
- Fehlende IDs: R01, R02, R03, R04, R05
- Alle `claim_register[*].statement` und fachlichen Inhalte von `brief_payload` auf IDs geprüft. Keine erwarteten IDs; Row-Locators und Aggregate ersetzen die Zuordnung nicht. `/runs/14/review_context/verifier`: success=true, critical_findings=0; kein Finding zum fehlenden Mapping.

Provenance: **UNCLEAR**

Dateien, Byte-Revisionhashes, gelesene Source-IDs und direkte Locators geprüft. Tool-UUIDs fehlen in tool_steps; result_payload fehlt. CSV-Nachrechnung bestätigt die Zahlen, aber nicht die historischen Tool-Result-Links.

Entscheidende Quellenstichprobe (vollständiger Locator-Audit im JSON):

- `/runs/14/review_context/claim_register/0` (C-001): „Der Rechnungsprozess prüft Rechnungsnummer, Bestellnummer, Betrag und Lieferant deterministisch gegen Bestellung und Wareneingang.“ → `01_invoice_process.md` {'line': 2}, revision `8e579e32118de0f1097e997c3b68a7228867a784d77d37889ccb7fb44bed0950`, source `e267b715-2c70-485d-a988-667465abd9b0`. Quellinhalt: Rechnungsnummer, Bestellnummer, Betrag und Lieferant werden deterministisch gegen Bestellung und Wareneingang geprüft.
- `/runs/14/review_context/claim_register/1` (C-002): „Bei formalen Übereinstimmungen ist keine semantische Interpretation notwendig.“ → `01_invoice_process.md` {'line': 3}, revision `8e579e32118de0f1097e997c3b68a7228867a784d77d37889ccb7fb44bed0950`, source `e267b715-2c70-485d-a988-667465abd9b0`. Quellinhalt: Bei formalen Übereinstimmungen ist keine semantische Interpretation notwendig.
- `/runs/14/review_context/claim_register/2` (C-003): „Bei Abweichungen enthalten Rechnungen und Bearbeitungsnotizen Freitext, dessen Bedeutung heute manuell zusammengefasst wird.“ → `01_invoice_process.md` {'line': 4}, revision `8e579e32118de0f1097e997c3b68a7228867a784d77d37889ccb7fb44bed0950`, source `e267b715-2c70-485d-a988-667465abd9b0`. Quellinhalt: Bei Abweichungen enthalten Rechnungen und Bearbeitungsnotizen jedoch Freitext, dessen Bedeutung heute manuell zusammengefasst wird.
- `/runs/14/review_context/claim_register/3` (C-004): „Die Sachbearbeitung entscheidet weiterhin über Klärung, Buchung oder Rückgabe.“ → `01_invoice_process.md` {'line': 5}, revision `8e579e32118de0f1097e997c3b68a7228867a784d77d37889ccb7fb44bed0950`, source `e267b715-2c70-485d-a988-667465abd9b0`. Quellinhalt: Die Sachbearbeitung entscheidet weiterhin über Klärung, Buchung oder Rückgabe.
- `/runs/14/review_context/claim_register/5` (C-006): „Die zwei Fälle mit formal_match=true in 02_exceptions.csv haben einen leeren free_text_note; die drei Fälle mit formal_match=false haben einen nichtleeren free_text_note.“ → `02_exceptions.csv` {'row': 1}, revision `1cf93e8f34842ba488407af553140003823d5e308ae02aaf8a1a9668e0c1ae62`, source `236c4457-81da-4199-b99f-bc0815bb1c11`. Quellinhalt: {"case_id": "R01", "formal_match": "true", "free_text_note": "", "decision": "standard"}
- `/runs/14/review_context/claim_register/5` (C-006): „Die zwei Fälle mit formal_match=true in 02_exceptions.csv haben einen leeren free_text_note; die drei Fälle mit formal_match=false haben einen nichtleeren free_text_note.“ → `02_exceptions.csv` {'row': 2}, revision `1cf93e8f34842ba488407af553140003823d5e308ae02aaf8a1a9668e0c1ae62`, source `236c4457-81da-4199-b99f-bc0815bb1c11`. Quellinhalt: {"case_id": "R02", "formal_match": "false", "free_text_note": "Menge laut Lieferschein abweichend", "decision": "manual_review"}
- `/runs/14/review_context/claim_register/5` (C-006): „Die zwei Fälle mit formal_match=true in 02_exceptions.csv haben einen leeren free_text_note; die drei Fälle mit formal_match=false haben einen nichtleeren free_text_note.“ → `02_exceptions.csv` {'row': 3}, revision `1cf93e8f34842ba488407af553140003823d5e308ae02aaf8a1a9668e0c1ae62`, source `236c4457-81da-4199-b99f-bc0815bb1c11`. Quellinhalt: {"case_id": "R03", "formal_match": "false", "free_text_note": "Zusatzleistung telefonisch vereinbart", "decision": "manual_review"}
- `/runs/14/review_context/claim_register/5` (C-006): „Die zwei Fälle mit formal_match=true in 02_exceptions.csv haben einen leeren free_text_note; die drei Fälle mit formal_match=false haben einen nichtleeren free_text_note.“ → `02_exceptions.csv` {'row': 4}, revision `1cf93e8f34842ba488407af553140003823d5e308ae02aaf8a1a9668e0c1ae62`, source `236c4457-81da-4199-b99f-bc0815bb1c11`. Quellinhalt: {"case_id": "R04", "formal_match": "true", "free_text_note": "", "decision": "standard"}
- `/runs/14/review_context/claim_register/5` (C-006): „Die zwei Fälle mit formal_match=true in 02_exceptions.csv haben einen leeren free_text_note; die drei Fälle mit formal_match=false haben einen nichtleeren free_text_note.“ → `02_exceptions.csv` {'row': 5}, revision `1cf93e8f34842ba488407af553140003823d5e308ae02aaf8a1a9668e0c1ae62`, source `236c4457-81da-4199-b99f-bc0815bb1c11`. Quellinhalt: {"case_id": "R05", "formal_match": "false", "free_text_note": "Preisänderung laut Nachtrag", "decision": "manual_review"}

Nicht auflösbare Tool-Links:

- `/runs/14/review_context/claim_register/4` (C-005): `39922bf7-d39b-4335-9226-ce130d44544d` / revision `1cf93e8f34842ba488407af553140003823d5e308ae02aaf8a1a9668e0c1ae62`.
- `/runs/14/review_context/claim_register/9` (C-010): `6cf532d2-a057-4499-b96b-a5234db0a651` / revision `1cf93e8f34842ba488407af553140003823d5e308ae02aaf8a1a9668e0c1ae62`.

Counterevidence: **PASS** – geforderte Einschränkungen werden in Claims und Options-/Recommendation-Abwägung berücksichtigt.
Human Authority: **PASS** – manuelle Ausnahmeentscheidung bleibt erhalten; keine Pilot-/Go-live-Freigabe behauptet.

- `/runs/14/review_context/claim_register/1/statement`: „Bei formalen Übereinstimmungen ist keine semantische Interpretation notwendig.“
- `/runs/14/review_context/claim_register/3/statement`: „Die Sachbearbeitung entscheidet weiterhin über Klärung, Buchung oder Rückgabe.“

Issue #117 pattern: **reproduced**

Hard-fail candidate: **unclear**

Explizite Hard-Fail-Prüfung (PASS = im sichtbaren Package nicht beobachtet):

- invented_facts: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- invented_measurements: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- invented_systems: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- invented_authority_decisions: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- lost_required_counterevidence: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- unchecked_critical_claims: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- hidden_unknowns: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- wrong_ready_waiting_human_semantics: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- human_authority_bypass: PASS. Im sichtbaren Package nicht beobachtet; ausschließlich AI-Vorannotation.
- broken_provenance: UNCLEAR. Dateien, Byte-Revisionhashes, gelesene Source-IDs und direkte Locators geprüft. Tool-UUIDs fehlen in tool_steps; result_payload fehlt. CSV-Nachrechnung bestätigt die Zahlen, aber nicht die historischen Tool-Result-Links.
- replay_recovery_idempotency: UNCLEAR. Keine Replay-/Idempotenz-Traces. Sichtbare Retry-Ereignisse sind allein kein Hard Fail.
- turns deterministic checks into an LLM-only task: PASS. Keine falsche Zuordnung oder entsprechende verbotene Entscheidung beobachtet; fehlende IDs gesondert als Vollständigkeitsfehler.
- grants autonomous booking or return authority: PASS. Keine falsche Zuordnung oder entsprechende verbotene Entscheidung beobachtet; fehlende IDs gesondert als Vollständigkeitsfehler.
- misstates the frozen exception rows: PASS. Keine falsche Zuordnung oder entsprechende verbotene Entscheidung beobachtet; fehlende IDs gesondert als Vollständigkeitsfehler.

AI preannotation: **FAIL**

Begründung:

Keine erwartete Fall-ID ist im fachlichen Claim Register oder Decision Brief enthalten; Row-Locators und Aggregate sind kein explizites Mapping. Die CSV wurde erfolgreich gelesen, aber das finale Ergebnis verliert die Fallzuordnung und reproduziert #117. Der Verifier meldet success=true und critical_findings=0 ohne Finding zur fehlenden Zuordnung. Vorgeschriebene Gegenbelege werden im Ergebnis berücksichtigt; Alternativen bleiben offen und menschliche Ausnahmeentscheidungen erhalten. not_null beweist keine nichtleeren Strings; die direkten CSV-Zeilen stützen die Notizen unabhängig davon. Direkte Source-Provenance ist geprüft; mangels auflösbarer Tool-Links bleibt die gesamte Provenance UNCLEAR. Alle tatsächlich kritischen Claims stehen in checked_critical_claims; vollständige Replay-/Idempotenzfreiheit ist nicht nachweisbar. Run-, Plan- und Review-Record-Hashes sowie der vollständige eingefrorene Execution Contract stimmen überein.

Human check recommended:

- YES: Bestätigen, dass im finalen Register/Brief die explizite Zuordnung R01, R02, R03, R04, R05 fehlt; Row-Locators nicht als Ersatz anerkennen.

## Aggregierte Matrix

| Case | Variant | Status | Mapping | Provenance | Counterevidence | Human Authority | #117 | AI |
|---|---|---|---|---|---|---|---|---|
| AP4-02 | V1 | ready | complete | UNCLEAR | PASS | PASS | not_reproduced | UNCLEAR |
| AP4-02 | V2 | ready | complete | UNCLEAR | PASS | PASS | not_reproduced | UNCLEAR |
| AP4-02 | V3 | ready | absent | UNCLEAR | PASS | PASS | reproduced | FAIL |
| AP4-02 | V4 | ready | complete | UNCLEAR | PASS | PASS | not_reproduced | UNCLEAR |
| AP4-04 | V1 | ready | absent | UNCLEAR | PASS | PASS | reproduced | FAIL |
| AP4-04 | V2 | ready | absent | UNCLEAR | PASS | PASS | reproduced | FAIL |
| AP4-04 | V3 | ready | absent | UNCLEAR | PASS | PASS | reproduced | FAIL |
| AP4-04 | V4 | ready | absent | UNCLEAR | PASS | PASS | reproduced | FAIL |

## RED

Keinen weiteren Provider-Nachweiszyklus empfehlen, bevor der fachliche Befund geklärt ist.

Fünf klare Mapping-Verluste reproduzieren #117; diese tragen RED unabhängig von den zusätzlichen Tool-Provenance-Lücken. Kein v20-Adoptionsbeschluss und keine Änderung des bestehenden #118-Ergebnisses.

Minimal empfohlene menschliche Prüfstellen: **8** konkrete Run-Prüfstellen – fünf Mappingbestätigungen (AP4-02 V3; AP4-04 V1–V4) und drei Tool-Link-Prüfungen der sonst vollständigen Runs (AP4-02 V1/V2/V4). Die übrigen Tool-Lücken bleiben dokumentiert, müssen für die aktuelle No-Go-Begründung aber nicht zusätzlich aufgelöst werden.

## Abschlusskontrolle

Mapping: complete=3, incomplete=0, absent=5, unclear=0. Provenance: PASS=0, FAIL=0, UNCLEAR=8. #117: reproduced=5, not_reproduced=3, partially_reproduced=0, unclear=0. AI: PASS=0, FAIL=5, UNCLEAR=3. Hard-Fail-Kandidaten: yes=0, none=0, unclear=8. Human Authority und Counterevidence: jeweils 8/8 PASS als AI-Vorannotation.

review.json unverändert, SHA-256 `2b3394c1330bf204254fd3b4d1a21f924722749db1c7d1e902f9e36140dddebf`. Alle vorhandenen Evidence-Dateien unverändert. Git status Variant: clean; Git status Control: clean. HEADs unverändert. Provider-Runs = 0; DB-Zugriffe = 0; Repositoryänderungen = 0; GitHub-Änderungen = 0.

Outputs: `C:\Users\user\Documents\issue118-evidence\C2C_8_RUN_REVIEW_PACKET.md` und `C:\Users\user\Documents\issue118-evidence\C2C_8_RUN_PREANNOTATION.json`. Keine vor Beginn vorhandene Datei überschrieben.

#118 C2C AI-VORPRÜFUNG ABGESCHLOSSEN – BEREIT FÜR FACHLICHEN REVIEW
