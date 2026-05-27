import tkinter as tk
from tkinter import filedialog, scrolledtext, simpledialog, messagebox
import shutil
import os
import random
import time
import subprocess
from PIL import Image, ImageTk
import win32gui
import win32con
import win32api
from main import otica_respond, model, hearing, start_gaq_loop
from otica_emoji import load_emoji_library
from otica_filesystem import OTICA_SHARED_ROOT, otica_list_shared, otica_read_shared
from otica_search import hybrid_search_with_vision
from otica_tts import speak


icons = ['💙', '🧐', '🤝', '✨', '🔥', '🧩', '💪', '🧪', '🌫️', '🔍', '🔄',
         '⏳', '⚖️', '👁️', '⚡', '💥', '❓', '🛑', '🌀', '🚫', '⚠️', '🌪️']


def bring_window_to_front(title_substring):
    def enum_handler(hwnd, result_list):
        if win32gui.IsWindowVisible(hwnd):
            window_text = win32gui.GetWindowText(hwnd)
            if title_substring.lower() in window_text.lower():
                result_list.append(hwnd)

    matches = []
    win32gui.EnumWindows(enum_handler, matches)

    if not matches:
        return False

    hwnd = matches[0]

    # Restore if minimized
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

    # Bring to foreground
    win32gui.SetForegroundWindow(hwnd)

    return True

class OticaUI:
    def __init__(self):
        self.window = tk.Tk()
        self.window.title("Otica — Thinking Interface")
        self.window.geometry("1000x700")
        self.window.configure(bg="#0A1F44")

        self.emoji_library = load_emoji_library()

        # Fallback icon; will be overridden by dominant emotion emoji
        self.sel_icon = random.choice(icons)

        # Placeholder temperatures (wire to sensors later)
        self.otica_temperature = "--.-°C"
        self.outside_temperature = "--.-°C"

        # -------------------------
        # TOP BAR
        # -------------------------
        top_frame = tk.Frame(self.window, bg="#0A1F44")
        top_frame.pack(fill=tk.X, pady=5)

        self.otica_label = tk.Label(
            top_frame,
            text=f"Otica {self.sel_icon}",
            font=("Arial", 18, "bold"),
            fg="#93C5FD",
            bg="#0A1F44"
        )
        self.otica_label.pack(side=tk.LEFT, padx=10)

        middle_frame = tk.Frame(top_frame, bg="#0A1F44")
        middle_frame.pack(side=tk.LEFT, expand=True, fill=tk.X)

        # -------------------------
        # DIRECTORY + PREVIEW STRIP
        # -------------------------
        top_strip = tk.Frame(middle_frame, bg="#0A1F44")
        top_strip.pack(anchor="n", fill=tk.X)

        # LEFT: Directory Browser
        dir_frame = tk.Frame(top_strip, bg="#1E3A8A", width=250, height=130)
        dir_frame.pack(side=tk.LEFT, anchor="s")
        dir_frame.pack_propagate(False)

        dir_label = tk.Label(
            dir_frame,
            text="Otica Files",
            bg="#1E3A8A",
            fg="#93C5FD",
            font=("Arial", 12, "bold")
        )
        dir_label.pack(pady=5)

        self.dir_list = tk.Listbox(dir_frame, bg="#F1F5F9")
        self.dir_list.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.dir_list.bind("<<ListboxSelect>>", self.on_dir_select)

        # PREVIEW
        preview_container = tk.Frame(top_strip, bg="#1E3A8A")
        preview_container.pack(side=tk.LEFT, anchor="s", padx=(5, 5))

        preview_frame = tk.Frame(preview_container, bg="#1E3A8A", width=250, height=250)
        preview_frame.pack(side=tk.BOTTOM)
        preview_frame.pack_propagate(False)

        preview_label = tk.Label(
            preview_frame,
            text="Preview",
            bg="#1E3A8A",
            fg="#93C5FD",
            font=("Arial", 12, "bold")
        )
        preview_label.pack(pady=5)

        self.preview_canvas = tk.Label(preview_frame, bg="#0A1F44")
        self.preview_canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # CLOCK + TEMPERATURES (between preview and emotional state)
        status_strip = tk.Frame(top_strip, bg="#0A1F44")
        status_strip.pack(side=tk.LEFT, anchor="n", padx=(10, 10))

        self.clock_label = tk.Label(
            status_strip,
            text="--:--:--",
            font=("Arial", 11, "bold"),
            fg="#E5E7EB",
            bg="#0A1F44"
        )
        self.clock_label.pack(anchor="w")

        self.otica_temp_label = tk.Label(
            status_strip,
            text=f"Otica Temperature: {self.otica_temperature}",
            font=("Arial", 10),
            fg="#93C5FD",
            bg="#0A1F44"
        )
        self.otica_temp_label.pack(anchor="w", pady=(4, 0))

        self.outside_temp_label = tk.Label(
            status_strip,
            text=f"Outside Temperature: {self.outside_temperature}",
            font=("Arial", 10),
            fg="#93C5FD",
            bg="#0A1F44"
        )
        self.outside_temp_label.pack(anchor="w")

        # Emotional State Panel
        emotion_frame = tk.Frame(top_frame, bg="#0A1F44")
        emotion_frame.pack(side=tk.RIGHT, padx=10)

        title = tk.Label(
            emotion_frame,
            text="Emotional State",
            font=("Arial", 12, "bold"),
            fg="#93C5FD",
            bg="#0A1F44"
        )
        title.pack()

        self.emotion_panel = scrolledtext.ScrolledText(
            emotion_frame,
            width=30,
            height=5,
            wrap=tk.WORD,
            bg="#0A1F44",
            fg="#93C5FD",
            font=("Arial", 10),
            borderwidth=0,
            highlightthickness=0
        )
        self.emotion_panel.pack()
        self.emotion_panel.configure(state='disabled')

        # -------------------------
        # MAIN LAYOUT
        # -------------------------
        main_frame = tk.Frame(self.window, bg="#0A1F44")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # LEFT PANEL
        left_panel = tk.Frame(main_frame, width=250, bg="#1E3A8A")
        left_panel.pack(side=tk.LEFT, fill=tk.Y)
        left_panel.pack_propagate(False)

        send_file_btn = tk.Button(
            left_panel,
            text="Send File to Otica",
            command=self.send_file,
            bg="#3B82F6",
            fg="white"
        )
        send_file_btn.pack(pady=10, padx=10, fill=tk.X)

        self.file_list_box = tk.Listbox(left_panel, bg="#F1F5F9")
        self.file_list_box.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        refresh_btn = tk.Button(
            left_panel,
            text="Refresh Files",
            command=self.refresh_file_list,
            bg="#3B82F6",
            fg="white"
        )
        refresh_btn.pack(pady=5, padx=10, fill=tk.X)

        read_file_btn = tk.Button(
            left_panel,
            text="Read Selected File",
            command=self.read_selected_file,
            bg="#2563EB",
            fg="white"
        )
        read_file_btn.pack(pady=5, padx=10, fill=tk.X)

        emoji_label = tk.Label(
            left_panel,
            text="Emoji Library",
            bg="#1E3A8A",
            fg="#93C5FD",
            font=("Arial", 11, "bold")
        )
        emoji_label.pack(pady=(15, 3))

        emoji_frame = tk.Frame(left_panel, bg="#1E3A8A")
        emoji_frame.pack(fill=tk.X, padx=5)

        for emo, emoji in self.emoji_library.items():
            lbl = tk.Label(
                emoji_frame,
                text=f"{emoji} {emo}",
                bg="#1E3A8A",
                fg="#F1F5F9",
                anchor="w",
                font=("Arial", 9)
            )
            lbl.pack(fill=tk.X)

        # -------------------------
        # CHAT PANEL
        # -------------------------
        chat_frame = tk.Frame(main_frame, bg="#0A1F44")
        chat_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Chat box (reduced vertical dominance by pairing with search + taskbar)
        self.chat_box = scrolledtext.ScrolledText(
            chat_frame,
            wrap=tk.WORD,
            state='disabled',
            bg="#F1F5F9",
            fg="black",
        )
        self.chat_box.pack(padx=10, pady=(10, 5), fill=tk.BOTH, expand=True)

        self.search_results_box = scrolledtext.ScrolledText(
            chat_frame,
            wrap=tk.WORD,
            state='disabled',
            height=6,
            bg="#F1F5F9",
            fg="black"
        )
        self.search_results_box.pack(padx=10, pady=(0, 5), fill=tk.BOTH)

        search_frame = tk.Frame(chat_frame, bg="#0A1F44")
        search_frame.pack(fill=tk.X, padx=10, pady=(5, 0))

        self.search_field = tk.Entry(search_frame, font=("Arial", 12))
        self.search_field.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        search_button = tk.Button(
            search_frame,
            text="Search",
            command=self.run_search,
            bg="#3B82F6",
            fg="white"
        )
        search_button.pack(side=tk.RIGHT)

        # -------------------------
        # INPUT BAR + LISTEN BUTTON
        # -------------------------
        input_frame = tk.Frame(chat_frame, bg="#0A1F44")
        input_frame.pack(fill=tk.X, padx=10, pady=10)

        self.input_field = tk.Text(input_frame, font=("Arial", 12), height=3)
        self.input_field.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        self.listen_button = tk.Button(
            input_frame,
            text="🎤 Listen",
            command=self.on_listen_button_pressed,
            bg="#10B981",
            fg="white",
            width=10
        )
        self.listen_button.pack(side=tk.RIGHT, padx=(0, 10))

        send_button = tk.Button(
            input_frame,
            text="Send",
            command=self.send_message,
            bg="#3B82F6",
            fg="white"
        )
        send_button.pack(side=tk.RIGHT)

        self.input_field.bind("<Return>", self._on_enter)
        self.input_field.bind("<Shift-Return>", self._on_shift_enter)

        # -------------------------
        # BOTTOM TASKBAR
        # -------------------------
        taskbar = tk.Frame(self.window, bg="#020617", height=32)
        taskbar.pack(side=tk.BOTTOM, fill=tk.X)

        # Simple emoji-based "OS" icons
        logs_btn = tk.Button(
            taskbar,
            text="📜 Logs",
            bg="#020617",
            fg="#E5E7EB",
            relief=tk.FLAT,
            command=self._open_logs_window
        )
        logs_btn.pack(side=tk.LEFT, padx=8, pady=2)

        status_btn = tk.Button(
            taskbar,
            text="🧠 Status",
            bg="#020617",
            fg="#E5E7EB",
            relief=tk.FLAT,
            command=self._open_status_window
        )
        status_btn.pack(side=tk.LEFT, padx=8, pady=2)

        cmd_btn = tk.Button(
            taskbar,
            text="🔐 CMD",
            bg="#020617",
            fg="#E5E7EB",
            relief=tk.FLAT,
            command=self._open_cmd_window
        )
        cmd_btn.pack(side=tk.LEFT, padx=8, pady=2)

        devtools_btn = tk.Button(
            taskbar,
            text="🛠️ Dev Tools",
            bg="#020617",
            fg="#E5E7EB",
            relief=tk.FLAT,
            command=self._open_devtools_window
        )
        devtools_btn.pack(side=tk.LEFT, padx=8, pady=2)

        # -------------------------
        # INITIAL LOAD + LOOPS
        # -------------------------
        self.refresh_file_list()
        self.load_directory_tree()
        self._schedule_directory_refresh()

        # Start GAQ loop
        start_gaq_loop(self._append_text_from_percept)

        # Poll hearing state
        self.window.after(100, self._poll_hearing_state)

        # Poll emotional state
        self.window.after(500, self._poll_emotional_state)

        # Clock + temperature updater
        self.window.after(1000, self._update_clock_and_temps)

    # -------------------------
    # LISTEN BUTTON CALLBACK
    # -------------------------
    def on_listen_button_pressed(self):
        if hearing.is_listening():
            hearing.stop_listening()
            return

        self.listen_button.configure(text="Listening...", bg="#EF4444")
        hearing.start_push_to_talk()

    def _poll_hearing_state(self):
        if hearing.is_listening():
            self.listen_button.configure(text="Listening...", bg="#EF4444")
        else:
            self.listen_button.configure(text="🎤 Listen", bg="#10B981")
        self.window.after(100, self._poll_hearing_state)

    # -------------------------
    # GAQ CALLBACK
    # -------------------------
    def _append_text_from_percept(self, percept, reply):
        self._append_text(f"You (via {percept.source}): {percept.content}\n")
        self._append_text(f"Otica: {reply}\n\n")
        speak(reply)

    # -------------------------
    # SEARCH
    # -------------------------
    def run_search(self):
        query = self.search_field.get().strip()
        if not query:
            return

        from main import current_emotional_state

        results = hybrid_search_with_vision(query, current_emotional_state, model=model)

        self.search_results_box.configure(state='normal')
        self.search_results_box.delete(1.0, tk.END)

        self.search_results_box.insert(tk.END, f"Search Mode: {results['source']}\n\n")

        self.search_results_box.insert(tk.END, "Local Results:\n")
        for item in results.get("local_results", []):
            self.search_results_box.insert(tk.END, f"- {item}\n")
        self.search_results_box.insert(tk.END, "\n")

        self.search_results_box.insert(tk.END, "Web Results:\n")
        self.search_results_box.insert(tk.END, f"{results.get('web_results', '')}\n\n")

        if "vision_analysis" in results:
            self.search_results_box.insert(tk.END, "Vision Analysis:\n")
            for item in results["vision_analysis"]:
                self.search_results_box.insert(tk.END, f"- File: {item['file']}\n")
                self.search_results_box.insert(tk.END, f"  Analysis: {item['analysis']}\n\n")

        self.search_results_box.configure(state='disabled')
        self.search_results_box.see(tk.END)

    # -------------------------
    # FILE SENDING
    # -------------------------
    def send_file(self):
        file_path = filedialog.askopenfilename()
        if not file_path:
            return

        incoming_folder = OTICA_SHARED_ROOT / "incoming"
        incoming_folder.mkdir(parents=True, exist_ok=True)

        shutil.copy(file_path, incoming_folder)
        self._append_text(f"System: File sent to Otica: {os.path.basename(file_path)}\n")
        self.refresh_file_list()

    def refresh_file_list(self):
        self.file_list_box.delete(0, tk.END)
        for f in otica_list_shared("incoming"):
            self.file_list_box.insert(tk.END, f)

    def read_selected_file(self):
        selection = self.file_list_box.curselection()
        if not selection:
            self._append_text("System: No file selected.\n")
            return

        filename = self.file_list_box.get(selection[0])
        relative_path = f"incoming/{filename}"

        self._append_text(f"You (file): {filename}\n")
        otica_reply = otica_respond(f"[FILE]{relative_path}")

        self._append_text(f"Otica: {otica_reply}\n\n")
        speak(otica_reply)

    # -------------------------
    # CHAT
    # -------------------------
    def _on_enter(self, event):
        self.send_message()
        return "break"

    def _on_shift_enter(self, event):
        return

    def send_message(self):
        user_message = self.input_field.get("1.0", tk.END).strip()
        if not user_message:
            return

        self._append_text(f"You: {user_message}\n")
        self.input_field.delete("1.0", tk.END)

        otica_reply = otica_respond(user_message)
        self._append_text(f"Otica: {otica_reply}\n\n")

        speak(otica_reply)

    def _append_text(self, text):
        self.chat_box.configure(state='normal')
        self.chat_box.insert(tk.END, text)
        self.chat_box.configure(state='disabled')
        self.chat_box.see(tk.END)

    # -------------------------
    # EMOTIONAL STATE POLLING
    # -------------------------
    def _poll_emotional_state(self):
        from main import current_emotional_state, current_emotional_mode

        text = ""
        for emo, value in current_emotional_state.items():
            emoji = self.emoji_library.get(emo, "")
            text += f"{emoji} {emo}: {value:.2f}\n"

        text += f"\nMode: {current_emotional_mode}"

        self.emotion_panel.configure(state='normal')
        self.emotion_panel.delete(1.0, tk.END)
        self.emotion_panel.insert(tk.END, text)
        self.emotion_panel.configure(state='disabled')

        # Use dominant emotional mode's emoji if available
        dominant_emoji = self.emoji_library.get(current_emotional_mode, self.sel_icon)
        self.sel_icon = dominant_emoji

        # Update top label text
        self.otica_label.config(
            text=f"Otica {self.sel_icon} : {current_emotional_mode.capitalize()}"
        )

        self.window.after(500, self._poll_emotional_state)

    # -------------------------
    # CLOCK + TEMPERATURE UPDATER
    # -------------------------
    def _update_clock_and_temps(self):
        now = time.strftime("%H:%M:%S  %d %b %Y")
        self.clock_label.config(text=now)

        # Temperatures are placeholders; update externally when sensors are wired
        self.otica_temp_label.config(
            text=f"Otica Temperature: {self.otica_temperature}"
        )
        self.outside_temp_label.config(
            text=f"Outside Temperature: {self.outside_temperature}"
        )

        self.window.after(1000, self._update_clock_and_temps)

    # -------------------------
    # DIRECTORY TREE
    # -------------------------
    def load_directory_tree(self):
        """
        Loads otica_shared/ and otica_private/ directories into the directory list.
        Only shows files and folders inside those roots.
        """
        self.dir_list.delete(0, tk.END)

        base = os.path.dirname(os.path.abspath(__file__))
        roots = [
            os.path.join(base, "otica_shared"),
            os.path.join(base, "otica_private")
        ]

        for root in roots:
            if os.path.isdir(root):
                for path, dirs, files in os.walk(root):
                    for f in files:
                        full_path = os.path.join(path, f)
                        rel = os.path.relpath(full_path, base)
                        self.dir_list.insert(tk.END, rel)

    def _select_most_recent_file(self):
        """
        Selects the most recently modified file in the directory list.
        """
        count = self.dir_list.size()
        if count == 0:
            return

        newest_index = None
        newest_mtime = -1

        for i in range(count):
            rel_path = self.dir_list.get(i)
            full_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), rel_path)

            if os.path.isfile(full_path):
                mtime = os.path.getmtime(full_path)
                if mtime > newest_mtime:
                    newest_mtime = mtime
                    newest_index = i

        if newest_index is not None:
            self.dir_list.selection_clear(0, tk.END)
            self.dir_list.selection_set(newest_index)
            self.dir_list.see(newest_index)
            self.on_dir_select(None)

    def _schedule_directory_refresh(self):
        self.load_directory_tree()
        self._select_most_recent_file()
        self.window.after(15000, self._schedule_directory_refresh)

    def on_dir_select(self, event):
        """
        When the user selects a file, attempt to preview it if it's an image.
        """
        selection = self.dir_list.curselection()
        if not selection:
            return

        filepath = self.dir_list.get(selection[0])

        if not filepath.lower().endswith((".png", ".jpg", ".jpeg")):
            self.preview_canvas.config(image="", text="(Not an image)")
            return

        try:
            img = Image.open(filepath)
            img.thumbnail((280, 140))
            self.preview_img = ImageTk.PhotoImage(img)
            self.preview_canvas.config(image=self.preview_img, text="")
        except Exception:
            self.preview_canvas.config(text="(Unable to preview image)")

    # -------------------------
    # TASKBAR WINDOWS (PLACEHOLDERS)
    # -------------------------
    def _open_logs_window(self):
        win = tk.Toplevel(self.window)
        win.title("Otica Logs")
        win.configure(bg="#020617")
        win.geometry("600x400")

        lbl = tk.Label(
            win,
            text="Logs window (placeholder)\nWe’ll wire this to GAQ / system logs.",
            bg="#020617",
            fg="#E5E7EB",
            font=("Arial", 11)
        )
        lbl.pack(padx=10, pady=10)

    def _open_status_window(self):
        win = tk.Toplevel(self.window)
        win.title("Technical Status")
        win.configure(bg="#020617")
        win.geometry("600x400")

        lbl = tk.Label(
            win,
            text="Technical Status window (placeholder)\nHere we’ll show system health, GPU/CPU, queues, etc.",
            bg="#020617",
            fg="#E5E7EB",
            font=("Arial", 11)
        )
        lbl.pack(padx=10, pady=10)

    def _prompt_restricted_access(self, label="Restricted"):
        password = simpledialog.askstring(
            f"{label} Access",
            "Enter access password:",
            show="*",
            parent=self.window
        )
        # Simple placeholder check; replace with your own auth later
        if password != "otica-dev":
            messagebox.showerror("Access Denied", "Incorrect password.")
            return False
        return True

    def _open_cmd_window(self):
        if not self._prompt_restricted_access("CMD"):
            return

        # Try to bring existing CMD window forward
        if bring_window_to_front("cmd"):
            return

        # If no CMD window exists, open a new one
        subprocess.Popen(["cmd.exe"], creationflags=subprocess.CREATE_NEW_CONSOLE)

    def _open_devtools_window(self):
        if not self._prompt_restricted_access("Dev Tools"):
            return

        win = tk.Toplevel(self.window)
        win.title("Dev Tools (Restricted)")
        win.configure(bg="#020617")
        win.geometry("700x500")

        top = tk.Frame(win, bg="#020617")
        top.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Skills list placeholder
        skills_frame = tk.LabelFrame(
            top,
            text="Skills",
            bg="#020617",
            fg="#E5E7EB",
            font=("Arial", 11, "bold"),
            labelanchor="n"
        )
        skills_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        skills_text = scrolledtext.ScrolledText(
            skills_frame,
            wrap=tk.WORD,
            bg="#020617",
            fg="#E5E7EB",
            insertbackground="#E5E7EB"
        )
        skills_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        skills_text.insert(tk.END, "Skills list placeholder.\nWe’ll populate this from Otica’s skill registry.")
        skills_text.configure(state='disabled')

        # Tiers + buttons
        right_frame = tk.Frame(top, bg="#020617")
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))

        tiers_frame = tk.LabelFrame(
            right_frame,
            text="Current Tiers",
            bg="#020617",
            fg="#E5E7EB",
            font=("Arial", 11, "bold"),
            labelanchor="n"
        )
        tiers_frame.pack(fill=tk.X, pady=(0, 10))

        tiers = [
            "Cognition: Tier ?",
            "Perception: Tier ?",
            "Physical Creativity: Tier ?",
            "Digital Creativity: Tier ?",
        ]
        for t in tiers:
            tk.Label(
                tiers_frame,
                text=t,
                bg="#020617",
                fg="#E5E7EB",
                anchor="w",
                font=("Arial", 10)
            ).pack(fill=tk.X, padx=5, pady=2)

        btns_frame = tk.Frame(right_frame, bg="#020617")
        btns_frame.pack(fill=tk.X)

        comfy_btn = tk.Button(
            btns_frame,
            text="🧩 Open ComfyUI",
            bg="#111827",
            fg="#E5E7EB",
            command=self._open_comfyui
        )
        comfy_btn.pack(fill=tk.X, pady=(0, 5))

        desktop_btn = tk.Button(
            btns_frame,
            text="🪟 Show Windows Desktop",
            bg="#111827",
            fg="#E5E7EB",
            command=self._show_windows_desktop
        )
        desktop_btn.pack(fill=tk.X)

    def _open_comfyui(self):
        # Try to bring ComfyUI Desktop to front
        if bring_window_to_front("ComfyUI"):
            return

        # If not found, try alternate title
        if bring_window_to_front("ComfyUI Desktop"):
            return

        messagebox.showerror("ComfyUI", "ComfyUI window not found. Is it running?")

    def _show_windows_desktop(self):
        try:
            # Minimize all windows
            subprocess.Popen([
                "powershell",
                "-Command",
                "(New-Object -ComObject Shell.Application).MinimizeAll()"
            ])

            # Ensure Explorer is running (restores desktop if hidden)
            explorer_running = subprocess.run(
                ["powershell", "-Command", "Get-Process explorer -ErrorAction SilentlyContinue"],
                capture_output=True, text=True
            )

            if explorer_running.returncode != 0:
                subprocess.Popen(["explorer.exe"])

            # Also minimize Otica UI itself
            self.window.iconify()

        except Exception as e:
            messagebox.showerror("Desktop Error", f"Failed to show desktop: {e}")

    # -------------------------
    # MAIN LOOP
    # -------------------------
    def run(self):
        self.window.mainloop()


if __name__ == "__main__":
    ui = OticaUI()
    ui.run()
