# Rapport de projet — Aniimo Overlay

> À donner à une nouvelle session (avec `CLAUDE.md`, qui reste la référence du brief).
> État au **2026-10-07**, version `0.1.0`. Ce rapport dit ce qui est fait, ce qui a été
> décidé et pourquoi, ce qui reste à valider sous Windows.

## 1. Contexte et préférences de l'utilisateur

- Échanges en **français** ; code, commits et commentaires en anglais.
- L'utilisateur développe sous **Linux (Ubuntu 24.04, Hyprland = Wayland pur)**, mais
  **tous les tests réels se feront sous Windows** (Aniimo ne tourne pas sous Linux).
  Sous Linux on ne valide que : tests unitaires, lint, lancement *offscreen*.
- GUI : **comme décrit dans `CLAUDE.md`** (en-tête + 5 onglets), avec un style
  **sobre et épuré**.
- Phases 0 → 7 enchaînées d'une traite ; la phase 8 (Windows + vrai jeu) est faite par
  l'utilisateur.
- Git : dépôt local initialisé, **pas encore de remote GitHub** (à créer pour la phase 7).
- Pas encore de captures du jeu, titre de fenêtre inconnu (défaut `Aniimo`), forme de la
  carte en jeu inconnue (hypothèse : plein écran, nord en haut).

## 2. État par phase

| Phase | État | Vérifié comment |
|---|---|---|
| 0 Squelette | ✅ | `python -m aniimo_overlay` ouvre la page |
| 1 Overlay | ✅ code | offscreen : fenêtre, opacité, zoom, géométrie sauvegardée/restaurée |
| 2 Hotkeys + modes | ✅ code | listener pynput démarre ; click-through **non testable ici** (Wayland) |
| 3 Détection | ✅ | 154 tests verts, 100 % des images synthétiques bien classées |
| 4 Capture + calibration | ✅ code | capture mss OK ; assistant GUI + CLI |
| 5 Pont site | ✅ | testé sur la vraie page (offscreen) : la touche pavé num. fonctionne |
| 6 GUI | ✅ | captures d'écran offscreen des 5 onglets |
| 7 Packaging | ✅ préparé | build onefile **Linux** OK + contenu QtWebEngine vérifié ; build Windows à lancer via GitHub Actions |
| 8 Windows | ⏳ | à faire par l'utilisateur (checklist §6) |

Commits : `git log --oneline` (5 commits, du cœur de détection à la documentation).

## 3. Architecture réelle (écarts au plan de `CLAUDE.md`)

Arborescence conforme à `CLAUDE.md` §5, à la racine du dossier `aniimo-interactiv-card/`.
Fichiers **ajoutés** par rapport au plan :

| Fichier | Rôle | Pourquoi |
|---|---|---|
| `src/aniimo_overlay/paths.py` | dossiers platformdirs + `resource_path()` (gère `sys._MEIPASS`) | centraliser les chemins |
| `src/aniimo_overlay/detect_task.py` | `QRunnable` capture + détection, `DetectionOutcome`, dumps debug | garder `app.py` lisible |
| `src/aniimo_overlay/detection/annotate.py` | dessine portes + flèche (aperçu GUI, debug) | pur OpenCV |
| `src/aniimo_overlay/gui/tab_site.py` | onglet Site (§6.5 le demande, absent de l'arborescence) | |
| `src/aniimo_overlay/resources/check.svg` | coche des cases à cocher du thème | |
| `tools/make_icon.py` | dessine `app.png`, `app.ico`, `packaging/splash.png` | icône créée par nous |
| `packaging/entry.py` | point d'entrée PyInstaller | |
| `packaging/check_exe.py` | vérifie que l'exe contient QtWebEngine | demandé par §8.1 |
| `tests/test_hotkeys.py`, `tests/conftest.py` | conversion touches Qt → pynput, conflits, URLs | |

`detection/map_state.py` est un **stub** (renvoie `None`), prévu « plus tard ».

## 4. Décisions prises (et pourquoi)

- **Pas de `pywin32`** : tout le WinAPI passe par `ctypes` (aucune dépendance en plus).
- **Cache HTTP en mémoire seulement** (`MemoryHttpCache`) : cookies et localStorage
  persistants (préférences, consentement, connexion Patreon), mais aucune image du site
  écrite sur disque (§3.1 « pas de cache disque »).
- **Exclusion de capture** : l'overlay et la fenêtre de contrôle appellent
  `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)` (Windows 10 2004+), sinon la
  détection verrait les portes **dessinées par le site** dans l'overlay. Si l'API échoue
  (ou hors Windows), leurs rectangles sont **noircis** dans la capture.
  Effet de bord : l'overlay n'apparaît pas dans OBS / captures d'écran (documenté README).
- **Mode passif Windows** : `WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW` +
  `WS_EX_NOACTIVATE` (pour ne pas voler le focus du jeu à l'affichage). Le click-through
  est réappliqué après chaque changement d'opacité (Qt réécrit le style layered).
- **Splash** : `pyi_splash` (s'affiche pendant la décompression, avant Python). Le spec
  le désactive automatiquement si Tcl/Tk manque (cas du build Linux).
- **Détection manuelle (F10)** : envoie la direction au site dès que les deux portes sont
  trouvées, même sous le seuil (la confiance est affichée). **Auto** : seuil + 2 captures
  identiques + n'envoie que si la direction change.
- **Fichier de config** : HSV par défaut du §10 ; champ ajouté `detection.debug`.
  `capture.monitor` et `capture.roi` existent mais **ne sont pas dans la GUI**.
- **Langues du site** : liste relevée sur le site (fr, en sans préfixe d'URL, de, es,
  pt-br, ru, th, vi, zh-cn) + « Personnalisée ».
- **Recherche de la fenêtre du jeu** : titre exact > commence par > contient ; ignore nos
  fenêtres (« Aniimo Overlay… ») et les onglets de navigateur contenant « aniimotools ».

## 5. Ce qu'on sait de la page (bridge/site.py)

Inspection faite une fois (lecture des sélecteurs uniquement, rien de copié) :

- Bloc « Quel plan ? » : `.ls-find` ; section d'ensemble : `[data-overview]`.
- Pavé de directions de la difficulté courante : `[data-pad]:not([hidden])`, un bouton
  par direction `[data-dir="N|NE|E|SE|S|SW|W|NW"]` (`disabled` si aucun plan,
  `aria-pressed="true"` si sélectionné). Mêmes codes que `detection/direction.py`.
- Raccourci clavier du site : écoute `keydown` sur `document`, utilise `e.key` ("8"…),
  **seulement en vue d'ensemble** et si la section est visible → on fait défiler avant.
- Si une direction n'a **qu'un plan**, le site **ouvre directement ce plan** (la vue
  d'ensemble est alors masquée). Retour : bouton `[data-back]`.
- Rappuyer sur une direction déjà sélectionnée (plusieurs plans) la **désélectionne**.

Algorithme de `SiteBridge.select_direction()` :
1. lit l'état du bouton (JSON) ; si un plan est ouvert → clic sur `[data-back]` puis
   recommence ;
2. défile jusqu'à `.ls-find`, puis envoie la **vraie frappe** pavé num.
   (`QKeyEvent` + `KeypadModifier` au `focusProxy()`) ;
3. succès si le bouton est pressé ou si le site a ouvert le plan ; sinon 2e frappe
   (cas « déjà sélectionné → désélectionné ») ; en dernier recours, clic JS sur le bouton.

Testé sur la vraie page (offscreen) avec NE, N, N, S, S, W : toujours le bon résultat,
**sans** passer par le clic de secours. `runJavaScript` ne renvoie pas les objets JS en
PySide6 → on passe par `JSON.stringify`.

Tous les sélecteurs sont dans la constante `SELECTORS` (commentée « peut casser »).

## 6. Checklist de validation Windows (phase 8)

1. Créer un dépôt GitHub (privé conseillé), `git remote add origin …`, `git push -u origin master`.
2. Onglet Actions → *Build Windows exe* → *Run workflow*. Récupérer l'artifact.
   Si l'étape « Check QtWebEngine files » échoue, regarder la liste qu'elle affiche.
3. Sur une machine **sans Python** : double-clic → splash → fenêtre de contrôle.
4. F8 : l'overlay apparaît par-dessus le jeu en **borderless**, sans voler le focus.
5. Mode passif : les clics vont bien au jeu. F9 : barre + liseré, déplacement /
   redimensionnement OK. Relancer → même position.
6. Opacité / zoom au clavier ; F8 / F9 / F10 **pendant que le jeu a le focus**.
7. Relever le **titre exact de la fenêtre du jeu** (voyant « Jeu » de l'en-tête) et le
   mettre dans l'onglet Détection.
8. Ouvrir la carte en jeu → « Tester sur l'écran actuel ». Si raté → « Calibrer ».
   Activer « Mode debug détection » et récupérer les images dans le dossier des logs.
9. Faire des **captures de la carte en jeu** et les placer dans `tests/fixtures/real/`
   nommées `<direction>_<nn>.png` (ex. `ne_01.png`) → ajouter le test paramétré (non
   écrit : aucune capture pour l'instant ; ces PNG sont ignorés par git).
10. Vérifier sur écran à 125 % / 150 % que la capture tombe au bon endroit (DPI).
11. Relancer l'exe alors qu'il tourne déjà → la fenêtre existante revient devant.

## 7. Points d'attention / limites connues

- **Taille de l'exe** : ~290 Mo sous Linux (QtWebEngine ≈ 200 Mo + OpenCV), sans doute
  ~200-250 Mo sous Windows ; décompression à chaque lancement → démarrage de plusieurs
  secondes. Pistes si gênant : mode `onedir` + installeur, ou exclure des modules Qt
  (QtQuick3D…) en testant que WebEngine marche toujours.
- La détection HSV n'a été réglée que sur des **images synthétiques**. Les vraies icônes
  de portes peuvent nécessiter la calibration, voire d'ajuster `DoorParams`
  (`min_circularity`, aires min/max) dans `detection/doors.py`.
- Après le mode interactif, le focus clavier reste sur l'overlay jusqu'à ce qu'on clique
  dans le jeu (on ne donne pas le focus au jeu par programme).
- `is_exclusive_fullscreen()` (SHQueryUserNotificationState) est best effort.
- Bandeau cookies du site : à accepter une fois en mode interactif (mémorisé).
- Non testé du tout ici : tout le code `win32` (ctypes), le tray Windows, le splash,
  l'instance unique sous Windows.
- Distribution publique : **demander l'accord de l'auteur** d'aniimotools.dev avant.

## 8. Environnement de dev Linux

- `python3-venv` absent sur la machine : venv créé avec
  `python3 -m venv --without-pip .venv && python3 -m pip --python .venv/bin/python install pip`.
- Smoke test sans écran : `QT_QPA_PLATFORM=offscreen python -m aniimo_overlay`
  (avec `XDG_CONFIG_HOME` etc. pointés vers un dossier temporaire pour ne pas toucher la
  vraie config).
- Versions installées : PySide6 6.11, opencv-python-headless 5.0, numpy 2.5,
  pynput 1.8, PyInstaller 6.22, Python 3.12 (le projet vise 3.11+).

## 9. Prochaines étapes possibles (seulement si demandé)

- Test paramétré sur `tests/fixtures/real/` dès que des captures existent.
- Départager deux plans de même direction (distance entre portes / forme) en le
  signalant au site, sans recopier ses données.
- `map_state.py` : détecter que la carte du jeu est ouverte.
- Choix de l'écran (`capture.monitor`) et de la ROI dans la GUI.
