import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from AUTO_CHECK_MESSENGER.app.messenger import MessengerClient


class SenderTests(unittest.IsolatedAsyncioTestCase):
    async def extract(self, raw, source='inbox', href='/t/test-thread'):
        item = SimpleNamespace(
            is_visible=AsyncMock(return_value=True),
            get_attribute=AsyncMock(return_value=href),
            inner_text=AsyncMock(return_value=raw),
        )
        client = MessengerClient()
        client.page = SimpleNamespace(
            locator=Mock(return_value=SimpleNamespace(all=AsyncMock(return_value=[item])))
        )
        return await client._extract(source)

    async def test_reported_attachment_uses_name_in_all_inboxes(self):
        for source in ('inbox', 'requests', 'spam'):
            items = await self.extract('Đang hoạt động\nĐào Đức\nĐức đã gửi một file đính kèm\n1 phút', source)
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].sender, 'Đào Đức')
            self.assertEqual(items[0].preview, 'Đức đã gửi một file đính kèm')
            self.assertEqual(items[0].age_minutes, 1)

    async def test_bullet_and_emoji_presence_stripped(self):
        for badge in ('• Đang hoạt động', '· Đang hoạt động', '🟢 Đang hoạt động', 'Đang hoạt động ·'):
            items = await self.extract(f'{badge}\nĐào Đức\nĐức đã gửi một file đính kèm\n1 phút')
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].sender, 'Đào Đức')
            self.assertEqual(items[0].preview, 'Đức đã gửi một file đính kèm')

    async def test_presence_after_sender_name_removed_from_preview(self):
        items = await self.extract('Đào Đức\nĐang hoạt động\nĐức đã gửi một file đính kèm\n1 phút')
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].sender, 'Đào Đức')
        self.assertEqual(items[0].preview, 'Đức đã gửi một file đính kèm')

    async def test_presence_age_is_not_message_age(self):
        for badge in ('Hoạt động 5 phút trước', 'Đang hoạt động', 'Active now', 'Active 5m ago', 'Hoạt động hôm qua'):
            items = await self.extract(f'{badge}\nĐào Đức\nXin chào\n20 phút')
            self.assertEqual(items[0].sender, 'Đào Đức')
            self.assertEqual(items[0].age_minutes, 20)
        items = await self.extract('Active now\nĐào Đức\nXin chào')
        self.assertIsNone(items[0].age_minutes)

    async def test_normal_sender_and_status_words_in_message_preserved(self):
        items = await self.extract('Đào Đức\nĐang hoạt động\n2 phút')
        self.assertEqual(items[0].sender, 'Đào Đức')
        self.assertEqual(items[0].preview, 'Đang hoạt động')

    async def test_badge_only_and_outgoing_skipped(self):
        self.assertEqual(await self.extract('Đang hoạt động'), [])
        self.assertEqual(await self.extract('Đang hoạt động\nĐào Đức\nBạn đã gửi một file\n1 phút'), [])

    async def test_focus_target_and_non_thread_links_skipped(self):
        # focus_target link should be ignored
        res1 = await self.extract('Đoạn chat · 1 tin nhắn chưa đọc', href='/t/123/?focus_target=1')
        self.assertEqual(res1, [])

        # non-thread Facebook profile/share link should be ignored
        res2 = await self.extract('Đang hoạt động\nĐào Đức', href='https://www.facebook.com/100011723794038/')
        self.assertEqual(res2, [])


if __name__ == '__main__':
    unittest.main()
