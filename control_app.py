import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, 
                           QWidget, QMessageBox, QLabel, QGridLayout, QLineEdit,
                           QGroupBox, QFormLayout)
from PyQt5.QtCore import Qt, QTimer
import socket
import threading
import time

class ControlApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Control Panel")
        
        # TCP/IP settings for two backends with two sockets each
        self.backends = [
            {"host": "localhost", "ports": [9090, 9091], "name": "Backend 1", 
             "reconnect_start": 0, "is_reconnecting": False, "ready": False,
             "sockets": [None, None]},  # Store socket objects
            {"host": "localhost", "ports": [9092, 9093], "name": "Backend 2",
             "reconnect_start": 0, "is_reconnecting": False, "ready": False,
             "sockets": [None, None]}   # Store socket objects
        ]
        self.is_toggle_on = False
        self.RECONNECT_TIMEOUT = 60  # 1 minute timeout for reconnection
        self.event_sent = False  # Track if event was sent and waiting for READY
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(20)  # Add more space between groups
        
        # Create IP configuration group
        config_group = QGroupBox("Backend Configuration")
        config_layout = QGridLayout()
        config_layout.setSpacing(10)  # Add space between elements
        
        # Create input fields for each backend
        self.ip_inputs = []
        
        for i, backend in enumerate(self.backends):
            # IP input
            ip_label = QLabel(f"{backend['name']} IP:")
            ip_label.setStyleSheet("font-size: 32px;")
            ip_input = QLineEdit(backend['host'])
            ip_input.setPlaceholderText("Enter IP address")
            ip_input.setStyleSheet("font-size: 32px; padding: 5px;")
            config_layout.addWidget(ip_label, i, 0)
            config_layout.addWidget(ip_input, i, 1)
            self.ip_inputs.append(ip_input)
            
            # Port labels (fixed ports)
            port_label = QLabel(f"Ports: {backend['ports'][0]}, {backend['ports'][1]}")
            port_label.setStyleSheet("font-size: 32px;")
            config_layout.addWidget(port_label, i, 2)
        
        # Add apply button
        self.apply_btn = QPushButton("Apply Configuration")
        self.apply_btn.setMinimumSize(200, 50)
        self.apply_btn.clicked.connect(self.apply_configuration)
        self.apply_btn.setStyleSheet("""
            QPushButton {
                font-size: 32px;
                font-weight: bold;
                padding: 5px;
                background-color: #008CBA;
                color: white;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #007399;
            }
        """)
        config_layout.addWidget(self.apply_btn, len(self.backends), 0, 1, 4)
        
        config_group.setLayout(config_layout)
        main_layout.addWidget(config_group)
        
        # Create control group
        control_group = QGroupBox("Control Panel")
        control_layout = QGridLayout()
        
        # Create status labels
        self.status_labels = []
        for i, backend in enumerate(self.backends):
            label = QLabel(f"{backend['name']}: Not Connected")
            label.setStyleSheet("color: red; font-size: 32px;")
            control_layout.addWidget(label, 0, i, alignment=Qt.AlignCenter)
            self.status_labels.append(label)
        
        # Create buttons with larger font
        self.toggle_btn = QPushButton("Start")
        self.toggle_btn.setMinimumSize(200, 50)
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                font-size: 32px;
                font-weight: bold;
                padding: 5px;
                background-color: #4CAF50;
                color: white;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.toggle_btn.clicked.connect(self.toggle_action)
        
        self.event_btn = QPushButton("Send Event")
        self.event_btn.setMinimumSize(200, 50)
        self.event_btn.setStyleSheet("""
            QPushButton {
                font-size: 32px;
                font-weight: bold;
                padding: 5px;
                background-color: #008CBA;
                color: white;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #007399;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.event_btn.clicked.connect(self.send_event)
        
        # Add buttons to layout
        control_layout.addWidget(self.toggle_btn, 1, 0, 1, 2, alignment=Qt.AlignCenter)
        control_layout.addWidget(self.event_btn, 2, 0, 1, 2, alignment=Qt.AlignCenter)
        
        control_group.setLayout(control_layout)
        main_layout.addWidget(control_group)
        
        # Set initial window size and position
        self.setMinimumSize(1200, 800)  # Increased window size to accommodate larger fonts
        self.resize(1200, 800)
        self.center_window()
        
        # Create timer for re-enabling event button
        self.timer = QTimer()
        self.timer.timeout.connect(self.enable_event_button)
        
        # Create timer for checking backend status
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.check_backend_status)
        self.status_timer.start(1000)  # Check every 1 second
        
        # Set window style
        self.setStyleSheet("""
            QGroupBox {
                font-size: 32px;
                font-weight: bold;
                margin-top: 1ex;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 3px;
            }
            QLineEdit {
                padding: 5px;
                border: 1px solid #999;
                border-radius: 3px;
            }
        """)
        
        self.event_btn.setEnabled(True)  # Enable event button in initial state
        
    def check_backend_status(self):
        # 첫 번째 포트(9090)만 사용하여 상태 및 READY 메시지 확인
        for i, backend in enumerate(self.backends):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.5)
                    s.connect((backend["host"], backend["ports"][0]))  # 첫 번째 포트만 사용
                    s.setblocking(False)
                    try:
                        message = s.recv(1024).decode()
                        if message == "READY":
                            backend["ready"] = True
                            if all(b["ready"] for b in self.backends) and self.event_sent:
                                self.event_btn.setEnabled(True)
                                self.event_sent = False
                    except:
                        pass
                    
                    # 연결 성공 시 상태 업데이트
                    self.status_labels[i].setText(f"{backend['name']}: Connected")
                    self.status_labels[i].setStyleSheet("color: green; font-size: 32px;")
            except Exception:
                # Connection failed
                if not backend["is_reconnecting"]:
                    backend["is_reconnecting"] = True
                    backend["reconnect_start"] = time.time()
                    self.status_labels[i].setText(f"{backend['name']}: Reconnecting...")
                    self.status_labels[i].setStyleSheet("color: orange; font-size: 32px;")
        
        # If any server is reconnecting during start stage, change to start state
        if any(backend["is_reconnecting"] for backend in self.backends) and self.is_toggle_on:
            self.toggle_btn.setText("Start")
            self.toggle_btn.setStyleSheet("""
                QPushButton {
                    font-size: 32px;
                    font-weight: bold;
                    padding: 5px;
                    background-color: #4CAF50;
                    color: white;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """)
            self.is_toggle_on = False
            self.event_btn.setEnabled(False)  # Enable event button when connection is lost
            # Send ERROR message to any connected backends
            self.send_tcp_message("ERROR")
            QMessageBox.warning(self, "Connection Lost", 
                "Connection lost to one or more backends.\nSystem reset to 'Start' state.")
        
    def apply_configuration(self):
        for i, backend in enumerate(self.backends):
            try:
                # Validate IP
                ip = self.ip_inputs[i].text().strip()
                if not ip:
                    raise ValueError(f"{backend['name']}: IP address cannot be empty")
                
                # Update backend configuration
                self.backends[i]['host'] = ip
                
            except ValueError as e:
                QMessageBox.warning(self, "Configuration Error", str(e))
                return
            
        QMessageBox.information(self, "Success", "Configuration applied successfully")
        
    def center_window(self):
        screen = QApplication.desktop().screenGeometry()
        size = self.geometry()
        self.move(
            (screen.width() - size.width()) // 2,
            (screen.height() - size.height()) // 2
        )
        
    def send_tcp_message(self, message):
        success = True
        failed_backends = []
        
        for i, backend in enumerate(self.backends):
            try:
                # 두 번째 포트(9091)로만 메시지 전송
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.5)
                s.connect((backend["host"], backend["ports"][1]))  # 두 번째 포트 사용
                s.sendall(message.encode())
                
                self.status_labels[i].setText(f"{backend['name']}: Connected")
                self.status_labels[i].setStyleSheet("color: green; font-size: 32px;")
            except Exception as e:
                success = False
                failed_backends.append(backend["name"])
                self.status_labels[i].setText(f"{backend['name']}: Not Connected")
                self.status_labels[i].setStyleSheet("color: red; font-size: 32px;")
        
        if not success:
            QMessageBox.warning(self, "Connection Warning", 
                              f"Failed to send message to: {', '.join(failed_backends)}")
        
        return success, failed_backends
    
    def toggle_action(self):
        if not self.is_toggle_on:  # Sending START
            success, failed_backends = self.send_tcp_message("START")
            if success:
                self.toggle_btn.setText("End")
                self.toggle_btn.setStyleSheet("""
                    QPushButton {
                        font-size: 32px;
                        font-weight: bold;
                        padding: 5px;
                        background-color: #ff9999;
                        color: white;
                        border-radius: 5px;
                    }
                    QPushButton:hover {
                        background-color: #ff8080;
                    }
                """)
                self.is_toggle_on = True
                self.event_btn.setEnabled(False)  # Disable event button after successful START
            else:
                # If START fails, notify other backend
                if len(failed_backends) < len(self.backends):
                    failure_message = f"CONNECTION_FAIL:{','.join(failed_backends)}"
                    self.send_tcp_message(failure_message)
                
                self.toggle_btn.setText("Start")
                self.toggle_btn.setStyleSheet("""
                    QPushButton {
                        font-size: 32px;
                        font-weight: bold;
                        padding: 5px;
                        background-color: #4CAF50;
                        color: white;
                        border-radius: 5px;
                    }
                    QPushButton:hover {
                        background-color: #45a049;
                    }
                """)
                self.is_toggle_on = False
                self.event_btn.setEnabled(True)  # Enable event button if START fails
        else:  # Sending END
            success, _ = self.send_tcp_message("END")
            if success:
                self.toggle_btn.setText("Start")
                self.toggle_btn.setStyleSheet("""
                    QPushButton {
                        font-size: 32px;
                        font-weight: bold;
                        padding: 5px;
                        background-color: #4CAF50;
                        color: white;
                        border-radius: 5px;
                    }
                    QPushButton:hover {
                        background-color: #45a049;
                    }
                """)
                self.is_toggle_on = False
                self.event_btn.setEnabled(True)  # Enable event button when END is sent
    
    def send_event(self):
        # Reset ready state for all backends
        for backend in self.backends:
            backend["ready"] = False
        
        success, _ = self.send_tcp_message("EVENT")
        if success:
            self.event_sent = True  # Mark that we're waiting for READY messages
            self.event_btn.setEnabled(False)  # Disable button while waiting for READY
            print("Event sent, waiting for READY messages from all backends")
    
    def enable_event_button(self):
        self.event_btn.setEnabled(True)
        self.timer.stop()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle('Fusion')
    
    window = ControlApp()
    window.show()
    sys.exit(app.exec_()) 