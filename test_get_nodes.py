import unittest
import get_nodes



_testnum = 0
def test_factory(A, B, errmsg=None):
	"""
	I want one test per assertion, rather than each case failing at the first assertion. this function lets me do that
	"""

	global _testnum

	testname = 'dyntest' + str(_testnum)

	globals()[testname] = type(testname, (unittest.TestCase,),
		{'input': A, 'expected': B, 'errmsg': errmsg, 'testme': lambda self: self.assertEqual(self.input, self.expected, self.errmsg)})

	_testnum += 1





f = get_nodes.mmnode_plus.parse_node_text

states = ('ignore', 'ignore_all', 'ignore_children')

tests = (
	('hello', ()),
	('hello (i)', ('ignore',)),
	('hello (ic)', ('ignore_children',)),
	('hello (ia)', ('ignore_all',)),
	('school principal interview after leaving (ic) (m: magnet)', ('ignore_children',))
)

for test in tests:
	result = f(test[0])
	for state in states:
		test_factory(state in test[1], result.get(state) or False, "Unexpected %s for state %s on input %s" % (result.get(state), state, test[0]))






root = get_nodes.mmnode_plus.factory('/Users/nick/Documents/lie to me.mm')

tests = [
	(root, {'skip_traversal': False, 'skip_as_child': True, 'skip_as_parent': False, 'is_leaf': False}),
	(root[0], {'skip_traversal': False, 'skip_as_child': False, 'skip_as_parent': False, 'is_leaf': False}),
	(root[1], {'skip_traversal': True, 'skip_as_child': True, 'skip_as_parent': True}),
	(root[1][0], {'skip_traversal': True}),
	(root[0][0], {'is_leaf': False, 'skip_traversal': False, 'skip_as_child': False, 'skip_as_parent': False}),
	(root[0][0][0], {'is_leaf': True, 'skip_traversal': False, 'skip_as_child': False, 'skip_as_parent': True}),
	(root[0][4], {'skip_traversal': True, 'skip_as_child': True, 'skip_as_parent': True}),
	(root[0][7], {'skip_traversal': False, 'skip_as_child': False, 'skip_as_parent': True}),
	(root[1][11], {'skip_traversal': True, 'skip_as_child': True, 'skip_as_parent': True}),
	(root[1][11][0], {'skip_traversal': True, 'skip_as_child': True, 'skip_as_parent': True}),
]

for (node, states) in tests:
	for test_state, exp_result in states.iteritems():
		input = node.__getattribute__(test_state)()
		errstr = "expected %s, not %s for state %s of node %s %s" % (input, exp_result, test_state, repr(node), repr(node.__dict__))

		test_factory(input, exp_result, errstr)




unittest.main()

