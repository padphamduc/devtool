import copy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


class WatcherTests(unittest.IsolatedAsyncioTestCase):
    async def test_failed_delivery_retries_then_deduplicates(self):
        from AUTO_CHECK_MESSENGER.app import watcher, storage
        instance = watcher.Watcher()
        item = SimpleNamespace(source="inbox", sender="Test", href="test-thread", preview="Xin chào", age_minutes=1)
        instance.client = SimpleNamespace(scan_inbox=AsyncMock(return_value=[item]), scan_requests=AsyncMock(return_value=[]), scan_spam=AsyncMock(return_value=[]))
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(storage, "DB_PATH", Path(directory) / "messages.db"), \
             patch.object(watcher, "CHECK_NOTIFICATIONS", False), \
             patch.object(watcher, "send_notification", new_callable=AsyncMock) as send:
            send.side_effect = RuntimeError("API unavailable")
            with self.assertRaises(RuntimeError):
                await instance._scan_once()
            self.assertIsNone(storage.get_thread_state(item.source, item.sender, item.href))
            send.side_effect = None
            await instance._scan_once()
            await instance._scan_once()
            self.assertEqual(send.await_count, 2)
            self.assertEqual(instance.notifications_sent, 1)
            # Existing sqlite helpers rely on GC to release their connections on Windows.
            import gc
            gc.collect()


class SettingsTests(unittest.TestCase):
    def test_activation_status_and_machine_code(self):
        import tkinter as tk
        import ductool_app as ui
        import ductool_license as license
        root = tk.Tk()
        root.withdraw()
        try:
            with patch.object(license, 'get_hwid', return_value='DUC-1111-2222-3333'), \
                 patch.object(license, 'get_saved_key', return_value=''), \
                 patch.object(ui.threading, 'Thread') as thread:
                window = ui.ActivationWindow(root)
                window.withdraw()
                self.assertEqual(window.hwid, 'DUC-1111-2222-3333')
                window.check_now()
                thread.assert_not_called()
                window.key_var.set('TEST')
                window.check_now()
                self.assertEqual(window.check_status_var.get(), 'Kiểm tra key')
                thread.assert_called_once()
                window.destroy()
        finally:
            root.destroy()

    def test_channel_buttons_and_save_preserve_both_credentials(self):
        import tkinter as tk
        import ductool_app as ui
        from ductool_config import DEFAULT_CONFIG
        cfg = copy.deepcopy(DEFAULT_CONFIG)
        root = tk.Tk()
        root.withdraw()
        root.status_var = tk.StringVar(master=root)
        root._button = lambda parent, text, command, **kwargs: tk.Button(parent, text=text, command=command)
        try:
            with patch.object(ui, "load_config", return_value=cfg), \
                 patch.object(ui, "save_config") as save, \
                 patch.object(ui.messagebox, "showinfo"):
                window = ui.SettingsWindow(root, "messenger")
                window.withdraw()
                def descendants(widget):
                    for child in widget.winfo_children():
                        yield child
                        yield from descendants(child)
                radios = [child for child in descendants(window) if isinstance(child, tk.Radiobutton)]
                self.assertEqual([r.cget("text") for r in radios], ["Telegram", "Zalo"])
                self.assertEqual(window.vars["messenger.notification_provider"].get(), "telegram")
                self.assertEqual(window.channel_cards["telegram"].winfo_manager(), "pack")
                self.assertEqual(window.channel_cards["zalo"].winfo_manager(), "")
                radios[1].invoke()
                self.assertEqual(window.channel_cards["telegram"].winfo_manager(), "")
                self.assertEqual(window.channel_cards["zalo"].winfo_manager(), "pack")
                for provider in ("telegram", "zalo"):
                    window.vars[f"messenger.{provider}_bot_token"].set(f"{provider}-test-token")
                    window.vars[f"messenger.{provider}_chat_id"].set(f"{provider}-chat")
                with patch.object(ui, "get_zalo_chat", new_callable=AsyncMock, return_value="received-chat") as lookup:
                    window.zalo_lookup_button.invoke()
                    root.after(300, root.quit)
                    root.mainloop()
                    lookup.assert_awaited_once_with("zalo-test-token")
                    self.assertEqual(window.vars["messenger.zalo_chat_id"].get(), "received-chat")
                    self.assertFalse(window._zalo_lookup_running)
                    save.assert_not_called()
                window.save()
                saved = save.call_args.args[0]["messenger"]
                self.assertEqual(saved["notification_provider"], "zalo")
                self.assertEqual(saved["telegram_bot_token"], "telegram-test-token")
                self.assertEqual(saved["zalo_chat_id"], "received-chat")
                radios[0].invoke()
                self.assertEqual(window.channel_cards["telegram"].winfo_manager(), "pack")
                self.assertEqual(window.channel_cards["zalo"].winfo_manager(), "")
                window.save()
                self.assertEqual(save.call_args.args[0]["messenger"]["notification_provider"], "telegram")
                window.destroy()
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
