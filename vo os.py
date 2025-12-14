import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import time
import threading
import random
import json
import os
from datetime import datetime


class Process:
    """Simulates an OS process with PID, state, and resource usage"""

    def __init__(self, pid, name, memory_req, priority=1):
        self.pid = pid
        self.name = name
        self.state = "READY"  # READY, RUNNING, BLOCKED, TERMINATED
        self.memory_req = memory_req  # in MB
        self.memory_address = None
        self.priority = priority
        self.cpu_time = 0
        self.creation_time = time.time()

    def __str__(self):
        return f"Process {self.pid}: {self.name} ({self.state})"


class MemoryManager:
    """Manages memory allocation using a simple segmentation approach"""

    def __init__(self, total_memory=1024):  # 1024 MB total memory
        self.total_memory = total_memory
        self.available_memory = total_memory
        # Memory blocks: (start_address, size, is_free)
        self.memory_blocks = [(0, total_memory, True)]

    def allocate(self, size):
        """First-fit memory allocation algorithm"""
        for i, (start, block_size, is_free) in enumerate(self.memory_blocks):
            if is_free and block_size >= size:
                # Allocate memory
                self.memory_blocks[i] = (start, size, False)

                # If there's remaining space, create a new free block
                if block_size > size:
                    self.memory_blocks.insert(i + 1, (start + size, block_size - size, True))

                self.available_memory -= size
                return start
        return None  # No suitable memory block found

    def deallocate(self, address):
        """Free memory at the given address and merge adjacent free blocks"""
        for i, (start, size, is_free) in enumerate(self.memory_blocks):
            if start == address and not is_free:
                # Mark block as free
                self.memory_blocks[i] = (start, size, True)
                self.available_memory += size

                # Merge with adjacent free blocks
                self._merge_free_blocks()
                return True
        return False

    def _merge_free_blocks(self):
        """Merge adjacent free memory blocks"""
        i = 0
        while i < len(self.memory_blocks) - 1:
            curr_start, curr_size, curr_free = self.memory_blocks[i]
            next_start, next_size, next_free = self.memory_blocks[i + 1]

            if curr_free and next_free:
                # Merge blocks
                self.memory_blocks[i] = (curr_start, curr_size + next_size, True)
                self.memory_blocks.pop(i + 1)
            else:
                i += 1


class FileSystem:
    """Simple file system implementation"""

    def __init__(self):
        self.root = {"type": "dir", "name": "root", "children": {}, "created": time.time()}
        self.current_path = ["root"]

        # Create initial directories
        self._mkdir("home")
        self._mkdir("system")
        self._mkdir("applications")

        # Add some initial files
        self._write_file("system/welcome.txt", "Welcome to SimpleOS!")
        self._write_file("system/about.txt", "SimpleOS - A Python OS Simulation")

    def _get_current_dir(self):
        """Get the current directory object"""
        current = self.root
        for dir_name in self.current_path[1:]:  # Skip 'root'
            current = current["children"][dir_name]
        return current

    def _mkdir(self, path):
        """Create a directory at the specified path"""
        if path.startswith("/"):
            path = path[1:]  # Remove leading slash

        parts = path.split("/")
        current = self.root

        for i, part in enumerate(parts):
            if part == "":
                continue

            if part not in current["children"]:
                current["children"][part] = {
                    "type": "dir",
                    "name": part,
                    "children": {},
                    "created": time.time()
                }

            current = current["children"][part]

    def _write_file(self, path, content):
        """Write content to a file at the specified path"""
        if path.startswith("/"):
            path = path[1:]

        parts = path.split("/")
        filename = parts[-1]
        directory = "/".join(parts[:-1])

        # Ensure directory exists
        if directory:
            self._mkdir(directory)

        # Navigate to the directory
        current = self.root
        for part in directory.split("/"):
            if part == "":
                continue
            current = current["children"][part]

        # Create or update the file
        current["children"][filename] = {
            "type": "file",
            "name": filename,
            "content": content,
            "size": len(content),
            "created": time.time(),
            "modified": time.time()
        }

    def list_dir(self, path=None):
        """List contents of a directory"""
        if path is None:
            # Use current directory
            current = self._get_current_dir()
        else:
            # Navigate to specified path
            if path.startswith("/"):
                path = path[1:]

            if not path:
                current = self.root
            else:
                current = self.root
                for part in path.split("/"):
                    if part == "":
                        continue
                    if part not in current["children"]:
                        return []
                    current = current["children"][part]

        if current["type"] != "dir":
            return []

        return [
            {"name": name, "type": item["type"],
             "size": item.get("size", 0) if item["type"] == "file" else 0}
            for name, item in current["children"].items()
        ]

    def read_file(self, path):
        """Read content from a file"""
        if path.startswith("/"):
            path = path[1:]

        parts = path.split("/")
        filename = parts[-1]
        directory = "/".join(parts[:-1])

        # Navigate to the directory
        current = self.root
        for part in directory.split("/"):
            if part == "":
                continue
            if part not in current["children"]:
                return None
            current = current["children"][part]

        # Read the file
        if filename not in current["children"]:
            return None

        file_obj = current["children"][filename]
        if file_obj["type"] != "file":
            return None

        return file_obj["content"]


class ProcessScheduler:
    """Implements process scheduling algorithms"""

    def __init__(self, memory_manager):
        self.processes = {}
        self.ready_queue = []
        self.running_process = None
        self.next_pid = 1000
        self.memory_manager = memory_manager
        self.time_quantum = 2  # For round-robin scheduling

    def create_process(self, name, memory_req, priority=1):
        """Create a new process and add it to the ready queue"""
        pid = self.next_pid
        self.next_pid += 1

        process = Process(pid, name, memory_req, priority)

        # Allocate memory
        memory_address = self.memory_manager.allocate(memory_req)
        if memory_address is None:
            return None  # Not enough memory

        process.memory_address = memory_address
        self.processes[pid] = process
        self.ready_queue.append(pid)

        return pid

    def terminate_process(self, pid):
        """Terminate a process and free its resources"""
        if pid not in self.processes:
            return False

        process = self.processes[pid]

        # Free memory
        if process.memory_address is not None:
            self.memory_manager.deallocate(process.memory_address)

        # Update process state
        process.state = "TERMINATED"

        # Remove from queues
        if pid in self.ready_queue:
            self.ready_queue.remove(pid)
        if self.running_process == pid:
            self.running_process = None

        return True

    def schedule_next_process(self):
        """Schedule the next process using Round Robin algorithm"""
        if self.running_process is not None:
            # Put current process back in the queue
            current = self.processes[self.running_process]
            current.state = "READY"
            self.ready_queue.append(self.running_process)
            self.running_process = None

        if not self.ready_queue:
            return None

        # Get next process from queue
        next_pid = self.ready_queue.pop(0)
        next_process = self.processes[next_pid]
        next_process.state = "RUNNING"
        self.running_process = next_pid

        return next_pid

    def get_process_info(self, pid):
        """Get information about a process"""
        if pid not in self.processes:
            return None
        return self.processes[pid]

    def get_all_processes(self):
        """Get all processes"""
        return self.processes


class SimpleOS:
    """Main OS class that integrates all components"""

    def __init__(self, root):
        self.root = root
        self.root.title("SimpleOS")
        self.root.geometry("800x600")

        # Initialize OS components
        self.memory_manager = MemoryManager(1024)  # 1GB RAM
        self.process_scheduler = ProcessScheduler(self.memory_manager)
        self.file_system = FileSystem()

        # Create system processes
        self.process_scheduler.create_process("System", 128, 10)
        self.process_scheduler.create_process("WindowManager", 64, 8)

        # Set up the UI
        self.setup_ui()

        # Start the OS scheduler
        self.scheduler_thread = threading.Thread(target=self.os_scheduler, daemon=True)
        self.scheduler_thread.start()

    def setup_ui(self):
        """Set up the main UI components"""
        # Create a notebook (tabbed interface)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Desktop tab
        self.desktop_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.desktop_frame, text="Desktop")

        # Process Manager tab
        self.process_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.process_frame, text="Process Manager")

        # File Explorer tab
        self.file_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.file_frame, text="File Explorer")

        # Memory Monitor tab
        self.memory_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.memory_frame, text="Memory Monitor")

        # Terminal tab
        self.terminal_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.terminal_frame, text="Terminal")

        # Set up each tab
        self.setup_desktop()
        self.setup_process_manager()
        self.setup_file_explorer()
        self.setup_memory_monitor()
        self.setup_terminal()

        # Status bar
        self.status_bar = ttk.Label(self.root, text="SimpleOS running...", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Clock update
        self.update_clock()

    def setup_desktop(self):
        """Set up the desktop with application icons"""
        # Desktop layout
        self.desktop_canvas = tk.Canvas(self.desktop_frame, bg="#f0f0f0")
        self.desktop_canvas.pack(fill=tk.BOTH, expand=True)

        # Application icons
        self.create_desktop_icon("Text Editor", 50, 50, self.open_text_editor)
        self.create_desktop_icon("Calculator", 150, 50, self.open_calculator)
        self.create_desktop_icon("Clock", 250, 50, self.open_clock)

        # Desktop context menu
        self.desktop_menu = tk.Menu(self.root, tearoff=0)
        self.desktop_menu.add_command(label="New Folder", command=self.create_new_folder)
        self.desktop_menu.add_command(label="Refresh", command=lambda: self.update_status("Desktop refreshed"))

        self.desktop_canvas.bind("<Button-3>", self.show_desktop_menu)

    def create_desktop_icon(self, name, x, y, command):
        """Create an icon on the desktop"""
        icon_frame = tk.Frame(self.desktop_canvas, width=60, height=80, bg="#f0f0f0")
        icon_id = self.desktop_canvas.create_window(x, y, window=icon_frame, anchor=tk.NW)

        # Icon representation (a colored rectangle)
        icon = tk.Canvas(icon_frame, width=40, height=40, bg="#f0f0f0", highlightthickness=0)
        icon.create_rectangle(5, 5, 35, 35, fill=self.get_app_color(name), outline="black")
        icon.pack(pady=(5, 0))

        # Icon label
        label = tk.Label(icon_frame, text=name, bg="#f0f0f0", wraplength=60)
        label.pack()

        # Bind click events
        icon.bind("<Button-1>", lambda e: command())
        label.bind("<Button-1>", lambda e: command())

    def get_app_color(self, app_name):
        """Return a color based on the application name"""
        colors = {
            "Text Editor": "#8cc",
            "Calculator": "#c8c",
            "Clock": "#cc8",
            "File Explorer": "#8c8",
            "Process Manager": "#c88"
        }
        return colors.get(app_name, "#ccc")

    def show_desktop_menu(self, event):
        """Show the desktop context menu"""
        self.desktop_menu.post(event.x_root, event.y_root)

    def create_new_folder(self):
        """Create a new folder on the desktop"""
        folder_name = simpledialog.askstring("New Folder", "Enter folder name:")
        if folder_name:
            self.file_system._mkdir(f"home/{folder_name}")
            self.update_status(f"Created folder: {folder_name}")
            self.refresh_file_explorer()

    def setup_process_manager(self):
        """Set up the process manager tab"""
        # Controls frame
        controls_frame = ttk.Frame(self.process_frame)
        controls_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(controls_frame, text="New Process", command=self.create_new_process).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Terminate", command=self.terminate_selected_process).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Refresh", command=self.refresh_process_list).pack(side=tk.LEFT, padx=5)

        # Process list
        columns = ("PID", "Name", "State", "Memory", "Priority", "CPU Time")
        self.process_tree = ttk.Treeview(self.process_frame, columns=columns, show="headings")

        for col in columns:
            self.process_tree.heading(col, text=col)
            width = 80 if col != "Name" else 150
            self.process_tree.column(col, width=width)

        self.process_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Initial process list
        self.refresh_process_list()

    def create_new_process(self):
        """Create a new user process"""
        name = simpledialog.askstring("New Process", "Process Name:")
        if not name:
            return

        memory = simpledialog.askinteger("Memory Requirement", "Memory (MB):", minvalue=1, maxvalue=512)
        if not memory:
            return

        priority = simpledialog.askinteger("Priority", "Priority (1-10):", minvalue=1, maxvalue=10)
        if not priority:
            priority = 5

        pid = self.process_scheduler.create_process(name, memory, priority)
        if pid:
            self.update_status(f"Created process: {name} (PID: {pid})")
            self.refresh_process_list()
        else:
            messagebox.showerror("Error", "Not enough memory to create process")

    def terminate_selected_process(self):
        """Terminate the selected process"""
        selected = self.process_tree.selection()
        if not selected:
            return

        pid = int(self.process_tree.item(selected[0])["values"][0])
        process = self.process_scheduler.get_process_info(pid)

        if process and process.name not in ["System", "WindowManager"]:
            if self.process_scheduler.terminate_process(pid):
                self.update_status(f"Terminated process: {process.name} (PID: {pid})")
                self.refresh_process_list()
        else:
            messagebox.showerror("Error", "Cannot terminate system processes")

    def refresh_process_list(self):
        """Refresh the process list display"""
        # Clear current items
        for item in self.process_tree.get_children():
            self.process_tree.delete(item)

        # Add all processes
        for pid, process in self.process_scheduler.get_all_processes().items():
            if process.state != "TERMINATED":
                self.process_tree.insert("", tk.END, values=(
                    pid,
                    process.name,
                    process.state,
                    f"{process.memory_req} MB",
                    process.priority,
                    f"{process.cpu_time:.1f}s"
                ))

    def setup_file_explorer(self):
        """Set up the file explorer tab"""
        # Path and controls frame
        path_frame = ttk.Frame(self.file_frame)
        path_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(path_frame, text="Path:").pack(side=tk.LEFT, padx=5)
        self.path_var = tk.StringVar(value="/root")
        ttk.Entry(path_frame, textvariable=self.path_var, width=50).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(path_frame, text="Go", command=self.navigate_to_path).pack(side=tk.LEFT, padx=5)

        # File operations frame
        ops_frame = ttk.Frame(self.file_frame)
        ops_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(ops_frame, text="New File", command=self.create_new_file).pack(side=tk.LEFT, padx=5)
        ttk.Button(ops_frame, text="New Folder", command=self.create_new_folder_in_explorer).pack(side=tk.LEFT, padx=5)
        ttk.Button(ops_frame, text="Delete", command=self.delete_selected_file).pack(side=tk.LEFT, padx=5)
        ttk.Button(ops_frame, text="Open", command=self.open_selected_file).pack(side=tk.LEFT, padx=5)

        # File list
        columns = ("Name", "Type", "Size")
        self.file_tree = ttk.Treeview(self.file_frame, columns=columns, show="headings")

        for col in columns:
            self.file_tree.heading(col, text=col)
            width = 100 if col == "Size" else 250
            self.file_tree.column(col, width=width)

        self.file_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.file_tree.bind("<Double-1>", self.on_file_double_click)

        # Initial file list
        self.refresh_file_explorer()

    def navigate_to_path(self):
        """Navigate to the specified path"""
        path = self.path_var.get()
        if not path.startswith("/"):
            path = "/" + path
        self.path_var.set(path)
        self.refresh_file_explorer()

    def refresh_file_explorer(self):
        """Refresh the file explorer display"""
        # Clear current items
        for item in self.file_tree.get_children():
            self.file_tree.delete(item)

        # Get path without leading slash for the file system
        path = self.path_var.get()
        if path.startswith("/"):
            path = path[1:]

        # List directory contents
        contents = self.file_system.list_dir(path)

        # Add all files and directories
        for item in contents:
            item_type = "Directory" if item["type"] == "dir" else "File"
            size = f"{item['size']} bytes" if item["type"] == "file" else ""

            self.file_tree.insert("", tk.END, values=(
                item["name"],
                item_type,
                size
            ))

    def on_file_double_click(self, event):
        """Handle double-click on file or directory"""
        selected = self.file_tree.selection()
        if not selected:
            return

        item_name = self.file_tree.item(selected[0])["values"][0]
        item_type = self.file_tree.item(selected[0])["values"][1]

        current_path = self.path_var.get()
        if not current_path.endswith("/"):
            current_path += "/"

        if item_type == "Directory":
            # Navigate to directory
            new_path = current_path + item_name
            self.path_var.set(new_path)
            self.refresh_file_explorer()
        else:
            # Open file
            file_path = current_path[1:] + item_name if current_path.startswith("/") else current_path + item_name
            content = self.file_system.read_file(file_path)
            if content is not None:
                self.open_text_editor(file_path, content)

    def create_new_file(self):
        """Create a new file in the current directory"""
        file_name = simpledialog.askstring("New File", "File Name:")
        if not file_name:
            return

        current_path = self.path_var.get()
        if not current_path.startswith("/"):
            current_path = "/" + current_path
        if not current_path.endswith("/"):
            current_path += "/"

        file_path = current_path[1:] + file_name
        self.file_system._write_file(file_path, "")
        self.update_status(f"Created file: {file_name}")
        self.refresh_file_explorer()

        # Open the new file
        self.open_text_editor(file_path, "")

    def create_new_folder_in_explorer(self):
        """Create a new folder in the current directory"""
        folder_name = simpledialog.askstring("New Folder", "Folder Name:")
        if not folder_name:
            return

        current_path = self.path_var.get()
        if not current_path.startswith("/"):
            current_path = "/" + current_path
        if not current_path.endswith("/"):
            current_path += "/"

        folder_path = current_path[1:] + folder_name
        self.file_system._mkdir(folder_path)
        self.update_status(f"Created folder: {folder_name}")
        self.refresh_file_explorer()

    def delete_selected_file(self):
        """Delete the selected file or directory"""
        # Note: This is a simplified implementation that doesn't actually delete
        # files since our file system doesn't support deletion yet
        selected = self.file_tree.selection()
        if not selected:
            return

        item_name = self.file_tree.item(selected[0])["values"][0]
        messagebox.showinfo("Not Implemented", f"Deletion of '{item_name}' is not implemented in this demo")

    def open_selected_file(self):
        """Open the selected file"""
        selected = self.file_tree.selection()
        if not selected:
            return

        item_name = self.file_tree.item(selected[0])["values"][0]
        item_type = self.file_tree.item(selected[0])["values"][1]

        if item_type != "File":
            return

        current_path = self.path_var.get()
        if not current_path.startswith("/"):
            current_path = "/" + current_path
        if not current_path.endswith("/"):
            current_path += "/"

        file_path = current_path[1:] + item_name
        content = self.file_system.read_file(file_path)

        if content is not None:
            self.open_text_editor(file_path, content)

    def setup_memory_monitor(self):
        """Set up the memory monitor tab"""
        # Memory usage frame
        usage_frame = ttk.LabelFrame(self.memory_frame, text="Memory Usage")
        usage_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Memory usage bar
        self.memory_usage_var = tk.DoubleVar(value=0)
        ttk.Label(usage_frame, text="Used Memory:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.memory_usage_bar = ttk.Progressbar(usage_frame, variable=self.memory_usage_var, maximum=100)
        self.memory_usage_bar.grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        self.memory_usage_label = ttk.Label(usage_frame, text="0 MB / 1024 MB")
        self.memory_usage_label.grid(row=0, column=2, padx=5, pady=5)

        # Memory allocation table
        ttk.Label(usage_frame, text="Memory Allocation Table:").grid(row=1, column=0, columnspan=3, padx=5, pady=5,
                                                                     sticky=tk.W)

        columns = ("Address", "Size", "Status", "Process")
        self.memory_tree = ttk.Treeview(usage_frame, columns=columns, show="headings", height=10)

        for col in columns:
            self.memory_tree.heading(col, text=col)
            width = 100
            self.memory_tree.column(col, width=width)

        self.memory_tree.grid(row=2, column=0, columnspan=3, padx=5, pady=5, sticky=tk.NSEW)

        # Configure grid
        usage_frame.columnconfigure(1, weight=1)
        usage_frame.rowconfigure(2, weight=1)

        # Memory stats frame
        stats_frame = ttk.LabelFrame(self.memory_frame, text="Memory Statistics")
        stats_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(stats_frame, text="Total Memory:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Label(stats_frame, text="1024 MB").grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)

        ttk.Label(stats_frame, text="Free Memory:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.free_memory_label = ttk.Label(stats_frame, text="1024 MB")
        self.free_memory_label.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)

        ttk.Label(stats_frame, text="Fragmentation:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        self.fragmentation_label = ttk.Label(stats_frame, text="0%")
        self.fragmentation_label.grid(row=2, column=1, padx=5, pady=5, sticky=tk.W)

        # Refresh button
        ttk.Button(self.memory_frame, text="Refresh", command=self.refresh_memory_monitor).pack(pady=10)

        # Initial memory monitor
        self.refresh_memory_monitor()

    def refresh_memory_monitor(self):
        """Refresh the memory monitor display"""
        # Update memory usage
        used_memory = self.memory_manager.total_memory - self.memory_manager.available_memory
        usage_percent = (used_memory / self.memory_manager.total_memory) * 100

        self.memory_usage_var.set(usage_percent)
        self.memory_usage_label.config(text=f"{used_memory} MB / {self.memory_manager.total_memory} MB")
        self.free_memory_label.config(text=f"{self.memory_manager.available_memory} MB")

        # Calculate fragmentation (simplified)
        free_blocks = sum(1 for _, _, is_free in self.memory_manager.memory_blocks if is_free)
        fragmentation = (free_blocks - 1) / max(len(self.memory_manager.memory_blocks),
                                                1) * 100 if free_blocks > 1 else 0
        self.fragmentation_label.config(text=f1) *100 if free_blocks > 1 else 0
        self.fragmentation_label.config(text=f"{fragmentation:.1f}%")

        # Clear current items in memory table
        for item in self.memory_tree.get_children():
            self.memory_tree.delete(item)

        # Add all memory blocks
        process_map = {}
        for pid, process in self.process_scheduler.get_all_processes().items():
            if process.memory_address is not None:
                process_map[process.memory_address] = process.name

        for start, size, is_free in self.memory_manager.memory_blocks:
            status = "Free" if is_free else "Allocated"
            process_name = process_map.get(start, "-") if not is_free else "-"

            self.memory_tree.insert("", tk.END, values=(
                f"0x{start:08x}",
                f"{size} MB",
                status,
                process_name
            ))

    def setup_terminal(self):
        """Set up the terminal tab"""
        # Terminal output
        terminal_frame = ttk.Frame(self.terminal_frame)
        terminal_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.terminal_output = tk.Text(terminal_frame, bg="black", fg="green", font=("Courier", 10))
        self.terminal_output.pack(fill=tk.BOTH, expand=True, side=tk.TOP)
        self.terminal_output.insert(tk.END, "SimpleOS Terminal v1.0\n")
        self.terminal_output.insert(tk.END, "Type 'help' for a list of commands\n\n")
        self.terminal_output.insert(tk.END, "$ ")

        # Terminal input
        input_frame = ttk.Frame(terminal_frame)
        input_frame.pack(fill=tk.X, side=tk.BOTTOM)

        ttk.Label(input_frame, text="$").pack(side=tk.LEFT, padx=5)
        self.terminal_input = ttk.Entry(input_frame)
        self.terminal_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.terminal_input.bind("<Return>", self.process_terminal_command)

    def process_terminal_command(self, event):
        """Process a terminal command"""
        command = self.terminal_input.get()
        self.terminal_input.delete(0, tk.END)

        # Add command to output
        self.terminal_output.insert(tk.END, f"{command}\n")

        # Process command
        if command == "help":
            self.terminal_output.insert(tk.END, "Available commands:\n")
            self.terminal_output.insert(tk.END, "  help - Show this help\n")
            self.terminal_output.insert(tk.END, "  ls [path] - List directory contents\n")
            self.terminal_output.insert(tk.END, "  cat <file> - Display file contents\n")
            self.terminal_output.insert(tk.END, "  ps - List processes\n")
            self.terminal_output.insert(tk.END, "  kill <pid> - Terminate a process\n")
            self.terminal_output.insert(tk.END, "  mem - Show memory usage\n")
            self.terminal_output.insert(tk.END, "  clear - Clear terminal\n")
        elif command.startswith("ls"):
            parts = command.split()
            path = parts[1] if len(parts) > 1 else None

            contents = self.file_system.list_dir(path)
            for item in contents:
                item_type = "d" if item["type"] == "dir" else "-"
                size = f"{item['size']} bytes" if item["type"] == "file" else ""
                self.terminal_output.insert(tk.END, f"{item_type} {item['name']:20} {size}\n")
        elif command.startswith("cat"):
            parts = command.split()
            if len(parts) < 2:
                self.terminal_output.insert(tk.END, "Usage: cat <file>\n")
            else:
                file_path = parts[1]
                content = self.file_system.read_file(file_path)
                if content is not None:
                    self.terminal_output.insert(tk.END, f"{content}\n")
                else:
                    self.terminal_output.insert(tk.END, f"File not found: {file_path}\n")
        elif command == "ps":
            self.terminal_output.insert(tk.END, f"{'PID':6} {'NAME':15} {'STATE':10} {'MEM':8} {'PRI':5}\n")
            for pid, process in self.process_scheduler.get_all_processes().items():
                if process.state != "TERMINATED":
                    self.terminal_output.insert(tk.END,
                                                f"{pid:6} {process.name:15} {process.state:10} {process.memory_req:4} MB {process.priority:5}\n")
        elif command.startswith("kill"):
            parts = command.split()
            if len(parts) < 2:
                self.terminal_output.insert(tk.END, "Usage: kill <pid>\n")
            else:
                try:
                    pid = int(parts[1])
                    process = self.process_scheduler.get_process_info(pid)
                    if process and process.name not in ["System", "WindowManager"]:
                        if self.process_scheduler.terminate_process(pid):
                            self.terminal_output.insert(tk.END, f"Process {pid} terminated\n")
                            self.refresh_process_list()
                        else:
                            self.terminal_output.insert(tk.END, f"Failed to terminate process {pid}\n")
                    else:
                        self.terminal_output.insert(tk.END, "Cannot terminate system processes\n")
                except ValueError:
                    self.terminal_output.insert(tk.END, "Invalid PID\n")
        elif command == "mem":
            used_memory = self.memory_manager.total_memory - self.memory_manager.available_memory
            self.terminal_output.insert(tk.END,
                                        f"Memory Usage: {used_memory} MB / {self.memory_manager.total_memory} MB\n")
            self.terminal_output.insert(tk.END, f"Free Memory: {self.memory_manager.available_memory} MB\n")

            self.terminal_output.insert(tk.END, "Memory Blocks:\n")
            for start, size, is_free in self.memory_manager.memory_blocks:
                status = "Free" if is_free else "Allocated"
                self.terminal_output.insert(tk.END, f"  0x{start:08x} - {size} MB - {status}\n")
        elif command == "clear":
            self.terminal_output.delete(1.0, tk.END)
        else:
            self.terminal_output.insert(tk.END, f"Command not found: {command}\n")

        # Add new prompt
        self.terminal_output.insert(tk.END, "$ ")
        self.terminal_output.see(tk.END)

    def open_text_editor(self, file_path=None, content=None):
        """Open the text editor application"""
        # Create a new process for the text editor
        pid = self.process_scheduler.create_process("TextEditor", 32, 5)

        if pid:
            # Create a new window for the text editor
            editor_window = tk.Toplevel(self.root)
            editor_window.title(f"Text Editor - {file_path if file_path else 'Untitled'}")
            editor_window.geometry("600x400")

            # Text area
            text_area = tk.Text(editor_window)
            text_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

            # Insert content if provided
            if content:
                text_area.insert(tk.END, content)

            # Menu bar
            menu_bar = tk.Menu(editor_window)

            # File menu
            file_menu = tk.Menu(menu_bar, tearoff=0)
            file_menu.add_command(label="Save", command=lambda: self.save_file(file_path, text_area.get(1.0, tk.END)))
            file_menu.add_command(label="Save As", command=lambda: self.save_file_as(text_area.get(1.0, tk.END)))
            file_menu.add_separator()
            file_menu.add_command(label="Close", command=lambda: self.close_application(editor_window, pid))

            menu_bar.add_cascade(label="File", menu=file_menu)
            editor_window.config(menu=menu_bar)

            # Handle window close
            editor_window.protocol("WM_DELETE_WINDOW", lambda: self.close_application(editor_window, pid))

    def save_file(self, file_path, content):
        """Save file content"""
        if not file_path:
            self.save_file_as(content)
            return

        self.file_system._write_file(file_path, content)
        self.update_status(f"Saved file: {file_path}")
        self.refresh_file_explorer()

    def save_file_as(self, content):
        """Save file with a new name"""
        file_name = simpledialog.askstring("Save As", "File Name:")
        if not file_name:
            return

        current_path = self.path_var.get()
        if not current_path.startswith("/"):
            current_path = "/" + current_path
        if not current_path.endswith("/"):
            current_path += "/"

        file_path = current_path[1:] + file_name
        self.file_system._write_file(file_path, content)
        self.update_status(f"Saved file as: {file_path}")
        self.refresh_file_explorer()

    def open_calculator(self):
        """Open the calculator application"""
        # Create a new process for the calculator
        pid = self.process_scheduler.create_process("Calculator", 16, 3)

        if pid:
            # Create a new window for the calculator
            calc_window = tk.Toplevel(self.root)
            calc_window.title("Calculator")
            calc_window.geometry("300x400")

            # Display
            display_var = tk.StringVar(value="0")
            display = ttk.Entry(calc_window, textvariable=display_var, font=("Arial", 20), justify=tk.RIGHT)
            display.pack(fill=tk.X, padx=10, pady=10)

            # Buttons frame
            buttons_frame = ttk.Frame(calc_window)
            buttons_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Calculator state
            calc_state = {"operand1": None, "operator": None, "reset_display": False}

            # Button click handler
            def button_click(value):
                current = display_var.get()

                if value in "0123456789.":
                    if current == "0" or calc_state["reset_display"]:
                        display_var.set(value)
                        calc_state["reset_display"] = False
                    else:
                        display_var.set(current + value)
                elif value in "+-*/":
                    calc_state["operand1"] = float(current)
                    calc_state["operator"] = value
                    calc_state["reset_display"] = True
                elif value == "=":
                    if calc_state["operand1"] is not None and calc_state["operator"] is not None:
                        operand2 = float(current)
                        result = 0

                        if calc_state["operator"] == "+":
                            result = calc_state["operand1"] + operand2
                        elif calc_state["operator"] == "-":
                            result = calc_state["operand1"] - operand2
                        elif calc_state["operator"] == "*":
                            result = calc_state["operand1"] * operand2
                        elif calc_state["operator"] == "/":
                            if operand2 != 0:
                                result = calc_state["operand1"] / operand2
                            else:
                                result = "Error"

                        display_var.set(str(result))
                        calc_state["operand1"] = None
                        calc_state["operator"] = None
                        calc_state["reset_display"] = True
                elif value == "C":
                    display_var.set("0")
                    calc_state["operand1"] = None
                    calc_state["operator"] = None
                    calc_state["reset_display"] = False

            # Create calculator buttons
            buttons = [
                "7", "8", "9", "/",
                "4", "5", "6", "*",
                "1", "2", "3", "-",
                "0", ".", "=", "+"
            ]

            row, col = 0, 0
            for button in buttons:
                ttk.Button(buttons_frame, text=button, width=5,
                           command=lambda b=button: button_click(b)).grid(row=row, column=col, padx=5, pady=5)
                col += 1
                if col > 3:
                    col = 0
                    row += 1

            # Clear button
            ttk.Button(buttons_frame, text="C", width=5,
                       command=lambda: button_click("C")).grid(row=row, column=0, columnspan=4, padx=5, pady=5,
                                                               sticky=tk.EW)

            # Handle window close
            calc_window.protocol("WM_DELETE_WINDOW", lambda: self.close_application(calc_window, pid))

    def open_clock(self):
        """Open the clock application"""
        # Create a new process for the clock
        pid = self.process_scheduler.create_process("Clock", 8, 2)

        if pid:
            # Create a new window for the clock
            clock_window = tk.Toplevel(self.root)
            clock_window.title("Clock")
            clock_window.geometry("300x200")

            # Clock display
            time_var = tk.StringVar()
            date_var = tk.StringVar()

            time_label = ttk.Label(clock_window, textvariable=time_var, font=("Arial", 36))
            time_label.pack(pady=(20, 5))

            date_label = ttk.Label(clock_window, textvariable=date_var, font=("Arial", 14))
            date_label.pack(pady=5)

            # Update clock function
            def update_clock_display():
                if clock_window.winfo_exists():
                    now = datetime.now()
                    time_var.set(now.strftime("%H:%M:%S"))
                    date_var.set(now.strftime("%A, %B %d, %Y"))
                    clock_window.after(1000, update_clock_display)

            # Start clock update
            update_clock_display()

            # Handle window close
            clock_window.protocol("WM_DELETE_WINDOW", lambda: self.close_application(clock_window, pid))

    def close_application(self, window, pid):
        """Close an application window and terminate its process"""
        window.destroy()
        self.process_scheduler.terminate_process(pid)
        self.refresh_process_list()

    def update_status(self, message):
        """Update the status bar message"""
        self.status_bar.config(text=message)

    def update_clock(self):
        """Update the clock in the status bar"""
        now = datetime.now()
        time_str = now.strftime("%H:%M:%S")
        self.status_bar.config(text=f"SimpleOS running... {time_str}")
        self.root.after(1000, self.update_clock)

    def os_scheduler(self):
        """OS scheduler thread that simulates process scheduling"""
        while True:
            # Schedule next process
            pid = self.process_scheduler.schedule_next_process()

            if pid is not None:
                # Simulate CPU time for the process
                process = self.process_scheduler.get_process_info(pid)
                if process:
                    # Simulate CPU usage
                    process.cpu_time += self.process_scheduler.time_quantum

                    # Sleep to simulate time quantum
                    time.sleep(0.1)  # Reduced for responsiveness
            else:
                # No process to run, just wait
                time.sleep(0.1)


# Run the OS
if __name__ == "__main__":
    root = tk.Tk()
    os_instance = SimpleOS(root)
    root.mainloop()