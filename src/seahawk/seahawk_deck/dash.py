import sys
from os import environ, path
from threading import Thread

from PyQt5 import QtWidgets as qtw
from PyQt5.QtGui import QKeyEvent
from cv_bridge import CvBridge, CvBridgeError
from PyQt5 import QtGui as qtg
# from PyQt5 import QtCore as qtc
import rclpy
from rclpy.node import Node 
from rclpy.publisher import Publisher
from std_msgs.msg import Int32
from sensor_msgs.msg import Image
from rclpy.executors import ExternalShutdownException
from rclpy.executors import MultiThreadedExecutor
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup

from seahawk_deck.dash_styling.color_palette import DARK_MODE
from seahawk_deck.dash_widgets.countdown_widget import CountdownWidget
from seahawk_deck.dash_widgets.numeric_data_widget import NumericDataWidget
from seahawk_deck.dash_widgets.state_widget import StateWidget
from seahawk_deck.dash_widgets.throttle_curve_widget import ThrtCrvWidget
from seahawk_deck.dash_widgets.turn_bank_indicator_widget import TurnBankIndicator
# from seahawk_deck.dash_widgets.image_view import Image_View
from seahawk_msgs.msg import InputStates, DebugInfo

COLOR_CONSTS = DARK_MODE
PATH = path.dirname(__file__)


class MainWindow(qtw.QMainWindow):
    """
    Creates a 'MainWindow' which inherits from the 'qtw.QMainWindow' class. 'MainWindow'
    provides the main dash window space to overlay widgets
    """

    def __init__(self):
        """
        Set up the 'MainWindow', overlay 'TabWidget's for multiple dash views, and display window
        """
        super().__init__()

        # Set up main window
        self.setWindowTitle("SeaHawk II Dashboard")
        self.setStyleSheet(f"background-color: {COLOR_CONSTS['MAIN_WIN_BKG']};")

        # Create tabs
        self.tab_widget = TabWidget(self, PATH + "/dash_styling/tab_widget.txt")
        self.setCentralWidget(self.tab_widget)

        self.keystroke_pub = None

        # Display window
        self.showMaximized()

    def keyPressEvent(self, a0: QKeyEvent) -> None:
        """
        Called for each time there is a keystroke. Publishes the code of the key that was
        pressed or released to the ROS topic 'keystroke'
        """
        msg = Int32()
        msg.data = a0.key()
        self.keystroke_pub.publish(msg)

    def add_keystroke_publisher(self, pub: Publisher):
        """
        Adds the keystroke publisher to 'MainWindow'
        """
        self.keystroke_pub = pub


class TabWidget(qtw.QWidget):
    """
    Creates a 'TabWidget' which inherits from the 'qtw.QWidget' class. A 'TabWidget' provides 
    a tab bar and a page area that is used to display pages related to each tab. The tab bar is 
    shown above the page area. Each tab is associated with a different widget called a page. 
    Only the current page is shown in the page area; all the other pages are hidden. The user can 
    show a different page by clicking on its tab
    """

    def __init__(self, parent: MainWindow, style_sheet_file: str):
        """
        Initialize tab widget

        Args:
            parent: Window where to place tabs
            style_sheet_file: Style sheet text file formatted as a CSS f-string
        """
        super().__init__(parent)
        
        # Define layout of tabs
        layout = qtw.QVBoxLayout(self)
        self.setLayout(layout)

        # Initialize tabs
        tabs = qtw.QTabWidget()

        # Create a dict in which the key is the provided name of the tab, and the value is a qtw.QWidget() object
        tab_names = ["Pilot", "Co-Pilot", "VPF", "Debug", "Cameras", "Control Mapping"]
        self.tab_dict = {name: qtw.QWidget() for name in tab_names}

        # Add tabs
        for name, tab in self.tab_dict.items():
            tabs.addTab(tab, name)
        
        # Apply css styling
        with open(style_sheet_file) as style_sheet:
            self.setStyleSheet(style_sheet.read().format(**COLOR_CONSTS))
        
        # Add tabs to widget
        layout.addWidget(tabs)

        # Create specific tabs
        self.create_pilot_tab(self.tab_dict["Pilot"])
    
    def create_pilot_tab(self, tab):
        """
        Creates pilot dash tab with the following widgets:
            - Feature states:   Displays the states of Bambi Mode (on/off), the claw (closed/open), CoM shift (engaged/not)
            - Throttle curve:   Displays the activated throttle curve
            - Temperature:      Displays the temperature reading
            - Depth:            Displays the depth reading
            - IMU:              Displays the IMU readings as a turn/bank indicator (graphic to help keep constant acceleration)
            - Countdown:        Displays a countdown
        """
        # Setup layouts
        home_window_layout = qtw.QHBoxLayout(tab)
        vert_widgets_layout = qtw.QVBoxLayout()
        vert_widgets_layout.setSpacing(0)
        cam_layout = qtw.QVBoxLayout()

        # Create widgets
        self.state_widget = StateWidget(tab, ["Bambi Mode", "Claw", "CoM Shift"], PATH + "/dash_styling/state_widget.txt")
        self.thrt_crv_widget = ThrtCrvWidget(tab)
        self.temp_widget = NumericDataWidget(tab, "Temperature", PATH + "/dash_styling/numeric_data_widget.txt")
        self.depth_widget = NumericDataWidget(tab, "Depth", PATH + "/dash_styling/numeric_data_widget.txt")
        self.turn_bank_indicator_widget = TurnBankIndicator(tab, PATH + "/dash_styling/numeric_data_widget.txt")
        self.countdown_widget = CountdownWidget(tab, PATH + "/dash_styling/countdown_widget.txt", minutes=15, seconds=0)

        # Add widgets to side vertical layout
        # Stretch modifies the ratios of the widgets (must add up to 100)
        vert_widgets_layout.addWidget(self.state_widget, stretch=16)
        vert_widgets_layout.addWidget(self.thrt_crv_widget, stretch=16)
        vert_widgets_layout.addWidget(self.temp_widget, stretch=16)
        vert_widgets_layout.addWidget(self.depth_widget, stretch=16)
        vert_widgets_layout.addWidget(self.turn_bank_indicator_widget, stretch=16)
        vert_widgets_layout.addWidget(self.countdown_widget, stretch=20)

        # Temp code for cameras
        self.label = qtw.QLabel()
        cam_layout.addWidget(self.label)

        home_window_layout.addLayout(vert_widgets_layout, stretch=1)
        home_window_layout.addLayout(cam_layout, stretch=9)

    def update_pilot_tab_input_states(self, state_to_update: str):
        """
        Update gui display of input states

        Args:
            feat_state_update: List of values to update for the feature widget
            thrt_crv_update: Updated value for throttle curve
        """
        self.state_widget.update_state(state_to_update["state_widget"])
        self.thrt_crv_widget.update_thrt_crv(state_to_update["throttle_curve"])
    
    def update_cam_img(self, cam_msg: Image):
        self.bridge = CvBridge()
        try:
            cv_image = self.bridge.imgmsg_to_cv2(cam_msg, desired_encoding="bgr8")
        except CvBridgeError as error:
            print(f"Image_View.callback_img() failed while trying to convert image from {cam_msg.encoding} to 'bgr8'.\n{error}")
            sys.exit()
        
        height, width, channel = cv_image.shape
        bytesPerLine = 3 * width
        frame = qtg.QImage(cv_image.data, width, height, bytesPerLine, qtg.QImage.Format_RGB888).rgbSwapped()
        self.label.setPixmap(qtg.QPixmap(frame))


class Dash(Node):
    """
    Creates and runs a ROS node which updates the PyQt dashboard with data from ROS topics
    """

    def __init__(self, dash_window):
        """
        Initialize 'dash' node
        """
        super().__init__("dash")
        self.dash_window = dash_window

        dash_group = MutuallyExclusiveCallbackGroup()
        cam_group = MutuallyExclusiveCallbackGroup()

        self.create_subscription(InputStates, "input_states", self.callback_input_states, 10, callback_group=dash_group)
        self.create_subscription(DebugInfo, "debug_info", self.callback_debug, 10, callback_group=dash_group)
        # self.create_subscription(Image, "repub_raw", self.callback_img, 10, callback_group=cam_group)
        # self.create_subscription(Packet, "republish_claw_camera", self.callback_camera, 10)
        
        # Add keystroke publisher to the dash so it can capture keystrokes and publish them to the ROS network
        dash_window.add_keystroke_publisher(self.create_publisher(Int32, "keystroke", 10))

    def callback_input_states(self, input_state_msg: InputStates): 
        """
        For every message published to the 'input_states' topic, update the relevant values on the gui 

        Updates dash representation of:
            - Bambi mode
            - Claw state 
            - CoM shift
            - Throttle curve option
        Based on values from 'input_states' topic

        Args:
            input_state_msg: Message from the type 'InputStates' from the 'input_states' topic
        """
        # Map the values sent from 'input_states' to feature names
        input_state_dict = {
            "state_widget": {
                "Bambi Mode":   input_state_msg.bambi_mode,
                "Claw":         input_state_msg.claw_state,
                "CoM Shift":    input_state_msg.com_shift,
            },
            "throttle_curve":   int(input_state_msg.throttle_curve),
        }
        self.dash_window.tab_widget.update_pilot_tab_input_states(input_state_dict)

    def callback_img(self, camera_msg: Image):
        self.dash_window.tab_widget.update_cam_img(camera_msg)

    def callback_debug(self):
        pass


def fix_term():
    """
    If VS Code was installed with snap, the 'GTK_PATH' variable must be unset.
    This is automated in this function
    """
    if "GTK_PATH" in environ and "snap" in environ["GTK_PATH"]:
        environ.pop("GTK_PATH")


def main(args=None):
    rclpy.init(args=args)
    
    fix_term()

    executor = MultiThreadedExecutor(num_threads=4)

    app = qtw.QApplication([])
    pilot_dash = MainWindow()
    
    # Setup node
    dash_node = Dash(pilot_dash)

    # Threading allows the process to display the dash and run the node at the same time
    # Create and start a thread for rclpy.spin function so the node spins while the dash is running
    executor.add_node(dash_node)

    node_thread = Thread(target=executor.spin, args=())
    node_thread.start()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main(sys.argv)