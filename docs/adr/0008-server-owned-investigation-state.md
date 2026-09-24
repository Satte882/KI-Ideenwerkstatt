# ADR 0008: Evidence-State gehört dem Server

## Status

Akzeptiert am 24.09.2026.

## Kontext

Die 19 lokalen Kalibrierungsruns der Variante A belegen wiederkehrende Ausfälle
des alten Planner-Vertrags. Ein Planner-Response musste gleichzeitig Werkzeug,
Parameter, Claim Register, Decision Brief, Quellenrelevanz, Fortschritt und
Klärung liefern. A/1–A/2 scheiterten am Werkzeugvertrag, A/5–A/6 an der
Aktionsform, A/14–A/19 unter anderem an Fortschritt, Zustandstransport und
ausbleibender Synthese. Providerfehler in A/7–A/9 und gekappte Antworten in
A/12–A/13 sind zusätzliche, nicht allein durch den Vertrag erklärbare Ursachen.

## Entscheidung

- In der Investigation liefert das Modell nur die nächste Werkzeugaktion oder
  eine entscheidungsrelevante Klärung. Das Antwortschema enthält keine Claims,
  keinen Brief, keine Quellenrelevanz und keine Fortschrittsmeldung.
- Die Runtime hält Quellen, Werkzeugresultate, Abdeckung und Fortschritt im
  bestehenden InvestigationRun und seinen unveränderlichen Werkzeugschritten.
- Nach abgeschlossener Evidence-Abdeckung erhält ein eigener Synthesizer den
  vollständigen gespeicherten Verlauf. Er erzeugt Claim Register, Decision
  Brief und Quellenrelevanz als ein validiertes Package.
- Ein unabhängiger Verifier prüft danach die gespeicherte Package-Revision.
  Bestehende Provenance-, Stopppolicy-, Budget- und Freigabe-Gates bleiben aktiv.
- Der Syntheseaufruf bekommt eine eigene Modellrolle und eine reservierte
  Kapazität im Runbudget. Die Reservierung wird aus dem bestehenden Runbudget
  und den erlaubten Repair-Zyklen abgeleitet (ein Syntheseaufruf je
  Verifikationsrunde); Transport, Retry und Timeout laufen unverändert über den
  gemeinsamen Providerpfad. Es entstehen keine zusätzlichen
  Synthesizer-Grenzwerte für Token, Timeout oder Budget.
  Prompt-, Schema- und Loop-Versionen sind eingefroren.

## Konsequenzen

Das Modell schreibt bei Werkzeugschritten keinen fachlichen Gesamtzustand mehr
zurück. Bereits laufende Runs mit altem Ausführungsvertrag bleiben historisch
lesbar, können mit der neuen Version aber nicht still fortgesetzt werden.
Eine neue reale Qualitätsmessung ist für den Wirksamkeitsnachweis weiterhin nötig;
die Änderung selbst löst keine kostenpflichtige Kalibrierung aus.
