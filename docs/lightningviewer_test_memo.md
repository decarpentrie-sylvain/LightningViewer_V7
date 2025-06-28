# Mémo : batterie de tests LightningViewer V7

> Ce document rassemble les commandes Terminal à copier/coller pour **vérifier qu’une installation de LightningViewer V7 fonctionne correctement**. Chaque test indique :
>
> - **But**
> - **Commande exacte** (copier **sans** le prompt `%`)
> - **Résultat attendu** (succès)
>
> *Tous les chemins sont donnés pour l’installation standard **`/Applications/LightningViewer_V7`**.*

---

# Où intégrer cette fiche ?

- **README.md** : si tu veux que les tests soient visibles immédiatement sur GitHub.
- **docs/tests.md** : si le README est déjà long et que tu préfères un fichier dédié.
- Ou conserve‑la localement dans un carnet de notes.

---

## 0 – Préparation

```bash
cd /Applications/LightningViewer_V7
source .venv/bin/activate   # active l’environnement virtuel
```

---

## 1 – Vérifier le chargement du fichier `.env`

**But** : s’assurer que les variables `BLITZ_LOGIN` et `BLITZ_PASSWORD` sont vues par Python.

```bash
python - <<'PY'
import os, dotenv, pathlib, pprint
dotenv.load_dotenv(pathlib.Path('.env'))
pprint.pp({k:v for k,v in os.environ.items() if k.startswith('BLITZ')})
PY
```

**Attendu** : un dictionnaire affichant les deux variables, par ex. :

```python
{'BLITZ_LOGIN': 'mon@mail.fr', 'BLITZ_PASSWORD': '******'}
```

---

## 2 – Voir l’aide de la CLI LightningViewer

```bash
python -m lightningviewer.cli --help | head
```

**Attendu** : le texte « LightningViewer V7 – outil en ligne de commande » avec les sous‑commandes `download`, `query`, `purge`, `gui`.

---

## 3 – Exécution manuelle du script **update\_blitz.py**

```bash
python src/lightningviewer/update_blitz.py
echo "Code retour update = $?"
tail -n 5 ~/Library/Logs/LightningViewer/update.log
```

**Attendu** :

- Le `code retour` doit être `0`.
- Les 5 lignes de log se terminent par `Mise à jour OK.` et `Fin du script.`

---

## 4 – Purge automatique (sans argument)

```bash
python src/lightningviewer/purge_blitz.py
tail -n 3 ~/Library/Logs/LightningViewer/purge.log
```

**Attendu** : message `✅ Purge automatique : …`, puis ligne de log correspondante.

---

## 5 – Purge manuelle d’un créneau

```bash
python src/lightningviewer/purge_blitz.py \
  --manual-start 2025-06-01T00:00 \
  --manual-end   2025-06-05T00:00 \
  --disable-events-purge
tail -n 2 ~/Library/Logs/LightningViewer/purge.log
```

**Attendu** : affichage `✅ Purge manuelle … Événements conservés` et écriture dans `purge.log`.

---

## 6 – Script de coordination

```bash
python src/lightningviewer/coordination_maj_bdd_blitz.py
tail -n 4 ~/Library/Logs/LightningViewer/coordination.log
```

**Attendu** : lignes `Déclenchement de la mise à jour Blitz` / `Purge non nécessaire` (ou l’inverse) puis `✅ Script … exécuté avec succès.`

---

## 7 – Intégrité de la base SQLite

```bash
sqlite3 data/blitz.db "PRAGMA integrity_check;"
```

**Attendu** : le mot `ok` seul sur la sortie.

---

## 8 – État des agents launchd

```bash
launchctl list | egrep 'lightningviewer'
```

**Attendu** : deux lignes similaires à :

```
-     0   org.lightningviewer.update
-     0   org.lightningviewer.purge
```

Le chiffre `0` indique que les jobs sont chargés **et** ne sont pas actuellement en échec.

---

## 9 – Forcer une exécution via launchctl

```bash
launchctl start org.lightningviewer.update
sleep 2
tail -n 3 ~/Library/Logs/LightningViewer/update.log
```

**Attendu** : apparition d’une nouvelle entrée « Téléchargement … ».

Refaire la même chose pour la purge :

```bash
launchctl start org.lightningviewer.purge
sleep 2
tail -n 3 ~/Library/Logs/LightningViewer/purge.log
```

---

## 10 – Affichage temps‑réel des journaux (debug live)

Suivre un journal :

```bash
tail -f ~/Library/Logs/LightningViewer/update.log
```

> **Ctrl‑C** pour quitter.

---

## 11 – Désactiver l’environnement virtuel

```bash
deactivate
```

---





