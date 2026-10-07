# CLAUDE.md — Aniimo Map Overlay

> Ce fichier est le brief du projet pour Claude Code. Lis-le en entier avant d'écrire du code.
> Langue de travail avec l'utilisateur : **français**. Code, noms de variables, commits et commentaires : **anglais**.

---

## 1. Le projet en une phrase

Un overlay de bureau, transparent et toujours au premier plan, qui s'affiche **par-dessus le jeu Aniimo** et montre la carte interactive du **Sanctuaire perdu** (mode *Chasse aux œufs*) du site **aniimotools.dev**, qui **reconnaît automatiquement le plan** sur lequel le joueur se trouve, et qu'on affiche / masque avec une touche.

Page cible : `https://aniimotools.dev/fr/map/lost-sanctum/`

**Livrables finaux :**
1. Une **interface graphique** complète (fenêtre de contrôle + réglages), utilisable sans jamais toucher à un fichier de config ni à un terminal.
2. **Un seul fichier `AniimoOverlay.exe`** pour Windows : double-clic → ça marche, sans installer Python ni quoi que ce soit.

## 2. Contexte jeu (ce qu'il faut savoir)

- Aniimo est un ARPG de capture de créatures (Pawprint Studio). Le mode **Chasse aux œufs – Mode équipe** se joue dans le **Sanctuaire perdu**.
- Le Sanctuaire **n'est pas généré aléatoirement** : chaque partie tire un plan parmi **21 plans dessinés à la main** (8 en Débutant, 6 en Difficile, 7 partagés par Cauchemar et Chaos).
- **Comment on identifie le plan** (méthode décrite par le site lui-même) : on ouvre la carte en jeu ; la **porte orange** = entrée principale, la **porte bleue** = entrée secondaire. **La direction de la porte bleue vue depuis la porte orange** (N, NE, E, SE, S, SO, O, NO) désigne la plupart des plans d'un coup. Quand deux plans partagent une direction, la forme de la carte / la distance entre portes les départage.
- La page aniimotools a déjà un sélecteur « Quel plan ? » utilisable **au pavé numérique** : `8 = nord`, `6 = est`, etc. (disposition du pavé numérique = rose des vents). **C'est ce mécanisme qu'on pilote** depuis l'overlay.

## 3. Contraintes NON négociables

### 3.1 Respect du site aniimotools.dev
Le site interdit explicitement (CGU + mentions légales + `llms.txt`) de **republier ou extraire ses textes, données, images ou pages dans une autre application**, même en le citant. Sa base de données (plans, coordonnées, positions des nids…) est protégée (CPI art. L.341-1). Donc :

- ✅ L'overlay **affiche la page live** du site dans une vue web embarquée, exactement comme un navigateur. L'utilisateur navigue sur le vrai site.
- ✅ On pilote la page **comme le ferait un utilisateur** (appui sur une touche du pavé numérique, clic, scroll, zoom).
- ❌ **Interdit** : télécharger / scraper / mettre en cache sur disque les images de plans, les vignettes (`/assets/lost-sanctum/maps/*`), les données JSON, les textes. Pas de dossier `assets/` contenant du contenu du site.
- ❌ **Interdit** : coder en dur une table « direction → numéro de plan » recopiée du site. La correspondance, c'est **le site qui la fait** quand on lui envoie la direction.
- ❌ **Interdit** : bloquer les pubs, masquer le nom/la marque AniimoTools, réécrire le contenu de la page.
- ✅ Autorisé : régler le zoom de la vue (`setZoomFactor`), faire défiler jusqu'à la section carte, ajuster l'opacité de la **fenêtre**.
- ⚠️ Charger la page **une fois**, pas de rechargement en boucle, pas de requêtes répétées vers le site ou son API.
- 📌 Avant toute distribution publique de l'outil : l'utilisateur doit **demander l'accord de l'auteur** (Discord du site ou `support@holst.network`). Si l'auteur propose un mode « embed » ou une API autorisée, on l'utilisera à la place. Garde l'URL et la logique de pilotage isolées dans `bridge/` pour pouvoir changer facilement.

### 3.2 Respect du jeu / anti-triche
- ❌ **Jamais** d'injection dans le processus du jeu, de hook DirectX, de lecture/écriture mémoire, de DLL.
- ❌ **Jamais** d'envoi de touches ou de clics **au jeu**.
- ✅ Uniquement : **capture d'écran** (lecture des pixels affichés) + une fenêtre séparée posée au-dessus.
- Le jeu doit tourner en **plein écran fenêtré (borderless)** : un overlay ne peut pas s'afficher par-dessus un plein écran exclusif sous Windows. À documenter dans le README.

## 4. Stack technique (choisie, ne pas changer sans demander)

| Besoin | Choix | Pourquoi |
|---|---|---|
| Langage | Python 3.11+ | Rapide à itérer, OpenCV natif, même code Linux/Windows |
| UI + vue web | **PySide6** (`QtWebEngineWidgets`) | Chromium embarqué identique sur Linux et Windows, fenêtres frameless / top-most / opacité bien supportées |
| Capture écran | `mss` | Rapide, multiplateforme |
| Vision | `opencv-python-headless`, `numpy` | Segmentation couleur + template matching |
| Hotkeys globales | `pynput` (`GlobalHotKeys`) | Fonctionne Linux X11 + Windows |
| Config | TOML (`tomllib` + `tomli-w`), dossier via `platformdirs` | |
| Spécifique Windows | `pywin32` (ou `ctypes`) | Click-through fiable, recherche de la fenêtre du jeu, DPI |
| Tests | `pytest` | |
| Packaging | `PyInstaller` (build **sur Windows**) | .exe unique |
| Lint / format | `ruff` | |

Gestion des dépendances : `pyproject.toml` + venv (`python -m venv .venv`). Dépendances Windows-only marquées avec `; sys_platform == "win32"`.

## 5. Architecture

```
aniimo-overlay/
├── CLAUDE.md
├── README.md                  # install, usage, hotkeys, borderless, Wayland
├── pyproject.toml
├── src/aniimo_overlay/
│   ├── __main__.py            # python -m aniimo_overlay
│   ├── app.py                 # QApplication, wiring des modules, signaux
│   ├── config.py              # dataclass Config, load/save TOML, valeurs par défaut
│   ├── overlay/
│   │   ├── window.py          # OverlayWindow : QWebEngineView frameless, top-most, opacité
│   │   ├── handle.py          # petite barre de poignée (déplacer / redimensionner / statut)
│   │   └── clickthrough.py    # set_click_through(window, bool) — impl. par OS
│   ├── hotkeys.py             # pynput -> Qt signals (thread-safe, QueuedConnection)
│   ├── tray.py                # icône de zone de notif : afficher, détecter, réglages, quitter
│   ├── gui/
│   │   ├── control_window.py  # fenêtre principale (statut, gros boutons, onglets)
│   │   ├── tab_display.py     # onglet Affichage : opacité, zoom, taille, position
│   │   ├── tab_hotkeys.py     # onglet Raccourcis : capture d'une touche au clic
│   │   ├── tab_detection.py   # onglet Détection : auto on/off, intervalle, test, aperçu
│   │   ├── calibration_dialog.py # assistant de calibration graphique des portes
│   │   ├── tab_about.py       # onglet À propos : version, lien aniimotools.dev, crédits, logs
│   │   └── widgets.py         # HotkeyEdit, sliders avec valeur, voyant d'état
│   ├── resources/             # icône .ico/.png de l'app (créée par nous), styles .qss
│   ├── capture/
│   │   ├── screen.py          # grab(region) -> np.ndarray BGR
│   │   └── game_window.py     # Windows : trouver la fenêtre "Aniimo" ; Linux : fallback écran/ROI
│   ├── detection/
│   │   ├── doors.py           # trouve porte orange + porte bleue sur une image
│   │   ├── direction.py       # vecteur -> secteur 8 directions -> touche numpad
│   │   ├── map_state.py       # (phase ultérieure) la carte du jeu est-elle ouverte ?
│   │   └── calibrate.py       # outil CLI : régler couleurs HSV / découper des templates
│   └── bridge/
│       └── site.py            # tout ce qui touche à la page web : URL, envoi de la direction, scroll
├── packaging/
│   ├── AniimoOverlay.spec     # spec PyInstaller (onefile, icône, version, ressources QtWebEngine)
│   ├── version_info.txt       # métadonnées Windows de l'exe
│   └── build_windows.ps1      # build local sur Windows en une commande
├── .github/workflows/
│   └── build-windows.yml      # build de l'exe sur un runner Windows, publié en artifact
├── tools/
│   ├── fake_game.py           # affiche une image plein écran pour simuler le jeu (dev Linux)
│   └── make_synthetic.py      # génère des images de test (fond sombre + 2 marqueurs colorés)
└── tests/
    ├── fixtures/              # images de test : synthétiques + captures d'écran PERSO du jeu
    ├── test_direction.py
    ├── test_doors.py
    └── test_config.py
```

Règles d'architecture :
- `detection/` est **pur** : prend un `np.ndarray`, renvoie un résultat. Aucun import Qt. 100 % testable sans écran.
- `bridge/site.py` est le **seul** module qui connaît le site (URL, sélecteurs, manière d'envoyer une touche).
- Tout ce qui est spécifique à un OS passe par une fonction avec un `if sys.platform == "win32"` isolé dans un seul fichier (`clickthrough.py`, `game_window.py`).
- Les callbacks `pynput` tournent dans un autre thread : **ne jamais** toucher un widget Qt depuis là, émettre un signal.
- La détection tourne hors du thread UI (`QThreadPool` / `QRunnable`), résultat renvoyé par signal.

## 6. Comportement attendu

### 6.1 La fenêtre overlay
- Sans bordure, toujours au premier plan, absente de la barre des tâches (`Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool`).
- **Opacité réglable** de 20 % à 100 % (`setWindowOpacity`), par pas de 5 %.
- **Déplaçable et redimensionnable** via la barre de poignée (visible seulement en mode interactif) + coins de redimensionnement.
- **Zoom de la page** réglable (`setZoomFactor`, 0.5 → 2.0).
- Position, taille, opacité, zoom **sauvegardés** dans la config à la fermeture et restaurés au lancement.
- Profil web **persistant** (`QWebEngineProfile` avec dossier de stockage) pour garder préférences / connexion du site (ex. un compte Patreon sans pub).

### 6.2 Deux modes
- **Mode passif (par défaut)** : clics traversants (click-through) → la souris va au jeu, l'overlay est juste une carte posée dessus.
- **Mode interactif** : l'overlay reçoit souris et clavier → on peut cliquer sur un plan, zoomer, scroller, déplacer/redimensionner. La barre de poignée apparaît avec un liseré coloré pour qu'on voie qu'on est dans ce mode.

### 6.3 Raccourcis globaux (configurables dans `config.toml`)
| Action | Défaut |
|---|---|
| Afficher / masquer l'overlay | `F8` |
| Basculer mode passif / interactif | `F9` |
| Détecter le plan maintenant | `F10` |
| Opacité + / − | `Ctrl+Alt+Haut` / `Ctrl+Alt+Bas` |
| Zoom page + / − | `Ctrl+Alt+Droite` / `Ctrl+Alt+Gauche` |

Format des hotkeys dans la config : syntaxe `pynput` (`"<f8>"`, `"<ctrl>+<alt>+<up>"`).

### 6.4 Reconnaissance du plan
Pipeline :
1. **Capture** : la région du jeu (Windows : rectangle client de la fenêtre Aniimo ; sinon écran principal ou ROI de la config).
2. **Détection des portes** (`detection/doors.py`) :
   - Approche 1 (par défaut) : segmentation **HSV** — un masque pour l'orange, un pour le bleu, nettoyage morphologique, garder le plus gros contour plausible (aire min/max, circularité), centroïde.
   - Approche 2 (repli) : **template matching** multi-échelle avec des icônes de portes **découpées par l'utilisateur dans ses propres captures du jeu** (via `calibrate.py`), stockées dans le dossier config. Jamais d'icônes venant du site.
   - Renvoie `DoorDetection(orange: (x,y)|None, blue: (x,y)|None, confidence: float)`.
3. **Direction** (`detection/direction.py`) : vecteur bleu − orange, attention **l'axe Y écran est inversé** (y vers le bas). Angle → un des 8 secteurs de 45°. Secteur → touche du pavé numérique : `N=8, NE=9, E=6, SE=3, S=2, SO=1, O=4, NO=7`. Renvoie aussi la distance (utile plus tard pour départager).
4. **Envoi au site** (`bridge/site.py`) : envoyer la touche numpad à la vue web **comme une vraie frappe** (`QKeyEvent` avec `Qt.KeypadModifier` envoyé au `focusProxy()` de la vue), puis faire défiler vers la section du sélecteur. C'est le site qui affiche le ou les plans correspondants. Si la frappe ne marche pas, inspecter le DOM (voir §8) et cliquer l'élément correspondant via `runJavaScript` — **sans** extraire de données.
5. **Retour visuel** : la barre de poignée / le tray affiche « Porte bleue : Nord-Est (confiance 0.92) » ou « Portes non trouvées — ouvre la carte en jeu ».

Déclenchement :
- **Manuel** (`F10`) en priorité : le joueur ouvre la carte en jeu, appuie sur F10.
- **Auto** (option, désactivée par défaut) : poll toutes les 1–2 s ; ne déclenche que si les deux portes sont trouvées avec une confiance > seuil **et** que le résultat est stable sur 2 captures consécutives ; ne renvoie rien au site si la direction n'a pas changé.
- La **difficulté** n'est pas détectée au début : l'utilisateur la choisit une fois dans la page (le site s'en souvient normalement).

### 6.5 Interface graphique (fenêtre de contrôle)

L'utilisateur final ne doit **jamais** avoir besoin d'éditer `config.toml` ni d'ouvrir un terminal. Tout se règle dans la GUI, et chaque changement est **appliqué en direct** à l'overlay et sauvegardé automatiquement.

Au lancement de l'exe : la fenêtre de contrôle s'ouvre + l'icône tray apparaît. Fermer la fenêtre de contrôle la **réduit dans le tray** (l'overlay continue de tourner) ; « Quitter » est dans le tray et dans la fenêtre.

**En-tête (toujours visible)**
- Voyants d'état : Overlay (visible / masqué), Mode (passif / interactif), Jeu (fenêtre Aniimo trouvée / non trouvée), Dernière détection (« Nord-Est · confiance 0.92 · il y a 12 s »).
- Gros boutons : **Afficher / masquer l'overlay**, **Mode interactif**, **Détecter maintenant**.

**Onglet Affichage**
- Sliders avec valeur affichée : opacité (20–100 %), zoom de la page (50–200 %).
- Champs largeur / hauteur / X / Y + boutons de position rapide (coin haut-gauche, haut-droite, bas-gauche, bas-droite de l'écran ou de la fenêtre du jeu).
- Case « Afficher l'overlay au démarrage ».
- Bouton « Réinitialiser la position ».

**Onglet Raccourcis**
- Une ligne par action (§6.3) avec un `HotkeyEdit` : on clique, on appuie sur la combinaison, elle s'enregistre. Bouton « effacer » par ligne.
- Détection des **conflits** (même combinaison sur deux actions) → message en rouge, pas de sauvegarde.
- Bouton « Rétablir les raccourcis par défaut ».
- Les hotkeys globales sont **suspendues** pendant qu'on édite un raccourci.

**Onglet Détection**
- Case « Détection automatique » + intervalle (0.5–5 s) + seuil de confiance.
- Bouton **« Tester sur l'écran actuel »** : capture, lance la détection, affiche l'image réduite avec les portes entourées (orange / bleu), la flèche, la direction trouvée et la confiance.
- Bouton **« Tester sur une image… »** (sélecteur de fichier) — indispensable pour le dev Linux.
- Bouton **« Calibrer les couleurs des portes »** → `calibration_dialog.py` : affiche une capture, l'utilisateur clique sur la porte orange puis sur la bleue, on calcule les plages HSV, on montre un aperçu des masques, bouton « Valider ».
- Champ « Titre de la fenêtre du jeu » (défaut `Aniimo`).

**Onglet Site**
- URL de la page (défaut FR) + choix de langue (FR / EN / DE / ES…) qui reconstruit l'URL.
- Bouton « Recharger la page » et « Ouvrir dans le navigateur ».

**Onglet À propos**
- Version, lien vers aniimotools.dev, mention claire « Carte fournie par aniimotools.dev, site de fans non officiel. Outil non affilié à Pawprint Studio / FunPlus. »
- Bouton « Ouvrir le dossier des logs », case « Mode debug détection ».

**Style**
- Thème sombre cohérent (fichier `.qss`), polices lisibles, fenêtre ~520×640, redimensionnable.
- Tous les textes en français, centralisés pour permettre une traduction plus tard (`self.tr()`).
- Icône de l'application **créée par nous** (pas d'image du jeu ni du site).

## 7. Spécificités Linux (phase 1) — à lire

- Aniimo **n'est pas testé sous Linux** : en phase 1 on développe et teste avec des **images** (synthétiques + captures d'écran que l'utilisateur fera sous Windows) et `tools/fake_game.py` qui affiche une image en plein écran pour simuler le jeu.
- **Wayland** casse trois choses : capture d'écran globale (`mss`), hotkeys globales (`pynput`), et « toujours au premier plan ». Solutions, dans l'ordre :
  1. se connecter en **session X11** pour le dev ;
  2. sinon lancer avec `QT_QPA_PLATFORM=xcb` (XWayland) et accepter que les hotkeys ne marchent que si une fenêtre X a le focus ;
  3. au démarrage, si `XDG_SESSION_TYPE == "wayland"`, **logger un avertissement clair** en français.
- Click-through sous Linux X11 : `Qt.WindowTransparentForInput` (nécessite `hide()` / `show()` après changement de flags).
- Transparence : un compositeur doit tourner (KDE, GNOME, picom…).

## 8. Spécificités Windows (phase 2)

- **Click-through** : `Qt.WindowTransparentForInput` ne suffit pas toujours → via WinAPI, ajouter `WS_EX_LAYERED | WS_EX_TRANSPARENT` (et `WS_EX_TOOLWINDOW`) avec `SetWindowLongW(GWL_EXSTYLE)`. Les retirer en mode interactif.
- **DPI** : rendre le process DPI-aware (`SetProcessDpiAwarenessContext(PER_MONITOR_AWARE_V2)`) avant de créer la `QApplication`, sinon les coordonnées de capture seront décalées sur écrans à 125/150 %.
- **Fenêtre du jeu** : `EnumWindows` + titre contenant `Aniimo` (titre exact à confirmer en jeu, le mettre dans la config) → `GetClientRect` + `ClientToScreen`. Option : coller l'overlay à un coin de la fenêtre du jeu.
- **Hotkeys** : vérifier que `pynput` reçoit bien les touches quand le jeu a le focus. Si le jeu tourne en admin, l'overlay doit aussi tourner en admin (sinon pas de hotkeys) — à documenter, ne pas forcer.
- **Packaging — un seul `.exe`** (voir §8.1).
- Vérifier le comportement en **plein écran fenêtré** uniquement ; afficher un message si on détecte que le jeu occupe l'écran en exclusif (best effort).

### 8.1 Build de l'exe unique

- **PyInstaller ne cross-compile pas** : un `.exe` Windows se construit **sur Windows**. Deux voies, les deux doivent marcher :
  1. **GitHub Actions** (`.github/workflows/build-windows.yml`) sur `windows-latest` : install Python 3.11, `pip install -e .`, `pyinstaller packaging/AniimoOverlay.spec`, upload de `dist/AniimoOverlay.exe` en artifact. Déclenché à la main (`workflow_dispatch`) et sur tag `v*` (le tag crée une release avec l'exe). Permet de produire l'exe **depuis Linux** en poussant le code.
  2. **Local** : `packaging/build_windows.ps1` (crée le venv, installe, build).
- Spec PyInstaller :
  - `--onefile`, `--noconsole` (`console=False`), icône `resources/app.ico`, `version_info.txt` (nom, version, éditeur).
  - Inclure les ressources QtWebEngine (`QtWebEngineProcess.exe`, `resources/*.pak`, `icudtl.dat`, `translations/qtwebengine_locales`) — utiliser les hooks PySide6 de PyInstaller et **vérifier** qu'elles sont bien dans l'archive.
  - Inclure `src/aniimo_overlay/resources/` (icônes, `.qss`).
  - Exclure ce qui ne sert pas (tkinter, modules Qt inutiles) pour réduire la taille.
- Le code doit trouver ses ressources via un helper `resource_path()` qui gère `sys._MEIPASS` (exe) et le mode dev.
- `--onefile` décompresse dans un dossier temporaire à chaque lancement → démarrage de quelques secondes : afficher un **splash screen** (`pyi_splash` ou fenêtre Qt minimale) pour que l'utilisateur sache que ça charge.
- Config, profil web, logs et calibration vont dans `%APPDATA%` / `%LOCALAPPDATA%` (via `platformdirs`), **jamais** à côté de l'exe ni dans le dossier temporaire.
- Une seule instance à la fois (`QLockFile` ou `QLocalServer`) : relancer l'exe ramène la fenêtre de contrôle existante au premier plan.
- Antivirus : un exe PyInstaller non signé peut déclencher SmartScreen / des faux positifs. Documenter dans le README (« Informations complémentaires → Exécuter quand même ») ; ne **pas** utiliser de packer/obfuscateur.
- Test d'acceptation de l'exe : copié seul sur une machine Windows **sans Python**, double-clic → splash → fenêtre de contrôle → la page s'affiche dans l'overlay → F8 / F9 / F10 fonctionnent.

## 9. Inspection de la page (pour `bridge/site.py`)

- Lancer l'app avec `QTWEBENGINE_REMOTE_DEBUGGING=9222`, ouvrir `http://localhost:9222` dans Chrome/Chromium pour avoir les DevTools de la vue embarquée.
- Objectifs : vérifier que l'appui numpad fonctionne quand la page a le focus ; repérer l'ancre/la section du sélecteur « Quel plan ? » pour `scrollIntoView` ; repérer le sélecteur de difficulté.
- Les sélecteurs CSS trouvés vont dans **une seule constante** en haut de `bridge/site.py`, avec un commentaire « peut casser si le site change ». Toute fonction du bridge doit **échouer proprement** (log + message dans la barre de statut) si l'élément n'existe plus.
- Ne lire du DOM que ce qui sert à naviguer (ex. existence d'un élément), jamais pour copier du contenu.

## 10. Config (`config.toml` dans `platformdirs.user_config_dir("aniimo-overlay")`)

```toml
[site]
url = "https://aniimotools.dev/fr/map/lost-sanctum/"

[window]
x = 100
y = 100
width = 520
height = 720
opacity = 0.85
zoom = 0.9
start_visible = false

[hotkeys]
toggle_visible = "<f8>"
toggle_interactive = "<f9>"
detect = "<f10>"
opacity_up = "<ctrl>+<alt>+<up>"
opacity_down = "<ctrl>+<alt>+<down>"
zoom_in = "<ctrl>+<alt>+<right>"
zoom_out = "<ctrl>+<alt>+<left>"

[capture]
game_window_title = "Aniimo"
monitor = 1
# roi = [x, y, w, h]   # optionnel, relatif à la fenêtre du jeu

[detection]
auto = false
interval_s = 1.5
min_confidence = 0.6
orange_hsv = [[5, 120, 150], [22, 255, 255]]   # à calibrer
blue_hsv   = [[95, 120, 120], [120, 255, 255]] # à calibrer
```

Valeurs absentes → défauts. Fichier corrompu → on le renomme en `.bak`, on repart des défauts, on logge.

## 11. Plan de développement (phases)

Avance phase par phase. À la fin de chaque phase : tests verts, `ruff` propre, court résumé à l'utilisateur de ce qui marche et de comment le tester.

**Phase 0 — Squelette**
- `pyproject.toml`, venv, arborescence, `python -m aniimo_overlay` ouvre une fenêtre qui charge la page.
- ✅ Fini quand : la page s'affiche dans une fenêtre normale.

**Phase 1 — Overlay**
- Frameless, top-most, opacité, barre de poignée, déplacement/redimensionnement, zoom, persistance de la géométrie, icône tray (Afficher/Masquer, Mode interactif, Quitter).
- ✅ Fini quand : on peut placer l'overlay semi-transparent par-dessus `tools/fake_game.py`, le redimensionner, relancer l'app et le retrouver au même endroit.

**Phase 2 — Hotkeys + modes**
- `hotkeys.py`, mode passif (click-through) / interactif, toutes les actions du §6.3.
- ✅ Fini quand : sous X11, F8/F9 et opacité marchent pendant que `fake_game.py` a le focus, et les clics traversent en mode passif.

**Phase 3 — Détection (sur images)**
- `direction.py` + tests exhaustifs (8 secteurs, frontières à 22.5°, axe Y inversé, portes confondues).
- `tools/make_synthetic.py` + `doors.py` + tests sur images synthétiques (bruit, échelles différentes, faux positifs colorés).
- ✅ Fini quand : `pytest` vert, 100 % des images synthétiques bien classées.

**Phase 4 — Capture + calibration**
- `capture/screen.py`, `calibrate.py` (ouvre une capture, l'utilisateur clique sur la porte orange puis la bleue → on calcule et sauvegarde les plages HSV ; option pour découper des templates).
- ✅ Fini quand : F10 sur `fake_game.py` affichant une image synthétique donne la bonne direction dans la barre de statut.

**Phase 5 — Pont vers le site**
- `bridge/site.py` : envoi de la touche numpad, scroll vers la section, gestion d'erreur. Mode auto optionnel.
- ✅ Fini quand : F10 → la page sélectionne la bonne direction toute seule.

**Phase 6 — Interface graphique**
- `gui/` complet selon §6.5 : fenêtre de contrôle, onglets, `HotkeyEdit`, assistant de calibration, test de détection sur image avec aperçu annoté, thème sombre, réduction dans le tray, instance unique.
- ✅ Fini quand : on peut tout régler depuis la GUI sous Linux sans ouvrir `config.toml`, et chaque réglage s'applique en direct et survit à un redémarrage.

**Phase 7 — Packaging (préparé sous Linux)**
- `packaging/AniimoOverlay.spec`, `version_info.txt`, `build_windows.ps1`, workflow GitHub Actions, `resource_path()`, splash screen, icône `.ico`.
- ✅ Fini quand : le workflow GitHub Actions produit un `AniimoOverlay.exe` téléchargeable en artifact.

**Phase 8 — Portage et validation Windows** (fait par l'utilisateur sur sa machine avec Aniimo)
- `clickthrough.py` WinAPI, DPI, `game_window.py`, tests avec le vrai jeu en borderless, calibration sur vraies captures.
- Ajouter les vraies captures de la carte en jeu dans `tests/fixtures/real/` avec le nom de la direction attendue (`ne_01.png`…) et un test paramétré dessus.
- ✅ Fini quand : **l'exe unique** tourne sur Windows par-dessus Aniimo, détecte le plan, F8 masque/affiche, et passe le test d'acceptation du §8.1.

**Plus tard (seulement si demandé)**
- Départager deux plans de même direction (distance entre portes / forme de la carte) → mais **en indiquant au site** quel candidat choisir, pas en recopiant ses données.
- Détecter automatiquement que la carte du jeu est ouverte (`map_state.py`).
- Détecter la difficulté.

## 12. Conventions

- Typage partout (`from __future__ import annotations`), dataclasses pour les résultats.
- `logging` (pas de `print`), fichier de log dans `platformdirs.user_log_dir`. Niveau DEBUG avec `--debug`.
- Option `--debug-detection` qui sauvegarde l'image capturée + les masques HSV + le résultat annoté dans le dossier de log (pour diagnostiquer sous Windows).
- Messages visibles par l'utilisateur en **français**.
- Pas de dépendance ajoutée sans la justifier à l'utilisateur.
- Commits petits et fréquents, message en anglais au présent (`Add HSV door detection`).

## 13. Commandes utiles

```bash
python -m venv .venv && source .venv/bin/activate      # Windows : .venv\Scripts\activate
pip install -e ".[dev]"
python -m aniimo_overlay                 # lancer
python -m aniimo_overlay --debug         # logs détaillés
python -m aniimo_overlay.detection.calibrate path/to/capture.png
python tools/make_synthetic.py --out tests/fixtures/synthetic
python tools/fake_game.py tests/fixtures/synthetic/ne_01.png
pytest -q
ruff check . && ruff format .
QTWEBENGINE_REMOTE_DEBUGGING=9222 python -m aniimo_overlay   # DevTools de la vue web

# Windows uniquement : build de l'exe unique
powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1
# -> dist\AniimoOverlay.exe

# Depuis Linux : pousser un tag pour que GitHub Actions construise l'exe
git tag v0.1.0 && git push origin v0.1.0
```

## 14. Questions ouvertes (à confirmer avec l'utilisateur au moment voulu)

- Titre exact de la fenêtre du jeu sous Windows.
- Apparence réelle des portes orange/bleue sur la carte en jeu (couleurs, taille, icône) → besoin de captures d'écran.
- La carte du jeu est-elle une carte plein écran ou une minicarte ? Est-elle orientée nord en haut ?
- L'auteur d'aniimotools.dev a-t-il donné son accord / propose-t-il un mode embed ?
