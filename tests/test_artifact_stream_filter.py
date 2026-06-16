from app.artifact_stream_filter import ArtifactStreamFilter

START = '<<<ARTIFACT title="T">>>'
BLOCK = START + "\n| x |\n<<<END ARTIFACT>>>"


def run(chunks):
    f = ArtifactStreamFilter()
    out = "".join(f.feed(c) for c in chunks)
    return out + f.flush()


def test_plain_text_passes_through_unchanged():
    assert run(["hello ", "world"]) == "hello world"


def test_full_artifact_block_in_one_chunk_is_removed():
    assert run([f"Tổng 42.\n{BLOCK}"]) == "Tổng 42.\n"


def test_artifact_split_across_many_chunks_is_removed():
    text = f"answer {BLOCK} tail"
    # one character at a time — the hardest boundary case
    assert run(list(text)) == "answer  tail"


def test_partial_start_marker_at_end_is_not_leaked_midstream():
    f = ArtifactStreamFilter()
    # chunk ends mid-marker; nothing past the safe point should be emitted yet
    emitted = f.feed("done <<<ARTIF")
    assert "<<<ARTIF" not in emitted
    assert emitted == "done "
    # marker completes and block closes -> still scrubbed
    rest = f.feed('ACT title="T">>>body<<<END ARTIFACT>>>')
    assert (emitted + rest + f.flush()) == "done "


def test_lone_triple_angle_that_is_not_an_artifact_is_kept():
    # never matches the full START token -> emitted as ordinary text
    assert run(["a <<< b ", "<<<not artifact>>> c"]) == "a <<< b <<<not artifact>>> c"


def test_unterminated_artifact_block_is_dropped_on_flush():
    assert run([f"x {START} never closes"]) == "x "


def test_end_marker_split_across_chunks_while_suppressing():
    assert run(["pre ", START, "data <<<END ", "ARTIFACT>>> post"]) == "pre  post"


def test_two_artifact_blocks_in_one_stream_both_removed():
    assert run([f"a {BLOCK} b {BLOCK} c"]) == "a  b  c"


def test_held_back_partial_start_that_is_plain_text_is_emitted():
    assert run(["abc<<<ARTIFA", "Bcd done"]) == "abc<<<ARTIFABcd done"
