# Montage-Video

Outil en ligne de commande pour automatiser les tâches répétitives du montage
vidéo : découpe, assemblage, suppression automatique des silences, export aux
formats YouTube / Shorts / Instagram, et montages complets décrits dans un
simple fichier YAML. Tout est basé sur [FFmpeg](https://ffmpeg.org).

## Installation

```bash
pip install -e .                # installe la commande `montage`
pip install -e ".[ffmpeg]"      # + un FFmpeg intégré si vous ne l'avez pas
```

FFmpeg est recherché dans cet ordre : variable `MONTAGE_FFMPEG`, commande
`ffmpeg` du PATH, puis le paquet `imageio-ffmpeg`.

## Commandes

| Commande | Rôle |
|---|---|
| `montage info video.mp4` | Durée, résolution, cadence, présence d'audio |
| `montage couper video.mp4 -d 1:05 -t 2:30` | Extraire un passage |
| `montage assembler a.mp4 b.mp4 c.mp4 -o final.mp4` | Mettre des vidéos bout à bout (résolutions différentes acceptées) |
| `montage silences video.mp4` | Couper automatiquement les blancs (jump cuts) |
| `montage exporter video.mp4 -f shorts --adaptation crop` | Convertir vers un autre format |
| `montage projet projet.yaml` | Rendre un montage complet décrit en YAML |
| `montage formats` | Lister les formats disponibles |

Options communes de rendu : `-f/--format`, `--adaptation pad|crop`,
`--rapide` (encodage plus rapide). `montage <commande> --help` détaille
chaque commande.

### Supprimer les silences

Idéal pour les vidéos face caméra, tutoriels ou podcasts :

```bash
montage silences rush.mp4 --analyser        # voir les silences détectés
montage silences rush.mp4 -o propre.mp4     # générer la vidéo sans les blancs
```

Réglages : `--seuil -35` (dB ; plus bas = seuls les vrais silences sont
coupés), `--duree-min 0.6` (silences plus courts ignorés), `--marge 0.15`
(respiration gardée autour de la parole).

### Projet YAML

Voir [`exemples/projet.yaml`](exemples/projet.yaml) : liste de clips avec
points d'entrée/sortie, format de sortie, fondus et musique de fond (volume
réglable, bouclée et fondue en fin de vidéo).

```bash
montage projet exemples/projet.yaml
montage projet exemples/projet.yaml -o test.mp4   # autre fichier de sortie
```

## Formats

| Nom | Résolution | Usage |
|---|---|---|
| `source` | celle du 1er clip | défaut |
| `youtube` | 1920×1080 | YouTube 16:9 |
| `youtube-4k` | 3840×2160 | YouTube 4K |
| `shorts` | 1080×1920 | Shorts, TikTok, Reels |
| `instagram` | 1080×1080 | carré |
| `instagram-portrait` | 1080×1350 | 4:5 |
| `brouillon` | 1280×720 | relecture rapide |

Sortie : H.264 + AAC, MP4 optimisé pour le web (`+faststart`).

## Tests

```bash
pip install -e ".[test]"
pytest
```

Les tests génèrent leurs propres vidéos avec FFmpeg, aucun média n'est requis.
