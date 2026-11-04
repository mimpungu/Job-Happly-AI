# Rapport de qualité — version candidate 0.5.0-rc.1

Mesuré le 2026-11-04, branche `dev`, sur l'environnement de travail (Linux, PostgreSQL 16 local, pdfLaTeX réel, Chromium Playwright). Chaque chiffre vient d'une exécution réelle ; ce qui n'a pas pu être vérifié est dit comme tel.

## 1. Verdict

| Question | Réponse |
|---|---|
| Les parcours métier principaux fonctionnent-ils de bout en bout ? | **Oui** : 8 parcours (import du CV, recherche, CV, lettre, candidature, budget IA, entretien, confidentialité) passent avec vraie API, vraie base, vrai pdfLaTeX et vrai navigateur. |
| Existe-t-il un défaut bloquant connu pour un usage local ? | **Non** (voir §6 pour les limites). |
| Peut-on déclarer une version stable (1.0) ? | **Non.** Le plan de releases (`RELEASE_PLAN.md`) exige l'internationalisation (EPIC 017), l'authentification (018-35/36) avant tout accès distant, et des connecteurs réels internationaux ; plusieurs tâches des EPIC 002, 006, 008 et 010 restent ouvertes. La version candidate **0.5.0-rc.1** est préparée, **non publiée** (aucun tag). |
| L'installation est-elle reproductible ? | **Partiellement vérifié** : la création de la base, les migrations, le démarrage de l'API et de l'interface sont rejoués à chaque lancement des parcours complets ; la voie Docker (`start.sh`) n'a **pas** pu être rejouée de zéro ici (pas de Docker dans l'environnement). |

## 2. Tests automatiques

| Niveau | Résultat |
|---|---|
| Backend (pytest, PostgreSQL réel, pdfLaTeX réel) | **1724 tests passent** |
| Couverture backend (lignes, `app/`) | **94,6 %** (12 423 / 13 127) ; seuil CI : 92 % |
| Frontend (Vitest, Testing Library) | **321 tests passent** (38 fichiers) |
| Accessibilité E2E (Playwright + axe, API simulée) | **140 / 140 passent** (3,1 min, 3 processus). Une première exécution complète avait vu 1 échec intermittent (`profil-clavier` : touche Entrée perdue avant l'hydratation de la page en mode développement) ; le test réessaie désormais la touche (jamais un clic) et la suite complète a été rejouée entièrement ensuite |
| Parcours complets (pile réelle) | **8 / 8 passent** (~35 s) |
| Formatage, lint, typage (ruff, mypy, Prettier, ESLint, `tsc`) | Passent (backend 418 fichiers formatés, mypy sans erreur) |
| CI GitHub sur `dev` | Dernier push vérifié : vert (run 15, commit `117ea3a`) ; les commits plus récents n'ont pas été poussés |

### Couverture par module

| Module | Lignes couvertes |
|---|---|
| `job_intelligence` | 97,9 % |
| `candidate_profile` | 96,9 % |
| `document_generation` | 95,7 % |
| `ai_management` | 95,7 % |
| `job_discovery` | 95,4 % |
| `core` | 95,4 % |
| `interview_preparation` | 95,1 % |
| `platform` | 94,2 % |
| `application_management` | 92,3 % |
| `privacy` | 88,3 % |
| `notifications` | 85,5 % |

Fichiers les moins couverts (> 30 lignes) : `notifications/infrastructure/preferences_repository.py` et `scheduled_task_repository.py` (54 %), `document_generation/infrastructure/generation_inputs.py` (61 %), `application_management/infrastructure/repository.py` (64 %), `notifications/presentation/router.py` (72 %), `interview_preparation/infrastructure/repository.py` (72 %). La couverture de lignes ne dit pas si les assertions sont bonnes : la priorité reste aux modules critiques (budget IA, déduplication, sécurité, faits des documents), tous au-dessus de 95 %.

## 3. Performance (20 000 offres, PostgreSQL local)

Seuils des tests volontairement larges (CI plus lente) ; valeurs mesurées ci-dessous sur l'environnement de travail.

| Mesure | Résultat | Seuil du test |
|---|---|---|
| Liste d'offres, page de 25 | ~0,14 s | 1,5 s |
| Page profonde (dernière page) | ~0,20 s | 1,5 s |
| 4 pages de 100 offres, sans doublon, ordre stable | ~0,52 s | — |
| Recherche texte (100 résultats parmi 20 000) | ~0,38 s | 2,0 s |
| Requêtes SQL par liste | indépendant de la taille de page (pas de N+1), ≤ 8 | ≤ 8 |
| EXPLAIN ANALYZE de la vraie requête de liste | exécution < 500 ms, pagination faite par la base | 500 ms |
| 10 workers concurrents, 100 tâches | chacune exécutée **exactement une fois**, ~1,3 s | — |
| 40 requêtes API simultanées (transactions séparées) | toutes 200, ~0,3 s | 10 s |

Non mesuré : charge HTTP soutenue (plusieurs milliers de requêtes/s), catalogues de 100 000 offres ou plus, performances sur le matériel cible.

## 4. Défauts trouvés et corrigés pendant l'EPIC 018-019

| Défaut | Comment trouvé | Correction |
|---|---|---|
| La mise en file d'une tâche échouait à partir de la 6ᵉ sur une même connexion (prédicat d'index partiel de `ON CONFLICT` en paramètres) | Test de charge | Prédicat littéral + test de régression |
| `PUT /notifications/preferences` et la mise à jour d'une tâche planifiée répondaient **500** (`MissingGreenlet`, `updated_at` expiré) | Tests de routes sur base réelle (les anciens tests acceptaient « 200 ou 503 ») | Relecture après écriture + 16 tests de routes |
| Règle de contrôle des PDF trop stricte : refusait tous les PDF pdfLaTeX (`/OpenAction` de destination) | Tests avec le vrai compilateur | Règle affinée + tests |
| Pages Espace CV (CV générés) et Lettres inexistantes côté interface | Audit de l'EPIC 019 | Pages construites, tests et E2E |
| Texte de la lettre non relisible après génération (non persisté) | Parcours complet | Aperçu à la génération, PDF ensuite (limite documentée) |
| Test clavier intermittent : Entrée pressée avant l'hydratation (mode développement) | Suite complète d'accessibilité | Le test réessaie la touche, suite rejouée : 140 / 140 |
| Assertion E2E trop faible (« aucun résultat » vraie pendant le chargement) | Relecture du parcours de recherche | État vide explicite attendu |
| Statuts du backlog et registre périmés | Audit de documentation | Réconciliation vérifiée + script `sync_backlog_registry.py` (contrôlé en CI) |

## 5. Critères d'acceptation de l'EPIC 019

| Critère | État |
|---|---|
| Tests critiques exécutés | ✅ |
| Aucun défaut bloquant connu | ✅ (usage local ; limites au §6) |
| Installation reproductible | ➖ voie Docker non rejouée de zéro ici |
| Documentation à jour | ✅ |
| Sauvegarde et restauration testées | ✅ (test automatisé `pg_dump` → `pg_restore` → comparaison) |
| Parcours métier principaux opérationnels | ✅ |
| Limites restantes clairement documentées | ✅ (ce rapport) |

## 6. Limites et dette connues

- **Pas d'authentification ni de multi-utilisateur** (018-35/36, ADR-0008) : exécution locale uniquement.
- **Internationalisation non réalisée** (EPIC 017) : interface en français, pas de référentiel de pays, de devises, ni de filtres multi-pays.
- **Sources d'offres** : Greenhouse, Lever et saisie manuelle seulement ; l'API France Travail est bloquée par le fournisseur ; EPIC 006 et 008 incomplets (pas de recherche par rayon, multilingue ni parallèle agrégée).
- **EPIC 010 incomplet** : pas de plafond par tâche ni par fournisseur, pas de coût estimé affiché avant l'opération, pas de fournisseur payant principal arrêté par ADR.
- **EPIC 002** : mode démonstration absent, protection des branches non vérifiée.
- **Tests de routes des notifications** : les anciens tests « 200 ou 503 » sont conservés mais redondants ; les nouveaux tests d'intégration les remplacent en pratique.
- **CI** : le workflow `e2e.yml` (parcours complets) n'a pas été exécuté sur GitHub ; il est déclenché à la demande et sur `master` pour limiter la consommation de minutes.
- **Lettres** : le texte n'est relisible à l'écran qu'à la génération.
- **Limiteur de débit et mesures** en mémoire, par processus (perdus au redémarrage).
- **Sauvegardes** non chiffrées ; purge de conservation manuelle (non planifiée).

## 7. Pour déclarer une version stable

1. Terminer l'EPIC 017 et les tâches ouvertes des EPIC 006, 008, 010, 002.
2. Intégrer l'authentification et le multi-utilisateur **ou** déclarer explicitement la version « locale uniquement ».
3. Rejouer l'installation Docker de zéro sur une machine propre, et exécuter `e2e.yml` sur GitHub.
4. Dérouler `RELEASE_CHECKLIST.md`.
