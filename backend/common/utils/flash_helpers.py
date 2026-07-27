"""
Flash Helpers
Provides standard helper methods for user notifications.
"""
from flask import flash

def flash_success(message):
    flash(message, "success")

def flash_error(message):
    flash(message, "danger")

def flash_warning(message):
    flash(message, "warning")

def flash_info(message):
    flash(message, "info")
