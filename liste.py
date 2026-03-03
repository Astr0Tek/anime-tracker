import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import os
import re
import sys
import threading
import subprocess
import unicodedata

# ─────────────────────────── CONSTANTES ───────────────────────────

DATA_FILE    = "animes.json"
WISH_FILE    = "wishlist.json"
CATALOG_FILE = "catalogue.json"

STATUSES      = ["a jour", "en cours", "termine", "arrete"]
WISH_PRIOS    = ["haute", "normale", "basse"]

# ══════════════════════════════════════════════════════════════════
#  I/O
# ══════════════════════════════════════════════════════════════════

def load_catalogue():
    if not os.path.exists(CATALOG_FILE):
        return []
    with open(CATALOG_FILE, encoding="utf-8") as f:
        data = json.load(f)
        return data if isinstance(data, list) else []


def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, encoding="utf-8") as f:
            raw = json.load(f)
    except Exception as e:
        messagebox.showerror("Erreur", f"Impossible de lire {DATA_FILE} : {e}")
        return {}
    data = {}
    if isinstance(raw, dict):
        for name, v in raw.items():
            if not isinstance(name, str) or not name.strip():
                continue
            name = name.strip()
            if isinstance(v, str):
                data[name] = {"status": v, "rating": 0}
            elif isinstance(v, dict):
                st = v.get("status", "en cours")
                rt = v.get("rating", 0)
                try: rt = int(rt)
                except: rt = 0
                if st not in STATUSES: st = "en cours"
                rt = max(0, min(5, rt))
                data[name] = {"status": st, "rating": rt}
    elif isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict): continue
            name = str(item.get("name", "")).strip()
            if not name: continue
            st = item.get("status", "en cours")
            rt = item.get("rating", 0)
            try: rt = int(rt)
            except: rt = 0
            if st not in STATUSES: st = "en cours"
            rt = max(0, min(5, rt))
            data[name] = {"status": st, "rating": rt}
    return data


def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(animes, f, ensure_ascii=False, indent=2)


def load_wishlist():
    if not os.path.exists(WISH_FILE):
        return {}
    try:
        with open(WISH_FILE, encoding="utf-8") as f:
            raw = json.load(f)
            if isinstance(raw, dict):
                return raw
    except Exception:
        pass
    return {}

def save_wishlist():
    with open(WISH_FILE, "w", encoding="utf-8") as f:
        json.dump(wishlist, f, ensure_ascii=False, indent=2)


# ══════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════

def _norm(s):
    """Normalise une chaîne pour la recherche : minuscules, sans accents, sans ponctuation."""
    s = (s or "").lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s{2,}", " ", s).strip()


def stars(n):
    n = max(0, min(5, int(n)))
    return "★" * n + "☆" * (5 - n)


def rebuild_search_cache():
    global catalogue_search
    catalogue_search = [(t, _norm(t)) for t in catalogue]


# ══════════════════════════════════════════════════════════════════
#  ONGLET TRACKER  (liste principale)
# ══════════════════════════════════════════════════════════════════

def refresh_table():
    for row in table.get_children():
        table.delete(row)
    items = sorted(
        animes.items(),
        key=lambda kv: (-int(kv[1].get("rating", 0)), kv[0].casefold()),
    )
    for name, d in items:
        table.insert("", tk.END,
                     values=(name, stars(d.get("rating", 0)), d.get("status", "en cours")))


def set_form(name, tab="tracker"):
    if tab == "tracker":
        entry_name.delete(0, tk.END)
        entry_name.insert(0, name)
        if name in animes:
            rating_var.set(int(animes[name].get("rating", 0)))
            status_var.set(animes[name].get("status", "en cours"))
        else:
            rating_var.set(0)
            status_var.set("en cours")
    else:
        wish_entry_name.delete(0, tk.END)
        wish_entry_name.insert(0, name)
        if name in wishlist:
            wish_prio_var.set(wishlist[name].get("priority", "normale"))
        else:
            wish_prio_var.set("normale")


def add_or_update():
    name = entry_name.get().strip()
    if not name:
        messagebox.showwarning("Erreur", "Choisis un anime.")
        return
    animes[name] = {"status": status_var.get(), "rating": int(rating_var.get())}
    save_data()
    refresh_table()
    messagebox.showinfo("OK", f"Enregistré : {name}")


def delete_selected():
    sel = table.selection()
    if not sel:
        messagebox.showinfo("Info", "Sélectionne un anime dans le tableau.")
        return
    name = table.item(sel[0])["values"][0]
    if name in animes:
        del animes[name]
        save_data()
        refresh_table()


def on_table_select(_=None):
    sel = table.selection()
    if not sel:
        return
    name, star_text, status = table.item(sel[0])["values"]
    entry_name.delete(0, tk.END)
    entry_name.insert(0, name)
    rating_var.set(star_text.count("★"))
    status_var.set(status)


def add_to_catalogue():
    name = entry_name.get().strip()
    if not name:
        messagebox.showwarning("Erreur", "Écris un nom d'anime.")
        return
    if any(name.casefold() == t.casefold() for t in catalogue):
        messagebox.showinfo("Info", "Déjà dans le catalogue.")
        return
    catalogue.append(name)
    cat_sorted = sorted(set(catalogue), key=str.casefold)
    with open(CATALOG_FILE, "w", encoding="utf-8") as f:
        json.dump(cat_sorted, f, ensure_ascii=False, indent=2)
    catalogue[:] = cat_sorted
    rebuild_search_cache()
    messagebox.showinfo("OK", f"Ajouté : {name}")
    rebuild_results()


def delete_from_catalogue():
    name = entry_name.get().strip()
    if not name:
        sel = results_list.curselection()
        name = results_list.get(sel[0]) if sel else ""
    if not name:
        messagebox.showwarning("Erreur", "Choisis un anime à supprimer.")
        return
    idx = next((i for i, t in enumerate(catalogue) if t.casefold() == name.casefold()), None)
    if idx is None:
        messagebox.showinfo("Info", "Pas dans le catalogue.")
        return
    if not messagebox.askyesno("Confirmer", f"Supprimer du catalogue :\n{catalogue[idx]} ?"):
        return
    del catalogue[idx]
    cat_sorted = sorted(set(catalogue), key=str.casefold)
    with open(CATALOG_FILE, "w", encoding="utf-8") as f:
        json.dump(cat_sorted, f, ensure_ascii=False, indent=2)
    catalogue[:] = cat_sorted
    rebuild_search_cache()
    rebuild_results()
    messagebox.showinfo("OK", f"Supprimé : {name}")


def export_txt():
    if not animes:
        messagebox.showinfo("Info", "Ta liste est vide.")
        return
    path = filedialog.asksaveasfilename(
        defaultextension=".txt",
        filetypes=[("Fichier texte", "*.txt")],
        title="Exporter ma liste",
    )
    if not path:
        return
    items = sorted(animes.items(),
                   key=lambda kv: (-int(kv[1].get("rating", 0)), kv[0].casefold()))
    nw, sw = 60, 10
    lines = [f"{'Nom':<{nw}} | {'Note':<7} | {'Statut':<{sw}}\n",
             "-" * (nw + sw + 14) + "\n"]
    for name, d in items:
        lines.append(f"{name[:nw]:<{nw}} | {stars(d.get('rating',0)):<7} | {d.get('status',''):<{sw}}\n")
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    messagebox.showinfo("OK", f"Exporté : {path}")


# ══════════════════════════════════════════════════════════════════
#  RECHERCHE CATALOGUE (partagée entre les deux onglets)
# ══════════════════════════════════════════════════════════════════

_pending_after = None
_active_tab    = "tracker"   # "tracker" ou "wish"


def rebuild_results():
    results_list.delete(0, tk.END)
    q = _norm(search_var.get().strip())
    if not q:
        return
    shown = 0
    for title, title_norm in catalogue_search:
        if q in title_norm:
            results_list.insert(tk.END, title)
            shown += 1
            if shown >= 200:
                break


def on_search_key(_=None):
    global _pending_after
    if _pending_after is not None:
        root.after_cancel(_pending_after)
    _pending_after = root.after(150, rebuild_results)


def _pick_result(name):
    """Envoie le titre sélectionné vers l'onglet actif."""
    if not name:
        return
    if _active_tab == "tracker":
        set_form(name, "tracker")
    else:
        set_form(name, "wish")


def pick_from_results(_=None):
    sel = results_list.curselection()
    if sel:
        _pick_result(results_list.get(sel[0]))


def pick_first_result(_=None):
    if results_list.size() > 0:
        _pick_result(results_list.get(0))
        return "break"


def on_results_arrow(_=None):
    """Navigation clavier dans la liste de résultats sans quitter la recherche."""
    sel = results_list.curselection()
    if not sel:
        if results_list.size() > 0:
            results_list.selection_set(0)
            results_list.activate(0)
    else:
        cur = sel[0]
        nxt = min(cur + 1, results_list.size() - 1)
        results_list.selection_clear(0, tk.END)
        results_list.selection_set(nxt)
        results_list.activate(nxt)
        results_list.see(nxt)
    return "break"


def on_results_arrow_up(_=None):
    sel = results_list.curselection()
    if sel:
        cur = sel[0]
        prv = max(cur - 1, 0)
        results_list.selection_clear(0, tk.END)
        results_list.selection_set(prv)
        results_list.activate(prv)
        results_list.see(prv)
    return "break"


def on_tab_changed(_=None):
    global _active_tab
    tab = notebook.tab(notebook.select(), "text")
    _active_tab = "wish" if tab == "🎯 Watch Later" else "tracker"


# ══════════════════════════════════════════════════════════════════
#  ONGLET WISHLIST
# ══════════════════════════════════════════════════════════════════

def refresh_wish_table():
    for row in wish_table.get_children():
        wish_table.delete(row)
    items = sorted(
        wishlist.items(),
        key=lambda kv: (WISH_PRIOS.index(kv[1].get("priority", "normale")),
                        kv[0].casefold()),
    )
    for name, d in items:
        prio = d.get("priority", "normale")
        icon = {"haute": "🔴", "normale": "🟡", "basse": "🟢"}.get(prio, "🟡")
        wish_table.insert("", tk.END, values=(name, f"{icon} {prio}"))


def wish_add_or_update():
    name = wish_entry_name.get().strip()
    if not name:
        messagebox.showwarning("Erreur", "Choisis un anime.")
        return
    wishlist[name] = {"priority": wish_prio_var.get()}
    save_wishlist()
    refresh_wish_table()
    messagebox.showinfo("OK", f"Watch Later mis à jour : {name}")


def wish_delete():
    sel = wish_table.selection()
    if not sel:
        messagebox.showinfo("Info", "Sélectionne un anime dans le tableau.")
        return
    name = wish_table.item(sel[0])["values"][0]
    if name in wishlist:
        del wishlist[name]
        save_wishlist()
        refresh_wish_table()


def export_wish_txt():
    if not wishlist:
        messagebox.showinfo("Info", "Ta watch later est vide.")
        return
    path = filedialog.asksaveasfilename(
        defaultextension=".txt",
        filetypes=[("Fichier texte", "*.txt")],
        title="Exporter ma Watch Later",
    )
    if not path:
        return
    items = sorted(
        wishlist.items(),
        key=lambda kv: (WISH_PRIOS.index(kv[1].get("priority", "normale")),
                        kv[0].casefold()),
    )
    nw = 60
    lines = [f"{'Nom':<{nw}} | Priorité\n", "-" * (nw + 12) + "\n"]
    for name, d in items:
        prio = d.get("priority", "normale")
        lines.append(f"{name[:nw]:<{nw}} | {prio}\n")
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    messagebox.showinfo("OK", f"Exporté : {path}")


def wish_move_to_tracker():
    """Transfère un anime de la watch later vers le tracker en demandant la note."""
    sel = wish_table.selection()
    if not sel:
        messagebox.showinfo("Info", "Sélectionne un anime dans le tableau.")
        return
    name = wish_table.item(sel[0])["values"][0]

    # Boîte de dialogue personnalisée
    dialog = tk.Toplevel(root)
    dialog.title("Commencer un anime")
    dialog.geometry("320x180")
    dialog.resizable(False, False)
    dialog.grab_set()  # bloque la fenêtre principale

    tk.Label(dialog, text=f"Anime : {name}", font=("", 10, "bold")).pack(pady=(14, 6))

    row1 = tk.Frame(dialog)
    row1.pack(pady=4)
    tk.Label(row1, text="Note :").pack(side="left")
    dlg_rating = tk.IntVar(value=0)
    tk.Spinbox(row1, from_=0, to=5, width=4, textvariable=dlg_rating).pack(side="left", padx=6)

    row2 = tk.Frame(dialog)
    row2.pack(pady=4)
    tk.Label(row2, text="Statut :").pack(side="left")
    dlg_status = tk.StringVar(value="en cours")
    ttk.Combobox(row2, textvariable=dlg_status,
                 values=STATUSES, state="readonly", width=12).pack(side="left", padx=6)

    def _confirm():
        animes[name] = {"status": dlg_status.get(), "rating": int(dlg_rating.get())}
        if name in wishlist:
            del wishlist[name]
        save_data()
        save_wishlist()
        refresh_table()
        refresh_wish_table()
        dialog.destroy()
        messagebox.showinfo("OK", f"'{name}' ajouté au tracker !")

    tk.Button(dialog, text="✅ Confirmer", command=_confirm).pack(pady=(8, 0))


def on_wish_table_select(_=None):
    sel = wish_table.selection()
    if not sel:
        return
    name = wish_table.item(sel[0])["values"][0]
    wish_entry_name.delete(0, tk.END)
    wish_entry_name.insert(0, name)
    if name in wishlist:
        wish_prio_var.set(wishlist[name].get("priority", "normale"))


# ══════════════════════════════════════════════════════════════════
#  GÉNÉRATION CATALOGUE EN ARRIÈRE-PLAN
# ══════════════════════════════════════════════════════════════════

_generation_id = 0   # incrémenté à chaque lancement, annule les anciens threads

CATALOGUE_SCRIPT = "catalogue.py"


def _run_catalogue_generation(gen_id):
    """Lance catalogue.py en sous-processus dans un thread de fond.

    RÈGLE TKINTER : aucun objet tk ne doit être touché depuis ce thread.
    Toutes les mises à jour UI passent par root.after(0, ...).
    """
    if not os.path.exists(CATALOGUE_SCRIPT):
        root.after(0, lambda: status_label.config(
            text=f"⚠️  {CATALOGUE_SCRIPT} introuvable."))
        return

    root.after(0, lambda: status_label.config(
        text="⏳ Génération du catalogue en cours…"))

    try:
        result = subprocess.run(
            [sys.executable, CATALOGUE_SCRIPT],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            err = result.stderr.strip() or result.stdout.strip()
            root.after(0, lambda: status_label.config(
                text=f"❌ Erreur : {err[:80]}"))
            return

        if gen_id != _generation_id:
            return

        # Relit le catalogue.json produit par catalogue.py
        with open(CATALOG_FILE, encoding="utf-8") as f:
            new_cat = json.load(f)

        def _apply(r=new_cat, gid=gen_id):
            if gid != _generation_id:
                return
            catalogue.clear()
            catalogue.extend(r)
            rebuild_search_cache()
            status_label.config(text=f"✅ Catalogue généré : {len(r)} franchises")
            rebuild_results()

        root.after(0, _apply)

    except Exception as ex:
        msg = str(ex)
        root.after(0, lambda: status_label.config(
            text=f"❌ Erreur : {msg}"))


def launch_catalogue_generation():
    global _generation_id
    _generation_id += 1
    gid = _generation_id
    t = threading.Thread(target=_run_catalogue_generation, args=(gid,), daemon=True)
    t.start()


# ══════════════════════════════════════════════════════════════════
#  DONNÉES GLOBALES
# ══════════════════════════════════════════════════════════════════

catalogue         = load_catalogue()
animes            = load_data()
wishlist          = load_wishlist()
catalogue_search  = []
rebuild_search_cache()

# ══════════════════════════════════════════════════════════════════
#  INTERFACE
# ══════════════════════════════════════════════════════════════════

root = tk.Tk()
root.title("Anime Tracker ⭐")
root.geometry("900x680")

# ── Barre de recherche (haut, commune aux deux onglets) ──────────
search_frame = tk.Frame(root)
search_frame.pack(fill="x", padx=10, pady=(8, 0))

tk.Label(search_frame, text="🔍 Recherche catalogue :").pack(side="left")
search_var  = tk.StringVar()
entry_search = tk.Entry(search_frame, textvariable=search_var, width=46)
entry_search.pack(side="left", padx=6)
entry_search.bind("<KeyRelease>", on_search_key)
entry_search.bind("<Return>",     pick_first_result)
entry_search.bind("<Down>",       on_results_arrow)   # ↓ depuis le champ

tk.Button(search_frame, text="🔄 Màj catalogue",
          command=launch_catalogue_generation).pack(side="right", padx=4)

status_label = tk.Label(search_frame, text="", fg="gray")
status_label.pack(side="right", padx=8)

# ── Liste de résultats ───────────────────────────────────────────
res_frame = tk.Frame(root)
res_frame.pack(fill="x", padx=10, pady=(2, 0))

tk.Label(res_frame,
         text="Résultats (↑↓ pour naviguer, Entrée ou double-clic pour sélectionner) :").pack(anchor="w")
results_list = tk.Listbox(res_frame, height=7)
results_list.pack(fill="x")
results_list.bind("<Double-Button-1>", pick_from_results)
results_list.bind("<Return>",          pick_from_results)
results_list.bind("<Down>",            on_results_arrow)
results_list.bind("<Up>",              on_results_arrow_up)
# Sélection en cliquant (simple clic) prévisualise dans le formulaire actif
results_list.bind("<ButtonRelease-1>", pick_from_results)

# Focus clavier : ↓ depuis la liste revient à la recherche en bas de liste
entry_search.bind("<Up>", on_results_arrow_up)

# ── Notebook (deux onglets) ──────────────────────────────────────
notebook = ttk.Notebook(root)
notebook.pack(fill="both", expand=True, padx=10, pady=6)
notebook.bind("<<NotebookTabChanged>>", on_tab_changed)

# ════════ Onglet 1 : Tracker ════════════════════════════════════
tab_tracker = tk.Frame(notebook)
notebook.add(tab_tracker, text="📋 Tracker")

form1 = tk.Frame(tab_tracker)
form1.pack(fill="x", padx=8, pady=6)

tk.Label(form1, text="Sélection :").grid(row=0, column=0, sticky="e")
entry_name = tk.Entry(form1, width=36)
entry_name.grid(row=0, column=1, padx=6, sticky="w")

tk.Label(form1, text="Note :").grid(row=0, column=2, padx=(12, 0), sticky="e")
rating_var = tk.IntVar(value=0)
tk.Spinbox(form1, from_=0, to=5, width=4,
           textvariable=rating_var).grid(row=0, column=3, sticky="w", padx=4)

tk.Label(form1, text="Statut :").grid(row=0, column=4, padx=(12, 0), sticky="e")
status_var = tk.StringVar(value="en cours")
ttk.Combobox(form1, textvariable=status_var,
             values=STATUSES, state="readonly", width=12)\
   .grid(row=0, column=5, padx=4, sticky="w")

btns1 = tk.Frame(tab_tracker)
btns1.pack(fill="x", padx=8, pady=(0, 4))
tk.Button(btns1, text="✅ Ajouter / Modifier",  command=add_or_update).pack(side="left")
tk.Button(btns1, text="🗑 Supprimer",           command=delete_selected).pack(side="left", padx=6)
tk.Button(btns1, text="➕ Ajouter au catalogue",command=add_to_catalogue).pack(side="left")
tk.Button(btns1, text="➖ Supprimer du catalogue",command=delete_from_catalogue).pack(side="left", padx=6)
tk.Button(btns1, text="💾 Exporter .txt",       command=export_txt).pack(side="left")

tk.Label(tab_tracker, text="Mes animes (triés par note) :").pack(anchor="w", padx=8)
cols1 = ("Nom", "Note", "Statut")
table = ttk.Treeview(tab_tracker, columns=cols1, show="headings", height=14)
for c in cols1: table.heading(c, text=c)
table.column("Nom",    anchor="w",      width=460)
table.column("Note",   anchor="center", width=120)
table.column("Statut", anchor="center", width=140)
table.pack(fill="both", expand=True, padx=8, pady=(0, 6))
table.bind("<<TreeviewSelect>>", on_table_select)

# ════════ Onglet 2 : Watch Later ════════════════════════════════════
tab_wish = tk.Frame(notebook)
notebook.add(tab_wish, text="🎯 Watch Later")

form2 = tk.Frame(tab_wish)
form2.pack(fill="x", padx=8, pady=6)

tk.Label(form2, text="Sélection :").grid(row=0, column=0, sticky="e")
wish_entry_name = tk.Entry(form2, width=36)
wish_entry_name.grid(row=0, column=1, padx=6, sticky="w")

tk.Label(form2, text="Priorité :").grid(row=0, column=2, padx=(12, 0), sticky="e")
wish_prio_var = tk.StringVar(value="normale")
ttk.Combobox(form2, textvariable=wish_prio_var,
             values=WISH_PRIOS, state="readonly", width=10)\
   .grid(row=0, column=3, padx=4, sticky="w")

btns2 = tk.Frame(tab_wish)
btns2.pack(fill="x", padx=8, pady=(0, 4))
tk.Button(btns2, text="✅ Ajouter / Modifier", command=wish_add_or_update).pack(side="left")
tk.Button(btns2, text="🗑 Supprimer",          command=wish_delete).pack(side="left", padx=6)
tk.Button(btns2, text="▶️ Commencer (→ Tracker)", command=wish_move_to_tracker).pack(side="left")
tk.Button(btns2, text="💾 Exporter .txt",      command=export_wish_txt).pack(side="left", padx=6)

tk.Label(tab_wish, text="Watch Later (trié par priorité) :").pack(anchor="w", padx=8)
cols2 = ("Nom", "Priorité")
wish_table = ttk.Treeview(tab_wish, columns=cols2, show="headings", height=14)
for c in cols2: wish_table.heading(c, text=c)
wish_table.column("Nom",      anchor="w",      width=560)
wish_table.column("Priorité", anchor="center", width=160)
wish_table.pack(fill="both", expand=True, padx=8, pady=(0, 6))
wish_table.bind("<<TreeviewSelect>>", on_wish_table_select)

# ── Démarrage ────────────────────────────────────────────────────
refresh_table()
refresh_wish_table()
entry_search.focus_set()

# Lance la génération uniquement si catalogue.json est absent
if not os.path.exists(CATALOG_FILE):
    launch_catalogue_generation()
else:
    status_label.config(text=f"✅ Catalogue chargé : {len(catalogue)} franchises")

root.mainloop()
