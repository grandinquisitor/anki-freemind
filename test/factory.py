import unittest


suite = unittest.TestSuite()

_testnum = 0
def test_factory(A, B, errmsg=None):
    """
    I want one test per assertion, rather than each case failing at the first assertion. this function lets me do that
    """

    global _testnum

    testname = 'dyntest' + str(_testnum)

    newcase = type(testname, (unittest.TestCase,),
        {'input': A, 'expected': B, 'errmsg': errmsg, 'runTest': lambda self: self.assertEqual(self.input, self.expected, self.errmsg)})

    suite.addTest(newcase())

    _testnum += 1


def finish():
    unittest.TextTestRunner(verbosity=1).run(suite)
    # could also use globals(), but need like unittest.main(module=__name__)
