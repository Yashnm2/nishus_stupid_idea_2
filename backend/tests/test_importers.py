from pathlib import Path
from zipfile import ZipFile

from openpyxl import Workbook

from app.importers import parse_csv, parse_entry, parse_ods, parse_pdf, parse_xlsx


def test_parse_entry_extracts_structured_class_session():
    session = parse_entry("Monday 09:00-11:00 Engineering Mathematics", "manual")

    assert session is not None
    assert session.day == "Monday"
    assert session.start.hour == 9
    assert session.end.hour == 11
    assert session.module == "Engineering Mathematics"


def test_parse_entry_accepts_unicode_dashes_between_times():
    en_dash_session = parse_entry("Monday 09:00\u201311:00 Engineering Mathematics", "manual")
    em_dash_session = parse_entry("Tuesday 14:00\u201415:00 Physics Lab", "manual")

    assert en_dash_session is not None
    assert en_dash_session.start.hour == 9
    assert en_dash_session.end.hour == 11
    assert en_dash_session.module == "Engineering Mathematics"
    assert em_dash_session is not None
    assert em_dash_session.start.hour == 14
    assert em_dash_session.end.hour == 15
    assert em_dash_session.module == "Physics Lab"


def test_parse_csv_normalizes_rows():
    data = Path("tests/fixtures/sample_timetable.csv").read_bytes()

    sessions = parse_csv(data, "sample_timetable.csv")

    assert [session.module for session in sessions] == [
        "Engineering Mathematics",
        "Physics Lab",
        "Computing Studio",
    ]

def test_parse_xlsx_normalizes_cells(tmp_path):
    path = tmp_path / "timetable.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Monday", "09:00-11:00", "Engineering Mathematics"])
    workbook.save(path)

    sessions = parse_xlsx(path.read_bytes(), "timetable.xlsx")

    assert len(sessions) == 1
    assert sessions[0].module == "Engineering Mathematics"


def test_parse_ods_normalizes_cells(tmp_path):
    path = tmp_path / "timetable.ods"
    content = """<?xml version="1.0" encoding="UTF-8"?>
    <office:document-content
      xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
      xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
      xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">
      <office:body><office:spreadsheet><table:table>
        <table:table-row>
          <table:table-cell><text:p>Tuesday</text:p></table:table-cell>
          <table:table-cell><text:p>14:00-15:00</text:p></table:table-cell>
          <table:table-cell><text:p>Physics Lab</text:p></table:table-cell>
        </table:table-row>
      </table:table></office:spreadsheet></office:body>
    </office:document-content>"""
    with ZipFile(path, "w") as archive:
        archive.writestr("content.xml", content)

    sessions = parse_ods(path.read_bytes(), "timetable.ods")

    assert len(sessions) == 1
    assert sessions[0].module == "Physics Lab"


def test_parse_pdf_extracts_text_lines(monkeypatch):
    class FakePage:
        def extract_text(self):
            return "Friday 16:00-17:30 Computing Studio"

    class FakeReader:
        def __init__(self, stream):
            self.pages = [FakePage()]

    monkeypatch.setattr("app.importers.PdfReader", FakeReader)

    sessions = parse_pdf(b"%PDF", "timetable.pdf")

    assert len(sessions) == 1
    assert sessions[0].module == "Computing Studio"
