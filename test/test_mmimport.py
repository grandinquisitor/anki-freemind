#!/usr/bin/env python

from factory import test_factory, finish

import sys
sys.path.append('..')
import mmimport
import get_nodes



root = get_nodes.mmnode_plus.factory('testmap.mm')


hash_tests = (
    (root[2][0], root[2][1], True, ((2,0),(2,1))),
    (root[2][1], root[2][2], False, ((2,2),(2,1))),
    (root[2][2], root[2][0], False, ((2,0),(2,2))),
)

for node1, node2, exp_result, coords in hash_tests:
    view1 = mmimport.basic_view(node1)
    view2 = mmimport.basic_view(node2)
    id1, chash1, ehash1 = view1.hash_this_node()
    id2, chash2, ehash2 = view2.hash_this_node()

    test_factory(ehash1 == ehash2, exp_result, "expected %s for %r == %r" % (exp_result, ehash1, ehash2))
    test_factory(chash1 == chash2, False, "expected %s for %r == %r" % (False, chash1, chash2))


if __name__ == '__main__':
    finish()
