from util import *
from unittest import TestCase


class TestPoW(TestCase):
    def test_pow(self):
        nonce = 0

        challenge = do_pow(nonce)
        verify = verify_pow(nonce, challenge)

        assert challenge == 66885
        assert verify


if __name__ == '__main__':
    main()
