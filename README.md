# python-flowcharter

Converts (exceedingly simple) python programs into flowcharts

#### Usage
Run the program with the path to the file as the first argument

Example: `python graphviz-flowchart-generator.py test.py`


### Limitations
* No function declarations in the file
* All function calls will be printed as they look in code (for example `func(a, b)`)
* No Lists yet
* No For loops yet
* Excessive number of parentheses in complex expressions
