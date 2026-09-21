# MoSCoW-Scope-Priorisierung im Delivery Package – Analyse

Issue: #424  
Analysierter Stand: `main` @ `1d0716c39e251e5942206743be7c23670991081f`  
Datum: 2026-09-13

## 1. Ergebnis in einem Satz

MoSCoW gehört vollständig in den bestehenden Bounded Context **Delivery & Handover** und in die vorhandene Sektion `scope_and_users`; die kleinste belastbare Modellierung ist **kein zweiter vollständiger Vier-Felder-Scope**, sondern die Weiterverwendung von `mvp_scope` als verpflichtender **Must-/Minimum-Scope** plus drei optionale Delivery-Angaben für **Should**, **Could** und **Won't this time**.

`in_scope` und `out_of_scope` bleiben unverändert die übernommenen fachlichen Scope-Grenzen. Requirements und Backlog bleiben Umsetzungsartefakte. Es entsteht keine neue Lifecycle-, Governance-, Bewertungs- oder Readiness-Stufe.

## 2. Entscheidungsrahmen

Die Leitfrage ist nicht, wie sich vier MoSCoW-Felder möglichst direkt ergänzen lassen, sondern:

> Welche kleinste Änderung ergänzt echte Scope-Priorisierung, ohne bestehende Scope-Semantik, Ownership oder Delivery-Methodik zu duplizieren?

Daraus folgen für diese Analyse vier Regeln:

1. **Bestehende Semantik schützen.** `in_scope`, `out_of_scope` und `mvp_scope` werden nicht nur wegen der Einführung einer bekannten Methode neu definiert.
2. **Delivery bleibt Owner.** MoSCoW konkretisiert einen bereits freigegebenen Lieferumfang; es trifft keine neue Portfolio-, Governance- oder Lifecycle-Entscheidung.
3. **Kein Scheingenauigkeitsmodell.** Ohne itembezogene Aufwandsschätzungen gibt es keine technische 60-%-Berechnung.
4. **Bestehende Mechanik wiederverwenden.** Sektion, Rechte, Review-Reset, Package-Versionierung und Handover bleiben die vorhandenen Delivery-Verträge.

## 3. Ist-Inventar: Scope, MVP, Requirements und Backlog

### 3.1 Persistenz und Section-Zuordnung

`DeliveryPackage` hält heute alle betrachteten Inhalte als freie Textfelder. Für MoSCoW relevant sind insbesondere:

| Feld | Heutiger fachlicher Zweck | Section | Struktur |
|---|---|---|---|
| `in_scope` | positive fachliche Scope-Grenze / was grundsätzlich zum betrachteten Lieferkontext gehört | `scope_and_users` | `TextField` |
| `out_of_scope` | explizite negative Scope-Grenze / was grundsätzlich nicht dazugehört | `scope_and_users` | `TextField` |
| `users_and_scenarios` | Nutzer und Anwendungssituationen | `scope_and_users` | `TextField` |
| `mvp_scope` | kleinster Ende-zu-Ende-Ablauf für die Nutzenvalidierung | `scope_and_users` | `TextField` |
| `functional_requirements` | funktionale Umsetzungsanforderungen | `requirements_and_governance` | `TextField` |
| `initial_backlog` | initialer Umsetzungsrahmen / Backlog | `delivery_control` | `TextField` |

`DELIVERY_SECTION_DEFINITIONS` enthält bereits die Sektion:

```text
scope_and_users = "Scope, Nutzer und MVP"
```

`SECTION_FIELDS` ordnet ihr genau `in_scope`, `out_of_scope`, `users_and_scenarios` und `mvp_scope` zu. Eine Änderung an einem dieser Felder wird daher bereits als Änderung derselben fachlichen Sektion behandelt.

### 3.2 Herkunft / Source

Die heutige Herkunft ist nicht für alle vier Felder gleich:

- `in_scope` wird bevorzugt aus `ValueStream.scope_in` übernommen; ohne Architecture-Origin greift ein Use-Case-Fallback (`summary`, danach `affected_process`).
- `out_of_scope` wird bei vorhandenem Architecture-Origin aus `ValueStream.scope_out` übernommen.
- `users_and_scenarios` wird aus `UseCase.intended_users`, alternativ `target_users`, übernommen.
- `mvp_scope` besitzt bewusst **keine automatische Evidence-Mapping-Regel**. Im klassischen Seeder wird nur ein generischer Arbeitsauftrag erzeugt; bei aktivem Evidence Mapper bleibt das Feld als echte Delivery-Lücke leer.
- `functional_requirements` und `initial_backlog` sind ebenfalls ausdrücklich von automatischer Block-8-Befüllung ausgeschlossen.

Damit ist `scope_and_users` fachlich bereits heute nicht rein `INHERITED`: drei Felder sind übernommen, während `mvp_scope` in Delivery konkretisiert werden muss. Die aktuelle Section-Origin-Klassifikation ist gröber als die tatsächliche Feldherkunft.

### 3.3 Readiness und Reviews

Für Readiness-Schema 2 sind in `READY_REQUIRED_FIELDS["scope_and_users"]` alle vier heutigen Felder Pflicht:

- `in_scope`
- `out_of_scope`
- `users_and_scenarios`
- `mvp_scope`

Leere oder generische Platzhalter blockieren `READY`. Zusätzlich muss die Section Review vorhanden, mit Source Manifest versehen und fachlich bestätigt sein.

`SECTION_REVIEW_REQUIREMENTS["scope_and_users"]` verlangt ausschließlich die **fachliche** Bestätigung. Das passt zur Scope-Priorisierung: MoSCoW benötigt keinen zusätzlichen technischen Approval-Pfad.

`DeliveryPackageForm._changed_sections()` leitet über `SECTION_FIELDS` die betroffene Sektion ab. `reset_section_reviews()` setzt bei Änderungen der Sektion den Review-Status auf `NEEDS_REVIEW`, löscht vorhandene Bestätigungen und setzt ein bereits `READY` markiertes Package zurück auf `DRAFT`.

### 3.4 Versionierung und Handover

`DeliveryPackage` ist versioniert. Eine übergebene Package-Version ist unveränderlich; spätere Änderungen gehören in eine neue Arbeitsversion. Das bestehende Modell ist deshalb bereits die richtige Versionierungsgrenze für MoSCoW. Eine eigene MoSCoW-Versionierung wäre doppelt.

Readiness-Schema 1 wird für alte bereits übergebene Packages bewusst nicht rückwirkend neu bewertet. Diese bestehende Backward-Compatibility-Regel ist für die spätere Umsetzung wichtig.

## 4. Aktuelles Mapping: Section → Felder → Origin → Review → Readiness → Export/AI

| Section / Feld | Origin heute | Review | Readiness | Export | AI / Mapping |
|---|---|---|---|---|---|
| `scope_and_users.in_scope` | Value Stream, sonst Use Case | Business | Pflicht | unter „Scope / Im Scope“ | Evidence Mapping erlaubt; Quelle für MVP-AI |
| `scope_and_users.out_of_scope` | Value Stream bei Architecture-Origin | Business | Pflicht | unter „Scope / Nicht im Scope“ | Evidence Mapping erlaubt; Quelle für MVP-AI |
| `scope_and_users.users_and_scenarios` | Use Case | Business | Pflicht | „Nutzer und Szenarien“ | Evidence Mapping erlaubt; Quelle für MVP-AI |
| `scope_and_users.mvp_scope` | Delivery-seitig zu konkretisieren | Business | Pflicht | eigener Abschnitt „MVP-Scope“ | automatisches Evidence Mapping verboten; eigener AI-Draft vorhanden |
| `requirements_and_governance.functional_requirements` | Delivery-seitig zu konkretisieren | Technical | Pflicht | „Funktionale Anforderungen“ | automatisches Evidence Mapping verboten |
| `delivery_control.initial_backlog` | Delivery-seitig zu konkretisieren | Business + Technical | Pflicht | „Initiales Backlog“ | automatisches Evidence Mapping verboten |

Wichtig: Das Source Manifest dokumentiert die übernommenen Feldquellen. Ein neues Delivery-eigenes Priorisierungsfeld braucht **keine erfundene Upstream-Quelle**. Die gemischte Herkunft wird korrekt über `ContentOrigin.MIXED` auf Section-Ebene ausgedrückt.

## 5. Fachliche Abgrenzung: MoSCoW versus bestehende Felder

### `in_scope`

`in_scope` beantwortet: **Was gehört grundsätzlich zum fachlichen Lösungs-/Lieferkontext?**

Es ist kein Synonym für `Must`. Ein Element kann innerhalb des grundsätzlich akzeptierten Scope liegen und trotzdem für die aktuelle Delivery-Version nur `Should`, `Could` oder `Won't this time` sein.

### `out_of_scope`

`out_of_scope` beantwortet: **Was gehört grundsätzlich nicht zum betrachteten Scope?**

Es ist kein Synonym für `Won't this time`. `Won't this time` bedeutet gerade, dass etwas fachlich grundsätzlich relevant sein kann, aber bewusst **nicht in dieser Delivery-Version / diesem Inkrement** umgesetzt wird. `out_of_scope` ist eine Grenze; `Won't this time` ist eine zeit-/inkrementbezogene Priorisierungsentscheidung innerhalb dieser Grenze.

### `mvp_scope`

`mvp_scope` beantwortet bereits: **Was ist der kleinste belastbare Ende-zu-Ende-Umfang, der umgesetzt werden muss, um den Nutzen zu validieren?**

Das überschneidet sich direkt mit der im Issue gewünschten `Must`-Semantik. Ein zusätzliches Feld `must` würde daher zwei konkurrierende Quellen für denselben Minimum-Scope schaffen.

Empfehlung: `mvp_scope` bleibt das kanonische Persistenzfeld und wird in der UI / Methodik als **„Must / MVP-Scope“** erklärt. Technisch gilt wie heute: nichtleer = mindestens ein belastbarer Must-/Minimum-Scope ist dokumentiert. Eine künstliche Zählung einzelner Must-Items wird nicht eingeführt.

### `functional_requirements`

Requirements beschreiben **was die Lösung funktional leisten muss**. MoSCoW beantwortet dagegen **welcher Teil des zulässigen Lieferumfangs in diesem Inkrement welche Priorität besitzt**. Requirements können die priorisierten Scope-Entscheidungen später detaillieren, sind heute aber nur Freitext und besitzen keine stabilen Item-IDs. Eine MoSCoW-Priorität auf Requirements zu legen würde daher ein neues Requirement-Modell voraussetzen und ist nicht Teil der kleinsten Lösung.

### `initial_backlog`

Das Backlog beschreibt die **Umsetzungszerlegung / Startarbeit**. Es ist nicht der fachliche Source of Truth für Scope-Priorität. Auch hier existieren heute keine strukturierten Backlog-Items oder Aufwandspunkte, an die MoSCoW sauber gebunden werden könnte.

## 6. Variantenvergleich A–D

| Kriterium | A – bestehende `scope_and_users` erweitern | B – bestehende Scope-Felder in MoSCoW umdeuten | C – neue Delivery-Section | D – eigenes Domainobjekt |
|---|---|---|---|---|
| Fachliche Redundanz | **niedrig**, wenn `mvp_scope` als Must wiederverwendet wird | hoch; Boundary und Priorität werden vermischt | mittel bis hoch; gleiche Verantwortung in zwei Sections | hoch ohne eigenständigen Lifecycle |
| Ownership / SoT | **klar: DeliveryPackage** | gefährdet Upstream-/Delivery-Trennung | weiterhin Delivery, aber künstlich gesplittet | zusätzlicher SoT ohne Nutzen |
| DDD-Konsistenz | **hoch** | gering | mittel | gering |
| UX | **eine bestehende Scope-Section** | zunächst kompakt, semantisch aber schwer verständlich | zusätzlicher Navigations-/Review-Schritt | zusätzliche UI und Relation |
| Persistenz | 3 optionale neue Textfelder; `mvp_scope` bleibt | Bestandsfelder müssten migriert/neu interpretiert werden | zusätzliche Felder plus Section-Vertrag | neues Modell/Relationen |
| Readiness | bestehendes Must-Kriterium bleibt | bestehende Guards müssten umgebaut werden | neue Section-/Readiness-Semantik nötig | zusätzliche Invarianten nötig |
| Section Reviews | bestehender Business-Review | bestehende bestätigte Semantik wird entwertet | neue Review-Instanz erforderlich | eigener Review-Pfad wahrscheinlich nötig |
| Versionierung / Handover | **bestehende Package-Version reicht** | Migrations-/Interpretationsrisiko | weiter Package, aber zusätzlicher Section-Zustand | doppelte Versionierungsfrage |
| Migration | klein und kontrollierbar | hoch | mittel | hoch |
| Export | Scope-Block gezielt erweitern | alte Exporte semantisch ändern | neue Exportsektion | neue Serialisierung |
| AI Draft | vorhandenen `mvp_scope`-Assist nur sprachlich schärfen | Prompt-/Quellenlogik stark ändern | separater Assist unklar | eigener AI-Vertrag nötig |
| Wartbarkeit | **hoch / KISS** | gering | mittel | gering |

### Entscheidung

**Variante A** ist eindeutig vorzuziehen, allerdings in einer reduzierten Form:

- vorhandenes `mvp_scope` = **Must / MVP-Scope**,
- neues optionales `should_scope`,
- neues optionales `could_scope`,
- neues optionales `wont_this_time`,
- `in_scope` / `out_of_scope` unverändert.

Nicht empfohlen ist Variante A in der naiven Form „zusätzlich vier neue Felder `must/should/could/wont`“, weil `must` dann `mvp_scope` dupliziert.

## 7. Empfohlenes Zielmodell

### 7.1 Ownership

Owner der konkreten MoSCoW-Priorisierung ist **Delivery & Handover**.

Kanonischer Source of Truth bleibt die jeweilige `DeliveryPackage`-Version. Use Case Steering, `DecisionAssessment`, `ApprovalDecision`, Governance und Lifecycle dürfen diese Priorisierung höchstens lesen, aber nicht parallel persistieren oder neu entscheiden.

Die bestehende `DOMAIN_CONTEXT_MAP.md` muss dafür fachlich **nicht geändert** werden. Sie beschreibt Delivery bereits als Owner von Delivery Package, Readiness, Section Reviews, Versionierung und Handover. Eine spätere Implementierung konkretisiert lediglich einen bestehenden Delivery-Inhalt.

### 7.2 Section-Zuordnung

Alle vier Priorisierungskategorien gehören in die bestehende Section:

```text
scope_and_users = "Scope, Nutzer und MVP"
```

Keine neue Section `scope_prioritization`.

### 7.3 Persistenz

Empfohlenes minimales Datenmodell für ein Folge-Issue:

```text
bestehend: mvp_scope       → UI-Semantik: Must / MVP-Scope
neu:       should_scope    → optional
neu:       could_scope     → optional
neu:       wont_this_time  → optional
```

Alle drei neuen Felder sind Delivery-eigene Textfelder. Es wird **kein** eigenes MoSCoW-Modell, keine Requirement-Entität und kein Backlog-Item-Modell eingeführt.

### 7.4 Content Origin

`scope_and_users` muss für neu erzeugte Packages künftig `ContentOrigin.MIXED` sein:

- `in_scope`, `out_of_scope`, `users_and_scenarios`: überwiegend übernommen,
- `mvp_scope`, `should_scope`, `could_scope`, `wont_this_time`: in Delivery konkretisiert.

Für bereits übergebene Packages darf die gespeicherte Review-Metadaten-Semantik nicht rückwirkend geändert werden. Für noch aktive Packages kann eine spätere Schema-Migration den Section-Origin auf `MIXED` korrigieren, ohne Inhalte künstlich zu backfillen und ohne allein deshalb Bestätigungen zurückzusetzen.

### 7.5 Review-Reset

Die bestehenden Regeln reichen aus:

- alle vier Priorisierungsfelder werden `SECTION_FIELDS["scope_and_users"]` zugeordnet,
- jede echte Inhaltsänderung setzt damit den Business-Review dieser Section zurück,
- ein `READY`-Package fällt dadurch wie heute auf `DRAFT` zurück,
- keine zusätzliche technische Bestätigung wird eingeführt.

Eine reine Migrationskorrektur von `ContentOrigin` bei noch nicht übergebenen Beständen ist keine fachliche Inhaltsänderung und sollte deshalb keinen Review-Reset auslösen.

## 8. Readiness- und Pflichtlogik

### Must

`mvp_scope` bleibt Pflichtfeld und bestehender Readiness-Blocker. Damit ist die Regel „mindestens ein Must muss existieren“ bereits fachlich abgedeckt, ohne ein Item-Zählmodell zu erfinden.

### Should

Darf leer bleiben. Ein leerer Should-Bereich ist eine zulässige Priorisierungsentscheidung und kein Delivery-Blocker.

### Could

Darf leer bleiben. Gleiches gilt wie bei Should.

### Won't this time

Darf ebenfalls leer bleiben. Eine Pflichtformulierung wie „keine bekannten Ausschlüsse“ würde nur formale Textfüllung erzeugen. `out_of_scope` bleibt davon unabhängig die strukturell bereits vorhandene fachliche Negativgrenze.

### Neue Readiness-Schema-Version?

**Nein, für die empfohlene Minimalvariante nicht.**

Die verbindliche Minimum-Scope-Regel bleibt exakt an `mvp_scope` gebunden und existiert bereits in Readiness-Schema 2. Die neuen Kategorien sind optional und werden nicht in `READY_REQUIRED_FIELDS` aufgenommen. Deshalb ändert sich die Menge der Readiness-Blocker nicht und eine `readiness_schema_version = 3` wäre unnötige Komplexität.

Eine neue Schema-Version wäre erst dann gerechtfertigt, wenn ein späteres Issue neue Pflichtbedingungen oder rückwirkend relevante Readiness-Semantik einführt.

## 9. Umgang mit bestehenden Packages

### Bereits `HANDED_OVER`

- unverändert lassen,
- keine Inhalte backfillen,
- keine Reviews oder Origins rückwirkend verändern,
- optionale neue DB-Spalten bleiben leer,
- bestehende Export-Snapshots behalten ihre damalige Semantik.

### `DRAFT` oder `READY`, noch nicht übergeben

- vorhandenes `mvp_scope` bleibt der bestehende Must-/Minimum-Scope,
- `should_scope`, `could_scope`, `wont_this_time` starten leer,
- keine automatische Ableitung aus `in_scope`, `out_of_scope`, Requirements oder Backlog,
- Section-Origin kann auf `MIXED` korrigiert werden,
- vorhandene fachliche Bestätigung wird nicht allein durch die Schemaeinführung invalidiert; sobald ein Priorisierungsfeld fachlich geändert wird, greift der bestehende Review-Reset.

Damit wird keine historische Aussage erfunden und gleichzeitig verhindert, dass eine reine Erweiterung optionaler Felder aktive Packages künstlich blockiert.

## 10. 60-%-Faustregel

### Befund

Der Radar besitzt **keine strukturierte Aufwandsschätzung je Scope-, Requirement- oder Backlog-Item**:

- Scope, Requirements und Backlog sind freie `TextField`-Inhalte.
- Es gibt keine Story Points, Aufwandseinheiten oder itembezogenen Schätzobjekte in Delivery.
- `SolutionOption.feasibility` und `SolutionOption.integration_effort` sind nur grobe Kategorien (`NOT_ASSESSED`, `LOW`, `MEDIUM`, `HIGH`) auf Ebene einer gesamten Lösungsoption. Sie lassen sich nicht seriös auf Must-/Should-/Could-Anteile verteilen.

### Entscheidung

Die 60-%-Regel wird ausschließlich als **methodische Leitplanke** dokumentiert, zum Beispiel:

> Must sollte bewusst auf den unverzichtbaren Minimum-Scope begrenzt werden. Eine quantitative 60-%-Prüfung ist im Radar nicht implementiert, solange keine belastbaren itembezogenen Aufwandsschätzungen existieren.

Keine Prozentanzeige, keine Warnlogik und keine Aufwandsschätzungs-Engine im MoSCoW-Folge-Issue.

## 11. Einordnung in `DELIVERY_METHODOLOGY.md`

MoSCoW soll in die bestehende zentrale Methodikreferenz aufgenommen werden, nicht in ein separates Dokument.

Empfohlene Kommunikationsregel:

> MoSCoW dient als etablierte Methode zur Priorisierung des Delivery-Scope. `Must` bezeichnet den unverzichtbaren Minimum-/MVP-Scope; `Should`, `Could` und `Won't this time` machen bewusste Priorisierungsentscheidungen sichtbar. Daraus entsteht kein eigener Workflow, kein Score, keine zusätzliche Freigabe und keine Governance-Entscheidung.

Die 60-%-Faustregel wird unmittelbar daneben als nicht technisch erzwungener Methodikhinweis erklärt.

Das ist konsistent mit der bereits dokumentierten Behandlung von CRISP-ML(Q) und Google ML Test Score: bekannte Methodik wird referenziert und operational nutzbar gemacht, ohne daraus zusätzliche Systemzustände zu erzeugen.

## 12. AI-Draft-Entscheidung

Der bestehende AI-Draft bleibt auf `mvp_scope` beschränkt.

Kleinste spätere Änderung:

- Labels und Prompt auf **Must-/MVP-Scope** schärfen,
- bestehende Quellen (`in_scope`, `out_of_scope`, Nutzer, Problem, Ziel, Lösungsrahmen) beibehalten,
- weiterhin nur einen Vorschlag erzeugen, nicht automatisch speichern oder bestätigen,
- **keine automatische Klassifikation nach Should/Could/Won't** in der ersten Umsetzung.

Der aktuelle Prompt verbietet dem Modell bereits eigenständige Priorisierungs-, Approval-, Governance- und Lifecycle-Entscheidungen. Dieses Sicherheitsprinzip bleibt bestehen. AI darf beim Minimum-Scope formulieren, aber nicht die fachliche MoSCoW-Entscheidung übernehmen.

## 13. Evidence Mapping / Source Manifest

Die bestehenden Mapping-Verträge bleiben führend:

- `in_scope`, `out_of_scope`, `users_and_scenarios` dürfen aus expliziten Upstream-Quellen übernommen werden.
- `mvp_scope` bleibt vom automatischen Evidence Mapping ausgeschlossen.
- `should_scope`, `could_scope` und `wont_this_time` erhalten **keine** automatische Mapping-Regel, solange keine fachlich autoritative Upstream-Quelle dafür existiert.
- Im Mapping Contract sollten die neuen Delivery-eigenen Felder explizit in die Menge der nicht automatisch befüllbaren Felder aufgenommen werden, damit der Fail-Closed-Vertrag testbar bleibt.

Es wird keine Source-Manifest-Quelle für eine Priorisierung erfunden. Die Section-Herkunft `MIXED` beschreibt genau die Kombination aus übernommenem Kontext und Delivery-eigener Konkretisierung.

## 14. Export- und UX-Zielbild

### Edit-UI

Die vorhandene Section bleibt eine Seite. Sinnvolle Reihenfolge:

1. Im Scope
2. Nicht im Scope
3. Nutzer und Szenarien
4. Must / MVP-Scope (`mvp_scope`)
5. Should
6. Could
7. Won't this time

Kurze Help-Texte müssen insbesondere die Differenz `out_of_scope` versus `Won't this time` erklären.

### Detailansicht / Export

Der Export soll Scope nicht doppelt ausgeben. Empfohlen:

```text
## Scope
### Im Scope
...
### Nicht im Scope
...

## Priorisierung für diese Delivery-Version
### Must / MVP-Scope
...
### Should
...
### Could
...
### Won't this time
...
```

Der heutige separate Exportabschnitt `MVP-Scope` wird in diesen Priorisierungsblock integriert, statt denselben Inhalt zweimal auszugeben.

## 15. Technische Impact Map für das Folge-Issue

| Bereich | Änderung erforderlich? | Kleinstmögliche Änderung | Hauptrisiko |
|---|---:|---|---|
| `ki_radar/delivery/models.py` | Ja | 3 optionale Textfelder; `SECTION_ORIGINS` liegt nicht hier, Section-Definition bleibt unverändert | Feldnamen/Semantik nicht wieder duplizieren |
| Migration | Ja | 3 nullable/blank-fähige Textfelder; aktive `scope_and_users`-Origins auf `MIXED`, handed-over unverändert | historische Reviews nicht rückwirkend verändern |
| `ki_radar/delivery/forms.py` | Ja | neue Felder in `SECTION_FIELDS["scope_and_users"]`; Help-Texte/Labels | Review-Reset muss weiterhin section-basiert greifen |
| `ki_radar/delivery/readiness.py` | Nein an Pflichtmenge | `mvp_scope` bleibt Pflicht; neue Felder **nicht** in `READY_REQUIRED_FIELDS` | versehentlich neue Pflicht-/Gate-Logik bauen |
| `ki_radar/delivery/services.py` | Ja | `SECTION_ORIGINS["scope_and_users"] = MIXED`; neue Felder beim Seed leer | künstliches Backfill / erfundene Prioritäten |
| `ki_radar/delivery/ai_draft.py` | Ja, klein | Prompt/UI-Semantik auf Must-/MVP-Scope schärfen; keine neuen Zielkategorien | AI trifft unzulässige Priorisierungsentscheidung |
| `static/js/delivery-mvp-scope-ai.js` | ggf. nur Text/Selektoren prüfen | bestehendes Ziel `mvp_scope` beibehalten | unnötiger Multi-Feld-AI-Flow |
| Evidence-/Mapping-Contract | Ja, klein | neue Felder explizit automatischer Befüllung entziehen | Priorität aus nicht autoritativer Quelle ableiten |
| Mapping Refresh / Source Manifest | grundsätzlich nein | neue Felder nicht in V1-Mappings aufnehmen | stille Überschreibung lokaler Delivery-Entscheidung |
| `templates/delivery/package_form.html` | meist automatisch | Section-Felder werden über Form-Gruppen gerendert; Help-Texte prüfen | zu lange unstrukturierte Section |
| `templates/delivery/package_detail.html` | Ja | Priorisierungsblock darstellen | doppelte Scope-/MVP-Darstellung |
| `ki_radar/delivery/exports.py` | Ja | einen konsolidierten Priorisierungsblock exportieren | alter MVP-Abschnitt bleibt doppelt |
| `docs/DELIVERY_METHODOLOGY.md` | Ja | kurzer MoSCoW-Abschnitt inkl. 60-%-Hinweis | Methode fälschlich als Gate/Score darstellen |
| `docs/planning/DOMAIN_CONTEXT_MAP.md` | Nein | bestehende Ownership reicht aus | unnötige neue Context-Grenze |
| Tests | Ja | Model/Form/Review/Readiness/Export/AI/Mapping/Legacy-Handover abdecken | nur Happy Path testen |

## 16. Kleinste belastbare Implementierungsvariante

Das Folge-Issue sollte **nur** Folgendes umsetzen:

1. `mvp_scope` bleibt kanonischer Must-/Minimum-Scope; UI-Label und Methodik werden auf „Must / MVP-Scope“ geschärft.
2. Drei optionale Textfelder `should_scope`, `could_scope`, `wont_this_time` auf `DeliveryPackage` ergänzen.
3. Alle drei Felder `scope_and_users` zuordnen, damit der bestehende Review-Reset greift.
4. `scope_and_users` für neue Packages als `MIXED` kennzeichnen; nicht übergebene Bestände ohne Inhaltsänderung auf `MIXED` korrigieren, übergebene Snapshots unangetastet lassen.
5. Readiness unverändert lassen: nur `mvp_scope` ist aus MoSCoW-Sicht Pflicht.
6. Mapping fail-closed halten; keine Prioritätsfelder automatisch aus Upstream-Daten füllen.
7. MVP-AI nur begrifflich auf Must-/Minimum-Scope schärfen; keine AI-Kategorisierung der drei optionalen Felder.
8. Detailansicht und Markdown-Export um einen konsolidierten Priorisierungsblock erweitern.
9. `DELIVERY_METHODOLOGY.md` um MoSCoW und die nicht technisch erzwungene 60-%-Leitplanke ergänzen.

Nicht Bestandteil dieses Folge-Issues:

- neue Requirement-/Backlog-Entitäten,
- Story Points / Aufwandsschätzungen,
- 60-%-Berechnung,
- neue Section,
- neuer Workflow oder Gate,
- neues Readiness-Schema,
- neue Governance-/Approval-Logik,
- automatische AI-Priorisierung.

## 17. Technisch testbare Acceptance Criteria für das Folge-Issue

1. Ein neu erzeugtes Delivery Package besitzt weiterhin genau die bestehenden sieben Delivery-Sektionen; keine `scope_prioritization`-Section entsteht.
2. `mvp_scope` bleibt Persistenzfeld und Readiness-Pflicht. Ein leeres `mvp_scope` blockiert `READY` weiterhin.
3. `should_scope`, `could_scope` und `wont_this_time` sind optionale persistierte Delivery-Felder und gehören in `SECTION_FIELDS["scope_and_users"]`.
4. Leere Should-/Could-/Won't-Felder erzeugen **keinen** Readiness-Blocker.
5. Eine Änderung an `mvp_scope`, `should_scope`, `could_scope` oder `wont_this_time` setzt eine zuvor bestätigte `scope_and_users`-Section auf `NEEDS_REVIEW`, löscht die fachliche Bestätigung und setzt ein `READY`-Package auf `DRAFT`.
6. `scope_and_users` benötigt weiterhin nur die bestehende Business-Bestätigung; es entsteht keine neue Technical-Confirmation-Pflicht.
7. Neue Packages erhalten für `scope_and_users` `ContentOrigin.MIXED`.
8. Bereits `HANDED_OVER` markierte Packages bleiben unveränderlich; Migration/Backfill verändert weder deren Inhalte noch Section-Review-Metadaten.
9. Nicht übergebene Bestände behalten ihren bisherigen `mvp_scope`; die drei neuen Felder werden nicht aus `in_scope`, `out_of_scope`, Requirements oder Backlog erfunden.
10. Für die neuen Prioritätsfelder existiert keine automatische V1-Evidence-Mapping-Regel; ein Versuch, sie als automatisch gemappte Felder zu behandeln, bleibt fail-closed.
11. Der bestehende MVP-AI-Assist schreibt weiterhin ausschließlich nach `mvp_scope` und speichert/confirmt nichts automatisch.
12. AI-Prompt und UI bezeichnen das Ziel als Must-/MVP-Scope bzw. Minimum-Scope und treffen keine automatische Should-/Could-/Won't-Zuordnung.
13. Markdown-Export und Detailansicht unterscheiden eindeutig `out_of_scope` von `Won't this time` und zeigen `mvp_scope` nicht doppelt.
14. Keine 60-%-Berechnung, kein Story-Point-Modell und kein neues Effort-Modell werden eingeführt.
15. `docs/DELIVERY_METHODOLOGY.md` dokumentiert MoSCoW als Referenzmethode ohne zusätzlichen Workflow, Score oder Governance-Entscheidung.
16. Bestehende Tests für Delivery Readiness, Evidence Mapping, Handover und MVP-AI bleiben grün; neue Regressionstests decken die Punkte 1–15 ab.

## 18. Verworfene Alternativen

### Vier neue Felder `must/should/could/wont` zusätzlich zu `mvp_scope`

**Verworfen.** `must` und `mvp_scope` würden denselben Minimum-Scope parallel halten. Nutzer müssten Inkonsistenzen manuell auflösen; Readiness, Export und AI müssten entscheiden, welches Feld führend ist.

### `in_scope` = Must und `out_of_scope` = Won't umdeuten

**Verworfen.** Dadurch gingen die heute klaren Scope-Grenzen verloren. Außerdem würden bestehende Value-Stream-Mappings semantisch falsch und Bestandsdaten müssten neu interpretiert werden.

### MoSCoW als neue Delivery-Section

**Verworfen.** Die bestehende Section heißt bereits „Scope, Nutzer und MVP“. Eine zweite Scope-Section würde zusätzliche Navigation, Review-Zustände, Rechte, Readiness-Zuordnung und Exportlogik erzeugen, ohne einen eigenen fachlichen Verantwortungsbereich zu schaffen.

### Eigenes MoSCoW-Domainobjekt

**Verworfen.** Es gibt keinen eigenen Lifecycle, keine unabhängige Versionierung und keine Invarianten, die nicht bereits durch `DeliveryPackage` und Section Reviews abgedeckt sind. Das Package ist die natürliche Aggregate-/Versionierungsgrenze.

### MoSCoW nur als Überschriften in einem einzigen Freitextfeld

**Nicht empfohlen.** Das wäre zwar migrationsarm, aber maschinell kaum testbar, im Export schwer sauber zu strukturieren und würde Should/Could/Won't nur als Konvention in einen Textblock verlagern. Drei optionale Felder sind der kleinste strukturierte Zusatz mit klarer Semantik.

### MoSCoW auf Requirements oder Backlog-Items modellieren

**Für jetzt verworfen.** Requirements und Backlog sind freie Textfelder ohne Item-Identität. Eine saubere itembezogene Priorisierung würde zuerst ein eigenes strukturiertes Requirement-/Backlog-Modell erfordern und wäre ein deutlich größeres Vorhaben.

### 60-%-Warnung im ersten MoSCoW-Issue

**Verworfen.** Ohne belastbare itembezogene Aufwände wäre die Prozentzahl Scheingenauigkeit. Der Hinweis gehört in die Methodik, nicht in Readiness oder UI-Berechnung.

## 19. Schlussentscheidung

Die Analyse bestätigt die Zielhypothese mit einer wichtigen Einschränkung: MoSCoW passt fachlich in Delivery, aber eine naive Vier-Felder-Erweiterung wäre bereits zu viel.

Die nachhaltige Minimalarchitektur lautet:

```text
Upstream Scope-Grenzen
  in_scope / out_of_scope / users_and_scenarios
          ↓ als Snapshot / Evidence
DeliveryPackage.scope_and_users  [ContentOrigin.MIXED]
  Must  = bestehendes mvp_scope   [Pflicht]
  Should = should_scope           [optional]
  Could  = could_scope            [optional]
  Won't this time = wont_this_time [optional]
          ↓
bestehender Business-Review → READY → Handover
```

Damit bleibt genau eine fachliche Source of Truth je Aussage erhalten:

- Boundary: `in_scope` / `out_of_scope`,
- Minimum-Scope: `mvp_scope`,
- Priorisierungsabstufung: drei neue optionale Delivery-Felder,
- Requirements: `functional_requirements`,
- Umsetzungszerlegung: `initial_backlog`,
- Version/Handover: `DeliveryPackage`.

## 20. Empfohlenes Folge-Issue

**Titelvorschlag:**

`[Delivery][Scope] MoSCoW-Priorisierung minimal in scope_and_users integrieren`

**Scope:** exakt die in Abschnitt 16 beschriebene Minimalvariante inklusive Migration, UI/Export, Methodik, Mapping-Fail-Closed-Vertrag und Regressionstests – ausdrücklich ohne 60-%-Berechnung, Requirement-/Backlog-Refactoring, neue Section oder neue Governance-/Lifecycle-Logik.
