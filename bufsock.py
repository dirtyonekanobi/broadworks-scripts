#!/usr/bin/env python

'''
socket or file wrapper provides buffered read and readto, among other methods.
Intended to deal intelligently with short reads.
Also provides a rawio wrapper for os.open.
'''

import os
import re
import sys
#mport platform

import python2x3

# read() brings in the remainder of the file
# read(length) brings in a specific number of bytes.
# readto(char) reads up thru the next occurence of char
# readtomax(char,length) reads up thru the next occurence of char, or length
#    bytes, whichever is less
# set_chunk_len(length) says "do reads in increments of length"
# send(buf) writes the bytes in buf.  It's currently unbuffered, but may
#    become buffered in the future
# flush() is currently a noop, but your programs should ignore that and
#    call it when you want an output buffer flushed
# shutdown(v) just like for a regular socket, except it flushes first

def o_binary():
    '''
    On platforms that have an os.O_BINARY, use it. This includes CPython on Windows, and probably should include
    Jython on *ix but doesn't (at least, not in Jython 2.5.2).
    '''
    if hasattr(os, 'O_BINARY'):
        return getattr(os, 'O_BINARY')
    else:
        return 0


class rawio(object):
    '''
    This class is a simple wrapper for os.open, os.read, os.write and os.close, that should in turn allow us to wrap
    these os.* routines with bufsock.  Alternatively, we should also be able to wrap a python file object with bufsock,
    but then you end up with two layers of buffering, each with slightly different functionality
    '''
    def __init__(self, filename=None, mode='r', perms=6 * 64 + 6 * 8 + 6, handle=None):
        assert (filename is not None) + (handle is not None) == 1
        if filename is not None:
            self.filename = filename
            if 'b' in mode:
                # we're always binary, so ignore 'b' in mode
                mode = re.sub('b', '', mode)
            if mode == 'r':
                self.mode = os.O_RDONLY | o_binary()
            elif mode == 'w':
                self.mode = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | o_binary()
            elif mode == 'rw':
                self.mode = os.O_RDWR | os.O_CREAT | o_binary()
            else:
                raise ValueError('Invalid mode: %s' % mode)
            self.perms = perms
            self.file_descriptor = os.open(filename, self.mode, perms)
        elif handle is not None:
            if isinstance(handle, int):
                self.filename = '/handle %d\\' % handle
            else:
                # Jython takes this code path
                self.filename = '/noninteger\\'
            self.file_descriptor = handle
        else:
            raise AssertionError('Neither filename nor handle provided')

    open = __init__

    def read(self, length=None):
        '''Read some bytes'''
        if length is None:
            list_ = []
            while True:
                block = os.read(self.file_descriptor, 2 ** 20)
                if not block:
                    break
                list_.append(block)
            return python2x3.empty_bytes.join(list_)
        else:
            return os.read(self.file_descriptor, length)

    def write(self, data):
        '''Write some bytes'''
        return os.write(self.file_descriptor, data)

    def close(self):
        '''Close our file-like object'''
        os.close(self.file_descriptor)

    def fileno(self):
        '''Return the numberic file descriptor corresponding to this rawio object'''
        return self.file_descriptor

#    def __enter__(self):
#        return self
#
#    def __exit__(self, type_, value, traceback_):
#        if value is None:
#            os.close(self.file_descriptor)
#            return True
#        else:
#            return False


class bufsock(object):
    # pylint: disable=R0902
    # R0902: We do appear to require quite a few instance attributes
    '''
    socket or file wrapper provides buffered read and readto, among other methods.
    Intended to deal intelligently with short reads.
    '''
    def __init__(self, filedes, disable_flush=False, chunk_len=4096, maintain_alignment=False):
        self.null_string = python2x3.empty_bytes
        self.filedes = filedes
        self.recvbuf = self.null_string[:]
        self.sendbuf = self.null_string[:]
        self.chunk_len = chunk_len
        self.disable_flush = disable_flush
        self.maintain_alignment = maintain_alignment

        if hasattr(filedes, 'read'):
            self.fetch = filedes.read
        elif hasattr(filedes, 'recv'):
            self.fetch = filedes.recv
        elif hasattr(filedes, 'pull'):
            self.fetch = lambda x: filedes.pull()
        elif isinstance(filedes, int):
            self.fetch = lambda length: os.read(self.filedes, length)
        else:
            raise TypeError('No read, no recv, no pull, not an int')

        if hasattr(filedes, 'write'):
            self.fling = filedes.write
        elif hasattr(filedes, 'send'):
            self.fling = filedes.send
        elif hasattr(filedes, 'push'):
            self.fling = filedes.push
        elif isinstance(filedes, int):
            self.fling = lambda data: os.write(self.filedes, data)
        else:
            raise TypeError('No write, no send, no push, not an int')

    def set_chunk_len(self, length):
        '''Set the chunk length (blocksize) for our buffering'''
        self.chunk_len = length

    def read(self, length=None):
        '''Read some bytes'''
        while length is None or len(self.recvbuf) < length:
            new_portion = self.fetch(self.chunk_len)
            if not new_portion:
                break
            self.recvbuf = self.recvbuf + new_portion
        len_recvbuf = len(self.recvbuf)
        if length is None:
            retval = self.recvbuf
            self.recvbuf = python2x3.empty_bytes
        else:
            if length < len_recvbuf:
                ind = length - len(self.recvbuf)
                retval = self.recvbuf[0:ind]
                self.recvbuf = self.recvbuf[ind:]
            else:
                retval = self.recvbuf[:]
                self.recvbuf = self.null_string
        return retval

    recv = read

    def readto(self, terminator):
        '''Read some bytes, up to a specified terminator'''
        term = python2x3.string_to_binary(terminator)
        while 1:
            ind = self.recvbuf.find(term)
            if ind != -1:
                break
            new_chunk = self.fetch(self.chunk_len)
            if new_chunk:
                self.recvbuf = self.recvbuf + new_chunk
            else:
                # we hit the end of the file, without first finding the terminator we wanted
                self.recvbuf += new_chunk
                ind = len(self.recvbuf) - 1
                break
        # include the terminator find found
        ind = ind + len(terminator)
        retval = self.recvbuf[:ind]
        self.recvbuf = self.recvbuf[ind:]
        return retval

    def readline(self):
        '''Read up to a newline'''
        return self.readto('\n')

    def readtomax(self, terminator, length):
        '''Read up to a specified terminator, or a maximum length, whichever comes first'''
        term = python2x3.string_to_binary(terminator)
        while 1:
            ind = self.recvbuf[:length].find(term)
            if ind != -1:
                found = 1
                break
            if len(self.recvbuf) > length:
                found = 0
                break
            self.recvbuf = self.recvbuf + self.fetch(self.chunk_len)
        # include the terminator find found
        if found:
            ind = ind + len(terminator)
        else:
            ind = length
        retval = self.recvbuf[:ind]
        self.recvbuf = self.recvbuf[ind:]
        return retval

    def send(self, buf):
        '''Send (write) some bytes'''
        self.sendbuf = self.sendbuf + buf
        # FIXME: This could be sped up a bit using slicing
        while len(self.sendbuf) >= self.chunk_len:
            self.fling(self.sendbuf[:self.chunk_len])
            self.sendbuf = self.sendbuf[self.chunk_len:]

    write = send

    def flush(self):
        '''Flush our buffer'''
        if self.disable_flush or self.maintain_alignment:
            return
        if not self.sendbuf:
            # Note that this also catches readonly files - no sense in flushing something that we only read from
            return
        self.fling(self.sendbuf)
        self.sendbuf = self.null_string[:]

    def shutdown(self, value):
        '''Shutdown our socket - or close the file'''
#        we may need something like this
#        if self.disable_flush or self.maintain_alignment:
#            return
        if hasattr(self.filedes, 'shutdown'):
            self.flush()
            self.filedes.shutdown(value)
        elif hasattr(self.filedes, 'close'):
            self.filedes.close()
        else:
            raise NotImplementedError("Sorry, I do not have a shutdown or close method for the object you passed me")

    def close(self):
        '''Close the file'''
#        in fact, this is a bit broken...
#        we may need something that'll pad out the last block
#        if self.disable_flush or self.maintain_alignment:
#            return
        self.disable_flush = False
        self.flush()
        if hasattr(self.filedes, 'close'):
            self.filedes.close()
        else:
            os.close(self.filedes)

    def fileno(self):
        '''Return the fileno corresponding to self.filedes'''
        if hasattr(self.filedes, 'fileno'):
            return self.filedes.fileno()
        else:
            return self.filedes


def simple_test():
    '''Perform a very simple test'''
    file_ = bufsock(rawio('/etc/passwd', 'r'))
    while 1:
        line = file_.readto('\n')
        if not line:
            break
        sys.stdout.write(line)
    file_.close()

if __name__ == '__main__':
    simple_test()
