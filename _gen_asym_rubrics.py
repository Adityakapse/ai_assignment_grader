"""Temporary generator: writes rubric.json for asym-6..21.

Mirrors the two existing rubric templates:
  - 11-point "Part-C" template  (like asym-1 / asym-3): g called once after f's loop
  - 10-point "per-iteration" template (like asym-2/4/5): g called inside f's loop

Re-runnable: overwrites each datastore/rubrics/asym-N/rubric.json.
"""
import json
import os

RUBRIC_DIR = os.path.join(os.path.dirname(__file__), "datastore", "rubrics")


def bucket(label, marks, desc):
    return {"label": label, "marks": marks, "description": desc}


def pt(pid, name, tag, mx, semi_marks, target, wrong, semi, correct, note=None):
    p = {
        "id": pid,
        "name": name,
        "tag": tag,
        "max_marks": mx,
        "target": target,
        "buckets": [
            bucket("Wrong", 0, wrong),
            bucket("Semi", semi_marks, semi),
            bucket("Correct", mx, correct),
        ],
    }
    if note:
        p["note"] = note
    return p


STRUCT_WRONG = ("Analysis does not clearly separate f vs g, or loops vs non-loops, "
                "and line numbers are unclear or missing.")
STRUCT_SEMI = ("Some attempt to separate components or refer to line numbers, but "
               "structure is incomplete or ambiguous.")
CONST_TARGET = "All non-loop code in f and g is Theta(1)."
CONST_WRONG = "Non-loop code not analysed or incorrectly claimed to be non-constant."
CONST_SEMI = "Some constant-time segments identified but others missing."
CONST_CORRECT = "All non-loop regions (initialisations and returns in f and g) stated as Theta(1)."
DD_NOTE = "Double deduction applies here."


def build_periter(p):
    pts = [
        pt(1, "Splitting code into parts + referencing line numbers", "structure", 5, 3,
           "Clear separation of f and g; loop vs non-loop code identified; line numbers referenced consistently.",
           STRUCT_WRONG, STRUCT_SEMI, p["struct_correct"]),
        pt(2, "Constant-time non-loop parts", "const-time", 5, 3,
           CONST_TARGET, CONST_WRONG, CONST_SEMI, CONST_CORRECT),
        pt(3, "f(): Loop iterations", "f-iters", 12, 6,
           p["f_iters"] + " iterations of " + p["f_loop"] + ".",
           p.get("f_iters_wrong", "Iteration count missing or not " + p["f_iters"] + "."),
           p["f_iters_semi"], p["f_iters_correct"]),
        pt(4, "f(): Cost per iteration", "f-per-iter", 12, 6,
           p["tg"] + " per iteration, dominated by the call to g.",
           "Claims Theta(1) per iteration or ignores the cost of g.",
           "Recognises the call to g but does not establish " + p["tg"] + " per iteration.",
           p["f_per_correct"]),
        pt(5, "f(): Total loop cost", "f-total-loop", 8, 4,
           p["tf"] + " from " + p["f_total_expr"] + ".",
           "No multiplication of iteration count x per-iteration cost, or unrelated complexity.",
           "Multiplies own values but final simplification or reasoning is unclear or incorrect.",
           p["f_total_expr"] + ", with justification."),
        pt(6, "g(): Loop iterations", "g-iters", 12, 6,
           p["g_iters"] + " iterations of " + p["g_loop"] + ".",
           "Iteration count missing or not " + p["g_iters"] + ".",
           p["g_iters_semi"], p["g_iters_correct"]),
        pt(7, "g(): Cost per iteration", "g-per-iter", 12, 6,
           "Theta(1) per iteration.",
           "Claims non-constant per-iteration cost.",
           "Suggests constant time but lacks explicit Theta(1) justification.",
           "Each iteration Theta(1): " + p["g_per_ops"] + "."),
        pt(8, "g(): Total loop cost", "g-total-loop", 8, 4,
           p["tg"] + " = " + p["g_total_expr"] + ".",
           "Does not combine iteration count x per-iteration cost.",
           "Attempts multiplication using own values but unclear or partially derived.",
           p["g_total_expr"] + ", with justification."),
        pt(9, "Overall worst-case runtime of g", "overall-g", 12, 6,
           "T_g(N) = " + p["tg"] + ", summing the constant-time parts and the loop.",
           "Runtime absent or incompatible with earlier analysis.",
           "States " + p["tg"] + " but with missing reasoning.",
           p["overall_g_expr"] + ".", note=DD_NOTE),
        pt(10, "Overall worst-case runtime of f", "overall-f", 14, 7,
           "T_f(N) = " + p["tf"] + ", accounting for non-loop parts + loop.",
           "Final complexity missing/incorrect and not derived from loop analysis.",
           "States " + p["tf"] + " but with missing reasoning.",
           p["overall_f_expr"] + ".", note=DD_NOTE),
    ]
    notes = [
        "No double deduction (except in points 9 and 10). Do not deduct again for an error already penalised in an earlier point.",
        "Students can use Theta or big-O notation with tight bounds.",
    ] + p.get("notes", []) + [
        "The intended answers are T_f(N) = " + p["tf"] + " and T_g(N) = " + p["tg"] + ".",
    ]
    return pts, notes


def build_partc(p):
    pts = [
        pt(1, "Splitting code into parts + referencing line numbers", "structure", 5, 3,
           "Clear separation of f and g; loops vs non-loop code identified; line numbers referenced consistently.",
           STRUCT_WRONG, STRUCT_SEMI, p["struct_correct"]),
        pt(2, "Constant-time non-loop parts", "const-time", 5, 3,
           CONST_TARGET, CONST_WRONG, CONST_SEMI, CONST_CORRECT),
        pt(3, "f(): " + p["f_iters_name"], "f-iters", 12, 6,
           p["f_iters"] + " " + p["iters_of"] + ".",
           p.get("f_iters_wrong", "Iteration count missing or not " + p["f_iters"] + "."),
           p["f_iters_semi"], p["f_iters_correct"]),
        pt(4, "f(): Cost per iteration", "f-per-iter", 12, 6,
           "Theta(1) per iteration.",
           "Claims non-constant per-iteration cost, or does not clearly state cost per iteration.",
           "Suggests constant time but with incomplete reasoning.",
           "States Theta(1), justified by " + p["f_per_ops"] + "; loop checks and increments are Theta(1)."),
        pt(5, "f(): Total loop cost = iterations x per-iteration", "f-total-loop", 8, 4,
           p["f_loop_total"] + " from " + p["f_total_expr"] + ".",
           "No multiplication of iteration count x per-iteration cost, or total complexity that does not match own previous analysis.",
           "Multiplies own values but final simplification or reasoning is unclear or incorrect.",
           p["f_total_expr"] + ", with justification."),
        pt(6, "f(): Cost of Part C (call to g + constant work)", "f-partC", 6, 3,
           p["tg"] + ", accounting for both the cost of the g call and the constant-time return.",
           "Cost of Part C missing or incorrect.",
           "Notes that cost comes from g but unclear about " + p["tg"] + ".",
           "Accounts for the cost of the g call as " + p["tg"] + " and the addition / return as Theta(1)."),
        pt(7, "g(): Loop iterations", "g-iters", 10, 5,
           p["g_iters"] + " iterations of " + p["g_loop"] + ".",
           "Iteration count missing or not " + p["g_iters"] + ".",
           p["g_iters_semi"], p["g_iters_correct"]),
        pt(8, "g(): Cost per iteration", "g-per-iter", 8, 4,
           "Theta(1) per iteration.",
           "Claims non-constant per-iteration cost, or does not clearly state cost per iteration.",
           "Suggests operations are small/constant but lacks explicit Theta(1) justification.",
           "Each iteration Theta(1): " + p["g_per_ops"] + "."),
        pt(9, "g(): Total loop cost", "g-total-loop", 6, 3,
           p["tg"] + " = " + p["g_total_expr"] + ".",
           "Does not combine iteration count x per-iteration cost, or resulting complexity is incompatible with own values.",
           "Attempts multiplication using own values but expression or simplification is unclear or incorrect.",
           p["g_total_expr"] + ", with justification."),
        pt(10, "Overall worst-case runtime of g", "overall-g", 12, 6,
           "T_g(N) = " + p["tg"] + ", summing the constant-time parts and the loop.",
           "Runtime absent or incompatible with earlier analysis.",
           "States " + p["tg"] + " but with missing reasoning.",
           p["overall_g_expr"] + ".", note=DD_NOTE),
        pt(11, "Overall worst-case runtime of f", "overall-f", 16, 8,
           "T_f(N) = " + p["tf"] + ", accounting for non-loop parts + loop + Part C.",
           "Final complexity missing/incorrect and not derived from loop analysis.",
           "States " + p["tf"] + " but with missing reasoning.",
           p["overall_f_expr"] + ".", note=DD_NOTE),
    ]
    notes = [
        "No double deduction (except in points 10 and 11). Do not deduct again for an error already penalised in an earlier point.",
        "Students can use Theta or big-O notation with tight bounds.",
    ] + p.get("notes", []) + [
        "The intended answers are T_f(N) = " + p["tf"] + " and T_g(N) = " + p["tg"] + ".",
    ]
    return pts, notes


def write_rubric(num, title_base, shape, p):
    p["task_id"] = "asym-" + str(num)
    pts, notes = (build_periter(p) if shape == "periter" else build_partc(p))
    rubric = {
        "task_id": "asym-" + str(num),
        "title": "Asymptotic Analysis Q" + str(num) + " - " + title_base,
        "rubric_type": "marks",
        "total_marks": 100,
        "general_notes": notes,
        "rubric_points": pts,
        "total_mark_template": "TOTAL MARK: SUM/100",
    }
    folder = os.path.join(RUBRIC_DIR, "asym-" + str(num))
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "rubric.json"), "w", encoding="utf-8") as fh:
        json.dump(rubric, fh, indent=2)
        fh.write("\n")
    total = sum(pt_["max_marks"] for pt_ in pts)
    return total, len(pts)


GP_BINSEARCH = "one midpoint computation, two array accesses, two comparisons, one update of l or r"
GP_LIN_ARR = "one array read and one += assignment"
GP_HALVE = "one array read, one += assignment, one division, one comparison"
G_BINSEARCH_SEMI = "States Theta(log N) but does not justify the halving of the interval."
G_BINSEARCH_CORR = "Justifies Theta(log N) by explaining that each iteration either returns or halves the search interval [l, r]."

NESTED_NOTE = "Both combined-analysis and separate-analysis approaches for nested loops are acceptable."

specs = []  # (num, title_base, shape, params)

# ---------- per-iteration (10-point) tasks ----------
specs.append((8, "Count Matches by Binary Search", "periter", {
    "tf": "Theta(N log N)", "tg": "Theta(log N)",
    "struct_correct": "Clear separation of f and g and identification of the call to g(b, a[i]) inside f's loop; line numbers referenced consistently.",
    "f_loop": "the outer for loop over a",
    "f_iters": "Theta(N)",
    "f_iters_semi": "States Theta(N) but with weak or incomplete justification.",
    "f_iters_correct": "Justifies Theta(N) by explaining that i increments from 0 to N-1 once per iteration.",
    "f_per_correct": "States Theta(log N) per iteration, justified by g(b, a[i]) being a binary search over b; the comparison and increment are Theta(1).",
    "f_total_expr": "Theta(N) x Theta(log N) = Theta(N log N)",
    "g_loop": "the binary-search while loop",
    "g_iters": "Theta(log N)",
    "g_iters_semi": G_BINSEARCH_SEMI, "g_iters_correct": G_BINSEARCH_CORR,
    "g_per_ops": GP_BINSEARCH,
    "g_total_expr": "Theta(log N) x Theta(1) = Theta(log N)",
    "overall_g_expr": "Theta(1) + Theta(log N) + Theta(1) = Theta(log N)",
    "overall_f_expr": "Theta(1) + Theta(N log N) + Theta(1) = Theta(N log N)",
}))

specs.append((9, "Halving Loop with Halving Helper", "periter", {
    "tf": "Theta((log N)^2)", "tg": "Theta(log N)",
    "struct_correct": "Clear separation of f and g and identification of the call to g(a, k) inside f's halving loop; line numbers referenced consistently.",
    "f_loop": "the outer halving while loop",
    "f_iters": "Theta(log N)",
    "f_iters_semi": "States Theta(log N) but does not explain the halving of k.",
    "f_iters_correct": "Justifies Theta(log N) by explaining that k starts at N and is divided by 2 each iteration until it reaches 0.",
    "f_per_correct": "States Theta(log N) per iteration in the worst case, justified by g(a, k) being a halving loop whose argument is at most N.",
    "f_total_expr": "Theta(log N) x Theta(log N) = Theta((log N)^2)",
    "g_loop": "the halving while loop",
    "g_iters": "Theta(log N)",
    "g_iters_semi": "States Theta(log N) but does not explain the halving of j.",
    "g_iters_correct": "Justifies Theta(log N) (worst case m = N) by explaining that j starts at m and is divided by 2 each iteration until it reaches 0.",
    "g_per_ops": GP_HALVE,
    "g_total_expr": "Theta(log N) x Theta(1) = Theta(log N)",
    "overall_g_expr": "Theta(1) + Theta(log N) + Theta(1) = Theta(log N)",
    "overall_f_expr": "Theta(1) + Theta((log N)^2) + Theta(1) = Theta((log N)^2)",
    "notes": ["The cost of g depends on its argument m; the worst case is m = N (the first call), giving Theta(log N) per call and Theta((log N)^2) overall for f."],
}))

specs.append((11, "Matrix Scan with Binary Search", "periter", {
    "tf": "Theta(N^2 log N)", "tg": "Theta(log N)",
    "struct_correct": "Clear separation of f and g and identification of the call to g(b, mat[i][j]) inside f's nested loops; line numbers referenced consistently.",
    "f_loop": "the nested loops over the matrix",
    "f_iters": "Theta(N^2)",
    "f_iters_semi": "States Theta(N^2) but with weak or incomplete justification.",
    "f_iters_correct": "Justifies Theta(N^2) by explaining that the outer and inner loops each run N times, so the body runs N x N times.",
    "f_per_correct": "States Theta(log N) per iteration, justified by g(b, mat[i][j]) being a binary search over b; the matrix access, comparison and increment are Theta(1).",
    "f_total_expr": "Theta(N^2) x Theta(log N) = Theta(N^2 log N)",
    "g_loop": "the binary-search while loop",
    "g_iters": "Theta(log N)",
    "g_iters_semi": G_BINSEARCH_SEMI, "g_iters_correct": G_BINSEARCH_CORR,
    "g_per_ops": GP_BINSEARCH,
    "g_total_expr": "Theta(log N) x Theta(1) = Theta(log N)",
    "overall_g_expr": "Theta(1) + Theta(log N) + Theta(1) = Theta(log N)",
    "overall_f_expr": "Theta(1) + Theta(N^2 log N) + Theta(1) = Theta(N^2 log N)",
    "notes": [NESTED_NOTE],
}))

specs.append((13, "Character Frequency Sum", "periter", {
    "tf": "Theta(N^2)", "tg": "Theta(N)",
    "struct_correct": "Clear separation of f and g and identification of the call to g(s, s[i]) inside f's loop; line numbers referenced consistently.",
    "f_loop": "the outer for loop over the string",
    "f_iters": "Theta(N)",
    "f_iters_semi": "States Theta(N) but with weak or incomplete justification.",
    "f_iters_correct": "Justifies Theta(N) by explaining that i increments from 0 to N-1 once per iteration.",
    "f_per_correct": "States Theta(N) per iteration, justified by g scanning the whole string of length N regardless of x; the character access is Theta(1).",
    "f_total_expr": "Theta(N) x Theta(N) = Theta(N^2)",
    "g_loop": "the for loop over the string",
    "g_iters": "Theta(N)",
    "g_iters_semi": "States Theta(N) but explanation is incomplete.",
    "g_iters_correct": "Justifies Theta(N) because i runs from 0 to N-1, scanning the whole string.",
    "g_per_ops": "one character access, one comparison, possibly one increment",
    "g_total_expr": "Theta(N) x Theta(1) = Theta(N)",
    "overall_g_expr": "Theta(1) + Theta(N) + Theta(1) = Theta(N)",
    "overall_f_expr": "Theta(1) + Theta(N^2) + Theta(1) = Theta(N^2)",
}))

specs.append((14, "Doubling Counter with Linear Helper", "periter", {
    "tf": "Theta(N log N)", "tg": "Theta(N)",
    "struct_correct": "Clear separation of f and g and identification of the call to g(a) inside f's doubling loop; line numbers referenced consistently.",
    "f_loop": "the doubling while loop",
    "f_iters": "Theta(log N)",
    "f_iters_semi": "States Theta(log N) but does not explain the doubling of k.",
    "f_iters_correct": "Justifies Theta(log N) by explaining that k starts at 1 and is doubled each iteration until it exceeds N.",
    "f_per_correct": "States Theta(N) per iteration, justified by g(a) being a full linear scan of a; the doubling and += are Theta(1).",
    "f_total_expr": "Theta(log N) x Theta(N) = Theta(N log N)",
    "g_loop": "the for loop over a",
    "g_iters": "Theta(N)",
    "g_iters_semi": "States Theta(N) but explanation is incomplete.",
    "g_iters_correct": "Justifies Theta(N) because i runs from 0 to N-1, scanning the whole array.",
    "g_per_ops": GP_LIN_ARR,
    "g_total_expr": "Theta(N) x Theta(1) = Theta(N)",
    "overall_g_expr": "Theta(1) + Theta(N) + Theta(1) = Theta(N)",
    "overall_f_expr": "Theta(1) + Theta(N log N) + Theta(1) = Theta(N log N)",
}))

specs.append((21, "Linked List with Full-List Helper", "periter", {
    "tf": "Theta(N^2)", "tg": "Theta(N)",
    "struct_correct": "Clear separation of f and g and identification of the call to g() inside f's list-traversal loop; line numbers referenced consistently.",
    "f_loop": "the while loop that traverses the list",
    "f_iters": "Theta(N)",
    "f_iters_semi": "States Theta(N) but does not say p advances by one node per iteration.",
    "f_iters_correct": "Justifies Theta(N) because p starts at h and advances by p.next each iteration until it becomes null after visiting N nodes.",
    "f_per_correct": "States Theta(N) per iteration, justified by g() scanning the whole list from the head every time.",
    "f_total_expr": "Theta(N) x Theta(N) = Theta(N^2)",
    "g_loop": "the while loop that traverses the list",
    "g_iters": "Theta(N)",
    "g_iters_semi": "States Theta(N) but explanation is incomplete.",
    "g_iters_correct": "Justifies Theta(N) because q starts at h and advances by q.next until null, visiting all N nodes.",
    "g_per_ops": "one field access, one += assignment, one pointer advance, one null comparison",
    "g_total_expr": "Theta(N) x Theta(1) = Theta(N)",
    "overall_g_expr": "Theta(1) + Theta(N) + Theta(1) = Theta(N)",
    "overall_f_expr": "Theta(1) + Theta(N^2) + Theta(1) = Theta(N^2)",
}))

# ---------- Part-C (11-point) tasks ----------
specs.append((6, "Linear Scan with Halving Helper", "partc", {
    "tf": "Theta(N)", "tg": "Theta(log N)",
    "struct_correct": "Clear separation of f and g; the single loop and the separate call to g identified; line numbers referenced consistently.",
    "f_iters_name": "Loop iterations", "iters_of": "iterations of the single for loop over a",
    "f_loop_total": "Theta(N)", "f_iters": "Theta(N)",
    "f_iters_semi": "States Theta(N) but with weak or incomplete justification.",
    "f_iters_correct": "Justifies Theta(N) because i increments from 0 to N-1.",
    "f_per_ops": "one array read and one += assignment",
    "f_total_expr": "Theta(N) x Theta(1) = Theta(N)",
    "g_loop": "the halving while loop", "g_iters": "Theta(log N)",
    "g_iters_semi": "States Theta(log N) but does not explain the halving (k = k / 2 each iteration).",
    "g_iters_correct": "Justifies Theta(log N) by explaining that k starts at N and is divided by 2 each iteration until it reaches 0.",
    "g_per_ops": GP_HALVE,
    "g_total_expr": "Theta(log N) x Theta(1) = Theta(log N)",
    "overall_g_expr": "Theta(1) + Theta(log N) + Theta(1) = Theta(log N)",
    "overall_f_expr": "Theta(1) + Theta(N) (loop) + Theta(log N) (Part C) = Theta(N)",
    "notes": ["The cost of the call to g (Theta(log N)) is a lower-order term absorbed by f's loop (Theta(N))."],
}))

specs.append((7, "Triple Nested Loop with Linear Helper", "partc", {
    "tf": "Theta(N^3)", "tg": "Theta(N)",
    "struct_correct": "Clear separation of f and g; the triple nested loop and the separate call to g identified; line numbers referenced consistently.",
    "f_iters_name": "Nested loop iterations", "iters_of": "combined iterations of the triple nested loops",
    "f_loop_total": "Theta(N^3)", "f_iters": "Theta(N^3)",
    "f_iters_semi": "States Theta(N^3) but with weak or incomplete justification.",
    "f_iters_correct": "Justifies Theta(N^3) because the three loops are independent and each runs N times, giving N x N x N.",
    "f_per_ops": "three array reads, two additions, one += assignment",
    "f_total_expr": "Theta(N^3) x Theta(1) = Theta(N^3)",
    "g_loop": "the for loop over a", "g_iters": "Theta(N)",
    "g_iters_semi": "States Theta(N) but explanation is unclear.",
    "g_iters_correct": "Justifies Theta(N) because i runs from 0 to N-1.",
    "g_per_ops": GP_LIN_ARR,
    "g_total_expr": "Theta(N) x Theta(1) = Theta(N)",
    "overall_g_expr": "Theta(1) + Theta(N) + Theta(1) = Theta(N)",
    "overall_f_expr": "Theta(1) + Theta(N^3) (loop) + Theta(N) (Part C) = Theta(N^3)",
    "notes": [NESTED_NOTE, "The Theta(N) cost of g is absorbed by the Theta(N^3) nested loop."],
}))

specs.append((10, "Two Sequential Linear Passes", "partc", {
    "tf": "Theta(N)", "tg": "Theta(N)",
    "struct_correct": "Clear separation of f and g; the single loop and the separate call to g identified; line numbers referenced consistently.",
    "f_iters_name": "Loop iterations", "iters_of": "iterations of the single for loop over a",
    "f_loop_total": "Theta(N)", "f_iters": "Theta(N)",
    "f_iters_semi": "States Theta(N) but with weak or incomplete justification.",
    "f_iters_correct": "Justifies Theta(N) because i increments from 0 to N-1.",
    "f_per_ops": "one array read, one multiplication, one += assignment",
    "f_total_expr": "Theta(N) x Theta(1) = Theta(N)",
    "g_loop": "the for loop over a", "g_iters": "Theta(N)",
    "g_iters_semi": "States Theta(N) but explanation is unclear.",
    "g_iters_correct": "Justifies Theta(N) because i runs from 0 to N-1.",
    "g_per_ops": GP_LIN_ARR,
    "g_total_expr": "Theta(N) x Theta(1) = Theta(N)",
    "overall_g_expr": "Theta(1) + Theta(N) + Theta(1) = Theta(N)",
    "overall_f_expr": "Theta(1) + Theta(N) (loop) + Theta(N) (Part C) = Theta(N)",
    "notes": ["f's loop and the call to g are sequential, so their costs ADD (Theta(N) + Theta(N) = Theta(N)); they are not multiplied."],
}))

specs.append((12, "Doubling Window Sum", "partc", {
    "tf": "Theta(N)", "tg": "Theta(N)",
    "struct_correct": "Clear separation of f and g; the doubling-window nested loop and the separate call to g identified; line numbers referenced consistently.",
    "f_iters_name": "Nested loop iterations", "iters_of": "combined iterations of the doubling-window nested loops",
    "f_loop_total": "Theta(N)", "f_iters": "Theta(N)",
    "f_iters_wrong": "Iteration count missing, or claims Theta(N log N) by multiplying the log N outer count by an N inner count.",
    "f_iters_semi": "States Theta(N) but does not clearly justify the geometric sum.",
    "f_iters_correct": "Justifies Theta(N) by summing the geometric series 1 + 2 + 4 + ... + N < 2N, dominated by its largest term.",
    "f_per_ops": "one array read and one += assignment",
    "f_total_expr": "Theta(N) x Theta(1) = Theta(N)",
    "g_loop": "the for loop over a", "g_iters": "Theta(N)",
    "g_iters_semi": "States Theta(N) but explanation is unclear.",
    "g_iters_correct": "Justifies Theta(N) because i runs from 0 to N-1.",
    "g_per_ops": GP_LIN_ARR,
    "g_total_expr": "Theta(N) x Theta(1) = Theta(N)",
    "overall_g_expr": "Theta(1) + Theta(N) + Theta(1) = Theta(N)",
    "overall_f_expr": "Theta(1) + Theta(N) (loop) + Theta(N) (Part C) = Theta(N)",
    "notes": ["TRAP: the nested loop in f is a geometric series 1 + 2 + ... + N = Theta(N), NOT Theta(N log N). Do not award the iteration mark for an answer that claims Theta(N log N)."],
}))

specs.append((15, "Two Sequential Halving Loops", "partc", {
    "tf": "Theta(log N)", "tg": "Theta(log N)",
    "struct_correct": "Clear separation of f and g; the halving loop and the separate call to g identified; line numbers referenced consistently.",
    "f_iters_name": "Loop iterations", "iters_of": "iterations of the halving while loop",
    "f_loop_total": "Theta(log N)", "f_iters": "Theta(log N)",
    "f_iters_semi": "States Theta(log N) but does not explain the halving of k.",
    "f_iters_correct": "Justifies Theta(log N) because k starts at N and is divided by 2 each iteration until it reaches 0.",
    "f_per_ops": "one array read, one += assignment, one division, one comparison",
    "f_total_expr": "Theta(log N) x Theta(1) = Theta(log N)",
    "g_loop": "the halving while loop", "g_iters": "Theta(log N)",
    "g_iters_semi": "States Theta(log N) but does not explain the halving of j.",
    "g_iters_correct": "Justifies Theta(log N) because j starts at N and is divided by 2 each iteration until it reaches 0.",
    "g_per_ops": GP_HALVE,
    "g_total_expr": "Theta(log N) x Theta(1) = Theta(log N)",
    "overall_g_expr": "Theta(1) + Theta(log N) + Theta(1) = Theta(log N)",
    "overall_f_expr": "Theta(1) + Theta(log N) (loop) + Theta(log N) (Part C) = Theta(log N)",
    "notes": ["The two halving loops are sequential, so their costs ADD (Theta(log N) + Theta(log N) = Theta(log N))."],
}))

specs.append((16, "Doubling Outer with Full Inner Pass", "partc", {
    "tf": "Theta(N log N)", "tg": "Theta(N)",
    "struct_correct": "Clear separation of f and g; the doubling-outer / full-inner nested loop and the separate call to g identified; line numbers referenced consistently.",
    "f_iters_name": "Nested loop iterations", "iters_of": "combined iterations of the nested loops",
    "f_loop_total": "Theta(N log N)", "f_iters": "Theta(N log N)",
    "f_iters_semi": "States Theta(N log N) but does not clearly justify both the doubling outer (log N) and the full inner (N).",
    "f_iters_correct": "Justifies Theta(N log N) because the outer loop doubles k and runs Theta(log N) times while the inner loop runs the full N each time, independent of k.",
    "f_per_ops": "one array read and one += assignment",
    "f_total_expr": "Theta(N log N) x Theta(1) = Theta(N log N)",
    "g_loop": "the for loop over a", "g_iters": "Theta(N)",
    "g_iters_semi": "States Theta(N) but explanation is unclear.",
    "g_iters_correct": "Justifies Theta(N) because i runs from 0 to N-1.",
    "g_per_ops": GP_LIN_ARR,
    "g_total_expr": "Theta(N) x Theta(1) = Theta(N)",
    "overall_g_expr": "Theta(1) + Theta(N) + Theta(1) = Theta(N)",
    "overall_f_expr": "Theta(1) + Theta(N log N) (loop) + Theta(N) (Part C) = Theta(N log N)",
    "notes": [NESTED_NOTE, "Unlike the geometric case, the inner loop here runs the full N on every outer pass, so the nested loop is genuinely Theta(N log N)."],
}))

specs.append((17, "Linear Caller with Quadratic Helper", "partc", {
    "tf": "Theta(N^2)", "tg": "Theta(N^2)",
    "struct_correct": "Clear separation of f and g; f's single loop and the separate call to g identified; line numbers referenced consistently.",
    "f_iters_name": "Loop iterations", "iters_of": "iterations of the single for loop reading the first column",
    "f_loop_total": "Theta(N)", "f_iters": "Theta(N)",
    "f_iters_semi": "States Theta(N) but with weak or incomplete justification.",
    "f_iters_correct": "Justifies Theta(N) because i runs from 0 to N-1.",
    "f_per_ops": "one matrix access and one += assignment",
    "f_total_expr": "Theta(N) x Theta(1) = Theta(N)",
    "g_loop": "the nested loops over the matrix", "g_iters": "Theta(N^2)",
    "g_iters_semi": "States Theta(N^2) but with weak justification.",
    "g_iters_correct": "Justifies Theta(N^2) because the outer and inner loops each run N times, so the body runs N x N times.",
    "g_per_ops": "one matrix access and one += assignment",
    "g_total_expr": "Theta(N^2) x Theta(1) = Theta(N^2)",
    "overall_g_expr": "Theta(1) + Theta(N^2) + Theta(1) = Theta(N^2)",
    "overall_f_expr": "Theta(1) + Theta(N) (loop) + Theta(N^2) (Part C) = Theta(N^2)",
    "notes": [NESTED_NOTE, "Here the helper g (Theta(N^2)) DOMINATES f's own loop (Theta(N)); the loop term is absorbed."],
}))

specs.append((18, "Constant-Bounded Inner Loop", "partc", {
    "tf": "Theta(N)", "tg": "Theta(N)",
    "struct_correct": "Clear separation of f and g; the nested loop (with a constant-bounded inner loop) and the separate call to g identified; line numbers referenced consistently.",
    "f_iters_name": "Nested loop iterations", "iters_of": "combined iterations of the nested loops",
    "f_loop_total": "Theta(N)", "f_iters": "Theta(N)",
    "f_iters_wrong": "Iteration count missing, or claims Theta(N^2) by treating the constant inner loop as if it depended on N.",
    "f_iters_semi": "States Theta(N) but does not clearly note that the inner loop is constant-bounded.",
    "f_iters_correct": "Justifies Theta(N) because the outer loop runs N times and the inner loop runs a constant 5 times, giving 5N.",
    "f_per_ops": "one array read and one += assignment",
    "f_total_expr": "Theta(N) x Theta(1) = Theta(N)",
    "g_loop": "the for loop over a", "g_iters": "Theta(N)",
    "g_iters_semi": "States Theta(N) but explanation is unclear.",
    "g_iters_correct": "Justifies Theta(N) because i runs from 0 to N-1.",
    "g_per_ops": GP_LIN_ARR,
    "g_total_expr": "Theta(N) x Theta(1) = Theta(N)",
    "overall_g_expr": "Theta(1) + Theta(N) + Theta(1) = Theta(N)",
    "overall_f_expr": "Theta(1) + Theta(N) (loop) + Theta(N) (Part C) = Theta(N)",
    "notes": ["TRAP: the inner loop in f runs a constant number of times (5), so it does not add a factor of N; f's loop is Theta(N). Do not award the iteration mark for an answer that claims Theta(N^2)."],
}))

specs.append((19, "Triangular Sum with Binary-Search Helper", "partc", {
    "tf": "Theta(N^2)", "tg": "Theta(log N)",
    "struct_correct": "Clear separation of f and g; the triangular nested loop and the separate call to g identified; line numbers referenced consistently.",
    "f_iters_name": "Nested loop iterations", "iters_of": "combined iterations of the triangular nested loops",
    "f_loop_total": "Theta(N^2)", "f_iters": "Theta(N^2)",
    "f_iters_semi": "States Theta(N^2) but with weak or incomplete justification (does not reference the j = i lower bound).",
    "f_iters_correct": "Justifies Theta(N^2) by summing N + (N-1) + ... + 1 = N(N+1)/2, or by stating outer Theta(N) x average inner Theta(N).",
    "f_per_ops": "one array access and one += assignment",
    "f_total_expr": "Theta(N^2) x Theta(1) = Theta(N^2)",
    "g_loop": "the binary-search while loop", "g_iters": "Theta(log N)",
    "g_iters_semi": G_BINSEARCH_SEMI, "g_iters_correct": G_BINSEARCH_CORR,
    "g_per_ops": GP_BINSEARCH,
    "g_total_expr": "Theta(log N) x Theta(1) = Theta(log N)",
    "overall_g_expr": "Theta(1) + Theta(log N) + Theta(1) = Theta(log N)",
    "overall_f_expr": "Theta(1) + Theta(N^2) (loop) + Theta(log N) (Part C) = Theta(N^2)",
    "notes": [NESTED_NOTE, "The Theta(log N) cost of g is absorbed by the Theta(N^2) nested loop."],
}))

specs.append((20, "Full Matrix Scan with Row Helper", "partc", {
    "tf": "Theta(N^2)", "tg": "Theta(N)",
    "struct_correct": "Clear separation of f and g; the full nested matrix loop and the separate call to g identified; line numbers referenced consistently.",
    "f_iters_name": "Nested loop iterations", "iters_of": "combined iterations of the nested loops over the matrix",
    "f_loop_total": "Theta(N^2)", "f_iters": "Theta(N^2)",
    "f_iters_semi": "States Theta(N^2) but with weak justification.",
    "f_iters_correct": "Justifies Theta(N^2) because the outer and inner loops each run N times, so the body runs N x N times.",
    "f_per_ops": "one matrix access and one += assignment",
    "f_total_expr": "Theta(N^2) x Theta(1) = Theta(N^2)",
    "g_loop": "the for loop scanning the first row", "g_iters": "Theta(N)",
    "g_iters_semi": "States Theta(N) but explanation is unclear.",
    "g_iters_correct": "Justifies Theta(N) because i runs from 0 to N-1 across one row.",
    "g_per_ops": "one matrix access and one += assignment",
    "g_total_expr": "Theta(N) x Theta(1) = Theta(N)",
    "overall_g_expr": "Theta(1) + Theta(N) + Theta(1) = Theta(N)",
    "overall_f_expr": "Theta(1) + Theta(N^2) (loop) + Theta(N) (Part C) = Theta(N^2)",
    "notes": [NESTED_NOTE, "The Theta(N) cost of g is absorbed by the Theta(N^2) nested loop."],
}))

# write all
for num, title_base, shape, params in specs:
    total, npts = write_rubric(num, title_base, shape, params)
    status = "OK" if total == 100 else "BAD"
    print(f"asym-{num:<2} {shape:8} points={npts:2} total={total} [{status}]  {title_base}")
