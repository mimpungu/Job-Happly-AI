# Guide utilisateur

Happly AI vous aide à chercher un emploi **sans jamais rien faire à votre place** : elle ne postule pas, n'envoie aucun message à un recruteur et n'invente aucune information sur vous. Tout reste sur votre ordinateur.

## 1. Votre profil maître (Espace CV → Profil maître)

C'est la source de vérité : tous vos CV et lettres en sont tirés.

1. **Importer un CV** (PDF, DOCX ou TXT, 5 Mo maximum) : il est lu localement, rien n'est conservé du fichier. Ou **saisir à la main**.
2. **Relire chaque information** : les éléments lus automatiquement restent « à confirmer » tant que vous ne les avez pas confirmés (onglets Expériences, Formations, Compétences, Langues).
3. Une langue sans niveau reconnu demande un choix explicite : un niveau n'est jamais deviné.
4. **Enregistrer**, puis **Valider le profil**. Une version validée n'est plus modifiable : « Créer une nouvelle version » la fait évoluer sans perdre l'ancienne.

Tant que le profil n'est pas validé, rien n'est généré (score, CV, lettre, entretien).

## 2. Trouver des offres (Recherche d'emploi)

- **Ajouter une offre** : collez l'adresse et le texte d'une offre lue dans votre navigateur. Aucune requête n'est envoyée au site d'origine.
- **Suivre des entreprises** (Paramètres) : les offres publiques de leurs sites carrières (Greenhouse, Lever) sont collectées à la demande.
- Filtrez par texte, entreprise, ville, pays, contrat, télétravail, salaire, date et **compatibilité minimale**. Chaque offre affiche un score expliqué ; un critère sans donnée est « non évalué », jamais compté comme zéro.
- Sauvegardez des recherches pour les relancer.

## 3. Générer un CV (Espace CV → CV générés)

Choisissez une offre (ou « CV général »), un style, une longueur. Le CV n'utilise **que** des faits de votre profil validé : un contrôle structurel refuse tout fait absent du profil. L'audit ATS indique le score, le nombre de pages et les mots-clés de l'offre que **vous n'avez pas** (ils ne sont jamais ajoutés).

- **Reformulation des réalisations** (facultative) : « modèle local » (rien ne quitte votre machine) ou « IA ». Une reformulation qui ajouterait un chiffre, un nom ou une technologie est écartée ; si l'IA est indisponible, vos réalisations d'origine sont conservées et le message l'indique.
- Téléchargez le **PDF** ou le **source LaTeX**.

## 4. Générer une lettre (Lettres de motivation)

Choisissez une offre, la langue, un destinataire et, si vous le souhaitez, **votre propre texte de motivation** : il est repris tel quel, jamais réécrit. Une page est affichée à la génération pour **relire** la lettre ; ensuite le PDF fait foi. L'audit signale cohérence avec le CV, longueur, formulations artificielles, fautes probables.

## 5. Suivre ses candidatures (Candidatures)

- **Suivre cette candidature** depuis une offre, vue tableau ou Kanban, historique complet, contacts, notes.
- **J'ai envoyé ma candidature** : vous confirmez un envoi fait **vous-même** sur le site de l'employeur ; l'application n'envoie jamais rien.
- Associez les versions exactes de votre CV et de votre lettre, planifiez une relance (candidature envoyée uniquement).

## 6. Préparer un entretien (Préparation d'entretien)

Choisissez une candidature, puis :

- **Préparation** : questions RH, comportementales et techniques adaptées au poste, présentation personnelle, expériences à mettre en avant, trames de réponse (Situation, Actions, Résultat) bâties sur votre vrai parcours, questions à poser au recruteur. Les résultats chiffrés et votre motivation sont **à compléter par vous**. Les compétences demandées que vous n'avez pas sont signalées, jamais présentées comme acquises.
- **Simulation** : répondez aux questions, obtenez un retour chiffré sur des critères vérifiables ; les chiffres absents de votre parcours sont signalés « à vérifier ». L'historique est conservé.
- **Entretiens** : fiche (date avec fuseau, interlocuteurs, notes, retour), brouillon de relance de remerciement (à copier : rien n'est envoyé).

Sans IA par défaut. « Modèle local » ou « IA » s'activent seulement quand vous le choisissez.

## 7. L'IA et ses coûts (Centre IA)

- L'IA est **facultative**. Aucun appel payant n'est possible sans : un fournisseur configuré, un **plafond journalier et mensuel** défini par vous, et votre **consentement**.
- Le coût maximal est estimé avant chaque appel ; un appel qui ferait dépasser un plafond est refusé. L'application n'augmente jamais un plafond d'elle-même.
- Le palier gratuit d'un fournisseur peut réutiliser les textes : il ne reçoit jamais vos données personnelles.

## 8. Vos données (Paramètres → Confidentialité)

- **Voir** ce qui est stocké, par catégorie.
- **Exporter** (ZIP : un JSON par table + vos PDF).
- **Supprimer** une catégorie ou tout, après avoir saisi `SUPPRIMER` : c'est définitif.
- **Politique d'envoi à l'IA** : autorisé selon vos réglages, modèle local seulement, ou jamais.
- **Conservation** : durées de chaque donnée et purge des données expirées.

## 9. Santé et sauvegarde

Paramètres → Santé de l'application : état de la base, du stockage, de LaTeX, de l'IA, des sources et des tâches. **Sauvegardez régulièrement** (`docs/operations/BACKUP_RESTORE.md`) et gardez une copie hors de votre ordinateur.

## Limites à connaître

- Pas de compte : toute personne qui a accès à votre ordinateur a accès à vos données. N'exposez jamais l'application sur un réseau.
- Les sources d'offres réelles sont limitées (voir `docs/DATA_SOURCES.md`) ; l'ajout manuel fonctionne toujours.
- La lettre générée n'est relisible à l'écran qu'au moment de sa génération ; le PDF est conservé.
