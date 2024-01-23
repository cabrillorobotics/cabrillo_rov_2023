from os import path
from enum import Enum

from PyQt5 import QtWidgets as qtw
from PyQt5 import QtCore as qtc
from PyQt5 import QtGui as qtg

from seahawk_deck.dash_styling.color_palette import DARK_MODE

COLOR_CONSTS = DARK_MODE
PATH = path.dirname(__file__)


class SecSpinBox(qtw.QSpinBox):
    """
    Class which inherits from 'qtw.QSpinBox'. An instance behaves identical to 'qtw.QSpinBox'
    except numbers are formatted such that single digits have a leading zero. Example: 5 becomes 05. 
    This is useful to represent seconds for a timer.
    """

    def init(self):
        """
        Initialize 'SecSpinBox' object
        """
        super().init()
    
    def textFromValue(self, v: int)-> str:
        """
        Used by the spin box whenever it needs to display the given value. This redefinition
        formats numbers such that single digits have a leading zero.

        Args:
            v: Value to display
        
        Returns:
            The value prefixed with a leading zero if only one digit 
        """
        return "0" + str_v  if len(str_v := str(v)) == 1 else str_v

    def valueFromText(self, text: str) -> int:
        """
        Used by the spin box whenever it needs to interpret text entered by the user as a value

        Args:
            text: The text to reinterpret as an integer value
        
        Returns:
            The text interpreted as a number
        """
        return int(text)


class TimerStatus(Enum):
    """
    Tracks the current status of the timer
    """
    init, counting, paused = 0, 1, 2

class CountStatus(Enum):
    """
    Tracks wether the timer is counting up or down
    """
    counting_down, counting_up = 0, 1

class CountdownWidget(qtw.QWidget):
    """
    Creates a 'CountdownWidget' which inherits from the 'qtw.QWidget' class. A 'CountdownWidget'
    includes a timer which counts down from some amount of time. The timer may be provided with a default
    value to start at, this can always be modified using the application at runtime. The widget
    also includes a start, pause/resume and stop button. Once the timer reaches 00:00, it begins counting
    with negative values until the user terminates the timer
    """

    def __init__(self, parent: qtw.QWidget, style_sheet_file: str, minutes: int = 0, seconds: int = 0):
        """
        Initialize countdown widget
        
        Args:
            parent: Widget to overlay 'CountdownWidget' on
            style_sheet_file: Style sheet text file formatted as a CSS f-string
            minutes: Default number of minutes the timer should start at  (defaults to 0)
            seconds: Default number of seconds the timer should start at  (defaults to 0)
        """
        super().__init__(parent)
       
        # Define layout of frame on parent
        layout_outer = qtw.QVBoxLayout(self)
        self.setLayout(layout_outer)

        # Create frame widget and display
        frame = qtw.QFrame()
        layout_outer.addWidget(frame)

        # Set layout of widgets on frame to grid
        layout_inner = qtw.QGridLayout(frame)
        frame.setLayout(layout_inner)
        
        # Setup minutes spin box
        self.min_spin_box = qtw.QSpinBox()
        self.min_spin_box.setRange(0, 59)
        self.min_spin_box.setWrapping(True)
        self.min_spin_box.setValue(minutes)
        self.min_spin_box.valueChanged.connect(self.spin_box_edit_event)
        
        # Setup seconds spin box
        self.sec_spin_box = SecSpinBox()
        self.sec_spin_box.setSingleStep(5)
        self.sec_spin_box.setRange(0, 59)
        self.sec_spin_box.setWrapping(True)
        self.sec_spin_box.setValue(seconds)
        self.sec_spin_box.valueChanged.connect(self.spin_box_edit_event)

        # Setup title
        self.title = qtw.QLabel()
        self.title.setAccessibleName("Title")
        self.title.setText("Timer")

        # Setup label to display timer
        self.timer_display = qtw.QLabel()
        self.timer_display.setAccessibleName("Timer Display")
        self.timer_display.setText(f"{self.min_spin_box.value()}:{self.sec_spin_box.textFromValue(self.sec_spin_box.value())}")

        # Setup start button
        self.start_button = qtw.QPushButton("Start")
        self.start_button.setAccessibleName("Start")
        self.start_button.clicked.connect(self.start_event)

        # Setup stop button
        self.stop_button = qtw.QPushButton("Stop")
        self.start_button.setAccessibleName("Stop")
        self.stop_button.clicked.connect(self.stop_event)

        # Add widgets to frame
        layout_inner.addWidget(self.title, 0, 0, 1, 2)
        layout_inner.addWidget(self.timer_display, 1, 0, 1, 2)
        layout_inner.addWidget(self.min_spin_box, 2, 0)
        layout_inner.addWidget(self.sec_spin_box, 2, 1)
        layout_inner.addWidget(self.start_button, 3, 0)
        layout_inner.addWidget(self.stop_button, 3, 1)
        layout_inner.setRowStretch(1, 20)

        # Setup timer
        self.timer = qtc.QTimer()
        self.timer.timeout.connect(self.countdown_and_display)
        self.status = TimerStatus.init
        self.count_status = CountStatus.counting_down
        self.sec_remaining = minutes * 60 + seconds
        self.display_time()

        # Apply css styling
        with open(style_sheet_file) as style_sheet:
            self.setStyleSheet(style_sheet.read().format(**COLOR_CONSTS))
        # Set style of stop button to be red when pressed, could not be included in style sheet
        self.stop_button.setStyleSheet(f"QPushButton::pressed {{background-color: {COLOR_CONSTS['WARNING']};}}")

    def spin_box_edit_event(self):
        """
        Called when a spin box is edited. Updates time display upon edit.
        """
        if self.status == TimerStatus.init:
            self.sec_remaining = self.min_spin_box.value() * 60 + self.sec_spin_box.value()
            self.display_time()

    def start_event(self):
        """
        Called when the start button is pressed. The start button switches to a pause button when the
        timer is running. Start/pause timer, display time, and modify button function to start or pause
        """
        # The timer should start (resume if was paused)
        if (self.status == TimerStatus.init or self.status == TimerStatus.paused) and self.sec_remaining > 0:
            self.status = TimerStatus.counting
            self.sec_remaining -= 1
            self.display_time()
            self.timer.start(1000) # Starts or restarts the timer with a timeout of duration msec milliseconds.
            self.start_button.setText("Pause") # Start button becomes pause button upon counting
        # Timer is paused
        elif self.status == TimerStatus.counting:
            self.timer.stop()
            self.status = TimerStatus.paused
            self.start_button.setText("Start")

    def stop_event(self):
        """
        Called when the stop button is pressed. Stops timer and resets timer to original settings
        """
        self.timer.stop()

        # Reset timer to original settings
        self.display_time()
        self.start_button.setText("Start")
        self.status = TimerStatus.init
        self.count_status = CountStatus.counting_down
        self.timer_display.setStyleSheet(f"color: {COLOR_CONSTS['ACCENT_LIGHT']};")
        self.sec_remaining = self.min_spin_box.value() * 60 + self.sec_spin_box.value()

    def countdown_and_display(self):
        """
        Called every second. While the remaining time is greater than zero, remove one second from the
        counter display. If the timer reaches zero, change text color to red and begin counting negatives
        Update time display
        """
        if self.sec_remaining == 0:
            self.count_status = CountStatus.counting_up

        if self.count_status == CountStatus.counting_down:
            self.sec_remaining -= 1
        else:
            # Begin counting up and change text color to red
            self.timer_display.setStyleSheet(f"color: {COLOR_CONSTS['WARNING']};")
            self.sec_remaining += 1

        self.display_time()

    def display_time(self):
        """
        Updates timer display text. Formats time as MM:SS
        """
        sec_formatted = "0" + str_sec if len(str_sec := str(self.sec_remaining % 60)) == 1 else str_sec
        min_formatted = self.sec_remaining // 60 if self.count_status == CountStatus.counting_down else "-" + str(self.sec_remaining // 60)
        self.timer_display.setText(f"{min_formatted}:{sec_formatted}")
