"""Deterministic seed corpus + background mutation loop.

The corpus is a small in-memory CRM dataset (Accounts, Contacts,
Opportunities). A background thread periodically mutates rows so each
incremental pull returns non-empty deltas. SystemModstamp monotonically
advances on every mutation and insert.
"""

from __future__ import annotations

import random
import string
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, Iterable

SObjectName = str


@dataclass
class _Record:
    Id: str
    attrs: dict
    SystemModstamp: datetime


@dataclass
class _Table:
    records: list[_Record] = field(default_factory=list)
    by_id: dict[str, _Record] = field(default_factory=dict)


def _rand_id(rng: random.Random, prefix: str) -> str:
    suffix = "".join(rng.choices(string.ascii_letters + string.digits, k=15))
    return f"{prefix}{suffix}"


def _rand_name(rng: random.Random) -> str:
    first = rng.choice(["Acme", "Globex", "Initech", "Umbrella", "Wayne", "Stark", "Tyrell", "Cyberdyne", "Soylent", "Hooli"])
    second = rng.choice(["Corp", "Industries", "LLC", "Holdings", "Partners", "Group", "Co", "Systems"])
    return f"{first} {second} {rng.randint(1, 9999)}"


def _rand_person(rng: random.Random) -> tuple[str, str]:
    first = rng.choice(["Alex", "Jordan", "Morgan", "Riley", "Taylor", "Casey", "Jamie", "Drew", "Sam", "Pat"])
    last = rng.choice(["Smith", "Johnson", "Williams", "Jones", "Brown", "Davis", "Miller", "Wilson", "Moore", "Taylor"])
    return first, last


class Corpus:
    def __init__(
        self,
        *,
        rng_seed: int,
        seed_accounts: int,
        seed_contacts: int,
        seed_opportunities: int,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._rng = random.Random(rng_seed)
        self._clock = clock
        self._lock = threading.RLock()
        self._tables: dict[SObjectName, _Table] = {
            "Account": _Table(),
            "Contact": _Table(),
            "Opportunity": _Table(),
        }
        self._last_stamp: datetime = clock() - timedelta(days=1)
        self._seed(seed_accounts, seed_contacts, seed_opportunities)

    def _next_stamp(self) -> datetime:
        now = self._clock()
        if now <= self._last_stamp:
            now = self._last_stamp + timedelta(milliseconds=1)
        self._last_stamp = now
        return now

    def _seed(self, n_accounts: int, n_contacts: int, n_opportunities: int) -> None:
        with self._lock:
            for _ in range(n_accounts):
                self._insert_account()
            for _ in range(n_contacts):
                self._insert_contact()
            for _ in range(n_opportunities):
                self._insert_opportunity()

    def _insert_record(self, sobject: str, attrs: dict) -> _Record:
        prefix = {"Account": "001", "Contact": "003", "Opportunity": "006"}[sobject]
        rec = _Record(
            Id=_rand_id(self._rng, prefix),
            attrs=attrs,
            SystemModstamp=self._next_stamp(),
        )
        self._tables[sobject].records.append(rec)
        self._tables[sobject].by_id[rec.Id] = rec
        return rec

    def _insert_account(self) -> _Record:
        return self._insert_record(
            "Account",
            {
                "Name": _rand_name(self._rng),
                "Industry": self._rng.choice(["Finance", "Technology", "Healthcare", "Retail", "Energy"]),
                "AnnualRevenue": self._rng.randint(100_000, 500_000_000),
                "NumberOfEmployees": self._rng.randint(5, 50_000),
            },
        )

    def _insert_contact(self) -> _Record:
        accounts = self._tables["Account"].records
        account = self._rng.choice(accounts) if accounts else None
        first, last = _rand_person(self._rng)
        return self._insert_record(
            "Contact",
            {
                "FirstName": first,
                "LastName": last,
                "Email": f"{first.lower()}.{last.lower()}@example.com",
                "AccountId": account.Id if account else None,
                "Title": self._rng.choice(["CEO", "CFO", "VP Sales", "Engineer", "Analyst", "Manager"]),
            },
        )

    def _insert_opportunity(self) -> _Record:
        accounts = self._tables["Account"].records
        account = self._rng.choice(accounts) if accounts else None
        return self._insert_record(
            "Opportunity",
            {
                "Name": f"Deal-{self._rng.randint(1000, 999999)}",
                "AccountId": account.Id if account else None,
                "StageName": self._rng.choice(["Prospecting", "Qualification", "Proposal", "Negotiation", "Closed Won", "Closed Lost"]),
                "Amount": self._rng.randint(5_000, 5_000_000),
                "CloseDate": (self._clock() + timedelta(days=self._rng.randint(-30, 180))).date().isoformat(),
            },
        )

    def mutate_once(self) -> int:
        """Mutate a handful of random rows and occasionally insert new ones."""
        with self._lock:
            changes = 0
            for sobject in ("Account", "Contact", "Opportunity"):
                tbl = self._tables[sobject]
                if not tbl.records:
                    continue
                n_mutations = self._rng.randint(1, max(2, len(tbl.records) // 50))
                for _ in range(n_mutations):
                    rec = self._rng.choice(tbl.records)
                    self._bump(sobject, rec)
                    changes += 1
                if self._rng.random() < 0.2:
                    if sobject == "Account":
                        self._insert_account()
                    elif sobject == "Contact":
                        self._insert_contact()
                    else:
                        self._insert_opportunity()
                    changes += 1
            return changes

    def _bump(self, sobject: str, rec: _Record) -> None:
        if sobject == "Account":
            rec.attrs["AnnualRevenue"] = max(0, rec.attrs["AnnualRevenue"] + self._rng.randint(-50_000, 50_000))
        elif sobject == "Contact":
            rec.attrs["Title"] = self._rng.choice(["CEO", "CFO", "VP Sales", "Engineer", "Analyst", "Manager", "Director"])
        else:
            rec.attrs["StageName"] = self._rng.choice(["Prospecting", "Qualification", "Proposal", "Negotiation", "Closed Won", "Closed Lost"])
            rec.attrs["Amount"] = max(0, rec.attrs["Amount"] + self._rng.randint(-100_000, 100_000))
        rec.SystemModstamp = self._next_stamp()

    def query(
        self,
        *,
        sobject: str,
        fields: Iterable[str],
        since_ts: datetime | None,
        limit: int | None,
    ) -> list[dict]:
        with self._lock:
            tbl = self._tables.get(sobject)
            if tbl is None:
                raise KeyError(sobject)
            rows = [r for r in tbl.records if since_ts is None or r.SystemModstamp > since_ts]
            rows.sort(key=lambda r: (r.SystemModstamp, r.Id))
            if limit is not None:
                rows = rows[:limit]
            out: list[dict] = []
            for r in rows:
                base = {
                    "attributes": {"type": sobject, "url": f"/services/data/v59.0/sobjects/{sobject}/{r.Id}"},
                    "Id": r.Id,
                    "SystemModstamp": r.SystemModstamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                }
                for f in fields:
                    if f in ("Id", "SystemModstamp"):
                        continue
                    base[f] = r.attrs.get(f)
                out.append(base)
            return out


class MutationLoop:
    def __init__(self, corpus: Corpus, interval_seconds: float) -> None:
        self._corpus = corpus
        self._interval = interval_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="sf-mock-mutator", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        while not self._stop.wait(self._interval):
            try:
                self._corpus.mutate_once()
            except Exception:
                pass
