#!/usr/bin/env python2

import random, sys
from math import log

def usage():
    print('Usage: point.py <bitlength>')
    sys.exit(1)

def random_bitstring(bitlength):
    r = random.randint(0, 2 ** bitlength - 1)
    bits = bin(r)[2:]
    return '0' * (bitlength - len(bits)) + bits

def binary_point(bitlength):
    with open('point-%d.circ' % bitlength, 'w') as f:
        secret = random_bitstring(bitlength)
        f.write('# TEST %s 0\n' % secret)
        for _ in xrange(5):
            test = random_bitstring(bitlength)
            if test != secret:
                f.write('# TEST %s 1\n' % test)
        for i in xrange(bitlength):
            f.write('%d input\n' % i)
        for i in xrange(bitlength):
            gate = 'ID' if secret[i] == '0' else 'NOT'
            f.write('%d gate %s %d\n' % (bitlength + i, gate, i))

        length = bitlength
        oldstart = bitlength
        start = oldstart + length
        leftover = None
        while length > 1:
            for i, j in zip(xrange(start, start + length / 2),
                            xrange(oldstart, start, 2)):
                if j + 1 == start:
                    if leftover:
                        f.write('%d gate OR %d %d\n' % (i, j, leftover))
                        leftover = None
                else:
                    f.write('%d gate OR %d %d\n' % (i, j, j + 1))
            if length % 2 == 1 and not leftover:
                leftover = start - 1
            oldstart = start
            start = start + length / 2
            length = (length + length % 2) / 2
        if leftover:
            f.write('%d gate OR %d %d\n' % (start + length / 2,
                                            start - 1,
                                            leftover))
            start = start + 1
        f.write('%d output ID %d\n' % (start, start - 1))

def main(argv):
    if len(argv) != 2:
        usage()
    try:
        bitlength = int(argv[1])
    except ValueError:
        usage()

    binary_point(bitlength)

if __name__ == '__main__':
    try:
        main(sys.argv)
    except KeyboardInterrupt:
        pass
