# Contraintes du projet (TASK-001-02)

Date : 2026-11-03

| Domaine | Contrainte | Décision |
|---|---|---|
| Environnement | Exécution locale d'abord ; partage ultérieur | Local-first, voir ADR-0008 |
| Systèmes cibles | macOS Apple Silicon (développement) ; Docker pour la portabilité | Docker Compose, ports liés à `127.0.0.1` |
| Accès Internet | Requis pour les sources d'offres et l'API IA ; l'application doit rester utilisable si une source ou l'IA est indisponible | Dégradation maîtrisée, jamais de blocage global |
| Authentification | Aucune au départ, intégrée plus tard | ADR-0008 ; `owner_id` dès le départ |
| Fournisseur IA | API payante, fournisseur **non choisi** | ADR-0005 ; aucune dépendance à un fournisseur précis |
| Budget IA | Plafond obligatoire | 10 €/mois, 1 €/jour proposés, à calibrer |
| Sources d'offres | Gratuites et publiques uniquement | ADR-0006 ; aucun contournement de protections |
| Finances | Aucune dépense ni service payant sans accord explicite | Règle de `CLAUDE.md` |
| Confidentialité | Le CV reste local ; envoi minimal et consenti vers l'IA | Minimisation, consentement affiché |
| Qualité attendue | Système robuste et durable, pas un prototype jetable | Tests, sécurité et documentation dès le début |
| Version de Python | 3.14 installé, jugé trop récent | 3.13 proposé via uv (ADR-0002) |

## Points ouverts

1. Choix du fournisseur d'IA payante (ADR à venir).
2. Calibrage des plafonds avec les tarifs réels.
3. Première source française gratuite (TASK-006-15) : à choisir après vérification des conditions d'utilisation.
4. Liste des entreprises ciblées pour les sites carrières (TASK-006-21).
