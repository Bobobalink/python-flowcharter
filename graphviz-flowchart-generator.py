import ast
import graphviz
import textwrap
import sys

textwidth = 28


class FlowchartNode:
    def __init__(self):
        self.child = None
        self.index = None

    def __str__(self):
        return textwrap.fill("base flowchart node?", width=textwidth)

    def shape(self):
        return "tripleoctagon"


class StartNode(FlowchartNode):
    def __str__(self):
        return "Start"

    def shape(self):
        return "ellipse"


class EndNode(FlowchartNode):
    def __str__(self):
        return "Stop"

    def shape(self):
        return "ellipse"


class InputNode(FlowchartNode):
    def __init__(self, varName):
        self.name = varName
        super().__init__()

    def __str__(self):
        return textwrap.fill("input {}".format(self.name), width=textwidth)

    def shape(self):
        return "parallelogram"


class OutputNode(FlowchartNode):
    def __init__(self, varName):
        self.name = varName
        super().__init__()

    def __str__(self):
        return textwrap.fill("output {}".format(self.name), width=textwidth)

    def shape(self):
        return "parallelogram"


class ProcessNode(FlowchartNode):
    def __init__(self, text):
        self.text = text
        super().__init__()

    def __str__(self):
        return textwrap.fill(self.text, width=textwidth)

    def shape(self):
        return "rectangle"


class VariableAssignmentNode(ProcessNode):
    def __init__(self, varName, expression):
        text = "{} = {}".format(varName, expression)
        super().__init__(text)


class ConditionalNode(FlowchartNode):
    def __init__(self, condition):
        self.condition = condition
        super().__init__()
        self.child = {"No": None, "Yes": None}

    def __str__(self):
        return textwrap.fill(self.condition, width=textwidth)

    def shape(self):
        return "diamond"


class SubProcessNode(FlowchartNode):
    def __init__(self, subprocessName):
        self.name = subprocessName
        super().__init__()

    def __str__(self):
        return textwrap.fill("| {} |".format(self.name), width=textwidth)

    def shape(self):
        return "rectangle"


class DummyConjunctionNode(FlowchartNode):  # node to allow two nodes to return to the same place
    def __init__(self):
        super().__init__()

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
        self.start = StartNode()
        self.currentParent = self.start

    def visit_Module(self, node: ast.Module):
        for n in node.body:
            self.visit(n)
        self.appendNode(EndNode())

    def visit_Assign(self, node):
        if isinstance(node.value, ast.Call):  # special case for / input / nodes
            if node.value.func.id == 'input':
                self.appendNode(InputNode(node.targets[0].id))
                return
            if isinstance(node.value.args[0], ast.Call) and node.value.args[0].func.id == 'input':  # basically, assume that any single function wrapping an input() statement in an assign is just a typecast
                self.appendNode(InputNode(node.targets[0].id))
                return
        rhs = self.parseChunk(node.value)
        self.appendNode(VariableAssignmentNode(node.targets[0].id, rhs))

    def visit_AugAssign(self, node):
        rhs = self.parseChunk(node.value)
        self.appendNode(VariableAssignmentNode(node.target.id, "{0} {1} {2}".format(node.target.id, self.operators[node.op.__class__], rhs)))

    def visit_Expr(self, node):
        if isinstance(node.value, ast.Call):
            if node.value.func.id in {'print', 'pprint'}:  # / output / special casing
                self.appendNode(OutputNode(', '.join(self.parseFunctionArgs(node.value))))
            else:
                self.appendNode(ProcessNode(self.parseFunctionCall(node.value)))
        else:
            raise Exception("Unknown Node type in Expr: {0} (line {0.lineno} col {0.col_offset})".format(node.value))

    def visit_If(self, node):
        cond = self.parseChunk(node.test)

        condNode = ConditionalNode(cond)
        self.appendNode(condNode)
        condNode.child['Yes'] = DummyMiddleNode()
        self.currentParent = condNode.child['Yes']
        for n in node.body:
            self.visit(n)
        endbody = self.currentParent  # so we can connect it to the endcap eventually
        condNode.child['No'] = DummyMiddleNode()
        self.currentParent = condNode.child['No']
        for n in node.orelse:
            self.visit(n)
        endcap = DummyConjunctionNode()
        endbody.child = endcap
        self.currentParent.child = endcap
        self.currentParent = endcap

    def visit_ImportFrom(self, node):
        pass

    def visit_While(self, node):
        top = DummyConjunctionNode()
        self.appendNode(top)
        c = self.parseChunk(node.test)
        condNode = ConditionalNode(c)
        self.appendNode(condNode)
        condNode.child["Yes"] = DummyMiddleNode()
        self.currentParent = condNode.child["Yes"]
        for n in node.body:
            self.visit(n)
        self.currentParent.child = top  # loop back
        condNode.child["No"] = DummyMiddleNode()
        self.currentParent = condNode.child["No"]

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


def deleteExtraneousNodes(node):
    if node.index == 0:
        return
    if isinstance(node.child, dict):
        for n in node.child:
            if isinstance(node.child[n], (DummyMiddleNode, DummyConjunctionNode)):
                node.child[n] = node.child[n].child
                deleteExtraneousNodes(node)  # test for if there's two dummy nodes one after another
            else:
                deleteExtraneousNodes(node.child[n])
        node.index = 0
    elif node.child:
        if isinstance(node.child, (DummyMiddleNode, DummyConjunctionNode)):
            node.child = node.child.child
            deleteExtraneousNodes(node)
        else:
            node.index = 0
            deleteExtraneousNodes(node.child)


directions = {"No": "s", "Yes": "e"}  # choose which corner of the node each child will come out of. Statically chosen, which makes some layouts uglier but overall helps


def generateGraph(graph: graphviz.Digraph, node):
    if isinstance(node.child, dict):
        ind = node.index + 1
        for n in node.child:
            if node.child[n].index:
                graph.edge("node{}".format(node.index), "node{}".format(node.child[n].index), label=n, tailport=directions[n], headport='n')
            else:
                graph.node("node{}".format(ind), str(node.child[n]), shape=node.child[n].shape())
                graph.edge("node{}".format(node.index), "node{}".format(ind), label=n, tailport=directions[n], headport='n')
                node.child[n].index = ind
                ind = generateGraph(graph, node.child[n]) + 1
        return ind
    elif node.child:
        if node.child.index:  # must be looping back
            graph.edge("node{}".format(node.index), "node{}".format(node.child.index), tailport='s', headport='n')
            return node.index + 1
        else:
            graph.node("node{}".format(node.index + 1), str(node.child), shape=node.child.shape())
            node.child.index = node.index + 1
            graph.edge("node{}".format(node.index), "node{}".format(node.child.index), tailport='s', headport='n')
            return generateGraph(graph, node.child) + 1
    return node.index


def printNodes(node):
    print(repr(node))
    if isinstance(node.child, dict):
        for n in node.child:
            printNodes(node.child[n])
            print('-------')
        print('-----------')
    elif node.child:
        printNodes(node.child)


def main():
    try:
        filename = sys.argv[1]
    except IndexError:
        print("No filename passed in")
        sys.exit(1)
    try:
        ftext = open(filename, 'r').read()
    except FileNotFoundError:
        print("Cannot find the file '{}'".format(filename))
        sys.exit(1)
    try:
        tree = ast.parse(ftext)
    except SyntaxError as e:
        print("Invalid syntax in file:")
        print(e)
        sys.exit(1)

    visitor = FlowchartMakingVisitor()
    visitor.visit(tree)
    start = visitor.start
    deleteExtraneousNodes(start)
    g = graphviz.Digraph(format='png', engine='dot')
    g.attr(splines='spline')
    g.attr(overlap='voronoi')
    g.attr(concentrate='false')
    g.node('node1', str(start), shape=start.shape())
    start.index = 1
    generateGraph(g, start)
    g.view(filename="flowchart")


if __name__ == '__main__':
    main()
