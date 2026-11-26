import io
import unittest


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
