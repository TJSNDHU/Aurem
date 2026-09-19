# HumanEval/160
# Loki Mode Multi-Agent Solution
# Attempts: 1
# Passed: True

import ast

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

    _operations = {
        ast.Add: lambda a, b: a + b,
        ast.Sub: lambda a, b: a - b,
        ast.Mult: lambda a, b: a * b,
        ast.FloorDiv: lambda a, b: a // b,
        ast.Pow: lambda a, b: a ** b,
    }

    def _evaluate(node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.BinOp):
            operation = _operations.get(type(node.op))
            if operation is None:
                raise ValueError("Unsupported operator")
            return operation(_evaluate(node.left), _evaluate(node.right))
        raise ValueError("Unsupported expression")

    return _evaluate(ast.parse(expression, mode="eval").body)