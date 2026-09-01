from pdf2read.extract import clean_extracted_text, group_notes, structure_lines


def test_check_widget_is_dropped():
    assert clean_extracted_text("CHECK▶ □□□") == ""
    assert clean_extracted_text("CHECK ▶□□□") == ""
    assert (
        clean_extracted_text("統一基準 CHECK▶ □□□“令和5年度版”")
        == "統一基準 “令和5年度版”"
    )


def test_lone_checkboxes_are_dropped():
    assert clean_extracted_text("□") == ""
    assert clean_extracted_text("□□") == ""
    assert clean_extracted_text("□ リバースブルートフォース攻撃") == "リバースブルートフォース攻撃"


def test_structure_does_not_treat_checkboxes_as_remember():
    lines = [
        {"text": "□", "size": 10, "bold": False},
        {"text": "本文です。", "size": 10, "bold": False},
    ]
    kinds = [k for k, _ in structure_lines(lines, 10)]
    assert "remember" not in kinds


def test_leader_dots_become_ellipsis():
    garbage = "\u029c" * 4
    assert (
        clean_extracted_text(f"機能性評価指標\t{garbage} 要求機能の実現度")
        == "機能性評価指標 …… 要求機能の実現度"
    )
    assert "\u029c" not in clean_extracted_text("可用性\t" + "\u029c" * 5 + "システム")


def test_bullet_lines_are_list_items_not_headings():
    lines = [
        {"text": "プロジェクト憲章", "size": 10, "bold": True},
        {"text": "•	プロジェクトの目的や妥当性", "size": 10, "bold": True},
        {"text": "•	測定可能なプロジェクト目標とその成功基準", "size": 10, "bold": True},
    ]
    blocks = structure_lines(lines, 9)
    assert blocks[0] == ("h3", "プロジェクト憲章")
    assert all(k == "item" for k, _ in blocks[1:])
    assert not any(k == "h3" and str(v).startswith("•") for k, v in blocks)


def test_control_chars_stripped():
    assert clean_extracted_text("・\x07組織内のハードウェア") == "・組織内のハードウェア"


def test_body_sentence_not_skipped_as_title():
    from pdf2read.extract import skip_line

    layout = {"body_size": 9.0, "height": 595.0, "width": 420.0}
    extra = {"情報セキュリティ管理"}
    body = {
        "text": "情報セキュリティ管理では，情報セキュリティポリシーに基づいて",
        "size": 9.0, "bold": False, "color": 0, "x0": 34, "y0": 160, "x1": 280, "y1": 172,
    }
    title = {
        "text": "情報セキュリティ管理",
        "size": 14.0, "bold": True, "color": 0, "x0": 90, "y0": 134, "x1": 220, "y1": 150,
    }
    assert skip_line(body, layout, set(), extra) is False
    assert skip_line(title, layout, set(), extra) is True


def test_list_item_does_not_swallow_next_paragraph():
    lines = [
        {"text": "• 信頼性評価指標 …… 稼働率", "size": 9, "bold": False, "x0": 51},
        {"text": "その他，安全性とセキュリティも評価項目です。", "size": 9, "bold": False, "x0": 34},
    ]
    blocks = structure_lines(lines, 9)
    kinds = [k for k, _ in blocks]
    assert kinds[0] == "item"
    assert kinds[1] == "p"


def test_full_heading_not_stripped_to_fragment():
    from pdf2read.extract import render_blocks

    html = render_blocks(
        [("h3", "情報セキュリティ管理におけるインシデント管理"), ("p", "本文です。")],
        "情報セキュリティ管理",
    )
    assert "情報セキュリティ管理におけるインシデント管理" in html



def test_group_notes_keeps_wrapped_definition():
    html = group_notes([
        {"text": "トレードオフとは，一方を", "size": 8, "bold": True},
        {"text": "追求すれば他方を犠牲にせざるを得ない状態です。", "size": 8, "bold": False},
    ])
    assert "header>側注<" in html
    assert "トレードオフとは，一方を追求すれば" in html

    notes = group_notes([
        {"text": "CHECK▶ □□□", "size": 8, "bold": False},
        {"text": "CHECK▶ □□□", "size": 8, "bold": False},
    ])
    assert notes == ""
