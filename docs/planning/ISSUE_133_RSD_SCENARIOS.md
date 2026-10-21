# Issue #133: synthetische fachliche Tests A–D

Für die anschließende methodische Nachprüfung ergänzen getrennte
[Quellenakten und vorab festgelegte Kriterien](../../tests/fixtures/issue133_methodology/)
diese Karten um Widersprüche, Gegenbeispiele und Erwartungsgrenzen. Sie sind kein
Bestandteil der nachstehenden natürlichen Ersttexte. Der aktuelle
[Abnahmebericht](ISSUE_133_METHODICAL_ACCEPTANCE.md) ordnet die tatsächlichen Freigaben
und Ergebnisse zu.

Stand: 21.10.2026. Auftrag: [Issue #133](https://github.com/Satte882/KI-Ideenwerkstatt/issues/133).

**Alles Folgende ist ausdrücklich synthetisch.** Weder die Aussagen noch Rollen,
Abläufe, Unterlagen oder Probleme sind Erkenntnisse über die RSD Touristik GmbH.
RSD bezeichnet hier ausschließlich den Bezug zum Issue. Keine echten Kunden-,
Beschäftigten- oder Buchungsdaten verwenden.

## Testvertrag und Informationsgrenze

1. In die Inbox kommen nur der jeweilige Einstiegstext, ein neutraler Titel und
   die Kennzeichnung als synthetische Testperson. Keine Ursachen, Lösung oder Kennzahl ergänzen.
2. Kontextkarten K1–K3 bleiben zunächst außerhalb der Anwendung. Sie werden erst
   nach einer passenden Frage oder einer ausdrücklich protokollierten manuellen
   Klärung verfügbar. Eine Karte ist eine simulierte Antwort, kein Beleg für die Realität.
3. Je Übernahme notieren: Frage, Karten-ID, Antwort, Zeitpunkt/Schritt, Zielobjekt/-feld,
   Eingebender und Erkenntnisstatus. Allgemeine Fragen geben nicht alle Karten frei.
4. Nutzerbericht, synthetisches Dokument, Testautoren-Hypothese, Messung und menschliche
   Bestätigung auseinanderhalten. Widerspruch ist keine bestätigte Ursache.
5. Originaltext erhalten; spätere Erkenntnisse nicht rückwirkend in den Erstinput einbauen.
   Ein leerer Wert ist kein Nullmesswert. Ersparnis, Marge und Pilotwirkung bleiben unbekannt.
6. Keine verbindliche Ursachenbestätigung, Lösungspräferenz, Freigabe, Übergabe,
   Pilotstart- oder Betriebsentscheidung durch den Testagenten. Stoppen und den
   konkret fehlenden Nachweis benennen. Kein künstlicher KI-Use-Case für die Vollständigkeit.

Die Karten erlauben einen frühen Diagnoseentwurf, **keinen vollständig durchfreigegebenen
Lifecycle**. Für spätere Gate-Tests vorhandene Regressionen separat ausführen;
deren vorbereitete Freigaben und Messwerte sind kein Szenarioergebnis.

## A – Kundenservice: Rückfragen zu einer gebuchten Reise

### Erstinput aus Sicht der Person

> Wenn jemand wegen seiner gebuchten Reise anruft, suche ich oft erst in der Buchung
> und dann noch in alten E-Mails. Manchmal muss ich im Büro nachfragen. Die Person
> wartet am Telefon, und ich kann ihr nicht gleich sagen, was gerade gilt.

### Später verfügbarer Testkontext

| Karte | Mögliche Rückfrage | Ausschließlich synthetische Antwort / Material |
|---|---|---|
| A-K1 | Was wird gefragt, und was tun Sie dann? Wer hilft bei Unklarheit? | Rückfragen nach Transferzeit oder gebuchter Leistung; Person öffnet Buchungsmaske und gemeinsames Postfach, fragt bei Unklarheit die Reiseorganisation. Keine verbindliche Auskunft über widersprüchliche Angaben ohne Rückfrage. Produktnamen und Antwortfrist unbekannt. |
| A-K2 | Können Sie einen konkreten Fall mit den Angaben zeigen? | Erfundenes Beispiel SYN-A-01: Buchungsnotiz nennt Transfer 09:00; spätere Änderungsnachricht nennt 10:00. Zustellung an den Kunden und endgültige Gültigkeit sind nicht dokumentiert. Beide Angaben bleiben getrennt erhalten. Kein Schluss, dass das Unternehmen generell veraltete Daten nutzt. |
| A-K3 | Gibt es Fälle, in denen es gleich klappt? Haben Sie Zeiten gemessen? | Erfundenes Gegenbeispiel SYN-A-02: einfache Leistungsfrage anhand übereinstimmender Buchungsangaben beantwortbar. Keine Zeitstichprobe, Mengen, Fehlerquote oder Kostendaten vorhanden. |

**Bekannt nach Freigabe:** die berichtete Suchfolge und zwei erfundene Einzelfälle.
**Unbekannt:** Häufigkeit, Suchzeit gegenüber Wartezeit, Aktualität und führende Quelle,
Rechte, Arbeitslast, Ursachen, Geschäftsschaden und Eignung einer bestimmten Lösung.
**Weitere Fragen:** Wer entscheidet bei widersprüchlichem Stand? Welche Information darf
welche Rolle sehen? Ist die Nachfrage ausbleibender Information oder deren Auffindbarkeit
geschuldet? Wie kann Antwortkorrektheit unabhängig geprüft werden?

**Prüfkriterien:** Kundenanliegen bis geklärte Antwort abgrenzen; Informationssuche als
Teilphase behandeln. Widerspruch nicht selbst entscheiden. Keine bestätigte Ursache aus
zwei Beispielen ableiten. Organisatorische Klärung, bestehende Software und gegebenenfalls
Suchhilfe offen vergleichen. Für Messung Such-/Wartezeit trennen, Korrektheit und
Wiederholkontakte mitbetrachten. Keine Einsparung aus einer hypothetischen Zeit ableiten.

## B – Geschäftsführung: mehr Buchungen bewältigen

### Erstinput aus Sicht der Person

> Ich möchte mehr Reisen verkaufen. Gleichzeitig können wir nicht immer neue Leute
> einstellen. Ich weiß noch nicht, an welchen Stellen uns mehr Buchungen besonders
> viel zusätzliche Arbeit machen und was wir daran ändern könnten.

### Später verfügbarer Testkontext

| Karte | Mögliche Rückfrage | Ausschließlich synthetische Antwort / Material |
|---|---|---|
| B-K1 | Was soll erreicht werden, was darf darunter nicht leiden? | Mehr Buchungen mit dem vorhandenen Team bewältigen; verlässliche Auskünfte und erreichbarer Service sollen erhalten bleiben. Kein beschlossenes Wachstumsziel, keine Entlassungsvorgabe und kein bestätigter Personalengpass. |
| B-K2 | Welche Arbeitsbereiche und Daten könnten wir betrachten? | Erfundenes Quellenverzeichnis: Buchungslisten, Dienstpläne und grobe Kontaktzählung wären bei zuständigen Personen anzufragen. Noch keine Auszüge, Zeitreihen oder belastbare Zuordnung von Kontakten zu Buchungen verfügbar. |
| B-K3 | Gibt es widersprechende Einschätzungen? | Simulierte Aussage Verkauf: Rückfragen seien aufwendig. Simulierte Aussage Reiseorganisation: kurzfristige Änderungen seien aufwendig. Beides ungemessene Einschätzungen, nicht bestätigte Hauptursachen. |

**Bekannt:** Zielwunsch und unterschiedliche Berichte. **Unbekannt:** tatsächliches
Wachstum, Kapazität, Saisonalität, Leistungsmix, Qualität, Wirtschaftlichkeit und Engpass.
**Weitere Fragen:** Welche Periode und Reisearten vergleichen? Welche Arbeit entsteht
pro zusätzlicher Buchung? Sind Änderungen, Nachfragen und Spitzen getrennt erfassbar?
Wer setzt Scope und akzeptiert den Trade-off zwischen Erreichbarkeit und Aufwand?

**Prüfkriterien:** keine willkürliche Verengung auf Kundenservice; zunächst mehrere
Wertströme/Fokusmöglichkeiten sichtbar machen. Wachstum als Wunsch behandeln, keine
Trendzahlen behaupten. Keine FTE-Ersparnis oder Automationsempfehlung ohne Nachfrage-,
Aufwands- und Qualitätsbasis. Messplan mit vergleichbaren Perioden und Leistungsmix;
Scope/Fokus bleiben menschliche Entscheidungen.

## C – reisende Person: aktueller Stand unterwegs

### Erstinput aus Sicht der Person

> Ich bin gerade auf der Reise. Für morgen habe ich einen Treffpunkt in meinen
> Unterlagen und eine andere Angabe in einer Nachricht. Jetzt bin ich unsicher,
> wo ich wann sein soll und wen ich fragen kann.

### Später verfügbarer Testkontext

| Karte | Mögliche Rückfrage | Ausschließlich synthetische Antwort / Material |
|---|---|---|
| C-K1 | Welche Angaben liegen vor? | Erfundenes Reiseblatt SYN-C-01: 08:30 an der Hotellobby. Erfundenes Nachrichtenfragment: 09:00 am Seiteneingang. Absenderbefugnis und Gültigkeit der Nachricht sind ungeklärt. |
| C-K2 | Wann kam die Nachricht, können Sie jemanden erreichen? | Die Person kann die Reihenfolge der Unterlagen nicht sicher rekonstruieren; sie hat zeitweise keinen Internetempfang. Eine Telefonnummer steht im Reiseblatt, wurde im Test noch nicht angerufen. |
| C-K3 | Was brauchen Sie jetzt; was wäre keine ausreichende Hilfe? | Verbindliche Klärung von Zeit und Ort sowie erreichbare Rückfragemöglichkeit; eine weitere ungeprüfte Nachricht würde die Unsicherheit nicht lösen. Keine Aussage über Verspätung oder tatsächlich verpasste Leistung. |

**Bekannt:** zwei widersprüchliche Angaben und berichtete Unsicherheit. **Unbekannt:**
gültiger Stand, Ursache, Übermittlungs-/Lesebestätigung, betroffene Reisende und Folgen.
**Weitere Fragen:** Wer darf Änderungen bestätigen? Wie gelingt Klärung ohne Empfang?
Wie werden Sprache, Barrierefreiheit und Dringlichkeit berücksichtigt?

**Prüfkriterien:** Kundenergebnis „weiß verlässlich, wo und wann“ erhalten; „ein Ort“
ist ein möglicher Wunsch, keine fertige Portalentscheidung. Neueste Nachricht nicht
automatisch als richtig setzen. Erreichbarkeit und Offline-Alternative berücksichtigen.
Keine automatische Benachrichtigung an echte Personen und keine Auskunft über echten Treffpunkt.

## D – lokaler Partner: Änderung gemeinsam klären

### Erstinput aus Sicht der Person

> Ich organisiere vor Ort die Busse für eine Reisegruppe. Wenn sich etwas ändert,
> telefoniere und schreibe ich mit mehreren Leuten. Danach bin ich manchmal unsicher,
> ob alle Bescheid wissen und ob ich den Bus schon anders bestellen soll.

### Später verfügbarer Testkontext

| Karte | Mögliche Rückfrage | Ausschließlich synthetische Antwort / Material |
|---|---|---|
| D-K1 | Welche Änderung und welche Beteiligten meinen Sie? | Erfundenes Beispiel SYN-D-01: Reiseorganisation fragt spätere Abholung an; Partner fragt Busunternehmen und Reiseleitung. Eine Anfrage ist noch kein bestätigter Auftrag. |
| D-K2 | Welche Antworten liegen vor, was ist offen? | Simulierte Busantwort: spätere Abholung grundsätzlich möglich, zusätzlicher Preis noch offen. Von der Reiseleitung fehlt die Bestätigung des Treffpunkts. Kein endgültiger Stand und keine Kostenfreigabe. |
| D-K3 | Wer darf bestellen oder Mehrkosten genehmigen? | Die Testperson kann Angebote einholen. Befugnis für verbindliche Änderungen und Mehrkosten ist nicht geklärt; Frist und Eskalationskontakt müssen erfragt werden. |

**Bekannt:** angefragte Änderung und zwei offene Punkte. **Unbekannt:** Entscheidungsrechte,
Vertrag, Datenzugang über Unternehmensgrenzen, Frist, Kosten und tatsächliche Auswirkung.
**Weitere Fragen:** Wer bestätigt Leistung, Information und Zahlung jeweils? Was bedeutet
Schweigen? Wie werden konkurrierende Änderungen und veraltete Rückmeldungen behandelt?

**Prüfkriterien:** Anfrage, Angebot, Bestätigung und Freigabe trennen; Schweigen ist
keine Zustimmung. Keine interne Zuständigkeit gegenüber einem Partner unterstellen.
Organisatorische Abstimmung und vorhandene Werkzeuge vor neuer Plattform/KI prüfen.
Verbindliche Bestellung und Mehrkostenfreigabe nicht durch den Agenten ersetzen.

## Gemeinsame Bewertung

Pro Stufe separat: **erfüllt / teilweise / offen / nicht geprüft**, mit Beleg und Eingreifendem.
Kein Summenscore. Fachlich prüfen: Problemtreue, passende Grenze des Wertstroms,
Trennung Beobachtung/Ursache, Gegenbelege, Lösungsoffenheit, Herkunft, Messbarkeit,
Rollen und begründeter Endpunkt. Ein korrektes Stoppen ist kein Nachweis einer
erfolgreichen Problemlösung, aber besser als ein erfundener Abschluss.

Quellenrahmen: `README.md`, `SETUP.md`, `AGENTS.md`, `docs/ROADMAP.md`,
`docs/DISCOVERY_ARCHITECTURE.md`, `docs/VALUE_STREAM_METHODOLOGY.md`,
`docs/DECISION_METHOD.md`, `docs/DELIVERY_METHODOLOGY.md`, `docs/SCALE_READINESS.md`,
ADRs 0007/0008 sowie `docs/planning/AGENTIC_TEST_CHARTER.md`.
Der Charter wird für Clean State, Lösungsoffenheit und valide Stopps wiederverwendet;
dieser #133-Lauf ist kein delegierter, verblindeter Browser-Test nach #428.
