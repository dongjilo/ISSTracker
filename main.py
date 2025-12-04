import tkinter as tk
import customtkinter as ctk
import os
import json
import math
import threading
import queue
from datetime import datetime
from PIL import Image, ImageTk
from collections import Counter
from iss_fetcher import ISSDataFetcher
from ui_components import ModernDataCard


class SpaceTrackerApp2025:
    """A Modern ISS Space Tracker made with CustomTkinter."""

    def __init__(self, root):
        """Initialize the main application."""
        self.root = root
        self.root.title("ISS Live Tracker")
        self.root.resizable(True, True)
        self.root.resizable(False, False)
        self.max_trail_points = 1200
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self.colors = {
            'bg_primary': "#040D21",
            'bg_secondary': "#0A0F2D",
            'bg_card': "#10172A",
            'accent_cyan': "#00E5FF",
            'accent_purple': "#7D5CFF",
            'accent_blue': "#2DCCFF",
            'text_primary': "#FFFFFF",
            'text_secondary': "#9CA3AF",
            'border': "#3d4d6d",
            'success': "#10B981",
            'error': "#EF4444"
        }

        self.root.configure(fg_color=self.colors['bg_primary'])

        self.data_fetcher = ISSDataFetcher()
        self.log_file = 'iss_tracking_log.json'
        self.canvas_width = 760
        self.canvas_height = 380
        self.auto_update_enabled = False
        self.auto_update_job = None
        self.last_position = None
        self.is_night_mode = False
        self.iss_trail_coords = []
        self.pulse_angle = 0
        self.map_photo_day = None
        self.map_photo_night = None
        self.iss_photo = None

        # Threading support
        self.update_queue = queue.Queue()
        self.fetch_thread = None
        self.is_fetching = False

        # Request staggering configuration
        self.update_interval = 1000  # 5 seconds between full updates
        self.cached_location = "Tracking"
        self.last_geo_update_time = 0
        self.geo_interval = 15
        self.api_call_delay = 0.5  # 500ms delay between different API calls
        self.min_request_interval = 1000  # Minimum 1 second between any requests
        self.last_request_time = 0

        # Canvas optimization
        self.grid_drawn = False
        self.trail_segments = []

        self._load_assets()
        self._create_widgets()
        self.update_location(is_manual=True)
        self._animate_pulse()
        self._process_queue()

    def _load_assets(self):
        """Load external images safely."""
        try:
            img_day = Image.open("world_map.png").resize((self.canvas_width, self.canvas_height))
            self.map_photo_day = ImageTk.PhotoImage(img_day)
        except Exception as e:
            print(f"Day map not found: {e}")

        try:
            img_night = Image.open("world_map_night.png").resize((self.canvas_width, self.canvas_height))
            self.map_photo_night = ImageTk.PhotoImage(img_night)
        except Exception as e:
            print(f"Night map not found: {e}")

        try:
            img_iss = Image.open("iss_icon.png").resize((32, 32))
            self.iss_photo = ImageTk.PhotoImage(img_iss)
        except Exception as e:
            print(f"ISS icon not found: {e}")

    def _create_widgets(self):
        """Create the modern UI."""
        main_container = ctk.CTkFrame(self.root, fg_color="transparent")
        main_container.pack(fill="both", expand=True, padx=20, pady=20)

        # === HEADER ===
        header = ctk.CTkFrame(
            main_container,
            fg_color=self.colors['bg_card'],
            corner_radius=24,
            border_width=1,
            border_color=self.colors['border']
        )
        header.pack(fill="x", pady=(0, 16))

        header_content = ctk.CTkFrame(header, fg_color="transparent")
        header_content.pack(fill="x", padx=24, pady=20)

        # Title
        title_frame = ctk.CTkFrame(header_content, fg_color="transparent")
        title_frame.pack(side="left")

        ctk.CTkLabel(
            title_frame,
            text="ISS LIVE TRACKER",
            font=ctk.CTkFont(family="Segoe UI", size=28, weight="bold"),
            text_color=self.colors['accent_cyan']
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_frame,
            text="Real-time orbital monitoring system",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=self.colors['text_secondary']
        ).pack(anchor="w")

        # Controls
        controls_frame = ctk.CTkFrame(header_content, fg_color="transparent")
        controls_frame.pack(side="right")

        self.status_indicator = ctk.CTkLabel(
            controls_frame, text="●", font=ctk.CTkFont(size=20),
            text_color=self.colors['text_secondary']
        )
        self.status_indicator.pack(side="left", padx=(0, 8))

        self.last_update_label = ctk.CTkLabel(
            controls_frame, text="Updated: --",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=self.colors['text_secondary']
        )
        self.last_update_label.pack(side="left", padx=(0, 16))

        self.track_button = ctk.CTkButton(
            controls_frame, text="START TRACKING",
            command=self._toggle_tracking, width=160, height=40,
            corner_radius=12, font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color=self.colors['accent_cyan'], hover_color=self.colors['accent_blue']
        )
        self.track_button.pack(side="left")

        content_grid = ctk.CTkFrame(main_container, fg_color="transparent")
        content_grid.pack(fill="both", expand=True)
        left_panel = ctk.CTkFrame(
            content_grid, fg_color=self.colors['bg_card'],
            corner_radius=24, border_width=1, border_color=self.colors['border']
        )
        left_panel.pack(side="left", fill="both", expand=True, padx=(0, 16))

        earth_header = ctk.CTkFrame(left_panel, fg_color="transparent")
        earth_header.pack(fill="x", padx=20, pady=(16, 12))
        ctk.CTkLabel(
            earth_header, text="EARTH PROJECTION",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=self.colors['text_primary']
        ).pack(side="left")

        view_controls = ctk.CTkFrame(earth_header, fg_color="transparent")
        view_controls.pack(side="right")
        self.mode_button = ctk.CTkButton(
            view_controls, text="🌙 Night Mode",
            command=self._toggle_day_night, width=120, height=32, corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color=("#1a2332", "#0f1419"), hover_color=("#2a3342", "#1f2429"),
            border_width=1, border_color=self.colors['border']
        )

        self.mode_button.pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            view_controls, text="Clear Trail", command=self._clear_trail,
            width=100, height=32, corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color=("#1a2332", "#0f1419"), hover_color=("#2a3342", "#1f2429"),
            border_width=1, border_color=self.colors['border']
        ).pack(side="left")

        canvas_container = ctk.CTkFrame(left_panel, fg_color="transparent")
        canvas_container.pack(padx=20, pady=(0, 20))
        self.canvas = tk.Canvas(
            canvas_container, width=self.canvas_width, height=self.canvas_height,
            bg='#0A0F2D', highlightthickness=0, relief='flat'
        )

        self.canvas.pack()
        if self.map_photo_day:
            self.map_image_id = self.canvas.create_image(
                0, 0, anchor=tk.NW, image=self.map_photo_day
            )

        coord_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        coord_frame.pack(fill="x", padx=20, pady=(0, 16))
        self.lat_display = ctk.CTkLabel(
            coord_frame, text="LAT: --",
            font=ctk.CTkFont(family="Courier New", size=11, weight="bold"),
            text_color=self.colors['accent_cyan'], fg_color=("#1a2332", "#0f1419"),
            corner_radius=8, padx=12, pady=6
        )
        self.lat_display.pack(side="left")

        self.lon_display = ctk.CTkLabel(
            coord_frame, text="LON: --",
            font=ctk.CTkFont(family="Courier New", size=11, weight="bold"),
            text_color=self.colors['accent_purple'], fg_color=("#1a2332", "#0f1419"),
            corner_radius=8, padx=12, pady=6
        )

        self.lon_display.pack(side="right")
        right_panel = ctk.CTkFrame(content_grid, fg_color="transparent")
        right_panel.pack(side="right", fill="y", anchor="n")

        coord_row = ctk.CTkFrame(right_panel, fg_color="transparent")
        coord_row.pack(fill="x", pady=(0, 10))

        self.card_latitude = ModernDataCard(
            coord_row, label="Latitude", unit="°", color=self.colors['accent_cyan'], width=135
        )
        self.card_latitude.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.card_longitude = ModernDataCard(
            coord_row, label="Longitude", unit="°", color=self.colors['accent_purple'], width=135
        )
        self.card_longitude.pack(side="left", fill="x", expand=True)

        telemetry_row = ctk.CTkFrame(right_panel, fg_color="transparent")
        telemetry_row.pack(fill="x", pady=(0, 10))

        self.card_altitude = ModernDataCard(
            telemetry_row, label="Altitude", value="408.0", unit="km", color=self.colors['accent_blue'], width=135
        )
        self.card_altitude.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.card_velocity = ModernDataCard(
            telemetry_row, label="Velocity", value="27.6", unit="km/s", color=self.colors['accent_cyan'], width=135
        )
        self.card_velocity.pack(side="left", fill="x", expand=True)

        self.card_location = ModernDataCard(
            right_panel, label="Location", unit="", color=self.colors['text_primary'], width=280
        )
        self.card_location.pack(fill="x", pady=(0, 10))

        status_panel = ctk.CTkFrame(
            right_panel,
            fg_color=("#1a2332", "#0f1419"),
            corner_radius=16,
            border_width=1,
            border_color=self.colors['border'],
            width=280
        )
        status_panel.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            status_panel,
            text="MISSION STATUS",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=self.colors['text_secondary']
        ).pack(pady=(12, 5), padx=12, anchor="w")

        separator = ctk.CTkFrame(
            status_panel,
            height=1,
            fg_color=self.colors['border']
        )
        separator.pack(fill="x", padx=12, pady=(0, 8))

        self.tracking_status = self._create_status_row(status_panel, "Tracking", "STANDBY")
        self.trail_status = self._create_status_row(status_panel, "Trail Points", "0")
        self.mode_status = self._create_status_row(status_panel, "Display Mode", "DAY")

        ctk.CTkButton(
            right_panel, text="MANUAL UPDATE", command=lambda: self.update_location(is_manual=True),
            height=40, corner_radius=10, font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color=self.colors['accent_purple'], hover_color="#6B4DD9"
        ).pack(fill="x", pady=(0, 10))

        # Action Buttons
        action_frame1 = ctk.CTkFrame(right_panel, fg_color="transparent")
        action_frame1.pack(fill="x", pady=(0, 0))

        ctk.CTkButton(
            action_frame1, text="Show History", command=self.show_history,
            height=36, corner_radius=10, font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=("#1a2332", "#0f1419"), hover_color=("#2a3342", "#1f2429"),
            border_width=1, border_color=self.colors['border']
        ).pack(side="left", fill="x", expand=True, padx=(0, 10))

        ctk.CTkButton(
            action_frame1, text="Show Summary", command=self.show_summary,
            height=36, corner_radius=10, font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=("#1a2332", "#0f1419"), hover_color=("#2a3342", "#1f2429"),
            border_width=1, border_color=self.colors['border']
        ).pack(side="left", fill="x", expand=True)

    def _create_status_row(self, parent, label, value):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(
            row, text=label, font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=self.colors['text_secondary']
        ).pack(side="left")
        value_label = ctk.CTkLabel(
            row, text=value, font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=self.colors['accent_cyan']
        )
        value_label.pack(side="right")
        return value_label

    def _toggle_tracking(self):
        self.auto_update_enabled = not self.auto_update_enabled
        if self.auto_update_enabled:
            self.track_button.configure(
                text="STOP TRACKING", fg_color=self.colors['error'], hover_color="#DC2626"
            )
            self.status_indicator.configure(text_color=self.colors['success'])
            self.tracking_status.configure(text="ACTIVE", text_color=self.colors['success'])
            self.update_location(is_manual=False)
        else:
            self.track_button.configure(
                text="START TRACKING", fg_color=self.colors['accent_cyan'], hover_color=self.colors['accent_blue']
            )
            self.status_indicator.configure(text_color=self.colors['text_secondary'])
            self.tracking_status.configure(text="STANDBY", text_color=self.colors['text_secondary'])
            if self.auto_update_job:
                self.root.after_cancel(self.auto_update_job)
                self.auto_update_job = None

    def _fetch_data_async(self, is_manual):
        """
        Fetches position immediately but staggers location lookups to prevent lag.
        Runs in a background thread.
        """
        if self.is_fetching:
            return

        # Ensure we import time (add to top of file if missing)
        import time

        self.is_fetching = True

        try:
            data = self.data_fetcher.get_iss_position()

            if data:
                current_time = time.time()

                if is_manual or (current_time - self.last_geo_update_time > self.geo_interval):
                    try:
                        # Fetch new address and update cache
                        new_location = self.data_fetcher.get_location_details(
                            data['latitude'], data['longitude']
                        )
                        self.cached_location = new_location
                        self.last_geo_update_time = current_time
                    except Exception as e:
                        print(f"Geo lookup skipped: {e}")

                # Attach the cached location to the fresh position data
                data['location'] = self.cached_location

                # Send combined data to UI immediately
                self.update_queue.put(('data', data))

        except Exception as e:
            print(f"Error fetching data: {e}")
            self.update_queue.put(('error', str(e)))
        finally:
            self.is_fetching = False
            # Schedule next update immediately if tracking
            if not is_manual and self.auto_update_enabled:
                self.update_queue.put(('schedule', None))

    def _process_queue(self):
        """Process queued updates from background thread."""
        try:
            while True:
                msg_type, data = self.update_queue.get_nowait()

                if msg_type == 'data':
                    self._update_ui_with_data(data)
                elif msg_type == 'schedule':
                    if self.auto_update_enabled:
                        # Use configurable update interval
                        self.auto_update_job = self.root.after(
                            self.update_interval,
                            lambda: self.update_location(is_manual=False)
                        )
                elif msg_type == 'error':
                    print(f"Update error: {data}")

        except queue.Empty:
            pass

        # Keep checking queue
        self.root.after(100, self._process_queue)

    def _update_ui_with_data(self, data):
        """Update UI elements with fetched data (runs on main thread)."""
        self.card_latitude.update_value(f"{data['latitude']:.4f}")
        self.card_longitude.update_value(f"{data['longitude']:.4f}")
        self.card_altitude.update_value(f"{data['altitude']:.1f}")
        velocity_kms = self._calculate_real_velocity(data)
        data['velocity'] = velocity_kms
        self.card_velocity.update_value(f"{velocity_kms:.2f}")
        self.card_location.update_value(data['location'][:25])
        self.lat_display.configure(text=f"LAT: {data['latitude']:.4f}°")
        self.lon_display.configure(text=f"LON: {data['longitude']:.4f}°")
        self.last_update_label.configure(text=f"Updated: {datetime.now().strftime('%H:%M:%S')}")

        self._update_canvas_position(data['latitude'], data['longitude'])
        self.trail_status.configure(text=str(len(self.iss_trail_coords)))

        # Save log
        log_data = data.copy()
        log_data.pop('timestamp_obj', None)
        self._save_log(log_data)
        self.last_position = data

    def update_location(self, is_manual=False):
        """Fetch and update ISS position (non-blocking)."""
        if not is_manual and not self.auto_update_enabled:
            return

        # Start fetch in background thread
        self.fetch_thread = threading.Thread(
            target=self._fetch_data_async,
            args=(is_manual,),
            daemon=True
        )
        self.fetch_thread.start()

    def _calculate_real_velocity(self, new_data):
        """Calculates velocity based on distance moved over time."""
        if not self.last_position:
            return 27600.0  # Fallback to average

        try:
            lat1 = math.radians(self.last_position['latitude'])
            lon1 = math.radians(self.last_position['longitude'])
            lat2 = math.radians(new_data['latitude'])
            lon2 = math.radians(new_data['longitude'])

            R = 6371.0
            dlon = lon2 - lon1
            dlat = lat2 - lat1

            a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            distance_km = R * c

            t1 = self.last_position['timestamp_obj'].timestamp()
            t2 = new_data['timestamp_obj'].timestamp()
            time_diff = t2 - t1

            if time_diff <= 0:
                return self.last_position.get('velocity', 27600.0)

            velocity_km_s = distance_km / time_diff

            return velocity_km_s * 3600.0

        except Exception as e:
            print(f"Velocity calc error: {e}")
            return 27600.0

    def _draw_grid_once(self):
        """Draw grid lines once and cache them."""
        if self.grid_drawn:
            return

        self.canvas.delete("grid")
        for i in range(13):
            self.canvas.create_line(
                (self.canvas_width / 12) * i, 0,
                (self.canvas_width / 12) * i, self.canvas_height,
                fill='#7D5CFF', width=1, stipple='gray25', tags="grid"
            )
        for i in range(7):
            self.canvas.create_line(
                0, (self.canvas_height / 6) * i,
                self.canvas_width, (self.canvas_height / 6) * i,
                fill='#7D5CFF', width=1, stipple='gray25', tags="grid"
            )
        self.grid_drawn = True

    def _update_canvas_position(self, lat, lon):
        """Update ISS position on canvas with trail, handling map wrapping."""
        x = (lon + 180) * (self.canvas_width / 360)
        y = (90 - lat) * (self.canvas_height / 180)

        self.iss_trail_coords.append((x, y))
        if len(self.iss_trail_coords) > self.max_trail_points:
            self.iss_trail_coords.pop(0)

        # Draw grid only once
        self._draw_grid_once()

        # Only redraw trail, not entire canvas
        self.canvas.delete("trail")

        if len(self.iss_trail_coords) > 1:
            current_segment = [self.iss_trail_coords[0]]

            for i in range(1, len(self.iss_trail_coords)):
                x1, y1 = self.iss_trail_coords[i - 1]
                x2, y2 = self.iss_trail_coords[i]
                if abs(x2 - x1) > self.canvas_width / 2:
                    # Draw the previous segment
                    if len(current_segment) > 1:
                        self.canvas.create_line(
                            current_segment,
                            fill='#00E5FF',
                            width=2,
                            smooth=True,
                            tags="trail"
                        )

                    current_segment = [(x2, y2)]
                else:
                    current_segment.append((x2, y2))

            if len(current_segment) > 1:
                self.canvas.create_line(
                    current_segment,
                    fill='#00E5FF',
                    width=2,
                    smooth=True,
                    tags="trail"
                )

        self.canvas.delete("iss")
        self.canvas.create_oval(
            x - 20, y - 20, x + 20, y + 20,
            fill='', outline='#00E5FF', width=2,
            tags="iss"
        )
        self.canvas.create_oval(
            x - 6, y - 6, x + 6, y + 6,
            fill='#00E5FF', outline='white', width=2,
            tags="iss"
        )

    def _animate_pulse(self):
        """Animate the status indicator pulse."""
        if self.auto_update_enabled:
            self.pulse_angle = (self.pulse_angle + 10) % 360
            alpha = int(128 + 127 * math.sin(math.radians(self.pulse_angle)))
            color = f"#{alpha:02x}FF{alpha:02x}"
            self.status_indicator.configure(text_color=color)
            self.root.after(50, self._animate_pulse)
        else:
            # Only schedule next animation if tracking is active
            self.root.after(200, self._animate_pulse)

    def _toggle_day_night(self):
        if not self.map_photo_night: return
        self.is_night_mode = not self.is_night_mode
        if self.is_night_mode:
            self.canvas.itemconfig(self.map_image_id, image=self.map_photo_night)
            self.mode_button.configure(text="☀️ Day Mode")
            self.mode_status.configure(text="NIGHT")
        else:
            self.canvas.itemconfig(self.map_image_id, image=self.map_photo_day)
            self.mode_button.configure(text="🌙 Night Mode")
            self.mode_status.configure(text="DAY")

    def _clear_trail(self):
        self.iss_trail_coords = []
        self.canvas.delete("trail")
        self.trail_status.configure(text="0")

    def _load_log(self):
        if not os.path.exists(self.log_file): return []
        try:
            with open(self.log_file, 'r') as f:
                logs = json.load(f)
                return logs if isinstance(logs, list) else []
        except Exception as e:
            print(f"Error loading log: {e}");
            return []

    def _save_log(self, data_entry):
        """Append data entry to JSON log file (async to avoid blocking)."""

        def save_thread():
            logs = self._load_log()
            logs.append(data_entry)
            try:
                with open(self.log_file, 'w', encoding='utf-8') as f:
                    json.dump(logs, f, indent=4, ensure_ascii=False)
            except IOError as e:
                print(f"Failed to write to log file: {e}")

        threading.Thread(target=save_thread, daemon=True).start()

    def show_history(self):
        win = ctk.CTkToplevel(self.root)
        win.title("ISS Track History")
        win.geometry("600x500")
        win.configure(fg_color=self.colors['bg_primary'])
        text_widget = ctk.CTkTextbox(
            win, font=ctk.CTkFont(family="Courier New", size=11), wrap="word",
            fg_color=self.colors['bg_card'], border_width=1, border_color=self.colors['border']
        )
        text_widget.pack(fill="both", expand=True, padx=20, pady=20)

        # Load logs in background
        def load_logs():
            logs = self._load_log()
            if logs:
                text = json.dumps(logs, indent=4)
            else:
                text = "No tracking history found."
            self.root.after(0, lambda: self._display_history(text_widget, text))

        threading.Thread(target=load_logs, daemon=True).start()

    def _display_history(self, text_widget, text):
        text_widget.insert("0.0", text)
        text_widget.configure(state="disabled")

    def show_summary(self):
        win = ctk.CTkToplevel(self.root)
        win.title("Tracking Summary")
        win.geometry("600x500")
        win.configure(fg_color=self.colors['bg_primary'])
        text_widget = ctk.CTkTextbox(
            win, font=ctk.CTkFont(family="Courier New", size=11), wrap="word",
            fg_color=self.colors['bg_card'], border_width=1, border_color=self.colors['border']
        )
        text_widget.pack(fill="both", expand=True, padx=20, pady=20)

        # Generate summary in background
        def generate_summary():
            logs = self._load_log()
            if not logs:
                summary = "No tracking data to summarize."
            else:
                total_entries = len(logs)
                locations = [entry.get('location', 'N/A') for entry in logs if entry.get('location')]
                summary = f"=== ISS TRACKING SUMMARY ===\n\nTotal log entries: {total_entries}\n\n"
                if locations:
                    unique_locations = set(locations)
                    summary += f"Unique locations: {len(unique_locations)}\n\nMost Frequent Locations:\n" + (
                                "-" * 50) + "\n"
                    location_counts = Counter(locations)
                    for location, count in location_counts.most_common(10):
                        summary += f"{location:<35} | {count:>3} hits\n"
                else:
                    summary += "No location data found in logs.\n"

            self.root.after(0, lambda: self._display_history(text_widget, summary))

        threading.Thread(target=generate_summary, daemon=True).start()


if __name__ == "__main__":
    root = ctk.CTk()
    app = SpaceTrackerApp2025(root)
    root.mainloop()