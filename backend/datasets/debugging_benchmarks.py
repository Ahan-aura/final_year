"""
Code Debugging Benchmark Suites and Held-Out Validation Cases.
Defines ground-truth buggy programs, failing test suites, and
held-out verification cases for Domain 2.
"""

from typing import Dict, Any, List

DEBUGGING_BENCHMARKS = {
    "off_by_one": {
        "title": "Binary Search Array Boundary Bug",
        "subtask": "off_by_one_fix",
        "description": "Binary search algorithm fails on edge boundaries due to improper high pointer initialization and loop condition.",
        "buggy_code": '''def binary_search(arr, target):
    # BUG: high initialized to len(arr) instead of len(arr) - 1, and loop uses strictly <
    low = 0
    high = len(arr)
    while low < high:
        mid = (low + high) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            low = mid + 1
        else:
            high = mid
    return -1
''',
        "entrypoint": "binary_search",
        "failing_tests": [
            {"inputs": [[1, 3, 5, 7, 9], 9], "expected": 4, "desc": "Find last element in odd array"},
            {"inputs": [[2, 4, 6, 8], 8], "expected": 3, "desc": "Find last element in even array"}
        ]
    },

    "null_none": {
        "title": "Nested User Profile Safe Email Lookup",
        "subtask": "null_none_handling",
        "description": "Crashes with TypeError: 'NoneType' object is not subscriptable when payload has missing or None user object.",
        "buggy_code": '''def safe_get_user_email(payload):
    # BUG: Crashes when payload is None or payload["user"] is None
    return payload["user"]["email"].strip()
''',
        "entrypoint": "safe_get_user_email",
        "failing_tests": [
            {"inputs": [None], "expected": None, "desc": "Handle completely None payload"},
            {"inputs": [{"user": None}], "expected": None, "desc": "Handle user object being None"},
            {"inputs": [{}], "expected": None, "desc": "Handle empty dictionary without user key"}
        ]
    },

    "type_mismatch": {
        "title": "User Summary String Formatter",
        "subtask": "type_mismatch_fix",
        "description": "Crashes with TypeError: can only concatenate str (not 'int') to str when formatting user identifier and score.",
        "buggy_code": '''def format_user_summary(user_id, name, score):
    # BUG: Direct string concatenation throws TypeError when user_id is int or score is float
    return "User #" + user_id + ": " + name + " (Score: " + score + ")"
''',
        "entrypoint": "format_user_summary",
        "failing_tests": [
            {"inputs": [101, "Alice", 95.5], "expected": "User #101: Alice (Score: 95.5)", "desc": "Numeric ID and Float score"}
        ]
    },

    "loop_bound": {
        "title": "Infinite Loop in Countdown Sequencer",
        "subtask": "loop_bound_correction",
        "description": "Function hangs indefinitely because loop counter 'current' is never decremented.",
        "buggy_code": '''def countdown_items(n):
    # BUG: current is never decremented, causing infinite loop timeout
    result = []
    current = int(n)
    while current > 0:
        result.append(current)
        # missing: current -= 1
    return result
''',
        "entrypoint": "countdown_items",
        "failing_tests": [
            {"inputs": [3], "expected": [3, 2, 1], "desc": "Countdown from 3"}
        ]
    },

    "operator_logic": {
        "title": "Loan Eligibility Logical Inversion",
        "subtask": "operator_logic_fix",
        "description": "Grants loan approval when applicant fails income or credit requirements due to erroneous OR operator.",
        "buggy_code": '''def is_eligible_for_loan(age, income, credit_score):
    # BUG: Uses OR instead of AND, allowing ineligible applicants through
    if age is None or income is None or credit_score is None:
        return False
    return (age >= 21) or (income >= 25000) or (credit_score >= 650)
''',
        "entrypoint": "is_eligible_for_loan",
        "failing_tests": [
            {"inputs": [18, 10000, 700], "expected": False, "desc": "Underage applicant should be rejected even with good credit"},
            {"inputs": [30, 15000, 600], "expected": False, "desc": "Low income and credit should be rejected"}
        ]
    },

    "missing_return": {
        "title": "Discount Calculator Edge Case & Zero Division",
        "subtask": "missing_return_edge_case",
        "description": "Omits return statement on zero discount and fails on invalid negative bounds.",
        "buggy_code": '''def calculate_safe_discount(price, discount_percent):
    # BUG: Missing return for discount_percent <= 0, and unhandled 100% discount
    if price is None or price <= 0:
        return 0.0
    if discount_percent > 0:
        discount_amount = price * (discount_percent / 100.0)
        return round(float(price - discount_amount), 2)
    # BUG: Reaches end of function without return (returns None)
''',
        "entrypoint": "calculate_safe_discount",
        "failing_tests": [
            {"inputs": [100.0, 0.0], "expected": 100.0, "desc": "Zero discount should return full price"},
            {"inputs": [200.0, 100.0], "expected": 0.0, "desc": "100% discount should return 0.0"}
        ]
    },

    "recursion_depth": {
        "title": "Recursive Factorial Missing Base Case",
        "subtask": "recursion_base_case",
        "description": "Infinite recursion crashes with RecursionError because base case for n <= 1 is missing.",
        "buggy_code": '''def factorial(n):
    # BUG: Missing base case if n <= 1, causes maximum recursion depth exceeded
    return n * factorial(n - 1)
''',
        "entrypoint": "factorial",
        "failing_tests": [
            {"inputs": [5], "expected": 120, "desc": "Factorial of 5"},
            {"inputs": [1], "expected": 1, "desc": "Factorial of 1"},
            {"inputs": [0], "expected": 1, "desc": "Factorial of 0"}
        ]
    },

    "palindrome_check": {
        "title": "Palindrome Verifier Out-of-Bounds & Case Bug",
        "subtask": "palindrome_bounds_fix",
        "description": "Index out of bounds on right pointer len(s) causes IndexError in palindrome verification.",
        "buggy_code": '''def is_palindrome(s):
    # BUG: Off-by-one in right pointer index: len(s) instead of len(s) - 1
    if s is None:
        return True
    left = 0
    right = len(s)
    while left < right:
        if s[left] != s[right]:
            return False
        left += 1
        right -= 1
    return True
''',
        "entrypoint": "is_palindrome",
        "failing_tests": [
            {"inputs": ["racecar"], "expected": True, "desc": "racecar is palindrome"},
            {"inputs": ["hello"], "expected": False, "desc": "hello is not palindrome"}
        ]
    },

    "matrix_transpose": {
        "title": "2D Matrix Transpose Inverted Row/Col Index",
        "subtask": "matrix_index_inversion",
        "description": "Inverted row/col indices cause IndexError on non-square rectangular matrices.",
        "buggy_code": '''def transpose_matrix(matrix):
    # BUG: Assumes square matrix, indexing matrix[c][r] instead of matrix[r][c]
    if not matrix or not matrix[0]:
        return []
    rows = len(matrix)
    cols = len(matrix[0])
    transposed = []
    for c in range(cols):
        new_row = []
        for r in range(rows):
            new_row.append(matrix[c][r])
        transposed.append(new_row)
    return transposed
''',
        "entrypoint": "transpose_matrix",
        "failing_tests": [
            {"inputs": [[[1, 2, 3], [4, 5, 6]]], "expected": [[1, 4], [2, 5], [3, 6]], "desc": "Transpose 2x3 rectangular matrix"},
            {"inputs": [[[1, 2], [3, 4]]], "expected": [[1, 3], [2, 4]], "desc": "Transpose 2x2 square matrix"}
        ]
    },

    "average_accumulator": {
        "title": "List Average Division by Zero & None Handling",
        "subtask": "zero_division_guard",
        "description": "Crashes with ZeroDivisionError when given empty list, and unhandled None input.",
        "buggy_code": '''def calculate_average(numbers):
    # BUG: Crashes when numbers is empty (ZeroDivisionError) or None (TypeError)
    total = sum(numbers)
    return total / len(numbers)
''',
        "entrypoint": "calculate_average",
        "failing_tests": [
            {"inputs": [[]], "expected": 0.0, "desc": "Empty list should safely return 0.0"},
            {"inputs": [None], "expected": 0.0, "desc": "None input should safely return 0.0"},
            {"inputs": [[10, 20, 30]], "expected": 20.0, "desc": "Average of [10, 20, 30] is 20.0"}
        ]
    }
}


def get_held_out_debugging_test_cases(subtask: str) -> List[Dict[str, Any]]:
    """Returns held-out test cases used exclusively by the sandbox validation gate."""
    if subtask == "off_by_one_fix":
        return [
            {"description": "Search first element", "inputs": [[10, 20, 30, 40], 10], "expected": 0},
            {"description": "Search last element", "inputs": [[10, 20, 30, 40], 40], "expected": 3},
            {"description": "Search mid element", "inputs": [[10, 20, 30, 40], 30], "expected": 2},
            {"description": "Search absent element", "inputs": [[10, 20, 30, 40], 25], "expected": -1},
            {"description": "Search single element match", "inputs": [[5], 5], "expected": 0},
            {"description": "Search single element absent", "inputs": [[5], 9], "expected": -1}
        ]

    elif subtask == "null_none_handling":
        return [
            {"description": "Valid complete nested payload", "inputs": [{"user": {"email": "test@mbu.asia"}}], "expected": "test@mbu.asia"},
            {"description": "Null user object", "inputs": [{"user": None}], "expected": None},
            {"description": "Completely empty payload", "inputs": [{}], "expected": None},
            {"description": "None root payload", "inputs": [None], "expected": None},
            {"description": "User without email key", "inputs": [{"user": {"name": "Alex"}}], "expected": None}
        ]

    elif subtask == "type_mismatch_fix":
        return [
            {"description": "Integer ID, string name, float score", "inputs": [42, "Bob", 88.0], "expected": "User #42: Bob (Score: 88.0)"},
            {"description": "String ID, string name, integer score", "inputs": ["A-9", "Carol", 92], "expected": "User #A-9: Carol (Score: 92.0)"},
            {"description": "None ID fallback", "inputs": [None, "Dave", 70.5], "expected": "User #0: Dave (Score: 70.5)"}
        ]

    elif subtask == "loop_bound_correction":
        return [
            {"description": "Countdown 5", "inputs": [5], "expected": [5, 4, 3, 2, 1]},
            {"description": "Countdown 1", "inputs": [1], "expected": [1]},
            {"description": "Countdown 0 (empty)", "inputs": [0], "expected": []},
            {"description": "Negative input (empty)", "inputs": [-4], "expected": []}
        ]

    elif subtask == "operator_logic_fix":
        return [
            {"description": "All requirements met -> True", "inputs": [25, 40000, 720], "expected": True},
            {"description": "Underage -> False", "inputs": [19, 50000, 750], "expected": False},
            {"description": "Low income -> False", "inputs": [35, 12000, 780], "expected": False},
            {"description": "Low credit -> False", "inputs": [40, 60000, 580], "expected": False},
            {"description": "None values -> False", "inputs": [None, 30000, 700], "expected": False}
        ]

    elif subtask == "missing_return_edge_case":
        return [
            {"description": "Normal discount 20%", "inputs": [100.0, 20.0], "expected": 80.0},
            {"description": "Zero discount", "inputs": [150.0, 0.0], "expected": 150.0},
            {"description": "Full 100% discount", "inputs": [90.0, 100.0], "expected": 0.0},
            {"description": "None price handling", "inputs": [None, 15.0], "expected": 0.0},
            {"description": "Negative price handling", "inputs": [-50.0, 10.0], "expected": 0.0}
        ]

    elif subtask == "recursion_base_case":
        return [
            {"description": "Factorial 3", "inputs": [3], "expected": 6},
            {"description": "Factorial 4", "inputs": [4], "expected": 24},
            {"description": "Factorial 0", "inputs": [0], "expected": 1},
            {"description": "Factorial 1", "inputs": [1], "expected": 1}
        ]

    elif subtask == "palindrome_bounds_fix":
        return [
            {"description": "Level is palindrome", "inputs": ["level"], "expected": True},
            {"description": "Noon is palindrome", "inputs": ["noon"], "expected": True},
            {"description": "World is not palindrome", "inputs": ["world"], "expected": False},
            {"description": "Empty string is palindrome", "inputs": [""], "expected": True}
        ]

    elif subtask == "matrix_index_inversion":
        return [
            {"description": "Transpose 1x2 matrix", "inputs": [[[7, 8]]], "expected": [[7], [8]]},
            {"description": "Transpose 2x1 matrix", "inputs": [[[7], [8]]], "expected": [[7, 8]]},
            {"description": "Transpose 3x3 identity", "inputs": [[[1, 0, 0], [0, 1, 0], [0, 0, 1]]], "expected": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]}
        ]

    elif subtask == "zero_division_guard":
        return [
            {"description": "Normal average", "inputs": [[5, 15]], "expected": 10.0},
            {"description": "Single element", "inputs": [[42]], "expected": 42.0},
            {"description": "Empty list zero division", "inputs": [[]], "expected": 0.0},
            {"description": "None list guard", "inputs": [None], "expected": 0.0}
        ]

    return []