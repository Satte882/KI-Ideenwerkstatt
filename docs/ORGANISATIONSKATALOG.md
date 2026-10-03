# Organisationskatalog

## Zweck

`BusinessUnit` bildet fachliche organisatorische Verantwortungsbereiche ab. Der
Katalog ist bewusst flach: keine Hierarchie, keine Standorte und keine Projekte auf
Vorrat.

Für neue produktive Zuordnungen sind aktuell genau diese sechs Bereiche vorgesehen:

1. **Unternehmenssteuerung**
2. **Touristik & Operations**
3. **Kundenservice & Buchung**
4. **Marketing & Vertrieb**
5. **IT & Digitalisierung**
6. **Finanzen & Administration**

Ein Firmenpräfix ist bewusst nicht Teil des Namens. Innerhalb der Anwendung ist
der Unternehmenskontext eindeutig; die Einheiten bleiben dadurch kürzer und besser
lesbar.

## Katalogstatus

Jede Organisationseinheit besitzt einen `catalog_scope`:

| Scope | Bedeutung | In neuen produktiven Dropdowns |
| --- | --- | --- |
| `productive` | freigegebener Organisationskatalog | ja, wenn aktiv |
| `demo_test` | Demo-, Evidence- oder Testdaten | nein |
| `legacy` | bestehende Altzuordnung ohne Freigabe | nein |

Bei der Migration werden vorhandene unbekannte Einträge nicht gelöscht und nicht
umgehängt. Sie werden als `legacy` erhalten. Die sechs oben definierten Einheiten
werden als aktive produktive Stammdaten angelegt.

Neue, über die Administration angelegte Einheiten sind standardmäßig produktiv.
Die Pflegeverantwortung liegt deshalb bei der Administration: neue Einheiten nur
für reale organisatorische Verantwortungsbereiche anlegen.

## Was keine Organisationseinheit ist

Nicht als produktive `BusinessUnit` anlegen:

- Projekte oder Programme,
- Prozesse oder einzelne Arbeitsschritte,
- Systeme und Plattformen,
- Rollen oder Personen,
- Issues, Evidence-Pakete und technische Testfälle.

Beispiele wie `Issue #106 Evidence`, `Issue #117 Evidence`,
`Block-5-Real-DEMO` oder die `[DEMO]`-Einheiten sind Demo/Test und werden von
produktiven Auswahlfeldern ausgeschlossen.

## Produktive Auswahlfelder

Der gemeinsame Katalogvertrag gilt mindestens für:

- Inbox: Idee oder Problem erfassen,
- Business Discovery: Organisationseinheit der Untersuchung,
- Guided Use-Case-Intake,
- Use-Case-Formular,
- Value Stream anlegen oder neu zuordnen,
- Organisationsfilter der Inbox.

Die Auswahl wird nicht nur im Browser gefiltert. Form-Querysets und der
Discovery-Service validieren den produktiven Scope serverseitig. Ein manipuliertes
POST mit einer Demo/Test- oder Legacy-ID ist für eine neue Zuordnung nicht zulässig.

## Bestehende Referenzen

Historische Beziehungen werden nicht automatisch geändert.

- Ein bestehender Eintrag, Use Case oder Value Stream darf seine bisherige
  Organisationseinheit weiterhin anzeigen.
- Bearbeitungsformulare dürfen die aktuell referenzierte Alt-Einheit anzeigen,
  damit keine stille Umhängung entsteht.
- Neue Zuordnungen und Wechsel verwenden ausschließlich aktive produktive Einheiten.
- Deaktivierung oder Katalogänderung löscht keine bestehenden Beziehungen.

Für bereits gestartete Business Discoveries bleibt der eingefrorene
Untersuchungskontext maßgeblich. Profil- oder Ideenänderungen verschieben einen
laufenden Fall nicht.

## Demo- und Evidence-Daten

Die bekannten Demo-/Evidence-Erzeugungspfade markieren ihre technischen
Organisationseinheiten explizit als `demo_test`. Dazu gehören insbesondere:

- `seed_demo_data`,
- Block-5/Block-6 Real-DEMO,
- #106-Baseline-Evidence,
- #117 Package-3-Evidence,
- #118 Experiment-Fallback.
- VS1/#4-Evidence-Fallback und Block-3/4/5-UI-Prüfungen.

Damit können Demo- und technische Nachweise im selben Datenbestand existieren,
ohne in produktiven Organisationsauswahlen zu erscheinen.

Die isolierte Desktop-Prüfung verwendet die sechs migrierten Katalogeinheiten und
zusätzlich ausgeschlossene Demo-/Legacy-Fixtures. Der #98-Abnahmehelfer verwendet
für neue produktive Discoveries die freigegebene Einheit IT & Digitalisierung;
er legt keine technische produktive Einheit mehr an.

## Bestandsüberführung und Inventar

Die sechs Namen sind durch den Auftrag zu #131/#132 bestätigt. Die Migration
übernimmt exakt gleich benannte vorhandene Einheiten unter ihrer bisherigen ID;
alle übrigen vorhandenen Einheiten erhalten zunächst `legacy`. Sie interpretiert
keine Namensmuster, löscht nichts und verändert keine Fremdschlüssel oder
eingefrorenen Discovery-Antworten. Auch vorhandene `RSD –`-Namen bleiben als
Altbestand erhalten, bis die Administration sie ausdrücklich einordnet.

Die Erzeugungspfade umfassen Administration, diese Migration, `seed_demo_data`,
Block-5/6-Real-DEMO, die #4/#106/#117/#118-Evidence-Helfer und UI-Abnahmehelfer.
Test-Fixtures erzeugen in isolierten Testdatenbanken produktive Einheiten für
positive Tests und explizite Demo/Test-, Legacy- und inaktive Einheiten für
negative Tests. Golden-Path-/Architektur-Demos verwenden bestehende Demo-Einheiten.

Neue Zuordnungen im Admin (Nutzer, Use Case, Value Stream) verwenden denselben
Katalogvertrag wie die produktiven Formulare; nur die eigene aktuelle historische
Zuordnung darf unverändert gespeichert werden. Listen-/Portfoliofilter dürfen
historische Einheiten weiter auffindbar machen; sie erzeugen keine Zuordnung.

Vor einer späteren manuellen Bereinigung ist pro fraglicher Einheit ein Bericht
mit ID, Name, Scope, Aktivität sowie Nutzer-, Ideen-, Value-Stream-, Use-Case- und
Discovery-Referenzen zu erstellen. Discovery-Referenzen liegen zusätzlich als ID
in `CaptureSession.answers.business_unit` vor. Der Bericht muss geplante
Klassifikation und betroffene Referenzen ausweisen. Dieses Issue führt keine
Bereinigung des lokalen produktiven Datenbestands aus.
