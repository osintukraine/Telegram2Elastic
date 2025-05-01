import pytest

from telegram2elastic import FileSize, DottedPathDict, TimeInterval


class TestFileSize:
    def test_human_readable_to_bytes(self):
        assert FileSize.human_readable_to_bytes("1KB") == 1024
        assert FileSize.human_readable_to_bytes("1.5MB") == 1572864
        assert FileSize.human_readable_to_bytes("5G") == 5368709120
        assert FileSize.human_readable_to_bytes("12TB") == 13194139533312

    def test_bytes_to_human_readable(self):
        assert FileSize.bytes_to_human_readable(100) == "100.0B"
        assert FileSize.bytes_to_human_readable(1024) == "1.0KB"
        assert FileSize.bytes_to_human_readable(1572864) == "1.5MB"
        assert FileSize.bytes_to_human_readable(5368709120) == "5.0GB"
        assert FileSize.bytes_to_human_readable(13194139533312) == "12.0TB"


class TestDottedPathDict:
    def test(self):
        dotted_path_dict = DottedPathDict()
        dotted_path_dict.set("foo.bar", "hello")
        dotted_path_dict.set("hello", "world")

        assert dotted_path_dict.get("foo.bar") == "hello"
        assert dotted_path_dict.get("hello") == "world"

        with pytest.raises(TypeError):
            dotted_path_dict.set("foo.bar.baz", "other value")


class TestTimeInterval:
    def test_parse(self):
        assert TimeInterval.parse("1h1m").seconds == 60*60 + 60
        assert TimeInterval.parse("1h5m").seconds == 60*60 + 60*5
        assert TimeInterval.parse("1d").seconds == 60*60*24
        assert TimeInterval.parse("1d3h10m").seconds == 60*60*24 + 60*60*3 + 60*10
        assert TimeInterval.parse("1y2mo").seconds == 60*60*24*365 + 60*60*24*60
        assert TimeInterval.parse("1mo2m").seconds == 60*60*24*30 + 60*2
        assert TimeInterval.parse("2m1mo").seconds == 60*60*24*30 + 60*2

    def test_format(self):
        assert TimeInterval(1).format_human_readable() == "1 second"
        assert TimeInterval(25).format_human_readable() == "25 seconds"
        assert TimeInterval(60).format_human_readable() == "1 minute"
        assert TimeInterval(90).format_human_readable() == "1 minute, 30 seconds"
        assert TimeInterval(60*2).format_human_readable() == "2 minutes"
        assert TimeInterval(60*60).format_human_readable() == "1 hour"
        assert TimeInterval(60*60*24).format_human_readable() == "1 day"
        assert TimeInterval(60*60*24*2).format_human_readable() == "2 days"
        assert TimeInterval(60*60*24 + 60*60*12 + 60 + 35).format_human_readable() == "1 day, 12 hours, 1 minute, 35 seconds"
