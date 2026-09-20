"""La connexion par QR : les méthodes de QRLogin sont des coroutines.

Les appeler sans les attendre renvoyait un objet toujours vrai — le script
croyait la connexion réussie et plantait plus loin sur un `me` à None.
"""

import asyncio

import pytest

from scripts.telegram_login import qr_login, run_sync


class FakeLogin:
    url = "tg://login?token=demo"

    def __init__(self, scans_avant_succes=0):
        self.restant = scans_avant_succes
        self.recreations = 0

    async def wait(self, timeout=None):
        if self.restant > 0:
            self.restant -= 1
            raise TimeoutError
        return True

    async def recreate(self):
        self.recreations += 1


class FakeClient:
    def __init__(self, login):
        self.loop = asyncio.new_event_loop()
        self._login = login

    def qr_login(self):
        return self._login


def test_le_scan_reussi_termine_la_connexion(capsys):
    client = FakeClient(FakeLogin())
    qr_login(client)
    assert client._login.recreations == 0
    assert "Scanne ce QR" in capsys.readouterr().out


def test_un_qr_expire_est_regenere(capsys):
    client = FakeClient(FakeLogin(scans_avant_succes=2))
    qr_login(client)
    assert client._login.recreations == 2
    assert capsys.readouterr().out.count("QR expiré") == 2


def test_abandon_apres_dix_qr_ignores():
    client = FakeClient(FakeLogin(scans_avant_succes=99))
    with pytest.raises(SystemExit):
        qr_login(client)
    assert client._login.recreations == 10


def test_run_sync_attend_vraiment_la_coroutine():
    client = FakeClient(FakeLogin())

    async def coro():
        return "résultat"

    assert run_sync(client, coro()) == "résultat"
