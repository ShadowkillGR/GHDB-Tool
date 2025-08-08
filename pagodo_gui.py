import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from ttkbootstrap import Style
from ttkbootstrap.tooltip import ToolTip
import json
import os
import random
import webbrowser
from pathlib import Path
import threading
import time
import traceback

from pagodo_core import run_pagodo_scan
from embedded_ghdb import GHDB_DATA

APP_TITLE = "Pagodo GUI — Neo Hacker Edition"
CONFIG_DIR_NAME = "PagodoGUI"
FAV_CATEGORY_NAME = "★ Favorites"
UNKNOWN_CAT_BUCKET = "Imported Dorks"
CONTACT_EMAIL = "kurasaki2010@gmail.com"

EMOJI_DEFAULT = "🗂️"
EMOJI_LOCK = "🔒"
EMOJI_DB = "🗄️"
EMOJI_WEB = "🌐"
EMOJI_FILE = "📄"
EMOJI_USER = "👤"
EMOJI_SERVER = "🖥️"


def _norm(s):
    return " ".join(str(s).split()) if s is not None else ""


def _emoji_for_category(cat):
    c = (cat or "").lower()
    if any(k in c for k in ("login", "admin", "auth", "password")):
        return EMOJI_LOCK
    if any(k in c for k in ("db", "database", "sql", "mongodb", "postgres")):
        return EMOJI_DB
    if any(k in c for k in ("site", "url", "web", "http", "https")):
        return EMOJI_WEB
    if any(k in c for k in ("file", "config", "backup", "txt", "pdf", "doc", "env")):
        return EMOJI_FILE
    if any(k in c for k in ("user", "account", "profile")):
        return EMOJI_USER
    if any(k in c for k in ("server", "apache", "nginx", "tomcat", "iis")):
        return EMOJI_SERVER
    return EMOJI_DEFAULT


def _appdata_dir():
    if os.name == "nt":
        return Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))) / CONFIG_DIR_NAME
    return Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / CONFIG_DIR_NAME


class UserDorkStore:
    """
    Persist only user-added dorks: list of {"category": str, "dork": str}
    Does NOT store the whole DB — only user additions/edits.
    """
    def __init__(self):
        self.path = _appdata_dir() / "user_dorks.json"
        self._cache = None

    def load(self):
        if self._cache is not None:
            return list(self._cache)
        if self.path.exists():
            try:
                rows = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                rows = []
        else:
            rows = []
        # normalize
        for r in rows:
            if "dork" in r:
                r["dork"] = _norm(r["dork"])
            if "category" in r and r["category"] is not None:
                r["category"] = r["category"].strip()
        self._cache = rows
        return list(self._cache)

    def _save(self, rows):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def add(self, category, dork):
        rows = self.load()
        item = {"category": (category or "").strip(), "dork": _norm(dork)}
        for r in rows:
            if r.get("category") == item["category"] and _norm(r.get("dork", "")) == item["dork"]:
                return
        rows.append(item)
        self._cache = rows
        self._save(rows)

    def remove(self, category, dork):
        nd = _norm(dork)
        rows = [r for r in self.load() if not (r.get("category") == (category or "").strip() and _norm(r.get("dork", "")) == nd)]
        self._cache = rows
        self._save(rows)

    def update(self, old_cat, old_dork, new_cat, new_dork):
        rows = self.load()
        ond = _norm(old_dork)
        changed = False
        for r in rows:
            if r.get("category") == (old_cat or "").strip() and _norm(r.get("dork", "")) == ond:
                r["category"] = (new_cat or "").strip()
                r["dork"] = _norm(new_dork)
                changed = True
                break
        if changed:
            self._cache = rows
            self._save(rows)


class DorkListStore:
    """
    Optional full DB override on disk:
    - Saves/loads {"Category": ["d1","d2", ...], ...}
    """
    def __init__(self):
        self.path = _appdata_dir() / "all_dorks.json"

    def exists(self):
        return self.path.exists()

    def load(self):
        if not self.exists():
            return None
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def save(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def clear(self):
        try:
            if self.path.exists():
                self.path.unlink()
        except Exception:
            pass


class FavoritesStore:
    """Persist favorites as [{"dork": str, "category": str}]"""
    def __init__(self):
        self.path = _appdata_dir() / "favorites.json"
        self._cache = None

    def load(self):
        if self._cache is not None:
            return list(self._cache)
        if self.path.exists():
            try:
                rows = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                rows = []
        else:
            rows = []
        for r in rows:
            if "dork" in r:
                r["dork"] = _norm(r["dork"])
            if "category" in r and r["category"] is not None:
                r["category"] = r["category"].strip()
        self._cache = rows
        return list(self._cache)

    def _save(self, rows):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def is_favorite(self, dork):
        nd = _norm(dork)
        return any(_norm(r.get("dork", "")) == nd for r in self.load())

    def add(self, dork, category):
        nd = _norm(dork)
        rows = self.load()
        if any(_norm(r.get("dork", "")) == nd for r in rows):
            return
        rows.append({"dork": nd, "category": (category or "").strip()})
        self._cache = rows
        self._save(rows)

    def remove(self, dork):
        nd = _norm(dork)
        rows = [r for r in self.load() if _norm(r.get("dork", "")) != nd]
        self._cache = rows
        self._save(rows)


class ManageDorksWindow(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app.root)
        self.app = app
        self.title("Manage Custom Dorks")
        self.minsize(720, 460)
        self.resizable(True, True)
        self.transient(app.root)
        self.grab_set()

        form = ttk.Frame(self)
        form.pack(fill=tk.X, padx=10, pady=8)

        ttk.Label(form, text="Category:").grid(row=0, column=0, sticky="w")
        self.var_cat = tk.StringVar()
        self.cbo_cat = ttk.Combobox(form, textvariable=self.var_cat, width=28,
                                    values=self._categories(), state="normal")
        self.cbo_cat.grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Dork:").grid(row=0, column=2, sticky="w", padx=(20, 0))
        self.var_dork = tk.StringVar()
        self.ent_dork = ttk.Entry(form, textvariable=self.var_dork, width=50)
        self.ent_dork.grid(row=0, column=3, sticky="we", padx=6)
        form.grid_columnconfigure(3, weight=1)

        btns_form = ttk.Frame(self)
        btns_form.pack(fill=tk.X, padx=10, pady=(0, 6))
        ttk.Button(btns_form, text="New", command=self._new_blank).pack(side=tk.LEFT)
        ttk.Button(btns_form, text="Add / Save", command=self._add_or_save).pack(side=tk.LEFT, padx=6)

        cols = ("category", "dork")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", selectmode="browse")
        self.tree.heading("category", text="Category")
        self.tree.heading("dork", text="Dork")
        self.tree.column("category", width=220, anchor="w")
        self.tree.column("dork", anchor="w")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)

        bottom = ttk.Frame(self)
        bottom.pack(fill=tk.X, padx=10, pady=(0, 10))
        ttk.Button(bottom, text="Delete Selected", command=self._delete_selected).pack(side=tk.LEFT)
        ttk.Button(bottom, text="Close", command=self._close).pack(side=tk.RIGHT)

        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self._refresh_tree()
        self._center()

    def _categories(self):
        return sorted(self.app.dorks_by_category.keys())

    def _center(self):
        self.update_idletasks()
        x = self.app.root.winfo_rootx() + self.app.root.winfo_width() // 2 - self.winfo_width() // 2
        y = self.app.root.winfo_rooty() + self.app.root.winfo_height() // 2 - self.winfo_height() // 2
        self.geometry(f"+{x}+{y}")

    def _refresh_tree(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        for row in self.app.user_store.load():
            cat, dork = row.get("category", ""), row.get("dork", "")
            self.tree.insert("", "end", values=(cat, dork))
        self.cbo_cat["values"] = self._categories()

    def _on_select(self, _event=None):
        item = self.tree.selection()
        if not item:
            return
        cat, dork = self.tree.item(item[0], "values")
        self.var_cat.set(cat)
        self.var_dork.set(dork)

    def _new_blank(self):
        self.tree.selection_remove(*self.tree.selection())
        self.var_cat.set("")
        self.var_dork.set("")
        self.cbo_cat.focus_set()

    def _add_or_save(self):
        cat = (self.var_cat.get() or "").strip()
        dork = _norm(self.var_dork.get())
        if not cat:
            messagebox.showwarning("Missing category", "Please enter a category.")
            return
        if not dork:
            messagebox.showwarning("Missing dork", "Please enter a dork.")
            return

        sel = self.tree.selection()
        if sel:
            old_cat, old_dork = self.tree.item(sel[0], "values")
            if (old_cat, old_dork) != (cat, dork):
                self.app.user_store.update(old_cat, old_dork, cat, dork)
                try:
                    if old_cat in self.app.dorks_by_category and old_dork in self.app.dorks_by_category[old_cat]:
                        self.app.dorks_by_category[old_cat].remove(old_dork)
                except ValueError:
                    pass
                self.app.dorks_by_category.setdefault(cat, [])
                if dork not in self.app.dorks_by_category[cat]:
                    self.app.dorks_by_category[cat].append(dork)
        else:
            self.app.user_store.add(cat, dork)
            self.app.dorks_by_category.setdefault(cat, [])
            if dork not in self.app.dorks_by_category[cat]:
                self.app.dorks_by_category[cat].append(dork)

        self._refresh_tree()
        self.app._refresh_after_user_change()
        messagebox.showinfo("Saved", "Custom dork saved.")

    def _delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        cat, dork = self.tree.item(sel[0], "values")
        if not messagebox.askyesno("Delete", f"Delete this dork?\n\n[{cat}]\n{dork}"):
            return
        self.app.user_store.remove(cat, dork)
        try:
            if cat in self.app.dorks_by_category and dork in self.app.dorks_by_category[cat]:
                self.app.dorks_by_category[cat].remove(dork)
        except ValueError:
            pass
        self._refresh_tree()
        self.app._refresh_after_user_change()

    def _close(self):
        self.destroy()


class PagodoGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)

        try:
            self.root.state('zoomed')
        except tk.TclError:
            try:
                self.root.attributes('-zoomed', True)
            except tk.TclError:
                pass

        self.root.geometry("1280x780")
        self.root.minsize(960, 720)

        self.user_store = UserDorkStore()
        self.full_store = DorkListStore()
        self.fav_store = FavoritesStore()

        stored = self.full_store.load()
        if stored:
            self.dorks_by_category = self._normalize_full(stored)
        else:
            self.dorks_by_category = {cat: list(dorks) for cat, dorks in GHDB_DATA.items()}
        self._merge_user_dorks()

        self.category_var = tk.StringVar()
        self.domain_var = tk.StringVar()
        self.search_var = tk.StringVar()
        self.theme_var = tk.StringVar(value="darkly")

        # --- Added: search engine support ---
        self.search_engines = {
            "Google": "https://www.google.com/search?q={query}",
            "Yahoo": "https://search.yahoo.com/search?p={query}",
            "Bing": "https://www.bing.com/search?q={query}",
            "DuckDuckGo": "https://duckduckgo.com/?q={query}",
        }
        self.selected_search_engine = tk.StringVar(value="Google")

        self.style = Style(theme=self.theme_var.get())

        self._build_menubar()
        self._build_ui()
        self._set_random_category()
        self._apply_hacker_theme()

        self.root.bind("<Control-d>", lambda e: self.toggle_favorite())
        self.root.bind("<Control-f>", lambda e: self._focus_search())
        self.root.bind("<Control-r>", lambda e: self.run_scan())
        self.root.bind("<Control-e>", lambda e: self.export_all_dorks())

        self._show_daily_dork()

        # Show enhanced ASCII art banner at startup
        self.root.after(300, self._show_disclaimer_banner)

    def _build_menubar(self):
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Import Dorks…", command=self.import_all_dorks)
        file_menu.add_command(label="Export Dorks…", command=self.export_all_dorks)
        file_menu.add_separator()
        file_menu.add_command(label="Reset to Embedded", command=self.reset_to_embedded)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(label="Add Dork", command=self.on_add_dork)
        tools_menu.add_command(label="Manage Dorks", command=self.open_manage_dorks)
        tools_menu.add_command(label="Toggle Favorite", command=self.toggle_favorite, accelerator="Ctrl+D")
        tools_menu.add_separator()
        tools_menu.add_command(label="Run Scan", command=self.run_scan, accelerator="Ctrl+R")
        tools_menu.add_command(label="Save Results", command=self.save_results)
        tools_menu.add_separator()
        tools_menu.add_command(label="Apply Theme", command=self.apply_theme)
        menubar.add_cascade(label="Tools", menu=tools_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Help", command=self.show_help)
        help_menu.add_command(label="About", command=lambda: messagebox.showinfo("About", f"{APP_TITLE}\nCreated by GreenRangerGR\nNeo Hacker Edition"))
        menubar.add_cascade(label="Help", menu=help_menu)

        contact_menu = tk.Menu(menubar, tearoff=0)
        contact_menu.add_command(label="Contact GreenRangerGR…", command=self.open_contact_window)
        menubar.add_cascade(label="Contact", menu=contact_menu)

        self.root.config(menu=menubar)

    def _build_ui(self):
        row1 = ttk.Frame(self.root)
        row1.pack(fill=tk.X, padx=10, pady=(6, 2))

        ttk.Label(row1, text="Category:").pack(side=tk.LEFT)
        self.category_combo = ttk.Combobox(
            row1, textvariable=self.category_var,
            values=self._all_categories_for_combo(),
            width=32, state="readonly")
        self.category_combo.pack(side=tk.LEFT, padx=5)
        ToolTip(self.category_combo, text="Pick a category (★ Favorites shows starred dorks)")
        self.category_combo.bind("<<ComboboxSelected>>", lambda e: self.load_dorks())

        ttk.Label(row1, text="Domain (optional):").pack(side=tk.LEFT, padx=(10, 0))
        self.domain_entry = ttk.Entry(row1, textvariable=self.domain_var, width=28)
        self.domain_entry.pack(side=tk.LEFT, padx=5)
        ToolTip(self.domain_entry, text="Limit search: site:example.com")

        # --- New Search Engine Dropdown ---
        se_frame = ttk.Frame(row1)
        se_frame.pack(side=tk.LEFT, padx=10)
        ttk.Label(se_frame, text="Search Engine:").pack(side=tk.LEFT)
        se_combo = ttk.Combobox(se_frame, textvariable=self.selected_search_engine,
                                values=list(self.search_engines.keys()), state="readonly", width=12)
        se_combo.pack(side=tk.LEFT)
        ToolTip(se_combo, text="Choose search engine for opening dorks")

        ttk.Button(row1, text="Load Dorks", command=self.load_dorks).pack(side=tk.LEFT, padx=5)
        ttk.Button(row1, text="Add Dork", command=self.on_add_dork).pack(side=tk.LEFT, padx=5)
        ttk.Button(row1, text="Manage Dorks", command=self.open_manage_dorks).pack(side=tk.LEFT, padx=5)
        ttk.Button(row1, text="Toggle Favorite (Ctrl+D)", command=self.toggle_favorite).pack(side=tk.LEFT, padx=5)
        self.fav_count_var = tk.StringVar(value="★ 0")
        self.fav_label = ttk.Label(row1, textvariable=self.fav_count_var)
        self.fav_label.pack(side=tk.LEFT, padx=(4, 0))
        ToolTip(self.fav_label, text="Total favorites")

        # Row 2 — utility controls
        row2 = ttk.Frame(self.root)
        row2.pack(fill=tk.X, padx=10, pady=(0, 6))
        ttk.Button(row2, text="Import Dorks…", command=self.import_all_dorks).pack(side=tk.LEFT, padx=5)
        ttk.Button(row2, text="Export Dorks…", command=self.export_all_dorks).pack(side=tk.LEFT, padx=5)
        ttk.Button(row2, text="Reset to Embedded", command=self.reset_to_embedded).pack(side=tk.LEFT, padx=5)
        ttk.Button(row2, text="Help", command=self.show_help).pack(side=tk.LEFT, padx=5)

        # Row 3 — search
        search_row = ttk.Frame(self.root)
        search_row.pack(fill=tk.X, padx=10)
        ttk.Label(search_row, text="Search:").pack(side=tk.LEFT)
        self.search_entry = ttk.Entry(search_row, textvariable=self.search_var, width=44)
        self.search_entry.pack(side=tk.LEFT, padx=6)
        ToolTip(self.search_entry, text="Filter across all categories + favorites")
        ttk.Button(search_row, text="Search", command=self.search_dorks).pack(side=tk.LEFT)

        # Row 4 — theme
        theme_row = ttk.Frame(self.root)
        theme_row.pack(fill=tk.X, padx=10, pady=4)
        ttk.Label(theme_row, text="Theme:").pack(side=tk.LEFT)
        theme_selector = ttk.Combobox(theme_row, textvariable=self.theme_var,
                                      values=self.style.theme_names(), width=20, state="readonly")
        theme_selector.pack(side=tk.LEFT, padx=4)
        ToolTip(theme_selector, text="Switch UI theme (base)")
        ttk.Button(theme_row, text="Apply Theme", command=self.apply_theme).pack(side=tk.LEFT, padx=6)

        # Daily Dork banner (hidden until populated)
        self.banner_frame = ttk.Frame(self.root)
        self.banner_frame.pack(fill=tk.X, padx=10, pady=(2, 0))
        self.banner_label = ttk.Label(self.banner_frame, text="", font=("Consolas", 10, "bold"))
        self.banner_label.pack(side=tk.LEFT)
        self.banner_btn_open = ttk.Button(self.banner_frame, text="Open", command=self._daily_dork_open)
        self.banner_btn_scan = ttk.Button(self.banner_frame, text="Scan Only", command=self._daily_dork_scan)
        self.banner_btn_dismiss = ttk.Button(self.banner_frame, text="Dismiss", command=self._daily_dork_dismiss)
        self.banner_btn_open.pack(side=tk.RIGHT, padx=4)
        self.banner_btn_scan.pack(side=tk.RIGHT, padx=4)
        self.banner_btn_dismiss.pack(side=tk.RIGHT, padx=4)
        self.banner_frame.pack_forget()

        # Main listbox
        self.dorks_listbox = tk.Listbox(self.root, selectmode=tk.MULTIPLE, font=("Consolas", 11))
        self.dorks_listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        ToolTip(self.dorks_listbox, text="Double-click a dork to open in browser")
        self.dorks_listbox.bind("<Double-Button-1>", self.open_dork_in_browser)

        # Right-click context menu on the listbox
        self._build_listbox_context_menu()

        # Run/save row
        run_row = ttk.Frame(self.root)
        run_row.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(run_row, text="Run Scan (Ctrl+R)", command=self.run_scan).pack(side=tk.LEFT)
        ttk.Button(run_row, text="Save Results", command=self.save_results).pack(side=tk.LEFT, padx=6)

        # Log — neon console vibe
        self.log_text = tk.Text(self.root, height=11, cursor="hand2", font=("Consolas", 10))
        self.log_text.pack(fill=tk.BOTH, padx=10, pady=(4, 6))
        ToolTip(self.log_text, text="Double-click a URL to open in browser")
        self.log_text.bind("<Double-Button-1>", self.open_url)

        logo = ttk.Label(self.root, text="Software created by GreenRangerGR",
                         anchor="e", font=("Segoe UI", 9, "italic"))
        logo.pack(fill=tk.X, padx=10, pady=(0, 8))

        self._update_fav_count()

    def _build_listbox_context_menu(self):
        self.ctx = tk.Menu(self.root, tearoff=0)
        self.ctx.add_command(label="Open in Browser", command=self._ctx_open)
        self.ctx.add_command(label="Copy Dork", command=self._ctx_copy)
        self.ctx.add_separator()
        self.ctx.add_command(label="Toggle Favorite", command=self.toggle_favorite)
        self.ctx.add_command(label="Run Scan", command=self.run_scan)

        def show_ctx(event):
            try:
                idx = self.dorks_listbox.nearest(event.y)
                if idx >= 0:
                    if idx not in self.dorks_listbox.curselection():
                        self.dorks_listbox.selection_clear(0, tk.END)
                        self.dorks_listbox.selection_set(idx)
                self.ctx.tk_popup(event.x_root, event.y_root)
            finally:
                self.ctx.grab_release()

        self.dorks_listbox.bind("<Button-3>", show_ctx)
        self.dorks_listbox.bind("<Control-Button-1>", show_ctx)

    def _ctx_open(self):
        sel = self.dorks_listbox.curselection()
        if not sel:
            return
        dork = self.dorks_listbox.get(sel[0])
        domain = self.domain_var.get().strip()
        query = f'site:{domain} {dork}' if domain else dork
        url_template = self.search_engines.get(self.selected_search_engine.get(), self.search_engines["Google"])
        url = url_template.format(query=query.replace(" ", "+"))
        webbrowser.open(url)

    def _ctx_copy(self):
        sel = self.dorks_listbox.curselection()
        if not sel:
            return
        dork = self.dorks_listbox.get(sel[0])
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(dork)
            self.root.update()
        except Exception:
            pass

    def _apply_hacker_theme(self):
        try:
            self.log_text.configure(bg="#0c0f0c", fg="#2ee44f", insertbackground="#2ee44f")
        except Exception:
            pass
        try:
            self.dorks_listbox.configure(bg="#101317", fg="#e6ffe6",
                                         selectbackground="#194a2a", selectforeground="#eaffea")
        except Exception:
            pass

    def _show_daily_dork(self):
        pool = []
        for dorks in self.dorks_by_category.values():
            pool.extend(dorks)
        if not pool:
            return
        self._daily_dork = random.choice(pool)
        self.banner_label.configure(text=f"Daily Dork:  {self._daily_dork}")
        self.banner_frame.pack(fill=tk.X, padx=10, pady=(2, 0))

    def _daily_dork_dismiss(self):
        self.banner_frame.pack_forget()

    def _daily_dork_open(self):
        dork = getattr(self, "_daily_dork", "")
        if not dork:
            return
        domain = self.domain_var.get().strip()
        query = f'site:{domain} {dork}' if domain else dork
        url_template = self.search_engines.get(self.selected_search_engine.get(), self.search_engines["Google"])
        url = url_template.format(query=query.replace(" ", "+"))
        webbrowser.open(url)

    def _daily_dork_scan(self):
        dork = getattr(self, "_daily_dork", "")
        if not dork:
            return
        self.log_text.delete(1.0, tk.END)
        self.log_text.insert(tk.END, "Running scan on 1 dork...\n\n")
        results = run_pagodo_scan([dork], self.domain_var.get())
        self.scan_results = results
        for dk, urls in results.items():
            self.log_text.insert(tk.END, f"[{dk}]\n")
            for u in urls:
                self.log_text.insert(tk.END, f"{u}\n")

    def open_contact_window(self):
        win = tk.Toplevel(self.root)
        win.title("Contact — GreenRangerGR")
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()

        frm = ttk.Frame(win, padding=10)
        frm.pack(fill=tk.BOTH, expand=True)

        msg = (
            "Got feedback, feature ideas, or a bug to report?\n\n"
            f"Email me at: {CONTACT_EMAIL}\n\n"
            "I read everything and try to reply quickly."
        )
        lbl = ttk.Label(frm, text=msg, justify="left")
        lbl.pack(anchor="w")

        btns = ttk.Frame(frm)
        btns.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(btns, text="Copy email", command=lambda: self._copy_to_clipboard(CONTACT_EMAIL)).pack(side=tk.LEFT)
        ttk.Button(btns, text="Open email app", command=lambda: webbrowser.open(f"mailto:{CONTACT_EMAIL}")).pack(
            side=tk.LEFT, padx=6
        )
        ttk.Button(btns, text="Close", command=win.destroy).pack(side=tk.RIGHT)

        self._center_child(win)

    def _copy_to_clipboard(self, text):
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.root.update()
            messagebox.showinfo("Copied", "Email address copied to clipboard.")
        except Exception:
            pass

    def _center_child(self, win):
        win.update_idletasks()
        x = self.root.winfo_rootx() + self.root.winfo_width() // 2 - win.winfo_width() // 2
        y = self.root.winfo_rooty() + self.root.winfo_height() // 2 - win.winfo_height() // 2
        win.geometry(f"+{x}+{y}")

    def _show_disclaimer_banner(self):
        ascii_helmet = (
"⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⠤⠞⣩⣴⠚⢿⣟⣿⣻⣟⡿⣶⣬⣉⡒⠦⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀\n"
"⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣼⣹⣯⣻⡿⣿⣷⣌⣿⣞⡷⣯⣟⡷⣯⣿⡿⣿⣄⣳⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀\n"
"⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢠⣧⣾⣯⣿⣽⡿⣾⣟⡷⣯⣟⡷⣯⣟⣷⡿⣟⣿⣽⡟⡆⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀\n"
"⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⡜⣾⣿⣻⣟⡾⣽⣳⢿⣟⣷⢯⣟⡷⣯⡿⣽⣿⣟⣿⡇⢹⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀\n"
"⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢰⢣⠟⠺⠷⠯⣟⣷⣯⣟⣾⣟⡿⣾⣽⡿⣽⣿⣟⠾⠟⠛⢸⡆⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀\n"
"⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣼⢩⣴⣾⢿⣶⣶⣤⣑⣛⣿⠯⠿⠷⢯⣿⣛⣥⣴⣶⣶⣶⣸⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀\n"
"⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢹⣶⠹⢿⣆⠈⢻⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⢸⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀\n"
"⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣯⣧⡈⠙⠷⣦⣩⢧⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠿⠏⣠⣸⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀\n"
"⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢻⣿⣻⢶⣤⣤⣭⣟⣻⠿⣿⣿⣿⣿⢿⣟⣯⣵⣶⣿⣯⡏⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀\n"
"⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⣿⣯⢿⣽⣻⣿⠿⠿⠿⠷⠾⠶⠿⠿⠿⢿⣽⣾⣽⣿⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀\n"
"⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⣿⣟⣯⣿⣷⣼⣉⣉⣩⡶⠩⠄⡈⢉⣵⣿⣿⣿⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀\n"
"⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⡻⣿⡿⣽⣧⡳⣕⢲⢒⠒⢆⡠⣲⣿⣿⣿⠏⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀\n"
"⠀⠀⠀⠀⠀⠀⠀⠀⢠⡞⠋⢳⡄⠀⠀⠀⠀⠀⠀⠀⢀⡇⠐⠝⠻⢯⣿⣷⣶⣶⣶⣶⣾⣿⠟⢻⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀\n"
"⠀⠀⠀⠀⠀⠀⠀⠀⢸⡇⠀⠀⢻⠀⠀⠀⠀⢀⣀⡤⢾⣇⠀⠈⠢⡀⠉⠉⠉⠉⠉⠛⠉⠀⠀⠸⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀\n"
"⠀⠀⠀⠀⠀⠀⠀⠀⠀⢧⠀⠀⢺⣀⣤⢖⣺⣭⣶⢾⡿⣿⣷⣤⡀⠈⠂⠄⡀⠀⠀⠀⠀⢀⣠⣶⣿⣷⣦⣤⣀⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀\n"
"⠀⠀⠀⠀⠀⠀⠀⢀⣠⣼⡇⢒⠁⢷⣾⢿⣽⣳⢯⡿⣽⣳⢯⡿⣿⣶⣦⣤⣠⣅⣠⣴⣶⣿⢿⣻⢿⡽⣯⣟⡿⣿⣿⣲⠦⣤⣀⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀\n"
"⠀⠀⠀⠀⠀⣠⡾⠿⠾⠽⠾⠤⠥⠬⢿⣟⡾⣽⢯⣟⡷⣯⢿⣽⣳⢯⣟⣿⡻⠏⢿⣯⢷⣯⣟⣯⢿⡽⣷⢯⣟⡷⣯⣟⡿⣶⣦⣭⡙⣳⢦⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀\n"
"⠀⠀⠀⢀⢟⣾⡏⠀⠀⠀⠀⠀⠀⢀⠈⣿⣻⣽⣻⢾⡽⣯⣟⡾⣽⣻⢾⠟⠁⠀⠈⠙⣿⢾⡽⣞⣿⡽⣯⣟⣾⣻⢷⣯⣟⡷⣯⡟⣱⡿⣷⣮⣳⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀\n"
"⠀⠀⠀⣸⣼⠋⠀⠀⠐⠒⠒⠒⠒⠂⠊⢿⣷⢯⣟⣯⣟⡷⣯⣟⣷⠟⠁⠀⠀⠀⠀⠀⠉⣿⣻⡽⣾⡽⣷⢯⣷⣻⣟⡾⣽⣻⡝⢰⣿⣽⣳⣟⣿⣿⡀⠀⠀⠀⠀⠀⠀⠀⠀\n"
"⠀⠀⠀⡇⣿⣇⠀⠀⢀⢀⢀⣀⣀⣐⣈⣸⡿⣯⣟⡾⣽⣻⢷⡻⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠙⢟⣷⣻⡽⣟⣾⣳⢯⣟⣷⡟⢀⣿⡷⣯⣷⣻⢾⣿⢷⠀⠀⠀⠀⠀⠀⠀⠀\n"
"⠀⠀⢸⣷⣿⣿⡀⠀⠁⠉⢉⡁⠀⠀⠈⣿⣟⡷⣯⣟⡷⡯⠋⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠻⣷⣻⣟⡾⣽⣯⣟⣾⠁⢸⣯⣟⡷⣯⣟⡿⣞⣿⡆⠀⠀⠀⠀⠀⠀⠀\n"
"⠀⠀⢸⣿⣿⢻⡇⠀⠀⠂⠒⠒⠒⠒⢺⣿⡽⣯⢷⡯⠋⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠙⢷⣯⣟⣷⣻⢾⠃⠀⣾⣿⣽⣻⢷⣯⣟⣯⣟⣿⡄⠀⠀⠀⠀⠀⠀\n"
"⠀⠀⣼⣿⡟⠈⠧⠤⣤⣤⣤⣤⣤⠤⠞⣿⣿⣽⠟⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⢻⣾⣳⢯⡏⠀⡀⣿⣿⡾⣽⣻⢾⡽⣾⡽⣾⣿⣄⠀⠀⠀⠀⠀\n"
"⠀⢠⣟⣿⣀⣤⣴⡿⣿⢿⣆⠀⠀⠀⠀⣿⢘⡋⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢻⣽⡿⠀⢠⢰⣿⣟⣿⣯⣟⣯⣟⣷⣻⡽⣿⣿⣆⠀⠀⠀⠀\n"
"⠀⣼⣿⠹⣿⣽⣳⣟⣿⣟⣿⣷⣄⠀⣼⣿⡾⣿⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢙⡅⠀⠎⢸⣿⣟⡾⣷⣟⡾⣽⢾⣽⣻⢷⣻⣞⣷⡀⠀⠀\n"
"⢀⣿⣿⡆⣿⣞⣷⣻⡿⣾⣟⣾⣿⢿⣿⣿⡿⣽⣻⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣿⣷⡘⠀⣾⣿⡿⣽⣻⢾⣟⣯⢿⡾⣽⢯⡿⣽⣿⣧⠀⠀\n"
"⢸⣿⣿⣿⣿⣽⢾⣿⡽⠟⠊⠉⠀⠸⣷⣿⣟⡷⣯⢿⣧⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣾⣟⣷⣻⣇⢀⡏⢻⣿⣯⣟⣯⢿⣾⢿⡽⣯⡿⣽⢷⣻⣿⡆⠀\n"
"⢸⣿⣿⣽⣻⣿⠛⠁⠀⠀⠀⠀⠀⠀⢹⣿⢯⡿⣽⣻⢾⣷⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣾⣟⣷⣻⢾⣟⣿⣼⠀⠀⠻⣿⣽⡾⣯⢿⣯⣟⡷⣟⣯⣿⣳⢿⣿⠀\n"
"⠘⢿⣿⣷⣯⡿⣿⣶⣶⣤⣤⣤⣶⣾⣿⣿⣯⣟⡷⣯⣟⡾⣽⣧⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣾⣟⣷⣻⣞⣯⣿⣟⣿⡇⠀⠀⠀⠙⢿⣿⣟⣯⢿⣯⣟⣯⡷⣯⣟⣯⣿⡇\n"
"⠀⠈⢻⣿⣷⣻⣽⢯⣟⣿⣻⣿⣿⣿⣿⣟⡾⣽⣻⢷⣯⣟⡷⣯⣿⣆⠀⠀⠀⠀⠀⠀⣠⣿⣟⣷⣻⣞⡷⣯⢷⣿⣻⣿⠃⠀⠀⠀⠀⠀⠈⢿⣿⣻⣞⡿⣯⣿⣳⣯⢷⣯⣿\n"
"⠀⠀⠈⠛⢿⣷⣯⣿⣾⣷⣿⣿⣟⣾⣯⣿⣟⡷⣯⣟⡾⣽⣻⢷⣻⣞⣧⡀⠀⠀⣠⣾⣟⣷⣻⣞⡷⣯⢿⣽⡿⣯⣿⡏⠀⠀⠀⠀⠀⠀⠀⢈⣿⣿⣽⣿⣽⣯⣷⣯⣿⢾⣽\n"
"⠀⠀⠀⠀⠀⠉⠛⠛⠛⠋⠉⣿⣿⢾⣟⣿⡾⣽⢷⣯⣟⡷⣯⣟⣷⢯⡿⣽⣤⣾⣟⣷⣻⣞⡷⣯⢿⣽⣻⣞⣿⣽⣿⡇⠀⠀⢀⣤⣾⣿⣿⣽⣿⢀⣠⣴⣾⡿⣿⡿⣏⢻⠟\n"
"⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣻⣿⣿⢯⣿⣽⢯⣟⣾⣽⣻⢷⣻⣞⡿⣽⢯⣟⡾⣽⣞⡷⣯⢿⣽⣻⢾⣽⡿⣾⣽⣿⡇⠀⠀⢀⣤⣾⣿⣿⣽⣿⢀⣠⣴⣾⡿⣿⡿⣏⢻⠟\n"
"⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢘⣿⣯⢿⣞⣿⢯⣟⣾⣳⢯⣿⣳⢯⣟⣯⢿⣞⣿⣳⢯⡿⣽⣯⢷⣻⢯⣿⢿⣳⣿⣿⠁⢀⣴⣿⡿⠿⠷⠛⠊⠉⢸⣿⣽⣾⣿⣳⢿⡿⡸⠀\n"
"⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠿⠿⠿⠯⠿⢯⣟⣾⣽⣻⣾⡽⣯⣟⣾⣯⣟⣾⣽⣯⣟⣷⣯⡿⠯⠿⠿⠛⠛⠛⠃⠀⠛⠉⠀⠀⠀⠀⠀⠀⠀⠈⠛⠚⠛⠚⠛⠫⠋⠀⠀\n"
        )

        text = (
            "Educational Use Only\n"
            "This tool is intended solely for learning, research, and\n"
            "testing on systems you own or have permission to test.\n"
            "Misuse may be illegal. The author assumes no liability.\n\n"
            "Built by GreenRangerGR"
        )

        win = tk.Toplevel(self.root)
        win.title("Welcome — Notice")
        win.transient(self.root)
        win.grab_set()
        win.resizable(False, False)

        outer = ttk.Frame(win, padding=12)
        outer.grid(row=0, column=0, sticky="nsew")
        win.grid_columnconfigure(0, weight=1)
        win.grid_rowconfigure(0, weight=1)

        ascii_container = ttk.Frame(outer)
        ascii_container.grid(row=0, column=0, sticky="nsew")
        outer.grid_columnconfigure(0, weight=1)

        ascii_label = tk.Label(
            ascii_container,
            text=ascii_helmet,
            font=("Consolas", 9),
            justify="center",
            anchor="center"
        )
        ascii_label.pack(fill="both", expand=True)

        ttk.Label(outer, text="").grid(row=1, column=0, pady=(6, 0))

        text_label = ttk.Label(outer, text=text, justify="center")
        text_label.grid(row=2, column=0, sticky="ew")

        btns = ttk.Frame(outer)
        btns.grid(row=3, column=0, sticky="e", pady=(10, 0))
        ttk.Button(btns, text="I Understand", command=win.destroy).pack(side=tk.RIGHT)

        self._center_child(win)

    def _normalize_full(self, data):
        if isinstance(data, dict):
            out = {}
            for k, v in data.items():
                if not isinstance(k, str):
                    continue
                lst = v if isinstance(v, list) else [v]
                lst2 = [_norm(x) for x in lst if _norm(x)]
                out[k] = lst2
            return out
        if isinstance(data, list):
            out = {}
            for row in data:
                if not isinstance(row, dict):
                    continue
                cat = _norm(row.get("category", ""))
                dork = _norm(row.get("dork", ""))
                if not cat or not dork:
                    continue
                out.setdefault(cat, [])
                if dork not in out[cat]:
                    out[cat].append(dork)
            return out
        return {}

    def _merge_user_dorks(self):
        changed = False
        for row in self.user_store.load():
            cat = (row.get("category") or "").strip()
            dork = _norm(row.get("dork", ""))
            if not cat or not dork:
                continue
            self.dorks_by_category.setdefault(cat, [])
            if not self._category_has_dork(cat, dork):
                self.dorks_by_category[cat].append(dork)
                changed = True
        if changed and hasattr(self, "category_combo"):
            self._refresh_categories_combo()

    def _category_has_dork(self, cat, nd):
        return any(_norm(x) == nd for x in self.dorks_by_category.get(cat, []))

    def _all_categories_for_combo(self):
        cats = sorted(self.dorks_by_category.keys())
        return [FAV_CATEGORY_NAME] + [f"{_emoji_for_category(c)} {c}" for c in cats]

    def _raw_from_disp(self, disp):
        if disp.startswith(FAV_CATEGORY_NAME):
            return FAV_CATEGORY_NAME
        parts = disp.split(" ", 1)
        if len(parts) == 2 and parts[0] and parts[0] != parts[1]:
            return parts[1]
        return disp

    def _refresh_categories_combo(self):
        self.category_combo["values"] = self._all_categories_for_combo()

    def _set_random_category(self):
        cats = self._all_categories_for_combo()
        if cats:
            self.category_var.set(random.choice(cats))
            self.load_dorks()

    def _focus_search(self):
        try:
            self.search_entry.focus_set()
            self.search_entry.select_range(0, tk.END)
        except Exception:
            pass

    def _refresh_after_user_change(self):
        self._refresh_categories_combo()
        self.load_dorks()

    def load_dorks(self):
        self.dorks_listbox.delete(0, tk.END)
        raw = self._raw_from_disp(self.category_var.get())
        if raw == FAV_CATEGORY_NAME:
            for dork in [r.get("dork", "") for r in self.fav_store.load() if r.get("dork")]:
                self.dorks_listbox.insert(tk.END, dork)
            return
        if raw in self.dorks_by_category:
            for dork in self.dorks_by_category[raw]:
                self.dorks_listbox.insert(tk.END, dork)

    def search_dorks(self):
        query = (self.search_var.get() or "").lower()
        self.dorks_listbox.delete(0, tk.END)
        added = set()
        for dorks in self.dorks_by_category.values():
            for dork in dorks:
                if query in dork.lower() and dork not in added:
                    self.dorks_listbox.insert(tk.END, dork)
                    added.add(dork)
        for r in self.fav_store.load():
            dork = r.get("dork", "")
            if dork and query in dork.lower() and dork not in added:
                self.dorks_listbox.insert(tk.END, dork)
                added.add(dork)

    def toggle_favorite(self):
        selection = self.dorks_listbox.curselection()
        if not selection:
            messagebox.showinfo("Favorites", "Select one or more dorks first.")
            return
        current_raw = self._raw_from_disp(self.category_var.get())
        changed = False
        for idx in selection:
            dork = _norm(self.dorks_listbox.get(idx))
            if not dork:
                continue
            if self.fav_store.is_favorite(dork):
                self.fav_store.remove(dork)
                changed = True
            else:
                cat_to_store = current_raw if current_raw != FAV_CATEGORY_NAME else ""
                if not cat_to_store:
                    for c, lst in self.dorks_by_category.items():
                        if self._category_has_dork(c, dork):
                            cat_to_store = c
                            break
                    if not cat_to_store:
                        cat_to_store = UNKNOWN_CAT_BUCKET
                self.fav_store.add(dork, cat_to_store)
                changed = True
        if changed:
            self._update_fav_count()
            if current_raw == FAV_CATEGORY_NAME:
                self.load_dorks()

    def _favorites_list(self):
        return [r.get("dork", "") for r in self.fav_store.load() if r.get("dork")]

    def _update_fav_count(self):
        try:
            self.fav_count_var.set(f"★ {len(self._favorites_list())}")
        except Exception:
            pass

    def on_add_dork(self):
        raw_cat = self._raw_from_disp(self.category_var.get())
        if not raw_cat or raw_cat == FAV_CATEGORY_NAME:
            messagebox.showwarning("No category", "Select a real category first (not Favorites).")
            return
        if raw_cat not in self.dorks_by_category:
            self.dorks_by_category[raw_cat] = []

        dork = simpledialog.askstring("Add Custom Dork", "Enter the Google dork:")
        if not dork:
            return
        dork = _norm(dork)
        if not dork:
            messagebox.showwarning("Empty dork", "Please enter a non-empty dork.")
            return
        if self._category_has_dork(raw_cat, dork):
            messagebox.showinfo("Already exists", f"This dork already exists in “{raw_cat}”.")
            return

        self.dorks_by_category[raw_cat].append(dork)
        try:
            self.user_store.add(raw_cat, dork)
        except Exception:
            messagebox.showwarning("Not saved", "Added to session, but couldn’t persist.")
        if self._raw_from_disp(self.category_var.get()).strip() == raw_cat:
            self.load_dorks()
        messagebox.showinfo("Added", f"Dork added under “{raw_cat}”.")

    def open_manage_dorks(self):
        for w in self.root.winfo_children():
            if isinstance(w, ManageDorksWindow):
                try:
                    w.lift()
                    return
                except Exception:
                    pass
        ManageDorksWindow(self)

    def run_scan(self):
        selected = [self.dorks_listbox.get(i) for i in self.dorks_listbox.curselection()]
        domain = self.domain_var.get()
        if not selected:
            messagebox.showwarning("No dorks selected", "Please select dorks first.")
            return

        # Clear log and status
        self.log_text.delete(1.0, tk.END)
        self.log_text.insert(tk.END, f"Running scan on {len(selected)} dorks...\n\n")

        # Spinner state
        self._scan_complete = False
        self._spinner_phase = 0

        def tick_spinner():
            if not getattr(self, "_scan_complete", True):
                spinner = "|/-\\"
                ch = spinner[self._spinner_phase % len(spinner)]
                self._spinner_phase += 1
                try:
                    self.root.title(f"{APP_TITLE} — Scanning {ch}")
                except Exception:
                    pass
                self.root.after(120, tick_spinner)
            else:
                self.root.title(APP_TITLE)

        tick_spinner()

        def do_scan():
            try:
                results = run_pagodo_scan(selected, domain)
            except Exception:
                try:
                    with open("error_log.txt", "w", encoding="utf-8") as f:
                        f.write(traceback.format_exc())
                except Exception:
                    pass
                def show_err():
                    self._scan_complete = True
                    messagebox.showerror("Scan error", "An error occurred during scanning. See error_log.txt for details.")
                self.root.after(0, show_err)
                return

            def show_results():
                self._scan_complete = True
                self.scan_results = results
                self.log_text.delete(1.0, tk.END)
                if not results:
                    self.log_text.insert(tk.END, "No results.\n")
                    return
                for dork, urls in results.items():
                    self.log_text.insert(tk.END, f"[{dork}]\n")
                    for url in urls:
                        self.log_text.insert(tk.END, f"{url}\n")
                    self.log_text.insert(tk.END, "\n")
                self.log_text.see(tk.END)
            self.root.after(0, show_results)

        threading.Thread(target=do_scan, daemon=True).start()

    def save_results(self):
        if not hasattr(self, "scan_results") or not getattr(self, "scan_results", {}):
            messagebox.showinfo("Nothing to save", "Please run a scan first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".json")
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(self.scan_results, f, indent=2)
                messagebox.showinfo("Saved", f"Results saved to {path}")
            except Exception as e:
                messagebox.showerror("Save failed", str(e))

    def open_url(self, event):
        index = self.log_text.index("@%s,%s" % (event.x, event.y))
        line = self.log_text.get(index + " linestart", index + " lineend").strip()
        if line.startswith("http"):
            webbrowser.open(line)

    def open_dork_in_browser(self, event):
        selection = self.dorks_listbox.curselection()
        if not selection:
            return
        dork = self.dorks_listbox.get(selection[0])
        domain = self.domain_var.get().strip()
        query = f'site:{domain} {dork}' if domain else dork
        url_template = self.search_engines.get(self.selected_search_engine.get(), self.search_engines["Google"])
        url = url_template.format(query=query.replace(" ", "+"))
        webbrowser.open(url)

    def apply_theme(self):
        new_theme = self.theme_var.get()
        self.style.theme_use(new_theme)
        self.load_dorks()
        self._apply_hacker_theme()

    def show_help(self):
        help_text = (
            f"{APP_TITLE}\n\n"
            "• Category: Pick a type (with emoji badges) — includes ★ Favorites.\n"
            "• Domain: Optionally limit search to a site (site:example.com).\n"
            "• Search: Filter dorks across all categories and favorites (Ctrl+F).\n"
            "• Run Scan: Send selected dorks to Google and log results (Ctrl+R).\n"
            "• Double-click a dork: Opens the Google search.\n"
            "• Save Results: Export current scan to JSON.\n"
            "• Add Dork: Add a custom dork to the current category.\n"
            "• Manage Dorks: Add/edit/delete user dorks (persisted in your profile).\n"
            "• Favorites: Toggle selected dorks as favorites (Ctrl+D).\n"
            "• Import Dorks: Merge JSON without duplicates; unknown categories → 'Imported Dorks'.\n"
            "• Export Dorks: Save the full DB to JSON (Ctrl+E).\n"
            "• Reset to Embedded: Restore the built-in list.\n"
            "• Daily Dork: Random suggestion banner with quick actions.\n"
            f"\nData folder: {_appdata_dir()} (user_dorks.json, favorites.json, all_dorks.json)\n"
        )
        messagebox.showinfo("Help", help_text)

    def _iter_import_items(self, data):
        if isinstance(data, dict):
            for cat, lst in data.items():
                if not isinstance(cat, str):
                    continue
                if isinstance(lst, list):
                    for d in lst:
                        yield (cat, str(d))
                else:
                    yield (cat, str(lst))
        elif isinstance(data, list):
            for row in data:
                if not isinstance(row, dict):
                    continue
                cat = row.get("category")
                dork = row.get("dork")
                if dork is None:
                    continue
                yield (str(cat) if cat is not None else None, str(dork))

    def import_all_dorks(self):
        path = filedialog.askopenfilename(
            title="Import Dorks JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            messagebox.showerror("Import failed", f"Could not read JSON:\n{e}")
            return

        existing = {}
        for cat, dorks in self.dorks_by_category.items():
            for d in dorks:
                existing[_norm(d)] = cat

        imported_any = False
        if UNKNOWN_CAT_BUCKET not in self.dorks_by_category:
            self.dorks_by_category[UNKNOWN_CAT_BUCKET] = []

        seen_in_file = set()
        for cat, dork in self._iter_import_items(data):
            nd = _norm(dork)
            if not nd or nd in seen_in_file:
                continue
            seen_in_file.add(nd)

            if nd in existing:
                continue

            dest_cat = (cat or "").strip()
            if not dest_cat or dest_cat not in self.dorks_by_category:
                dest_cat = UNKNOWN_CAT_BUCKET

            self.dorks_by_category.setdefault(dest_cat, [])
            if not self._category_has_dork(dest_cat, nd):
                self.dorks_by_category[dest_cat].append(nd)
                imported_any = True

        if imported_any:
            messagebox.showinfo("Import complete", "Dorks imported successfully.")
            self._refresh_categories_combo()
            self.load_dorks()
        else:
            messagebox.showinfo("Import complete", "No new dorks were imported.")

    def export_all_dorks(self):
        path = filedialog.asksaveasfilename(
            title="Export All Dorks JSON",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            data = {k: v for k, v in self.dorks_by_category.items()}
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("Export complete", f"All dorks exported to {path}")
        except Exception as e:
            messagebox.showerror("Export failed", str(e))

    def reset_to_embedded(self):
        if not messagebox.askyesno("Reset", "Restore the built-in dork list and discard changes?"):
            return
        self.dorks_by_category = {cat: list(dorks) for cat, dorks in GHDB_DATA.items()}
        self.user_store._cache = []
        self.user_store._save([])
        self.fav_store._cache = []
        self.fav_store._save([])
        self._refresh_categories_combo()
        self.load_dorks()
        messagebox.showinfo("Reset", "Reset to embedded dorks completed.")

def main():
    root = tk.Tk()
    app = PagodoGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
