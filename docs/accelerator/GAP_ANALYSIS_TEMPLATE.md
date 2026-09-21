# Accelerator Gap-Analyse

**Block / Issue:**  
**Geprüfter Branch:** `main`  
**Geprüfter Commit:**  
**Prüfdatum:**  
**Bearbeiter:**  

## 1. Ziel und Scope des Blocks

- Welcher konkrete Nutzer- oder Technikzustand soll nach dem Block existieren?
- Welche Abhängigkeiten aus früheren Blocks sind verbindlich?
- Welche Nicht-Ziele und Gate-Grenzen gelten?

## 2. Repository-Evidenz

| Prüfbereich | Geprüfte Dateien, Modelle, Forms oder Services | Bestätigter Befund |
|---|---|---|
| Domänenobjekte |  |  |
| Forms und Validierung |  |  |
| Domain Services und Transaktionen |  |  |
| Berechtigungen und Rollen |  |  |
| Historisierung und Audit |  |  |
| Quellen, Snapshots und Staleness |  |  |
| UI, Navigation und bestehende Workflows |  |  |
| Tests und Referenzdaten |  |  |
| Konfiguration, Logging und Betrieb |  |  |
| Dokumentation |  |  |

## 3. Bereits vorhandene Bausteine

- Was kann unverändert wiederverwendet werden?
- Welche bestehenden Forms oder Services sind der maßgebliche Schreibpfad?
- Welche bestehenden Seiteneffekte müssen erhalten bleiben?
- Welche Tests schützen das Verhalten bereits?

## 4. Nicht bestätigte Planannahmen

| Annahme aus dem Issue | Repository-Befund | Konsequenz |
|---|---|---|
|  |  |  |

Keine Negativsuche allein als Beweis verwenden. Relevante Dateien und Laufpfade direkt prüfen.

## 5. Widersprüche und veraltete Dokumente

- Welche Dokumente oder Kommentare beschreiben einen älteren Stand?
- Welches Artefakt ist autoritativ?
- Wird ein alter Stand gelöscht, als historisch markiert oder fachlich aktualisiert?

## 6. Minimale repo-spezifische Lösung

- Kleinste unterstützte Objekt- und Feldmenge:
- Wiederverwendete Forms und Services:
- Neue Dateien oder Modelle:
- Erforderliche Migrationen:
- Atomaritätsgrenze:
- Fehler- und Rollback-Verhalten:
- Bewusst nicht gebaute Abstraktionen:

## 7. Abweichungen vom Issue-Plan

| Abweichung | Repository-Grund | Risiko | Dokumentation im PR |
|---|---|---|---|
|  |  |  |  |

## 8. Risiken und Schutzmaßnahmen

- Datenverlust oder Teiländerungen:
- Umgehung von Rollen oder Gates:
- Stale Sources und konkurrierende Änderungen:
- unzulässige LLM-Erfindungen:
- Datenschutz und Logging:
- Kosten, Rate Limits und Provider-Ausfall:
- Rückwärtskompatibilität:

## 9. Validierung und Abnahme

| Abnahmekriterium des Issues | Implementierungsnachweis | Testnachweis |
|---|---|---|
|  |  |  |

Mindestens prüfen:

- Erfolgsfall,
- fehlende Berechtigung,
- ungültige Eingabe,
- konkurrierende Änderung,
- Teilfehler und Rollback,
- unzulässige Felder oder Zustände,
- bestehende Gates und Rollen,
- relevante Golden-Path-Regression.

## 10. Entscheidung vor Coding

- **Empfohlener Zuschnitt:**
- **Begründung:**
- **Nicht umgesetzte Alternativen:**
- **Offene fachliche Entscheidung, die Coding tatsächlich blockiert:** keine / Beschreibung

Wenn keine blockierende fachliche Entscheidung besteht, beginnt die Umsetzung ohne zusätzliche Rückfrage.