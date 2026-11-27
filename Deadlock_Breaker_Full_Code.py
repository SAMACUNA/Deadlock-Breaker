import io
import math
import random
import sys
import unittest
from datetime import datetime

try:
    import tkinter as tk
    import tkinter.font as tkfont
    from tkinter import ttk, messagebox
except ImportError:
    tk = None


def vec_le(a, b):
    return all(x <= y for x, y in zip(a, b))


def vec_add(a, b):
    return [x + y for x, y in zip(a, b)]


def vec_sub(a, b):
    return [x - y for x, y in zip(a, b)]


def fmt_vec(v):
    return "(" + ", ".join(str(x) for x in v) + ")"


def compute_need(maxm, alloc):
    return [vec_sub(m, a) for m, a in zip(maxm, alloc)]


def compute_available(total, alloc):
    col_sums = [sum(col) for col in zip(*alloc)]
    return vec_sub(total, col_sums)


def validate_state(total, alloc, maxm):
    errors = []
    m = len(total)
    n = len(alloc)
    if n == 0 or m == 0:
        return ["At least one process and one resource type are required."]
    if len(maxm) != n:
        errors.append("Allocation and Max must have the same number of rows.")
        return errors
    if any(len(row) != m for row in alloc):
        errors.append("Every Allocation row must match the resource vector length.")
    if any(len(row) != m for row in maxm):
        errors.append("Every Max row must match the resource vector length.")
    if errors:
        return errors
    if any(x < 0 for x in total):
        errors.append("Total vector cannot contain negative values.")
    for i in range(n):
        if len(alloc[i]) != m or len(maxm[i]) != m:
            continue
        if any(x < 0 for x in alloc[i]):
            errors.append(f"P{i}: Allocation cannot be negative.")
        if any(x < 0 for x in maxm[i]):
            errors.append(f"P{i}: Max cannot be negative.")
        if not vec_le(alloc[i], maxm[i]):
            errors.append(f"P{i}: Allocation {fmt_vec(alloc[i])} exceeds "
                          f"Max {fmt_vec(maxm[i])} (Need would be negative).")
    col_sums = [sum(col) for col in zip(*alloc)]
    for j, (s, t) in enumerate(zip(col_sums, total)):
        if s > t:
            errors.append(f"Resource {chr(65 + j)}: allocated {s} is more than "
                          f"the total {t}.")
    return errors


def safety_check(available, alloc, need, start=0):
    n = len(alloc)
    work = list(available)
    finish = [False] * n
    sequence = []
    steps = []
    pos = start % n

    while not all(finish):
        progressed = False
        for k in range(n):
            i = (pos + k) % n
            if finish[i]:
                continue
            ok = vec_le(need[i], work)
            step = {"process": i, "need": list(need[i]),
                    "work_before": list(work), "ok": ok}
            if ok:
                work = vec_add(work, alloc[i])
                finish[i] = True
                sequence.append(i)
                step["work_after"] = list(work)
                step["finish"] = list(finish)
                steps.append(step)
                pos = (i + 1) % n
                progressed = True
                break
            steps.append(step)
        if not progressed:
            break

    return {"safe": all(finish), "sequence": sequence, "finish": finish,
            "steps": steps, "work": work}


def request_check(pid, request, total, alloc, maxm, start=0):
    if not isinstance(pid, int) or pid < 0 or pid >= len(alloc):
        return {"pid": pid, "request": list(request), "need_row": [],
                "available": [], "checks": {}, "tentative": None,
                "safety": None, "decision": "ERROR",
                "reason": "Invalid process ID."}
    if len(request) != len(total):
        return {"pid": pid, "request": list(request),
                "need_row": [], "available": [], "checks": {},
                "tentative": None, "safety": None,
                "decision": "ERROR",
                "reason": "Request vector length does not match the resource types."}
    need = compute_need(maxm, alloc)
    available = compute_available(total, alloc)
    out = {"pid": pid, "request": list(request), "need_row": list(need[pid]),
           "available": list(available), "checks": {}, "tentative": None,
           "safety": None}

    if any(x < 0 for x in request):
        out.update(decision="ERROR", reason="Request contains negative values.")
        return out

    le_need = vec_le(request, need[pid])
    out["checks"]["request_le_need"] = le_need
    if not le_need:
        out.update(decision="ERROR",
                   reason=f"P{pid}: Request exceeds Need.")
        return out

    le_avail = vec_le(request, available)
    out["checks"]["request_le_available"] = le_avail
    if not le_avail:
        out.update(decision="WAIT",
                   reason="Not enough resources are available right now "
                          "(Request > Available).")
        return out

    new_avail = vec_sub(available, request)
    new_alloc = [list(r) for r in alloc]
    new_alloc[pid] = vec_add(alloc[pid], request)
    new_need = [list(r) for r in need]
    new_need[pid] = vec_sub(need[pid], request)
    out["tentative"] = {"available": new_avail, "allocation": new_alloc,
                        "need": new_need}

    res = safety_check(new_avail, new_alloc, new_need, start)
    out["safety"] = res
    if res["safe"]:
        out.update(decision="GRANT",
                   reason="The tentative state is SAFE, so the request is "
                          "granted.")
    else:
        out.update(decision="WAIT",
                   reason="The tentative state is UNSAFE. The allocation is "
                          "rolled back and the process must wait.")
    return out


def _table(headers, rows):
    widths = [max(len(str(h)), *(len(str(r[c])) for r in rows))
              for c, h in enumerate(headers)]
    line = "+" + "+".join("-" * (w + 2) for w in widths) + "+"

    def row(cells):
        return "| " + " | ".join(str(c).ljust(w)
                                  for c, w in zip(cells, widths)) + " |"
    out = [line, row(headers), line]
    out += [row(r) for r in rows]
    out.append(line)
    return out


def _sv(v):
    return " ".join(str(x) for x in v)


def report_state(total, alloc, maxm):
    need = compute_need(maxm, alloc)
    avail = compute_available(total, alloc)
    m = len(total)
    names = " ".join(chr(65 + j) for j in range(m))
    L = [("=== SYSTEM STATE ===", "h"),
         (f"Total     = {_sv(total)}", "n"),
         (f"Allocated = {_sv([sum(c) for c in zip(*alloc)])}  "
          f"(sum of Allocation columns)", "n"),
         (f"Available = Total - Allocated = {_sv(total)} - "
          f"{_sv([sum(c) for c in zip(*alloc)])} = {_sv(avail)}", "info"),
         ("", "n")]
    hdr = ["Process", f"Allocation ({names})", f"Max ({names})",
           f"Need ({names})", "Available / Work"]
    rows = []
    for i in range(len(alloc)):
        rows.append([f"P{i}", _sv(alloc[i]), _sv(maxm[i]), _sv(need[i]),
                     _sv(avail) if i == 0 else ""])
    for t in _table(hdr, rows):
        L.append((t, "n"))
    L.append(("Need = Max - Allocation", "info"))
    L.append(("", "n"))
    return L


def _fmt_finish(flags):
    return "[" + ", ".join("T" if f else "F" for f in flags) + "]"


def report_safety_trace(available, alloc, need, result, heading):
    L = [(heading, "h"),
         ("Work = Available;  Finish[i] = False for all i.", "n"),
         ("A process Pi can run when Need[i] <= Work (every resource).", "n"),
         ("", "n")]
    n = len(alloc)
    hdr = ["Iteration", "Work Before", "Process Selected",
           "Allocation Released", "Work After", "Checked (Need<=Work)", "Finish"]
    rows = [["Initial", "-", "-", "-", _sv(available), "-",
             _fmt_finish([False] * n)]]
    pending, it = [], 0
    for s in result["steps"]:
        i = s["process"]
        if not s["ok"]:
            pending.append(f"P{i} F")
            continue
        it += 1
        pending.append(f"P{i} T")
        rows.append([str(it), _sv(s["work_before"]), f"P{i}", _sv(alloc[i]),
                     _sv(s["work_after"]), ", ".join(pending),
                     _fmt_finish(s["finish"])])
        pending = []
    for t in _table(hdr, rows):
        L.append((t, "n"))
    L.append(("(Checked: T = Need <= Work so the process runs, "
              "F = skipped for now)", "info"))
    L.append(("", "n"))
    if result["safe"]:
        seq = ", ".join(f"P{i}" for i in result["sequence"])
        L.append((f"Finish flags: {_fmt_finish(result['finish'])}", "n"))
        L.append((f"RESULT: SAFE STATE.  Safe Sequence: < {seq} >", "ok"))
    else:
        stuck = [f"P{i}" for i, f in enumerate(result["finish"]) if not f]
        L.append((f"Finish flags: {_fmt_finish(result['finish'])}", "n"))
        L.append((f"No unfinished process has Need <= Work({_sv(result['work'])}).  "
                  f"Stuck: {', '.join(stuck)}", "bad"))
        L.append(("RESULT: UNSAFE STATE", "bad"))
    return L


def report_safety(total, alloc, maxm, start=0):
    need = compute_need(maxm, alloc)
    avail = compute_available(total, alloc)
    res = safety_check(avail, alloc, need, start)
    L = report_state(total, alloc, maxm)
    L += report_safety_trace(avail, alloc, need, res,
                             "=== SAFETY ALGORITHM ===")
    return L, res


def report_request(pid, request, total, alloc, maxm, start=0):
    res = request_check(pid, request, total, alloc, maxm, start)
    L = report_state(total, alloc, maxm)
    L.append((f"=== RESOURCE REQUEST: P{pid} requests {fmt_vec(request)} ===", "h"))
    need_row = res["need_row"]
    avail = res["available"]
    c = res["checks"]
    if "request_le_need" in c:
        ok = c["request_le_need"]
        L.append((f"Step A (Check Need):      Request{fmt_vec(request)} <= "
                  f"Need{fmt_vec(need_row)} -> {'TRUE' if ok else 'FALSE'}",
                  "ok" if ok else "bad"))
    if "request_le_available" in c:
        ok = c["request_le_available"]
        L.append((f"Step B (Check Available): Request{fmt_vec(request)} <= "
                  f"Available{fmt_vec(avail)} -> {'TRUE' if ok else 'FALSE'}",
                  "ok" if ok else "bad"))
    if res["tentative"]:
        t = res["tentative"]
        L.append(("Step C (Tentative Allocation):", "n"))
        L.append((f"    New Available = {fmt_vec(avail)} - {fmt_vec(request)} = "
                  f"{fmt_vec(t['available'])}", "n"))
        L.append((f"    New Allocation(P{pid}) = {fmt_vec(alloc[pid])} + "
                  f"{fmt_vec(request)} = {fmt_vec(t['allocation'][pid])}", "n"))
        L.append((f"    New Need(P{pid}) = {fmt_vec(need_row)} - "
                  f"{fmt_vec(request)} = {fmt_vec(t['need'][pid])}", "n"))
        L.append(("", "n"))
        L += report_safety_trace(t["available"], t["allocation"], t["need"],
                                 res["safety"],
                                 "Step D (Safety check on tentative state):")
    L.append(("", "n"))
    tag = {"GRANT": "ok", "WAIT": "bad", "ERROR": "bad"}[res["decision"]]
    L.append((f"DECISION: {res['decision']}  -  {res['reason']}", tag))
    return L, res


def to_plain(lines):
    return "\n".join(t for t, _ in lines)


SAMPLE = {
    "total": [10, 5, 7],
    "alloc": [[0, 1, 0], [2, 0, 0], [3, 0, 2], [2, 1, 1], [0, 0, 2]],
    "max":   [[7, 5, 3], [3, 2, 2], [9, 0, 2], [2, 2, 2], [4, 3, 3]],
}

SAMPLE2 = {
    "total": [9, 5, 7],
    "alloc": [[1, 0, 1], [2, 1, 0], [3, 0, 2], [0, 2, 1]],
    "max":   [[4, 2, 2], [3, 2, 2], [6, 1, 3], [2, 3, 2]],
}
SAMPLES = {"Sample 1 (lecture)": SAMPLE, "Sample 2": SAMPLE2}


ALGO_TEXT = [
    ("BANKER'S ALGORITHM - HOW IT WORKS", "h"),
    ("", "n"),
    ("The Banker's Algorithm is a deadlock AVOIDANCE method. Before granting a", "n"),
    ("resource request, the system checks whether the resulting state is still", "n"),
    ("SAFE. If it is not safe, the request is refused and the process waits.", "n"),
    ("", "n"),
    ("DATA STRUCTURES", "h"),
    ("  Total       Total number of instances of each resource type.", "n"),
    ("  Allocation  Resources currently held by each process.", "n"),
    ("  Max         Maximum resources each process may ever need.", "n"),
    ("  Need        Resources each process may still request.", "n"),
    ("  Available   Resources that are free right now.", "n"),
    ("", "n"),
    ("FORMULAS", "h"),
    ("  Need      = Max - Allocation", "info"),
    ("  Available = Total - (sum of all Allocation rows)", "info"),
    ("", "n"),
    ("SAFE STATE", "h"),
    ("A state is SAFE if there is an order of the processes (a safe sequence)", "n"),
    ("in which every process can obtain what it still needs, run to completion,", "n"),
    ("and release everything it holds. An UNSAFE state does not mean deadlock", "n"),
    ("has happened yet, only that deadlock is possible.", "n"),
    ("", "n"),
    ("SAFETY ALGORITHM", "h"),
    ("  1. Set Work = Available and Finish[i] = False for every process.", "n"),
    ("  2. Find a process Pi with Finish[i] = False and Need[i] <= Work.", "n"),
    ("  3. If found: Work = Work + Allocation[i], Finish[i] = True, add Pi to", "n"),
    ("     the safe sequence, then go back to step 2.", "n"),
    ("  4. If none is found: if every Finish[i] is True the state is SAFE,", "n"),
    ("     otherwise the state is UNSAFE.", "n"),
    ("", "n"),
    ("RESOURCE-REQUEST ALGORITHM", "h"),
    ("When process Pi asks for a Request vector:", "n"),
    ("  1. If Request <= Need[i], continue. Otherwise it is an ERROR because", "n"),
    ("     the process has exceeded its maximum claim.", "n"),
    ("  2. If Request <= Available, continue. Otherwise Pi must WAIT.", "n"),
    ("  3. Pretend to allocate the resources:", "n"),
    ("       Available     = Available - Request", "info"),
    ("       Allocation[i] = Allocation[i] + Request", "info"),
    ("       Need[i]       = Need[i] - Request", "info"),
    ("  4. Run the Safety Algorithm on this tentative state.", "n"),
    ("       SAFE   -> the request is GRANTED.", "ok"),
    ("       UNSAFE -> the allocation is rolled back and Pi must WAIT.", "bad"),
    ("", "n"),
    ("USING THE SIMULATOR", "h"),
    ("  - Set the number of processes and resource types, then press Set Size.", "n"),
    ("  - Fill in the Total vector, and the Allocation and Max tables.", "n"),
    ("  - Press Run Safety Check to see the full step-by-step trace.", "n"),
    ("  - Press Scan to see each process check from the chosen start.", "n"),
    ("  - Use the Resource Request panel to test a request from one process.", "n"),
    ("  - 'Scan starts at' chooses which process is checked first.", "n"),
]


def demo():
    lines, _ = report_safety(SAMPLE["total"], SAMPLE["alloc"], SAMPLE["max"])
    print(to_plain(lines))
    print()
    lines, _ = report_request(1, [1, 0, 2], SAMPLE["total"], SAMPLE["alloc"],
                              SAMPLE["max"])
    print(to_plain(lines))


S = SAMPLE


class TestBanker(unittest.TestCase):
    def test_tc1_safe_state(self):
        need = compute_need(S["max"], S["alloc"])
        self.assertEqual(need, [[7, 4, 3], [1, 2, 2], [6, 0, 0], [0, 1, 1], [4, 3, 1]])
        avail = compute_available(S["total"], S["alloc"])
        self.assertEqual(avail, [3, 3, 2])
        res = safety_check(avail, S["alloc"], need)
        self.assertTrue(res["safe"])
        self.assertEqual(res["sequence"], [1, 3, 4, 0, 2])
        self.assertEqual(res["work"], [10, 5, 7])

    def test_tc2_unsafe_state(self):
        total, alloc, maxm = [2], [[1], [1]], [[2], [2]]
        need = compute_need(maxm, alloc)
        res = safety_check(compute_available(total, alloc), alloc, need)
        self.assertFalse(res["safe"])
        self.assertEqual(res["sequence"], [])

    def test_tc3_request_grant(self):
        r = request_check(1, [1, 0, 2], S["total"], S["alloc"], S["max"])
        self.assertEqual(r["decision"], "GRANT")
        self.assertEqual(r["tentative"]["available"], [2, 3, 0])
        self.assertEqual(r["tentative"]["allocation"][1], [3, 0, 2])
        self.assertEqual(r["tentative"]["need"][1], [0, 2, 0])

    def test_tc4_request_exceeds_need(self):
        r = request_check(1, [2, 0, 0], S["total"], S["alloc"], S["max"])
        self.assertEqual(r["decision"], "ERROR")

    def test_tc5_request_exceeds_available(self):
        r = request_check(0, [4, 0, 0], S["total"], S["alloc"], S["max"])
        self.assertEqual(r["decision"], "WAIT")
        self.assertFalse(r["checks"]["request_le_available"])

    def test_tc6_request_unsafe(self):
        r = request_check(4, [3, 3, 0], S["total"], S["alloc"], S["max"])
        self.assertEqual(r["decision"], "WAIT")
        self.assertFalse(r["safety"]["safe"])

    def test_tc8_second_example(self):
        S2 = SAMPLE2
        need = compute_need(S2["max"], S2["alloc"])
        self.assertEqual(need, [[3, 2, 1], [1, 1, 2], [3, 1, 1], [2, 1, 1]])
        avail = compute_available(S2["total"], S2["alloc"])
        self.assertEqual(avail, [3, 2, 3])
        res = safety_check(avail, S2["alloc"], need, start=1)
        self.assertEqual(res["sequence"], [1, 2, 3, 0])
        works = [s["work_after"] for s in res["steps"] if s["ok"]]
        self.assertEqual(works, [[5, 3, 3], [8, 3, 5], [8, 5, 6], [9, 5, 7]])
        self.assertTrue(safety_check(avail, S2["alloc"], need)["safe"])

    def test_tc7_validation(self):
        self.assertEqual(validate_state(S["total"], S["alloc"], S["max"]), [])
        bad = validate_state([1], [[2]], [[1]])
        self.assertTrue(bad)


def _safe_text(total, alloc, maxm, start=0):
    need = compute_need(maxm, alloc)
    res = safety_check(compute_available(total, alloc), alloc, need, start)
    if not res["safe"]:
        return "UNSAFE STATE"
    return "SAFE  < " + ", ".join(f"P{i}" for i in res["sequence"]) + " >"


def _decision(pid, req):
    return request_check(pid, req, S["total"], S["alloc"], S["max"])["decision"]


def _cases():
    return [
        ("TC1 safe state (lecture)", "SAFE  < P1, P3, P4, P0, P2 >",
         lambda: _safe_text(S["total"], S["alloc"], S["max"])),
        ("TC2 unsafe state", "UNSAFE STATE",
         lambda: _safe_text([2], [[1], [1]], [[2], [2]])),
        ("TC3 P1 requests (1,0,2)", "GRANT", lambda: _decision(1, [1, 0, 2])),
        ("TC4 P1 requests (2,0,0)", "ERROR", lambda: _decision(1, [2, 0, 0])),
        ("TC5 P0 requests (4,0,0)", "WAIT", lambda: _decision(0, [4, 0, 0])),
        ("TC6 P4 requests (3,3,0)", "WAIT", lambda: _decision(4, [3, 3, 0])),
        ("TC8 second example, start P1", "SAFE  < P1, P2, P3, P0 >",
         lambda: _safe_text(SAMPLE2["total"], SAMPLE2["alloc"], SAMPLE2["max"], 1)),
    ]


def run_test_report():
    lines = [("TEST CASES - expected vs. actual", "h"), ("", "n"),
             (f"{'Test case':30} {'Expected':30} {'Actual':30} Result", "info")]
    all_ok = True
    for name, exp, fn in _cases():
        try:
            act = fn()
        except Exception as ex:
            act = f"EXCEPTION: {ex}"
        ok = act == exp
        all_ok = all_ok and ok
        lines.append((f"{name:30} {exp:30} {act:30} {'PASS' if ok else 'FAIL'}",
                      "ok" if ok else "bad"))
    lines += [("", "n"), ("unittest results", "h")]
    buf = io.StringIO()
    res = unittest.TextTestRunner(stream=buf, verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(TestBanker))
    for ln in buf.getvalue().splitlines():
        lines.append((ln, "bad" if ("FAIL" in ln or "ERROR" in ln) else "n"))
    all_ok = all_ok and res.wasSuccessful()
    lines += [("", "n"), ("ALL TESTS PASSED" if all_ok else "SOME TESTS FAILED",
                          "ok" if all_ok else "bad")]
    return lines, all_ok


PANEL = "#17142e"
PANEL2 = "#221d45"
ENTRY = "#2c2658"
FG = "#f4ecff"
PINK = "#ff8fc7"
CYAN = "#7ee8fa"
GREEN = "#7dffb0"
RED = "#ff7b8f"

THEMES = {
    "night": {"top": (12, 10, 44), "bottom": (120, 52, 130), "stars": True,
              "orb": "#fff6c9", "glow": "#cdb8ff", "sky_city": "#0b0820",
              "title": "#ff8fc7", "shadow": "#000000", "text": "#7ee8fa"},
    "sunset": {"top": (255, 148, 170), "bottom": (255, 214, 140), "stars": False,
               "orb": "#fff2e0", "glow": "#ffc2a0", "sky_city": "#3a1b46",
               "title": "#4a1250", "shadow": "#ffffff", "text": "#2b0a3d"},
}


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def rgb(c):
    return "#%02x%02x%02x" % c


BUTTON_STYLES = {
    "pink":   ("#ff8fc7", "#ffb3da", "#1a0f2e"),
    "green":  ("#7dffb0", "#b0ffd0", "#0b2b1a"),
    "cyan":   ("#7ee8fa", "#b5f3ff", "#0c2430"),
    "purple": ("#6c55c9", "#8a72e8", "#ffffff"),
    "red":    ("#ff7b8f", "#ffa3b1", "#33080f"),
    "gold":   ("#ffd479", "#ffe4a8", "#33240a"),
}


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


def main():
    if "--test" in sys.argv:
        lines, ok = run_test_report()
        print(to_plain(lines))
        sys.exit(0 if ok else 1)
    if "--demo" in sys.argv:
        demo()
        return
    if tk is None:
        print("tkinter is not installed. Install it (Linux: sudo apt install "
              "python3-tk) or use --test / --demo.")
        return
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
