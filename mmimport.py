#!/usr/bin/env python

import os
import os.path
import re
import shutil
from datetime import datetime
import operator
import itertools
import logging

import pprint

import anki
from anki.utils import canonifyTags

import get_nodes

__version__ = 0.1

def concat(*args):
    if len(args) == 1 and hasattr(args[0], 'next'): # is there a better test for a generator?
        args = list(args[0])

    if not args:
        return ''
    else:
        assert all(isinstance(s, basestring) for s in args), args
        return reduce(operator.concat, args)


class object_capturer(object):
    """
    the point of this object is to provide pseudo-dynamic multiple inheritance.

    subclasses of this object's names will resolve to the parent first
    """

    expected_capture = None

    def __init__(self, obj):
        if self.expected_capture and obj.__class__ != self.expected_capture: raise TypeError
        self.__dict__['captured_object'] = obj

        if hasattr(self, '_postinit'):
            assert callable(self._postinit)
            self._postinit()

    def __getattribute__(self, name):
        try:
            return object.__getattribute__(self, name)
        except AttributeError:
            return object.__getattribute__(self, 'captured_object').__getattribute__(name)

    def __setattr__(self, name, val):
        # this is actually how hasattr() works, but that func might call the __getattribute__ override which will also resolve names for the captured object
        try:
            object.__getattribute__(self, name)
        except AttributeError:
            object.__getattribute__(self, 'captured_object').__setattr__(name, val)
        else:
            object.__setattr__(self, name, val)
            


class object_capturer_subs(object_capturer):
    "subscribable object capturer"

    def __getitem__(self, k):
        return self.captured_object[k]

    def __setitem__(self, k, v):
        self.captured_object[k] = v


class view(object_capturer):
    is_active = True
    expected_capture = get_nodes.mmnode_plus
    default_tags = ()


    def _postinit(self):
        self.mapname = self.ultimate_parent().text


    @classmethod
    def cast_node(cls, anode):
        builders = []
        for child in cls.__subclasses__():
            if child.is_active:
                new_frame_view = child(anode)
                if new_frame_view.use_this_fact():
                    builders.append(new_frame_view)

        return builders


    @classmethod
    def get_subclass_by_name(cls, name):
        for child in cls.__subclasses__():
            if child.__name__ == name:
                return child

        raise KeyError, "fact type '%s' not found" % name


    def node_identifier(self):
        assert self.mapname and isinstance(self.mapname, basestring)
        assert self.node_id
        assert all(':' not in x for x in (self.node_id, self.__class__.__name__, self.mapname))
        return ':'.join((self.mapname, self.node_id, self.__class__.__name__))


    @staticmethod
    def taggify_mapname(mapname):
        return re.compile(r'[^a-z0-9]+', re.I).sub('_', mapname.replace("'", '')).strip('_').lower()

    def get_tags(self):
        assert self.mapname and isinstance(self.mapname, basestring)
        auto_tags = (self.__class__.__name__, self.taggify_mapname(self.mapname))
        return ' '.join(map(unicode, sorted(itertools.chain(self.default_tags, auto_tags))))


    def update_fact_with_node(self, somefact, mydeck=None):

        # update fact fields
        for k, v in self.node_into_fields().iteritems():
            try:
                # db access layer complains about this
                if isinstance(v, str):
                    v = unicode(v)

                somefact[k] = v

            except KeyError:
                logging.critical("anki is complaining that %s does not exist" % k)
                raise

        # update tags
        somefact.tags = canonifyTags(self.get_tags())
        somefact.setModified(textChanged=True)

        # update the deck. needed if updating cards
        if mydeck is not None: # should be OK if we're using this function to add a new fact
            mydeck.updateFactTags([somefact.id])
            for card in somefact.cards:
                mydeck.updatePriority(card)

            self.update_num_fact_cards(somefact, mydeck)


    def update_num_fact_cards(self, somefact, mydeck):
        """
        when a new fact is created or updated, make sure it has the right number of cards regardless of the defaults in the fact model
        """

        expected_cards = set(self.expected_cards())

        assert len(expected_cards) >= 1

        changes = 0

        for missing_card in expected_cards ^ set(c.cardModel.name for c in somefact.cards):
            # add a missing card
            if missing_card in expected_cards:
                logging.info('card missing, adding...')
                mydeck.addCards(somefact, [cm.id for cm in somefact.model.cardModels if cm.name == missing_card])

            # delete an extra card
            else:
                logging.info('card extra, removing...')
                mydeck.deleteCards([c.id for c in somefact.cards if c.cardModel.name == missing_card])

            changes += 1

        assert len(somefact.cards) > 0
        assert len(somefact.cards) == len(expected_cards)

        return changes




    def should_use_reverse(self):
        # to be overridden by child classes
        return True

    def expected_cards(self):
        return ('F2B',) + (self.should_use_reverse() and ('B2F',) or ())

    @staticmethod
    def hash_list(somelist):
        assert all(isinstance(s, basestring) for s in somelist)
        return '+'.join(sorted(map(lambda s: s.lower(), somelist)))

    @classmethod
    def hash_tags(cls, sometags):
        assert isinstance(sometags, basestring)
        return cls.hash_list(sometags.split())

    @classmethod
    def hash_this_fact (cls, somefact):
        "hash a fact object as if it were generated by this view"

        essential_hash = 'Front=%(Front)s&Back=%(Back)s' % dict(map(cls._normalize_hash, dict(somefact).iteritems()))
        changed_hash = '&'.join("%s=%s" % (field.name,somefact[field.name]) for field in sorted(somefact.model.fieldModels, key=operator.attrgetter('name')) if field.name != 'id') \
            + '&tags=' + cls.hash_tags(somefact.tags) \
            + '&cards=' + cls.hash_list([c.cardModel.name for c in somefact.cards])

        return (somefact['id'], changed_hash, essential_hash)


    def hash_this_node (self):
        "hash this view object"
        field_dict = self.node_into_fields()

        essential_hash = 'Front=%(Front)s&Back=%(Back)s' % dict(map(self._normalize_hash, field_dict.iteritems()))
        changed_hash = '&'.join(concat(k, '=', v) for k, v in sorted(field_dict.iteritems(), key=operator.itemgetter(0))) \
            + '&tags=' + self.hash_tags(self.get_tags()) \
            + '&cards=' + self.hash_list(self.expected_cards())

        return (self.node_identifier(), changed_hash, essential_hash)


    def new_fact_from_node(self, themodel):
        newfact = anki.facts.Fact(model=themodel)
        newfact['id'] = unicode(self.node_identifier())
        self.update_fact_with_node(newfact)
        return newfact


    @staticmethod
    def _normalize_hash(field_member):
        "kludge: strip out the parts we don't want to bother hashing"
        # intended can be overridden by child classes if there is some special way that they need to be normalized

        field_name, field_value = field_member

        field_value = re.compile(re.escape('<span style="color: #226;">&lt;') + r'\d+' + re.escape('&gt;</span>')).sub('', field_value) # strip child counts
        field_value = re.compile(r'(?:\s*<[^>]+>\s*)+').sub('@@@', field_value).strip('@') # strip html, but leave as a @@@ as a separator in its place
        field_value = re.compile(r'\s*\((?:new|i[ca]?)\)\s*').sub('', field_value)
        field_value = re.compile(r'\s+').sub(' ', field_value).strip() # normalize whitespace
        
        return field_name, field_value




# could add these to the view... but they then would need to be added to all child nodes as well.
def render_node_li(somenode):
    return concat(
        u"<li>",
        somenode.text,
        u' <span style="color: #226;">&lt;%s&gt;</span>' % len(somenode.children) if len(somenode.children) else u'',
        u'</li>')



def render_node_breadcrumbs(somenode):
    return unicode(
                concat(
                    '<div align="left"><span style="color: gray">[</span><b>$</b>',
                    ' <b>&gt;</b> '.join('<span style="color: #222;">' + parent.text + '</span>' for parent in list(somenode.parent_arr())[::-1]),
                    '<span style="color: gray">]</span>'
                )
            )


def format_instruction(instruction):
    return concat(u'<span style="color: #cce">', instruction, u'</span>')


class fact_wrapper(object_capturer_subs):
    expected_capture = anki.facts.Fact

    def _postinit(self):
        self.mapname, self.node_id, self.viewname = self['id'].split(':')

    def hashme(self):
        return view.get_subclass_by_name(self.viewname).hash_this_fact(self)



class basic_view(view):
    is_active = True
    default_tags = ('PriorityHigh',)

    def node_into_fields (self):
        return {
            'Breadcrumbs': render_node_breadcrumbs(self),
            'Front_instruction': format_instruction('ALL: Look into this room. What do you see?'),
            'Back_instruction': format_instruction('ALL: What room are you in?'),
            'Front': self.text,
            'Back': concat('<ul align="left">',
                concat(
                    render_node_li(c)
                    for c in self.children
                    if not c.skip_as_child()),
                '</ul>')
        }

    def use_this_fact(self):
        return not self.is_leaf() and not self.has_new_parent()

    def should_use_reverse(self):
        return False




class sibling_view(view):
    is_active = True
    default_tags = ('PriorityLow',)

    def use_this_fact(self):
        return \
            self.parent and \
            self.has_any_siblings() and \
            not self.has_new_parent() and \
            not re.compile(r'^[\(_]?m:').match(self.text) and \
            not self.skip_as_child() and \
            len([c for c in self.parent.children if not c.skip_as_child()]) > 4 and \
            0 < self.parent.children.index(self.captured_object) < len(self.parent.children) - 1 # doesn't account for the first or last nodes being mnemonic nodes

    def node_into_fields (self):
        # thoughts: we should have our own model in we can stick the location in another field, and therefore dont have to call normalize_hash anymore. we could stick all the formatting code into the card model. we can do this once we're comfortable having multiple models.
        siblings = self.get_immediate_siblings()
        assert any(siblings), siblings
        return {
            'Breadcrumbs': render_node_breadcrumbs(self),
            'Front_instruction': format_instruction('SIBLINGS: what are the siblings of this node?'),
            'Back_instruction': format_instruction('SIBLINGS: of what node are these the siblings?'),
            'Front': self.text,
            'Back': concat(
                u'<ul align="left">',
                render_node_li(siblings[0]) if siblings[0] else '',
                '<li>...</li>',
                render_node_li(siblings[1]) if siblings[1] else '',
                u"</ul>"
            )
        }


class meaning_view(view):
    is_active = True

    def use_this_fact(self):
        assert hasattr(self, 'split_mnemonic') and callable(self.split_mnemonic)
        return self.split_mnemonic() and all(self.split_mnemonic()) and not self.has_new_parent()

    def node_into_fields (self):
        parts = self.split_mnemonic()
        assert parts and len(parts) == 2 and all(parts), parts

        return {
            'Breadcrumbs': render_node_breadcrumbs(self),
            'Front_instruction': format_instruction('MNEMONIC: What is this the mnemonic for?'),
            'Back_instruction': format_instruction('MNEMONIC: What is the mnemonic for this?'),
            'Front': parts[1],
            'Back': parts[0],
        }



# more fact types:
# meanings to mnemonics (should have its own type of card, which will also require switching over to tags to identify which facts in the deck are our facts)
# frames to locations. visualize the overall location of this card




def backup_deck(deck_path):
    assert os.path.exists(deck_path)
    new_path = deck_path + '.bak'
    shutil.copyfile(deck_path, new_path)
    os.system('gzip -f "' + new_path + '"')
    new_path += '.gz'

    # copy to a dated version in /tmp
    for i in itertools.count():
        alt_new_path = '/tmp/%s-%s.%02i' % (os.path.basename(new_path), datetime.today().strftime('%Y-%m-%d'), i)
        if not os.path.exists(alt_new_path):
            shutil.copyfile(new_path, alt_new_path)
            break
    
    return new_path





def get_model(deck, bail_if_not_found=False):

    f2b_template = (u'%(Breadcrumbs)s<br /><br />%(Front_instruction)s<br /><br />%(Front)s', u'%(Back)s')
    b2f_template = (u'%(Breadcrumbs)s<br /><br />%(Back_instruction)s<br /><br />%(Back)s', u'%(Front)s')
    initial_spacing = 30 * 60.0


    #anki_node_model= deck.s.query(anki.models.Model).filter('name="mindmap node"')[0]
    models = [m for m in deck.models if m.name == 'mindmap node']

    if not models and bail_if_not_found:
        logging.critical("tried creating the model and then wasn't able to find it! ack!")
        raise Exception

    elif models:
        assert len(models) == 1

        our_model = models[0]

        # make sure that the model contains everything we expect
        assert len(our_model.cardModels) == 2
        assert our_model.cardModels[0].name != our_model.cardModels[1].name
        assert set(cm.name for cm in our_model.cardModels) == set((u'B2F', u'F2B'))
        was_updated = False

        try:
            assert [(cm.qformat, cm.aformat) for cm in our_model.cardModels if cm.name == u'F2B'][0] == f2b_template
            assert [(cm.qformat, cm.aformat) for cm in our_model.cardModels if cm.name == u'B2F'][0] == b2f_template

            assert our_model.initialSpacing == initial_spacing, our_model.initialSpacing

        # update the model if there are differences
        except AssertionError:
            logging.warning("model apparently out-of-date, attempting to upgrade")
            f2b = [cm for cm in our_model.cardModels if cm.name == u'F2B'][0]
            b2f = [cm for cm in our_model.cardModels if cm.name == u'B2F'][0]
            f2b.qformat = f2b_template[0]
            f2b.aformat = f2b_template[1]
            b2f.qformat = b2f_template[0]
            b2f.aformat = b2f_template[1]

            setattr(our_model, 'initialSpacing', initial_spacing) # for some reason we have to do this rather than setting attributes directly
            
            our_model.setModified()
            was_updated = True

        return (our_model, was_updated)


    # didn't find the model, so create it
    else:
        # may eventually want to have different models for every frame
        logging.warning("missing mindmap node model. adding")

        # based on: http://ichi2.net/anki/wiki/Plugins?action=AttachFile&do=view&target=iknowimport.py
        # above code also shows how to do it from the GUI rather than the command line, which I might want to do at some point


        # how to do upgrades on models: 
        # detect which version of the model we're working with
        # create a new copy of the model under a different name
        # convert all cards from the old model to the new modek
        # drop the old mode
        # rename the new model to the correct name

        newmodel = anki.models.Model(u'mindmap node')
        newmodel.addFieldModel(anki.models.FieldModel(u'Front', False, False))
        newmodel.addFieldModel(anki.models.FieldModel(u'Back', False, False))
        newmodel.addFieldModel(anki.models.FieldModel(u'Breadcrumbs', False, False))
        newmodel.addFieldModel(anki.models.FieldModel(u'Front_instruction', False, False))
        newmodel.addFieldModel(anki.models.FieldModel(u'Back_instruction', False, False))
        newmodel.addFieldModel(anki.models.FieldModel(u'id', True, True))

        newmodel.addCardModel(anki.models.CardModel(u'F2B', f2b_template[0], f2b_template[1]))
        newmodel.addCardModel(anki.models.CardModel(u'B2F', b2f_template[0], b2f_template[1]))

        newmodel.initialSpacing = initial_spacing

        # to disable or enable a card model for a given fact:
        # every fact has a .cards list of cards. can i just delete said object?

        deck.addModel(newmodel)

        return get_model(deck, True)





def main(from_mindmap, to_deck, depthlimit = None, delete_nonmindmap=False):
    assert os.path.exists(from_mindmap)
    assert os.path.exists(to_deck)
    assert (isinstance(depthlimit, int) and depthlimit > 0) or depthlimit is None
    assert isinstance(delete_nonmindmap, bool)

    # might want to only back up if there were any changes...
    backup_fname = backup_deck(to_deck)

    mydeck = anki.DeckStorage.Deck(to_deck)

    try:
        found_facts = set()
        frame_dict = {}

        changes = {
            'updates': 0,
            'resets': 0,
            'adds': 0,
            'deletes': 0,
            'any': 0}

        (anki_node_model, was_updated) = get_model(mydeck)

        changes['model'] = int(was_updated)

        deckfacts = mydeck.s.query(anki.facts.Fact)

        total_leaf_nodes = 0
        total_branch_nodes = 0
        total_views = 0

        mm_nodes = get_nodes.mmnode_plus.factory(from_mindmap)

        map_title = mm_nodes.text
        assert map_title.strip()
        logging.info("map title is '%s'" % map_title)

        if not len(mm_nodes):
            logging.error("this map is empty. no views will be added. exiting...")
            raise SystemExit

        # make a list of every node
        for (frame, lvl) in mm_nodes.downseek():
            if (depthlimit is None or lvl < depthlimit) and not frame.skip_traversal():
                frame_views = view.cast_node(frame)
                for view_of_frame in frame_views:
                    (frame_id, changed_hash, essential_hash) = view_of_frame.hash_this_node()
                    frame_dict[frame_id] = {'view': view_of_frame, 'changed_hash': changed_hash, 'essential_hash': essential_hash}
                    total_views += 2 # should conditionally change to one when we support one-sided views

                if len(frame):
                    total_branch_nodes += 1
                else:
                    total_leaf_nodes += 1 


        for fact in deckfacts:
            if fact.model == anki_node_model:
                fact = fact_wrapper(fact)
                (fact_id, changed_hash, essential_hash) = fact.hashme()

                # must be from this deck
                if fact.mapname == map_title:

                    # if we don't recognize this fact anymore, delete it
                    if fact_id not in frame_dict:
                        logging.debug("deleting deck fact %(id)s %(Front)s" % fact)
                        mydeck.deleteFact(fact.id)
                        changes['deletes'] += 1

                    # if the card has changed, update it
                    elif frame_dict[fact_id]['changed_hash'] != changed_hash:

                        logging.debug("updating card %(id)s %(Front)s" % fact)
                        #print repr(frame_dict[fact_id]['changed_hash'])
                        #print repr(changed_hash)

                        frame_dict[fact_id]['view'].update_fact_with_node(fact, mydeck)

                        # if an essential part of the card has changed (i.e. not formatting), then reset the progress
                        if frame_dict[fact_id]['essential_hash'] != essential_hash:
                            logging.debug("resetting card %(id)s %(Front)s" % fact)
                            mydeck.resetCards([c.id for c in fact.cards])
                            changes['resets'] += 1

                        changes['updates'] += 1

                    found_facts.add(fact_id)

                else:
                    logging.debug('ignoring a fact from a different mind map (%s)' % fact.mapname)
                    # may want to have an option to delete


            else:
                # may want to delete it
                if delete_nonmindmap:
                    logging.debug("deleting non-mindmap fact")
                    mydeck.deleteFact(fact.id)
                    changes['deletes'] += 1
                else:
                    logging.debug("skipping non-mindmap fact")


        if not found_facts:
            logging.warning("no frames from this map exist in this deck yet. will add them all")
            #raise Exception


        for (frame_id, frame_info) in frame_dict.iteritems():
            if frame_id not in found_facts:
                # create facts for nodes that don't already exist
                newfact = frame_info['view'].new_fact_from_node(anki_node_model)
                logging.debug("creating new card %(id)s %(Front)s" % newfact)
                mydeck.addFact(newfact) # should return a list of new card objects
                frame_info['view'].update_num_fact_cards(newfact, mydeck)
                changes['adds'] += 1



        changes['any'] = sum(changes.itervalues()) - changes['resets'] # resets are semi-redundant with updates

        logging.info("backup made to " + backup_fname)
        logging.info("made %(any)s changes, including %(updates)s updates, %(resets)s resets, %(adds)s adds and %(deletes)s deletes. model_changed=%(model)s" % changes)
        logging.info("tracking %s end frames on %s branch frames, with %s total views of these frames" % (total_leaf_nodes, total_branch_nodes, total_views))

        if changes['any'] or changes['resets']:
            mydeck.s.flush()
            mydeck.flushMod()
            mydeck.setModified()
            mydeck.save()
            logging.debug("saving updated deck")

    except:
        logging.critical("error! exiting prematurely.")
        logging.critical("backup made to " + backup_fname + '!')
        raise

    finally:
        mydeck.close()




if __name__ == '__main__':

    import sys
    import optparse

    def get_options():
        parser = optparse.OptionParser(usage='usage: %prog [input mind map].mm [output anki deck].anki [options]', version='%prog ' + str(__version__))

        parser.add_option('-d', '--depth-limit', dest='depthlimit', default=None, type='int')
        parser.add_option('-i', '--input-map', dest='mapfile')
        parser.add_option('-o', '--output-deck', dest='deckfile')
        parser.add_option('-q', '--quiet', dest='verbosity', action='append_const', const=1, help="silence output")
        parser.add_option('-v', '--verbose', dest='verbosity', action='append_const', const=-1, help="increases output")
        parser.add_option('--delete-nonmindmap', dest='delete_nonmindmap', default=False, action='store_true', help="delete non-mindmap cards")

        (options, args) = parser.parse_args()

        if len(args) == 2:
            if options.mapfile is not None or options.deckfile is not None:
                parser.error('too many files specified')
            options.mapfile = args[0]
            options.deckfile = args[1]

        elif len(args) == 1:
            if options.deckfile is not None:
                options.mapfile = args[0]
            elif options.mapfile is not None:
                options.deckfile = args[0]
            else:
                parser.error('not enough files specified')

        elif len(args) == 0:
            if options.mapfile is None or options.deckfile is None:
                parser.error('not enough files specified')

        else:
            parser.error('wrong number of files specified')

        if not options.deckfile[-5:] == '.anki':
            parser.error('deckfile should have .anki extension')

        if not options.mapfile[-3:] == '.mm':
            parser.error('mapfile should have .mm extension')

        if not os.path.exists(options.mapfile):
            parser.error('mapfile does not exist')

        if not os.path.exists(options.deckfile):
            parser.error('deck file does not exist')

        return options

    options = get_options()

    # set the verbosity level:
    default_verbosity = 2
    logging_verbosity = max(min(sum(options.verbosity or (0,)), 5) + default_verbosity, 1) * 10 # bound to 1-5, and set the default to default_verbosity

    logging.basicConfig(level=logging_verbosity, format="%(asctime)s - %(levelname)s - %(message)s")

    logging.info("setting verbosity level to %s" % logging_verbosity)

    logging.debug("main(to_deck=%r, from_mindmap=%r, depthlimit=%r, delete_nonmindmap=%r)" % (options.deckfile, options.mapfile, options.depthlimit, options.delete_nonmindmap))
    result = main(to_deck=options.deckfile, from_mindmap=options.mapfile, depthlimit=options.depthlimit, delete_nonmindmap=options.delete_nonmindmap)



# REMAINING TODO:
# rather than '(new)'... maybe automatically only active some views when their parents have been answered correctly a couple of times
# some way to indicate that a set of nodes are not ordered, and therefore views which test your knowledge of the order should be skipped
# add _loc: node support
# _mr: support.... contains the relationship of the mnemonic to other nodes, which we might want to hide for certain views

# when i'm feeling bored... make "superdebug" debug level for logging for really mundane stuff
