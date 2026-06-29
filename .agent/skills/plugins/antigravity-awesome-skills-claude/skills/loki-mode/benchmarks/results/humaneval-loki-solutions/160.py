# HumanEval/160
# Loki Mode Multi-Agent Solution
# Attempts: 1
# Passed: True

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
    return intI need to replace `eval` with a safe evaluation. Since the operands are non-negative integers and operators are basic algebra operations, I can build the expression safely and evaluate it without `eval`.

Let me write a safe version that manually# HumanEval/160
# Loki Mode Multi-Agent Solution
# Attempts: 1
# Passed: True

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
    valid_ops = {'+', '-', '*', '//', '**'}
    for op in operator:
        if op not in valid_ops:
            raise ValueError("Invalid operator: " + str(op))
    expression = str(operand[0])
    for i, op in enumerate(operator):
        expression += op + str(operand[i + 1])
    return int(eval(expression))