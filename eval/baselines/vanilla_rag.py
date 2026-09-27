"""Vanilla-RAG baseline: same corpus, same BM25, NO date filter, NO Status Ledger.

It stands in for a conventional RAG assistant (BENCH_SPEC §3). The implementation lives in
api/baseline.py so the web demo can show it side by side; this module is the eval's name for it.
"""

from api.baseline import retrieve

__all__ = ["retrieve"]
