# Architecture Advisor – UI-Playbook

Dieses Playbook enthält ausschließlich manuelle Klick- und Prüfschritte für die bestehende SolutionOption-Oberfläche.

## Einstieg

1. Öffne einen Value Stream mit vorhandener Prozessanalyse.
2. Öffne eine vorhandene Lösungsoption zur Bearbeitung.
3. Prüfe, dass der Bereich **Architektur-Einschätzung** innerhalb der bestehenden Lösungsoptions-Oberfläche erscheint und keine neue Hauptnavigation geöffnet wird.
4. Prüfe, dass exakt vier Fragen sichtbar sind und jede ausschließlich `Ja`, `Nein` oder `Unklar` anbietet.

## Fall 1 – No LLM required

1. Setze die Antworten auf `Ja / Nein / Nein / Nein`.
2. Speichere die Architektur-Einschätzung.
3. Prüfe den Architecture Mode **No LLM required**.
4. Prüfe, dass **Warum dieses Muster?** erklärt, dass eine einfachere deterministische Lösung ausreicht.
5. Prüfe, dass kein Abschnitt **Warum kein Agent?** angezeigt wird.

## Fall 2 – Controlled LLM

1. Setze die Antworten auf `Nein / Ja / Nein / Nein`.
2. Speichere.
3. Prüfe den Architecture Mode **Controlled LLM**.
4. Prüfe **Warum dieses Muster?**.
5. Prüfe, dass **Warum kein Agent?** sichtbar ist und die fehlende Notwendigkeit dynamischer Orchestrierung erklärt.

## Fall 3 – LLM Workflow

1. Setze die Antworten auf `Nein / Ja / Ja / Nein`.
2. Speichere.
3. Prüfe den Architecture Mode **LLM Workflow**.
4. Prüfe, dass **Warum dieses Muster?** den fest vorgegebenen Mehrschritt-Ablauf erklärt.
5. Prüfe, dass **Warum kein Agent?** sichtbar ist und auf den vorab bekannten Ablauf verweist.

## Fall 4 – Bounded Agent

1. Setze die Antworten auf `Nein / Ja / Nein / Ja`.
2. Speichere.
3. Prüfe den Architecture Mode **Bounded Agent**.
4. Prüfe, dass **Warum dieses Muster?** die notwendige dynamische Schritt-/Toolwahl nennt.
5. Prüfe, dass kein Abschnitt **Warum kein Agent?** angezeigt wird.

## Fall 5 – Widerspruch

1. Setze die Antworten auf `Ja / Ja / Nein / Nein`.
2. Speichere.
3. Prüfe den Architecture Mode **Assessment open**.
4. Prüfe, dass als offener Punkt ein Widerspruch zwischen ausreichender einfacherer Lösung und gleichzeitig erforderlichem semantischem Reasoning sichtbar wird.

## Fall 6 – Unzureichende Information

1. Setze die Antworten auf `Unklar / Nein / Nein / Nein`.
2. Speichere.
3. Prüfe den Architecture Mode **Assessment open**.
4. Prüfe, dass der offene Punkt fehlende entscheidende Information verständlich benennt.

## Vergleichsansicht

1. Öffne anschließend die bestehende Lösungsvergleichsansicht derselben Prozessanalyse.
2. Prüfe pro Lösungsoption die kompakte Architektur-Zeile.
3. Prüfe, dass die vorhandenen Bewertungs-, Auswahl- und Empfehlungsanzeigen unverändert vorhanden sind.
