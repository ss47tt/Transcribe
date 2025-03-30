import os
import sys
import shutil
import whisper
import threading
import torch
from concurrent.futures import ThreadPoolExecutor
from pydub import AudioSegment
from pydub.effects import normalize
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk  # For Combobox

# Get the path of the current directory where the executable is running
if getattr(sys, 'frozen', False):
    application_path = sys._MEIPASS  # PyInstaller bundled path
else:
    application_path = os.path.dirname(os.path.abspath(__file__))

whisper_assets_path = os.path.join(application_path, 'whisper', 'assets')

# Determine device
device = "cuda" if torch.cuda.is_available() else "cpu"

def amplify_audio(audio, amplification_factor):
    """Amplify the audio by a given factor."""
    return audio.apply_gain(amplification_factor)

def stereo_to_mono(audio):
    """Convert stereo audio to mono.""" 
    return audio.set_channels(1)

def process_audio(input_path, output_path, target_max_amplitude):
    """Normalize, amplify, and convert WAV audio to mono.""" 
    try:
        audio = AudioSegment.from_wav(input_path)
        audio = stereo_to_mono(audio)
        audio = normalize(audio)
        amplification_factor = target_max_amplitude - audio.max_dBFS
        if amplification_factor > 0:
            audio = amplify_audio(audio, amplification_factor)
        
        os.makedirs(output_path, exist_ok=True)
        output_file = os.path.join(output_path, os.path.basename(input_path))
        audio.export(output_file, format="wav")
        print(f"Processed and saved: {output_file}")
    except Exception as e:
        print(f"Error processing {input_path}: {e}")

def add_silence(audio_path, output_path, silence_duration):
    """Add silence at the beginning and end of an audio file.""" 
    try:
        audio = AudioSegment.from_wav(audio_path)
        silence = AudioSegment.silent(duration=silence_duration * 1000)
        padded_audio = silence + audio + silence
        padded_audio.export(output_path, format="wav")
    except Exception as e:
        print(f"Error adding silence to {audio_path}: {e}")

def transcribe_audio(input_path, output_path, model, silence_duration, language):
    """Transcribe all WAV files using Whisper with silence compensation.""" 
    try:
        os.makedirs(output_path, exist_ok=True)
        for filename in os.listdir(input_path):
            if filename.endswith(".wav"):
                padded_file_path = os.path.join(input_path, filename)
                result = model.transcribe(padded_file_path, language=language)
                output_file_path = os.path.join(output_path, f"{os.path.splitext(filename)[0]}.txt")
                with open(output_file_path, "w", encoding="utf-8") as f:
                    for segment in result["segments"]:
                        start_time = max(segment["start"] - silence_duration, 0)
                        end_time = max(segment["end"] - silence_duration, 0)
                        f.write(f"[{start_time:.2f} - {end_time:.2f}] {segment['text']}\n")
                print(f"Transcription complete for {filename}")
        print("All transcriptions are finished.")
    except Exception as e:
        print(f"Error during transcription: {e}")

def process_files(model_name, language):
    """Handles the complete process: Copy → Process Audio → Add Silence → Transcribe""" 
    files = filedialog.askopenfilenames(filetypes=[("WAV files", "*.wav")])
    if not files:
        messagebox.showwarning("No files", "No files selected.")
        return
    for file in files:
        shutil.copy(file, wav_directory)
    audio_files = [f for f in os.listdir(wav_directory) if f.endswith(".wav")]
    audio_paths = [os.path.join(wav_directory, f) for f in audio_files]
    with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        futures = {executor.submit(process_audio, file, amplified_directory, target_max_amplitude): file for file in audio_paths}
        for future in futures:
            try:
                future.result()
            except Exception as e:
                print(f"Error processing {futures[future]}: {e}")
    amplified_files = [f for f in os.listdir(amplified_directory) if f.endswith(".wav")]
    amplified_paths = [os.path.join(amplified_directory, f) for f in amplified_files]
    with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        futures = {executor.submit(add_silence, file, os.path.join(temp_padded_directory, os.path.basename(file)), silence_duration): file for file in amplified_paths}
        for future in futures:
            try:
                future.result()
            except Exception as e:
                print(f"Error adding silence to {futures[future]}: {e}")
    try:
        whisper_model = whisper.load_model(model_name, device=device)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to load Whisper model: {e}")
        return
    transcribe_audio(temp_padded_directory, transcription_directory, whisper_model, silence_duration, language)
    messagebox.showinfo("Success", "Processing, adding silence, and transcription completed for selected files.")

# Create Directories
wav_directory = 'wav'
amplified_directory = 'amplified_wav'
transcription_directory = 'transcription_with_timestamps'
temp_padded_directory = 'temp_padded'
os.makedirs(wav_directory, exist_ok=True)
os.makedirs(amplified_directory, exist_ok=True)
os.makedirs(temp_padded_directory, exist_ok=True)
os.makedirs(transcription_directory, exist_ok=True)

target_max_amplitude = -3.0
silence_duration = 30

# Set up Tkinter GUI
root = tk.Tk()
root.title("Audio Processor")

# Language selection (only combobox, no text box)
language_label = tk.Label(root, text="Select Language:", font=("Helvetica", 16))
language_label.pack(pady=5)

# Combobox for predefined language options
languages = ["en", "zh"]
language_var = tk.StringVar()
language_combobox = ttk.Combobox(root, textvariable=language_var, values=languages, state="normal", font=("Helvetica", 14))
language_combobox.set("en")  # Set default value
language_combobox.pack(pady=5)

# Model selection dropdown
model_label = tk.Label(root, text="Select Model Size:", font=("Helvetica", 16))
model_label.pack(pady=5)
model_var = tk.StringVar(value="medium")
model_menu = tk.OptionMenu(root, model_var, "small", "medium", "large")
model_menu.pack(pady=5)

# Process button
process_button = tk.Button(root, text="Select WAV Files to Process", 
                           command=lambda: threading.Thread(target=process_files, 
                                                            args=(model_var.get(), language_var.get())).start(),
                           font=("Helvetica", 20))

process_button.pack(pady=20)

root.mainloop()