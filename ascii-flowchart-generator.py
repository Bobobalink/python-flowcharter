import ast
import astpp
import numpy as np


class FlowchartNode:
    def __init__(self, parent):
        self.parent = parent
        self.child = None
        self.row = None
        self.col = None  # for display logic

    def __str__(self):
        return "base flowchart node?"


class StartNode(FlowchartNode):
    def __init__(self, text):
        self.name = text
        super().__init__(None)
        self.inputs = []
        self.outputs = []

    def __str__(self):
        return "( start )"


class InputNode(FlowchartNode):
    def __init__(self, parent, varName):
        self.name = varName
        super().__init__(parent)

    def __str__(self):
        return "/ input {} /".format(self.name)


class OutputNode(FlowchartNode):
    def __init__(self, parent, varName):
        self.name = varName
        super().__init__(parent)

    def __str__(self):
        return "/ output {} /".format(self.name)


class ProcessNode(FlowchartNode):
    def __init__(self, parent, text):
        self.text = text
        super().__init__(parent)

    def __str__(self):
        return "[ {} ]".format(self.text)


class VariableAssignmentNode(ProcessNode):
    def __init__(self, parent, varName, expression):
        text = "{} = {}".format(varName, expression)
        super().__init__(parent, text)


class ConditionalNode(FlowchartNode):
    def __init__(self, parent, condition):
        self.condition = condition
        super().__init__(parent)
        self.child = {"No": None, "Yes": None}

    def __str__(self):
        return "< {} >".format(self.condition)


class SubProcessNode(FlowchartNode):
    def __init__(self, parent, subprocessName):
        self.name = subprocessName
        super().__init__(parent)

    def __str__(self):
        return "[ | {} | ]".format(self.name)


class DummyConjunctionNode(FlowchartNode):  # node to allow two nodes to return to the same place
    def __init__(self, parent1, parent2):
        self.parent2 = parent2
        super().__init__(parent1)

    def __str__(self):
        return "     | <---"


class DummyMiddleNode(FlowchartNode):
    def __str__(self):
        return ''


class FlowchartMakingVisitor(ast.NodeVisitor):
    operators = {ast.Mult: '*', ast.Add: '+', ast.Sub: '-', ast.Div: '/', ast.Or: 'or', ast.And: 'and', ast.Gt: '>', ast.Lt: '<', ast.Eq: '=', ast.NotEq: '!='}

    def __init__(self):
        self.start = StartNode("start")
        self.currentParent = self.start

    def visit_Module(self, node: ast.Module):
        for n in node.body:
            self.visit(n)

    def visit_Assign(self, node):
        if isinstance(node.value, ast.Call):  # special case for / input / nodes
            if node.value.func.id == 'input':
                self.appendNode(InputNode(self.currentParent, node.targets[0].id))
                return
            if isinstance(node.value.args[0], ast.Call) and node.value.args[0].func.id == 'input':  # basically, assume that any single function wrapping an input() statement in an assign is just a typecast
                self.appendNode(InputNode(self.currentParent, node.targets[0].id))
                return
        rhs = self.parseChunk(node.value)
        self.appendNode(VariableAssignmentNode(self.currentParent, node.targets[0].id, rhs))

    def visit_AugAssign(self, node):
        rhs = self.parseChunk(node.value)
        self.appendNode(VariableAssignmentNode(self.currentParent, node.target.id, "{0} {1} {2}".format(node.target.id, self.operators[node.op.__class__], rhs)))

    def visit_Expr(self, node):
        if isinstance(node.value, ast.Call):
            if node.value.func.id in {'print', 'pprint'}:  # / output / special casing
                self.appendNode(OutputNode(self.currentParent, ', '.join(self.parseFunctionArgs(node.value))))
            else:
                self.appendNode(ProcessNode(self.currentParent, self.parseFunctionCall(node.value)))
        else:
            raise Exception("Unknown Node type in Expr: {0} (line {0.lineno} col {0.col_offset})".format(node.value))

    def visit_If(self, node):
        cond = self.parseChunk(node.test)

        condNode = ConditionalNode(self.currentParent, cond)
        self.appendNode(condNode)
        condNode.child['Yes'] = DummyMiddleNode(condNode)
        self.currentParent = condNode.child['Yes']
        for n in node.body:
            self.visit(n)
        endbody = self.currentParent  # so we can connect it to the endcap eventually
        condNode.child['No'] = DummyMiddleNode(condNode)
        self.currentParent = condNode.child['No']
        for n in node.orelse:
            self.visit(n)
        endcap = DummyConjunctionNode(self.currentParent, endbody)
        endbody.child = endcap
        self.currentParent.child = endcap
        self.currentParent = endcap

    def visit_ImportFrom(self, node):
        pass

    def generic_visit(self, node):
        raise Exception("Unknown Node type: {0} (line {0.lineno} col {0.col_offset})".format(node))

    def appendNode(self, node):
        self.currentParent.child = node
        self.currentParent = node

    def parseFunctionCall(self, call):
        name = call.func.id
        args = self.parseFunctionArgs(call)
        return "{0}({1})".format(name, ', '.join(map(str, args)))

    def parseFunctionArgs(self, call):
        args = []
        for arg in call.args:
            args.append(self.parseChunk(arg))
        return args

    def parseBinOp(self, op):
        left = self.parseChunk(op.left)
        right = self.parseChunk(op.right)

        return "{0} {1} {2}".format(left, self.operators[op.op.__class__], right)

    def parseBoolOp(self, op):
        things = []
        for thing in op.values:
            things.append(self.parseChunk(thing))
        return (' ' + self.operators[op.op.__class__] + ' ').join(things)

    def parseCompare(self, op):
        str = self.parseChunk(op.left)
        for i in range(len(op.ops)):
            str += ' ' + self.operators[op.ops[i].__class__] + ' ' + self.parseChunk(op.comparators[i])
        return str

    def parseChunk(self, o):  # parse pretty much anything
        if isinstance(o, ast.BinOp):
            return '(' + self.parseBinOp(o) + ')'
        elif isinstance(o, ast.Num):
            return str(o.n)
        elif isinstance(o, ast.Name):
            return o.id
        elif isinstance(o, ast.Str):
            return repr(o.s)
        elif isinstance(o, ast.Call):
            return self.parseFunctionCall(o)
        elif isinstance(o, ast.BoolOp):
            return '(' + self.parseBoolOp(o) + ')'
        elif isinstance(o, ast.Compare):
            return '(' + self.parseCompare(o) + ')'
        else:
            raise Exception("Unknown object to parse: {0} (line {0.lineno} col {0.col_offset})".format(o))


blockWidth = 60
blockHeight = 3


# This stuff is all for printing the graph to the console. It doesn't work well with conditionals, but arrow drawing gets really really complicated quickly. Use the graphviz version instead
def followNodePath(node, col=0, row=0):
    if node.col is not None:
        return
    node.col = col
    node.row = row
    if node.child:
        if isinstance(node.child, dict):
            if isinstance(node.child["No"], DummyMiddleNode):
                node.child["No"] = node.child["No"].child
            if isinstance(node.child["Yes"], DummyMiddleNode):
                node.child["Yes"] = node.child["Yes"].child
            followNodePath(node.child["No"], col, row + 1)
            followNodePath(node.child["Yes"], col + 1, row)
        else:
            followNodePath(node.child, col, row + 1)


def nodeToText(po, node):
    po[node.row * 3][node.col * blockWidth:(node.col + 1) * blockWidth] = list(map(ord, ("{0:^" + str(blockWidth) + "}").format(str(node))))
    po[node.row * 3 + 1][node.col * blockWidth:(node.col + 1) * blockWidth] = list(map(ord, ("{0:^" + str(blockWidth) + "}").format("|")))
    po[node.row * 3 + 2][node.col * blockWidth:(node.col + 1) * blockWidth] = list(map(ord, ("{0:^" + str(blockWidth) + "}").format("V")))
    if isinstance(node.child, dict):
        e1 = nodeToText(po, node.child['Yes'])
        e2 = nodeToText(po, node.child['No'])
        return max(e1, e2)
    else:
        if node.child is None:
            return (node.row + 1) * 3
        else:
            return nodeToText(po, node.child)


tree = ast.parse(open('test.py', 'r').read())
print(tree)
print(astpp.dump(tree))

visitor = FlowchartMakingVisitor()
visitor.visit(tree)
start = visitor.start

followNodePath(start)  # mark each node with it's position in the printout

# print layout
# each column: 10 chars for up arrow space, then 50 chars padded for node space
# each node: 1 line for node itself, 2 lines of arrow (TODO: maybe special case conjunction nodes?)

printout = np.zeros((1000, 1000), dtype=np.uint8)

lastLine = nodeToText(printout, start)

printout[lastLine][0:60] = list(map(ord, "{0:^60}".format('( stop )')))

for line in printout:
    l = ''.join(map(chr, np.trim_zeros(line)))
    if l:
        print(l)
