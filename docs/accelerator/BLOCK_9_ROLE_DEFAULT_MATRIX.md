# Accelerator Block 9 – AP 2 Rollenquellen- und Prioritätsmatrix

**Issue:** #125  
**Workplan:** `docs/accelerator/BLOCK_9_WORKPLAN.md`  
**Gap-Analyse:** `docs/accelerator/BLOCK_9_GAP_ANALYSIS.md`  
**Basis:** `main` auf `65906c4c0c0c43f584826d618bef0c3f00b9d519`

## 1. Zweck

Diese Matrix legt vor Implementierung des Resolvers verbindlich fest, welche vorhandenen Rollenbeziehungen Block 9 als Vorbelegung, als bloßen Vorschlag oder ausdrücklich nicht als Personen-Default verwenden darf.

Sie ist keine neue Rollen- oder Permission-Architektur. Die vorhandenen Domänenfelder und Eligibility-/Permission-Services bleiben autoritativ.

## 2. Begriffe

### Vorbelegung

Eine Person darf im Ziel-Feld initial ausgewählt werden, wenn Quelle und Ziel dieselbe fachliche Rollenbeziehung abbilden und die Person aktuell zulässig ist. Die Vorbelegung ist trotzdem keine Rollenhandlung und wird erst durch den regulären Speichervorgang wirksam.

### Vorschlag

Eine fachlich benachbarte, aber nicht identische Rollenbeziehung darf sichtbar als mögliche Person genannt werden, wenn die Herkunft eindeutig ist. Der Nutzer muss die Person ausdrücklich auswählen beziehungsweise übernehmen. Ein Vorschlag darf nie als gespeicherter Zielwert behandelt werden.

### Offen

Es existiert keine ausreichend eindeutige fachliche Personenquelle. Das System zeigt keine erfundene Person an.

### Aktuell zulässig

Eine Person ist nur dann nutzbar, wenn die bestehenden Ziel-Permissions beziehungsweise Ziel-Eligibility sie im Zeitpunkt des Requests zulassen. Insbesondere müssen Deaktivierung und Anonymisierung berücksichtigt werden. Wo eine unabhängige Prüfung verlangt wird, gelten zusätzlich die bestehenden Trennungsregeln.

## 3. Globale Priorität

Für alle Zielrollen gilt:

1. **Bestehender Zielwert:** Ein bereits gespeicherter Rollenwert bleibt erhalten und wird nie durch einen Default still überschrieben.
2. **Same-Role-Quelle:** Eine explizite, fachlich identische Rollenquelle darf vorbelegen, sofern aktuell zulässig.
3. **Cross-Role-Quelle:** Eine fachlich benachbarte, aber nicht identische Rolle darf höchstens einen sichtbaren Vorschlag liefern, wenn die Beziehung im konkreten Kontext nachvollziehbar ist.
4. **Eligibility-Menge:** Eine Gruppe oder Queryset zulässiger Personen erzeugt allein keinen Personen-Default.
5. **Kein eindeutiger Kandidat:** Ziel bleibt offen.

Bei mehreren gleichrangigen, voneinander abweichenden Quellen entsteht kein First-Match-Verhalten. Der Resolver liefert `conflict` beziehungsweise keinen Default.

## 4. Verbindliche Matrix

| Zielkontext | Zielrolle | Erlaubte Quelle | Beziehung | UI-Klassifikation | Server-Regel | Konflikt-/Fehlverhalten |
|---|---|---|---|---|---|---|
| bestehender Value Stream | Value-Stream-Owner | bereits gespeicherter `ValueStream.owner` | identisch | bestehender Wert | bestehende Owner-Eligibility | unzulässiger Altwert bleibt sichtbar mit bestehender Warnung; vor neuem Speichern aktive zulässige Person erforderlich |
| neuer Value Stream | Value-Stream-Owner | keine allgemeine Personenquelle vorhanden | – | offen | `eligible_value_stream_owners()` begrenzt Auswahl | keine automatische Auswahl aus Gruppe oder aktuellem Nutzer |
| bestehender Use Case | Business Owner | bereits gespeicherter `UseCase.business_owner` | identisch | bestehender Wert | bestehende Use-Case-Permissions | nie durch anderen Default überschreiben |
| neuer Use Case mit explizitem Architekturkontext | Business Owner | `UseCaseOrigin`-fähiger Stage-Kontext → `ValueStream.owner` | **nicht identisch** | Vorschlag | aktuelle Ziel-Eligibility zusätzlich prüfen | fehlt Owner oder ist er unzulässig: kein Vorschlag; mehrere widersprüchliche fachliche Quellen: offen/conflict |
| neuer Use Case ohne expliziten Architekturkontext | Business Owner | keine belastbare Rollenquelle | – | offen | aktuelle Business-Owner-Eligibility begrenzt Auswahl | `request.user` beziehungsweise Gruppenmitgliedschaft allein ist kein fachlicher Default |
| bestehender Use Case | KI-Koordinator | bereits gespeicherter `UseCase.coordinator` | identisch | bestehender Wert | aktive/nicht anonymisierte Person und bestehende Coordinator-Eligibility | unzulässige/fehlende Zuordnung nicht durch irgendeinen Gruppenmember ersetzen |
| neuer Use Case | KI-Koordinator | keine konkrete fachliche Zuordnung vorhanden | – | offen | Coordinator-Eligibility begrenzt Auswahl | keine automatische Auswahl aus Coordinator-Gruppe |
| bestehender Use Case | Technical Owner | bereits gespeicherter `UseCase.technical_owner` | identisch | bestehender Wert | aktive/nicht anonymisierte Person; vorhandene Zielberechtigungen | unzulässige/fehlende Zuordnung offen lassen |
| neuer Use Case | Technical Owner | keine allgemeine eindeutige Quelle vorhanden | – | offen | Ziel-Eligibility begrenzt Auswahl | weder Value-Stream-Owner noch Coordinator automatisch umdeuten |
| neues Delivery Package | Technical Owner | `UseCase.technical_owner` | identisch | Vorbelegung / bestehendes Copy-Verhalten | vorhandene Delivery-Permissions und bestehende Role-Source-Provenance | fehlende Source bleibt leer; Source-Änderungen über bestehenden Delivery-Konfliktpfad behandeln |
| bestehendes Delivery Package | Technical Owner | gespeicherter Package-Wert + vorhandenes `role_sources.technical_owner` | identisch mit eigener Source-Provenance | bestehender Wert; Source-Abweichung sichtbar | `can_resolve_role_source()` | keine stille Überschreibung; vorhandene `DeliveryRoleSourceDecision` verwenden |
| neue Freigabe mit Auflagen | Auflagenverantwortlicher | keine allgemeine eindeutige Personenquelle | – | offen | aktive/nicht anonymisierte Personen im bestehenden Approval-Pfad | Business Owner, Technical Owner, Coordinator oder Value-Stream-Owner nicht automatisch einsetzen |
| bestehender konkreter Approval-Kontext | Auflagenverantwortlicher | bereits gespeicherter `ApprovalDecision.condition_owner` | identisch | bestehender Wert | reguläre Approval-Validierung | bei geänderter/ungültiger Person keine Ersatzperson erfinden |
| neue unabhängige Zweitprüfung | Zweitprüfer | `eligible_second_approvers()` | Eligibility-Menge, keine Zuordnung | offen; zulässige Auswahl | vorhandener unabhängiger Approver-Service | bei 0 Kandidaten offen/blockiert; bei 1 Kandidat **trotzdem keine automatische Bestätigung**, Person darf nur als eindeutig zulässiger Vorschlag erscheinen; bei >1 keine Person bevorzugen |
| bereits zugewiesene Zweitprüfung | Zweitprüfer | `ApprovalDecision.second_approval_assignee` | identisch | bestehender Wert | Eligibility bei Aktion erneut prüfen | Zuweisung ist keine Bestätigung; geänderte Eligibility muss fail-closed wirken |
| Delivery Section | nächste erforderliche Prüfrolle Business | `SECTION_REVIEW_REQUIREMENTS` / fehlende Business Confirmation | Rollenanforderung | Rolle anzeigen | `reviewer_roles()` / `can_confirm_business()` | keine Person allein aus Gruppenmenge erfinden |
| Delivery Section mit eindeutig zugewiesenem Business Owner | vorgeschlagene fachliche Prüferperson | `UseCase.business_owner` | identische accountable Business-Rolle | Vorschlag | `can_confirm_business()` im aktuellen Request | wenn nicht mehr zulässig: kein Vorschlag; Stellvertretungsberechtigung erzeugt keine bevorzugte Person |
| Delivery Section | nächste erforderliche Prüfrolle Technical | `SECTION_REVIEW_REQUIREMENTS` / fehlende Technical Confirmation | Rollenanforderung | Rolle anzeigen | `reviewer_roles()` / `can_confirm_technical()` | keine Person allein aus Gruppenmenge erfinden |
| Delivery Section mit eindeutig zugewiesenem Technical Owner | vorgeschlagene technische Prüferperson | `DeliveryPackage.technical_owner` | identische accountable Technical-Rolle | Vorschlag | `can_confirm_technical()` im aktuellen Request | wenn nicht mehr zulässig: kein Vorschlag; Coordinator-Berechtigung erzeugt keine bevorzugte Person |
| Governance Review | nächste Prüfrolle | Review-Typ / `responsible_role` | Rollen-/Textinformation, keine eindeutige Person | Rolle beziehungsweise bestehende Rollenbeschreibung anzeigen | vorhandene Governance-Validierung | keine Person aus Business/Technical/Coordinator ableiten |

## 5. Bewusste Abgrenzung des bestehenden `request.user`-Defaults

Der aktuelle Use-Case-Intake erzeugt den neuen Use Case mit dem eingeloggten Nutzer als `business_owner`. Diese bestehende Implementierung wird für Block 9 **nicht** als fachlicher Same-Role-Default klassifiziert.

Begründung:

- `can_create_use_case()` prüft generische Business-Owner-Eligibility, nicht die accountable Zuordnung für den konkreten Fall.
- KI-Koordinatoren beziehungsweise technische Administratoren können diese Eligibility ebenfalls erfüllen.
- Die Architektur trennt Value-Stream-Owner ausdrücklich von Business Owner und Technical Owner.

Daraus folgt für die spätere UI-Integration: Der aktuelle technische Automatismus muss so angepasst werden, dass eine belegte Rollenquelle beziehungsweise eine explizite Nutzerentscheidung maßgeblich ist. Die konkrete Formularänderung erfolgt erst in AP 4/AP 5, nicht in diesem Dokumentations-AP.

## 6. Value-Stream-Owner als Cross-Role-Vorschlag

Der Value-Stream-Owner ist die einzige bewusst zugelassene Cross-Role-Quelle in Version 1, und auch nur für einen **Vorschlag** zum Business Owner eines neuen Use Cases mit explizitem Architekturkontext.

Voraussetzungen:

- der neue Use Case stammt nachweisbar aus einem konkreten Stage-/Value-Stream-Kontext,
- der Value Stream besitzt genau einen gespeicherten Owner,
- dieser Owner ist im aktuellen Request als Zielperson für den Business-Owner-Pfad zulässig,
- es existiert noch kein expliziter Business Owner im Zielkontext,
- keine gleichrangige abweichende Quelle existiert.

Der UI-Text muss die unterschiedliche Rolle offenlegen, sinngemäß: „Vorschlag aus Value Stream · dortiger Owner“. Er darf nicht als „übernommener Business Owner“ erscheinen.

## 7. Delivery Technical Owner bleibt vorhandener Spezialpfad

Block 9 baut für `UseCase.technical_owner -> DeliveryPackage.technical_owner` keinen generischen Resolver-Write-Pfad.

Der bestehende Delivery-Service:

- kopiert den Technical Owner bei Package-Erzeugung,
- speichert ihn als Rollenquelle im Source Manifest,
- erkennt Source-Änderungen,
- besitzt eine explizite Auflösungsentscheidung,
- setzt bei Übernahme die betroffenen Delivery-Reviews kontrolliert zurück.

AP 3 darf diesen Zustand für Anzeige/Entscheidung auswerten, aber nicht duplizieren.

## 8. Zweitprüfung: Eligibility ist nicht Assignment

`eligible_second_approvers()` bleibt die einzige Quelle für die Menge aktuell zulässiger unabhängiger Zweitprüfer.

Regeln:

- 0 zulässige Personen: kein Vorschlag.
- 1 zulässige Person: eindeutiger **Vorschlag** ist zulässig, aber keine automatische Zuweisung, keine Anfrage und keine Bestätigung.
- mehr als 1 zulässige Person: keine Person wird bevorzugt.
- bereits gespeicherte `second_approval_assignee` bleibt bestehender Zielwert; die tatsächliche Zweitprüfung validiert die Zulässigkeit erneut.

Damit wird Bedienreibung reduziert, ohne das Vier-Augen-Prinzip zu schwächen.

## 9. Nächste erforderliche Prüfrolle

Block 9 unterscheidet ausdrücklich zwischen **Rolle** und **Person**.

Die nächste erforderliche Rolle darf deterministisch aus vorhandenem Workflowzustand abgeleitet werden, zum Beispiel:

- Business Confirmation fehlt,
- Technical Confirmation fehlt,
- beide fehlen,
- Governance-Prüftyp ist offen.

Eine konkrete Person darf nur genannt werden, wenn ein expliziter accountable Owner derselben Rolle existiert und diese Person aktuell die betreffende Aktion ausführen darf. Berechtigte Stellvertreter oder Gruppenmitglieder werden nicht gerankt.

## 10. Resolver-Ausgabeklassen für AP 3

AP 3 soll keine allgemeine Rule Engine bauen. Für die kleine statische Matrix reichen folgende semantische Ergebnisse:

- `existing`: Ziel besitzt bereits einen Wert; nichts vorbelegen.
- `prefill`: identische eindeutige Rollenquelle, aktuell zulässig.
- `suggestion`: zulässige, nachvollziehbare Cross-Role- beziehungsweise eindeutige Eligibility-Empfehlung, Nutzeraktion erforderlich.
- `role_only`: nächste erforderliche Rolle ist bekannt, aber keine eindeutige Person.
- `open`: keine belastbare Quelle.
- `conflict`: mehrere relevante Quellen widersprechen sich.
- `ineligible`: Quelle existiert, ist aktuell aber nicht zulässig.

Jedes Ergebnis mit Person enthält mindestens:

- Zielrollenschlüssel,
- User-ID,
- anzeigbaren Namen,
- Quelltyp,
- Quellobjekt-ID soweit vorhanden,
- kurze Herkunftsbezeichnung,
- Klassifikation.

Keine dieser Ausgaben wird als fachlicher Rollenwert persistiert.

## 11. Sicherheitsinvarianten

Unabhängig von der Klassifikation gilt:

- kein Resolver-Ergebnis löst Save, Approval, Confirmation, Review, Handover oder Lifecycle Transition aus,
- kein Resolver-Ergebnis erzeugt eine Notification,
- kein Resolver-Ergebnis ersetzt serverseitige Permission-/Eligibility-Prüfung,
- keine Rolle wird aus LLM-Ausgaben bestimmt,
- keine Person wird aus Textfeldern oder Rollenbezeichnungen heuristisch gesucht,
- keine globale Rangfolge von Nutzern wird eingeführt,
- bestehende Zielwerte haben Vorrang vor Defaults.

## 12. AP-2-Abnahme

AP 2 ist erfüllt, wenn diese Matrix als verbindliche Eingabe für AP 3 gilt. Produktcode wird in AP 2 nicht geändert.

Die wichtigste Designentscheidung lautet: **Version 1 automatisiert nur echte Same-Role-Beziehungen. Cross-Role-Beziehungen bleiben sichtbar deklarierte Vorschläge; Eligibility-Mengen bleiben grundsätzlich personenneutral.**
