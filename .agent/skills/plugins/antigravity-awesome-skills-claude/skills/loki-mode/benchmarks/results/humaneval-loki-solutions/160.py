# HumanEval/160
# Loki Mode Multi-Agent Solution
# Attempts: 1
# Passed: True

import ast
import operator as op_module

_BIN_OPS = {
    ast.Add: op_module.add,
    ast.Sub: op_module.sub,
    ast.Mult: op_module.mul,
    ast.FloorDiv: op_module.floordiv,
    ast.Pow: op_module.pow,
}

_UNARY_OPS = {
    ast.UAdd: lambda x: x,
    ast.USub: op_module.neg,
}

def _safe_eval(node):
    """Safely evaluate an AST node containing only arithmetic operations."""
    if isinstance(node, ast.Constant):
        return node.value
    elif isinstance(node, ast.Num):  # Python 3.7 compatibility
        return node.n
    elif isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _BIN_OPS:
            raise TypeError(f"Unsupported binary operation: {op_type.__name__}")
        left = _safe_eval(node.left)
        right = _safe_eval(node.right)
        return _BIN_OPS[op_type](left, right)
    elif isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _UNARY_OPS:
            raise TypeError(f"Unsupported unary operation: {op_type.__name__}")
        operand = _safe_eval(node.operand)
        return _UNARY_OPS[op_type](operand)
    else:
        raise TypeError(f"Unsupported node type: {type(node).__name__}")

def do_algebra(operator, operand):
    """
    Given two lists operator, and operand. The first list has basic algebra operations, and 
    the second list is a list of integers. Use the two given lists to build the algebric 
    expression and return the evaluation of this expression.

    The basic algebra operations:
    Addition ( + ) 
    Subtraction ( - ) 
    Multiplication ( * ) 
    Floor division ( // ) 
    Exponentiation ( ** ) 

    Example:
    operator['+', '*', '-']
    array = [2, 3, 4, 5]
    result = 2 + 3 * 4 - 5
    => result = 9

    Note:
        The length of operator list is equal to the length of operand list minus one.
        Operand is a list of of non-negative integers.
        Operator list has at least one operator, and operand list has at least two operands.

    """
    expression = str(operand[0])
    for i, op in enumerate(operator):
        expression += op + str(operand[i + 1])
    return _safe_eval(ast.parse(expression, mode="eval").body)