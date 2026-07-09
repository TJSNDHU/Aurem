import ast
import operator as _op


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
        expression += ' ' + op + ' ' + str(operand[i + 1])
    return _safe_eval(expression)


_ALLOWED_OPS = {
    ast.Add: _op.add,
    ast.Sub: _op.sub,
    ast.Mult: _op.mul,
    ast.FloorDiv: _op.floordiv,
    ast.Pow: _op.pow,
}


def _safe_eval(expr):
    node = ast.parse(expr, mode='eval').body

    def _eval(n):
        if isinstance(n, ast.Constant):
            return n.value
        if isinstance(n, ast.BinOp):
            return _ALLOWED_OPS[type(n.op)](_eval(n.left), _eval(n.right))
        raise ValueError("Unsupported expression")

    return _eval(node)