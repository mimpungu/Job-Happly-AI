# Coûts et plafonds de l'IA

L'application fonctionne **sans IA** (règles, SQL, scores déterministes). L'IA est une aide optionnelle, toujours encadrée.

## Principes
- **Niveau 0** : aucune IA. **Niveau 1** : modèle économique (extraction, classification, résumé). **Niveau 2** : modèle plus performant (CV, lettres, analyse approfondie).
- **Hybride** (ADR-0011) : le modèle local d'abord (gratuit, données sur la machine), l'API payante en renfort.
- **Aucun appel payant** sans : un fournisseur API configuré, un plafond **journalier et mensuel** défini par l'utilisateur, et son **consentement** à l'envoi de données.
- Le **coût maximal** est estimé avant chaque appel (entrée estimée prudemment + sortie à la limite de tokens). L'appel est refusé s'il ferait dépasser le plafond journalier, mensuel ou la limite par opération. Jamais d'augmentation automatique d'un plafond.
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

## Limites connues
- Aucun fournisseur concret n'est branché : tous les tests utilisent de faux fournisseurs.
- Plafond par fournisseur et alertes envoyées en notification : non faits.
- Un délai dépassé n'est pas compté comme dépensé.
