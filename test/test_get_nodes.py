#!/usr/bin/env python

import unittest

from factory import test_factory, finish

import sys
sys.path.append('..')
import get_nodes





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






root = get_nodes.mmnode_plus.factory('testmap.mm')



test_factory('lie to me', root.ultimate_parent().text)



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

    (root[4][2][1], {'skip_as_child': True}),
]

for (node, states) in tests:
    for test_state, exp_result in states.iteritems():
        input = node.__getattribute__(test_state)()
        errstr = "expected %s, not %s for state %s of node %s %s" % (input, exp_result, test_state, repr(node), repr(node.__dict__))

        test_factory(input, exp_result, errstr)

    test_factory('lie to me', root.ultimate_parent().text)




# sibling tests
sib_tests = (
    # these contain no special syntax:
    (root[3][0][0], (None, None), False),
    (root[3][1][0], (None, 'sibb'), True),
    (root[3][1][1], ('siba', None), True),
    (root[3][2][0], (None, 'sib2'), True),
    (root[3][2][1], ('sib1', 'sib3'), True),
    (root[3][2][2], ('sib2', None), True),


    # these contain some ignore syntax:
    (root[4][0][0], (None, None), False),

    (root[4][1][0], (None, None), False),

    (root[4][2][0], (None, 'sib3'), True),
    (root[4][2][1], ('sib1', 'sib3'), True),
    (root[4][2][2], ('sib1', None), True),

    (root[4][3][0], (None, None), False),
    (root[4][3][1], (None, None), False),

    (root[4][4][0], (None, 'sibb'), True),
    (root[4][4][1], (None, None), False),

    (root[4][5][0], (None, 'sib2'), True),
    (root[4][5][1], (None, 'sib3'), True),
    (root[4][5][2], ('sib2', None), True),

    (root[4][6][0], (None, 'sib2'), True),
    (root[4][6][1], ('sib1', None), True),
    (root[4][6][2], ('sib2', None), True),
)


for (node, exp_sibs, any_sibs) in sib_tests:
    test_factory(tuple(n.text if n is not None else None for n in node.get_immediate_siblings()), exp_sibs)
    test_factory(node.has_any_siblings(), any_sibs)



# split_mnemonic
test_factory(root[5][0].split_mnemonic(), map(unicode, ('something', 'a mnemonic')))
test_factory(root[5][1].split_mnemonic(), None)




# new parents
new_parent_tests = {
    False: (root[6][0][0], root[6][0][1], root[6][0][1][0]),
    True: (root[6][1][0], root[6][1][1], root[6][1][1][0])
}

for exp_result, nodes in new_parent_tests.iteritems():
    for node in nodes:
        test_factory(node.has_new_parent(), exp_result)



if __name__ == '__main__':
    finish()
