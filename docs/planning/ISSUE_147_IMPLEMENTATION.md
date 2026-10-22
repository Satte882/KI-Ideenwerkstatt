# #147 – Gemeinsamer aktueller Wirkungsreview

Basis: `main@f893c0f`, ADR 0009 und Schnittstellen aus #146 / PR #151.

## Minimaler Vertrag

`ImprovementInitiative` bleibt Outcome-Träger und Source of Truth für Owner,
Geschäftsergebnis, Wirkannahme, Status, Review-Termin sowie `effect_status/effect_reason`.
`InitiativeImpactReview` ergänzt genau einen aktuellen Review-Stand pro Vorhaben:
Interventionsreferenz, Non-KI-Prozessbefund, eigene Geschäftsergebnismessung mit
Nachweis, Abgrenzung und getrennte Attribution. Keine neue Lifecycle-Engine.
Textuelle Messdefinition und aktueller Stand dürfen qualitative Kriterien enthalten;
Methode, Zeitraum, Population und Nachweis werden ausdrücklich abgefragt. Unbekannt
bleibt leer / noch ungeklärt; keine Default-Nullwerte oder ROI-Ableitungen.

`save_impact_review` verwendet die bestehenden Vorhabensrechte, Row-Lock,
Optimistic-Lock und `save_initiative` für die gemeinsame Wirkungsaussage. Ein
expliziter Prüfabschluss verlangt Intervention und begründete Aussage; „ungeklärt“
ist zulässig. Bestätigte/widerlegte Geschäftsergebnisse benötigen einen eigenen
Messstand und Nachweis. Attribution ist separat und benötigt bei einer positiven
oder negativen Aussage eine Begründung mit Evidenzgrenzen. Keine automatische
Bestätigung durch Prozessziel, Lösungsauswahl oder fachliche Hypothesenannahme.

KI-Prozessmetriken bleiben ausschließlich `UseCase.metric_*`. Der Review speichert
nur den Use-Case-FK und die ID seines Original-Historienstands. Darstellung liest
aktuelle Originaldaten über bestehende Metric-Presentation; keine editierbaren
Messwertkopien und keine Aggregation mehrerer Use Cases. Bei zusätzlicher
Geschäftsergebnismessung muss der Mensch ihre inhaltlich andere Größe erklären.
Diese fachliche Abgrenzung kann nicht durch Textvergleich kausal bewiesen werden.
Entscheidungs-/Use-Case-Referenzen müssen zum selben Vorhaben und bei gemeinsamer
Referenz zur selben Ursprungskette gehören.

Die bestehende Simple-History erhält Bearbeiter und ältere Review-Stände als Audit,
keine fachliche Messreihe. Vorhabensrevision, Outcome-Revision und Original-Messstand
referenzieren die geprüfte Grundlage. Änderungen am Vorhaben (konservativ auch
Metadaten), Use Case oder stale Lösungsentscheidung erzeugen einen Hinweis zur
Neubewertung; sie ändern keine alten Auswahl-/Freigabesnapshots und keine Gates.

## Bedienung und Bestand

Vorhabenseite und vorhandene Dashboard-Kategorie zeigen offene Prüfungen.
Lösungsvergleich und Wirkung-&-Betrieb-Workspace verlinken denselben Vorhabenstand.
Bearbeitungsformular hat getrennte Befehle zum Entwurfsspeichern und Prüfabschluss;
fehlgeschlagene Prüfung behält Eingaben. Fehlende Nachweise blockieren keinen Intake.
Vorhandene Abschluss-/Abbruchregeln werden wiederverwendet, nicht verschärft.
Nach fehlgeschlagenen Änderungen liest die Zusammenfassung den gespeicherten
Stand neu; ungespeicherte Eingaben erhalten nie den Prüfzeitpunkt eines alten Reviews.
Gespeicherte Wirkungsaussagen bleiben vollständig editierbar. Ohne aktuellen
Prüfabschluss erscheinen sie ausdrücklich als „Ungeprüfte Wirkungsaussage (Entwurf)“;
dies gilt auch nach späteren Entwurfsänderungen eines vormals geprüften Reviews.
Prozessbefund und Attribution kennzeichnen ungeprüfte Entwürfe ebenso. Historische
Vorhabensaussagen sind dokumentierte Aussagen, kein eigenständiger Prüfnachweis.
Der konservative Review-Hinweis bei reinen Use-Case-Metadatenänderungen bleibt gemäß
Review als nicht blockierende Beobachtung außerhalb dieser Korrektur.

Migration 0017 legt ausschließlich Review-/Audit-Tabellen an. Keine Backfills,
keine Kohortenänderung und keine Änderung an Governance-, Review-, Pilot-, Go-live-
oder Use-Case-Messservices. Non-KI benötigt keinen Use Case.

## Prüfung und Abgrenzung

Gezielte Gegenproben: `tests/test_issue_147_impact_reviews.py`, ergänzt um die
bestehenden #145/#146-, Intake-, Review-, Outcome-Workspace- und Messregressionen.
Vollständiger CI-Nachweis steht im PR. Der lokale Caller-Abgleich umfasst Vorhaben,
Messfelder, Lösungsentscheidungen, Outcome Workspace, Scan/Dashboard und Exporte;
keine Änderung an bestehenden Export-/Governance-Contracts notwendig.
Desktop-Prüfung bei 1440 × 1000: Originalmetrik und offene Geschäftswirkung getrennt
sichtbar, Prüfablehnung mit erhaltenen Eingaben und anschließender Entwurfsspeicherung.
Mobil/Tablet sind gemäß Nutzerauftrag kein Abnahmescope.

#148 benötigt für die unveränderte Trennung von Learning Value und Business Value
keine neue technische Abhängigkeit. Es bleibt separat zu priorisieren; kein neuer
Experimentstatus, kein Synchronisationsadapter und keine Messreihenplattform.
