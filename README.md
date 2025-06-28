# LightningViewer

## Automatisation macOS : Launch Agent (upload données blitzortung automatiques). Ce texte explique l’utilité de chaque section, la personnalisation des horaires,
l’adaptation du chemin Python et la procédure de (dés)installation. Pour maintenir la base `blitz.db` à jour sans intervention, LightningViewer fournit
un *Launch Agent* macOS.

    ### Installation rapide

    ```bash
        # Copier le fichier dans le dossier utilisateur
        mkdir -p ~/Library/LaunchAgents
        cp fr.svdvet.lightningviewer.coordination.plist ~/Library/LaunchAgents/

    # Charger l’agent (démarrage immédiat grâce à RunAtLoad)
    launchctl load ~/Library/LaunchAgents/fr.svdvet.lightningviewer.coordination.plist

    Personnaliser les horaires de l'upload des données depuis blitzortnung.org:
    Ouvrez le fichier avec un éditeur (nano, TextEdit, VS Code) et modifiez la section:
            StartCalendarInterval :
            <array>
            <dict><key>Hour</key><integer>6</integer><key>Minute</key><integer>0</integer></dict>
            <dict><key>Hour</key><integer>12</integer><key>Minute</key><integer>0</integer></dict>
            <dict><key>Hour</key><integer>18</integer><key>Minute</key><integer>0</integer></dict>
            </array>

        Ajouter ou supprimer un bloc <dict> pour changer le nombre de créneaux.
        Changer la valeur Hour / Minute selon vos besoins.

    Après modification (depuis le terminal):
    launchctl unload ~/Library/LaunchAgents/fr.svdvet lightningviewer.coordination.plist
    launchctl load   ~/Library/LaunchAgents/fr.svdvet.lightningviewer.coordination.plist

    ### Chemin python
Si votre Python n’est pas /usr/bin/python3, modifiez le premier
élément de ProgramArguments (ex. /opt/homebrew/bin/python3).

    # Journaux
	•	Stdout : ~/Library/Logs/LightningViewer/coordination_stdout.log
	•	Stderr : ~/Library/Logs/LightningViewer/coordination_stderr.log
	•	Journal applicatif : ~/Library/Logs/LightningViewer/coordination.log

    # Désinstallation:
    launchctl unload ~/Library/LaunchAgents/fr.svdvet.lightningviewer.coordination.plist
rm               ~/Library/LaunchAgents/fr.svdvet.lightningviewer.coordination.plist
L’agent est alors supprimé et ne tournera plus au démarrage.

📂 Gestion automatique des purges (purge_blitz.py):
Sujet
Comportement par défaut
Comment régler
Rétention des impacts
Tous les impacts situés à plus de 15 jours dans le passé sont supprimés.
Changer la constante dans purge_blitz.py (dt.timedelta(days=15)).
Délai de grâce
Les impacts (et événements) des 2 derniers jours sont toujours conservés, même s’ils sont hors fenêtre 15 j (utile pour une étude ponctuelle).
Modifier dt.timedelta(days=2) dans purge_blitz.py.
Événements (log_events) conservés
- Tous les événements concernant la fenêtre glissante de 15 j.- Les événements hors fenêtre créés il y a moins de 2 jours.
Même logique de délai ; ajustable au même endroit.
Lancement automatique
Le script coordination_maj_bdd_blitz.py déclenche purge_blitz.py si aucune purge réussie depuis > 24 h.
Adapter la valeur 24 * 3600 dans should_run_purge().
Planification
Le Launch Agent exécute coordination_maj_bdd_blitz.py à 6 h, 12 h, 18 h (et au login).La purge n’a lieu que si le critère de 24 h est rempli.
Modifier les heures dans le .plist, ou l’intervalle dans should_run_purge().
Purge manuelle
Exécuter :python purge_blitz.py --manual-start 2025-06-01T00:00 --manual-end 2025-06-10T00:00
L’interface Streamlit proposera bientôt un formulaire pour choisir les dates.
Désactiver la purge des événements
Ajoutez --disable-events-purge lors d’un appel manuel (utile pour le débogage).
Exemple de log (~/Library/Logs/LightningViewer/purge.log): 2025-06-26 18:00:03 - Purge automatique : 12 impacts supprimés, 3 événements log supprimés.
2025-06-26 18:00:03 - Purge terminée. Impacts antérieurs au 2025-06-24T18:00:00 supprimés.
Astuce :
Consultez en direct :
tail -f ~/Library/Logs/LightningViewer/purge.log

Ainsi, la base reste légère et performante tout en garantissant qu’aucune donnée récente ou en cours d’analyse ne soit supprimée par inadvertance.

## Tests de validation rapides

Voir le pas-à-pas : [docs/tests.md](docs/tests.md)
