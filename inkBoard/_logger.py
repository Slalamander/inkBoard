#Entry point and handling for command inkBoard logs

import logging
import logging.handlers
import pickle
import socketserver
import struct

class LogRecordStreamHandler(socketserver.StreamRequestHandler):
    """Handler for a streaming logging request.

    This basically logs the record using whatever logging policy is
    configured locally.
    """

    def handle(self):
        """
        Handle multiple requests - each expected to be a 4-byte length,
        followed by the LogRecord in pickle format. Logs the record
        according to whatever policy is configured locally.
        """
        while True:
            chunk = self.connection.recv(4)
            if len(chunk) < 4:
                break
            slen = struct.unpack('>L', chunk)[0]
            chunk = self.connection.recv(slen)
            while len(chunk) < slen:
                chunk = chunk + self.connection.recv(slen - len(chunk))
            obj = self.unPickle(chunk)
            # record = logging.makeLogRecord(obj)
            print(obj)
            # self.handleLogRecord(record)

    def unPickle(self, data):
        return pickle.loads(data)

class LogRecordSocketReceiver(socketserver.ThreadingTCPServer):
    """
    Simple TCP socket-based logging receiver suitable for testing.
    """

    allow_reuse_address = True

    def __init__(self, host='localhost',
                port=logging.handlers.DEFAULT_TCP_LOGGING_PORT,
                handler=LogRecordStreamHandler):
        socketserver.ThreadingTCPServer.__init__(self, (host, port), handler)
        self.abort = 0
        self.timeout = 1
        self.logname = None

    def serve_until_stopped(self):
        import select
        abort = 0
        while not abort:
            rd, wr, ex = select.select([self.socket.fileno()],
                                    [], [],
                                    self.timeout)
            if rd:
                self.handle_request()
            abort = self.abort

def run_logger(*args):
    ##argument options:
    ##host to connect to (default localhost)
    ##port to connect to (default is default_tcp_port)
    ##config to run from (handled by the api I think, which should resolve correct host + port)
    
    tcpserver = LogRecordSocketReceiver()
    print('About to start TCP server...')
    tcpserver.serve_until_stopped()
    return

if __name__ == "__main__":
    
    ##Need an entrypoint for this to enable a new console etc. to stream the logs??
    ##Do I?
    ##Entry point would potentially only be needed when directly running the file
    ##I.e. simply recalling inkBoard logs should do the same as it would spawn a new process
    run_logger()