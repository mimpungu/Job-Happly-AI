# ADR-0012 — Fournisseurs IA de démarrage : Gemini (AI Studio) et Ollama

- **Statut :** Provisoire — pour valider la plateforme ; le choix définitif suivra une mesure sur nos tâches.
- **Date :** 2026-11-04
- **Complète :** ADR-0005, ADR-0011

## Contexte
La plateforme IA (passerelle, plafonds, cache, journal) est prête mais n'a aucun fournisseur réel. Il faut la valider de bout en bout, à moindre coût et sans exposer de données personnelles.

## Décision
1. **API payante, pour démarrer : Gemini via Google AI Studio.** Modèles par défaut : `gemini-2.5-flash-lite` (niveau 1) et `gemini-3-flash-preview` (niveau 2), réglables par variables d'environnement.
2. **Local : Ollama** (boucle locale uniquement), modèles `gemma4:e4b` (niveau 1) et `gemma4:12b` (niveau 2), sur un MacBook M1 16 Go.
3. **Palier gratuit Gemini = contenus réutilisables et relisibles par des humains** (conditions Google lues le 2026-11-04). Le fournisseur déclare donc `uses_data_for_training` ; toute requête marquée `contains_personal_data` l'exclut du routage. Palier par défaut : `free` (hypothèse la plus prudente) ; `paid` seulement si l'utilisateur lie un compte de facturation.
4. **Les tarifs sont en USD** : les plafonds doivent être définis en USD pour Gemini (aucune conversion).
5. Le choix définitif (fournisseur payant, modèle local) n'est pas fait ici : il suivra un banc d'essai comparant qualité, vitesse et coût sur des offres anonymisées.

## Critères du choix définitif
Qualité du JSON structuré et du français, coût par tâche, latence, taille en mémoire (16 Go), confidentialité (palier payant ou local pour tout contenu personnel), stabilité des modèles (dépréciations et hausses de prix annoncées).

## Conséquences
- Aucun code métier ne dépend de Gemini ni d'Ollama : seuls deux adaptateurs les connaissent.
- Les formats de requête sont écrits d'après la documentation connue et à confirmer au premier appel réel.
- Les tarifs sont en dur dans l'adaptateur Gemini avec leur date de relevé : à revérifier avant tout usage payant.
