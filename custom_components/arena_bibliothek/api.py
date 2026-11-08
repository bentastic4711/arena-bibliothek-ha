"""Lesender Zugriff auf ein Axiell-Arena-Bibliothekskonto.

Arena ist ein Liferay-Portal mit Apache-Wicket-Portlets. Die Formular-Action
des Login-Portlets enthaelt eine sitzungsabhaengige Wicket-Interface-ID und
kann deshalb nicht fest hinterlegt werden - sie wird bei jeder Anmeldung neu
von der Startseite gelesen.

Das Modul laesst sich auch direkt aufrufen, um Zugangsdaten zu testen:

    python3 api.py --base-url https://beispiel.arena.axiell.de \
        --username 12345 --password geheim
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

_LOGGER = logging.getLogger(__name__)

TIMEOUT = 30
ACCOUNT_PATH = "/protected/my-account/overview"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

DATE_RE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})")
INT_RE = re.compile(r"(\d+)")

# Marker im HTML: das Login-Portlet rendert das Formular nur im abgemeldeten
# Zustand. Angemeldet steht dort stattdessen ein Hinweistext.
LOGIN_FORM_MARKER = "signInForm"


class ArenaError(Exception):
    """Abruf fehlgeschlagen."""


class ArenaAuthError(ArenaError):
    """Anmeldung mit Ausweisnummer und Passwort fehlgeschlagen."""


def _parse_date(text: str) -> date | None:
    """'05.12.26' oder '05.12.2026' in ein date umwandeln."""
    match = DATE_RE.search(text or "")
    if not match:
        return None
    day, month, year = (int(part) for part in match.groups())
    if year < 100:
        year += 2000
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _clean(text: str | None) -> str | None:
    if not text:
        return None
    collapsed = " ".join(text.split())
    return collapsed or None


@dataclass(slots=True)
class Loan:
    """Ein ausgeliehenes Medium."""

    title: str
    record_id: str | None = None
    authors: list[str] = field(default_factory=list)
    media_type: str | None = None
    year: str | None = None
    due_date: date | None = None
    renewals_left: int | None = None
    renewable: bool = False
    overdue: bool = False
    branch: str | None = None
    note: str | None = None

    @property
    def author(self) -> str | None:
        """Alle Urheber als ein String, fuer Benachrichtigungen."""
        return ", ".join(self.authors) if self.authors else None

    @property
    def days_left(self) -> int | None:
        """Tage bis zur Rueckgabe, negativ wenn ueberfaellig."""
        if self.due_date is None:
            return None
        return (self.due_date - date.today()).days

    def as_dict(self) -> dict[str, Any]:
        """Darstellung fuer Entity-Attribute (JSON-tauglich)."""
        return {
            "title": self.title,
            "author": self.author,
            "authors": self.authors,
            "media_type": self.media_type,
            "year": self.year,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "days_left": self.days_left,
            "renewable": self.renewable,
            "renewals_left": self.renewals_left,
            "overdue": self.overdue,
            "branch": self.branch,
            "note": self.note,
            "record_id": self.record_id,
        }


def parse_loans(html: str) -> list[Loan]:
    """Die Ausleihtabelle der Kontoseite in Loan-Objekte umwandeln."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table.arena-renewal-table")
    if table is None:
        # Ohne Ausleihen rendert Arena die Tabelle gar nicht erst.
        return []

    # Achtung: Arena liefert die Tabelle OHNE <tbody>. Browser ergaenzen das
    # beim Parsen automatisch, BeautifulSoups html.parser nicht - ein Selektor
    # "tbody tr" findet hier also nichts.
    rows = table.select("tr[id^='loan-row-id']")
    if not rows:
        rows = [
            row
            for row in table.find_all("tr")
            if row.find("td", class_="arena-renewal-loan") is not None
        ]
    if not rows:
        _LOGGER.warning(
            "Ausleihtabelle gefunden, aber keine Zeilen erkannt - "
            "vermutlich hat sich das Arena-Markup geaendert"
        )

    loans: list[Loan] = []
    for row in rows:
        classes = row.get("class") or []
        title_el = row.select_one(".arena-record-title a span") or row.select_one(
            ".arena-record-title"
        )
        title = _clean(title_el.get_text() if title_el else None)
        if not title:
            continue

        authors: list[str] = []
        for author_el in row.select(".arena-record-author"):
            # Steht als "Ersteller/-in: Nachname, Vorname" bzw. "Autor:in ..." da.
            text = _clean(author_el.get_text())
            if not text:
                continue
            text = re.sub(r"^(Ersteller/-in|Autor:in|Verfasser:in)\s*:?\s*", "", text)
            if text:
                authors.append(text)

        media_el = row.select_one(".arena-record-media .arena-value")
        year_el = row.select_one(".arena-record-year .arena-value")
        note_el = row.select_one(".arena-renewal-notes .arena-value")
        branch_el = row.select_one(".arena-renewal-branch")
        date_el = row.select_one(".arena-renewal-date-value") or row.select_one(
            "td.arena-renewal-date"
        )
        status_el = row.select_one("td.arena-renewal-status")

        renewals_left: int | None = None
        if status_el is not None:
            match = INT_RE.search(status_el.get_text())
            if match:
                renewals_left = int(match.group(1))

        branch = _clean(branch_el.get_text() if branch_el else None)
        if branch:
            branch = re.sub(r"^Abholungsort:\s*", "", branch)

        record_el = row.select_one(".arena-record-id")

        loans.append(
            Loan(
                title=title,
                record_id=_clean(record_el.get_text() if record_el else None),
                authors=authors,
                media_type=_clean(media_el.get_text() if media_el else None),
                year=_clean(year_el.get_text() if year_el else None),
                due_date=_parse_date(date_el.get_text() if date_el else ""),
                renewals_left=renewals_left,
                renewable="arena-renewal-true" in classes,
                overdue="arena-loan-overdue-true" in classes,
                branch=branch,
                note=_clean(note_el.get_text() if note_el else None),
            )
        )

    return loans


class ArenaClient:
    """Meldet sich am Arena-Portal an und liest die Ausleihen."""

    def __init__(self, base_url: str, username: str, password: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._username = username
        self._password = password
        self._session: requests.Session | None = None

    # -- intern ---------------------------------------------------------

    def _new_session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update(
            {"User-Agent": USER_AGENT, "Accept-Language": "de-DE,de;q=0.9"}
        )
        # Liferay prueft teilweise, ob der Client Cookies unterstuetzt.
        session.cookies.set("COOKIE_SUPPORT", "true")
        session.cookies.set("GUEST_LANGUAGE_ID", "de_DE")
        return session

    @staticmethod
    def _is_logged_in(html: str) -> bool:
        return LOGIN_FORM_MARKER not in html

    def _login(self, session: requests.Session) -> None:
        """Startseite holen, Login-Formular auslesen, Zugangsdaten posten."""
        try:
            start = session.get(self._base_url + "/", timeout=TIMEOUT)
            start.raise_for_status()
        except requests.RequestException as err:
            raise ArenaError(f"Startseite nicht erreichbar: {err}") from err

        soup = BeautifulSoup(start.text, "html.parser")
        form = next(
            (
                candidate
                for candidate in soup.find_all("form")
                if "patronLogin" in (candidate.get("action") or "")
            ),
            None,
        )
        if form is None:
            raise ArenaError(
                "Login-Formular nicht gefunden - vermutlich hat Arena sein "
                "Layout geaendert oder die Basis-URL stimmt nicht."
            )

        payload: dict[str, str] = {}
        for element in form.find_all("input"):
            name = element.get("name")
            if not name or (element.get("type") or "text").lower() == "submit":
                continue
            payload[name] = element.get("value") or ""

        user_field = next(
            (name for name in payload if name.endswith("openTextUsername")), None
        )
        password_field = next(
            (name for name in payload if "password" in name.lower()), None
        )
        if not user_field or not password_field:
            raise ArenaError("Felder fuer Ausweisnummer/Passwort nicht gefunden.")

        payload[user_field] = self._username
        payload[password_field] = self._password

        action = urljoin(start.url, form["action"])
        try:
            response = session.post(
                action, data=payload, timeout=TIMEOUT, headers={"Referer": start.url}
            )
            response.raise_for_status()
        except requests.RequestException as err:
            raise ArenaError(f"Anmeldung fehlgeschlagen: {err}") from err

    def _account_html(self, session: requests.Session) -> str:
        try:
            response = session.get(self._base_url + ACCOUNT_PATH, timeout=TIMEOUT)
            response.raise_for_status()
        except requests.RequestException as err:
            raise ArenaError(f"Kontoseite nicht erreichbar: {err}") from err
        return response.text

    # -- oeffentlich ----------------------------------------------------

    def fetch_loans(self) -> list[Loan]:
        """Ausleihen abrufen, bei Bedarf vorher neu anmelden.

        Blockierend - in Home Assistant ueber async_add_executor_job aufrufen.
        """
        if self._session is not None:
            html = self._account_html(self._session)
            if self._is_logged_in(html):
                return parse_loans(html)
            _LOGGER.debug("Arena-Sitzung abgelaufen, melde neu an")

        session = self._new_session()
        self._login(session)
        html = self._account_html(session)
        if not self._is_logged_in(html):
            self._session = None
            raise ArenaAuthError(
                "Anmeldung abgelehnt - Ausweisnummer oder Passwort pruefen."
            )

        self._session = session
        loans = parse_loans(html)
        _LOGGER.debug("%d Ausleihen aus %d Zeichen HTML gelesen", len(loans), len(html))
        return loans


def _main() -> int:
    """Kommandozeilen-Test ausserhalb von Home Assistant."""
    import argparse

    parser = argparse.ArgumentParser(description="Arena-Bibliothekskonto auslesen")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG)
    client = ArenaClient(args.base_url, args.username, args.password)
    try:
        loans = client.fetch_loans()
    except ArenaError as err:
        print(f"Fehler: {err}")
        return 1

    if not loans:
        print("Keine Ausleihen gefunden.")
        return 0

    for loan in sorted(loans, key=lambda item: item.due_date or date.max):
        due = loan.due_date.strftime("%d.%m.%Y") if loan.due_date else "?"
        flag = " UEBERFAELLIG" if loan.overdue else ""
        print(f"{due}  {loan.title}  ({loan.media_type or '-'}){flag}")
        print(
            f"          Verlaengerungen uebrig: {loan.renewals_left}, "
            f"verlaengerbar: {loan.renewable}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
