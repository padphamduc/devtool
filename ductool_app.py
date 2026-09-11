
from __future__ import annotations


from pathlib import Path
import os
import subprocess
import sys
import threading
import time
import asyncio
from ductool_notifications import send_notification, get_zalo_chat
import queue
import urllib.request
import urllib.parse
import json
import tkinter as tk
from tkinter import filedialog, messagebox

from ductool_config import ensure_config, load_config, save_config, CONFIG_PATH, app_root, sheet_csv_from_edit_url
from ductool_updater import CURRENT_VERSION, check_update_status, perform_auto_replace
from PIL import Image, ImageTk

ASSETS_DIR = Path(__file__).resolve().parent / "assets"

ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent

# ===== THEME =====
BG = "#0B0F16"
TOP = "#111722"
PANEL = "#151C28"
PANEL2 = "#192231"
BORDER = "#2B3648"
TEXT = "#F8FAFC"
MUTED = "#A6B1C3"
PURPLE = "#8B5CF6"
PURPLE_HOVER = "#7C3AED"
BLUE = "#4F86FF"
GREEN = "#34D399"
BTN_DARK = "#2A3445"
BTN_DARK_HOVER = "#364258"
INPUT = "#0E1520"
DANGER = "#EF4444"


def ensure_console(title="DUCTOOL"):
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.kernel32.AllocConsole()
            ctypes.windll.kernel32.SetConsoleTitleW(title)
            sys.stdout = open("CONOUT$", "w", encoding="utf-8", errors="replace")
            sys.stderr = open("CONOUT$", "w", encoding="utf-8", errors="replace")
            sys.stdin = open("CONIN$", "r", encoding="utf-8", errors="replace")
        except Exception:
            pass


PATCH_PATHS = [
    Path(r"C:\duc\code"),
    (Path(sys.executable).resolve().parent / "code") if getattr(sys, "frozen", False) else None,
]

def _inject_patch_paths():
    if not getattr(sys, "frozen", False):
        # Running this source checkout must use its modules, not an older C:\duc\code patch.
        return
    for p in PATCH_PATHS:
        if p and p.exists() and str(p) not in sys.path:
            sys.path.insert(0, str(p))

_inject_patch_paths()


def run_facebook_module():
    ensure_console("DUCTOOL — Auto Đăng Bài Facebook")
    _inject_patch_paths()
    from ductool_license import verify_license_or_exit
    verify_license_or_exit("Auto Đăng Bài Facebook")
    base = Path(__file__).resolve().parent
    if str(base) not in sys.path:
        sys.path.insert(0, str(base))
    from AUTO_DANG_BAI_FACEBOOK.main import guarded_main
    sys.exit(guarded_main())


def run_messenger_module():
    ensure_console("DUCTOOL — Messenger to Telegram / Zalo")
    _inject_patch_paths()
    from ductool_license import verify_license_or_exit
    verify_license_or_exit("Messenger to Telegram / Zalo")
    base = Path(__file__).resolve().parent
    msg_dir = base / "AUTO_CHECK_MESSENGER"
    if str(base) not in sys.path:
        sys.path.insert(0, str(base))
    if str(msg_dir) not in sys.path:
        sys.path.insert(0, str(msg_dir))
    from AUTO_CHECK_MESSENGER.run import run_messenger_main
    run_messenger_main()


def run_group_collector_module():
    ensure_console("DUCTOOL — Lấy Danh Sách Group Facebook")
    _inject_patch_paths()
    from ductool_license import verify_license_or_exit
    verify_license_or_exit("Lấy Danh Sách Group")
    base = Path(__file__).resolve().parent
    if str(base) not in sys.path:
        sys.path.insert(0, str(base))
    from AUTO_GROUP_COLLECTOR.main import main as collector_main
    collector_main()


def run_group_join_module():
    ensure_console("DUCTOOL — Auto Tham Gia Group Facebook")
    _inject_patch_paths()
    from ductool_license import verify_license_or_exit
    verify_license_or_exit("Auto Tham Gia Group")
    base = Path(__file__).resolve().parent
    if str(base) not in sys.path:
        sys.path.insert(0, str(base))
    from AUTO_GROUP_JOIN.main import async_main
    import asyncio
    asyncio.run(async_main())


def run_image_renamer_module():
    _inject_patch_paths()
    from ductool_license import verify_license_or_exit
    verify_license_or_exit("Đổi Tên Ảnh Hàng Loạt")
    base = Path(__file__).resolve().parent
    if str(base) not in sys.path:
        sys.path.insert(0, str(base))
    from ductool_image_renamer import main as renamer_main
    renamer_main()


def run_hidden(cmd, cwd=None):
    return subprocess.Popen(
        cmd,
        cwd=str(cwd) if cwd else None,
        creationflags=(getattr(subprocess, "CREATE_NEW_CONSOLE", 0) if os.name == "nt" else 0),
    )


class App(tk.Tk):

    def _load_brand_logo(self, size=(82, 82)):
        try:
            img = Image.open(ASSETS_DIR / "logo.png").convert("RGBA")
            img.thumbnail(size, Image.LANCZOS)
            self._ductool_logo_img = ImageTk.PhotoImage(img)
            return self._ductool_logo_img
        except Exception:
            return None


    def __init__(self):
        super().__init__()
        self.title("Đức Tool Launcher")
        try:
            self.iconbitmap(str(ASSETS_DIR / "logo.ico"))
        except Exception:
            pass
        self.geometry("980x700")
        self.minsize(900, 620)
        self.configure(bg=BG)

        self.cfg = ensure_config()
        self.status_var = tk.StringVar(value="Sẵn sàng")
        self.license_info = {}
        self.is_licensed = False
        self.license_status_var = tk.StringVar(value="Bản quyền: Đang kiểm tra...")
        self.force_update_active = False

        self._build_header()
        self._build_body()
        self._build_footer()

        # Kiểm tra bản quyền ngầm sau khi tải giao diện
        self.after(350, lambda: self._check_license_async(show_modal_if_invalid=False))
        # Kiểm tra cập nhật tự động & bắt buộc
        self.after(800, lambda: self._check_update_startup())

    # ---------- Header ----------
    def _build_header(self):
        top = tk.Frame(self, bg=TOP, height=125)
        top.pack(fill="x")
        top.pack_propagate(False)

        left = tk.Frame(top, bg=TOP)
        left.pack(side="left", padx=28, pady=18)

        brand_logo = self._load_brand_logo((72, 72))
        if brand_logo:
            tk.Label(left, image=brand_logo, bg=TOP, bd=0).pack(side="left")
        else:
            tk.Label(left, text="Đ", bg=TOP, fg=TEXT, font=("Segoe UI", 24, "bold")).pack(side="left")

        title_wrap = tk.Frame(left, bg=TOP)
        title_wrap.pack(side="left", padx=14)
        tk.Label(
            title_wrap, text="ĐỨC TOOL", bg=TOP, fg=TEXT,
            font=("Segoe UI", 25, "bold")
        ).pack(anchor="w")
        tk.Label(
            title_wrap, text=f"Dynamic Launcher  •  v{CURRENT_VERSION}", bg=TOP, fg="#B8C2D2",
            font=("Segoe UI", 11)
        ).pack(anchor="w", pady=(4, 0))

        right = tk.Frame(top, bg=TOP)
        right.pack(side="right", padx=28, pady=28)
        self._button(
            right, "⟳  Kiểm tra cập nhật", self.check_update, accent=True, width=19
        ).pack()

    # ---------- Body ----------
    def _build_body(self):
        main_scroll = tk.Frame(self, bg=BG)
        main_scroll.pack(fill="both", expand=True)

        main_canvas = tk.Canvas(
            main_scroll, bg=BG, highlightthickness=0, bd=0
        )
        main_scrollbar = tk.Scrollbar(
            main_scroll, orient="vertical", command=main_canvas.yview
        )
        main_canvas.configure(yscrollcommand=main_scrollbar.set)

        main_scrollbar.pack(side="right", fill="y")
        main_canvas.pack(side="left", fill="both", expand=True)

        wrap = tk.Frame(main_canvas, bg=BG)
        main_window = main_canvas.create_window(
            (0, 0), window=wrap, anchor="nw"
        )

        def _sync_main_scrollregion(event=None):
            main_canvas.configure(scrollregion=main_canvas.bbox("all"))

        def _sync_main_width(event):
            main_canvas.itemconfigure(main_window, width=event.width)

        wrap.bind("<Configure>", _sync_main_scrollregion)
        main_canvas.bind("<Configure>", _sync_main_width)

        row = tk.Frame(wrap, bg=BG)
        row.pack(fill="x", pady=(0, 14))
        tk.Label(
            row, text="Công cụ", bg=BG, fg=TEXT,
            font=("Segoe UI", 18, "bold")
        ).pack(side="left")
        tk.Label(
            row, text="5 tools", bg=BG, fg="#BAC5D6",
            font=("Segoe UI", 10)
        ).pack(side="right", pady=5)

        self._tool_card(
            wrap,
            icon_text="f",
            icon_bg="#1877F2",
            title="Auto Đăng Bài Facebook",
            desc="Đăng bài lên các group từ danh sách Google Sheet, hỗ trợ nhiều nội dung, nhiều ảnh, random, delay, tránh spam...",
            setup=lambda: self.open_settings("facebook"),
            launch=self.launch_facebook,
            action_bg=PURPLE,
        )

        self._tool_card(
            wrap,
            icon_text="↯",
            icon_bg="#C43AE0",
            title="Auto Check Messenger & Thông Báo FB → Telegram / Zalo",
            desc="Tự động quét tin nhắn mới (Inbox, Chờ, Spam) & Thông báo Facebook chưa đọc, lọc theo phút SETUP, chống spam/trùng và gửi về Telegram hoặc Zalo theo kênh đã chọn.",
            setup=lambda: self.open_settings("messenger"),
            launch=self.launch_messenger,
            action_bg=BLUE,
        )

        self._tool_card(
            wrap,
            icon_text="G",
            icon_bg="#16A34A",
            title="Lấy Danh Sách Group Facebook",
            desc="Quét Nhóm của tôi, lấy Link Group, Tên Group, Số Thành Viên và ghi trực tiếp vào Google Sheet. Hỗ trợ đa tab 1–10.",
            setup=lambda: self.open_settings("collector"),
            launch=self.launch_group_collector,
            action_bg="#16A34A",
        )

        self._tool_card(
            wrap,
            icon_text="+",
            icon_bg="#E67E22",
            title="Auto Tham Gia Group Facebook",
            desc="Đọc link group từ Google Sheet và tự tham gia nhóm bằng đa tab 1–10. Dùng chung Chrome/Profile/Proxy của DUCTOOL.",
            setup=lambda: self.open_settings("joiner"),
            launch=self.launch_group_join,
            action_bg="#E67E22",
        )

        self._tool_card(
            wrap,
            icon_text="🖼",
            icon_bg="#06B6D4",
            title="Đổi Tên Ảnh Hàng Loạt",
            desc="Sắp xếp tự nhiên A-Z 0-9, đổi tên ảnh hàng loạt theo format tùy biến {n}, đổi đuôi ảnh, xem trước và chống trùng lặp an toàn.",
            setup=None,
            launch=self.launch_image_renamer,
            action_bg="#06B6D4",
        )

        chrome = tk.Frame(wrap, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
        chrome.pack(fill="x", pady=(0, 14))

        icon = tk.Canvas(chrome, width=74, height=92, bg=PANEL, highlightthickness=0)
        icon.pack(side="left", padx=(20, 10), pady=12)
        icon.create_oval(12, 20, 64, 72, fill="#34A853", outline="")
        icon.create_oval(20, 28, 56, 64, fill="#4285F4", outline="")
        icon.create_text(38, 46, text="C", fill="white", font=("Segoe UI", 18, "bold"))

        mid = tk.Frame(chrome, bg=PANEL)
        mid.pack(side="left", fill="both", expand=True, pady=18)
        tk.Label(mid, text="Setup Chrome", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 14, "bold")).pack(anchor="w")
        tk.Label(
            mid,
            text="Thiết lập Chrome, profile, port và proxy riêng cho Chrome 1 – 4.",
            bg=PANEL, fg=MUTED, font=("Segoe UI", 10), wraplength=560, justify="left"
        ).pack(anchor="w", pady=(6, 0))

        self._button(
            chrome, "SETUP", lambda: self.open_settings("chrome"), width=10
        ).pack(side="right", padx=22, pady=30)

        # Cuộn màn hình chính: bind sau khi toàn bộ card đã được tạo.
        self._bind_main_mousewheel(wrap, main_canvas)
        self._bind_main_mousewheel(main_canvas, main_canvas)

    def _tool_card(self, parent, icon_text, icon_bg, title, desc, setup, launch, action_bg):
        card = tk.Frame(parent, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
        card.pack(fill="x", pady=(0, 14))

        icon = tk.Canvas(card, width=88, height=110, bg=PANEL, highlightthickness=0)
        icon.pack(side="left", padx=(16, 6), pady=10)
        icon.create_oval(14, 24, 74, 84, fill=icon_bg, outline="")
        icon.create_text(44, 54, text=icon_text, fill="white", font=("Segoe UI", 27, "bold"))

        mid = tk.Frame(card, bg=PANEL)
        mid.pack(side="left", fill="both", expand=True, pady=20)
        tk.Label(mid, text=title, bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 15, "bold")).pack(anchor="w")
        tk.Label(
            mid, text=desc, bg=PANEL, fg=MUTED,
            font=("Segoe UI", 10), wraplength=560, justify="left"
        ).pack(anchor="w", pady=(8, 0))

        actions = tk.Frame(card, bg=PANEL)
        actions.pack(side="right", padx=20)
        if setup:
            self._button(actions, "SETUP", setup, width=9).pack(side="left", padx=(0, 10))

        btn = tk.Button(
            actions, text="MỞ TOOL", command=launch,
            bg=action_bg, fg="white",
            activebackground=action_bg, activeforeground="white",
            bd=0, relief="flat", cursor="hand2",
            font=("Segoe UI", 10, "bold"),
            padx=18, pady=12, width=10
        )
        btn.pack(side="left")

    # ---------- Footer ----------
    def _build_footer(self):
        foot = tk.Frame(self, bg=TOP, height=48)
        foot.pack(fill="x", side="bottom")
        foot.pack_propagate(False)

        left = tk.Frame(foot, bg=TOP)
        left.pack(side="left", padx=28)
        self.license_dot = tk.Label(left, text="●", bg=TOP, fg=MUTED, font=("Segoe UI", 11), cursor="hand2")
        self.license_dot.pack(side="left")
        self.license_label = tk.Label(
            left, textvariable=self.license_status_var, bg=TOP, fg="#D5DDEA",
            font=("Segoe UI", 10), cursor="hand2"
        )
        self.license_label.pack(side="left", padx=(6, 0))
        self.license_dot.bind("<Button-1>", lambda e: self.open_activation_window())
        self.license_label.bind("<Button-1>", lambda e: self.open_activation_window())

        right = tk.Frame(foot, bg=TOP)
        right.pack(side="right", padx=28)
        tk.Label(right, text="●", bg=TOP, fg=GREEN, font=("Segoe UI", 11)).pack(side="left")
        tk.Label(
            right, textvariable=self.status_var, bg=TOP, fg="#D5DDEA",
            font=("Segoe UI", 10)
        ).pack(side="left", padx=(6, 0))

    # ---------- Buttons ----------
    def _button(self, parent, text, command, accent=False, width=None):
        bg = PURPLE if accent else BTN_DARK
        hover = PURPLE_HOVER if accent else BTN_DARK_HOVER
        b = tk.Button(
            parent, text=text, command=command,
            bg=bg, fg="white", activebackground=hover, activeforeground="white",
            bd=0, relief="flat", cursor="hand2",
            font=("Segoe UI", 10, "bold"),
            padx=14, pady=10, width=width
        )

        b.bind("<Enter>", lambda e: b.configure(bg=hover))
        b.bind("<Leave>", lambda e: b.configure(bg=bg))
        return b


    def _bind_main_mousewheel(self, widget, canvas):
        """Cho phép lăn chuột trên toàn bộ màn hình chính DUCTOOL."""
        def _on_mousewheel(event):
            delta = getattr(event, "delta", 0)
            if delta:
                steps = int(-delta / 120)
                if steps == 0:
                    steps = -1 if delta > 0 else 1
                canvas.yview_scroll(steps, "units")
                return "break"

            num = getattr(event, "num", None)
            if num == 4:
                canvas.yview_scroll(-1, "units")
                return "break"
            if num == 5:
                canvas.yview_scroll(1, "units")
                return "break"

        def _bind(w):
            try:
                w.bind("<MouseWheel>", _on_mousewheel, add="+")
                w.bind("<Button-4>", _on_mousewheel, add="+")
                w.bind("<Button-5>", _on_mousewheel, add="+")
            except Exception:
                pass
            try:
                for child in w.winfo_children():
                    _bind(child)
            except Exception:
                pass

        _bind(widget)

    # ---------- License Management ----------
    def _require_license(self, tool_name: str) -> bool:
        if not self.is_licensed:
            messagebox.showwarning(
                "DUCTOOL",
                f"Bạn chưa kích hoạt bản quyền hoặc bản quyền đã hết hạn.\nVui lòng kích hoạt để mở '{tool_name}'."
            )
            self.open_activation_window()
            return False
        return True

    def open_activation_window(self):
        ActivationWindow(self)

    def _check_license_async(self, show_modal_if_invalid: bool = False):
        import threading
        from ductool_license import check_license_quick

        def worker():
            valid, status, info = check_license_quick()
            self.is_licensed = valid
            self.license_info = info

            def update_ui():
                if valid:
                    days = info.get("days_left", 0)
                    exp = info.get("expire_date", "")
                    color = GREEN if days > 3 else "#F59E0B"
                    self.license_dot.configure(fg=color)
                    self.license_status_var.set(f"Bản quyền: Còn {days} ngày ({exp})")
                else:
                    self.license_dot.configure(fg=DANGER)
                    if status == "EXPIRED":
                        self.license_status_var.set("Bản quyền: ĐÃ HẾT HẠN (Bấm để gia hạn)")
                    elif status == "BLOCKED":
                        self.license_status_var.set("Bản quyền: ĐÃ BỊ KHÓA")
                    elif status == "NOT_FOUND":
                        self.license_status_var.set("Bản quyền: CHƯA KÍCH HOẠT (Bấm vào đây)")
                    elif status == "NOT_CONFIGURED":
                        self.license_dot.configure(fg="#F59E0B")
                        self.license_status_var.set("Bản quyền: Chưa cấu hình Sheet Link")
                    else:
                        self.license_status_var.set("Bản quyền: Lỗi kết nối")

                    if show_modal_if_invalid and status in ("NOT_FOUND", "EXPIRED", "BLOCKED"):
                        self.open_activation_window()

            self.after(0, update_ui)

        threading.Thread(target=worker, daemon=True).start()

    # ---------- Tool launch ----------
    def launch_facebook(self):
        if not self._require_not_force_update("Auto Đăng Bài Facebook"):
            return
        if not self._require_license("Auto Đăng Bài Facebook"):
            return
        if getattr(sys, "frozen", False):
            cmd = [sys.executable, "--mode", "facebook"]
        else:
            cmd = [sys.executable, str(Path(__file__).resolve()), "--mode", "facebook"]

        self.status_var.set("Đang mở Facebook tool...")
        run_hidden(cmd)


    def launch_messenger(self):
        if not self._require_not_force_update("Messenger to Telegram / Zalo"):
            return
        if not self._require_license("Messenger to Telegram / Zalo"):
            return
        if getattr(sys, "frozen", False):
            cmd = [sys.executable, "--mode", "messenger"]
        else:
            cmd = [sys.executable, str(Path(__file__).resolve()), "--mode", "messenger"]

        self.status_var.set("Đang mở Messenger tool...")
        run_hidden(cmd)


    def launch_group_collector(self):
        if not self._require_not_force_update("Lấy Danh Sách Group"):
            return
        if not self._require_license("Lấy Danh Sách Group"):
            return
        if getattr(sys, "frozen", False):
            cmd = [sys.executable, "--mode", "collector"]
        else:
            cmd = [sys.executable, str(Path(__file__).resolve()), "--mode", "collector"]

        self.status_var.set("Đang mở Group Collector...")
        run_hidden(cmd)


    def launch_group_join(self):
        if not self._require_not_force_update("Auto Tham Gia Group"):
            return
        if not self._require_license("Auto Tham Gia Group"):
            return
        if getattr(sys, "frozen", False):
            cmd = [sys.executable, "--mode", "joiner"]
        else:
            cmd = [sys.executable, str(Path(__file__).resolve()), "--mode", "joiner"]

        self.status_var.set("Đang mở Auto Tham Gia Group...")
        run_hidden(cmd)


    def launch_image_renamer(self):
        if not self._require_not_force_update("Đổi Tên Ảnh Hàng Loạt"):
            return
        if not self._require_license("Đổi Tên Ảnh Hàng Loạt"):
            return
        if getattr(sys, "frozen", False):
            cmd = [sys.executable, "--mode", "renamer"]
        else:
            cmd = [sys.executable, str(Path(__file__).resolve()), "--mode", "renamer"]

        self.status_var.set("Đang mở Đổi Tên Ảnh Hàng Loạt...")
        run_hidden(cmd)


    def _require_not_force_update(self, tool_name: str) -> bool:
        if self.force_update_active:
            messagebox.showerror(
                "YÊU CẦU CẬP NHẬT",
                f"Phiên bản của bạn đã cũ và bị tạm ngưng!\n\nVui lòng cập nhật phiên bản mới nhất để tiếp tục sử dụng '{tool_name}'."
            )
            self.show_force_update_modal(self.update_info if hasattr(self, "update_info") else {})
            return False
        return True

    def _check_update_startup(self):
        """Tự động kiểm tra cập nhật khi vừa khởi động."""
        def worker():
            res = check_update_status()
            self.update_info = res
            if res.get("has_update"):
                if res.get("is_force"):
                    self.force_update_active = True
                    self.after(0, lambda: self.show_force_update_modal(res))
                else:
                    # Update nhỏ: Tự động tải ngầm hoặc gợi ý cập nhật
                    self.after(0, lambda: self.prompt_auto_update(res))

        threading.Thread(target=worker, daemon=True).start()

    def show_force_update_modal(self, info: dict):
        ForceUpdateWindow(self, info)

    def prompt_auto_update(self, info: dict):
        new_v = info.get("latest_version", "")
        title = info.get("title", "")
        changelog = info.get("changelog", "")
        msg = f"Đã có phiên bản mới v{new_v}!\n\nTiêu đề: {title}\nChi tiết:\n{changelog}\n\nBạn có muốn cập nhật tự động ngay bây giờ không?"
        if messagebox.askyesno("CẬP NHẬT PHIÊN BẢN MỚI", msg):
            self.trigger_auto_update(info)

    def trigger_auto_update(self, info: dict):
        exe_url = info.get("exe_url") or ""
        setup_url = info.get("setup_url") or ""
        if not getattr(sys, "frozen", False):
            # Nếu đang chạy từ code python
            messagebox.showinfo(
                "DUCTOOL",
                f"Đang chạy từ mã nguồn Python. Bản mới là v{info.get('latest_version')}.\nBạn chỉ cần git pull hoặc tải code mới."
            )
            return

        progress_win = tk.Toplevel(self)
        progress_win.title("Đang cập nhật DUCTOOL...")
        progress_win.geometry("450x180")
        progress_win.configure(bg=BG)
        progress_win.transient(self)
        progress_win.grab_set()

        lbl = tk.Label(progress_win, text="Đang tải bộ cài phiên bản mới...\nVui lòng không tắt máy.", bg=BG, fg=TEXT, font=("Segoe UI", 11, "bold"))
        lbl.pack(pady=25)

        status_lbl = tk.Label(progress_win, text="0%", bg=BG, fg=PURPLE, font=("Segoe UI", 14, "bold"))
        status_lbl.pack(pady=5)

        def worker():
            def cb(downloaded, total):
                if total > 0:
                    pct = int(downloaded * 100 / total)
                    mb_down = downloaded / (1024 * 1024)
                    mb_tot = total / (1024 * 1024)
                    progress_win.after(0, lambda: status_lbl.configure(text=f"{pct}% ({mb_down:.1f}MB / {mb_tot:.1f}MB)"))

            ok, err = perform_auto_replace(
                exe_url,
                progress_callback=cb,
                setup_url=setup_url,
                checksum_url=info.get("checksum_url", ""),
                exe_sha256=info.get("exe_sha256", ""),
                setup_sha256=info.get("setup_sha256", ""),
            )
            if ok:
                progress_win.after(0, lambda: lbl.configure(text="Tải xong! Đang cài đặt và mở lại app..."))
                time.sleep(1.5)
                progress_win.after(0, lambda: sys.exit(0))
            else:
                progress_win.after(0, lambda: messagebox.showerror("Lỗi Cập Nhật", f"Không thể cập nhật tự động: {err}\nVui lòng tải bộ cài từ GitHub Releases."))
                progress_win.after(0, progress_win.destroy)

        threading.Thread(target=worker, daemon=True).start()

    def check_update(self):
        self.status_var.set("Đang kiểm tra cập nhật...")
        def worker():
            res = check_update_status()
            self.update_info = res
            if res.get("has_update"):
                if res.get("is_force"):
                    self.force_update_active = True
                    self.after(0, lambda: self.show_force_update_modal(res))
                else:
                    self.after(0, lambda: self.prompt_auto_update(res))
            elif res.get("error"):
                self.after(0, lambda: self.status_var.set("Không thể kiểm tra cập nhật"))
                self.after(0, lambda: messagebox.showwarning(
                    "DUCTOOL Cập Nhật",
                    res.get("error", "Không thể kết nối đến máy chủ cập nhật.")
                ))
            else:
                self.after(0, lambda: self.status_var.set("Phiên bản hiện tại là mới nhất"))
                self.after(0, lambda: messagebox.showinfo(
                    "DUCTOOL Cập Nhật",
                    f"Bạn đang sử dụng phiên bản mới nhất (v{CURRENT_VERSION})!\nKhông có bản cập nhật nào mới."
                ))
        threading.Thread(target=worker, daemon=True).start()

    # ---------- Settings ----------
    def open_settings(self, section):
        SettingsWindow(self, section)



class ForceUpdateWindow(tk.Toplevel):
    """Cửa sổ bắt buộc cập nhật - khóa toàn bộ tool cũ cho tới khi update."""
    def __init__(self, master, info: dict):
        super().__init__(master)
        self.master_app = master
        self.info = info
        self.title("BẮT BUỘC CẬP NHẬT — DUCTOOL")
        self.geometry("640x440")
        self.minsize(580, 400)
        self.configure(bg=BG)
        self.transient(master)
        self.grab_set()

        # Không cho bấm nút X để bỏ qua nếu là force update
        self.protocol("WM_DELETE_WINDOW", self.on_exit)

        # Header cảnh báo màu đỏ
        top = tk.Frame(self, bg="#881337", height=80)
        top.pack(fill="x")
        top.pack_propagate(False)

        tk.Label(
            top, text="⚠️  YÊU CẦU CẬP NHẬT PHIÊN BẢN MỚI", bg="#881337", fg="white",
            font=("Segoe UI", 15, "bold")
        ).pack(side="left", padx=24, pady=24)

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=24, pady=20)

        curr_v = info.get("current_version", CURRENT_VERSION)
        new_v = info.get("latest_version", "Mới")
        title = info.get("title", "Bản cập nhật quan trọng")
        changelog = info.get("changelog", "Bản cập nhật lớn, bắt buộc phải nâng cấp để tiếp tục sử dụng.")

        tk.Label(
            body,
            text=f"Phiên bản hiện tại ({curr_v}) đã cũ và bị ngưng hoạt động.\nVui lòng cập nhật lên phiên bản mới nhất ({new_v}) để tiếp tục sử dụng tool.",
            bg=BG, fg=TEXT, font=("Segoe UI", 11, "bold"), justify="left"
        ).pack(anchor="w", pady=(0, 10))

        # Khung hiển thị nội dung cập nhật
        box = tk.Frame(body, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
        box.pack(fill="both", expand=True, pady=(0, 15))

        tk.Label(
            box, text=f"★ {title}", bg=PANEL, fg="#38BDF8",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", padx=14, pady=(10, 4))

        tk.Label(
            box, text=changelog, bg=PANEL, fg=MUTED,
            font=("Segoe UI", 10), justify="left", wraplength=540
        ).pack(anchor="w", padx=14, pady=(0, 10))

        # Các nút hành động
        btn_box = tk.Frame(body, bg=BG)
        btn_box.pack(fill="x")

        # Nút tự động cập nhật
        self.btn_update = tk.Button(
            btn_box, text="⚡ CẬP NHẬT TỰ ĐỘNG GHI ĐÈ",
            command=self.do_auto_update,
            bg=PURPLE, fg="white", activebackground=PURPLE_HOVER,
            activeforeground="white", bd=0, relief="flat", cursor="hand2",
            font=("Segoe UI", 11, "bold"), padx=16, pady=10
        )
        self.btn_update.pack(side="left", fill="x", expand=True, padx=(0, 10))

        # Nút mở link tải
        tk.Button(
            btn_box, text="🌐 Mở Link Tải Trực Tiếp",
            command=self.open_download_url,
            bg=BTN_DARK, fg="white", activebackground=BTN_DARK_HOVER,
            activeforeground="white", bd=0, relief="flat", cursor="hand2",
            font=("Segoe UI", 10, "bold"), padx=14, pady=10
        ).pack(side="left", padx=(0, 10))

        # Nút thoát
        tk.Button(
            btn_box, text="Thoát",
            command=self.on_exit,
            bg="#3F171A", fg="#FCA5A5", bd=0, relief="flat", cursor="hand2",
            font=("Segoe UI", 10, "bold"), padx=16, pady=10
        ).pack(side="right")

    def open_download_url(self):
        import webbrowser
        url = self.info.get("release_page") or "https://github.com/padphamduc/devtool/releases/latest"
        webbrowser.open(url)

    def do_auto_update(self):
        self.destroy()
        self.master_app.trigger_auto_update(self.info)

    def on_exit(self):
        sys.exit(0)



class ActivationWindow(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.master_app = master
        self.title("KÍCH HOẠT BẢN QUYỀN — DUCTOOL")
        self.geometry("620x460")
        self.minsize(560, 420)
        self.configure(bg=BG)
        self.transient(master)

        from ductool_license import get_hwid, get_saved_key
        self.hwid = get_hwid()
        self.check_status_var = tk.StringVar(value="")
        self.key_var = tk.StringVar(value=get_saved_key())

        # Header
        top = tk.Frame(self, bg=TOP, height=72)
        top.pack(fill="x")
        top.pack_propagate(False)
        tk.Label(
            top, text="KÍCH HOẠT BẢN QUYỀN DUCTOOL", bg=TOP, fg=TEXT,
            font=("Segoe UI", 15, "bold")
        ).pack(side="left", padx=24, pady=20)

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=24, pady=16)

        # Card 1: Mã máy (HWID)
        card1 = tk.Frame(body, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
        card1.pack(fill="x", pady=(0, 12))

        tk.Label(
            card1, text="1. MÃ MÁY CỦA BẠN (HWID):", bg=PANEL, fg="#DCE5F2",
            font=("Segoe UI", 10, "bold")
        ).pack(anchor="w", padx=16, pady=(12, 4))

        hwid_row = tk.Frame(card1, bg=PANEL)
        hwid_row.pack(fill="x", padx=16, pady=(0, 6))

        hwid_entry = tk.Entry(
            hwid_row, bg=INPUT, fg="#38BDF8", insertbackground=TEXT,
            relief="flat", bd=0, font=("Consolas", 12, "bold"), justify="center"
        )
        hwid_entry.insert(0, self.hwid)
        hwid_entry.configure(state="readonly")
        hwid_entry.pack(side="left", fill="x", expand=True, ipady=7, padx=(0, 8))

        self.copy_btn = tk.Button(
            hwid_row, text="📋 SAO CHÉP MÃ MÁY", command=self.copy_hwid,
            bg=PURPLE, fg="white", activebackground=PURPLE_HOVER,
            activeforeground="white", bd=0, relief="flat", cursor="hand2",
            font=("Segoe UI", 9, "bold"), padx=12, pady=6
        )
        self.copy_btn.pack(side="right")

        self.copy_feedback = tk.Label(card1, text="* Gửi mã máy này cho Admin để gắn key với máy của bạn.", bg=PANEL, fg=MUTED, font=("Segoe UI", 8))
        self.copy_feedback.pack(anchor="w", padx=16, pady=(0, 8))

        # Card 2: Ô NHẬP MÃ KEY (RẤT NỔI BẬT)
        card2 = tk.Frame(body, bg=PANEL, highlightthickness=1, highlightbackground=PURPLE)
        card2.pack(fill="x", pady=(0, 12))

        tk.Label(
            card2, text="2. NHẬP MÃ KEY BẢN QUYỀN:", bg=PANEL, fg="#F59E0B",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", padx=16, pady=(12, 4))

        key_row = tk.Frame(card2, bg=PANEL)
        key_row.pack(fill="x", padx=16, pady=(0, 12))

        self.key_entry = tk.Entry(
            key_row, textvariable=self.key_var, bg=INPUT, fg=TEXT,
            insertbackground=TEXT, relief="flat", bd=0, font=("Consolas", 13, "bold")
        )
        self.key_entry.pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 8))
        self.key_entry.focus_set()

        # Nút dán key từ clipboard
        tk.Button(
            key_row, text="📋 DÁN KEY", command=self.paste_key,
            bg=BTN_DARK, fg="white", activebackground=BTN_DARK_HOVER,
            activeforeground="white", bd=0, relief="flat", cursor="hand2",
            font=("Segoe UI", 9, "bold"), padx=12, pady=7
        ).pack(side="right")

        # Label trạng thái kết quả
        self.status_label = tk.Label(
            body, textvariable=self.check_status_var, bg=BG, fg="#F59E0B",
            font=("Segoe UI", 10, "bold")
        )
        self.status_label.pack(anchor="w", pady=(0, 6))

        # Nút hành động phía dưới
        bottom = tk.Frame(self, bg=BG)
        bottom.pack(fill="x", padx=24, pady=(0, 16), side="bottom")

        self.check_btn = tk.Button(
            bottom, text="🔑 KÍCH HOẠT BẢN QUYỀN", command=self.check_now,
            bg=PURPLE, fg="white", activebackground=PURPLE_HOVER,
            activeforeground="white", bd=0, relief="flat", cursor="hand2",
            font=("Segoe UI", 11, "bold"), padx=22, pady=11
        )
        self.check_btn.pack(side="right")

        close_btn = tk.Button(
            bottom, text="ĐÓNG", command=self.destroy,
            bg=BTN_DARK, fg="white", activebackground=BTN_DARK_HOVER,
            activeforeground="white", bd=0, relief="flat", cursor="hand2",
            font=("Segoe UI", 10, "bold"), padx=16, pady=11
        )
        close_btn.pack(side="right", padx=(0, 10))

    def paste_key(self):
        try:
            text = self.clipboard_get().strip()
            if text:
                self.key_var.set(text)
        except Exception:
            pass

    def copy_hwid(self):
        self.clipboard_clear()
        self.clipboard_append(self.hwid)
        self.copy_feedback.configure(text="✅ Đã sao chép mã máy! Hãy gửi mã này cho Admin để nhận Key.", fg=GREEN)

    def check_now(self):
        entered_key = self.key_var.get().strip()
        if not entered_key:
            self.check_status_var.set("Vui lòng nhập key bản quyền.")
            return
        self.check_btn.configure(state="disabled")
        self.check_status_var.set("Kiểm tra key")
        self.status_label.configure(fg="#F59E0B")

        import threading
        from ductool_license import check_license_online

        def worker():
            res = check_license_online(self.hwid, key=entered_key, timeout=20, activate=True)
            status = res.get("status")

            def finish():
                self.check_btn.configure(state="normal")
                if status == "ACTIVE":
                    days = res.get("days_left", 0)
                    exp = res.get("expire_date", "")
                    self.status_label.configure(fg=GREEN)
                    self.check_status_var.set(f"✅ BẢN QUYỀN HỢP LỆ! Còn {days} ngày (Hết hạn: {exp}).")
                    self.master_app.is_licensed = True
                    self.master_app.license_info = res
                    self.master_app.license_dot.configure(fg=GREEN)
                    self.master_app.license_status_var.set(f"Bản quyền: Còn {days} ngày ({exp})")
                    messagebox.showinfo("DUCTOOL", f"🎉 KÍCH HOẠT THÀNH CÔNG!\n\nThời hạn bản quyền: {exp}\n(Còn {days} ngày sử dụng)")
                    self.destroy()
                elif status == "HWID_MISMATCH":
                    self.status_label.configure(fg=DANGER)
                    self.check_status_var.set("❌ Mã Key này đã được cấp cho máy khác, không thể dùng trên máy tính này!")
                    messagebox.showerror("DUCTOOL", "Mã Key này đã được cấp cho máy khác, không thể dùng trên máy tính này!")
                elif status == "NOT_FOUND":
                    self.status_label.configure(fg=DANGER)
                    msg = f"❌ Không tìm thấy Key '{entered_key}' trong hệ thống." if entered_key else "❌ Vui lòng nhập Mã Key trước khi bấm kích hoạt."
                    self.check_status_var.set(msg)
                elif status == "EXPIRED":
                    exp = res.get("expire_date", "")
                    self.status_label.configure(fg=DANGER)
                    self.check_status_var.set(f"❌ Key này đã hết hạn vào ngày {exp}. Vui lòng gia hạn.")
                elif status == "BLOCKED":
                    self.status_label.configure(fg=DANGER)
                    self.check_status_var.set("❌ Key / Mã máy này đã bị tạm khóa quyền sử dụng.")
                elif status == "NOT_CONFIGURED":
                    self.status_label.configure(fg="#F59E0B")
                    self.check_status_var.set("⚠️ Máy chủ kích hoạt chưa được cấu hình. Liên hệ Admin.")
                else:
                    msg = res.get("message", "Không thể kết nối máy chủ")
                    self.status_label.configure(fg=DANGER)
                    self.check_status_var.set(f"❌ Lỗi: {msg}")

            self.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()



class SettingsWindow(tk.Toplevel):
    def __init__(self, master, section):
        super().__init__(master)
        self.master_app = master
        self.section = section
        self.cfg = load_config()
        self.vars = {}
        self.txt_rows = []
        self.image_rows = []

        titles = {
            "chrome": "SETUP — Setup Chrome",
            "facebook": "SETUP — Auto Đăng Bài Facebook",
            "messenger": "SETUP — Messenger → Telegram / Zalo",
            "collector": "SETUP — Lấy Danh Sách Group Facebook",
            "joiner": "SETUP — Auto Tham Gia Group Facebook",
        }
        self.title(titles[section])
        self.geometry("790x660")
        self.minsize(720, 580)
        self.configure(bg=BG)
        self.transient(master)

        # Explicit clipboard shortcuts for all Entry widgets in this window.
        self.bind_class("Entry", "<Control-v>", self._paste_to_entry)
        self.bind_class("Entry", "<Control-V>", self._paste_to_entry)
        self.bind_class("Entry", "<Control-c>", self._copy_from_entry)
        self.bind_class("Entry", "<Control-C>", self._copy_from_entry)
        self.bind_class("Entry", "<Control-x>", self._cut_from_entry)
        self.bind_class("Entry", "<Control-X>", self._cut_from_entry)
        self.bind_class("Entry", "<Control-a>", self._select_all_entry)
        self.bind_class("Entry", "<Control-A>", self._select_all_entry)

        top = tk.Frame(self, bg=TOP, height=68)
        top.pack(fill="x")
        top.pack_propagate(False)
        tk.Label(
            top, text=titles[section], bg=TOP, fg=TEXT,
            font=("Segoe UI", 16, "bold")
        ).pack(side="left", padx=22, pady=19)

        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        bar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        inner = tk.Frame(self.canvas, bg=BG)
        window = self.canvas.create_window((0,0), window=inner, anchor="nw")
        self.canvas.configure(yscrollcommand=bar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")
        inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(window, width=e.width))

        # Mouse wheel only while pointer is inside this setup window.
        self.bind("<MouseWheel>", self._on_mousewheel)
        self.bind("<Button-4>", self._on_mousewheel_linux)
        self.bind("<Button-5>", self._on_mousewheel_linux)

        body = tk.Frame(inner, bg=BG)
        body.pack(fill="both", expand=True, padx=22, pady=18)

        if section == "chrome":
            self._build_chrome(body)
        elif section == "facebook":
            self._build_facebook(body)
        elif section == "messenger":
            self._build_messenger(body)
        elif section == "collector":
            self._build_collector(body)
        else:
            self._build_joiner(body)

        # Bind wheel to toàn bộ vùng SETUP, kể cả Entry/Label/Button/Combobox.
        self._bind_mousewheel_recursive(body, self.canvas)

        bottom = tk.Frame(inner, bg=BG)
        bottom.pack(fill="x", padx=22, pady=(0,22))
        self.master_app._button(bottom, "LƯU CẤU HÌNH", self.save, accent=True).pack(side="right")
        self.master_app._button(bottom, "ĐÓNG", self.destroy).pack(side="right", padx=(0,10))

    # ----- clipboard -----
    def _paste_to_entry(self, event):
        try:
            text = self.clipboard_get()
            event.widget.delete("sel.first", "sel.last")
        except tk.TclError:
            try:
                text = self.clipboard_get()
            except tk.TclError:
                return "break"
        event.widget.insert("insert", text)
        return "break"

    def _copy_from_entry(self, event):
        try:
            text = event.widget.selection_get()
        except tk.TclError:
            return "break"
        self.clipboard_clear()
        self.clipboard_append(text)
        return "break"

    def _cut_from_entry(self, event):
        try:
            text = event.widget.selection_get()
            self.clipboard_clear()
            self.clipboard_append(text)
            event.widget.delete("sel.first", "sel.last")
        except tk.TclError:
            pass
        return "break"

    def _select_all_entry(self, event):
        event.widget.selection_range(0, "end")
        event.widget.icursor("end")
        return "break"

    # ----- mouse wheel -----
    def _on_mousewheel(self, event):
        delta = int(-1 * (event.delta / 120))
        if delta == 0:
            delta = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(delta, "units")
        return "break"

    def _on_mousewheel_linux(self, event):
        self.canvas.yview_scroll(-1 if event.num == 4 else 1, "units")
        return "break"

    def _card(self, parent, title):
        f = tk.Frame(parent, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
        f.pack(fill="x", pady=(0,14))
        tk.Label(f, text=title, bg=PANEL, fg=TEXT, font=("Segoe UI", 12, "bold")).pack(
            anchor="w", padx=16, pady=(14,8)
        )
        body = tk.Frame(f, bg=PANEL)
        body.pack(fill="x", padx=16, pady=(0,16))
        return body

    def _entry(self, parent, label, key, value="", browse=None, secret=False):
        row = tk.Frame(parent, bg=PANEL)
        row.pack(fill="x", pady=6)

        tk.Label(row, text=label, bg=PANEL, fg="#DCE5F2", width=26,
                 anchor="w", font=("Segoe UI", 9, "bold")).pack(side="left")

        v = tk.StringVar(value=str(value))
        self.vars[key] = v
        e = tk.Entry(
            row, textvariable=v, show="*" if secret else "",
            bg=INPUT, fg=TEXT, insertbackground=TEXT,
            relief="flat", bd=0, font=("Segoe UI", 10)
        )
        e.pack(side="left", fill="x", expand=True, ipady=8, padx=(0,8))
        if browse:
            self.master_app._button(row, "CHỌN", lambda: browse(v), width=7).pack(side="right")

    def _browse_file(self, var):
        p = filedialog.askopenfilename()
        if p:
            var.set(p)

    def _browse_txt(self, var):
        p = filedialog.askopenfilename(
            title="Chọn file nội dung TXT",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if p:
            var.set(p)

    def _browse_image(self, var):
        p = filedialog.askopenfilename(
            title="Chọn file ảnh",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.webp *.gif *.bmp"),
                ("All files", "*.*")
            ]
        )
        if p:
            var.set(p)

    def _browse_dir(self, var):
        p = filedialog.askdirectory()
        if p:
            var.set(p)

    # ----- dynamic list UI -----
    def _dynamic_header(self, parent, title, add_command):
        head = tk.Frame(parent, bg=PANEL)
        head.pack(fill="x", pady=(2,8))
        tk.Label(head, text=title, bg=PANEL, fg="#DCE5F2",
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        plus = tk.Button(
            head, text="+", command=add_command,
            bg=PURPLE, fg="white", activebackground=PURPLE_HOVER,
            activeforeground="white", bd=0, relief="flat",
            font=("Segoe UI", 13, "bold"), width=3, cursor="hand2"
        )
        plus.pack(side="right")
        return head

    def _add_txt_row(self, value=""):
        idx = len(self.txt_rows) + 1
        row = tk.Frame(self.txt_list_frame, bg=PANEL)
        row.pack(fill="x", pady=5)

        tk.Label(row, text=f"Nội dung {idx}", bg=PANEL, fg="#DCE5F2",
                 width=13, anchor="w", font=("Segoe UI", 9, "bold")).pack(side="left")

        var = tk.StringVar(value=value)
        ent = tk.Entry(row, textvariable=var, bg=INPUT, fg=TEXT,
                       insertbackground=TEXT, relief="flat", bd=0,
                       font=("Segoe UI", 10))
        ent.pack(side="left", fill="x", expand=True, ipady=8, padx=(0,8))
        self.master_app._button(row, "CHỌN", lambda v=var: self._browse_txt(v), width=7).pack(side="left")
        tk.Button(
            row, text="×", command=lambda r=row, v=var: self._remove_dynamic_row(self.txt_rows, r, v, "txt"),
            bg="#3A2430", fg="#FCA5A5", activebackground="#512B39",
            activeforeground="white", bd=0, relief="flat",
            font=("Segoe UI", 11, "bold"), width=3, cursor="hand2"
        ).pack(side="left", padx=(8,0))
        self.txt_rows.append((row, var))
        self._renumber_rows(self.txt_rows, "Nội dung")

    def _add_image_row(self, value=""):
        idx = len(self.image_rows) + 1
        row = tk.Frame(self.image_list_frame, bg=PANEL)
        row.pack(fill="x", pady=5)

        tk.Label(row, text=f"Ảnh {idx}", bg=PANEL, fg="#DCE5F2",
                 width=13, anchor="w", font=("Segoe UI", 9, "bold")).pack(side="left")

        var = tk.StringVar(value=value)
        ent = tk.Entry(row, textvariable=var, bg=INPUT, fg=TEXT,
                       insertbackground=TEXT, relief="flat", bd=0,
                       font=("Segoe UI", 10))
        ent.pack(side="left", fill="x", expand=True, ipady=8, padx=(0,8))
        self.master_app._button(row, "CHỌN", lambda v=var: self._browse_image(v), width=7).pack(side="left")
        tk.Button(
            row, text="×", command=lambda r=row, v=var: self._remove_dynamic_row(self.image_rows, r, v, "img"),
            bg="#3A2430", fg="#FCA5A5", activebackground="#512B39",
            activeforeground="white", bd=0, relief="flat",
            font=("Segoe UI", 11, "bold"), width=3, cursor="hand2"
        ).pack(side="left", padx=(8,0))
        self.image_rows.append((row, var))
        self._renumber_rows(self.image_rows, "Ảnh")

    def _remove_dynamic_row(self, collection, row, var, kind):
        # Keep at least two rows as requested.
        if len(collection) <= 2:
            messagebox.showinfo("DUCTOOL", "Giữ tối thiểu 2 mục.")
            return
        for i, (r, v) in enumerate(collection):
            if r is row:
                collection.pop(i)
                break
        row.destroy()
        self._renumber_rows(collection, "Nội dung" if kind == "txt" else "Ảnh")

    def _renumber_rows(self, rows, prefix):
        for i, (row, _var) in enumerate(rows, start=1):
            labels = [w for w in row.winfo_children() if isinstance(w, tk.Label)]
            if labels:
                labels[0].configure(text=f"{prefix} {i}")


    def _bind_mousewheel_recursive(self, widget, canvas):
        """Cho phép lăn chuột ở mọi control bên trong cửa sổ SETUP."""
        def _on_mousewheel(event):
            # Windows/macOS
            delta = getattr(event, "delta", 0)
            if delta:
                steps = int(-delta / 120)
                if steps == 0:
                    steps = -1 if delta > 0 else 1
                canvas.yview_scroll(steps, "units")
                return "break"

            # Linux/X11
            num = getattr(event, "num", None)
            if num == 4:
                canvas.yview_scroll(-1, "units")
                return "break"
            if num == 5:
                canvas.yview_scroll(1, "units")
                return "break"

        def _bind(w):
            try:
                w.bind("<MouseWheel>", _on_mousewheel, add="+")
                w.bind("<Button-4>", _on_mousewheel, add="+")
                w.bind("<Button-5>", _on_mousewheel, add="+")
            except Exception:
                pass
            try:
                for child in w.winfo_children():
                    _bind(child)
            except Exception:
                pass

        _bind(widget)

    def _build_chrome(self, parent):
        c = self.cfg.get("chrome", {})
        g = self.cfg.get("general", {})
        b0 = self._card(parent, "Chrome mặc định")
        self._entry(b0, "Chọn Chrome để chạy", "general.selected_chrome", g.get("selected_chrome", 1))

        b = self._card(parent, "Setup Chrome / Profile / Proxy")
        self._entry(b, "Chrome executable", "chrome.executable", c.get("executable",""), self._browse_file)
        self._entry(b, "Profile root", "chrome.profile_root", c.get("profile_root", g.get("chrome_profile_root", r"C:\duc\FacebookChrome")), self._browse_dir)
        ports = c.get("ports", {"1":9311,"2":9312,"3":9313,"4":9314})
        proxies = c.get("proxies", {"1":"","2":"","3":"","4":""})
        for i in range(1,5):
            self._entry(b, f"Port Chrome {i}", f"chrome.port.{i}", ports.get(str(i), 9310+i))
            self._entry(b, f"Proxy Chrome {i}", f"chrome.proxy.{i}", proxies.get(str(i), ""))
        tk.Label(b, text="Proxy hỗ trợ: IP:PORT, http://IP:PORT, socks5://IP:PORT, USER:PASS@IP:PORT hoặc IP:PORT:USER:PASS. Đổi proxy cần đóng Chrome profile đó rồi mở lại.", bg=PANEL, fg=MUTED, font=("Segoe UI", 9), wraplength=650, justify="left").pack(anchor="w", pady=(10,0))

    def _build_facebook(self, parent):
        f = self.cfg.get("facebook", {})

        run = self._card(parent, "Chrome chạy tool")
        self._entry(run, "Chọn Chrome để chạy", "general.selected_chrome", self.cfg.get("general", {}).get("selected_chrome", 1))

        source = self._card(parent, "Nguồn dữ liệu")
        self._entry(source, "Google Sheet URL", "facebook.sheet_url", f.get("sheet_url",""))

        # TXT dynamic list - use current txt_files or content_files
        self._dynamic_header(source, "File nội dung TXT", self._add_txt_row)
        self.txt_list_frame = tk.Frame(source, bg=PANEL)
        self.txt_list_frame.pack(fill="x")
        txt_values = list(f.get("txt_files", []) or f.get("content_files", []) or [])
        while len(txt_values) < 2:
            txt_values.append("")
        for value in txt_values:
            self._add_txt_row(value)

        tk.Frame(source, bg=BORDER, height=1).pack(fill="x", pady=12)

        # Image dynamic list
        self._dynamic_header(source, "File ảnh", self._add_image_row)
        self.image_list_frame = tk.Frame(source, bg=PANEL)
        self.image_list_frame.pack(fill="x")
        image_values = list(f.get("image_files", []) or [])
        while len(image_values) < 2:
            image_values.append("")
        for value in image_values:
            self._add_image_row(value)

        b2 = self._card(parent, "Thông số đăng")
        self._entry(
            b2,
            "1 Nội Dung Bao Nhiêu Group",
            "facebook.groups_per_content",
            f.get("groups_per_content",1)
        )
        self._entry(b2, "Delay tối thiểu", "facebook.delay_min", f.get("delay_min", f.get("delay_between_groups_seconds", 5)))
        self._entry(b2, "Delay tối đa", "facebook.delay_max", f.get("delay_max", f.get("delay_between_groups_seconds", 12)))
        self._entry(b2, "Nghỉ sau N group", "facebook.rest_every", f.get("rest_every", f.get("jobs_before_break", 0)))
        self._entry(b2, "Thời gian nghỉ (s)", "facebook.rest_seconds", f.get("rest_seconds", f.get("break_after_jobs_seconds", 0)))
        self._entry(b2, "File log", "facebook.log_file", f.get("log_file", f.get("log_path", "")))

        # state_file and failed_groups_file intentionally removed from UI.

    def _build_collector(self, parent):
        run = self._card(parent, "Chrome chạy tool")
        self._entry(
            run,
            "Chọn Chrome để chạy",
            "general.selected_chrome",
            self.cfg.get("general", {}).get("selected_chrome", 1),
        )

        col = self.cfg.get("collector", {})
        source = self._card(parent, "Nguồn ghi dữ liệu")
        self._entry(
            source,
            "Link Google Sheet",
            "collector.sheet_url",
            col.get("sheet_url", ""),
        )

        params = self._card(parent, "Thông số quét")
        self._entry(
            params,
            "Dữ liệu cần lấy (1, 2, 3 hoặc 123)",
            "collector.fields",
            col.get("fields", "123"),
        )
        self._entry(
            params,
            "Số tab chạy song song (1-10)",
            "collector.tab_count",
            col.get("tab_count", 3),
        )

        info = self._card(parent, "Cách hoạt động")
        tk.Label(
            info,
            text=(
                "Tool dùng cùng Chrome/Profile/Proxy với Auto Đăng Bài và Messenger.\n"
                "• Dữ liệu cần lấy: 1 = Link Group, 2 = Tên Group, 3 = Số Thành Viên (123 = lấy cả 3).\n"
                "• Link Google Sheet, dữ liệu và số tab được tự động lấy từ SETUP này khi chạy tool."
            ),
            bg=PANEL, fg=MUTED, font=("Segoe UI", 10),
            wraplength=650, justify="left"
        ).pack(anchor="w", pady=(4, 8))


    def _build_joiner(self, parent):
        run = self._card(parent, "Chrome chạy tool")
        self._entry(
            run,
            "Chọn Chrome để chạy",
            "general.selected_chrome",
            self.cfg.get("general", {}).get("selected_chrome", 1),
        )

        joiner = self.cfg.get("joiner", {})
        source = self._card(parent, "Nguồn link Group")
        self._entry(
            source,
            "Link Google Sheet",
            "joiner.sheet_url",
            joiner.get("sheet_url", ""),
        )

        params = self._card(parent, "Thông số tham gia")
        self._entry(
            params,
            "Số tab chạy song song (1-10)",
            "joiner.tab_count",
            joiner.get("tab_count", 1),
        )
        self._entry(
            params,
            "Delay giữa các group (giây)",
            "joiner.delay_seconds",
            joiner.get("delay_seconds", 10),
        )

        info = self._card(parent, "Cách hoạt động")
        tk.Label(
            info,
            text=(
                "Tool dùng chung Chrome/Profile/Proxy với các tool Facebook khác.\n"
                "Link Google Sheet, số tab (mặc định 1 tab) và delay (mặc định 10s) được lưu từ SETUP này;\n"
                "khi mở tool sẽ tự động đọc cấu hình.\n"
                "State và log lưu tại C:\\duc."
            ),
            bg=PANEL, fg=MUTED, font=("Segoe UI", 10),
            wraplength=650, justify="left"
        ).pack(anchor="w", pady=(4, 8))


    def _build_messenger(self, parent):
        m = self.cfg.get("messenger", {})
        run = self._card(parent, "Chrome chạy tool")
        self._entry(run, "Chọn Chrome để chạy", "general.selected_chrome", self.cfg.get("general", {}).get("selected_chrome", 1))

        channel = self._card(parent, "Kênh nhận thông báo")
        provider = tk.StringVar(value=m.get("notification_provider", "telegram"))
        self.vars["messenger.notification_provider"] = provider
        row = tk.Frame(channel, bg=PANEL)
        row.pack(fill="x", pady=8)
        for value, label in (("telegram", "Telegram"), ("zalo", "Zalo")):
            tk.Radiobutton(
                row, text=label, variable=provider, value=value,
                bg=PANEL, fg=TEXT, selectcolor=PANEL2,
                activebackground=PANEL, activeforeground=TEXT,
                font=("Segoe UI", 11), indicatoron=False, width=14,
            ).pack(side="left", padx=(0, 10))
        tk.Label(channel, text="Chọn kênh rồi bấm Lưu. Thông báo tiếp theo sẽ dùng kênh đã lưu.",
                 bg=PANEL, fg=MUTED, wraplength=620, justify="left").pack(anchor="w", pady=6)
        credentials = tk.Frame(parent, bg=BG)
        credentials.pack(fill="x")
        self.channel_cards = {}
        for value, label in (("telegram", "Telegram"), ("zalo", "Zalo")):
            card = self._card(credentials, label)
            self.channel_cards[value] = card
            self._entry(card, "Bot Token", f"messenger.{value}_bot_token", m.get(f"{value}_bot_token", ""), secret=True)
            self._entry(card, "Chat ID", f"messenger.{value}_chat_id", m.get(f"{value}_chat_id", ""))
            if value == "zalo":
                tk.Label(card, text="Dùng Zalo Bot Token và ID cuộc trò chuyện từ Bot API (không phải số điện thoại).",
                         bg=PANEL, fg=MUTED, wraplength=620, justify="left").pack(anchor="w", pady=6)
                self.zalo_lookup_button = self.master_app._button(
                    card, "LẤY CHAT ID ZALO", self.get_zalo_chat_id, accent=True, width=20)
                self.zalo_lookup_button.pack(anchor="e", pady=8)
                self.zalo_lookup_status = tk.StringVar(value="Bấm Lấy Chat ID, rồi nhắn cho bot từ cuộc trò chuyện muốn nhận thông báo.")
                tk.Label(card, textvariable=self.zalo_lookup_status, bg=PANEL, fg=MUTED,
                         wraplength=620, justify="left").pack(anchor="w", pady=6)
            self.master_app._button(card, f"TEST {label.upper()}",
                lambda selected=value: self.test_notification(selected), accent=True, width=16).pack(anchor="e", pady=8)
        def show_channel(*_):
            for card in self.channel_cards.values():
                card.pack_forget()
            self.channel_cards.get(provider.get(), self.channel_cards["telegram"]).pack(fill="x", pady=(0, 12))
        provider.trace_add("write", show_channel)
        show_channel()
        b = self._card(parent, "Chu kỳ quét Messenger")

        self._entry(b, "Chu kỳ check (s)", "messenger.poll_seconds", m.get("poll_seconds",30))
        self._entry(b, "Tin / Thông báo tối đa (phút)", "messenger.max_age_minutes", m.get("max_age_minutes", m.get("max_message_age_minutes", 30)))
        self._entry(b, "Chống trùng (giờ)", "messenger.dedupe_hours", m.get("dedupe_hours", 24))

        b2 = self._card(parent, "URLs & Facebook Notifications")
        self._entry(b2, "Inbox URL", "messenger.inbox_url", m.get("inbox_url","https://www.messenger.com/"))
        self._entry(b2, "Requests URL", "messenger.requests_url", m.get("requests_url","https://www.messenger.com/requests/"))
        self._entry(b2, "Spam URL", "messenger.spam_url", m.get("spam_url","https://www.messenger.com/requests/spam/"))
        self._entry(b2, "FB Notifications URL", "messenger.notifications_url", m.get("notifications_url","https://www.facebook.com/notifications"))
        self._entry(b2, "Đọc thông báo FB (1=Bật, 0=Tắt)", "messenger.check_notifications", 1 if m.get("check_notifications", True) else 0)
        self._entry(b2, "Dashboard port", "messenger.dashboard_port", m.get("dashboard_port",8000))

    def get_zalo_chat_id(self):
        if getattr(self, "_zalo_lookup_running", False):
            return
        token = self.vars["messenger.zalo_bot_token"].get().strip()
        if not token:
            messagebox.showwarning("DUCTOOL", "Vui lòng nhập Zalo Bot Token trước khi lấy Chat ID.")
            return
        self._zalo_lookup_running = True
        self.zalo_lookup_button.configure(state="disabled")
        self.zalo_lookup_status.set("Đang chờ khoảng 30 giây — hãy gửi một tin nhắn cho bot trên Zalo ngay bây giờ.")
        results = queue.Queue()

        def worker():
            try:
                results.put((asyncio.run(get_zalo_chat(token)), None))
            except Exception as exc:
                results.put((None, str(exc).replace(token, "[ẩn token]")))

        def check_result():
            try:
                chat_id, error = results.get_nowait()
            except queue.Empty:
                self.after(100, check_result)
                return
            self._zalo_lookup_running = False
            self.zalo_lookup_button.configure(state="normal")
            if token != self.vars["messenger.zalo_bot_token"].get().strip() or self.vars["messenger.notification_provider"].get() != "zalo":
                self.zalo_lookup_status.set("Kênh hoặc Token đã thay đổi. Chọn Zalo và bấm Lấy Chat ID để thử lại.")
                return
            if error:
                self.zalo_lookup_status.set(error)
                return
            self.vars["messenger.zalo_chat_id"].set(chat_id)
            self.zalo_lookup_status.set(f"Đã điền Chat ID: {chat_id}. Bấm TEST ZALO để kiểm tra người nhận, rồi LƯU CẤU HÌNH.")

        threading.Thread(target=worker, daemon=True).start()
        self.after(100, check_result)

    def test_notification(self, provider):
        label = "Zalo" if provider == "zalo" else "Telegram"
        settings = {"notification_provider": provider}
        for suffix in ("bot_token", "chat_id"):
            settings[f"{provider}_{suffix}"] = self.vars[f"messenger.{provider}_{suffix}"].get().strip()
        if not settings[f"{provider}_bot_token"] or not settings[f"{provider}_chat_id"]:
            messagebox.showwarning("DUCTOOL", f"Vui lòng nhập {label} Bot Token và Chat ID trước khi test.")
            return
        self.master_app.status_var.set(f"Đang test {label}...")

        def complete(error=None):
            if error:
                self.master_app.status_var.set(f"{label} lỗi")
                messagebox.showerror("DUCTOOL", f"TEST {label.upper()} THẤT BẠI\n\n{error}")
            else:
                self.master_app.status_var.set(f"{label} OK")
                messagebox.showinfo("DUCTOOL", f"Đã gửi tin nhắn test tới {label}.")

        def worker():
            error = None
            try:
                asyncio.run(send_notification(f"✅ TEST {label.upper()} - DUCTOOL", settings))
            except Exception as exc:
                error = str(exc).replace(settings[f"{provider}_bot_token"], "[ẩn token]")
            try:
                self.after(0, lambda message=error: complete(message))
            except (RuntimeError, tk.TclError):
                pass  # Settings window was closed while the request was running.

        threading.Thread(target=worker, daemon=True).start()

    def save(self):
        cfg = load_config()

        def get(key, default=""):
            v = self.vars.get(key)
            return v.get().strip() if v else default

        if self.section == "chrome":
            cfg.setdefault("chrome", {})
            cfg["chrome"]["executable"] = get("chrome.executable")
            cfg["chrome"]["profile_root"] = get("chrome.profile_root")
            cfg["chrome"]["ports"] = {str(i): int(get(f"chrome.port.{i}", str(9310+i)) or (9310+i)) for i in range(1,5)}
            cfg["chrome"]["proxies"] = {str(i): get(f"chrome.proxy.{i}", "") for i in range(1,5)}
            cfg.setdefault("general", {})["chrome_profile_root"] = cfg["chrome"]["profile_root"]
            sel = int(get("general.selected_chrome", str(cfg.get("general", {}).get("selected_chrome", 1))) or 1)
            cfg.setdefault("general", {})["selected_chrome"] = max(1, min(4, sel))
            cfg["chrome"]["default_slot"] = cfg["general"]["selected_chrome"]
            ports = cfg["chrome"]["ports"]
            if all(int(ports[str(i)]) == int(ports["1"]) + (i-1) for i in range(1,5)):
                cfg["general"]["chrome_port_base"] = int(ports["1"]) - 1

        elif self.section == "facebook":
            sel = int(get("general.selected_chrome", "1") or 1)
            cfg.setdefault("general", {})["selected_chrome"] = max(1, min(4, sel))
            cfg.setdefault("chrome", {})["default_slot"] = cfg["general"]["selected_chrome"]
            f = cfg.setdefault("facebook", {})
            f["sheet_url"] = get("facebook.sheet_url")
            f["sheet_csv_url"] = sheet_csv_from_edit_url(f["sheet_url"])

            # Dynamic values are the real source-of-truth now.
            txt_list = [v.get().strip() for _r, v in self.txt_rows if v.get().strip()]
            img_list = [v.get().strip() for _r, v in self.image_rows if v.get().strip()]
            f["txt_files"] = txt_list
            f["content_files"] = txt_list
            f["image_files"] = img_list
            f["content_count"] = max(1, len(txt_list))
            f["image_count"] = max(1, len(img_list))

            # Remove legacy folder settings so UI/source is unambiguous.
            f.pop("txt_dir", None)
            f.pop("image_dir", None)

            f["groups_per_content"] = int(get("facebook.groups_per_content","1") or 1)
            d_min = float(get("facebook.delay_min","5") or 5)
            d_max = float(get("facebook.delay_max","12") or 12)
            f["delay_min"] = d_min
            f["delay_max"] = d_max
            f["delay_between_groups_seconds"] = d_min

            rest_ev = int(get("facebook.rest_every","0") or 0)
            rest_sec = int(get("facebook.rest_seconds","0") or 0)
            f["rest_every"] = rest_ev
            f["jobs_before_break"] = rest_ev
            f["rest_seconds"] = rest_sec
            f["break_after_jobs_seconds"] = rest_sec

            log_f = get("facebook.log_file")
            f["log_file"] = log_f
            if log_f:
                f["log_path"] = log_f

            # Delete deprecated keys from actual config.
            f.pop("state_file", None)
            f.pop("failed_groups_file", None)

        elif self.section == "messenger":
            sel = int(get("general.selected_chrome", "1") or 1)
            cfg.setdefault("general", {})["selected_chrome"] = max(1, min(4, sel))
            cfg.setdefault("chrome", {})["default_slot"] = cfg["general"]["selected_chrome"]
            m = cfg.setdefault("messenger", {})
            m["notification_provider"] = get("messenger.notification_provider", "telegram")
            m["zalo_bot_token"] = get("messenger.zalo_bot_token")
            m["zalo_chat_id"] = get("messenger.zalo_chat_id")
            m["telegram_bot_token"] = get("messenger.telegram_bot_token")
            m["telegram_chat_id"] = get("messenger.telegram_chat_id")
            m["poll_seconds"] = int(get("messenger.poll_seconds","30") or 30)
            age = int(get("messenger.max_age_minutes","30") or 30)
            m["max_age_minutes"] = age
            m["max_message_age_minutes"] = age
            m["dedupe_hours"] = int(get("messenger.dedupe_hours","24") or 24)
            m["inbox_url"] = get("messenger.inbox_url")
            m["requests_url"] = get("messenger.requests_url")
            m["spam_url"] = get("messenger.spam_url")
            m["notifications_url"] = get("messenger.notifications_url", "https://www.facebook.com/notifications").strip()
            check_notif_val = get("messenger.check_notifications", "1").strip()
            m["check_notifications"] = (check_notif_val in ("1", "true", "True", "yes"))
            m["dashboard_port"] = int(get("messenger.dashboard_port","8000") or 8000)

        elif self.section == "collector":
            sel = int(get("general.selected_chrome", "1") or 1)
            cfg.setdefault("general", {})["selected_chrome"] = max(1, min(4, sel))
            cfg.setdefault("chrome", {})["default_slot"] = cfg["general"]["selected_chrome"]
            col = cfg.setdefault("collector", {})
            col["sheet_url"] = get("collector.sheet_url").strip()
            col["fields"] = get("collector.fields", "123").strip()
            col["tab_count"] = max(1, min(10, int(get("collector.tab_count", "3") or 3)))

        else:
            sel = int(get("general.selected_chrome", "1") or 1)
            cfg.setdefault("general", {})["selected_chrome"] = max(1, min(4, sel))
            cfg.setdefault("chrome", {})["default_slot"] = cfg["general"]["selected_chrome"]
            j = cfg.setdefault("joiner", {})
            j["sheet_url"] = get("joiner.sheet_url").strip()
            j["tab_count"] = max(1, min(10, int(get("joiner.tab_count", "1") or 1)))
            j["delay_seconds"] = max(0, int(get("joiner.delay_seconds", "10") or 10))

        save_config(cfg)
        self.master_app.cfg = cfg
        self.master_app.status_var.set("Đã lưu cấu hình")
        messagebox.showinfo("DUCTOOL", "Đã lưu cấu hình thật vào config.json")


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()

    if len(sys.argv) == 2 and sys.argv[1] == "--version":
        sys.exit(0)
    elif len(sys.argv) > 2 and sys.argv[1] == "--mode":
        mode = sys.argv[2].lower()
        if mode in ("facebook", "fb"):
            run_facebook_module()
        elif mode in ("messenger", "msg"):
            run_messenger_module()
        elif mode in ("collector", "group-collector", "groups"):
            run_group_collector_module()
        elif mode in ("joiner", "group-join", "auto-join"):
            run_group_join_module()
        elif mode in ("renamer", "rename", "image-renamer", "image"):
            run_image_renamer_module()
        elif mode == "test-chrome":
            ensure_console("DUCTOOL — Test Chrome")
            base = Path(__file__).resolve().parent
            msg_dir = base / "AUTO_CHECK_MESSENGER"
            if str(base) not in sys.path:
                sys.path.insert(0, str(base))
            if str(msg_dir) not in sys.path:
                sys.path.insert(0, str(msg_dir))
            import asyncio
            from AUTO_CHECK_MESSENGER.test_chrome import main as test_chrome_main
            asyncio.run(test_chrome_main())
            try:
                input("\nNhấn Enter để đóng...")
            except Exception:
                pass
            sys.exit(0)
        else:
            print(f"Unknown mode: {mode}")
            sys.exit(1)
    else:
        App().mainloop()
