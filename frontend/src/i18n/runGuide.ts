/**
 * "Running Kwak Finance": install, start, stop, update and fix the Docker stack. Keep it in
 * step with docker-compose.yml, the Makefile and the `kwak` CLI.
 */

/** A paragraph, optionally followed by commands to type in a terminal. */
export type GuideStep = { text: string; commands?: string[] };
export type GuideSection = { id: string; title: string; steps: GuideStep[] };

// Commands are the same in both languages.
const CLONE = ["git clone https://github.com/gwils28/kwak-finance.git", "cd kwak-finance"];
const ENV = ["cp .env.example .env"];
const KEY = ["cd backend && uv run kwak generate-key && cd .."];
const BACKUP_DIR = ["mkdir -p data/backups"];
const UP = ["make up"];
const MIGRATE = ["docker compose exec api kwak migrate"];
const OWNER = [
  'docker compose exec -it api kwak create-owner --household "Home" --email you@example.com --name "You"',
];
const PS = ["docker compose ps"];
const DOWN = ["make down"];
const PAUSE = ["docker compose stop", "docker compose start"];
const ENABLE_DOCKER = ["sudo systemctl enable --now docker"];
const UPDATE = ["git pull", "make up", "docker compose exec api kwak migrate"];
const LOGS = ["docker compose logs --tail 50 api", "make logs"];
const RESTART = ["docker compose restart api"];
const BACKUPS = ["docker compose logs backup", "ls -lh data/backups"];
const DANGER = [
  "docker compose down -v",
  "docker volume rm kwak_pgdata",
  "docker system prune --volumes",
];

export const runGuideEn = {
  footerLink: "How to run the app",
  title: "Running Kwak Finance",
  intro:
    "Kwak Finance runs on your own computer, in Docker. This page explains how to install it once, start and stop it, update it and get out of trouble. Commands are typed in a terminal, from the project folder (kwak-finance).",
  backToApp: "Back to the app",
  copy: "Copy",
  copied: "Copied",
  contents: "On this page",
  sections: [
    {
      id: "overview",
      title: "What runs where",
      steps: [
        {
          text: "The app is made of four Docker containers, grouped under the name kwak: db (PostgreSQL, the database), api (the server), web (Caddy, which serves the pages on https://localhost:8443) and backup (a copy of the database every night at 3:00).",
        },
        {
          text: "Your data is not inside the containers but in a Docker volume named kwak_pgdata. Stopping, removing or rebuilding the containers keeps it. Backups land in data/backups/.",
        },
      ],
    },
    {
      id: "install",
      title: "First installation (once)",
      steps: [
        {
          text: "1. Install Docker with Compose, git, make and uv. Check that Docker answers:",
          commands: ["docker compose version"],
        },
        { text: "2. Get the code:", commands: CLONE },
        {
          text: "3. Create the settings file, then open .env in an editor: set KWAK_ENV=prod and choose a database password.",
          commands: ENV,
        },
        {
          text: "4. Generate the secret key and paste it into .env as KWAK_SECRET_KEY. It encrypts the two-step verification secrets: keep a copy outside this computer.",
          commands: KEY,
        },
        {
          text: "5. Create the backup folder before the first start, otherwise Docker creates it owned by root:",
          commands: BACKUP_DIR,
        },
        {
          text: "6. Build and start everything (the first build takes a few minutes):",
          commands: UP,
        },
        { text: "7. Create the database tables:", commands: MIGRATE },
        {
          text: "8. Create your household and your account (it asks for a password of at least 12 characters):",
          commands: OWNER,
        },
        {
          text: "9. Open https://localhost:8443. The browser warns about the certificate the first time: it is a local certificate made by Caddy, accept it (Advanced → Continue). Sign in, scan the QR code with an authenticator app and store the recovery codes.",
        },
      ],
    },
    {
      id: "start-stop",
      title: "Start and stop",
      steps: [
        {
          text: "Is it running? Four lines with the status running (Up) mean yes; db also says healthy. An empty list means it is off.",
          commands: PS,
        },
        {
          text: "Start it, then wait about ten seconds and open https://localhost:8443. make up also rebuilds what changed, so it is the only start command you need.",
          commands: UP,
        },
        {
          text: "Stop it. The containers are removed but your data stays in the kwak_pgdata volume: the next make up finds everything again.",
          commands: DOWN,
        },
        {
          text: "To pause without removing the containers, use stop, then start to resume:",
          commands: PAUSE,
        },
      ],
    },
    {
      id: "always-on",
      title: "Leave it on or turn it off?",
      steps: [
        {
          text: "Leave it on. It uses little memory and almost no processor when nobody uses it, and the nightly backup only runs while it is on.",
        },
        {
          text: "After a computer restart, the containers start again on their own (restart: unless-stopped), as long as Docker itself starts at boot. On Linux, enable it once:",
          commands: ENABLE_DOCKER,
        },
        {
          text: "If you stopped it yourself (make down or docker compose stop), it stays off until you start it again, even after a restart.",
        },
        {
          text: "Turn it off when you need the resources or will be away for a long time. When you start it again, the backup service makes a backup at once if the last one is more than a day old.",
        },
      ],
    },
    {
      id: "update",
      title: "After an update",
      steps: [
        {
          text: "Get the new version, rebuild and apply the database changes (migrate does nothing when there are none), then reload the page with Ctrl+Shift+R:",
          commands: UPDATE,
        },
      ],
    },
    {
      id: "trouble",
      title: "When something goes wrong",
      steps: [
        {
          text: "The page does not open: check the containers with docker compose ps. If the terminal says “Cannot connect to the Docker daemon”, Docker itself is off: start it (sudo systemctl start docker on Linux, or open Docker Desktop), then make up.",
          commands: PS,
        },
        {
          text: "See what happened: the last lines of a service (api, db, web or backup), or every service live. Leave the live view with Ctrl+C: the app keeps running.",
          commands: LOGS,
        },
        { text: "Restart one service only:", commands: RESTART },
        {
          text: "An error right after an update (for example “column does not exist”): the database changes were not applied. Run:",
          commands: MIGRATE,
        },
        {
          text: "“port is already allocated” at start-up: another program uses port 8080 or 8443. Stop it, or change the ports in docker-compose.yml.",
        },
        { text: "Check the backups:", commands: BACKUPS },
      ],
    },
    {
      id: "danger",
      title: "Never type these",
      steps: [
        {
          text: "These commands delete the database volume, that is all your data. Only a backup could bring it back (see docs/OPERATIONS.md for restoring).",
          commands: DANGER,
        },
        { text: "Never share or commit the .env file: it holds your passwords and secret key." },
      ],
    },
  ] as GuideSection[],
};

export const runGuideFr: typeof runGuideEn = {
  footerLink: "Lancer et arrêter l'application",
  title: "Faire tourner Kwak Finance",
  intro:
    "Kwak Finance tourne sur votre propre ordinateur, dans Docker. Cette page explique comment l'installer une fois, la démarrer, l'arrêter, la mettre à jour et se dépanner. Les commandes se tapent dans un terminal, depuis le dossier du projet (kwak-finance).",
  backToApp: "Retour à l'application",
  copy: "Copier",
  copied: "Copié",
  contents: "Sur cette page",
  sections: [
    {
      id: "overview",
      title: "Qu'est-ce qui tourne, et où",
      steps: [
        {
          text: "L'application se compose de quatre conteneurs Docker, regroupés sous le nom kwak : db (PostgreSQL, la base de données), api (le serveur), web (Caddy, qui sert les pages sur https://localhost:8443) et backup (une copie de la base chaque nuit à 3 h).",
        },
        {
          text: "Vos données ne sont pas dans les conteneurs mais dans un volume Docker nommé kwak_pgdata. Arrêter, supprimer ou reconstruire les conteneurs les conserve. Les sauvegardes arrivent dans data/backups/.",
        },
      ],
    },
    {
      id: "install",
      title: "Première installation (une seule fois)",
      steps: [
        {
          text: "1. Installez Docker avec Compose, git, make et uv. Vérifiez que Docker répond :",
          commands: ["docker compose version"],
        },
        { text: "2. Récupérez le code :", commands: CLONE },
        {
          text: "3. Créez le fichier de réglages, puis ouvrez .env dans un éditeur : mettez KWAK_ENV=prod et choisissez un mot de passe pour la base.",
          commands: ENV,
        },
        {
          text: "4. Générez la clé secrète et collez-la dans .env en face de KWAK_SECRET_KEY. Elle chiffre les secrets de double authentification : gardez-en une copie hors de cet ordinateur.",
          commands: KEY,
        },
        {
          text: "5. Créez le dossier des sauvegardes avant le premier démarrage, sinon Docker le crée au nom de root :",
          commands: BACKUP_DIR,
        },
        {
          text: "6. Construisez et démarrez le tout (la première construction prend quelques minutes) :",
          commands: UP,
        },
        { text: "7. Créez les tables de la base :", commands: MIGRATE },
        {
          text: "8. Créez votre foyer et votre compte (un mot de passe d'au moins 12 caractères est demandé) :",
          commands: OWNER,
        },
        {
          text: "9. Ouvrez https://localhost:8443. La première fois, le navigateur signale un problème de certificat : c'est un certificat local créé par Caddy, acceptez-le (Paramètres avancés → Continuer). Connectez-vous, scannez le QR code avec une application d'authentification et rangez les codes de secours.",
        },
      ],
    },
    {
      id: "start-stop",
      title: "Démarrer et arrêter",
      steps: [
        {
          text: "Est-ce que ça tourne ? Quatre lignes à l'état running (Up) veulent dire oui ; db indique aussi healthy. Une liste vide veut dire que c'est éteint.",
          commands: PS,
        },
        {
          text: "Démarrer, puis attendre une dizaine de secondes et ouvrir https://localhost:8443. make up reconstruit aussi ce qui a changé : c'est la seule commande de démarrage à retenir.",
          commands: UP,
        },
        {
          text: "Arrêter. Les conteneurs sont supprimés mais vos données restent dans le volume kwak_pgdata : le prochain make up retrouve tout.",
          commands: DOWN,
        },
        {
          text: "Pour mettre en pause sans supprimer les conteneurs, utilisez stop, puis start pour reprendre :",
          commands: PAUSE,
        },
      ],
    },
    {
      id: "always-on",
      title: "Laisser allumé ou éteindre ?",
      steps: [
        {
          text: "Laissez allumé. L'application prend peu de mémoire et quasiment pas de processeur quand personne ne s'en sert, et la sauvegarde de la nuit ne se fait que si elle tourne.",
        },
        {
          text: "Après un redémarrage de l'ordinateur, les conteneurs repartent tout seuls (restart: unless-stopped), à condition que Docker lui-même démarre au boot. Sous Linux, activez-le une fois :",
          commands: ENABLE_DOCKER,
        },
        {
          text: "Si vous l'avez arrêtée vous-même (make down ou docker compose stop), elle reste éteinte jusqu'à ce que vous la redémarriez, même après un redémarrage.",
        },
        {
          text: "Éteignez-la si vous avez besoin des ressources ou partez longtemps. Au redémarrage, le service de sauvegarde en fait une tout de suite si la dernière a plus d'un jour.",
        },
      ],
    },
    {
      id: "update",
      title: "Après une mise à jour",
      steps: [
        {
          text: "Récupérez la nouvelle version, reconstruisez et appliquez les changements de la base (migrate ne fait rien s'il n'y en a pas), puis rechargez la page avec Ctrl+Maj+R :",
          commands: UPDATE,
        },
      ],
    },
    {
      id: "trouble",
      title: "En cas de problème",
      steps: [
        {
          text: "La page ne s'ouvre pas : vérifiez les conteneurs avec docker compose ps. Si le terminal répond « Cannot connect to the Docker daemon », c'est Docker lui-même qui est éteint : démarrez-le (sudo systemctl start docker sous Linux, ou ouvrez Docker Desktop), puis make up.",
          commands: PS,
        },
        {
          text: "Voir ce qui s'est passé : les dernières lignes d'un service (api, db, web ou backup), ou tous les services en direct. Quittez le direct avec Ctrl+C : l'application continue de tourner.",
          commands: LOGS,
        },
        { text: "Redémarrer un seul service :", commands: RESTART },
        {
          text: "Une erreur juste après une mise à jour (par exemple « column does not exist ») : les changements de la base n'ont pas été appliqués. Lancez :",
          commands: MIGRATE,
        },
        {
          text: "« port is already allocated » au démarrage : un autre programme utilise le port 8080 ou 8443. Arrêtez-le, ou changez les ports dans docker-compose.yml.",
        },
        { text: "Vérifier les sauvegardes :", commands: BACKUPS },
      ],
    },
    {
      id: "danger",
      title: "À ne jamais taper",
      steps: [
        {
          text: "Ces commandes effacent le volume de la base, c'est-à-dire toutes vos données. Seule une sauvegarde pourrait les ramener (voir docs/OPERATIONS.md pour la restauration).",
          commands: DANGER,
        },
        {
          text: "Ne partagez et ne commitez jamais le fichier .env : il contient vos mots de passe et la clé secrète.",
        },
      ],
    },
  ],
};
