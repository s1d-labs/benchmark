"""MoSPI task: pure functions, no network."""
import mospi


def test_list_rows_become_records_with_the_sites_ids_and_total():
    answer = {"data": [{"id": "7", "title": "A"}, {"title": "B"}], "pagination": {"currentPage": 2, "totalItems": 114}}
    rows, total = mospi.parse_list("release", answer)
    assert [r for r, _ in rows] == ["release-7", "release-p2-1"] and total == 114


def test_total_key_differs_by_list():
    assert mospi.parse_list("achievement", {"data": [], "pagination": {"total": 58}})[1] == 58
    assert mospi.parse_list("announcement", {"data": [], "pagination": {"totalRecords": 48}})[1] == 48
    assert mospi.parse_list("x", {"status": "error"}) == ([], None)


def test_file_refs_keep_only_mospi_files_once_each():
    row = {"file_one": {"path": "uploads/a b.pdf", "filename": "a b.pdf", "filemime": "application/pdf", "filesize": 5},
           "file_url": "https://mospi.gov.in/uploads/a%20b.pdf",
           "file_two": {"path": "https://other.example/x.pdf"},
           "doc_url": [{"path": "https://www.mospi.gov.in/sites/default/files/y.pdf"}]}
    urls = [u for u, *_ in mospi.file_refs(row)]
    assert urls == ["https://www.mospi.gov.in/uploads/a%20b.pdf", "https://www.mospi.gov.in/sites/default/files/y.pdf"]


def test_bucket_path_uses_only_allowed_characters():
    assert mospi.bucket_path("https://www.mospi.gov.in/uploads/a%20b (1).pdf") == "files/uploads/a_b_1_.pdf"


def test_request_body_default_and_extra():
    b = mospi.request_body({"sort_field": "id"}, 3)
    assert b["sort_field"] == "id" and b["page_no"] == 3 and b["page_size"] == 100
