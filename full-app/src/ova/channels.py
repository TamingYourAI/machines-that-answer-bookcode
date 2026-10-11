"""Channels around the call: texts and email as steps in the work.

Say it, then send it: the agent says what it is sending and to where ("I've texted the link to
the mobile ending four two one seven"), and the message goes out as an operation that can fail
and be retried. A message is an action. Every message is written to the store first, so the
console and the caller's view show it even when no provider is configured (the simulated
outbox), and a live call hears about a reply or an upload as soon as it arrives.
"""
from __future__ import annotations

import asyncio
import smtplib
import ssl
import uuid
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Awaitable, Callable, Protocol

from .store import Store


@dataclass
class Message:
    id: str
    call_id: str | None
    channel: str                # sms | email
    to: str
    body: str
    subject: str = ""
    status: str = "queued"      # queued | sent | simulated | failed
    provider_id: str = ""


class Sender(Protocol):
    name: str

    async def send(self, m: Message) -> str:
        """Deliver the message; return the provider's id. Raise on failure."""
        ...


class SimulatedSender:
    """No provider configured: the message is recorded and shown, not delivered."""
    name = "simulated"

    async def send(self, m: Message) -> str:
        return "sim-" + m.id


class TwilioSms:
    """Twilio Programmable Messaging (REST, form-encoded). Written to the docs; tested against
    a fake in tests/test_providers.py."""
    name = "twilio-sms"

    def __init__(self, account_sid: str, auth_token: str, from_number: str,
                 client=None, base_url: str = "https://api.twilio.com"):
        self.sid, self.token, self.from_number = account_sid, auth_token, from_number
        self.base_url, self.client = base_url, client

    async def send(self, m: Message) -> str:
        import httpx
        client = self.client or httpx.AsyncClient(timeout=10)
        try:
            r = await client.post(
                f"{self.base_url}/2010-04-01/Accounts/{self.sid}/Messages.json",
                data={"To": m.to, "From": self.from_number, "Body": m.body},
                auth=(self.sid, self.token))
            r.raise_for_status()
            return r.json().get("sid", "")
        finally:
            if self.client is None:
                await client.aclose()


class SmtpEmail:
    """Plain SMTP with STARTTLS. Standard library."""
    name = "smtp"

    def __init__(self, host: str, port: int, user: str, password: str, from_addr: str):
        self.host, self.port, self.user, self.password = host, port, user, password
        self.from_addr = from_addr

    def _send_sync(self, m: Message) -> str:
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = self.from_addr, m.to, m.subject or "Message"
        msg.set_content(m.body)
        with smtplib.SMTP(self.host, self.port, timeout=15) as s:
            s.starttls(context=ssl.create_default_context())
            if self.user:
                s.login(self.user, self.password)
            s.send_message(msg)
        return msg.get("Message-ID", "") or m.id

    async def send(self, m: Message) -> str:
        return await asyncio.to_thread(self._send_sync, m)


Listener = Callable[[Message], Awaitable[None] | None]


class Channels:
    def __init__(self, store: Store, sms: Sender | None = None, email: Sender | None = None):
        self.store = store
        self.sms = sms or SimulatedSender()
        self.email = email or SimulatedSender()
        self.listeners: list[Listener] = []

    def subscribe(self, fn: Listener) -> Callable[[], None]:
        self.listeners.append(fn)
        return lambda: self.listeners.remove(fn) if fn in self.listeners else None

    async def _deliver(self, m: Message, sender: Sender) -> Message:
        self.store.add_message(m.id, m.call_id, m.channel, m.to, m.body, "queued",
                               meta={"subject": m.subject})
        try:
            m.provider_id = await sender.send(m)
            m.status = "simulated" if sender.name == "simulated" else "sent"
        except Exception as e:                       # noqa: BLE001 - reported, then retried
            m.status = "failed"
            m.provider_id = type(e).__name__
        self.store.add_message(m.id, m.call_id, m.channel, m.to, m.body, m.status,
                               m.provider_id, meta={"subject": m.subject,
                                                    "via": sender.name})
        for fn in list(self.listeners):
            r = fn(m)
            if asyncio.iscoroutine(r):
                await r
        return m

    async def send_text(self, call_id: str | None, to: str, body: str) -> Message:
        m = Message("msg-" + uuid.uuid4().hex[:10], call_id, "sms", to, body)
        return await self._deliver(m, self.sms)

    async def send_email(self, call_id: str | None, to: str, subject: str, body: str
                         ) -> Message:
        m = Message("msg-" + uuid.uuid4().hex[:10], call_id, "email", to, body, subject)
        return await self._deliver(m, self.email)
