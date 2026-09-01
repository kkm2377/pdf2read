from pdf2read.extract import stitch_question_marks
from pdf2read.outline import _clean_title, _no_from_title


def test_clean_title_keeps_leading_digit_words():
    assert _clean_title("2要素認証") == "2要素認証"
    assert _clean_title("1-1-2 マルウェア") == "マルウェア"
    assert _clean_title("第2章 情報セキュリティ技術") == "情報セキュリティ技術"


def test_no_from_title_ignores_lone_digit():
    assert _no_from_title("2要素認証", "p026") == "p026"
    assert _no_from_title("1-1-2 マルウェア", "x") == "1-1-2"


def test_stitch_question_marks():
    lines = [
        {"text": "1", "size": 28, "bold": False, "x0": 92, "y0": 97, "x1": 110, "y1": 120, "color": 0},
        {"text": "問", "size": 11, "bold": False, "x0": 75, "y0": 109, "x1": 90, "y1": 120, "color": 0},
        {"text": "入退室管理はどれか。", "size": 9.6, "bold": False, "x0": 129, "y0": 110, "x1": 400, "y1": 122, "color": 0},
    ]
    out = stitch_question_marks(lines)
    texts = [L["text"] for L in out]
    assert "問1" in texts
    assert "問" not in texts
    assert "1" not in texts
