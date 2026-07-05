from src.parsers.base import DocumentBlock, ParsedDocument, blocks_to_chunks


def test_blocks_to_chunks_preserves_table_and_image_metadata():
    parsed = ParsedDocument(
        title="demo.docx",
        blocks=[
            DocumentBlock(
                id="b1",
                type="paragraph",
                text="普通段落内容",
                parent_title="第一章",
                page_start=1,
                order=1,
            ),
            DocumentBlock(
                id="b2",
                type="table",
                caption="表1 指标",
                text="| 指标 | 数值 |\n| --- | --- |\n| A | 10 |",
                summary="表格包含指标和数值两列。",
                parent_title="第一章",
                page_start=1,
                order=2,
            ),
            DocumentBlock(
                id="b3",
                type="image",
                caption="图1 架构图",
                summary="图片展示系统架构。",
                asset_path="user/u/workspace/ws/docs/demo_assets/image_001.png",
                parent_title="第一章",
                page_start=2,
                order=3,
            ),
        ],
    )

    chunks = blocks_to_chunks(parsed)

    assert [chunk.block_type for chunk in chunks] == ["paragraph", "table", "image"]
    table_meta = chunks[1].to_metadata("doc-1", "demo.docx")
    image_meta = chunks[2].to_metadata("doc-1", "demo.docx")
    assert table_meta["block_id"] == "b2"
    assert table_meta["block_type"] == "table"
    assert table_meta["caption"] == "表1 指标"
    assert image_meta["asset_path"] == "user/u/workspace/ws/docs/demo_assets/image_001.png"
    assert "图片展示系统架构" in chunks[2].text


def test_blocks_to_chunks_preserves_h1_h2_hierarchy():
    parsed = ParsedDocument(
        title="demo.pdf",
        blocks=[
            DocumentBlock(id="h1", type="title", text="Go语言基础", level=1, page_start=1, order=1),
            DocumentBlock(id="h2", type="title", text="make和new的区别", level=2, page_start=2, order=2),
            DocumentBlock(id="p1", type="paragraph", text="make 用于初始化引用类型。", page_start=2, order=3),
            DocumentBlock(id="h3", type="title", text="总结", level=3, page_start=3, order=4),
            DocumentBlock(id="p2", type="paragraph", text="new 只用于分配内存。", page_start=3, order=5),
        ],
    )

    chunks = blocks_to_chunks(parsed)

    assert chunks[0].chapter_title == "Go语言基础"
    assert chunks[0].section_title == "make和new的区别"
    assert chunks[0].section_level == 2
    assert chunks[1].chapter_title == "Go语言基础"
    assert chunks[1].section_title == "make和new的区别"
