"""Identity resolution engine for Ghost Data Still Exists.

Reconstructs complete current and historical user profiles by linking
user_identities.csv and user_audit_log.csv.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class IdentityLink:
    field_name: str
    old_value: str
    new_value: str
    event_time: str
    audit_id: str


@dataclass
class UserProfile:
    user_id: str
    current_name: str
    current_email: str
    current_phone: str
    current_email_hash: str
    updated_at: str
    historical_emails: Set[str] = field(default_factory=set)
    historical_phones: Set[str] = field(default_factory=set)
    historical_hashes: Set[str] = field(default_factory=set)
    audit_links: List[IdentityLink] = field(default_factory=list)

    @property
    def all_emails(self) -> Set[str]:
        emails = {self.current_email.lower()}
        for em in self.historical_emails:
            emails.add(em.lower())
        return emails

    @property
    def all_phones(self) -> Set[str]:
        phones = {self.current_phone}
        for ph in self.historical_phones:
            phones.add(ph)
        return phones

    @property
    def all_hashes(self) -> Set[str]:
        hashes = {self.current_email_hash.lower()}
        for h in self.historical_hashes:
            hashes.add(h.lower())
        return hashes

    def get_identifiers_summary(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "current_name": self.current_name,
            "all_emails": sorted(self.all_emails),
            "all_phones": sorted(self.all_phones),
            "all_hashes": sorted(self.all_hashes),
            "audit_events_count": len(self.audit_links),
        }


class IdentityResolver:
    """Indexes and resolves user identities across current and historical records."""

    def __init__(self, dataset_dir: str | Path):
        self.dataset_dir = Path(dataset_dir)
        self.users_by_id: Dict[str, UserProfile] = {}
        self.email_to_user_id: Dict[str, str] = {}
        self.phone_to_user_id: Dict[str, str] = {}
        self.hash_to_user_id: Dict[str, str] = {}
        self._load_identities()
        self._load_audit_logs()

    def _load_identities(self) -> None:
        ident_file = self.dataset_dir / "user_identities.csv"
        if not ident_file.exists():
            raise FileNotFoundError(f"Missing {ident_file}")

        with open(ident_file, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                uid = row["user_id"].strip()
                name = row.get("name", "").strip()
                email = row.get("email", "").strip()
                phone = row.get("phone", "").strip()
                email_hash = row.get("email_hash", "").strip()
                updated_at = row.get("updated_at", "").strip()

                profile = UserProfile(
                    user_id=uid,
                    current_name=name,
                    current_email=email,
                    current_phone=phone,
                    current_email_hash=email_hash,
                    updated_at=updated_at,
                )
                self.users_by_id[uid] = profile

                if email:
                    self.email_to_user_id[email.lower()] = uid
                if phone:
                    self.phone_to_user_id[phone] = uid
                if email_hash:
                    self.hash_to_user_id[email_hash.lower()] = uid

    def _load_audit_logs(self) -> None:
        audit_file = self.dataset_dir / "user_audit_log.csv"
        if not audit_file.exists():
            return

        with open(audit_file, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                aid = row["audit_id"].strip()
                uid = row["user_id"].strip()
                event_time = row["event_time"].strip()
                field_name = row["field_name"].strip()
                old_val = row["old_value"].strip()
                new_val = row["new_value"].strip()

                link = IdentityLink(
                    field_name=field_name,
                    old_value=old_val,
                    new_value=new_val,
                    event_time=event_time,
                    audit_id=aid,
                )

                if uid not in self.users_by_id:
                    # Synthetic entry if not in primary snapshot
                    self.users_by_id[uid] = UserProfile(
                        user_id=uid,
                        current_name="",
                        current_email="",
                        current_phone="",
                        current_email_hash="",
                        updated_at=event_time,
                    )

                profile = self.users_by_id[uid]
                profile.audit_links.append(link)

                if field_name == "email":
                    if old_val:
                        profile.historical_emails.add(old_val)
                        self.email_to_user_id[old_val.lower()] = uid
                    if new_val:
                        self.email_to_user_id[new_val.lower()] = uid
                elif field_name == "phone":
                    if old_val:
                        profile.historical_phones.add(old_val)
                        self.phone_to_user_id[old_val] = uid
                    if new_val:
                        self.phone_to_user_id[new_val] = uid
                elif field_name == "email_hash":
                    if old_val:
                        profile.historical_hashes.add(old_val)
                        self.hash_to_user_id[old_val.lower()] = uid
                    if new_val:
                        self.hash_to_user_id[new_val.lower()] = uid

    def resolve_by_email(self, email: str) -> Optional[UserProfile]:
        """Resolve a user profile given a current or historical email."""
        clean_email = email.strip().lower()
        uid = self.email_to_user_id.get(clean_email)
        if uid:
            return self.users_by_id.get(uid)
        return None

    def resolve_by_user_id(self, user_id: str) -> Optional[UserProfile]:
        """Resolve a user profile given user_id."""
        return self.users_by_id.get(user_id.strip())

    def resolve_by_phone(self, phone: str) -> Optional[UserProfile]:
        """Resolve a user profile given phone."""
        uid = self.phone_to_user_id.get(phone.strip())
        if uid:
            return self.users_by_id.get(uid)
        return None

    def resolve_by_hash(self, email_hash: str) -> Optional[UserProfile]:
        """Resolve a user profile given email hash."""
        uid = self.hash_to_user_id.get(email_hash.strip().lower())
        if uid:
            return self.users_by_id.get(uid)
        return None
