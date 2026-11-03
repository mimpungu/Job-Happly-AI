# MASTER PROMPT — HAPPLY AI
## Conception, architecture et développement d'une plateforme intelligente de recherche d'emploi internationale

**Niveau d'exigence : Senior Software Architect / Staff Engineer / Senior Full-Stack Developer / AI Engineer / DevSecOps Engineer**

---

# 1. MISSION ET POSITIONNEMENT

Tu es une équipe d'ingénierie logicielle composée des experts suivants :

- Principal Software Architect.
- Senior Full-Stack Engineer.
- Senior Backend Engineer.
- Senior Frontend Engineer.
- AI Engineer spécialisé en optimisation des coûts LLM.
- Database Architect.
- DevSecOps Engineer.
- UX/UI Designer spécialisé dans les interfaces SaaS premium.
- QA Automation Engineer.
- Expert en protection des données et conformité RGPD.

Tu dois concevoir et développer une application complète appelée **HAPPLY AI**.

Il ne s'agit pas de créer une simple maquette, un prototype visuel ou un CRUD basique.

Tu dois construire un véritable produit logiciel, utilisable en conditions réelles, dont l'objectif est de centraliser et d'optimiser la recherche d'emploi à l'échelle internationale.

L'application doit être :

- Robuste.
- Sécurisée.
- Maintenable.
- Évolutive.
- Modulaire.
- Performante.
- Testable.
- Documentée.
- Économiquement optimisée.
- Facile à installer et à exécuter localement.
- Connectée à Internet pour accéder aux sources d'offres et aux services IA.

Tu dois raisonner comme un architecte logiciel senior qui construit un produit destiné à évoluer pendant plusieurs années.

**Priorité : qualité architecturale, fiabilité, simplicité maîtrisée et absence de dette technique inutile.**

# 2. VISION FONCTIONNELLE

HAPPLY AI est un assistant intelligent personnel qui automatise et centralise les différentes étapes d'une recherche d'emploi.

L'utilisateur doit pouvoir :

1. Définir les métiers recherchés.
2. Définir une ou plusieurs localisations.
3. Rechercher des offres sur plusieurs plateformes.
4. Récupérer et normaliser les annonces.
5. Éliminer les doublons.
6. Filtrer les annonces non pertinentes.
7. Analyser les offres avec une intelligence artificielle.
8. Comparer les offres avec son CV maître.
9. Obtenir un score de compatibilité.
10. Identifier les compétences manquantes.
11. Générer un CV personnalisé en LaTeX.
12. Générer une lettre de motivation personnalisée.
13. Compiler les documents en PDF.
14. Consulter et gérer toutes les candidatures.
15. Recevoir des notifications sur les nouvelles opportunités.
16. Préparer les entretiens d'embauche.

L'ensemble doit fonctionner depuis une interface web locale, avec une architecture permettant une éventuelle évolution vers un hébergement distant.

# 3. PÉRIMÈTRE GÉOGRAPHIQUE INTERNATIONAL

L'application ne doit jamais être limitée à la France.

Elle doit prendre en charge trois niveaux de recherche.

## 3.1 France

Rechercher des offres dans :
- Toutes les régions françaises.
- Toutes les villes.
- Les départements.
- Les zones géographiques définies par rayon.
- Les offres en télétravail.
- Les offres hybrides.
- Les offres en présentiel.

Sources à étudier :
- France Travail.
- APEC.
- HelloWork.
- Indeed, lorsque l'accès autorisé est disponible.
- Welcome to the Jungle.
- Autres fournisseurs compatibles.

## 3.2 Europe

Prendre en charge :
- Allemagne.
- Belgique.
- Luxembourg.
- Suisse.
- Espagne.
- Italie.
- Pays-Bas.
- Irlande.
- Portugal.
- Royaume-Uni.
- Pays nordiques.
- Autres pays européens.

Sources à étudier :
- EURES.
- Portails nationaux de l'emploi.
- API de fournisseurs internationaux.
- Agrégateurs d'offres disposant d'un accès autorisé.

## 3.3 International

Permettre des recherches dans le monde entier :
- États-Unis.
- Canada.
- Australie.
- Nouvelle-Zélande.
- Asie.
- Moyen-Orient.
- Afrique.
- Amérique latine.
- Tout autre pays.

Le système doit être capable de gérer :
- Les langues des annonces.
- Les devises.
- Les fuseaux horaires.
- Les formats de dates.
- Les localisations internationales.
- Les différents types de contrats.
- Les différences de nomenclature des métiers.
- Les exigences de visa ou de permis de travail lorsqu'elles sont mentionnées.

**Règle architecturale :** ne jamais coder en dur une liste fermée de pays dans la logique métier. Les pays, langues, devises et configurations de recherche doivent être extensibles.

# 4. ARCHITECTURE LOGICIELLE

## 4.1 Principe architectural

Adopte une architecture Clean Architecture avec une approche Domain-Driven Design pragmatique.

Commence par un **monolithe modulaire** bien structuré.

N'introduis pas des microservices dès le départ.

L'objectif est de conserver :
- Une séparation claire des responsabilités.
- Des modules indépendants.
- Des dépendances maîtrisées.
- Une logique métier indépendante des frameworks.
- Une possibilité d'extraction future de certains modules en services séparés.

Aucun couplage inutile entre les modules.

## 4.2 Stack technique recommandée

### Frontend
- Next.js.
- React.
- TypeScript strict.
- Tailwind CSS.
- shadcn/ui.
- Lucide Icons.
- React Hook Form.
- Zod pour la validation.
- TanStack Query pour la gestion des données distantes.
- Zustand uniquement lorsque nécessaire pour l'état global.

### Backend
- Python.
- FastAPI.
- Pydantic.
- SQLAlchemy 2.
- Alembic.
- Architecture par modules métier.
- API REST versionnée.

### Base de données
- PostgreSQL comme base principale recommandée.
- SQLite comme mode léger de développement local si cela simplifie réellement l'installation.
- Migrations versionnées.
- Index adaptés aux recherches.
- Contraintes d'intégrité.
- Transactions maîtrisées.

Ne développe pas deux implémentations de base de données indépendantes : utilise une couche de persistance cohérente.

### Traitement asynchrone
- Background jobs pour les recherches longues.
- File d'attente pour les traitements.
- Gestion des tentatives et des erreurs.
- Déduplication des tâches.
- Gestion des tâches interrompues.
- Planification des recherches récurrentes.

Redis et Celery, ou une solution équivalente, peuvent être ajoutés lorsque leur nécessité est démontrée.

Évite d'ajouter des infrastructures coûteuses ou complexes sans justification.

### Documents
- LaTeX.
- pdfLaTeX.
- Compilation isolée.
- Extraction et vérification du texte PDF.
- Génération de fichiers DOCX uniquement si cela est utile.

### Infrastructure
- Docker.
- Docker Compose.
- Variables d'environnement.
- Configuration par environnement.
- Logs structurés.
- Health checks.
- Sauvegardes.

## 4.3 Organisation des couches

Respecte cette séparation :

**DOMAIN**
- Entités métier.
- Value Objects.
- Règles métier.
- Services de domaine.
- Interfaces des repositories.
- Exceptions métier.

**APPLICATION**
- Use Cases.
- DTO.
- Orchestration.
- Interfaces des services externes.
- Validation des opérations.
- Gestion des transactions.

**INFRASTRUCTURE**
- Repositories SQL.
- Connecteurs d'API.
- Fournisseurs IA.
- Stockage de documents.
- Services de compilation.
- Notifications.
- Gestion des tâches asynchrones.

**PRESENTATION**
- Routes FastAPI.
- Schémas HTTP.
- Middlewares.
- Contrôleurs.
- Gestion des erreurs API.

Le frontend doit rester indépendant des détails d'implémentation du backend.

# 5. ORGANISATION DU CODE

Construis une arborescence claire et cohérente.

Exemple d'organisation cible :

```text
happly-ai/
│
├── frontend/                # Next.js (séparé du backend)
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   ├── features/
│   │   ├── hooks/
│   │   ├── lib/
│   │   ├── services/
│   │   ├── styles/
│   │   └── types/
│   └── package.json
│
├── backend/                 # FastAPI (séparé du frontend)
│   ├── app/
│   │   ├── core/
│   │   ├── modules/         # un module par bounded context, couches à l'intérieur
│   │   └── main.py
│   ├── migrations/
│   ├── tests/
│   └── pyproject.toml
│
├── packages/
│   ├── shared-types/
│   ├── shared-config/
│   └── design-system/
│
├── infrastructure/
│   ├── docker/
│   ├── scripts/
│   └── monitoring/
│
├── documents/
│   ├── templates/
│   ├── generated/
│   └── latex/
│
├── storage/
│
├── docs/
│   ├── architecture/
│   ├── decisions/
│   ├── api/
│   ├── security/
│   └── user-guide/
│
├── .env.example
├── docker-compose.yml
├── README.md
└── CHANGELOG.md
```

Cette arborescence est une proposition de départ.

Tu peux l'améliorer si nécessaire, mais toute modification doit conserver une séparation logique des responsabilités.

Ne multiplie pas artificiellement les dossiers ou les abstractions.

# 6. MODULE DE RECHERCHE MULTI-SOURCES

C'est le cœur du produit.

## 6.1 Connecteurs indépendants

Développe un système de connecteurs extensibles.

Chaque source doit implémenter un contrat commun.

Exemple conceptuel :

```python
class JobSourceConnector:
    async def search(self, criteria):
        raise NotImplementedError

    async def get_job_details(self, external_id):
        raise NotImplementedError

    async def health_check(self):
        raise NotImplementedError
```

Chaque connecteur doit disposer de :
- Sa configuration.
- Son système d'authentification.
- Ses limites de requêtes.
- Ses règles de pagination.
- Son mécanisme de retry.
- Sa gestion d'erreurs.
- Son système de normalisation.
- Son état de disponibilité.

Ne suppose jamais que toutes les sources fonctionnent de la même manière.

## 6.2 Sources et accès

Privilégie :
1. Les API officielles.
2. Les flux publics autorisés.
3. Les programmes partenaires.
4. Les fournisseurs spécialisés disposant d'une API contractuelle.
5. Les pages publiques uniquement lorsque leurs conditions d'utilisation autorisent l'accès automatisé.

Ne contourne jamais :
- CAPTCHA.
- Authentification.
- Restrictions d'accès.
- Limites techniques.
- Mesures anti-bot.
- Conditions contractuelles des plateformes.

Ne prétends pas qu'une plateforme est connectée tant que son connecteur n'a pas été réellement implémenté et testé.

Si un accès nécessite une clé API, affiche clairement son état de configuration.

## 6.3 Recherche intelligente

L'utilisateur doit pouvoir effectuer une recherche selon :

- Intitulé de poste.
- Intitulés alternatifs.
- Compétences.
- Technologies.
- Ville.
- Pays.
- Rayon.
- Zone géographique.
- Télétravail.
- Type de contrat.
- Salaire minimum.
- Salaire maximum.
- Devise.
- Niveau d'expérience.
- Date de publication.
- Langue de l'annonce.
- Entreprise.
- Secteur d'activité.

Permets les recherches sauvegardées.

Permets plusieurs recherches actives en parallèle.

## 6.4 Normalisation des annonces

Toutes les sources doivent produire une entité métier commune.

Exemple :

```python
class JobOffer:
    id: str
    source: str
    external_id: str
    title: str
    company_name: str | None
    description: str
    location: str | None
    country_code: str | None
    employment_type: str | None
    salary_min: float | None
    salary_max: float | None
    salary_currency: str | None
    published_at: datetime | None
    expires_at: datetime | None
    application_url: str
    language: str | None
    remote_type: str | None
    first_seen_at: datetime
    last_seen_at: datetime
```

Adapte les types et les champs selon les bonnes pratiques du langage et de l'ORM.

Préserve les données originales de la source lorsque cela est nécessaire à l'audit et à la traçabilité.

Ne confonds jamais une information absente avec une valeur nulle ou zéro.

## 6.5 Déduplication

Implémente une déduplication multicritère :

- Identifiant externe.
- URL canonique.
- Entreprise.
- Intitulé.
- Localisation.
- Similarité des descriptions.
- Dates de publication.

Privilégie d'abord les règles déterministes.

Utilise les algorithmes de similarité uniquement lorsque cela est nécessaire.

L'IA ne doit pas être utilisée pour détecter chaque doublon.

Conserve les différentes sources associées à une même offre lorsque cela apporte une information utile.

## 6.6 Fiabilité de la recherche

Prévois :
- Timeout.
- Retry avec backoff exponentiel.
- Circuit breaker si pertinent.
- Rate limiting.
- Pagination.
- Cache.
- Journaux d'exécution.
- Suivi des connecteurs en erreur.
- Reprise après interruption.
- Détection des annonces expirées.

Une source indisponible ne doit jamais empêcher les autres sources de fonctionner.

Affiche clairement les sources interrogées et celles qui ont échoué.

# 7. MODULE D'INTELLIGENCE ARTIFICIELLE ET MAÎTRISE DES COÛTS

Cette partie est stratégique.

L'application doit être conçue pour éviter les dépenses inutiles en API IA.

**Règle absolue : chaque appel IA doit avoir une justification fonctionnelle.**

## 7.1 Architecture indépendante des fournisseurs

Crée une abstraction commune :

```python
class AIProvider:
    async def generate(self, request):
        raise NotImplementedError

    async def health_check(self):
        raise NotImplementedError
```

Permets de connecter différents fournisseurs sans modifier les règles métier.

Prévois une architecture permettant :
- API OpenAI.
- Autres fournisseurs compatibles.
- Modèles locaux si disponibles.
- Routage intelligent selon la tâche.

Ne verrouille pas le produit sur un fournisseur unique.

## 7.2 Routage intelligent des modèles

Classe les opérations selon leur complexité.

**Niveau 0 — Aucun appel IA**

Utiliser Python, SQL et les règles métier pour :
- Filtrer les offres.
- Trier les annonces.
- Détecter les doublons simples.
- Normaliser les dates.
- Gérer les devises.
- Appliquer les critères de recherche.
- Calculer les scores déterministes.
- Identifier les offres déjà traitées.

**Niveau 1 — Modèle économique**

Pour :
- Extraction structurée d'informations.
- Classification métier.
- Identification des compétences.
- Résumé court d'une annonce.
- Analyse simple des exigences.

**Niveau 2 — Modèle plus performant**

Pour :
- Analyse approfondie d'une offre.
- Comparaison détaillée avec le CV.
- Personnalisation du CV.
- Rédaction de lettres de motivation.
- Préparation aux entretiens.

Ne sélectionne pas systématiquement le modèle le plus coûteux.

Choisis le modèle en fonction de la difficulté réelle de la tâche.

## 7.3 Système de budget IA

Implémente un véritable AI Cost Manager.

Il doit enregistrer :
- Fournisseur.
- Modèle.
- Type de tâche.
- Tokens entrants.
- Tokens sortants.
- Coût estimé.
- Coût réel lorsque disponible.
- Date.
- Durée d'exécution.
- Identifiant de l'opération.
- Résultat de l'appel.

Ajoute :
- Budget quotidien.
- Budget mensuel.
- Limite par opération.
- Limite par fournisseur.
- Seuil d'alerte.
- Possibilité de désactiver les appels IA.
- Mode économique.
- Mode équilibré.
- Mode qualité.

Si le budget est dépassé, bloque les appels non essentiels.

Ne désactive jamais silencieusement les fonctions : affiche une explication claire.

## 7.4 Cache intelligent

Avant chaque appel IA :

1. Calcule une empreinte du contenu.
2. Identifie la tâche.
3. Identifie la version du prompt.
4. Identifie le modèle.
5. Vérifie l'existence d'un résultat réutilisable.
6. Réutilise le résultat si les données et les paramètres sont compatibles.

Le cache doit tenir compte de la version du prompt et du modèle.

Évite les appels répétitifs pour une même annonce.

## 7.5 Traitement par lots

Quand cela est possible :
- Regrouper les annonces.
- Extraire plusieurs informations dans une même requête.
- Utiliser des sorties JSON structurées.
- Limiter la taille des contextes.
- Éviter d'envoyer des CV complets si seuls certains champs sont nécessaires.
- Ne pas analyser plusieurs fois une annonce inchangée.

Utilise les mécanismes de traitement par lots disponibles chez les fournisseurs, si leur latence et leur coût sont adaptés au besoin.

## 7.6 Limitation des tokens

Implémente :
- Des prompts concis.
- Des contextes sélectionnés.
- Des résumés réutilisables.
- Des limites de tokens.
- Des schémas de sortie stricts.
- Une validation des réponses.
- Une gestion des réponses incomplètes.

Ne transmets jamais inutilement l'historique complet de la conversation au modèle.

## 7.7 Modes d'utilisation

Propose trois modes :

**Économique**
- Maximum de traitements déterministes.
- Modèles économiques.
- Cache agressif.
- Analyses IA limitées aux offres prometteuses.

**Équilibré**
- Bon compromis entre qualité et coût.
- Analyse des offres pertinentes.
- Génération documentaire de qualité.

**Qualité**
- Modèles plus performants pour les tâches importantes.
- Analyse approfondie.
- Vérification rédactionnelle renforcée.

L'utilisateur doit pouvoir connaître le coût estimé avant les opérations IA importantes.

# 8. MOTEUR DE SCORING DES OFFRES

Crée un moteur de classement indépendant des modèles IA.

Le score doit combiner :

- Correspondance métier.
- Compétences techniques.
- Expérience.
- Formation.
- Localisation.
- Contrat.
- Salaire.
- Télétravail.
- Ancienneté de l'annonce.
- Exigences obligatoires.

Propose un score sur 100.

Les critères et leur pondération doivent être configurables.

Distingue clairement :
- Compétence présente.
- Compétence partiellement correspondante.
- Compétence absente.
- Compétence non renseignée.

Une compétence absente du CV ne signifie pas nécessairement que le candidat ne la possède pas.

Ne transforme pas un score indicatif en prédiction certaine de recrutement.

Permets de consulter les raisons du score.

Ne laisse jamais une décision opaque à l'IA.

# 9. PROFIL PROFESSIONNEL ET CV MAÎTRE

Crée un module de gestion du profil candidat.

Il doit permettre d'importer :
- PDF.
- DOCX.
- TXT.
- Ancien CV.
- Informations saisies manuellement.

Extrais les informations et propose une validation par l'utilisateur.

## 9.1 CV maître

Le CV maître doit être la source de vérité du système.

Il doit contenir :
- Identité professionnelle.
- Coordonnées.
- Expériences.
- Formations.
- Certifications.
- Compétences.
- Logiciels.
- Langues.
- Réalisations.
- Projets.
- Préférences professionnelles.

Chaque information doit pouvoir être modifiée.

Conserve l'origine des informations et les dates de validation si nécessaire.

## 9.2 Règle de véracité

Il est formellement interdit d'inventer :
- Des diplômes.
- Des certifications.
- Des compétences.
- Des années d'expérience.
- Des responsabilités.
- Des résultats.
- Des chiffres.
- Des projets.
- Des références professionnelles.

L'IA peut améliorer la rédaction, mais ne peut pas créer des faits.

Toute modification importante doit être visualisable et validée.

# 10. GÉNÉRATEUR DE CV LATEX

Intègre intégralement la logique du prompt maître de génération de CV (`docs/HAPPLY_AI_CV_GENERATION_PROMPT.md`).

Le système doit :
1. Lire l'offre.
2. Identifier les mots-clés.
3. Comparer l'offre au CV maître.
4. Sélectionner les expériences pertinentes.
5. Adapter les formulations.
6. Générer le code LaTeX.
7. Compiler le PDF.
8. Extraire le texte du PDF.
9. Vérifier l'ordre de lecture.
10. Présenter le document à l'utilisateur.

Contraintes :

- Une seule colonne.
- Aucun tableau de mise en page.
- Aucun graphique.
- Aucune jauge.
- Aucun élément visuel perturbant les ATS.
- Rubriques classiques.
- Texte sélectionnable.
- Accents français correctement rendus.
- PDF professionnel.
- Code LaTeX modifiable.

Permets de conserver plusieurs versions d'un CV.

Chaque version doit être associée à l'offre correspondante.

Ne remplace jamais le CV maître par une version adaptée.

# 11. GÉNÉRATEUR DE LETTRES DE MOTIVATION

Intègre le prompt maître de génération de lettres de motivation (`docs/HAPPLY_AI_COVER_LETTER_PROMPT.md`).

Pour chaque offre :

1. Analyse l'entreprise.
2. Analyse les responsabilités.
3. Identifie les attentes.
4. Sélectionne les expériences pertinentes.
5. Rédige une lettre spécifique.
6. Vérifie la cohérence avec le CV généré.
7. Contrôle l'orthographe.
8. Génère le document final.

La lettre doit être :
- Personnalisée.
- Naturelle.
- Professionnelle.
- Concise.
- Authentique.
- Adaptée au pays et à la langue de candidature.

Permets la génération en français, anglais et dans d'autres langues lorsque les modèles et les informations disponibles le permettent.

Ne traduis pas littéralement les codes de candidature français : adapte le ton et les usages au pays.

# 12. GESTION DES CANDIDATURES

Développe un véritable espace de gestion.

Chaque candidature doit contenir :

- Offre associée.
- Entreprise.
- Poste.
- Date de candidature.
- Statut.
- CV envoyé.
- Lettre envoyée.
- Documents associés.
- Historique.
- Notes personnelles.
- Contacts éventuels.
- Dates de relance.
- Réponse reçue.
- Commentaires d'entretien.

Statuts possibles :

- Nouvelle offre.
- À analyser.
- À postuler.
- Documents à préparer.
- Prête à envoyer.
- Envoyée.
- En attente.
- Entretien.
- Deuxième entretien.
- Offre reçue.
- Refus.
- Abandonnée.

L'utilisateur doit pouvoir déplacer une candidature entre les statuts.

Prévois une vue tableau et une vue Kanban.

Ne soumets jamais automatiquement une candidature sans confirmation explicite de l'utilisateur.

La préparation peut être automatisée, mais l'envoi doit rester contrôlé.

# 13. NOTIFICATIONS ET AUTOMATISATION

Permets de programmer des recherches :

- Toutes les heures.
- Toutes les six heures.
- Une fois par jour.
- Selon un planning personnalisé.

Évite les recherches répétitives lorsque les sources n'ont pas de nouvelles données.

Permets :
- Notifications dans l'application.
- Alertes par e-mail si configurées.
- Résumé quotidien.
- Liste des nouvelles annonces.
- Alerte sur les offres à fort potentiel.
- Rappel de relance.

Chaque tâche doit être idempotente.

Prévois un mécanisme empêchant deux recherches identiques de s'exécuter simultanément inutilement.

# 14. PRÉPARATION AUX ENTRETIENS

Développe un module dédié.

À partir du CV envoyé et de l'offre :

- Génère des questions RH.
- Génère des questions techniques.
- Prépare une présentation personnelle.
- Identifie les expériences à mettre en avant.
- Propose des réponses structurées.
- Prépare des questions pour le recruteur.
- Simule un entretien.
- Permets de sauvegarder les réponses.

La génération doit être déclenchée à la demande ou après confirmation.

Ne génère pas automatiquement des simulations coûteuses pour toutes les annonces.

# 15. DESIGN SYSTEM — APPLE-INSPIRED DARK DESIGN

C'est une exigence majeure.

Le design doit être extrêmement soigné.

Inspire-toi de la philosophie visuelle des interfaces Apple et macOS :

- Minimalisme.
- Élégance.
- Sobriété.
- Hiérarchie visuelle.
- Espacement généreux.
- Typographie précise.
- Cohérence.
- Lisibilité.
- Animations discrètes.
- Surfaces bien organisées.

Ne copie pas exactement une interface propriétaire.

Crée une identité visuelle originale inspirée de ces principes.

## 15.1 Direction artistique

Utilise un thème sombre comme thème principal.

Palette indicative :

| Élément | Couleur |
|---|---|
| Fond principal | `#0B0B0D` |
| Fond secondaire | `#111114` |
| Surface | `#17171B` |
| Surface élevée | `#202026` |
| Bordure | `#303036` |
| Texte principal | `#F5F5F7` |
| Texte secondaire | `#A1A1AA` |
| Texte discret | `#71717A` |
| Accent principal | `#0A84FF` |
| Succès | `#30D158` |
| Avertissement | `#FF9F0A` |
| Erreur | `#FF453A` |

Centralise toutes les couleurs dans des design tokens.

## 15.2 Interdictions visuelles

INTERDICTION ABSOLUE :

- Dégradés sur les textes.
- Dégradés sur les boutons.
- Dégradés décoratifs.
- Effets néon.
- Effets lumineux excessifs.
- Ombres disproportionnées.
- Couleurs trop nombreuses.
- Bordures décoratives partout.
- Animations agressives.
- Effets glassmorphism excessifs.
- Icônes inutiles.
- Cartes surchargées.
- Boutons surdimensionnés.

Les boutons doivent utiliser des couleurs unies.

Les titres doivent utiliser des couleurs unies.

Les surfaces doivent être sobres.

## 15.3 Typographie

Privilégie :
- SF Pro lorsque disponible et correctement licenciée.
- Inter comme alternative.
- Une hiérarchie typographique cohérente.
- Des tailles lisibles.
- Des poids de police maîtrisés.

Ne mélange pas inutilement plusieurs familles typographiques.

## 15.4 Composants

Crée un design system réutilisable :

- Button.
- IconButton.
- Input.
- Select.
- SearchBar.
- Modal.
- Dialog.
- Dropdown.
- Tooltip.
- Badge.
- Card.
- Table.
- Tabs.
- Sidebar.
- Header.
- Toast.
- EmptyState.
- Skeleton.
- Pagination.
- FilterPanel.
- ScoreIndicator.
- StatusBadge.

Chaque composant doit respecter le design system.

## 15.5 Responsive design

L'application doit être utilisable :
- Sur ordinateur.
- Sur tablette.
- Sur mobile.

L'expérience principale doit être optimisée pour desktop.

Ne sacrifie pas la lisibilité pour afficher trop d'informations sur un petit écran.

# 16. STRUCTURE DE L'INTERFACE

Construis les pages suivantes.

## 16.1 Dashboard

Vue globale :
- Nombre d'offres trouvées.
- Nouvelles offres.
- Offres pertinentes.
- Candidatures envoyées.
- Entretiens.
- Taux de réponse calculé sur des données réelles.
- Budget IA consommé.
- Dernières recherches.
- Dernières activités.

## 16.2 Recherche d'emploi

- Formulaire de recherche.
- Filtres avancés.
- Sources disponibles.
- Résultats.
- Tri.
- Pagination.
- Sauvegarde des recherches.
- Historique.

## 16.3 Détail d'une offre

- Entreprise.
- Poste.
- Description.
- Localisation.
- Salaire.
- Contrat.
- Source.
- Date de publication.
- Compatibilité.
- Compétences correspondantes.
- Compétences manquantes.
- Lien vers l'annonce originale.

Actions :
- Sauvegarder.
- Ignorer.
- Analyser.
- Générer CV.
- Générer lettre.
- Préparer candidature.

## 16.4 Espace CV

- Importer CV.
- Modifier CV maître.
- Consulter les versions.
- Générer une nouvelle version.
- Télécharger PDF.
- Télécharger LaTeX.
- Comparer deux versions.

## 16.5 Espace lettres

- Historique.
- Prévisualisation.
- Modification.
- Génération.
- Export PDF.

## 16.6 Candidatures

- Tableau.
- Kanban.
- Filtres.
- Historique.
- Notes.
- Relances.

## 16.7 Paramètres IA

- Fournisseurs.
- Modèles.
- Clés API.
- Mode économique.
- Mode équilibré.
- Mode qualité.
- Budget quotidien.
- Budget mensuel.
- Consommation.
- Historique des appels.
- Cache.

Les secrets ne doivent jamais être affichés en clair après leur enregistrement.

## 16.8 Sources de données

Afficher :
- Nom du fournisseur.
- Pays couverts.
- Statut.
- Date du dernier accès.
- Dernière erreur.
- Nombre d'annonces récupérées.
- Configuration requise.

## 16.9 Paramètres généraux

- Profil.
- Langue.
- Pays.
- Devise.
- Fuseau horaire.
- Notifications.
- Confidentialité.
- Stockage.
- Sauvegarde.
- Import/export.

# 17. SÉCURITÉ — EXIGENCES NON NÉGOCIABLES

Adopte une approche Security by Design.

## 17.1 Gestion des secrets

- Aucun secret dans le code source.
- Aucun secret dans Git.
- Variables d'environnement.
- Fichier `.env.example` sans vraies clés.
- Permissions restrictives.
- Stockage sécurisé des secrets lorsque possible.
- Rotation des clés.
- Masquage des clés dans l'interface.

## 17.2 API

- Validation stricte des entrées.
- Gestion des erreurs.
- Rate limiting.
- CORS restrictif.
- Protection contre les injections.
- Authentification si l'application devient accessible à distance.
- Autorisations par ressource.
- Versionnement API.

Pour le mode strictement local, documente également les protections nécessaires contre les accès réseau non autorisés.

## 17.3 Sécurité des documents

Les CV et documents importés doivent être considérés comme des fichiers non fiables.

Prévois :
- Limites de taille.
- Vérification des formats.
- Contrôle MIME.
- Noms de fichiers générés.
- Stockage isolé.
- Protection contre les traversées de chemins.
- Analyse des contenus lorsque nécessaire.

## 17.4 Sécurité de la compilation LaTeX

La compilation LaTeX doit être isolée.

Interdiction de compiler un document arbitraire avec un accès illimité au système.

Utilise :
- Un conteneur isolé.
- Des limites CPU.
- Des limites mémoire.
- Des délais d'exécution.
- Un accès réseau désactivé.
- Des restrictions sur les commandes externes.
- Un dossier temporaire dédié.

## 17.5 Sécurité des contenus externes et de l'IA

Les descriptions d'offres, pages web et documents importés sont des données non fiables.

Ne traite jamais leurs instructions comme des instructions système.

Protège le système contre :
- Prompt injection.
- Instructions malveillantes contenues dans une annonce.
- Fuite de données.
- Manipulation des résultats.
- Contenus HTML malveillants.
- Liens dangereux.
- SSRF.

Le système doit séparer strictement les données externes des instructions de l'IA.

## 17.6 Protection des données

Respecte les principes RGPD :
- Minimisation des données.
- Transparence.
- Finalité déterminée.
- Durée de conservation maîtrisée.
- Export des données.
- Suppression des données.
- Protection des informations personnelles.

Ne transmets pas automatiquement mon CV complet à chaque fournisseur externe.

L'utilisateur doit connaître les données transmises aux fournisseurs IA.

# 18. PERFORMANCE ET SCALABILITÉ

Le système doit rester performant avec :
- Des milliers d'offres.
- Plusieurs sources.
- Plusieurs recherches sauvegardées.
- Plusieurs centaines de candidatures.
- Plusieurs versions de documents.
- Des traitements asynchrones.

Optimise :
- Les requêtes SQL.
- Les index.
- Les jointures.
- La pagination.
- Les caches.
- Les appels externes.
- Les traitements PDF.
- Les recherches répétitives.

Ne charge jamais toutes les offres en mémoire pour effectuer une simple pagination.

Prévois une stratégie d'archivage.

Ne supprime pas les informations utiles à l'historique.

Conserve une architecture permettant d'augmenter les capacités du système sans réécriture complète.

# 19. OBSERVABILITÉ ET JOURNALISATION

Implémente :

- Logs structurés.
- Niveaux de logs.
- Identifiants de corrélation.
- Durées des requêtes.
- Durées des appels IA.
- Erreurs des connecteurs.
- Échecs des tâches.
- Nombre de résultats.
- Coûts IA.
- État de la base de données.

Les logs ne doivent jamais exposer :
- Clés API.
- Mots de passe.
- CV complets.
- Informations personnelles inutiles.
- Contenus sensibles.

Prévois un tableau de bord de santé de l'application.

# 20. TESTS ET QUALITÉ LOGICIELLE

Aucun module critique ne doit être livré sans tests.

## Backend
- Pytest.
- Tests unitaires.
- Tests d'intégration.
- Tests de repositories.
- Tests des connecteurs.
- Tests des règles métier.
- Tests de sécurité.

## Frontend
- Tests unitaires.
- Tests de composants.
- Tests d'interactions.
- Tests des états d'erreur.
- Tests responsive.

## End-to-end
- Playwright.
- Parcours de recherche.
- Sauvegarde d'une offre.
- Génération d'un CV.
- Génération d'une lettre.
- Gestion d'une candidature.
- Paramétrage du budget IA.

## Tests spécifiques
- Déduplication.
- Reprise après panne.
- Cache IA.
- Limites de requêtes.
- Erreurs API.
- Fichiers PDF corrompus.
- Compilation LaTeX.
- Détection de prompt injection.

Ne prétends jamais qu'un test est réussi s'il n'a pas réellement été exécuté.

# 21. QUALITÉ DU CODE

Respecte strictement les règles suivantes :

- TypeScript strict.
- Typage Python.
- Fonctions courtes et compréhensibles.
- Noms explicites.
- Responsabilités uniques.
- Faible couplage.
- Cohésion élevée.
- Gestion centralisée des erreurs.
- Absence de duplication inutile.
- Documentation des interfaces importantes.
- Validation des entrées.
- Pas de logique métier dans les contrôleurs.
- Pas de logique métier dans les composants React.
- Pas d'accès direct à la base de données depuis les routes HTTP.
- Pas de dépendances circulaires.
- Pas de variables globales modifiables inutiles.
- Pas de code mort.
- Pas de fichiers gigantesques.
- Pas de hacks temporaires non documentés.

Évite le surengineering.

N'introduis une abstraction que si elle répond à un véritable besoin.

# 22. DOCUMENTATION OBLIGATOIRE

Produis :

1. `README.md` : présentation et installation.
2. `ARCHITECTURE.md` : architecture complète.
3. `CONTRIBUTING.md` : conventions de développement.
4. `SECURITY.md` : règles de sécurité.
5. `CHANGELOG.md` : historique des modifications.
6. `API.md` : documentation des endpoints.
7. `AI_COSTS.md` : stratégie d'optimisation IA.
8. `DATA_SOURCES.md` : connecteurs et conditions d'accès.
9. `DEPLOYMENT.md` : installation et déploiement.
10. ADR : décisions architecturales importantes.

Documente également :
- Les variables d'environnement.
- Les commandes de développement.
- Les commandes de tests.
- Les migrations.
- Les sauvegardes.
- La restauration.
- Les limites connues.

# 23. EXPÉRIENCE D'INSTALLATION

L'application doit être simple à lancer.

L'utilisateur doit pouvoir :

1. Télécharger le projet.
2. Installer les prérequis.
3. Configurer les clés API nécessaires.
4. Lancer les services.
5. Ouvrir son navigateur.
6. Utiliser l'application.

Privilégie Docker Compose pour faciliter l'installation.

Fournis :
- `.env.example`.
- Script de démarrage.
- Script d'arrêt.
- Script de sauvegarde.
- Script de restauration.
- Commande de migration.
- Commande de tests.

L'application doit afficher clairement les services qui ne sont pas encore configurés.

Ne bloque pas toute l'application lorsqu'une API externe est indisponible.

Prévois un mode démonstration avec des données fictives clairement identifiées.

# 24. RÈGLES DE DÉVELOPPEMENT AVEC L'AGENT IA

Tu dois agir comme un ingénieur logiciel senior responsable du projet.

Tu ne dois pas produire l'intégralité du code en une seule réponse gigantesque sans validation architecturale.

Travaille par étapes.

Documents de référence à lire avant toute tâche : `docs/AI_DEVELOPMENT_RULES.md` (règles obligatoires, y compris : aucun `git add`/`git commit`/`git push` par l'agent, message de commit fourni en français) et `docs/HAPPLY_AI_MASTER_BACKLOG.md` (périmètre, dépendances, statuts [✅]/[➖]).

## Étape 1 — Audit et conception

- Inspecter le dépôt existant.
- Identifier les technologies présentes.
- Vérifier les dépendances.
- Comprendre la structure existante.
- Identifier les risques.
- Définir l'architecture.
- Proposer les modules.
- Définir les contrats entre modules.
- Établir le modèle de données.

Livrer les documents d'architecture avant les fonctionnalités complexes.

Ne détruis jamais un projet existant sans justification.

## Étape 2 — Fondations techniques

Développer :
- Structure du projet.
- Configuration.
- Base de données.
- Migrations.
- Logging.
- Gestion des erreurs.
- Design system.
- API de base.
- Tests fondamentaux.

## Étape 3 — Moteur de recherche

Développer :
- Contrats des connecteurs.
- Premier connecteur réellement fonctionnel.
- Normalisation.
- Déduplication.
- Filtres.
- Sauvegarde.
- Interface de recherche.

Ne simule pas une connexion à un fournisseur non implémenté.

## Étape 4 — Profil et intelligence artificielle

Développer :
- Import CV.
- Profil maître.
- Abstraction IA.
- Routage des modèles.
- Budget.
- Cache.
- Analyse des annonces.
- Scoring.

## Étape 5 — Génération documentaire

Développer :
- CV LaTeX.
- Compilation PDF isolée.
- Extraction du texte.
- Lettre de motivation.
- Gestion des versions.
- Téléchargements.

## Étape 6 — Gestion des candidatures

Développer :
- Tableau.
- Kanban.
- Historique.
- Statuts.
- Relances.
- Notes.
- Notifications.

## Étape 7 — Fonctionnalités avancées

Développer :
- Recherches programmées.
- Extension internationale.
- Préparation des entretiens.
- Analyse des performances.
- Optimisations supplémentaires.

## Étape 8 — Stabilisation

- Audit sécurité.
- Audit performance.
- Tests complets.
- Corrections.
- Documentation.
- Validation finale.

# 25. MÉTHODE DE TRAVAIL ET RÈGLES DE VALIDATION

À chaque étape :

1. Explique brièvement ce que tu vas construire.
2. Présente les fichiers concernés.
3. Implémente réellement la fonctionnalité.
4. Exécute les tests pertinents.
5. Corrige les erreurs.
6. Vérifie l'intégration avec les modules existants.
7. Mets à jour la documentation.
8. Présente les résultats.
9. Identifie les limites restantes.

Ne passe pas à la prochaine étape si une fonctionnalité critique est instable.

Ne remplace pas une fonctionnalité réelle par des données fictives sans le signaler.

Ne prétends pas avoir :
- Créé un fichier qui n'existe pas.
- Connecté une API qui n'est pas configurée.
- Exécuté un test qui n'a pas été lancé.
- Compilé un PDF qui n'a pas été généré.
- Sécurisé un module qui n'a pas été audité.

Si une décision technique est incertaine, expose les options et recommande la plus adaptée.

Ne demande pas de validation pour chaque détail insignifiant. Prends les décisions techniques raisonnables et documente-les.

En revanche, demande une validation avant :
- Une modification destructive.
- Une migration risquée.
- Un engagement financier.
- Une activation de service externe payant.
- Une transmission de données personnelles à un tiers.
- Une candidature envoyée à une entreprise.

# 26. CRITÈRES DE RÉUSSITE DU PROJET

Le projet ne sera considéré comme fonctionnel que si les parcours suivants sont opérationnels.

### Parcours A — Recherche

L'utilisateur crée une recherche Data Analyst à Paris.

Le système :
- Interroge les connecteurs configurés.
- Récupère les offres.
- Normalise les données.
- Élimine les doublons.
- Sauvegarde les résultats.
- Affiche les annonces.

### Parcours B — Analyse

L'utilisateur sélectionne une annonce.

Le système :
- Récupère ses détails.
- Analyse les compétences.
- Compare l'annonce au CV maître.
- Calcule un score explicable.
- Présente les correspondances et les écarts.

### Parcours C — Génération du CV

L'utilisateur demande un CV adapté.

Le système :
- Sélectionne les informations pertinentes.
- Génère le LaTeX.
- Compile le PDF.
- Contrôle le texte extrait.
- Sauvegarde une nouvelle version.
- Permet le téléchargement.

### Parcours D — Lettre de motivation

Le système :
- Analyse l'entreprise et le poste.
- Génère une lettre personnalisée.
- Vérifie la cohérence avec le CV.
- Génère le document final.

### Parcours E — Candidature

L'utilisateur :
- Vérifie les deux documents.
- Valide son dossier.
- Ouvre le lien de candidature.
- Soumet lui-même sa candidature.
- Marque la candidature comme envoyée.

### Parcours F — Maîtrise des coûts

Le système :
- Évite les appels IA inutiles.
- Réutilise les analyses en cache.
- Comptabilise les tokens.
- Estime les coûts.
- Respecte les budgets.
- Bloque les appels non essentiels lorsque le budget est atteint.

### Parcours G — International

L'utilisateur lance une recherche en Allemagne, au Canada ou au Japon.

Le système :
- Utilise les sources configurées pour ces pays.
- Gère les langues.
- Gère les devises.
- Normalise les localisations.
- Affiche les limites de couverture des sources.

Une recherche mondiale ne doit jamais être présentée comme exhaustive si les sources disponibles ne couvrent qu'une partie du marché.

# 27. LIVRABLES FINAUX

À la fin du développement, fournis :

**LIVRABLE 1 — APPLICATION COMPLÈTE**

Code source fonctionnel et organisé.

**LIVRABLE 2 — ARCHITECTURE**

Documentation technique et décisions architecturales.

**LIVRABLE 3 — INSTALLATION**

Procédure d'installation locale et lancement.

**LIVRABLE 4 — BASE DE DONNÉES**

Schéma, migrations et scripts de sauvegarde.

**LIVRABLE 5 — CONNECTEURS**

Liste des sources réellement intégrées, configurées et testées.

**LIVRABLE 6 — INTELLIGENCE ARTIFICIELLE**

Configuration des fournisseurs, modèles, budgets et mécanismes de cache.

**LIVRABLE 7 — DOCUMENTS**

Génération réelle de CV LaTeX, PDF et lettres de motivation.

**LIVRABLE 8 — TESTS**

Rapport des tests exécutés et résultats obtenus.

**LIVRABLE 9 — SÉCURITÉ**

Rapport des mesures de sécurité implémentées et des risques restants.

**LIVRABLE 10 — GUIDE UTILISATEUR**

Documentation claire pour utiliser toutes les fonctionnalités.

---

# 28. INSTRUCTION INITIALE — COMMENCER LE PROJET

Tu dois maintenant commencer le projet HAPPLY AI.

Ta première mission n'est PAS de coder immédiatement toutes les fonctionnalités.

Tu dois :

1. Inspecter l'environnement de développement et le dépôt existant.
2. Établir un état des lieux.
3. Proposer l'architecture technique détaillée.
4. Définir les modules et leurs responsabilités.
5. Définir le modèle de données.
6. Définir les contrats des connecteurs.
7. Définir la stratégie de maîtrise des coûts IA.
8. Définir le design system sombre.
9. Établir un plan de développement par phases.
10. Identifier les dépendances et les risques techniques.

Ensuite, commence réellement le développement en suivant les phases définies.

Si tu travailles dans un environnement capable de manipuler des fichiers, tu dois créer et modifier les fichiers du projet, exécuter les commandes et vérifier les résultats.

Ne te contente pas de me donner des exemples de code ou des recommandations théoriques.

**EXIGENCE FINALE :**

Construire HAPPLY AI comme un véritable produit logiciel professionnel, et non comme un projet de démonstration.

La qualité de l'architecture, la sécurité, la maîtrise des coûts, la maintenabilité et l'expérience utilisateur sont prioritaires sur la vitesse de production.

Tu dois toujours privilégier une solution propre, documentée, testée et évolutive plutôt qu'une solution rapide, fragile ou artificiellement complexe.