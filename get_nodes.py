import re
from xml.dom import minidom

class mmnode(object):
    "generic mindmap node with no special syntax"

    def __init__(self, myxmlnode, parent=None):
        assert myxmlnode.hasAttribute('TEXT')
        assert myxmlnode.hasAttribute('ID')
        
        self.node_id = myxmlnode.getAttribute('ID')
        self.text = myxmlnode.getAttribute('TEXT')
        self.parent = parent

        self.children = [self.__class__(child, self) for child in myxmlnode.childNodes if child.nodeType == 1 and child.tagName == 'node']

    @classmethod
    def factory(cls, fname):
        xml = minidom.parse(fname)
        cnodes = [node for node in xml.childNodes[0].childNodes if node.nodeType == 1 and node.tagName == 'node']
        assert len(cnodes) == 1
        tree = cls(cnodes[0])
        return tree

    def downseek(self, depth=0):
        yield (self, depth)
        depth += 1
        for child in self.children:
            for part in child.downseek(depth):
                yield part

    def upseek(self, depth=0):
        yield (self, depth)
        depth += 1
        if self.parent is not None:
            for part in self.parent.upseek(depth):
                yield part

    def parent_arr(self):
        return (node for (node, depth) in self.upseek() if depth > 0)

    def depth(self):
        return len(list(self.parent_arr()))

    def ultimate_parent(self):
        if not self.parent:
            return self
        else:
            return list(self.parent_arr())[-1]

    def skip_as_parent(self):
        " include this node for recall with its immediate children? "
        return False

    def skip_as_child(self):
        " include this node as a child of another node? "
        return False

    def skip_traversal(self):
        " traverse this node at all? "
        return False

    def is_leaf(self):
        return not bool(self.children)

    def num_children(self):
        return len(self.children)

    def get_immediate_siblings(self):
        if not self.parent: raise IndexError
        prev_one = None
        found_me = False
        for c in self.parent.children:
            if c == self:
                found_me = True

            elif not c.skip_as_child():
                if found_me:
                    # if self is 1st node, prev_one will already be None
                    return (prev_one, c)
                else:
                    prev_one = c
        
        # self is last node or has no sibling nodes
        return (prev_one, None)


    def has_any_siblings(self):
        if not self.parent: raise IndexError
        return bool([x for x in self.parent.children if not x.skip_as_child() and x is not self])


    def __repr__(self):
        return '<%s #%s \'%s\' at 0x%s>' % (self.__class__.__name__, self.node_id, self.text, hex(id(self)))
        
    def __unicode__(self):
        assert isinstance(self.text, unicode)
        return self.text

    def __getitem__(self, ix):
        return self.children[ix]

    def __len__(self):
        return len(self.children)

    def __nonzero__(self):
        return True

    def print_tree(self):
        for (node, lvl) in self.downseek():
            print (' ' * lvl) + repr(node)
    




class mmnode_plus(mmnode):
    "mmnode node plus my special node syntax"

    def __init__(self, myxmlnode, parent=None):
        mmnode.__init__(self, myxmlnode, parent)

        self.ignore = False
        self.ignore_children = False
        self.ignore_all = False
        self.mnemonic = False

        for key, val in self.parse_node_text(self.text).iteritems():
            self.__dict__[key] = val


    def split_mnemonic(self):
        m = re.compile(r'(.*)\(m:\s*([^\)]+)\)').match(self.text)
        if m:
            return map(lambda s: s.strip(), m.groups())

    def has_new_parent(self):
        return any('(new)' in node.text for node, depth in self.upseek() if node != self)

    def is_leaf(self):
        return not self.children or self.ignore_all or self.ignore_children or not any(not c.skip_as_child() for c in self.children)

    def skip_as_parent(self):
        return (self.ignore_all or self.ignore or self.ignore_children) or not self.children or self.skip_traversal()

    def skip_as_child(self):
        return self.ignore or self.ignore_all or not self.parent or any(c.ignore_all for c, _ in self.upseek() if c is not self)
        # note special case: if the root node, this should return True

    def skip_traversal(self):
        return (self.ignore_all) or any(c.ignore_all or c.ignore_children for c, _ in self.upseek() if c is not self)

    @staticmethod
    def parse_node_text(text):
        """
        parse the node text to set some flags.

        static so that it can be tested easily.

        this could/should be replaced with some sort of parser so that i can use actual grammar
        """

        # http://stackoverflow.com/questions/555344/match-series-of-non-nested-balanced-parentheses-at-end-of-string

        finder = lambda input: set( s.rstrip(" \t)") for s in input.split("(") if s )

        d = {}

        found = finder(text)

        if 'i' in found:
            d['ignore'] = True

        if 'ic' in found:
            d['ignore_children'] = True

        if 'ia' in found:
            d['ignore_all'] = True

        d['found'] = found

        return d

# cases for skipping:
# ignore on self, but do recurse down to children; don't include as a direct parent or a child (i)
# ignore parent if all children are set to ignore ([implicit])
# don't include self or any descendent (ia)
# include self for its direct parent, but don't include any descendent (ic)
