from pdf2read.extract import (
    clean_extracted_text,
    group_notes,
    has_two_content_columns,
    line_inside_box,
    order_page_items,
    stitch_checkbox_items,
    stitch_question_marks,
    structure_lines,
)


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


def test_standalone_checkbox_and_text_become_remember_item():
    lines = [
        {
            "text": "□", "size": 8, "bold": False, "color": 0,
            "x0": 40, "y0": 529, "x1": 48, "y1": 539,
        },
        {
            "text": "機密性，完全性，可用性を維持すること", "size": 8, "bold": False, "color": 0,
            "x0": 59, "y0": 529, "x1": 250, "y1": 539,
        },
    ]
    stitched = stitch_checkbox_items(lines)
    assert len(stitched) == 1
    assert stitched[0]["text"].startswith("□ ")
    blocks = structure_lines([{**stitched[0], "page": 50}], 9)
    assert blocks == [("remember", ["機密性，完全性，可用性を維持すること"])]


def test_question_number_is_not_joined_across_page():
    lines = [
        {
            "text": "問", "size": 11, "bold": False, "color": 0,
            "x0": 75, "y0": 100, "x1": 90, "y1": 115,
        },
        {
            "text": "1", "size": 24, "bold": False, "color": 0,
            "x0": 300, "y0": 100, "x1": 315, "y1": 120,
        },
    ]
    assert [line["text"] for line in stitch_question_marks(lines)] == ["問", "1"]


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


def test_choices_require_a_question_and_only_join_indented_wraps():
    lines = [
        {"text": "通常の説明です。", "size": 9, "bold": False, "page": 1, "x0": 42, "y0": 40},
        {"text": "ア これは一般段落です。", "size": 9, "bold": False, "page": 1, "x0": 42, "y0": 55},
        {"text": "問1", "size": 12, "bold": True, "page": 1, "x0": 42, "y0": 90},
        {"text": "適切なものはどれか。", "size": 9, "bold": False, "page": 1, "x0": 42, "y0": 105},
        {"text": "ア 長い選択肢の前半", "size": 9, "bold": False, "page": 1, "x0": 54, "y0": 120},
        {"text": "後半です。", "size": 9, "bold": False, "page": 1, "x0": 72, "y0": 135},
        {"text": "イ 句点のない選択肢", "size": 9, "bold": False, "page": 1, "x0": 54, "y0": 150},
        {"text": "次の本文です。", "size": 9, "bold": False, "page": 1, "x0": 42, "y0": 180},
    ]
    blocks = structure_lines(lines, 9)
    choices = next(value for kind, value in blocks if kind == "choices")
    assert choices == [("ア", "長い選択肢の前半後半です。"), ("イ", "句点のない選択肢")]
    assert any(kind == "p" and "ア これは一般段落です。" in value for kind, value in blocks)
    assert any(kind == "p" and value == "次の本文です。" for kind, value in blocks)


def test_latin_range_in_question_is_not_a_choice():
    lines = [
        {"text": "問1", "size": 12, "bold": True, "page": 1, "x0": 42, "y0": 40},
        {"text": "a 〜dのうち，適切なものはどれか。", "size": 9, "bold": False, "page": 1, "x0": 42, "y0": 55},
    ]
    assert not any(kind == "choices" for kind, _ in structure_lines(lines, 9))


def test_figure_box_preserves_body_sized_sentence():
    box = (30, 170, 340, 390)
    body = {
        "text": "資産には，商品や不動産など形のあるものだけでなく，顧客情報も含まれます。",
        "size": 9, "x0": 42, "y0": 180, "x1": 278, "y1": 192,
    }
    label = {
        "text": "顧客情報", "size": 7, "x0": 99, "y0": 204, "x1": 127, "y1": 214,
    }
    assert not line_inside_box(body, box, preserve_body=True, body_size=9)
    assert line_inside_box(label, box, preserve_body=True, body_size=9)


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


def test_indented_continuation_is_not_mistaken_for_two_columns():
    layout = {
        "mode": "two", "split_x": 294, "width": 420, "height": 595, "body_size": 9,
    }
    lines = [
        {"text": f"본문 {i}", "size": 9, "x0": 42, "y0": 40 + i * 15}
        for i in range(20)
    ]
    lines += [
        {"text": "장애 건수, 복구 시간", "size": 9, "x0": 199, "y0": 370},
        {"text": "가동률", "size": 9, "x0": 199, "y0": 385},
    ]
    assert not has_two_content_columns(lines, layout)
    ordered = order_page_items(lines, layout, False)
    assert [line["text"] for line in ordered][-3:] == [
        "본문 19", "장애 건수, 복구 시간", "가동률",
    ]


def test_dense_two_up_page_reads_left_column_then_right():
    layout = {
        "mode": "two", "split_x": 294, "width": 420, "height": 595, "body_size": 9,
    }
    left = [
        {"text": f"왼쪽 {i}", "size": 7, "x0": 62, "y0": 50 + i * 12}
        for i in range(12)
    ]
    right = [
        {"text": f"오른쪽 {i}", "size": 7, "x0": 233, "y0": 50 + i * 12}
        for i in range(12)
    ]
    lines = [item for pair in zip(left, right) for item in pair]
    assert has_two_content_columns(lines, layout)
    ordered = order_page_items(lines, layout, True)
    assert [line["text"] for line in ordered] == [
        *(f"왼쪽 {i}" for i in range(12)),
        *(f"오른쪽 {i}" for i in range(12)),
    ]
