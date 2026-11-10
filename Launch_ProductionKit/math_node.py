import ast
import math
import textwrap

import bpy

from . import utility_panel

# Math Node: turns a Python math expression into a node group (Geometry, Shader, or Compositor nodes).
#
# The source text is stored as a custom property on the node group datablock itself, which is native
# Blender data: it survives saving from a Blender install without this extension, and the group keeps
# working (only the editing UI is missing). Regenerating updates the group in place, so the group
# interface keeps its identity and links to existing group nodes are preserved.
#
# Source is a single line. Newlines are written as the two characters \n, and the clipboard operator
# converts multi-line Python to that form. Two source styles are supported:
#   • Expression:  4 * t ** 3 if t < 0.5 else 1 - pow(-2 * t + 2, 3) / 2
#       Inputs are the variable names, in order of first use.
#   • Function:    def ease(t, v: vector = (0, 0, 1)): ...
#       Inputs come from the arguments (annotations pick float or vector, defaults set socket defaults).
#
# Supported: numbers, variables, + - * / // % **, comparisons, and/or/not, a if c else b, (x, y, z) vector
# literals, .x .y .z and [0] [1] [2], assignments (including tuple and +=), if / elif / else with return,
# and the functions listed in the tables below.

EXPRESSION_KEY = "productionkit_expression"
OUTPUT_NAME = "Result"
DEFAULT_GROUP_NAME = "Math Expression"

FLOAT = 'FLOAT'
VECTOR = 'VECTOR'

TREE_GROUP_NODES = {
	'GeometryNodeTree': 'GeometryNodeGroup',
	'ShaderNodeTree': 'ShaderNodeGroup',
	'CompositorNodeTree': 'CompositorNodeGroup',
}
SOCKET_TYPES = {FLOAT: 'NodeSocketFloat', VECTOR: 'NodeSocketVector'}

CONSTANTS = {'pi': math.pi, 'tau': math.tau, 'e': math.e}

# Python function name -> Math node operation
FLOAT_UNARY = {
	'sin': 'SINE', 'cos': 'COSINE', 'tan': 'TANGENT',
	'asin': 'ARCSINE', 'acos': 'ARCCOSINE', 'atan': 'ARCTANGENT',
	'sinh': 'SINH', 'cosh': 'COSH', 'tanh': 'TANH',
	'sqrt': 'SQRT', 'exp': 'EXPONENT', 'abs': 'ABSOLUTE', 'fabs': 'ABSOLUTE',
	'floor': 'FLOOR', 'ceil': 'CEIL', 'trunc': 'TRUNC', 'int': 'TRUNC',
	'fract': 'FRACT', 'sign': 'SIGN', 'radians': 'RADIANS', 'degrees': 'DEGREES', 'round': 'ROUND',
}
FLOAT_BINARY = {'pow': 'POWER', 'atan2': 'ARCTAN2', 'fmod': 'MODULO', 'snap': 'SNAP', 'pingpong': 'PINGPONG'}
FLOAT_TERNARY = {'wrap': 'WRAP'}

# Math operation -> Vector Math operation, for functions that also accept vectors
VECTOR_EQUIVALENT = {
	'ABSOLUTE': 'ABSOLUTE', 'FLOOR': 'FLOOR', 'CEIL': 'CEIL', 'FRACT': 'FRACTION', 'SIGN': 'SIGN',
	'SINE': 'SINE', 'COSINE': 'COSINE', 'TANGENT': 'TANGENT', 'ROUND': 'ROUND',
	'POWER': 'POWER', 'MODULO': 'MODULO', 'SNAP': 'SNAP', 'WRAP': 'WRAP',
	'MINIMUM': 'MINIMUM', 'MAXIMUM': 'MAXIMUM',
}

# Python function name -> (Vector Math operation, argument count, output type)
VECTOR_FUNCTIONS = {
	'dot': ('DOT_PRODUCT', 2, FLOAT), 'cross': ('CROSS_PRODUCT', 2, VECTOR),
	'length': ('LENGTH', 1, FLOAT), 'normalize': ('NORMALIZE', 1, VECTOR),
	'distance': ('DISTANCE', 2, FLOAT), 'reflect': ('REFLECT', 2, VECTOR),
	'project': ('PROJECT', 2, VECTOR), 'faceforward': ('FACEFORWARD', 3, VECTOR),
	'refract': ('REFRACT', 3, VECTOR),
}

VECTOR_ANNOTATIONS = {'vector', 'vec', 'vec3', 'vector3', 'float3', 'tuple'}
FLOAT_ANNOTATIONS = {'float', 'int', 'bool', 'number'}

# Constant folding for operations whose Python result matches the Blender node
FOLD = {
	'ADD': lambda a, b: a + b, 'SUBTRACT': lambda a, b: a - b, 'MULTIPLY': lambda a, b: a * b,
	'DIVIDE': lambda a, b: a / b, 'POWER': lambda a, b: a ** b,
	'FLOORED_MODULO': lambda a, b: a % b, 'FLOOR': lambda a: float(math.floor(a)),
	'CEIL': lambda a: float(math.ceil(a)), 'ABSOLUTE': abs, 'SQRT': math.sqrt,
	'SINE': math.sin, 'COSINE': math.cos, 'TANGENT': math.tan, 'EXPONENT': math.exp,
	'RADIANS': math.radians, 'DEGREES': math.degrees,
	'MINIMUM': min, 'MAXIMUM': max,
}

AXES = {'x': 0, 'y': 1, 'z': 2}



###########################################################################
# Errors and source encoding

class ExpressionError(Exception):
	pass


def decode_source(text):
	"""Single-line storage form -> multi-line Python"""
	return textwrap.dedent(text.replace('\\n', '\n')).strip('\n')


def encode_source(text):
	"""Multi-line Python -> single-line storage form"""
	lines = [line.expandtabs(4).rstrip() for line in text.replace('\r\n', '\n').split('\n')]
	lines = [line for line in lines if line.strip()]
	return '\\n'.join(textwrap.dedent('\n'.join(lines)).split('\n'))



###########################################################################
# Abstract graph (built and validated before any node is touched)

class Value:
	__slots__ = ('type', 'const', 'kind', 'props', 'args', 'out', 'input', 'boolean')

	def __init__(self, type, const=None, kind=None, props=(), args=(), out=0, input=None, boolean=False):
		self.type = type
		self.const = const
		self.kind = kind
		self.props = props
		self.args = args
		self.out = out
		self.input = input
		self.boolean = boolean


def _arg_key(value):
	return ('c', value.const) if value.const is not None else ('v', id(value))


class Compiler:
	def __init__(self):
		self.cache = {}
		self.inputs = {}

	########## Value construction ##########

	def const(self, number):
		return Value(FLOAT, const=float(number))

	def node(self, kind, props, args, out, type, boolean=False):
		key = (kind, props, tuple(_arg_key(a) for a in args), out)
		value = self.cache.get(key)
		if value is None:
			value = Value(type, kind=kind, props=props, args=tuple(args), out=out, boolean=boolean)
			self.cache[key] = value
		return value

	def group_input(self, name, type):
		value = Value(type, input=name)
		self.inputs[name] = value
		return value

	def need_float(self, value, what):
		if value.type != FLOAT:
			raise ExpressionError(f"{what} needs a float, not a vector (use .x .y .z or length())")
		return value

	########## Operations ##########

	def math(self, operation, *args, boolean=False):
		for arg in args:
			self.need_float(arg, operation.lower())
		if all(arg.const is not None for arg in args) and operation in FOLD:
			try:
				result = FOLD[operation](*(arg.const for arg in args))
				if isinstance(result, (int, float)) and math.isfinite(result):
					return self.const(result)
			except (ValueError, ZeroDivisionError, OverflowError):
				pass
		return self.node('MATH', (('operation', operation),), args, 0, FLOAT, boolean)

	def vector_math(self, operation, *args, out_type=VECTOR):
		# Output 0 is the vector, output 1 the float result
		return self.node('VMATH', (('operation', operation),), args, 0 if out_type == VECTOR else 1, out_type)

	def separate(self, vector, axis):
		if vector.const is not None:
			return self.const(vector.const[axis])
		return self.node('SEPARATE', (), (vector,), axis, FLOAT)

	def combine(self, x, y, z):
		if all(v.const is not None for v in (x, y, z)):
			return Value(VECTOR, const=(x.const, y.const, z.const))
		return self.node('COMBINE', (), (x, y, z), 0, VECTOR)

	def select(self, condition, if_true, if_false):
		"""Mix node controlled by a 0/1 condition; Python evaluates both sides, this does too"""
		if condition.const is not None:
			return if_true if condition.const else if_false
		if if_true is if_false:
			return if_true
		type = VECTOR if VECTOR in (if_true.type, if_false.type) else FLOAT
		props = (('data_type', type), ('clamp_factor', True))
		return self.node('MIX', props, (condition, if_false, if_true), 0, type)

	def truth(self, value):
		self.need_float(value, "A condition")
		if value.boolean:
			return value
		if value.const is not None:
			return Value(FLOAT, const=1.0 if value.const else 0.0, boolean=True)
		return self.not_equal(value, self.const(0.0))

	def invert(self, value):
		if value.const is not None:
			return Value(FLOAT, const=0.0 if value.const else 1.0, boolean=True)
		return self.math('SUBTRACT', self.const(1.0), value, boolean=True)

	def not_equal(self, a, b):
		return self.invert(self.compare('==', a, b))

	def compare(self, operator, a, b):
		self.need_float(a, "Comparison")
		self.need_float(b, "Comparison")
		if a.const is not None and b.const is not None:
			result = {'<': a.const < b.const, '>': a.const > b.const, '<=': a.const <= b.const,
				'>=': a.const >= b.const, '==': a.const == b.const, '!=': a.const != b.const}[operator]
			return Value(FLOAT, const=1.0 if result else 0.0, boolean=True)
		if operator == '<':
			return self.math('LESS_THAN', a, b, boolean=True)
		if operator == '>':
			return self.math('GREATER_THAN', a, b, boolean=True)
		if operator == '<=':
			return self.invert(self.math('GREATER_THAN', a, b, boolean=True))
		if operator == '>=':
			return self.invert(self.math('LESS_THAN', a, b, boolean=True))
		equal = self.node('MATH', (('operation', 'COMPARE'),), (a, b, self.const(0.0)), 0, FLOAT, True)
		return equal if operator == '==' else self.invert(equal)

	def binary(self, operator, a, b):
		operations = {ast.Add: 'ADD', ast.Sub: 'SUBTRACT', ast.Mult: 'MULTIPLY', ast.Div: 'DIVIDE',
			ast.Pow: 'POWER', ast.Mod: 'FLOORED_MODULO', ast.FloorDiv: 'FLOORDIV'}
		operation = operations.get(type(operator))
		if operation is None:
			raise ExpressionError(f"Operator {type(operator).__name__} is not supported")

		if a.type == FLOAT and b.type == FLOAT:
			if operation == 'FLOORDIV':
				return self.math('FLOOR', self.math('DIVIDE', a, b))
			return self.math(operation, a, b)

		# Vector arithmetic (float operands are splatted to vectors by the node sockets)
		if operation == 'MULTIPLY' and (a.type == FLOAT or b.type == FLOAT):
			vector, scale = (b, a) if a.type == FLOAT else (a, b)
			return self.node('VMATH', (('operation', 'SCALE'),), (vector, scale), 0, VECTOR)
		if operation == 'FLOORDIV':
			return self.vector_math('FLOOR', self.vector_math('DIVIDE', a, b))
		if operation == 'FLOORED_MODULO':
			operation = 'MODULO'
		return self.vector_math(operation, a, b)

	def negate(self, value):
		if value.const is not None:
			if value.type == FLOAT:
				return self.const(-value.const)
			return Value(VECTOR, const=tuple(-c for c in value.const))
		if value.type == FLOAT:
			return self.math('MULTIPLY', value, self.const(-1.0))
		return self.node('VMATH', (('operation', 'SCALE'),), (value, self.const(-1.0)), 0, VECTOR)

	def reduce(self, operation, values):
		result = values[0]
		for value in values[1:]:
			if VECTOR in (result.type, value.type):
				result = self.vector_math(VECTOR_EQUIVALENT[operation], result, value)
			else:
				result = self.math(operation, result, value)
		return result

	########## Function calls ##########

	def call(self, name, args):
		count = len(args)

		def expect(*counts):
			if count not in counts:
				raise ExpressionError(f"{name}() takes {' or '.join(str(c) for c in counts)} arguments, not {count}")

		if name in VECTOR_FUNCTIONS:
			operation, needed, out_type = VECTOR_FUNCTIONS[name]
			expect(needed)
			if operation == 'REFRACT':
				return self.node('VMATH', (('operation', 'REFRACT'),), (args[0], args[1], self.need_float(args[2], "refract() IOR")), 0, VECTOR)
			return self.vector_math(operation, *args, out_type=out_type)

		if name in ('min', 'max'):
			if count < 2:
				raise ExpressionError(f"{name}() needs at least 2 arguments")
			return self.reduce('MINIMUM' if name == 'min' else 'MAXIMUM', args)

		if name in FLOAT_UNARY or name in FLOAT_BINARY or name in FLOAT_TERNARY:
			operation = FLOAT_UNARY.get(name) or FLOAT_BINARY.get(name) or FLOAT_TERNARY.get(name)
			expect(1 if name in FLOAT_UNARY else 2 if name in FLOAT_BINARY else 3)
			if any(arg.type == VECTOR for arg in args):
				if operation not in VECTOR_EQUIVALENT:
					raise ExpressionError(f"{name}() does not support vectors")
				return self.vector_math(VECTOR_EQUIVALENT[operation], *args)
			return self.math(operation, *args)

		if name == 'float':
			expect(1)
			return self.need_float(args[0], "float()")
		if name == 'log':
			expect(1, 2)
			return self.math('LOGARITHM', args[0], args[1] if count == 2 else self.const(math.e))
		if name in ('log2', 'log10'):
			expect(1)
			return self.math('LOGARITHM', args[0], self.const(2.0 if name == 'log2' else 10.0))
		if name == 'hypot':
			expect(2)
			return self.math('SQRT', self.math('ADD', self.math('MULTIPLY', args[0], args[0]), self.math('MULTIPLY', args[1], args[1])))
		if name == 'clamp':
			expect(3)
			for arg in args:
				self.need_float(arg, "clamp()")
			return self.node('CLAMP', (), args, 0, FLOAT)
		if name in ('lerp', 'mix'):
			expect(3)
			type = VECTOR if VECTOR in (args[0].type, args[1].type) else FLOAT
			self.need_float(args[2], f"{name}() factor")
			return self.node('MIX', (('data_type', type), ('clamp_factor', False)), (args[2], args[0], args[1]), 0, type)
		if name == 'smoothstep':
			expect(3)
			for arg in args:
				self.need_float(arg, "smoothstep()")
			# smoothstep(edge0, edge1, x) -> Map Range inputs (value, from min, from max)
			return self.node('SMOOTHSTEP', (), (args[2], args[0], args[1]), 0, FLOAT)

		raise ExpressionError(f"Unknown function '{name}'")

	########## Expressions ##########

	def expression(self, node, env):
		if isinstance(node, ast.Constant):
			if isinstance(node.value, (bool, int, float)):
				return self.const(node.value)
			raise ExpressionError(f"Unsupported value {node.value!r}")

		if isinstance(node, ast.Name):
			if node.id in env:
				return env[node.id]
			if node.id in CONSTANTS:
				return self.const(CONSTANTS[node.id])
			raise ExpressionError(f"Unknown variable '{node.id}'")

		if isinstance(node, ast.UnaryOp):
			operand = self.expression(node.operand, env)
			if isinstance(node.op, ast.USub):
				return self.negate(operand)
			if isinstance(node.op, ast.UAdd):
				return operand
			if isinstance(node.op, ast.Not):
				return self.invert(self.truth(operand))
			raise ExpressionError("Unsupported unary operator")

		if isinstance(node, ast.BinOp):
			return self.binary(node.op, self.expression(node.left, env), self.expression(node.right, env))

		if isinstance(node, ast.Compare):
			operators = {ast.Lt: '<', ast.Gt: '>', ast.LtE: '<=', ast.GtE: '>=', ast.Eq: '==', ast.NotEq: '!='}
			left = self.expression(node.left, env)
			result = None
			for op, comparator in zip(node.ops, node.comparators):
				if type(op) not in operators:
					raise ExpressionError("Unsupported comparison")
				right = self.expression(comparator, env)
				part = self.compare(operators[type(op)], left, right)
				result = part if result is None else self.math('MULTIPLY', result, part, boolean=True)
				left = right
			return result

		if isinstance(node, ast.BoolOp):
			values = [self.truth(self.expression(v, env)) for v in node.values]
			operation = 'MULTIPLY' if isinstance(node.op, ast.And) else 'MAXIMUM'
			result = values[0]
			for value in values[1:]:
				result = self.math(operation, result, value, boolean=True)
			return result

		if isinstance(node, ast.IfExp):
			condition = self.truth(self.expression(node.test, env))
			if condition.const is not None:
				return self.expression(node.body if condition.const else node.orelse, env)
			return self.select(condition, self.expression(node.body, env), self.expression(node.orelse, env))

		if isinstance(node, ast.Tuple):
			if len(node.elts) != 3:
				raise ExpressionError("Vectors need exactly 3 components, like (x, y, z)")
			x, y, z = (self.need_float(self.expression(e, env), "Vector component") for e in node.elts)
			return self.combine(x, y, z)

		if isinstance(node, ast.Attribute):
			if isinstance(node.value, ast.Name) and node.value.id == 'math' and node.attr in CONSTANTS:
				return self.const(CONSTANTS[node.attr])
			if node.attr not in AXES:
				raise ExpressionError(f"Unknown attribute '.{node.attr}' (only .x .y .z)")
			vector = self.expression(node.value, env)
			if vector.type != VECTOR:
				raise ExpressionError(f".{node.attr} needs a vector; annotate the variable (v: vector)")
			return self.separate(vector, AXES[node.attr])

		if isinstance(node, ast.Subscript):
			index = node.slice
			if not (isinstance(index, ast.Constant) and index.value in (0, 1, 2)):
				raise ExpressionError("Vectors can only be indexed with 0, 1, or 2")
			vector = self.expression(node.value, env)
			if vector.type != VECTOR:
				raise ExpressionError("Indexing needs a vector; annotate the variable (v: vector)")
			return self.separate(vector, index.value)

		if isinstance(node, ast.Call):
			func = node.func
			if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == 'math':
				name = func.attr
			elif isinstance(func, ast.Name):
				name = func.id
			else:
				raise ExpressionError("Unsupported function call")
			if node.keywords:
				raise ExpressionError("Keyword arguments are not supported")
			return self.call(name, [self.expression(a, env) for a in node.args])

		raise ExpressionError(f"Unsupported syntax: {type(node).__name__}")

	########## Statements ##########

	def block(self, statements, env):
		"""Run statements; returns the Value that is returned, or None if the block falls through"""
		statements = list(statements)
		for index, statement in enumerate(statements):
			if isinstance(statement, ast.Return):
				if statement.value is None:
					raise ExpressionError("return needs a value")
				return self.expression(statement.value, env)

			elif isinstance(statement, ast.Expr):
				if isinstance(statement.value, ast.Constant) and isinstance(statement.value.value, str):
					continue # Docstring
				if index == len(statements) - 1:
					return self.expression(statement.value, env) # Final bare expression is the result
				raise ExpressionError("An expression statement has no effect")

			elif isinstance(statement, (ast.Assign, ast.AnnAssign)):
				if isinstance(statement, ast.AnnAssign):
					if statement.value is None:
						continue
					targets = [statement.target]
				else:
					targets = statement.targets
				for target in targets:
					self.assign(target, statement.value, env)

			elif isinstance(statement, ast.AugAssign):
				if not isinstance(statement.target, ast.Name):
					raise ExpressionError("Only variables can be assigned")
				current = self.expression(statement.target, env)
				env[statement.target.id] = self.binary(statement.op, current, self.expression(statement.value, env))

			elif isinstance(statement, ast.Pass):
				continue

			elif isinstance(statement, ast.If):
				condition = self.truth(self.expression(statement.test, env))
				rest = statements[index + 1:]
				if condition.const is not None:
					return self.block((statement.body if condition.const else statement.orelse) + rest, env)

				if any(isinstance(n, ast.Return) for n in ast.walk(statement)):
					# Each side continues with the remaining statements; both must end in a return
					if_true = self.block(statement.body + rest, dict(env))
					if_false = self.block(statement.orelse + rest, dict(env))
					if if_true is None or if_false is None:
						raise ExpressionError("Every branch of an if statement must return a value")
					return self.select(condition, if_true, if_false)

				env_true, env_false = dict(env), dict(env)
				if self.block(statement.body, env_true) is not None or self.block(statement.orelse, env_false) is not None:
					raise ExpressionError("An expression statement has no effect")
				for name in env_true.keys() & env_false.keys(): # Names defined in only one branch are dropped
					env[name] = self.select(condition, env_true[name], env_false[name])

			else:
				raise ExpressionError(f"Unsupported statement: {type(statement).__name__}")
		return None

	def assign(self, target, value_node, env):
		if isinstance(target, ast.Name):
			env[target.id] = self.expression(value_node, env)
		elif isinstance(target, ast.Tuple):
			names = target.elts
			if not all(isinstance(n, ast.Name) for n in names):
				raise ExpressionError("Only variables can be assigned")
			if isinstance(value_node, ast.Tuple) and len(value_node.elts) == len(names):
				values = [self.expression(v, env) for v in value_node.elts] # Right side is evaluated first
			else:
				vector = self.expression(value_node, env)
				if vector.type != VECTOR or len(names) != 3:
					raise ExpressionError("Unpacking needs a matching tuple or a vector into 3 names")
				values = [self.separate(vector, i) for i in range(3)]
			for name, value in zip(names, values):
				env[name.id] = value
		else:
			raise ExpressionError("Only variables can be assigned")



###########################################################################
# Source -> function definition

def _annotation_type(annotation):
	if annotation is None:
		return None
	name = ast.unparse(annotation).replace("'", "").replace('"', '').split('.')[-1].lower()
	if name in VECTOR_ANNOTATIONS:
		return VECTOR
	if name in FLOAT_ANNOTATIONS:
		return FLOAT
	raise ExpressionError(f"Unknown type '{ast.unparse(annotation)}' (use float or vector)")


def _default_value(node, type):
	try:
		value = ast.literal_eval(node)
	except ValueError:
		raise ExpressionError("Argument defaults must be numbers or (x, y, z)")
	if isinstance(value, (bool, int, float)):
		return (float(value),) * 3 if type == VECTOR else float(value)
	if isinstance(value, tuple) and len(value) == 3 and all(isinstance(v, (int, float)) for v in value):
		if type != VECTOR:
			raise ExpressionError("A vector default needs a vector annotation (v: vector)")
		return tuple(float(v) for v in value)
	raise ExpressionError("Argument defaults must be numbers or (x, y, z)")


def _implied_vectors(tree):
	"""Names used in ways that only make sense for vectors"""
	names = set()
	for node in ast.walk(tree):
		if isinstance(node, (ast.Attribute, ast.Subscript)) and isinstance(node.value, ast.Name):
			if not isinstance(node, ast.Attribute) or node.attr in AXES:
				names.add(node.value.id)
		elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in VECTOR_FUNCTIONS:
			limit = 2 if node.func.id == 'refract' else 3
			names.update(a.id for a in node.args[:limit] if isinstance(a, ast.Name))
	return names


def compile_source(source):
	"""Returns (suggested name, inputs, result) where inputs is a list of (name, type, default or None)"""
	text = decode_source(source)
	if not text.strip():
		raise ExpressionError("The expression is empty")
	try:
		module = ast.parse(text, mode='exec')
	except SyntaxError as error:
		raise ExpressionError(f"Syntax error: {error.msg} (column {error.offset})")

	compiler = Compiler()
	body = module.body
	name = DEFAULT_GROUP_NAME
	inputs = []

	if len(body) == 1 and isinstance(body[0], ast.FunctionDef):
		function = body[0]
		name = function.name.replace('_', ' ').title() if function.name else name
		arguments = function.args
		if arguments.vararg or arguments.kwarg or arguments.kwonlyargs or arguments.posonlyargs:
			raise ExpressionError("Only plain arguments are supported")
		defaults = [None] * (len(arguments.args) - len(arguments.defaults)) + list(arguments.defaults)
		for argument, default in zip(arguments.args, defaults):
			type = _annotation_type(argument.annotation)
			if type is None:
				type = VECTOR if default is not None and isinstance(default, ast.Tuple) else FLOAT
			inputs.append((argument.arg, type, _default_value(default, type) if default is not None else None))
		body = function.body
	else:
		assigned = {n.id for n in ast.walk(module) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
		called = {id(n.func) for n in ast.walk(module) if isinstance(n, ast.Call)}
		loads = sorted((n for n in ast.walk(module) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
			and id(n) not in called and n.id not in CONSTANTS and n.id not in assigned and n.id != 'math'),
			key=lambda n: (n.lineno, n.col_offset))
		vectors = _implied_vectors(module)
		for load in loads:
			if load.id not in {i[0] for i in inputs}:
				inputs.append((load.id, VECTOR if load.id in vectors else FLOAT, None))

	names = [i[0] for i in inputs]
	if len(set(names)) != len(names):
		raise ExpressionError("Duplicate input names")

	env = {input_name: compiler.group_input(input_name, type) for input_name, type, default in inputs}
	result = compiler.block(body, env)
	if result is None:
		raise ExpressionError("No result: end with a return statement or an expression")
	return name, inputs, result



###########################################################################
# Node group building

def _interface_items(tree, in_out):
	return [item for item in tree.interface.items_tree if item.item_type == 'SOCKET' and item.in_out == in_out]


def _sync_interface(tree, inputs, result_type):
	"""Update the group interface in place so existing group nodes keep their links"""
	interface = tree.interface
	old = _interface_items(tree, 'INPUT')
	new_names = [i[0] for i in inputs]

	# Pair by name first, then pair what is left by position (so renaming a variable keeps its links)
	pairs = {}
	for item in old:
		if item.name in new_names and item.name not in pairs:
			pairs[item.name] = item
	leftover_old = [item for item in old if item not in pairs.values()]
	leftover_new = [n for n in new_names if n not in pairs]
	for item, new_name in zip(leftover_old, leftover_new):
		pairs[new_name] = item
	paired = set(id(item) for item in pairs.values())

	for item in old:
		if id(item) not in paired:
			interface.remove(item)

	items = []
	for name, type, default in inputs:
		item = pairs.get(name)
		if item is None:
			item = interface.new_socket(name, in_out='INPUT', socket_type=SOCKET_TYPES[type])
			if default is not None:
				item.default_value = default
		else:
			if item.name != name:
				item.name = name
			if item.socket_type != SOCKET_TYPES[type]:
				item.socket_type = SOCKET_TYPES[type]
			if default is not None:
				item.default_value = default
		items.append(item)

	outputs = _interface_items(tree, 'OUTPUT')
	for extra in outputs[1:]:
		interface.remove(extra)
	if outputs:
		output = outputs[0]
		output.name = OUTPUT_NAME
		if output.socket_type != SOCKET_TYPES[result_type]:
			output.socket_type = SOCKET_TYPES[result_type]
	else:
		output = interface.new_socket(OUTPUT_NAME, in_out='OUTPUT', socket_type=SOCKET_TYPES[result_type])

	# Inputs follow the outputs in the interface list, in signature order
	base = len(interface.items_tree) - len(items)
	for position, item in enumerate(items):
		interface.move(item, base + position)

	tree.interface_update(bpy.context)
	return items, output


def by_identifier(sockets, identifier):
	return next(s for s in sockets if s.identifier == identifier)


NODE_ESTIMATED_HEIGHT = {'MATH': 150, 'VMATH': 210, 'MIX': 230, 'CLAMP': 160, 'SMOOTHSTEP': 260, 'SEPARATE': 140, 'COMBINE': 160}
COLUMN_WIDTH = 240


def _build_nodes(tree, inputs, result, input_items, output_item):
	nodes = tree.nodes
	nodes.clear()

	group_input = nodes.new('NodeGroupInput')
	group_input.location = (0, 0)
	input_sockets = {item.name: group_input.outputs[item.identifier] for item in input_items}

	levels = {}
	def level(value):
		if id(value) not in levels:
			levels[id(value)] = 0 if value.kind is None else 1 + max([level(a) for a in value.args if a.const is None] or [0])
		return levels[id(value)]

	created = {}
	column_heights = {}

	def feed(socket, value):
		if value.const is not None:
			if socket.type == 'VECTOR':
				socket.default_value = value.const if value.type == VECTOR else (value.const,) * 3
			else:
				socket.default_value = value.const
		else:
			tree.links.new(output_socket(value), socket)

	def output_socket(value):
		if value.input is not None:
			return input_sockets[value.input]
		if id(value) not in created:
			created[id(value)] = make(value)
		return created[id(value)]

	def make(value):
		properties = dict(value.props)
		kind = value.kind
		idname = {'MATH': 'ShaderNodeMath', 'VMATH': 'ShaderNodeVectorMath', 'MIX': 'ShaderNodeMix', 'CLAMP': 'ShaderNodeClamp',
			'SMOOTHSTEP': 'ShaderNodeMapRange', 'SEPARATE': 'ShaderNodeSeparateXYZ', 'COMBINE': 'ShaderNodeCombineXYZ'}[kind]
		node = nodes.new(idname)

		if kind == 'MATH' or kind == 'VMATH':
			node.operation = properties['operation']
			sockets = [node.inputs[i] for i in range(len(value.args))]
			if kind == 'VMATH' and properties['operation'] in ('SCALE', 'REFRACT'):
				sockets[-1] = node.inputs[3] # Scale / IOR is a float socket after the three vectors
			for socket, arg in zip(sockets, value.args):
				feed(socket, arg)
			out = node.outputs[value.out]
		elif kind == 'MIX':
			node.data_type = properties['data_type']
			node.clamp_factor = properties['clamp_factor']
			suffix = 'Float' if properties['data_type'] == FLOAT else 'Vector'
			factor, a, b = value.args
			feed(by_identifier(node.inputs, 'Factor_Float'), factor)
			feed(by_identifier(node.inputs, 'A_' + suffix), a)
			feed(by_identifier(node.inputs, 'B_' + suffix), b)
			out = by_identifier(node.outputs, 'Result_' + suffix)
		elif kind == 'CLAMP':
			for socket_name, arg in zip(('Value', 'Min', 'Max'), value.args):
				feed(node.inputs[socket_name], arg)
			out = node.outputs[0]
		elif kind == 'SMOOTHSTEP':
			node.data_type = 'FLOAT'
			node.interpolation_type = 'SMOOTHSTEP'
			node.clamp = True
			for socket_name, arg in zip(('Value', 'From Min', 'From Max'), value.args):
				feed(node.inputs[socket_name], arg)
			out = node.outputs['Result']
		elif kind == 'SEPARATE':
			feed(node.inputs[0], value.args[0])
			out = node.outputs[value.out]
		else:
			for socket, arg in zip(node.inputs, value.args):
				feed(socket, arg)
			out = node.outputs[0]

		column = level(value)
		node.location = (column * COLUMN_WIDTH, -column_heights.get(column, 0))
		column_heights[column] = column_heights.get(column, 0) + NODE_ESTIMATED_HEIGHT[kind]
		return out

	final = result
	if final.const is not None:
		# A constant result needs a node to carry it to the output
		operation = 'ADD'
		if final.type == FLOAT:
			final = Value(FLOAT, kind='MATH', props=(('operation', operation),), args=(result, Value(FLOAT, const=0.0)))
		else:
			final = Value(VECTOR, kind='VMATH', props=(('operation', operation),), args=(result, Value(VECTOR, const=(0.0, 0.0, 0.0))))

	source = output_socket(final)
	depth = max(level(final), 0) + 1
	group_output = nodes.new('NodeGroupOutput')
	group_output.location = (depth * COLUMN_WIDTH, 0)
	group_output.is_active_output = True
	tree.links.new(source, group_output.inputs[output_item.identifier])

	# Spread unconnected-height columns around the middle line
	for node in nodes:
		if node.bl_idname not in ('NodeGroupInput', 'NodeGroupOutput'):
			column = round(node.location.x / COLUMN_WIDTH)
			node.location.y += column_heights[column] / 2 - 60


def build_group(tree, source):
	"""Compile the source and (re)build the node group; nothing is changed if the source has an error"""
	name, inputs, result = compile_source(source)
	items, output = _sync_interface(tree, inputs, result.type)
	_build_nodes(tree, inputs, result, items, output)
	tree[EXPRESSION_KEY] = source
	return name



###########################################################################
# Validation
#
# Blender only changes a text field's value when editing is committed (Enter or clicking away), so
# compiling once per distinct source string means nothing runs while typing or on ordinary redraws.

_validation_cache = {}

def validate(source):
	"""Returns (valid, message), cached by source text"""
	result = _validation_cache.get(source)
	if result is None:
		if len(_validation_cache) > 64:
			_validation_cache.clear()
		if not source.strip():
			result = (False, "")
		else:
			try:
				name, inputs, value = compile_source(source)
				names = ", ".join(i[0] for i in inputs) or "none"
				result = (True, f"Inputs: {names}  →  {'Vector' if value.type == VECTOR else 'Float'}")
			except ExpressionError as error:
				result = (False, str(error))
		_validation_cache[source] = result
	return result


def _draw_status(layout, source):
	valid, message = validate(source)
	if message:
		row = layout.row()
		row.alert = not valid
		row.label(text=message, icon='CHECKMARK' if valid else 'ERROR')
	return valid



###########################################################################
# Editor helpers

def _supported_tree_type(context):
	space = context.space_data
	if context.area is None or context.area.type != 'NODE_EDITOR' or space.type != 'NODE_EDITOR':
		return None
	tree_type = space.tree_type
	if tree_type == 'CompositorNodeTree' and bpy.app.version < (5, 0, 0):
		return None # Compositor Math nodes became shared with the Shader/Geometry Math nodes in 5.0
	return tree_type if tree_type in TREE_GROUP_NODES else None


def _find_group(context):
	"""Returns (node tree being edited, or None; multiple nodes selected)"""
	space = context.space_data
	edit_tree = space.edit_tree
	if edit_tree is None:
		return None, False
	if EXPRESSION_KEY in edit_tree:
		return edit_tree, False
	selected = [n for n in edit_tree.nodes if n.select]
	if len(selected) == 1 and selected[0].type == 'GROUP':
		tree = selected[0].node_tree
		if tree is not None and EXPRESSION_KEY in tree:
			return tree, False
	return None, len(selected) > 1



###########################################################################
# Operators

class PRODUCTIONKIT_OT_math_node_generate(bpy.types.Operator):
	"""Generate a node group from the math expression, or update the selected expression group"""
	bl_idname = "production_kit.math_node_generate"
	bl_label = "Generate Group"
	bl_options = {'REGISTER', 'UNDO'}

	update: bpy.props.BoolProperty(options={'HIDDEN'}, default=False)

	@classmethod
	def poll(cls, context):
		return _supported_tree_type(context) is not None

	def execute(self, context):
		space = context.space_data

		if self.update:
			tree, multiple = _find_group(context)
			if tree is None:
				self.report({'ERROR'}, "Select a single expression group node")
				return {'CANCELLED'}
			try:
				build_group(tree, str(tree[EXPRESSION_KEY]))
			except ExpressionError as error:
				self.report({'ERROR'}, str(error))
				return {'CANCELLED'}
			self.report({'INFO'}, f"Updated {tree.name}")
			return {'FINISHED'}

		source = context.scene.production_kit_settings.math_expression
		try:
			name, inputs, result = compile_source(source) # Validate before creating anything
		except ExpressionError as error:
			self.report({'ERROR'}, str(error))
			return {'CANCELLED'}

		settings = context.scene.production_kit_settings
		tree = bpy.data.node_groups.new(settings.math_name.strip() or name, space.tree_type)
		try:
			build_group(tree, source)
		except Exception as error:
			bpy.data.node_groups.remove(tree)
			self.report({'ERROR'}, f"Could not build the group: {error}")
			return {'CANCELLED'}

		edit_tree = space.edit_tree
		if edit_tree is not None:
			for node in edit_tree.nodes:
				node.select = False
			node = edit_tree.nodes.new(TREE_GROUP_NODES[space.tree_type])
			node.node_tree = tree
			node.location = space.cursor_location
			node.select = True
			edit_tree.nodes.active = node
		self.report({'INFO'}, f"Created {tree.name}")
		return {'FINISHED'}


class PRODUCTIONKIT_OT_math_node_paste(bpy.types.Operator):
	"""Paste Python code from the clipboard as a single-line expression"""
	bl_idname = "production_kit.math_node_paste"
	bl_label = "Paste Python"
	bl_options = {'REGISTER', 'UNDO'}

	update: bpy.props.BoolProperty(options={'HIDDEN'}, default=False)

	@classmethod
	def poll(cls, context):
		return _supported_tree_type(context) is not None

	def execute(self, context):
		text = context.window_manager.clipboard
		if not text.strip():
			self.report({'WARNING'}, "The clipboard is empty")
			return {'CANCELLED'}
		encoded = encode_source(text)
		if self.update:
			tree, multiple = _find_group(context)
			if tree is None:
				self.report({'ERROR'}, "Select a single expression group node")
				return {'CANCELLED'}
			tree[EXPRESSION_KEY] = encoded
		else:
			context.scene.production_kit_settings.math_expression = encoded
		return {'FINISHED'}



###########################################################################
# Panel

class PRODUCTIONKIT_PT_math_node(bpy.types.Panel):
	"""Generate node groups from Python math expressions"""
	bl_idname = "PRODUCTIONKIT_PT_math_node"
	bl_label = "Math Expression"
	bl_space_type = 'NODE_EDITOR'
	bl_region_type = 'UI'
	bl_category = "Node"
	bl_options = {'DEFAULT_CLOSED'}
	category_preference = "math_node_category"

	@classmethod
	def poll(cls, context):
		return _supported_tree_type(context) is not None

	def draw(self, context):
		layout = self.layout
		tree, multiple = _find_group(context)
		
		if tree is not None:
			# An existing expression group: edit its name and stored source
			layout.prop(tree, "name", text="", icon='NODETREE')
			layout.prop(tree, f'["{EXPRESSION_KEY}"]', text="")
			valid = _draw_status(layout, str(tree[EXPRESSION_KEY]))
			row = layout.row(align=True)
			row.operator(PRODUCTIONKIT_OT_math_node_paste.bl_idname, text="Paste Python", icon='PASTEDOWN').update = True
			sub = row.row(align=True)
			sub.enabled = valid
			sub.operator(PRODUCTIONKIT_OT_math_node_generate.bl_idname, text="Update Group", icon='FILE_REFRESH').update = True
		else:
			# Nothing to edit: the scene settings define a new group
			settings = context.scene.production_kit_settings
			layout.prop(settings, "math_name", text="", icon='NODETREE', placeholder="Group name")
			layout.prop(settings, "math_expression", text="", placeholder="Expression")
			valid = _draw_status(layout, settings.math_expression)
			row = layout.row(align=True)
			row.operator(PRODUCTIONKIT_OT_math_node_paste.bl_idname, text="Paste Python", icon='PASTEDOWN')
			sub = row.row(align=True)
			sub.enabled = valid
			sub.operator(PRODUCTIONKIT_OT_math_node_generate.bl_idname, text="Generate Group", icon='ADD')
			if multiple:
				layout.label(text="Select one group node to edit it", icon='INFO')



# Registration
classes = (
	PRODUCTIONKIT_OT_math_node_generate,
	PRODUCTIONKIT_OT_math_node_paste,
	)

panels = [
	PRODUCTIONKIT_PT_math_node,
	]

def register():
	for cls in classes:
		bpy.utils.register_class(cls)
	utility_panel.register_panels(panels)

def unregister():
	utility_panel.unregister_panels(panels)
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
