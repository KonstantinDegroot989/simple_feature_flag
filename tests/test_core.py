import unittest

from simple_feature_flag import EvaluationError, Flag, FlagSet


class FlagValidationTests(unittest.TestCase):
    def test_rejects_empty_name(self):
        with self.assertRaises(EvaluationError):
            Flag(name="")

    def test_rejects_out_of_range_percentage(self):
        with self.assertRaises(EvaluationError):
            Flag(name="x", percentage=-0.1)
        with self.assertRaises(EvaluationError):
            Flag(name="x", percentage=100.1)

    def test_accepts_boundary_percentages(self):
        self.assertEqual(Flag(name="x", percentage=0.0).percentage, 0.0)
        self.assertEqual(Flag(name="x", percentage=100.0).percentage, 100.0)

    def test_rejects_non_bool_override_value(self):
        with self.assertRaises(EvaluationError):
            Flag(name="x", overrides={"a": 1})


class BucketTests(unittest.TestCase):
    def test_bucket_is_deterministic(self):
        flag = Flag(name="checkout")
        self.assertEqual(flag.bucket("alice"), flag.bucket("alice"))

    def test_bucket_differs_by_flag_name(self):
        # The flag name is part of the hash input, so two flags with the same
        # roll-out do not bucket subjects identically.
        a = Flag(name="one")
        b = Flag(name="two")
        self.assertNotEqual(a.bucket("alice"), b.bucket("alice"))

    def test_bucket_in_range(self):
        flag = Flag(name="checkout")
        for subject in ("alice", "bob", "carol", "", "\u00e9"):
            value = flag.bucket(subject)
            self.assertGreaterEqual(value, 0.0)
            self.assertLess(value, 100.0)


class EvaluateTests(unittest.TestCase):
    def test_zero_percentage_is_off(self):
        flag = Flag(name="x", percentage=0.0)
        for subject in ("a", "b", "c", "d", "e"):
            self.assertFalse(flag.evaluate(subject))

    def test_full_percentage_is_on(self):
        flag = Flag(name="x", percentage=100.0)
        for subject in ("a", "b", "c", "d", "e"):
            self.assertTrue(flag.evaluate(subject))

    def test_override_wins_over_percentage(self):
        flag = Flag(
            name="x",
            percentage=0.0,
            overrides={"alice": True, "bob": False},
        )
        self.assertTrue(flag.evaluate("alice"))
        self.assertFalse(flag.evaluate("bob"))

    def test_override_false_on_full_rollout(self):
        flag = Flag(name="x", percentage=100.0, overrides={"alice": False})
        self.assertFalse(flag.evaluate("alice"))
        self.assertTrue(flag.evaluate("bob"))

    def test_default_applies_when_not_bucketed(self):
        # A 0% rollout with default True means everyone gets the default unless
        # an override says otherwise.
        flag = Flag(name="x", percentage=0.0, default=True)
        self.assertTrue(flag.evaluate("alice"))


class FlagSetTests(unittest.TestCase):
    def test_evaluate_known_flag(self):
        flags = FlagSet([Flag(name="a", percentage=100.0)])
        self.assertTrue(flags.evaluate("a", "alice"))

    def test_unknown_flag_raises(self):
        flags = FlagSet()
        with self.assertRaises(EvaluationError):
            flags.evaluate("missing", "alice")

    def test_add_replaces_existing(self):
        flags = FlagSet([Flag(name="a", percentage=0.0)])
        flags.add(Flag(name="a", percentage=100.0))
        self.assertTrue(flags.evaluate("a", "alice"))
        self.assertEqual(len(flags), 1)

    def test_contains(self):
        flags = FlagSet([Flag(name="a")])
        self.assertIn("a", flags)
        self.assertNotIn("b", flags)


if __name__ == "__main__":
    unittest.main()
