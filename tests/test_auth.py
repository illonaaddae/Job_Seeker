"""Authentication is the only thing standing between the internet and an inbox."""

import time
import unittest

from jobseeker.server.auth import (
    LoginThrottle,
    SessionSigner,
    hash_password,
    token_matches,
    verify_password,
)


class TestPasswordHashing(unittest.TestCase):
    def test_the_plain_password_never_appears_in_the_hash(self):
        encoded = hash_password("correct horse battery staple")
        self.assertNotIn("correct", encoded)
        self.assertTrue(encoded.startswith("scrypt$"))

    def test_the_right_password_verifies(self):
        encoded = hash_password("a-good-password")
        self.assertTrue(verify_password("a-good-password", encoded))

    def test_a_wrong_password_is_rejected(self):
        encoded = hash_password("a-good-password")
        self.assertFalse(verify_password("a-good-passworE", encoded))
        self.assertFalse(verify_password("", encoded))

    def test_the_same_password_hashes_differently_each_time(self):
        # A per password salt means two identical passwords are not detectable
        # as identical from the stored hashes.
        self.assertNotEqual(hash_password("same"), hash_password("same"))

    def test_a_corrupt_hash_fails_closed(self):
        for broken in ("", "garbage", "scrypt$bad", "bcrypt$1$2$3$4$5"):
            with self.subTest(hash=broken):
                self.assertFalse(verify_password("anything", broken))


class TestSessions(unittest.TestCase):
    def setUp(self):
        self.signer = SessionSigner("a-signing-secret")

    def test_a_freshly_issued_token_verifies(self):
        self.assertIsNotNone(self.signer.verify(self.signer.issue()))

    def test_a_tampered_payload_is_rejected(self):
        token = self.signer.issue()
        body, _, signature = token.partition(".")
        forged = f"{body[:-2]}xx.{signature}"
        self.assertIsNone(self.signer.verify(forged))

    def test_a_token_from_another_secret_is_rejected(self):
        other = SessionSigner("a-different-secret")
        self.assertIsNone(self.signer.verify(other.issue()))

    def test_an_expired_token_is_rejected(self):
        self.assertIsNone(self.signer.verify(self.signer.issue(hours=0)))

    def test_rubbish_is_rejected_rather_than_raising(self):
        for value in ("", "no-dot", "a.b", "....", "x" * 500):
            with self.subTest(token=value):
                self.assertIsNone(self.signer.verify(value))


class TestThrottle(unittest.TestCase):
    def test_lockout_after_repeated_failures(self):
        throttle = LoginThrottle(max_attempts=3, window=60, lockout=60)
        self.assertEqual(throttle.locked_for("1.2.3.4"), 0)
        for _ in range(3):
            throttle.record_failure("1.2.3.4")
        self.assertGreater(throttle.locked_for("1.2.3.4"), 0)

    def test_a_success_clears_the_count(self):
        throttle = LoginThrottle(max_attempts=3)
        throttle.record_failure("1.2.3.4")
        throttle.record_success("1.2.3.4")
        self.assertEqual(throttle.locked_for("1.2.3.4"), 0)

    def test_clients_are_throttled_independently(self):
        throttle = LoginThrottle(max_attempts=2, lockout=60)
        throttle.record_failure("1.1.1.1")
        throttle.record_failure("1.1.1.1")
        self.assertGreater(throttle.locked_for("1.1.1.1"), 0)
        self.assertEqual(throttle.locked_for("2.2.2.2"), 0)

    def test_old_failures_fall_out_of_the_window(self):
        throttle = LoginThrottle(max_attempts=3, window=1, lockout=60)
        throttle.record_failure("1.2.3.4")
        throttle.record_failure("1.2.3.4")
        time.sleep(1.1)
        # The two stale failures are discarded, so this is treated as the first.
        self.assertEqual(throttle.record_failure("1.2.3.4"), 2)


class TestApiTokens(unittest.TestCase):
    def test_matching_and_mismatching_tokens(self):
        self.assertTrue(token_matches("abc123", "abc123"))
        self.assertFalse(token_matches("abc124", "abc123"))
        self.assertFalse(token_matches("", ""))
        self.assertFalse(token_matches("anything", ""))


if __name__ == "__main__":
    unittest.main()
