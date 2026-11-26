import pytest
from app.api.routes.query import is_summary_request


class TestIsSummaryRequest:
    def test_detects_summarize(self):
        assert is_summary_request("Can you summarize this document?") == True

    def test_detects_summary(self):
        assert is_summary_request("Give me a summary of the PDF") == True

    def test_detects_brief(self):
        assert is_summary_request("Provide a brief overview") == True

    def test_detects_tldr(self):
        assert is_summary_request("TL;DR of this document") == True

    def test_detects_key_points(self):
        assert is_summary_request("What are the key points?") == True

    def test_not_summary_query(self):
        assert is_summary_request("What is quantum entanglement?") == False

    def test_case_insensitive(self):
        assert is_summary_request("SUMMARIZE THIS") == True

    def test_empty_string(self):
        assert is_summary_request("") == False
