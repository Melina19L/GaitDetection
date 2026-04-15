# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'main_pagesQyHlSu.ui'
##
## Created by: Qt User Interface Compiler version 6.9.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QFormLayout, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QLayout, QSizePolicy,
    QStackedWidget, QVBoxLayout, QWidget)

class Ui_MainPages(object):
    def setupUi(self, MainPages):
        if not MainPages.objectName():
            MainPages.setObjectName(u"MainPages")
        MainPages.resize(781, 638)
        self.main_pages_layout = QVBoxLayout(MainPages)
        self.main_pages_layout.setSpacing(0)
        self.main_pages_layout.setObjectName(u"main_pages_layout")
        self.main_pages_layout.setContentsMargins(5, 5, 5, 5)
        self.pages = QStackedWidget(MainPages)
        self.pages.setObjectName(u"pages")
        self.page_01 = QWidget()
        self.page_01.setObjectName(u"page_01")
        self.page_01.setStyleSheet(u"QFrame {\n"
"	font-size: 16pt;\n"
"}")
        self.page_1_layout = QVBoxLayout(self.page_01)
        self.page_1_layout.setObjectName(u"page_1_layout")
        self.setup_title_widget = QWidget(self.page_01)
        self.setup_title_widget.setObjectName(u"setup_title_widget")
        self.setup_title_widget.setMaximumSize(QSize(16777215, 70))
        self.horizontalLayout = QHBoxLayout(self.setup_title_widget)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.title_label = QLabel(self.setup_title_widget)
        self.title_label.setObjectName(u"title_label")
        self.title_label.setMaximumSize(QSize(16777215, 70))
        self.title_label.setStyleSheet(u"font-size: 16pt")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.horizontalLayout.addWidget(self.title_label)

        self.time_label = QLabel(self.setup_title_widget)
        self.time_label.setObjectName(u"time_label")
        self.time_label.setEnabled(True)

        self.horizontalLayout.addWidget(self.time_label)


        self.page_1_layout.addWidget(self.setup_title_widget)

        self.stop_btn_widget = QWidget(self.page_01)
        self.stop_btn_widget.setObjectName(u"stop_btn_widget")
        self.stop_btn_widget.setEnabled(True)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.stop_btn_widget.sizePolicy().hasHeightForWidth())
        self.stop_btn_widget.setSizePolicy(sizePolicy)
        self.stop_layout = QHBoxLayout(self.stop_btn_widget)
        self.stop_layout.setObjectName(u"stop_layout")

        self.page_1_layout.addWidget(self.stop_btn_widget)

        self.selection_btn_widget = QWidget(self.page_01)
        self.selection_btn_widget.setObjectName(u"selection_btn_widget")
        self.selection_btn_widget.setAutoFillBackground(False)
        self.selection_btn_widget.setStyleSheet(u"")
        self.select_layout = QGridLayout(self.selection_btn_widget)
        self.select_layout.setObjectName(u"select_layout")
        self.select_layout.setContentsMargins(0, 0, 0, 0)

        self.page_1_layout.addWidget(self.selection_btn_widget)

        self.stimulator_frame = QFrame(self.page_01)
        self.stimulator_frame.setObjectName(u"stimulator_frame")
        self.stimulator_frame.setFrameShape(QFrame.Shape.Box)
        self.stimulator_layout = QGridLayout(self.stimulator_frame)
        self.stimulator_layout.setObjectName(u"stimulator_layout")
        self.serial_port_label = QLabel(self.stimulator_frame)
        self.serial_port_label.setObjectName(u"serial_port_label")

        self.stimulator_layout.addWidget(self.serial_port_label, 0, 0, 1, 1)

        self.baud_rate_label = QLabel(self.stimulator_frame)
        self.baud_rate_label.setObjectName(u"baud_rate_label")

        self.stimulator_layout.addWidget(self.baud_rate_label, 1, 0, 1, 1)


        self.page_1_layout.addWidget(self.stimulator_frame)

        self.start_btn_widget = QWidget(self.page_01)
        self.start_btn_widget.setObjectName(u"start_btn_widget")
        self.start_layout = QGridLayout(self.start_btn_widget)
        self.start_layout.setObjectName(u"start_layout")
        self.start_layout.setContentsMargins(0, 0, 0, 0)

        self.page_1_layout.addWidget(self.start_btn_widget)

        self.pages.addWidget(self.page_01)
        self.page_02 = QWidget()
        self.page_02.setObjectName(u"page_02")
        self.page_2_layout = QVBoxLayout(self.page_02)
        self.page_2_layout.setObjectName(u"page_2_layout")
        self.title_label_2 = QLabel(self.page_02)
        self.title_label_2.setObjectName(u"title_label_2")
        self.title_label_2.setMaximumSize(QSize(16777215, 70))
        font = QFont()
        font.setPointSize(16)
        self.title_label_2.setFont(font)
        self.title_label_2.setStyleSheet(u"font-size: 16pt")
        self.title_label_2.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.page_2_layout.addWidget(self.title_label_2)

        self.name_widget = QWidget(self.page_02)
        self.name_widget.setObjectName(u"name_widget")
        self.name_layout = QGridLayout(self.name_widget)
        self.name_layout.setSpacing(0)
        self.name_layout.setObjectName(u"name_layout")
        self.name_layout.setContentsMargins(0, 0, 0, 9)
        self.label_subj_id = QLabel(self.name_widget)
        self.label_subj_id.setObjectName(u"label_subj_id")
        self.label_subj_id.setMaximumSize(QSize(200, 16777215))
        self.label_subj_id.setStyleSheet(u"font-size: 14pt")
        self.label_subj_id.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.name_layout.addWidget(self.label_subj_id, 1, 2, 1, 1)

        self.label_fname = QLabel(self.name_widget)
        self.label_fname.setObjectName(u"label_fname")
        self.label_fname.setMaximumSize(QSize(200, 16777215))
        self.label_fname.setStyleSheet(u"font-size: 14pt")
        self.label_fname.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.name_layout.addWidget(self.label_fname, 1, 0, 1, 1)

        self.label_lname = QLabel(self.name_widget)
        self.label_lname.setObjectName(u"label_lname")
        self.label_lname.setMaximumSize(QSize(200, 16777215))
        self.label_lname.setStyleSheet(u"font-size: 14pt")
        self.label_lname.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.name_layout.addWidget(self.label_lname, 1, 1, 1, 1)


        self.page_2_layout.addWidget(self.name_widget)

        self.info_widget = QWidget(self.page_02)
        self.info_widget.setObjectName(u"info_widget")
        self.info_layout = QGridLayout(self.info_widget)
        self.info_layout.setSpacing(0)
        self.info_layout.setObjectName(u"info_layout")
        self.info_layout.setContentsMargins(0, 0, 0, 9)
        self.label_height = QLabel(self.info_widget)
        self.label_height.setObjectName(u"label_height")
        self.label_height.setMaximumSize(QSize(200, 16777215))
        self.label_height.setStyleSheet(u"font-size: 14pt")
        self.label_height.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.info_layout.addWidget(self.label_height, 0, 0, 1, 1)

        self.label_age = QLabel(self.info_widget)
        self.label_age.setObjectName(u"label_age")
        self.label_age.setMaximumSize(QSize(200, 16777215))
        self.label_age.setStyleSheet(u"font-size: 14pt")
        self.label_age.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.info_layout.addWidget(self.label_age, 0, 2, 1, 1)

        self.label_weight = QLabel(self.info_widget)
        self.label_weight.setObjectName(u"label_weight")
        self.label_weight.setMaximumSize(QSize(200, 16777215))
        self.label_weight.setStyleSheet(u"font-size: 14pt")
        self.label_weight.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.info_layout.addWidget(self.label_weight, 0, 1, 1, 1)


        self.page_2_layout.addWidget(self.info_widget)

        self.spaceholder_1 = QWidget(self.page_02)
        self.spaceholder_1.setObjectName(u"spaceholder_1")
        self.spaceholder_1.setMaximumSize(QSize(16777215, 80))

        self.page_2_layout.addWidget(self.spaceholder_1)

        self.finish_btn_widget = QWidget(self.page_02)
        self.finish_btn_widget.setObjectName(u"finish_btn_widget")
        self.finish_btn_widget.setMaximumSize(QSize(16777215, 80))
        self.finish_btn_layout = QHBoxLayout(self.finish_btn_widget)
        self.finish_btn_layout.setSpacing(0)
        self.finish_btn_layout.setObjectName(u"finish_btn_layout")
        self.finish_btn_layout.setContentsMargins(0, 0, 0, 0)

        self.page_2_layout.addWidget(self.finish_btn_widget)

        self.spaceholder_5 = QWidget(self.page_02)
        self.spaceholder_5.setObjectName(u"spaceholder_5")
        self.spaceholder_5.setMaximumSize(QSize(16777215, 40))

        self.page_2_layout.addWidget(self.spaceholder_5)

        self.pages.addWidget(self.page_02)
        self.page_04 = QWidget()
        self.page_04.setObjectName(u"page_04")
        self.page_4_layout = QVBoxLayout(self.page_04)
        self.page_4_layout.setObjectName(u"page_4_layout")
        self.title_label_4 = QLabel(self.page_04)
        self.title_label_4.setObjectName(u"title_label_4")
        self.title_label_4.setMaximumSize(QSize(16777215, 70))
        self.title_label_4.setStyleSheet(u"font-size: 16pt")
        self.title_label_4.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.page_4_layout.addWidget(self.title_label_4)

        self.dropdown_btn_widget = QWidget(self.page_04)
        self.dropdown_btn_widget.setObjectName(u"dropdown_btn_widget")
        self.dropdown_btn_widget.setMaximumSize(QSize(16777215, 70))
        self.dropdown_layout = QHBoxLayout(self.dropdown_btn_widget)
        self.dropdown_layout.setSpacing(0)
        self.dropdown_layout.setObjectName(u"dropdown_layout")
        self.dropdown_layout.setContentsMargins(0, 0, 0, 10)

        self.page_4_layout.addWidget(self.dropdown_btn_widget)

        self.custom_frame = QFrame(self.page_04)
        self.custom_frame.setObjectName(u"custom_frame")
        self.custom_frame.setMinimumSize(QSize(0, 120))
        self.custom_frame.setMaximumSize(QSize(16777215, 300))
        self.custom_frame.setStyleSheet(u"")
        self.custom_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.custom_frame.setFrameShadow(QFrame.Shadow.Raised)
        self.custom_option_layout = QVBoxLayout(self.custom_frame)
        self.custom_option_layout.setSpacing(15)
        self.custom_option_layout.setObjectName(u"custom_option_layout")
        self.custom_option_layout.setContentsMargins(0, 3, 0, -1)
        self.option_label = QLabel(self.custom_frame)
        self.option_label.setObjectName(u"option_label")
        self.option_label.setMinimumSize(QSize(0, 40))
        self.option_label.setMaximumSize(QSize(16777215, 80))
        self.option_label.setStyleSheet(u"font-size: 14pt")
        self.option_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.custom_option_layout.addWidget(self.option_label)

        self.custom_selection_widget = QWidget(self.custom_frame)
        self.custom_selection_widget.setObjectName(u"custom_selection_widget")
        self.custom_selection_widget.setMaximumSize(QSize(16777215, 16777215))
        self.custom_selection_widget.setStyleSheet(u"")
        self.custom_selection_layout = QHBoxLayout(self.custom_selection_widget)
        self.custom_selection_layout.setSpacing(0)
        self.custom_selection_layout.setObjectName(u"custom_selection_layout")
        self.custom_selection_layout.setContentsMargins(0, 0, 0, 0)

        self.custom_option_layout.addWidget(self.custom_selection_widget)

        self.custom_text_widget = QWidget(self.custom_frame)
        self.custom_text_widget.setObjectName(u"custom_text_widget")
        self.custom_text_widget.setMaximumSize(QSize(16777215, 16777215))
        self.custom_text_layout = QHBoxLayout(self.custom_text_widget)
        self.custom_text_layout.setSpacing(0)
        self.custom_text_layout.setObjectName(u"custom_text_layout")
        self.custom_text_layout.setContentsMargins(0, 0, 0, 0)

        self.custom_option_layout.addWidget(self.custom_text_widget)


        self.page_4_layout.addWidget(self.custom_frame)

        self.text_label = QLabel(self.page_04)
        self.text_label.setObjectName(u"text_label")
        self.text_label.setMaximumSize(QSize(16777215, 60))
        self.text_label.setStyleSheet(u"font-size: 14pt")
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignBottom|Qt.AlignmentFlag.AlignHCenter)

        self.page_4_layout.addWidget(self.text_label)

        self.text_widget = QWidget(self.page_04)
        self.text_widget.setObjectName(u"text_widget")
        self.text_widget.setMaximumSize(QSize(16777215, 90))
        self.file_name_layout = QHBoxLayout(self.text_widget)
        self.file_name_layout.setSpacing(0)
        self.file_name_layout.setObjectName(u"file_name_layout")
        self.file_name_layout.setContentsMargins(0, 0, 0, 0)

        self.page_4_layout.addWidget(self.text_widget)

        self.browse_widget = QWidget(self.page_04)
        self.browse_widget.setObjectName(u"browse_widget")
        self.browse_widget.setMaximumSize(QSize(16777215, 100))
        self.browse_layout = QGridLayout(self.browse_widget)
        self.browse_layout.setObjectName(u"browse_layout")
        self.browse_layout.setHorizontalSpacing(0)
        self.browse_layout.setVerticalSpacing(6)
        self.browse_layout.setContentsMargins(0, 0, 0, 0)

        self.page_4_layout.addWidget(self.browse_widget)

        self.finish_btn_widget_2 = QWidget(self.page_04)
        self.finish_btn_widget_2.setObjectName(u"finish_btn_widget_2")
        self.finish_btn_widget_2.setMaximumSize(QSize(16777215, 1677215))
        self.finish_btn_layout_2 = QHBoxLayout(self.finish_btn_widget_2)
        self.finish_btn_layout_2.setObjectName(u"finish_btn_layout_2")

        self.page_4_layout.addWidget(self.finish_btn_widget_2)

        self.pages.addWidget(self.page_04)
        self.page_03 = QWidget()
        self.page_03.setObjectName(u"page_03")
        self.page_3_layout = QVBoxLayout(self.page_03)
        self.page_3_layout.setObjectName(u"page_3_layout")
        self.title_label_3 = QLabel(self.page_03)
        self.title_label_3.setObjectName(u"title_label_3")
        self.title_label_3.setMaximumSize(QSize(16777215, 70))
        self.title_label_3.setStyleSheet(u"font-size:16pt")
        self.title_label_3.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.page_3_layout.addWidget(self.title_label_3)

        self.task_selection_widget = QWidget(self.page_03)
        self.task_selection_widget.setObjectName(u"task_selection_widget")
        self.task_selection_widget.setMaximumSize(QSize(16777215, 40))
        self.task_selection_layout = QHBoxLayout(self.task_selection_widget)
        self.task_selection_layout.setSpacing(0)
        self.task_selection_layout.setObjectName(u"task_selection_layout")
        self.task_selection_layout.setContentsMargins(0, 0, 0, 0)

        self.page_3_layout.addWidget(self.task_selection_widget)

        self.task_frame_widget = QWidget(self.page_03)
        self.task_frame_widget.setObjectName(u"task_frame_widget")
        self.task_frame_widget.setMaximumSize(QSize(16777215, 16777215))
        self.task_frame_layout = QGridLayout(self.task_frame_widget)
        self.task_frame_layout.setObjectName(u"task_frame_layout")
        self.task_frame_layout.setContentsMargins(9, 9, 9, 9)
        self.back_image_frame = QFrame(self.task_frame_widget)
        self.back_image_frame.setObjectName(u"back_image_frame")
        self.back_image_frame.setMaximumSize(QSize(250, 200))
        self.back_image_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.back_image_frame.setFrameShadow(QFrame.Shadow.Raised)
        self.back_image_layout = QVBoxLayout(self.back_image_frame)
        self.back_image_layout.setSpacing(9)
        self.back_image_layout.setObjectName(u"back_image_layout")

        self.task_frame_layout.addWidget(self.back_image_frame, 1, 0, 1, 1)

        self.task_option_frame = QFrame(self.task_frame_widget)
        self.task_option_frame.setObjectName(u"task_option_frame")
        self.task_option_frame.setEnabled(True)
        sizePolicy.setHeightForWidth(self.task_option_frame.sizePolicy().hasHeightForWidth())
        self.task_option_frame.setSizePolicy(sizePolicy)
        self.task_option_frame.setMinimumSize(QSize(200, 0))
        self.task_option_frame.setStyleSheet(u"")
        self.task_option_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.task_option_frame.setFrameShadow(QFrame.Shadow.Raised)
        self.task_option_layout = QVBoxLayout(self.task_option_frame)
        self.task_option_layout.setSpacing(5)
        self.task_option_layout.setObjectName(u"task_option_layout")
        self.task_option_layout.setContentsMargins(9, 6, 6, 6)
        self.gait_detection_frame = QFrame(self.task_option_frame)
        self.gait_detection_frame.setObjectName(u"gait_detection_frame")
        self.gait_detection_frame.setEnabled(True)
        sizePolicy.setHeightForWidth(self.gait_detection_frame.sizePolicy().hasHeightForWidth())
        self.gait_detection_frame.setSizePolicy(sizePolicy)
        self.gait_detection_frame.setStyleSheet(u"")
        self.gait_detection_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.gait_detection_frame.setFrameShadow(QFrame.Shadow.Raised)
        self.gait_detection_layout = QVBoxLayout(self.gait_detection_frame)
        self.gait_detection_layout.setSpacing(5)
        self.gait_detection_layout.setObjectName(u"gait_detection_layout")
        self.gait_detection_layout.setContentsMargins(9, 6, 6, 6)
        self.imu_frame = QFrame(self.gait_detection_frame)
        self.imu_frame.setObjectName(u"imu_frame")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.imu_frame.sizePolicy().hasHeightForWidth())
        self.imu_frame.setSizePolicy(sizePolicy1)
        self.imu_frame.setMaximumSize(QSize(16777215, 16777215))
        self.imu_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.imu_frame.setFrameShadow(QFrame.Shadow.Raised)
        self.imu_layout = QVBoxLayout(self.imu_frame)
        self.imu_layout.setSpacing(5)
        self.imu_layout.setObjectName(u"imu_layout")
        self.imu_layout.setContentsMargins(9, 6, 6, 6)
        self.nb_imu_widget = QWidget(self.imu_frame)
        self.nb_imu_widget.setObjectName(u"nb_imu_widget")
        sizePolicy1.setHeightForWidth(self.nb_imu_widget.sizePolicy().hasHeightForWidth())
        self.nb_imu_widget.setSizePolicy(sizePolicy1)
        self.nb_imu_layout = QHBoxLayout(self.nb_imu_widget)
        self.nb_imu_layout.setSpacing(0)
        self.nb_imu_layout.setObjectName(u"nb_imu_layout")
        self.nb_imu_layout.setContentsMargins(0, 0, 0, 0)

        self.imu_layout.addWidget(self.nb_imu_widget)


        self.gait_detection_layout.addWidget(self.imu_frame)

        self.phase_detection_frame = QFrame(self.gait_detection_frame)
        self.phase_detection_frame.setObjectName(u"phase_detection_frame")
        sizePolicy1.setHeightForWidth(self.phase_detection_frame.sizePolicy().hasHeightForWidth())
        self.phase_detection_frame.setSizePolicy(sizePolicy1)
        self.phase_detection_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.phase_detection_layout = QVBoxLayout(self.phase_detection_frame)
        self.phase_detection_layout.setSpacing(5)
        self.phase_detection_layout.setObjectName(u"phase_detection_layout")
        self.phase_detection_layout.setContentsMargins(9, 6, 6, 6)

        self.gait_detection_layout.addWidget(self.phase_detection_frame)


        self.task_option_layout.addWidget(self.gait_detection_frame)


        self.task_frame_layout.addWidget(self.task_option_frame, 0, 0, 1, 1)

        self.para_image_widget = QWidget(self.task_frame_widget)
        self.para_image_widget.setObjectName(u"para_image_widget")
        self.para_image_widget.setMaximumSize(QSize(1000, 16777215))
        self.para_image_layout = QVBoxLayout(self.para_image_widget)
        self.para_image_layout.setSpacing(0)
        self.para_image_layout.setObjectName(u"para_image_layout")
        self.para_image_layout.setContentsMargins(0, 0, 0, 0)

        self.task_frame_layout.addWidget(self.para_image_widget, 0, 1, 1, 1)

        self.stim_para_frame = QFrame(self.task_frame_widget)
        self.stim_para_frame.setObjectName(u"stim_para_frame")
        self.stim_para_frame.setMaximumSize(QSize(16777215, 200))
        self.stim_para_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.stim_para_frame.setFrameShadow(QFrame.Shadow.Raised)
        self.stim_para_layout = QGridLayout(self.stim_para_frame)
        self.stim_para_layout.setObjectName(u"stim_para_layout")
        self.stim_para_layout.setHorizontalSpacing(9)
        self.stim_para_layout.setVerticalSpacing(6)
        self.burst_duration_label = QLabel(self.stim_para_frame)
        self.burst_duration_label.setObjectName(u"burst_duration_label")

        self.stim_para_layout.addWidget(self.burst_duration_label, 1, 0, 1, 1)

        self.burst_period_value_label = QLabel(self.stim_para_frame)
        self.burst_period_value_label.setObjectName(u"burst_period_value_label")

        self.stim_para_layout.addWidget(self.burst_period_value_label, 0, 3, 1, 1)

        self.burst_frequency_label = QLabel(self.stim_para_frame)
        self.burst_frequency_label.setObjectName(u"burst_frequency_label")

        self.stim_para_layout.addWidget(self.burst_frequency_label, 0, 0, 1, 1)

        self.pulse_width_value_label = QLabel(self.stim_para_frame)
        self.pulse_width_value_label.setObjectName(u"pulse_width_value_label")

        self.stim_para_layout.addWidget(self.pulse_width_value_label, 3, 3, 1, 1)

        self.pulse_period_value_label = QLabel(self.stim_para_frame)
        self.pulse_period_value_label.setObjectName(u"pulse_period_value_label")

        self.stim_para_layout.addWidget(self.pulse_period_value_label, 2, 3, 1, 1)

        self.nb_pulses_value_label = QLabel(self.stim_para_frame)
        self.nb_pulses_value_label.setObjectName(u"nb_pulses_value_label")

        self.stim_para_layout.addWidget(self.nb_pulses_value_label, 4, 3, 1, 1)

        self.burst_period_label = QLabel(self.stim_para_frame)
        self.burst_period_label.setObjectName(u"burst_period_label")

        self.stim_para_layout.addWidget(self.burst_period_label, 0, 2, 1, 1)

        self.carrier_frequency_label = QLabel(self.stim_para_frame)
        self.carrier_frequency_label.setObjectName(u"carrier_frequency_label")

        self.stim_para_layout.addWidget(self.carrier_frequency_label, 2, 0, 1, 1)

        self.pulse_deadtime_label = QLabel(self.stim_para_frame)
        self.pulse_deadtime_label.setObjectName(u"pulse_deadtime_label")

        self.stim_para_layout.addWidget(self.pulse_deadtime_label, 3, 0, 1, 1)

        self.interpulse_interval_label = QLabel(self.stim_para_frame)
        self.interpulse_interval_label.setObjectName(u"interpulse_interval_label")

        self.stim_para_layout.addWidget(self.interpulse_interval_label, 4, 0, 1, 1)

        self.pulse_period_label = QLabel(self.stim_para_frame)
        self.pulse_period_label.setObjectName(u"pulse_period_label")

        self.stim_para_layout.addWidget(self.pulse_period_label, 2, 2, 1, 1)

        self.pulse_width_label = QLabel(self.stim_para_frame)
        self.pulse_width_label.setObjectName(u"pulse_width_label")

        self.stim_para_layout.addWidget(self.pulse_width_label, 3, 2, 1, 1)

        self.nb_pulses_label = QLabel(self.stim_para_frame)
        self.nb_pulses_label.setObjectName(u"nb_pulses_label")

        self.stim_para_layout.addWidget(self.nb_pulses_label, 4, 2, 1, 1)


        self.task_frame_layout.addWidget(self.stim_para_frame, 1, 1, 1, 1)


        self.page_3_layout.addWidget(self.task_frame_widget)

        self.pages.addWidget(self.page_03)
        self.page_05 = QWidget()
        self.page_05.setObjectName(u"page_05")
        self.page_5_layout = QVBoxLayout(self.page_05)
        self.page_5_layout.setObjectName(u"page_5_layout")
        self.title_label_5 = QLabel(self.page_05)
        self.title_label_5.setObjectName(u"title_label_5")
        self.title_label_5.setMaximumSize(QSize(16777215, 70))
        self.title_label_5.setStyleSheet(u"font-size: 16pt")
        self.title_label_5.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.page_5_layout.addWidget(self.title_label_5)

        self.channel_grid_widget = QWidget(self.page_05)
        self.channel_grid_widget.setObjectName(u"channel_grid_widget")
        sizePolicy.setHeightForWidth(self.channel_grid_widget.sizePolicy().hasHeightForWidth())
        self.channel_grid_widget.setSizePolicy(sizePolicy)
        self.channel_grid_widget.setMinimumSize(QSize(0, 160))
        self.channel_grid_widget.setMaximumSize(QSize(16777215, 16777215))
        self.channgel_grid_layout = QGridLayout(self.channel_grid_widget)
        self.channgel_grid_layout.setObjectName(u"channgel_grid_layout")
        self.channgel_grid_layout.setHorizontalSpacing(10)
        self.channel_widget_0 = QWidget(self.channel_grid_widget)
        self.channel_widget_0.setObjectName(u"channel_widget_0")
        self.channel_layout_0 = QVBoxLayout(self.channel_widget_0)
        self.channel_layout_0.setSpacing(9)
        self.channel_layout_0.setObjectName(u"channel_layout_0")
        self.channel_layout_0.setContentsMargins(5, 0, 5, 9)
        self.channel_label = QLabel(self.channel_widget_0)
        self.channel_label.setObjectName(u"channel_label")
        self.channel_label.setStyleSheet(u"font-size: 12pt")
        self.channel_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.channel_label.setWordWrap(False)

        self.channel_layout_0.addWidget(self.channel_label)


        self.channgel_grid_layout.addWidget(self.channel_widget_0, 0, 0, 1, 1)

        self.channel_widget_1 = QWidget(self.channel_grid_widget)
        self.channel_widget_1.setObjectName(u"channel_widget_1")
        self.channel_layout_1 = QVBoxLayout(self.channel_widget_1)
        self.channel_layout_1.setSpacing(9)
        self.channel_layout_1.setObjectName(u"channel_layout_1")
        self.channel_layout_1.setContentsMargins(5, 0, 5, 9)
        self.channel_label_1 = QLabel(self.channel_widget_1)
        self.channel_label_1.setObjectName(u"channel_label_1")
        self.channel_label_1.setStyleSheet(u"font-size: 12pt")
        self.channel_label_1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.channel_label_1.setWordWrap(False)

        self.channel_layout_1.addWidget(self.channel_label_1)


        self.channgel_grid_layout.addWidget(self.channel_widget_1, 0, 1, 1, 1)

        self.channel_widget_2 = QWidget(self.channel_grid_widget)
        self.channel_widget_2.setObjectName(u"channel_widget_2")
        self.channel_layout_2 = QVBoxLayout(self.channel_widget_2)
        self.channel_layout_2.setSpacing(9)
        self.channel_layout_2.setObjectName(u"channel_layout_2")
        self.channel_layout_2.setContentsMargins(5, 0, 5, 9)
        self.channel_label_2 = QLabel(self.channel_widget_2)
        self.channel_label_2.setObjectName(u"channel_label_2")
        self.channel_label_2.setStyleSheet(u"font-size: 12pt")
        self.channel_label_2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.channel_label_2.setWordWrap(True)

        self.channel_layout_2.addWidget(self.channel_label_2)


        self.channgel_grid_layout.addWidget(self.channel_widget_2, 0, 2, 1, 1)

        self.channel_widget_3 = QWidget(self.channel_grid_widget)
        self.channel_widget_3.setObjectName(u"channel_widget_3")
        self.channel_layout_3 = QVBoxLayout(self.channel_widget_3)
        self.channel_layout_3.setSpacing(9)
        self.channel_layout_3.setObjectName(u"channel_layout_3")
        self.channel_layout_3.setContentsMargins(5, 0, 5, 9)
        self.channel_label_3 = QLabel(self.channel_widget_3)
        self.channel_label_3.setObjectName(u"channel_label_3")
        self.channel_label_3.setStyleSheet(u"font-size: 12pt")
        self.channel_label_3.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.channel_layout_3.addWidget(self.channel_label_3)


        self.channgel_grid_layout.addWidget(self.channel_widget_3, 0, 3, 1, 1)

        self.channel_widget_4 = QWidget(self.channel_grid_widget)
        self.channel_widget_4.setObjectName(u"channel_widget_4")
        self.channel_layout_4 = QVBoxLayout(self.channel_widget_4)
        self.channel_layout_4.setSpacing(9)
        self.channel_layout_4.setObjectName(u"channel_layout_4")
        self.channel_layout_4.setContentsMargins(5, 0, 5, 9)
        self.channel_label_4 = QLabel(self.channel_widget_4)
        self.channel_label_4.setObjectName(u"channel_label_4")
        self.channel_label_4.setStyleSheet(u"font-size: 12pt")
        self.channel_label_4.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.channel_layout_4.addWidget(self.channel_label_4)


        self.channgel_grid_layout.addWidget(self.channel_widget_4, 1, 0, 1, 1)

        self.channel_widget_5 = QWidget(self.channel_grid_widget)
        self.channel_widget_5.setObjectName(u"channel_widget_5")
        self.channel_layout_5 = QVBoxLayout(self.channel_widget_5)
        self.channel_layout_5.setSpacing(9)
        self.channel_layout_5.setObjectName(u"channel_layout_5")
        self.channel_layout_5.setContentsMargins(5, 0, 5, 9)
        self.channel_label_5 = QLabel(self.channel_widget_5)
        self.channel_label_5.setObjectName(u"channel_label_5")
        self.channel_label_5.setStyleSheet(u"font-size: 12pt")
        self.channel_label_5.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.channel_layout_5.addWidget(self.channel_label_5)


        self.channgel_grid_layout.addWidget(self.channel_widget_5, 1, 1, 1, 1)

        self.channel_widget_6 = QWidget(self.channel_grid_widget)
        self.channel_widget_6.setObjectName(u"channel_widget_6")
        self.channel_layout_6 = QVBoxLayout(self.channel_widget_6)
        self.channel_layout_6.setSpacing(9)
        self.channel_layout_6.setObjectName(u"channel_layout_6")
        self.channel_layout_6.setContentsMargins(5, 0, 5, 9)
        self.channel_label_6 = QLabel(self.channel_widget_6)
        self.channel_label_6.setObjectName(u"channel_label_6")
        self.channel_label_6.setStyleSheet(u"font-size: 12pt")
        self.channel_label_6.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.channel_layout_6.addWidget(self.channel_label_6)


        self.channgel_grid_layout.addWidget(self.channel_widget_6, 1, 2, 1, 1)

        self.channel_widget_7 = QWidget(self.channel_grid_widget)
        self.channel_widget_7.setObjectName(u"channel_widget_7")
        self.channel_layout_7 = QVBoxLayout(self.channel_widget_7)
        self.channel_layout_7.setSpacing(9)
        self.channel_layout_7.setObjectName(u"channel_layout_7")
        self.channel_layout_7.setContentsMargins(5, 0, 5, 9)
        self.channel_label_7 = QLabel(self.channel_widget_7)
        self.channel_label_7.setObjectName(u"channel_label_7")
        self.channel_label_7.setStyleSheet(u"font-size: 12pt")
        self.channel_label_7.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.channel_layout_7.addWidget(self.channel_label_7)


        self.channgel_grid_layout.addWidget(self.channel_widget_7, 1, 3, 1, 1)


        self.page_5_layout.addWidget(self.channel_grid_widget)

        self.image_frame = QFrame(self.page_05)
        self.image_frame.setObjectName(u"image_frame")
        self.image_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.view_layout = QGridLayout(self.image_frame)
        self.view_layout.setObjectName(u"view_layout")
        self.selected_task_widget = QWidget(self.image_frame)
        self.selected_task_widget.setObjectName(u"selected_task_widget")
        self.selected_task_widget.setMaximumSize(QSize(16777215, 16777215))
        self.selected_task_layout = QHBoxLayout(self.selected_task_widget)
        self.selected_task_layout.setSpacing(0)
        self.selected_task_layout.setObjectName(u"selected_task_layout")
        self.selected_task_layout.setContentsMargins(0, 0, 0, 0)

        self.view_layout.addWidget(self.selected_task_widget, 0, 1, 1, 1)

        self.image_widget = QWidget(self.image_frame)
        self.image_widget.setObjectName(u"image_widget")
        self.image_layout = QVBoxLayout(self.image_widget)
        self.image_layout.setObjectName(u"image_layout")

        self.view_layout.addWidget(self.image_widget, 1, 1, 1, 1)

        self.channel_assign_widget = QWidget(self.image_frame)
        self.channel_assign_widget.setObjectName(u"channel_assign_widget")
        self.channel_assign_layout = QGridLayout(self.channel_assign_widget)
        self.channel_assign_layout.setObjectName(u"channel_assign_layout")
        self.channel_assign_layout.setSizeConstraint(QLayout.SizeConstraint.SetDefaultConstraint)
        self.channel_assign_layout.setContentsMargins(-1, -1, -1, 9)
        self.channel_assignment_label = QLabel(self.channel_assign_widget)
        self.channel_assignment_label.setObjectName(u"channel_assignment_label")
        self.channel_assignment_label.setMaximumSize(QSize(16777215, 50))
        self.channel_assignment_label.setStyleSheet(u"font-size: 11pt")
        self.channel_assignment_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.channel_assign_layout.addWidget(self.channel_assignment_label, 0, 0, 1, 2)


        self.view_layout.addWidget(self.channel_assign_widget, 0, 0, 2, 1)

        self.target_assign_widget = QWidget(self.image_frame)
        self.target_assign_widget.setObjectName(u"target_assign_widget")
        self.target_assign_layout = QGridLayout(self.target_assign_widget)
        self.target_assign_layout.setObjectName(u"target_assign_layout")
        self.left_dist_label = QLabel(self.target_assign_widget)
        self.left_dist_label.setObjectName(u"left_dist_label")

        self.target_assign_layout.addWidget(self.left_dist_label, 5, 0, 1, 1)

        self.right_leg_label = QLabel(self.target_assign_widget)
        self.right_leg_label.setObjectName(u"right_leg_label")

        self.target_assign_layout.addWidget(self.right_leg_label, 2, 0, 1, 1)

        self.target_assignment_label = QLabel(self.target_assign_widget)
        self.target_assignment_label.setObjectName(u"target_assignment_label")
        self.target_assignment_label.setMaximumSize(QSize(16777215, 50))
        self.target_assignment_label.setStyleSheet(u"font-size: 12pt")
        self.target_assignment_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.target_assign_layout.addWidget(self.target_assignment_label, 0, 0, 1, 2)

        self.right_dist_label = QLabel(self.target_assign_widget)
        self.right_dist_label.setObjectName(u"right_dist_label")

        self.target_assign_layout.addWidget(self.right_dist_label, 6, 0, 1, 1)

        self.left_prox_label = QLabel(self.target_assign_widget)
        self.left_prox_label.setObjectName(u"left_prox_label")

        self.target_assign_layout.addWidget(self.left_prox_label, 3, 0, 1, 1)

        self.right_prox_label = QLabel(self.target_assign_widget)
        self.right_prox_label.setObjectName(u"right_prox_label")

        self.target_assign_layout.addWidget(self.right_prox_label, 4, 0, 1, 1)

        self.left_leg_label = QLabel(self.target_assign_widget)
        self.left_leg_label.setObjectName(u"left_leg_label")

        self.target_assign_layout.addWidget(self.left_leg_label, 1, 0, 1, 1)

        self.label = QLabel(self.target_assign_widget)
        self.label.setObjectName(u"label")

        self.target_assign_layout.addWidget(self.label, 7, 0, 1, 1)


        self.view_layout.addWidget(self.target_assign_widget, 0, 2, 2, 1)


        self.page_5_layout.addWidget(self.image_frame)

        self.finish_btn_widget_4 = QWidget(self.page_05)
        self.finish_btn_widget_4.setObjectName(u"finish_btn_widget_4")
        self.finish_btn_widget_4.setMaximumSize(QSize(16777215, 80))
        self.finish_btn_layout_4 = QHBoxLayout(self.finish_btn_widget_4)
        self.finish_btn_layout_4.setSpacing(0)
        self.finish_btn_layout_4.setObjectName(u"finish_btn_layout_4")
        self.finish_btn_layout_4.setContentsMargins(0, 0, 0, 0)

        self.page_5_layout.addWidget(self.finish_btn_widget_4)

        self.pages.addWidget(self.page_05)
        self.page_06 = QWidget()
        self.page_06.setObjectName(u"page_06")
        self.verticalLayout = QVBoxLayout(self.page_06)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.title_label_6 = QLabel(self.page_06)
        self.title_label_6.setObjectName(u"title_label_6")
        self.title_label_6.setMinimumSize(QSize(0, 40))
        self.title_label_6.setMaximumSize(QSize(16777215, 70))
        self.title_label_6.setStyleSheet(u"font-size:16pt;")
        self.title_label_6.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.verticalLayout.addWidget(self.title_label_6)

        self.subject_frame = QFrame(self.page_06)
        self.subject_frame.setObjectName(u"subject_frame")
        self.subject_frame.setMaximumSize(QSize(16777215, 120))
        self.subject_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.subject_frame.setFrameShadow(QFrame.Shadow.Raised)
        self.subject_layout = QGridLayout(self.subject_frame)
        self.subject_layout.setObjectName(u"subject_layout")
        self.info_label_6 = QLabel(self.subject_frame)
        self.info_label_6.setObjectName(u"info_label_6")
        self.info_label_6.setMaximumSize(QSize(16777215, 40))
        self.info_label_6.setStyleSheet(u"font-size:12pt")
        self.info_label_6.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.subject_layout.addWidget(self.info_label_6, 0, 5, 1, 1)

        self.info_label_4 = QLabel(self.subject_frame)
        self.info_label_4.setObjectName(u"info_label_4")
        self.info_label_4.setMaximumSize(QSize(16777215, 40))
        self.info_label_4.setStyleSheet(u"font-size:12pt")
        self.info_label_4.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.subject_layout.addWidget(self.info_label_4, 0, 3, 1, 1)

        self.info_label = QLabel(self.subject_frame)
        self.info_label.setObjectName(u"info_label")
        self.info_label.setMaximumSize(QSize(16777215, 40))
        self.info_label.setStyleSheet(u"font-size:12pt")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.subject_layout.addWidget(self.info_label, 0, 0, 1, 1)

        self.info_label_2 = QLabel(self.subject_frame)
        self.info_label_2.setObjectName(u"info_label_2")
        self.info_label_2.setMaximumSize(QSize(16777215, 40))
        self.info_label_2.setStyleSheet(u"font-size:12pt")
        self.info_label_2.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.subject_layout.addWidget(self.info_label_2, 0, 1, 1, 1)

        self.info_label_5 = QLabel(self.subject_frame)
        self.info_label_5.setObjectName(u"info_label_5")
        self.info_label_5.setMaximumSize(QSize(16777215, 40))
        self.info_label_5.setStyleSheet(u"font-size:12pt")
        self.info_label_5.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.subject_layout.addWidget(self.info_label_5, 0, 4, 1, 1)

        self.info_label_3 = QLabel(self.subject_frame)
        self.info_label_3.setObjectName(u"info_label_3")
        self.info_label_3.setMaximumSize(QSize(16777215, 40))
        self.info_label_3.setStyleSheet(u"font-size:12pt")
        self.info_label_3.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.subject_layout.addWidget(self.info_label_3, 0, 2, 1, 1)


        self.verticalLayout.addWidget(self.subject_frame)

        self.task_save_widget = QWidget(self.page_06)
        self.task_save_widget.setObjectName(u"task_save_widget")
        self.task_save_widget.setMaximumSize(QSize(16777215, 100))
        self.task_save_layout = QHBoxLayout(self.task_save_widget)
        self.task_save_layout.setSpacing(6)
        self.task_save_layout.setObjectName(u"task_save_layout")
        self.task_save_layout.setContentsMargins(0, 0, 0, 0)
        self.task_frame = QFrame(self.task_save_widget)
        self.task_frame.setObjectName(u"task_frame")
        self.task_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.task_frame.setFrameShadow(QFrame.Shadow.Raised)
        self.task_info_layout = QVBoxLayout(self.task_frame)
        self.task_info_layout.setObjectName(u"task_info_layout")
        self.info_label_7 = QLabel(self.task_frame)
        self.info_label_7.setObjectName(u"info_label_7")
        self.info_label_7.setStyleSheet(u"font-size:12pt")
        self.info_label_7.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.task_info_layout.addWidget(self.info_label_7)


        self.task_save_layout.addWidget(self.task_frame)

        self.save_frame = QFrame(self.task_save_widget)
        self.save_frame.setObjectName(u"save_frame")
        self.save_frame.setMinimumSize(QSize(500, 0))
        self.save_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.save_frame.setFrameShadow(QFrame.Shadow.Raised)
        self.save_layout = QVBoxLayout(self.save_frame)
        self.save_layout.setObjectName(u"save_layout")
        self.info_label_8 = QLabel(self.save_frame)
        self.info_label_8.setObjectName(u"info_label_8")
        self.info_label_8.setStyleSheet(u"font-size:12pt")
        self.info_label_8.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.save_layout.addWidget(self.info_label_8)


        self.task_save_layout.addWidget(self.save_frame)


        self.verticalLayout.addWidget(self.task_save_widget)

        self.stimulation_frame = QFrame(self.page_06)
        self.stimulation_frame.setObjectName(u"stimulation_frame")
        self.stimulation_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.stimulation_frame.setFrameShadow(QFrame.Shadow.Raised)
        self.stimuation_layout = QHBoxLayout(self.stimulation_frame)
        self.stimuation_layout.setObjectName(u"stimuation_layout")
        self.confirm_widget = QWidget(self.stimulation_frame)
        self.confirm_widget.setObjectName(u"confirm_widget")
        self.confirm_layout = QVBoxLayout(self.confirm_widget)
        self.confirm_layout.setObjectName(u"confirm_layout")
        self.channel_widget = QWidget(self.confirm_widget)
        self.channel_widget.setObjectName(u"channel_widget")
        self.channel_widget.setMinimumSize(QSize(300, 0))
        self.channel_layout = QFormLayout(self.channel_widget)
        self.channel_layout.setObjectName(u"channel_layout")
        self.info_label_9 = QLabel(self.channel_widget)
        self.info_label_9.setObjectName(u"info_label_9")
        self.info_label_9.setStyleSheet(u"font-size:12pt")

        self.channel_layout.setWidget(0, QFormLayout.ItemRole.LabelRole, self.info_label_9)

        self.info_label_10 = QLabel(self.channel_widget)
        self.info_label_10.setObjectName(u"info_label_10")
        self.info_label_10.setStyleSheet(u"font-size:12pt")

        self.channel_layout.setWidget(1, QFormLayout.ItemRole.LabelRole, self.info_label_10)

        self.info_label_11 = QLabel(self.channel_widget)
        self.info_label_11.setObjectName(u"info_label_11")
        self.info_label_11.setStyleSheet(u"font-size:12pt")

        self.channel_layout.setWidget(2, QFormLayout.ItemRole.LabelRole, self.info_label_11)

        self.info_label_12 = QLabel(self.channel_widget)
        self.info_label_12.setObjectName(u"info_label_12")
        self.info_label_12.setStyleSheet(u"font-size:12pt")

        self.channel_layout.setWidget(3, QFormLayout.ItemRole.LabelRole, self.info_label_12)

        self.info_label_13 = QLabel(self.channel_widget)
        self.info_label_13.setObjectName(u"info_label_13")
        self.info_label_13.setStyleSheet(u"font-size:12pt")

        self.channel_layout.setWidget(4, QFormLayout.ItemRole.LabelRole, self.info_label_13)

        self.info_label_14 = QLabel(self.channel_widget)
        self.info_label_14.setObjectName(u"info_label_14")
        self.info_label_14.setStyleSheet(u"font-size:12pt")

        self.channel_layout.setWidget(5, QFormLayout.ItemRole.LabelRole, self.info_label_14)

        self.info_label_15 = QLabel(self.channel_widget)
        self.info_label_15.setObjectName(u"info_label_15")
        self.info_label_15.setStyleSheet(u"font-size:12pt")

        self.channel_layout.setWidget(6, QFormLayout.ItemRole.LabelRole, self.info_label_15)

        self.info_label_16 = QLabel(self.channel_widget)
        self.info_label_16.setObjectName(u"info_label_16")
        self.info_label_16.setStyleSheet(u"font-size:12pt")

        self.channel_layout.setWidget(7, QFormLayout.ItemRole.LabelRole, self.info_label_16)


        self.confirm_layout.addWidget(self.channel_widget)

        self.confirm_cancel_widget = QWidget(self.confirm_widget)
        self.confirm_cancel_widget.setObjectName(u"confirm_cancel_widget")
        self.confirm_cancel_layout = QHBoxLayout(self.confirm_cancel_widget)
        self.confirm_cancel_layout.setObjectName(u"confirm_cancel_layout")

        self.confirm_layout.addWidget(self.confirm_cancel_widget)


        self.stimuation_layout.addWidget(self.confirm_widget)

        self.image_widget_2 = QWidget(self.stimulation_frame)
        self.image_widget_2.setObjectName(u"image_widget_2")
        self.image_info_layout = QHBoxLayout(self.image_widget_2)
        self.image_info_layout.setObjectName(u"image_info_layout")

        self.stimuation_layout.addWidget(self.image_widget_2)


        self.verticalLayout.addWidget(self.stimulation_frame)

        self.pages.addWidget(self.page_06)
        self.page_07 = QWidget()
        self.page_07.setObjectName(u"page_07")
        self.gridLayout = QGridLayout(self.page_07)
        self.gridLayout.setObjectName(u"gridLayout")
        self.finish_btn_widget_5 = QWidget(self.page_07)
        self.finish_btn_widget_5.setObjectName(u"finish_btn_widget_5")
        self.finish_btn_widget_5.setMaximumSize(QSize(16777215, 80))
        self.finish_btn_layout_5 = QHBoxLayout(self.finish_btn_widget_5)
        self.finish_btn_layout_5.setSpacing(0)
        self.finish_btn_layout_5.setObjectName(u"finish_btn_layout_5")
        self.finish_btn_layout_5.setContentsMargins(0, 0, 0, 0)

        self.gridLayout.addWidget(self.finish_btn_widget_5, 2, 0, 1, 2)

        self.title_label_7 = QLabel(self.page_07)
        self.title_label_7.setObjectName(u"title_label_7")
        self.title_label_7.setMaximumSize(QSize(16777215, 80))
        self.title_label_7.setStyleSheet(u"font-size:16pt")
        self.title_label_7.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gridLayout.addWidget(self.title_label_7, 0, 0, 1, 2)

        self.left_leg_frame = QFrame(self.page_07)
        self.left_leg_frame.setObjectName(u"left_leg_frame")
        self.left_leg_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.left_leg_frame.setFrameShadow(QFrame.Shadow.Raised)
        self.left_leg_layout = QVBoxLayout(self.left_leg_frame)
        self.left_leg_layout.setSpacing(0)
        self.left_leg_layout.setObjectName(u"left_leg_layout")
        self.left_leg_layout.setContentsMargins(9, 0, 0, 0)
        self.count_label_2 = QLabel(self.left_leg_frame)
        self.count_label_2.setObjectName(u"count_label_2")
        self.count_label_2.setMaximumSize(QSize(16777215, 60))
        self.count_label_2.setStyleSheet(u"font-size:14pt")
        
        # phase display above the step counter (left)
        self.phase_left_value_label = QLabel(self.left_leg_frame)
        self.phase_left_value_label.setObjectName(u"phase_left_value_label")
        self.phase_left_value_label.setMaximumSize(QSize(16777215, 30))
        self.phase_left_value_label.setStyleSheet(u"font-size:12pt; font-weight:600;")
        self.phase_left_value_label.setText("Phase: Unknown")
        self.left_leg_layout.addWidget(self.phase_left_value_label)


        self.left_leg_layout.addWidget(self.count_label_2)

        self.phase_left_widget = QWidget(self.left_leg_frame)
        self.phase_left_widget.setObjectName(u"phase_left_widget")
        self.phase_left_layout = QVBoxLayout(self.phase_left_widget)
        self.phase_left_layout.setObjectName(u"phase_left_layout")
        self.phase_left_layout.setContentsMargins(0, -1, -1, -1)
        self.phase_label_2 = QLabel(self.phase_left_widget)
        self.phase_label_2.setObjectName(u"phase_label_2")
        self.phase_label_2.setMaximumSize(QSize(16777215, 40))
        self.phase_label_2.setStyleSheet(u"font-size:12pt")

        self.phase_left_layout.addWidget(self.phase_label_2)


        self.left_leg_layout.addWidget(self.phase_left_widget)

        self.subphase_left_widget = QWidget(self.left_leg_frame)
        self.subphase_left_widget.setObjectName(u"subphase_left_widget")
        self.subphase_left_layout = QVBoxLayout(self.subphase_left_widget)
        self.subphase_left_layout.setObjectName(u"subphase_left_layout")
        self.subphase_left_layout.setContentsMargins(0, -1, -1, -1)
        self.subphase_label_2 = QLabel(self.subphase_left_widget)
        self.subphase_label_2.setObjectName(u"subphase_label_2")
        self.subphase_label_2.setMaximumSize(QSize(16777215, 40))
        self.subphase_label_2.setStyleSheet(u"font-size:12pt")

        self.subphase_left_layout.addWidget(self.subphase_label_2)


        self.left_leg_layout.addWidget(self.subphase_left_widget)


        self.gridLayout.addWidget(self.left_leg_frame, 1, 0, 1, 1)

        self.right_leg_frame = QFrame(self.page_07)
        self.right_leg_frame.setObjectName(u"right_leg_frame")
        self.right_leg_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.right_leg_frame.setFrameShadow(QFrame.Shadow.Raised)
        self.right_leg_layout = QVBoxLayout(self.right_leg_frame)
        self.right_leg_layout.setSpacing(0)
        self.right_leg_layout.setObjectName(u"right_leg_layout")
        self.right_leg_layout.setContentsMargins(9, 0, 0, 0)
        self.count_label = QLabel(self.right_leg_frame)
        self.count_label.setObjectName(u"count_label")
        self.count_label.setMaximumSize(QSize(16777215, 60))
        self.count_label.setStyleSheet(u"font-size:14pt")
        

        # phase display above the step counter (right)
        self.phase_right_value_label = QLabel(self.right_leg_frame)
        self.phase_right_value_label.setObjectName(u"phase_right_value_label")
        self.phase_right_value_label.setMaximumSize(QSize(16777215, 30))
        self.phase_right_value_label.setStyleSheet(u"font-size:12pt; font-weight:600;")
        self.phase_right_value_label.setText("Phase: Unknown")
        self.right_leg_layout.addWidget(self.phase_right_value_label)


        self.right_leg_layout.addWidget(self.count_label)

        self.phase_right_widget = QWidget(self.right_leg_frame)
        self.phase_right_widget.setObjectName(u"phase_right_widget")
        self.phase_right_layout = QVBoxLayout(self.phase_right_widget)
        self.phase_right_layout.setObjectName(u"phase_right_layout")
        self.phase_right_layout.setContentsMargins(0, -1, -1, -1)
        self.phase_label = QLabel(self.phase_right_widget)
        self.phase_label.setObjectName(u"phase_label")
        self.phase_label.setMaximumSize(QSize(16777215, 40))
        self.phase_label.setStyleSheet(u"font-size:12pt")

        self.phase_right_layout.addWidget(self.phase_label)


        self.right_leg_layout.addWidget(self.phase_right_widget)

        self.subphase_right_widget = QWidget(self.right_leg_frame)
        self.subphase_right_widget.setObjectName(u"subphase_right_widget")
        self.subphase_right_layout = QVBoxLayout(self.subphase_right_widget)
        self.subphase_right_layout.setObjectName(u"subphase_right_layout")
        self.subphase_right_layout.setContentsMargins(0, -1, -1, -1)
        self.subphase_label = QLabel(self.subphase_right_widget)
        self.subphase_label.setObjectName(u"subphase_label")
        self.subphase_label.setMaximumSize(QSize(16777215, 40))
        self.subphase_label.setStyleSheet(u"font-size:12pt")

        self.subphase_right_layout.addWidget(self.subphase_label)


        self.right_leg_layout.addWidget(self.subphase_right_widget)


        self.gridLayout.addWidget(self.right_leg_frame, 1, 1, 1, 1)

        self.pages.addWidget(self.page_07)
        self.page_08 = QWidget()
        self.page_08.setObjectName(u"page_08")
        self.verticalLayout_3 = QVBoxLayout(self.page_08)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.title_label_8 = QLabel(self.page_08)
        self.title_label_8.setObjectName(u"title_label_8")
        self.title_label_8.setMaximumSize(QSize(16777215, 80))
        self.title_label_8.setStyleSheet(u"font-size:16pt")

        self.verticalLayout_3.addWidget(self.title_label_8, 0, Qt.AlignmentFlag.AlignHCenter)

        self.fsr_status_widget = QWidget(self.page_08)
        self.fsr_status_widget.setObjectName(u"fsr_status_widget")
        sizePolicy.setHeightForWidth(self.fsr_status_widget.sizePolicy().hasHeightForWidth())
        self.fsr_status_widget.setSizePolicy(sizePolicy)
        self.fsr_status_widget.setMaximumSize(QSize(16777215, 16777215))
        self.fsr_status_layout = QGridLayout(self.fsr_status_widget)
        self.fsr_status_layout.setObjectName(u"fsr_status_layout")
        self.fsr_status_layout.setVerticalSpacing(4)
        self.fsr_status_layout.setContentsMargins(0, 0, 0, 0)

        self.verticalLayout_3.addWidget(self.fsr_status_widget, 0, Qt.AlignmentFlag.AlignHCenter)

        self.fsr_frame = QFrame(self.page_08)
        self.fsr_frame.setObjectName(u"fsr_frame")
        self.fsr_frame.setMinimumSize(QSize(400, 0))
        self.fsr_frame.setMaximumSize(QSize(500, 200))
        self.fsr_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.fsr_frame.setFrameShadow(QFrame.Shadow.Raised)
        self.gridLayout_2 = QGridLayout(self.fsr_frame)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.gridLayout_2.setHorizontalSpacing(6)
        self.mf_label_right = QLabel(self.fsr_frame)
        self.mf_label_right.setObjectName(u"mf_label_right")

        self.gridLayout_2.addWidget(self.mf_label_right, 2, 6, 1, 1, Qt.AlignmentFlag.AlignHCenter)

        self.mf_label_left = QLabel(self.fsr_frame)
        self.mf_label_left.setObjectName(u"mf_label_left")
        self.mf_label_left.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gridLayout_2.addWidget(self.mf_label_left, 2, 2, 1, 1)

        self.line_3 = QFrame(self.fsr_frame)
        self.line_3.setObjectName(u"line_3")
        self.line_3.setFrameShape(QFrame.Shape.VLine)
        self.line_3.setFrameShadow(QFrame.Shadow.Sunken)

        self.gridLayout_2.addWidget(self.line_3, 3, 4, 1, 1)

        self.bf_label_left = QLabel(self.fsr_frame)
        self.bf_label_left.setObjectName(u"bf_label_left")
        self.bf_label_left.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gridLayout_2.addWidget(self.bf_label_left, 2, 3, 1, 1)

        self.ff_value_left = QLabel(self.fsr_frame)
        self.ff_value_left.setObjectName(u"ff_value_left")
        self.ff_value_left.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gridLayout_2.addWidget(self.ff_value_left, 3, 0, 1, 1)

        self.mf_value_left = QLabel(self.fsr_frame)
        self.mf_value_left.setObjectName(u"mf_value_left")
        self.mf_value_left.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gridLayout_2.addWidget(self.mf_value_left, 3, 2, 1, 1)

        self.bf_value_left = QLabel(self.fsr_frame)
        self.bf_value_left.setObjectName(u"bf_value_left")
        self.bf_value_left.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gridLayout_2.addWidget(self.bf_value_left, 3, 3, 1, 1)

        self.line_2 = QFrame(self.fsr_frame)
        self.line_2.setObjectName(u"line_2")
        self.line_2.setFrameShape(QFrame.Shape.VLine)
        self.line_2.setFrameShadow(QFrame.Shadow.Sunken)

        self.gridLayout_2.addWidget(self.line_2, 2, 4, 1, 1)

        self.ff_label_right = QLabel(self.fsr_frame)
        self.ff_label_right.setObjectName(u"ff_label_right")

        self.gridLayout_2.addWidget(self.ff_label_right, 2, 5, 1, 1, Qt.AlignmentFlag.AlignHCenter)

        self.ff_label_left = QLabel(self.fsr_frame)
        self.ff_label_left.setObjectName(u"ff_label_left")
        self.ff_label_left.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gridLayout_2.addWidget(self.ff_label_left, 2, 0, 1, 1)

        self.mf_value_right = QLabel(self.fsr_frame)
        self.mf_value_right.setObjectName(u"mf_value_right")

        self.gridLayout_2.addWidget(self.mf_value_right, 3, 6, 1, 1, Qt.AlignmentFlag.AlignHCenter)

        self.line = QFrame(self.fsr_frame)
        self.line.setObjectName(u"line")
        self.line.setFrameShape(QFrame.Shape.VLine)
        self.line.setFrameShadow(QFrame.Shadow.Sunken)

        self.gridLayout_2.addWidget(self.line, 1, 4, 1, 1)

        self.bf_value_right = QLabel(self.fsr_frame)
        self.bf_value_right.setObjectName(u"bf_value_right")

        self.gridLayout_2.addWidget(self.bf_value_right, 3, 7, 1, 1, Qt.AlignmentFlag.AlignHCenter)

        self.fsr_label_right = QLabel(self.fsr_frame)
        self.fsr_label_right.setObjectName(u"fsr_label_right")

        self.gridLayout_2.addWidget(self.fsr_label_right, 1, 6, 1, 1)

        self.ff_value_right = QLabel(self.fsr_frame)
        self.ff_value_right.setObjectName(u"ff_value_right")

        self.gridLayout_2.addWidget(self.ff_value_right, 3, 5, 1, 1, Qt.AlignmentFlag.AlignHCenter)

        self.bf_label_right = QLabel(self.fsr_frame)
        self.bf_label_right.setObjectName(u"bf_label_right")

        self.gridLayout_2.addWidget(self.bf_label_right, 2, 7, 1, 1)

        self.fsr_label_left = QLabel(self.fsr_frame)
        self.fsr_label_left.setObjectName(u"fsr_label_left")
        self.fsr_label_left.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.gridLayout_2.addWidget(self.fsr_label_left, 1, 2, 1, 1)


        self.verticalLayout_3.addWidget(self.fsr_frame, 0, Qt.AlignmentFlag.AlignHCenter)

        self.finish_btn_widget_3 = QWidget(self.page_08)
        self.finish_btn_widget_3.setObjectName(u"finish_btn_widget_3")
        self.finish_btn_widget_3.setMaximumSize(QSize(16777215, 80))
        self.finish_btn_layout_3 = QHBoxLayout(self.finish_btn_widget_3)
        self.finish_btn_layout_3.setObjectName(u"finish_btn_layout_3")

        self.verticalLayout_3.addWidget(self.finish_btn_widget_3)

        self.pages.addWidget(self.page_08)
        self.page_09 = QWidget()
        self.page_09.setObjectName(u"page_09")
        self.verticalLayout_2 = QVBoxLayout(self.page_09)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.title_label_9 = QLabel(self.page_09)
        self.title_label_9.setObjectName(u"title_label_9")
        self.title_label_9.setMaximumSize(QSize(16777215, 80))
        self.title_label_9.setStyleSheet(u"font-size:16pt")
        self.title_label_9.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.verticalLayout_2.addWidget(self.title_label_9)

        self.imu_calibration_widget = QWidget(self.page_09)
        self.imu_calibration_widget.setObjectName(u"imu_calibration_widget")
        self.imu_calibration_layout = QGridLayout(self.imu_calibration_widget)
        self.imu_calibration_layout.setObjectName(u"imu_calibration_layout")
        self.imu_calibration_layout.setContentsMargins(0, 0, 0, 0)

        self.verticalLayout_2.addWidget(self.imu_calibration_widget)

        self.angle_plot_widget = QWidget(self.page_09)
        self.angle_plot_widget.setObjectName(u"angle_plot_widget")
        self.angle_plot_widget.setMaximumSize(QSize(16777215, 16777215))
        self.angle_plot_layout = QVBoxLayout(self.angle_plot_widget)
        self.angle_plot_layout.setSpacing(0)
        self.angle_plot_layout.setObjectName(u"angle_plot_layout")
        self.angle_plot_layout.setContentsMargins(0, 0, 0, 0)

        self.verticalLayout_2.addWidget(self.angle_plot_widget)

        self.finish_btn_widget_6 = QWidget(self.page_09)
        self.finish_btn_widget_6.setObjectName(u"finish_btn_widget_6")
        self.finish_btn_widget_6.setMaximumSize(QSize(16777215, 60))
        self.finish_btn_layout_6 = QHBoxLayout(self.finish_btn_widget_6)
        self.finish_btn_layout_6.setObjectName(u"finish_btn_layout_6")

        self.verticalLayout_2.addWidget(self.finish_btn_widget_6)

        self.pages.addWidget(self.page_09)

        self.main_pages_layout.addWidget(self.pages)


        self.retranslateUi(MainPages)

        self.pages.setCurrentIndex(7)


        QMetaObject.connectSlotsByName(MainPages)
    # setupUi

    def retranslateUi(self, MainPages):
        MainPages.setWindowTitle(QCoreApplication.translate("MainPages", u"Form", None))
        self.title_label.setText(QCoreApplication.translate("MainPages", u"Setup", None))
        self.time_label.setText(QCoreApplication.translate("MainPages", u"00:00:00", None))
        self.serial_port_label.setText(QCoreApplication.translate("MainPages", u"Serial Port", None))
        self.baud_rate_label.setText(QCoreApplication.translate("MainPages", u"Baud Rate", None))
        self.title_label_2.setText(QCoreApplication.translate("MainPages", u"Subject Information", None))
        self.label_subj_id.setText(QCoreApplication.translate("MainPages", u"Subject ID", None))
        self.label_fname.setText(QCoreApplication.translate("MainPages", u"First Name", None))
        self.label_lname.setText(QCoreApplication.translate("MainPages", u"Last Name", None))
        self.label_height.setText(QCoreApplication.translate("MainPages", u"Height [cm]", None))
        self.label_age.setText(QCoreApplication.translate("MainPages", u"Age", None))
        self.label_weight.setText(QCoreApplication.translate("MainPages", u"Weight [kg]", None))
        self.title_label_4.setText(QCoreApplication.translate("MainPages", u"Safe Information", None))
        self.option_label.setText(QCoreApplication.translate("MainPages", u"Select Custom Format", None))
        self.text_label.setText(QCoreApplication.translate("MainPages", u"Example", None))
        self.title_label_3.setText(QCoreApplication.translate("MainPages", u"Task Configuration", None))
        self.burst_duration_label.setText(QCoreApplication.translate("MainPages", u"Burst Duration [us]", None))
        self.burst_period_value_label.setText(QCoreApplication.translate("MainPages", u"nan", None))
        self.burst_frequency_label.setText(QCoreApplication.translate("MainPages", u"Burst Frequency [Hz]", None))
        self.pulse_width_value_label.setText(QCoreApplication.translate("MainPages", u"nan", None))
        self.pulse_period_value_label.setText(QCoreApplication.translate("MainPages", u"nan", None))
        self.nb_pulses_value_label.setText(QCoreApplication.translate("MainPages", u"nan", None))
        self.burst_period_label.setText(QCoreApplication.translate("MainPages", u"Burst Period [ms]", None))
        self.carrier_frequency_label.setText(QCoreApplication.translate("MainPages", u"Carrier Frequency [Hz]", None))
        self.pulse_deadtime_label.setText(QCoreApplication.translate("MainPages", u"Pulse Deadtime (T2) [us]", None))
        self.interpulse_interval_label.setText(QCoreApplication.translate("MainPages", u"Interpulse Interval (T3) [us]", None))
        self.pulse_period_label.setText(QCoreApplication.translate("MainPages", u"Pulse Period [us]", None))
        self.pulse_width_label.setText(QCoreApplication.translate("MainPages", u"Pulse Width [us]", None))
        self.nb_pulses_label.setText(QCoreApplication.translate("MainPages", u"Pulses per Burst", None))
        self.title_label_5.setText(QCoreApplication.translate("MainPages", u"Stimulation Parameters", None))
        self.channel_label.setText(QCoreApplication.translate("MainPages", u"Channel 0 [mA]\n"
"Optimal - Maximal", None))
        self.channel_label_1.setText(QCoreApplication.translate("MainPages", u"Channel 1 [mA]\n"
"Optimal - Maximal", None))
        self.channel_label_2.setText(QCoreApplication.translate("MainPages", u"Channel 2 [mA]\n"
"Optimal - Maximal", None))
        self.channel_label_3.setText(QCoreApplication.translate("MainPages", u"Channel 3 [mA]\n"
"Optimal - Maximal", None))
        self.channel_label_4.setText(QCoreApplication.translate("MainPages", u"Channel 4 [mA]\n"
"Optimal - Maximal", None))
        self.channel_label_5.setText(QCoreApplication.translate("MainPages", u"Channel 5 [mA]\n"
"Optimal - Maximal", None))
        self.channel_label_6.setText(QCoreApplication.translate("MainPages", u"Channel 6 [mA]\n"
"Optimal - Maximal", None))
        self.channel_label_7.setText(QCoreApplication.translate("MainPages", u"Channel 7 [mA]\n"
"Optimal - Maximal", None))
        self.channel_assignment_label.setText(QCoreApplication.translate("MainPages", u"Assign Channel to Electrode", None))
        self.left_dist_label.setText(QCoreApplication.translate("MainPages", u"Left Distal", None))
        self.right_leg_label.setText(QCoreApplication.translate("MainPages", u"Right Leg", None))
        self.target_assignment_label.setText(QCoreApplication.translate("MainPages", u"Assign Channel to Target", None))
        self.right_dist_label.setText(QCoreApplication.translate("MainPages", u"Right Distal", None))
        self.left_prox_label.setText(QCoreApplication.translate("MainPages", u"Left Proximal", None))
        self.right_prox_label.setText(QCoreApplication.translate("MainPages", u"Right Proximal", None))
        self.left_leg_label.setText(QCoreApplication.translate("MainPages", u"Left Leg", None))
#if QT_CONFIG(tooltip)
        self.label.setToolTip(QCoreApplication.translate("MainPages", u"Only assign a channel to this target if that channel should be continuously stimulated.", None))
#endif // QT_CONFIG(tooltip)
        self.label.setText(QCoreApplication.translate("MainPages", u"Continuous", None))
        self.title_label_6.setText(QCoreApplication.translate("MainPages", u"Confirm Information", None))
        self.info_label_6.setText(QCoreApplication.translate("MainPages", u"Age", None))
        self.info_label_4.setText(QCoreApplication.translate("MainPages", u"Height [cm]", None))
        self.info_label.setText(QCoreApplication.translate("MainPages", u"First Name", None))
        self.info_label_2.setText(QCoreApplication.translate("MainPages", u"Last Name", None))
        self.info_label_5.setText(QCoreApplication.translate("MainPages", u"Weight [kg]", None))
        self.info_label_3.setText(QCoreApplication.translate("MainPages", u"Subject ID", None))
        self.info_label_7.setText(QCoreApplication.translate("MainPages", u"Task", None))
        self.info_label_8.setText(QCoreApplication.translate("MainPages", u"Save As", None))
        self.info_label_9.setText(QCoreApplication.translate("MainPages", u"Channel 0 [mA]", None))
        self.info_label_10.setText(QCoreApplication.translate("MainPages", u"Channel 1 [mA]", None))
        self.info_label_11.setText(QCoreApplication.translate("MainPages", u"Channel 2 [mA]", None))
        self.info_label_12.setText(QCoreApplication.translate("MainPages", u"Channel 3 [mA]", None))
        self.info_label_13.setText(QCoreApplication.translate("MainPages", u"Channel 4 [mA]", None))
        self.info_label_14.setText(QCoreApplication.translate("MainPages", u"Channel 5 [mA]", None))
        self.info_label_15.setText(QCoreApplication.translate("MainPages", u"Channel 6 [mA]", None))
        self.info_label_16.setText(QCoreApplication.translate("MainPages", u"Channel 7 [mA]", None))
        self.title_label_7.setText(QCoreApplication.translate("MainPages", u"Counters", None))
        self.count_label_2.setText(QCoreApplication.translate("MainPages", u"Final Counters for Left Shank IMU:", None))
        self.phase_label_2.setText(QCoreApplication.translate("MainPages", u"Phase Count:", None))
        self.subphase_label_2.setText(QCoreApplication.translate("MainPages", u"Subphase Count:", None))
        self.count_label.setText(QCoreApplication.translate("MainPages", u"Final counters for Right Shank IMU:", None))
        self.phase_label.setText(QCoreApplication.translate("MainPages", u"Phase Count:", None))
        self.subphase_label.setText(QCoreApplication.translate("MainPages", u"Subphase Count:", None))
        self.title_label_8.setText(QCoreApplication.translate("MainPages", u"FSR", None))
        self.mf_label_right.setText(QCoreApplication.translate("MainPages", u"Middle Foot", None))
        self.mf_label_left.setText(QCoreApplication.translate("MainPages", u"Middle Foot", None))
        self.bf_label_left.setText(QCoreApplication.translate("MainPages", u"Back Foot", None))
        self.ff_value_left.setText(QCoreApplication.translate("MainPages", u"999", None))
        self.mf_value_left.setText(QCoreApplication.translate("MainPages", u"999", None))
        self.bf_value_left.setText(QCoreApplication.translate("MainPages", u"999", None))
        self.ff_label_right.setText(QCoreApplication.translate("MainPages", u"Front Foot", None))
        self.ff_label_left.setText(QCoreApplication.translate("MainPages", u"Front Foot", None))
        self.mf_value_right.setText(QCoreApplication.translate("MainPages", u"999", None))
        self.bf_value_right.setText(QCoreApplication.translate("MainPages", u"999", None))
        self.fsr_label_right.setText(QCoreApplication.translate("MainPages", u"Right Foot Values", None))
        self.ff_value_right.setText(QCoreApplication.translate("MainPages", u"999", None))
        self.bf_label_right.setText(QCoreApplication.translate("MainPages", u"Back foot", None))
        self.fsr_label_left.setText(QCoreApplication.translate("MainPages", u"Left Foot Values", None))
        self.title_label_9.setText(QCoreApplication.translate("MainPages", u"IMU", None))
    # retranslateUi

