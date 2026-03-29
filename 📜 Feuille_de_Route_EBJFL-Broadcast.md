📜 Feuille de Route : EBJFL-Broadcast
Nom du Projet : EBJFL-Broadcast

Nature : Application Hybride de Régie Live (Desktop + Web + Mobile)

Objectif : Piloter OBS Studio, gérer les Lower Thirds, la projection biblique et intégrer l'IA pour le STT (Speech-to-Text) et la recherche sémantique.

🏗️ 1. Architecture du Système
L'application repose sur un modèle Hub-and-Spoke :

Core (Python/FastAPI) : Le cerveau installé sur le PC de régie. Il gère la logique, la base de données, et les connexions OBS.

Desktop UI (PyQt6) : L'interface d'administration locale pour le technicien principal.

Remote UI (Web/Mobile) : Interface tactile pour tablettes et smartphones (contrôle déporté).

Overlay (HTML/CSS/JS) : La source "Navigateur" dans OBS qui affiche les animations.

🛠️ 2. Stack Technique (Spécifications pour l'Agent)
Langage : Python 3.11+

Framework Desktop : PyQt6

Framework Web/API : FastAPI + Uvicorn

Communication OBS : obs-websocket-py (v5.x)

Base de Données : SQLite + ChromaDB (pour la recherche IA)

IA (STT) : Deepgram SDK ou Faster-Whisper

IA (Sémantique) : Sentence-Transformers (Local) ou OpenAI API

Temps Réel : WebSockets (pour la synchro entre tous les terminaux)

🚀 3. Phases de Développement
Phase 1 : Fondations & Connectivité (MVP)
[ ] Structure du projet : Mise en place de l'arborescence (folders: core/, ui/, web/, assets/).

[ ] Serveur FastAPI : Lancement du serveur en arrière-plan de PyQt6.

[ ] Pont OBS : Création du module de connexion automatique à obs-websocket.

[ ] Dashboard PyQt6 : Fenêtre principale affichant le statut de la connexion (OBS, Internet, Clients Web).

Phase 2 : Gestion des Contenus (Lower Thirds & Bible)
[ ] Module Lower Thirds : CRUD (Créer, Lire, Mettre à jour, Supprimer) pour les noms et titres des intervenants.

[ ] Module Biblique : Importation de la Bible (LSG/KJV) en SQLite.

[ ] Interface de contrôle : Boutons sur le PC et la tablette pour "Lancer" ou "Retirer" un texte.

Phase 3 : L'Intelligence Artificielle
[ ] Recherche Sémantique : Intégration de l'IA pour trouver un verset par thème (ex: "Versets sur la paix") via des embeddings.

[ ] Sous-titrage Live (STT) : * Capture du flux audio local.

Envoi en streaming vers le moteur STT.

Récupération et envoi immédiat vers l'Overlay OBS.

[ ] Traduction Instantanée (Optionnel) : Utiliser l'IA pour traduire les paroles en temps réel.

Phase 4 : Interface Hybride & Mobilité
[ ] Web Remote : Création d'une interface responsive en HTML/JS pour tablettes.

[ ] Générateur de QR Code : Affichage d'un QR Code sur l'app PyQt6 pour connecter instantanément les smartphones au réseau local.

[ ] Système de Preview : Permettre de voir le texte sur la tablette avant de le pousser sur le live.

Phase 5 : Overlay & Animations (Le Rendu)
[ ] Dynamic Graphics : Création d'une page HTML overlay.html utilisant GSAP pour des animations fluides.

[ ] Themes : Possibilité de changer les couleurs (ex: Thème Culte, Thème Mariage, Thème Conférence) depuis la tablette.

📋 4. Spécifications des Endpoints API (pour l'agent)
L'agent doit implémenter les routes suivantes dans FastAPI :

GET /bible/search?q=... : Recherche classique et IA.

POST /obs/lower-third : Envoie les données vers l'overlay.

WS /ws/live : WebSocket pour synchroniser l'état du live entre tous les appareils.

🔒 5. Sécurité & Réseau
Local-Only : Par défaut, l'API ne doit être accessible que sur le réseau local de l'EBJFL.

Auto-Détection : Utilisation de zeroconf pour que les tablettes trouvent le serveur sans taper l'IP (optionnel mais recommandé).

📅 6. Jalons (Milestones)
Semaine 1 : Connexion Python <-> OBS fonctionnelle et affichage d'un texte simple.

Semaine 2 : Interface tablette opérationnelle pour l'édition de texte.

Semaine 3 : Intégration du moteur STT pour le sous-titrage auto.

Semaine 4 : Tests intensifs en condition de live à l'EBJFL.

Note pour l'Agent Codeur : Priorise la stabilité de la connexion WebSocket. En environnement live, la latence doit être inférieure à 200ms pour les commandes manuelles et 1s pour le STT.