# Issue #155 – Phase B: Screenshot-Index

[Prüfbericht](ISSUE_155_PHASE_B_UX_ABNAHME.md) · [72 Bildanhänge](https://github.com/Satte882/KI-Ideenwerkstatt/pull/157#issuecomment-6347652458) · [Manifest mit URL, Hash, Rolle und Breite](ISSUE_155_PHASE_B_SCREENSHOT_MANIFEST.json)

26 gezielte Nachweise und 46 Rollen-/Breitenansichten. Die Originaldateien bleiben unverändert außerhalb des Git-Repositories. Der geprüfte Produktstand ist `0e0823fe5367cfcf8d986d1029ce3f9be966f04a`; nachfolgende Änderungen betreffen Tests und Dokumentation.

## Vorher / Nachher nach Befund

| Befund | Phase A: Vorher | Phase B: Nachher |
| --- | --- | --- |
| F1 | [29-load-before.png](https://github.com/user-attachments/assets/bc6ad986-5a3f-45ae-9bf2-ca4042b6768c), [30-load-after.png](https://github.com/user-attachments/assets/064637a8-cac6-4818-9693-c41e8dcca440) | [F1-replace-choice-1440.png](https://github.com/user-attachments/assets/d8d1c6cd-dbd3-4369-80d2-300da43f220b), [F1-cancel-preserves-input-1440.png](https://github.com/user-attachments/assets/6a9473e0-4e8f-4b49-bdcd-f8096ef45837) |
| F2 | [35-draft-path-before.png](https://github.com/user-attachments/assets/c6642c14-db2f-4817-bef5-4fa989b37f27), [36-draft-path-after.png](https://github.com/user-attachments/assets/ce2ab6e7-381f-4fae-b048-031f43e63b62), [37-draft-recovered.png](https://github.com/user-attachments/assets/41a5d135-5343-4dc8-b401-2ab3e8c15173) | [F2-before-draft-save-1440.png](https://github.com/user-attachments/assets/5ca349f2-22a6-4693-b791-5fee35739b8d), [F2-after-draft-save-1440.png](https://github.com/user-attachments/assets/9d25638c-f99f-458a-b25c-16819c6c89e6), [F2-after-login-resume-1024.png](https://github.com/user-attachments/assets/643c1ac2-6f59-4011-bd17-96a0bfb13b11), [F2-invalid-confirm-preserves-input-1024.png](https://github.com/user-attachments/assets/e0c464e5-8f2a-435b-bea9-adb5a3b6aa0f) |
| F3 | [03-compare-before.png](https://github.com/user-attachments/assets/cdba3d9b-39b3-418e-8b46-043f87e54534), [04-compare-error.png](https://github.com/user-attachments/assets/f41fea45-3feb-4b2a-9182-34e3e5098bd7) | [F3-blocker-before-selection-1440.png](https://github.com/user-attachments/assets/fdffdc0c-9117-4655-bfd2-7bd907c60cda), [F3-ready-after-confirmation-1440.png](https://github.com/user-attachments/assets/10768b7a-7658-4f45-b111-e8a3216ee4e0) |
| F4 | [08-initiative.png](https://github.com/user-attachments/assets/c3f71cd3-dd55-4a36-9d45-7dd0dcab8bed), [09-capability-error.png](https://github.com/user-attachments/assets/10a636f8-01d4-4348-b7fc-8883a5325bc5), [11-impact-error.png](https://github.com/user-attachments/assets/838680bd-5f9f-4d28-9221-1d919b2aa478) | [F4-initiative-navigation-1440.png](https://github.com/user-attachments/assets/70434e03-5a87-4e86-b256-88c1cc93c79a), [F4-capability-draft-1440.png](https://github.com/user-attachments/assets/2ab55df4-b4e6-4840-bb7e-3c3d1b050e40), [F4-impact-navigation-1440.png](https://github.com/user-attachments/assets/3de27c91-8f8a-45e1-a3f0-5ca54be3e316), [F4-direct-outcome-context-1440.png](https://github.com/user-attachments/assets/1bc8d2a9-e5fb-4beb-a59b-e9c1a2bef6da) |
| F5 | [07-ki-selection.png](https://github.com/user-attachments/assets/e7d6cc0f-36e3-4505-ada3-0ea8133f9530), [22-bottom-e2e-ki.png](https://github.com/user-attachments/assets/6831fb8c-45b9-4790-9869-a51efcd97b0e) | [F5-selection-no-generation-1440.png](https://github.com/user-attachments/assets/e93cffeb-2fee-438a-a0be-a68ca8d71faf), [F5-explicit-cost-notice-1440.png](https://github.com/user-attachments/assets/21058c15-fa78-426c-b5d1-32aac96f9a3c), [F5-explicit-mock-feedback-1440.png](https://github.com/user-attachments/assets/360f50fa-7d04-4458-b9a8-2dd20d5c9b35) |
| F6 | [38-sidebar-1024-viewport.png](https://github.com/user-attachments/assets/54ee3b91-a105-4f39-b019-cbcdade115cb), [layout-1024-topCompare.png](https://github.com/user-attachments/assets/cb1a0712-8875-4d0b-9d99-3df4a36cd08c) | [F6-dense-navigation-1024-viewport.png](https://github.com/user-attachments/assets/683e0f1d-bbf2-4b2d-8a53-e7256b771d4e), [F4-F6-outcome-navigation-1024.png](https://github.com/user-attachments/assets/a32b52c1-0438-456c-813d-441699b2cd56), [F4-F6-back-forward-1024.png](https://github.com/user-attachments/assets/3a7d41fb-67c2-44d1-af01-c6f5b5d54f0c) |

F5: Bilder belegen den Bedienkontext; die Aufrufzahl stammt aus Regressionstest und Mock-Protokoll. Fullpage-Aufnahmen können die feste Sidebar am damaligen Scrollstand abbilden. Die drei mit `viewport` bzw. `F4-F6` bezeichneten 1024-Aufnahmen zeigen den echten sichtbaren Ausschnitt.

## Alle 72 Nachweise

| Bild | Journey / Bereich | Rolle | Viewport | Befund |
| --- | --- | --- | --- | --- |
| [F1-cancel-preserves-input-1440.png](https://github.com/user-attachments/assets/6a9473e0-4e8f-4b49-bdcd-f8096ef45837) | Gezielte Regression | owner | 1440 × 1000 | F1 |
| [F1-replace-choice-1440.png](https://github.com/user-attachments/assets/d8d1c6cd-dbd3-4369-80d2-300da43f220b) | Gezielte Regression | owner | 1440 × 1000 | F1 |
| [F2-after-draft-save-1440.png](https://github.com/user-attachments/assets/9d25638c-f99f-458a-b25c-16819c6c89e6) | Gezielte Regression | owner | 1440 × 1000 | F2 |
| [F2-after-login-resume-1024.png](https://github.com/user-attachments/assets/643c1ac2-6f59-4011-bd17-96a0bfb13b11) | Gezielte Regression | owner | 1024 × 1000 | F2 |
| [F2-before-draft-save-1440.png](https://github.com/user-attachments/assets/5ca349f2-22a6-4693-b791-5fee35739b8d) | Gezielte Regression | owner | 1440 × 1000 | F2 |
| [F2-invalid-confirm-preserves-input-1024.png](https://github.com/user-attachments/assets/e0c464e5-8f2a-435b-bea9-adb5a3b6aa0f) | Gezielte Regression | owner | 1024 × 1000 | F2 |
| [F3-blocker-before-selection-1440.png](https://github.com/user-attachments/assets/fdffdc0c-9117-4655-bfd2-7bd907c60cda) | Gezielte Regression | owner | 1440 × 1000 | F3 |
| [F3-ready-after-confirmation-1440.png](https://github.com/user-attachments/assets/10768b7a-7658-4f45-b111-e8a3216ee4e0) | Gezielte Regression | owner | 1440 × 1000 | F3 |
| [F4-capability-draft-1440.png](https://github.com/user-attachments/assets/2ab55df4-b4e6-4840-bb7e-3c3d1b050e40) | Gezielte Regression | owner | 1440 × 1000 | F4 |
| [F4-direct-outcome-context-1440.png](https://github.com/user-attachments/assets/1bc8d2a9-e5fb-4beb-a59b-e9c1a2bef6da) | Gezielte Regression | coordinator | 1440 × 1000 | F4 |
| [F4-F6-back-forward-1024.png](https://github.com/user-attachments/assets/3a7d41fb-67c2-44d1-af01-c6f5b5d54f0c) | Gezielte Regression | owner | 1024 × 1000 | F4, F6 |
| [F4-F6-outcome-navigation-1024.png](https://github.com/user-attachments/assets/a32b52c1-0438-456c-813d-441699b2cd56) | Gezielte Regression | owner | 1024 × 1000 | F4, F6 |
| [F4-impact-navigation-1440.png](https://github.com/user-attachments/assets/3de27c91-8f8a-45e1-a3f0-5ca54be3e316) | Gezielte Regression | owner | 1440 × 1000 | F4 |
| [F4-initiative-navigation-1440.png](https://github.com/user-attachments/assets/70434e03-5a87-4e86-b256-88c1cc93c79a) | Gezielte Regression | owner | 1440 × 1000 | F4 |
| [F5-explicit-cost-notice-1440.png](https://github.com/user-attachments/assets/21058c15-fa78-426c-b5d1-32aac96f9a3c) | Gezielte Regression | owner | 1440 × 1000 | F5 |
| [F5-explicit-mock-feedback-1440.png](https://github.com/user-attachments/assets/360f50fa-7d04-4458-b9a8-2dd20d5c9b35) | Gezielte Regression | owner | 1440 × 1000 | F5 |
| [F5-selection-no-generation-1440.png](https://github.com/user-attachments/assets/e93cffeb-2fee-438a-a0be-a68ca8d71faf) | Gezielte Regression | owner | 1440 × 1000 | F5 |
| [F6-dense-navigation-1024-viewport.png](https://github.com/user-attachments/assets/683e0f1d-bbf2-4b2d-8a53-e7256b771d4e) | Gezielte Regression | owner | 1024 × 1000 | F6 |
| [journey-bottom-idea-1440.png](https://github.com/user-attachments/assets/aa3be4c8-b17e-4179-a416-b3effb2401be) | bottom | owner | 1440 × 1000 | Journey/Governance |
| [journey-bottom-outcome-1440.png](https://github.com/user-attachments/assets/e035e6b2-3bd4-4c19-a55d-f1c5dbd571da) | bottom | owner | 1440 × 1000 | Journey/Governance |
| [journey-direct-after-outcome-1440.png](https://github.com/user-attachments/assets/afe829f0-6e61-4cd6-8487-e316429a1cfe) | direct | coordinator | 1440 × 1000 | Journey/Governance |
| [journey-direct-before-outcome-1440.png](https://github.com/user-attachments/assets/df2fffd8-e05c-43cc-a94e-6d441cf1a1c6) | direct | coordinator | 1440 × 1000 | Journey/Governance |
| [journey-nonki-impact-1440.png](https://github.com/user-attachments/assets/2c040344-e5ae-41a7-9a3b-6313625533ca) | nonki | owner | 1440 × 1000 | Journey/Governance |
| [journey-top-idea-1440.png](https://github.com/user-attachments/assets/01be168b-63c5-4722-ae22-228882de5512) | top | owner | 1440 × 1000 | Journey/Governance |
| [journey-top-nonki-end-1440.png](https://github.com/user-attachments/assets/3aa74d36-6653-4ac2-8f1b-c422d63f933b) | top | owner | 1440 × 1000 | Journey/Governance |
| [journey-top-strategic-outcome-1440.png](https://github.com/user-attachments/assets/9d1dc122-86af-4d14-aa79-872bbb4e77fa) | top | owner | 1440 × 1000 | Journey/Governance |
| [role-coordinator-bottomCompare-1024.png](https://github.com/user-attachments/assets/a0b57205-eb5d-4741-a62f-0e4e528c5935) | bottomCompare | coordinator | 1024 × 1000 | F6 |
| [role-coordinator-bottomCompare-1440.png](https://github.com/user-attachments/assets/582a2f84-7d64-4532-8a65-88294c398c80) | bottomCompare | coordinator | 1440 × 1000 | F6 |
| [role-coordinator-bottomProcess-1024.png](https://github.com/user-attachments/assets/3cab5741-1dfb-46a3-97f8-cc1dd15a0439) | bottomProcess | coordinator | 1024 × 1000 | F6 |
| [role-coordinator-bottomProcess-1440.png](https://github.com/user-attachments/assets/df2e6bfd-5438-41cb-aa29-4e297da3864b) | bottomProcess | coordinator | 1440 × 1000 | F6 |
| [role-coordinator-capability-1024.png](https://github.com/user-attachments/assets/ea7cfe3e-cad6-4d98-83d1-e564472d9ec9) | capability | coordinator | 1024 × 1000 | F4, F6 |
| [role-coordinator-capability-1440.png](https://github.com/user-attachments/assets/6349380c-bc7c-43b9-88fe-5be1de5ca2e0) | capability | coordinator | 1440 × 1000 | F4, F6 |
| [role-coordinator-direct-1024.png](https://github.com/user-attachments/assets/b925f2b5-8e8e-4b15-91e8-73b105d69c6e) | direct | coordinator | 1024 × 1000 | F6 |
| [role-coordinator-direct-1440.png](https://github.com/user-attachments/assets/b29b66d5-f5ff-4ca6-a111-c0ff95975bb9) | direct | coordinator | 1440 × 1000 | F6 |
| [role-coordinator-impact-1024.png](https://github.com/user-attachments/assets/773eb23b-71cd-425d-b1be-a20e1ec7375a) | impact | coordinator | 1024 × 1000 | F4, F6 |
| [role-coordinator-impact-1440.png](https://github.com/user-attachments/assets/0758727a-dc3d-4638-9a69-d3e2069dddba) | impact | coordinator | 1440 × 1000 | F4, F6 |
| [role-coordinator-initiative-1024.png](https://github.com/user-attachments/assets/6c46224a-f122-4264-ba61-3160eb98026a) | initiative | coordinator | 1024 × 1000 | F4, F6 |
| [role-coordinator-initiative-1440.png](https://github.com/user-attachments/assets/f38d23e5-3736-48f5-bfc7-f682ce753f87) | initiative | coordinator | 1440 × 1000 | F4, F6 |
| [role-coordinator-topCompare-1024.png](https://github.com/user-attachments/assets/354177e0-78f3-492a-ad7f-dfff784a688e) | topCompare | coordinator | 1024 × 1000 | F6 |
| [role-coordinator-topCompare-1440.png](https://github.com/user-attachments/assets/f61d8cde-70ed-4e01-b74a-9277c7e76334) | topCompare | coordinator | 1440 × 1000 | F6 |
| [role-coordinator-topProcess-1024.png](https://github.com/user-attachments/assets/a0086329-0713-49c9-8dad-e80af5ba8785) | topProcess | coordinator | 1024 × 1000 | F6 |
| [role-coordinator-topProcess-1440.png](https://github.com/user-attachments/assets/fed2e60b-94cd-4ee7-b87a-0921bb29fe79) | topProcess | coordinator | 1440 × 1000 | F6 |
| [role-owner-bottomCompare-1024.png](https://github.com/user-attachments/assets/57a2ff56-b046-47a9-85e8-83abb85ee334) | bottomCompare | owner | 1024 × 1000 | F6 |
| [role-owner-bottomCompare-1440.png](https://github.com/user-attachments/assets/0bdffd8b-b000-481b-ac5c-3f9658f549ed) | bottomCompare | owner | 1440 × 1000 | F6 |
| [role-owner-bottomProcess-1024.png](https://github.com/user-attachments/assets/6e24d252-b038-4441-804d-3ea94fd07e70) | bottomProcess | owner | 1024 × 1000 | F6 |
| [role-owner-bottomProcess-1440.png](https://github.com/user-attachments/assets/8d90ef5f-0b72-4e71-833d-52d99b946e5f) | bottomProcess | owner | 1440 × 1000 | F6 |
| [role-owner-capability-1024.png](https://github.com/user-attachments/assets/c57ce050-fdc5-43d1-bc96-5c13f8ef868b) | capability | owner | 1024 × 1000 | F4, F6 |
| [role-owner-capability-1440.png](https://github.com/user-attachments/assets/f7fcf572-19dd-4dca-bcda-78c0955e6f9d) | capability | owner | 1440 × 1000 | F4, F6 |
| [role-owner-direct-1024.png](https://github.com/user-attachments/assets/f75540de-65ab-40f6-9dda-9f90f47b1492) | direct | owner | 1024 × 1000 | F6 |
| [role-owner-direct-1440.png](https://github.com/user-attachments/assets/98a059e0-8876-4eb8-928d-ac47c17b0fba) | direct | owner | 1440 × 1000 | F6 |
| [role-owner-impact-1024.png](https://github.com/user-attachments/assets/e27dfd58-a1b8-46b2-acce-5e64a03b5f21) | impact | owner | 1024 × 1000 | F4, F6 |
| [role-owner-impact-1440.png](https://github.com/user-attachments/assets/3f5c4d8c-2cc8-49ce-853b-cf5e8c990719) | impact | owner | 1440 × 1000 | F4, F6 |
| [role-owner-initiative-1024.png](https://github.com/user-attachments/assets/7949951b-d962-49f4-b6ea-0302704eeca4) | initiative | owner | 1024 × 1000 | F4, F6 |
| [role-owner-initiative-1440.png](https://github.com/user-attachments/assets/cf5c66ae-4119-424f-bffb-283c78a39e5e) | initiative | owner | 1440 × 1000 | F4, F6 |
| [role-owner-topCompare-1024.png](https://github.com/user-attachments/assets/2824fdcb-168e-4c83-8ac4-432c1fe78992) | topCompare | owner | 1024 × 1000 | F6 |
| [role-owner-topCompare-1440.png](https://github.com/user-attachments/assets/7669a1f9-7b98-49cf-90fe-ab427bfaf328) | topCompare | owner | 1440 × 1000 | F6 |
| [role-owner-topProcess-1024.png](https://github.com/user-attachments/assets/bef6c3cc-7f65-4e6c-b2a3-3887e05efde6) | topProcess | owner | 1024 × 1000 | F6 |
| [role-owner-topProcess-1440.png](https://github.com/user-attachments/assets/dd4a3588-6133-46bb-9978-2f23a0b2a4e4) | topProcess | owner | 1440 × 1000 | F6 |
| [role-reader-bottomCompare-1024.png](https://github.com/user-attachments/assets/d48c0d18-1871-4a9c-aec8-52c77647876a) | bottomCompare | reader | 1024 × 1000 | F6 |
| [role-reader-bottomCompare-1440.png](https://github.com/user-attachments/assets/c38397de-ceda-4354-8764-aec5e8ec8e1d) | bottomCompare | reader | 1440 × 1000 | F6 |
| [role-reader-bottomProcess-1024.png](https://github.com/user-attachments/assets/cf589583-c6de-44df-916c-eea630719c20) | bottomProcess | reader | 1024 × 1000 | F6 |
| [role-reader-bottomProcess-1440.png](https://github.com/user-attachments/assets/3d26e3e3-3918-4f89-9ad7-cf9e761cf349) | bottomProcess | reader | 1440 × 1000 | F6 |
| [role-reader-capability-1024.png](https://github.com/user-attachments/assets/e1bd1c06-c247-4748-bf6e-9fcaf535a069) | capability | reader | 1024 × 1000 | F4, F6 |
| [role-reader-capability-1440.png](https://github.com/user-attachments/assets/2d55649d-8257-408a-979c-f6f001d26c3b) | capability | reader | 1440 × 1000 | F4, F6 |
| [role-reader-direct-1024.png](https://github.com/user-attachments/assets/b3093c19-c600-4fdc-9cc2-d8b1cb3f8125) | direct | reader | 1024 × 1000 | F6 |
| [role-reader-direct-1440.png](https://github.com/user-attachments/assets/dcb66ac4-5018-48ed-8d8d-33632e59de0b) | direct | reader | 1440 × 1000 | F6 |
| [role-reader-initiative-1024.png](https://github.com/user-attachments/assets/42c74c66-7a27-4022-a3b1-ad91f5b04419) | initiative | reader | 1024 × 1000 | F4, F6 |
| [role-reader-initiative-1440.png](https://github.com/user-attachments/assets/6b85e9c2-deb8-4a32-86a0-12397cfce874) | initiative | reader | 1440 × 1000 | F4, F6 |
| [role-reader-topCompare-1024.png](https://github.com/user-attachments/assets/1e9ae903-187a-4322-9eec-1658fbc106d9) | topCompare | reader | 1024 × 1000 | F6 |
| [role-reader-topCompare-1440.png](https://github.com/user-attachments/assets/d8057140-0d2f-4266-b2c1-24d928813e15) | topCompare | reader | 1440 × 1000 | F6 |
| [role-reader-topProcess-1024.png](https://github.com/user-attachments/assets/ca99cc9c-a178-4376-a6b0-8ad9623ec5fc) | topProcess | reader | 1024 × 1000 | F6 |
| [role-reader-topProcess-1440.png](https://github.com/user-attachments/assets/5370c46e-f256-43ec-9b95-9854549bfb90) | topProcess | reader | 1440 × 1000 | F6 |
