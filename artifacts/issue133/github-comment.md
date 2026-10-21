# In GitHub veröffentlichter Ergebnis- und Blockerkommentar

URL: https://github.com/Satte882/KI-Ideenwerkstatt/issues/133#issuecomment-6313951190

Nach Veröffentlichung wortgleich über den GitHub-Connector zurückgelesen.

## Fachliche Validierung A–D: echte Providerläufe, Abnahme noch offen

Produktstand: `095062aa52efe5b2a9a3770b6bd04b1a3f41907e`, 21.10.2026.
Alle Texte, Rollen, Beispiele und Zusatzinformationen sind synthetisch; keine festgestellten Probleme oder Daten der RSD Touristik GmbH.

Nach ausdrücklicher Nutzerfreigabe wurden A–D jeweils mit dem natürlichen Ersttext und genau einer passenden faktischen Klärungsantwort über die unveränderten Inbox-/Discovery-Views geprüft. Vorhandenes effektives Discovery-Modell: `google/gemini-3.6-flash` über OpenRouter. Eigene SQLite-Datenbank und Quellenablage je Fall, Business-Owner-Rolle, keine Produktänderungen.

**18 echte Modellaufrufe, Provider-Istkosten insgesamt 0,27575325 USD** (Testgrenze 5 USD). A: 4 / 0,06813225 USD; B: 4 / 0,06398100 USD; C: 6 / 0,09250200 USD; D: 4 / 0,05113800 USD. C nutzte den vorhandenen einmaligen Repair. Alle acht Analysefassungen enden technisch mit `success` und Modellprüfer `approved`; das ist keine menschliche oder fachliche Abnahme.

### Belegte Leistung und Schwächen

- **A:** selbstständige Strukturierung von Informationssuche, interner Rückfrage und wartendem Kunden; Messlücken bleiben sichtbar. Gleichzeitig wird unbelegt ein „primärer Engpass“ behauptet. Nach der Klärung wird der Recherche sogar die Entstehung widersprüchlicher Angaben zugeschrieben. Der Modellprüfer akzeptiert das; Process Scope und Fokus bleiben unterschiedlich weit.
- **B:** Ziel und fehlende Ablauf-/Zeitdaten erkannt. R0 verschärft „nicht immer neue Leute einstellen“ zum Fakt, kontinuierlicher Personalaufbau sei ausgeschlossen. Der Fokus wechselt nach ungemessenen Aussagen von Buchungserfassung zu Verkauf. In **beiden Revisionen** ist die genaue Ablauf-/Systemfrage `blocking=true`, während Verifier und Analyse `approved/success` melden. Kein Scope-Submit oder Gate-Bypass ausgeführt.
- **C:** Informationswiderspruch und Kontaktfrage erkannt. Nach Hinweis auf eine vorhandene Telefonnummer und fehlenden Internetempfang fordert der Verifier eine Scope-Korrektur an; der vorhandene Repair wird tatsächlich ausgeführt. Der finale Entwurf nennt einen Anruf als mögliche einfache Klärung, **falls** die Nummer erreichbar ist. Weder Erreichbarkeit noch gültiger Treffpunkt werden behauptet. Die tatsächliche Klärung von Ort/Zeit bleibt offen.
- **D:** Partnerrollen und „Anfrage ist noch kein bestätigter Auftrag“ nach Klärung korrekt übernommen. Dennoch unbelegter „zentraler Bestätigungsnachweis“ im Bottleneckfeld; die entscheidende Vollmacht für Bestellung/Mehrkosten wird nicht ausdrücklich erfragt.

Originaltexte und versionierte Nutzerantworten bleiben erhalten. Die referenzierten Aussagen zeigen auf `U0`; valide Herkunft ersetzt keinen Beleg für jede Ableitung. Karten wurden über das vorhandene Korrekturfeld geliefert, nicht als getrennte Dokumentquellen. Durchgängige Domain-/Lifecycle-Provenance wurde deshalb nicht behauptet.

### Konkreter verbleibender Blocker

**Kein Providerfreigabe-Blocker mehr.** Es fehlen tatsächliche Abläufe, belastbare Aufwands-/Qualitätsdaten, gültige Informationsstände und Entscheidungsrechte sowie eine verantwortete fachliche Prüfung der teils fehlerhaften Scope-/Diagnoseentwürfe. Die Nutzungsfreigabe für Provideraufrufe ist keine nachträgliche fachliche Scope-, Ursachen- oder Lösungsfreigabe.

Kein Entwurf wurde verbindlich materialisiert, keine Ursache bestätigt, keine Lösungspräferenz, Governance-Freigabe oder Pilotwirkung erfunden. Der Vergleich organisatorischer/klassischer/KI-Lösungen und eine umsetzbare Endentscheidung sind **noch nicht nachgewiesen**. Dass C eine Telefonklärung nennt, ist kein vollständiger No-AI-Alternativenvergleich.

Je Fall drei skriptgesteuerte Eingabeaktionen einschließlich einer Antwortrevision; Auswahl der Karten und fachliche Gegenprüfung durch den Testagenten erforderlich. Keine reale menschliche Arbeitszeit gemessen, keine Minutenersparnis oder Wirtschaftlichkeit behauptet.

Testabweichung: C/D-Klärungsläufe überlappten kurz durch einen Steuerungsfehler; Falldaten blieben getrennt. Die 18 vollständigen Requests/Antworten wurden ohne Wiederholung aus gesicherten Ledgerständen abgeglichen; Kosten stimmen mit den Anwendungsanalysen bis auf Feldrundung überein. Exklusive Laufsperre im Teststarter anschließend ohne Provideraufruf geprüft.

### Nachweise und Abschlussentscheidung

Lokal im beauftragten Repository:
- `docs/planning/ISSUE_133_RSD_CONSOLIDATED.md`: konsolidierter Bericht, Einzelbefunde, Abnahmematrix und Grenzen.
- `artifacts/issue133/live/A.json` bis `D.json`, `provider-ledger.json`, `results-summary.json`, Protokoll und bereinigte Konfigurations-/Modellnachweise.
- `scripts/run_issue133_live.py`: expliziter Real-Provider-Opt-in, Isolation, Kostenreservierung, vorhandene Ergebniswiederverwendung und Laufsperre.
- Frühere 123 bestandene Mechanismen-/Regressionstests bleiben berücksichtigt; keine unnötige Wiederholung. Neue Python-Datei und vorhandene Ergänzungen: Ruff/Format grün.

**Abnahme nicht erfüllt: Issue offen lassen, kein Abnahme-PR/Merge/Close.** Keine weiteren Modellschleifen mit denselben unbekannten Fakten. Für Fortsetzung zuerst reale bzw. belastbar autorisierte Evidenz und eine konkrete fachliche Scope-/Ursachenprüfung bereitstellen. Keine neuen Features oder Architekturänderungen aus diesem Lauf allein.
