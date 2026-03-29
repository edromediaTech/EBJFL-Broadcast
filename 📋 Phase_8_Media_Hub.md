# 📋 Feuille de Route - Phase 8 : Media Hub & Multi-Device Upload

## Objectif
Transformer le PC de régie en serveur de stockage centralisé permettant à n'importe quel appareil (tablette, téléphone, clé USB) d'uploader et projeter des médias (PowerPoint, images, vidéos, PDF, textes) en temps réel via OBS.

---

## 🏗️ Architecture

```
Tablette/Téléphone                    PC Régie                        OBS Studio
     │                                    │                               │
     ├─ Upload fichier ──────────►  POST /upload-media                    │
     │                                    │                               │
     │                              ┌─────▼──────┐                        │
     │                              │ Traitement  │                        │
     │                              │ - PPTX→PNG  │                        │
     │                              │ - PDF→IMG   │                        │
     │                              │ - Stockage  │                        │
     │                              └─────┬──────┘                        │
     │                                    │                               │
     ├─ "Projeter" ──────────────►  WebSocket broadcast ──────────► Overlay HTML
     │                                    │                               │
     ├─ "Slide suivante" ────────►  WebSocket broadcast ──────────► Overlay HTML
     │                                    │                               │
     └─ Preview en temps réel ◄──── GET /media/list                       │
```

---

## 📦 Étape 1 : Endpoint d'Upload (Semaine 1)

### 1.1 Route d'upload multi-fichiers
- [ ] `POST /upload-media` acceptant `multipart/form-data`
- [ ] Validation des types : `.pptx`, `.pdf`, `.txt`, `.jpg`, `.png`, `.gif`, `.mp4`, `.webm`
- [ ] Limite de taille configurable (défaut : 200 MB)
- [ ] Stockage dans `assets/uploads/` avec sous-dossiers par date (`2026-03-28/`)
- [ ] Réponse JSON avec URL, type, taille, prévisualisation

### 1.2 Gestionnaire de fichiers
- [ ] `GET /media/list` : Liste tous les fichiers uploadés avec métadonnées
- [ ] `GET /media/{id}/preview` : Prévisualisation (thumbnail)
- [ ] `DELETE /media/{id}` : Suppression
- [ ] Nettoyage automatique des fichiers > 30 jours (configurable)

### 1.3 Servir les fichiers statiques
- [ ] Monter `assets/uploads/` comme route statique FastAPI
- [ ] Support CORS pour accès depuis les tablettes

### Dépendances à ajouter
```
python-pptx>=0.6.23
Pillow>=10.0
pdf2image>=1.17.0    # nécessite poppler-utils
comtypes>=1.4.1      # Windows uniquement, pour conversion PPTX native
```

---

## 📦 Étape 2 : Conversion PowerPoint (Semaine 1-2)

### 2.1 Option A — Conversion en images (prioritaire)
- [ ] À l'upload d'un `.pptx`, extraire chaque slide en PNG 1920x1080
- [ ] Utiliser `python-pptx` + `Pillow` pour la conversion de base
- [ ] Fallback `comtypes` (Windows) pour ouvrir PowerPoint en COM et exporter en haute qualité
- [ ] Stocker les images dans `assets/uploads/{nom_fichier}/slide_001.png`, `slide_002.png`, etc.
- [ ] Générer un manifest JSON : `{slides: [{index, url, notes}], total: N}`
- [ ] Générer une thumbnail de la première slide pour la preview

### 2.2 Option B — Capture de fenêtre PowerPoint (optionnel, Phase ultérieure)
- [ ] Lancer PowerPoint en mode diaporama via `subprocess`
- [ ] Utiliser `pywinauto` pour simuler les touches (Flèche droite/gauche, Échap)
- [ ] Capturer la fenêtre via OBS (source "Capture de fenêtre")
- [ ] Commandes : `POST /pptx/start`, `POST /pptx/next`, `POST /pptx/prev`, `POST /pptx/stop`

### 2.3 Conversion PDF
- [ ] Convertir chaque page en image PNG via `pdf2image` / `Pillow`
- [ ] Même structure de stockage que PPTX (`slide_001.png`, etc.)

---

## 📦 Étape 3 : Interface Web "Médias" (Semaine 2)

### 3.1 Nouvel onglet "Médias" sur la tablette (`remote.html`)
- [ ] Zone de drag-and-drop pour uploader des fichiers
- [ ] Bouton "Parcourir" classique en fallback
- [ ] Barre de progression d'upload
- [ ] Grille de prévisualisation des fichiers sur le serveur (thumbnails)
- [ ] Filtrage par type (Images, PPTX, PDF, Vidéos, Tous)
- [ ] Indicateur de fichier en cours de conversion (spinner)

### 3.2 Contrôle de projection média
- [ ] Clic sur un fichier → Preview plein écran sur la tablette
- [ ] Bouton "Projeter" → Envoie vers l'overlay OBS
- [ ] Pour les PPTX/PDF (multi-slides) :
  - Barre de navigation : ◀ Précédent | Slide 3/12 | Suivant ▶
  - Grille de toutes les slides (vue miniatures) pour saut direct
  - Bouton "Écran noir" entre les slides
- [ ] Pour les vidéos :
  - Play / Pause / Stop
  - Barre de progression avec seek
  - Contrôle du volume
- [ ] Pour les images :
  - Projeter / Masquer
  - Option "fond d'écran" (derrière les paroles)

### 3.3 QR Code pour upload invité
- [ ] Génération d'un QR Code sur le dashboard PyQt6 (module `qrcode`)
- [ ] Le QR Code pointe vers `http://<IP>:8000/static/upload.html`
- [ ] Page d'upload simplifiée pour les invités (juste un bouton "Envoyer mon fichier")
- [ ] Notification en temps réel sur le dashboard quand un fichier arrive

---

## 📦 Étape 4 : Dashboard PyQt6 "Médias" (Semaine 2-3)

### 4.1 Nouvel onglet "Médias" sur le desktop
- [ ] Liste des fichiers uploadés avec icônes par type
- [ ] Double-clic → Preview
- [ ] Boutons : Projeter, Supprimer, Renommer
- [ ] Drag-and-drop depuis l'explorateur Windows
- [ ] Indicateur de conversion en cours

### 4.2 Contrôle PPTX/PDF
- [ ] Vue miniatures de toutes les slides
- [ ] Navigation slide par slide avec raccourcis clavier (Flèches)
- [ ] Preview sur l'écran secondaire avant projection

### 4.3 QR Code invité
- [ ] Widget QR Code dans l'onglet Connexion
- [ ] Taille configurable
- [ ] Affichable en plein écran pour scanner facile

---

## 📦 Étape 5 : Overlay OBS enrichi (Semaine 3)

### 5.1 Support des nouveaux types de médias
- [ ] Projection d'images plein écran avec transitions
- [ ] Diaporama PPTX : affichage slide par slide avec animation fade
- [ ] Lecture vidéo intégrée (play/pause/seek via WebSocket)
- [ ] Affichage PDF page par page
- [ ] Texte long avec défilement automatique (vitesse configurable)

### 5.2 Transitions entre slides
- [ ] Fondu enchaîné (crossfade)
- [ ] Glissement (slide left/right)
- [ ] Aucune (cut direct)
- [ ] Configurable depuis la tablette

---

## 📦 Étape 6 : Gestion avancée des fichiers (Semaine 3-4)

### 6.1 Organisation
- [ ] Dossiers/catégories : Prédications, Annonces, Fonds, Vidéos, Archives
- [ ] Favoris / fichiers épinglés
- [ ] Recherche par nom de fichier

### 6.2 Optimisation
- [ ] Compression automatique des images > 5 MB
- [ ] Conversion vidéo en format web-compatible (H.264/WebM) si nécessaire
- [ ] Cache des thumbnails pour chargement rapide

### 6.3 Intégration au Planning
- [ ] Ajouter un média comme élément du service (type "media")
- [ ] Pré-charger les médias du service en cache au démarrage
- [ ] Bouton "GO LIVE" qui enchaîne automatiquement les éléments

---

## 🎯 Scénario d'utilisation cible

```
Dimanche matin, 8h30 :
1. Le technicien lance EBJFL-Broadcast → le serveur démarre
2. Le QR Code s'affiche à l'écran

8h45 :
3. Un invité arrive avec son diaporama sur son téléphone
4. Il scanne le QR Code → page d'upload s'ouvre
5. Il sélectionne son .pptx → upload en cours (barre de progression)
6. Le PC convertit automatiquement les slides en PNG

8h50 :
7. Le technicien voit "Nouveau fichier : Predication_Pasteur_X.pptx (12 slides)"
8. Il clique → preview des miniatures
9. Il l'ajoute au planning du service

9h00 - Culte :
10. Le technicien suit le planning : chant → verset → chant → prédication
11. Au moment de la prédication, il clique "Projeter"
12. Les slides s'affichent sur le vidéoprojecteur via OBS
13. Le pasteur avance lui-même les slides depuis sa tablette
14. Fin → retour aux chants en un clic
```

---

## 📊 Endpoints API à créer

| Méthode | Route | Description |
|---------|-------|-------------|
| `POST` | `/upload-media` | Upload d'un fichier |
| `GET` | `/media/list` | Liste des fichiers avec métadonnées |
| `GET` | `/media/{id}` | Détails d'un fichier |
| `GET` | `/media/{id}/preview` | Thumbnail/preview |
| `DELETE` | `/media/{id}` | Suppression |
| `POST` | `/media/{id}/project` | Projeter un fichier |
| `POST` | `/media/slides/next` | Slide suivante (PPTX/PDF) |
| `POST` | `/media/slides/prev` | Slide précédente |
| `POST` | `/media/slides/goto/{n}` | Aller à la slide N |
| `GET` | `/media/slides/state` | État du diaporama en cours |
| `POST` | `/pptx/start` | Lancer PowerPoint natif (Option B) |
| `POST` | `/pptx/stop` | Arrêter PowerPoint |

---

## 📅 Planning estimé

| Semaine | Tâches | Livrable |
|---------|--------|----------|
| **S1** | Upload + conversion PPTX/PDF + stockage | Fichiers uploadables et convertis |
| **S2** | Interface tablette Médias + contrôle slides | Projection depuis mobile |
| **S3** | Dashboard PyQt6 + overlay enrichi + QR Code | Expérience complète desktop |
| **S4** | Organisation fichiers + intégration planning + tests live | Prêt pour production |

---

## ⚠️ Points d'attention

- **Performance** : La conversion PPTX peut prendre 5-15 secondes selon le nombre de slides. Afficher un spinner.
- **Stockage** : Prévoir 500 MB - 1 GB pour les fichiers. Nettoyage automatique recommandé.
- **Réseau** : Upload de gros fichiers (vidéos) nécessite un bon WiFi local. Limiter à 200 MB par défaut.
- **Sécurité** : Valider les types de fichiers côté serveur. Pas d'exécution de fichiers uploadés.
- **Latence** : La navigation slides doit rester < 200ms (images pré-chargées en mémoire).
