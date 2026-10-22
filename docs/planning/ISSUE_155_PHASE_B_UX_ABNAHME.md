# Issue #155 – Phase B: F1–F6

Arbeitsstand 22.10.2026. Die Browser-Abnahme und die vollständige CI werden vor der Übergabe ergänzt. Keine Freigabe zum Mergen.

## Auftrag und Freigaben

Grundlage ist die [Phase-B-Freigabe mit Feedback](https://github.com/Satte882/KI-Ideenwerkstatt/issues/155#issuecomment-6346485531). Alle 60 Originalbilder der Phase A wurden vor den Produktänderungen einzeln visuell geöffnet und mit den Befunden abgeglichen. Die ursprünglichen Nachweise bleiben unverändert; Zuordnung siehe `ISSUE_155_SCREENSHOT_INDEX.md`.

Die ursprünglich ausgeschlossene Migration wurde für F2 ausdrücklich separat freigegeben. Antwort des Nutzers am 22.10.2026 im zugehörigen Codex-Chat: „Ein Feld plus Migration für F2 freigeben“. Diese Ausnahme umfasst ausschließlich das optionale JSON-Feld am bestehenden Vorhaben sowie die additive Migration einschließlich Historienmodell. V1–V3 werden nicht umgesetzt.

## Umsetzung

| Befund | Änderung | Technische Grenze |
| --- | --- | --- |
| F1 | „Vorhaben laden“ zeigt zunächst Ersetzen/Behalten. Auch unvollständige Eingaben bleiben bis zur ausdrücklichen Auswahl erhalten. | Laden und Abbrechen speichern nichts. |
| F2 – separate Speicheraufgabe | Unbestätigter Pfadkontext wird im bestehenden Vorhaben nach Herkunftsobjekt gespeichert und nach Redirect/Login wieder geladen. | Bestehende Revision, Rechte und Transaktion; keine verbindliche Pfad-/Fokusentscheidung durch Entwurf. Erst erfolgreiche ausdrückliche Bestätigung entfernt den Entwurf. |
| F3 | Vergleich nennt die tatsächlichen Outcome-Blocker vor der Auswahl und verlinkt die Vorbereitung. | Bestehende serverseitige Entscheidungsgates bleiben maßgeblich. |
| F4 | Outcome, Vorhaben, Capability und Wirkungsprüfung besitzen passenden Hauptbereich und lokale aktuelle Position. | Direktes Use-Case-Outcome bleibt im Use-Case-Kontext. |
| F5 – separate Aufrufaufgabe | Auswahl erzeugt den kanonischen KI-Use-Case ohne automatische Planung. Bestehende Planung läuft erst über „KI-Planungsentwürfe kostenpflichtig erstellen“, mit Hinweis und Rückmeldung. | Bestehende Planungsdienste, Provenance, Fehlerbehandlung und Governance bleiben erhalten. |
| F6 | Beschriftete bestehende Seitennavigation auch bei 1024 px; lokale Beschriftungen dürfen umbrechen. | Vorhandenes Layout und Design-Tokens; kein neuer Navigationsmodus. |

## Prüfbedingungen

Isolierte Kopie synthetischer Testdaten; echter sichtbarer Chromium-Browser. Keine echten LLM-Aufrufe: Schlüssel leer, externe Netzwerkverbindungen gesperrt, deterministische Antworten ausschließlich an der Provider-Grenze. Fachliche Dienste werden im Browser unverändert durchlaufen. Diese Prüfung bewertet Ablauf, Zustand, Rechte und Darstellung; sie belegt keine Qualität echter Modellantworten und keine Geschäftswirkung.

Weitere Klickpfade, Originalbild-Abgleich, Screenshot-Matrix, Rollenprüfung und CI-Ergebnisse werden nach Abschluss der laufenden Prüfungen hier ergänzt.
