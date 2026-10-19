import pytest

from jhq.radar import jd


@pytest.mark.parametrize("url", [
    "http://127.0.0.1:8765/api/data",
    "http://localhost/admin",
    "http://192.168.1.1/",
    "file:///etc/passwd",
    "https://www.linkedin.com/jobs/view/123",
    "https://ca.indeed.com/viewjob?jk=1",
])
def test_refuses_local_and_blocked_urls(url):
    with pytest.raises(ValueError):
        jd._check_url(url)
