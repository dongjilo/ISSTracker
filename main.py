import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
import requests
import json
import os
from datetime import datetime
from PIL import Image, ImageTk
from collections import Counter
import time

class ISSDataFetcher:
    """Handles API requests to fetch ISS and location data."""

    def __init__(self):
        """Initialize the data fetcher."""
        self.iss_api_url = "http://api.open-notify.org/iss-now.json"
        self.geo_api_url = "https://api.bigdatacloud.net/data/reverse-geocode-client"

    def get_iss_position(self):
        """
        Fetches the current ISS position from the API.

        Returns:
            dict: A dictionary with 'latitude', 'longitude', and 'timestamp'
                  if successful, None otherwise.
        """
        try:
            response = requests.get(self.iss_api_url, timeout=5)
            response.raise_for_status()  # Raise exception for 4xx/5xx errors
            data = response.json()

            if data.get('message') == 'success':
                latitude = float(data['iss_position']['latitude'])
                longitude = float(data['iss_position']['longitude'])
                timestamp_obj = datetime.fromtimestamp(data['timestamp'])

                return {
                    'latitude': latitude,
                    'longitude': longitude,
                    'timestamp_obj': timestamp_obj,
                    'timestamp_str': timestamp_obj.strftime('%Y-%m-%d %H:%M:%S')
                }
            else:
                print(f"API error: {data.get('reason', 'Unknown')}")
                return None
        except requests.RequestException as e:
            # Handle connection errors, timeouts, etc.
            print(f"ISS API request failed: {e}")
            return None

    def get_location_details(self, lat, lon):
        """
        Fetches nearest city/country using reverse geocoding.

        Args:
            lat (float): Latitude
            lon (float): Longitude

        Returns:
            str: A formatted location string (e.g., "City, Country", "Ocean", "N/A")
        """
        params = {
            'latitude': lat,
            'longitude': lon,
            'localityLanguage': 'en'
        }
        try:
            response = requests.get(self.geo_api_url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()

            # Format the location string
            locality = data.get('locality')
            country = data.get('countryName')

            if locality and country:
                return f"{locality}, {country}"
            elif country:
                return country
            elif data.get('localityInfo', {}).get('informative'):
                # Often describes oceans
                return data['localityInfo']['informative'][-1].get('name', 'Ocean')
            else:
                return "Over Ocean"
        except requests.RequestException as e:
            print(f"Geo API request failed: {e}")
            return "N/A"
        except json.JSONDecodeError:
            print("Failed to decode Geo API response.")
            return "N/A"

class SpaceTrackerApp:
    """Main application class for the modern ISS Space Tracker GUI."""

    def __init__(self, root):
        """
        Initialize the main application.

        Args:
            root (ctk.CTk): The root CustomTkinter window.
        """
        self.root = root
        self.root.title("Modern Real-Time ISS Tracker")
        self.root.geometry("800x720")  # Increased height for better spacing
        self.root.resizable(False, False)

        # Set default appearance
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        # --- Fonts ---
        self.font_large = ctk.CTkFont(family="Segoe UI", size=20, weight="bold")
        self.font_normal = ctk.CTkFont(family="Segoe UI", size=14)
        self.font_small_italic = ctk.CTkFont(family="Segoe UI", size=12, slant="italic")
        self.font_status = ctk.CTkFont(family="Segoe UI", size=12)
        self.font_button = ctk.CTkFont(family="Segoe UI", size=12, weight="bold")
        self.font_mono = ctk.CTkFont(family="Courier New", size=12)

        # --- Data & State ---
        self.data_fetcher = ISSDataFetcher()
        self.log_file = 'iss_tracking_log.json'

        # Canvas dimensions
        self.canvas_width = 760
        self.canvas_height = 380

        # State Variables
        self.auto_update_enabled = False
        self.auto_update_job = None
        self.last_position = None
        self.is_night_mode = False
        self.iss_trail_coords = []

        # Asset References
        self.map_image_day = None
        self.map_photo_day = None
        self.map_image_night = None
        self.map_photo_night = None
        self.iss_icon = None
        self.iss_photo = None

        # Canvas Item IDs
        self.map_image_id = None
        self.iss_item_id = None

        # StringVars for Labels
        self.lat_var = tk.StringVar(value="Latitude: --")
        self.lon_var = tk.StringVar(value="Longitude: --")
        self.time_var = tk.StringVar(value="Timestamp: --")
        self.location_var = tk.StringVar(value="Location: --")
        self.status_var = tk.StringVar(value="Status: Ready. Press 'Enable Auto-Track' to begin.")
        self.utc_time_var = tk.StringVar(value="UTC: --:--:--")

        # --- Load assets and build UI ---
        self._load_assets()
        self._create_widgets()

        # Initial actions
        self.update_location(is_manual=True)
        self._start_utc_clock()

    def _load_assets(self):
        """Load external images (maps, icons) safely."""
        try:
            img_day = Image.open("world_map.png").resize((self.canvas_width, self.canvas_height))
            self.map_photo_day = ImageTk.PhotoImage(img_day)

            img_night = Image.open("world_map_night.png").resize((self.canvas_width, self.canvas_height))
            self.map_photo_night = ImageTk.PhotoImage(img_night)
        except Exception as e:
            print(f"Map image not found or failed to load: {e}. Using fallback color.")
            if not self.map_photo_day:
                print("Critical: Default 'world_map.png' is missing.")

        try:
            img_iss = Image.open("iss_icon.png").resize((32, 32))
            self.iss_photo = ImageTk.PhotoImage(img_iss)
        except Exception as e:
            print(f"ISS icon not found: {e}. Using fallback dot.")
            self.iss_photo = None

    def _create_widgets(self):
        """Create and layout all GUI widgets using a grid system."""

        # Configure root grid
        self.root.grid_rowconfigure(2, weight=1)  # Map row expands
        self.root.grid_columnconfigure(0, weight=1)

        # --- 0. Top Navigation Bar ---
        nav_frame = ctk.CTkFrame(self.root, corner_radius=0, height=40)
        nav_frame.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        nav_frame.grid_columnconfigure(3, weight=1)  # Push theme toggle right

        ctk.CTkLabel(nav_frame, text="Real-Time ISS Tracker", font=self.font_large).grid(row=0, column=0, padx=20,
                                                                                         pady=10)

        ctk.CTkButton(nav_frame, text="Exit", command=self.root.quit, width=60, font=self.font_button).grid(row=0,
                                                                                                            column=1,
                                                                                                            padx=5,
                                                                                                            pady=10)
        ctk.CTkButton(nav_frame, text="About", command=self._show_about, width=60, font=self.font_button).grid(row=0,
                                                                                                               column=2,
                                                                                                               padx=5,
                                                                                                               pady=10)

        # View Options Menu
        self.view_menu = ctk.CTkOptionMenu(
            nav_frame,
            values=["View Options", "Toggle Day/Night", "Clear ISS Trail"],
            command=self._handle_view_menu,
            font=self.font_button,
            width=120
        )
        self.view_menu.grid(row=0, column=3, padx=10, pady=10)

        # Light/Dark Mode Toggle
        self.theme_switch = ctk.CTkSwitch(
            nav_frame,
            text="Light Mode",
            command=self._toggle_theme,
            font=self.font_normal,
            onvalue="Light",
            offvalue="Dark"
        )
        self.theme_switch.grid(row=0, column=4, padx=20, pady=10, sticky="e")

        # --- 1. Info "Card" ---
        info_frame = ctk.CTkFrame(self.root, corner_radius=10)
        info_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(10, 5))
        info_frame.grid_columnconfigure(0, weight=1)
        info_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            info_frame,
            textvariable=self.time_var,
            font=self.font_large,
        ).grid(row=0, column=0, columnspan=2, pady=(10, 5))

        ctk.CTkLabel(
            info_frame,
            textvariable=self.lat_var,
            font=self.font_normal,
        ).grid(row=1, column=0, pady=5)

        ctk.CTkLabel(
            info_frame,
            textvariable=self.lon_var,
            font=self.font_normal,
        ).grid(row=1, column=1, pady=5)

        ctk.CTkLabel(
            info_frame,
            textvariable=self.location_var,
            font=self.font_small_italic,
        ).grid(row=2, column=0, columnspan=2, pady=(5, 10))

        # --- 2. Map "Card" ---
        canvas_frame = ctk.CTkFrame(self.root, corner_radius=10)
        canvas_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)

        self.canvas = tk.Canvas(
            canvas_frame,
            width=self.canvas_width,
            height=self.canvas_height,
            bg='#2B2B2B',
            highlightthickness=0
        )
        self.canvas.pack()

        if self.map_photo_day:
            self.map_image_id = self.canvas.create_image(
                0, 0,
                anchor=tk.NW,
                image=self.map_photo_day
            )

        # Create ISS item
        if self.iss_photo:
            self.iss_item_id = self.canvas.create_image(
                self.canvas_width / 2, self.canvas_height / 2,
                image=self.iss_photo
            )
        else:
            self.iss_item_id = self.canvas.create_oval(
                self.canvas_width / 2 - 5, self.canvas_height / 2 - 5,
                self.canvas_width / 2 + 5, self.canvas_height / 2 + 5,
                fill='#e74c3c', outline='white', width=2
            )

        # --- 3. Controls "Card" ---
        button_frame = ctk.CTkFrame(self.root, corner_radius=10)
        button_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=5)
        button_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.update_button = ctk.CTkButton(
            button_frame,
            text="Manual Update",
            command=lambda: self.update_location(is_manual=True),
            font=self.font_button
        )
        self.update_button.grid(row=0, column=0, padx=5, pady=10)

        self.toggle_button = ctk.CTkButton(
            button_frame,
            text="Enable Auto-Track",
            command=self._toggle_auto_update,
            font=self.font_button,
            fg_color="#2ecc71",  # Green
            hover_color="#27ae60"  # Darker Green
        )
        self.toggle_button.grid(row=0, column=1, padx=5, pady=10)

        self.history_button = ctk.CTkButton(
            button_frame,
            text="Show History",
            command=self.show_history,
            font=self.font_button
        )
        self.history_button.grid(row=0, column=2, padx=5, pady=10)

        self.summary_button = ctk.CTkButton(
            button_frame,
            text="Show Summary",
            command=self.show_summary,
            font=self.font_button
        )
        self.summary_button.grid(row=0, column=3, padx=5, pady=10)

        # --- 4. Status Bar ---
        status_frame = ctk.CTkFrame(self.root, corner_radius=0, height=30)
        status_frame.grid(row=4, column=0, sticky="ew", padx=0, pady=0)
        status_frame.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(
            status_frame,
            textvariable=self.status_var,
            font=self.font_status,
            anchor=tk.W
        )
        self.status_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")

        self.utc_label = ctk.CTkLabel(
            status_frame,
            textvariable=self.utc_time_var,
            font=self.font_status,
            anchor=tk.E
        )
        self.utc_label.grid(row=0, column=1, padx=10, pady=5, sticky="e")

    def _start_utc_clock(self):
        """Updates the UTC clock label every second."""
        utc_now = datetime.utcnow().strftime('UTC: %H:%M:%S')
        self.utc_time_var.set(utc_now)
        self.root.after(1000, self._start_utc_clock)  # Reschedule

    def _toggle_auto_update(self):
        """Starts or stops the automatic update loop."""
        self.auto_update_enabled = not self.auto_update_enabled

        if self.auto_update_enabled:
            self.toggle_button.configure(
                text="Disable Auto-Track",
                fg_color="#e74c3c",  # Red
                hover_color="#c0392b"  # Darker Red
            )
            self.update_button.configure(state="disabled")
            self.update_location(is_manual=False)  # Start the loop
        else:
            self.toggle_button.configure(
                text="Enable Auto-Track",
                fg_color="#2ecc71",  # Green
                hover_color="#27ae60"  # Darker Green
            )
            self.update_button.configure(state="normal")

            if self.auto_update_job:
                self.root.after_cancel(self.auto_update_job)
                self.auto_update_job = None

            self.status_var.set("Status: Auto-Tracking OFF.")
            self.status_label.configure(text_color="gray")

    def update_location(self, is_manual=False):
        """
        Fetches new ISS data, updates GUI, and saves to log.
        """
        if not is_manual and not self.auto_update_enabled:
            return

        status_text = "Manual update..." if is_manual else "Auto-updating..."
        self.status_var.set(f"Status: {status_text}")
        self.status_label.configure(text_color="yellow")  # Processing color
        self.root.update_idletasks()

        data = self.data_fetcher.get_iss_position()

        if data:
            location_str = self.data_fetcher.get_location_details(
                data['latitude'], data['longitude']
            )

            # Update GUI labels
            self.lat_var.set(f"Latitude: {data['latitude']:.4f}")
            self.lon_var.set(f"Longitude: {data['longitude']:.4f}")
            self.time_var.set(f"Timestamp: {data['timestamp_str']}")
            self.location_var.set(f"Location: {location_str}")

            self._update_canvas_position(data['latitude'], data['longitude'])

            status_text = "Auto-Tracking ON" if self.auto_update_enabled else "Auto-Tracking OFF"
            self.status_var.set(f"Status: {status_text} | Last update: {datetime.now().strftime('%H:%M:%S')}")
            self.status_label.configure(text_color="#66B2FF")  # Success color

            # Save data
            data['location'] = location_str
            data.pop('timestamp_obj', None)
            self._save_log(data)
            self.last_position = data
        else:
            self.status_var.set("Error: Failed to fetch ISS data. Check connection.")
            self.status_label.configure(text_color="#FF6B6B")  # Error color

        if self.auto_update_enabled:
            self.auto_update_job = self.root.after(
                10000,  # 10 seconds
                lambda: self.update_location(is_manual=False)
            )

    def _update_canvas_position(self, lat, lon):
        """
        Converts lat/lon to canvas coords, moves the ISS, and draws the trail.
        """
        x = (lon + 180) * (self.canvas_width / 360)
        y = (90 - lat) * (self.canvas_height / 180)

        self.iss_trail_coords.append((x, y))
        if len(self.iss_trail_coords) > 100:
            self.iss_trail_coords.pop(0)

        self.canvas.delete("trail")
        if len(self.iss_trail_coords) > 1:
            self.canvas.create_line(
                self.iss_trail_coords,
                fill='yellow',
                width=2,
                tags="trail"
            )

        if self.iss_photo:
            self.canvas.coords(self.iss_item_id, x, y)
        else:
            self.canvas.coords(self.iss_item_id, x - 5, y - 5, x + 5, y + 5)

        self.canvas.tag_raise(self.iss_item_id)

    def _clear_trail(self):
        """Clears the ISS trail from the canvas."""
        self.iss_trail_coords = []
        self.canvas.delete("trail")
        self.status_var.set("Status: ISS trail cleared.")

    def _load_log(self):
        """Loads tracking history from the JSON log file."""
        if not os.path.exists(self.log_file):
            return []
        try:
            with open(self.log_file, 'r') as f:
                logs = json.load(f)
                return logs if isinstance(logs, list) else []
        except Exception as e:
            print(f"Error loading log: {e}")
            return []

    def _save_log(self, data_entry):
        """Appends a new data entry to the JSON log file."""
        logs = self._load_log()
        logs.append(data_entry)

        try:
            with open(self.log_file, 'w') as f:
                json.dump(logs, f, indent=4)
        except IOError as e:
            print(f"Failed to write to log file: {e}")

    def _show_toplevel_window(self, title):
        """Helper to create a standardized CTkToplevel window with a CTkTextbox."""
        win = ctk.CTkToplevel(self.root)
        win.title(title)
        win.geometry("500x400")
        win.transient(self.root)
        win.grab_set()

        text_widget = ctk.CTkTextbox(
            win,
            font=self.font_mono,
            wrap=tk.WORD,
            activate_scrollbars=True
        )
        text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        return text_widget

    def show_history(self):
        """Displays the tracking history in a new Toplevel window."""
        text_widget = self._show_toplevel_window("ISS Track History")
        logs = self._load_log()

        if logs:
            history_data = json.dumps(logs, indent=4)
            text_widget.insert("0.0", history_data)
        else:
            text_widget.insert("0.0", "No tracking history found.")

        text_widget.configure(state="disabled")

    def show_summary(self):
        """Analyzes log data and displays a summary."""
        text_widget = self._show_toplevel_window("Tracking Summary")
        logs = self._load_log()

        if not logs:
            text_widget.insert("0.0", "No tracking data to summarize.")
            text_widget.configure(state="disabled")
            return

        total_entries = len(logs)
        locations = [entry.get('location', 'N/A') for entry in logs if entry.get('location')]

        summary = f"--- ISS Tracking Summary ---\n\n"
        summary += f"Total log entries: {total_entries}\n\n"

        if locations:
            unique_locations = set(locations)
            summary += f"Unique locations tracked: {len(unique_locations)}\n\n"
            summary += "Most Frequent Locations:\n"
            summary += "--------------------------\n"
            location_counts = Counter(locations)
            for location, count in location_counts.most_common(10):
                summary += f"{location:<30} | {count} hits\n"
        else:
            summary += "No location data found in logs.\n"

        text_widget.insert("0.0", summary)
        text_widget.configure(state="disabled")

    def _show_about(self):
        """Displays the 'About' message box."""
        messagebox.showinfo(
            "About Modern ISS Tracker",
            "Version: 3.0 (CustomTkinter)\n\n"
            "This application tracks the International Space Station in real-time "
            "using data from Open Notify and BigDataCloud APIs.\n\n"
            "UI rebuilt with CustomTkinter."
        )

    def _toggle_day_night(self):
        """Toggles the map between day and night images."""
        if not self.map_image_id or not self.map_photo_night:
            self.status_var.set("Error: Night map 'world_map_night.png' not found.")
            self.status_label.configure(text_color="#FF6B6B")  # Error color
            return

        self.is_night_mode = not self.is_night_mode

        if self.is_night_mode:
            self.canvas.itemconfig(self.map_image_id, image=self.map_photo_night)
            self.status_var.set("Status: Night mode enabled.")
        else:
            self.canvas.itemconfig(self.map_image_id, image=self.map_photo_day)
            self.status_var.set("Status: Day mode enabled.")
        self.status_label.configure(text_color="gray")

    def _handle_view_menu(self, choice):
        """Handles the 'View Options' dropdown menu."""
        if choice == "Toggle Day/Night":
            self._toggle_day_night()
        elif choice == "Clear ISS Trail":
            self._clear_trail()
        self.root.after(100, lambda: self.view_menu.set("View Options"))

    def _toggle_theme(self):
        """Toggles the application's appearance mode."""
        new_mode = self.theme_switch.get()  # "Light" or "Dark"
        ctk.set_appearance_mode(new_mode)
        self.theme_switch.configure(text="Dark Mode" if new_mode == "Light" else "Light Mode")


if __name__ == "__main__":
    root = ctk.CTk()
    app = SpaceTrackerApp(root)
    root.mainloop()