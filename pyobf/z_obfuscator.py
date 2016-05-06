from __future__ import print_function

import pyobf._zobfuscator as _zobf
from pyobf.circuit import parse
from pyobf.obfuscator import Obfuscator

import networkx as nx
import os, time

class Circuit(object):
    def __init__(self, fname, verbose=False):
        self._verbose = verbose
        self.info = None
        self.ys = []
        self.y_deg = 0
        self.x_degs = None
        self.circuit = None
        self.n_xins = 0
        self.n_yins = 0
        self.ngates = 0
        self._parse(fname)

    def _inp_gate(self, g, num, inp):
        assert(inp.startswith('x') or inp.startswith('y'))
        if inp.startswith('x'):
            self.n_xins += 1
            g[0].add_node(num, label=[inp])
        elif inp.startswith('y'):
            self.n_yins += 1
            inp, value = inp.split(None, 1)
            self.ys.append(long(value))
            g[0].add_node(num, label=[inp], value=long(value))

    def _gate(self, g, num, lineno, gate, inputs):
        g = g[0]
        def _add_gate(num, x, y):
            g.add_node(num, gate='ADD', label=[])
            g.add_edge(x, num)
            g.add_edge(y, num)
        def _sub_gate(num, x, y):
            g.add_node(num, gate='SUB', label=[])
            g.add_edge(x, num)
            g.add_edge(y, num)
        def _mul_gate(num, x, y):
            g.add_node(num, gate='MUL', label=[])
            g.add_edge(x, num)
            g.add_edge(y, num)
        gates = {
            'ADD': _add_gate,
            'SUB': _sub_gate,
            'MUL': _mul_gate,
        }
        gates[gate](num, *inputs)
        self.ngates += 1
        return [g]

    def _compute_degs(self, circ, n_xins, n_yins):
        for k, v in circ.pred.iteritems():
            assert(0 <= len(v.keys()) <= 2)
            if len(v.keys()) == 1:
                p = v.keys()[0]
                circ.node[k]['label'].extend(circ.node[p]['label'])
                circ.node[k]['label'].extend(circ.node[p]['label'])
            else:
                for p in v.iterkeys():
                    circ.node[k]['label'].extend(circ.node[p]['label'])
        x_degs = [circ.node[circ.nodes()[-1]]['label'].count('x%d' % i)
                  for i in xrange(n_xins)]
        y_degs = [circ.node[circ.nodes()[-1]]['label'].count('y%d' % i)
                  for i in xrange(n_yins)]
        return x_degs, sum(y_degs)

    def _parse(self, fname):
        g = nx.digraph.DiGraph()
        self.circuit, self.info = parse(fname, [g], self._inp_gate, self._gate,
                                        keyed=True)
        self.x_degs, self.y_deg = self._compute_degs(self.circuit, self.n_xins,
                                                     self.n_yins)

    def evaluate(self, x):
        # XXX: this is a massive hack
        x = x[::-1]
        assert self.circuit
        g = self.circuit.copy()
        for node in nx.topological_sort(g):
            if 'gate' not in g.node[node]:
                if g.node[node]['label'][0].startswith('x'):
                    g.add_node(node, value=int(x[node]))
                else:
                    g.add_node(node, value=int(g.node[node]['value']))
            elif g.node[node]['gate'] in ('ADD', 'MUL', 'SUB'):
                keys = g.pred[node].keys()
                if len(keys) == 1:
                    idx1 = idx2 = keys[0]
                else:
                    assert(len(keys) == 2)
                    idx1 = g.pred[node].keys()[0]
                    idx2 = g.pred[node].keys()[1]
                if g.node[node]['gate'] == 'ADD':
                    value = g.node[idx1]['value'] + g.node[idx2]['value']
                elif g.node[node]['gate'] == 'SUB':
                    value = g.node[idx1]['value'] - g.node[idx2]['value']
                elif g.node[node]['gate'] == 'MUL':
                    value = g.node[idx1]['value'] * g.node[idx2]['value']
                g.add_node(node, value=value)
            else:
                raise Exception('Unable to evaluate')
        idx = nx.topological_sort(g)[-1]
        return g.node[idx]['value'] != 0


ZOBFUSCATOR_FLAG_NONE = 0x00
ZOBFUSCATOR_FLAG_VERBOSE = 0x01

class ZObfuscator(Obfuscator):
    def __init__(self, mlm, verbose=False, nthreads=None, ncores=None):
        assert mlm == 'CLT'
        super(ZObfuscator, self).__init__(_zobf, mlm, verbose=verbose,
                                          nthreads=nthreads, ncores=ncores)

    def _init_mmap(self, secparam, kappa, nzs, pows, directory):
        self.logger('Initializing mmap...')
        start = time.time()
        if not os.path.exists(directory):
            os.mkdir(directory)
        flags = ZOBFUSCATOR_FLAG_NONE
        if self._verbose:
            flags |= ZOBFUSCATOR_FLAG_VERBOSE
        self._state = _zobf.init(secparam, kappa, nzs, pows, directory,
                                 self._nthreads, self._nthreads, flags)
        end = time.time()
        self.logger('Took: %f' % (end - start))

    def _obfuscate(self, circname, circ):
        self.logger('Encoding circuit...')
        self.logger('  n = %s, m = %s' % (circ.n_xins, circ.n_yins))
        start = time.time()
        _zobf.encode_circuit(self._state, circname, circ.ys, circ.x_degs,
                             circ.y_deg, circ.n_xins, circ.n_yins)
        end = time.time()
        self.logger('Took: %f' % (end - start))

    def obfuscate(self, circname, secparam, directory, obliviate=False,
                  nslots=None, kappa=None, **kwargs):
        self.logger("Obfuscating '%s'" % circname)
        start = time.time()

        self._remove_old(directory)

        circ = Circuit(circname)
        self.logger('  number of gates = %s' % circ.ngates)
        self.logger('  deg(xs) = %s' % circ.x_degs)
        self.logger('  deg(y) = %s' % circ.y_deg)
        nzs = 4 * circ.n_xins + 1
        pows = []
        for pow in circ.x_degs:
            pows.extend([pow, pow])
        pows.extend([1 for _ in xrange(2 * circ.n_xins)])
        pows.append(circ.y_deg)
        assert(len(pows) == nzs)

        if not kappa:
            kappa = circ.y_deg + 2 * sum(circ.x_degs) + 2 * circ.n_xins

        self._init_mmap(secparam, kappa, nzs, pows, directory)
        self._obfuscate(circname, circ)
        end = time.time()
        self.logger('Obfuscation took: %f' % (end - start))
        if self._verbose:
            _zobf.max_mem_usage()

    def evaluate(self, directory, inp):
        def f(directory, inp, length, mlm, nthreads, flags):
            inp = inp[::-1]
            circname = os.path.join(directory, 'circuit')
            # Count number of y values
            m = 0
            with open(circname) as f:
                for line in f:
                    if 'y' in line:
                        m += 1
            return _zobf.evaluate(directory, circname, inp, len(inp), m,
                                  nthreads, flags)
        flags = ZOBFUSCATOR_FLAG_NONE
        if self._verbose:
            flags |= ZOBFUSCATOR_FLAG_VERBOSE
        return self._evaluate(directory, inp, f, _zobf, flags)