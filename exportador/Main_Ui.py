import sys
import os
import copy
import simplekml
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QFormLayout, QPushButton, QFileDialog, QCheckBox, QComboBox, QLineEdit,
    QColorDialog, QTabWidget, QGroupBox, QMessageBox, QScrollArea
)
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtCore import Qt
from .pdf_utils import generar_pdf_trafo

# IMPORTS desde core.py (asegúrate de tener estas funciones implementadas)
from .core import (
    obtener_circuitos,
    obtener_trafos_por_circuito,
    exportar_kmz_puntos,
    exportar_kmz_lineas,
    exportar_kmz_por_trafo,
    limpiar_nombre
    # obtener_datos etc. ya están en core si los necesitas
)

# -------------------------
# ENTIDADES / CONFIG (puedes reemplazar por tu dict real si lo tienes en otro archivo)
# (Asegúrate de mantener las claves que usa core.py: 'TRAFOS', 'POSTES_BT_BY_TRAFO', 'RED_BT_BY_TRAFO', etc.)
# Reuso el esquema que estabas usando — si ya tienes este dict en otro archivo, puedes importarlo.
# -------------------------
entidades_config = {
    "AISLADEROS": {
        "campos": [("CODIGO_FID", "LONG"), ("CODIGO", "TEXT"), ("CODIGO_OPERATIVO", "TEXT"),
                    ("CIRCUITO", "TEXT"), ("REGION", "TEXT"),("NIVEL_TENSION", "TEXT"), ("ZONAID", "TEXT"),
                    ("FID_ANTERIOR", "LONG"), ("MUNICIPIO", "TEXT"), ("UBICACION", "TEXT"),
                    ("CONTRATO_INSTALACION", "TEXT"), ("FECHA_OPERACION", "DATE"), ("CAPACIDAD", "LONG"),
                    ("TIPO_AISLADREO", "TEXT"), ("UC", "TEXT"),
                    ("COOR_GPS_LON", "DOUBLE"), ("COOR_GPS_LAT", "DOUBLE")],
        "etiqueta": "CODIGO",
        "estilo": {
            "icon_href": r"D:\kmz_generator_project\Simbologia\AISLADEROS.png",
            "color": "ff0000ff",
            "scale": 1.2,
            "tipo": "punto"
        }
    },
    "CUCHILLAS": {
        "campos": [("CODIGO_FID", "LONG"), ("CODIGO", "TEXT"), ("CODIGO_OPERATIVO", "TEXT"),
                    ("CIRCUITO", "TEXT"), ("REGION", "TEXT"),("NIVEL_TENSION", "TEXT"), ("ZONAID", "TEXT"),
                    ("MUNICIPIO", "TEXT"), ("UBICACION", "TEXT"), ("CONTRATO_INSTALACION", "TEXT"),
                    ("FECHA_OPERACION", "DATE"), ("UC", "TEXT"),
                    ("COOR_GPS_LON", "DOUBLE"), ("COOR_GPS_LAT", "DOUBLE")],
        "etiqueta": "CODIGO",
        "estilo": {
            "icon_href": r"D:\kmz_generator_project\Simbologia\CUCHILLAS.png",
            "color": "ff00ffff",
            "scale": 1.1,
            "tipo": "punto"
        }
    },
    "RECONECTADORES": {
        "campos": [("CODIGO_FID", "LONG"), ("CODIGO_OPERATIVO", "TEXT"), ("CIRCUITO", "TEXT"),("REGION", "TEXT"),
                    ("NIVEL_TENSION", "TEXT"), ("ZONAID", "TEXT"), ("MUNICIPIO", "TEXT"),
                    ("UBICACION", "TEXT"), ("CONTRATO_INSTALACION", "TEXT"), ("FECHA_OPERACION", "DATE"),
                    ("UC", "TEXT"), ("COOR_GPS_LON", "DOUBLE"), ("COOR_GPS_LAT", "DOUBLE")],
        "etiqueta": "CODIGO_OPERATIVO",
        "estilo": {
            "icon_href": r"D:\kmz_generator_project\Simbologia\RECONECTADORES.png",
            "color": "ff00ffff",
            "scale": 2,
            "tipo": "punto"
         }
     },
      "TRAFOS": {
         "campos": [("NODO_TRANSFORM_V", "TEXT"), ("G3E_FID", "LONG"), ("ZONAID", "TEXT"),
                     ("MUNICIPIO", "TEXT"), ("UBICACION", "TEXT"), ("CONTRATO_INSTALACION", "TEXT"),
                     ("FECHA_OPERACION", "DATE"), ("NRO_TRANSFORMADOR_V", "TEXT"), ("FASES", "TEXT"),
                      ("CIRCUITO", "TEXT"), ("REGION", "TEXT"),("CODIGO", "TEXT"), ("FABRICANTE_TRAFO", "TEXT"),
                      ("FECHA_FABRICACION", "DATE"), ("TIPO_SUBESTACION", "TEXT"),
                      ("CLASIFICACION_MERCADO", "TEXT"), ("CAPACIDAD_NOMINAL", "TEXT"),
                      ("OBSERVACIONES", "TEXT"), ("USUARIOS", "LONG"),("COOR_GPS_LON", "DOUBLE"),("COOR_GPS_LAT", "DOUBLE")],
           "etiqueta": "NODO_TRANSFORM_V",
           "estilo": {
              "icon_href": r"D:\kmz_generator_project\Simbologia\TRAFOS.png",
               "color": "ff7f7f00",
               "scale": 1.3,
               "tipo": "punto"
          }
      },
      "POSTES_MT": {
          "campos": [("G3E_FID", "LONG"), ("CODIGO", "TEXT"), ("CODIGO_OPERATIVO", "TEXT"), ("MACRONORMA", "TEXT"),
                      ("CIRCUITO", "TEXT"),("REGION", "TEXT"),("NIVEL_TENSION", "TEXT"), ("MUNICIPIO", "TEXT"),
                      ("UBICACION", "TEXT"), ("CONTRATO_INSTALACION", "TEXT"), ("CLASIFICACION_MERCADO", "TEXT"),
                    ("FECHA_INSTALACION", "DATE"), ("OBSERVACIONES", "TEXT"), ("NORMA", "TEXT"),
                     ("APOYO", "TEXT"), ("MATERIAL", "TEXT"), ("ALTURA", "DOUBLE"), ("TIPO_ADECUACION", "TEXT"),
                     ("RESISTENCIA_KGF", "TEXT"), ("CODIGO2", "TEXT"), ("UC", "TEXT"), ("TIPO_RED", "TEXT"),
                     ("COOR_GPS_LON", "DOUBLE"), ("COOR_GPS_LAT", "DOUBLE")],
           "etiqueta": None,
          "estilo": {
              "icon_href": r"D:\kmz_generator_project\Simbologia\POSTES_MT.png",
              "color": "ff0000ff",
              "scale": 0.9,
              "tipo": "punto"
         }
      },
      "POSTES_BT": {
          "campos": [("G3E_FID", "LONG"), ("CODIGO", "TEXT"), ("CODIGO_OPERATIVO", "TEXT"),("MACRONORMA", "TEXT"),
                   ("CIRCUITO", "TEXT"), ("REGION", "TEXT"),("CODIGO_TRAFO", "TEXT"), ("NIVEL_TENSION", "TEXT"),
                    ("MUNICIPIO", "TEXT"), ("UBICACION", "TEXT"), ("CONTRATO_INSTALACION", "TEXT"),
                    ("CLASIFICACION_MERCADO", "TEXT"), ("FECHA_INSTALACION", "DATE"), ("OBSERVACIONES", "TEXT"),
                    ("NORMA", "TEXT"), ("APOYO", "TEXT"), ("MATERIAL", "TEXT"), ("ALTURA", "DOUBLE"),
                    ("TIPO_ADECUACION", "TEXT"), ("RESISTENCIA_KGF", "TEXT"), ("CODIGO2", "TEXT"),
                    ("UC", "TEXT"), ("TIPO_RED", "TEXT"), ("COOR_GPS_LON", "DOUBLE"), ("COOR_GPS_LAT", "DOUBLE")],
         "etiqueta": None,
         "estilo": {
             "icon_href": r"D:\kmz_generator_project\Simbologia\POSTES_BT.png",
             "color": "ffff0000",
             "scale": 0.9,
             "tipo": "punto"
        }
    },
    "RED_MT": {
         "campos": [("G3E_FID", "LONG"), ("CODIGO_OPERATIVO", "TEXT"), ("CODIGO", "TEXT"), ("CODE_CONDUCTOR", "TEXT"),
                     ("NODO1_ID", "TEXT"), ("NODO2_ID", "TEXT"), ("TENSION", "TEXT"),
                    ("CONTRATO_INSTALACION", "TEXT"), ("SUBREGION", "TEXT"), ("MUNICIPIO", "TEXT"),
                    ("OBSERVACIONES", "TEXT"), ("FASES", "TEXT"), ("LONGITUD", "DOUBLE"),
                   ("TIPO_AISLAMIENTO", "TEXT"), ("LOCALIZACION", "TEXT"),
                      ("CLASIFICACION_MERCADO", "TEXT"), ("CIRCUITO", "TEXT"),("REGION", "TEXT"), ("UC", "TEXT"),
                      ("FECHA_INSTALACION", "DATE")],
           "etiqueta": "CODE_CONDUCTOR",
          "estilo": {
              "color": "ff0000ff",
              "width": 3.0,
             "tipo": "linea"
        }
      },
      "RED_BT": {
               "campos": [("G3E_FID", "LONG"), ("CODIGO", "TEXT"), ("CODE_CONDUCTOR", "TEXT"),
                          ("CODIGO_MAXIMO", "TEXT"), ("CONTRATO_INSTALACION", "TEXT"),
                          ("SUBREGION", "TEXT"), ("MUNICIPIO", "TEXT"), ("LONGITUD", "DOUBLE"),
                          ("NODO_TRANSFORM_V", "TEXT"), ("LOCALIZACION", "TEXT"),
                          ("CLASIFICACION_MERCADO", "TEXT"), ("CIRCUITO", "TEXT"),
                          ("REGION", "TEXT"), ("FECHA_INSTALACION", "DATE"),
                          ("FASES", "TEXT")],
         "etiqueta": None,
          "estilo": {
              "color": "ffff0000",
             "width": 2.5,
         "tipo": "linea"
        }
     },
    "POSTES_BT_BY_TRAFO": {
    "campos": [("G3E_FID", "LONG"), ("CODIGO", "TEXT"), ("CODIGO_OPERATIVO", "TEXT"),("MACRONORMA", "TEXT"),
               ("CIRCUITO", "TEXT"), ("REGION", "TEXT"), ("CODIGO_TRAFO", "TEXT"), ("NIVEL_TENSION", "TEXT"),
               ("MUNICIPIO", "TEXT"), ("UBICACION", "TEXT"), ("CONTRATO_INSTALACION", "TEXT"),
               ("CLASIFICACION_MERCADO", "TEXT"), ("FECHA_INSTALACION", "DATE"), ("OBSERVACIONES", "TEXT"),
               ("NORMA", "TEXT"), ("APOYO", "TEXT"), ("MATERIAL", "TEXT"), ("ALTURA", "DOUBLE"),
               ("TIPO_ADECUACION", "TEXT"), ("RESISTENCIA_KGF", "TEXT"), ("CODIGO2", "TEXT"),
               ("UC", "TEXT"), ("TIPO_RED", "TEXT"),
               ("COOR_GPS_LON", "DOUBLE"), ("COOR_GPS_LAT", "DOUBLE")],
    "etiqueta": None,
    "estilo": {
        "icon_href": r"D:\kmz_generator_project\Simbologia\POSTES_BT.png",
        "color": "ffff0000",
        "scale": 0.9,
        "tipo": "punto"
    }
},
"TRAFOS": {
    "campos": [
        ("NODO_TRANSFORM_V", "TEXT"), ("G3E_FID", "LONG"), ("ZONAID", "TEXT"),
        ("MUNICIPIO", "TEXT"), ("UBICACION", "TEXT"), ("CONTRATO_INSTALACION", "TEXT"),
        ("FECHA_OPERACION", "DATE"), ("NRO_TRANSFORMADOR_V", "TEXT"), ("FASES", "TEXT"),
        ("CIRCUITO", "TEXT"), ("REGION", "TEXT"), ("CODIGO", "TEXT"), ("FABRICANTE_TRAFO", "TEXT"),
        ("FECHA_FABRICACION", "DATE"), ("TIPO_SUBESTACION", "TEXT"),
        ("CLASIFICACION_MERCADO", "TEXT"), ("CAPACIDAD_NOMINAL", "TEXT"),
        ("OBSERVACIONES", "TEXT"), ("COOR_GPS_LON", "DOUBLE"), ("COOR_GPS_LAT", "DOUBLE")
    ],
    "etiqueta": "NODO_TRANSFORM_V",
    "estilo": {
        "icon_href": r"D:\kmz_generator_project\Simbologia\TRAFOS.png",
        "color": "ff7f7f00",
        "scale": 1.3,
        "tipo": "punto"
    }
},
"RED_BT_BY_TRAFO": {
    "campos": [("G3E_FID", "LONG"), ("CODIGO", "TEXT"), ("CODE_CONDUCTOR", "TEXT"),
               ("CODIGO_MAXIMO", "TEXT"),("CONTRATO_INSTALACION", "TEXT"), ("SUBREGION", "TEXT"),
               ("MUNICIPIO", "TEXT"), ("LONGITUD", "DOUBLE"), ("NODO_TRANSFORM_V", "TEXT"),
               ("LOCALIZACION", "TEXT"), ("CLASIFICACION_MERCADO", "TEXT"), ("CIRCUITO", "TEXT"), ("REGION", "TEXT"),
               ("FECHA_INSTALACION", "DATE"),("FASES", "TEXT")],
    "etiqueta": None,
    "estilo": {
        "color": "ffff0000",
        "width": 2.5,
        "tipo": "linea"
    }
}
}
# alias útiles (no mostrar como checkboxes en la interfaz principal)
entidades_config["TRAFOS_ALL"] = entidades_config["TRAFOS"]
entidades_config["POSTES_BT_BY_TRAFO"] = entidades_config["POSTES_BT"]
entidades_config["RED_BT_BY_TRAFO"] = entidades_config["RED_BT"]

# -------------------------
# Utilidades de color
# -------------------------
def setup_ui(self):
    # ... lo que ya tienes
    self.btn_export_pdf = QPushButton("Exportar PDF TRAFO", self)
    self.btn_export_pdf.clicked.connect(self.exportar_pdf_trafo)
    self.layout().addWidget(self.btn_export_pdf)

def exportar_pdf_trafo(self):
    circuito = self.comboBox_circuito.currentText()
    codigo = "TRAFO123"  # aquí lo tomas del query Oracle
    capacidad = "50"
    usuario = "UsuarioApp"

    meta = {
        "circuito": circuito,
        "codigo_trafo": codigo,
        "capacidad": capacidad,
        "usuario": usuario
    }

    tabla = [
        ["Campo", "Valor", "Extra"],
        ["CODIGO", codigo, ""],
        ["CIRCUITO", circuito, ""],
        ["CAPACIDAD (kVA)", capacidad, ""],
        ["NIVEL TENSIÓN", "13.2", ""],
        ["COORD_X", "-75.1234", ""],
        ["COORD_Y", "7.8901", ""],
        ["ESTADO", "OPERACION", ""],
    ]

    pdf_bytes = generar_pdf_trafo(meta, tabla)

    save_path, _ = QFileDialog.getSaveFileName(self, "Guardar PDF", f"trafo_{codigo}.pdf", "PDF Files (*.pdf)")
    if save_path:
        with open(save_path, "wb") as f:
            f.write(pdf_bytes)
        QMessageBox.information(self, "Éxito", f"PDF guardado en {save_path}")

#----------------------------------
def abgr_to_hex(abgr):
    """Convierte color KML 'AABBGGRR' -> '#RRGGBB' para mostrar en botones."""
    try:
        s = abgr.lower()
        s = s.replace("#", "")
        if len(s) == 8:
            # AABBGGRR -> RRGGBB = s[6:8]+s[4:6]+s[2:4]
            return "#" + s[6:8] + s[4:6] + s[2:4]
        elif len(s) == 6:
            return "#" + s[0:2] + s[2:4] + s[4:6]
    except Exception:
        pass
    return "#FF0000"

# -------------------------
# INTERFAZ
# -------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("KMZ Generator - Circuitos y Transformadores")
        self.setMinimumSize(820, 560)

        # Default folders / estado
        self.carpeta_salida = ""
        self.colores = {}        # {entidad: '#RRGGBB'}
        self.checkboxes = {}     # {entidad: QCheckBox}
        self.color_btns = {}     # {entidad: QPushButton}
        self.entidades_linea = [k for k,v in entidades_config.items() if v.get("estilo", {}).get("tipo")=="linea"]
        self.primary_entities = [k for k in entidades_config.keys() if not (k.endswith("_ALL") or k.endswith("_BY_TRAFO"))]

        # Tabs
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.tab_total = QWidget()
        self.tab_trafo = QWidget()
        self.tabs.addTab(self.tab_trafo, "Por Transformador (Trafo + BT)")
        self.tabs.addTab(self.tab_total, "Por Circuito (Total)")
        

        self._build_tab_total()
        self._build_tab_trafo()

        # Cargar inicial
        self.combo_regional_total.setCurrentIndex(0)
        self.actualizar_circuitos_total()
        # inicializar colores de linea
        for ent in self.entidades_linea:
            # si existe color en config, convertimos ABGR->#RRGGBB
            color_abgr = entidades_config.get(ent, {}).get("estilo", {}).get("color")
            self.colores[ent] = abgr_to_hex(color_abgr) if color_abgr else "#FF0000"
            if ent in self.color_btns:
                self.color_btns[ent].setStyleSheet(f"background-color: {self.colores[ent]}")

    # -------------------------
    # Construcción Tab Total
    # -------------------------
    def _build_tab_total(self):
        w = QWidget()
        layout = QVBoxLayout()
        form = QFormLayout()

        # Regional + circuito
        self.combo_regional_total = QComboBox()
        self.combo_regional_total.addItems(["AGUACHICA", "OCAÑA", "CUCUTA", "PAMPLONA", "TIBU"])
        self.combo_regional_total.currentTextChanged.connect(self.actualizar_circuitos_total)

        self.combo_circuito_total = QComboBox()
        form.addRow("Regional:", self.combo_regional_total)
        form.addRow("Circuito:", self.combo_circuito_total)

        # Nombre KMZ y carpeta
        self.input_nombre_total = QLineEdit()
        self.input_carpeta_total = QLineEdit()
        self.input_carpeta_total.setReadOnly(True)
        btn_folder_total = QPushButton("...")
        btn_folder_total.clicked.connect(self.seleccionar_carpeta_total)
        h_folder = QHBoxLayout()
        h_folder.addWidget(self.input_carpeta_total)
        h_folder.addWidget(btn_folder_total)
        form.addRow("Nombre KMZ:", self.input_nombre_total)
        form.addRow("Carpeta salida:", h_folder)

        # Checkboxes (scroll area si son muchos)
        group = QGroupBox("Entidades")
        vbox_ent = QVBoxLayout()
        scroll = QScrollArea()
        scw = QWidget()
        sc_layout = QVBoxLayout()

        for ent in self.primary_entities:
            chk = QCheckBox(ent)
            self.checkboxes[ent] = chk
            sc_layout.addWidget(chk)

            # si es linea, añadimos boton color
            if ent in self.entidades_linea:
                btn = QPushButton("Color")
                btn.setFixedWidth(60)
                btn.clicked.connect(lambda _, e=ent: self.cambiar_color(e))
                self.color_btns[ent] = btn
                sc_layout.addWidget(btn)

        scw.setLayout(sc_layout)
        scroll.setWidget(scw)
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(220)

        vbox_ent.addWidget(scroll)
        group.setLayout(vbox_ent)
        form.addRow(group)

        # Usar altura en redes
        self.checkbox_altura = QCheckBox("Usar altura en redes")
        form.addRow(self.checkbox_altura)

        # Boton exportar total
        btn_export_total = QPushButton("Exportar KMZ Total")
        btn_export_total.clicked.connect(self.exportar_total_clicked)
        form.addRow(btn_export_total)

        layout.addLayout(form)
        w.setLayout(layout)
        self.tab_total.setLayout(QVBoxLayout())
        self.tab_total.layout().addWidget(w)

    # -------------------------
    # Construcción Tab Trafo
    # -------------------------
    def _build_tab_trafo(self):
        w = QWidget()
        layout = QVBoxLayout()
        self.tab_trafo.setStyleSheet("""
            QWidget {
                background-image: url("D:\kmz_generator_project\Simbologia\FONDO1.jpg");
                background-repeat: no-repeat;
                background-position: center;
                background-attachment: fixed;
                background-color: #f0f0f0; /* gris claro, limpio */
            }
            QLabel, QComboBox, QPushButton, QLineEdit {
                font-weight: bold;
                color: #222222; /* gris oscuro para texto */
                background-color: transparent;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 4px;
            }
        """)
        form = QFormLayout()
        # Logo CENS
        label_icon = QLabel()
        pixmap_icon = QPixmap("D:\2025\kmz_generator_project\Simbologia\CENS_EPM.jpg")
        if not pixmap_icon.isNull():
            pixmap_icon = pixmap_icon.scaledToHeight(120, Qt.TransformationMode.SmoothTransformation)
            label_icon.setPixmap(pixmap_icon)
            label_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label_icon)

        # Regional + circuito
        self.combo_regional_trafo = QComboBox()
        self.combo_regional_trafo.addItems(["AGUACHICA", "OCAÑA", "CUCUTA", "PAMPLONA", "TIBU"])
        # Mantener sincronía con tab total: cuando cambie, actualizar los dos
        self.combo_regional_trafo.currentTextChanged.connect(self.actualizar_circuitos_total)
        self.combo_regional_trafo.currentTextChanged.connect(self.actualizar_circuitos_trafo)

        self.combo_circuito_trafo = QComboBox()
        self.combo_circuito_trafo.currentIndexChanged.connect(self.cargar_trafos)
        label_regional = QLabel("Regional:")
        label_regional.setStyleSheet("font-weight: bold; color: red;")
        form.addRow("Regional:", self.combo_regional_trafo)
        label_circuito = QLabel("Circuito:")
        label_circuito.setStyleSheet("font-weight: bold; color: red;")
        form.addRow("Circuito:", self.combo_circuito_trafo)

        # Combo trafos
        self.combo_trafo = QComboBox()
        label_trafo = QLabel("Transformador:")
        label_trafo.setStyleSheet("font-weight: bold; color: red;")
        form.addRow("Transformador:", self.combo_trafo)

        # Carpeta salida (usa la misma carpeta que total por conveniencia)
        self.input_carpeta_trafo = QLineEdit()
        self.input_carpeta_trafo.setReadOnly(True)
        btn_folder_trafo = QPushButton("...")
        btn_folder_trafo.clicked.connect(self.seleccionar_carpeta_trafo)
        h_folder = QHBoxLayout()
        h_folder.addWidget(self.input_carpeta_trafo)
        h_folder.addWidget(btn_folder_trafo)
        form.addRow("Carpeta salida:", h_folder)

        # Botón generar KMZ trafo
        # Botón de color para RED_BT_BY_TRAFO
        btn_color_red_bt = QPushButton("Color RED_BT")
        btn_color_red_bt.setFixedWidth(100)
        btn_color_red_bt.clicked.connect(lambda: self.cambiar_color("RED_BT_BY_TRAFO"))
        self.color_btns["RED_BT_BY_TRAFO"] = btn_color_red_bt
        self.colores["RED_BT_BY_TRAFO"] = abgr_to_hex(entidades_config["RED_BT_BY_TRAFO"]["estilo"]["color"])
        btn_color_red_bt.setStyleSheet(f"background-color: {self.colores['RED_BT_BY_TRAFO']}")
        form.addRow("Color RED_BT:", btn_color_red_bt)
        btn_export_trafo = QPushButton("Generar KMZ Trafo + BT")
        btn_export_trafo.clicked.connect(self.exportar_trafo_clicked)
        form.addRow(btn_export_trafo)

        layout.addLayout(form)
        w.setLayout(layout)
        self.tab_trafo.setLayout(QVBoxLayout())
        self.tab_trafo.layout().addWidget(w)

    # -------------------------
    # Acciones UI
    # -------------------------
    def seleccionar_carpeta_total(self):
        carpeta = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta salida")
        if carpeta:
            self.input_carpeta_total.setText(carpeta)
            self.carpeta_salida = carpeta
            # propagar a tab trafo si está vacío
            if not self.input_carpeta_trafo.text():
                self.input_carpeta_trafo.setText(carpeta)

    def seleccionar_carpeta_trafo(self):
        carpeta = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta salida")
        if carpeta:
            self.input_carpeta_trafo.setText(carpeta)
            self.carpeta_salida = carpeta
            if not self.input_carpeta_total.text():
                self.input_carpeta_total.setText(carpeta)

    def cambiar_color(self, entidad):
        color = QColorDialog.getColor()
        if color.isValid():
            hex_color = color.name()  # '#RRGGBB'
            self.colores[entidad] = hex_color
            if entidad in self.color_btns:
                self.color_btns[entidad].setStyleSheet(f"background-color: {hex_color}")

    def actualizar_circuitos_total(self, _=None):
        """Actualiza combo de circuitos en tab total y copia a tab trafo."""
        regional = self.combo_regional_total.currentText().strip().upper()
        try:
            circuitos = obtener_circuitos(regional)
            self.combo_circuito_total.clear()
            if circuitos:
                # si obtener_circuitos devuelve filas, extraer primer campo
                if isinstance(circuitos[0], (list, tuple)):
                    items = [row[0] for row in circuitos]
                else:
                    items = circuitos
                self.combo_circuito_total.addItems(items)
                # también actualizar tab trafo
                if self.combo_regional_trafo.currentText().strip().upper() == regional:
                    self.combo_circuito_trafo.clear()
                    self.combo_circuito_trafo.addItems(items)
            else:
                self.combo_circuito_total.addItem("⚠ No se encontraron circuitos")
        except Exception as e:
            print("Error actualizando circuitos:", e)

    def actualizar_circuitos_trafo(self, _=None):
        """Mantiene sincronía cuando cambian regional en tab trafo."""
        # simplemente reutiliza total: copia los mismos circuitos si regional coincide
        regional = self.combo_regional_trafo.currentText().strip().upper()
        try:
            circuitos = obtener_circuitos(regional)
            self.combo_circuito_trafo.clear()
            if circuitos:
                if isinstance(circuitos[0], (list, tuple)):
                    items = [row[0] for row in circuitos]
                else:
                    items = circuitos
                self.combo_circuito_trafo.addItems(items)
            else:
                self.combo_circuito_trafo.addItem("⚠ No se encontraron circuitos")
        except Exception as e:
            print("Error actualizando circuitos (trafo):", e)

    def cargar_trafos(self):
        circuito = self.combo_circuito_trafo.currentText()
        regional = self.combo_regional_trafo.currentText().strip().upper()
        if not circuito or circuito.startswith("⚠"):
            return
        try:
            datos, cols = obtener_trafos_por_circuito(circuito, regional)
            # admitir dos formatos: lista simple o rows+cols
            if datos is None:
                self.combo_trafo.clear()
                self.combo_trafo.addItem("⚠ Error al obtener trafos")
                return
            if len(datos) == 0:
                self.combo_trafo.clear()
                self.combo_trafo.addItem("⚠ No hay trafos para este circuito")
                return
            # si datos son filas (tupla/list), extraer primer campo
            if isinstance(datos[0], (list, tuple)):
                trafos = [str(row[0]) for row in datos]
            else:
                trafos = [str(x) for x in datos]
            self.combo_trafo.clear()
            self.combo_trafo.addItems(trafos)
        except Exception as e:
            print("Error cargando trafos:", e)
            self.combo_trafo.clear()
            self.combo_trafo.addItem("⚠ Error cargando trafos")

    # -------------------------
    # Exportaciones
    # -------------------------
    def construir_estilos(self):
        """Construye diccionario de estilos a pasar a exportar_kmz_por_trafo
           y a la exportación total. No muta entidades_config original."""
        estilos = {}
        for ent, cfg in entidades_config.items():
            # copia segura
            estilo_orig = cfg.get("estilo", {}) or {}
            estilo = copy.deepcopy(estilo_orig)
            # si existe color personalizado en self.colores (para lineas), lo aplicamos
            if ent in self.colores:
                estilo["color"] = self.colores[ent]
            else:
                # si estilo tiene color en ABGR, convertimos a #RRGGBB
                c = estilo.get("color")
                if c:
                    estilo["color"] = abgr_to_hex(c)
            estilos[ent] = estilo
        return estilos

    def exportar_total_clicked(self):
        circuito = self.combo_circuito_total.currentText()
        regional = self.combo_regional_total.currentText().strip().upper()
        nombre = self.input_nombre_total.text().strip()
        carpeta = self.input_carpeta_total.text().strip() or self.carpeta_salida
        usar_altura = self.checkbox_altura.isChecked()

        if not carpeta:
            QMessageBox.warning(self, "Falta carpeta", "Seleccione una carpeta de salida.")
            return
        if not nombre:
            QMessageBox.warning(self, "Falta nombre", "Ingrese un nombre para el KMZ.")
            return
        if not circuito or circuito.startswith("⚠"):
            QMessageBox.warning(self, "Falta circuito", "Seleccione un circuito válido.")
            return

        kml = simplekml.Kml()
        estilos = self.construir_estilos()

        # Iterar checkboxes marcados
        for entidad, chk in self.checkboxes.items():
            if not chk.isChecked():
                continue
            estilo = estilos.get(entidad, {})
            try:
                if entidades_config[entidad].get("estilo", {}).get("tipo") == "linea":
                    exportar_kmz_lineas(
                        entidad=entidad,
                        circuito=circuito,
                        regional=regional,
                        estilo=estilo,
                        usar_altura=usar_altura,
                        entidades_config=entidades_config,
                        kml=kml,
                        codigo_trafo=None
                    )
                else:
                    exportar_kmz_puntos(
                        entidad=entidad,
                        circuito=circuito,
                        regional=regional,
                        estilo=estilo,
                        entidades_config=entidades_config,
                        kml=kml,
                        codigo_trafo=None
                    )
            except Exception as e:
                print(f"Error exportando {entidad}: {e}")

        # Guardar KMZ unificado
        try:
            salida = os.path.join(carpeta, limpiar_nombre(nombre) + ".kmz")
            kml.savekmz(salida)
            QMessageBox.information(self, "KMZ generado", f"KMZ unificado guardado en:\n{salida}")
        except Exception as e:
            QMessageBox.critical(self, "Error guardando KMZ", str(e))

    def exportar_trafo_clicked(self):
        circuito = self.combo_circuito_trafo.currentText()
        regional = self.combo_regional_trafo.currentText().strip().upper()
        codigo_trafo = self.combo_trafo.currentText()
        carpeta = self.input_carpeta_trafo.text().strip() or self.carpeta_salida

        if not carpeta:
            QMessageBox.warning(self, "Falta carpeta", "Seleccione una carpeta de salida.")
            return
        if not circuito or circuito.startswith("⚠"):
            QMessageBox.warning(self, "Falta circuito", "Seleccione un circuito válido.")
            return
        if not codigo_trafo or codigo_trafo.startswith("⚠"):
            QMessageBox.warning(self, "Falta trafo", "Seleccione un transformador válido.")
            return

        estilos = self.construir_estilos()
        # preparar un dict con las claves que exportar_kmz_por_trafo espera (TRAFOS, POSTES_BT_BY_TRAFO, RED_BT_BY_TRAFO)
        estilos_por_trafo = {
            "TRAFOS": estilos.get("TRAFOS", {}),
            "POSTES_BT_BY_TRAFO": estilos.get("POSTES_BT_BY_TRAFO", estilos.get("POSTES_BT", {})),
            "RED_BT_BY_TRAFO": estilos.get("RED_BT_BY_TRAFO", estilos.get("RED_BT", {}))
        }

        try:
            ruta = exportar_kmz_por_trafo(
                salida=os.path.join(carpeta, f"TRAFO_{codigo_trafo}.kmz"),
                codigo_trafo=codigo_trafo,
                circuito=circuito,
                estilos=estilos_por_trafo,  # ← este debe estar incluido
                entidades_config=entidades_config,  # ← este también
                regional=regional
            )
            if ruta:
                QMessageBox.information(self, "KMZ Trafo", f"KMZ generado:\n{ruta}")
            else:
                QMessageBox.warning(self, "Sin resultados", "No se generó KMZ (quizá no hay datos para ese trafo).")
        except Exception as e:
            QMessageBox.critical(self, "Error exportando trafo", str(e))

# -------------------------
# Lanzamiento
# -------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
