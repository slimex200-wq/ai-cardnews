import tempfile
from pathlib import Path
from page_generator import generate_gallery


def test_generate_gallery_creates_html():
    with tempfile.TemporaryDirectory() as tmpdir:
        date_dir = Path(tmpdir) / "output" / "2026-03-20"
        date_dir.mkdir(parents=True)
        (date_dir / "card-01.png").write_bytes(b"fake png")
        (date_dir / "card-02.png").write_bytes(b"fake png")

        docs_dir = Path(tmpdir) / "docs"
        docs_dir.mkdir()

        generate_gallery(str(Path(tmpdir) / "output"), str(docs_dir))

        index = docs_dir / "index.html"
        assert index.exists()
        content = index.read_text(encoding="utf-8")
        assert "2026-03-20" in content
        assert "card-01.png" in content


def test_generate_gallery_multiple_dates():
    with tempfile.TemporaryDirectory() as tmpdir:
        for date in ["2026-03-19", "2026-03-20"]:
            date_dir = Path(tmpdir) / "output" / date
            date_dir.mkdir(parents=True)
            (date_dir / "card-01.png").write_bytes(b"fake png")

        docs_dir = Path(tmpdir) / "docs"
        docs_dir.mkdir()

        generate_gallery(str(Path(tmpdir) / "output"), str(docs_dir))

        content = (docs_dir / "index.html").read_text(encoding="utf-8")
        assert content.index("2026-03-20") < content.index("2026-03-19")


def test_generate_gallery_empty_output():
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "output"
        output_dir.mkdir()
        docs_dir = Path(tmpdir) / "docs"
        docs_dir.mkdir()

        generate_gallery(str(output_dir), str(docs_dir))

        content = (docs_dir / "index.html").read_text(encoding="utf-8")
        assert "AI Card News" in content
