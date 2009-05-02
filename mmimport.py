#!/usr/bin/env python

import os.path

import anki

import get_nodes

__version__ = 0.1

# TODO: should not change if only the number of items in a child node changes
# TODO: should namespace out different decks so they can share the same file

def node_into_fields (anode):
    return (
        unicode(
            '<div align="left"><span style="color: gray">[</span><b>$</b>' +
            ' <b>&gt;</b> '.join('<span style="color: #222;">' + parent.text + '</span>' for parent in list(anode.parent_arr())[::-1]) +
            '<span style="color: gray">]</span><br /><br />' +
            anode.text +
            '</div>'
        ), 
        unicode('<ul align="left"><li>' + '</li><li>'.join(unicode(c) + (c.children and ' <span style="color: #226;">&lt;%s&gt;</span>' % len(c.children) or '') for c in anode.children if not c.skip_as_child()) + "</li></ul>")
    )

def hash_this_card (acard):
    flat_card = '&'.join("%s=%s" % (field.name,acard.fact[field.name]) for field in acard.fact.model.fieldModels if field.name != 'id')
    return (acard.fact['id'], flat_card)

def hash_this_node (anode):
    return (anode.node_id, 'Front=%s&Back=%s' % node_into_fields(anode))

def new_fact_from_node(anode, themodel):
    newfact = anki.facts.Fact(model=themodel)
    newfact['id'] = unicode(anode.node_id)
    (newfact['Front'], newfact['Back']) = node_into_fields(anode)
    print "creating new card %(id)s %(Front)s/%(Back)s" % newfact
    return newfact

def update_card_with_node(acard, anode):
    (acard.fact['Front'], acard.fact['Back']) = node_into_fields(anode)
    print "updating card %(id)s %(Front)s/%(Back)s" % acard.fact
    acard.fact.setModified(textChanged=True) # reset progress



def main(from_mindmap, to_deck, depthlimit = None):
    assert os.path.exists(from_mindmap)
    assert os.path.exists(to_deck)
    assert (isinstance(depthlimit, int) and depthlimit > 0) or depthlimit is None

    mydeck = anki.DeckStorage.Deck(to_deck)

    card_dict = {}
    node_dict = {}

    num_changes = 0

    try:
        anki_node_model= mydeck.s.query(anki.models.Model).filter('name="mindmap node"')[0]
        
        cards = mydeck.s.query(anki.cards.Card)

        total_leaf_nodes = 0
        total_branch_nodes = 0

        mm_nodes = get_nodes.mmnode_plus.factory(from_mindmap)

        for (node, lvl) in mm_nodes.downseek():
            if not node.is_leaf() \
                   and (depthlimit is None or lvl < depthlimit) \
                   and not node.skip_traversal():
                (node_id, flat) = hash_this_node(node)
                node_dict[node_id] = {'node': node, 'flat': flat}
                total_leaf_nodes += node.num_children()
                total_branch_nodes += 1



        for card in cards:
            if card.fact.model.name == 'mindmap node':
                (fact_id, flat) = hash_this_card(card)
                if fact_id not in node_dict:
                    #delete card
                    print "deleting card %(id)s %(Front)s/%(Back)s" % card.fact
                    mydeck.deleteCard(card.id)
                    num_changes += 1

                elif node_dict[fact_id]['flat'] != flat:
                    # update card, reset progress
                    update_card_with_node(card, node_dict[fact_id]['node'])
                    mydeck.resetCards([card.id])
                    num_changes += 1
                    
                card_dict[fact_id] = flat


        for (node_id, node_d) in node_dict.iteritems():
            if node_id not in card_dict:
                #create facts for nodes that don't already exist
                newfact = new_fact_from_node(node_d['node'], anki_node_model)
                mydeck.addFact(newfact) # creates cards automatically?
                num_changes += 1
        

        print "made", num_changes, "changes"
        print "tracking %s leaf nodes on %s branches" % (total_leaf_nodes, total_branch_nodes)

        if num_changes:
            mydeck.s.flush()
            mydeck.setModified()
            mydeck.save()
                
    finally:
        mydeck.close()




if __name__ == '__main__':

    import sys
    import optparse

    def get_options():
        parse = optparse.OptionParser(usage='usage: %prog [input mind map].mm [output anki deck].anki [options]', version='%prog ' + str(__version__))

        parse.add_option('-d', '--depth-limit', dest='depthlimit', default=None, type='int')
        parse.add_option('-i', '--input-map', dest='mapfile')
        parse.add_option('-o', '--output-deck', dest='deckfile')
        parse.add_option('-q', '--quiet', dest='verbose', default=False, help="silence output")

        (options, args) = parse.parse_args()

        try:
            if len(args) == 2:
                assert options.mapfile is None
                assert options.deckfile is None
                options.mapfile = args[0]
                options.deckfile = args[1]

            elif len(args) == 1:
                if options.deckfile is not None:
                    options.mapfile = args[0]
                elif options.mapfile is not None:
                    options.deckfile = args[0]
                else:
                    assert False

            elif len(args) == 0:
                assert options.mapfile is not None
                assert options.deckfile is not None

            else:
                assert False

            try:
                assert options.deckfile[-5:] == '.anki', 'deckfile should have .anki extension'
                assert options.mapfile[-3:] == '.mm', 'mapfile should have .mm extension'
                assert os.path.exists(options.mapfile), 'mapfile does not exist'
                assert os.path.exists(options.deckfile), 'deck file does not exist'
            except AssertionError, e:
                print 'ERROR:', e
                raise

        except AssertionError:
            parse.print_help()
            raise
            #sys.exit(1)

        return options

    options = get_options()

    #main(to_deck='/Users/nick/Documents/development.anki', from_mindmap='/Users/nick/Documents/lie to me.mm', depthlimit=3)
    main(to_deck=options.deckfile, from_mindmap=options.mapfile, depthlimit=options.depthlimit)
