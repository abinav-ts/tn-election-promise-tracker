import hashlib

from ept.corpus.catalogue import canonical_url, doc_id_for_manual, doc_id_for_url
from ept.corpus.wayback import Capture, Wayback, payload_digest


def test_doc_id_deterministic_and_canonical():
    url = "https://cms.tn.gov.in/cms_migrated/document/docfiles/hfw_e_pn_2022_23.pdf"
    assert doc_id_for_url(url) == hashlib.sha1(url.encode()).hexdigest()[:16]
    assert doc_id_for_url(url) == doc_id_for_url("  HTTPS://CMS.tn.gov.in:443/cms_migrated/document/docfiles/hfw_e_pn_2022_23.pdf#p2")
    assert len(doc_id_for_url(url)) == 16
    assert doc_id_for_url(url) != doc_id_for_url(url.replace("2022_23", "2023_24"))
    assert canonical_url("http://Example.org:80/a?b=1") == "http://example.org/a?b=1"


def test_manual_ids():
    a = doc_id_for_manual("budget/bs_2016.pdf")
    assert a == hashlib.sha1(b"manual/budget/bs_2016.pdf").hexdigest()[:16]
    assert a != doc_id_for_url("budget/bs_2016.pdf")


def _cap(ts, digest):
    return Capture(ts, "http://tnbudget.tn.gov.in/x.pdf", "200", digest)


def test_wayback_versions_and_kept_digest_first_capture():
    # Feb 2021 interim budget, later replaced by the Aug 2021 revised budget at the same URL (D-018)
    caps = [_cap("20210301000000", "OLD"), _cap("20210601000000", "OLD"),
            _cap("20210901000000", "NEW"), _cap("20220101000000", "NEW")]
    vs = Wayback.versions(caps)
    assert [(v.digest, v.first, v.last, v.n_captures) for v in vs] == [
        ("OLD", "20210301000000", "20210601000000", 2), ("NEW", "20210901000000", "20220101000000", 2)]
    assert Wayback.latest(caps).digest == "NEW"
    # the date fallback uses the first capture of the kept bytes, not the URL's first capture
    assert Wayback.first_of_digest(caps, "NEW").timestamp == "20210901000000"
    assert Wayback.first_of_digest(caps, "MISSING") is None


def test_payload_digest_is_base32_sha1():
    assert payload_digest(b"abc") == "VGMT4NSHA2AWVOR6EVYXQUGCNSONBWE5"
