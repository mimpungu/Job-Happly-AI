# Coûts et plafonds de l'IA

L'application fonctionne **sans IA** (règles, SQL, scores déterministes). L'IA est une aide optionnelle, toujours encadrée.

## Principes
- **Niveau 0** : aucune IA. **Niveau 1** : modèle économique (extraction, classification, résumé). **Niveau 2** : modèle plus performant (CV, lettres, analyse approfondie).
- **Hybride** (ADR-0011) : le modèle local d'abord (gratuit, données sur la machine), l'API payante en renfort.
- **Aucun appel payant** sans : un fournisseur API configuré, un plafond **journalier et mensuel** défini par l'utilisateur, et son **consentement** à l'envoi de données.
- Le **coût maximal** est estimé avant chaque appel (entrée estimée prudemment + sortie à la limite de tokens). L'appel est refusé s'il ferait dépasser le plafond journalier, mensuel ou la limite par opération. Un **plafond journalier par fournisseur** peut s'ajouter aux plafonds globaux. Les **alertes** (seuils 50/80/100 % par défaut) sont calculées à partir de la dépense réelle et affichées dans le Centre IA tant qu'elles sont franchies ; à 100 %, les appels payants sont bloqués avec une explication. Jamais d'augmentation automatique d'un plafond.
- Deux devises différentes ne sont jamais converties : l'appel est refusé.

## Valeurs par défaut (ADR-0005, à recalibrer avec les tarifs réels)
| Paramètre | Valeur |
|---|---|
| Limite par opération, niveau 1 | 0,02 € |
| Limite par opération, niveau 2 | 0,30 € |
| Seuils d'alerte | 50 %, 80 %, 100 % |
| Plafonds journalier / mensuel | **non définis** (donc aucun appel payant) ; propositions : 1 € / 10 € |
| Durée du cache | 30 jours |

## Ce qui est journalisé (`ai_usages`)
Fournisseur, modèle, tâche, niveau, tokens d'entrée et de sortie, coût estimé et réel, durée, résultat (`success`, `cache_hit`, `blocked_budget`, `error`, `invalid_output`). Jamais le contenu des requêtes.

## Cache
Clé = empreinte (tâche, version du prompt, modèle, instructions, contenu, schéma). Une réponse invalide n'est jamais mise en cache. Une réponse expirée est remplacée.

## Fournisseurs de démarrage (ADR-0012)
| Fournisseur | Rôle | Remarques |
|---|---|---|
| Ollama `gemma4:e4b` / `gemma4:12b` | Local, gratuit | M1 16 Go ; rien ne quitte la machine ; modèle à installer (`ollama pull`) |
| Gemini `gemini-3.1-flash-lite` (niv. 1), `gemini-3-flash-preview` (niv. 2) | API | Tarifs USD relevés le 2026-11-04 ; `gemini-2.5-flash-lite` est retiré aux nouveaux comptes (404) ; réflexion réglée sur « minimal » ; **palier gratuit : contenus réutilisables et relus par des humains -> textes publics seulement** |

Ordre de grandeur (tarifs payants, USD) : résumer une offre ≈ 0,0008 $ avec `gemini-3.1-flash-lite` ; une lettre ou un CV ≈ 0,01 $ avec `gemini-3-flash-preview`. Les tarifs augmentent pour plusieurs modèles au 1er décembre 2026 et au 1er janvier 2027.

## Banc d'essai
`PYTHONPATH=backend uv run --project backend python backend/tools/ai_benchmark.py --n 20` compare les modèles sur de vraies offres publiques collectées (passage par la passerelle : journal, plafonds, cache). Mesures automatiques : JSON conforme, **ancrage** (part des compétences réellement présentes dans le texte, un ancrage bas révèle des inventions), vitesse, tokens, coût au tarif payant. La qualité d'écriture se juge en relisant la comparaison côte à côte. `--gemini` envoie les textes d'offres (publics) à Google et exige l'accord de l'utilisateur.

## Limites connues
- Les tests automatiques utilisent de faux fournisseurs (aucun appel réseau réel) ; les adaptateurs Gemini et Ollama sont testés sur transport simulé, et Gemini a été exercé en réel par le banc d'essai.
- Plafond par fournisseur : non fait. Les franchissements de seuil sont signalés par la passerelle ; l'envoi en notification dépend du réglage `notify_ai_budget_alerts` (EPIC 015).
- Politique de confidentialité (`allowed`, `local_only`, `never`) : voir `docs/security/PRIVACY.md` ; catalogue des données envoyées : `GET /api/v1/privacy/ai-transfers`.
- Un délai dépassé n'est pas compté comme dépensé.
