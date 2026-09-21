# Block 3 – Retention und Löschung

## Geltungsbereich

Diese Regel gilt ausschließlich für die in Block 3 eingeführten `CaptureSession`-Rohantworten. Sie ist keine allgemeine Retention-Plattform und verändert keine regulären Fachobjekte.

## Entwürfe

- Jeder neue Entwurf erhält ein Ablaufdatum 30 Tage nach Anlage.
- Jede erfolgreiche fachliche Speicherung setzt das Ablaufdatum erneut auf 30 Tage nach der letzten Aktivität.
- Überfällige Entwürfe wechseln kontrolliert in den Zustand `expired` und sind danach nicht mehr bearbeitbar.

## Verworfen und abgelaufen

- `discarded` ist eine ausdrückliche irreversible Nutzerentscheidung.
- `expired` und `discarded` werden nach einer Karenz von sieben Tagen physisch gelöscht.
- Das idempotente Management Command `python manage.py purge_capture_sessions` führt Zustandswechsel und physische Bereinigung aus.
- Die Karenz kann betrieblich über `--grace-days` angepasst werden; negative Werte sind unzulässig.

## Abgeschlossene Sessions

Abgeschlossene Sessions bleiben in Block 3 erhalten, weil sie die Eingangsquelle für die spätere Blueprint-Extraktion in Block 4 bilden. Das ist ausdrücklich ein Zwischenzustand und keine Freigabe für unbegrenzte Aufbewahrung.

Vor produktiver Nutzung der Block-4-Extraktion muss eine Folgeregel festlegen:

1. wie lange abgeschlossene Rohantworten nach erfolgreicher Blueprint-Erzeugung benötigt werden,
2. ob Rohantworten anschließend gelöscht, minimiert oder getrennt archiviert werden,
3. wie Löschung und Nachweis bei fehlgeschlagener oder wiederholter Extraktion funktionieren,
4. welche Verantwortlichkeit und Rechtsgrundlage für sensible Freitexte gilt.

Bis diese Regel umgesetzt ist, darf Block 4 abgeschlossene Sessions lesen, aber keine unbegrenzte produktive Rohdatenhaltung als Zielzustand deklarieren.
