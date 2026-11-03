# ADR-0005 — Stratégie IA, API payante et plafonds

- **Statut :** Accepté (fournisseur à décider)
- **Date :** 2026-11-03

## Contexte

L'IA est le principal poste de coût. Le produit doit rester utile sans IA et ne jamais dépasser le budget fixé.

## Décision

1. **API payante** comme fournisseur principal, derrière une interface `AIProvider` indépendante du fournisseur.
2. **Le fournisseur n'est pas encore choisi.** Aucun code ne doit dépendre d'un fournisseur précis avant cette décision (ADR dédié à venir).
3. **Plafond obligatoire** : aucun appel payant tant qu'un plafond n'est pas défini. Contrôle du coût estimé avant chaque appel, refus si dépassement, blocage jamais silencieux.
4. **Niveaux** : niveau 0 sans IA (règles, SQL), niveau 1 modèle économique (extraction, classification, résumé), niveau 2 modèle plus performant (CV, lettres, analyse approfondie, entretiens).
5. Cache par empreinte du contenu + version du prompt + modèle ; sorties JSON validées ; contextes minimaux ; jamais le CV complet par défaut.
6. Modèle local : option ultérieure, même interface.

## Plafonds proposés (valeurs initiales, à ajuster)

| Paramètre | Valeur proposée |
|---|---|
| Budget mensuel | 10 € |
| Budget journalier | 1 € |
| Limite par opération de niveau 1 | 0,02 € |
| Limite par opération de niveau 2 | 0,30 € |
| Seuils d'alerte | 50 %, 80 %, 100 % |
| Comportement à 100 % | blocage des appels non essentiels, explication affichée |
| Mode par défaut | économique |

Ces valeurs sont **indicatives** : elles seront calibrées avec les tarifs réels une fois le fournisseur choisi. Elles ne peuvent être augmentées que par l'utilisateur.

## Conséquences

- Le suivi des coûts (`AIUsage`) et le contrôle de budget sont des fondations, à construire avant tout appel réel.
- Un test automatisé doit prouver qu'aucun appel ne dépasse le plafond.
