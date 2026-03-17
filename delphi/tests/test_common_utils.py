"""Tests for common_utils vote loading functions.

Ensures vote revisions resolve correctly regardless of CSV row order.
"""

import os
import tempfile

import numpy as np
import pytest

from tests.common_utils import load_votes, create_test_conversation
from polismath.conversation.conversation import Conversation


def _write_votes_csv(path: str, rows: list[tuple]) -> None:
    """Write a votes CSV with (timestamp, comment-id, voter-id, vote) rows."""
    with open(path, "w") as f:
        f.write("timestamp,datetime,comment-id,voter-id,vote\n")
        for ts, cid, vid, vote in rows:
            f.write(f"{ts},fake-datetime,{cid},{vid},{vote}\n")


class TestLoadVotesRevisionOrdering:
    """Verify that load_votes() sorts by timestamp so vote revisions resolve correctly."""

    def test_revision_keeps_latest_vote(self, tmp_path):
        """If a participant revises their vote, the chronologically latest one must win.

        Regression test: without timestamp sorting, drop_duplicates(keep='last')
        would keep the last CSV row, which may be the older vote.
        """
        csv_path = str(tmp_path / "votes.csv")
        # CSV row order: disagree at t=2 FIRST, then agree at t=1 SECOND.
        # Without sorting, keep='last' would pick agree (wrong).
        # With sorting, keep='last' picks disagree (correct — it's later).
        _write_votes_csv(csv_path, [
            (2, 0, 0, -1),  # revision: disagree at t=2 (should win)
            (1, 0, 0, 1),   # original: agree at t=1 (should lose)
        ])

        result = load_votes(csv_path)
        votes = result["votes"]

        # After sorting by timestamp, the last vote for (pid=0, tid=0) should be
        # the one at t=2 (disagree = -1.0)
        pid0_tid0_votes = [v for v in votes if v["pid"] == "0" and v["tid"] == "0"]
        assert len(pid0_tid0_votes) == 2
        # The last one in the list should be the latest chronologically
        assert pid0_tid0_votes[-1]["vote"] == -1.0

    def test_revision_through_conversation_update(self, tmp_path):
        """End-to-end: revised vote must appear in the rating matrix after update_votes().

        This is the actual consequence of the bug: the rating matrix would contain
        the wrong vote value if CSV rows weren't sorted by timestamp.
        """
        csv_path = str(tmp_path / "votes.csv")
        # Participant 0 votes agree on comment 0 at t=1, then disagree at t=2.
        # Participant 1 votes agree on comment 0 at t=3 (no revision).
        # CSV order deliberately puts the revision BEFORE the original.
        _write_votes_csv(csv_path, [
            (2, 0, 0, -1),  # pid=0, tid=0: disagree at t=2 (revision, should win)
            (1, 0, 0, 1),   # pid=0, tid=0: agree at t=1 (original, should lose)
            (3, 0, 1, 1),   # pid=1, tid=0: agree at t=3 (no conflict)
        ])

        votes_data = load_votes(csv_path)
        conv = Conversation("test-revision")
        conv = conv.update_votes(votes_data, recompute=False)

        # pid=0 should have disagree (-1) on comment 0
        # Column/row labels may be str or int depending on update_votes internals
        mat = conv.raw_rating_mat
        pid0_label = "0" if "0" in mat.index else 0
        tid0_label = "0" if "0" in mat.columns else 0
        pid1_label = "1" if "1" in mat.index else 1
        assert mat.loc[pid0_label, tid0_label] == -1.0
        # pid=1 should have agree (1) on comment 0
        assert mat.loc[pid1_label, tid0_label] == 1.0

    def test_no_timestamp_column_still_works(self, tmp_path):
        """If CSV has no timestamp column, load_votes() should not crash."""
        csv_path = str(tmp_path / "votes.csv")
        with open(csv_path, "w") as f:
            f.write("comment-id,voter-id,vote\n")
            f.write("0,0,1\n")
            f.write("1,0,-1\n")

        result = load_votes(csv_path)
        assert len(result["votes"]) == 2


class TestCreateTestConversationRevisionOrdering:
    """Verify that create_test_conversation() handles vote revisions correctly."""

    def test_revision_in_matrix_keeps_latest(self, tmp_path, monkeypatch):
        """create_test_conversation() iterates rows to fill the matrix.

        Last write wins — rows must be in timestamp order so the latest revision
        is the one that ends up in the matrix.
        """
        csv_path = str(tmp_path / "votes.csv")
        comments_path = str(tmp_path / "comments.csv")

        # Votes: pid=0 revises vote on comment 0 (agree→disagree)
        # CSV order: revision first, then original (wrong order without sort)
        _write_votes_csv(csv_path, [
            (2, 0, 0, -1),  # revision at t=2 (should win)
            (1, 0, 0, 1),   # original at t=1 (should lose)
            (3, 1, 0, 1),   # pid=1, no conflict
        ])

        # Minimal comments file
        with open(comments_path, "w") as f:
            f.write("timestamp,datetime,comment-id,author-id,agrees,disagrees,moderated,comment-body\n")
            f.write("1,fake,0,99,0,0,1,test comment\n")

        # Monkeypatch get_dataset_files to return our temp files
        import tests.common_utils as cu
        monkeypatch.setattr(cu, "get_dataset_files", lambda name: {"votes": csv_path, "comments": comments_path})

        conv = cu.create_test_conversation("test-revision")

        # pid=0 (index 0) should have disagree (-1) on comment 0 (index 0)
        assert conv.raw_rating_mat.iloc[0, 0] == -1.0
