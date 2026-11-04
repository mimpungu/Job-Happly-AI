# Modèle de menaces — Happly AI

Périmètre : application locale mono-utilisateur, sans authentification (ADR-0008), exécutée sur
`127.0.0.1`. Ce document est tenu à jour avec le code ; les contrôles cités renvoient à des tests.

## 1. Ce qu'il faut protéger

| Actif | Sensibilité | Où |
|---|---|---|
| CV, profil, coordonnées | Données personnelles | PostgreSQL, `storage/documents` |
| Candidatures, entretiens, réponses de simulation | Données personnelles | PostgreSQL |
| Clés d'API (IA, France Travail) | Secret | Variables d'environnement (`.env`), jamais en base |
| Disponibilité de l'application | Service | API, base, worker |
| Intégrité des documents générés | Confiance (aucun fait inventé) | Contrôle des faits, audits |

## 2. Frontières de confiance

```text
Navigateur (UI) ──HTTP local──► API ──SQL──► PostgreSQL            [F1] [F2]
                                 │
                                 ├──HTTPS──► Fournisseurs d'IA                 [F3]
                                 ├──HTTPS──► Sources d'offres / sites publics  [F4]
                                 ├──processus isolé──► pdfLaTeX                [F5]
                                 └──fichiers importés (CV)                     [F6]
```

| Frontière | Données qui la traversent | Confiance accordée |
|---|---|---|
| F1 navigateur → API | Requêtes JSON, fichiers | Aucune : tout est validé (schémas bornés) |
| F2 API → base | Requêtes ORM paramétrées | Base de confiance, jamais de SQL assemblé |
| F3 API → IA | Texte d'offre, réalisations, réponses de simulation | Fournisseur **non fiable** : consentement, plafonds, politique de confidentialité, sorties validées |
| F4 API → sources | Requêtes publiques | Contenu **non fiable** (annonces = données) ; SSRF bloqué |
| F5 API → pdfLaTeX | Source LaTeX générée ou éditée | Source **non fiable** : liste noire, mode paranoïaque, env minimal, rlimits, réseau coupé |
| F6 fichier importé → extraction | PDF/DOCX/TXT | Fichier **non fiable** : taille, contenu réel, pages, ratio de compression |

## 3. Menaces et contrôles

| # | Menace (STRIDE) | Contrôles | Preuve |
|---|---|---|---|
| T1 | Accès distant à des données sans authentification (I) | Liaison `127.0.0.1`, ports Docker locaux, CORS restreint, `*` interdit, production impose base et mot de passe non exemple | `tests/architecture/test_local_mode.py` |
| T2 | Entrée malformée ou démesurée → déni de service (D) | Schémas bornés (longueur, nombre d'éléments), taille de requête, limite de débit (générale et routes coûteuses) | `test_input_validation.py`, `test_observability.py` |
| T3 | Injection SQL (T, I) | ORM / paramètres liés ; SQL dynamique interdit par test | `test_security_surface.py` |
| T4 | SSRF via une URL fournie (I) | HTTPS seul, pas d'identifiants, toutes les adresses résolues publiques ; surface sortante figée et revue | `tests/unit/job_discovery/test_http.py`, `test_security_surface.py` |
| T5 | Prompt injection via annonce ou document (T, E) | Données hors instructions, délimiteurs infalsifiables, motifs d'injection journalisés, sortie JSON validée, aucune action irréversible pilotée par l'IA | `test_framing.py`, `test_ai_gateway.py` |
| T6 | Fuite de données personnelles vers l'IA (I) | `contains_personal_data` explicite, palier gratuit exclu, politique `allowed` / `local_only` / `never`, transferts documentés et testés | `test_catalogues.py`, `test_ai_gateway.py` |
| T7 | Exécution de code via LaTeX (E) | Liste noire de commandes, `openin_any=p`, env minimal, rlimits, `unshare --net`, taille de sortie bornée | `test_latex_safety.py`, `test_latex_compiler.py` |
| T8 | Fichier importé piégé (T, D) | 5 Mo, contenu réel, 30 pages, ratio de compression, noms générés (UUID), anti-traversée | `tests/unit/candidate_profile`, `test_document_storage.py` |
| T9 | Secret divulgué par logs, réponses ou dépôt (I) | `SecretStr`, masquage des logs, indice `…abcd` en UI, `.env` ignoré et non versionné | `test_masking.py`, `test_observability.py`, `test_local_mode.py` |
| T10 | Lecture ou modification des données d'un autre propriétaire (I, T) | `owner_id` partout, 404 (jamais 403) pour l'inexistant, effacement et export limités au propriétaire | `test_owner_isolation.py`, `test_api_privacy.py` |
| T11 | Perte de données (D) | Sauvegarde + somme de contrôle, restauration vérifiée, reprise des tâches orphelines | `test_resilience.py`, `test_job_queue.py` |
| T12 | Candidature envoyée sans l'accord de l'utilisateur (R) | Aucun envoi automatique : l'application ouvre le lien, l'utilisateur confirme | ADR-0015, tests CRM |
| T13 | Faits inventés dans un CV ou une lettre (T) | Contrôle structurel des faits, garde-fou de reformulation, chiffres sans source signalés | `test_fact_checker.py`, `test_resume_rewrite.py` |
| T14 | Répudiation : actions sans trace (R) | Journal d'accès structuré avec identifiant de corrélation, journal IA, historique de candidature immuable | `test_observability.py` |

## 4. Risques résiduels assumés

- **Pas d'authentification** : quiconque accède à la machine accède aux données. Condition :
  rester local. L'authentification (TASK-018-35/36) est **différée** (ADR-0008) et obligatoire
  avant tout accès distant (voir `LOCAL_NO_AUTH_NOTICE.md`).
- **Rebinding DNS** entre la résolution et la connexion (SSRF) : redirections jamais suivies,
  hôtes des connecteurs figés ; non éliminé pour les pages publiques d'entreprises.
- **Limiteur de débit et mesures en mémoire**, locaux au processus : à déplacer dans un stockage
  partagé en cas de déploiement multi-processus.
- **Corps sans `Content-Length`** (transfert fragmenté) : seul l'import de fichier est borné à la
  lecture ; les autres routes sont bornées par les schémas.
- **Sauvegardes non chiffrées** : à stocker sur un support protégé.
- **Aucune analyse de dépendances automatisée** dans cet EPIC : voir l'état de Dependabot dans le
  dépôt.
