import ast
import astpp

tree = ast.parse(open('test.py', 'r').read())
print(astpp.dump(tree))
