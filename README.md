# Aniimo Overlay

Overlay de bureau transparent, toujours au premier plan, qui affiche la carte interactive du
**Sanctuaire perdu** d'[aniimotools.dev](https://aniimotools.dev/fr/map/lost-sanctum/)
par-dessus le jeu **Aniimo**, et qui reconnaît le plan en repérant la porte bleue par
rapport à la porte orange sur la carte du jeu.

> Carte fournie par aniimotools.dev, site de fans non officiel.
> Outil non affilié à Pawprint Studio / FunPlus ni à aniimotools.dev.

## Utilisation (Windows)

1. Télécharge `AniimoOverlay.exe` et double-clique dessus. Rien à installer.
2. Mets le jeu en **plein écran fenêtré (borderless)**. Un overlay ne peut pas s'afficher
   par-dessus un plein écran exclusif.
3. La fenêtre de contrôle s'ouvre. **F8** affiche l'overlay.
4. La première fois, passe en **mode interactif (F9)** pour accepter le bandeau de
   cookies du site et choisir ta difficulté. Le site retient ces choix.
5. En partie, ouvre la carte du jeu puis appuie sur **F10** : l'overlay sélectionne la
   bonne direction sur le site.

| Action | Raccourci par défaut |
|---|---|
| Afficher / masquer l'overlay | `F8` |
| Mode passif / interactif | `F9` |
| Détecter le plan | `F10` |
| Opacité + / − | `Ctrl+Alt+Haut` / `Ctrl+Alt+Bas` |
| Zoom de la page + / − | `Ctrl+Alt+Droite` / `Ctrl+Alt+Gauche` |

Tout se règle dans la fenêtre de contrôle (onglets Affichage, Raccourcis, Détection, Site,
À propos). Si tu la fermes, l'application reste dans la zone de notification ; « Quitter »
est dans le menu de l'icône et en haut de la fenêtre.

- **Mode passif** (par défaut) : les clics traversent l'overlay et vont au jeu.
- **Mode interactif** : l'overlay reçoit souris et clavier. Une barre apparaît en haut
  avec un liseré bleu : glisse la barre pour déplacer, tire les bords pour redimensionner.

### Si la détection se trompe

Onglet **Détection** → **Calibrer les couleurs des portes** : capture l'écran avec la
carte du jeu ouverte, clique sur la porte orange puis sur la bleue, vérifie les masques,
valide. « Tester sur l'écran actuel » montre ce que l'outil a trouvé.

### Bon à savoir

- **SmartScreen / antivirus** : l'exe n'est pas signé. Windows peut afficher « Windows a
  protégé votre ordinateur » → *Informations complémentaires* → *Exécuter quand même*.
- **Démarrage** : l'exe se décompresse à chaque lancement, il faut quelques secondes
  (un écran « Chargement… » s'affiche).
- **Jeu lancé en administrateur** : lance aussi l'overlay en administrateur, sinon les
  raccourcis ne fonctionnent pas quand le jeu a le focus.
- **Captures et streaming** : l'overlay est exclu des captures d'écran (pour ne pas
  perturber la détection). Il n'apparaîtra donc pas non plus dans OBS ou une capture.
- Réglages, profil web, logs : `%APPDATA%\aniimo-overlay` et `%LOCALAPPDATA%\aniimo-overlay`.

## Respect du site et du jeu

- La page est affichée en direct, comme dans un navigateur, et chargée une seule fois.
  Aucun contenu du site n'est copié, mis en cache sur disque ou modifié (pubs et marque
  comprises). L'outil appuie sur la touche du pavé numérique comme le ferait un joueur ;
  c'est le site qui choisit le plan.
- Aucune interaction avec le processus du jeu : uniquement une capture d'écran et une
  fenêtre posée au-dessus. Aucune touche n'est envoyée au jeu.
- Avant toute distribution publique, l'accord de l'auteur d'aniimotools.dev doit être
  demandé (Discord du site ou `support@holst.network`).

## Développement

Python 3.11+.

```bash
python -m venv .venv && source .venv/bin/activate      # Windows : .venv\Scripts\activate
pip install -e ".[dev]"
python -m aniimo_overlay                 # lancer
python -m aniimo_overlay --debug         # logs détaillés
python -m aniimo_overlay --debug-detection   # sauve captures + masques dans les logs
pytest -q
ruff check . && ruff format .
python tools/make_synthetic.py --out tests/fixtures/synthetic
python tools/fake_game.py tests/fixtures/synthetic/ne_01.png
python -m aniimo_overlay.detection.calibrate capture.png --orange 812,440 --blue 1033,301
QTWEBENGINE_REMOTE_DEBUGGING=9222 python -m aniimo_overlay   # DevTools de la vue web
```

Sous Ubuntu, si `python -m venv` échoue (paquet `python3-venv` absent) :
`python3 -m venv --without-pip .venv && python3 -m pip --python .venv/bin/python install pip`.

**Linux / Wayland** : capture globale, raccourcis globaux et « toujours au premier plan »
ne fonctionnent pas sous Wayland. L'application bascule automatiquement sur XWayland
(`QT_QPA_PLATFORM=xcb`) et l'écrit dans les logs. Les tests réels se font sous Windows.

### Construire l'exe

- **Sous Windows** : `powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1`
  → `dist\AniimoOverlay.exe`.
- **Depuis Linux** : pousser le dépôt sur GitHub, puis lancer le workflow
  *Build Windows exe* (onglet Actions) ou pousser un tag `v*`
  (`git tag v0.1.0 && git push origin v0.1.0`) : l'exe est publié en artifact, et en
  release pour un tag.
# aniimo-interactiv-card-overlay
