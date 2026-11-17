"""eaindustry task: parsing on a saved page, no network."""
from pathlib import Path

import eaindustry

PAGE = (Path(__file__).parent / "pages" / "eaindustry_home.html").read_text(encoding="utf-8", errors="replace")
URL = "https://eaindustry.nic.in/"


def test_page_record_has_title_pages_and_files_of_this_host_only():
    rid, data, files = eaindustry.parse(PAGE, URL)
    assert rid == "home" and data["title"] == "Office of Economic Adviser"
    assert "https://eaindustry.nic.in/download_data_2223.asp" in data["links"]
    assert "https://eaindustry.nic.in/press_release/press_release_202610.pdf" in files
    assert all(u.startswith("https://eaindustry.nic.in/") for u in data["links"] + files)


def test_login_and_portal_pages_are_not_followed():
    page = '<a href="/newseries/login.asp">x</a><a href="/jobs/email_verification.php">y</a><a href="/about_us.asp">z</a>'
    assert eaindustry.parse(page, URL)[1]["links"] == ["https://eaindustry.nic.in/about_us.asp"]


def test_file_names_with_spaces_are_encoded_once():
    _, _, files = eaindustry.parse('<a href="eight_core_infra/Core Industries 2004-05.xlsx">d</a>', URL)
    assert files == ["https://eaindustry.nic.in/eight_core_infra/Core%20Industries%202004-05.xlsx"]
