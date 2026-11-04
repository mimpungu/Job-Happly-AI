# ADR-0015 — Architecture du suivi des candidatures (CRM) et tableau de bord

- **Statut :** Accepté
- **Date :** 2026-11-04

## Contexte

L'EPIC 014 a pour objectif de centraliser, piloter et suivre le cycle de vie complet de chaque candidature dans un CRM personnel de recrutement, conformément à la spécification `docs/HAPPLY_AI_MASTER_SPEC.md` §12 et au parcours utilisateur §26 (Parcours E).
Les contraintes et exigences majeures sont :
1. **Contrôle absolu par l'utilisateur** : Aucune candidature n'est jamais soumise automatiquement. L'envoi externe est obligatoirement déclenché ou confirmé par l'utilisateur (`applied_at`).
2. **Machine à états stricte** : Gestion exhaustive des statuts de candidature (`new_offer`, `to_analyze`, `to_apply`, `documents_to_prepare`, `ready_to_send`, `sent`, `pending`, `interview`, `second_interview`, `offer_received`, `rejected`, `abandoned`).
3. **Traçabilité et historique complet** : Journalisation immuable de chaque événement (`status_change`, `note`, `interview`, `follow_up`, `other`).
4. **Association documentaire précise** : Rattachement des versions exactes de documents envoyés (CV version ID, lettre de motivation version ID).
5. **Préparation et audit de dossier** : Vérification de la présence des pièces indispensables avant envoi (CV ciblé, lettre, URL de candidature).
6. **Statistiques et KPIs réels** : Aucun indicateur fictif ni estimé arbitrairement. Le taux de réponse et les volumes sont calculés exclusivement à partir des données réelles de l'utilisateur.

## Décision

1. **Modèle de Domaine (`application_management.domain`)** :
   - Agrégat principal `ApplicationAggregate` encapsulant l'état, les dates clés (`created_at`, `applied_at`, `follow_up_at`, `response_received_at`), les contacts, les documents et les événements.
   - Machine à états déterministe avec matrice de transitions autorisées (`validate_status_transition`).
   - Objets-valeurs `ContactInfo`, `TimelineEvent`, `AssociatedDocument`, `ApplicationDossier`.
   - Moteur de calcul statistique pur (`compute_application_stats`, `calculate_response_rate`).

2. **Couche Applicative (`ApplicationTrackingService` & `DashboardService`)** :
   - Création unique de candidature liée à une offre (`DuplicateApplicationError` en cas de doublon pour le même propriétaire).
   - Confirmation manuelle de soumission externe (`confirm_manual_submission`) horodatant `applied_at` et créant l'événement de statut `SENT`.
   - Planification et suivi des relances (`schedule_follow_up`).
   - Préparation et validation du dossier (`prepare_dossier`) avec détection des éléments manquants.
   - Validation sécurisée des liens externes de candidature (`get_application_url_action`).
   - Agrégation des métriques globales pour le tableau de bord (`DashboardService`).

3. **Infrastructure & Persistance (`SQLAlchemyApplicationRepository` & `SQLAlchemyDashboardRepository`)** :
   - Exploitation des tables initiales existantes (`applications`, `application_events`, `application_contacts`, `application_documents`).
   - Prise en charge optimisée des requêtes de vue tableau (filtrage par statut, entreprise, intitulé, relance due) et de vue Kanban (regroupement par colonnes de statut).
   - Intégration transversale pour le Dashboard avec les offres réelles (`job_offers`) et le budget IA consommé (`ai_usages`, `ai_budgets`).

4. **API REST (`/api/v1/applications` & `/api/v1/dashboard`)** :
   - Endpoints RESTful complets pour les opérations CRM (création, consultation, filtres, kanban, détails, transitions de statut, notes, entretiens, relances, association de documents, dossier et dashboard).

## Alternatives étudiées

- **Envoi automatisé des candidatures par scraping / headless browser** : Formellement rejeté conformément à la spécification (§12 et §26). L'utilisateur doit garder la pleine maîtrise de l'acte de candidature ; l'outil prépare le dossier et valide l'URL de candidature, mais ne soumet rien en cachette.
- **Statuts libres en chaîne de caractères** : Rejeté au profit d'un `StrEnum` strict et d'une contrainte `CHECK` en base de données pour garantir l'intégrité de la machine à états.

## Conséquences

- L'utilisateur dispose d'un CRM personnel rigoureux pour piloter toutes ses candidatures.
- Le dossier de candidature relie harmonieusement les offres (EPIC 006/007/008) et les documents générés (EPIC 012/013).
- Les métriques du tableau de bord reflètent fidèlement l'activité réelle de recherche d'emploi.


## Révision du 2026-11-04 — audit et corrections

Un audit exécuté sur PostgreSQL réel et dans un navigateur a montré que l'EPIC 014 était coché
alors que l'interface n'existait pas (les pages Candidatures et Tableau de bord étaient des
écrans vides) et que plusieurs chiffres affichés étaient faux ou inventés. Décisions correctives :

1. **Aucun chiffre sans donnée** : « nouvelles offres » interrogeait un statut `new` qui n'existe
   pas (toujours 0) ; « offres pertinentes » valait le total des offres ; un taux de réponse sans
   envoi s'affichait « 0 % ». Désormais : nouvelle = offre active vue depuis moins de 7 jours et
   ni sauvegardée, ni ignorée, ni suivie ; pertinente = dernier score ≥ seuil choisi par
   l'utilisateur pour ses notifications (70 par défaut), `None` tant qu'aucun score n'existe ;
   taux de réponse `None` sans candidature envoyée (un vrai 0 % reste 0 %). Le tableau de bord et
   les statistiques partagent la même règle (`compute_application_stats`).
2. **L'envoi reste sous contrôle de l'utilisateur** : une candidature ne peut plus être créée au
   statut « envoyée » ou « répondue » ; l'envoi ne se déduit pas d'un changement de statut mais
   d'une confirmation explicite, datée (jamais dans le futur), non rejouable (la date d'origine
   n'est plus écrasée) et possible seulement depuis les statuts de préparation. L'interface
   rappelle que l'application n'envoie rien.
3. **Machine à états appliquée** : la confirmation d'envoi la contournait ; « prête à envoyer »
   exige désormais un dossier complet ; un changement vers le même statut ne crée plus
   d'événement ; la ligne est verrouillée (`FOR UPDATE`) pour que deux requêtes s'enchaînent.
4. **Documents** : les versions associées doivent exister, appartenir à l'utilisateur et être du
   bon type (un CV n'est pas une lettre) ; une fois envoyé, un document ne peut plus être
   remplacé (il atteste de ce qui est parti) ; réassocier la même version n'échoue plus ; la fiche
   renvoie enfin les documents (elle renvoyait toujours `[]`) avec leur audit de qualité.
5. **Relances** : « relance échue » signifie date atteinte (elle renvoyait toute relance
   planifiée) ; on ne planifie une relance que sur une candidature envoyée, dans le futur.
6. **Performance** : plus de N+1 (3 requêtes par candidature) ; le tableau est paginé en base, le
   Kanban renvoie le total réel par colonne et les 20 cartes les plus récentes (fenêtre SQL) ;
   les motifs `%` et `_` saisis dans les filtres sont littéraux.
7. **Sécurité** : le lien de candidature est refusé s'il n'est pas un lien http(s) nu
   (`javascript:`, identifiants intégrés, espaces) ; il est ouvert dans un onglet isolé
   (`noopener,noreferrer`) par l'utilisateur lui-même ; dates sans fuseau refusées.
8. **Architecture** : l'accès aux offres et aux documents passe par des ports (`OfferReaderPort`,
   `DocumentVersionReaderPort`) ; routes minces ; erreurs métier traduites centralement ; horloge
   injectable. Le tableau de bord est un modèle de lecture transverse assumé (offres, scores,
   candidatures, budget IA, recherches).
9. **Interface** : page Candidatures (tableau filtrable, Kanban, statistiques, URL source de
   vérité), fiche (statut, annonce, confirmation d'envoi, dossier, documents, relance, contacts,
   historique), action « Suivre cette candidature » depuis une offre, Tableau de bord. Vérifiée
   par des tests de composants et des tests E2E d'accessibilité avec données, aux trois tailles.

Limites assumées : pas de glisser-déposer dans le Kanban (le statut est validé par la machine à
états et l'envoi se confirme, ce qu'un déplacement de carte ne saurait exprimer) ; le budget IA
du tableau de bord somme les coûts sans conversion de devise ; la vérification du dossier contrôle
la présence et l'audit stocké des versions, pas le contenu des PDF.
