# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'left_columnxojrxw.ui'
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
from PySide6.QtWidgets import (QApplication, QFrame, QLabel, QSizePolicy,
    QStackedWidget, QVBoxLayout, QWidget)

class Ui_LeftColumn(object):
    def setupUi(self, LeftColumn):
        if not LeftColumn.objectName():
            LeftColumn.setObjectName(u"LeftColumn")
        LeftColumn.resize(203, 562)
        self.main_pages_layout = QVBoxLayout(LeftColumn)
        self.main_pages_layout.setSpacing(0)
        self.main_pages_layout.setObjectName(u"main_pages_layout")
        self.main_pages_layout.setContentsMargins(5, 5, 5, 5)
        self.menus = QStackedWidget(LeftColumn)
        self.menus.setObjectName(u"menus")
        self.menu_1 = QWidget()
        self.menu_1.setObjectName(u"menu_1")
        self.verticalLayout = QVBoxLayout(self.menu_1)
        self.verticalLayout.setSpacing(5)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(5, 5, 5, 5)
        self.btn_1_widget = QWidget(self.menu_1)
        self.btn_1_widget.setObjectName(u"btn_1_widget")
        self.btn_1_widget.setMinimumSize(QSize(0, 40))
        self.btn_1_widget.setMaximumSize(QSize(16777215, 40))
        self.btn_1_layout = QVBoxLayout(self.btn_1_widget)
        self.btn_1_layout.setSpacing(0)
        self.btn_1_layout.setObjectName(u"btn_1_layout")
        self.btn_1_layout.setContentsMargins(0, 0, 0, 0)

        self.verticalLayout.addWidget(self.btn_1_widget)

        self.btn_2_widget = QWidget(self.menu_1)
        self.btn_2_widget.setObjectName(u"btn_2_widget")
        self.btn_2_widget.setMinimumSize(QSize(0, 40))
        self.btn_2_widget.setMaximumSize(QSize(16777215, 40))
        self.btn_2_layout = QVBoxLayout(self.btn_2_widget)
        self.btn_2_layout.setSpacing(0)
        self.btn_2_layout.setObjectName(u"btn_2_layout")
        self.btn_2_layout.setContentsMargins(0, 0, 0, 0)

        self.verticalLayout.addWidget(self.btn_2_widget)

        self.btn_3_widget = QWidget(self.menu_1)
        self.btn_3_widget.setObjectName(u"btn_3_widget")
        self.btn_3_widget.setMinimumSize(QSize(0, 40))
        self.btn_3_widget.setMaximumSize(QSize(16777215, 40))
        self.btn_3_layout = QVBoxLayout(self.btn_3_widget)
        self.btn_3_layout.setSpacing(0)
        self.btn_3_layout.setObjectName(u"btn_3_layout")
        self.btn_3_layout.setContentsMargins(0, 0, 0, 0)

        self.verticalLayout.addWidget(self.btn_3_widget)

        self.label_1 = QLabel(self.menu_1)
        self.label_1.setObjectName(u"label_1")
        font = QFont()
        font.setPointSize(16)
        self.label_1.setFont(font)
        self.label_1.setStyleSheet(u"font-size: 16pt")
        self.label_1.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.verticalLayout.addWidget(self.label_1)

        self.menus.addWidget(self.menu_1)
        self.menu_2 = QWidget()
        self.menu_2.setObjectName(u"menu_2")
        self.verticalLayout_2 = QVBoxLayout(self.menu_2)
        self.verticalLayout_2.setSpacing(5)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.verticalLayout_2.setContentsMargins(5, 5, 5, 5)
        self.save_btn_widget = QWidget(self.menu_2)
        self.save_btn_widget.setObjectName(u"save_btn_widget")
        self.save_btn_widget.setMaximumSize(QSize(16777215, 40))
        self.save_btn_layout = QVBoxLayout(self.save_btn_widget)
        self.save_btn_layout.setSpacing(0)
        self.save_btn_layout.setObjectName(u"save_btn_layout")
        self.save_btn_layout.setContentsMargins(0, 0, 0, 0)

        self.verticalLayout_2.addWidget(self.save_btn_widget)

        self.load_btn_widget = QWidget(self.menu_2)
        self.load_btn_widget.setObjectName(u"load_btn_widget")
        self.load_btn_widget.setMinimumSize(QSize(0, 40))
        self.load_btn_widget.setMaximumSize(QSize(16777215, 40))
        self.load_btn_layout = QVBoxLayout(self.load_btn_widget)
        self.load_btn_layout.setSpacing(0)
        self.load_btn_layout.setObjectName(u"load_btn_layout")
        self.load_btn_layout.setContentsMargins(0, 0, 0, 0)

        self.verticalLayout_2.addWidget(self.load_btn_widget)

        self.menu_2_break_line_frame = QFrame(self.menu_2)
        self.menu_2_break_line_frame.setObjectName(u"menu_2_break_line_frame")
        self.menu_2_break_line_frame.setFrameShape(QFrame.Shape.HLine)
        self.menu_2_break_line_frame.setFrameShadow(QFrame.Shadow.Raised)

        self.verticalLayout_2.addWidget(self.menu_2_break_line_frame)

        self.save_task_btn_widget = QWidget(self.menu_2)
        self.save_task_btn_widget.setObjectName(u"save_task_btn_widget")
        self.save_task_btn_widget.setMaximumSize(QSize(16777215, 40))
        self.save_task_btn_layout = QVBoxLayout(self.save_task_btn_widget)
        self.save_task_btn_layout.setSpacing(0)
        self.save_task_btn_layout.setObjectName(u"save_task_btn_layout")
        self.save_task_btn_layout.setContentsMargins(0, 0, 0, 0)

        self.verticalLayout_2.addWidget(self.save_task_btn_widget)

        self.load_task_btn_widget = QWidget(self.menu_2)
        self.load_task_btn_widget.setObjectName(u"load_task_btn_widget")
        self.load_task_btn_widget.setMaximumSize(QSize(16777215, 40))
        self.load_task_btn_layout = QVBoxLayout(self.load_task_btn_widget)
        self.load_task_btn_layout.setSpacing(0)
        self.load_task_btn_layout.setObjectName(u"load_task_btn_layout")
        self.load_task_btn_layout.setContentsMargins(0, 0, 0, 0)

        self.verticalLayout_2.addWidget(self.load_task_btn_widget)

        self.label = QLabel(self.menu_2)
        self.label.setObjectName(u"label")
        self.label.setStyleSheet(u"font-size:12pt")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setWordWrap(True)

        self.verticalLayout_2.addWidget(self.label)

        self.menus.addWidget(self.menu_2)

        self.main_pages_layout.addWidget(self.menus)


        self.retranslateUi(LeftColumn)

        self.menus.setCurrentIndex(1)


        QMetaObject.connectSlotsByName(LeftColumn)
    # setupUi

    def retranslateUi(self, LeftColumn):
        LeftColumn.setWindowTitle(QCoreApplication.translate("LeftColumn", u"Form", None))
        self.label_1.setText(QCoreApplication.translate("LeftColumn", u"Menu 1 - Left Menu", None))
        self.label.setText(QCoreApplication.translate("LeftColumn", u"Save or Load Information", None))
    # retranslateUi

