#!/usr/bin/env python

from factory import test_factory, finish

import sys
sys.path.append('..')
import mmimport
import get_nodes



root = get_nodes.mmnode_plus.factory('testmap.mm')


hash_tests = (
    (root[2][0], root[2][1], True),
    (root[2][1], root[2][2], False),
    (root[2][2], root[2][0], False),
    (root[6][0], root[6][1], True),
    (root[6][2], root[6][3], True),
    (root[6][2], root[6][4], True),
    (root[6][2], root[6][5], True),
    (root[6][2], root[6][6], True),
)

for node1, node2, exp_result in hash_tests:
    view1 = mmimport.basic_view(node1)
    view2 = mmimport.basic_view(node2)
    id1, chash1, ehash1 = view1.hash_this_node()
    id2, chash2, ehash2 = view2.hash_this_node()

    test_factory(ehash1 == ehash2, exp_result, "expected %s for %r == %r" % (exp_result, ehash1, ehash2))
    test_factory(chash1 == chash2, False, "expected %s for %r == %r" % (False, chash1, chash2))



sibling_tests = (
    (root[7][0][0], False),
    (root[7][0][1], False),
    (root[7][0][2], False),
    (root[7][0][3], True),
)


for node, exp_result in sibling_tests:
    v = mmimport.sibling_view(node)
    test_factory(v.use_this_fact(), exp_result)




mapname_tests = (
    ("map name", 'map_name'),
    ("map name ", 'map_name'),
    ("map's name", 'maps_name'),
    ("map name9", 'map_name9'),
    ("map name&", 'map_name'),
)

for name, tag_name in mapname_tests:
    test_factory(mmimport.view.taggify_mapname(name), tag_name)



hash_tests = (
    (root[6][0], root[6][1]),
    (root[6][2], root[6][3]),
)


for node1, node2 in hash_tests:
    test_factory(mmimport.view._normalize_hash(('x', node1.text)), mmimport.view._normalize_hash(('x', node2.text)))



if __name__ == '__main__':
    finish()

