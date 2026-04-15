import sys
import numpy as np
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton
from PySide6.QtCore import QTimer
import pyqtgraph as pg

class RealTimePlot(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Knee Angle Monitor")
        self.setGeometry(100, 100, 800, 400)

        # Central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # PyQtGraph plot widget
        self.plot_widget = pg.PlotWidget()
        layout.addWidget(self.plot_widget)
        
        # QPushButton
        self.btn = QPushButton("Btn")
        self.btn_2 = QPushButton("Reset Plot")
        self.btn_2.clicked.connect(self.reset_plot)
        layout.addWidget(self.btn_2)
        self.btn.clicked.connect(self.change_plot)
        layout.addWidget(self.btn)

        # Data as numpy arrays
        self.max_points = 200  # visible window size
        self.x = np.array([], dtype=float)
        self.y = np.array([], dtype=float)
        self.y2 = np.array([], dtype=float)
        self.ptr = 0
        
        # Fxing ranges
        self.plot_widget.setXRange(0, self.max_points, padding=0)
        self.plot_widget.setYRange(0, 120, padding=0)
        
        # Disable mouse interaction
        #self.plot_widget.setMouseEnabled(x=False, y=False)
        
        # Set full widget background color
        self.plot_widget.setBackground("#21252d")

        # Customize axis and tick text colors
        axis_pen = pg.mkPen(color="#8a95aa")

        for axis in ('bottom', 'left'):
            ax = self.plot_widget.getAxis(axis)
            ax.setPen(axis_pen)
            ax.setTextPen(axis_pen)

        # Plot line
        pen = pg.mkPen(color='#f1fa8c', width=4)
        self.curve = self.plot_widget.plot(pen=pen)
        self.second_curve = self.plot_widget.plot(pen='r')
        
        self.second_curve_enabled = False

        # Timer for updates
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(50)  # update every 50 ms

    def update_plot(self):
        self.ptr += 1
        # Append new data using numpy
        self.x = np.append(self.x, self.ptr)
        new_value = np.sin(self.ptr * 0.1) * 30 + 60  # simulated knee angle
        self.y = np.append(self.y, new_value)
        
        if self.second_curve_enabled:
            new_cos = np.cos(self.ptr * 0.1) * 30 + 60
            self.y2 = np.append(self.y2, new_cos)
        else:
            self.y2 = np.append(self.y2, 0)

        if self.x.size > self.max_points:
            self.x = self.x[-self.max_points:]
            self.y = self.y[-self.max_points:]
            self.y2 = self.y2[-self.max_points:]
            
        self.curve.setData(self.x, self.y)
        self.second_curve.setData(self.x, self.y2)
        
        # Dynamic X range to follow data
        if self.ptr > self.max_points:
            self.plot_widget.setXRange(self.ptr - self.max_points, self.ptr, padding=0)
        else:
            self.plot_widget.setXRange(0, self.max_points, padding=0)
        
    def change_plot(self):
        self.second_curve_enabled = not self.second_curve_enabled
        
    def reset_plot(self):
        self.x = np.array([], dtype=float)
        self.y = np.array([], dtype=float)
        self.y2 = np.array([], dtype=float)
        self.ptr = 0
        self.curve.clear()
        self.second_curve.clear()
        self.plot_widget.setXRange(0, self.max_points, padding=0)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = RealTimePlot()
    win.show()
    sys.exit(app.exec())
