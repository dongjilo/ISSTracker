import tkinter as tk
import customtkinter as ctk

class ModernDataCard(ctk.CTkFrame):
    """A modern glass-morphic data card widget."""

    def __init__(self, parent, label, value="--", unit="", color="#00E5FF", **kwargs):
        super().__init__(parent, **kwargs)

        self.configure(
            fg_color=("#1a2332", "#0f1419"),
            corner_radius=16,
            border_width=1,
            border_color=("#3d4d6d", "#3d4d6d")
        )
        self.label_widget = ctk.CTkLabel(
            self,
            text=label.upper(),
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=("#9CA3AF", "#6B7280")
        )
        self.label_widget.pack(pady=(12, 4), padx=12, anchor="w")

        value_frame = ctk.CTkFrame(self, fg_color="transparent")
        value_frame.pack(pady=(0, 12), padx=12, anchor="w")

        self.value_var = tk.StringVar(value=value)
        self.value_widget = ctk.CTkLabel(
            value_frame,
            textvariable=self.value_var,
            font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"),
            text_color=color
        )
        self.value_widget.pack(side="left")

        self.unit_widget = ctk.CTkLabel(
            value_frame,
            text=unit,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=("#6B7280", "#4B5563")
        )
        self.unit_widget.pack(side="left", padx=(4, 0))

    def update_value(self, value):
        """Update the card's value."""
        self.value_var.set(value)