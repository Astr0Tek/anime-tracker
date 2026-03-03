# 🎌 Anime Tracker

Une application de bureau en Python pour gérer ta liste d'animes — noter ceux que tu as vus, suivre ceux en cours, et organiser ta Watch Later.

---

## ✨ Fonctionnalités

- 🔍 **Recherche rapide** dans un catalogue de ~11 000 franchises d'animes, navigation au clavier (↑↓)
- ⭐ **Notation** de 0 à 5 étoiles et suivi du statut (*à jour, en cours, terminé, arrêté*)
- 🎯 **Watch Later** — liste séparée avec priorité (haute / normale / basse), et transfert en un clic vers le tracker
- 🔄 **Catalogue auto-généré** depuis la base de données [anime-offline-database](https://sourceforge.net/projects/anime-offline-database.mirror/files/) au premier lancement
- 💾 **Export .txt** de la liste notée et de la Watch Later

---

## 📁 Fichiers nécessaires

Tous les fichiers doivent être dans le **même dossier** :

| Fichier | Description |
|--------|-------------|
| `liste.py` | Application principale (à lancer) |
| `catalogue.py` | Script de génération du catalogue |
| `anime-offline-database-minified.json` | Base de données des animes ([télécharger ici](https://sourceforge.net/projects/anime-offline-database.mirror/files/)) |
| `catalogue.json` | Généré automatiquement au premier lancement |
| `animes.json` | Créé automatiquement — sauvegarde ta liste notée |
| `wishlist.json` | Créé automatiquement — sauvegarde ta Watch Later |

---

## 🚀 Installation

### 1. Cloner le dépôt

```bash
git clone https://github.com/TON_PSEUDO/anime-tracker.git
cd anime-tracker
```

### 2. Télécharger la base de données

Télécharge `anime-offline-database-minified.json` depuis :
👉 [https://sourceforge.net/projects/anime-offline-database.mirror/files/](https://sourceforge.net/projects/anime-offline-database.mirror/files/)

Place le fichier dans le même dossier que `liste.py`.

### 3. Lancer l'application

```bash
python liste.py
```

> Python 3.8+ requis. Aucune dépendance externe — uniquement la bibliothèque standard Python (`tkinter`, `json`, `subprocess`…).

---

## 🗂️ Structure du projet

```
anime-tracker/
├── liste.py                              # Application principale
├── catalogue.py                          # Générateur de catalogue
├── anime-offline-database-minified.json  # Base de données (à télécharger)
├── catalogue.json                        # Auto-généré
├── animes.json                           # Auto-généré
└── wishlist.json                         # Auto-généré
```

---

## 📜 Licence

Ce projet est libre d'utilisation. La base de données anime est fournie par [manami-project](https://sourceforge.net/projects/anime-offline-database.mirror/files/).
