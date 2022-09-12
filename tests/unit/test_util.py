from util import PoW
from unittest import TestCase


class TestPoW(TestCase):
    def test_pow(self):
        nonce = 0

        challenge = PoW.do_pow(nonce)
        verify = PoW.verify_pow(nonce, challenge)

        assert challenge == 6049217
        assert verify


if __name__ == '__main__':
    main()
