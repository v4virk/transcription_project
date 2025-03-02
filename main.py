import os
import whisper
import tkinter as tk
from tkinter import filedialog, ttk
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading
import json


# Media formats
SUPPORTED_FORMATS = (".mp3", ".wav", ".mp4", ".mkv", ".mov", ".flv", ".aac", ".m4a")

# File to track processed files
PROCESSED_FILES_LOG = "processed_files.json"
SESSION_FILE = "session.json"

# Thread lock for thread-safe file operations
file_lock = threading.Lock()

def load_processed_files():
    """Load the list of already processed files."""
    if os.path.exists(PROCESSED_FILES_LOG):
        with file_lock:
            with open(PROCESSED_FILES_LOG, "r") as f:
                return set(json.load(f))
    return set()

def save_processed_file(file_path):
    """Save the processed file to the log."""
    processed_files = load_processed_files()
    processed_files.add(os.path.abspath(file_path))  # Use absolute path
    with file_lock:
        with open(PROCESSED_FILES_LOG, "w") as f:
            json.dump(list(processed_files), f)

def load_session():
    """Load the session state."""
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, "r") as f:
            return json.load(f)
    return {"directory": None, "processed_files": []}

def save_session(directory, processed_files):
    """Save the session state."""
    with open(SESSION_FILE, "w") as f:
        json.dump({"directory": directory, "processed_files": list(processed_files)}, f)

def transcribe_audio(file_path, log_text, progress_label, progress_bar):
    """Transcribes audio/video files using Whisper and updates UI."""
    try:
        # Normalize file path
        file_path = os.path.abspath(file_path)

        # Skip if already processed
        if file_path in load_processed_files():
            log_text.insert(tk.END, f"Skipped (already processed): {os.path.basename(file_path)}\n")
            return

        # Update UI for processing state
        progress_label.config(text=f"Processing: {os.path.basename(file_path)}", fg="white")
        progress_bar.start(10)

        # Load Whisper model
        model = whisper.load_model("medium")

        # Transcribe the media file
        result = model.transcribe(file_path)

        # Create a "Transcriptions" subfolder in the directory of the media file
        media_directory = os.path.dirname(file_path)
        transcriptions_folder = os.path.join(media_directory, "Transcriptions")
        os.makedirs(transcriptions_folder, exist_ok=True)

        # Save transcription in the "Transcriptions" subfolder
        transcript_filename = os.path.basename(file_path).rsplit('.', 1)[0] + "_transcription.txt"
        transcript_path = os.path.join(transcriptions_folder, transcript_filename)
        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write(f"File Name: {os.path.basename(file_path)}\n")
            f.write(f"File Path: {file_path}\n\n")
            f.write("Transcription:\n")
            f.write(result["text"])

        # Mark file as processed
        save_processed_file(file_path)
        log_text.insert(tk.END, f"Transcribed: {os.path.basename(file_path)}\n")
    
    except Exception as e:
        log_text.insert(tk.END, f"Error processing {os.path.basename(file_path)}: {e}\n")

    finally:
        # Reset UI after completion
        progress_label.config(text="Ready", fg="white")
        progress_bar.stop()

class MediaFileHandler(FileSystemEventHandler):
    """Automatically transcribes new media files detected in the directory."""
    def __init__(self, log_text, progress_label, progress_bar):
        self.log_text = log_text
        self.progress_label = progress_label
        self.progress_bar = progress_bar

    def on_created(self, event):
        if not event.is_directory and event.src_path.lower().endswith(SUPPORTED_FORMATS):
            threading.Thread(target=transcribe_audio, args=(event.src_path, self.log_text, self.progress_label, self.progress_bar), daemon=True).start()

def start_observer(directory, log_text, progress_label, progress_bar):
    """Starts a watchdog observer to monitor the directory for new media files."""
    event_handler = MediaFileHandler(log_text, progress_label, progress_bar)
    observer = Observer()
    observer.schedule(event_handler, directory, recursive=True)
    observer.start()
    return observer

def select_directory():
    directory = filedialog.askdirectory()
    if directory:
        log_text.insert(tk.END, f"Scanning directory: {directory}\n")
        progress_label.config(text="Scanning files...", fg="yellow")
        
        # Load session and processed files
        session = load_session()
        processed_files = load_processed_files()

        # Scan directory for files
        files = [os.path.abspath(os.path.join(root, file)) for root, _, files in os.walk(directory) for file in files if file.lower().endswith(SUPPORTED_FORMATS)]
        
        if not files:
            log_text.insert(tk.END, "No media files found in the selected directory.\n")
            progress_label.config(text="Ready", fg="green")
        else:
            new_files_found = False
            for file in files:
                if file not in processed_files:
                    new_files_found = True
                    threading.Thread(target=transcribe_audio, args=(file, log_text, progress_label, progress_bar), daemon=True).start()
            
            # If no new files are found, display a message
            if not new_files_found:
                log_text.insert(tk.END, "No new files found to transcribe.\n")
                progress_label.config(text="Ready", fg="green")
        
        # Save session
        save_session(directory, processed_files)

        # Start observer to monitor new files
        global observer
        observer = start_observer(directory, log_text, progress_label, progress_bar)

        # Enable the Stop Monitoring button
        stop_button.config(state=tk.NORMAL)

def stop_observer():
    """Stops the observer without terminating the application."""
    observer.stop()
    observer.join()
    log_text.insert(tk.END, "Monitoring stopped.\n")
    progress_label.config(text="Monitoring Stopped", fg="red")
    stop_button.config(state=tk.DISABLED)

def terminate_application():
    """Terminates the application."""
    log_text.insert(tk.END, "Application is terminating...\n")
    root.after(2000, root.destroy)

# Create UI
root = tk.Tk()
root.title("Whisper Transcription")
root.geometry("700x600")

# Frame for the directory selection label and button
top_frame = tk.Frame(root, padx=20, pady=20)
top_frame.pack()

tk.Label(top_frame, text="Select a directory to scan for media files", font=("Arial", 12)).pack(pady=10)

# Browse button
browse_button = tk.Button(top_frame, text="Browse", command=select_directory, font=("Arial", 12), bg="lightblue")
browse_button.pack(pady=5)

# Progress label
progress_label = tk.Label(root, text="Ready", font=("Arial", 12), fg="white")
progress_label.pack(pady=5)

# Progress bar
progress_bar = ttk.Progressbar(root, mode="indeterminate", length=300)
progress_bar.pack(pady=5)

# Log text area
log_text = tk.Text(root, height=15, width=90)
log_text.pack(pady=10)

# Frame for the buttons below the log box
button_frame = tk.Frame(root, padx=20, pady=10)
button_frame.pack()

# Stop Monitoring button (initially disabled)
stop_button = tk.Button(button_frame, text="Stop Monitoring", command=stop_observer, font=("Arial", 12), bg="lightcoral", state=tk.DISABLED)
stop_button.pack(side=tk.LEFT, padx=5)

# Terminate Application button
terminate_button = tk.Button(button_frame, text="Terminate Application", command=terminate_application, font=("Arial", 12), bg="red", fg="black")
terminate_button.pack(side=tk.LEFT, padx=5)

root.mainloop()