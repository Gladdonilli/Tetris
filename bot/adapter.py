"""A bot process that speaks Triangle's adapter protocol: one JSON message per
line on stdin/stdout. The process answers each `play` with a `move`; its
diagnostics go to stderr, which this process shares.
"""

import json
import subprocess


class AdapterError(RuntimeError):
    pass


class Adapter:
    def __init__(self, command):
        """`command`: the adapter binary and its arguments."""
        self.proc = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            text=True, bufsize=1)
        assert self.proc.stdin is not None and self.proc.stdout is not None
        self.stdin = self.proc.stdin
        self.stdout = self.proc.stdout
        info = self._read()
        if info.get('type') != 'info':
            self.close()
            raise AdapterError('expected an info message first, got {!r}'.format(info.get('type')))
        self.info = info.get('data') or {}
        if self.info.get('installed') is False:
            self.close()
            raise AdapterError('bot package not installed: {}'.format(self.info.get('error')))

    def _send(self, message):
        try:
            self.stdin.write(json.dumps(message, separators=(',', ':')) + '\n')
            self.stdin.flush()
        except (BrokenPipeError, OSError) as error:
            raise AdapterError('adapter exited ({})'.format(error))

    def _read(self):
        line = self.stdout.readline()
        if not line:
            raise AdapterError('adapter exited (code {})'.format(self.proc.poll()))
        return json.loads(line)

    def play(self, position):
        """Asks for a move in `position` and waits for it: {'keys': [...], 'data': {...} or None}."""
        self._send({'type': 'play', 'garbageMultiplier': 1, 'data': position})
        while True:
            message = self._read()
            if message.get('type') == 'move':
                return message

    def close(self):
        if self.proc.poll() is None:
            try:
                self.stdin.close()
            except OSError:
                pass
            try:
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
