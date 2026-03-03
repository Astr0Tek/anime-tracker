import json
import re
from pathlib import Path

INPUT  = Path("anime-offline-database-minified.json")
OUTPUT = Path("catalogue.json")

# ---------------------------------------------------------------------------
# Suffixes à retirer en FIN de titre pour trouver la franchise racine
# On applique en boucle jusqu'à stabilisation
# ---------------------------------------------------------------------------
SUFFIX_RE = re.compile(
    r"""(?ix)
    \s*
    \b(
        season\s*\d*                 |
        final\s+season               |
        the\s+final                  |
        part\s*\d+                   |
        cour\s*\d+                   |
        \d+(st|nd|rd|th)\s+season    |
        movie\s*\d+                  |
        the\s+movie                  |
        film\s+\d+                   |
        chapter\s*\d+                |
        chapters                     |
        ova | ona | special\s*\d*    |
        # Chiffres romains seulement s'ils sont SEULS en fin (II, III… mais pas I seul)
        \b(II|III|IV|V[I]{0,3}|IX|X[I]{0,3})\b   |
        # Numéro arabe seul en fin
        (?<!\w)\d+(?!\w)
    )\s*$
    """,
)

# Coupe les sous-titres :
#   - séparateur entouré d'espaces  "SNK - Final Season"
#   - deux-points SANS espace avant "One Piece: Stampede"  (mais PAS Re:Zero, Re:Creators…)
#     → on accepte ":" seulement s'il est précédé d'au moins 4 caractères non-deux-points
#       (évite de couper "Re:Zero" dont le préfixe fait 2 chars)
SUBTITLE_RE = re.compile(r"(?:\s+[:\-–—]\s+|(?<=\w{4}):\s+)")


def ntype(t):
    return (t or "").lower().replace("_", " ").strip()


def clean_base(title: str) -> str:
    """Réduit un titre à sa franchise racine.

    Étapes :
    1. Coupe le sous-titre (ex: "SNK - The Final Season" -> "SNK")
    2. Retire en boucle les suffixes de dérivés en fin de titre
       (Season 3, Part 2, The Movie, II, 2…)
    """
    t = (title or "").strip()

    # 1) coupe sous-titre
    t = SUBTITLE_RE.split(t, 1)[0].strip()

    # 2) retire les suffixes en boucle
    while True:
        t2 = SUFFIX_RE.sub("", t).strip()
        if t2 == t:
            break
        t = t2

    return re.sub(r"\s{2,}", " ", t).strip()


def norm(s: str) -> str:
    """Clé de déduplication : minuscules, unicode normalisé, ponctuation -> espace."""
    import unicodedata
    s = (s or "").lower()
    # Normalise les caractères unicode (ū -> u, ō -> o, etc.)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s{2,}", " ", s).strip()
    return s


def iter_titles(e):
    """Retourne [titre_principal, *synonymes] dédupliqués (insensible à la casse)."""
    out = []
    t = e.get("title")
    if isinstance(t, str) and t.strip():
        out.append(t.strip())
    for s in (e.get("synonyms") or []):
        if isinstance(s, str) and s.strip():
            out.append(s.strip())
    seen, res = set(), []
    for x in out:
        k = x.casefold()
        if k not in seen:
            seen.add(k)
            res.append(x)
    return res


def words(s: str) -> list[str]:
    return norm(s).split()


# Clés à exclure de l'index : particules japonaises et mots trop génériques
# qui apparaissent dans des titres sans rapport
INVALID_KEYS = {
    "no", "wa", "ga", "wo", "ni", "de", "to", "ka", "mo", "na", "yo",
    "no", "ha", "he", "ne", "sa", "zo", "ze", "ya", "nu", "se",
    "the", "a", "an", "of", "in", "on", "at", "is", "it",
}

def is_valid_franchise_key(k: str) -> bool:
    """Rejette les clés qui sont trop courtes ou des mots grammaticaux."""
    if len(k) <= 2:
        return False
    if k in INVALID_KEYS:
        return False
    # Rejette les clés purement alphanumériques très courtes (ex: "r", "k", "f", "22")
    if re.match(r'^[\w\d]{1,2}$', k):
        return False
    return True


def build_tv_index(canonical: dict, tv_entry_count: dict) -> tuple[dict, set]:
    """
    Retourne (word_index, prefix_set) :
    - word_index : premier_mot -> [tuple_de_mots] pour le matching "contains" multi-mots
    - prefix_set : ensemble de toutes les clés TV valides (≥4 chars) pour le matching
      "starts-with" — on stocke la clé elle-même, et le test devient :
      chercher si key[:len(tv_key)] == tv_key pour les longueurs présentes dans prefix_set.
      En pratique on construit un set de (longueur, préfixe) pour un lookup O(1).
    """
    idx: dict[str, list] = {}
    # prefix_set : set de chaînes — toutes les clés TV éligibles au starts-with
    prefix_set: set[str] = set()

    for disp in set(canonical.values()):
        w = tuple(words(disp))
        if not w:
            continue
        full_key = norm(disp)
        if not is_valid_franchise_key(full_key):
            continue
        if len(w) == 1:
            if tv_entry_count.get(full_key, 0) < 2:
                continue

        # Index word pour contains multi-mots
        idx.setdefault(w[0], []).append(w)

        # Index préfixe : clés de ≥4 chars pour le starts-with
        if len(full_key) >= 4:
            prefix_set.add(full_key)

    for k in idx:
        idx[k].sort(key=len, reverse=True)

    return idx, prefix_set


def movie_belongs_to_tv(movie_titles: list, tv_keys: set, tv_index: dict, prefix_set: set) -> bool:
    """
    Retourne True si le film appartient à une franchise TV.

    Trois stratégies, toutes O(1) ou O(len(titre)) :
    1. Match exact  : norm(clean_base(titre)) est une clé TV connue
    2. Starts-with  : norm(clean_base(titre)) commence par une clé TV (≥4 chars)
       → lookup O(1) via prefix_set en testant les sous-chaînes jusqu'au prochain espace
    3. Contains multi-mots : le titre contient une franchise TV ≥2 mots (word_index)
    """
    for title in movie_titles:
        base = clean_base(title)
        key  = norm(base)

        # Stratégie 1 : match exact
        if key and key in tv_keys:
            return True

        # Stratégie 2 : starts-with O(1)
        # On extrait tous les préfixes de `key` jusqu'aux espaces et on cherche dans prefix_set
        if len(key) >= 4:
            i = key.find(" ")
            while i != -1:
                prefix = key[:i]
                if len(prefix) >= 4 and prefix in prefix_set:
                    return True
                i = key.find(" ", i + 1)

        # Stratégie 3 : contains multi-mots
        mw = words(title)
        if not mw:
            continue
        for i, w0 in enumerate(mw):
            for cand in tv_index.get(w0, []):
                if len(cand) < 2:
                    continue
                L = len(cand)
                if i + L <= len(mw) and tuple(mw[i:i+L]) == cand:
                    return True
    return False


def register(franchises: dict, key: str, disp: str):
    """Enregistre une franchise seulement si la clé n'existe pas encore."""
    if key and key not in franchises:
        franchises[key] = disp


# ---------------------------------------------------------------------------
# Union-Find minimaliste pour regrouper les franchises TV
# ---------------------------------------------------------------------------
class UF:
    def __init__(self):
        self.parent: dict[str, str] = {}

    def add(self, x: str):
        if x not in self.parent:
            self.parent[x] = x

    def find(self, x: str) -> str:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]  # path compression
            x = self.parent[x]
        return x

    def union(self, a: str, b: str):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            # On garde comme racine celui qui vient en premier (ordre alpha)
            if ra < rb:
                self.parent[rb] = ra
            else:
                self.parent[ra] = rb


def main():
    db   = json.loads(INPUT.read_text(encoding="utf-8"))
    data = db["data"]

    # ------------------------------------------------------------------
    # Passe 1 : union-find sur toutes les entrées TV
    #
    # Pour chaque entrée TV, tous ses titres/synonymes (nettoyés) sont
    # fusionnés dans le même groupe.  À la fin on choisit un display
    # par groupe = le titre nettoyé le plus court (ou le premier alpha).
    # ------------------------------------------------------------------
    uf = UF()
    # node_display[key] = meilleur display candidat pour ce nœud
    node_display: dict[str, str] = {}

    for e in data:
        if ntype(e.get("type")) != "tv":
            continue
        titles = iter_titles(e)
        if not titles:
            continue

        keys = []
        displays = []
        for t in titles:
            base = clean_base(t)
            k    = norm(base)
            if not k:
                continue
            uf.add(k)
            keys.append(k)
            displays.append(base)

        if not keys:
            continue

        # Le display candidat pour cette entrée = titre principal nettoyé (index 0)
        main_key  = keys[0]
        main_disp = displays[0]

        # N'enregistre le display que si ce nœud n'en a pas encore
        if main_key not in node_display:
            node_display[main_key] = main_disp

        # Fusionne tous les synonymes dans le même groupe
        for i in range(1, len(keys)):
            uf.union(main_key, keys[i])

    # Construit franchises : racine -> display canonique du groupe
    # Priorité : display du nœud qui EST la racine (il a été enregistré en premier dans son groupe)
    group_display: dict[str, str] = {}
    for k, disp in node_display.items():
        root = uf.find(k)
        # On préfère le display de la racine elle-même
        if root == k:
            group_display[root] = disp
        elif root not in group_display:
            group_display[root] = disp

    # franchises : toute clé -> display canonique de son groupe
    franchises: dict[str, str] = {
        k: group_display[uf.find(k)]
        for k in node_display
    }

    # Compte combien d'entrées TV brutes pointent vers chaque franchise
    # (avant union-find : on compte les entrées dont clean_base(titre) = cette franchise)
    tv_entry_count: dict[str, int] = {}
    for e in data:
        if ntype(e.get("type")) != "tv":
            continue
        titles = iter_titles(e)
        if not titles:
            continue
        base = clean_base(titles[0])
        k = norm(base)
        if k:
            tv_entry_count[k] = tv_entry_count.get(k, 0) + 1
        # Compte aussi via la racine union-find
        if k in franchises:
            root_disp = franchises[k]
            root_key  = norm(root_disp)
            if root_key != k:
                tv_entry_count[root_key] = tv_entry_count.get(root_key, 0) + 1

    # tv_keys = ensemble de toutes les clés normalisées de franchises TV
    tv_keys = set(franchises.keys())
    # Index pour la détection rapide film -> franchise TV
    tv_index, prefix_set = build_tv_index(franchises, tv_entry_count)

    # ------------------------------------------------------------------
    # Passe 2 : films
    # - film lié à une franchise TV existante  -> ignoré (absorbé)
    # - film standalone                        -> nouvelle franchise
    # ------------------------------------------------------------------
    for e in data:
        if ntype(e.get("type")) != "movie":
            continue
        titles = iter_titles(e)
        if not titles:
            continue

        title_main = titles[0]

        if movie_belongs_to_tv(titles, tv_keys, tv_index, prefix_set):
            continue  # absorbé dans la franchise TV



        # Film standalone
        disp = clean_base(title_main)
        key  = norm(disp)
        if not key:
            continue

        register(franchises, key, disp)
        canonical_disp = franchises[key]

        for t in titles[1:]:
            k2 = norm(clean_base(t))
            register(franchises, k2, canonical_disp)

    # ------------------------------------------------------------------
    # Résultat final : valeurs uniques, triées alphabétiquement
    # ------------------------------------------------------------------
    final = sorted(set(franchises.values()), key=str.casefold)

    OUTPUT.write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ {len(final)} franchises -> {OUTPUT}")


if __name__ == "__main__":
    main()
