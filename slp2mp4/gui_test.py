import tkinter as tk
from tkinter import filedialog
import subprocess
import os
import json

#some notes: slippi folder is the folder containing slippi replays



def browse_melee_iso():
    melee_iso_path = filedialog.askopenfilename(title="Select Melee ISO file", filetypes=[("ISO files", "*.iso")])
    entry_melee_iso.delete(0, tk.END)
    entry_melee_iso.insert(0, melee_iso_path)

def browse_dolphin_directory():
    dolphin_directory = filedialog.askdirectory(title="Select Dolphin Directory")
    entry_dolphin_directory.delete(0, tk.END)
    entry_dolphin_directory.insert(0, dolphin_directory)

def browse_slippi_folder():
    slippi_folder = filedialog.askdirectory(title="Select Slippi Files Folder")
    entry_slippi_folder.delete(0, tk.END)
    entry_slippi_folder.insert(0, slippi_folder)

def update_encoder_option(*args):
    selected_encoder.set(encoder_option.get())

def update_resolution_option(*args):
    selected_resolution.set(resolution_option.get())

def update_widescreen_option(*args):
    selected_widescreen.set(widescreen_option.get())

def update_combine_option(*args):
    selected_combine.set(combine_option.get())

def update_remove_slps_option(*args):
    selected_remove_slps.set(remove_slps_option.get())

def update_remove_short_slps_option(*args):
    selected_remove_short_slps.set(remove_short_slps_option.get())

def browse_video_output():
    # Opens a directory selection window
    video_output_path = filedialog.askdirectory(title="Select Video Output Folder")

    # Update the video output variable with the selected path
    video_output_var.set(video_output_path)

# Create the main window
root = tk.Tk()
root.title("SLP2MP4 - Iowa Melee")

# Variables to store user entries
melee_iso_var = tk.StringVar()
dolphin_directory_var = tk.StringVar()
slippi_folder_var = tk.StringVar()
selected_encoder = tk.StringVar()
selected_resolution = tk.StringVar(value="1080p")  # Default value is set to 1080p
selected_widescreen = tk.StringVar(value="False")  # Default value is set to False
selected_combine = tk.StringVar()
selected_remove_slps = tk.StringVar(value="False")  # Default value is set to False
selected_remove_short_slps = tk.StringVar(value="False")  # Default value is set to False
bitrate_var = tk.StringVar(value="20000")  # Default value is set to 20000

#script and data folder path variables
script_directory = os.path.dirname(os.path.realpath(__file__))
data_folder = os.path.join(script_directory, "data")

config_data = {
    "melee_iso": melee_iso_var.get(),
    "dolphin_dir": dolphin_directory_var.get(),
    "resolution": selected_resolution.get(),
    "video_backend": selected_encoder.get(),
    "widescreen": selected_widescreen.get(),
    "bitrateKbps": bitrate_var.get(),
    "parallel_games": "recommended",
    "remove_short": selected_remove_short_slps.get(),
    "combine": selected_combine.get(),
    "remove_slps": selected_remove_slps.get(),
    "ffmpeg": "C:\\ffmpeg\\bin\\ffmpeg.exe"
    # Can add other configuration parameters here as needed
}



def save_config():
    config_data["melee_iso"] = melee_iso_var.get()
    config_data["dolphin_dir"] = dolphin_directory_var.get()
    config_data["resolution"] = selected_resolution.get()
    config_data["video_backend"] = selected_encoder.get()
    config_data["widescreen"] = selected_widescreen.get()
    config_data["bitrateKbps"] = bitrate_var.get()
    config_data["remove_short"] = selected_remove_short_slps.get()
    config_data["combine"] = selected_combine.get()
    config_data["remove_slps"] = selected_remove_slps.get()
    # Add other config parameters here if needed

    os.makedirs(data_folder, exist_ok=True)  # Ensure the "data" folder exists
    config_file_path = os.path.abspath(os.path.join(data_folder, "config.json"))

    with open(config_file_path, "w", encoding="utf-8") as config_file:
        json.dump(config_data, config_file, indent=4)
        config_file.truncate()

#run slp2mp4 function
def run_slp2mp4():
    try:
        script_directory = os.path.dirname(os.path.realpath(__file__))
        slp2mp4_script = os.path.abspath(os.path.join(script_directory, "slp2mp4"))
        slippi_folder_var.get() #maybe not necessary in python
        subprocess.run([slp2mp4_script, "run", video_output_var.get(), slippi_folder_var.get() ], check=True, shell=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running slp2mp4: {e}")

def render():
    save_config()  # Save the configuration before rendering
    run_slp2mp4()
    pass

# Melee ISO button
button_melee_iso = tk.Button(root, text="Melee ISO:", command=browse_melee_iso)
button_melee_iso.grid(row=0, column=0, pady=10, padx=5, sticky='w')

# Entry widget for Melee ISO path
entry_melee_iso = tk.Entry(root, textvariable=melee_iso_var, width=50)
entry_melee_iso.grid(row=0, column=1, pady=10, padx=5, sticky='w')

# Dolphin Directory button
button_dolphin_directory = tk.Button(root, text="Slippi 'Playback' Folder", command=browse_dolphin_directory)
button_dolphin_directory.grid(row=1, column=0, pady=10, padx=5, sticky='w')

# Entry widget for Dolphin Directory path
entry_dolphin_directory = tk.Entry(root, textvariable=dolphin_directory_var, width=50)
entry_dolphin_directory.grid(row=1, column=1, pady=10, padx=5, sticky='w')

# Slippi Files Folder button
button_slippi_folder = tk.Button(root, text="Slippi Files Folder", command=browse_slippi_folder)
button_slippi_folder.grid(row=2, column=0, pady=10, padx=5, sticky='w')

# Entry widget for Slippi Files Folder path
entry_slippi_folder = tk.Entry(root, textvariable=slippi_folder_var, width=50)
entry_slippi_folder.grid(row=2, column=1, pady=10, padx=5, sticky='w')

# Label for Encoder
encoder_label = tk.Label(root, text="Encoder:")
encoder_label.grid(row=4, column=0, pady=5, padx=5, sticky='w')

# Encoder dropdown
encoder_options = ["D3D", "OGL"]
encoder_option = tk.StringVar()
encoder_option.set(encoder_options[0])  # Set the default option
encoder_menu = tk.OptionMenu(root, encoder_option, *encoder_options)
encoder_menu.grid(row=4, column=1, pady=10, padx=5, sticky='w')
encoder_option.trace_add("write", update_encoder_option)

# Label for Resolution
resolution_label = tk.Label(root, text="Resolution:")
resolution_label.grid(row=5, column=0, pady=5, padx=5, sticky='w')

# Resolution dropdown
resolution_options = ["720p", "1080p", "1440p"]
resolution_option = tk.StringVar()
resolution_option.set(resolution_options[1])  # Set the default option to 1080p
resolution_menu = tk.OptionMenu(root, resolution_option, *resolution_options)
resolution_menu.grid(row=5, column=1, pady=10, padx=5, sticky='w')
resolution_option.trace_add("write", update_resolution_option)

# Label for Widescreen
widescreen_label = tk.Label(root, text="Widescreen:")
widescreen_label.grid(row=6, column=0, pady=5, padx=5, sticky='w')

# Widescreen dropdown
widescreen_options = ["True", "False"]
widescreen_option = tk.StringVar()
widescreen_option.set(widescreen_options[1])  # Set the default option to False
widescreen_menu = tk.OptionMenu(root, widescreen_option, *widescreen_options)
widescreen_menu.grid(row=6, column=1, pady=10, padx=5, sticky='w')
widescreen_option.trace_add("write", update_widescreen_option)

# Label for Combine
combine_label = tk.Label(root, text="Combine:")
combine_label.grid(row=7, column=0, pady=5, padx=5, sticky='w')

# Combine dropdown
combine_options = ["True", "False"]
combine_option = tk.StringVar()
combine_option.set(combine_options[0])  # Set the default option
combine_menu = tk.OptionMenu(root, combine_option, *combine_options)
combine_menu.grid(row=7, column=1, pady=10, padx=5, sticky='w')
combine_option.trace_add("write", update_combine_option)

# Label for Remove SLP's
remove_slps_label = tk.Label(root, text="Remove SLP's:")
remove_slps_label.grid(row=8, column=0, pady=5, padx=5, sticky='w')

# Remove SLP's dropdown
remove_slps_options = ["True", "False"]
remove_slps_option = tk.StringVar()
remove_slps_option.set(remove_slps_options[1])  # Set the default option to False
remove_slps_menu = tk.OptionMenu(root, remove_slps_option, *remove_slps_options)
remove_slps_menu.grid(row=8, column=1, pady=10, padx=5, sticky='w')
remove_slps_option.trace_add("write", update_remove_slps_option)

# Label for Remove Short SLP's
remove_short_slps_label = tk.Label(root, text="Remove Short SLP's:")
remove_short_slps_label.grid(row=9, column=0, pady=5, padx=5, sticky='w')

# Remove Short SLP's dropdown
remove_short_slps_options = ["True", "False"]
remove_short_slps_option = tk.StringVar()
remove_short_slps_option.set(remove_short_slps_options[1])  # Set the default option to False
remove_short_slps_menu = tk.OptionMenu(root, remove_short_slps_option, *remove_short_slps_options)
remove_short_slps_menu.grid(row=9, column=1, pady=10, padx=5, sticky='w')
remove_short_slps_option.trace_add("write", update_remove_short_slps_option)

# Label for Bitrate
bitrate_label = tk.Label(root, text="Bitrate (Default: 20000 Kbps):")
bitrate_label.grid(row=10, column=0, pady=5, padx=5, sticky='w')

# Entry widget for Bitrate
entry_bitrate = tk.Entry(root, textvariable=bitrate_var, width=10)
entry_bitrate.grid(row=10, column=1, pady=10, padx=5, sticky='w')

# Entry widget for Video Output path
video_output_var = tk.StringVar()
entry_video_output =  tk.Entry(root, textvariable=video_output_var, width=50)
entry_video_output.grid(row=3, column=1, pady=10, padx=5, sticky='w')

# Video Output button
button_video_output = tk.Button(root, text="Video Output:", command=browse_video_output)
button_video_output.grid(row=3, column=0, pady=10, padx=5, sticky='w')

# Render button
render_button = tk.Button(root, text="Render", command=render, width=20, height=2)
render_button.grid(row=10, column=2, columnspan=2, pady=20)

# Load the image
os.makedirs(data_folder, exist_ok=True)  # Ensure the "data" folder exists
Diggles_file_path = os.path.abspath(os.path.join(data_folder, "Diggles.pgm"))
img = tk.PhotoImage(file=Diggles_file_path)

# Scale down the image to fit in any sized window
img = img.subsample(2)  # Change the subsample factor as needed 2 is what looked good to me

# Display the image using a label

image_label = tk.Label(root, image=img)
image_label.grid(row=0, column=2, rowspan=10, pady=10, padx=10, sticky='w')

# Run the main loop
root.mainloop()

# Access the selected options using these variables
melee_iso_path = melee_iso_var.get()
dolphin_directory = dolphin_directory_var.get()
slippi_folder = slippi_folder_var.get()
selected_encoder_option = selected_encoder.get()
selected_resolution_option = selected_resolution.get()
selected_widescreen_option = selected_widescreen.get()
selected_combine_option = selected_combine.get()
selected_remove_slps_option = selected_remove_slps.get()
selected_remove_short_slps_option = selected_remove_short_slps.get()
selected_bitrate_option = bitrate_var.get()


# Render button
render_button = tk.Button(root, text="Render", command=render, width=20, height=2)
render_button.grid(row=10, column=0, columnspan=2, pady=20, sticky='w')

# Load the image
os.makedirs(data_folder, exist_ok=True)  # Ensure the "data" folder exists
Diggles_file_path = os.path.abspath(os.path.join(data_folder, "Diggles.pgm"))
img = tk.PhotoImage(file=Diggles_file_path)

# Scale down the image to fit in any sized window
img = img.subsample(2)  # Change the subsample factor as needed; 2 is what looked good to me

# Display the image using a label
image_label = tk.Label(root, image=img)
image_label.grid(row=11, column=0, columnspan=2, pady=10, padx=10, sticky='w')
