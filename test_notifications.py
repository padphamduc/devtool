import unittest
from unittest.mock import patch
import httpx

import ductool_notifications as notifications


class DeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_zalo_lookup_uses_incoming_chat_not_sender_id(self):
        import json
        def handler(request):
            self.assertEqual(request.method, "POST")
            self.assertEqual(request.url.path, "/bottest-secret/getUpdates")
            self.assertEqual(json.loads(request.content), {"timeout": 30})
            return httpx.Response(200, json={"ok": True, "result": {"message": {
                "chat": {"id": "group-chat", "chat_type": "GROUP"}, "from": {"id": "sender-id"}}}})
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with patch.object(notifications.httpx, "AsyncClient", return_value=client):
            self.assertEqual(await notifications.get_zalo_chat("test-secret"), "group-chat")

    async def test_zalo_lookup_errors_preserve_token_privacy(self):
        responses = [httpx.Response(200, json={"ok": True, "result": {}}),
                     httpx.Response(200, text="invalid JSON"),
                     httpx.Response(409, json={"ok": False, "description": "webhook test-secret"})]
        for response in responses:
            client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: response))
            with patch.object(notifications.httpx, "AsyncClient", return_value=client):
                with self.assertRaises(RuntimeError) as error:
                    await notifications.get_zalo_chat("test-secret")
                self.assertNotIn("test-secret", str(error.exception))
        def timeout(request):
            raise httpx.ReadTimeout(str(request.url), request=request)
        client = httpx.AsyncClient(transport=httpx.MockTransport(timeout))
        with patch.object(notifications.httpx, "AsyncClient", return_value=client):
            with self.assertRaisesRegex(RuntimeError, "Chưa nhận được tin nhắn"):
                await notifications.get_zalo_chat("test-secret")

    async def deliver(self, settings, handler, text="Xin chào"):
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with patch.object(notifications.httpx, "AsyncClient", return_value=client):
            return await notifications.send_notification(text, settings)

    async def test_default_telegram_and_zalo_routing(self):
        for provider, host in (("telegram", "api.telegram.org"), ("zalo", "bot-api.zaloplatforms.com")):
            settings = {f"{provider}_bot_token": "test-secret", f"{provider}_chat_id": "abc.xyz"}
            if provider == "zalo":
                settings["notification_provider"] = provider
            def handler(request):
                self.assertEqual(request.url.host, host)
                self.assertEqual(request.method, "POST")
                self.assertIn(b'"chat_id":"abc.xyz"', request.content)
                return httpx.Response(200, json={"ok": True})
            await self.deliver(settings, handler)

    async def test_zalo_chunks_preserve_unicode(self):
        import json
        parts = []
        def handler(request):
            part = json.loads(request.content)["text"]
            self.assertLessEqual(len(part.encode("utf-16-le")) // 2, 2000)
            parts.append(part)
            return httpx.Response(200, json={"ok": True})
        text = "Xin chào 😀\n" * 600
        await self.deliver({"notification_provider": "zalo", "zalo_bot_token": "secret", "zalo_chat_id": "id"}, handler, text)
        self.assertEqual("".join(parts), text)
        self.assertGreater(len(parts), 1)

    async def test_failures_and_token_redaction(self):
        settings = {"telegram_bot_token": "secret", "telegram_chat_id": "id"}
        for response in (httpx.Response(200, json={"ok": False, "description": "bad secret"}),
                         httpx.Response(401, json={"ok": False}),
                         httpx.Response(200, text="not JSON")):
            with self.assertRaises(RuntimeError) as error:
                await self.deliver(settings, lambda request: response)
            self.assertNotIn("secret", str(error.exception))
        def failure(request):
            raise httpx.ConnectError(str(request.url), request=request)
        with self.assertRaises(RuntimeError) as error:
            await self.deliver(settings, failure)
        self.assertNotIn("secret", str(error.exception))

    async def test_missing_selected_credentials_does_not_fallback(self):
        with self.assertRaisesRegex(RuntimeError, "Zalo Bot Token"):
            await notifications.send_notification("test", {"notification_provider": "zalo", "telegram_bot_token": "secret", "telegram_chat_id": "id"})

    async def test_running_sender_reloads_channel(self):
        configs = [{"messenger": {"telegram_bot_token": "t", "telegram_chat_id": "id"}},
                   {"messenger": {"notification_provider": "zalo", "zalo_bot_token": "z", "zalo_chat_id": "id"}}]
        hosts = []
        def handler(request):
            hosts.append(request.url.host)
            return httpx.Response(200, json={"ok": True})
        with patch.object(notifications, "load_config", side_effect=configs):
            await self.deliver(None, handler)
            await self.deliver(None, handler)
        self.assertEqual(hosts, ["api.telegram.org", "bot-api.zaloplatforms.com"])


if __name__ == "__main__":
    unittest.main()
