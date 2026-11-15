"""Offline deterministic tests of initial SCPI response alignment."""
import contextlib
import io
import socket
import unittest
from unittest.mock import patch
import cpx400dp_run_enhanced as r

class FakeSocket:
    def __init__(self, stale_first=None, unstable=False):
        self.buffer=b''
        self.sent=[]
        self.stale_first=stale_first
        self.unstable=unstable
        self.snapshot_no=0
    def sendall(self,data):
        cmd=data.decode('ascii').strip()
        self.sent.append(cmd)
        if cmd=='V1?' and self.stale_first is not None:
            self.buffer+= (self.stale_first+'\n').encode()
            self.stale_first=None
        if cmd=='V1?':
            self.snapshot_no+=1
            answer='V1 2.30' if self.unstable and self.snapshot_no>=2 else 'V1 2.27'
        else:
            answer={'I1?':'I1 1.50','OP1?':'1','V2?':'V2 26.83',
                    'I2?':'I2 1.28','OP2?':'1'}[cmd]
        self.buffer+=(answer+'\n').encode()
    def recv(self,n):
        buf,self.buffer=self.buffer[:n],self.buffer[n:]
        if not buf: raise socket.timeout('empty response')
        return buf

class SnapshotTests(unittest.TestCase):
    def test_stale_op_reply_before_tagged_voltage(self):
        sock=FakeSocket(stale_first='1')
        with contextlib.redirect_stdout(io.StringIO()) as o:
            state,pending=r.verify_initial_snapshot(sock,[1,2],b'')
        self.assertEqual(state[1],(2.27,1.5,1))
        self.assertEqual(state[2],(26.83,1.28,1))
        self.assertIn('[SNAPSHOT SYNC]',o.getvalue())
        self.assertFalse(pending)
        self.assertEqual(sock.sent, ['V1?','I1?','OP1?','V2?','I2?','OP2?']*2)
    def test_wrong_tagged_reply_does_not_get_misassigned(self):
        sock=FakeSocket(stale_first='I1 1.50')
        with contextlib.redirect_stdout(io.StringIO()):
            state,pending=r.verify_initial_snapshot(sock,[1],b'')
        self.assertEqual(state[1],(2.27,1.5,1))
    def test_disagreement_aborts(self):
        sock=FakeSocket(unstable=True)
        with self.assertRaisesRegex(ValueError,'inconsistent'):
            r.verify_initial_snapshot(sock,[1],b'')
        self.assertTrue(all(cmd.endswith('?') for cmd in sock.sent))
    def test_reject_extra_unexpected_without_unbounded_read(self):
        sock=FakeSocket(stale_first='junk')
        with contextlib.redirect_stdout(io.StringIO()):
            r.verify_initial_snapshot(sock,[1],b'')
        self.assertTrue(all(cmd.endswith('?') for cmd in sock.sent))

if __name__=='__main__': unittest.main()
