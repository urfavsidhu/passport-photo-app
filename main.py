"""Main entry point for Passport Photo App.

Initializes logging, QApplication, styles, settings, and handles
first-run setup wizard before launching the main window.
Includes a global unhandled exception hook for friendly crash protection.
"""

import logging
import logging.handlers
import sys
import traceback
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from app.settings_manager import SettingsManager, resource_path, user_data_dir


def setup_logging() -> None:
    """Set up rotating file logger in %APPDATA%/PassportPhotoApp/logs/."""
    log_dir = user_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Format
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] (%(name)s:%(lineno)d): %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Rotating file handler (5 MB, 3 backups)
    file_handler = logging.handlers.RotatingFileHandler(
        str(log_file), maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)

    logging.info("=== Passport Photo App starting ===")


def global_exception_hook(exc_type, exc_value, exc_traceback) -> None:
    """Catch unhandled exceptions, log them, and show a friendly UI dialog."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    err_text = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    logging.critical("Unhandled application exception:\n%s", err_text)

    # Show friendly message in UI if QApplication exists
    app = QApplication.instance()
    if app:
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setWindowTitle("Unexpected Application Error")
        msg.setText(
            "An unexpected error occurred.\n\n"
            f"Error: {exc_value}\n\n"
            "The error details have been saved to your log file in AppData."
        )
        msg.setDetailedText(err_text)
        msg.exec()


def main() -> int:
    """Application main entry point."""
    setup_logging()
    sys.excepthook = global_exception_hook

    # Enable High DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("PassportPhotoApp")
    app.setOrganizationName("PassportPhotoApp")
    app.setFont(QFont("Segoe UI", 10))

    # Load App Icon
    icon_path = resource_path("assets/icon.ico")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Load QSS stylesheet
    qss_path = resource_path("app/ui/styles.qss")
    if qss_path.exists():
        try:
            with open(qss_path, "r", encoding="utf-8") as f:
                app.setStyleSheet(f.read())
            logging.info("Loaded stylesheet from %s", qss_path)
        except Exception as exc:
            logging.warning("Could not load styles.qss: %s", exc)

    # Initialize Settings
    settings = SettingsManager()

    # Show first-run wizard if not completed yet
    first_run_done = settings.get("first_run_done", False)
    if not first_run_done:
        logging.info("First run detected. Launching setup wizard...")
        from app.ui.setup_wizard import SetupWizard
        wizard = SetupWizard(settings)
        # If user cancels wizard on first run, we still proceed with defaults
        wizard.exec()

    # Launch Main Window
    from app.ui.main_window import MainWindow
    window = MainWindow(settings)
    window.show()

    return app.exec()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
