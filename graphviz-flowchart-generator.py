import ast
import astpp
import graphviz


class FlowchartNode:
    def __init__(self, parent):
        self.parent = parent
        self.child = None
        self.index = None

    def __str__(self):
        return "base flowchart node?"

    def shape(self):
        return "tripleoctagon"


class StartNode(FlowchartNode):
    def __init__(self, text):
        self.name = text
        super().__init__(None)
        self.inputs = []
        self.outputs = []

    def __str__(self):
        return "start"

    def shape(self):
        return "ellipse"


class InputNode(FlowchartNode):
    def __init__(self, parent, varName):
        self.name = varName
        super().__init__(parent)

    def __str__(self):
        return "input {}".format(self.name)

    def shape(self):
        return "parallelogram"


class OutputNode(FlowchartNode):
    def __init__(self, parent, varName):
        self.name = varName
        super().__init__(parent)

    def __str__(self):
        return "output {}".format(self.name)

    def shape(self):
        return "parallelogram"


class ProcessNode(FlowchartNode):
    def __init__(self, parent, text):
        self.text = text
        super().__init__(parent)

    def __str__(self):
        return self.text

    def shape(self):
        return "rectangle"


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
        return self.condition

    def shape(self):
        return "diamond"


class SubProcessNode(FlowchartNode):
    def __init__(self, parent, subprocessName):
        self.name = subprocessName
        super().__init__(parent)

    def __str__(self):
        return "| {} |".format(self.name)

    def shape(self):
        return "rectangle"


class DummyConjunctionNode(FlowchartNode):  # node to allow two nodes to return to the same place
    def __init__(self, parent1, parent2):
        self.parent2 = parent2
        super().__init__(parent1)

    def __str__(self):
        return "     | <---"

    def shape(self):
        return None


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


def generateGraph(graph: graphviz.Digraph, node, index=1):
    if isinstance(node, DummyConjunctionNode) or isinstance(node, DummyMiddleNode):
        return generateGraph(graph, node.child, index)
    if isinstance(node.child, dict):
        graph.node("node{}".format(index), str(node), shape=node.shape())
        node.index = index
        i = index + 1
        for n in node.child:
            graph.node("node{}".format(i), str(node.child[n]), shape=node.child[n].shape())
            node.child[n].index = i
            graph.edge("node{}".format(index), "node{}".format(i), label=n)
            i = generateGraph(graph, node.child[n].child, i)
        return i
    elif node.child:
        graph.node("node{}".format(index), str(node), shape=node.shape())
        node.index = index
        graph.node("node{}".format(index + 1), str(node.child), shape=node.child.shape())
        graph.edge("node{}".format(index), "node{}".format(index + 1))
        if node.child.index:  # must be looping back
            return index + 1
        else:
            return generateGraph(graph, node.child, index + 1)
    else:
        graph.node("node{}".format(index), str(node), shape=node.shape())
        return index + 1


g = graphviz.Digraph(format='png')

tree = ast.parse(open('test.py', 'r').read())
print(tree)
print(astpp.dump(tree))

visitor = FlowchartMakingVisitor()
visitor.visit(tree)
start = visitor.start

generateGraph(g, start)
g.view(filename="flowchart")
