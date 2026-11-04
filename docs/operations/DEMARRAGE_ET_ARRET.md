# Démarrer et arrêter Happly AI

Rien ne démarre tout seul et rien ne doit tourner en permanence. Tout se lance à la demande et
s'arrête avec une commande. Toutes les commandes se lancent **depuis la racine du dépôt**
(`/Users/deomimpungu/Development/Job-Happly-AI`). Tout reste sur votre machine (`127.0.0.1`).

## Ce qui tourne, et ce que cela consomme

| Élément | Rôle | Obligatoire | Mémoire approximative | Se lance avec |
|---|---|---|---|---|
| **Docker Desktop** | Moteur qui fait tourner les services ci-dessous | Oui (pour l'application) | machine virtuelle de 7,7 Go **réservée** (mesuré) | Ouvrir l'application Docker |
| PostgreSQL (Docker) | Base de données | Oui | ~30 Mo (mesuré) | `start.sh` |
| API (Docker) | Le serveur de l'application | Oui | ~90 Mo (mesuré) | `start.sh` |
| Web (Docker) | L'interface dans le navigateur | Oui | ~40 Mo (mesuré) | `start.sh` |
| Base de **test** (Docker, projet `happly-ai-test`) | Tests automatiques seulement | Non | ~35 Mo | `test.sh` la démarre, `stop.sh` l'arrête |
| **Ollama** (IA locale) | Modèle `gemma4:e4b` sur votre Mac | **Non** (facultatif) | **~9,4 Go** (mesuré) | `ia-start.sh` |
| Gemini (IA en ligne) | Aucun processus : un simple appel réseau | Non | 0 | Clé dans `.env` |

L'application fonctionne **entièrement sans IA** (collecte, recherche, score, analyse par règles).
Sur un Mac de 16 Go, évitez de lancer Ollama en même temps que beaucoup d'autres applications :
la mémoire sature et tout ralentit.

> **Attention aux autres projets Docker.** Docker Desktop est partagé : si d'autres projets y
> tournent (par exemple `deuswell-backend` / Supabase, ~2 Go), ils consomment la même mémoire.
> Happly ne les arrête jamais, car ils ne lui appartiennent pas. Pour les arrêter, faites-le
> depuis leur propre projet, ou quittez Docker Desktop (cela arrête tout).

## Démarrer

### 1. L'application (Docker)
1. Ouvrez **Docker Desktop** et attendez que l'icône indique « running ».
2. Lancez :
   ```bash
   ./infrastructure/scripts/start.sh
   ```
   La première fois (ou après une mise à jour du code), l'image est reconstruite : comptez quelques
   minutes. Le script attend que les services soient prêts.
3. **Après la toute première installation ou une mise à jour** qui ajoute une migration :
   ```bash
   ./infrastructure/scripts/migrate.sh
   ```
4. Ouvrez http://127.0.0.1:3000 (interface). L'API répond sur http://127.0.0.1:8000/api/v1/health.

### 2. L'IA locale (facultatif)
```bash
./infrastructure/scripts/ia-start.sh
```
Le script lance Ollama (lié à `127.0.0.1` uniquement) et affiche les modèles installés. Il faut aussi
que `.env` contienne `HAPPLY_OLLAMA_ENABLED=true`, puis `./infrastructure/scripts/stop.sh` +
`start.sh` si vous venez de le modifier.

### 3. L'IA en ligne Gemini (facultatif)
Dans `.env`, renseignez `HAPPLY_GEMINI_API_KEY=` (clé Google AI Studio), puis redémarrez
l'application (étape 1). Ne collez jamais la clé ailleurs que dans `.env`.
Palier gratuit : Google peut réutiliser et relire les textes envoyés, donc uniquement des offres
publiques, jamais votre CV (l'application l'impose). Plafonds et accord se règlent dans **Centre IA**.

## Arrêter

Dans cet ordre (le plus gourmand d'abord) :

```bash
./infrastructure/scripts/ia-stop.sh   # décharge le modèle de la mémoire puis arrête Ollama
./infrastructure/scripts/stop.sh      # arrête l'application et la base de test (données conservées)
```

Pour libérer aussi la mémoire de Docker : quittez **Docker Desktop** (menu de la barre de menus →
« Quit Docker Desktop »).

> `stop.sh` supprime les conteneurs mais **jamais vos données** (le volume `postgres_data` reste).
> Ne lancez pas `docker compose down -v` : l'option `-v` efface la base.

## Vérifier ce qui tourne

```bash
docker compose ps                 # services de l'application (vide = arrêtés)
curl -s http://127.0.0.1:11434/api/version || echo "Ollama arrêté"
ollama ps                         # modèles actuellement chargés en mémoire
```

## Docker : commandes utiles

| Besoin | Commande |
|---|---|
| Voir les journaux de l'API | `docker compose logs -f api` (Ctrl+C pour quitter) |
| Redémarrer l'API après un changement de `.env` | `docker compose up -d api` |
| Reconstruire après une mise à jour du code | `./infrastructure/scripts/build.sh` puis `start.sh` |
| Sauvegarder / restaurer la base | voir `docs/operations/BACKUP_RESTORE.md` |
| Libérer de la place disque (images inutilisées) | `docker image prune` |

Les ports sont publiés **uniquement sur `127.0.0.1`** : 3000 (interface), 8000 (API), 5432 (base).
Il n'y a pas d'authentification (ADR-0008) : ne les exposez jamais sur un réseau.

## Modèles locaux

| Action | Commande |
|---|---|
| Lister | `ollama list` |
| Supprimer un modèle inutile (ex. le 12B, jugé trop lent) | `ollama rm gemma4:12b` |
| Réinstaller | `ollama pull gemma4:e4b` |

Modèle par défaut du niveau 1 : `gemma4:e4b` (réglable par `HAPPLY_OLLAMA_MODEL_LEVEL1`).

## Dépannage

| Symptôme | Cause probable | Que faire |
|---|---|---|
| « Cannot connect to the Docker daemon » | Docker Desktop fermé | Ouvrez-le, attendez, relancez `start.sh` |
| L'écran affiche une erreur 503 ou « Base de données non configurée » | Services pas prêts ou migration manquante | `docker compose ps`, puis `migrate.sh` |
| « Ollama est injoignable » dans le Centre IA | Ollama arrêté (il s'arrête aussi si le Mac manque de mémoire) | `ia-start.sh` |
| « Modèle local absent : ollama pull … » | Modèle non installé | La commande indiquée dans le message |
| « Quota Gemini atteint » | Limite du palier gratuit | Attendre une minute, ou passer le compte en facturation (plafonds obligatoires) |
| « Gemini a refusé la clé d'API » | Clé absente, fausse ou révoquée | Vérifier `HAPPLY_GEMINI_API_KEY` dans `.env`, `docker compose up -d api` |
| Tout est lent, ventilateur au maximum | Mémoire saturée (Ollama + Docker + navigateur) | `ia-stop.sh`, fermer des applications |
| « Another next dev server is already running » (tests E2E) | Ancien serveur de développement | Arrêter ce processus (`kill` du PID indiqué), relancer |
| `Port is already allocated` | Un autre programme utilise 3000, 8000 ou 5432 | Le fermer, ou `stop.sh` puis `start.sh` |

## Ce qui n'est jamais lancé automatiquement
Aucun service au démarrage du Mac, aucune tâche planifiée, aucun redémarrage automatique d'Ollama.
La collecte d'offres et le calcul des scores sont des **boutons** de l'interface. (Les
conteneurs Docker ont `restart: unless-stopped` : ils ne repartent qu'avec Docker Desktop, et pas
après `stop.sh`.)
