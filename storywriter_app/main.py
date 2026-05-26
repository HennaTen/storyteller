import sys
import traceback

from PyQt5.QtWidgets import QApplication

from .widgets import StoryWriter


def excepthook(exc_type, exc_value, exc_tb):
    tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    print("catched:", tb)
    sys.__excepthook__(exc_type, exc_value, exc_tb)


def main():
    app = QApplication([])
    sys.excepthook = excepthook
    form = StoryWriter()
    form.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
