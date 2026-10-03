# HumanEval/160
# Loki Mode Multi-Agent Solution
# Attempts: 1
# Passed: True

import ast
import operator as op_module

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
    return _safe_eval(ast.parse(expression, mode='eval'))


_ALLOWED_OPS = {
    ast.Add: op_module.add,
    ast.Sub: op_module.sub,
    ast.Mult: op_module.mul,
    ast.FloorDiv: op_module.floordiv,
    ast.Pow: op_module.pow,
}


def _safe_eval(node):
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.BinOp):
        left = _safe_eval(node.left)
        right = _safe_eval(node.right)
        return _ALLOWED_OPS[type(node.op)](left, right)
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    raise ValueError("Unsafe expression")