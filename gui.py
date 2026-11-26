import math
import random
from datetime import datetime

try:
    import tkinter as tk
    import tkinter.font as tkfont
    from tkinter import ttk, messagebox
except ImportError:
    tk = None

from algorithms import (vec_add, fmt_vec, compute_need, compute_available,
                        validate_state, safety_check, report_safety,
                        report_request, SAMPLES, ALGO_TEXT)
from theme import (PANEL, PANEL2, ENTRY, FG, PINK, CYAN, GREEN, RED, THEMES,
                   BUTTON_STYLES, lerp, rgb)


class RoundButton(tk.Canvas if tk else object):
    """Rounded button with a shadow, hover color and press effect."""

    def __init__(self, parent, text, command, style="purple"):
        font = tkfont.Font(family="Arial", size=12, weight="bold")
        self.bw = font.measure(text) + 30
        self.bh = font.metrics("linespace") + 16
        super().__init__(parent, width=self.bw, height=self.bh + 3,
                         bg=parent["bg"], highlightthickness=0, bd=0,
                         cursor="hand2", takefocus=1)
        self.command = command
        self.normal, self.hover, fg = BUTTON_STYLES[style]
        self.inside = False
        self.rounded(0, 3, self.bw, self.bh + 3, fill="#07051a", tags="shadow")
        self.rounded(0, 0, self.bw, self.bh, fill=self.normal, tags="face")
        self.create_text(self.bw / 2, self.bh / 2, text=text, fill=fg,
                         font=font, tags="label")
        self.font = font
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        self.bind("<ButtonPress-1>", self.on_press)
        self.bind("<ButtonRelease-1>", self.on_release)
        self.bind("<Return>", lambda _e: self.command())
        self.bind("<space>", lambda _e: self.command())
        self.bind("<FocusIn>", self.on_enter)
        self.bind("<FocusOut>", self.on_leave)
        self.pressed = False

    def rounded(self, x1, y1, x2, y2, r=12, **kw):
        pts = (x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
               x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
               x1, y2, x1, y2 - r, x1, y1 + r, x1, y1)
        return self.create_polygon(pts, smooth=True, **kw)

    def on_enter(self, _event):
        self.inside = True
        self.itemconfigure("face", fill=self.hover)

    def on_leave(self, _event):
        self.inside = False
        self.itemconfigure("face", fill=self.normal)

    def on_press(self, _event):
        self.pressed = True
        self.move("face", 0, 2)
        self.move("label", 0, 2)

    def on_release(self, _event):
        if not self.pressed:
            return
        self.pressed = False
        self.move("face", 0, -2)
        self.move("label", 0, -2)
        if self.inside:
            self.command()


class App:
    def __init__(self, root):
        self.root = root
        root.title("DEADLOCK BREAKER")
        gw = min(1500, root.winfo_screenwidth() - 60)
        gh = min(900, root.winfo_screenheight() - 100)
        root.geometry(f"{gw}x{gh}")
        root.minsize(1000, 680)

        self.theme = "night"
        self.w, self.h = gw, gh
        self.petals = []
        self.t = 0.0
        # Monospace font so the ASCII tables line up (Arial is proportional).
        self.mono = tkfont.Font(family=self.pick_mono(), size=12)
        self.ui_font = ("Arial", 13)
        root.option_add("*Font", self.ui_font)
        root.option_add("*TCombobox*Listbox.font", self.ui_font)
        root.option_add("*TCombobox*Listbox.background", ENTRY)
        root.option_add("*TCombobox*Listbox.foreground", FG)
        root.option_add("*TCombobox*Listbox.selectBackground", PINK)
        root.option_add("*TCombobox*Listbox.selectForeground", "#1a0f2e")

        self.canvas = tk.Canvas(root, highlightthickness=0, bg="#0c0a2c")
        self.canvas.pack(fill="both", expand=True)

        self.title_shadow = self.canvas.create_text(
            0, 0, text="", fill="#000000", font=("Arial", 24, "bold"))
        self.title_main = self.canvas.create_text(
            0, 0, text="", fill=PINK, font=("Arial", 24, "bold"))
        self.sub = self.canvas.create_text(
            0, 0, text="", fill=CYAN, font=("Arial", 11))
        self.clock = self.canvas.create_text(
            0, 0, text="", fill=CYAN, font=("Arial", 10),
            anchor="ne", justify="right")
        self.logo_items = {
            "ring": self.canvas.create_oval(
                0, 0, 0, 0, outline=PINK, width=2, fill="#20183b",
                tags="logo"),
            "links": [
                self.canvas.create_line(
                    0, 0, 0, 0, fill="#b9a2ff", width=1.5,
                    arrow="last", arrowshape=(5, 6, 2), tags="logo")
                for _ in range(3)
            ],
            "nodes": [
                self.canvas.create_oval(
                    0, 0, 0, 0, fill=color, outline="#20183b", width=1,
                    tags="logo")
                for color in (CYAN, PINK, CYAN)
            ],
            "badge": self.canvas.create_oval(
                0, 0, 0, 0, fill=GREEN, outline="#20183b", width=1,
                tags="logo"),
            "check": self.canvas.create_line(
                0, 0, 0, 0, fill="#1a0f2e", width=2, tags="logo"),
        }
        self.position_logo(42, 40)

        self.panel = tk.Frame(self.canvas, bg=PANEL, highlightthickness=2,
                              highlightbackground=PINK)
        self.win = self.canvas.create_window(0, 0, window=self.panel, anchor="n")

        self.alloc_e, self.max_e, self.total_e, self.req_e = [], [], [], []
        self.build_panel()
        self.load_sample()

        self.canvas.bind("<Configure>", self.on_resize)
        self.make_petals(38)
        self.update_clock()
        self.animate()

    def pick_mono(self):
        avail = set(tkfont.families(self.root))
        for name in ("Consolas", "Cascadia Mono", "Courier New",
                     "DejaVu Sans Mono", "Menlo", "Liberation Mono"):
            if name in avail:
                return name
        return "Courier"

    def build_panel(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TNotebook", background=PANEL, borderwidth=0)
        style.configure("TNotebook.Tab", background=PANEL2, foreground=FG,
                        padding=(16, 6), font=("Arial", 11, "bold"))
        style.map("TNotebook.Tab",
                  background=[("selected", PINK)],
                  foreground=[("selected", "#1a0f2e")])
        style.configure("TCombobox", fieldbackground=ENTRY, background=PANEL2,
                        foreground=FG, arrowcolor=FG, font=self.ui_font,
                        padding=4)
        style.map("TCombobox",
                  fieldbackground=[("readonly", ENTRY)],
                  foreground=[("readonly", FG)],
                  selectbackground=[("readonly", ENTRY)],
                  selectforeground=[("readonly", FG)])
        nb = ttk.Notebook(self.panel)
        nb.pack(fill="both", expand=True, padx=6, pady=6)
        tab1 = tk.Frame(nb, bg=PANEL)
        tab2 = tk.Frame(nb, bg=PANEL)
        self.build_algo_tab(tab2)
        nb.add(tab2, text="  1. Banker's Algorithm  ")
        nb.add(tab1, text="  2. Simulator  ")
        p = tab1
        left = tk.Frame(p, bg=PANEL)
        left.pack(side="left", fill="y", padx=12, pady=10)
        right = tk.Frame(p, bg=PANEL)
        right.pack(side="left", fill="both", expand=True, padx=(0, 12), pady=10)

        row = tk.Frame(left, bg=PANEL)
        row.pack(fill="x")
        tk.Label(row, text="Processes", bg=PANEL, fg=FG).pack(side="left")
        self.n_var = tk.IntVar(value=5)
        tk.Spinbox(row, from_=1, to=10, width=4, font=self.ui_font, textvariable=self.n_var,
                   bg=ENTRY, fg=FG, buttonbackground=PANEL2).pack(side="left", padx=4)
        tk.Label(row, text="Resource types", bg=PANEL, fg=FG).pack(side="left", padx=(8, 0))
        self.m_var = tk.IntVar(value=3)
        tk.Spinbox(row, from_=1, to=6, width=4, font=self.ui_font, textvariable=self.m_var,
                   bg=ENTRY, fg=FG, buttonbackground=PANEL2).pack(side="left", padx=4)
        self.button(row, "Set Size", self.set_size, "cyan").pack(side="left", padx=6)

        self.total_frame = tk.Frame(left, bg=PANEL)
        self.total_frame.pack(fill="x", pady=(10, 4))

        self.grid_frame = tk.Frame(left, bg=PANEL)
        self.grid_frame.pack(fill="x", pady=4)

        b = tk.Frame(left, bg=PANEL)
        b.pack(fill="x", pady=6)
        self.button(b, "Run Safety Check", self.run_safety, "pink").pack(side="left")
        self.button(b, "Sample 1", lambda: self.load_sample("Sample 1 (lecture)"), "purple").pack(side="left", padx=(6, 0))
        self.button(b, "Sample 2", lambda: self.load_sample("Sample 2"), "purple").pack(side="left", padx=6)
        self.button(b, "Clear", self.clear_all, "red").pack(side="left")

        st = tk.Frame(left, bg=PANEL)
        st.pack(fill="x", pady=(0, 4))
        tk.Label(st, text="Scan starts at", bg=PANEL, fg=FG).pack(side="left")
        self.start_var = tk.StringVar(value="P0")
        self.start_box = ttk.Combobox(st, textvariable=self.start_var, width=6,
                                      state="readonly")
        self.start_box.pack(side="left", padx=4)
        tk.Label(st, text="(circular scan order)",
                 bg=PANEL, fg="#a99cd6").pack(side="left")
        self.button(st, "Scan", self.run_scan, "green").pack(side="left", padx=(10, 0))

        rq = tk.LabelFrame(left, text=" Resource Request (extension) ", bg=PANEL,
                           fg=CYAN, bd=1)
        rq.pack(fill="x", pady=8)
        r1 = tk.Frame(rq, bg=PANEL)
        r1.pack(fill="x", padx=6, pady=4)
        tk.Label(r1, text="Process", bg=PANEL, fg=FG).pack(side="left")
        self.pid_var = tk.StringVar(value="P1")
        self.pid_box = ttk.Combobox(r1, textvariable=self.pid_var, width=6,
                                    state="readonly")
        self.pid_box.pack(side="left", padx=4)
        tk.Label(r1, text="Request", bg=PANEL, fg=FG).pack(side="left", padx=(8, 2))
        self.req_frame = tk.Frame(r1, bg=PANEL)
        self.req_frame.pack(side="left")
        r2 = tk.Frame(rq, bg=PANEL)
        r2.pack(fill="x", padx=6, pady=(0, 6))
        self.apply_var = tk.BooleanVar(value=False)
        tk.Checkbutton(r2, text="Apply to state if GRANTED", variable=self.apply_var,
                       bg=PANEL, fg=FG, selectcolor=ENTRY, activebackground=PANEL,
                       activeforeground=FG).pack(side="left")
        self.button(r2, "Check Request", self.run_request, "pink").pack(side="right")

        bg = tk.LabelFrame(left, text=" Background ", bg=PANEL, fg=CYAN, bd=1)
        bg.pack(fill="x", pady=4)
        self.button(bg, "Change Background", self.cycle_theme, "gold").pack(side="left", padx=6, pady=6)

        self.banner = tk.Label(right, text="Enter a system state, then run the algorithm.",
                               bg=PANEL2, fg=FG, font=("Arial", 18, "bold"),
                               pady=10)
        self.banner.pack(fill="x")
        wrap = tk.Frame(right, bg=PANEL)
        wrap.pack(fill="both", expand=True, pady=(6, 0))
        self.out = tk.Text(wrap, bg="#0f0c24", fg=FG, font=self.mono, wrap="none",
                           state="disabled", relief="flat", padx=8, pady=6)
        ys = tk.Scrollbar(wrap, command=self.out.yview)
        xs = tk.Scrollbar(wrap, command=self.out.xview, orient="horizontal")
        self.out.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        ys.pack(side="right", fill="y")
        xs.pack(side="bottom", fill="x")
        self.out.pack(side="left", fill="both", expand=True)
        bold_font = (self.mono.actual("family"), 12, "bold")
        self.out.tag_configure("h", foreground=PINK, font=bold_font)
        self.out.tag_configure("ok", foreground=GREEN)
        self.out.tag_configure("bad", foreground=RED)
        self.out.tag_configure("info", foreground=CYAN)
        self.out.tag_configure("n", foreground=FG)

    def make_text(self, parent, wrap="word"):
        wrap_f = tk.Frame(parent, bg=PANEL)
        wrap_f.pack(fill="both", expand=True, padx=10, pady=10)
        t = tk.Text(wrap_f, bg="#0f0c24", fg=FG, font=self.mono, wrap=wrap,
                    relief="flat", padx=10, pady=8)
        ys = tk.Scrollbar(wrap_f, command=t.yview)
        t.configure(yscrollcommand=ys.set)
        ys.pack(side="right", fill="y")
        t.pack(side="left", fill="both", expand=True)
        bold = (self.mono.actual("family"), 12, "bold")
        for name, color in (("h", PINK), ("ok", GREEN), ("bad", RED),
                            ("info", CYAN), ("n", FG), ("code", "#ffd9a0")):
            t.tag_configure(name, foreground=color)
        t.tag_configure("h", font=bold)
        return t

    def build_algo_tab(self, parent):
        t = self.make_text(parent)
        for text, tag in ALGO_TEXT:
            t.insert("end", text + "\n", tag)
        t.configure(state="disabled")

    def button(self, parent, text, cmd, style="purple"):
        return RoundButton(parent, text, cmd, style)

    def entry(self, parent, value="0"):
        e = tk.Entry(parent, width=4, font=self.mono, justify="center", bg=ENTRY, fg=FG,
                     insertbackground=FG, relief="flat")
        e.insert(0, str(value))

        def select_all(_event):
            e.selection_range(0, "end")

        def clear_default_zero(event):
            if (e.get() == "0" and
                    (event.char.isdigit() or event.char == "-" or
                     event.keysym in ("BackSpace", "Delete"))):
                e.delete(0, "end")

        e.bind("<FocusIn>", select_all)
        e.bind("<KeyPress>", clear_default_zero)
        return e

    def build_grid(self, n, m):
        for f in (self.total_frame, self.grid_frame, self.req_frame):
            for c in f.winfo_children():
                c.destroy()
        names = [chr(65 + j) for j in range(m)]

        tk.Label(self.total_frame, text="Total vector:", bg=PANEL, fg=PINK,
                 font=("Arial", 12, "bold")).pack(side="left", padx=(0, 6))
        self.total_e = []
        for j in range(m):
            tk.Label(self.total_frame, text=names[j], bg=PANEL, fg=CYAN,
                     width=3, anchor="center").pack(side="left", padx=(2, 0))
            e = self.entry(self.total_frame)
            e.config(width=4)
            e.pack(side="left", padx=(0, 5), ipady=3)
            self.total_e.append(e)

        g = self.grid_frame
        table = tk.Frame(g, bg=PANEL2, highlightthickness=1,
                         highlightbackground="#564778")
        table.pack(anchor="w")

        tk.Label(table, text="Process", bg=PANEL2, fg=PINK,
                 width=9, anchor="center", font=("Arial", 11, "bold")
                 ).grid(row=0, column=0, rowspan=2, padx=2, pady=4, sticky="nsew")
        tk.Label(table, text="Allocation", bg=PANEL2, fg=PINK,
                 width=max(12, m * 6), anchor="center",
                 font=("Arial", 11, "bold")
                 ).grid(row=0, column=1, columnspan=m, padx=2, pady=(4, 2), sticky="ew")
        tk.Label(table, text="", bg=PANEL2, width=2
                 ).grid(row=0, column=m + 1, rowspan=2)
        tk.Label(table, text="Max", bg=PANEL2, fg=PINK,
                 width=max(12, m * 6), anchor="center",
                 font=("Arial", 11, "bold")
                 ).grid(row=0, column=m + 2, columnspan=m, padx=2, pady=(4, 2), sticky="ew")

        for j in range(m):
            tk.Label(table, text=names[j], bg=PANEL2, fg=CYAN,
                     width=6, anchor="center", font=("Arial", 11, "bold")
                     ).grid(row=1, column=1 + j, pady=(0, 4), sticky="nsew")
            tk.Label(table, text=names[j], bg=PANEL2, fg=CYAN,
                     width=6, anchor="center", font=("Arial", 11, "bold")
                     ).grid(row=1, column=m + 2 + j, pady=(0, 4), sticky="nsew")

        self.alloc_e, self.max_e = [], []
        for i in range(n):
            row_bg = "#20183b" if i % 2 == 0 else "#18132f"
            tk.Label(table, text=f"P{i}", bg=row_bg, fg=FG,
                     width=9, anchor="center"
                     ).grid(row=2 + i, column=0, padx=2, pady=2, sticky="nsew")
            ra, rm = [], []
            for j in range(m):
                a = self.entry(table)
                a.config(width=4)
                a.grid(row=2 + i, column=1 + j, padx=4, pady=2, ipady=3)
                ra.append(a)
                x = self.entry(table)
                x.config(width=4)
                x.grid(row=2 + i, column=m + 2 + j, padx=4, pady=2, ipady=3)
                rm.append(x)
            self.alloc_e.append(ra)
            self.max_e.append(rm)

        self.req_e = []
        for j in range(m):
            e = self.entry(self.req_frame)
            e.pack(side="left", padx=3, ipady=3)
            self.req_e.append(e)
        self.pid_box["values"] = [f"P{i}" for i in range(n)]
        self.start_box["values"] = [f"P{i}" for i in range(n)]
        if self.start_var.get() not in self.start_box["values"]:
            self.start_var.set("P0")
        if self.pid_var.get() not in self.pid_box["values"]:
            self.pid_var.set("P0")

    def set_size(self):
        try:
            n, m = int(self.n_var.get()), int(self.m_var.get())
        except (tk.TclError, ValueError):
            messagebox.showerror("Invalid size", "Enter whole numbers for size.")
            return
        if not (1 <= n <= 10 and 1 <= m <= 6):
            messagebox.showerror("Invalid size", "Processes: 1-10, resource types: 1-6.")
            return
        self.build_grid(n, m)

    def fill(self, entries, values):
        for e, v in zip(entries, values):
            e.delete(0, "end")
            e.insert(0, str(v))

    def load_sample(self, key="Sample 1 (lecture)"):
        s = SAMPLES[key]
        n, m = len(s["alloc"]), len(s["total"])
        self.n_var.set(n)
        self.m_var.set(m)
        self.build_grid(n, m)
        self.fill(self.total_e, s["total"])
        for i in range(n):
            self.fill(self.alloc_e[i], s["alloc"][i])
            self.fill(self.max_e[i], s["max"][i])
        if key.startswith("Sample 2"):
            self.fill(self.req_e, [1, 0, 0])
            self.start_var.set("P1")
        else:
            self.fill(self.req_e, [1, 0, 2])
            self.start_var.set("P0")
        self.pid_var.set("P1")

    def clear_all(self):
        for e in self.total_e + self.req_e:
            self.fill([e], [0])
        for r in self.alloc_e + self.max_e:
            self.fill(r, [0] * len(r))
        self.show([], "Enter a system state, then run the algorithm.", FG, PANEL2)

    def read_int(self, e, label):
        txt = e.get().strip()
        try:
            return int(txt)
        except ValueError:
            raise ValueError(f"{label}: '{txt}' is not a whole number.")

    def read_state(self):
        names = [chr(65 + j) for j in range(len(self.total_e))]
        total = [self.read_int(e, f"Total {names[j]}") for j, e in enumerate(self.total_e)]
        alloc = [[self.read_int(e, f"Allocation P{i}/{names[j]}") for j, e in enumerate(r)]
                 for i, r in enumerate(self.alloc_e)]
        maxm = [[self.read_int(e, f"Max P{i}/{names[j]}") for j, e in enumerate(r)]
                for i, r in enumerate(self.max_e)]
        errs = validate_state(total, alloc, maxm)
        if errs:
            raise ValueError("\n".join(errs))
        return total, alloc, maxm

    def start_index(self):
        try:
            return int(self.start_var.get()[1:])
        except ValueError:
            return 0

    def show(self, lines, banner, color, bgcolor):
        self.banner.configure(text=banner, fg=color, bg=bgcolor)
        self.out.configure(state="normal")
        self.out.delete("1.0", "end")
        for text, tag in lines:
            self.out.insert("end", text + "\n", tag)
        self.out.configure(state="disabled")
        self.out.yview_moveto(0)

    def run_safety(self):
        try:
            total, alloc, maxm = self.read_state()
        except ValueError as ex:
            messagebox.showerror("Invalid input", str(ex))
            return
        lines, res = report_safety(total, alloc, maxm, self.start_index())
        if res["safe"]:
            self.show(lines, "SAFE STATE", "#0b2b1a", GREEN)
        else:
            self.show(lines, "UNSAFE STATE", "#33080f", RED)

    def run_scan(self):
        try:
            total, alloc, maxm = self.read_state()
        except ValueError as ex:
            messagebox.showerror("Invalid input", str(ex))
            return

        start = self.start_index()
        need = compute_need(maxm, alloc)
        avail = compute_available(total, alloc)
        res = safety_check(avail, alloc, need, start)

        lines = [(f"=== SCAN STARTING AT P{start} ===", "h"),
                 (f"Available = {fmt_vec(avail)}", "info"),
                 ("", "n")]

        for number, s in enumerate(res["steps"], 1):
            text = (f"{number}. Check P{s['process']}: "
                    f"Need{fmt_vec(s['need'])} <= Work{fmt_vec(s['work_before'])}")
            if s["ok"]:
                lines.append((f"{text} -> YES, runs. "
                              f"New Work = {fmt_vec(s['work_after'])}", "ok"))
            else:
                lines.append((f"{text} -> NO, skip", "bad"))

        lines.append(("", "n"))
        if res["safe"]:
            seq = ", ".join(f"P{i}" for i in res["sequence"])
            lines.append((f"SAFE SEQUENCE: < {seq} >", "ok"))
            self.show(lines, "SAFE STATE", "#0b2b1a", GREEN)
        else:
            lines.append(("No remaining process can run.", "bad"))
            self.show(lines, "UNSAFE STATE", "#33080f", RED)

    def run_request(self):
        try:
            total, alloc, maxm = self.read_state()
            pid = int(self.pid_var.get()[1:])
            req = [self.read_int(e, f"Request {chr(65 + j)}") for j, e in enumerate(self.req_e)]
        except ValueError as ex:
            messagebox.showerror("Invalid input", str(ex))
            return
        lines, res = report_request(pid, req, total, alloc, maxm,
                                    self.start_index())
        d = res["decision"]
        if d == "GRANT":
            self.show(lines, f"GRANT  -  P{pid} request {fmt_vec(req)}", "#0b2b1a", GREEN)
            if self.apply_var.get():
                self.fill(self.alloc_e[pid], vec_add(alloc[pid], req))
        elif d == "WAIT":
            self.show(lines, f"WAIT  -  P{pid} must wait", "#33080f", RED)
        else:
            self.show(lines, f"ERROR  -  P{pid} exceeded its maximum claim", "#33080f", RED)

    def on_resize(self, ev):
        if ev.width < 50 or ev.height < 50:
            return
        self.w, self.h = ev.width, ev.height
        self.draw_background()
        self.canvas.itemconfigure(self.win, width=self.w - 50, height=self.h - 105)
        self.canvas.coords(self.win, self.w / 2, 82)
        for item, dy in ((self.title_shadow, 2), (self.title_main, 0)):
            self.canvas.coords(item, self.w / 2 + dy, 30 + dy)
        self.canvas.coords(self.sub, self.w / 2, 60)
        self.canvas.coords(self.clock, self.w - 24, 16)
        self.position_logo(42, 40)
        self.canvas.itemconfigure(self.title_main, text="DEADLOCK BREAKER")
        self.canvas.itemconfigure(self.title_shadow, text="DEADLOCK BREAKER")
        self.canvas.itemconfigure(self.sub, text="Banker's Algorithm - Deadlock Avoidance Simulator")
        self.canvas.tag_raise(self.title_shadow)
        self.canvas.tag_raise(self.title_main)
        self.canvas.tag_raise(self.sub)
        self.canvas.tag_raise(self.clock)
        self.canvas.tag_raise("logo")

    def position_logo(self, x, y):
        self.canvas.coords(self.logo_items["ring"], x - 24, y - 24,
                           x + 24, y + 24)
        node_points = ((x, y - 12), (x - 12, y + 9), (x + 12, y + 9))
        for item, start, end in zip(
                self.logo_items["links"],
                (node_points[0], node_points[1], node_points[2]),
                (node_points[1], node_points[2], node_points[0])):
            self.canvas.coords(item, *start, *end)
        for item, (nx, ny) in zip(self.logo_items["nodes"], node_points):
            self.canvas.coords(item, nx - 4, ny - 4, nx + 4, ny + 4)
        self.canvas.coords(self.logo_items["badge"], x + 12, y + 9,
                           x + 26, y + 23)
        self.canvas.coords(self.logo_items["check"], x + 15, y + 16,
                           x + 18, y + 19, x + 23, y + 13)

    def update_clock(self):
        self.canvas.itemconfigure(
            self.clock, text=datetime.now().strftime("%b %d, %Y\n%I:%M:%S %p"))
        self.root.after(1000, self.update_clock)

    def draw_background(self):
        c = self.canvas
        c.delete("bg")
        w, h = self.w, self.h
        th = THEMES[self.theme]
        band = 4
        for y in range(0, h, band):
            col = rgb(lerp(th["top"], th["bottom"], y / max(1, h)))
            c.create_rectangle(0, y, w, y + band, fill=col, outline=col, tags="bg")
        rnd = random.Random(7)
        if th["stars"]:
            for _ in range(130):
                x, y = rnd.randint(0, w), rnd.randint(0, int(h * 0.65))
                r = rnd.choice((1, 1, 1, 2))
                c.create_oval(x, y, x + r, y + r, fill="#ffffff", outline="", tags=("bg", "star"))
        ox, oy = int(w * 0.84), int(h * 0.2)
        for k, rad in enumerate((120, 90, 65)):
            col = rgb(lerp(th["top"], (255, 255, 255), 0.12 + 0.1 * k))
            c.create_oval(ox - rad, oy - rad, ox + rad, oy + rad, fill=col, outline="", tags="bg")
        c.create_oval(ox - 44, oy - 44, ox + 44, oy + 44, fill=th["orb"], outline="", tags="bg")
        base = h
        x = 0
        while x < w:
            bw = rnd.randint(28, 70)
            bh = rnd.randint(40, 150)
            c.create_rectangle(x, base - bh, x + bw, base, fill=th["sky_city"], outline="", tags="bg")
            for wy in range(base - bh + 8, base - 6, 14):
                for wx in range(x + 6, x + bw - 6, 12):
                    if rnd.random() < 0.28:
                        c.create_rectangle(wx, wy, wx + 4, wy + 6, fill="#ffe9a8", outline="", tags="bg")
            x += bw + rnd.randint(0, 6)
        c.tag_lower("bg")
        self.update_header_colors()

    def update_header_colors(self):
        th = THEMES[self.theme]
        for item, key in ((self.title_main, "title"), (self.title_shadow, "shadow"),
                          (self.sub, "text"), (self.clock, "text")):
            self.canvas.itemconfigure(item, fill=th[key])

    def cycle_theme(self):
        order = list(THEMES)
        i = order.index(self.theme) if self.theme in order else 0
        self.theme = order[(i + 1) % len(order)]
        self.draw_background()

    def make_petals(self, count):
        for _ in range(count):
            size = random.uniform(5, 11)
            col = random.choice(("#ffc2dd", "#ffadd0", "#ffd9ea", "#ff9ec6"))
            x, y = random.uniform(0, self.w), random.uniform(0, self.h)
            pid = self.canvas.create_oval(x, y, x + size, y + size * 0.6,
                                          fill=col, outline="", tags="petal")
            self.petals.append({"id": pid, "vy": random.uniform(0.8, 2.2),
                                "ph": random.uniform(0, 6.28), "sz": size})

    def animate(self):
        self.t += 0.05
        for p in self.petals:
            dx = math.sin(self.t + p["ph"]) * 0.9 + 0.6
            self.canvas.move(p["id"], dx, p["vy"])
            x1, y1, x2, y2 = self.canvas.coords(p["id"])
            if y1 > self.h or x1 > self.w:
                nx = random.uniform(-40, self.w)
                self.canvas.coords(p["id"], nx, -20, nx + p["sz"], -20 + p["sz"] * 0.6)
        for s in self.canvas.find_withtag("star"):
            if random.random() < 0.02:
                cur = self.canvas.itemcget(s, "fill")
                self.canvas.itemconfigure(s, fill="#8a84c8" if cur == "#ffffff" else "#ffffff")
        self.canvas.tag_raise("petal")
        self.canvas.tag_raise(self.title_shadow)
        self.canvas.tag_raise(self.title_main)
        self.canvas.tag_raise(self.sub)
        self.canvas.tag_raise(self.clock)
        self.canvas.tag_raise("logo")
        self.root.after(40, self.animate)
