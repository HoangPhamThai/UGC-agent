# agents/app/artifact_stream_filter.py
"""Incrementally strips sentinel-delimited artifact blocks from a streamed reply
so the sentinel never flashes in the chat bubble. Display-only: the authoritative
parse/persistence uses extract_artifact() on the full accumulated text."""

_START = '<<<ARTIFACT'
_END = '<<<END ARTIFACT>>>'


def _longest_prefix_suffix(buf: str, token: str) -> int:
    """Length of the longest suffix of buf that is a (proper) prefix of token.
    Used to hold back a trailing partial marker that may complete next chunk."""
    n = min(len(buf), len(token) - 1)
    for size in range(n, 0, -1):
        if token.startswith(buf[-size:]):
            return size
    return 0


class ArtifactStreamFilter:
    """Stateful. feed(chunk) -> text safe to display now (possibly ""). flush() ->
    any remaining buffered text once the stream ends."""

    def __init__(self) -> None:
        self._buf = ""
        self._suppress = False  # True once a full _START token is seen, until _END

    def feed(self, chunk: str) -> str:
        self._buf += chunk
        out: list[str] = []
        while True:
            if self._suppress:
                end = self._buf.find(_END)
                if end == -1:
                    # whole buffer is (start of) an artifact block — emit nothing
                    return "".join(out)
                # drop the block including the END marker, resume scanning as text
                self._buf = self._buf[end + len(_END):]
                self._suppress = False
                continue
            start = self._buf.find(_START)
            if start != -1:
                out.append(self._buf[:start])
                self._buf = self._buf[start:]
                self._suppress = True
                continue
            # no full start marker: emit everything except a possible partial tail
            hold = _longest_prefix_suffix(self._buf, _START)
            if hold:
                out.append(self._buf[:-hold])
                self._buf = self._buf[-hold:]
            else:
                out.append(self._buf)
                self._buf = ""
            return "".join(out)

    def flush(self) -> str:
        if self._suppress:
            # unterminated block — drop it from display
            return ""
        leftover, self._buf = self._buf, ""
        return leftover
