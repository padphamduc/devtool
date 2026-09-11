# -*- coding: utf-8 -*-
import os
import re
import uuid
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff"}

# Theme matching DUCTOOL
BG = "#0B0F16"
TOP = "#111722"
PANEL = "#151C28"
BORDER = "#2B3648"
TEXT = "#F8FAFC"
MUTED = "#A6B1C3"
PURPLE = "#8B5CF6"
PURPLE_HOVER = "#7C3AED"
INPUT_BG = "#0E1520"


class ImageRenamerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Đổi tên ảnh hàng loạt — DUCTOOL")
        self.root.geometry("820x620")
        self.root.minsize(720, 520)
        self.root.configure(bg=BG)

        self.folder_var = tk.StringVar()
        self.format_var = tk.StringVar(value="anh_{n}")
        self.ext_var = tk.StringVar(value="Giữ nguyên")

        # Configure dark ttk style
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure("Treeview",
                        background=PANEL,
                        foreground=TEXT,
                        fieldbackground=PANEL,
                        rowheight=26,
                        font=("Segoe UI", 9))
        style.map("Treeview", background=[('selected', PURPLE)])
        style.configure("Treeview.Heading",
                        background=TOP,
                        foreground=TEXT,
                        font=("Segoe UI", 10, "bold"))

        frm = tk.Frame(root, bg=BG, padx=16, pady=16)
        frm.pack(fill="both", expand=True)

        tk.Label(frm, text="Folder chứa ảnh:", bg=BG, fg=TEXT, font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w")
        
        folder_row = tk.Frame(frm, bg=BG)
        folder_row.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 12))
        
        entry_folder = tk.Entry(folder_row, textvariable=self.folder_var, bg=INPUT_BG, fg=TEXT, insertbackground=TEXT, relief="flat", font=("Segoe UI", 10))
        entry_folder.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 8))
        
        btn_browse = tk.Button(folder_row, text="📁 Chọn folder", command=self.choose_folder, bg=PURPLE, fg="white", activebackground=PURPLE_HOVER, activeforeground="white", bd=0, relief="flat", cursor="hand2", font=("Segoe UI", 9, "bold"), padx=14, pady=6)
        btn_browse.pack(side="right")

        tk.Label(frm, text="Format tên (dùng {n} cho số thứ tự, vd: anh_{n}):", bg=BG, fg=TEXT, font=("Segoe UI", 10, "bold")).grid(row=2, column=0, sticky="w")
        
        fmt_row = tk.Frame(frm, bg=BG)
        fmt_row.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(4, 12))
        
        entry_fmt = tk.Entry(fmt_row, textvariable=self.format_var, bg=INPUT_BG, fg=TEXT, insertbackground=TEXT, relief="flat", font=("Segoe UI", 10))
        entry_fmt.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 8))
        
        btn_preview = tk.Button(fmt_row, text="👁️ Xem trước", command=self.preview, bg="#2A3445", fg="white", activebackground="#364258", activeforeground="white", bd=0, relief="flat", cursor="hand2", font=("Segoe UI", 9, "bold"), padx=14, pady=6)
        btn_preview.pack(side="right")

        tk.Label(frm, text="Đuôi file:", bg=BG, fg=TEXT, font=("Segoe UI", 10, "bold")).grid(row=4, column=0, sticky="w")
        ext_frame = tk.Frame(frm, bg=BG)
        ext_frame.grid(row=5, column=0, columnspan=2, sticky="w", pady=(4, 8))

        self.ext_combo = ttk.Combobox(
            ext_frame,
            textvariable=self.ext_var,
            values=["Giữ nguyên", ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff"],
            width=18
        )
        self.ext_combo.pack(side="left")
        self.ext_combo.bind("<<ComboboxSelected>>", lambda e: self.preview())
        self.ext_combo.bind("<KeyRelease>", lambda e: self.preview())

        tk.Label(
            ext_frame,
            text="  (Có thể tự nhập, ví dụ: .avif)",
            bg=BG, fg=MUTED, font=("Segoe UI", 9)
        ).pack(side="left")

        tk.Label(
            frm,
            text="★ Sắp xếp tự nhiên theo tên A-Z, 0-9 trước khi đánh số (vd: a1, a2, a10...).",
            bg=BG, fg="#38BDF8", font=("Segoe UI", 9)
        ).grid(row=6, column=0, columnspan=2, sticky="w", pady=(2, 8))

        # Treeview frame
        tree_frame = tk.Frame(frm, bg=BG)
        tree_frame.grid(row=7, column=0, columnspan=2, sticky="nsew")

        self.tree = ttk.Treeview(tree_frame, columns=("old", "new"), show="headings")
        self.tree.heading("old", text="Tên file hiện tại")
        self.tree.heading("new", text="Tên file mới")
        self.tree.column("old", width=370)
        self.tree.column("new", width=370)
        self.tree.pack(side="left", fill="both", expand=True)

        scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")

        btns = tk.Frame(frm, bg=BG)
        btns.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        
        btn_rename = tk.Button(btns, text="⚡ ĐỔI TÊN TẤT CẢ", command=self.rename_all, bg=PURPLE, fg="white", activebackground=PURPLE_HOVER, activeforeground="white", bd=0, relief="flat", cursor="hand2", font=("Segoe UI", 10, "bold"), padx=20, pady=8)
        btn_rename.pack(side="left")

        btn_exit = tk.Button(btns, text="Thoát", command=root.destroy, bg="#2A3445", fg="white", activebackground="#364258", activeforeground="white", bd=0, relief="flat", cursor="hand2", font=("Segoe UI", 10, "bold"), padx=18, pady=8)
        btn_exit.pack(side="right")

        frm.columnconfigure(0, weight=1)
        frm.rowconfigure(7, weight=1)

        self.format_var.trace_add("write", lambda *args: self.preview())

    def choose_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.folder_var.set(folder)
            self.preview()

    def get_images(self):
        folder_text = self.folder_var.get().strip()
        if not folder_text:
            return []
        folder = Path(folder_text)
        if not folder.is_dir():
            return []
        files = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS]

        def natural_key(path):
            parts = re.split(r"(\d+)", path.name.lower())
            return [int(part) if part.isdigit() else part for part in parts]

        return sorted(files, key=natural_key)

    def selected_extension(self, original_ext):
        value = self.ext_var.get().strip()
        if not value or value.lower() == "giữ nguyên":
            return original_ext.lower()

        if not value.startswith("."):
            value = "." + value

        if any(ch in value for ch in '<>:"/\\|?* '):
            raise ValueError("Đuôi file không hợp lệ.")

        return value.lower()

    def build_new_name(self, index, original_ext):
        fmt = self.format_var.get().strip()
        if not fmt:
            raise ValueError("Bạn chưa nhập format tên.")

        base = fmt.replace("{n}", str(index)) if "{n}" in fmt else f"{fmt}{index}"

        invalid = '<>:"/\\|?*'
        if any(ch in base for ch in invalid):
            raise ValueError('Tên chứa ký tự không hợp lệ: < > : " / \\ | ? *')

        return base + self.selected_extension(original_ext)

    def preview(self):
        if not hasattr(self, "tree"):
            return
        for item in self.tree.get_children():
            self.tree.delete(item)

        images = self.get_images()
        if not images:
            return

        try:
            for i, path in enumerate(images, start=1):
                self.tree.insert("", "end", values=(path.name, self.build_new_name(i, path.suffix)))
        except ValueError:
            pass

    def rename_all(self):
        folder_text = self.folder_var.get().strip()
        if not folder_text:
            messagebox.showerror("Lỗi", "Vui lòng chọn folder.")
            return

        folder = Path(folder_text)
        images = self.get_images()

        if not folder.is_dir():
            messagebox.showerror("Lỗi", "Vui lòng chọn folder hợp lệ.")
            return
        if not images:
            messagebox.showwarning("Không có ảnh", "Không tìm thấy ảnh trong folder.")
            return

        try:
            plan = []
            new_names = set()

            for i, path in enumerate(images, start=1):
                new_name = self.build_new_name(i, path.suffix)
                key = new_name.lower()
                if key in new_names:
                    raise ValueError(f"Tên bị trùng: {new_name}")
                new_names.add(key)
                plan.append((path, folder / new_name))

            warning = (
                f"Sẽ đổi tên {len(plan)} ảnh.\n\n"
                "Lưu ý: đổi đuôi file chỉ thay phần mở rộng của tên file, "
                "không chuyển đổi định dạng dữ liệu ảnh.\n\n"
                "Bạn có muốn tiếp tục?"
            )
            if not messagebox.askyesno("Xác nhận", warning):
                return

            temp_plan = []
            for old_path, final_path in plan:
                temp_path = folder / f".__rename_tmp_{uuid.uuid4().hex}{old_path.suffix}"
                os.rename(old_path, temp_path)
                temp_plan.append((temp_path, final_path))

            for temp_path, final_path in temp_plan:
                os.rename(temp_path, final_path)

            self.preview()
            messagebox.showinfo("Hoàn tất", f"Đã đổi tên {len(plan)} ảnh thành công.")

        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể đổi tên ảnh:\n{e}")


def main():
    root = tk.Tk()
    app = ImageRenamerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
